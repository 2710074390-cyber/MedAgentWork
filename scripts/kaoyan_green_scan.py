#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kaoyan_green_scan.py — 从贺银成扫描版下册直接识别「绿色选项字母」答案。

背景（2026-10-20）：
  《历年真题精析（下册）》原书标注「答案为绿色的选项」，但 OCR 转 Markdown 时
  颜色丢失，导致 1994–2004 大量题目只剩解析、没有答案。
  本脚本回到扫描版 PDF + MinerU layout（行 bbox），按像素识别哪一个字母是绿色：

    1. 按 MinerU layout 找到 `N. ABCDE ...` 题首行；
    2. 渲染该页 → 取行带 → 连通域分割；
    3. 从行首向右累积「间距 < 阈值」的字形簇 = 题号 + 字母；
    4. 取簇内最后 N 个字形为 A..E，统计每个字形的绿色像素占比；
    5. 绿色占比显著最高的字母 = 答案（多选可多个）。

用法：
  python scripts/kaoyan_green_scan.py --validate            # 用 2013/2012 标准答案验证
  python scripts/kaoyan_green_scan.py --apply --merge       # 1994–2004 提取并合并
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy as np

BASE = Path(__file__).resolve().parent.parent
UPPER = BASE / "GoldenSet" / "structured" / "GS_上册_2024.json"
ANSWER_FILE = BASE / "question_bank" / "kaoyan_answers.json"
OUT_FILE = BASE / "question_bank" / "real_questions" / "kaoyan_answers_green.json"

MINERU_ROOT = Path(r"C:\Users\38063\MinerU")
PART_GLOB = "2026考研西医临床医学综合能力历年真题(下册)*"
SPLIT_DIR = Path(r"C:\Users\38063\Desktop\大三下\26贺银成\split_150mb")

HEADER_RE = re.compile(r"^\s*(\d{1,3})\s*[\.、]\s*([A-E]{2,6})")
YEAR_RE = re.compile(r"(19\d{2}|20\d{2})\s*年全国硕士")
RENDER_DPI = 300
CLUSTER_GAP_PX = 22       # 题号/字母之间视为同一簇的最大水平间距（300dpi）
MIN_GLYPH_AREA = 6
GREEN_RATIO = 0.10        # 旧版像素占比阈值（保留兼容）
GREEN_MARGIN = 0.06       # 旧版差值（保留兼容）
GREENNESS_MIN = 3.0       # 字形绿色强度下限：mean(G-(R+B)/2) over 字形像素
GREENNESS_MARGIN = 1.5    # 单选时与次高格的差距


@dataclass
class Detected:
    page: int
    qno: int
    letters: str
    scores: list[float]


def _green_mask(arr: np.ndarray) -> np.ndarray:
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    return (g > 70) & (g > r * 1.25) & (g > b * 1.25)


