#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_review_shards.py — 复习资料分片合并器（HC-26 配套 · 2026-10-27）

把分模块生成的复习资料（head + M01…Mnn + appendix + 自测答案）合并成**单一交付文件**，
并在写盘前校验合并结果的完整性，避免"模块生成完散着交付"。

用法:
  python scripts/merge_review_shards.py \
    --shards 中间产物/batch043/bpa_v6 \
    --appendix 中间产物/batch043/bpa/appendix.md \
    --out 复习资料/急诊与灾难医学教师重点版/急诊与灾难医学教师重点版_主复习资料.md

约定:
  --shards/head.md          可选，总纲（标题、使用指南、蓝图）
  --shards/M01.md … Mnn.md  必填，模块正文，标题须为 `## 模块N：…`
  --shards/answers/M01.md…  可选，`| 题 | 答案 | 卡片 |` 表格行，按模块并入附录五
  --appendix                可选，原附录；若含「附录五」，用 answers 重建该节
"""
import argparse
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODULE_HEAD_RE = re.compile(r"^## 模块(\d+)：", re.M)
CARD_RE = re.compile(r"^####\s*[🔴🟡🟢].*?K-M\d{2}-\d{3}", re.M)
APPENDIX5 = "## 附录五"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def build_appendix(appendix: Path | None, answers_dir: Path | None) -> str:
    if not appendix or not appendix.exists():
        return ""
    text = read(appendix)
    if not answers_dir or not answers_dir.exists():
        return text
    parts = text.split(APPENDIX5)[0].rstrip()
    # 交付文件只能有一个一级标题：附录父标题降级为分隔线
    parts = "\n".join(line for line in parts.splitlines() if line.strip() != "# 附录").rstrip()
    rows = [APPENDIX5 + "：主动回忆答案", "",
            "> 与各卡 `<b>🔄 自测</b>` 一一对应：序号＝卡内小问顺序，答案逐条作答。", ""]
    for f in sorted(answers_dir.glob("M[0-9][0-9].md")):
        mid = f.stem
        rows += [f"### {mid}", "", "| 题 | 答案 | 卡片 |", "|---|---|---|"]
        rows += read(f).strip().splitlines()
        rows.append("")
    return parts + "\n\n" + "\n".join(rows).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="合并复习资料分片为单一交付文件")
    ap.add_argument("--shards", required=True, help="分片目录（含 head.md 可选、M01.md…）")
    ap.add_argument("--appendix", help="原附录 MD（含页码索引/术语/口诀/数字锚）")
    ap.add_argument("--answers", help="自测答案目录（默认 <shards>/answers）")
    ap.add_argument("--out", required=True, help="合并后的交付文件")
    ap.add_argument("--expect-modules", type=int, help="期望模块数；缺省按分片文件数推断")
    args = ap.parse_args()

    shards = Path(args.shards)
    modules = sorted(shards.glob("M[0-9][0-9].md"))
    if not modules:
        print(f"✗ {shards} 下没有 Mnn.md 分片", file=sys.stderr)
        return 1

    parts = []
    head = shards / "head.md"
    if head.exists():
        parts.append(read(head).rstrip() + "\n")
    for m in modules:
        text = read(m).strip()
        if not MODULE_HEAD_RE.search(text):
            print(f"✗ {m.name} 缺少 `## 模块N：` 标题", file=sys.stderr)
            return 1
        parts.append(text + "\n")
    appendix = build_appendix(Path(args.appendix) if args.appendix else None,
                              Path(args.answers) if args.answers else shards / "answers")
    if appendix:
        parts.append(appendix.rstrip() + "\n")

    merged = "\n".join(parts)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(merged, encoding="utf-8")

    # 合并完整性校验：写盘后立刻核验，不合格即失败
    expect = args.expect_modules or len(modules)
    problems = []
    h1 = len(re.findall(r"^# .+$", merged, re.M))
    found = len(MODULE_HEAD_RE.findall(merged))
    cards = len(CARD_RE.findall(merged))
    if h1 != 1:
        problems.append(f"一级标题 {h1} 个（应为 1）")
    if found != expect:
        problems.append(f"模块 {found} 个（应为 {expect}）")
    if cards == 0:
        problems.append("未解析到考点卡")
    if appendix and merged.count(APPENDIX5) != 1:
        problems.append(f"附录五出现 {merged.count(APPENDIX5)} 次（应为 1）")
    if problems:
        print("✗ 合并结果不合格：" + "；".join(problems), file=sys.stderr)
        return 1
    print(f"✓ 合并完成：{out}")
    print(f"  模块 {found}｜卡片 {cards}｜字符 {len(merged)}｜行 {merged.count(chr(10)) + 1}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
