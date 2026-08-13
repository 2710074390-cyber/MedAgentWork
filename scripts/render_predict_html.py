# -*- coding: utf-8 -*-
"""渲染押题卷HTML"""
import json, os
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

type_stats = {}; bloom_stats = {}
for q in questions:
    type_stats[q['type']] = type_stats.get(q['type'],0)+1
    bloom_stats[q['bloom']] = bloom_stats.get(q['bloom'],0)+1

H = []
H.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">')
H.append('<meta name="viewport" content="width=device-width,initial-scale=1.0">')
H.append(f'<title>神经病学考前押题卷 - {today}</title>')
H.append('<style>')
H.append('*{margin:0;padding:0;box-sizing:border-box}')
H.append('body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;line-height:1.8;color:#2c3e50;background:#f0f2f5;max-width:1000px;margin:0 auto;padding:20px}')
H.append('@media print{body{background:white;padding:0}.no-print{display:none}.question-card{break-inside:avoid}.answer-toggle{display:none}.answer-section{display:block!important}}')
H.append('.cover{background:linear-gradient(135deg,#1a237e,#283593,#3949ab);color:white;padding:50px 40px;border-radius:16px;margin-bottom:30px;text-align:center}')
H.append('.cover h1{font-size:2.4em;margin-bottom:10px;letter-spacing:4px}')
H.append('.cover .subtitle{font-size:1.2em;opacity:.9;margin-bottom:30px}')
H.append('.cover .meta{display:flex;justify-content:center;gap:40px;flex-wrap:wrap}')
H.append('.cover .meta-item{text-align:center}.cover .meta-value{font-size:2em;font-weight:bold}.cover .meta-label{font-size:.9em;opacity:.8}')
H.append('.stats-bar{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}')
H.append('.stat-card{background:white;border-radius:10px;padding:16px 20px;flex:1;min-width:120px;box-shadow:0 2px 8px rgba(0,0,0,.06);text-align:center}')
H.append('.stat-value{font-size:1.8em;font-weight:bold;color:#1a237e}.stat-label{font-size:.85em;color:#666;margin-top:4px}')
H.append('.module-section{margin-bottom:32px}')
H.append('.module-header{padding:20px 24px;border-radius:12px 12px 0 0;color:white}')
H.append('.module-header h2{font-size:1.3em;margin-bottom:6px}')
H.append('.priority-badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.75em;background:rgba(255,255,255,.25);margin-left:8px}')
H.append('.question-card{background:white;border:1px solid #e8e8e8;border-top:none;padding:20px 24px}')
H.append('.question-card:last-child{border-radius:0 0 12px 12px}')
H.append('.question-number{display:inline-block;background:#e8eaf6;color:#1a237e;padding:2px 10px;border-radius:12px;font-size:.8em;font-weight:bold;margin-right:8px}')
H.append('.question-type{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.75em;font-weight:600;margin-right:8px}')
H.append('.type-A1{background:#e3f2fd;color:#1565c0}.type-A2{background:#e8f5e9;color:#2e7d32}')
H.append('.type-A3{background:#fff3e0;color:#e65100}.type-B1{background:#f3e5f5;color:#7b1fa2}')
H.append('.type-X{background:#fce4ec;color:#c62828}.type-判断{background:#fff9c4;color:#f57f17}')
H.append('.question-stem{margin:10px 0;font-size:1.05em;line-height:1.8;color:#333}')
H.append('.options{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}')
H.append('.option-tag{display:inline-block;background:#f5f5f5;padding:6px 14px;border-radius:6px;font-size:.95em;border:1px solid #e0e0e0;min-width:80px}')
H.append('.answer-toggle{display:inline-block;padding:4px 14px;border:1px solid #1a237e;color:#1a237e;border-radius:16px;cursor:pointer;font-size:.8em;margin-top:8px;background:white;transition:all .2s;user-select:none}')
H.append('.answer-toggle:hover{background:#1a237e;color:white}')
H.append('.answer-section{margin-top:12px;padding:14px 18px;background:#f8f9fa;border-radius:8px;border-left:4px solid #1a237e}')
H.append('.answer-box{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}')
H.append('.answer-label{font-weight:bold;color:#666}')
H.append('.answer-value{font-weight:bold;font-size:1.15em;color:#c62828;background:#ffebee;padding:2px 12px;border-radius:4px}')
H.append('.source-tag{font-size:.8em;color:#666;background:#e8eaf6;padding:2px 8px;border-radius:4px}')
H.append('.bloom-tag{font-size:.75em;background:#e0f2f1;color:#00695c;padding:2px 8px;border-radius:4px}')
H.append('.explanation{color:#555;font-size:.9em;line-height:1.7;margin-top:6px}')
H.append('.answer-key{background:white;border-radius:12px;padding:24px;margin:30px 0;box-shadow:0 2px 8px rgba(0,0,0,.06)}')
H.append('.answer-key h2{color:#1a237e;margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid #1a237e}')
H.append('.answer-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(60px,1fr));gap:8px}')
H.append('.answer-grid-item{text-align:center;padding:6px;background:#f5f5f5;border-radius:6px;font-size:.9em}')
H.append('.answer-grid-item .num{color:#666;font-size:.8em}.answer-grid-item .ans{color:#c62828;font-weight:bold}')
H.append('.tips-section{background:linear-gradient(135deg,#fff8e1,#fff3e0);border-radius:12px;padding:24px;margin:30px 0;border:1px solid #ffe0b2}')
H.append('.tips-section h2{color:#e65100;margin-bottom:12px}.tips-section ul{padding-left:20px}.tips-section li{margin-bottom:8px;color:#555}')
H.append('.toggle-all-bar{display:flex;gap:10px;margin-bottom:24px;flex-wrap:wrap}')
H.append('.toggle-all-btn{padding:8px 20px;border:2px solid #1a237e;background:white;color:#1a237e;border-radius:24px;cursor:pointer;font-size:.9em;font-weight:500;transition:all .2s}')
H.append('.toggle-all-btn:hover{background:#1a237e;color:white}')
H.append('.footer{text-align:center;padding:30px;color:#999;font-size:.85em}')
H.append('.module-nav{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:28px}')
H.append('.module-nav a{text-decoration:none;padding:6px 14px;border-radius:20px;font-size:.85em;font-weight:500;color:white;transition:transform .2s}')
H.append('.module-nav a:hover{transform:scale(1.05)}')
H.append('</style></head><body>')

