#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_produce_rules.py — 产物形态门禁（2026-08-22）

按 docs/产物格式规范.md 校验交付目录与押题卷模板：
  1. 扩展名白名单：押题卷=仅 .html；题库=仅 .md/.html/.pdf；复习资料=仅 .md/.html
  2. 押题卷：PAPER_META.sub 无「统一模板/TEST/v1.x」；QUESTIONS 字段契约（options 纯数组）
  3. 复习资料 MD：无批次/流程标记残留；无 Mermaid；无 YAML front matter
  4. 复习资料 HTML：无批次标记残留
  5. PDF 来源断言（2026-09-28 新增）：`大三下/` + `大四上/` 下每个 PDF 必须
     ① ≤ 25 MiB（Cloudflare Pages 单文件上限）
     ② /Creator 不含 HeadlessChrome（脚本无头打印指纹，规范 §5.6 禁止脚本生成 PDF）
     背景：2026-09-12 脚本打印件覆盖了用户 09-01 的人工导出版，而当时门禁只覆盖
     `大三下/`、且对 PDF 的检查恒为 True，所以没拦住。
用法：python scripts/verify_produce_rules.py   → 全量检查，FAIL==0 时 exit 0
"""
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "大三下"
# 2026-09-28：大四上分区此前完全不在门禁范围内（SITE 只指 大三下），
# 于是 export_review_pdfs.py 生成的 Chrome 无头打印件能直接进站并覆盖人工导出版。
SITE_ROOTS = [SITE, ROOT / "大四上"]

ALLOWED = {
    "押题卷": {".html"},
    "题库": {".md", ".html", ".pdf"},
    "复习资料": {".md", ".html"},
}
S1_ALLOWED = {".pdf", ".md", ".html"}      # 大四上分区（复习资料/题库）
PDF_NOTE = "题库/复习资料 PDF 由用户人工上传（管线不生产，本校验仅提示）"

# ---------- PDF 来源断言（2026-09-28）----------
# 规范 §5.6：PDF 一律人工导出上传，脚本不得生成。但「人工导出」本身也是
# Chromium 的 printToPDF（Chrome 打印对话框、Obsidian 内置导出都是），
# 所以不能靠 /Producer=Skia/PDF 区分 —— 那会把人工导出的也一起毙掉。
# 可区分的指纹在 /Creator：
#   人工（Chrome 打印对话框 / Obsidian 内置导出）：Chromium
#   脚本（chrome --headless=new --print-to-pdf）：Mozilla/5.0 (…) HeadlessChrome/149.0.0.0 Safari/537.36
SCRIPT_PRINT_RE = re.compile(rb"HeadlessChrome|HeadlessShell", re.I)
PDF_SIZE_LIMIT = 25 * 1024 * 1024          # Cloudflare Pages 单文件硬上限 25 MiB

BANNED_SUB = re.compile(r"统一模板|TEST|v\d+\.\d")
BANNED_MD = re.compile(r"复习资料批次|批次\s*\d+/\d+\s*完成|本批产出|本批统计|下一批"
                       r"|V1-V\d+\s*视觉质量|视觉质量自检报告|视觉质量自检清单|全量自检")
BANNED_HTML = re.compile(r"复习资料批次|下一批|本批产出")
MERMAID = re.compile(r"```mermaid")
FRONTMATTER = re.compile(r"^\s*---\s*$")
# v1.1 复习资料 MD 标签白名单：仅允许 <b>/<i>；<details>/<summary> 为 v1.0 旧写法（仅提示）
REVIEW_TAG_ALLOW = {"b", "i"}
REVIEW_TAG_LEGACY = {"details", "summary"}

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
        for f in sorted(d.glob("*")):
            if f.is_dir():
                continue
            if f.suffix.lower() not in exts:
                bad.append(f.name)
        check(f"扩展名白名单 · {sub}（{len(exts)} 类）", not bad, "违规: " + ",".join(bad) if bad else "")

    # 1b) 大四上分区（2026-09-28 起纳入门禁）
    s1 = ROOT / "大四上"
    if s1.exists():
        for sub in ("复习资料", "题库"):
            d = s1 / sub
            if not d.exists():
                check(f"目录存在 · 大四上/{sub}", False, "缺失")
                continue
            bad = [f.name for f in sorted(d.glob("*"))
                   if not f.is_dir() and f.suffix.lower() not in S1_ALLOWED]
            check(f"扩展名白名单 · 大四上/{sub}（{len(S1_ALLOWED)} 类）",
                  not bad, "违规: " + ",".join(bad) if bad else "")

    # 1c) PDF 来源断言：站点目录下所有 PDF（递归）
    pdfs = []
    for root in SITE_ROOTS:
        if root.exists():
            pdfs += [p for p in sorted(root.rglob("*.pdf")) if p.is_file()]
    if not pdfs:
        # 抽不到目标 = 门禁失效，不能当成"通过"
        check("PDF 来源断言 · 扫到 PDF", False,
              "站点目录下一个 PDF 都没扫到 —— 路径约定可能已变，门禁失效")
    for p in pdfs:
        rel = p.relative_to(ROOT).as_posix()
        size = p.stat().st_size
        issues = []
        if size > PDF_SIZE_LIMIT:
            issues.append(f"{size/1048576:.2f} MiB 超 Cloudflare Pages 25 MiB 单文件上限")
        data = p.read_bytes()
        m = re.search(rb"/Creator\s*\(([^)]{0,200})\)", data)
        creator = m.group(1).decode("latin1", "replace") if m else ""
        if SCRIPT_PRINT_RE.search(data):
            issues.append("Creator 含 HeadlessChrome —— 脚本无头打印产物，规范 §5.6 禁止")
        check(f"PDF 来源 · {rel}", not issues,
              "; ".join(issues) if issues else f"{size/1048576:.2f} MiB · Creator={creator[:38]}")

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
            # v1.1 标签白名单：仅 <b>/<i>；其余（除旧 details/summary 外）判 FAIL
            tags = re.findall(r"</?([a-zA-Z][a-zA-Z0-9-]*)[^>]*>", t)
            bad = sorted({x.lower() for x in tags if x.lower() not in REVIEW_TAG_ALLOW})
            if bad:
                others = [x for x in bad if x not in REVIEW_TAG_LEGACY]
                legacy = [x for x in bad if x in REVIEW_TAG_LEGACY]
                if others:
                    issues.append("非白名单 HTML 标签（仅允许 <b>/<i>）: " + ",".join(others[:6]))
                if legacy:
                    print(f"  ⚠️ {f.name}: 旧格式折叠区 {legacy}（产物契约 v1.1 起新产物禁用，旧产物仅提示）")
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
