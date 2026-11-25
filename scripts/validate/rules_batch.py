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

# 新批次阻断生效点（2026-11-25）：定义在 DEFAULT_THRESHOLDS 之前，供其引用
ENFORCE_SINCE_DEFAULT = "batch051"

DEFAULT_THRESHOLDS = {
    "x1_letter_min": 0.15,
    "x1_letter_max": 0.30,
    "x2_unique_longest_max": 0.30,
    "x6_misconception_reuse_min": 0.20,
    "x5_reverse_max": 0.15,
    # X7 多选答案分布（2026-11-25）：X1 只统计单选，多选长期无规则，
    # batch049 出现 18 题里 16 题答案为 ABCD、E 从未作答案的退化形态。
    "x7_max_combo_share": 0.40,      # 单一答案组合占全部多选题的上限
    "x7_letter_min": 0.12,           # 单个字母被选为正确项的最低占比（5 字母均等 = 20%）
    "x7_letter_max": 0.32,
    "x7_prefix_cluster_max": 0.60,   # 正确项恰为 {A..k} 前缀集合的题占比上限
    "x7_max_same_n_share": 0.60,     # 正确项个数为同一取值（如恒 4 项）的题占比上限
    "x7_min_items": 5,               # 少于该题数不判定（样本太小）
    # X8 难度-题型解耦（2026-11-25）：难度曾被当成题型代理，A2 ≡ 难。
    "x8_type_tvd_max": 0.30,         # 题型内难度分布与全局分布的 TVD 上限
    "x8_tier_min_share": 0.15,       # 每种题型在「易（L1+L2）/ 难（L3+L4）」两侧的最低占比
    "x8_min_items_per_type": 10,
    "x8_global_l1": 0.10,
    "x8_global_l2": 0.30,
    "x8_global_l3": 0.40,
    "x8_global_l4": 0.20,
    "x8_global_dev_max": 0.08,       # 全局各档与目标的偏差上限
    # X9 选项尾部模板复用（2026-11-25）：为压 X2「唯一最长」而给干扰项贴同一句话，
    # 会让 133/250 题出现「等临床情况需鉴别」这类非选项文本。
    "x9_template_tail": 6,           # 取选项末尾 N 字（去标点）做模板指纹
    "x9_template_q_share": 0.10,     # 同一指纹覆盖的题占比上限
    "x9_template_min_questions": 3,  # 覆盖率之外，至少在这么多题里重复才算模板
    # X10 答案位置周期性（2026-11-25）：X1 只看总量，看不出「第 1、6、11 题永远是 A」
    "x10_periodicity_max": 0.90,
    "x10_min_items": 20,
    # 生效批次：≥ 该批次的 X7/X9/X10 与 X8 的 TVD/两侧占比计入 FAIL（旧批次不追溯）
    "x_enforce_since": ENFORCE_SINCE_DEFAULT,
}

# schema_version >= 该值的批次才检查结构字段（历史批次不追溯）
STRUCT_SINCE = (2, 2)

# ── 新批次阻断（2026-11-25）────────────────────────────────
#
# X7/X8/X9/X10 是 batch049 事故后新增的四条规则（多选位置泄漏、难度=题型代理、
# 选项贴套话、答案位置周期）。历史批次已在 advisory 下产出并签收，按「不追溯」原则
# 不再回溯；从 x_enforce_since 指定的批次起，这四条从「记录」变成「阻断」。
#
# 只阻断「可预测 / 文本被改坏 / 难度无信息量」这类**机械可判定的硬缺陷**；
# X1/X2/X5/X6 与 X8 的全局配比偏差继续 advisory —— 配比是理想值，不该卡住交付。
X_BLOCKING_RULES = ("X7", "X9", "X10", "X11", "X12")
X8_BLOCKING_METRICS = ("type_tvd", "tier_min_share")


def batch_number(batch) -> int | None:
    """'batch051' / 'batch051-眼科' / 路径 → 51；认不出返回 None（按非阻断处理）。"""
    m = re.search(r"batch(\d{3})", str(batch or ""))
    return int(m.group(1)) if m else None


