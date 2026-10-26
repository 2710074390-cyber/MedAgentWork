# -*- coding: utf-8 -*-
"""T5–T6 12 维学习价值评分卡测试。"""
import json
import tempfile
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
import review_scorecard as rs  # noqa: E402


def test_actual_scorecard_baseline():
    card = rs.build_scorecard(
        "ent", "batch040",
        rs.DEFAULT_REVIEW, rs.DEFAULT_RUBRIC, rs.DEFAULT_KC, rs.DEFAULT_LEARNING_VALUE,
    )
    assert abs(card["overall"] - 3.63) <= 0.01
    assert card["gate"] == "ADVISORY_PASS"
    assert card["gate_mode"] == "advisory"
    assert len(card["dimensions"]) == 12
    assert abs(sum(d["weight"] for d in card["dimensions"]) - 100) < 0.01
    assert card["metrics"]["kc_mapping_rate"]["value"] == 1.0
    assert card["metrics"]["keypoint_coverage_rate"]["value"] == 1.0
    assert card["metrics"]["content_only_ratio"]["value"] == round(19 / 85, 4)
    assert card["blocking_issues"] == []


def test_bad_rubric_rejected():
    data = json.loads(rs.DEFAULT_RUBRIC.read_text(encoding="utf-8"))
    data["dimensions"][0]["weight"] = 1
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "bad_rubric.json"
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        try:
            rs.load_rubric(p)
        except ValueError as exc:
            assert "权重" in str(exc) or "100" in str(exc)
        else:
            raise AssertionError("bad rubric should be rejected")
