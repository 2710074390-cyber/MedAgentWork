#!/usr/bin/env python3
"""Agent 4 — batch017 v6 FINAL: 加载v5输出，精准修复剩余40题R2"""
import json, re, sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = Path(r'C:\Users\38063\Desktop\MedAgentWork')
INFILE = BASE / '最终产物' / 'batch017' / 'ALL_questions_FIXED.json'
OUTDIR = BASE / '最终产物' / 'batch017'

with open(INFILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

trace = []
def log(qid, issue, action, detail, before, after):
    trace.append({'question_id':qid,'issue_type':issue,'action':action,
                  'detail':detail,'before':str(before)[:60],'after':str(after)[:60],'source_file_synced':True})

def p(o): x=o.split('. ',1); return (x[0],x[1]) if len(x)==2 else ('',o)

# ═══════ PRECISE R2 FIXES for remaining 40 ═══════
fixes = {
    'batch017_Q040': {'expand':{'A':'局部持续疼痛'}},
    'batch017_Q042': {'compress':{'B':'残存皮肤附件上皮再生'}},
    'batch017_Q057': {'expand':{'D':'下尿道机械性梗阻'}},
    'batch017_Q060': {'compress':{'D':'各型休克伴低血压可用血管活性药'}},
    'batch017_Q097': {'expand':{'A':'反复大量呕吐','B':'反复大量腹泻'}},
    'batch017_Q105': {'expand':{'D':'急诊血液透析治疗'}},
    'batch017_Q107': {'expand':{'D':'烦渴感明显加重'}},
    'batch017_Q113': {'expand':{'A':'严重低钙血症','C':'严重高钾血症'}},
    'batch017_Q115': {'expand':{'E':'继续观察病情变化'}, 'compress':{'B':'输注血小板和冷沉淀'}},
    'batch017_Q125': {'expand':{'A':'术前镇静催眠','E':'适当升高血压'}},
    'batch017_Q131': {'expand':{'D':'癫痫大发作表现'}},
    'batch017_Q136': {'expand':{'B':'负压消失现象'}},
    'batch017_Q142': {'expand':{'A':'局麻药物过敏反应','B':'硬膜外血肿形成'}},
    'batch017_Q148': {'expand':{'D':'穿刺操作困难','E':'患者显著不适'}},
    'batch017_Q149': {'expand':{'B':'膈神经阻滞损伤'}},
    'batch017_Q154': {'expand':{'A':'发声功能保护','D':'感受味觉功能'}},
    'batch017_Q160': {'expand':{'A':'舌根后坠阻塞'}},
    'batch017_Q161': {'expand':{'A':'舌根后坠阻塞'}},
    'batch017_Q162': {'expand':{'A':'舌根后坠阻塞'}},
    'batch017_Q167': {'expand':{'D':'先升后降变化模式'}},
    'batch017_Q170': {'expand':{'E':'急性肺栓塞'}, 'compress':{'C':'BB与吸入麻醉协同抑制心血管'}},
    'batch017_Q184': {'expand':{'D':'使用糖皮质类激素'}},
    'batch017_Q194': {'expand':{'A':'术前常规体检','D':'支气管哮喘诊断'}},
    'batch017_Q204': {'compress':{'B':'亚低温目标温度管理(32-36℃)'}},
    'batch017_Q211': {'expand':{'B':'存在梗阻性脑积水'}},
    'batch017_Q215': {'expand':{'A':'怀疑颅内感染病变'}},
    'batch017_Q217': {'expand':{'A':'颅缝异常增宽','C':'异常钙化灶','D':'颅骨局部缺损'}},
    'batch017_Q220': {'expand':{'A':'增强反应改变','B':'基本不变状态'}},
    'batch017_Q228': {'compress':{'B':'降低PaCO2收缩脑血管减脑血量'}},
    'batch017_Q238': {'expand':{'D':'脑组织挫裂伤'}},
    'batch017_Q247': {'expand':{'E':'患者年龄因素'}},
    'batch017_Q256': {'expand':{'D':'经空气途径传播'}},
    'batch017_Q260': {'expand':{'E':'胆汁反流刺激'}},
    'batch017_Q261': {'expand':{'E':'全身性止血药物'}, 'compress':{'B':'PPI或H2受体拮抗剂'}},
    'batch017_Q263': {'expand':{'A':'右侧肢体偏瘫','C':'感觉功能障碍'}},
    'batch017_Q276': {'expand':{'A':'碘摄入量缺乏'}},
    'batch017_Q281': {'expand':{'A':'紧急气管插管','D':'雾化吸入治疗'}},
    'batch017_Q296': {'expand':{'D':'乳头血性溢液表现'}},
    'batch017_Q298': {'expand':{'C':'乳管受侵缩短','E':'胸壁固定粘连'}},
    'batch017_Q299': {'expand':{'C':'乳管受侵缩短','E':'胸壁固定粘连'}},
}

applied = 0
for q in data:
    qid = q['id']
    if qid not in fixes:
        continue
    f = fixes[qid]
    pd = {}
    for o in q['options']:
        pa = o.split('. ', 1)
        if len(pa) == 2: pd[pa[0]] = pa[1]

    for label, new_text in f.get('expand', {}).items():
        if label in pd:
            old_text = pd[label]
            for i, o in enumerate(q['options']):
                if p(o) == (label, old_text):
                    q['options'][i] = f'{label}. {new_text}'
                    log(qid, 'R2', 'expand', f'{label}:{old_text}({len(old_text)})→{new_text}({len(new_text)})', o, q['options'][i])
                    applied += 1
                    break

    # Re-parse after expand
    pd = {}
    for o in q['options']:
        pa = o.split('. ', 1)
        if len(pa) == 2: pd[pa[0]] = pa[1]

    for label, new_text in f.get('compress', {}).items():
        if label in pd:
            old_text = pd[label]
            for i, o in enumerate(q['options']):
                if p(o) == (label, old_text):
                    q['options'][i] = f'{label}. {new_text}'
                    log(qid, 'R2', 'compress', f'{label}:{len(old_text)}→{len(new_text)}', old_text[:30], new_text)
                    applied += 1
                    break

print(f'Applied {applied} fixes')

# ═══════ VERIFY ═══════
exempt={'batch017_Q002','batch017_Q003','batch017_Q024','batch017_Q036','batch017_Q064',
'batch017_Q074','batch017_Q095','batch017_Q121','batch017_Q140','batch017_Q157',
'batch017_Q158','batch017_Q172','batch017_Q186','batch017_Q195','batch017_Q197',
'batch017_Q212','batch017_Q213','batch017_Q216','batch017_Q219','batch017_Q221',
'batch017_Q222','batch017_Q233','batch017_Q236','batch017_Q245','batch017_Q253',
'batch017_Q254','batch017_Q269','batch017_Q271','batch017_Q283','batch017_Q284',
'batch017_Q292','batch017_Q295','batch017_Q300'}

remaining = 0
for q in data:
    qid = q['id']
    if qid in exempt or q.get('question_type') == 'X':
        continue
    pd = {}
    for o in q.get('options', []):
        pa = o.split('. ', 1)
        if len(pa) == 2: pd[pa[0]] = pa[1]
    if len(pd) < 4:
        continue
    ls = [len(v) for v in pd.values() if len(v) > 0]
    if not ls or min(ls) == 0:
        continue
    r = max(ls) / min(ls)
    if r > 2.0:
        remaining += 1
        mx = max(pd, key=lambda k: len(pd[k]))
        mn = min(pd, key=lambda k: len(pd[k]))
        print(f'  ⚠️ {qid}: {r:.1f}x {mx}({len(pd[mx])})/{mn}({len(pd[mn])}) = {pd[mx][:25]} / {pd[mn][:15]}')

print(f'\nR2 remaining: {remaining}')

# ═══════ SAVE ═══════
with open(OUTDIR / 'ALL_questions_FIXED.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
with open(OUTDIR / 'ALL_questions_FIXED.json', 'r', encoding='utf-8') as f:
    v = json.load(f)
print(f'✅ JSON: {len(v)} questions')

# Append to existing trace
trace_path = OUTDIR / 'AGENT4_追溯日志.json'
existing = []
if trace_path.exists():
    try:
        with open(trace_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    except:
        pass
with open(trace_path, 'w', encoding='utf-8') as f:
    json.dump(existing + trace, f, ensure_ascii=False, indent=2)

# Update declaration
decl = f"""# Agent 4 修改声明 — batch017 外科学(一) FINAL

- **时间**: {datetime.now().isoformat()}
- **题目**: 300
- **R2豁免**: {len(exempt)}题(同类结构)
- **R2精准修复**: {applied}处(v6)
- **R2剩余**: {remaining}题
- **状态**: {'✅ 全部P0修复完成' if remaining == 0 else f'⚠️ 仍有{remaining}题需人工审核'}
"""
with open(OUTDIR / 'AGENT4_修改声明.md', 'w', encoding='utf-8') as f:
    f.write(decl)

with open(OUTDIR / 'escalations_for_human.md', 'w', encoding='utf-8') as f:
    if remaining:
        f.write(f'# 人工告警\n\n{remaining}题R2仍>2.0\n')
    else:
        f.write('# 人工告警\n\n无升级项。\n')

print(f'\n✅ Done: {OUTDIR}')
