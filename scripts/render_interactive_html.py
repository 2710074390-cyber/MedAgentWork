# -*- coding: utf-8 -*-
"""神经病学押题卷 — 交互式HTML（点击作答+即时判定+进度追踪）"""
import json, os, re
from datetime import datetime

BASE = r"C:\Users\38063\Desktop\MedAgentWork"
with open(os.path.join(BASE,'中间产物','predict_100q_final.json'),'r',encoding='utf-8') as f:
    questions = json.load(f)

total = len(questions)
today = datetime.now().strftime("%Y年%m月%d日")

grouped = {}
for q in questions:
    m = q['module_name']
    if m not in grouped: grouped[m] = []
    grouped[m].append(q)

mod_info = [
    ("绪论", "了解", "#6c757d"), ("神经解剖与定位诊断", "核心", "#dc3545"),
    ("常见症状", "掌握", "#fd7e14"), ("病史采集与体格检查", "掌握", "#fd7e14"),
    ("辅助检查", "掌握", "#fd7e14"), ("脑血管疾病", "核心", "#dc3545"),
    ("运动障碍性疾病", "掌握", "#fd7e14"), ("癫痫", "核心", "#dc3545"),
    ("周围神经疾病", "掌握", "#fd7e14"), ("神经肌肉接头和肌肉疾病", "掌握", "#fd7e14"),
]

def esc(s):
    if not s: return ''
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

def parse_answer(q):
    """解析答案为子题数组"""
    tp = q['type']
    ans = q.get('answer','')
    if tp in ('A1','A2','判断'):
        return [ans]  # 单选，单答案
    elif tp == 'X':
        return [list(ans)]  # 多选，答案字符列表
    elif tp == 'B1':
        return ans.split('/')  # "A/C" → ["A","C"]
    elif tp == 'A3':
        # A3 = 复合型，选项text内含分号分隔的子答案提示
        # 从选项文本中提取子答案信息
        opts = q.get('options',[])
        correct_opt = None
        for o in opts:
            if o['label'] == ans:
                correct_opt = o['text']
                break
        # 尝试按分号拆分
        if correct_opt and '；' in correct_opt:
            return correct_opt.split('；')
        return [ans]  # fallback
    return [ans]

# Count types
type_counts = {}
for q in questions:
    type_counts[q['type']] = type_counts.get(q['type'],0)+1
bloom_counts = {}
for q in questions:
    bloom_counts[q['bloom']] = bloom_counts.get(q['bloom'],0)+1

