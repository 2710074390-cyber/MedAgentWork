import json, re, os, sys

SCRATCH = "/workspace/_scratch"
TPL = "/workspace/scripts/quiz_template.html"
OUT = "/workspace/大三下/押题卷/耳鼻咽喉头颈外科学押题卷_100题.html"

SECTION_MAP = {
    "S1": "第一部分 · 一、单项选择题（A1型）·20题·每题1分",
    "S2": "第一部分 · 二、单项选择题（A2型·病例摘要）·10题·每题1分",
    "S3": "第一部分 · 三、单项选择题（A3/A4型·病例串）·10题·每题1分",
    "S4": "第一部分 · 四、判断题·10题·每题1分",
    "S5": "第一部分 · 五、多项选择题（X型）·10题·每题2分",
    "S6": "第一部分 · 六、案例分析题（不定项选择）·3案例×5小题·每题2分",
    "S7": "第二部分 · 七、判断题（进阶）·10题·每题1分",
    "S8": "第二部分 · 八、案例分析题（进阶·不定项）·1案例×5小题·每题2分",
    "S9": "第二部分 · 九、多项选择题（进阶·X型）·10题·每题2分",
}

q = []
for f in ("ent_p1.json", "ent_p2.json", "ent_p3.json"):
    with open(os.path.join(SCRATCH, f), encoding="utf-8") as fh:
        q.extend(json.load(fh))

# ---- 校验 ----
from collections import Counter
c = Counter(x["type"] for x in q)
csec = Counter(x["sec"] for x in q)
assert len(q) == 100, f"题目总数 {len(q)} != 100"
assert c["A1"] == 20 and c["A2"] == 10 and c["A4"] == 10, c
assert c["判断"] == 20 and c["X"] == 40, c
assert csec == {"S1": 20, "S2": 10, "S3": 10, "S4": 10, "S5": 10, "S6": 15,
                "S7": 10, "S8": 5, "S9": 10}, csec
for x in q:
    assert x["answer"], x["qid"]
    opts = x["options"]
    assert all(x["answer"].count(ch) <= 1 for ch in x["answer"]), x["qid"]
    for ch in x["answer"]:
        assert ch in "ABCDE" and (ord(ch) - 65) < len(opts), (x["qid"], x["answer"])
    if x["type"] != "X" and x["type"] != "判断":
        assert len(x["answer"]) == 1, x["qid"]

# ---- 组卷 ----
questions = []
for x in q:
    questions.append({
        "qid": x["qid"],
        "type": x["type"],
        "system": x["system"],
        "bloom": x["bloom"],
        "section": SECTION_MAP[x["sec"]],
        "stem": x["stem"],
        "options": x["options"],
        "answer": x["answer"],
        "explanation": x["explanation"],
        "source": x["source"],
    })

meta = {
    "title": "耳鼻咽喉头颈外科学押题卷（100题）",
    "sub": "期末押题卷 · 100题（第一部分75题·100分 + 第二部分25题·40分）· 出题源：耳鼻咽喉头颈外科学期末综合复习讲义",
}
intro = """<div class="paper-intro" id="paper-intro">
  <h2>耳鼻咽喉头颈外科学 · 期末押题卷（100题）</h2>
  <p>出题源：《<b>耳鼻咽喉头颈外科学期末综合复习讲义</b>》。本卷共 <b>100</b> 道客观题，分两部分：第一部分 <b>75</b> 题按考试大纲题型分配（合计 100 分），第二部分为 <b>25</b> 道拓展题（合计 40 分）。</p>
  <table>
    <thead><tr><th>题型</th><th>题量</th><th>分值</th><th>小计</th></tr></thead>
    <tbody>
      <tr><td>一、单项选择题（A1型 · 基本概念/解剖/生理）</td><td>20</td><td>1分/题</td><td>20分</td></tr>
      <tr><td>二、单项选择题（A2型 · 病例摘要最佳选择）</td><td>10</td><td>1分/题</td><td>10分</td></tr>
      <tr><td>三、单项选择题（A3/A4型 · 病例组/串型）</td><td>10</td><td>1分/题</td><td>10分</td></tr>
      <tr><td>四、判断题</td><td>10</td><td>1分/题</td><td>10分</td></tr>
      <tr><td>五、多项选择题（X型）</td><td>10</td><td>2分/题</td><td>20分</td></tr>
      <tr><td>六、案例分析题（不定项选择 · 3案例×5小题）</td><td>15</td><td>2分/小题</td><td>30分</td></tr>
      <tr><td colspan="3"><b>第一部分合计</b></td><td><b>75题 · 100分</b></td></tr>
      <tr><td>七、判断题（进阶）</td><td>10</td><td>1分/题</td><td>10分</td></tr>
      <tr><td>八、案例分析题（进阶 · 1案例×5小题）</td><td>5</td><td>2分/小题</td><td>10分</td></tr>
      <tr><td>九、多项选择题（进阶 · X型）</td><td>10</td><td>2分/题</td><td>20分</td></tr>
      <tr><td colspan="3"><b>第二部分合计</b></td><td><b>25题 · 40分</b></td></tr>
      <tr><td colspan="3"><b>全卷合计</b></td><td><b>100题 · 140分</b></td></tr>
    </tbody>
  </table>
  <p>说明：题型标签显示于每题上方（A1 / A2 / A4 / 判断 / X）。<b>X 型与案例分析（不定项）为多选</b>，请选齐全部正确项后点击「确认作答」。判断题选项为「正确 / 错误」。每题均附答案解析与讲义溯源，可打印为 PDF。</p>
</div>"""