def _is_blocking(check: dict, batch, th: dict) -> bool:
    """该条违例在**本批次**是否阻断 A2。"""
    if check.get("status") != "VIOLATED":
        return False
    since = batch_number(th.get("x_enforce_since") or ENFORCE_SINCE_DEFAULT)
    cur = batch_number(batch)
    if since is None or cur is None or cur < since:
        return False  # 历史批次：不追溯
    rule = check.get("rule")
    if rule in X_BLOCKING_RULES:
        return True
    if rule == "X8":
        return any(v.get("metric") in X8_BLOCKING_METRICS
                   for v in (check.get("violations") or []))
    return False
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
            if isinstance(v, str):
                continue  # 批次号是字符串，走下面的原值读取
            try:
                out[k] = _pc.get_number(k, v)
            except Exception:
                pass
        try:
            out["x_enforce_since"] = _pc.get_threshold("x_enforce_since", out["x_enforce_since"])
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
    # 无标号的纯文本列表（batch044 押题卷的形态）：按位置补 A/B/C…，
    # 否则 options() 返回空 dict，X1/X7/X9 会集体「看不见」这些题。
    if not out and isinstance(raw, list) and len(raw) >= 2:
        if all(isinstance(x, str) and x.strip() for x in raw):
            out = {chr(ord("A") + i): x.strip() for i, x in enumerate(raw)}
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
    binary = 0
    letters: set[str] = set()
    for q in items:
        opts = options(q)
        letters |= set(opts)
        a = answer(q)
        # 判断题（两选项 + A/B 作答）不是五选一的分布问题：把它算进分母会让
        # A/B 凭空多出十几票，掩盖真正的单选偏倚（batch049 的 232 分母里就有 36 题判断）。
        if len(opts) <= 2:
            binary += 1
            continue
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
        "excluded_binary": binary,
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


# ── X7 多选答案分布 ─────────────────────────────────────────

TIER_ORDER = ("L1", "L2", "L3", "L4")


def _tier(q: dict) -> str:
    """归一化难度档到 L1–L4；认不出返回 ''（不参与分布统计）。"""
    raw = str(q.get("difficulty_tier") or q.get("difficulty") or "").strip().upper()
    m = re.search(r"L\s*([1-4])", raw)
    return f"L{m.group(1)}" if m else ""


def _qtype(q: dict) -> str:
    for k in ("type", "question_type", "qtype"):
        v = q.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "unknown"


def check_multi_answer_distribution(items: list[dict], th: dict, sample_limit: int = 15) -> dict:
    """X7：多选题的答案位置 / 组合 / 项数分布。

    X1 只把「答案恰 1 个字母」的题计入分母，多选被整体排除——于是「多选题答案
    永远是 ABCD」这种缺陷，历史上没有任何规则能算出来。batch049 的实测是
    18 题里 16 题答案 ABCD、2 题 ABC，**E 一次都没当过答案**：学生按「选 ABCD」
    盲猜就能拿 89%。

    四个指标各抓一种退化：
      · combo_share     —— 答案组合是否退化成单一形态；
      · letter_share    —— 是否有字母（通常是 E）系统性不作答案；
      · prefix_cluster  —— 答案是否总落在开头几位（"前三个/前四个"）；
      · n_correct       —— 正确项个数是否恒定（恒 4 项 = 只剩「选哪个错」）。
    """
    multi = []
    for i, q in enumerate(items):
        opts = options(q)
        a = answer(q)
        if len(a) >= 2:
            multi.append((i, q, set(a) & set(opts)))
    n = len(multi)
    if n < int(th.get("x7_min_items", 5)):
        return {
            "rule": "X7", "name": "多选答案分布",
            "threshold": f"多选 ≥ {int(th.get('x7_min_items', 5))} 题才判定",
            "status": "SKIP", "applicable": False, "multi_items": n,
            "note": "多选样本太小，不做分布判定（不是通过，是没数据）。",
        }

    combos = Counter("".join(sorted(s)) for _, _, s in multi)
    letters = Counter()
    for _, _, s in multi:
        for lab in s:
            letters[lab] += 1
    correct_total = sum(len(s) for _, _, s in multi)
    ncorrect = Counter(len(s) for _, _, s in multi)
    prefix = 0
    for _, _, s in multi:
        k = len(s)
        if s == {chr(ord("A") + j) for j in range(k)}:
            prefix += 1

    top_combo, top_combo_n = combos.most_common(1)[0]
    combo_share = top_combo_n / n
    letter_share = {lab: round(c / correct_total, 4) for lab, c in sorted(letters.items())}
    all_letters = sorted(set(letters) | {chr(ord("A") + j) for j in range(5)})
    prefix_share = prefix / n
    top_n, top_n_count = ncorrect.most_common(1)[0]
    same_n_share = top_n_count / n

    violations = []
    if combo_share > th["x7_max_combo_share"]:
        violations.append({"metric": "combo_share", "value": round(combo_share, 4),
                           "combo": top_combo, "count": top_combo_n,
                           "why": f"单一组合 {top_combo} 占 {combo_share:.0%}"})
    for lab in all_letters:
        c = letters.get(lab, 0)
        share = c / correct_total if correct_total else 0.0
        if share < th["x7_letter_min"]:
            violations.append({"metric": "letter_share", "letter": lab,
                               "value": round(share, 4), "count": c,
                               "why": f"{lab} 作为正确项仅 {c} 次（{share:.0%}）"})
        elif share > th["x7_letter_max"]:
            violations.append({"metric": "letter_share", "letter": lab,
                               "value": round(share, 4), "count": c,
                               "why": f"{lab} 作为正确项 {c} 次（{share:.0%}）过高"})
    if prefix_share > th["x7_prefix_cluster_max"]:
        violations.append({"metric": "prefix_cluster", "value": round(prefix_share, 4),
                           "why": f"{prefix}/{n} 题的正确项恰为开头连续几位"})
    if same_n_share > th["x7_max_same_n_share"]:
        violations.append({"metric": "n_correct", "value": round(same_n_share, 4),
                           "n": top_n, "count": top_n_count,
                           "why": f"正确项个数恒为 {top_n} 的题占 {same_n_share:.0%}"})
    return {
        "rule": "X7", "name": "多选答案分布",
        "threshold": (f"单组合 ≤{th['x7_max_combo_share']:.0%}；每字母 "
                      f"{th['x7_letter_min']:.0%}–{th['x7_letter_max']:.0%}；"
                      f"前缀聚集 ≤{th['x7_prefix_cluster_max']:.0%}；"
                      f"同项数 ≤{th['x7_max_same_n_share']:.0%}"),
        "status": "VIOLATED" if violations else "PASS",
        "applicable": True, "multi_items": n, "correct_option_occurrences": correct_total,
        "combo_share": round(combo_share, 4), "combo_dist": dict(combos.most_common()),
        "letter_share": letter_share, "prefix_cluster_share": round(prefix_share, 4),
        "n_correct_dist": dict(ncorrect.most_common()),
        "violations": violations,
        "sample": [{"qid": _qid(q, i), "answer": "".join(sorted(s))}
                   for i, q, s in multi][:sample_limit],
        "note": "分母 = 多选题题数（项数指标）/ 正确项总出现次数（字母指标）。X1 不覆盖多选，本规则补这个盲区。",
    }


