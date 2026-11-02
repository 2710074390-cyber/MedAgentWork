#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agreement.py — 评分者一致性统计（P3-S2，2026-11-02）

三个指标，各有各的用途，**不能互相替代**：

  加权 κ（quadratic weighted kappa）
      有序评分（0–3 分）的「扣除偶然一致后」的一致性。对「差 1 分」比「差 3 分」宽容。
      局限：只在两名评分者、同一组题上定义，边际分布极偏时 κ 会失真（kappa paradox）。

  ICC(2,1)（two-way random, single measures）
      把「题」当随机效应、「评分者」当随机效应的方差分解，衡量单个评分者在单题上的
      可靠性。κ 只看一致与否，ICC 看的是方差里有多少来自「真差异」而不是「评分者差异」。

  Bland–Altman
      不看相关性，直接看「两人差多少」：偏倚（平均差）+ 95% 一致性界限。
      能抓出「一致地一个偏高一个偏低」——这种情况 κ 和 ICC 都可能不报警。

实现约束：本仓库默认解释器无 numpy，全部用纯 Python 实现（方差分解手算）。

用法：
  python scripts/agreement.py --ratings reports/calibration/ratings_50_20261102.json
  python scripts/agreement.py --ratings r.json --out reports/calibration/agreement_20261102.json

输入格式：
  {
    "meta": {"dims": ["D1", ...], "raters": ["r1", "r2"]},
    "items": [
      {"qid": "Q1", "scores": {"r1": {"D1": 2, "D2": 3}, "r2": {"D1": 3, "D2": 3}}},
      ...
    ]
  }

**只有一名评分者时必须返回 BLOCKED**：不许用「同一人两轮」冒充专家间一致性，
除非显式传 --intra 并在报告里标明这是 intra-rater（自身一致性），不是 inter-rater。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent


# ── 加权 κ ──────────────────────────────────────────────────

def quadratic_weights(k: int) -> list[list[float]]:
    """w_ij = (i-j)^2 / (k-1)^2 —— 有序类别，差 1 格的惩罚是差 3 格的 1/9。"""
    if k < 2:
        return [[0.0]]
    denom = (k - 1) ** 2
    return [[((i - j) ** 2) / denom for j in range(k)] for i in range(k)]


def weighted_kappa(a: list[int], b: list[int], levels: int = 4) -> dict:
    """两名评分者对同一组有序类别评分的二次加权 κ。"""
    if len(a) != len(b):
        raise ValueError("两名评分者的题目数不一致")
    n = len(a)
    if n == 0:
        return {"kappa": None, "n": 0, "observed": None, "expected": None, "levels": levels}
    if levels < 2:
        raise ValueError("levels 必须 ≥ 2")
    obs = [[0] * levels for _ in range(levels)]
    for x, y in zip(a, b):
        if not (0 <= x < levels and 0 <= y < levels):
            raise ValueError(f"评分超界：{x},{y}（levels={levels}）")
        obs[x][y] += 1
    row = [sum(r) for r in obs]
    col = [sum(obs[i][j] for i in range(levels)) for j in range(levels)]
    w = quadratic_weights(levels)
    num = sum(w[i][j] * obs[i][j] for i in range(levels) for j in range(levels))
    den = sum(w[i][j] * row[i] * col[j] / n for i in range(levels) for j in range(levels))
    kappa = None if den == 0 else 1 - num / den
    po = sum(obs[i][i] for i in range(levels)) / n
    pe = sum(row[i] * col[i] for i in range(levels)) / (n * n)
    return {
        "kappa": None if kappa is None else round(kappa, 4),
        "n": n,
        "observed_agreement": round(po, 4),
        "expected_agreement": round(pe, 4),
        "levels": levels,
        "degenerate": den == 0,
        "note": "分母为 0：两人评分完全集中在同一格，κ 无定义（不是满分）" if den == 0 else "",
    }