H = []
# ─── HTML Head ───
H.append('''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>神经病学考前押题卷 - 交互版</title>
<style>
:root{--correct:#2e7d32;--wrong:#c62828;--neutral:#1a237e;--bg:#f0f2f5;--card:#fff;--border:#e0e0e0;--radius:12px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif;line-height:1.8;color:#2c3e50;background:var(--bg);max-width:1000px;margin:0 auto;padding:20px 20px 100px}
@media print{body{background:#fff;padding:0}.no-print{display:none!important}.question-card{break-inside:avoid}.option-label{cursor:default!important;pointer-events:none}}
/* ─── Fixed Score Bar ─── */
.score-bar{position:fixed;top:0;left:0;right:0;background:#fff;box-shadow:0 2px 12px rgba(0,0,0,.1);z-index:1000;padding:10px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.score-bar .total{font-size:1.4em;font-weight:bold;color:var(--neutral)}
.score-bar .correct{color:var(--correct);font-weight:bold}
.score-bar .wrong{color:var(--wrong);font-weight:bold}
.score-bar .progress{flex:1;min-width:200px;height:8px;background:#e0e0e0;border-radius:4px;overflow:hidden}
.score-bar .progress-fill{height:100%;background:linear-gradient(90deg,var(--correct),#43a047);border-radius:4px;transition:width .3s}
.score-bar .reset-btn{padding:6px 16px;border:1px solid var(--neutral);background:#fff;color:var(--neutral);border-radius:20px;cursor:pointer;font-size:.85em;transition:all .2s}
.score-bar .reset-btn:hover{background:var(--neutral);color:#fff}
/* ─── Cover ─── */
.cover{background:linear-gradient(135deg,#1a237e,#283593,#3949ab);color:#fff;padding:50px 40px;border-radius:var(--radius);margin:60px 0 30px;text-align:center}
.cover h1{font-size:2.4em;margin-bottom:10px;letter-spacing:4px}
.cover .subtitle{font-size:1.15em;opacity:.9;margin-bottom:25px}
.cover .meta{display:flex;justify-content:center;gap:40px;flex-wrap:wrap}
.cover .meta-item{text-align:center}
.cover .meta-value{font-size:2em;font-weight:bold}
.cover .meta-label{font-size:.85em;opacity:.8}
/* ─── Module Nav ─── */
.module-nav{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px}
.module-nav a{text-decoration:none;padding:6px 14px;border-radius:20px;font-size:.85em;font-weight:500;color:#fff;transition:transform .2s}
.module-nav a:hover{transform:scale(1.05)}
/* ─── Module Section ─── */
.module-section{margin-bottom:28px}
.module-header{padding:18px 22px;border-radius:var(--radius) var(--radius) 0 0;color:#fff}
.module-header h2{font-size:1.25em}
.priority-badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.72em;background:rgba(255,255,255,.25);margin-left:8px}
.module-count{float:right;font-size:.85em;opacity:.9}
/* ─── Question Card ─── */
.question-card{background:var(--card);border:1px solid var(--border);border-top:none;padding:20px 24px;transition:background .3s}
.question-card:last-child{border-radius:0 0 var(--radius) var(--radius)}
.question-card.answered-correct{background:#e8f5e9}
.question-card.answered-wrong{background:#ffebee}
.question-number{display:inline-block;background:#e8eaf6;color:var(--neutral);padding:2px 10px;border-radius:12px;font-size:.8em;font-weight:bold;margin-right:8px}
.question-type{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.72em;font-weight:600;margin-right:8px}
.type-A1{background:#e3f2fd;color:#1565c0}.type-A2{background:#e8f5e9;color:#2e7d32}
.type-A3{background:#fff3e0;color:#e65100}.type-B1{background:#f3e5f5;color:#7b1fa2}
.type-X{background:#fce4ec;color:#c62828}.type-判断{background:#fff9c4;color:#f57f17}
.question-stem{margin:10px 0;font-size:1.05em;line-height:1.8;color:#333}
.sub-stem{font-weight:600;color:var(--neutral);margin-top:12px;margin-bottom:6px;font-size:.95em}
/* ─── Options Grid ─── */
.options-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px;margin:10px 0}
.options-grid.single-col{grid-template-columns:1fr}
.option-label{display:flex;align-items:flex-start;gap:8px;padding:10px 14px;background:#f5f5f5;border:2px solid var(--border);border-radius:8px;cursor:pointer;transition:all .2s;font-size:.93em;line-height:1.6;user-select:none}
.option-label:hover{border-color:#90caf9;background:#e3f2fd;transform:translateY(-1px);box-shadow:0 2px 6px rgba(0,0,0,.08)}
.option-label:active{transform:translateY(0)}
.option-label.correct{border-color:var(--correct);background:#c8e6c9;color:#1b5e20;font-weight:600}
.option-label.wrong{border-color:var(--wrong);background:#ffcdd2;color:#b71c1c}
.option-label.show-correct{border-color:var(--correct);background:#e8f5e9}
.option-label.disabled{cursor:not-allowed;opacity:.7}
.option-label.disabled:hover{transform:none;box-shadow:none;border-color:var(--border);background:#f5f5f5}
.option-letter{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;background:#e0e0e0;border-radius:50%;font-weight:bold;font-size:.85em;flex-shrink:0}
.option-label.correct .option-letter{background:var(--correct);color:#fff}
.option-label.wrong .option-letter{background:var(--wrong);color:#fff}
.option-label.show-correct .option-letter{background:var(--correct);color:#fff}
.option-feedback{display:none;margin-left:auto;font-size:.85em;font-weight:bold;flex-shrink:0}
.option-label.correct .option-feedback{display:inline;color:var(--correct)}
.option-label.wrong .option-feedback{display:inline;color:var(--wrong)}
/* ─── X型 Submit ─── */
.submit-row{display:flex;align-items:center;gap:12px;margin-top:10px}
.submit-btn{padding:8px 20px;background:var(--neutral);color:#fff;border:none;border-radius:20px;cursor:pointer;font-size:.88em;font-weight:500;transition:all .2s}
.submit-btn:hover{background:#283593;transform:translateY(-1px)}
.submit-btn:disabled{background:#bbb;cursor:not-allowed;transform:none}
.submit-hint{font-size:.82em;color:#999}
/* ─── Explanation ─── */
.explanation-box{margin-top:12px;padding:14px 18px;background:#f8f9fa;border-radius:8px;border-left:4px solid var(--neutral);display:none;animation:fadeIn .3s}
.explanation-box.show{display:block}
.explanation-box .exp-text{color:#555;font-size:.9em;line-height:1.7}
.explanation-box .exp-meta{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.exp-tag{font-size:.75em;padding:2px 8px;border-radius:4px}
.exp-tag.src{background:#e8eaf6;color:var(--neutral)}
.exp-tag.bloom{background:#e0f2f1;color:#00695c}
@keyframes fadeIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}
/* ─── Tips ─── */
.tips-section{background:linear-gradient(135deg,#fff8e1,#fff3e0);border-radius:var(--radius);padding:24px;margin:30px 0;border:1px solid #ffe0b2}
.tips-section h2{color:#e65100;margin-bottom:12px}.tips-section ul{padding-left:20px}.tips-section li{margin-bottom:7px;color:#555;font-size:.92em}
/* ─── Footer ─── */
.footer{text-align:center;padding:30px;color:#999;font-size:.82em}
/* ─── Responsive ─── */
@media(max-width:640px){.options-grid{grid-template-columns:1fr}.score-bar{font-size:.85em;padding:8px 12px}.cover{padding:30px 20px}.cover h1{font-size:1.6em}.question-card{padding:14px 16px}}
</style></head><body>
<!-- Score Bar -->
<div class="score-bar no-print">
<span style="font-weight:bold">📊 答题进度</span>
<span class="total" id="answeredCount">0</span><span style="color:#666">/''')
H.append(str(total))
H.append('''</span>
<span class="correct" id="correctCount">✓0</span>
<span class="wrong" id="wrongCount">✗0</span>
<div class="progress"><div class="progress-fill" id="progressFill" style="width:0%"></div></div>
<button class="reset-btn" onclick="resetAll()">🔄 重置全部</button>
</div>
<!-- Cover -->''')

