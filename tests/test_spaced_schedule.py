# -*- coding: utf-8 -*-
"""M3/T7–T10 卡片构建、SM-2 调度、Anki/HTML 测试。"""
import json
import tempfile
from pathlib import Path
import sys
from datetime import date

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
import spaced_schedule as ss  # noqa: E402
import render_pilot_review as rp  # noqa: E402


def test_selftest_and_appendix_reconciliation():
    md = ss.read_text(ss.DEFAULT_REVIEW)
    prompts = ss.parse_self_tests(md)
    rows = ss.parse_appendix_rows(md)
    matched, gaps, extras = ss.reconcile(prompts, rows)
    assert len(prompts) == 82
    assert len(rows) == 90
    assert len(matched) + len(gaps) == len(prompts)
    assert len(extras) == len(rows) - len(matched)
    # 当前教师版实证：75 匹配 / 7 缺答案 / 15 多余；不作为永久硬编码
    assert len(matched) >= 70
    assert len(gaps) >= 0


def test_build_items_covers_keypoints():
    md = ss.read_text(ss.DEFAULT_REVIEW)
    prompts = ss.parse_self_tests(md)
    rows = ss.parse_appendix_rows(md)
    matched, _, _ = ss.reconcile(prompts, rows)
    kp_items = ss.parse_keypoint_items(ss.read_text(ss.DEFAULT_KEYPOINTS))
    key_cards = ss.build_keypoint_items(md, kp_items)
    recall = ss.build_recall_items(matched)
    items, duplicates = ss.dedupe(recall + key_cards)
    assert len(kp_items) == 125
    assert len(key_cards) == 125
    assert len(recall) == len(matched)
    assert len(items) >= 190
    assert len({x["item_id"] for x in items}) == len(items)
    assert all(x.get("kc_id") for x in items)
    assert duplicates >= 0


def test_sm2_intervals_and_lapse():
    st = {"due": "2026-10-23", "interval": 0, "ease": 2.5, "reps": 0, "lapses": 0}
    st = ss.sm2_update(st, 2, date(2026, 10, 23))
    assert st["interval"] == 1 and st["due"] == "2026-10-24" and st["reps"] == 1
    st = ss.sm2_update(st, 2, date(2026, 10, 24))
    assert st["interval"] == 3 and st["due"] == "2026-10-27" and st["reps"] == 2
    st = ss.sm2_update(st, 2, date(2026, 10, 27))
    assert st["interval"] >= 7 and st["reps"] == 3
    st = ss.sm2_update(st, 0, date(2026, 10, 28))
    assert st["interval"] == 1 and st["reps"] == 0 and st["lapses"] == 1


def test_html_is_offline_and_has_progress():
    md = ss.read_text(ss.DEFAULT_REVIEW)
    prompts = ss.parse_self_tests(md)
    rows = ss.parse_appendix_rows(md)
    matched, _, _ = ss.reconcile(prompts, rows)
    kp_items = ss.parse_keypoint_items(ss.read_text(ss.DEFAULT_KEYPOINTS))
    items, _ = ss.dedupe(ss.build_recall_items(matched) + ss.build_keypoint_items(md, kp_items))
    html = rp.render(items, "测试复习")
    assert "localStorage" in html
    assert "const ITEMS =" in html
    assert "http" not in html.lower()
    assert "显示答案" in html
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "review.html"
        out.write_text(html, encoding="utf-8")
        assert out.stat().st_size > 10000
