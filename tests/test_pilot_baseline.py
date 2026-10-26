# -*- coding: utf-8 -*-
"""T1 基线冻结解析器测试。"""
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
import pilot_baseline as pb  # noqa: E402


def test_parse_review_stats_small_fixture():
    md = """# 测试

## 模块1：测试模块

#### 🔴 K-M01-001｜测试卡A（教师重点第1、2条｜P10、P11）
📌 重点原文（第1条）：甲。
📌 重点原文（第2条）：乙。

#### 🔴 K-M01-002｜测试卡B（教师重点第3条｜P12）
📌 重点原文（第3条）：丙。

## 附录五：主动回忆答案

| 题 | 答案 | 卡片 |
|---|---|---|
| 1 | 甲 | K-M01-001 |
| 2 | 乙 | K-M01-002 |
"""
    st = pb.parse_review_stats(md)
    assert st["modules"] == 1
    assert st["cards"] == 2
    assert st["keypoints"] == 3
    assert st["appendix_answer_rows"] == 2
    assert st["images"] == 0
    assert st["ascii_blocks"] == 0


def test_parse_question_stats():
    data = [
        {"id": "q1", "module": "M01", "type": "A1", "keypoint_ref": ["第1条"]},
        {"id": "q2", "module": "M01", "type": "X", "keypoint_ref": ["补充·源③"]},
    ]
    st = pb.parse_question_stats(data)
    assert st["total"] == 2
    assert st["keypoint_ref_present"] == 2
    assert st["supplemental_questions"] == 1
    assert st["modules"] == {"M01": 2}
    assert st["types"] == {"A1": 1, "X": 1}


def test_parse_keypoint_stats():
    text = """## 四、统一锚定清单

1. 【源①】甲
2. 【源①】乙
3. 【源③】丙

## 五、原始标号对照
"""
    st = pb.parse_keypoint_stats(text)
    assert st["items"] == 3
    assert st["first_id"] == 1
    assert st["last_id"] == 3
    assert st["continuous"] is True
    assert st["sources"] == {"源①": 2, "源③": 1}


def test_parse_blueprint_stats_bold_total():
    text = """| 模块 | 范围 | A1 | 合计 |
|---|---|---|---|
| M01 | 总论 | 6 | **12** |
| M02 | 耳科 | 11 | **42** |
| **合计** | | **17** | **54** |
"""
    st = pb.parse_blueprint_stats(text)
    assert st["modules"] == {"M01": 12, "M02": 42}
    assert st["total"] == 54


def test_parse_learning_value_stats():
    data = [
        {"id": "q1", "kc_id": "ENT:K-M01-001", "learning_value": {
            "review_status": "pilot_unreviewed", "source_quote_status": "exact",
            "anchor_status": "verified"}},
        {"id": "q2", "learning_value": {
            "review_status": "pilot_reviewed", "source_quote_status": "missing",
            "anchor_status": "partial"}},
    ]
    st = pb.parse_learning_value_stats(data)
    assert st["total"] == 2
    assert st["with_kc_slug"] == 1
    assert st["source_quote_status"] == {"exact": 1, "missing": 1}
    assert st["anchor_status"] == {"partial": 1, "verified": 1}
