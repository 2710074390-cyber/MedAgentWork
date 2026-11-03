# -*- coding: utf-8 -*-
"""schema 2.2 生成契约回归：真实样例题（20 题）必须能过结构 / 概念 / 学习价值最小检查。

背景：v2.2 契约自 2026-11-02 起草后一直没有真实批次，AC-P2-02「新格式覆盖率 100%」
长期挂着。本夹具是当时生成的 v2.2 样例题（急诊 20 题），把它固化成回归样本，
用来钉住「新契约能生产合格题」这条最小证据；等 batch047 真实批次落地后，
本样本仍可作为反例/正例基线。

约束：纯标准库，无 pytest fixture，run_tests.py 与 pytest 都能跑。
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

FIXTURE = BASE / "tests" / "fixtures" / "schema_v22_sample_20.json"


def _items():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_is_v22_batch():
    items = _items()
    assert len(items) == 20, len(items)
    assert {str(q.get("schema_version")) for q in items} == {"2.2"}


def test_struct_coverage_passes():
    from scripts.validate import rules_batch as rb

    rep = rb.check_structural_coverage(_items())
    assert rep["status"] == "PASS", rep
    assert rep["mechanism_coverage"] == 1.0, rep


def test_every_item_has_one_primary_concept_matching_keypoint():
    for q in _items():
        concepts = q.get("concepts") or []
        prim = [c for c in concepts if c.get("role") == "primary"]
        assert len(prim) == 1, q.get("id")
        refs = q.get("keypoint_ref")
        ref = refs[0] if isinstance(refs, list) and refs else refs
        assert prim[0].get("keypoint") == ref, q.get("id")
        assert len(str(prim[0].get("evidence") or "")) >= 8, q.get("id")
        if q.get("type") in ("A2", "A3", "A4", "X"):
            assert len(concepts) >= 2, q.get("id")


def test_learning_value_minimum_fields():
    from scripts.validate import rules_batch as rb

    for q in _items():
        lv = q.get("learning_value") or {}
        assert len(str(lv.get("correct_rationale") or "")) >= 60, q.get("id")
        assert len(str(lv.get("key_takeaway") or "")) >= 30, q.get("id")
        per = lv.get("per_option") or []
        options = q.get("options") or []
        assert len(per) >= len(options), q.get("id")
        answer = str(q.get("answer") or "")
        for row in per:
            if row.get("label") == answer:
                assert row.get("truth") is True, (q.get("id"), row)
                assert row.get("distractor_mechanism") is None, (q.get("id"), row)
            else:
                assert row.get("truth") is False, (q.get("id"), row)
                assert row.get("distractor_mechanism") in rb.MECHANISMS, (q.get("id"), row)
