#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kaoyan_pdf_answers.py — 从原版解析 PDF 提取考研 306 标准答案。

背景（2026-10-20 排查）：
  GoldenSet/真题下册.md 是 OCR/文本化产物，原书标注「答案为绿色的选项」，
  但颜色在转 Markdown 时丢失；大量解析只讲知识点、不写「故答X」，
  所以仅靠解析正则只能恢复约 20%。

  `27网盘/00.西综306历年真题PDF/` 下的原版解析 PDF：
  - 2013–2022：正文含 `1.【标准答案】C`（文本层可直接抽取）
  - 2024：正文含 `正确答案：C`
  - 2005–2012：只有绿色高亮（文本层颜色不可靠），不在此脚本强行猜
  - 2023/2025：扫描件/损坏，暂跳过

用法：
  python scripts/kaoyan_pdf_answers.py
  python scripts/kaoyan_pdf_answers.py --merge
  python scripts/kaoyan_pdf_answers.py --pdf-dir "D:/.../02.306..." --out ...
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# 不用 io.TextIOWrapper 替换 stdout：被 pytest 等导入时会关闭捕获流。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = Path(__file__).resolve().parent.parent
UPPER = BASE / "GoldenSet" / "structured" / "GS_上册_2024.json"
ANSWER_FILE = BASE / "question_bank" / "kaoyan_answers.json"
PDF_ANSWER_FILE = BASE / "question_bank" / "real_questions" / "kaoyan_answers_pdf.json"
MANUAL_ANSWER_FILE = BASE / "question_bank" / "kaoyan_manual_answers.json"

DEFAULT_PDF_DIRS = [
    Path(r"C:\Users\38063\Desktop\27考研AI\27网盘\00.西综306历年真题PDF\02.306西综历年真题解析（2005-2022）"),
    Path(r"C:\Users\38063\Desktop\27考研AI\27网盘\00.西综306历年真题PDF\03.306西综历年真题及答案（2023-2024）"),
    Path(r"C:\Users\38063\Desktop\27考研AI\27网盘\00.西综306历年真题PDF"),
]

STD_RE = re.compile(
    r"(\d{1,3})\s*[\.、]\s*[【（(]*\s*标准答案\s*[】）)]*\s*[：:]?\s*([A-E]{1,5})"
)
CORRECT_RE = re.compile(r"正确答案\s*[：:]\s*([A-E]{1,5})")
QNO_RE = re.compile(r"^(\d{1,3})\s*[\.、]")

GREEN_YEARS = range(2005, 2013)
RENDER_DPI = 150


def extract_year(path: Path) -> int | None:
    m = re.search(r"(19|20)\d{2}", path.name)
    return int(m.group(0)) if m else None


