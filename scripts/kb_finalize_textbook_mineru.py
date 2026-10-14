#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MedAgentWork — MinerU 教材产物规范化（入库收口）

把 `知识库素材/解剖学/_mineru_raw/<书>/<超长PDF名>/txt/...` 规范为
`知识库素材/解剖学/<书名>_mineru/`，并瘦身（保留 markdown / images / content_list / middle，删除可视化大件）。

用法：
  python scripts/kb_finalize_textbook_mineru.py            # 规范化 + 瘦身
  python scripts/kb_finalize_textbook_mineru.py --dry-run  # 只打印计划
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "知识库素材" / "解剖学"
RAW = KB / "_mineru_raw"

# 保留的后缀；其余大件（可视化 PDF、model.json）删除以瘦身
KEEP_SUFFIX = {".md", ".json", ".jpg", ".jpeg", ".png", ".webp"}
DROP_NAME_PARTS = ("_layout.pdf", "_span.pdf", "_origin.pdf", "_model.json")


def human_mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f}MB"


def plan_for(book_dir: Path) -> tuple[Path, Path, list[Path], int]:
    """返回 (源 txt 目录, 目标目录, 待删文件, 删除体积)"""
    inner = [p for p in book_dir.iterdir() if p.is_dir()]
    if not inner:
        raise SystemExit(f"{book_dir} 下没有 MinerU 输出子目录")
    src_root = inner[0]
    txt = src_root / "txt" if (src_root / "txt").is_dir() else src_root
    dst = KB / f"{book_dir.name}_mineru"
    drops, size = [], 0
    for p in txt.rglob("*"):
        if p.is_file() and any(part in p.name for part in DROP_NAME_PARTS):
            drops.append(p)
            size += p.stat().st_size
    return txt, dst, drops, size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-heavy", action="store_true", help="保留 layout/span/origin PDF 与 model.json")
    args = ap.parse_args()

    if not RAW.exists():
        print(f"未找到 {RAW}")
        return 1
    total_drop = 0
    for book_dir in sorted(p for p in RAW.iterdir() if p.is_dir()):
        try:
            txt, dst, drops, size = plan_for(book_dir)
        except SystemExit as e:
            print(e)
            continue
        figs = list((txt / "images").glob("*")) if (txt / "images").is_dir() else []
        mds = list(txt.glob("*.md"))
        print(f"\n=== {book_dir.name} ===")
        print(f"  源：{txt}")
        print(f"  目标：{dst}")
        print(f"  markdown {len(mds)} 个 ｜ 插图 {len(figs)} 张 ｜ 待删大件 {len(drops)} 个（{human_mb(size)}）")
        if args.dry_run:
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(txt, dst)
        if not args.keep_heavy:
            for p in dst.rglob("*"):
                if p.is_file() and any(part in p.name for part in DROP_NAME_PARTS):
                    p.unlink()
            total_drop += size
        print(f"  ✓ 已入库：{dst}")
    if not args.dry_run:
        print(f"\n瘦身合计释放 {human_mb(total_drop)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
