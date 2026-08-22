#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_produce_rules.py — 产物形态门禁（2026-08-22）

按 docs/产物格式规范.md 校验 `大三下/` 交付目录与押题卷模板：
  1. 扩展名白名单：押题卷=仅 .html；题库=仅 .md/.html/.pdf；复习资料=仅 .md/.html
  2. 押题卷：PAPER_META.sub 无「统一模板/TEST/v1.x」；QUESTIONS 字段契约（options 纯数组）
  3. 复习资料 MD：无批次/流程标记残留；无 Mermaid；无 YAML front matter
  4. 复习资料 HTML：无批次标记残留
  5. 题库：允许 .pdf 但打「人工上传」提示（管线不生产）
用法：python scripts/verify_produce_rules.py   → 全量检查，FAIL==0 时 exit 0
"""
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "大三下"

ALLOWED = {
    "押题卷": {".html"},
    "题库": {".md", ".html", ".pdf"},
    "复习资料": {".md", ".html"},
}
PDF_NOTE = "题库/复习资料 PDF 由用户人工上传（管线不生产，本校验仅提示）"

BANNED_SUB = re.compile(r"统一模板|TEST|v\d+\.\d")
BANNED_MD = re.compile(r"复习资料批次|批次\s*\d+/\d+\s*完成|本批产出|本批统计|下一批"
                       r"|V1-V13\s*视觉质量|视觉质量自检报告|视觉质量自检清单|全量自检")
BANNED_HTML = re.compile(r"复习资料批次|下一批|本批产出")
MERMAID = re.compile(r"```mermaid")
FRONTMATTER = re.compile(r"^\s*---\s*$")

rules = []


def check(name, ok, detail=""):
    rules.append((name, ok, detail))
    print(("  ✅ " if ok else "  ❌ ") + name + (f" ｜ {detail}" if detail else ""))


def main():
    print("=== 产物形态门禁 verify_produce_rules.py ===")

    # 1) 扩展名白名单 + PDF 提示
    for sub, exts in ALLOWED.items():
        d = SITE / sub
        if not d.exists():
            check(f"目录存在 · {sub}", False, "缺失")
            continue
        bad = []
        pdfs = []
        for f in sorted(d.glob("*")):
            if f.is_dir():
                continue
            if f.suffix.lower() not in exts:
                bad.append(f.name)
            if f.suffix.lower() == ".pdf":
                pdfs.append(f.name)
        check(f"扩展名白名单 · {sub}（{len(exts)} 类）", not bad, "违规: " + ",".join(bad) if bad else "")
        if pdfs:
            check(f"PDF 人工上传标记 · {sub}", True, f"{len(pdfs)} 个 PDF（人工提供，本机不产）")

    # 2) 押题卷
    quiz = SITE / "押题卷"
    if quiz.exists():
        for f in sorted(quiz.glob("*.html")):
            t = f.read_text(encoding="utf-8")
            issues = []
            m = re.search(r'"sub"\s*:\s*"([^"]+)"', t)
            if m and BANNED_SUB.search(m.group(1)):
                issues.append(f"副标题含内部标记: {m.group(1)}")
            if "const QUESTIONS" not in t:
                issues.append("缺 QUESTIONS 数组")
            if "options" in t and re.search(r'"options"\s*:\s*\[\s*\{', t):
                issues.append("options 为对象数组（应为纯文本数组）")
            check(f"押题卷 · {f.name}", not issues, "; ".join(issues) if issues else
                  (f"sub={m.group(1) if m else '?'}"))

    # 3) 复习资料 MD
    review = SITE / "复习资料"
    if review.exists():
        md_files = sorted(review.glob("*.md"))
        html_files = sorted(review.glob("*.html"))
        for f in md_files:
            t = f.read_text(encoding="utf-8")
            issues = []
            if BANNED_MD.search(t):
                issues.append("流程标记残留")
            if MERMAID.search(t):
                issues.append("Mermaid 代码块（应改 ASCII 图）")
            if t.lstrip().startswith("---") or t.startswith("---"):
                issues.append("文件首部孤立 ---（front matter/残留分隔线）")
            check(f"复习资料 MD · {f.name}", not issues, "; ".join(issues) if issues else "")
        for f in html_files:
            t = f.read_text(encoding="utf-8")
            issues = []
            if BANNED_HTML.search(t):
                issues.append("批次标记残留")
            check(f"复习资料 HTML · {f.name}", not issues, "; ".join(issues) if issues else "")

    # 4) 汇总
    fails = [r for r in rules if not r[1]]
    print(f"\n=== 门禁结果: {len(rules) - len(fails)}/{len(rules)} 通过 · FAIL={len(fails)} ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
