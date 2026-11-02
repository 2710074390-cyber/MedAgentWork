"""
rules_batch.py — 批次级规则 X1 / X2 / X6 + 结构字段覆盖率（P2-S3，2026-11-02）

与 R1–R13 的区别：R 系列逐题判定，X 系列**只在整批上看分布**——
单题永远看不出「正确答案偏向 B」「正确项总是最长」「错误认知从不复用」，
这三类缺陷必须批级统计才能暴露。

规则口径（工作指令 §1.4 P2-S3）：
  X1 答案字母分布     每个字母（单选）占 15%–30%
  X2 唯一最长         正确选项是「唯一最长项」的题 ≤ 30%
  X6 错误认知复用     同一 misconception_id 被 ≥2 题使用，其占全部干扰项 ≥ 20%
  S-STRUCT 结构覆盖   schema_version ≥ 2.2 的批次，5 个结构字段 + distractor_mechanism 覆盖 100%

起步阶段 **advisory**：违例记为 violation 但默认不阻断（enforce=False）。
advisory 不是「不检查」——报告照样列出违例题目与指标，只是 gate 暂不吃它。

用法：
  python scripts/validate/rules_batch.py --file 最终产物/batch046/ALL_questions_FIXED.json
  python scripts/validate/rules_batch.py --file x.json --enforce --json out.json --md out.md
  python -m scripts.validate --file x.json --batch-mode
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

try:  # 阈值单一事实来源；缺模块时退回本文件 DEFAULT_THRESHOLDS
    import pipeline_config as _pc
except Exception:  # pragma: no cover - 仅在没有 scripts/ 的环境触发
    _pc = None

DEFAULT_THRESHOLDS = {
    "x1_letter_min": 0.15,
    "x1_letter_max": 0.30,
    "x2_unique_longest_max": 0.30,
    "x6_misconception_reuse_min": 0.20,
    "x5_reverse_max": 0.15,
}

# schema_version >= 该值的批次才检查结构字段（历史批次不追溯）
STRUCT_SINCE = (2, 2)
STRUCT_FIELDS = ("difficulty_tier", "step_count", "competing_dx", "negative_cues", "conditionals")

MECHANISMS = (
    "similar_presentation", "adjacent_concept", "direction_error", "timing_error",
    "population_mismatch", "mechanism_confusion", "overgeneralization", "outdated_guideline",
)

# ── 反选题（P2-S4）────────────────────────────────────────────
#
# 权威信号是 `polarity` 字段（生成时显式标注）；题干正则只做两件事：
#   ① polarity 缺失时兜底；② 与 polarity 交叉核对，产出待人工复核清单。
#
# 正则必须只认「设问位置」的否定词。踩过的两个坑：
#   · "**错误的**是" —— 加粗星号插在词中间，不先去 `*` 就匹配不上；
#   · "禁忌证是？" / "不宜手术的患者，最常用…是？" —— 否定词作定语，不是设问，
#     这类是正选题。把"禁忌"计进否定词会凭空造出 26 道"反选题"。
REV_TAIL = re.compile(
    r"(不正确|错误|不属于|不包括|不符合|不恰当|不宜|除外|排除|最少见|最不可能|不是)"
    r"[^。？]{0,10}?\s*(的)?\s*(是|为)?\s*[？?]?\s*$"
)
REV_ASK_AFTER = re.compile(
    r"(哪项|哪一项|何项|哪种|哪一个|何者)[^。]{0,12}?"
    r"(不正确|错误|不属于|不包括|不符合|不恰当|除外|不是|最不可能|最少见)"
)
REV_ASK_BEFORE = re.compile(
    r"(不正确|错误|不属于|不包括|不符合|不恰当|除外|不是)[^。]{0,12}?"
    r"(下列|以下)?\s*(哪项|哪一项|何项|哪种|哪一个|何种)"
)


def polarity(q: dict) -> str:
    """归一化极性：negative / positive / multi / ''（未标注）。"""
    for k in ("polarity", "question_polarity"):
        v = q.get(k)
        if isinstance(v, str) and v.strip():
            s = v.strip().lower()
            if s in ("negative", "反选", "neg"):
                return "negative"
            if s in ("multi", "多选", "multiple"):
                return "multi"
            if s in ("positive", "正选", "pos"):
                return "positive"
            return s
    return ""


def stem_reverse(q: dict) -> bool:
    """题干是否在「设问位置」出现否定词。

    先去强调标记再判：实测踩过三种写法，任何一种没处理都会整批漏检——
      · `**错误的**是`（markdown 粗体）
      · `<b>不属于</b>牙周组织的是`（HTML 标签，batch037 因此 29 道全漏）
      · `<b><b>错误</b>的是</b>`（嵌套标签）
    """
    s = _stem(q)
    if not s:
        return False
    s = re.sub(r"<[^>]+>", "", s).replace("*", "").replace("_", "")
    return bool(REV_TAIL.search(s) or REV_ASK_AFTER.search(s) or REV_ASK_BEFORE.search(s))


def is_reverse(q: dict) -> tuple[bool, str]:
    """返回 (是否反选题, 依据)。polarity 优先，缺失看题干。"""
    p = polarity(q)
    if p:
        return p == "negative", "polarity"
    return stem_reverse(q), "stem"


def distractor_labels(q: dict) -> set[str]:
    """干扰项 = **非答案项**，与极性无关。

    不能用 `truth is False` 找干扰项：反选题里 truth=False 的那一个恰恰是
    **答案本身**（"下列哪项不正确"→ 错误说法为答案），而另外 4 个为真说法
    才是干扰项。用 truth 判会把反选题的干扰项整体判反，机制标签与错误认知
    都会要求到错误的位置上。
    """
    opts = set(options(q))
    return opts - set(answer(q))


def check_reverse_selection(items: list[dict], th: dict, sample_limit: int = 20) -> dict:
    """X5：反选题占比上限（P2-S4 / AC-P2-05）。

    取 **polarity 与题干设问的并集**，不用单一口径：

    · 只用 polarity：batch042 的 14 道「下列哪项不正确」全被标成 `positive`，
      占比会算成 0%——不是题没问题，是标注没写对。
    · 只用题干：会漏掉题干里没有典型否定词、但 polarity 明确标了 negative 的题。

    门禁宁可高估：任一信号说它是反选，就计进分子。分母用全部题
    （并集不依赖标注完整性，未标注的题也能靠题干进来）。
    """
    limit = float(th.get("x5_reverse_max", 0.15))
    total = len(items)
    pol_neg = [q for q in items if polarity(q) == "negative"]
    stem_neg = [q for q in items if stem_reverse(q)]
    union = [q for q in items if polarity(q) == "negative" or stem_reverse(q)]
    value = round(len(union) / total, 4) if total else 0.0
    pol_value = round(len(pol_neg) / total, 4) if total else 0.0
    stem_value = round(len(stem_neg) / total, 4) if total else 0.0
    return {
        "rule": "X5", "name": "反选题占比",
        "threshold": f"≤ {limit:.0%}",
        "status": "VIOLATED" if total and value > limit else "PASS",
        "value": value, "numerator": len(union), "denominator": total,
        "by_signal": {"polarity": pol_value, "stem": stem_value,
                      "polarity_n": len(pol_neg), "stem_n": len(stem_neg)},
        "sample": [{"qid": _qid(q, i), "stem": _stem(q)[:60]}
                   for i, q in enumerate(union)][:sample_limit],
        "note": "分子 = polarity=negative 与题干设问的并集（宁可高估）；分母 = 全部题。",
    }


def check_polarity_consistency(items: list[dict], sample_limit: int = 15) -> dict:
    """X5-p（advisory）：polarity 标注 vs 题干设问的交叉核对。

    不是门禁。历史上出现过的三种形态都要能被看见：
      · 题干确实在反选、polarity 标了 positive —— 标注错，R15 会按错的期望值判定 truth；
      · 题干是正选、polarity 标了 negative —— 标注错，同样是 R15 的输入错误；
      · 题干正则误判（"禁忌证是？"这类设问）—— 是工具问题，不改数据。
    """
    mismatch = []
    agree = 0
    for i, q in enumerate(items):
        p = polarity(q)
        if not p or p == "multi":
            continue  # 多选与未标注不参与一致性比对
        by_stem = stem_reverse(q)
        by_pol = p == "negative"
        if by_stem == by_pol:
            agree += 1
        else:
            mismatch.append({
                "qid": _qid(q, i), "polarity": p,
                "stem_says": "negative" if by_stem else "positive",
                "stem": _stem(q)[:70],
            })
    denom = agree + len(mismatch)
    return {
        "rule": "X5-P", "name": "极性标注一致性（advisory）",
        "threshold": "参考值，不阻断",
        "status": "INFO",
        "agree": agree, "mismatch": len(mismatch),
        "value": round(len(mismatch) / denom, 4) if denom else 0.0,
        "sample": mismatch[:sample_limit],
        "note": "不一致项要人工看一遍再定性：可能是标注错，也可能是题干正则误判。",
    }


def check_reverse_option_anchors(items: list[dict], sample_limit: int = 20) -> dict:
    """X5-a：反选题的 4 个「为真干扰项」须逐项锚点（P2-S4）。

    反选题里非答案项是**正确说法**，它们的价值在于「这句话出自教材哪一段」，
    而不是「它错在哪」。所以要求的是锚点，不是 misconception_id。

    只在 schema_version ≥ 2.2 的批次上强制；历史批次没有 per_option 锚点字段，
    只统计不判定（与 S-STRUCT 同一分档逻辑）。
    """
    current = [q for q in items if schema_version(q) >= STRUCT_SINCE]
    historical = len(items) - len(current)
    if not current:
        return {
            "rule": "X5-A", "name": "反选题为真干扰项逐项锚点",
            "threshold": "schema_version ≥ 2.2 时 100%",
            "status": "SKIP", "applicable": False, "historical_items": historical,
            "note": "本批无 schema_version ≥ 2.2 的题目；历史产物无 per_option 锚点字段，不追溯。",
        }

    target = 0
    anchored = 0
    missing: list[str] = []
    reverse_total = 0
    for i, q in enumerate(current):
        rev, _ = is_reverse(q)
        if not rev:
            continue
        reverse_total += 1
        qid = _qid(q, i)
        lv = q.get("learning_value") or {}
        item_anchor = str(lv.get("answer_evidence") or "").strip()
        per = {str(p.get("label", "")).strip().upper(): p
               for p in (lv.get("per_option") or []) if isinstance(p, dict)}
        for lab in sorted(distractor_labels(q)):
            target += 1
            p = per.get(lab) or {}
            has = (str(p.get("source_anchor") or p.get("anchor") or "").strip()
                   or item_anchor)
            if has:
                anchored += 1
            else:
                missing.append(f"{qid}:{lab}")
    cov = round(anchored / target, 4) if target else 1.0
    return {
        "rule": "X5-A", "name": "反选题为真干扰项逐项锚点",
        "threshold": "schema_version ≥ 2.2 时 100%",
        "status": "VIOLATED" if target and cov < 1.0 else "PASS",
        "applicable": True, "items": len(current), "historical_items": historical,
        "reverse_items": reverse_total, "target_options": target,
        "anchored": anchored, "coverage": cov,
        "missing": missing[:sample_limit],
    }


# ── 取值工具 ────────────────────────────────────────────────

def thresholds() -> dict:
    out = dict(DEFAULT_THRESHOLDS)
    if _pc is not None:
        for k, v in DEFAULT_THRESHOLDS.items():
            try:
                out[k] = _pc.get_number(k, v)
            except Exception:
                pass
    return out


def _qid(q: dict, i: int) -> str:
    for k in ("question_id", "id", "qid"):
        v = q.get(k)
        if v not in (None, ""):
            return str(v)
    return f"#{i}"


def _stem(q: dict) -> str:
    for k in ("stem", "question", "question_text"):
        v = q.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def options(q: dict) -> dict[str, str]:
    """归一化选项为 {label: text}。容忍 dict / [{label,text}] / ['A. xxx'] 三种历史形态。"""
    raw = q.get("options")
    out: dict[str, str] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            out[str(k).strip().upper()] = str(v)
    elif isinstance(raw, list):
        for it in raw:
            if isinstance(it, dict):
                lab = it.get("label") or it.get("key") or it.get("option")
                txt = it.get("text") or it.get("value") or it.get("content")
                if lab:
                    out[str(lab).strip().upper()] = str(txt or "")
            elif isinstance(it, str):
                m = re.match(r"^\s*([A-Za-z])\s*[.．、)）:：]\s*(.*)$", it)
                if m:
                    out[m.group(1).upper()] = m.group(2)
    return out


def answer(q: dict) -> str:
    for k in ("answer", "answer_key", "correct_answer", "key"):
        v = q.get(k)
        if isinstance(v, str) and v.strip():
            return re.sub(r"[^A-Za-z]", "", v).upper()
        if isinstance(v, list) and v:
            return "".join(str(x).strip().upper() for x in v)
    return ""


def schema_version(q: dict) -> tuple:
    v = str(q.get("schema_version") or "").strip()
    m = re.match(r"^(\d+)\.(\d+)$", v)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


# ── X1 答案字母分布 ─────────────────────────────────────────

def check_answer_distribution(items: list[dict], th: dict) -> dict:
    """单选（答案恰 1 个字母）计入分布；多选/判断单列，不混进分母。"""
    single = Counter()
    multi = 0
    letters: set[str] = set()
    for q in items:
        opts = options(q)
        letters |= set(opts)
        a = answer(q)
        if len(a) == 1 and a in opts:
            single[a] += 1
        elif len(a) > 1:
            multi += 1
    total = sum(single.values())
    dist = {}
    violations = []
    for lab in sorted(letters):
        n = single.get(lab, 0)
        share = (n / total) if total else 0.0
        dist[lab] = {"count": n, "share": round(share, 4)}
        if total and (share < th["x1_letter_min"] or share > th["x1_letter_max"]):
            violations.append({
                "letter": lab, "share": round(share, 4), "count": n,
                "why": "偏低" if share < th["x1_letter_min"] else "偏高",
            })
    return {
        "rule": "X1", "name": "答案字母分布",
        "threshold": f"{th['x1_letter_min']:.0%}–{th['x1_letter_max']:.0%} / 字母",
        "value": dist, "denominator": total, "excluded_multi": multi,
        "violations": violations,
        "status": "PASS" if not violations else "VIOLATED",
    }


# ── X2 唯一最长 ─────────────────────────────────────────────

def check_unique_longest(items: list[dict], th: dict, sample_limit: int = 20) -> dict:
    hits = []
    valid = 0
    for i, q in enumerate(items):
        opts = options(q)
        a = answer(q)
        if len(opts) < 2 or len(a) != 1 or a not in opts:
            continue
        valid += 1
        lens = {k: len(v.strip()) for k, v in opts.items()}
        mx = max(lens.values())
        if lens[a] == mx and sum(1 for v in lens.values() if v == mx) == 1:
            hits.append(_qid(q, i))
    rate = (len(hits) / valid) if valid else 0.0
    bad = rate > th["x2_unique_longest_max"]
    return {
        "rule": "X2", "name": "正确项唯一最长",
        "threshold": f"≤ {th['x2_unique_longest_max']:.0%}",
        "value": round(rate, 4), "hits": len(hits), "denominator": valid,
        "samples": hits[:sample_limit],
        "violations": [] if not bad else [{"rate": round(rate, 4), "hits": len(hits)}],
        "status": "PASS" if not bad else "VIOLATED",
    }


# ── X6 错误认知复用 ─────────────────────────────────────────

def check_misconception_reuse(items: list[dict], th: dict, sample_limit: int = 20) -> dict:
    """复用率 = 使用「被复用 ID」的干扰项数 / 干扰项总数。

    复用的意义：同一个错误认知在整批里反复出现，才能沉淀成可训练的概念卡；
    每题一个全新 misconception_id 等于把错误认知写成了题内私有标签，
    既无法跨题追踪，也无法支撑 P9 的概念卡复用。
    """
    ids: list[str] = []
    missing: list[str] = []
    for i, q in enumerate(items):
        lv = q.get("learning_value") or {}
        for po in (lv.get("per_option") or []):
            if not isinstance(po, dict) or po.get("truth") is not False:
                continue
            mid = str(po.get("misconception_id") or "").strip()
            if mid:
                ids.append(mid)
            else:
                missing.append(f"{_qid(q, i)}:{po.get('label')}")
    counts = Counter(ids)
    reused_ids = {k: v for k, v in counts.items() if v >= 2}
    reused_occ = sum(reused_ids.values())
    total = len(ids)
    rate = (reused_occ / total) if total else 0.0
    bad = rate < th["x6_misconception_reuse_min"]
    return {
        "rule": "X6", "name": "错误认知复用率",
        "threshold": f"≥ {th['x6_misconception_reuse_min']:.0%}",
        "value": round(rate, 4), "distinct_ids": len(counts), "distractor_occurrences": total,
        "reused_ids": len(reused_ids), "reused_occurrences": reused_occ,
        "missing_id_count": len(missing),
        "top_reused": [{"id": k, "n": v} for k, v in sorted(reused_ids.items(), key=lambda kv: -kv[1])[:sample_limit]],
        "violations": [] if not bad else [{"rate": round(rate, 4), "note": "复用率不足，干扰项标签退化为题内私有"}],
        "status": "PASS" if not bad else "VIOLATED",
    }


# ── S-STRUCT 结构字段覆盖 ───────────────────────────────────

def check_structural_coverage(items: list[dict]) -> dict:
    """schema_version ≥ 2.2 才强制；历史批次只统计不判定（不追溯）。"""
    current = [q for q in items if schema_version(q) >= STRUCT_SINCE]
    historical = [q for q in items if schema_version(q) < STRUCT_SINCE]
    if not current:
        return {
            "rule": "S-STRUCT", "name": "结构字段覆盖率",
            "threshold": "schema_version ≥ 2.2 时 100%",
            "status": "SKIP", "applicable": False,
            "historical_items": len(historical),
            "note": "本批无 schema_version ≥ 2.2 的题目；历史批次不追溯（回滚口径：新字段 optional）。",
        }

    missing: dict[str, list[str]] = {f: [] for f in STRUCT_FIELDS}
    mech_missing: list[str] = []
    for i, q in enumerate(current):
        qid = _qid(q, i)
        for f in STRUCT_FIELDS:
            # 数组字段区分「字段缺失」与「显式空数组」：
            # negative_cues / conditionals 对正向题、无条件题合法地留空，
            # 判缺失会把「合法的空」误判成「没写」。
            if f not in q or q.get(f) is None:
                missing[f].append(qid)
            elif f == "competing_dx" and not q.get(f):
                missing[f].append(qid)  # schema minItems=1：空数组不合法
        lv = q.get("learning_value") or {}
        per = {str(po.get("label", "")).strip().upper(): po
               for po in (lv.get("per_option") or []) if isinstance(po, dict)}
        for lab in sorted(distractor_labels(q)):
            if not str((per.get(lab) or {}).get("distractor_mechanism") or "").strip():
                mech_missing.append(f"{qid}:{lab}")
    total = len(current)
    coverage = {f: round((total - len(v)) / total, 4) for f, v in missing.items()}
    mech_total = sum(len(distractor_labels(q)) for q in current)
    mech_cov = round((mech_total - len(mech_missing)) / mech_total, 4) if mech_total else 0.0
    bad = [f for f, c in coverage.items() if c < 1.0] + ([] if mech_cov >= 1.0 else ["distractor_mechanism"])
    return {
        "rule": "S-STRUCT", "name": "结构字段覆盖率",
        "threshold": "schema_version ≥ 2.2 时 100%",
        "status": "PASS" if not bad else "VIOLATED",
        "applicable": True, "items": total, "historical_items": len(historical),
        "coverage": coverage, "mechanism_coverage": mech_cov,
        "missing": {f: v[:20] for f, v in missing.items() if v},
        "mechanism_missing": mech_missing[:20],
        "violations": [{"field": f} for f in bad],
    }


# ── 汇总 ────────────────────────────────────────────────────

def audit_batch(items: list[dict], enforce: bool = False, th: dict | None = None) -> dict:
    th = th or thresholds()
    checks = [
        check_answer_distribution(items, th),
        check_unique_longest(items, th),
        check_misconception_reuse(items, th),
        check_reverse_selection(items, th),
        check_reverse_option_anchors(items),
        check_polarity_consistency(items),
        check_structural_coverage(items),
    ]
    violated = [c["rule"] for c in checks if c["status"] == "VIOLATED"]
    if not violated:
        status = "PASS"
    else:
        status = "FAIL" if enforce else "ADVISORY"
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "scripts/validate/rules_batch.py",
        "mode": "enforce" if enforce else "advisory",
        "items": len(items),
        "thresholds": th,
        "status": status,
        "violated_rules": violated,
        "checks": checks,
        "note": ("advisory 模式：违例如实记录但不阻断流水线；"
                 "转 enforce 需先完成历史回测与误伤确认（P2-S3 → AC-P2-09）。"),
    }


def render_md(report: dict, title: str = "") -> str:
    t = title or f"批次规则回测（{Path(report['path']).name if report.get('path') else ''}）"
    lines = [
        f"# {t}", "",
        f"- 生成：{report['generated_at']}",
        f"- 工具：`{report['tool']}`",
        f"- 模式：**{report['mode']}**　结论：**{report['status']}**",
        f"- 题量：{report['items']}",
        f"- 违例规则：{', '.join(report['violated_rules']) or '无'}",
        "",
        "## 指标",
        "",
        "| 规则 | 名称 | 口径 | 实测 | 结论 |",
        "|---|---|---|---|---|",
    ]
    for c in report["checks"]:
        v = c.get("value")
        if isinstance(v, dict):
            vs = "、".join(f"{k} {d['share']:.1%}" for k, d in v.items())
        elif isinstance(v, float):
            vs = f"{v:.1%}"
        elif v is None:
            vs = "未适用" if c["status"] == "SKIP" else "—"
        else:
            vs = str(v)
        lines.append(f"| {c['rule']} | {c['name']} | {c['threshold']} | {vs} | {c['status']} |")
    lines += ["", "## 违例明细", ""]
    for c in report["checks"]:
        if c["status"] != "VIOLATED":
            continue
        lines.append(f"### {c['rule']} {c['name']}")
        lines.append("")
        for v in c.get("violations", []) or []:
            lines.append(f"- `{json.dumps(v, ensure_ascii=False)}`")
        lines.append("")
    lines += [
        "---", "",
        "> advisory 阶段的含义：这些违例**已经能自动算出来**，但门禁尚未阻断流水线。",
        "> 转 enforce 的前置是历史回测确认误伤可控（AC-P2-09），不是「报告好看就开」。",
        "",
    ]
    return "\n".join(lines)


def load_items(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for k in ("questions", "items", "data"):
            if isinstance(data.get(k), list):
                return data[k]
        raise ValueError(f"{path} 是对象且无 questions/items/data 数组")
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="批次级规则 X1/X2/X6 + 结构覆盖率")
    ap.add_argument("--file", "-f", required=True, help="题库 JSON（数组）")
    ap.add_argument("--enforce", action="store_true", help="违例即 FAIL（默认 advisory）")
    ap.add_argument("--json", default="", help="报告 JSON 输出路径")
    ap.add_argument("--md", default="", help="报告 Markdown 输出路径")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    items = load_items(args.file)
    rep = audit_batch(items, enforce=args.enforce)
    rep["path"] = str(args.file)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.md:
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(render_md(rep), encoding="utf-8")

    if not args.quiet:
        print(f"批次规则（{rep['mode']}）: {rep['status']}  {args.file}")
        for c in rep["checks"]:
            v = c.get("value")
            vs = f"{v:.1%}" if isinstance(v, float) else ("" if isinstance(v, dict) else str(v or ""))
            print(f"  {c['rule']:<9} {c['status']:<9} {c['name']}  {vs}")
    return 1 if rep["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