def _components(mask: np.ndarray):
    """极简连通域：行扫描 + 并查集，返回 [(x0,y0,x1,y1,pixel_count)]。"""
    h, w = mask.shape
    parent = {}
    boxes = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
            ba, bb = boxes[ra], boxes[rb]
            boxes[ra] = (min(ba[0], bb[0]), min(ba[1], bb[1]),
                         max(ba[2], bb[2]), max(ba[3], bb[3]), ba[4] + bb[4])
            del boxes[rb]

    for y in range(h):
        for x in range(w):
            if not mask[y, x]:
                continue
            idx = y * w + x
            parent[idx] = idx
            boxes[idx] = (x, y, x + 1, y + 1, 1)
            for nx, ny in ((x - 1, y), (x, y - 1), (x + 1, y - 1), (x - 1, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and mask[ny, nx]:
                    nidx = ny * w + nx
                    if nidx in parent:
                        union(idx, nidx)

    roots = {find(k) for k in parent}
    return [boxes[r] for r in roots if boxes[r][4] >= MIN_GLYPH_AREA]


def detect_page(page_img: np.ndarray, lines: list[dict], scale: float) -> list[Detected]:
    """lines: [{bbox:[x0,y0,x1,y1], text:str}]，单位 pt。

    MinerU 的行 bbox 常是「整段」高度（含多行视觉行），题首字母只在段落顶部，
    因此纵向只取段落顶部 18pt。
    """
    out: list[Detected] = []
    green_all = _green_mask(page_img)
    for line in lines:
        m = HEADER_RE.match(line["text"])
        if not m:
            continue
        qno = int(m.group(1))
        n_letters = len(m.group(2))
        bx0, by0, bx1, _by1 = line["bbox"]
        x0 = int(bx0 * scale)
        y0 = max(0, int(by0 * scale) - 2)
        y1 = min(page_img.shape[0], int((by0 + 18) * scale))
        x1 = min(page_img.shape[1], x0 + int((bx1 - bx0) * 0.35 * scale) + 20)
        if x1 - x0 < 10 or y1 - y0 < 6:
            continue
        crop = page_img[y0:y1, x0:x1]
        if crop.size == 0:
            continue
        dark = crop.mean(axis=2) < 150
        comps = sorted(_components(dark), key=lambda c: c[0])
        if len(comps) < 3:
            continue

        # 找小数点：小而扁的组件；字母从小数点之后开始
        dot_idx = None
        for i, (cx0, cy0, cx1, cy1, n) in enumerate(comps[:4]):
            if (cx1 - cx0) <= 9 and (cy1 - cy0) <= 9:
                dot_idx = i
                break
        if dot_idx is None:
            continue

        # 字母区：小数点后第一个组件起，直到出现 ≥ CLUSTER_GAP_PX 的间隔
        start_i = dot_idx + 1
        if start_i >= len(comps):
            continue
        end_i = start_i
        while end_i + 1 < len(comps) and comps[end_i + 1][0] - comps[end_i][2] <= CLUSTER_GAP_PX:
            end_i += 1
        region_x0 = comps[start_i][0]
        region_x1 = comps[end_i][2]
        if region_x1 - region_x0 < n_letters * 6:
            continue

        # 等分成 n_letters 格（字母按等距印刷，避免字形被拆/粘连导致错位）
        step = (region_x1 - region_x0) / n_letters
        scores = []
        for k in range(n_letters):
            cx0 = int(region_x0 + k * step)
            cx1 = int(region_x0 + (k + 1) * step)
            box_dark = dark[:, cx0:cx1]
            if not box_dark.any():
                scores.append(0.0)
                continue
            sub = crop[:, cx0:cx1]
            r = sub[:, :, 0].astype(np.int16)
            g_ch = sub[:, :, 1].astype(np.int16)
            b = sub[:, :, 2].astype(np.int16)
            # 绿色强度：G 相对 R/B 的平均超出量（只在字形像素上统计）
            greenness = ((g_ch - r) + (g_ch - b)) / 2.0
            scores.append(round(float(greenness[box_dark].mean()), 2))
        best = max(scores)
        if best < GREENNESS_MIN:
            continue
        picked = [i for i, s in enumerate(scores) if s >= max(GREENNESS_MIN, best * 0.5)]
        if not picked:
            continue
        # 单选：与次高格需有差距
        if len(picked) == 1:
            others = [s for i, s in enumerate(scores) if i != picked[0]]
            if others and best - max(others) < GREENNESS_MARGIN:
                continue
        letters = "".join(chr(65 + i) for i in sorted(picked))
        out.append(Detected(page=-1, qno=qno, letters=letters, scores=scores))
    return out


def _walk_lines(block) -> list[dict]:
    """递归收集 block（含 list/table 嵌套 blocks）里的行。"""
    out = []
    for ln in block.get("lines", []) or []:
        text = "".join(sp.get("content", "") for sp in ln.get("spans", []))
        out.append({"bbox": ln["bbox"], "text": text})
    for sub in block.get("blocks", []) or []:
        out.extend(_walk_lines(sub))
    return out


def iter_parts():
    for d in sorted(MINERU_ROOT.glob(PART_GLOB)):
        lay = d / "layout.json"
        if not lay.exists():
            continue
        stem = d.name.rsplit("-", 1)[0]
        origin = next(iter(d.glob("*_origin.pdf")), None)
        split_pdf = SPLIT_DIR / f"{stem}.pdf"
        pdf = origin if origin and origin.exists() else (split_pdf if split_pdf.exists() else None)
        if pdf is None:
            print(f"  ! 找不到 PDF：{d.name}")
            continue
        yield d, pdf


def scan(years: set[int] | None = None, limit_pages: int = 0):
    import fitz

    answers: dict[str, dict] = {}
    stats = Counter()
    for d, pdf in iter_parts():
        layout = json.loads((d / "layout.json").read_text(encoding="utf-8"))
        doc = fitz.open(str(pdf))
        scale = RENDER_DPI / 72
        current_year = None
        for pg in layout["pdf_info"]:
            idx = pg["page_idx"]
            texts = []
            lines = []
            for block in pg.get("para_blocks", []):
                for ln in _walk_lines(block):
                    texts.append(ln["text"])
                    lines.append(ln)
            head = " ".join(texts[:3])
            ym = YEAR_RE.search(head) or YEAR_RE.search(" ".join(texts))
            if ym:
                current_year = int(ym.group(1))
            if current_year is None:
                continue
            if years and current_year not in years:
                continue
            img = doc[idx].get_pixmap(dpi=RENDER_DPI)
            arr = np.frombuffer(img.samples, dtype=np.uint8).reshape(img.height, img.width, img.n)
            arr = arr[:, :, :3]
            dets = detect_page(arr, lines, scale)
            for det in dets:
                key = f"{current_year}-{det.qno}"
                if key in answers:
                    continue
                answers[key] = {"year": current_year, "qno": det.qno,
                                "answer": det.letters, "scores": det.scores}
                stats["detected"] += 1
            stats["pages"] += 1
            if limit_pages and stats["pages"] >= limit_pages:
                return answers, stats
        doc.close()
    return answers, stats


def upper_index() -> dict[tuple[int, int], str]:
    data = json.loads(UPPER.read_text(encoding="utf-8"))
    idx = {}
    for q in data:
        if q.get("year") is None or q.get("question_no") is None:
            continue
        idx.setdefault((int(q["year"]), int(q["question_no"])), q["gs_id"])
    return idx


def cmd_validate(args):
    pool = json.loads(ANSWER_FILE.read_text(encoding="utf-8"))
    years = {2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015, 2014, 2013}
    found, stats = scan(years=years)
    idx = upper_index()
    agree = diff = 0
    errors = []
    for key, rec in found.items():
        gs = idx.get((rec["year"], rec["qno"]))
        if not gs:
            continue
        truth = (pool.get(gs) or {}).get("answer_recovered")
        if not truth:
            continue
        if truth == rec["answer"]:
            agree += 1
        else:
            diff += 1
            errors.append((gs, truth, rec["answer"], rec["scores"]))
    total = agree + diff
    print(f"验证：识别 {len(found)} 题；可比对 {total}")
    print(f"  一致 {agree}；不一致 {diff}；准确率 {agree / total * 100 if total else 0:.1f}%")
    if args.verbose:
        for e in errors[: args.show]:
            print("   ", e[0], "标准", e[1], "扫描", e[2], [round(x, 2) for x in e[3]])
    return 0


def cmd_apply(args):
    if args.years:
        years = {int(y) for y in args.years.split(",") if y.strip()}
    else:
        years = set(range(1994, 2005))
    found, stats = scan(years=years)
    idx = upper_index()
    records = {}
    for key, rec in found.items():
        gs = idx.get((rec["year"], rec["qno"]))
        if not gs:
            continue
        scores = rec["scores"]
        best = max(scores) if scores else 0.0
        others = sorted(scores, reverse=True)[1:] or [0.0]
        margin = best - others[0]
        # 强信号（绿字明显且唯一）→ high；弱信号 → medium
        confidence = "high" if best >= 8.0 and margin >= 4.0 else "medium"
        records[gs] = {
            "gs_id": gs,
            "year": rec["year"],
            "question_no": rec["qno"],
            "answer_recovered": rec["answer"],
            "confidence": confidence,
            "evidence": "扫描版绿色标记",
            "method": "scan_green",
            "green_scores": [round(x, 2) for x in scores],
        }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ 扫描识别 {len(records)} 条 → {OUT_FILE}")
    print(f"  扫描页数 {stats['pages']}")
    if args.merge:
        base = json.loads(ANSWER_FILE.read_text(encoding="utf-8")) if ANSWER_FILE.exists() else {}
        added = 0
        for gs, rec in records.items():
            if gs in base:
                continue
            base[gs] = rec
            added += 1
        ANSWER_FILE.write_text(json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✅ 合并进 {ANSWER_FILE}：新增 {added}；总 {len(base)}")
        print(f"  high {sum(1 for v in base.values() if v.get('confidence') == 'high')}；"
              f"medium {sum(1 for v in base.values() if v.get('confidence') == 'medium')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="扫描版绿色标记答案识别")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--show", type=int, default=20)
    ap.add_argument("--years", default="", help="逗号分隔年份，如 1994,1995（默认 1994-2004）")
    args = ap.parse_args()
    if args.validate:
        return cmd_validate(args)
    if args.apply:
        return cmd_apply(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
