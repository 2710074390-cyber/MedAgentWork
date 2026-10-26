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
  ANSWER 答案一致性：is_correct 标记必须与 answer 完全一致，per_option.truth 必须与 is_correct 一致。

用法：
  python scripts/check_learning_value.py --file 中间产物/batch040/learning_value_pilot/item_v2_pilot.json
  python scripts/check_learning_value.py --file ... --out reports/validate/learning_value_pilot_batch040.json
"""
from __future__ import annotations

import argparse
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
DEFAULT_OUT = BASE / "reports" / "validate"

PLACEHOLDERS = {"同上", "见解析", "见上", "略", "略述", "无", "n/a", "N/A", "-"}


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
        mid = p.get("misconception_id")
        mtext = p.get("misconception")
        if not _nonempty(mid):
            issues.append({"rule": "R15", "detail": f"{lab} 为干扰项但缺 misconception_id"})
        else:
            misconception_ids.append(str(mid).strip())
            distractor_covered += 1
        if not _nonempty(mtext):
            issues.append({"rule": "R15", "detail": f"{lab} 为干扰项但缺 misconception 描述"})

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

    # 质量标记本身也是复核队列
    flags = lv.get("quality_flags") or []
    for f in flags:
        warnings.append({"rule": "QUALITY_FLAG", "detail": str(f)})

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
    false_total = sum(r["distractors"] for r in results)
    false_covered = sum(r["distractors_covered"] for r in results)
    misconception_cov = false_covered / false_total if false_total else 0
    source_exact = sum(1 for r in results if r["source_quote_status"] == "exact") / total if total else 0
    quote_total = sum(1 for r in results if r["quote_checked"])
    quote_ok = sum(1 for r in results if r["quote_checked"] and r["quote_supported"])
    quote_rate = quote_ok / quote_total if quote_total else 1.0
    anchor_verified = sum(1 for r in results if r["anchor_status"] == "verified") / total if total else 0
    anchor_low = sum(1 for r in results if r["anchor_overlap"] < r["anchor_threshold"])

    summary = {
        "total": total,
        "pass": len(passes),
        "warn": len(warns),
        "fail": len(fails),
        "per_option_coverage": round(per_cov, 4),
        "misconception_coverage": round(misconception_cov, 4),
        "source_quote_exact_rate": round(source_exact, 4),
        "quote_verified_rate": round(quote_rate, 4),
        "misconception_id_conflicts": len(conflict_ids),
        "anchor_verified_rate": round(anchor_verified, 4),
        "anchor_low_overlap_count": anchor_low,
    }
    return results, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="item_v2 JSON 文件（数组）")
    ap.add_argument("--out", default=str(DEFAULT_OUT / "learning_value_pilot.json"), help="报告输出路径")
    args = ap.parse_args()

    src = Path(args.file)
    data = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("[FAIL] 输入必须是 JSON 数组", file=sys.stderr)
        return 2

    results, summary = audit_batch(data)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "file": str(src),
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