# Cover
app_cnt = bloom_stats.get('应用',0) + bloom_stats.get('分析',0)
H.append('<div class="cover"><h1>神经病学考前押题卷</h1>')
H.append('<div class="subtitle">基于教师最新重点（2026更新版） | 99题全新命制 | 非题库搬运</div>')
H.append('<div class="meta">')
H.append(f'<div class="meta-item"><div class="meta-value">{total}</div><div class="meta-label">精选题目</div></div>')
H.append('<div class="meta-item"><div class="meta-value">10</div><div class="meta-label">覆盖模块</div></div>')
H.append(f'<div class="meta-item"><div class="meta-value">{app_cnt}</div><div class="meta-label">临床应用题</div></div>')
H.append(f'<div class="meta-item"><div class="meta-value">{today}</div><div class="meta-label">生成日期</div></div>')
H.append('</div></div>')

# Stats
a1a2 = type_stats.get('A1',0) + type_stats.get('A2',0)
H.append('<div class="stats-bar">')
H.append(f'<div class="stat-card"><div class="stat-value">{a1a2}</div><div class="stat-label">单选题(A1+A2)</div></div>')
H.append(f'<div class="stat-card"><div class="stat-value">{type_stats.get("A3",0)}</div><div class="stat-label">病例组题(A3)</div></div>')
H.append(f'<div class="stat-card"><div class="stat-value">{type_stats.get("B1",0)}</div><div class="stat-label">配伍题(B1)</div></div>')
H.append(f'<div class="stat-card"><div class="stat-value">{type_stats.get("X",0)}</div><div class="stat-label">多选题(X)</div></div>')
H.append(f'<div class="stat-card"><div class="stat-value">{type_stats.get("判断",0)}</div><div class="stat-label">判断题</div></div>')
H.append('</div>')

# Toggle bar
H.append('<div class="toggle-all-bar no-print">')
H.append('<button class="toggle-all-btn" onclick="toggleAll(1)">显示全部答案</button>')
H.append('<button class="toggle-all-btn" onclick="toggleAll(0)">隐藏全部答案</button>')
H.append('<span style="color:#666;font-size:.85em;align-self:center;margin-left:10px">点击题目下方按钮查看单题答案</span>')
H.append('</div>')

# Module nav
H.append('<div class="module-nav no-print">')
for name, pri, color in mod_info:
    H.append(f'<a href="#mod-{name}" style="background:{color}">{name} [{pri}]</a>')
H.append('</div>')

# Questions by module
qidx = 0
for name, pri, color in mod_info:
    if name not in grouped: continue
    H.append(f'<div class="module-section" id="mod-{name}">')
    H.append(f'<div class="module-header" style="background:{color}"><h2>{name} <span class="priority-badge">{pri}</span></h2></div>')
    for q in grouped[name]:
        qidx += 1
        qid = f"q{qidx}"
        tp = q['type']
        stem = esc(q['stem'])
        ans = q.get('answer','')
        exp = esc(q.get('explanation',''))
        src = esc(q.get('source_page',''))
        bloom = q.get('bloom','')
        opts = q.get('options',[])

        opts_html = ''
        if tp == '判断':
            opts_html = '<div class="options"><span class="option-tag">A. 正确</span><span class="option-tag">B. 错误</span></div>'
        else:
            parts = ['<div class="options">']
            for o in opts:
                parts.append(f'<span class="option-tag">{o["label"]}. {esc(o["text"])}</span>')
            parts.append('</div>')
            opts_html = ''.join(parts)

        H.append(f'<div class="question-card">')
        H.append(f'<span class="question-number">第{qidx}题</span><span class="question-type type-{tp}">{tp}</span>')
        H.append(f'<div class="question-stem">{stem}</div>')
        H.append(opts_html)
        H.append(f'<div class="no-print"><span class="answer-toggle" onclick="toggleAns(\'{qid}\')" id="btn-{qid}">查看答案</span></div>')
        H.append(f'<div id="{qid}" class="answer-section" style="display:none">')
        H.append(f'<div class="answer-box"><span class="answer-label">答案：</span><span class="answer-value">{esc(ans)}</span>')
        H.append(f'<span class="source-tag">{src}</span><span class="bloom-tag">{bloom}</span></div>')
        H.append(f'<div class="explanation">{exp}</div></div>')
        H.append('</div>')
    H.append('</div>')

