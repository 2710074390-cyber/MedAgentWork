#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clean_produce_markup.py — 清理交付物中的"流程残留"（2026-08-22）

背景：MedReview 分批生成时会把「📦 复习资料批次 X/Y」「✅ 批次完成」「👉 下一批」
「V1-V13 自检报告」等流程性文本写进最终 MD；站点预览/下载/HTML 版会原样显示。
本脚本将其从交付物中清除，并把押题卷副标题里的「统一模板 v1.1-TEST」等
内部版本号替换为成品文案。

规则（docs/产物格式规范.md）：
  - 押题卷交付物 = 仅 HTML（副标题不得含 TEST/内部版本号）
  - 复习资料交付物 = MD（无流程标记）+ HTML（同）
  - 题库交付物 = MD + HTML（PDF 一律人工上传，管线不生产）

用法：python scripts/clean_produce_markup.py [--dry-run]
"""
import io
import re
import sys
import shutil
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
REVIEW_DIR = ROOT / "大三下" / "复习资料"
QUIZ_DIR = ROOT / "大三下" / "押题卷"
BACKUP_DIR = ROOT / "archive" / "交付物清理前备份_20260822"

# ---- MD 逐行删除模式（流程残留行） ----
MD_LINE_PATTERNS = [
    r"复习资料批次",
    r"批次\s*\d+/\d+\s*完成",
    r"本批产出",
    r"本批统计",
    r"产出Callout",
    r"产出D2",
    r"考点数：",
    r"Callout 本批统计",
    r"Details open 本批统计",
    r"下一批",
    r"预计约\s*\d+\s*页",
    r"请输入「继续」",
    r"无需重复",
]
MD_LINE_RE = re.compile("|".join(MD_LINE_PATTERNS))

# ---- MD 整段删除：V1-V13 自检报告（标题行起到文件尾；附录一二三在其之前，安全） ----
# 兼容标题变体：V1-V13 视觉质量自检报告 / 视觉质量自检报告（V1-V13） / ## 📊 V1-V13 视觉质量自检清单 / ## v5 自检报告（V1-V13） 等
# 注意：标题形如 "V1-V13"（dash 后还有 V13），连字符显式用 \u 转义（- / en-dash / em-dash）
MD_SELFCHECK_RE = re.compile(
    "^#{1,3}\\s*[^\\n]*V\\s*1\\s*[-\u2013\u2014]\\s*V?\\s*1\\s*3[^\\n]*$",
    re.M,
)


def clean_md(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    before = len(text)
    lines = text.split("\n")
    kept = [ln for ln in lines if not MD_LINE_RE.search(ln)]
    text = "\n".join(kept)
    m = MD_SELFCHECK_RE.search(text)
    if m:
        text = text[: m.start()].rstrip() + "\n"
    # 清理文件首部孤立的 ---（批次标记被删后的残留分隔线）与随之的空行
    text = re.sub(r"^(?:-{3,}\s*\n)+", "", text)
    text = re.sub(r"^(?:-{3,}\s*\n)+\s*\n?", "", text)
    # 清理连排的 ---（流程标记删除后可能留下多余分隔线，压缩为单条）
    text = re.sub(r"(?:\n-{3,}\s*){2,}", "\n\n---\n\n", text)
    path.write_text(text, encoding="utf-8")
    return before - len(text)

# ---- HTML 行级删除：批次标记行 ----
HTML_LINE_PATTERNS = [
    r"复习资料批次",
    r"批次\s*\d+/\d+\s*完成",
    r"以下自检基于",
    r"下一批",
    r"本批产出",
    r"视觉质量自检 V1-V13",
    r'href="#v1-v13',  # 指向已清理自检段的侧栏链接
]
HTML_LINE_RE = re.compile("|".join(HTML_LINE_PATTERNS))


def clean_html(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    before = len(text)
    lines = text.split("\n")
    keep = []
    skip_block = False  # V1-V13 段：从 id="v1-v13 的 h2 起，到 </main> 前结束
    for ln in lines:
        if re.search(r'id="v1-v13', ln):
            skip_block = True
            continue
        if skip_block:
            if "</main>" in ln:
                skip_block = False
                keep.append(ln)
            continue
        if HTML_LINE_RE.search(ln):
            continue
        keep.append(ln)
    text = "\n".join(keep)
    path.write_text(text, encoding="utf-8")
    return before - len(text)


def clean_quiz(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    before = len(text)
    # 副标题："统一模板 v1.1-TEST · 90 题 …" → "按考频组卷 · 90 题 …"（保留后续题数等）
    bank_sub = "\u6309\u8003\u9891\u7ec4\u5377 \u00b7 "  # 按考频组卷 ·
    text = re.sub(
        '("sub"\\s*:\\s*")[^"]*?\\u7edf\\u4e00\\u6a21\\u677f v[0-9.]+(?:-?TEST)?\\s*\\u00b7\\s*',
        lambda m: m.group(1) + bank_sub,
        text,
    )
    path.write_text(text, encoding="utf-8")
    return before - len(text)


def main():
    dry = "--dry-run" in sys.argv
    changed = []
    if not dry:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # 1) 复习资料 MD
    for md in sorted(REVIEW_DIR.glob("*.md")):
        text0 = md.read_text(encoding="utf-8")
        need = (MD_LINE_RE.search(text0) or MD_SELFCHECK_RE.search(text0)
                or re.match(r"^(?:-{3,}\s*\n)+", text0))
        if dry:
            if need:
                changed.append(f"MD {md.name}（命中流程标记/首部分隔线）")
            continue
        if not need:
            continue
        shutil.copy2(md, BACKUP_DIR / md.name)
        delta = clean_md(md)
        changed.append(f"MD {md.name}（-{delta} 字节）")

    # 2) 复习资料 HTML
    for html in sorted(REVIEW_DIR.glob("*.html")):
        text = html.read_text(encoding="utf-8")
        if not (HTML_LINE_RE.search(text) or 'id="v1-v13' in text):
            continue
        if dry:
            changed.append(f"HTML {html.name}（命中流程标记）")
            continue
        shutil.copy2(html, BACKUP_DIR / html.name)
        delta = clean_html(html)
        changed.append(f"HTML {html.name}（-{delta} 字节）")

    # 3) 押题卷副标题
    for q in sorted(QUIZ_DIR.glob("*.html")):
        text = q.read_text(encoding="utf-8")
        if "统一模板 v" not in text:
            continue
        if dry:
            changed.append(f"QUIZ {q.name}（存在内部版本号副标题）")
            continue
        shutil.copy2(q, BACKUP_DIR / q.name)
        delta = clean_quiz(q)
        changed.append(f"QUIZ {q.name}（-{delta} 字节，副标题已成品化）")

    print("=== 清理结果 ===")
    for c in changed:
        print("  •", c)
    if not changed:
        print("  （无可清理项）")
    if not dry:
        print(f"\n备份目录：{BACKUP_DIR}")
    else:
        print("\n（--dry-run 模式，未写入）")


if __name__ == "__main__":
    main()