def read_pdf_text(path: Path) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(str(path))
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def extract_std(text: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for m in STD_RE.finditer(text):
        qno = int(m.group(1))
        ans = m.group(2).upper()
        if qno not in out:
            out[qno] = ans
    return out


def extract_2024(text: str) -> dict[int, str]:
    """2024 格式：题干/选项 + 换行 `正确答案：C`。"""
    out: dict[int, str] = {}
    cur: int | None = None
    for line in text.splitlines():
        s = line.strip()
        m = QNO_RE.match(s)
        if m:
            cur = int(m.group(1))
        a = CORRECT_RE.search(s)
        if a and cur is not None and cur not in out:
            out[cur] = a.group(1).upper()
    return out


def _count_green(pix, x0: int, y0: int, x1: int, y1: int) -> int:
    g = 0
    for yy in range(max(0, y0), min(pix.height, y1)):
        for xx in range(max(0, x0), min(pix.width, x1)):
            r, gg, bl = pix.pixel(xx, yy)[:3]
            if gg > 80 and gg > r + 30 and gg > bl + 30:
                g += 1
    return g


def extract_green(path: Path) -> dict[int, tuple[str, int]]:
    """2005–2012 版式：`1. A B C D 解析…`，正确选项字母为绿色。

    返回 {题号: (答案字母, 绿色像素最大值)}。仅当唯一字母显著最绿时采用。
    """
    import fitz

    doc = fitz.open(str(path))
    out: dict[int, tuple[str, int]] = {}
    scale = RENDER_DPI / 72
    try:
        for page in doc:
            pix = page.get_pixmap(dpi=RENDER_DPI)
            data = page.get_text("rawdict")
            for block in data.get("blocks", []):
                for line in block.get("lines", []):
                    chars = [c for s in line["spans"] for c in s.get("chars", [])]
                    text = "".join(c["c"] for c in chars)
                    m = QNO_RE.match(text)
                    if not m:
                        continue
                    qno = int(m.group(1))
                    opts = []
                    started = False
                    for c in chars:
                        ch = c["c"].strip().upper()
                        if ch in "ABCDE":
                            opts.append(c)
                            started = True
                        elif started and ch and ch not in " .、,，:：":
                            break
                    if not opts:
                        continue
                    scores = []
                    for c in opts:
                        x0, y0, x1, y1 = [int(v * scale) for v in c["bbox"]]
                        scores.append((c["c"].strip().upper(), _count_green(pix, x0, y0, x1, y1)))
                    peak = max(v for _, v in scores)
                    if peak < 15:
                        continue
                    selected = sorted({ch for ch, g in scores if g >= max(15, peak * 0.6)})
                    if selected:
                        out.setdefault(qno, ("".join(selected), peak))
    finally:
        doc.close()
    return out


def build_upper_index() -> dict[tuple[int, int], str]:
    data = json.loads(UPPER.read_text(encoding="utf-8"))
    idx: dict[tuple[int, int], str] = {}
    for q in data:
        year = q.get("year")
        qno = q.get("question_no")
        if year is None or qno is None:
            continue
        idx.setdefault((int(year), int(qno)), q["gs_id"])
    return idx


def main() -> int:
    ap = argparse.ArgumentParser(description="从原版解析 PDF 提取考研 306 标准答案")
    ap.add_argument("--pdf-dir", action="append", default=[], help="PDF 目录，可重复")
    ap.add_argument("--out", default=str(PDF_ANSWER_FILE))
    ap.add_argument("--merge", action="store_true", help="合并进 question_bank/kaoyan_answers.json")
    ap.add_argument("--no-green", action="store_true", help="跳过 2005–2012 绿色标记解析（较慢）")
    args = ap.parse_args()

    pdf_dirs = [Path(p) for p in args.pdf_dir] if args.pdf_dir else DEFAULT_PDF_DIRS
    pdfs: list[Path] = []
    for d in pdf_dirs:
        if d.exists():
            pdfs.extend(sorted(d.glob("*.pdf")))
    # 去重（同一文件可能在多个目录）
    seen = set()
    pdfs = [p for p in pdfs if not (str(p) in seen or seen.add(str(p)))]
    if not pdfs:
        print("✗ 未找到解析 PDF。用 --pdf-dir 指定目录（见 DEFAULT_PDF_DIRS）。")
        return 2

    upper_idx = build_upper_index()
    # 已有规则答案（用于绿色标记交叉校验）
    rule_answers = json.loads(ANSWER_FILE.read_text(encoding="utf-8")) if ANSWER_FILE.exists() else {}
    extracted: dict[int, dict[int, str]] = {}
    green_medium: dict[int, dict[int, str]] = {}
    conflicts: list[str] = []
    sources: dict[int, str] = {}
    for p in pdfs:
        year = extract_year(p)
        if year is None:
            continue
        if year in extracted:
            continue
        if year == 2024:
            ans = extract_2024(read_pdf_text(p))
        elif 2013 <= year <= 2022:
            ans = extract_std(read_pdf_text(p))
        elif year in GREEN_YEARS and not args.no_green:
            green = extract_green(p)
            ans = {}
            med = {}
            for qno, (a, _peak) in green.items():
                gs_id = upper_idx.get((year, qno))
                rule = (rule_answers.get(gs_id) or {}) if gs_id else {}
                rule_ans = rule.get("answer_recovered")
                if rule_ans and rule.get("confidence") == "high":
                    if rule_ans == a:
                        ans[qno] = a            # 双方法一致 → high
                    else:
                        conflicts.append(f"{gs_id}(绿{a}/规则{rule_ans})")
                        continue                 # 冲突丢弃，不硬判
                else:
                    med[qno] = a                 # 仅绿色证据 → medium
            if med:
                green_medium[year] = med
        else:
            continue
        if ans:
            extracted[year] = ans
            sources[year] = str(p)

    # 转 gs_id
    records: dict[str, dict] = {}
    stats = Counter()
    for year, ans in sorted(extracted.items()):
        for qno, a in sorted(ans.items()):
            gs_id = upper_idx.get((year, qno))
            if not gs_id:
                stats["no_upper_match"] += 1
                continue
            records[gs_id] = {
                "gs_id": gs_id,
                "year": year,
                "question_no": qno,
                "answer_recovered": a,
                "confidence": "high",
                "evidence": "PDF 标准答案" if year != 2024 else "PDF 正确答案",
                "method": "pdf",
                "source_pdf": sources[year],
            }
            stats["extracted"] += 1

    # 人工转录答案键（2023 扫描件：原 PDF 无文本层，答案页已人工逐题转录）
    manual_count = 0
    if MANUAL_ANSWER_FILE.exists():
        manual = json.loads(MANUAL_ANSWER_FILE.read_text(encoding="utf-8"))
        for year_s, answers in manual.items():
            year = int(year_s)
            for qno_s, a in answers.items():
                qno = int(qno_s)
                gs_id = upper_idx.get((year, qno))
                if not gs_id:
                    continue
                records[gs_id] = {
                    "gs_id": gs_id,
                    "year": year,
                    "question_no": qno,
                    "answer_recovered": str(a).upper(),
                    "confidence": "high",
                    "evidence": "人工转录答案页",
                    "method": "manual_key",
                    "source_pdf": "2023年考研西医综合（仅答案）.pdf",
                }
                manual_count += 1
    stats["manual"] = manual_count

    # 2005–2012：仅绿色标记、无规则高可信交叉校验的题 → medium
    for year, ans in sorted(green_medium.items()):
        for qno, a in sorted(ans.items()):
            gs_id = upper_idx.get((year, qno))
            if not gs_id or gs_id in records:
                continue
            records[gs_id] = {
                "gs_id": gs_id,
                "year": year,
                "question_no": qno,
                "answer_recovered": a,
                "confidence": "medium",
                "evidence": "PDF 绿色标记（单证据）",
                "method": "pdf_green",
                "source_pdf": str(next((p for p in pdfs if extract_year(p) == year), "")),
            }
            stats["green_medium"] += 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ PDF 答案已写出：{out}（{len(records)} 条）")
    for year, ans in sorted(extracted.items()):
        print(f"  {year}: PDF {len(ans)} 条")
    print(f"  人工转录：{stats['manual']}；绿色标记 medium：{stats['green_medium']}；冲突丢弃：{len(conflicts)}")
    print(f"  未匹配上册 gs_id：{stats['no_upper_match']}")
    if conflicts:
        print("  冲突样例：" + "；".join(conflicts[:5]))

    if args.merge:
        base = json.loads(ANSWER_FILE.read_text(encoding="utf-8")) if ANSWER_FILE.exists() else {}
        added = 0
        for gs_id, rec in records.items():
            old = base.get(gs_id) or {}
            # PDF 标准答案优先；保留旧解析文本
            merged = dict(old)
            merged.update(rec)
            if old.get("explanation"):
                merged["explanation"] = old["explanation"]
            base[gs_id] = merged
            added += 1
        ANSWER_FILE.write_text(json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✅ 已合并进 {ANSWER_FILE}：新增/覆盖 {added} 条；总 {len(base)} 条")
        print(f"  high：{sum(1 for v in base.values() if v.get('confidence') == 'high')}；"
              f"medium：{sum(1 for v in base.values() if v.get('confidence') == 'medium')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
