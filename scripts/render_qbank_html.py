#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_qbank_html.py — 题库最终产物 HTML 生成器（2026-08-22 新增）

规则（docs/产物格式规范.md）：
  · 题库最终交付物 = MD（如 MedFix 的 ALL_questions_FIXED.md / export_psychiatry_md.py）
    + HTML（本脚本生成，可打印为 PDF）
  · 题库 PDF 一律由人工上传（用户提供），管线/脚本不产出 PDF

用法：
  python scripts/render_qbank_html.py --input 中间产物/batch027/ALL_questions_FIXED.json \
      --output 最终产物/batch027/内科学题库.html [--title "内科学题库"] [--subject 内科学]

字段兼容：agent2_output.schema.json 新契约 + 历史字段（question/question_type/answer_key/
correct_answer/analysis/source_pages 等），与 qbank.parse_question() 归一化口径一致。
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

TYPE_LABEL = {"A1": "A1", "A2": "A2", "A3": "A3", "A4": "A4", "B1": "B1", "X": "X", "判断": "判断"}
TYPE_COLOR = {
    "A1": "#2563eb", "A2": "#0891b2", "A3": "#dc2626", "A4": "#dc2626",
    "B1": "#d97706", "X": "#7c3aed", "判断": "#059669",
}


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def norm_type(raw):
    t = str(raw or "").strip()
    if "判断" in t:
        return "判断"
    m = re.search(r"([A-Z]?\d?|X|判断)", t)
    best = m.group(1) if m else t
    return best if best in TYPE_LABEL else (t or "A1")


def norm_options(opts):
    """options → {label: text}：兼容 dict / [{label,text}] / ['A. text']。"""
    out = {}
    if isinstance(opts, dict):
        for k, v in opts.items():
            if isinstance(v, str) and v.strip():
                out[str(k).strip().upper()] = v.strip()
    elif isinstance(opts, list):
        for o in opts:
            if isinstance(o, dict) and o.get("label") and o.get("text"):
                out[str(o["label"]).strip().upper()] = str(o["text"]).strip()
            elif isinstance(o, str):
                m = re.match(r"^([A-E])[.、）)\s]+(.*)$", o.strip())
                if m:
                    out[m.group(1)] = m.group(2).strip()
                elif o.strip():
                    out[str(len(out) + 1)] = o.strip()
    return out


def norm_answer(ans):
    if isinstance(ans, (list, tuple)):
        ans = "".join(str(a).strip() for a in ans if str(a).strip())
    ans = str(ans or "").strip().upper()
    m = re.fullmatch(r"[A-E]+", ans)
    if m:
        return m.group(0)
    m = re.search(r"[A-E]{2,}", ans)
    if m:
        return m.group(0)
    m = re.search(r"[A-E]", ans)
    return m.group(0) if m else ans[:1]