# Answer Key
H.append('<div class="answer-key no-print"><h2>快速答案对照表</h2><div class="answer-grid">')
idx = 0
for name, pri, color in mod_info:
    if name not in grouped: continue
    for q in grouped[name]:
        idx += 1
        H.append(f'<div class="answer-grid-item"><span class="num">{idx}</span><br><span class="ans">{esc(q["answer"])}</span></div>')
H.append('</div></div>')

# Tips
H.append('<div class="tips-section no-print"><h2>考前核心提醒（教师重点）</h2><ul>')
tips = [
    "定位诊断是基础：12对脑神经功能定位必须烂熟；中枢性vs周围性面瘫（额纹保留与否）；真性vs假性延髓麻痹（强哭强笑、咽反射）；内囊三偏征、脑干交叉瘫、脊髓半切综合征",
    "脑血管疾病占分最大：脑血栓（安静起病）vs脑栓塞（房颤+活动起病）vs脑出血（活动中+头痛呕吐+意识障碍）；TIA 24h恢复；rt-PA 4.5h时间窗；SAH爆裂样头痛+脑膜刺激征",
    "Wallenberg综合征：眩晕+交叉性感觉障碍+Horner征+后组脑神经麻痹=延髓背外侧=椎动脉/PICA闭塞",
    "帕金森病四大主征：静止性震颤（搓丸样）+肌强直（齿轮样）+运动迟缓（面具脸）+姿势步态异常（慌张步态），病理=黑质多巴胺神经元缺失+路易小体",
    "癫痫持续状态：持续>30min或连续发作间意识未恢复；首选地西泮静推；可致缺氧、高热、电解质紊乱",
    "重症肌无力：眼外肌首发+晨轻暮重+AChR-Ab阳性+低频重复电刺激衰减；三种危象处理截然不同",
    "GBS：前驱感染（空肠弯曲菌）到对称性弛缓瘫（由下向上）+脑脊液蛋白-细胞分离；治疗PE或IVIG（激素无效）",
    "失语分类：Broca（额下回后部，表达障碍，电报式）vs Wernicke（颞上回后部，理解障碍，流利错语）",
    "腰椎穿刺：后颅窝占位为绝对禁忌（可诱发脑疝）；脑脊液蛋白-细胞分离=GBS特征",
]
for tip in tips:
    H.append(f'<li><b>{tip.split("：")[0]}</b>：{tip.split("：")[1] if "：" in tip else tip}</li>')
H.append('</ul></div>')

# Footer
H.append('<div class="footer">')
H.append('<p>命题依据：教师最新重点（2026更新版）+ 网络最新考题趋势分析</p>')
H.append('<p>全新命制99题，非题库搬运 | 覆盖全部10个模块 | 教师重点关键词逐题匹配</p>')
H.append(f'<p>生成时间：{today} | MedAgentWork</p>')
H.append('</div>')

# Script
H.append('<script>')
H.append('function toggleAns(id){var e=document.getElementById(id);var b=document.getElementById("btn-"+id);')
H.append('if(e.style.display==="none"||e.style.display===""){e.style.display="block";b.textContent="隐藏答案";b.style.background="#1a237e";b.style.color="white"}')
H.append('else{e.style.display="none";b.textContent="查看答案";b.style.background="white";b.style.color="#1a237e"}}')
H.append('function toggleAll(s){document.querySelectorAll(".answer-section").forEach(function(e){e.style.display=s?"block":"none"});')
H.append('document.querySelectorAll(".answer-toggle").forEach(function(b){if(s){b.textContent="隐藏答案";b.style.background="#1a237e";b.style.color="white"}else{b.textContent="查看答案";b.style.background="white";b.style.color="#1a237e"}})}')
H.append('window.addEventListener("beforeprint",function(){document.querySelectorAll(".answer-section").forEach(function(e){e.style.display="block"})});')
H.append('</script></body></html>')

out_path = os.path.join(BASE, '最终产物', '神经病学押题卷_2026.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(''.join(H))
print(f'HTML generated: {out_path}')
print(f'Size: {os.path.getsize(out_path):,} bytes | Questions: {total}')
