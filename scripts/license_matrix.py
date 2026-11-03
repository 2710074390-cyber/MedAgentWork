#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""license_matrix.py — 权利盘点（P8-S1，2026-11-02；仅盘点，不作发布门禁）

只做**盘点**，不做法律定性。判定"能不能发"是人的事；本工具只回答三件事：

  1. 这道题是不是真题（依据 question 自带标注，不靠猜）；
  2. 它的 license 状态是什么（有值 / unknown / 与来源矛盾）；
  3. 有没有留下授权凭证（license_note、来源锚点、真题 ID）。

输出逐题矩阵 + 按批次/来源/字段的汇总，unknown 单列（AC-P8-02）。

用法：
  python scripts/license_matrix.py
  python scripts/license_matrix.py --json reports/compliance/license_matrix_20261102.json \
                                   --md   reports/compliance/license_matrix_20261102.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
DEFAULT_GLOB = "最终产物/batch*/ALL_questions_FIXED.json"

REAL_TYPES = ("考研真题", "执业医师真题", "真题", "考研原题", "执医真题")
LICENSE_STATES = ("cleared", "public_noncommercial", "unknown", "restricted", "unclear")


def _rel(p: Path) -> str:
    """仓库内文件显示相对路径；仓库外的（如测试临时文件）原样显示。"""
    try:
        return str(p.relative_to(BASE)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def qid_of(q: dict, i: int) -> str:
    for k in ("question_id", "id", "qid"):
        v = q.get(k)
        if v not in (None, ""):
            return str(v)
    return f"#{i}"


def origin_of(q: dict) -> dict:
    """返回 {kind, source, year, ref, mode}：真题来源的机器可读投影。"""
    for key, kind in (("kaoyan_origin", "kaoyan"), ("zhiyi_origin", "zhiyi"), ("zhiyi_pdf_origin", "zhiyi_pdf")):
        v = q.get(key)
        if not v:
            continue
        if isinstance(v, str):
            return {"kind": kind, "source": v, "year": "", "ref": "", "mode": ""}
        if isinstance(v, dict):
            return {
                "kind": kind,
                "source": str(v.get("source") or v.get("source_id") or ""),
                "year": str(v.get("year") or ""),
                "ref": str(v.get("gs_id") or v.get("source_id") or ""),
                "mode": str(v.get("mode") or ""),
            }
    st = str(q.get("source_type") or "")
    if st in REAL_TYPES:
        return {"kind": "declared", "source": st, "year": "", "ref": "", "mode": ""}
    return {"kind": "original", "source": str(q.get("source_type") or "原创"), "year": "", "ref": "", "mode": ""}


def evidence_of(q: dict) -> list[str]:
    ev = []
    if q.get("license_note"):
        ev.append(f"license_note={q['license_note']}")
    if q.get("source_anchors"):
        ev.append(f"source_anchors×{len(q['source_anchors'])}")
    if q.get("source_anchor"):
        ev.append("source_anchor")
    if q.get("source_page"):
        ev.append(f"source_page={q['source_page']}")
    return ev


def scan(paths: list[Path]) -> tuple[list[dict], dict]:
    rows = []
    per_batch = defaultdict(lambda: Counter())
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        batch = next((part for part in p.parts[::-1] if part.startswith("batch")), p.parent.name)
        for i, q in enumerate(data):
            org = origin_of(q)
            lic = str(q.get("license") or "").strip()
            state = lic or "unknown"
            rows.append({
                "qid": qid_of(q, i),
                "batch": batch,
                "file": _rel(p),
                "type": str(q.get("type") or ""),
                "real": org["kind"] != "original",
                "origin_kind": org["kind"],
                "origin_source": org["source"],
                "year": org["year"],
                "origin_ref": org["ref"],
                "mode": org["mode"],
                "license": state,
                "license_known": bool(lic),
                "evidence": evidence_of(q),
                "public": None,  # 由 P8-S2 的公开风险清单回填
            })
            per_batch[batch]["total"] += 1
            per_batch[batch]["real"] += 1 if org["kind"] != "original" else 0
            per_batch[batch][f"license:{state}"] += 1

    real = [r for r in rows if r["real"]]
    covered = [r for r in real if r["license_known"]]
    summary = {
        "total": len(rows),
        "real_total": len(real),
        "original_total": len(rows) - len(real),
        "real_with_license": len(covered),
        "real_without_license": len(real) - len(covered),
        "real_license_coverage": round(len(covered) / len(real), 4) if real else 1.0,
        "license_states": dict(Counter(r["license"] for r in real)),
        "origin_kinds": dict(Counter(r["origin_kind"] for r in real)),
        "unknown_qids": [r["qid"] for r in real if not r["license_known"]],
        "per_batch": {k: dict(v) for k, v in per_batch.items()},
    }
    return rows, summary


def render_md(rows: list[dict], s: dict, paths: list[str]) -> str:
    lines = [
        "# 权利盘点 · license matrix（P8-S1）", "",
        f"- 生成：{datetime.now().isoformat(timespec='seconds')}",
        f"- 工具：`scripts/license_matrix.py`",
        f"- 扫描文件：{len(paths)} 个批次产物（`{'`, `'.join(paths)}`）",
        f"- 题目总数：**{s['total']}**（真题 {s['real_total']} / 原创 {s['original_total']}）",
        f"- 真题 license 覆盖率：**{s['real_license_coverage']:.1%}**"
        f"（{s['real_with_license']}/{s['real_total']}）",
        "",
        "> **本表只盘点，不做法律定性。** 「license=unknown」不等于「不能发」，",
        "> 只表示仓库里没有记录授权状态，需要人工确认。",
        "",
        "## 1. 真题来源分布", "",
        "| 来源类型 | 题数 |", "|---|---|",
    ]
    for k, v in sorted(s["origin_kinds"].items(), key=lambda kv: -kv[1]):
        name = {"kaoyan": "考研真题", "zhiyi": "执业医师真题", "zhiyi_pdf": "执业医师历年真题（PDF 通道）",
                "declared": "仅声明 source_type", "original": "原创"}.get(k, k)
        lines.append(f"| {name} | {v} |")
    lines += ["", "## 2. 真题 license 状态", "", "| 状态 | 题数 |", "|---|---|"]
    for k, v in sorted(s["license_states"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{k}` | {v} |")
    lines += ["", "## 3. unknown 清单（AC-P8-02）", ""]
    lines += [
        "> **AC-P8-01「状态覆盖率 100%」有两种读法，必须分开说：**",
        f"> ① 状态标注率 = {s['real_total']}/{s['real_total']} = **100%**（unknown 也算一种状态）；",
        f"> ② 显式授权覆盖率 = {s['real_with_license']}/{s['real_total']} = **{s['real_license_coverage']:.1%}**。",
        "> 只有②能支撑「能不能发」的判断，①只是说明「没有被漏记成空白」。",
        "> 本表按②报数，不拿①当达成。",
        "",
    ]
    if s["real_without_license"] == 0:
        lines.append("无：全部真题都记录了 license 状态。")
    else:
        lines += [f"共 **{s['real_without_license']}** 题未记录 license，逐题可追溯：", "",
                  "| qid | 批次 | 题型 | 来源 | 年份 |", "|---|---|---|---|---|"]
        for r in rows:
            if r["real"] and not r["license_known"]:
                lines.append(f"| `{r['qid']}` | {r['batch']} | {r['type']} | {r['origin_source'] or r['origin_kind']} | {r['year'] or '—'} |")
    lines += ["", "## 4. 按批次", "", "| 批次 | 题量 | 真题 | license 状态 |", "|---|---|---|---|"]
    for b, c in sorted(s["per_batch"].items()):
        st = "、".join(f"{k.split(':', 1)[1]} {v}" for k, v in c.items() if k.startswith("license:"))
        lines.append(f"| {b} | {c['total']} | {c['real']} | {st} |")
    lines += [
        "", "## 5. 口径与局限", "",
        "1. **真题判定依据题目自带标注**（`kaoyan_origin` / `zhiyi_origin` / `zhiyi_pdf_origin` / `source_type`）。",
        "   没有标注的题一律按原创处理——如果实际是真题，这是**漏检**，不是「已清权」。",
        "2. `license` 字段由生成端写入，本工具不复核其真实性；`public_noncommercial` 是否有法律效力，须由人判断。",
        "3. 授权凭证目前只有文本痕迹（`license_note`、来源锚点），**没有可核验的授权文件或合同编号**。",
        "   这是 P8-S4（provenance schema）要补的字段。",
        "4. 教师重点锚定（`keypoint_ref`）不是版权凭证，不能替代授权。",
        "",
        "---", "",
        "逐题明细见同名 JSON（`rows[]`，每行含 qid / 批次 / 来源 / license / 凭证）。",
        "本表只含题目 ID 与元数据，不含任何用户数据。",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="权利盘点（license matrix）")
    ap.add_argument("--glob", default=DEFAULT_GLOB)
    ap.add_argument("--json", default=str(BASE / "reports/compliance/license_matrix_20261102.json"))
    ap.add_argument("--md", default=str(BASE / "reports/compliance/license_matrix_20261102.md"))
    args = ap.parse_args(argv)

    paths = sorted(BASE.glob(args.glob))
    if not paths:
        print(f"[FAIL] 没有匹配 {args.glob} 的文件", file=sys.stderr)
        return 2
    rows, summary = scan(paths)
    rel_paths = [str(p.relative_to(BASE)).replace("\\", "/") for p in paths]

    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "scripts/license_matrix.py",
        "sources": rel_paths,
        "summary": summary,
        "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.md).write_text(render_md(rows, summary, rel_paths), encoding="utf-8")

    print(f"题目 {summary['total']}（真题 {summary['real_total']}）| "
          f"真题 license 覆盖 {summary['real_license_coverage']:.1%} | "
          f"unknown {summary['real_without_license']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