# ── X8 难度-题型解耦 ────────────────────────────────────────

def _tvd(p: dict, q: dict, keys: tuple) -> float:
    """两个分布的 total variation distance（0 = 同分布，1 = 完全不重叠）。"""
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


def check_difficulty_type_decoupling(items: list[dict], th: dict, sample_limit: int = 20) -> dict:
    """X8：难度必须由「考点细致程度」决定，不能是题型的代理变量。

    病史：batch049 把「病例型题占比」当成了难度本身——89 道 A2 里 88 道被标
    L3/L4，107 道 A1 只有 28 道进 L3/L4，判断与多选又各自堆在一档。后果是
    难度标签不携带任何信息：看到题号就知道难度，看到难度就知道题型。

    判定用两条互补的指标，不看绝对题数：
      · TVD（题型内难度分布 vs 全局难度分布）——太低才说明「难度独立于题型」；
      · 每种题型在易（L1+L2）/ 难（L3+L4）两侧的最低占比——防止某题型被整段
        贴成单一档（哪怕全局分布碰巧合格）。
    另加全局各档与目标分布的偏差，防止「分布好看但档位意义漂移」。
    """
    labeled = [(q, _tier(q)) for q in items if _tier(q)]
    unlabeled = len(items) - len(labeled)
    if len(labeled) < 20:
        return {
            "rule": "X8", "name": "难度-题型解耦",
            "threshold": "已标难度 ≥ 20 题才判定",
            "status": "SKIP", "applicable": False,
            "items": len(items), "labeled": len(labeled),
            "note": "difficulty_tier 覆盖不足，无法做分布判定。",
        }

    gcount = Counter(t for _, t in labeled)
    gtotal = len(labeled)
    gdist = {k: gcount.get(k, 0) / gtotal for k in TIER_ORDER}

    target = {f"L{j+1}": float(th.get(f"x8_global_l{j+1}", d))
              for j, d in enumerate((0.10, 0.30, 0.40, 0.20))}
    global_dev = {k: round(gdist[k] - target[k], 4) for k in TIER_ORDER}
    violations = []
    for k in TIER_ORDER:
        if abs(gdist[k] - target[k]) > th["x8_global_dev_max"]:
            violations.append({"metric": "global_share", "tier": k,
                               "value": round(gdist[k], 4), "target": target[k],
                               "why": f"{k} 实占 {gdist[k]:.0%}，目标 {target[k]:.0%}"})

    by_type: dict[str, dict] = {}
    for t in sorted({_qtype(q) for q, _ in labeled}):
        sub = [tier for q, tier in labeled if _qtype(q) == t]
        n = len(sub)
        c = Counter(sub)
        dist = {k: c.get(k, 0) / n for k in TIER_ORDER}
        easy = sum(1 for x in sub if x in ("L1", "L2")) / n
        hard = sum(1 for x in sub if x in ("L3", "L4")) / n
        tvd = _tvd(dist, gdist, TIER_ORDER)
        row = {
            "n": n, "dist": {k: round(v, 4) for k, v in dist.items()},
            "tvd": round(tvd, 4), "easy_share": round(easy, 4), "hard_share": round(hard, 4),
            "applicable": n >= int(th.get("x8_min_items_per_type", 10)),
        }
        if row["applicable"]:
            if tvd > th["x8_type_tvd_max"]:
                violations.append({"metric": "type_tvd", "type": t, "value": round(tvd, 4),
                                   "why": f"{t} 的难度分布偏离全局 {tvd:.0%}（上限 {th['x8_type_tvd_max']:.0%}）"})
            if easy < th["x8_tier_min_share"]:
                violations.append({"metric": "tier_min_share", "type": t, "side": "easy",
                                   "value": round(easy, 4),
                                   "why": f"{t} 的 L1+L2 仅 {easy:.0%}，难度被判成了题型属性"})
            if hard < th["x8_tier_min_share"]:
                violations.append({"metric": "tier_min_share", "type": t, "side": "hard",
                                   "value": round(hard, 4),
                                   "why": f"{t} 的 L3+L4 仅 {hard:.0%}，该题型没有难题"})
        by_type[t] = row

    return {
        "rule": "X8", "name": "难度-题型解耦",
        "threshold": (f"题型内 TVD ≤{th['x8_type_tvd_max']:.0%}；"
                      f"易/难各 ≥{th['x8_tier_min_share']:.0%}；"
                      f"全局各档偏差 ≤{th['x8_global_dev_max']:.0%}"),
        "status": "VIOLATED" if violations else "PASS",
        "applicable": True, "items": len(items), "labeled": len(labeled),
        "unlabeled": unlabeled,
        "global_dist": {k: round(v, 4) for k, v in gdist.items()},
        "target_dist": target, "global_dev": global_dev,
        "by_type": by_type, "violations": violations,
        "sample": [{"qid": _qid(q, i), "type": _qtype(q), "tier": tier}
                   for i, (q, tier) in enumerate(labeled)][:sample_limit],
        "note": ("难度口径见 docs/产物格式规范.md §2.4：由考点粒度 / 推理步数 / 干扰项贴近度 / "
                 "交叉度四要素定档，题型不参与。TVD 越低说明难度越不依赖题型。"),
    }


