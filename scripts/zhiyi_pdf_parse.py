# -*- coding: utf-8 -*-
"""zhiyi_pdf_parse.py — 执业医师真题扫描册：版面重建 + 题目切分。

输入：`scripts/zhiyi_pdf_ocr.py` 产出的逐页文本框缓存（JSONL）
输出：`question_bank/real_questions/zhiyi_pdf_raw.jsonl`（RealQuestion schema；再由 build 做去重/入库）
      + `reports/validate/zhiyi_pdf_parse_report.json`（逐册解析质量）

版面差异（实测 49 册）：
  1. 单栏 · 选项同行（2007–2016 单元册，A1/A2）
  2. 单栏 · 选项分行（2022 起）
  3. 双栏（2017–2021 全年册的试卷部分）
  4. A3/A4「（共用题干）」：题号在每个病例内从 1 重排
  5. B1「（共用备选答案）」：选项只印一次，每题只印空的 A. B. C. D. E.
  6. 答案位置：册内逐题【答案】/答案:/答案 X，或册末「参考答案与解析」区
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from real_question.schema import (  # noqa: E402
    RealQuestion,
    exact_hash,
    prepare_item,
    simhash64,
)
from real_question.sources import classify_subject, _norm_subject  # noqa: E402

OCR_DIR = BASE / "知识库素材" / "执业医师真题" / "_ocr"
# 双栏册（2017–2021）MinerU 解析产物：<册名>.md
MINERU_DIR = BASE / "知识库素材" / "执业医师真题" / "_mineru"
OUT_DIR = BASE / "question_bank" / "real_questions"
REPORT = BASE / "reports" / "validate" / "zhiyi_pdf_parse_report.json"

CN_UNIT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}

Q_RE = re.compile(r"^\s*(\d{1,3})\s*[.．、]\s*(.*)$")
ANS_RE = re.compile(r"答\s*案\s*[】\]]?\s*[：:.、]?\s*([A-Ea-e]{1,5})")
EXP_RE = re.compile(r"[【\[]?\s*解\s*析\s*[】\]]?\s*[：:]?")
OPT_RE = re.compile(r"(?<![A-Za-z0-9])([A-E])\s*[．.、]\s*")
SECTION_RE = re.compile(r"^[一二三四五六]、\s*(A[1-4](?:\s*/\s*A[1-4])?|B1|B2)?\s*型?\s*选?择?题?")
UNIT_RE = re.compile(r"^第\s*([一二三四五])\s*单元\s*(.*)$")
SHARED_STEM_RE = re.compile(r"共\s*用\s*(?:题\s*干|题\s*目|病\s*例|题\s*干|题)")
# 页眉页脚：不参与题目内容，否则会粘进上一题的选项里
HEADER_RE = re.compile(r"(真题试卷|参考答案|答案解析|考试题|答题卡|第\s*\d+\s*页)")
PAGE_NO_RE = re.compile(r"^[·•\s]*\d{1,3}[·•\s]*$")
# "6.5×10⁹/L"、"38.5℃"、"1.5cm" 这类数值行不是题目起点：
# 小数点后跟非中文（单位/符号）即判为数值；"4.24岁" 这种中文紧随的仍算题号。
DECIMAL_RE = re.compile(r"^\s*\d{1,3}\s*[.．]\s*\d+(?:\.\d+)?\s*([^\d\s])")
KEY_ROW_RE = re.compile(r"^(?:(\d{1,3})\s*[.．、]?\s*([A-E])(?:\s+|$))+$")
KEY_PAIR_RE = re.compile(r"(\d{1,3})\s*[.．、]?\s*([A-E])(?=\s|$)")
# 册末答案区里「53.B」这类标记可能被夹在正文中间（双栏合并行），四处搜
ANS_PAIR_RE = re.compile(r"(?<![\d.])(\d{1,3})\s*[.．]\s*([A-Ea-e])(?![A-Za-z0-9])")
ANS_SECTION_MARK = ("参考答案", "答案与解析", "答案解析")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


# ── 版面重建 ───────────────────────────────────────────────────────────────

def _join(parts: list[str]) -> str:
    out = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if not out:
            out = p
        elif CJK_RE.search(out[-1]) or CJK_RE.search(p[0]):
            out += p
        else:
            out += " " + p
    return out


def _split_columns(lines: list[list], width: float) -> tuple[list, list, list] | None:
    """双栏页按行首 x 归入左右栏；单栏页返回 None。

    直接按聚类归属分栏，而不是找几何栏缝——扫描册里左栏正文常一直写到栏缝附近，
    与右栏行首在 x 上重叠，几何栏缝不可靠。整幅宽的行（页眉/标题）单独提前输出。
    """
    n = len(lines)
    if n < 12:
        return None
    a, b = width * 0.15, width * 0.70
    for _ in range(20):
        left = [l for l in lines if abs(l[0] - a) <= abs(l[0] - b)]
        right = [l for l in lines if abs(l[0] - a) > abs(l[0] - b)]
        if not left or not right:
            return None
        na = sum(l[0] for l in left) / len(left)
        nb = sum(l[0] for l in right) / len(right)
        if abs(na - a) < 0.5 and abs(nb - b) < 0.5:
            a, b = na, nb
            break
        a, b = na, nb
    if b - a < 0.25 * width:
        return None
    wide = [l for l in lines if (l[2] - l[0]) > 0.55 * width]
    rest = [l for l in lines if (l[2] - l[0]) <= 0.55 * width]
    left = [l for l in rest if abs(l[0] - a) <= abs(l[0] - b)]
    right = [l for l in rest if abs(l[0] - a) > abs(l[0] - b)]
    if len(left) < 0.2 * n or len(right) < 0.2 * n:
        return None
    return wide, left, right


def _rows_of(lines: list[list]) -> list[str]:
    """按纵向重叠聚成行，行内按 x 排序拼接。"""
    if not lines:
        return []
    items = sorted(lines, key=lambda l: (l[1], l[0]))
    rows: list[list[list]] = []
    for l in items:
        h = max(1.0, l[3] - l[1])
        placed = False
        for row in rows:
            ry0 = min(x[1] for x in row)
            ry1 = max(x[3] for x in row)
            ov = min(ry1, l[3]) - max(ry0, l[1])
            if ov > 0.5 * min(h, ry1 - ry0):
                row.append(l)
                placed = True
                break
        if not placed:
            rows.append([l])
    rows.sort(key=lambda r: (min(x[1] for x in r), min(x[0] for x in r)))
    return [_join([x[4] for x in sorted(r, key=lambda x: x[0])]) for r in rows]


def page_rows(page: dict, two_col: bool = True) -> list[str]:
    lines = page.get("lines") or []
    if not lines:
        return []
    w = float(page.get("w") or 1)
    cols = _split_columns(lines, w) if two_col else None
    if cols is None:
        return _rows_of(lines)
    wide, left, right = cols
    return _rows_of(wide) + _rows_of(left) + _rows_of(right)


# ── 题目切分 ───────────────────────────────────────────────────────────────

@dataclass
class QBlock:
    no: int
    unit: int
    section: str
    rows: list[str] = field(default_factory=list)
    shared_stem: str = ""
    shared_options: list[str] = field(default_factory=list)


EMBED_Q_SPLIT = re.compile(r"(?<=[\u4e00-\u9fff])(?=\d{1,3}[.．](?!\d))")


OPT_MARK_ANY = re.compile(r"(?<![A-Za-z0-9])[A-Ea-e]\s*[．.、)）]")


def _expand_embedded(text: str) -> list[str]:
    """MinerU 会把「上一题最后选项 + 下一题题号」并成一段，在 中文+题号+点 处切开。

    只在切点前缀像「选项列表」（含 A–E 标号）时才切，避免把解析正文里的
    「…治疗3.5周」这类普通数字误当题号（配合点后非数字的防小数判断双保险）。
    """
    ms = list(EMBED_Q_SPLIT.finditer(text))
    if not ms:
        return [text]
    out: list[str] = []
    prev = 0
    for m in ms:
        prefix = text[prev:m.start()]
        if OPT_MARK_ANY.search(prefix):
            out.append(prefix)
            prev = m.start()
    out.append(text[prev:])
    return [x for x in out if x.strip()]


def _sections_and_blocks(rows: list[str]) -> tuple[list[QBlock], dict[tuple[int, int], str]]:
    blocks: list[QBlock] = []
    answers: dict[tuple[int, int], str] = {}
    ans_seq: dict[int, list[tuple[int, str]]] = {}
    unit = 0
    section = ""
    cur: QBlock | None = None
    ctx_stem: list[str] = []
    shared_opts: list[str] = []
    shared_buf: list[str] = []
    in_shared = False
    last_no: int | None = None
    ans_mode = False

    def _try_shared() -> None:
        """共用备选答案可能跨 1–3 行印出；凑齐 A–E 才算成功。"""
        nonlocal shared_opts, in_shared, shared_buf
        if not shared_buf:
            return
        opts = _split_options(_join(shared_buf))[1]
        if len(opts) >= 5:
            shared_opts = opts[:5]
            in_shared = False
            shared_buf = []

    queue: deque[str] = deque(rows)
    while queue:
        text = queue.popleft()
        parts = _expand_embedded(text)
        if len(parts) > 1:
            queue.extendleft(reversed(parts[1:]))
        s = parts[0].strip()
        if not s:
            continue

        m = UNIT_RE.match(s)
        if m:
            unit = CN_UNIT.get(m.group(1), unit)
            if cur:
                blocks.append(cur)
                cur = None
            shared_opts, ctx_stem, in_shared, shared_buf = [], [], False, []
            continue

        # 册末「参考答案与解析」区：整段按 题号+字母 抽答案。
        # 双栏答案页的 OCR 会把左右栏并成一行，逐行严格匹配会全部落空，
        # 因此这里在后文一律用宽松正则扫描。
        if any(k in s for k in ANS_SECTION_MARK) and len(s) <= 60:
            ans_mode = True
            continue
        if ans_mode:
            for no, a in ANS_PAIR_RE.findall(s):
                no = int(no)
                answers.setdefault((unit, no), a.upper())
                ans_seq.setdefault(unit, []).append((no, a.upper()))
            continue

        if (len(s) <= 40 and HEADER_RE.search(s)) or PAGE_NO_RE.match(s):
            continue

        # 册末「参考答案与解析」区：题号 + 答案字母
        if len(s) <= 80 and KEY_ROW_RE.match(s) and not CJK_RE.search(s):
            pairs = KEY_PAIR_RE.findall(s)
            if pairs:
                for no, ans in pairs:
                    answers[(unit, int(no))] = ans
                continue

        m = SECTION_RE.match(s)
        if m and len(s) < 160:
            if cur:
                blocks.append(cur)
                cur = None
            section = (m.group(1) or "").strip()
            ctx_stem, shared_opts, in_shared, shared_buf = [], [], False, []
            last_no = None
            continue

        if "共用备选答案" in s:
            if cur:
                blocks.append(cur)
                cur = None
            in_shared = True
            shared_opts = []
            shared_buf = []
            ctx_stem = []
            continue

        if SHARED_STEM_RE.search(s):
            if cur:
                blocks.append(cur)
                cur = None
            in_shared = False
            ctx_stem = [SHARED_STEM_RE.sub("", s).strip().strip("（）()")]
            shared_opts = []
            shared_buf = []
            continue

        if in_shared:
            shared_buf.append(s)
            _try_shared()
            if in_shared:
                continue

        m = Q_RE.match(s)
        if m and not ANS_RE.match(s):
            no = int(m.group(1))
            dm = DECIMAL_RE.match(s)
            if dm and not CJK_RE.search(dm.group(1)):
                if cur is not None:
                    cur.rows.append(s)
                continue
            # 序列闸门：体温/数值（T38.5℃、2.0cm）也长得像「38.」，靠题号连续性排除。
            # A3/A4/B1 组内题号会重排回 1，因此 no==1 永远接受。
            if not (no == 1 or last_no is None or no in (last_no + 1, last_no + 2)):
                if cur is not None:
                    cur.rows.append(s)
                continue
            last_no = no
            rest = m.group(2).strip()
            if cur:
                blocks.append(cur)
            cur = QBlock(no=no, unit=unit, section=section,
                         rows=[rest] if rest else [],
                         shared_stem=_join(ctx_stem),
                         shared_options=list(shared_opts))
            continue

        if cur is not None:
            cur.rows.append(s)
        elif in_shared:
            continue
        else:
            if ctx_stem or unit or section:
                # 病例题干/说明文字：留给下一个 共用题干 组
                if ctx_stem and len(ctx_stem) < 8:
                    ctx_stem.append(s)
    if cur:
        blocks.append(cur)
    return blocks, answers, ans_seq


def _split_options(text: str) -> tuple[str, list[str]]:
    """返回 (stem, options)。

    按 A→E 顺序**逐个向后搜索**标记（不用 lookbehind）：扫描件里选项常与
    上一段数字/英文粘连（如 `16mlD．静脉滴注`），lookbehind 会漏掉 D/E。
    """
    marks: list[tuple[int, int, str]] = []
    pos = 0
    for ch in "ABCDE":
        # OCR 常把小写字母混进选项标号（如 "c.感染"），大小写都要认
        m = re.search(rf"[{ch}{ch.lower()}]\s*[．.、)）]\s*", text[pos:])
        if not m:
            break
        st, en = pos + m.start(), pos + m.end()
        marks.append((st, en, ch))
        pos = en
    if not marks:
        return text.strip(), []
    stem = text[:marks[0][0]].strip()
    opts = []
    for i, (st, en, ch) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        opts.append(text[en:end].strip(" ；;，,。【["))
    return stem, opts


def _clean_stem(stem: str) -> str:
    s = re.sub(r"^[.．、\s]+", "", stem)
    s = s.rstrip(" 【[")
    # OCR 常见误识：尿糖（十十十十）→（++++）
    s = re.sub(r"（[十\s]{2,}）", lambda m: "（" + "+" * m.group(0).count("十") + "）", s)
    s = re.sub(r"\s+", "", s) if CJK_RE.search(s) else re.sub(r"\s+", " ", s)
    return s.strip()


def rows_from_markdown(md: str) -> list[str]:
    """MinerU markdown → 行序列（与 OCR 行同构，供同一套切分逻辑使用）。

    双栏册（2017–2021）用 MinerU 解析：它按版面还原段落，题目与选项顺序正确；
    RapidOCR 的检测器会把同一行的左右栏并成一条长行，无法还原。
    """
    rows: list[str] = []
    for line in md.splitlines():
        s = line.strip()
        if not s or s.startswith("!["):
            continue
        s = re.sub(r"^#+\s*", "", s)
        s = re.sub(r"^[-*]\s+", "", s)
        s = s.replace(r"\~", "~")
        if s:
            rows.append(s)
    return rows


def _items_from_rows(rows: list[str], p: Path, meta: dict, book_stats: dict) -> list[RealQuestion]:
    """行序列 → RealQuestion 列表（OCR 与 MinerU 两条通道共用）。"""
    items: list[RealQuestion] = []
    slug = p.stem
    blocks, key_answers, ans_seq = _sections_and_blocks(rows)
    book_stats["blocks"] = len(blocks)
    # 全年册的答案区可能只标一次单元号；单元对不上时按题号兜底（仅单一单元时）
    key_units = {u for (u, _no) in key_answers}
    key_by_no = {no: a for (_u, no), a in key_answers.items()} if len(key_units) == 1 else {}
    # A3/A4、B1 组内题号会重排回 1，(单元,题号) 键会互相覆盖；
    # 当「某单元答案条数 == 该单元题块数」时，按出现顺序一一配对（试卷顺序=答案顺序）
    blocks_by_unit: dict[int, list[QBlock]] = {}
    for b in blocks:
        blocks_by_unit.setdefault(b.unit, []).append(b)
    pos_answer: dict[int, str] = {}
    for u, lst in ans_seq.items():
        qs = blocks_by_unit.get(u, [])
        if qs and len(qs) == len(lst):
            for b, (_no, a) in zip(qs, lst):
                pos_answer[id(b)] = a

    for b in blocks:
        body = _join(b.rows)
        ans_m = ANS_RE.search(body)
        inline_answer = ans_m.group(1).upper() if ans_m else ""
        exp = ""
        em = EXP_RE.search(body)
        if em:
            exp = body[em.end():].strip()
        main = body[:ans_m.start()] if ans_m else body
        exp = EXP_RE.split(exp)[0] if exp else ""
        stem, opts = _split_options(main)
        stem = _clean_stem(stem)
        # B1：共用备选答案只印一次，逐题只印空的 A. B. C. D. E.
        if b.shared_options and (len(opts) < 3 or sum(1 for o in opts if len(o) >= 1) < 3):
            opts = list(b.shared_options)
            book_stats["shared_options"] += 1

        answer = (inline_answer or pos_answer.get(id(b))
                  or key_answers.get((b.unit, b.no), "") or key_by_no.get(b.no, ""))
        if inline_answer:
            conf = "high"
            evidence = "印刷答案（册内逐题）"
        elif answer:
            conf = "high"
            evidence = "印刷答案（册末参考答案区）"
            book_stats["from_answer_key"] += 1
        else:
            conf = "low"
            evidence = ""

        if b.shared_stem:
            stem = f"{b.shared_stem}{stem}"
            book_stats["shared_stem"] += 1

        qtype = b.section or ("A1" if len(stem) <= 40 else "A2")
        if b.shared_options:
            qtype = b.section or "B1"

        unit = b.unit or meta.get("unit") or 0
        item = RealQuestion(
            item_id=f"ZP-{meta.get('year') or 0}-{unit}-{b.no}-{len(items)}",
            source="zhiyi_pdf",
            source_id=f"{slug}#{unit}-{b.no}",
            exam="执业医师",
            year=meta.get("year"),
            question_no=b.no,
            subject="未分类",
            subject_aliases=[],
            department="",
            module=f"第{unit}单元" if unit else "",
            chapter="",
            keypoints=[],
            teacher_keypoint_refs=[],
            stem=stem,
            options=opts,
            answer=answer.upper(),
            explanation=exp,
            question_type=qtype,
            bloom="",
            difficulty_p=None,
            answer_confidence=conf,
            answer_evidence=evidence,
            license="public_noncommercial",
            license_note="执业医师历年真题（扫描册 OCR）；用户声明仅非商业个人刷题使用",
            dedup_hash=exact_hash(stem, opts),
            simhash=simhash64(stem + " " + " ".join(opts)),
            selectable=True,
            source_file=p.name,
        )
        item = prepare_item(item)
        if not item.selectable:
            if "missing_answer" in item.quality_flags:
                book_stats["no_answer"] += 1
            if any(f.startswith("missing_stem") or f.startswith("answer_out") or
                   f.startswith("option_") or f.startswith("too_many") for f in item.quality_flags):
                book_stats["bad_options"] += 1
            continue
        if len(item.options) != 5:
            book_stats["bad_options"] += 1
            continue

        subject, _ = classify_subject(stem + " " + " ".join(opts), min_score=2)
        item.subject = _norm_subject(subject)
        item.subject_aliases = [item.subject]
        items.append(item)
        book_stats["kept"] += 1
    return items


def build_items(paths: list[Path], pdf_dir: Path | None = None,
                mineru_dir: Path | None = None) -> tuple[list[RealQuestion], dict]:
    """逐册解析。同一册若存在 MinerU markdown（双栏册专用通道）则优先使用。"""
    from zhiyi_pdf_ocr import list_pdfs, parse_meta

    meta_by_slug = {m["slug"]: m for m in list_pdfs(pdf_dir)} if pdf_dir else {}
    items: list[RealQuestion] = []
    report: dict = {"books": [], "totals": {}}

    for p in sorted(paths):
        meta = meta_by_slug.get(p.stem) or parse_meta(p.stem)
        md_path = (Path(mineru_dir) / f"{p.stem}.md") if mineru_dir else None
        if md_path and md_path.exists():
            book_stats = {"file": p.name, "year": meta.get("year"), "unit": meta.get("unit"),
                          "two_column": True, "source": "mineru",
                          "blocks": 0, "kept": 0, "no_answer": 0, "bad_options": 0,
                          "from_answer_key": 0, "shared_options": 0, "shared_stem": 0}
            rows = rows_from_markdown(md_path.read_text(encoding="utf-8"))
            items.extend(_items_from_rows(rows, p, meta, book_stats))
            report["books"].append(book_stats)
            continue

        pages = [json.loads(line) for line in open(p, encoding="utf-8") if line.strip()]
        # 书级版式先验：全书行宽中位数 < 0.35W → 双栏册，否则单栏册。
        # 逐页判定会被「答案页窄栏 / 试卷页宽行」带偏，故按整册投票。
        meds = []
        for pg in pages:
            ws = sorted((l[2] - l[0]) for l in (pg.get("lines") or []))
            if ws and pg.get("w"):
                meds.append(ws[len(ws) // 2] / float(pg["w"]))
        meds.sort()
        # 双栏册要求两个条件同时成立：行宽中位数小 + 绝大多数页能分出左右栏
        # （2010–2016 单栏册行虽短，但只有 ~65% 的页能「分栏」，2017 则是 100%）
        split_ok = sum(1 for pg in pages if _split_columns(pg.get("lines") or [], float(pg.get("w") or 1)))
        book_two_col = (
            bool(meds) and meds[len(meds) // 2] < 0.35
            and pages and split_ok / len(pages) >= 0.9
        )
        rows: list[str] = []
        for pg in pages:
            rows.extend(page_rows(pg, two_col=book_two_col))

        book_stats = {"file": p.name, "year": meta.get("year"), "unit": meta.get("unit"),
                      "two_column": book_two_col, "source": "rapidocr",
                      "blocks": 0, "kept": 0, "no_answer": 0, "bad_options": 0,
                      "from_answer_key": 0, "shared_options": 0, "shared_stem": 0}
        items.extend(_items_from_rows(rows, p, meta, book_stats))
        report["books"].append(book_stats)

    report["totals"] = {
        "books": len(report["books"]),
        "blocks": sum(b["blocks"] for b in report["books"]),
        "kept": sum(b["kept"] for b in report["books"]),
        "no_answer": sum(b["no_answer"] for b in report["books"]),
        "bad_options": sum(b["bad_options"] for b in report["books"]),
        "from_answer_key": sum(b["from_answer_key"] for b in report["books"]),
        "shared_options": sum(b["shared_options"] for b in report["books"]),
        "shared_stem": sum(b["shared_stem"] for b in report["books"]),
    }
    return items, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="执业医师真题扫描册 → 题目级索引")
    ap.add_argument("--ocr-dir", default=str(OCR_DIR))
    ap.add_argument("--mineru-dir", default=str(MINERU_DIR),
                    help="双栏册的 MinerU markdown 目录（同名 .md 优先于 OCR 缓存）")
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=str(OUT_DIR / "zhiyi_pdf_raw.jsonl"))
    ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--dump", type=int, default=0, help="打印前 N 题供人工核对")
    args = ap.parse_args(argv)

    ocr_dir = Path(args.ocr_dir)
    paths = sorted(ocr_dir.glob("*.jsonl"))
    if args.only:
        paths = [p for p in paths if args.only in p.name]
    if not paths:
        print(f"未找到 OCR 缓存：{ocr_dir}")
        return 1

    items, report = build_items(paths, mineru_dir=Path(args.mineru_dir) if args.mineru_dir else None)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it.to_dict(), ensure_ascii=False) + "\n")

    t = report["totals"]
    print(f"✅ {t['books']} 册 → 有效题目 {t['kept']} / 题块 {t['blocks']}"
          f"（无答案 {t['no_answer']}，选项不合格 {t['bad_options']}）")
    print(f"   册末答案区补齐 {t['from_answer_key']}；共用备选答案 {t['shared_options']}；共用题干 {t['shared_stem']}")
    print(f"   索引 {out}\n   报告 {args.report}")
    if args.dump:
        from collections import Counter
        print("   学科分布：", Counter(x.subject for x in items).most_common(10))
        for it in items[: args.dump]:
            print(f"   - [{it.subject}/{it.question_type}] ({it.year}·{it.module}) {it.stem[:40]} | "
                  f"{len(it.options)}项 | 答案 {it.answer} | {it.answer_confidence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
