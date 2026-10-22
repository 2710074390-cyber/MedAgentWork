# -*- coding: utf-8 -*-
"""pdf_ocr.py — 执业医师真题扫描册 OCR 缓存层（RapidOCR，本地离线）。

设计要点
--------
1. **只做 OCR + 版面几何**，不做题目切分；切分交给 `pdf_parse.py`。
   两者解耦的好处：解析规则可以反复迭代而不用重跑 2286 页 OCR。
2. 缓存按册一文件（JSONL，一行一页），带页数与 dpi 指纹；可断点续跑。
3. 本机无 GPU、无 tesseract，RapidOCR（onnxruntime）是唯一离线可用且
   能完整识别「【答案】X」短行的引擎（MinerU 会吞答案行，见 HC-23 决策记录）。

缓存位置：`知识库素材/执业医师真题/_ocr/<slug>.jsonl`（.gitignore 忽略，可重建）

用法
----
  python scripts/zhiyi_pdf_ocr.py scan
  python scripts/zhiyi_pdf_ocr.py run [--workers 8] [--dpi 200] [--force] [--only 2014]
  python scripts/zhiyi_pdf_ocr.py stats
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = Path(__file__).resolve().parent.parent
DEFAULT_PDF_DIR = Path(
    os.environ.get("ZHIYI_PDF_DIR", r"C:/Users/38063/Desktop/27网盘/执业医师真题及答案（2010-2023年）")
)
CACHE_DIR = BASE / "知识库素材" / "执业医师真题" / "_ocr"
DEFAULT_DPI = 200

CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}


def slugify(name: str) -> str:
    s = re.sub(r"\.pdf$", "", name, flags=re.I)
    s = re.sub(r"[（）()【】\s]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def parse_meta(name: str) -> dict:
    """从文件名抽取年份 / 单元 / 分部。"""
    year_m = re.search(r"(19|20)\d{2}", name)
    year = int(year_m.group(0)) if year_m else None
    unit = None
    m = re.search(r"第([一二三四五六])单元", name)
    if m:
        unit = CN_NUM.get(m.group(1))
    part = None
    m = re.search(r"第([一二三四五])部分", name)
    if m:
        part = CN_NUM.get(m.group(1))
    return {"year": year, "unit": unit, "part": part}


def list_pdfs(pdf_dir: Path | None = None) -> list[dict]:
    pdf_dir = Path(pdf_dir or DEFAULT_PDF_DIR)
    out = []
    for p in sorted(pdf_dir.glob("*.pdf")):
        meta = parse_meta(p.name)
        meta.update({"path": p, "name": p.name, "slug": slugify(p.name), "size_mb": round(p.stat().st_size / 1048576, 1)})
        out.append(meta)
    return out


# ── 工作进程 ────────────────────────────────────────────────────────────────

_OCR = None


def _engine():
    global _OCR
    if _OCR is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR = RapidOCR(intra_op_num_threads=2)
    return _OCR


def _ocr_image(engine, png: bytes) -> list[list]:
    res, _ = engine(png)
    out = []
    for box, text, conf in (res or []):
        xs = [float(pt[0]) for pt in box]
        ys = [float(pt[1]) for pt in box]
        text = (text or "").strip()
        if not text:
            continue
        out.append([round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1),
                    text, round(float(conf), 3)])
    return out


def _ocr_chunk(args) -> list[dict]:
    """OCR 一段连续页（一次 open，避免每页重开文档）。"""
    path, start, end, dpi = args
    import fitz

    doc = fitz.open(path)
    engine = _engine()
    pages = []
    for i in range(start, min(end, len(doc))):
        pix = doc[i].get_pixmap(dpi=dpi)
        lines = _ocr_image(engine, pix.tobytes("png"))
        pages.append({"page": i, "w": pix.width, "h": pix.height, "lines": lines})
    doc.close()
    return pages


def ocr_pdf(meta: dict, dpi: int = DEFAULT_DPI, workers: int = 8, force: bool = False) -> Path:
    import fitz

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = CACHE_DIR / f"{meta['slug']}.jsonl"
    doc = fitz.open(meta["path"])
    n = len(doc)
    doc.close()

    if out.exists() and not force:
        have = sum(1 for _ in open(out, encoding="utf-8"))
        if have == n:
            return out

    # 按页数切成 2×workers 段，平衡尾段
    chunks = max(1, workers * 2)
    step = max(1, (n + chunks - 1) // chunks)
    tasks = [(str(meta["path"]), s, min(s + step, n), dpi) for s in range(0, n, step)]
    pages: list[dict] = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for part in ex.map(_ocr_chunk, tasks):
            pages.extend(part)
    pages.sort(key=lambda x: x["page"])
    tmp = out.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for pg in pages:
            f.write(json.dumps(pg, ensure_ascii=False) + "\n")
    tmp.replace(out)
    return out


def load_pages(slug: str) -> list[dict]:
    p = CACHE_DIR / f"{slug}.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in open(p, encoding="utf-8") if line.strip()]


# ── CLI ────────────────────────────────────────────────────────────────────

def cmd_scan(args) -> int:
    rows = list_pdfs(args.pdf_dir)
    import fitz

    total = 0
    for r in rows:
        d = fitz.open(r["path"])
        n = len(d)
        d.close()
        total += n
        have = ""
        cache = CACHE_DIR / f"{r['slug']}.jsonl"
        if cache.exists():
            have = f"缓存 {sum(1 for _ in open(cache, encoding='utf-8'))}p"
        print(f"{r['year']} 单元{r['unit'] or '-'} 分部{r['part'] or '-'}  {n:4d}p  {r['size_mb']:6.1f}MB  {have:10s} {r['name']}")
    print(f"共 {len(rows)} 册 / {total} 页")
    return 0


def cmd_run(args) -> int:
    rows = list_pdfs(args.pdf_dir)
    if args.only:
        rows = [r for r in rows if args.only in r["name"]]
    if not rows:
        print("没有匹配的 PDF")
        return 1
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        st = time.time()
        out = ocr_pdf(r, dpi=args.dpi, workers=args.workers, force=args.force)
        n = sum(1 for _ in open(out, encoding="utf-8"))
        print(f"[{i}/{len(rows)}] {r['name']} → {n}p  {time.time()-st:.0f}s", flush=True)
    print(f"✅ 完成 {len(rows)} 册，{time.time()-t0:.0f}s")
    return 0


def cmd_stats(args) -> int:
    rows = list_pdfs(args.pdf_dir)
    done = miss = 0
    for r in rows:
        cache = CACHE_DIR / f"{r['slug']}.jsonl"
        if cache.exists():
            done += 1
        else:
            miss += 1
            print(f"  缺：{r['name']}")
    print(f"已缓存 {done} 册；未缓存 {miss} 册；目录 {CACHE_DIR}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="执业医师真题扫描册 OCR（RapidOCR 本地离线）")
    ap.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan", help="列出待处理 PDF")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("run", help="执行 OCR（断点续跑）")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    p.add_argument("--force", action="store_true")
    p.add_argument("--only", default="")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("stats", help="缓存完成度")
    p.set_defaults(func=cmd_stats)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
