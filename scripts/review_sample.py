#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""review_sample.py — 50 题抽检回填（P3-S1，2026-11-02）

为什么重新抽样，而不是直接用 `reports/人工抽检清单_50题_20260821.md`：
那份清单的 50 道题来自 batch004–batch027，**20/20 个来源文件在当前仓库中全部不存在**
（只剩 batch032–043、046）。拿不到原题就无法评分，硬填等于编造。
因此本工具从**现存批次**重新分层抽 50 题，并如实记录"这是新样本，不是原清单"。

评分口径（关键）：
  - 7 个维度里，D1–D7 全部由**机器可核规则**给出 0–3 分，每分都附可复核的证据；
  - 这是 **proxy（代理评分）**，不是专家判断。它只能回答"这一维有没有硬伤"，
    不能回答"这道题临床上是否站得住"；
  - 专家列恒为 `null` + `status=BLOCKED`（无专家资源）。**不得用机器分冒充专家分**。

用法：
  python scripts/review_sample.py                       # 默认从 batch043+046 抽 50
  python scripts/review_sample.py --n 50 --seed 20261102 --out ... --md-out ...
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
_SCRIPTS = BASE / "scripts"
for p in (str(BASE), str(_SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

DEFAULT_SOURCES = [
    BASE / "最终产物/batch043/ALL_questions_FIXED.json",
    BASE / "最终产物/batch046/ALL_questions_FIXED.json",
]

DIMS = [
    ("D1", "题干清晰度"), ("D2", "答案唯一性"), ("D3", "干扰项质量"),
    ("D4", "解析质量"), ("D5", "溯源可靠性"), ("D6", "难度标注"), ("D7", "概念标注"),
]
CRITICAL_DIMS = {"D2", "D3", "D5"}

PLACEHOLDER = ("待补", "略", "XXX", "xxx", "TODO", "TBD", "同上")


# ── 取字段 ─────────────────────────────────────────────────

def qid_of(q: dict, i: int = 0) -> str:
    for k in ("question_id", "id", "qid"):
        v = q.get(k)
        if v not in (None, ""):
            return str(v)
    return f"#{i}"


def stem_of(q: dict) -> str:
    for k in ("stem", "question", "question_text"):
        v = q.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def options_of(q: dict) -> dict:
    from validate.rules_batch import options

    return options(q)


def answer_of(q: dict) -> str:
    from validate.rules_batch import answer

    return answer(q)


def batch_of(path: Path) -> str:
    for part in path.parts[::-1]:
        if part.startswith("batch"):
            return part
    return path.parent.name


# ── 机器评分（每维 0–3，附证据）─────────────────────────────

def score_d1(q: dict) -> tuple[int, str]:
    stem = stem_of(q)
    if not stem:
        return 0, "题干为空"
    if len(stem) < 10:
        return 1, f"题干仅 {len(stem)} 字，信息量不足"
    for w in PLACEHOLDER:
        if w in stem:
            return 1, f"题干含占位词「{w}」"
    polarity = str(q.get("polarity") or "").lower()
    if polarity in ("negative", "反选"):
        cues = q.get("negative_cues")
        has_cue = any(k in stem for k in ("不属于", "不正确", "错误", "除外", "不是"))
        if not has_cue:
            return 1, "反选题但题干无显式反选词（易漏读）"
        if not cues:
            return 2, "反选词齐备，但 v2.2 的 negative_cues 字段未填"
    ends_ok = stem.endswith(("？", "?", "：", ":")) or "下列" in stem or "最" in stem
    return (3, "题干完整、无占位词、提问明确") if ends_ok else (2, "题干完整但提问方式不够明确")


def score_d2(q: dict, rule_hits: dict) -> tuple[int, str]:
    opts = options_of(q)
    ans = answer_of(q)
    if not opts:
        return 0, "无选项"
    if not ans:
        return 0, "缺答案字段"
    if len(ans) > 1 and str(q.get("type")) not in ("X", "多选"):
        return 1, f"单选题答案出现多个字母（{ans}）"
    if ans not in opts and len(ans) == 1:
        return 0, f"答案 {ans} 不在选项集合内"
    if "R1" in rule_hits:
        return 1, "命中 R1 禁止项（以上都是/绝对化用语），答案可被排除法猜出"
    if len(opts) < 4:
        return 1, f"选项仅 {len(opts)} 个，不足以构成唯一答案"
    return 3, f"答案 {ans} 在选项内，选项数 {len(opts)}，未命中 R1"


def score_d3(q: dict, rule_hits: dict) -> tuple[int, str]:
    distractor_rules = [r for r in ("R2", "R3", "R5", "R6", "R8", "R12", "R13") if r in rule_hits]
    mech = q.get("distractor_mechanism")
    n_fail = len(distractor_rules)
    if n_fail == 0:
        base = 3
        txt = "干扰项未命中长度/截断/结构类规则"
    elif n_fail == 1:
        base, txt = 2, f"命中 {distractor_rules[0]}"
    elif n_fail == 2:
        base, txt = 1, f"命中 {'、'.join(distractor_rules)}"
    else:
        base, txt = 0, f"命中 {'、'.join(distractor_rules)}（{n_fail} 类）"
    lv = q.get("learning_value") or {}
    tagged = sum(1 for p in (lv.get("per_option") or [])
                 if isinstance(p, dict) and p.get("truth") is False and p.get("distractor_mechanism"))
    if tagged:
        return min(3, base + 1), txt + f"；机制标签 {tagged} 项"
    return base, txt + "；无机制标签（schema<2.2，HC-29 未覆盖）"


def score_d4(q: dict, lv_item: dict) -> tuple[int, str]:
    fails = [i for i in (lv_item.get("issues") or []) if i.get("rule") in ("R17", "R14", "ANSWER")]
    if not fails:
        return 3, "解析齐全（rationale≥60字、逐项 why≥20字、takeaway≥30字）"
    if len(fails) == 1:
        return 2, f"1 处解析缺陷：{fails[0]['detail'][:40]}"
    if len(fails) == 2:
        return 1, f"2 处解析缺陷"
    return 0, f"{len(fails)} 处解析缺陷（解析不完整或与答案不一致）"


def score_d5(q: dict, lv_item: dict) -> tuple[int, str]:
    anchor = str(lv_item.get("anchor_status") or "")
    sq = str(lv_item.get("source_quote_status") or "")
    if anchor == "verified" and sq == "exact" and lv_item.get("quote_supported"):
        return 3, "锚点 verified + 引文 exact 且逐字命中"
    if anchor == "verified" and sq in ("exact", "paraphrase"):
        return 2, f"锚点 verified，引文 {sq}（未做逐字核验）"
    if sq in ("missing", "mismatch") or anchor in ("missing", "mismatch"):
        return 0, f"锚点 {anchor or '空'} / 引文 {sq or '空'}，无法溯源"
    return 1, f"锚点 {anchor or '空'} / 引文 {sq or '空'}，仅部分可核"


def score_d6(q: dict) -> tuple[int, str]:
    tier = q.get("difficulty_tier")
    steps = q.get("step_count")
    if tier and isinstance(steps, int):
        expect = {"L1": (1, 1), "L2": (1, 2), "L3": (2, 3), "L4": (3, 8)}.get(str(tier), (1, 8))
        if expect[0] <= steps <= expect[1]:
            return 3, f"{tier} + {steps} 步，层级与步数一致"
        return 2, f"{tier} 与 {steps} 步不匹配（期望 {expect[0]}–{expect[1]} 步）"
    if tier:
        return 2, f"有 {tier} 但缺 step_count"
    legacy = q.get("difficulty")
    if q.get("difficulty_index") is not None:
        return 0, f"只有已弃用的 difficulty_index（{q['difficulty_index']}，LLM 主观估值，不可复核）"
    if legacy not in (None, ""):
        return 0, f"只有自由文本 difficulty=「{legacy}」，不是可校验的结构字段"
    return 0, "无难度标注（既无 v2.2 结构字段，也无历史估值字段）"


def score_d7(q: dict, concept_result: tuple) -> tuple[int, str]:
    fails, warns = concept_result
    if not fails and not warns:
        return 3, "概念标注齐全（primary 唯一、条数达标、evidence 具体）"
    if not fails:
        return 2, f"{len(warns)} 条告警：{warns[0][:40]}"
    return 1, f"{len(fails)} 条硬缺陷：{fails[0][:40]}"


# ── 抽样 ───────────────────────────────────────────────────

def load_pool(paths: list[Path]) -> list[dict]:
    pool = []
    for p in paths:
        if not p.exists():
            print(f"  ⚠️ 跳过不存在的来源：{p}", file=sys.stderr)
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for i, q in enumerate(data):
            q = dict(q)
            q["_source"] = str(p.relative_to(BASE)) if str(p).startswith(str(BASE)) else str(p)
            q["_batch"] = batch_of(p)
            q["_qid"] = qid_of(q, i)
            pool.append(q)
    return pool


def stratified_sample(pool: list[dict], n: int, seed: int) -> list[dict]:
    """按 (batch, type) 分层，按比例分配后再补零头；种子固定 → 可复现。"""
    rnd = random.Random(seed)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for q in pool:
        groups[(q["_batch"], str(q.get("type") or "?"))].append(q)
    for g in groups.values():
        rnd.shuffle(g)

    total = len(pool)
    quota = {k: max(1, round(len(v) / total * n)) for k, v in groups.items()}
    while sum(quota.values()) > n:
        k = max(quota, key=lambda x: quota[x])
        quota[k] -= 1
    keys = sorted(groups)
    while sum(quota.values()) < n:
        k = max(keys, key=lambda x: len(groups[x]) - quota[x])
        quota[k] += 1

    picked = []
    for k in keys:
        picked.extend(groups[k][:quota[k]])
    return picked[:n]


# ── 主流程 ─────────────────────────────────────────────────

def evaluate(items: list[dict]) -> list[dict]:
    from validate.engine import validate_questions
    from check_learning_value import check_item
    import check_source_concepts as csc

    normalized = []
    for q in items:
        normalized.append({
            "id": q["_qid"], "type": q.get("type") or "A1",
            "question": stem_of(q), "options": options_of(q),
            "answer": answer_of(q),
        })
    by_q, _summary = validate_questions(normalized, mode="full")

    out = []
    for q in items:
        qid = q["_qid"]
        hits = set()
        for it in (by_q.get(qid) or []):
            if isinstance(it, dict):
                hits.add(str(it.get("rule")))
        lv_item = check_item(q)
        concept = csc.check_question(q)

        s = {}
        s["D1"] = score_d1(q)
        s["D2"] = score_d2(q, hits)
        s["D3"] = score_d3(q, hits)
        s["D4"] = score_d4(q, lv_item)
        s["D5"] = score_d5(q, lv_item)
        s["D6"] = score_d6(q)
        s["D7"] = score_d7(q, concept)

        out.append({
            "qid": qid, "batch": q["_batch"], "source": q["_source"],
            "type": q.get("type"), "stem_head": stem_of(q)[:50],
            "scores": {k: v[0] for k, v in s.items()},
            "evidence": {k: v[1] for k, v in s.items()},
            "machine_total": sum(v[0] for v in s.values()),
            "core_total": sum(s[d][0] for d in ("D1", "D2", "D3", "D4", "D5")),
            "critical_pass": all(s[d][0] >= 2 for d in CRITICAL_DIMS),
            "expert_score": None,
            "expert_status": "BLOCKED",
            "expert_blocked_reason": "无专家资源（阶段 0）：不得以机器代理分替代专家评分",
        })
    return out


def render_md(rows: list[dict], meta: dict) -> str:
    head = [
        "# 50 题抽检回填（P3-S1）", "",
        f"- 生成：{meta['generated_at']}",
        f"- 工具：`scripts/review_sample.py`",
        f"- 样本：**{len(rows)} 题**，来自 {meta['pool_size']} 题池（{', '.join(meta['sources'])}）",
        f"- 分层：按（批次 × 题型）比例分配，种子 `{meta['seed']}`，可复现",
        f"- 专家终评：**BLOCKED** —— 无专家资源。本表**不含任何专家评分**。",
        "",
        "> **这份表不是原清单的回填。** `reports/人工抽检清单_50题_20260821.md` 的 50 道题来自",
        "> batch004–batch027，这 20 个来源文件在当前仓库中全部不存在（详见 `review50_20261102_blocked.md`）。",
        "> 硬填会变成编造，因此重新抽样，并把「换了样本」写在最前面。",
        "",
        "## 评分口径",
        "",
        "D1–D7 全部由机器规则给出 0–3 分，每分附可复核证据。这是 **proxy 代理评分**：",
        "能回答「这一维有没有硬伤」，不能回答「这道题临床上是否站得住」。",
        "关键维度 **D2 答案唯一性 / D3 干扰项质量 / D5 溯源可靠性** 任一 <2 分即 `critical_fail`。",
        "",
        "> ⚠️ **D6/D7 是版本绑定维度，不是题目质量维度。** 本样本来自 schema 2.0 批次",
        "> （batch043/046 均在 HC-27、P2-S1 之前落地），因此**结构上不可能**有 `difficulty_tier`/",
        "> `step_count`/`concepts`，D6 恒 0、D7 恒 1。这两维的低分反映的是「字段还没落地」，",
        "> **不是**「这些题难度标注乱写、概念标错」。把它们与 D1–D5 的分数直接相加会低估题目质量，",
        "> 这也是为什么本报告同时给出「关键维度」列，而不只看合计。",
        "",
        "## 明细",
        "",
        "| # | qid | 批次 | 题型 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | 机器合计 | 关键维度 | 专家评 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        sc = r["scores"]
        head.append(
            f"| {i} | `{r['qid']}` | {r['batch']} | {r['type']} | "
            + " | ".join(str(sc[d]) for d, _ in DIMS)
            + f" | {r['machine_total']}/21 | {'PASS' if r['critical_pass'] else '**FAIL**'} | BLOCKED |"
        )
    dist = Counter(r["machine_total"] for r in rows)
    tail = [
        "", "## 汇总", "",
        f"- 机器合计均分：**{sum(r['machine_total'] for r in rows) / max(1, len(rows)):.1f}/21**",
        f"- 内容维度（D1–D5）均分：**{sum(r['core_total'] for r in rows) / max(1, len(rows)):.1f}/15**"
        " ← 与版本无关、可比的口径",
        f"- 关键维度不达标：**{sum(1 for r in rows if not r['critical_pass'])}/{len(rows)}**",
        f"- 各维均分：" + "、".join(
            f"{d} {sum(r['scores'][d] for r in rows) / max(1, len(rows)):.2f}" for d, _ in DIMS),
        f"- 分数分布：{dict(sorted(dist.items()))}",
        "",
        "## 证据（节选）",
        "",
    ]
    for r in rows[:10]:
        tail.append(f"**{r['qid']}**（{r['batch']}）")
        for d, name in DIMS:
            tail.append(f"- {d} {name}：**{r['scores'][d]}** — {r['evidence'][d]}")
        tail.append("")
    tail += [
        "---", "",
        "来源文件与逐题证据见 `reports/calibration/review50_20261102.json`。",
        "本表只含题目 ID、题号与规则判定，不含任何用户数据。",
        "",
    ]
    return "\n".join(head + tail)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="50 题抽检回填（机器代理评分 + 专家 BLOCKED）")
    ap.add_argument("--sources", nargs="*", default=[str(p) for p in DEFAULT_SOURCES])
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20261102)
    ap.add_argument("--out", default=str(BASE / "reports/calibration/review50_20261102.json"))
    ap.add_argument("--md-out", default=str(BASE / "reports/calibration/review50_20261102.md"))
    args = ap.parse_args(argv)

    paths = [Path(s) if Path(s).is_absolute() else BASE / s for s in args.sources]
    pool = load_pool(paths)
    if not pool:
        print("[FAIL] 题池为空，检查 --sources", file=sys.stderr)
        return 2
    picked = stratified_sample(pool, args.n, args.seed)
    rows = evaluate(picked)

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "scripts/review_sample.py",
        "seed": args.seed,
        "requested": args.n,
        "pool_size": len(pool),
        "sources": [str(p.relative_to(BASE)) if str(p).startswith(str(BASE)) else str(p) for p in paths],
        "dims": [{"id": d, "name": n} for d, n in DIMS],
        "critical_dims": sorted(CRITICAL_DIMS),
        "expert_status": "BLOCKED",
        "expert_blocked_reason": "无专家资源（阶段 0）；禁止以机器代理分冒充专家评分",
        "scoring_note": "D1–D7 为机器规则代理分（0–3），非专家判断，不能作为 κ 的评分者之一",
    }
    report = {"meta": meta, "items": rows}

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.md_out).write_text(render_md(rows, meta), encoding="utf-8")

    print(f"抽样 {len(rows)} 题（池 {len(pool)}）→ {args.out}")
    print(f"  机器均分 {sum(r['machine_total'] for r in rows) / len(rows):.1f}/21 | "
          f"关键维度不达标 {sum(1 for r in rows if not r['critical_pass'])}/{len(rows)} | 专家评 BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
