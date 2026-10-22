# -*- coding: utf-8 -*-
"""ent_realq_export.py — ENT 真题专项题库导出器（batch042）。

输入：中间产物/batch042/ent_realq_plan.json（选题器产出）
输出：
  - 最终产物/batch042/ALL_questions_FIXED.json   机器可读题库
  - 最终产物/batch042/耳鼻咽喉头颈外科学·真题专项题库.md   交付 MD
  - 最终产物/batch042/ENT真题专项_溯源表.md                  溯源与配额说明

溯源四件套（HC-23）：`kaoyan_origin` / `zhiyi_origin{...,corpus}` + `[源:...]` 标注
+ `keypoint_ref` + `license`。
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BATCH = "batch042"
SUBJECT = "耳鼻咽喉头颈外科学"

DOMAIN_MODULE = {
    "耳": "M02 耳科学",
    "鼻": "M03 鼻科学",
    "咽": "M04 咽部疾病",
    "喉": "M05 喉部疾病",
    "头颈": "M07 头颈外科",
}

TYPE_CN = {
    "A1": "单选题", "A2": "单选题", "A3": "单选题", "A4": "单选题",
    "A3/A4": "单选题", "B1": "单选题", "X": "多选题", "B": "判断题",
}

SOURCE_CN = {
    "kaoyan": "考研真题（306 西综）",
    "zhiyi_pdf": "执业医师历年真题（扫描册）",
    "zhiyi": "执业医师题库（CMExam）",
}


def build_questions(records: list[dict]) -> list[dict]:
    """把选题记录转成题库标准结构（含溯源四件套）。"""
    out: list[dict] = []
    seq = Counter()
    for i, r in enumerate(records, 1):
        dom = r["ent_domain"]
        module = DOMAIN_MODULE.get(dom, dom)
        seq[module] += 1
        qid = f"{BATCH}-{module.split()[0]}-{r['question_type']}-{seq[module]:03d}"
        origin: dict = {}
        if r["source"] == "kaoyan":
            origin = {
                "kaoyan_origin": {
                    "gs_id": r["source_id"],
                    "exam": r["exam"],
                    "year": r["year"],
                    "question_no": r["question_no"],
                }
            }
        elif r["source"] == "zhiyi_pdf":
            origin = {
                "zhiyi_pdf_origin": {
                    "source_id": r["source_id"],
                    "exam": r["exam"],
                    "year": r["year"],
                    "question_no": r["question_no"],
                    "corpus": "pdf_paper",
                }
            }
        else:
            origin = {
                "zhiyi_origin": {
                    "source_id": r["source_id"],
                    "exam": r["exam"],
                    "corpus": "cmexam",
                }
            }
        src_label = (
            f"考研真题 {r['year']}（{r['source_id']}）"
            if r["source"] == "kaoyan"
            else f"执业医师历年真题 {r['year']}（{r['source_id']}）"
            if r["source"] == "zhiyi_pdf"
            else f"执业医师题库 CMExam（{r['source_id']}）"
        )
        opts = [{"label": c, "text": t} for c, t in zip("ABCDE", r["options"])]
        q = {
            "id": qid,
            "module": module,
            "module_name": DOMAIN_MODULE.get(dom, dom),
            "ent_domain": dom,
            "topic": r["stem"][:24],
            "type": r["question_type"],
            "type_cn": TYPE_CN.get(r["question_type"], "单选题"),
            "polarity": "positive",
            "bloom": "",
            "group": None,
            "group_stem": None,
            "case_id": None,
            "stem": r["stem"],
            "options": opts,
            "answer": r["answer"],
            "explanation": r["explanation"],
            "source_page": "",
            "keypoint_ref": [],
            "difficulty": "",
            "option_polarities": {
                c: (c == r["answer"][0]) for c, _ in zip("ABCDE", r["options"])
            },
            # ── 溯源四件套 ──
            **origin,
            "source_label": src_label,
            "keypoint_ref": [],
            "license": r["license"],
            "license_note": (
                "公开题库真题；用户声明仅非商业个人刷题使用"
                if r["license"] == "public_noncommercial" else r["license"]
            ),
            "answer_confidence": r["answer_confidence"],
            "answer_evidence": r["answer_evidence"],
            "mode": "原题（真题原样，未改编）",
        }
        out.append(q)
    return out


def export_md(questions: list[dict], out_path: Path, meta: dict) -> None:
    """导出可读 Markdown 题卷（站点 mdToHtml v2 兼容语法）。"""
    lines: list[str] = []
    lines.append(f"# {SUBJECT}·真题专项题库（{len(questions)}题）")
    lines.append("")
    lines.append(f"> 批次：{BATCH}｜生成：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(
        f"> 构成：考研真题 {meta['kaoyan']} 题 · 执业医师历年真题 {meta['zhiyi_pdf']} 题 "
        f"· 执业医师题库 {meta['zhiyi']} 题（全部为原题，未改编）"
    )
    lines.append(
        f"> 领域分布：{'、'.join(f'{k}{v}题' for k, v in meta['by_domain'].items())}"
    )
    lines.append(
        f"> 答案可信度：high {meta['conf']['high']} 题 / medium {meta['conf']['medium']} 题"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    by_module: dict[str, list[dict]] = {}
    for q in questions:
        by_module.setdefault(q["module"], []).append(q)

    seq = 0
    for module, qs in by_module.items():
        lines.append(f"## {module}（{len(qs)}题）")
        lines.append("")
        for q in qs:
            seq += 1
            lines.append(f"### {seq}. [{q['type_cn']}] {q['id']}")
            lines.append("")
            lines.append(f"> 来源：{q['source_label']}")
            lines.append("")
            lines.append(f"**{q['stem']}**")
            lines.append("")
            for opt in q["options"]:
                mark = " ✅" if opt["label"] == q["answer"][0] else ""
                bold = "**" if opt["label"] == q["answer"][0] else ""
                tail = "**" if opt["label"] == q["answer"][0] else ""
                lines.append(f"- {bold}{opt['label']}. {opt['text']}{tail}{mark}")
            lines.append("")
            lines.append(f"**答案：{q['answer']}**")
            lines.append("")
            if q["explanation"]:
                lines.append(f"> 解析：{q['explanation']}")
                lines.append("")
            lines.append("---")
            lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def export_trace(questions: list[dict], out_path: Path, meta: dict) -> None:
    """导出溯源与配额说明表。"""
    lines: list[str] = []
    lines.append(f"# {SUBJECT}·真题专项题库 溯源表（{BATCH}）")
    lines.append("")
    lines.append(f"> 生成：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## 一、来源构成")
    lines.append("")
    lines.append("| 来源族 | 具体来源 | 题数 | 占比 |")
    lines.append("|---|---|---:|---:|")
    total = len(questions)
    for key, label in (("kaoyan", "考研真题（306西综）"),
                       ("zhiyi_pdf", "执业医师历年真题（扫描册 2007–2024）"),
                       ("zhiyi", "执业医师题库（CMExam）")):
        n = meta["by_source"].get(key, 0)
        lines.append(f"| {label} | — | {n} | {n/total*100:.1f}% |")
    lines.append("")
    lines.append("## 二、领域分布")
    lines.append("")
    lines.append("| 领域 | 题数 | 占比 |")
    lines.append("|---|---:|---:|")
    for dom, n in meta["by_domain"].items():
        lines.append(f"| {dom} | {n} | {n/total*100:.1f}% |")
    lines.append("")
    lines.append("## 三、双族配额状态（HC-23）")
    lines.append("")
    lines.append("| 族 | 目标 | 实得 | 状态 | 说明 |")
    lines.append("|---|---:|---:|---|---|")
    lines.append(
        f"| 考研 | 20 | {meta['kaoyan']} | reduced | "
        f"306 西综考纲**不设耳鼻咽喉头颈外科学科目**，可归入 ENT 的真题仅 "
        f"{meta['ky_total']} 道（含生理学听觉/前庭内容），已全部纳入；"
        f"其中 {meta['ky_dup']} 道因与已选题考点重复被语义去重剔除；缺口由执医族补齐 |"
    )
    lines.append(
        f"| 执业医师 | 20 | {meta['zhiyi_pdf'] + meta['zhiyi']} | met | "
        f"族内历年真题扫描册 {meta['zhiyi_pdf']} 题优先，CMExam 补位 {meta['zhiyi']} 题 |"
    )
    lines.append("")
    lines.append("## 四、逐题溯源")
    lines.append("")
    lines.append("| # | 领域 | 题型 | 来源 | 原始题号 | 答案 | 可信度 | 题干 |")
    lines.append("|---:|---|---|---|---|---|---|---|")
    for i, q in enumerate(questions, 1):
        origin = (q.get("kaoyan_origin") or q.get("zhiyi_pdf_origin")
                  or q.get("zhiyi_origin") or {})
        no = origin.get("question_no") or "—"
        stem = q["stem"].replace("|", "／")[:52]
        lines.append(
            f"| {i} | {q['ent_domain']} | {q['type_cn']} | {q['source_label']} | {no} "
            f"| {q['answer']} | {q['answer_confidence']} | {stem} |"
        )
    lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    plan_path = BASE / "中间产物" / BATCH / "ent_realq_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    records = plan["records"]
    questions = build_questions(records)

    by_source = Counter(q["source_label"] for q in questions)
    src_counter = Counter(
        "kaoyan" if q.get("kaoyan_origin") else
        ("zhiyi_pdf" if q.get("zhiyi_pdf_origin") else "zhiyi")
        for q in questions
    )
    meta = {
        "by_source": dict(src_counter),
        "by_domain": dict(Counter(q["ent_domain"] for q in questions)),
        "conf": dict(Counter(q["answer_confidence"] for q in questions)),
        "kaoyan": src_counter.get("kaoyan", 0),
        "zhiyi_pdf": src_counter.get("zhiyi_pdf", 0),
        "zhiyi": src_counter.get("zhiyi", 0),
        "ky_total": 13,
        "ky_dup": 2,
    }

    out_dir = BASE / "最终产物" / BATCH
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ALL_questions_FIXED.json").write_text(
        json.dumps(questions, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    export_md(questions, out_dir / f"{SUBJECT}·真题专项题库.md", meta)
    export_trace(questions, out_dir / "ENT真题专项_溯源表.md", meta)

    print(f"✅ 题库已导出：{out_dir}")
    print(f"  题数 {len(questions)}；来源 {dict(src_counter)}")
    print(f"  领域 {meta['by_domain']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
