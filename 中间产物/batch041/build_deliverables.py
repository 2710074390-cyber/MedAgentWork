# -*- coding: utf-8 -*-
"""生成 batch041 交付物：题库 JSON + 押题卷 MD（走 paper_builder.export_paper_md）。"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:/Users/38063/Desktop/MedAgentWork")
sys.path.insert(0, str(ROOT / "中间产物" / "batch041"))
sys.path.insert(0, str(ROOT / "scripts"))

from questions import build  # noqa: E402

SUBJECT = "耳鼻咽喉头颈外科学"


def main() -> int:
    qs = build()
    assert len(qs) == 100, f"题数不对: {len(qs)}"

    # 1) 题库 JSON（最终产物，供 build_seed.py 读取）
    out_dir = ROOT / "最终产物" / "batch041"
    out_dir.mkdir(parents=True, exist_ok=True)
    bank_json = out_dir / "ALL_questions_FIXED.json"
    bank_json.write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")

    # 2) 押题卷机器源 + MD 交付
    paper_qs = [{
        "qid": q["id"],
        "system": q["module_name"],
        "bloom": q["bloom"],
        "source": q["source_page"],
        "stem": q["stem"],
        "options": [o["text"] for o in q["options"]],
        "answer": q["answer"],
        "explanation": q["explanation"],
        "type": q["type"],
    } for q in qs]

    meta = {
        "subject": SUBJECT,
        "count": len(paper_qs),
        "source": "26秋耳鼻咽喉头颈外科-期末复习重点",
    }
    paper_json = ROOT / "最终产物" / f"押题卷_{SUBJECT}_100题.json"
    paper_json.write_text(json.dumps(
        {"meta": meta, "questions": paper_qs}, ensure_ascii=False, indent=1), encoding="utf-8")

    md_out = ROOT / "大四上" / "押题卷" / f"{SUBJECT}押题卷_100题.md"
    from paper_builder import export_paper_md  # noqa: E402
    path, counter = export_paper_md(paper_qs, meta, md_out)

    # 组卷口径改写：本卷为「按重点文档逐条覆盖的原创命题」，不是从既有题库抽题，
    # paper_builder 默认的「考频权重 × 难度配平（calibrated_p）」不适用。
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "> 组卷口径：考频权重 × 难度配平（calibrated_p）",
        "> 组卷口径：26秋期末复习重点逐条覆盖 · 100% 原创命题（非题库抽题）")
    path.write_text(text, encoding="utf-8")

    # 3) 统计
    print("题数:", len(qs))
    print("题型:", dict(Counter(q["type"] for q in qs)))
    print("模块:", dict(Counter(q["module"] for q in qs)))
    print("Bloom:", dict(Counter(q["bloom"] for q in qs)))
    print("MD题型分布:", dict(counter))
    print("MD:", path)
    print("题库JSON:", bank_json)
    print("押题卷JSON:", paper_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