# ---- 注入模板 ----
with open(TPL, encoding="utf-8") as fh:
    html = fh.read()

data_block = (
    '<script id="quiz-data">\n'
    'const PAPER_META = ' + json.dumps(meta, ensure_ascii=False, indent=2) + ';\n'
    'const QUESTIONS = ' + json.dumps(questions, ensure_ascii=False, indent=2) + ';\n'
    '</script>'
)
html, n1 = re.subn(r'(?m)^<script id="quiz-data">.*?</script>', lambda m: data_block, html, count=1, flags=re.S)
assert n1 == 1, "quiz-data 注入失败"

# 分节标题 CSS + 试卷说明 CSS
css_add = """  /* ---------- 押题卷分节标题 / 试卷说明 ---------- */
  .section-head {
    margin: 30px 0 6px; padding: 12px 18px; border-radius: var(--radius-card);
    background: var(--accent-light); color: var(--accent);
    font-size: 15px; font-weight: 700; letter-spacing: .02em;
    border-left: 4px solid var(--accent); break-inside: avoid;
  }
  .section-head:first-child { margin-top: 2px; }
  .paper-intro {
    background: var(--bg-secondary); border: 1px solid var(--border);
    border-radius: var(--radius-card); box-shadow: var(--shadow);
    padding: 18px 22px; margin: 18px 0; font-size: 13.5px; line-height: 1.9;
    color: var(--text-secondary); break-inside: avoid;
  }
  .paper-intro h2 { font-size: 16px; color: var(--text-primary); margin-bottom: 10px; }
  .paper-intro table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 13px; }
  .paper-intro th, .paper-intro td { border: 1px solid var(--border); padding: 6px 10px; text-align: left; }
  .paper-intro th { background: var(--bg-tertiary); color: var(--text-secondary); font-weight: 700; }
  body.mode-focus #paper-intro { display: none; }
  @media print {
    .section-head { background: #eef4ff !important; color: #0b4f8a !important;
      -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .paper-intro { box-shadow: none; }
  }

"""
html = html.replace("  /* ---------- 解析 ---------- */", css_add + "  /* ---------- 解析 ---------- */", 1)

# 试卷说明块
_needle = '<div class="container">\n  <div id="quiz"></div>'
html = html.replace(_needle,
                    '<div class="container">\n  ' + intro + '\n  <div id="quiz"></div>', 1)
assert 'id="paper-intro"' in html, "试卷说明注入失败"

# render() 增加分节标题
old_render = """  function render() {
    var list = visibleQuestions();
    quizEl.innerHTML = '';
    list.forEach(function (q, i) { quizEl.appendChild(buildCard(q, i + 1)); });
    updateScore();
  }"""
new_render = """  function buildSectionHead(title) {
    var d = document.createElement('div');
    d.className = 'section-head';
    d.textContent = title;
    return d;
  }
  function render() {
    var list = visibleQuestions();
    quizEl.innerHTML = '';
    var lastSec = null;
    list.forEach(function (q, i) {
      if (q.section && q.section !== lastSec) { lastSec = q.section; quizEl.appendChild(buildSectionHead(q.section)); }
      quizEl.appendChild(buildCard(q, i + 1));
    });
    updateScore();
  }"""
html = html.replace(old_render, new_render, 1)
assert 'buildSectionHead' in html, "分节标题注入失败"

# 专注模式元信息加 section
old_meta = "(q.system ? '<span class=\"q-bloom\">' + q.system + '</span>' : '') +"
new_meta = old_meta + "\n      (q.section ? '<span class=\"q-bloom\">' + q.section + '</span>' : '') +"
assert html.count(old_meta) == 1, "专注模式元信息注入点不唯一"
html = html.replace(old_meta, new_meta, 1)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(html)

print("OK ->", OUT)
print("题目总数:", len(questions), "| 题型:", dict(c))
