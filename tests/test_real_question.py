# -*- coding: utf-8 -*-
"""真题检索子系统测试：答案恢复 / 考点解析 / 选题 / 门禁。"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))

from real_question.answer_recovery import recover_answer
from real_question.check import run_check
from real_question.planner import build_plan
from real_question.retrieval import parse_keypoints
from real_question.schema import RealQuestion, dedupe_items, prepare_item, write_jsonl


# ── 答案恢复 ──

def test_recover_phrase_high():
    r = recover_answer("...故答 D。", raw_answer="ABCD")
    assert r.answer == "D"
    assert r.confidence == "high"
    assert r.method == "phrase"


def test_recover_inline_positive_medium():
    r = recover_answer("A 错，B 不符合，D 对。", raw_answer="ABCD")
    assert r.answer == "D"
    assert r.confidence == "medium"
    assert r.method == "positive_inline"


def test_recover_elimination_medium():
    r = recover_answer("故不答 A、B、C。", raw_answer="ABCD")
    assert r.answer == "D"
    assert r.confidence == "medium"
    assert r.method == "elimination"


def test_recover_none_when_ambiguous():
    r = recover_answer("本题考查临床表现，请结合教材。", raw_answer="ABCD")
    assert r.answer is None
    assert r.confidence == "low"


def test_recover_multi_letter_exclusion():
    r = recover_answer("A、B、C、D均不是。", raw_answer="ABCDE")
    assert r.answer == "E"
    assert r.method == "elimination"


def test_pdf_answer_regexes():
    from kaoyan_pdf_answers import extract_2024, extract_std

    std = extract_std("1.【标准答案】C\n2.【【标准答案】D\n3.【标准答案】（\n4. 标准答案：AB")
    assert std[1] == "C"
    assert std[2] == "D"
    assert std[4] == "AB"

    text = "1.题干\nA.甲\nB.乙\nC.丙\nD.丁\n正确答案：C\n2.题干\n正确答案：ABD\n"
    ans = extract_2024(text)
    assert ans[1] == "C"
    assert ans[2] == "ABD"


def test_green_scan_synthetic():
    """合成页：题号 + 5 个字母，第 3 个为绿色 → 应识别为 C。"""
    import numpy as np
    from kaoyan_green_scan import detect_page

    h, w = 40, 260
    img = np.full((h, w, 3), 255, dtype=np.uint8)
    # "1." 两个字形
    img[8:24, 10:16] = 0
    img[14:17, 18:21] = 0
    # A B C D E 五个字形，C 绿色
    xs = [30, 62, 94, 126, 158]
    for i, x in enumerate(xs):
        color = (30, 120, 40) if i == 2 else (0, 0, 0)
        img[8:28, x:x + 18] = color
    lines = [{"bbox": [0, 0, 500, 18], "text": "1. ABCDE 合成测试"}]
    out = detect_page(img, lines, scale=1.0)
    assert len(out) == 1
    assert out[0].letters == "C", out[0].scores


def test_manual_answer_key_shape():
    """人工答案键必须是 2023 年 165 题、每题 1–5 个合法字母。"""
    import json
    p = BASE / "question_bank" / "kaoyan_manual_answers.json"
    if not p.exists():
        return
    data = json.loads(p.read_text(encoding="utf-8"))
    key = data["2023"]
    assert len(key) == 165
    for qno, ans in key.items():
        assert 1 <= int(qno) <= 165
        assert ans and set(ans) <= set("ABCDE")
        assert ans == "".join(sorted(set(ans)))


# ── 考点解析 ──

def test_parse_keypoints_section_four(tmp_path):
    p = tmp_path / "kp.md"
    p.write_text(
        "# 标题\n\n## 四、统一锚定清单\n\n"
        "1. 【源①】心力衰竭的诊断标准〔源①原标号1〕\n"
        "2. 【源①】冠心病的治疗原则〔源①原标号2〕\n",
        encoding="utf-8",
    )
    kps = parse_keypoints(p)
    assert [k.ref for k in kps] == ["第1条", "第2条"]
    assert "心力衰竭" in kps[0].text


# ── 去重 ──

def _item(item_id, source, stem, options=None, answer="A", year=2024, confidence="high"):
    return prepare_item(RealQuestion(
        item_id=item_id,
        source=source,
        source_id=item_id,
        exam="306西综" if source == "kaoyan" else "执业医师",
        year=year,
        question_no=1,
        subject="内科学",
        subject_aliases=["内科学"],
        stem=stem,
        options=options or ["甲", "乙", "丙", "丁"],
        answer=answer,
        explanation="",
        question_type="A1",
        answer_confidence=confidence,
        license="public_noncommercial",
        source_file="CMExam-test" if source == "zhiyi" else "GS",
    ))


def test_dedupe_exact_and_near():
    items = [
        _item("K1", "kaoyan", "心力衰竭的诊断标准是什么"),
        _item("K2", "kaoyan", "心力衰竭的诊断标准是什么"),
        _item("Z1", "zhiyi", "冠心病治疗原则包括哪些"),
    ]
    kept, removed = dedupe_items(items)
    assert len(kept) == 2
    assert removed == 1


# ── 选题 ──

def _write_index(tmp_path):
    kaoyan = [
        _item(f"K{i}", "kaoyan", stem)
        for i, stem in enumerate([
            "心力衰竭的诊断标准是脑钠肽升高",
            "心力衰竭诊断标准包括射血分数",
            "冠心病的治疗原则包括抗血小板",
            "冠心病治疗原则需要他汀",
            "社区获得性肺炎的抗感染治疗首选",
            "肺炎抗感染治疗疗程",
            "糖尿病的诊断标准是空腹血糖",
            "糖尿病诊断标准包括糖化血红蛋白",
        ], start=1)
    ]
    zhiyi = [
        _item(f"Z{i}", "zhiyi", stem)
        for i, stem in enumerate([
            "心力衰竭诊断标准中脑钠肽的意义",
            "心力衰竭诊断标准与射血分数",
            "冠心病治疗原则的抗血小板方案",
            "冠心病治疗原则的他汀选择",
            "社区获得性肺炎抗感染治疗药物",
            "肺炎抗感染治疗的疗程",
            "糖尿病诊断标准的空腹血糖阈值",
            "糖尿病诊断标准的糖化血红蛋白",
        ], start=1)
    ]
    write_jsonl(tmp_path / "kaoyan_items.jsonl", kaoyan)
    write_jsonl(tmp_path / "zhiyi_items.jsonl", zhiyi)


def test_build_plan_dual_quota(tmp_path):
    _write_index(tmp_path)
    kp = tmp_path / "kp.md"
    kp.write_text(
        "## 四、统一锚定清单\n"
        "1. 心力衰竭的诊断标准\n"
        "2. 冠心病的治疗原则\n"
        "3. 社区获得性肺炎的抗感染治疗\n"
        "4. 糖尿病的诊断标准\n",
        encoding="utf-8",
    )
    bp = tmp_path / "blueprint.md"
    bp.write_text(
        "| 模块 | 范围 | A1 | 合计 |\n"
        "|---|---|---|---|\n"
        "| M01 | 心血管 | 5 | **5** |\n"
        "| M02 | 呼吸与内分泌 | 5 | **5** |\n",
        encoding="utf-8",
    )
    plan = build_plan(
        subject="内科学",
        target=10,
        index_dir=tmp_path,
        keypoints_path=kp,
        blueprint_path=bp,
        batch="TEST",
        top_k_per_keypoint=10,
    )
    assert plan["counts"]["kaoyan"] == 2
    assert plan["counts"]["zhiyi"] == 2
    assert plan["counts"]["selected"] == 4
    assert plan["counts"]["remaining_slots"] == 6
    ids = [x["item_id"] for x in plan["selected"]]
    assert len(ids) == len(set(ids))
    assert plan["keypoint_coverage"]["covered_by_plan"] >= 2


# ── 门禁 ──

def _question(qid, source, stem, refs, confidence="high", answer="A"):
    q = {
        "id": qid,
        "stem": stem,
        "options": ["甲", "乙", "丙", "丁"],
        "answer": answer,
        "keypoint_ref": refs,
        "answer_confidence": confidence,
        "license": "public_noncommercial",
    }
    if source == "kaoyan":
        q["kaoyan_origin"] = {"gs_id": qid, "mode": "原题", "source": "test"}
    elif source == "zhiyi":
        q["zhiyi_origin"] = {"source_id": qid, "mode": "原题", "source": "test"}
    return q


def test_check_pass_and_fail(tmp_path):
    kp = tmp_path / "kp.md"
    kp.write_text(
        "## 四、统一锚定清单\n1. 心力衰竭\n2. 冠心病\n3. 肺炎\n4. 糖尿病\n",
        encoding="utf-8",
    )
    questions = []
    for i in range(4):
        questions.append(_question(f"K{i}", "kaoyan", f"考研题{i}", [f"第{i+1}条"]))
    for i in range(4):
        questions.append(_question(f"Z{i}", "zhiyi", f"执医题{i}", [f"第{i+1}条"]))
    for i in range(12):
        questions.append(_question(f"O{i}", "original", f"原创题{i}", [f"第{i%4+1}条"]))
    f = tmp_path / "bank.json"
    f.write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
    report = run_check(f, keypoints_path=kp)
    assert report["pass"], report["failures"]
    assert report["ratios"]["kaoyan"] == 0.2
    assert report["ratios"]["zhiyi"] == 0.2

    # 低可信答案 → FAIL
    questions[0]["answer_confidence"] = "low"
    f.write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
    report = run_check(f, keypoints_path=kp)
    assert "low_answer_confidence" in report["failures"]

    # 重复题 → FAIL
    questions[0]["answer_confidence"] = "high"
    questions[1]["stem"] = questions[0]["stem"]
    f.write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
    report = run_check(f, keypoints_path=kp)
    assert "duplicate_questions" in report["failures"]


def test_check_allows_documented_shortfall(tmp_path):
    kp = tmp_path / "kp.md"
    kp.write_text(
        "## 四、统一锚定清单\n1. 心力衰竭\n2. 冠心病\n3. 肺炎\n4. 糖尿病\n",
        encoding="utf-8",
    )
    questions = []
    for i in range(4):
        questions.append(_question(f"Z{i}", "zhiyi", f"执医题{i}", [f"第{i+1}条"]))
    for i in range(16):
        questions.append(_question(f"O{i}", "original", f"原创题{i}", [f"第{i%4+1}条"]))
    f = tmp_path / "bank.json"
    f.write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
    plan = {
        "quota_status": {
            "kaoyan": {"requested": 4, "selected": 0, "available": 0, "status": "unavailable"},
            "zhiyi": {"requested": 4, "selected": 4, "available": 6, "status": "met"},
        }
    }
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    report = run_check(f, plan_path=p, keypoints_path=kp)
    assert report["pass"], report["failures"]
    assert "kaoyan" in report["allowed_shortfalls"]
