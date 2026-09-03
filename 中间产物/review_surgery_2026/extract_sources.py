#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外科学复习资料素材提取器：从 RAG chunk 元数据 JSONL 中按关键词/章节/页码过滤。

用法示例：
  python extract_sources.py --subject surgery --keywords "食管癌,贲门失弛缓" --max 40
  python extract_sources.py --subject heyincheng-jy3 --keywords "股骨颈骨折,骨盆骨折" --max 30
  python extract_sources.py --subject surgery --chapter "第二十九章" --max 60
  python extract_sources.py --subject surgery --keywords "张力性气胸" --page-range 257-270

说明：
  - subject 取值：surgery（外科学第10版教材）/ heyincheng-jy1|jy2|jy3（贺银成讲义上中下册）
                  / surgery-exercise（外科学学习指导与习题集，可选）
  - 输出格式：`[PAGE 页码 | CH 章节 | idx 块#]` + 文本
  - 贺银成讲义无页码（page_number=0），按块#引用
  - 期刊目录页特征：chapter 字段以 `....` 结尾（或含大量点）→ 默认过滤，--toc 可保留
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "知识库素材", "chunks_metadata")

FILES = {
    "surgery": "surgery_chunks.jsonl",
    "heyincheng-jy1": "heyincheng-jy1_chunks.jsonl",
    "heyincheng-jy2": "heyincheng-jy2_chunks.jsonl",
    "heyincheng-jy3": "heyincheng-jy3_chunks.jsonl",
    "surgery-exercise": "surgery-exercise_chunks.jsonl",
}


def is_toc(chapter: str) -> bool:
    if not chapter:
        return False
    dots = chapter.count(".")
    return dots >= 3 or "\u3000" + "...." in chapter.replace(" ", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True, choices=list(FILES))
    ap.add_argument("--keywords", default="", help="逗号分隔关键词；任一命中即选（--all-kw 可改为全部命中）")
    ap.add_argument("--all-kw", action="store_true", help="全部关键词都命中才选")
    ap.add_argument("--chapter", default="", help="章节名子串过滤，如 第二十九章")
    ap.add_argument("--page-range", default="", help="页码区间 a-b")
    ap.add_argument("--max", type=int, default=25, help="最多输出条数")
    ap.add_argument("--full", action="store_true", help="输出完整文本（默认截断 600 字）")
    ap.add_argument("--toc", action="store_true", help="不过滤目录页")
    args = ap.parse_args()

    path = os.path.join(BASE, FILES[args.subject])
    if not os.path.exists(path):
        print(f"ERROR: 找不到 {path}", file=sys.stderr)
        sys.exit(1)

    kws = [k.strip() for k in args.keywords.split(",") if k.strip()]
    pmin, pmax = 0, 10 ** 9
    if args.page_range:
        try:
            a, b = args.page_range.split("-")
            pmin, pmax = int(a), int(b)
        except ValueError:
            print("ERROR: --page-range 格式应为 a-b", file=sys.stderr)
            sys.exit(1)

    hits, shown = 0, 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not args.toc and is_toc(d.get("chapter", "")):
                continue
            if args.chapter and args.chapter not in (d.get("chapter") or ""):
                continue
            pg = d.get("page_number") or 0
            if pg < pmin or pg > pmax:
                continue
            text = d.get("text") or ""
            if kws:
                hit = [k for k in kws if k in text]
                if args.all_kw and len(hit) != len(kws):
                    continue
                if not args.all_kw and not hit:
                    continue
            hits += 1
            if shown >= args.max:
                continue
            shown += 1
            ch = (d.get("chapter") or "").replace("\u2003", " ").replace("\u2002", " ").strip()[:40]
            out = text if args.full else text[:600]
            print(f"[PAGE {pg} | CH {ch} | #{d.get('chunk_index', '')}]")
            print(out)
            print("-" * 80)
    print(f"# 匹配 {hits} 条；展示 {shown} 条。限制用 --max 调整。")


if __name__ == "__main__":
    main()
