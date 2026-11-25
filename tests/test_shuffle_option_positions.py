# -*- coding: utf-8 -*-
"""shuffle_option_positions.py 的行为测试（2026-11-25）。

核心断言只有三条：
  1. 只换位置——每题的选项文本集合、正确项对应的文本、反选题极性全不变；
  2. 位置不再与题号相关（X10 字母周期、X1 字母占比）；
  3. 顺序有含义的题（数值升序、判断题）原样不动。
"""
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
for p in (BASE, BASE / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import shuffle_option_positions as sp  # noqa: E402
from validate import rules_batch as rb  # noqa: E402


def _q(i, ans, type_="A1", texts=None):
    texts = texts or {k: f"{k}项陈述内容{i}" for k in "ABCDE"}
    opts = []
    for k in "ABCDE":
        opts.append({"label": k, "text": texts[k], "is_correct": k in ans})
    return {
        "id": f"T{i:03d}", "question_id": f"T{i:03d}", "type": type_,
        "module": "M01", "stem": f"题干{i}", "answer": ans, "options": opts,
        "polarity": "positive",
        "option_polarities": {k: (k in ans) for k in "ABCDE"},
        "learning_value": {
            "per_option": [{"label": k, "truth": k in ans} for k in "ABCDE"],
        },
        "difficulty_tier": "L2",
    }


def _degenerate(n=40):
    """复刻 batch049：单选答案 ABCDE 轮转、多选恒 ABCD。"""
    items = [_q(i, "ABCDE"[i % 5]) for i in range(n)]
    for j in range(10):
        items.append(_q(100 + j, "ABCD", type_="X"))
    return items


def _texts(q):
    return sorted(o["text"] for o in q["options"])


def test_cycle_is_broken_and_distribution_kept():
    items = _degenerate()
    before = rb.check_answer_position_periodicity(items, rb.thresholds())
    assert before["status"] == "VIOLATED"

    work, _stat = sp.shuffle_batch(items)
    after = rb.check_answer_position_periodicity(work, rb.thresholds())
    assert after["letter_cycle_fit"] < 0.90, after["letter_cycle_fit"]

    x1 = rb.check_answer_distribution(work, rb.thresholds())
    assert x1["status"] == "PASS", x1["violations"]


def test_content_is_untouched():
    items = _degenerate()
    work, _stat = sp.shuffle_batch(items)
    for a, b in zip(items, work):
        assert _texts(a) == _texts(b), "选项文本必须逐字不变"
        assert ({o["text"] for o in a["options"] if o["is_correct"]}
                == {o["text"] for o in b["options"] if o["is_correct"]}), "正确项对应文本必须不变"
        assert b["answer"] == "".join(sorted(o["label"] for o in b["options"] if o["is_correct"]))
        per = {p["label"]: p for p in b["learning_value"]["per_option"]}
        for o in b["options"]:
            assert bool(per[o["label"]]["truth"]) == bool(o["is_correct"])


def test_negative_polarity_truth_follows_answer():
    """反选题：truth 与被选中相反，重排后仍必须相反。"""
    q = _q(0, "B")
    q["polarity"] = "negative"
    for o in q["options"]:
        o["is_correct"] = o["label"] in "B"
    q["learning_value"]["per_option"] = [
        {"label": k, "truth": k not in "B"} for k in "ABCDE"
    ]
    items = [q] + [_q(i, "ABCDE"[i % 5]) for i in range(1, 30)]
    work, _stat = sp.shuffle_batch(items)
    w = work[0]
    per = {p["label"]: p for p in w["learning_value"]["per_option"]}
    for o in w["options"]:
        assert bool(per[o["label"]]["truth"]) == (not o["is_correct"])


def test_numeric_and_judge_untouched():
    numeric = _q(0, "C", texts={"A": "10mmHg", "B": "15mmHg", "C": "20mmHg",
                                "D": "25mmHg", "E": "30mmHg"})
    judge = {"id": "J1", "type": "判断", "stem": "s", "answer": "A", "module": "M01",
             "options": [{"label": "A", "text": "正确", "is_correct": True},
                         {"label": "B", "text": "错误", "is_correct": False}],
             "learning_value": {"per_option": []}}
    items = [numeric, judge] + [_q(i, "ABCDE"[i % 5]) for i in range(1, 30)]
    work, _stat = sp.shuffle_batch(items)
    assert [o["text"] for o in work[0]["options"]] == \
           ["10mmHg", "15mmHg", "20mmHg", "25mmHg", "30mmHg"], "数值型不得重排（须升序）"
    assert work[0]["answer"] == "C"
    assert work[1] == judge, "判断题不得改动"


def test_multi_prefix_cluster_reduced():
    """多选恒 ABCD 时，重排后前缀聚集与字母占比都要改善。"""
    items = _degenerate()
    before = rb.check_multi_answer_distribution(items, rb.thresholds())
    assert before["prefix_cluster_share"] == 1.0

    work, _stat = sp.shuffle_batch(items)
    after = rb.check_multi_answer_distribution(work, rb.thresholds())
    assert after["prefix_cluster_share"] < 0.60
    shares = after["letter_share"]
    assert all(0.12 <= v <= 0.32 for v in shares.values()), shares


def test_residual_notes_name_content_defects():
    items = _degenerate()
    work, _stat = sp.shuffle_batch(items)
    notes = " ".join(sp.residual_notes(work))
    assert "正确项个数" in notes, notes