# ── X11 解析标号一致性 ──────────────────────────────────────

EXPL_LABEL = re.compile(r"^[ \t]*([A-E])[ \t]*[：:.、][ \t]*", re.M)


def check_explanation_labels(items: list[dict], th: dict, sample_limit: int = 15) -> dict:
    """X11：解析里的「A：…」逐选项行必须与选项标号一一对应且同序。

    为什么单列一条：重排选项（或用 `shuffle_option_positions.py`）之后，`answer`
    会被自动改对，机器读答案永远一致；但**人读的是解析**。解析里「A：该选项描述
    前葡萄膜炎…」如果不跟着搬，学生看到的逐项理由与选项整体错位——而且不报错，
    因为没有任何门禁读解析。

    文献侧同样提示这点：LLM 生成的多选题答案位置有系统性偏好，事后 shuffle 会让
    explanation / distractor rationale 里的字母引用失同步，且失败是静默的
    （PrepareBuddy, Answer-Position Bias in Generated MCQs；Attali & Bar-Hillel 2003
    指出位置偏倚会实质影响难度与区分度）。所以位置可以改，引用必须同步改。

    判定两层：

    1. **结构**：解析里的标号序列必须严格等于排序后的选项标号序列（不缺、不重、不乱序）。
       这一层能抓「重排后忘了重排逐选项行」——序列会变成 CABDE 之类。

    2. **内容**：把每条逐选项行的正文与 `learning_value.per_option[].why` 做相似度比对，
       该行最像的那条 why 必须属于**同一个字母**。这一层抓的是更危险的一种：标号还是
       ABCDE、顺序也对，但 A 位置上的选项已经换成了别的内容，解析还在讲旧的 A。
       纯结构检查对此完全免疫（序列没变），只有内容比对才能发现。
    """
    import difflib

    applicable, violations = 0, []
    for i, q in enumerate(items):
        expl = q.get("explanation")
        if not isinstance(expl, str):
            continue
        found = EXPL_LABEL.findall(expl)
        if len(found) < 2:
            continue  # 没有逐选项行的题（老格式）不参与判定
        applicable += 1
        want = sorted(options(q))
        qid = _qid(q, i)
        if found != want:
            violations.append({
                "qid": qid, "found": "".join(found), "want": "".join(want),
                "why": "解析标号序列与选项不一致（重排后未同步解析，或漏写/重写）",
            })
            continue
        # ── 内容层：逐选项行正文 vs per_option.why ──
        lv = q.get("learning_value") or {}
        whys = {str(p.get("label", "")).strip().upper(): str(p.get("why") or "")
                for p in (lv.get("per_option") or []) if isinstance(p, dict)}
        if len(whys) < len(want) or not all(whys.get(k) for k in want):
            continue  # 没有逐项理由可比，只做结构判定
        bodies = {}
        for m in EXPL_LABEL.finditer(expl):
            lab = m.group(1)
            start = m.end()
            nxt = EXPL_LABEL.search(expl, start)
            bodies[lab] = expl[start:nxt.start() if nxt else len(expl)].strip()[:80]
        for lab in want:
            body = bodies.get(lab, "")
            if not body:
                continue
            scored = sorted(
                ((difflib.SequenceMatcher(None, body, whys[k][:80]).ratio(), k) for k in want),
                reverse=True)
            if scored and scored[0][1] != lab:
                violations.append({
                    "qid": qid, "label": lab, "why": "解析内容与 per_option 不对应",
                    "detail": f"{lab} 行最像 {scored[0][1]} 的说明（相似度 {scored[0][0]:.2f}）"
                              f"——选项换位后解析未同步",
                })
                break
    total = len(items)
    if applicable < max(5, int(total * 0.3)):
        return {
            "rule": "X11", "name": "解析标号一致性",
            "threshold": "有逐选项行的题 ≥30% 才判定",
            "status": "SKIP", "applicable": False, "items": total, "applicable_items": applicable,
            "note": "本批解析基本没有「A：…」逐选项行，无法判定（不是通过，是没数据）。",
        }
    return {
        "rule": "X11", "name": "解析标号一致性",
        "threshold": "解析标号序列 == 排序后的选项标号序列（100%）",
        "status": "VIOLATED" if violations else "PASS",
        "applicable": True, "items": total, "applicable_items": applicable,
        "mismatch": len(violations),
        "sample": violations[:sample_limit],
        "violations": violations[:sample_limit],
        "note": ("位置可以重排，解析里的字母引用必须同步重排——否则机器读答案是对的，"
                 "人看到的逐项理由是错的，而且不报错。"),
    }