app_cnt = bloom_counts.get('应用',0) + bloom_counts.get('分析',0)
H.append('<div class="cover"><h1>🧠 神经病学考前押题卷</h1>')
H.append('<div class="subtitle">基于教师最新重点（2026更新版） | 交互式答题 | 点击选项即时判定</div>')
H.append('<div class="meta">')
H.append(f'<div class="meta-item"><div class="meta-value">{total}</div><div class="meta-label">精选题目</div></div>')
H.append(f'<div class="meta-item"><div class="meta-value">10</div><div class="meta-label">覆盖模块</div></div>')
H.append(f'<div class="meta-item"><div class="meta-value">{app_cnt}</div><div class="meta-label">临床应用题</div></div>')
H.append(f'<div class="meta-item"><div class="meta-value">{today}</div><div class="meta-label">生成日期</div></div>')
H.append('</div></div>')

# Module nav
H.append('<div class="module-nav no-print">')
for name, pri, color in mod_info:
    H.append(f'<a href="#mod-{name}" style="background:{color}">{name}</a>')
H.append('</div>')

# ─── Questions by Module ───
qidx = 0
for name, pri, color in mod_info:
    if name not in grouped: continue
    mod_qs = grouped[name]
    H.append(f'<div class="module-section" id="mod-{name}">')
    H.append(f'<div class="module-header" style="background:{color}"><h2>{name} <span class="priority-badge">{pri}</span><span class="module-count">{len(mod_qs)}题</span></h2></div>')

    for q in mod_qs:
        qidx += 1
        qid = f"q{qidx}"
        tp = q['type']
        stem = esc(q['stem'])
        ans = q.get('answer','')
        exp = esc(q.get('explanation',''))
        src = esc(q.get('source_page',''))
        bloom = q.get('bloom','')
        opts = q.get('options',[])

        # Parse answer for different types
        if tp == 'X':
            correct_labels = list(ans)  # "ABDE" → ['A','B','D','E']
        elif tp == 'B1':
            correct_labels = ans.split('/')  # "A/C" → ['A','C']
        else:
            correct_labels = [ans]

        H.append(f'<div class="question-card" id="card-{qid}">')
        H.append(f'<span class="question-number">第{qidx}题</span><span class="question-type type-{tp}">{tp}</span>')
        H.append(f'<div class="question-stem">{stem}</div>')

        # Render options based on type
        if tp in ('A1','A2'):
            # Single choice radio
            has_long_opts = any(len(o.get('text','')) > 20 for o in opts)
            grid_cls = 'options-grid' if not has_long_opts else 'options-grid single-col'
            H.append(f'<div class="{grid_cls}">')
            for o in opts:
                lbl = o['label']
                txt = esc(o.get('text',''))
                is_correct = (lbl == ans)
                H.append(f'<label class="option-label" data-qid="{qid}" data-letter="{lbl}" data-correct="{"1" if is_correct else "0"}" onclick="selectOption(this,\'{qid}\',\'{tp}\')">')
                H.append(f'<span class="option-letter">{lbl}</span><span>{txt}</span><span class="option-feedback">{" ✓" if is_correct else ""}</span>')
                H.append('</label>')
            H.append('</div>')
        elif tp == '判断':
            H.append('<div class="options-grid">')
            for o in opts:
                lbl = o['label']
                txt = esc(o.get('text',''))
                is_correct = (lbl == ans)
                H.append(f'<label class="option-label" data-qid="{qid}" data-letter="{lbl}" data-correct="{"1" if is_correct else "0"}" onclick="selectOption(this,\'{qid}\',\'{tp}\')">')
                H.append(f'<span class="option-letter">{lbl}</span><span>{txt}</span><span class="option-feedback">{" ✓" if is_correct else ""}</span>')
                H.append('</label>')
            H.append('</div>')
        elif tp == 'X':
            # Multiple choice with checkboxes
            H.append(f'<div class="options-grid single-col">')
            for o in opts:
                lbl = o['label']
                txt = esc(o.get('text',''))
                is_correct = (lbl in correct_labels)
                H.append(f'<label class="option-label x-option" data-qid="{qid}" data-letter="{lbl}" data-correct="{"1" if is_correct else "0"}" onclick="toggleXOption(this)">')
                H.append(f'<span class="option-letter">{lbl}</span><span>{txt}</span><span class="option-feedback">{" ✓" if is_correct else ""}</span>')
                H.append('</label>')
            H.append('</div>')
            H.append(f'<div class="submit-row"><button class="submit-btn" id="submit-{qid}" onclick="submitXAnswer(\'{qid}\')">✅ 提交判定</button>')
            H.append(f'<span class="submit-hint">点击选项选中/取消，然后提交判定</span></div>')
        elif tp == 'B1':
            # Shared options with sub-questions
            H.append('<div style="background:#f3e5f5;padding:8px 12px;border-radius:6px;margin:8px 0;font-size:.85em;color:#7b1fa2;font-weight:500">📎 共用选项</div>')
            H.append('<div class="options-grid">')
            for o in opts:
                lbl = o['label']
                txt = esc(o.get('text',''))
                H.append(f'<div class="option-label disabled" style="cursor:default"><span class="option-letter">{lbl}</span><span>{txt}</span></div>')
            H.append('</div>')
            # Sub-questions
            # Parse stem for sub-question separators
            sub_stems = re.split(r'[\(（]\d+[\)）]', stem)
            # sub_stems[0] is before first sub, then each element is a sub-question
            if len(sub_stems) > 1:
                for si in range(1, len(sub_stems)):
                    sub_text = esc(sub_stems[si].strip())
                    sub_idx = si - 1
                    sub_ans = correct_labels[sub_idx] if sub_idx < len(correct_labels) else '?'
                    sub_qid = f"{qid}s{si}"
                    H.append(f'<div class="sub-stem">({si}) {sub_text}</div>')
                    H.append(f'<div class="options-grid">')
                    for o in opts:
                        lbl = o['label']
                        txt = esc(o.get('text',''))
                        is_correct = (lbl == sub_ans)
                        H.append(f'<label class="option-label" data-qid="{sub_qid}" data-letter="{lbl}" data-correct="{"1" if is_correct else "0"}" onclick="selectOption(this,\'{sub_qid}\',\'B1\')">')
                        H.append(f'<span class="option-letter">{lbl}</span><span>{txt}</span><span class="option-feedback">{" ✓" if is_correct else ""}</span>')
                        H.append('</label>')
                    H.append('</div>')
            else:
                # Fallback: single set
                for o in opts:
                    lbl = o['label']
                    txt = esc(o.get('text',''))
                    is_correct = (lbl == ans)
                    H.append(f'<label class="option-label" data-qid="{qid}" data-letter="{lbl}" data-correct="{"1" if is_correct else "0"}" onclick="selectOption(this,\'{qid}\',\'B1\')">')
                    H.append(f'<span class="option-letter">{lbl}</span><span>{txt}</span><span class="option-feedback">{" ✓" if is_correct else ""}</span>')
                    H.append('</label>')
        elif tp == 'A3':
            # Case-based with sub-questions
            # Split stem at sub-question markers
            sub_stems = re.split(r'[\(（](\d+)[\)）]', stem)
            if len(sub_stems) > 1:
                case_text = esc(sub_stems[0].strip())
                H.append(f'<div style="background:#fff3e0;padding:10px 14px;border-radius:6px;margin:8px 0;font-size:.9em;color:#e65100;border-left:3px solid #e65100">{case_text}</div>')
                # Parse: sub_stems[1]="1", sub_stems[2]=text1, sub_stems[3]="2", sub_stems[4]=text2, ...
                for si in range(1, len(sub_stems), 2):
                    if si+1 < len(sub_stems):
                        s_num = sub_stems[si]
                        s_text = esc(sub_stems[si+1].strip())
                        sub_qid = f"{qid}s{s_num}"
                        H.append(f'<div class="sub-stem">({s_num}) {s_text}</div>')
                        H.append(f'<div class="options-grid">')
                        # For A3, options are compound. Extract individual sub-options.
                        for o in opts:
                            lbl = o['label']
                            full_text = o.get('text','')
                            # Try to extract this sub-question's portion
                            parts = full_text.split('；')
                            display_text = parts[int(s_num)-1] if int(s_num)-1 < len(parts) else full_text
                            is_correct = (lbl == ans)
                            H.append(f'<label class="option-label" data-qid="{sub_qid}" data-letter="{lbl}" data-correct="{"1" if is_correct else "0"}" onclick="selectOption(this,\'{sub_qid}\',\'A3\')">')
                            H.append(f'<span class="option-letter">{lbl}</span><span>{esc(display_text)}</span><span class="option-feedback">{" ✓" if is_correct else ""}</span>')
                            H.append('</label>')
                        H.append('</div>')
            else:
                # Fallback: render as regular A1
                H.append(f'<div class="options-grid">')
                for o in opts:
                    lbl = o['label']
                    txt = esc(o.get('text',''))
                    is_correct = (lbl == ans)
                    H.append(f'<label class="option-label" data-qid="{qid}" data-letter="{lbl}" data-correct="{"1" if is_correct else "0"}" onclick="selectOption(this,\'{qid}\',\'A3\')">')
                    H.append(f'<span class="option-letter">{lbl}</span><span>{txt}</span><span class="option-feedback">{" ✓" if is_correct else ""}</span>')
                    H.append('</label>')
                H.append('</div>')

        # Explanation box (hidden by default)
        H.append(f'<div class="explanation-box" id="exp-{qid}">')
        H.append(f'<div class="exp-meta"><span class="exp-tag src">{src}</span><span class="exp-tag bloom">{bloom}</span></div>')
        H.append(f'<div class="exp-text">💡 解析：{exp}</div>')
        H.append('</div>')

        H.append('</div>')  # end question-card

    H.append('</div>')  # end module-section

