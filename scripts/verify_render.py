# -*- coding: utf-8 -*-
"""用 markdown-it 渲染真实产出，验证结构是否真的能渲染。

与 check_obsidian.py 的区别：那个做正则结构检查，这个做真实渲染，
能发现「语法看起来对但渲染不出来」的问题（如表格缺分隔行）。
"""
import re
import sys
from pathlib import Path
from markdown_it import MarkdownIt

md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
FM_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.S)


def check(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    body = FM_RE.sub("", text, count=1)
    html = md.render(body)
    # 表格源码出现在 <p> 里 = 没渲染成表格。但要区分两类：
    #   flattened —— 表头/分隔/数据被压进同一行（MinerU 产物，W13 已知问题，非本工具缺陷）
    #   unrendered —— 三行语法完整却没渲染（真缺陷，说明转换或语法有问题）
    flat_paras = re.findall(r"<p>[^<]*\|[^<]*(?:---|:-:)[^<]*\|[^<]*</p>", html)
    flattened = sum(1 for p in flat_paras if len(p) > 400 or p.count("／") >= 3)
    return {
        "file": str(path),
        "tables": html.count("<table>"),
        "unrendered": len(flat_paras) - flattened,
        "flattened": flattened,
        "details_left": html.count("<details"),
        "callouts": len(re.findall(r"^>\s*\[!\w+\][+-]?", body, re.M)),
        "images": html.count("<img"),
        "mermaid": body.count("```mermaid"),
        "h1": len(re.findall(r"^# ", body, re.M)),
        "code_fence_odd": body.count("```") % 2,
    }


samples = sorted(Path(".").glob("Obsidian产物/[!_]*/*.md"))
samples += sorted(Path(".").glob("Obsidian产物/*.md"))

print(f"抽查 {len(samples)} 个文件\n")
tot = {"tables": 0, "unrendered": 0, "flattened": 0, "details_left": 0,
       "callouts": 0, "images": 0, "mermaid": 0}
bad = []
for p in samples:
    if not p.is_file():
        continue
    r = check(p)
    for k in tot:
        tot[k] += r[k]
    # 只有「未渲染」与「围栏奇数」算真缺陷；
    # details_left 在样章里是故意保留的对照项；flattened 是 MinerU 源数据问题
    if r["unrendered"] or r["code_fence_odd"]:
        bad.append((p.name, r["unrendered"], r["code_fence_odd"]))

print(f"{'表格渲染':>10s} {'未渲染':>7s} {'压平':>6s} {'callout':>8s} {'图片':>6s} {'mermaid':>8s}")
print(f"{tot['tables']:>10d} {tot['unrendered']:>7d} {tot['flattened']:>6d} "
      f"{tot['callouts']:>8d} {tot['images']:>6d} {tot['mermaid']:>8d}")
print()
if bad:
    print(f"{len(bad)} 个文件有真缺陷:")
    for name, u, f in bad[:15]:
        print(f"  未渲染表格 {u} / 围栏奇数 {f}  {name[:60]}")
    sys.exit(1)
print("抽查文件渲染结构正常（「压平」属 MinerU 源数据问题，见门禁 W13）")