# ── X12 难度自述自洽 ────────────────────────────────────────

def check_difficulty_consistency(items: list[dict], th: dict, sample_limit: int = 15) -> dict:
    """X12：`difficulty_tier` 不能与 `step_count` / `concepts` 自相矛盾。

    X8 判的是「难度有没有随题型走」，管不了「单题标签贴得对不对」。这里补的是
    **纯逻辑矛盾**，不做难度判断：

      · 标 L1（整块结论直取）却 `step_count ≥ 3` —— 三步推理不可能是 L1；
      · 标 L4（≥3 步或多考点交叉）却 `step_count ≤ 2` 且 `concepts ≤ 1`
        —— 既不多步、也没交叉，L4 没有任何依据。

    只判这两个方向，是因为它们**不可能同时成立**；而「L1 但 step=2」「L3 但 step=1
    （问的是细节边界）」都是合法的，不做限制。
    """
    violations = []
    for i, q in enumerate(items):
        tier = _tier(q)
        if not tier:
            continue
        try:
            steps = int(q.get("step_count") or 0)
        except Exception:
            continue
        n_concepts = len(q.get("concepts") or [])
        if tier == "L1" and steps >= 3:
            violations.append({"qid": _qid(q, i), "tier": tier, "step_count": steps,
                               "why": "标 L1（单点直取）却写了 ≥3 步推理"})
        elif tier == "L4" and steps <= 2 and n_concepts <= 1:
            violations.append({"qid": _qid(q, i), "tier": tier, "step_count": steps,
                               "concepts": n_concepts,
                               "why": "标 L4 却既 ≤2 步、又没有第二个考点"})
    return {
        "rule": "X12", "name": "难度自述自洽",
        "threshold": "L1 不得 ≥3 步；L4 不得「≤2 步且 ≤1 考点」",
        "status": "VIOLATED" if violations else "PASS",
        "items": len(items), "contradictions": len(violations),
        "sample": violations[:sample_limit],
        "violations": violations[:sample_limit],
        "note": "只判逻辑矛盾（两个条件不可能同时成立），不判档位是否合理；合理与否看 X8 + 人工。",
    }


