#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MedAgentWork — 教材插图索引构建器（①教材 通道专用）

输入：MinerU 解析产物目录（每本书一个），含 *.md（排版 Markdown，图片以 ![](...) 引用）
      与 images/ 子目录（切分后的插图）。
输出：
  知识库素材/解剖学/教材插图索引/{书名}_image_index.md    —— 人读索引（页号 · 图注 · 尺寸）
  知识库素材/解剖学/教材插图索引/{书名}_image_index.json  —— 机读索引（供取图脚本消费）

用法：
  python scripts/kb_build_textbook_index.py                 # 自动扫描 知识库素材/解剖学/*_mineru
  python scripts/kb_build_textbook_index.py --dir <产物目录> [--dir ...]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "知识库素材" / "解剖学"
OUTDIR = KB / "教材插图索引"

IMG_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)")
CAP_RE = re.compile(r"^\s*(?:图|Fig\.?|Figure)\s*([0-9]+[-–.]?[0-9]*)\s*[:：.]?\s*(.*)$")


def image_size(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as im:
            return im.size
    except Exception:
        return (0, 0)


def scan(book_dir: Path) -> dict:
    md_files = sorted(book_dir.rglob("*.md"))
    figures: list[dict] = []
    for md in md_files:
        lines = md.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines):
            for m in IMG_RE.finditer(line):
                rel = m.group("path").strip()
                if rel.startswith("http"):
                    continue
                f = (md.parent / rel).resolve()
                if not f.exists():
                    f2 = (book_dir / rel.lstrip("./")).resolve()
                    f = f2 if f2.exists() else f
                alt = m.group("alt").strip()
                # 图注：优先读图片后的下一行（MinerU 常把图注单独成行）
                caption = ""
                for j in range(i + 1, min(i + 4, len(lines))):
                    s = lines[j].strip()
                    if not s or IMG_RE.search(s):
                        continue
                    caption = s
                    break
                cap_no = ""
                cm = CAP_RE.match(caption or alt)
                if cm:
                    cap_no = cm.group(1)
                w, h = image_size(f) if f.exists() else (0, 0)
                figures.append({
                    "file": f.name,
                    "rel_path": str(f.relative_to(ROOT)) if f.exists() else rel,
                    "exists": f.exists(),
                    "width": w,
                    "height": h,
                    "caption": caption,
                    "alt": alt,
                    "cap_no": cap_no,
                    "source_md": md.name,
                    "line": i + 1,
                })
    return {
        "book": book_dir.name,
        "engine": "MinerU",
        "md_files": len(md_files),
        "figures": figures,
        "count": len(figures),
    }


def write_index(data: dict) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    stem = data["book"].removesuffix("_mineru")
    (OUTDIR / f"{stem}_image_index.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    figs = [f for f in data["figures"] if f["exists"]]
    color = sum(1 for f in figs if f["width"] >= 600)
    lines = [
        f"# {stem} · 教材插图索引（MinerU 解析产物）",
        "",
        f"> 来源目录：`知识库素材/解剖学/{data['book']}/` ｜ 解析引擎：MinerU ｜ Markdown 文件 {data['md_files']} 个",
        f"> 插图合计 **{data['count']}** 张（其中文件存在 {len(figs)} 张、宽度 ≥600px {color} 张）",
        "> ⚠ 取图纪律：按「图注 + 来源文件」定位后**逐张目视核验**，严禁只按文件名/序号取图（图谱库已有系统性错位教训）。",
        "",
        "| # | 文件名 | 尺寸 | 图注 | 来源 | 行 |",
        "|---|---|---|---|---|---|",
    ]
    for i, f in enumerate(figs, 1):
        cap = (f["caption"] or f["alt"] or "").replace("|", "／")[:60]
        lines.append(f"| {i} | `{f['file']}` | {f['width']}×{f['height']} | {cap} | {f['source_md']} | {f['line']} |")
    (OUTDIR / f"{stem}_image_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  → {OUTDIR / (stem + '_image_index.md')}（{len(figs)} 张）")


def main() -> int:
    ap = argparse.ArgumentParser(description="教材插图索引构建器")
    ap.add_argument("--dir", action="append", default=None, help="MinerU 产物目录（可多次指定）")
    args = ap.parse_args()

    dirs = [Path(d) for d in args.dir] if args.dir else sorted(KB.glob("*_mineru"))
    if not dirs:
        print(f"未找到 MinerU 产物目录（{KB}/*_mineru）。请先运行 mineru 解析。")
        return 1
    for d in dirs:
        if not d.exists():
            print(f"跳过（不存在）：{d}")
            continue
        print(f"扫描：{d}")
        write_index(scan(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