# ─── Tips ───
H.append('''<div class="tips-section no-print"><h2>💡 考前核心提醒（教师重点）</h2><ul>
<li><b>定位诊断是基础</b>：12对脑神经功能定位必须烂熟；中枢性vs周围性面瘫（额纹保留与否）；真性vs假性延髓麻痹（强哭强笑）；内囊三偏征、脑干交叉瘫、脊髓半切综合征</li>
<li><b>脑血管疾病占分最大</b>：脑血栓（安静起病）vs脑栓塞（房颤+活动起病）vs脑出血（活动中+头痛呕吐）；TIA 24h恢复；rt-PA 4.5h时间窗；SAH爆裂样头痛+脑膜刺激征</li>
<li><b>Wallenberg综合征</b>：眩晕+交叉性感觉障碍+Horner征+后组脑神经麻痹=延髓背外侧=椎动脉/PICA闭塞</li>
<li><b>帕金森病四大主征</b>：静止性震颤（搓丸样）+肌强直（齿轮样）+运动迟缓（面具脸）+姿势步态异常（慌张步态）</li>
<li><b>癫痫持续状态</b>：持续>30min或连续发作间意识未恢复；首选地西泮静推</li>
<li><b>重症肌无力</b>：眼外肌首发+晨轻暮重+AChR-Ab阳性；三种危象处理截然不同</li>
<li><b>GBS</b>：前驱感染（空肠弯曲菌）→对称性弛缓瘫+脑脊液蛋白-细胞分离；治疗PE或IVIG（激素无效）</li>
<li><b>失语分类</b>：Broca（额下回后部→表达障碍）vs Wernicke（颞上回后部→理解障碍）</li>
<li><b>腰椎穿刺</b>：后颅窝占位为绝对禁忌；脑脊液蛋白-细胞分离=GBS特征</li>
</ul></div>''')

