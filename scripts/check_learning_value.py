#!/usr/bin/env python3
"""check_learning_value.py — 题目学习价值契约 v2 试点校验器。

校验项：
  R14 逐项覆盖：per_option 必须与 options 的 label 集合完全一致，不得缺项/多项/重复。
  R15 错误认知：每个错误选项必须有 misconception_id + misconception，且题内唯一。
  R16 来源核验（实证，非自报）：
      - source_quote_status=exact 时 source_quote 不得为空；
      - exact + anchor_status=verified 时，规范化后的 source_quote 必须能在
        teacher_anchor 中逐字找到（省略号分段，逐段命中）；找不到 → FAIL；
      - exact 但锚点为 partial/missing/mismatch → WARN，进入复核队列。
  R17 信息量：correct_rationale≥60 字、why≥20 字、key_takeaway≥30 字；
      不许用“同上/见解析/略”等占位词。
  R19 错误认知 ID 一致性：同一批次内，同一 misconception_id 必须对应同一释义；
      同一 ID 出现多种释义 → WARN + 汇总冲突数（gate 对 v2 批次按 0 冲突阻断）。
  R20 干扰项机制（HC-29 · 2026-11-02）：schema_version ≥ 2.2 的批次，
      每个干扰项的 distractor_mechanism 必须存在且属合法枚举（缺失/非法 → FAIL）；
      2.1 及以下为历史批次，只统计覆盖率不判定（SKIP，不追溯）。
  ANSWER 答案一致性：is_correct 标记必须与 answer 完全一致，per_option.truth 必须与 is_correct 一致。

用法：
  python scripts/check_learning_value.py --file 中间产物/batch040/learning_value_pilot/item_v2_pilot.json
  python scripts/check_learning_value.py --file ... --out reports/validate/learning_value_pilot_batch040.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent

# 2026-11-03 政策：取消“逐题人工医学核验”作为发布前置。
# 下列 quality_flag 属流程/状态说明，不再计入 WARN；真正的风险标记仍会告警。
POLICY_INFO_FLAGS = ("draft", "待独立复核", "未经独立医学核验",
                     "管线v2.2测试", "机制标签已标注")
DEFAULT_OUT = BASE / "reports" / "validate"

PLACEHOLDERS = {"同上", "见解析", "见上", "略", "略述", "无", "n/a", "N/A", "-"}

# HC-29 机制枚举的唯一事实来源是 scripts/validate/rules_batch.py（schema 由
# test_distractor_mechanism_enum_matches_rule_module 保证一致）。这里只做引用，
# 缺模块时才退回本地副本——绝不各写一份然后漂移。
try:
    from validate.rules_batch import MECHANISMS as DISTRACTOR_MECHANISMS
except ImportError:  # pragma: no cover
    try:
        from scripts.validate.rules_batch import MECHANISMS as DISTRACTOR_MECHANISMS
    except ImportError:
        DISTRACTOR_MECHANISMS = (
            "similar_presentation", "adjacent_concept", "direction_error", "timing_error",
            "population_mismatch", "mechanism_confusion", "overgeneralization", "outdated_guideline",
        )

MECHANISM_SINCE = (2, 2)


def _schema_version(q: dict) -> tuple:
    m = re.match(r"^(\d+)\.(\d+)$", str(q.get("schema_version") or "").strip())
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _nonempty(s) -> bool:
    return isinstance(s, str) and s.strip() and s.strip() not in PLACEHOLDERS


def _labels(options) -> list[str]:
    return [str(o.get("label", "")).strip() for o in options if isinstance(o, dict)]


def _answer_set(answer) -> set[str]:
    if isinstance(answer, (list, tuple, set)):
        return {str(x).strip().upper() for x in answer if str(x).strip()}
    return set(str(answer or "").strip().upper())


def _bigrams(s: str) -> set[str]:
    """中文/英文混合文本的 2-gram 集合，用于轻量主题覆盖度。"""
    s = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", str(s or ""))
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else set()


def _norm_text(s) -> str:
    """归一化用于逐字比对：去空白、标点、引号、括号与破折号。"""
    return re.sub(r"[\s，。；：、,.;:!?！？\"'“”‘’（）()【】\[\]《》<>·\-—–…]+", "", str(s or ""))


_QUOTE_SPLIT = re.compile(r"(?:…|⋯|\.{3,})")


def _quote_supported(quote, anchor) -> bool:
    """source_quote 是否能在 teacher_anchor 中逐字命中（省略号分段逐段命中）。"""
    a = _norm_text(anchor)
    if not a:
        return False
    segments = [_norm_text(p) for p in _QUOTE_SPLIT.split(str(quote or ""))]
    segments = [s for s in segments if s]
    return bool(segments) and all(s in a for s in segments)


def _normalize_options(options, answer: str) -> list[dict]:
    """兼容三种历史 options 形态，并补齐 is_correct。

    - dict: {"A": "text", ...} → 标签顺序按 A/B/C...
    - list[dict]: [{label,text}] 或 [{label,text,is_correct}]
    - list[str]: ["A. text", ...]
    is_correct 缺省时按 answer 推导（answer 是答案键，不是陈述真值）。
    """
    answer_set = _answer_set(answer)
    out: list[dict] = []
    if isinstance(options, dict):
        for k, v in options.items():
            label = str(k).strip().upper()
            out.append({"label": label, "text": str(v), "is_correct": label in answer_set})
        return out
    if isinstance(options, list):
        for i, o in enumerate(options):
            if isinstance(o, dict):
                label = str(o.get("label", chr(65 + i))).strip().upper()
                text = str(o.get("text", "")).strip()
                is_correct = o.get("is_correct")
                if not isinstance(is_correct, bool):
                    is_correct = label in answer_set
                out.append({"label": label, "text": text, "is_correct": is_correct})
            elif isinstance(o, str):
                m = re.match(r"^([A-H])[.、）)\s]+(.*)$", o.strip())
                label = m.group(1) if m else chr(65 + i)
                text = (m.group(2) if m else o.strip()).strip()
                out.append({"label": label, "text": text, "is_correct": label in answer_set})
    return out


def check_item(q: dict) -> dict:
    issues: list[dict] = []
    warnings: list[dict] = []
    qid = str(q.get("id") or "<missing-id>")

    answer_raw = q.get("answer") or q.get("answer_key") or q.get("correct_answer") or ""
    answer_set = _answer_set(answer_raw)
    answer = ("".join(sorted(answer_set)) if isinstance(answer_raw, (list, tuple, set))
              else str(answer_raw).strip().upper())
    opts = _normalize_options(q.get("options") or [], answer_raw)
    lv = q.get("learning_value") or {}
    labels = _labels(opts)
    label_set = set(labels)
    correct_labels = {str(o.get("label")) for o in opts if o.get("is_correct") is True}
    polarity = str(q.get("polarity") or "positive").strip().lower()
    negative = polarity in ("negative", "反选")
    distractor_labels = label_set - answer_set

    # ANSWER：答案键与 is_correct 必须一致
    if answer_set != correct_labels:
        issues.append({
            "rule": "ANSWER",
            "detail": f"answer={answer or '∅'} 与 is_correct={sorted(correct_labels) or '∅'} 不一致",
        })

    # R14：逐项覆盖
    per = lv.get("per_option") or []
    per_labels = [str(p.get("label", "")).strip() for p in per if isinstance(p, dict)]
    if len(per_labels) != len(set(per_labels)):
        issues.append({"rule": "R14", "detail": "per_option 存在重复 label"})
    if set(per_labels) != label_set:
        missing = sorted(label_set - set(per_labels))
        extra = sorted(set(per_labels) - label_set)
        issues.append({
            "rule": "R14",
            "detail": f"per_option 未覆盖全部选项；缺失={missing or '无'} 多余={extra or '无'}",
        })

    # R15 / R17：逐项错误认知与信息量
    # 注意：truth 表示“该选项陈述本身是否为真”，is_correct 表示“是否为答案”。
    # 正选题二者一致；反选题（不包括/错误/除外）二者相反。
    misconception_ids: list[str] = []
    distractor_count = 0
    distractor_covered = 0
    # 正选题的「错误认知覆盖」与反选题的「为真项锚点覆盖」分开统计：
    # 混在一个分母里，两种完全不同的要求会被平均成一个看不出问题的数字。
    mc_total = 0
    mc_covered = 0
    ra_total = 0
    ra_covered = 0
    mech_covered = 0
    mech_missing: list[str] = []
    mech_invalid: list[str] = []
    per_by_label = {str(p.get("label", "")).strip(): p for p in per if isinstance(p, dict)}
    for o in opts:
        lab = str(o.get("label", "")).strip()
        p = per_by_label.get(lab) or {}
        is_correct = o.get("is_correct") is True
        expected_truth = (not is_correct) if negative else is_correct
        if p.get("truth") is not expected_truth:
            issues.append({
                "rule": "R15",
                "detail": f"{lab} 的 truth={p.get('truth')} 与极性不符（polarity={polarity}, 期望 {expected_truth}）",
            })
        why = p.get("why")
        if not _nonempty(why) or len(str(why).strip()) < 20:
            issues.append({"rule": "R17", "detail": f"{lab} 的 why 为空或信息量不足（<20字）"})
        if lab not in distractor_labels:
            continue
        distractor_count += 1
        if negative:
            # 反选题（P2-S4）：非答案项是**为真说法**。
            #   必填 = 逐项锚点（这句对的话出自教材哪段）
            #   可选 = misconception（描述「学生为什么误选它」，通常是忽略否定词）
            # 原口径把两者都按正选题处理，既漏了锚点，又把 misconception 当成
            # 「这句话错在哪」——语义上反了。
            ra_total += 1
            opt_anchor = str(p.get("source_anchor") or p.get("anchor") or "").strip()
            item_anchor = str(lv.get("answer_evidence") or "").strip()
            if opt_anchor or item_anchor:
                ra_covered += 1
                distractor_covered += 1
            elif _schema_version(q) >= MECHANISM_SINCE:
                issues.append({
                    "rule": "R15",
                    "detail": f"{lab} 为反选题的为真干扰项，缺逐项锚点 source_anchor（P2-S4）",
                })
            else:
                warnings.append({
                    "rule": "R15",
                    "detail": f"{lab} 为反选题的为真干扰项但无锚点（历史批次不追溯）",
                })
            # 写了就收：R19 的 ID 一致性也要覆盖反选题，否则这里成盲区。
            mid = p.get("misconception_id")
            if _nonempty(mid):
                misconception_ids.append(str(mid).strip())
        else:
            mc_total += 1
            mid = p.get("misconception_id")
            mtext = p.get("misconception")
            if not _nonempty(mid):
                issues.append({"rule": "R15", "detail": f"{lab} 为干扰项但缺 misconception_id"})
            else:
                misconception_ids.append(str(mid).strip())
                distractor_covered += 1
                mc_covered += 1
            if not _nonempty(mtext):
                issues.append({"rule": "R15", "detail": f"{lab} 为干扰项但缺 misconception 描述"})

        # R20（HC-29）：干扰项机制标签
        mech = p.get("distractor_mechanism")
        if _nonempty(mech):
            mstr = str(mech).strip()
            if mstr in DISTRACTOR_MECHANISMS:
                mech_covered += 1
            else:
                mech_invalid.append(f"{lab}:{mstr}")
        else:
            mech_missing.append(lab)

    # R20 判定按版本分档：2.2+ 缺标签/非法标签 → FAIL；历史批次只统计不判定
    # （不逐题挂 WARN，否则 200 题全变 WARN，把真正的告警淹掉；批次汇总里有覆盖率）。
    mech_required = _schema_version(q) >= MECHANISM_SINCE
    if mech_required:
        for lab in mech_missing:
            issues.append({"rule": "R20", "detail": f"{lab} 为干扰项但缺 distractor_mechanism（HC-29）"})
        for item in mech_invalid:
            issues.append({"rule": "R20", "detail": f"distractor_mechanism 非法：{item}"})

    # 同一题内多个干扰项可以共享一个错误认知类别（如“器械功能混淆”），
    # 因此不把重复 ID 当问题；真正要防的是“每个错误选项都没有标签”。

    rationale = lv.get("correct_rationale")
    if not _nonempty(rationale) or len(str(rationale).strip()) < 60:
        issues.append({"rule": "R17", "detail": "correct_rationale 为空或信息量不足（<60字）"})
    takeaway = lv.get("key_takeaway")
    if not _nonempty(takeaway) or len(str(takeaway).strip()) < 30:
        issues.append({"rule": "R17", "detail": "key_takeaway 为空或信息量不足（<30字）"})

    # R16：来源核验（实证）
    sq_status = str(lv.get("source_quote_status") or "").strip()
    sq = lv.get("source_quote") or ""
    anchor = str(lv.get("anchor_status") or "").strip()
    anchor_text = str(q.get("teacher_anchor") or "").strip()
    legal_anchor = {"verified", "partial", "mismatch", "missing"}
    quote_checked = sq_status == "exact"
    quote_supported = _quote_supported(sq, anchor_text) if quote_checked else False
    if sq_status not in {"exact", "paraphrase", "missing", "mismatch"}:
        issues.append({"rule": "R16", "detail": f"source_quote_status 非法：{sq_status or '空'}"})
    if anchor not in legal_anchor:
        issues.append({"rule": "R16", "detail": f"anchor_status 非法：{anchor or '空'}"})
    if sq_status == "exact":
        if not _nonempty(sq):
            issues.append({"rule": "R16", "detail": "source_quote_status=exact 但 source_quote 为空"})
        elif anchor == "verified":
            if not anchor_text:
                issues.append({"rule": "R16", "detail": "exact+verified 但缺 teacher_anchor，无法实证"})
            elif not quote_supported:
                issues.append({
                    "rule": "R16",
                    "detail": "source_quote 未能在 teacher_anchor 中逐字命中（禁止自报 exact）",
                })
        elif not quote_supported:
            warnings.append({
                "rule": "R16",
                "detail": f"source_quote 未能在 teacher_anchor 中逐字命中（anchor_status={anchor}），需复核",
            })
    if sq_status in {"missing", "mismatch"}:
        warnings.append({"rule": "R16", "detail": f"source_quote_status={sq_status}，需补原文"})
    if anchor in {"partial", "mismatch", "missing"}:
        warnings.append({"rule": "R16", "detail": f"anchor_status={anchor}，需复核锚点"})

    # 质量标记：政策/流程类信息只记录不告警（2026-11-03）；其余仍进复核队列
    flags = lv.get("quality_flags") or []
    informational_flags = []
    for f in flags:
        text = str(f)
        if any(key in text for key in POLICY_INFO_FLAGS):
            informational_flags.append(text)
        else:
            warnings.append({"rule": "QUALITY_FLAG", "detail": text})

    # R18：锚点主题覆盖度（题干 2-gram 被 teacher_anchor 覆盖的比例）
    # 病例题（A2/A3/A4/案例）题干含大量病例细节，锚文通常是通用规则，
    # 因此阈值低于纯知识点题；阈值仅用于“复核队列”，不是硬性对错。
    anchor_thresholds = {"A2": 0.03, "A3": 0.03, "A4": 0.03, "案例": 0.03,
                         "X": 0.05, "A1": 0.10, "判断": 0.10, "B1": 0.05}
    anchor_threshold = anchor_thresholds.get(str(q.get("type") or "").strip(), 0.05)
    stem_terms = _bigrams(q.get("stem"))
    anchor_terms = _bigrams(anchor_text)
    if not anchor_text:
        warnings.append({"rule": "R18", "detail": "缺 teacher_anchor，无法做主题对齐"})
        anchor_overlap = 0.0
    elif stem_terms and anchor_terms:
        anchor_overlap = len(stem_terms & anchor_terms) / len(stem_terms)
        if anchor_overlap < anchor_threshold:
            warnings.append({
                "rule": "R18",
                "detail": f"teacher_anchor 对题干主题覆盖度低（{anchor_overlap:.3f} < {anchor_threshold:.2f}），需复核是否错配",
            })
    else:
        anchor_overlap = 0.0

    # 统计信息量
    all_texts = [str(rationale or ""), str(takeaway or "")]
    all_texts += [str(p.get("why") or "") for p in per if isinstance(p, dict)]
    info_units = sum(1 for t in all_texts if _nonempty(t))
    chars = [len(t.strip()) for t in all_texts if _nonempty(t)]

    return {
        "id": qid,
        "type": q.get("type"),
        "module": q.get("module"),
        "options": len(opts),
        "per_option": len(per),
        "distractors": distractor_count,
        "distractors_covered": distractor_covered,
        "mc_total": mc_total,
        "mc_covered": mc_covered,
        "reverse_anchor_total": ra_total,
        "reverse_anchor_covered": ra_covered,
        "negative": negative,
        "mechanism_covered": mech_covered,
        "mechanism_missing": len(mech_missing),
        "mechanism_invalid": len(mech_invalid),
        "mechanism_required": mech_required,
        "misconceptions": len(set(misconception_ids)),
        "info_units": info_units,
        "median_chars": round(statistics.median(chars), 1) if chars else 0,
        "source_quote_status": sq_status,
        "quote_checked": quote_checked,
        "quote_supported": quote_supported,
        "anchor_status": anchor,
        "anchor_overlap": round(anchor_overlap, 4),
        "anchor_threshold": anchor_threshold,
        "issues": issues,
        "warnings": warnings,
        "informational_flags": informational_flags,
        "status": "FAIL" if issues else ("WARN" if warnings else "PASS"),
    }


def _misconception_index(data: list[dict]) -> tuple[dict, list[set[str]]]:
    """建立 misconception_id → {归一化释义: 题号集合}，并记录每题使用的 ID。"""
    index: dict[str, dict[str, set[str]]] = {}
    item_ids: list[set[str]] = []
    for q in data:
        qid = str(q.get("id") or "<missing-id>")
        used: set[str] = set()
        lv = q.get("learning_value") or {}
        for p in lv.get("per_option") or []:
            if not isinstance(p, dict):
                continue
            mid = str(p.get("misconception_id") or "").strip()
            text = _norm_text(p.get("misconception"))
            if not mid or not text:
                continue
            used.add(mid)
            index.setdefault(mid, {}).setdefault(text, set()).add(qid)
        item_ids.append(used)
    return index, item_ids


def audit_batch(data: list[dict]) -> tuple[list[dict], dict]:
    """逐题校验 + 批次级 R19 错误认知 ID 一致性，返回（逐题结果, 汇总）。"""
    results = [check_item(q) for q in data]
    index, item_ids = _misconception_index(data)
    conflict_ids = {mid for mid, texts in index.items() if len(texts) > 1}
    for i, used in enumerate(item_ids):
        hit = sorted(used & conflict_ids)
        if not hit:
            continue
        results[i]["warnings"].append({
            "rule": "R19",
            "detail": "同一 misconception_id 在本批次内有多种释义：" + "、".join(hit),
        })
        if results[i]["status"] == "PASS":
            results[i]["status"] = "WARN"

    fails = [r for r in results if r["status"] == "FAIL"]
    warns = [r for r in results if r["status"] == "WARN"]
    passes = [r for r in results if r["status"] == "PASS"]

    total = len(results)
    per_cov = sum(1 for r in results if r["per_option"] == r["options"]) / total if total else 0
    # 错误认知覆盖只算正选题；反选题的为真干扰项另算锚点覆盖（P2-S4）。
    false_total = sum(r.get("mc_total", 0) for r in results)
    false_covered = sum(r.get("mc_covered", 0) for r in results)
    misconception_cov = false_covered / false_total if false_total else 0
    ra_total_all = sum(r.get("reverse_anchor_total", 0) for r in results)
    ra_cov_all = sum(r.get("reverse_anchor_covered", 0) for r in results)
    reverse_anchor_cov = ra_cov_all / ra_total_all if ra_total_all else 1.0
    reverse_items = sum(1 for r in results if r.get("negative"))
    source_exact = sum(1 for r in results if r["source_quote_status"] == "exact") / total if total else 0
    quote_total = sum(1 for r in results if r["quote_checked"])
    quote_ok = sum(1 for r in results if r["quote_checked"] and r["quote_supported"])
    quote_rate = quote_ok / quote_total if quote_total else 1.0
    anchor_verified = sum(1 for r in results if r["anchor_status"] == "verified") / total if total else 0
    anchor_low = sum(1 for r in results if r["anchor_overlap"] < r["anchor_threshold"])

    mech_total = sum(r["distractors"] for r in results)
    mech_ok = sum(r["mechanism_covered"] for r in results)
    mech_cov = mech_ok / mech_total if mech_total else 0
    mech_required = any(r.get("mechanism_required") for r in results)
    mech_status = ("PASS" if mech_cov >= 1.0 else "FAIL") if mech_required else "SKIP"

    summary = {
        "total": total,
        "pass": len(passes),
        "warn": len(warns),
        "fail": len(fails),
        "per_option_coverage": round(per_cov, 4),
        "misconception_coverage": round(misconception_cov, 4),
        "misconception_denominator": false_total,
        "reverse_items": reverse_items,
        "reverse_anchor_coverage": round(reverse_anchor_cov, 4),
        "reverse_anchor_denominator": ra_total_all,
        "distractor_mechanism_coverage": round(mech_cov, 4),
        "distractor_mechanism_required": mech_required,
        "distractor_mechanism_status": mech_status,
        "distractor_mechanism_tagged": mech_ok,
        "distractor_mechanism_total": mech_total,
        "source_quote_exact_rate": round(source_exact, 4),
        "quote_verified_rate": round(quote_rate, 4),
        "misconception_id_conflicts": len(conflict_ids),
        "anchor_verified_rate": round(anchor_verified, 4),
        "anchor_low_overlap_count": anchor_low,
        "informational_flag_count": sum(len(r.get("informational_flags") or []) for r in results),
    }
    return results, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="item_v2 JSON 文件（数组）")
    ap.add_argument("--batch", default="", help="报告所属批次")
    ap.add_argument("--out", default=str(DEFAULT_OUT / "learning_value_pilot.json"), help="报告输出路径")
    args = ap.parse_args()

    src = Path(args.file)
    raw = src.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, list):
        print("[FAIL] 输入必须是 JSON 数组", file=sys.stderr)
        return 2

    batch = args.batch
    if not batch:
        match = re.fullmatch(r"learning_value_(batch\d+)\.json", Path(args.out).name, re.IGNORECASE)
        if match and int(match.group(1)[5:]) >= 44:
            batch = match.group(1)

    results, summary = audit_batch(data)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "file": str(src),
        "batch": batch,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "summary": summary,
        "items": results,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"总题数 {summary['total']} | PASS {summary['pass']} | WARN {summary['warn']} | FAIL {summary['fail']}")
    print(
        f"逐项覆盖 {summary['per_option_coverage']:.1%} | 错误认知覆盖 {summary['misconception_coverage']:.1%} | "
        f"标注 exact {summary['source_quote_exact_rate']:.1%} | 引文实证 {summary['quote_verified_rate']:.1%} | "
        f"ID 冲突 {summary['misconception_id_conflicts']} | 锚点已核 {summary['anchor_verified_rate']:.1%}"
    )
    print(
        f"干扰项机制标签 {summary['distractor_mechanism_coverage']:.1%}"
        f"（{summary['distractor_mechanism_tagged']}/{summary['distractor_mechanism_total']}）"
        f" | R20 判定 {summary['distractor_mechanism_status']}"
        + ("" if summary["distractor_mechanism_required"]
           else "（历史批次 schema<2.2，不追溯，仅统计）")
    )
    print(f"报告：{out}")
    for r in results:
        mark = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}[r["status"]]
        print(f"[{mark}] {r['id']} | per_option={r['per_option']}/{r['options']} | 错误认知={r['misconceptions']} | 中位={r['median_chars']}字")
        for i in r["issues"]:
            print(f"  - {i['rule']}: {i['detail']}")
        for w in r["warnings"]:
            print(f"  ! {w['rule']}: {w['detail']}")

    return 1 if summary["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
