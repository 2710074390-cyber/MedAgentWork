# -*- coding: utf-8 -*-
"""回归防护（契约 E4 / 自检 V16）：obsidian-print snippet 必须保留「导出保真」打印规则。

背景（2026-10-15 事故）：
    复习资料的强调一律写在 HTML `<b>`（契约 E1 禁用 `**`）。而 `@media print` 把正文
    强制成**无真粗体字面的宋体系**（SimSun/宋体），Chromium 打印不渲染内联加粗
    → 用户导出 PDF 后「加粗全部消失」；彩色 emoji（🔴🟡🟢）也受打印 economy 模式影响。
修复：`scripts/obsidian-snippets/medagentwork-print.css` 的 `@media print` §7.0。
本测试防止该修复被日后改动无声回退（改坏了这里必须红）。
"""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "scripts" / "obsidian-snippets" / "medagentwork-print.css"


def _print_section() -> str:
    """返回文档中第一个真正的 `@media print { ... }`（花括号配平）整块，即 §7 打印段。"""
    text = CSS.read_text(encoding="utf-8")
    m = re.search(r"@media\s+print\s*\{", text)
    assert m, "medagentwork-print.css 缺少 @media print { ... } 块"
    start = m.start()
    depth = 0
    for j in range(m.end() - 1, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
    raise AssertionError("@media print 块未闭合")


def test_snippet_file_exists():
    assert CSS.exists(), "缺少 CSS snippet 源文件：%s" % CSS


def test_bold_hardened_in_print():
    """E4 核心：内联 <b>/<strong> 在打印时必须落到有真粗体字面的字体 + 显式 700。"""
    sec = _print_section()
    assert re.search(r"b\s*,\s*strong", sec), "打印段缺 `b, strong` 选择器"
    assert re.search(r"font-weight\s*:\s*700\s*!important", sec), "打印段缺 `font-weight: 700 !important`（E4）"
    assert re.search(r"Microsoft YaHei|Noto Sans CJK SC|Source Han Sans|PingFang SC", sec), \
        "加粗未指定有真粗体字面的字体（雅黑/思源黑等）"


def test_color_exact_in_print():
    """彩色 emoji（🔴🟡🟢）与底色：打印须 print-color-adjust: exact。"""
    sec = _print_section()
    assert re.search(r"print-color-adjust\s*:\s*exact", sec), "缺 `print-color-adjust: exact`"
    assert re.search(r"-webkit-print-color-adjust\s*:\s*exact", sec), "缺 `-webkit-print-color-adjust: exact`"


def test_emoji_font_in_print_stack():
    """打印字体栈末尾必须有 emoji 字体兜底。"""
    sec = _print_section()
    assert "Segoe UI Emoji" in sec, "打印字体栈缺 emoji 字体（Segoe UI Emoji）"