# ─── Footer ───
H.append(f'''<div class="footer"><p>📚 全新命制99题（非题库搬运） | 基于教师最新重点（2026更新版）+ 网络考题趋势</p>
<p>点击选项即时判定 | 支持打印（打印时显示全部解析） | {today} | MedAgentWork</p></div>''')

# ─── JavaScript ───
H.append('''<script>
// State
let answered = {};  // qid -> true (已答)
let correctSet = {};  // qid -> true (正确)
let xSelections = {};  // qid -> Set of selected letters

let totalAnswered = 0;
let totalCorrect = 0;

function updateScoreBar() {
    document.getElementById('answeredCount').textContent = totalAnswered;
    document.getElementById('correctCount').textContent = '\\u2713'+totalCorrect;
    document.getElementById('wrongCount').textContent = '\\u2717'+(totalAnswered-totalCorrect);
    let pct = ''' + str(total) + ''' > 0 ? Math.round(totalAnswered/''' + str(total) + '''*100) : 0;
    document.getElementById('progressFill').style.width = pct+'%';
}

function showExplanation(qid) {
    let exp = document.getElementById('exp-'+qid);
    if (exp) exp.classList.add('show');
}

// Single choice: A1, A2, B1-sub, A3-sub, 判断
function selectOption(labelEl, qid, type) {
    if (answered[qid]) return; // already answered

    let isCorrect = labelEl.dataset.correct === '1';
    let card = document.getElementById('card-'+qid.split('s')[0]); // parent card

    // Mark all options in this group as disabled
    let parent = labelEl.parentElement;
    let allLabels = parent.querySelectorAll('.option-label');
    allLabels.forEach(l => l.classList.add('disabled'));

    // Show result
    if (isCorrect) {
        labelEl.classList.add('correct');
        if (card) card.classList.add('answered-correct');
    } else {
        labelEl.classList.add('wrong');
        if (card) card.classList.add('answered-wrong');
        // Show correct answer
        allLabels.forEach(l => {
            if (l.dataset.correct === '1') l.classList.add('show-correct');
        });
    }

    answered[qid] = true;
    correctSet[qid] = isCorrect;
    totalAnswered++;
    if (isCorrect) totalCorrect++;

    updateScoreBar();
    showExplanation(qid.split('s')[0]); // show parent explanation
}

// X type: toggle selection
function toggleXOption(labelEl) {
    let qid = labelEl.dataset.qid;
    if (answered[qid]) return;
    if (!xSelections[qid]) xSelections[qid] = new Set();

    let letter = labelEl.dataset.letter;
    if (xSelections[qid].has(letter)) {
        xSelections[qid].delete(letter);
        labelEl.style.background = '#f5f5f5';
        labelEl.style.borderColor = '#e0e0e0';
        labelEl.style.fontWeight = 'normal';
    } else {
        xSelections[qid].add(letter);
        labelEl.style.background = '#e3f2fd';
        labelEl.style.borderColor = '#90caf9';
        labelEl.style.fontWeight = '600';
    }
}

// X type: submit answer
function submitXAnswer(qid) {
    if (answered[qid]) return;

    let selected = xSelections[qid] || new Set();
    let parent = document.getElementById('submit-'+qid).parentElement.parentElement;
    let allLabels = parent.querySelectorAll('.option-label.x-option');

    // Get correct labels
    let correctLabels = new Set();
    allLabels.forEach(l => { if (l.dataset.correct === '1') correctLabels.add(l.dataset.letter); });

    // Check if answer matches
    let isCorrect = setsEqual(selected, correctLabels);
    let card = document.getElementById('card-'+qid.split('s')[0]);

    allLabels.forEach(l => {
        l.classList.add('disabled');
        let letter = l.dataset.letter;
        if (l.dataset.correct === '1') {
            l.classList.add('show-correct');
            l.querySelector('.option-feedback').style.display = 'inline';
            l.querySelector('.option-feedback').style.color = 'var(--correct)';
        }
        if (selected.has(letter) && l.dataset.correct !== '1') {
            l.classList.add('wrong');
        }
    });

    if (isCorrect) {
        if (card) card.classList.add('answered-correct');
    } else {
        if (card) card.classList.add('answered-wrong');
    }

    document.getElementById('submit-'+qid).disabled = true;
    answered[qid] = true;
    correctSet[qid] = isCorrect;
    totalAnswered++;
    if (isCorrect) totalCorrect++;

    updateScoreBar();
    showExplanation(qid.split('s')[0]);
}

function setsEqual(a, b) {
    if (a.size !== b.size) return false;
    for (let x of a) if (!b.has(x)) return false;
    return true;
}

function resetAll() {
    answered = {};
    correctSet = {};
    xSelections = {};
    totalAnswered = 0;
    totalCorrect = 0;

    document.querySelectorAll('.option-label').forEach(l => {
        l.classList.remove('correct','wrong','show-correct','disabled');
        l.style.background = '#f5f5f5';
        l.style.borderColor = '#e0e0e0';
        l.style.fontWeight = 'normal';
    });
    document.querySelectorAll('.question-card').forEach(c => {
        c.classList.remove('answered-correct','answered-wrong');
    });
    document.querySelectorAll('.explanation-box').forEach(e => {
        e.classList.remove('show');
    });
    document.querySelectorAll('.submit-btn').forEach(b => {
        b.disabled = false;
    });
    document.querySelectorAll('.option-feedback').forEach(f => {
        f.style.display = '';
        f.style.color = '';
    });

    updateScoreBar();
}

updateScoreBar();

// Print: show all explanations
window.addEventListener('beforeprint', function() {
    document.querySelectorAll('.explanation-box').forEach(e => e.classList.add('show'));
    document.querySelectorAll('.option-label').forEach(l => {
        if (l.dataset.correct === '1') {
            l.classList.add('show-correct');
            l.querySelector('.option-feedback').style.display = 'inline';
            l.querySelector('.option-feedback').style.color = 'var(--correct)';
        }
    });
});
</script></body></html>''')

# ─── Write Output ───
out_path = os.path.join(BASE, '最终产物', '神经病学押题卷_2026.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(H))
print(f'HTML generated: {out_path}')
print(f'Size: {os.path.getsize(out_path):,} bytes | Questions: {total}')
print(f'Features: click-to-answer, instant feedback, progress tracking, type-specific interactions')
