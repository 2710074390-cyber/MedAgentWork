#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SA-6 / SA-7 测试：批次上下文构建器 + 指针取数 + qbank 子集抽取（零依赖）。"""
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE / "scripts"))

import build_batch_context as bbc  # noqa: E402
import ctx_fetch as cf  # noqa: E402
import qbank  # noqa: E402


def test_parse_keypoint_items_offsets_exact():
    text = "# T\n\n## 四、统一锚定清单\n\n1. 第一条内容足够长\n2. 第二条内容也够长\n3. 第三条短\n"
    items = bbc.parse_keypoint_items(text)
    assert [i["no"] for i in items] == [1, 2, 3], items
    for it in items:
        assert text[it["offset"]: it["offset"] + it["chars"]] == it["text"]


def test_parse_keypoint_items_stops_at_gap():
    text = '## 统一锚定清单\n\n1. 第一条内容\n3. 第三条跳号\n'
    items = bbc.parse_keypoint_items(text)
    assert [i["no"] for i in items] == [1], items

def test_compose_ctx_budget_and_degrade():
    items = [{"no": i + 1, "text": "内容" * 30, "line": i + 2, "offset": 0, "chars": 63}
             for i in range(80)]
    data = {"subject": "测试科目", "product_types": ["question_bank"], "status": "PILOT"}
    text, budget, warns, limit = bbc.compose_ctx("batch099", data, items, "输入素材/x.md", BASE, max_chars=4000)
    assert len(text) <= 4000, len(text)
    assert warns and limit < 80
    text2, _, _, limit2 = bbc.compose_ctx("batch099", data, items, "输入素材/x.md", BASE, max_chars=8000)
    assert len(text2) <= 8000 and limit2 == 80


def test_subject_core_strips_parens():
    assert bbc.subject_core("急诊与灾难医学（试点留档）") == "急诊与灾难医学"
    assert bbc.subject_core("耳鼻咽喉头颈外科学") == "耳鼻咽喉头颈外科学"


def test_section_pointer_isolated():
    d = Path(tempfile.mkdtemp(prefix="ctx_sec_"))
    (d / "SOUL.md").write_text(
        "# A\n\n## HC-99 标题\n\n内容A\n\n### 子标题\n\n子内容\n\n## HC-100 后一节\n\n后一节内容\n",
        encoding="utf-8")
    res = cf.resolve_section(d, "SOUL", "HC-99", 2000)
    assert "内容A" in res["text"] and "子内容" in res["text"]
    assert "HC-100" not in res["text"] and "后一节内容" not in res["text"]


def test_section_pointer_truncates():
    d = Path(tempfile.mkdtemp(prefix="ctx_sec2_"))
    (d / "SOUL.md").write_text("## 长节\n\n" + "字" * 500 + "\n", encoding="utf-8")
    res = cf.resolve_section(d, "SOUL", "长节", 50)
    assert res["truncated"] is True and res["chars"] <= 120


def test_kp_pointer_exact_roundtrip():
    d = Path(tempfile.mkdtemp(prefix="ctx_kp_"))
    src = d / "input" / "kp.md"
    src.parent.mkdir(parents=True)
    kp_text = "## 四、统一锚定清单\n\n1. 第一条原文足够长\n2. 第二条原文也够长\n"
    src.write_text(kp_text, encoding="utf-8")
    items = bbc.parse_keypoint_items(kp_text)
    assert len(items) == 2
    idx = d / "中间产物" / "batch099"
    idx.mkdir(parents=True)
    with (idx / "_kpidx.jsonl").open("w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps({"id": f"KP-batch099-{it['no']:03d}", "batch": "batch099",
                                 "src": "input/kp.md", "line": it["line"], "offset": it["offset"],
                                 "chars": it["chars"], "no": it["no"], "text": it["text"]},
                                ensure_ascii=False) + "\n")
    res = cf.resolve_kp(d, "KP-batch099-001", 300)
    assert res["text"] == items[0]["text"]
    assert res["truncated"] is False


def test_art_pointer_archive_fallback():
    d = Path(tempfile.mkdtemp(prefix="ctx_art_"))
    p = d / "archive" / "最终产物" / "batch099" / "ALL_questions_FIXED.json"
    p.parent.mkdir(parents=True)
    p.write_text('[\n {"id": "x"}\n]', encoding="utf-8")
    res = cf.resolve_art(d, "ART:batch099/a4#L1-L1", 100)
    assert res["text"].startswith("[")
    assert "archive" in res["source"]


def test_art_pointer_unknown_role():
    d = Path(tempfile.mkdtemp(prefix="ctx_art2_"))
    try:
        cf.resolve_art(d, "ART:batch099/nope", 100)
        assert False, "应抛 KeyError"
    except KeyError:
        pass


def test_subselect_by_ids_with_case_group():
    items = [{"id": "batch099-Q001", "case_group": "CG1"},
             {"id": "batch099-Q002", "case_group": "CG1"},
             {"id": "batch099-Q003"}]
    picked = qbank.subselect(items, ids=["batch099-Q002"], with_case_group=True)
    assert [x["id"] for x in picked] == ["batch099-Q001", "batch099-Q002"]


def test_subselect_intersects_report_ids_and_ignores_batch_ids():
    items = [{"id": "batch099-Q003"}]
    d = Path(tempfile.mkdtemp(prefix="ctx_sel_"))
    rep = d / "r.json"
    rep.write_text(json.dumps({
        "issues": [{"question_id": "batch099-Q003"}],
        "review_queue": [{"id": "batch099-RQ-001"}],
        "modification_instructions": [{"id": "MOD-001", "question_id": "batch099-Q003"}],
    }), encoding="utf-8")
    picked = qbank.subselect(items, from_report=str(rep))
    assert [x["id"] for x in picked] == ["batch099-Q003"]


def test_subselect_unknown_ids_returns_empty():
    items = [{"id": "batch099-Q001"}]
    assert qbank.subselect(items, ids=["batch099-Q999"]) == []


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
