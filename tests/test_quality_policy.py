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
