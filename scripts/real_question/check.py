# -*- coding: utf-8 -*-
"""check.py — 真题双族配额 / 教师重点覆盖 / 答案可信 / 去重 / license 终审门禁。

执业医师族 = 历年真题（zhiyi_pdf）+ CMExam（zhiyi），比例按族结算（15%–25%）。
"""
from __future__ import annotations

import json
from pathlib import Path

from .retrieval import parse_keypoints
from .schema import PUBLIC_LICENSES, exact_hash, hamming, simhash64

BASE = Path(__file__).resolve().parent.parent.parent


def _load_questions(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("questions", []) or []
    return data if isinstance(data, list) else []


def _refs(q: dict) -> list[str]:
    value = q.get("keypoint_ref") or q.get("keypoint_refs") or q.get("teacher_keypoint_refs") or []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out = []
        for x in value:
            if isinstance(x, str):
                out.append(x)
            elif isinstance(x, dict):
                out.append(str(x.get("ref") or x.get("id") or ""))
        return [x for x in out if x]
    return []


def _source(q: dict) -> str:
    """返回 kaoyan | zhiyi_pdf | zhiyi | original（zhiyi_pdf=执业医师历年真题）。"""
    if q.get("kaoyan_origin"):
        return "kaoyan"
    if q.get("zhiyi_pdf_origin"):
        return "zhiyi_pdf"
    origin = q.get("zhiyi_origin") or {}
    if isinstance(origin, dict) and origin.get("corpus") in ("pdf_paper", "zhiyi_pdf"):
        return "zhiyi_pdf"
    if origin or q.get("source") in ("zhiyi", "zhiyi_pdf"):
        return "zhiyi_pdf" if q.get("source") == "zhiyi_pdf" else "zhiyi"
    return "original"


def run_check(
    file_path: str | Path,
    plan_path: str | Path | None = None,
    keypoints_path: str | Path | None = None,
    build: str = "public",
    require_ratio: float = 0.15,
    max_ratio: float = 0.25,
) -> dict:
    questions = _load_questions(file_path)
    total = len(questions)
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8")) if plan_path and Path(plan_path).exists() else {}
    selected_by_source_id = {
        str(x.get("source_id")): x for x in plan.get("selected", [])
    }

    counts = {"kaoyan": 0, "zhiyi_pdf": 0, "zhiyi": 0, "original": 0}
    low_confidence: list[str] = []
    license_violations: list[str] = []
    missing_trace: list[str] = []
    for q in questions:
        source = _source(q)
        counts[source] += 1
        qid = str(q.get("id") or q.get("qid") or "")
        origin = q.get("kaoyan_origin") or q.get("zhiyi_pdf_origin") or q.get("zhiyi_origin") or {}
        source_id = str(origin.get("gs_id") or origin.get("source_id") or "")
        plan_item = selected_by_source_id.get(source_id)
        # 答案可信：优先看题库字段，其次看 plan
        conf = q.get("answer_confidence") or (plan_item or {}).get("answer_confidence")
        if source in ("kaoyan", "zhiyi", "zhiyi_pdf") and conf not in ("high", "medium"):
            low_confidence.append(qid or source_id)
        # license：公开构建只允许 public / public_noncommercial；缺失也视为不合格
        lic = q.get("license") or (plan_item or {}).get("license")
        if build == "public" and source in ("kaoyan", "zhiyi", "zhiyi_pdf") and lic not in PUBLIC_LICENSES:
            license_violations.append(qid or source_id)
        # 溯源
        if source in ("kaoyan", "zhiyi", "zhiyi_pdf"):
            if not source_id or not _refs(q):
                missing_trace.append(qid or source_id)

    ratios = {k: round(v / total, 4) if total else 0.0 for k, v in counts.items()}
    family_counts = {
        "kaoyan": counts["kaoyan"],
        "zhiyi": counts["zhiyi_pdf"] + counts["zhiyi"],
        "original": counts["original"],
    }
    family_ratios = {k: round(v / total, 4) if total else 0.0 for k, v in family_counts.items()}
    kp_total = 0
    uncovered: list[str] = []
    invalid_refs: list[str] = []
    if keypoints_path:
        kps = parse_keypoints(keypoints_path)
        kp_total = len(kps)
        valid_refs = {kp.ref for kp in kps}
        covered = set()
        for q in questions:
            refs = _refs(q)
            covered.update(refs)
            invalid = [r for r in refs if r not in valid_refs]
            if invalid:
                invalid_refs.append(f"{q.get('id', '')}:{','.join(invalid)}")
        uncovered = [kp.ref for kp in kps if kp.ref not in covered]

    # 去重
    exact: dict[str, int] = {}
    sims: list[tuple[int, int]] = []
    duplicates = 0
    for i, q in enumerate(questions):
        stem = str(q.get("stem") or "")
        opts = q.get("options") or []
        h = exact_hash(stem, opts if isinstance(opts, list) else [])
        if h in exact:
            duplicates += 1
        else:
            exact[h] = i
        s = simhash64(stem + " " + " ".join(str(x) for x in opts))
        if any(hamming(s, old) <= 3 for old, _ in sims):
            duplicates += 1
        else:
            sims.append((s, i))

    # 判定
    failures = []
    allowed_shortfalls: list[str] = []
    plan_status = plan.get("quota_status", {}) if plan else {}
    if total == 0:
        failures.append("empty_question_bank")
    else:
        for fam in ("kaoyan", "zhiyi"):
            ratio = family_counts[fam] / total
            st = plan_status.get(fam, {}) if plan else {}
            # 只有「候选不足（减量/取消/用尽）」才允许低于 15%
            shortfall_ok = st.get("status") in ("reduced", "cancelled", "insufficient", "unavailable")
            if ratio < require_ratio and not shortfall_ok:
                failures.append(f"{fam}_ratio_below_{require_ratio}")
            if ratio < require_ratio and shortfall_ok:
                allowed_shortfalls.append(fam)
            if ratio > max_ratio:
                failures.append(f"{fam}_ratio_above_{max_ratio}")
    if low_confidence:
        failures.append("low_answer_confidence")
    if license_violations:
        failures.append("license_violation")
    if missing_trace:
        failures.append("missing_source_or_keypoint_trace")
    if duplicates:
        failures.append("duplicate_questions")
    if invalid_refs:
        failures.append("invalid_keypoint_ref")
    if kp_total and uncovered:
        failures.append("keypoint_uncovered")

    return {
        "file": str(file_path),
        "build": build,
        "total": total,
        "counts": counts,
        "ratios": ratios,
        "family_counts": family_counts,
        "family_ratios": family_ratios,
        "quota_target": {"kaoyan": 0.20, "zhiyi": 0.20, "band": [require_ratio, max_ratio]},
        "keypoint_coverage": {
            "total": kp_total,
            "uncovered": uncovered,
            "invalid_refs": invalid_refs,
            "rate": round(1 - len(uncovered) / kp_total, 4) if kp_total else None,
        },
        "low_answer_confidence": low_confidence,
        "license_violations": license_violations,
        "missing_trace": missing_trace,
        "duplicates": duplicates,
        "plan_quota_status": plan.get("quota_status", {}),
        "allowed_shortfalls": allowed_shortfalls,
        "pass": not failures,
        "failures": failures,
    }


def print_report(report: dict) -> None:
    print(f"📊 真题终审：{report['file']}")
    c, r = report["counts"], report["ratios"]
    print(f"  总题数：{report['total']}；考研 {c['kaoyan']}（{r['kaoyan']*100:.1f}%）；"
          f"执医 {c['zhiyi'] + c['zhiyi_pdf']}（{(r['zhiyi'] + r['zhiyi_pdf'])*100:.1f}%"
          f" = 历年真题 {c['zhiyi_pdf']} + CMExam {c['zhiyi']}）；原创 {c['original']}")
    kp = report["keypoint_coverage"]
    if kp["total"]:
        print(f"  教师重点覆盖：{kp['total']-len(kp['uncovered'])}/{kp['total']}（{kp['rate']*100:.1f}%）")
    if report["duplicates"]:
        print(f"  ⚠️ 重复/近重复：{report['duplicates']}")
    if report["low_answer_confidence"]:
        print(f"  ⚠️ 低可信答案：{len(report['low_answer_confidence'])}")
    if report["license_violations"]:
        print(f"  ⚠️ license 违规：{len(report['license_violations'])}")
    if report["missing_trace"]:
        print(f"  ⚠️ 缺溯源/keypoint：{len(report['missing_trace'])}")
    if report.get("allowed_shortfalls"):
        print(f"  ⚠️ 允许短缺（相关候选已用尽/不可用）：{', '.join(report['allowed_shortfalls'])}")
    if report["pass"]:
        print("  ✅ PASS")
    else:
        print("  ✗ FAIL：" + ", ".join(report["failures"]))
