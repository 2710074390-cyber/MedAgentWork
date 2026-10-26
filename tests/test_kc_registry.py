# -*- coding: utf-8 -*-
"""T2–T4 KC 注册表、映射、校验测试。

注意：项目自定义 runner `scripts/run_tests.py` 会直接调用无参测试函数，
因此这里使用 tempfile 而不是 pytest 的 tmp_path fixture。
"""
import json
import tempfile
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
import kc_registry as kc  # noqa: E402


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_build_registry_and_check():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        review = _write(tmp / "review.md", """# 测试科目

## 模块1：测试模块

#### 🔴 K-M01-001｜测试卡A（教师重点第1、2条｜P10、P11）
📌 重点原文（第1条）：甲。
📌 重点原文（第2条）：乙。

#### 🔴 K-M01-002｜测试卡B（教师重点第3条｜P12）
📌 重点原文（第3条）：丙。
""")
        keypoints = _write(tmp / "keypoints.md", """## 四、统一锚定清单

1. 【源①】甲
2. 【源①】乙
3. 【源①】丙

## 五、原始标号对照
""")
        questions = tmp / "questions.json"
        questions.write_text(json.dumps([
            {"id": "q1", "module": "M01", "topic": "测试卡A", "type": "A1",
             "keypoint_ref": ["第1条"], "source_page": "P10", "stem": "测试卡A的考点"},
            {"id": "q2", "module": "M01", "topic": "测试卡B", "type": "A1",
             "keypoint_ref": ["补充·源③"], "source_page": "P12", "stem": "测试卡B的考点"},
            {"id": "q3", "module": "M01", "topic": "无卡主题", "type": "A1",
             "keypoint_ref": ["补充·源③"], "source_page": "P99", "stem": "无卡主题的考点"},
        ], ensure_ascii=False), encoding="utf-8")
        rules = tmp / "rules.json"
        rules.write_text(json.dumps({"rules": [
            {"id": "TEST_B", "module": "M01", "pattern": "测试卡B",
             "kc": "ENT:K-M01-002", "reason": "test"}
        ]}, ensure_ascii=False), encoding="utf-8")

        registry, qmap, _ = kc.build_registry(
            "ent", "test", review, questions, keypoints, rules
        )

        assert len(registry["cards"]) == 2
        assert len(registry["provisional"]) == 1
        assert len(qmap) == 3
        by_id = {r["question_id"]: r for r in qmap}
        assert by_id["q1"]["primary_kc"] == "ENT:K-M01-001"
        assert by_id["q1"]["mapping_method"] == "keypoint_exact"
        assert by_id["q2"]["primary_kc"] == "ENT:K-M01-002"
        assert by_id["q2"]["mapping_method"] == "topic_rule"
        assert by_id["q3"]["mapping_method"] == "provisional"
        assert by_id["q3"]["primary_kc"].startswith("ENT:SUPP-M01-")

        result = kc.check_registry(
            registry, qmap,
            expect_cards=2, expect_keypoints=3, expect_questions=3,
            strict=False,
        )
        assert result["ok"] is True
        assert result["mapped"] == 3
        assert result["provisional"] == 1
        assert result["keypoints"] == 3


def test_check_registry_rejects_missing_primary():
    registry = {
        "schema_version": 1, "subject": "ENT", "batch": "test",
        "generated_at": "2026-10-22T00:00:00",
        "cards": [{
            "kc_id": "ENT:K-M01-001", "display_id": "K-M01-001", "subject": "ENT",
            "module": "M01", "title": "A", "keypoints": [1], "question_ids": [],
            "secondary_question_ids": [], "source_pages": [], "review_anchor": "L1",
            "content_chars": 10, "blueprint_weight": 8, "status": "content_only",
            "needs_content": False, "aliases": [], "notes": "", "version": 1,
        }],
        "provisional": [],
    }
    qmap = [{
        "question_id": "q1", "module": "M01", "topic": "A",
        "primary_kc": "", "secondary_kcs": [], "mapping_method": "provisional",
        "confidence": "low", "score": 0, "candidates": [],
        "review_status": "needs_review", "notes": "",
    }]
    result = kc.check_registry(
        registry, qmap, expect_cards=1, expect_keypoints=1, expect_questions=1
    )
    assert result["ok"] is False
    assert any("缺主 KC" in e for e in result["errors"])


def test_parse_review_cards_keypoints_and_pages():
    md = """## 模块3：鼻科学

#### 🔴 K-M03-001｜鼻腔三个门（教师重点第38、46、47条｜P152、P159）
📌 重点原文（第38条）：甲。
📌 重点原文（第46条）：乙。
"""
    cards = kc.parse_review_cards(md)
    assert len(cards) == 1
    c = cards[0]
    assert c["display_id"] == "K-M03-001"
    assert c["module"] == "M03"
    assert c["keypoints"] == [38, 46, 47]
    assert c["pages"] == [152, 159]
    assert c["title_clean"] == "鼻腔三个门"
