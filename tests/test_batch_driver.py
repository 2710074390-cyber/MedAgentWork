#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_driver 零依赖测试（scripts/run_tests.py 可直接发现 test_* 函数）。

覆盖：判定器自测、阶段图、退出码映射、payload 形状、schema 契约、
      「driver 不重复实现判定」的代码级约束（AC-SA4-08）。
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE / "scripts"))

import batch_driver as bd  # noqa: E402


def test_selftest_passes():
    assert bd.main(["selftest"]) == 0


def test_normalizers_match_fixtures():
    fx = BASE / "tests" / "fixtures" / "gates"
    for name, kind, _n, expect in bd.SELFTEST_CASES:
        got = bd._selftest_one(fx, name, kind)
        assert got == expect, f"{name}: got {got}, expect {expect}"


def test_exit_map_semantics():
    assert bd._mapped("check_source_concepts", 2) == "SKIP"
    assert bd._mapped("check_keypoint_coverage", 2) == "SKIP"
    assert bd._mapped("gate_check", 2) == "ERROR"
    assert bd._mapped("check_patch_integrity", 1) == "FAIL"
    assert bd._mapped("gate_check", None) == "ERROR"


def test_plan_question_bank_order():
    data = {"product_types": ["question_bank"], "item_schema_version": "2.2", "status": "PILOT"}
    plan, types = bd.plan_boundaries("batch099", data)
    assert types == {"question_bank"}
    for stage in ("r0", "r1", "a2", "a3", "a4", "lv", "r2", "r3", "final", "r4"):
        assert stage in plan, f"missing {stage}: {plan}"
    assert plan.index("a4") < plan.index("lv") < plan.index("final")
    assert plan.index("r3") < plan.index("final") < plan.index("r4")


def test_plan_review_material_has_a5_without_a2():
    data = {"product_types": ["review_material"], "status": "PILOT"}
    plan, types = bd.plan_boundaries("batch090", data)
    assert types == {"review_material"}
    assert "a5" in plan and "a2" not in plan
    assert plan.index("a5") < plan.index("final")


def test_plan_legacy_batch_without_quality_stages():
    data = {"product_types": ["question_bank"], "status": "COMPLETED"}
    plan, _ = bd.plan_boundaries("batch040", data)
    assert "r0" not in plan and "r4" not in plan
    assert plan[-1] == "final"


def test_learning_value_needs_schema_2x():
    assert bd.needs_learning_value({"item_schema_version": "2.0"})
    assert bd.needs_learning_value({"item_schema_version": "2.2"})
    assert not bd.needs_learning_value({})
    assert not bd.needs_learning_value({"item_schema_version": "1.0"})


def test_aggregate_and_payload_shape():
    res = [
        bd._result("GATE-A2", "PASS"),
        bd._result("GATE-A3", "FAIL", code="GATE-A3", owner="MedQC"),
    ]
    verdict, code = bd.aggregate(res)
    assert (verdict, code) == ("BLOCKED", 1)
    payload = bd.build_payload("batch099", "a3", ["a2", "a3"], {"question_bank"}, res, verdict, code)
    assert payload["verdict"] == "BLOCKED"
    assert payload["next_stage"] == "a3"
    assert payload["halt"]["active"] is True
    assert payload["failed"][0]["owner"] == "MedQC"
    assert [p["gate"] for p in payload["passed"]] == ["GATE-A2"]


def test_skip_only_exit_code_3():
    res = [bd._result("GATE-A5-KP", "SKIP", code="NO_KEYPOINTS")]
    verdict, code = bd.aggregate(res)
    assert verdict == "SKIP" and code == 3


def test_schema_file_contract():
    schema = json.loads((BASE / "schemas" / "batch_driver.schema.json").read_text(encoding="utf-8"))
    for key in ("batch", "stage", "verdict", "halt", "passed", "failed", "skipped", "unparsed"):
        assert key in schema["required"], key
    assert schema["properties"]["verdict"]["enum"] == ["PASS", "BLOCKED", "SKIP", "ERROR"]


def test_driver_does_not_reimplement_judgement():
    """AC-SA4-08：driver 不得自带配额/Bloom 口径常量（判定唯一来源是 gate_check）。"""
    src = (BASE / "scripts" / "batch_driver.py").read_text(encoding="utf-8")
    for token in ("QUOTA_MIN", "QUOTA_MAX", "BLOOM_SHORTFALL_PP", "P9_MODE_MIN_BATCH"):
        assert token not in src, token


def test_stage_sequence_lv_for_schema_2x():
    """SA-B-F1 回归：schema 2.1/2.2 必须进入 LV 阶段（原实现只认 2.0）。"""
    import gate_check as gc

    for ver in ("2.0", "2.1", "2.2"):
        seq = gc.stage_sequence("batch099", {"product_types": ["question_bank"], "item_schema_version": ver})
        assert "learning_value" in seq, f"schema {ver} 缺少 LV: {seq}"
    seq = gc.stage_sequence("batch099", {"product_types": ["question_bank"], "item_schema_version": "1.0"})
    assert "learning_value" not in seq
    seq_old = gc.stage_sequence("batch040", {"product_types": ["question_bank"]})
    assert "learning_value" not in seq_old


def test_cli_help_exits_zero():
    try:
        bd.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"  FAIL {name}: {exc}")
    raise SystemExit(1 if failures else 0)