# ── X10 答案位置周期性 ──────────────────────────────────────

def check_answer_position_periodicity(items: list[dict], th: dict, sample_limit: int = 12) -> dict:
    """X10：答案字母是否按固定周期轮转（位置泄漏）。

    X1 只看各字母的**总量**是否均衡，看不见「顺序」。用 A→B→C→D→E 循环给答案
    标号，总量完美均匀，但第 1、6、11 题永远是 A；判断题按 ABAB 交替，第 1、3、5
    题永远是「正确」。学生不需要知识，只需要数题号。

    batch049 实测：196 道单选近乎严格的 ABCDE 轮转（首题例外），36 道判断题
    100% 严格 AB 交替——这两条都不是「均衡」，是「可预测」。

    判定用「与理想轮转序列的一致率」，不看总量。阈值 0.90：随机分布下该一致率
    约 0.20，误报概率极低。
    """
    single = [answer(q) for q in items if len(answer(q)) == 1 and len(options(q)) > 2]
    binary = [answer(q) for q in items if len(answer(q)) == 1 and len(options(q)) == 2]
    min_items = int(th.get("x10_min_items", 20))
    limit = float(th.get("x10_periodicity_max", 0.90))
    violations = []

    cycle_fit = None
    if len(single) >= min_items and single and single[0] in "ABCDE":
        base = ord(single[0]) - 65
        hit = sum(1 for i, a in enumerate(single)
                  if a in "ABCDE" and (ord(a) - 65) == (base + i) % 5)
        cycle_fit = hit / len(single)
        if cycle_fit >= limit:
            violations.append({
                "metric": "letter_cycle", "value": round(cycle_fit, 4),
                "items": len(single), "period": 5,
                "why": f"{hit}/{len(single)} 道单选的答案字母等于「起始字母+题号」循环",
            })

    alternate_fit = None
    if len(binary) >= min_items and len(binary) > 1:
        flips = sum(1 for i in range(1, len(binary)) if binary[i] != binary[i - 1])
        alternate_fit = flips / (len(binary) - 1)
        if alternate_fit >= limit:
            violations.append({
                "metric": "binary_alternation", "value": round(alternate_fit, 4),
                "items": len(binary), "flips": flips,
                "why": f"{flips}/{len(binary) - 1} 次相邻判断题答案互异（ABAB 交替）",
            })

    return {
        "rule": "X10", "name": "答案位置周期性",
        "threshold": f"与固定周期的一致率 ≤{limit:.0%}（样本 ≥{min_items} 题）",
        "status": "VIOLATED" if violations else "PASS",
        "items": len(items), "single_items": len(single), "binary_items": len(binary),
        "letter_cycle_fit": round(cycle_fit, 4) if cycle_fit is not None else None,
        "binary_alternation_fit": round(alternate_fit, 4) if alternate_fit is not None else None,
        "violations": violations,
        "sample": [{"qid": _qid(q, i), "answer": answer(q)}
                   for i, q in enumerate(items)][:sample_limit],
        "note": ("X1 只看总量是否均衡，看不出顺序；答案位置必须由内容决定。"
                 "机械轮转 = 学生按题号就能答对。"),
    }


# ── X9 选项尾部模板复用 ─────────────────────────────────────

_TAIL_STRIP = re.compile(r"[\s，,。；;、：:！!？?“”\"'（）()【】\[\]《》<>\-—…]+$")

#: 选项尾部的「空话短语」——这类话无论出现在哪，都说明该选项没有实际内容。
#: 只收「整段收尾」的写法：`需与急性闭角型青光眼鉴别` 这种带具体病名的鉴别是有效内容，
#: 不在此列（正则要求 `需鉴别` 紧邻收尾，中间不许夹病名）。
BOILERPLATE_TAIL = re.compile(
    r"(临床情况需鉴别|需结合临床|结合临床鉴别|结合临床综合判断|结合临床判断|"
    r"结合临床表现|需鉴别|需进一步结合临床|视临床情况而定)$"
)