def _bootstrap_kappa_ci(a, b, levels, iters: int = 1000, alpha: float = 0.05, seed: int = 20261102):
    """百分位 bootstrap 95% CI。纯 Python 的 random 足够，无需 numpy。"""
    import random

    rnd = random.Random(seed)
    n = len(a)
    if n < 5 or iters <= 0:
        return None
    vals = []
    for _ in range(iters):
        idx = [rnd.randrange(n) for _ in range(n)]
        try:
            k = weighted_kappa([a[i] for i in idx], [b[i] for i in idx], levels)["kappa"]
        except ValueError:
            continue
        if k is not None:
            vals.append(k)
    if len(vals) < max(20, iters // 5):
        return None
    vals.sort()
    lo = vals[int((alpha / 2) * len(vals))]
    hi = vals[int((1 - alpha / 2) * len(vals)) - 1]
    return [round(lo, 4), round(hi, 4)]


# ── ICC(2,1) ────────────────────────────────────────────────

def icc_2_1(matrix: list[list[float]]) -> dict:
    """ICC(2,1)：two-way random effects, single rater, absolute agreement.

    matrix: n_subjects × k_raters（每题一行，每名评分者一列）
    公式：ICC = (MSR - MSE) / (MSR + (k-1)MSE + k(MSC - MSE)/n)
      MSR = 题间均方（between-targets）
      MSC = 评分者间均方（between-raters）
      MSE = 残差均方
    """
    n = len(matrix)
    if n == 0:
        return {"icc": None, "n": 0, "k": 0}
    k = len(matrix[0])
    if k < 2:
        return {"icc": None, "n": n, "k": k, "note": "只有 1 名评分者，ICC 无定义（不是 1.0）"}
    for row in matrix:
        if len(row) != k:
            raise ValueError("matrix 行长度不一致")

    grand = sum(sum(r) for r in matrix) / (n * k)
    row_means = [sum(r) / k for r in matrix]
    col_means = [sum(matrix[i][j] for i in range(n)) / n for j in range(k)]

    ss_total = sum((matrix[i][j] - grand) ** 2 for i in range(n) for j in range(k))
    ss_row = k * sum((m - grand) ** 2 for m in row_means)
    ss_col = n * sum((m - grand) ** 2 for m in col_means)
    ss_err = ss_total - ss_row - ss_col

    df_row, df_col, df_err = n - 1, k - 1, (n - 1) * (k - 1)
    if df_row <= 0 or df_err <= 0:
        return {"icc": None, "n": n, "k": k, "note": "自由度不足"}
    ms_row = ss_row / df_row
    ms_col = ss_col / df_col if df_col else 0.0
    ms_err = ss_err / df_err

    denom = ms_row + (k - 1) * ms_err + k * (ms_col - ms_err) / n
    icc = None if denom == 0 else (ms_row - ms_err) / denom
    return {
        "icc": None if icc is None else round(icc, 4),
        "n": n, "k": k,
        "ms_row": round(ms_row, 4), "ms_col": round(ms_col, 4), "ms_err": round(ms_err, 4),
    }


# ── Bland–Altman ────────────────────────────────────────────

def bland_altman(x: list[float], y: list[float]) -> dict:
    """差值 d = x − y；偏倚 = mean(d)；95% 一致性界限 = 偏倚 ± 1.96·SD(d)。"""
    if len(x) != len(y):
        raise ValueError("两组评分数不一致")
    n = len(x)
    if n < 2:
        return {"bias": None, "sd": None, "loa_lower": None, "loa_upper": None, "n": n}
    d = [a - b for a, b in zip(x, y)]
    mean_d = sum(d) / n
    sd = math.sqrt(sum((v - mean_d) ** 2 for v in d) / (n - 1))
    return {
        "bias": round(mean_d, 4),
        "sd": round(sd, 4),
        "loa_lower": round(mean_d - 1.96 * sd, 4),
        "loa_upper": round(mean_d + 1.96 * sd, 4),
        "n": n,
        "outside_loa": sum(1 for v in d if abs(v - mean_d) > 1.96 * sd),
    }


# ── 报告 ────────────────────────────────────────────────────

THRESHOLD_KAPPA = 0.61   # AC-P3-02：关键维度 κ ≥ 0.61
THRESHOLD_ICC = 0.75     # AC-P3-06（阶段 1）


def _levels_for(scores: list[int]) -> int:
    return max(4, (max(scores) + 1) if scores else 4)


def build_report(ratings: dict, intra: bool = False) -> dict:
    meta = ratings.get("meta") or {}
    items = ratings.get("items") or []
    raters = meta.get("raters") or []
    dims = meta.get("dims") or []

    # 从数据里补全 raters/dims，避免 meta 不全时静默算空
    if not raters:
        seen = []
        for it in items:
            for r in (it.get("scores") or {}):
                if r not in seen:
                    seen.append(r)
        raters = seen
    if not dims:
        seen_d = []
        for it in items:
            for sc in (it.get("scores") or {}).values():
                for d in sc:
                    if d not in seen_d:
                        seen_d.append(d)
        dims = seen_d

    usable = [it for it in items if all(r in (it.get("scores") or {}) for r in raters)]
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "scripts/agreement.py",
        "mode": "intra-rater" if intra else "inter-rater",
        "n_items_total": len(items),
        "n_items_complete": len(usable),
        "raters": raters,
        "dims": dims,
        "thresholds": {"kappa": THRESHOLD_KAPPA, "icc": THRESHOLD_ICC},
        "per_dim": [],
        "status": "BLOCKED",
    }

    if len(raters) < 2:
        report["status"] = "BLOCKED"
        report["reason"] = (
            f"只有 {len(raters)} 名评分者（{', '.join(raters) or '无'}），无法计算一致性。"
            "单评分者不得输出 κ —— 这是 AC-P3-02 的硬线：宁报 BLOCKED，不伪造数值。"
        )
        return report

    if len(usable) < 2:
        report["status"] = "BLOCKED"
        report["reason"] = f"完整双评的题目只有 {len(usable)} 道（<2），无法统计。"
        return report

    r1, r2 = raters[0], raters[1]
    for d in dims:
        try:
            a = [int(usable[i]["scores"][r1][d]) for i in range(len(usable))]
            b = [int(usable[i]["scores"][r2][d]) for i in range(len(usable))]
        except (KeyError, TypeError, ValueError):
            report["per_dim"].append({"dim": d, "status": "SKIP", "reason": "该维度存在缺失或非整数评分"})
            continue
        lv = _levels_for(a + b)
        kap = weighted_kappa(a, b, lv)
        kap["ci95"] = _bootstrap_kappa_ci(a, b, lv)
        icc = icc_2_1([[x, y] for x, y in zip(a, b)])
        ba = bland_altman([float(x) for x in a], [float(y) for y in b])
        k = kap["kappa"]
        report["per_dim"].append({
            "dim": d,
            "kappa": k,
            "kappa_ci95": kap["ci95"],
            "observed_agreement": kap["observed_agreement"],
            "icc": icc["icc"],
            "bland_altman": ba,
            "status": ("BLOCKED" if k is None else ("PASS" if k >= THRESHOLD_KAPPA else "BELOW")),
        })

    scored = [r for r in report["per_dim"] if r.get("status") in ("PASS", "BELOW")]
    report["status"] = "PASS" if scored and all(r["status"] == "PASS" for r in scored) else (
        "BELOW" if scored else "BLOCKED")
    report["low_dims"] = [r["dim"] for r in scored if r["status"] == "BELOW"]
    return report


