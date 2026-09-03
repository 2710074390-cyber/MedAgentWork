#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diagnose_review_md.py — 检查复习资料 MD 的渲染健康度

检查项:
  1. 代码围栏 ``` 是否配对
  2. <details open> 与 </details> 是否配对（旧格式；v1.1 起新产物禁用，见底部 ⚠️ 提示）
  3. <summary> 是否闭合
  4. 每张表格各行列数是否一致（列数不一致会破坏渲染器表格解析）
  5. Callout 行 (> [!XX]) 是否以 "> " 前缀延续（内部空行必须以 > 开头的规则）
  6. 未闭合的粗体 ** 数量；<b>/</b> 与 <i>/</i> 配对（v5.2 新语法）
  7. 是否有 Mermaid / 其他 HTML 标签 / YAML 头
  8. 表格分隔行 (|---|) 是否有对应表头
  9. 展开区 `#### 🔬 展开：` 计数（v1.1 起替代 details 折叠区）
（details/`**` 为 v1.0 旧语法：出现时仅打印 ⚠️ 提示，不判 FAIL——旧产物仍兼容渲染）
用法: python scripts/diagnose_review_md.py <md路径>
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def diagnose(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    problems = []

    # 1. 代码围栏
    fences = [i for i, ln in enumerate(lines) if ln.strip().startswith("```")]
    if len(fences) % 2 != 0:
        problems.append(f"[围栏] ``` 出现 {len(fences)} 次（奇数！未闭合，最后一个 fence 行 {fences[-1]+1}）")
    else:
        for i in range(0, len(fences), 2):
            if (lines[fences[i]].strip() != "```") and (lines[fences[i+1]].strip() != "```"):
                problems.append(f"[围栏] 第 {fences[i]+1} 行起代码块首尾不是裸 ``` (可能存在 ```text 与裸 ``` 不匹配)")
    # 检查 ```text/```ascii/``` 开尾不一致
    for i in range(0, len(fences), 2):
        open_line = lines[fences[i]].strip()
        close_idx = fences[i+1] if i + 1 < len(fences) else None
        if close_idx is None:
            continue
        close_line = lines[close_idx].strip()
        if open_line.startswith("```") and open_line != "```":
            if close_line != "```":
                problems.append(f"[围栏] 第 {fences[i]+1} 行开 {open_line!r} 但第 {fences[i+1]+1} 行闭 {close_line!r}")

    # 2. details 配对（统计前先剔除行内代码，如 "`<details open>`" 教学说明不算标签）
    code_free = re.sub(r"`[^`]*`", "", text)
    d_open = code_free.count("<details open>")
    d_close = code_free.count("</details>")
    if d_open != d_close:
        problems.append(f"[details] open={d_open} close={d_close}（不配对）")
    s_open = code_free.count("<summary>")
    s_close = code_free.count("</summary>")
    if s_open != s_close:
        problems.append(f"[summary] open={s_open} close={s_close}（不配对）")
    # details 内容行若含裸 <details>（无 open）
    bare = re.findall(r"<details(?![^>]*open)[^>]*>", code_free)
    if bare:
        problems.append(f"[details] 发现裸 <details>{len(bare)} 个（缺 open）")

    # 3. 表格一致性（相邻行构成表格）
    tbl_pattern = re.compile(r"^\s*\|.*\|\s*$")
    i = 0
    while i < len(lines):
        if tbl_pattern.match(lines[i]):
            # 收集表格块
            block = []
            while i < len(lines) and tbl_pattern.match(lines[i]):
                block.append(lines[i])
                i += 1
            cols = [ln.count("|") - 1 for ln in block if not re.match(r"^\s*\|[\s:\-|]+\|\s*$", ln)]
            ncols = set(cols)
            if len(ncols) > 1:
                problems.append(f"[表格] 第 {block[0][:30]}… 行 {len(block)} 行列数不一致 {sorted(ncols)}")
            # 分隔行必须存在且位于第2行
            if len(block) >= 2:
                if not re.match(r"^\s*\|[\s:\-|]+\|\s*$", block[1]):
                    problems.append(f"[表格] 第 {len(block)} 行表格缺少分隔行（首行 {block[0][:30]}）")
        else:
            i += 1

    # 4. Callout 检查：> [!XX] 后续行若为空行则必须结束；callout 内出现非 > 且非空行 → 破坏
    # 简化: 检查 "> [!WARNING]" 等后除非 callout 样式>线, 否则用裸文本的段落会中断
    callout_re = re.compile(r"^> \[!(WARNING|TIP|INFO|SUCCESS|NOTE)\]", re.M)
    ct = len(callout_re.findall(text))
    # callout 行内嵌 ``` 的检查
    callout_fence = re.findall(r"^>!\s*$", text, re.M)

    # 5. 粗体配对（v5.2：<b>/</b> 与 <i>/</i>；** 为 v1.0 旧语法仅提示）
    bolds = re.findall(r"(?<!\*)\*\*(?!\*)(.+?)(?<!\*)\*\*(?!\*)", text, re.S)
    star = text.count("**")
    if star % 2 != 0:
        problems.append(f"[粗体] ** 共 {star} 个（奇数，存在未闭合粗体或干扰表格阴影）")
    elif star > 0:
        print(f"  ⚠️ 旧格式 ** 强调 {star // 2} 处（v5.2 起新产物禁用，应改 <b>/<i>）")
    b_open = text.count("<b>"); b_close = text.count("</b>")
    i_open = text.count("<i>"); i_close = text.count("</i>")
    if b_open != b_close:
        problems.append(f"[粗体] <b> {b_open} 个 / </b> {b_close} 个（不配对）")
    if i_open != i_close:
        problems.append(f"[斜体] <i> {i_open} 个 / </i> {i_close} 个（不配对）")

    # 6. 禁用项
    head = text[:2000]
    yaml_head = re.match(r"^---\s*\n[^\n]*\n---\s*$", text, re.M) or re.match(r"^---\s*$", head, re.M) and (
        re.search(r"^---\s*$", text[100:], re.M)
    )
    for pat, desc in [
        (r"(?i)mermaid", "Mermaid"),
        (r"<div|<span|<table|<br|<img|<a\s", "禁用 HTML"),
        (r"- \[[ x]\]", "任务列表"),
    ]:
        c = len(re.findall(pat, text, re.S | re.M))
        if c:
            problems.append(f"[禁用] {desc} 出现 {c} 处")
    # YAML front matter 仅在文件真正的开头（前 2000 字符内连续两行 ---）
    if yaml_head:
        problems.append("[禁用] 疑似 YAML front matter（文件开头 --- 对）")

    # 7. 序号起点检查（主动回忆区以 1. 开头即可）
    bad_num = re.findall(r"(?m)^(?!\s?\d+\.\s|#|>|\||-|\*|```|\s*$)\d+\.\s", text)
    if bad_num:
        problems.append(f"[序号] 疑似列表序号异常 {len(bad_num)} 处")

    print(f"== {path.name} ==")
    expand = len(re.findall(r"^####\s+(?:🔬\s*)?展开：", text, re.M))
    print(f"行数 {len(lines)} | callout {ct} | 围栏组 {len(fences)//2} | 展开区 {expand} | details(旧) {d_open} 对")
    if problems:
        print(f"发现 {len(problems)} 个问题:")
        for p in problems:
            print("  ⚠️", p)
        return 1
    print("✅ 未发现结构性渲染问题")
    return 0

if __name__ == "__main__":
    for a in sys.argv[1:]:
        diagnose(Path(a))