def _tail(text: str, n: int) -> str:
    s = _TAIL_STRIP.sub("", str(text or "").strip())
    s = re.sub(r"^[A-Za-z]\s*[.．、)）]\s*", "", s)
    return s[-n:] if len(s) >= n else ""


def check_option_template_pollution(items: list[dict], th: dict, sample_limit: int = 15) -> dict:
    """X9：选项尾部模板复用（为了凑长度而贴同一句话）。

    X2 要求「正确项是唯一最长」的题 ≤30%。绕过的办法是给干扰项尾部机械加长，
    于是整批出现同一句无意义后缀——batch049 的 `等临床情况需鉴别` 覆盖 133/250 题、
    298 个选项，其中 24 个还是**正确项**（"交感性眼炎等临床情况需鉴别"）。

    这种文本既不是选项内容，也过不了人工阅读：它是"指标达标"的伪证据。

    指纹只认「枚举概括尾」：选项以 `等 + ≤10 字` 收尾。真实病名（"急性前葡萄
    膜炎"）在 300 题的批次里也会撞同一个 6 字尾巴，只用尾部 n-gram 会大面积误报；
    而 `等XX` 收尾在选择题选项里本身就不成立——选项必须是完整陈述，不能用
    "等"把列举悬空。第二类（不带"等"的纯填充）只在「同题 ≥2 个选项撞同一尾巴
    且覆盖 ≥20% 的题」时才计入，避免把术语当套话。
    """
    tail_n = int(th.get("x9_template_tail", 6))
    q_share = th["x9_template_q_share"]
    min_q = int(th.get("x9_template_min_questions", 3))
    enum_re = re.compile(r"等[^，,。；;、\s]{0,10}$")

    per_template: dict[str, set[str]] = {}
    per_q_options: dict[str, Counter] = {}
    for i, q in enumerate(items):
        qid = _qid(q, i)
        local = Counter()
        for lab, txt in options(q).items():
            s = _TAIL_STRIP.sub("", str(txt or "").strip())
            m = enum_re.search(s)
            fp = ("等:" + m.group(0)) if m else ("tail:" + _tail(txt, tail_n))
            if not fp or fp == "tail:":
                continue  # 选项过短（"3个月"/"正确"），尾部指纹无意义
            local[fp] += 1
            per_template.setdefault(fp, set()).add(qid)
        per_q_options[qid] = local

    total_q = len(items)

    # ── 第二类：空话短语尾（单条即判）──
    # 「等临床情况需鉴别」这类是**跨题复用**才判；而「需结合临床」「需鉴别」收尾的空话，
    # 单条就已经不是选项内容了（选项必须是确定陈述），不设频率门槛。
    phrase_hits = []
    for i, q in enumerate(items):
        qid = _qid(q, i)
        for lab, txt in options(q).items():
            body = _TAIL_STRIP.sub("", str(txt or "").strip())
            m = BOILERPLATE_TAIL.search(body)
            if m:
                phrase_hits.append({"qid": qid, "label": lab, "phrase": m.group(0),
                                    "text": body[-30:]})

    hits, soft = [], []
    for fp, qids in per_template.items():
        share = len(qids) / total_q if total_q else 0.0
        multi_opt_q = sum(1 for qid in qids if per_q_options[qid][fp] >= 2)
        multi_share = multi_opt_q / total_q if total_q else 0.0
        row = {"template": fp, "questions": len(qids), "share": round(share, 4),
               "in_multi_options": multi_opt_q,
               "sample_qids": sorted(qids)[:sample_limit]}
        if len(qids) >= min_q and share > q_share:
            # 只有「等 + 概括词」收尾才判 VIOLATED：这是语法上就不成立的选项形态，
            # 不依赖语义判断。纯尾部 n-gram 复用只作 soft 信号——术语（"急性前葡萄
            # 膜炎"）在几百题的批次里必然撞尾巴，当门禁会大面积误伤。
            if fp.startswith("等:"):
                hits.append(row)
            elif multi_share > 0.20:
                row["why"] = "非枚举尾但同题 ≥2 项且覆盖 ≥20%，疑似填充"
                soft.append(row)
    hits.sort(key=lambda h: -h["questions"])
    soft.sort(key=lambda h: -h["questions"])

    # 正确项也带模板 → 单独点名，这是最坏的一种（答案本身读不通）
    bad_fps = {h["template"] for h in hits}
    correct_hit = []
    for i, q in enumerate(items):
        qid = _qid(q, i)
        opts = options(q)
        ans = {lab for lab in answer(q)}
        for lab, txt in opts.items():
            truth = True if (lab in ans) else None
            for o in q.get("options") or []:
                if isinstance(o, dict) and str(o.get("label", "")).strip().upper() == lab:
                    truth = o.get("is_correct") is True
                    break
            if not truth:
                continue
            s = _TAIL_STRIP.sub("", str(txt or "").strip())
            m = enum_re.search(s)
            fp = ("等:" + m.group(0)) if m else ("tail:" + _tail(txt, tail_n))
            if fp and fp != "tail:" and fp in bad_fps:
                correct_hit.append({"qid": qid, "label": lab, "template": fp,
                                    "text": str(txt)[:40]})
    return {
        "rule": "X9", "name": "选项尾部模板复用",
        "threshold": (f"枚举概括尾（等+≤10字收尾）覆盖 ≤{q_share:.0%} 的题，至少 {min_q} 题；"
                      f"空话短语尾（需鉴别/需结合临床/结合临床…）0 条"),
        "status": "VIOLATED" if (hits or phrase_hits) else "PASS",
        "items": total_q, "templates": len(per_template), "hits": len(hits),
        "boilerplate_tail_items": len(phrase_hits),
        "boilerplate_tail_sample": phrase_hits[:sample_limit],
        "top_templates": hits[:sample_limit],
        "soft_signals": soft[:sample_limit],
        "correct_option_hits": len(correct_hit),
        "correct_option_sample": correct_hit[:sample_limit],
        "violations": ([{"template": h["template"], "questions": h["questions"],
                         "share": h["share"]} for h in hits[:sample_limit]]
                       + [{"qid": p["qid"], "label": p["label"], "phrase": p["phrase"],
                           "why": "选项以空话短语收尾，不是确定陈述"}
                          for p in phrase_hits[:sample_limit]]),
        "note": ("命中说明选项里有跨题复用的尾巴，通常是「为压 X2 唯一最长而给干扰项加长」留下的。"
                 "修法是把干扰项写成真正同层的错误陈述（或把正确项改短），不是加一句套话。"),
    }