HTML_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} · MedAgentWork 题库</title>
<style>
:root {{
  --bg:#f6f8fa; --card:#fff; --ink:#1a1a2e; --ink-soft:#4a5568; --line:#e2e8f0;
  --accent:#2563eb; --ok:#047857; --ok-bg:#ecfdf5; --mono:"Cascadia Code",Consolas,monospace;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  background:var(--bg); color:var(--ink); line-height:1.8; max-width:960px; margin:0 auto; padding:24px 20px 80px; }}
h1 {{ font-size:26px; margin:8px 0 4px; }}
.sub {{ font-size:13px; color:var(--ink-soft); margin-bottom:24px; }}
.stats {{ font-family:var(--mono); font-size:12px; color:var(--ink-soft); margin-bottom:28px; }}
.q {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:20px 22px; margin:14px 0;
  break-inside:avoid; }}
.q-meta {{ display:flex; gap:8px; align-items:center; margin-bottom:8px; flex-wrap:wrap; }}
.q-num {{ font-weight:700; color:var(--accent); font-variant-numeric:tabular-nums; }}
.q-type {{ font-size:12px; font-weight:700; padding:1px 9px; border-radius:10px; color:#fff; }}
.q-bloom {{ font-size:12px; color:var(--ink-soft); }}
.q-stem {{ font-size:15.5px; margin:8px 0 12px; }}
.q-stem b {{ font-weight:700; }}
.opt {{ display:flex; gap:10px; padding:8px 12px; margin:6px 0; border:1px solid var(--line);
  border-radius:8px; background:#fafbfc; }}
.opt .l {{ font-weight:700; color:var(--accent); min-width:18px; }}
.opt.correct {{ border-color:#6ee7b7; background:var(--ok-bg); }}
.opt.correct .l {{ color:var(--ok); }}
.ans {{ display:none; margin-top:12px; padding:12px 14px; background:#f0f4ff; border-left:3px solid var(--accent);
  border-radius:8px; font-size:13.5px; }}
.ans.show {{ display:block; }}
.ans-head {{ font-weight:700; margin-bottom:4px; }}
.exp {{ color:var(--ink-soft); }}
.src {{ font-size:12px; color:#94a3b8; margin-top:6px; }}
@media print {{ body {{ background:#fff; padding:0; max-width:none; }} .q {{ border-color:#cbd5e1; }}
  .ans {{ display:block; }} }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="sub">MedAgentWork · 题库 HTML 交付版 · 可打印导出 PDF（答案解析默认展开）</div>
<div class="stats">{count} 题 · {types} ｜ 生成 {date}</div>
{questions}
</body>
</html>
"""


def build_questions(raw_list):
    parts = []
    for i, raw in enumerate(raw_list, 1):
        if not isinstance(raw, dict):
            continue
        stem = raw.get("stem") or raw.get("question") or raw.get("question_text") or raw.get("题干") or ""
        stem = esc(stem)
        options = norm_options(raw.get("options"))
        answer = norm_answer(raw.get("answer") or raw.get("answer_key") or raw.get("correct_answer"))
        expl = raw.get("explanation") or raw.get("analysis") or raw.get("解析") or ""
        src = raw.get("source") or raw.get("source_page") or ""
        if isinstance(src, list):
            src = ", ".join(esc(x) for x in src)
        else:
            src = esc(src)
        if not stem:
            continue

        parts.append(f'<div class="q">')
        parts.append(f'<div class="q-meta"><span class="q-num">第 {i} 题</span>'
                     f'<span class="q-type" style="background:{TYPE_COLOR.get(norm_type(raw.get("type")), "#475569")}">'
                     f'{esc(norm_type(raw.get("type")))}</span>'
                     f'{"<span class=&#34;q-bloom&#34;>" + esc(raw.get("bloom_level") or raw.get("bloom") or "") + "</span>" if raw.get("bloom_level") or raw.get("bloom") else ""}'
                     f'</div>')
        parts.append(f'<div class="q-stem">{stem}</div>')
        for label, text in options.items():
            cls = "opt correct" if (answer and label in answer) else "opt"
            parts.append(f'<div class="{cls}"><span class="l">{esc(label)}.</span><span>{esc(text)}</span></div>')
        parts.append(f'<div class="ans"><div class="ans-head">答案：{esc(answer) or "—"}</div>'
                     f'<div class="exp">{esc(expl)}</div>'
                     f'{"<div class=&#34;src&#34;>来源： " + src + "</div>" if src else ""}</div>')
        parts.append("</div>")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description="题库 JSON → 交付 HTML")
    ap.add_argument("--input", required=True, help="题库 JSON（数组）")
    ap.add_argument("--output", required=True, help="输出 HTML 路径")
    ap.add_argument("--title", default="题库")
    ap.add_argument("--subject", default="")
    args = ap.parse_args()

    raw_list = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(raw_list, list):
        sys.exit("❌ 输入应为 JSON 数组（题目列表）")

    qu = raw_list if isinstance(raw_list, list) else []
    types = {}
    for r in qu:
        if isinstance(r, dict):
            t = norm_type(r.get("type") or r.get("question_type") or "A1")
            types[t] = types.get(t, 0) + 1
    type_str = " / ".join(f"{k} {v}" for k, v in types.items())
    title = args.title
    html = HTML_TMPL.format(
        title=esc(title),
        count=len(qu),
        types=esc(type_str),
        date=__import__("datetime").datetime.now().strftime("%Y-%m-%d"),
        questions=build_questions(qu),
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"✅ 题库 HTML 已生成: {out}（{out.stat().st_size:,} 字节 / {len(qu)} 题）")
    print(f"   {title} ｜ 题量 {len(qu)} ｜ 类型 {type_str}")


if __name__ == "__main__":
    main()
