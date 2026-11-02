# -*- coding: utf-8 -*-
"""HC-25 质量基准 policy 测试。"""
import json
import tempfile
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
import quality_policy as qp  # noqa: E402


def test_policy_loads_and_profiles_exist():
    data = qp.load_policy()
    assert data["schema_version"] == 1
    assert data.get("policy_version")
    for name in ("pilot", "release_teacher_keypoint", "release_teaching_plan"):
        profile = qp.get_profile(name, data)
        assert profile["required_checks"]
        assert "scorecard_overall_enforce" in profile["thresholds"]


def test_policy_threshold_sanity():
    data = qp.load_policy()
    pilot = qp.get_profile("pilot", data)["thresholds"]
    release = qp.get_profile("release_teacher_keypoint", data)["thresholds"]
    assert pilot["content_only_ratio_warn"] < pilot["content_only_ratio_block"]
    assert release["content_only_ratio_block"] <= pilot["content_only_ratio_block"]
    assert pilot["anchor_verified_block"] < pilot["anchor_verified_warn"]
    assert release["anchor_verified_block"] > pilot["anchor_verified_block"]


def test_bad_policy_rejected():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "bad.json"
        p.write_text(json.dumps({"schema_version": 1, "profiles": {}}), encoding="utf-8")
        try:
            qp.load_policy(p)
        except ValueError as exc:
            assert "profiles" in str(exc)
        else:
            raise AssertionError("empty profiles should be rejected")


# ── P6-S4 预置：策略动作解析（AC-P6-05，0 隐式放行）────────────

def test_severity_actions_exist_and_legal():
    data = qp.load_policy()
    table = data.get("severity_actions")
    assert isinstance(table, dict) and table, "缺少 severity_actions"
    for sev, action in table.items():
        assert str(action).upper() in qp.ACTIONS, f"{sev} → {action} 非法"


def test_fail_maps_to_repair_and_warn_to_warn():
    assert qp.resolve_action("FAIL")["action"] == "REPAIR"
    assert qp.resolve_action("WARN")["action"] == "WARN"
    assert qp.resolve_action("INFO")["action"] == "PASS"


def test_unknown_severity_halts_not_passes():
    """未知/缺失 severity 必须 HALT —— 这是「0 隐式放行」的核心断言。"""
    for sev in ("", None, "UNKNOWN", "fatal", "info "):
        r = qp.resolve_action(sev)
        if str(sev or "").strip().upper() in ("INFO",):
            continue
        assert r["action"] == "HALT", r
        assert r["source"] == "fallback", r


def test_illegal_configured_action_falls_back_to_halt():
    policy = {"severity_actions": {"FAIL": "IGNORE_IT"}, "action_fallback": "HALT"}
    r = qp.resolve_action("FAIL", policy)
    assert r["action"] == "HALT" and r["source"] == "fallback"


def test_audit_actions_covers_fallback_cases():
    rows = qp.audit_actions()
    assert len(rows) >= 5
    assert any(r["source"] == "fallback" for r in rows)
    assert all(r["action"] in qp.ACTIONS for r in rows)