# ── 汇总 ────────────────────────────────────────────────────

def audit_batch(items: list[dict], enforce: bool = False, th: dict | None = None,
                batch: str | None = None) -> dict:
    """enforce=True 时任一违例即 FAIL；batch ≥ x_enforce_since 时**指定规则**阻断。

    两种 FAIL 的区别：`enforce` 是人工开的总闸（回测用）；`batch` 是自动闸，
    只对 X7/X9/X10 与 X8 的 TVD/两侧占比生效，历史批次不受影响。
    """
    th = th or thresholds()
    checks = [
        check_answer_distribution(items, th),
        check_unique_longest(items, th),
        check_misconception_reuse(items, th),
        check_reverse_selection(items, th),
        check_reverse_option_anchors(items),
        check_polarity_consistency(items),
        check_structural_coverage(items),
        check_multi_answer_distribution(items, th),
        check_difficulty_type_decoupling(items, th),
        check_option_template_pollution(items, th),
        check_answer_position_periodicity(items, th),
        check_explanation_labels(items, th),
        check_difficulty_consistency(items, th),
    ]
    violated = [c["rule"] for c in checks if c["status"] == "VIOLATED"]
    blocking = [c["rule"] for c in checks if _is_blocking(c, batch, th)]
    if not violated:
        status = "PASS"
    elif enforce or blocking:
        status = "FAIL"
    else:
        status = "ADVISORY"
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "scripts/validate/rules_batch.py",
        "mode": "enforce" if (enforce or blocking) else "advisory",
        "items": len(items),
        "thresholds": th,
        "status": status,
        "batch": batch,
        "violated_rules": violated,
        "blocking_rules": blocking,
        "checks": checks,
        "note": ("batch ≥ x_enforce_since 时，X7/X9/X10 与 X8 的 type_tvd/tier_min_share "
                 "计入 FAIL；其他规则与旧批次只记录不阻断（P2-S3 → AC-P2-09）。"),
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
    ap.add_argument("--batch", "-b", default="", help="批次号（决定 X7–X10 是否阻断；缺省从文件名推断）")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    items = load_items(args.file)
    batch = args.batch or (re.search(r"(batch\d{3}[A-Za-z0-9_\-]*)", str(args.file)) or [None]) and \
        re.search(r"(batch\d{3}[A-Za-z0-9_\-]*)", str(args.file)).group(1)
    rep = audit_batch(items, enforce=args.enforce, batch=batch)
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