def render_md(rep: dict) -> str:
    lines = [
        "# 评分者一致性报告", "",
        f"- 生成：{rep['generated_at']}",
        f"- 工具：`{rep['tool']}`　模式：**{rep['mode']}**",
        f"- 题量：完整双评 {rep['n_items_complete']} / 共 {rep['n_items_total']}",
        f"- 评分者：{', '.join(rep['raters']) or '无'}",
        f"- 结论：**{rep['status']}**",
        "",
    ]
    if rep.get("reason"):
        lines += [f"> {rep['reason']}", ""]
    if rep["per_dim"]:
        lines += [
            "| 维度 | 加权 κ | 95%CI | ICC(2,1) | 偏倚 | 95% 界限 | 结论 |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in rep["per_dim"]:
            ba = r.get("bland_altman") or {}
            lines.append(
                f"| {r['dim']} | {r.get('kappa')} | {r.get('kappa_ci95')} | {r.get('icc')} | "
                f"{ba.get('bias')} | [{ba.get('loa_lower')}, {ba.get('loa_upper')}] | {r['status']} |"
            )
        lines += [
            "",
            f"> 阈值：加权 κ ≥ {rep['thresholds']['kappa']}（AC-P3-02）；ICC ≥ {rep['thresholds']['icc']}（AC-P3-06，阶段 1）。",
        ]
    lines += [
        "",
        "---",
        "",
        "**口径说明**：κ 与 ICC 都不能替代专家判断，它们只回答「两名评分者是否一致」。",
        "两名评分者一致地都错，κ 依然是 1.0。因此一致性报告必须与「评分者是谁」一起读。",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="评分者一致性：加权 κ / ICC(2,1) / Bland–Altman")
    ap.add_argument("--ratings", required=True, help="评分 JSON（items[].scores{ rater: {dim: 0-3} }）")
    ap.add_argument("--out", default="", help="报告 JSON 输出")
    ap.add_argument("--md-out", default="", help="报告 Markdown 输出")
    ap.add_argument("--intra", action="store_true", help="标记为 intra-rater（同一评分者两轮）")
    args = ap.parse_args(argv)

    data = json.loads(Path(args.ratings).read_text(encoding="utf-8"))
    rep = build_report(data, intra=args.intra)
    rep["source"] = str(args.ratings)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.md_out:
        Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md_out).write_text(render_md(rep), encoding="utf-8")

    print(f"一致性（{rep['mode']}）: {rep['status']}")
    if rep.get("reason"):
        print(f"  {rep['reason']}")
    for r in rep["per_dim"]:
        print(f"  {r['dim']:<4} κ={r.get('kappa')} ICC={r.get('icc')} → {r['status']}")
    return 0 if rep["status"] in ("PASS", "BELOW", "BLOCKED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
