#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""quality_gate.py — R0–R4 全流程质量门禁编排器（HC-25）。

设计原则
    - 只读源产物与既有报告；不修改源题库/源复习资料/workflow_state。
    - 复用已有确定性脚本（pilot_baseline / kc_registry / check_learning_value /
      review_scorecard / verify_produce_rules / check_site_freshness / check_site_links）。
    - PASS / WARN / FAIL / SKIP 必须显式记录；SKIP 不得当作 PASS。
    - advisory 模式：FAIL 降级为 WARN，退出码 0；enforce 模式：required FAIL → 退出码 1。

用法
    python scripts/quality_gate.py --stage r2 --batch batch040 --profile pilot --mode advisory
    python scripts/quality_gate.py --stage r3 --batch batch040 --profile release_teacher_keypoint --mode enforce
    python scripts/quality_gate.py --stage r0 --batch batch040 --mode advisory
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def _configure_stdio() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


BASE = Path(__file__).resolve().parent.parent
DEFAULT_REVIEW = BASE / "复习资料/耳鼻咽喉头颈外科学教师重点版/耳鼻咽喉头颈外科学教师重点版_主复习资料.md"
DEFAULT_KC = BASE / "中间产物/batch040/pilot/kc_registry.json"
DEFAULT_BASELINE = BASE / "中间产物/batch040/pilot/baseline_manifest.json"
DEFAULT_QUESTIONS = BASE / "最终产物/batch040/ALL_questions_FIXED.json"
DEFAULT_LEARNING_VALUE = BASE / "reports/validate/learning_value_v2_batch040_20261022.json"
DEFAULT_SCORECARD = BASE / "reports/validate/review_scorecard_ent_20261022.json"
DEFAULT_RUBRIC = BASE / "中间产物/batch040/pilot/review_score_rubric.json"
DEFAULT_POLICY = BASE / "scripts/quality_policy.json"
DEFAULT_PLAN = BASE / "reports/research/medical-review-material-optimization-research-20261022/试点项目实施计划.md"
DEFAULT_SPEC = BASE / "docs/质量管控规范.md"
DEFAULT_KEYPOINTS = BASE / "输入素材/大四上/耳鼻咽喉头颈外科学/耳鼻咽喉头颈外科学_教师重点_锚定清单_20261019.md"
DEFAULT_BLUEPRINT = BASE / "中间产物/batch040/出题蓝图_batch040.md"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def run_cmd(cmd: list[str], timeout: int = 300) -> dict:
    try:
        proc = subprocess.run(
            cmd, cwd=BASE, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return {
            "command": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-2000:],
            "stderr": (proc.stderr or "")[-2000:],
        }
    except FileNotFoundError as exc:
        return {"command": " ".join(cmd), "returncode": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired:
        return {"command": " ".join(cmd), "returncode": 124, "stdout": "", "stderr": "timeout"}


def check_item(check_id: str, status: str, reason: str, *, required: bool = True,
               details: dict | None = None) -> dict:
    return {
        "id": check_id,
        "status": status,
        "required": required,
        "reason": reason,
        "details": details or {},
    }


def _load_policy(path: Path) -> dict:
    import quality_policy
    return quality_policy.load_policy(path)


def _ratio(n, d) -> float:
    return float(n) / float(d) if d else 0.0


def _batch_state(batch: str) -> dict:
    """只读 workflow_state.json，取批次记录。"""
    try:
        state = read_json(BASE / "workflow_state.json")
        batch_data = state.get(batch) if isinstance(state, dict) else None
        return batch_data if isinstance(batch_data, dict) else {}
    except Exception:
        return {}


def _batch_subject(batch: str) -> str:
    return str(_batch_state(batch).get("subject") or "")


def infer_batch_products(batch: str) -> set[str]:
    """轻量产物类型推断（与 gate_check.infer_product_types 同口径）。"""
    data = _batch_state(batch)
    explicit = data.get("product_types")
    if isinstance(explicit, str):
        explicit = [explicit]
    if isinstance(explicit, (list, tuple, set)):
        picked = {str(x).strip() for x in explicit if str(x).strip() in
                  ("question_bank", "prediction_paper", "review_material")}
        if picked:
            return picked

    subject = str(data.get("subject") or "")
    marker = subject + str(data.get("chapter") or "") + str(data.get("exam_type") or "")
    final_dir = BASE / "最终产物" / batch
    final_md = [p.name for p in final_dir.glob("*.md")] if final_dir.exists() else []
    raw_steps = data.get("steps") if isinstance(data.get("steps"), dict) else {}
    types: set[str] = set()
    if "押题" in marker or any("押题" in x for x in final_md):
        types.add("prediction_paper")
    has_json = bool(list(final_dir.glob("ALL_questions_FIXED*.json"))) if final_dir.exists() else False
    if has_json or "AGENT2" in raw_steps:
        types.add("question_bank")
    review_dir = BASE / "复习资料"
    has_review = bool(subject and review_dir.exists()
                      and list(review_dir.rglob(f"{subject}*主复习资料.md")))
    if "AGENT5" in raw_steps or has_review or (data.get("final_review") and not types):
        types.add("review_material")
    return types or {"question_bank"}


def derive_batch_defaults(args) -> None:
    """按 --batch 派生批次级默认路径；显式传参优先，不覆盖用户输入。"""
    batch = args.batch
    final_dir = BASE / "最终产物" / batch
    pilot_dir = BASE / "中间产物" / batch / "pilot"
    candidates = {
        "questions": [final_dir / "ALL_questions_FIXED.json"],
        "learning_value": [BASE / "reports/validate" / f"learning_value_{batch}.json",
                           BASE / "reports/validate" / f"learning_value_{batch}_final.json"],
        "kc": [pilot_dir / "kc_registry.json", BASE / "中间产物" / batch / "kc_registry.json"],
        "baseline": [pilot_dir / "baseline_manifest.json",
                     BASE / "中间产物" / batch / "baseline_manifest.json"],
    }
    defaults = {
        "questions": DEFAULT_QUESTIONS,
        "learning_value": DEFAULT_LEARNING_VALUE,
        "kc": DEFAULT_KC,
        "baseline": DEFAULT_BASELINE,
    }
    for attr, paths in candidates.items():
        if str(getattr(args, attr)) != str(defaults[attr]):
            continue
        hit = next((p for p in paths if p.exists()), None)
        # 没有批次专属产物时也落到批次专属路径（缺失），避免误用 batch040 的报告。
        setattr(args, attr, str(hit or paths[0]))

    if str(args.review) == str(DEFAULT_REVIEW):
        subject = _batch_subject(batch)
        products = infer_batch_products(batch)
        if "review_material" in products and subject:
            review_dir = BASE / "复习资料"
            # 默认路径已指向本科目教师重点版时保留，避免被同名教学计划版抢占。
            if subject in str(DEFAULT_REVIEW):
                pass
            else:
                hits = sorted(review_dir.rglob(f"{subject}*主复习资料.md")) if review_dir.exists() else []
                args.review = str(hits[0]) if hits else str(review_dir / f"{subject}_主复习资料.md")
        elif "review_material" not in products:
            args.review = str(BASE / "复习资料" / "__no_review_product__.md")


def check_required_inputs(args, profile: dict) -> list[dict]:
    """R0 输入完备性：按 profile.required_checks 决定必需项，避免无关输入阻断。"""
    checks = []
    required_checks = set(profile.get("required_checks") or [])
    checks.append(check_item(
        "r0.spec", "PASS" if DEFAULT_SPEC.exists() else "FAIL",
        f"质量管控规范：{DEFAULT_SPEC}" + ("" if DEFAULT_SPEC.exists() else "（缺失）"),
        details={"path": str(DEFAULT_SPEC)},
    ))
    checks.append(check_item(
        "r0.policy", "PASS" if DEFAULT_POLICY.exists() else "FAIL",
        f"质量基准 policy：{DEFAULT_POLICY}" + ("" if DEFAULT_POLICY.exists() else "（缺失）"),
        details={"path": str(DEFAULT_POLICY)},
    ))

    optional = [
        ("baseline", Path(args.baseline), "基线 manifest", "baseline"),
        ("kc", Path(args.kc), "KC 注册表", "kc_registry"),
        ("review", Path(args.review), "复习资料 MD", "scorecard"),
        ("rubric", Path(args.rubric), "人工 rubric", "scorecard"),
        ("keypoints", Path(args.keypoints), "教师重点锚定清单", "keypoint_coverage"),
    ]
    products = infer_batch_products(args.batch)
    for cid, path, label, gate in optional:
        if gate not in required_checks:
            continue
        if gate in ("scorecard", "keypoint_coverage") and "review_material" not in products:
            checks.append(check_item(
                f"r0.{cid}", "SKIP", f"{label}：批次无复习资料产物，不适用", required=False,
                details={"path": str(path)},
            ))
            continue
        checks.append(check_item(
            f"r0.{cid}", "PASS" if path.exists() else "FAIL",
            f"{label}：{path}" + ("" if path.exists() else "（缺失）"),
            details={"path": str(path)},
        ))

    # 试点专属输入：只在 pilot profile 要求
    if "baseline" in required_checks and profile.get("description", "").startswith("试点"):
        for cid, path, label in (
            ("plan", DEFAULT_PLAN, "试点实施计划"),
            ("blueprint", Path(args.blueprint), "出题蓝图"),
        ):
            checks.append(check_item(
                f"r0.{cid}", "PASS" if path.exists() else "FAIL",
                f"{label}：{path}" + ("" if path.exists() else "（缺失）"),
                details={"path": str(path)},
            ))
    return checks


def check_baseline(args) -> dict:
    path = Path(args.baseline)
    if not path.exists():
        return check_item("r1.baseline", "FAIL", f"基线 manifest 缺失：{path}", details={"path": str(path)})
    r = run_cmd([sys.executable, "scripts/pilot_baseline.py", "verify", "--manifest", str(path)])
    return check_item(
        "r1.baseline",
        "PASS" if r["returncode"] == 0 else "FAIL",
        f"基线冻结校验 {'PASS' if r['returncode'] == 0 else 'FAIL'}",
        details=r,
    )


def check_schema(args) -> list[dict]:
    checks = []
    for cid, name in (
        ("r1.kc_schema", "schemas/kc.schema.json"),
        ("r1.score_schema", "schemas/review_score.schema.json"),
    ):
        p = BASE / name
        try:
            read_json(p)
            checks.append(check_item(cid, "PASS", f"{name} JSON 可解析", details={"path": name}))
        except Exception as exc:
            checks.append(check_item(cid, "FAIL", f"{name} 解析失败：{exc}", details={"path": name}))
    return checks


def check_kc_registry(args, profile: dict, mode: str) -> dict:
    kc_path = Path(args.kc)
    if not kc_path.exists():
        return check_item("r2.kc_registry", "FAIL", f"KC 注册表缺失：{kc_path}", details={"path": str(kc_path)})
    r = run_cmd([sys.executable, "scripts/kc_registry.py", "check", "--file", str(kc_path), "--strict"])
    registry = read_json(kc_path)
    map_path = kc_path.with_name("kc_question_map.jsonl")
    qmap = []
    if map_path.exists():
        qmap = [json.loads(x) for x in map_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    cards = registry.get("cards", [])
    provisional = registry.get("provisional", [])
    content_only = sum(1 for c in cards if c.get("status") == "content_only")
    mapped = sum(1 for r0 in qmap if r0.get("primary_kc"))
    kp_ids = {int(k) for c in cards for k in (c.get("keypoints") or [])}
    expected_count = int(registry.get("metadata", {}).get("keypoint_items", 0) or (max(kp_ids) if kp_ids else 0))
    expected_kp = set(range(1, expected_count + 1)) if expected_count else set()
    th = profile["thresholds"]
    issues = []
    status = "PASS"
    if r["returncode"] != 0:
        status = "FAIL"
        issues.append("kc_registry.py check 退出码非 0")
    if mapped != len(qmap) or (qmap and mapped / len(qmap) < th["kc_mapped_ratio"]):
        status = "FAIL"
        issues.append(f"题目主映射 {mapped}/{len(qmap)}")
    if expected_kp and len(kp_ids & expected_kp) < expected_count * th["keypoint_coverage"]:
        status = "FAIL"
        issues.append(f"重点覆盖 {len(kp_ids & expected_kp)}/{expected_count}")
    content_ratio = _ratio(content_only, len(cards))
    if content_ratio > th["content_only_ratio_block"]:
        status = "FAIL"
        issues.append(f"content_only {content_only}/{len(cards)}={content_ratio:.1%} 超过 block 阈值")
    elif content_ratio > th["content_only_ratio_warn"]:
        if status != "FAIL":
            status = "WARN"
        issues.append(f"content_only {content_only}/{len(cards)}={content_ratio:.1%} 超过 warn 阈值")
    provisional_ratio = _ratio(sum(1 for x in qmap if x.get("mapping_method") == "provisional"), len(qmap))
    if provisional_ratio > th["provisional_ratio_max"]:
        status = "FAIL"
        issues.append(f"provisional 题占比 {provisional_ratio:.1%} 超过阈值")
    if mode == "advisory" and status == "FAIL":
        status = "WARN"
        issues.append("advisory 模式：FAIL 降级为 WARN，不阻断")
    return check_item(
        "r2.kc_registry", status,
        "; ".join(issues) or f"映射 {mapped}/{len(qmap)}；重点 {len(kp_ids & expected_kp)}/{expected_count}",
        details={
            "content_only": content_only, "content_only_ratio": round(content_ratio, 4),
            "provisional_kcs": len(provisional), "provisional_ratio": round(provisional_ratio, 4),
            "mapped": mapped, "questions": len(qmap), "command": r,
        },
    )


def check_item_learning_value(args, profile: dict, mode: str) -> dict:
    path = Path(args.learning_value)
    checks = []
    if not path.exists():
        # 只在显式允许时尝试生成；默认不重跑，避免覆盖报告
        if args.questions and Path(args.questions).exists():
            out = BASE / "reports/validate" / f"learning_value_{args.batch}.json"
            r = run_cmd([sys.executable, "scripts/check_learning_value.py",
                         "--file", str(args.questions), "--out", str(out)])
            if r["returncode"] != 0:
                return check_item("r2.item_learning_value", "FAIL",
                                  "check_learning_value.py 执行失败", details=r)
            path = out
        else:
            return check_item("r2.item_learning_value", "SKIP", f"学习价值报告缺失：{path}", required=False)
    try:
        data = read_json(path)
    except Exception as exc:
        return check_item("r2.item_learning_value", "FAIL", f"报告解析失败：{exc}", details={"path": str(path)})
    s = data.get("summary", {})
    th = profile["thresholds"]
    fail_count = int(s.get("fail", 0))
    per_option = float(s.get("per_option_coverage", 0))
    mis = float(s.get("misconception_coverage", 0))
    source = float(s.get("source_quote_exact_rate", 0))
    quote = float(s.get("quote_verified_rate", 1.0))
    conflicts = int(s.get("misconception_id_conflicts", 0))
    anchor = float(s.get("anchor_verified_rate", 0))
    issues = []
    status = "PASS"
    if fail_count > 0:
        status = "FAIL"; issues.append(f"FAIL={fail_count}")
    if per_option < 1 or mis < 1:
        status = "FAIL"; issues.append(f"覆盖 per_option={per_option:.1%} misconception={mis:.1%}")
    if source < th["source_quote_exact_min"]:
        status = "FAIL"; issues.append(f"source exact={source:.1%}")
    if quote < float(th.get("quote_verified_min", 0.95)):
        status = "FAIL"; issues.append(f"quote verified={quote:.1%} < {th.get('quote_verified_min', 0.95):.0%}")
    if conflicts > int(th.get("misconception_conflict_max", 0)):
        status = "FAIL"; issues.append(f"misconception ID 冲突={conflicts} > {th.get('misconception_conflict_max', 0)}")
    if anchor < th["anchor_verified_block"]:
        status = "FAIL"; issues.append(f"anchor verified={anchor:.1%} < block")
    elif anchor < th["anchor_verified_warn"]:
        if status != "FAIL": status = "WARN"
        issues.append(f"anchor verified={anchor:.1%} < warn")
    if mode == "advisory" and status == "FAIL":
        status = "WARN"; issues.append("advisory 模式：FAIL 降级为 WARN")
    return check_item(
        "r2.item_learning_value", status,
        "; ".join(issues) or f"PASS；source={source:.1%} anchor={anchor:.1%}",
        details={"path": str(path), "summary": s},
    )


def check_scorecard(args, profile: dict, mode: str) -> dict:
    if not Path(args.review).exists():
        return check_item("r2.scorecard", "SKIP",
                          f"批次无复习资料产物，评分卡不适用：{args.review}", required=False)
    path = Path(args.scorecard)
    if not path.exists():
        r = run_cmd([sys.executable, "scripts/review_scorecard.py",
                     "--subject", args.subject, "--batch", args.batch,
                     "--review", args.review, "--kc", args.kc,
                     "--learning-value", args.learning_value, "--rubric", args.rubric,
                     "--out", str(path), "--md-out", str(path.with_suffix(".md"))])
        if r["returncode"] != 0:
            return check_item("r2.scorecard", "FAIL", "评分卡生成失败", details=r)
    try:
        card = read_json(path)
    except Exception as exc:
        return check_item("r2.scorecard", "FAIL", f"评分卡解析失败：{exc}", details={"path": str(path)})
    th = profile["thresholds"]
    overall = float(card.get("overall", -1))
    dims = card.get("dimensions") or []
    critical = [d for d in dims if int(d.get("id", 0)) in (2, 3, 8)]
    critical_low = [d for d in critical if float(d.get("score", 0)) < th["critical_dim_min"]]
    threshold = th["scorecard_overall_enforce"] if mode == "enforce" else th["scorecard_overall_advisory"]
    issues = []
    status = "PASS"
    if overall < threshold:
        status = "FAIL" if mode == "enforce" else "WARN"
        issues.append(f"overall={overall:.2f} < {threshold}")
    if critical_low:
        status = "FAIL"
        issues.append("关键维度低于 " + ", ".join(f"{d['id']}:{d['score']}" for d in critical_low))
    if card.get("blocking_issues"):
        status = "FAIL"
        issues.append(f"blocking_issues={len(card['blocking_issues'])}")
    warnings = card.get("warnings") or []
    if warnings and status == "PASS":
        status = "WARN"
    if mode == "advisory" and status == "FAIL":
        status = "WARN"
        issues.append("advisory 模式：FAIL 降级为 WARN")
    return check_item(
        "r2.scorecard", status,
        "; ".join(issues) or f"overall={overall:.2f}；warnings={len(warnings)}",
        details={"path": str(path), "overall": overall, "warnings": warnings,
                 "critical": [{"id": d["id"], "score": d["score"]} for d in critical]},
    )


def check_review_detail(args, profile: dict, mode: str) -> dict:
    """HC-26 复习资料详细度：九槽位/模块块/自测答案/课程安排八块。"""
    md = Path(args.review)
    if not md.exists():
        return check_item("r2.review_detail", "SKIP",
                          f"批次无复习资料产物，详细度检查不适用：{args.review}", required=False)
    out = BASE / "reports/validate" / f"review_detail_{args.batch}_{args.stage}.json"
    cmd = [sys.executable, "scripts/check_review_detail.py",
           "--md", str(md), "--mode", "auto", "--profile", args.profile,
           "--json-out", str(out), "--md-out", str(out.with_suffix(".md")), "--quiet"]
    if mode == "advisory":
        cmd.append("--advisory")
    r = run_cmd(cmd)
    if not out.exists():
        return check_item("r2.review_detail", "FAIL",
                          "详细度检查未产出报告", details=r)
    try:
        data = read_json(out)
    except Exception as exc:
        return check_item("r2.review_detail", "FAIL",
                          f"详细度报告解析失败：{exc}", details={"path": str(out)})
    s = data.get("summary", {})
    status = str(s.get("status") or "FAIL")
    if status == "SKIP":
        return check_item("r2.review_detail", "SKIP",
                          str((data.get("warnings") or ["未解析到考点卡"])[0]),
                          required=False, details={"path": str(out), "summary": s})
    issues = list(data.get("blocking") or [])
    if status == "FAIL" and mode == "advisory":
        status = "WARN"
        issues.append("advisory 模式：FAIL 降级为 WARN")
    reason = "; ".join(issues) or (
        f"详细度 {s.get('overall')}；核心槽位 {s.get('core_slot_ratio')}；"
        f"卡片达标 {s.get('card_pass_ratio')}"
    )
    return check_item(
        "r2.review_detail", status, reason,
        details={"path": str(out), "mode": data.get("mode"), "summary": s,
                 "command": r},
    )


def check_review_items(args, profile: dict, mode: str) -> dict:
    """D3 复习卡片/Anki/HTML 的轻量验收；未生成则 SKIP，不阻断其他批次。"""
    base = Path(args.kc).parent
    items_path = base / "review_items.jsonl"
    if not items_path.exists():
        return check_item("r2.review_items", "SKIP", "未生成 review_items.jsonl（D3 未在范围内）", required=False)
    items = [json.loads(x) for x in items_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    total = len(items)
    kp = sum(1 for x in items if x.get("type") in ("cloze", "keypoint_recall"))
    recall = sum(1 for x in items if x.get("type") == "recall")
    th = profile["thresholds"]
    min_total = int(th.get("review_items_min_total", 190))
    min_kp = int(th.get("review_keypoint_min", 125))
    issues = []
    status = "PASS"
    if total < min_total:
        status = "FAIL"; issues.append(f"卡片 {total} < {min_total}")
    if kp < min_kp:
        status = "FAIL"; issues.append(f"重点卡 {kp} < {min_kp}")
    for name, path in (
        ("answer_reconciliation.md", base / "answer_reconciliation.md"),
        ("anki CSV", base / "anki_ent_pilot.csv"),
        ("pilot_review.html", base / "pilot_review.html"),
    ):
        if not path.exists():
            if status == "PASS": status = "WARN"
            issues.append(f"{name} 缺失")
    if mode == "advisory" and status == "FAIL":
        status = "WARN"; issues.append("advisory 模式：FAIL 降级为 WARN")
    return check_item(
        "r2.review_items", status,
        "; ".join(issues) or f"卡片 {total}（keypoint {kp} / recall {recall}）",
        required=False,
        details={"total": total, "keypoint": kp, "recall": recall, "path": str(items_path)},
    )


def check_produce_rules(args) -> dict:
    r = run_cmd([sys.executable, "scripts/verify_produce_rules.py"])
    return check_item("r3.produce_rules", "PASS" if r["returncode"] == 0 else "FAIL",
                      "产物形态门禁 " + ("PASS" if r["returncode"] == 0 else "FAIL"), details=r)


def check_site_freshness(args) -> dict:
    r = run_cmd([sys.executable, "scripts/check_site_freshness.py", "--offline"])
    return check_item("r3.site_freshness", "PASS" if r["returncode"] == 0 else "FAIL",
                      "站点一致性 " + ("PASS" if r["returncode"] == 0 else "FAIL"), details=r)


def check_site_links(args) -> dict:
    r = run_cmd(["node", "scripts/check_site_links.mjs", "index.html"])
    if r["returncode"] == 127:
        return check_item("r3.site_links", "SKIP", "node 不可用，链接门禁跳过", required=False, details=r)
    return check_item("r3.site_links", "PASS" if r["returncode"] == 0 else "FAIL",
                      "站点链接 " + ("PASS" if r["returncode"] == 0 else "FAIL"), details=r)


def check_keypoint_coverage(args) -> dict:
    kp = Path(args.keypoints)
    md = Path(args.review)
    if not kp.exists() or not md.exists():
        return check_item("r3.keypoint_coverage", "SKIP",
                          f"教师重点或复习资料缺失，跳过：{kp} / {md}", required=False)
    r = run_cmd([sys.executable, "scripts/check_keypoint_coverage.py",
                 "--keypoints", str(kp), "--md", str(md)])
    return check_item("r3.keypoint_coverage", "PASS" if r["returncode"] == 0 else "FAIL",
                      "教师重点覆盖 " + ("PASS" if r["returncode"] == 0 else "FAIL"), details=r)


def check_inline_images(args) -> dict:
    md = Path(args.review)
    if not md.exists():
        return check_item("r3.inline_images", "SKIP", f"复习资料缺失，跳过：{md}", required=False)
    r = run_cmd([sys.executable, "scripts/check_inline_images.py", "--md", str(md)])
    return check_item("r3.inline_images", "PASS" if r["returncode"] == 0 else "FAIL",
                      "插图引用 " + ("PASS" if r["returncode"] == 0 else "FAIL"), details=r)


def check_tests(args) -> dict:
    r = run_cmd([sys.executable, "scripts/run_tests.py"], timeout=600)
    return check_item("r2.tests", "PASS" if r["returncode"] == 0 else "FAIL",
                      "全量回归 " + ("PASS" if r["returncode"] == 0 else "FAIL"), details=r)


def build_stage_checks(args, profile: dict, mode: str) -> list[dict]:
    """按 profile.required_checks 组装阶段检查，未声明的门禁不误触发。"""
    req = set(profile.get("required_checks") or [])
    checks: list[dict] = []
    stage = args.stage

    if "baseline" in req:
        checks.append(check_baseline(args))
    if stage == "r1":
        checks += check_schema(args)
        if "kc_registry" in req:
            checks.append(check_kc_registry(args, profile, mode))
        return checks

    if "kc_registry" in req:
        checks.append(check_kc_registry(args, profile, mode))
    if "item_learning_value" in req:
        checks.append(check_item_learning_value(args, profile, mode))
    if "scorecard" in req:
        checks.append(check_scorecard(args, profile, mode))
    if "review_detail" in req:
        checks.append(check_review_detail(args, profile, mode))
    checks.append(check_review_items(args, profile, mode))

    if stage == "r3":
        if "produce_rules" in req:
            checks.append(check_produce_rules(args))
        if "site_freshness" in req:
            checks.append(check_site_freshness(args))
        if "site_links" in req:
            checks.append(check_site_links(args))
        if "keypoint_coverage" in req:
            checks.append(check_keypoint_coverage(args))
        if "inline_images" in req:
            checks.append(check_inline_images(args))

    if args.with_tests:
        checks.append(check_tests(args))
    return checks


def check_post_release(args) -> list[dict]:
    checks = []
    if args.commit:
        r = run_cmd([sys.executable, "scripts/check_site_freshness.py",
                     "--expect-commit", args.commit])
        checks.append(check_item("r4.site_freshness", "PASS" if r["returncode"] == 0 else "FAIL",
                                 "线上最新性校验 " + ("PASS" if r["returncode"] == 0 else "FAIL"), details=r))
    else:
        checks.append(check_item("r4.site_freshness", "SKIP", "未提供 --commit，跳过线上最新性校验", required=False))
    analysis = list((BASE / "reports/validate").glob("pilot_analysis*.md"))
    checks.append(check_item("r4.learning_outcome", "PASS" if analysis else "SKIP",
                             "学习结果报告：" + (", ".join(p.name for p in analysis) if analysis else "未生成"),
                             required=bool(analysis)))
    return checks


def aggregate(checks: list[dict], mode: str) -> tuple[str, list[str], list[str]]:
    blocking = [c["reason"] for c in checks if c["status"] == "FAIL" and c.get("required", True)]
    warnings = [c["reason"] for c in checks if c["status"] in ("WARN", "SKIP")]
    if mode == "enforce" and blocking:
        return "BLOCKED", blocking, warnings
    if warnings or any(c["status"] == "FAIL" for c in checks):
        return "WARN", [], warnings
    return "PASS", [], warnings


def render_md(report: dict) -> str:
    lines = [
        "# 全流程质量门禁报告",
        "",
        f"> 批次：{report['batch']} ｜ 阶段：{report['stage']} ｜ Profile：{report['profile']} ｜ 模式：{report['mode']}",
        f"> 结论：**{report['status']}** ｜ 时间：{report['generated_at']}",
        "",
        "## 检查项",
        "",
        "| 检查 | 状态 | 必需 | 说明 |",
        "|---|---|---|---|",
    ]
    for c in report["checks"]:
        lines.append(f"| {c['id']} | {c['status']} | {'是' if c.get('required', True) else '否'} | {c['reason']} |")
    lines += ["", "## 阻断项", ""]
    lines += [f"- {x}" for x in report.get("blocking") or []] or ["无。"]
    lines += ["", "## 警告/跳过", ""]
    lines += [f"- {x}" for x in report.get("warnings") or []] or ["无。"]
    lines += [
        "",
        "## 说明",
        "",
        "- 本报告由 `scripts/quality_gate.py` 生成，只读源产物与既有报告；不修改源题库/源复习资料/workflow_state。",
        "- SKIP 不代表 PASS；enforce 模式下 required FAIL 会阻断发布。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    _configure_stdio()
    ap = argparse.ArgumentParser(description="R0–R4 全流程质量门禁（HC-25）")
    ap.add_argument("--stage", required=True, choices=["r0", "r1", "r2", "r3", "r4"])
    ap.add_argument("--batch", default="batch040")
    ap.add_argument("--subject", default="ent")
    ap.add_argument("--profile", default="")
    ap.add_argument("--mode", choices=["advisory", "enforce"], default="advisory")
    ap.add_argument("--review", default=str(DEFAULT_REVIEW))
    ap.add_argument("--kc", default=str(DEFAULT_KC))
    ap.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    ap.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    ap.add_argument("--learning-value", default=str(DEFAULT_LEARNING_VALUE))
    ap.add_argument("--scorecard", default=str(DEFAULT_SCORECARD))
    ap.add_argument("--rubric", default=str(DEFAULT_RUBRIC))
    ap.add_argument("--keypoints", default=str(DEFAULT_KEYPOINTS))
    ap.add_argument("--blueprint", default=str(DEFAULT_BLUEPRINT))
    ap.add_argument("--policy", default=str(DEFAULT_POLICY))
    ap.add_argument("--commit", default="")
    ap.add_argument("--with-tests", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    profile_name = args.profile or ("release_teacher_keypoint" if args.stage == "r3" else "pilot")
    args.profile = profile_name
    try:
        policy = _load_policy(Path(args.policy))
        profile = policy["profiles"][profile_name]
    except Exception as exc:
        print(f"[FAIL] 质量基准加载失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    derive_batch_defaults(args)

    checks: list[dict] = []
    if args.stage == "r0":
        checks += check_required_inputs(args, profile)
    elif args.stage == "r4":
        checks += check_post_release(args)
    else:
        checks += build_stage_checks(args, profile, args.mode)

    status, blocking, warnings = aggregate(checks, args.mode)
    now = datetime.now()
    out = Path(args.out) if args.out else (
        BASE / "reports/gate" / f"quality_gate_{args.batch}_{args.stage}_{now.strftime('%Y%m%dT%H%M%S')}.json"
    )
    report = {
        "schema_version": 1,
        "batch": args.batch,
        "stage": args.stage,
        "profile": profile_name,
        "mode": args.mode,
        "generated_at": now.isoformat(timespec="seconds"),
        "status": status,
        "checks": checks,
        "blocking": blocking,
        "warnings": warnings,
        "policy_version": policy.get("policy_version"),
    }
    write_json(out, report)
    md = out.with_suffix(".md")
    write_text(md, render_md(report))
    print(f"=== 质量门禁 {args.stage.upper()} / {profile_name} / {args.mode} ===")
    for c in checks:
        print(f"  [{c['status']}] {c['id']}: {c['reason']}")
    print(f"=== 结论: {status} ===")
    print(f"  JSON: {out}")
    print(f"  MD  : {md}")
    return 0 if status != "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
