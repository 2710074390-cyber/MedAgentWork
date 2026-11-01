# -*- coding: utf-8 -*-
"""md -> business-report HTML（doc-formatter Stage2，v2：design-token 合规版）"""
import re
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(r"C:\Users\38063\Desktop\MedAgentWork\output\patenteval-20261028002753")
SRC = BASE / "stage1" / "final_draft.md"
DST = BASE / "stage2" / "formatted-MedAgentWork与MedKit专利可行性评估.html"

md = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(s: str) -> str:
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r'<code class="ic">\1</code>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s


lines = md.split("\n")
blocks = []
i = 0
while i < len(lines):
    ln = lines[i]
    st = ln.strip()
    if not st:
        i += 1
        continue
    if st.startswith("```"):
        i += 1
        buf = []
        while i < len(lines) and not lines[i].strip().startswith("```"):
            buf.append(lines[i])
            i += 1
        i += 1
        blocks.append(("pre", "\n".join(buf)))
        continue
    if st == "---":
        blocks.append(("hr", ""))
        i += 1
        continue
    m = re.match(r"^(#{1,4})\s+(.*)$", st)
    if m:
        blocks.append(("h%d" % len(m.group(1)), m.group(2)))
        i += 1
        continue
    if st.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()):
        head = [c.strip() for c in st.strip("|").split("|")]
        i += 2
        rows = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
            i += 1
        blocks.append(("table", (head, rows)))
        continue
    if st.startswith(">"):
        buf = []
        while i < len(lines) and lines[i].strip().startswith(">"):
            buf.append(lines[i].strip().lstrip(">").strip())
            i += 1
        blocks.append(("quote", " ".join(buf)))
        continue
    if re.match(r"^[-*]\s+", st):
        buf = []
        while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
            buf.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
            i += 1
        blocks.append(("ul", buf))
        continue
    if re.match(r"^\d+\.\s+", st):
        buf = []
        while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
            buf.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
            i += 1
        blocks.append(("ol", buf))
        continue
    buf = []
    while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,4}\s|\||>|[-*]\s|\d+\.\s|---$|```)", lines[i].strip()):
        buf.append(lines[i].strip())
        i += 1
    blocks.append(("p", " ".join(buf)))

h2_seq = []
n = 0
for kind, payload in blocks:
    if kind == "h2":
        n += 1
        h2_seq.append((n, payload))

TOC = "\n".join(
    '    <li><a href="#section-%d">%s</a></li>' % (num, inline(t)) for num, t in h2_seq
)

out = []
h2_idx = 0
for kind, payload in blocks:
    if kind == "h1":
        continue
    if kind == "h2":
        h2_idx += 1
        out.append('<h2 id="section-%d">%s</h2>' % (h2_idx, inline(payload)))
    elif kind == "h3":
        out.append("<h3>%s</h3>" % inline(payload))
    elif kind == "h4":
        out.append("<h4>%s</h4>" % inline(payload))
    elif kind == "p":
        if payload.startswith("**报告完**"):
            out.append('<p class="end-mark">%s</p>' % inline(payload))
        else:
            out.append("<p>%s</p>" % inline(payload))
    elif kind == "pre":
        out.append("<pre>%s</pre>" % esc(payload))
    elif kind == "hr":
        continue
    elif kind == "quote":
        out.append('<div class="callout"><p>%s</p></div>' % inline(payload))
    elif kind == "ul":
        out.append("<ul>" + "".join("<li>%s</li>" % inline(x) for x in payload) + "</ul>")
    elif kind == "ol":
        out.append("<ol>" + "".join("<li>%s</li>" % inline(x) for x in payload) + "</ol>")
    elif kind == "table":
        head, rows = payload
        th = "".join("<th>%s</th>" % inline(c) for c in head)
        tr = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in rows)
        out.append('<table class="dt"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (th, tr))

BODY = "\n".join(out)

# 摘要块 -> .executive-summary
BODY = BODY.replace('<h2 id="section-1">', '<div class="executive-summary">\n<div class="summary-header"><p class="summary-badge">EXECUTIVE SUMMARY</p></div>\n<h2 id="section-1">', 1)
cut = BODY.find('<h2 id="section-2">')
head = BODY[:cut]
tail = BODY[cut:]
head = head.rstrip() + "\n</div>\n\n"
BODY = head + tail

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="docx-page-size" content="A4">
<title>MedAgentWork 与 MedKit 专利可行性评估与全链路申请方案</title>
<style>
/* 页面规则：正文页脚居中页码，封面与目录页不显示 */
@page { @bottom-center { content: counter(page); } }
@page cover { @bottom-center { content: none; } }
section[role="cover"] { page: cover; }

:root {
  --color-bg: #ffffff;
  --color-text: #1a1a1a;
  --color-primary: #123a5e;
  --color-accent: #1f6fb2;
  --color-muted: #5b6b7a;
  --color-border: #c9d6e2;
  --color-thbg: #e6eef6;
  --color-zebra: #f7f9fb;
  --color-soft: #f2f6fa;
  --color-code: #0d4a7a;

  --ff-heading: "SimHei", "黑体", sans-serif;
  --ff-body: "SimSun", "宋体", serif;
  --ff-mono: "Consolas", "Courier New", monospace;

  --fs-cover-t1: 30pt;
  --fs-cover-t2: 22pt;
  --fs-cover-cat: 11pt;
  --fs-cover-sub: 11.5pt;
  --fs-h2: 17pt;
  --fs-h3: 13pt;
  --fs-h4: 11.5pt;
  --fs-body: 12pt;
  --fs-small: 9.5pt;
  --fs-code: 9pt;
  --fs-table: 9.5pt;

  --sp-1: 2pt;  --sp-2: 4pt;  --sp-3: 6pt;  --sp-4: 8pt;
  --sp-5: 10pt; --sp-6: 12pt; --sp-7: 14pt; --sp-8: 18pt;
  --sp-9: 22pt; --sp-10: 28pt;
  --pad-page: 2.4cm;
  --pad-cover-top: 3.2cm;
  --indent-body: 2em;
  --indent-list: 2.2em;
  --misc-line: 1.7;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--ff-body);
  font-size: var(--fs-body);
  line-height: var(--misc-line);
  color: var(--color-text);
  background: var(--color-bg);
}

/* ---------------- 封面 ---------------- */
section.cover-plate {
  padding: var(--pad-cover-top) var(--pad-page) var(--pad-page) var(--pad-page);
  border-top: var(--sp-5) solid var(--color-primary);
}
.cover-rule { width: var(--sp-10); height: var(--sp-1); background: var(--color-accent); margin-bottom: var(--sp-9); }
.cover-cat {
  font-family: var(--ff-heading); font-size: var(--fs-cover-cat); font-weight: bold;
  color: var(--color-accent); letter-spacing: var(--sp-1); margin-bottom: var(--sp-9); text-indent: 0;
}
.cover-t1 {
  font-family: var(--ff-heading); font-size: var(--fs-cover-t1); font-weight: bold;
  color: var(--color-primary); line-height: var(--misc-line); margin-bottom: var(--sp-3); text-indent: 0;
}
.cover-t2 {
  font-family: var(--ff-heading); font-size: var(--fs-cover-t2); font-weight: bold;
  color: var(--color-primary); line-height: var(--misc-line); margin-bottom: var(--sp-8); text-indent: 0;
}
.cover-sub { font-size: var(--fs-cover-sub); color: var(--color-muted); text-indent: 0; }
.cover-meta {
  margin-top: var(--sp-10); padding-top: var(--sp-6); border-top: var(--sp-1) solid var(--color-border);
}
.cover-meta p {
  font-size: var(--fs-small); color: var(--color-muted);
  line-height: var(--misc-line); text-indent: 0; margin-bottom: var(--sp-1);
}

/* ---------------- 目录 ---------------- */
section.toc-plate { padding: var(--sp-10) var(--pad-page); page-break-before: always; }
section[role="body"] { page-break-before: always; }
.toc-title {
  font-family: var(--ff-heading); font-size: var(--fs-h2); font-weight: bold;
  color: var(--color-primary); margin-bottom: var(--sp-7); text-indent: 0;
  padding-bottom: var(--sp-3); border-bottom: var(--sp-1) solid var(--color-primary);
}
.toc-list, .toc-list ol, .toc-list ul { list-style: none; list-style-type: none; padding-left: 0; }
.toc-list li {
  margin-bottom: var(--sp-3); padding-bottom: var(--sp-2);
  border-bottom: var(--sp-1) dotted var(--color-border);
  font-size: var(--fs-body); text-indent: 0;
}
.toc-list a { color: var(--color-text); text-decoration: none; }

/* ---------------- 正文 ---------------- */
section.body-plate { padding: 0 var(--pad-page) var(--pad-page) var(--pad-page); }
h2 {
  font-family: var(--ff-heading); font-size: var(--fs-h2); font-weight: bold;
  color: var(--color-primary); text-indent: 0;
  margin: 0 0 var(--sp-6) 0; padding: 0 0 var(--sp-3) 0;
  border-bottom: var(--sp-1) solid var(--color-primary);
  page-break-before: always;
}
h3 {
  font-family: var(--ff-heading); font-size: var(--fs-h3); font-weight: bold;
  color: var(--color-accent); text-indent: 0;
  margin: var(--sp-8) 0 var(--sp-4) 0; padding-left: var(--sp-3);
  border-left: var(--sp-1) solid var(--color-accent);
  page-break-after: avoid;
}
h4 {
  font-family: var(--ff-heading); font-size: var(--fs-h4); font-weight: bold;
  color: var(--color-primary); text-indent: 0;
  margin: var(--sp-6) 0 var(--sp-2) 0;
}
p {
  margin: 0 0 var(--sp-4) 0; text-indent: var(--indent-body);
  text-align: justify;
}
p.end-mark { text-align: center; text-indent: 0; color: var(--color-muted); font-size: var(--fs-small); margin-top: var(--sp-8); }

ul, ol { margin: 0 0 var(--sp-4) 0; padding-left: var(--indent-list); }
li { margin-bottom: var(--sp-1); line-height: var(--misc-line); text-align: justify; }

pre {
  font-family: var(--ff-mono); font-size: var(--fs-code);
  line-height: var(--misc-line); background: var(--color-soft);
  border: var(--sp-1) solid var(--color-border);
  border-left: var(--sp-2) solid var(--color-accent);
  padding: var(--sp-4) var(--sp-5); margin: var(--sp-4) 0 var(--sp-5) 0;
  white-space: pre-wrap; text-indent: 0;
}

code.ic {
  font-family: var(--ff-mono); font-size: var(--fs-small);
  background: var(--color-soft); padding: var(--sp-1) var(--sp-1);
  color: var(--color-code);
}

/* ---------------- 执行摘要 ---------------- */
.executive-summary {
  background: var(--color-soft);
  border-left: var(--sp-2) solid var(--color-accent);
  padding: var(--sp-6) var(--sp-6) var(--sp-4) var(--sp-6);
  margin: var(--sp-6) 0 var(--sp-8) 0;
}
.summary-header { margin-bottom: var(--sp-2); }
.summary-badge {
  font-size: var(--fs-small); color: var(--color-accent); font-weight: bold;
  letter-spacing: var(--sp-1); text-indent: 0; margin-bottom: 0;
}
.executive-summary h2 {
  page-break-before: auto; border-bottom: var(--sp-1) solid var(--color-accent);
  margin: var(--sp-2) 0 var(--sp-5) 0;
}

table.dt {
  width: 100%; border-collapse: collapse;
  margin: var(--sp-3) 0 var(--sp-6) 0;
  font-size: var(--fs-table); line-height: var(--misc-line);
}
table.dt th {
  background: var(--color-thbg); color: var(--color-primary);
  font-family: var(--ff-heading); font-weight: bold; font-size: var(--fs-table);
  border: var(--sp-1) solid var(--color-border);
  padding: var(--sp-2) var(--sp-3); text-align: left;
}
table.dt td {
  border: var(--sp-1) solid var(--color-border);
  padding: var(--sp-2) var(--sp-3); vertical-align: top; text-align: left;
}
table.dt tbody tr:nth-child(even) td { background: var(--color-zebra); }
table.dt tr { page-break-inside: avoid; }
table.dt strong { color: var(--color-primary); }
</style>
</head>
<body>

<section role="cover" class="cover-plate">
  <div class="cover-rule"></div>
  <p class="cover-cat">知识产权战略评估</p>
  <p class="cover-t1">MedAgentWork 与 MedKit</p>
  <p class="cover-t2">专利可行性评估与全链路申请方案</p>
  <p class="cover-sub">技术点梳理 · 三性判断 · 现有技术比对 · 检索与撰写路径 · 风险预案</p>
  <div class="cover-meta">
    <p>评估基准日：2026 年 10 月 28 日</p>
    <p>评估对象：MedAgentWork（医学题库生产管线）· MedKit（医学题库工坊桌面端）</p>
    <p>报告性质：技术与知识产权策略评估，非法律意见书</p>
  </div>
</section>

<section role="cover" class="toc-plate">
  <p class="toc-title">目录</p>
  <ol class="toc-list">
%TOC%
  </ol>
</section>

<section role="body" class="body-plate" data-page-restart="1">
%BODY%
</section>

</body>
</html>
"""

HTML = HTML.replace("%TOC%", TOC).replace("%BODY%", BODY)
DST.write_text(HTML, encoding="utf-8")
print("OK ->", DST)
print("h2:", len(h2_seq), "tables:", BODY.count('<table class="dt"'), "exec:", BODY.count("executive-summary"))
