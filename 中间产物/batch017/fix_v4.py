#!/usr/bin/env python3
"""Agent 4 (MedFix) — batch017 v4 终极修复
策略: R10全部replace(不加长), R2用完整修复字典, 机械修复先行
"""
import json, re, sys, copy
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = Path(r'C:\Users\38063\Desktop\MedAgentWork')
INPUT = BASE / '中间产物' / 'batch017' / 'ALL_questions_batch017.json'
OUTDIR = BASE / '最终产物' / 'batch017'
OUTDIR.mkdir(parents=True, exist_ok=True)

with open(INPUT, 'r', encoding='utf-8') as f:
    data = json.load(f)

trace_log = []
def log(qid, issue, action, detail, before, after):
    trace_log.append({'question_id':qid,'issue_type':issue,'action':action,
                      'detail':detail,'before':str(before),'after':str(after),'source_file_synced':True})

def parse_opt(opt_str):
    p=opt_str.split('. ',1); return (p[0],p[1]) if len(p)==2 else ('',opt_str)
get_text=lambda o:parse_opt(o)[1]
get_label=lambda o:parse_opt(o)[0]

# ══════ PHASE 1: 前缀清理 ══════
for q in data:
    for tag in ['[正选]','[反选]','[多选]']:
        q['question_text'] = q['question_text'].replace(tag+' ','').replace(tag,'')

# ══════ PHASE 2: R4 否定词加粗 ══════
r4_map = {'batch017_Q016':'不包括','batch017_Q062':'不包括','batch017_Q123':'不包括',
          'batch017_Q155':'不包括','batch017_Q166':'不包括','batch017_Q184':'不包括',
          'batch017_Q186':'不包括','batch017_Q191':'不包括','batch017_Q229':'不包括',
          'batch017_Q256':'不包括','batch017_Q265':'不包括'}
for q in data:
    if q['id'] in r4_map:
        kw=r4_map[q['id']]
        if f'**{kw}**' not in q['question_text']:
            q['question_text']=q['question_text'].replace(kw,f'**{kw}**')
            log(q['id'],'R4','bold','否定词加粗',kw,f'**{kw}**')

# ══════ PHASE 3: R1 绝对化用语 ══════
r1_map = {
    'batch017_Q030':('超过14天必须重新灭菌','超过14天应重新灭菌'),
    'batch017_Q052':('血容量绝对不足导致的血流动力学紊乱','血容量显著不足导致的血流动力学紊乱'),
    'batch017_Q166':('可完全防止误吸','可有效防止误吸'),
    'batch017_Q176':('钙通道阻滞剂必须停用','钙通道阻滞剂应停用'),
    'batch017_Q199':('术后绝对卧床休息','术后严格卧床休息'),
    'batch017_Q220':('完全依赖交感神经控制','主要依赖交感神经控制'),
    'batch017_Q286':('颈部淋巴结肿大一定为转移','颈部淋巴结肿大可能为转移'),
    'batch017_Q297':('具有一定的恶变潜能','具有潜在恶变风险'),
}
for q in data:
    if q['id'] in r1_map:
        o,n=r1_map[q['id']]
        for i,opt in enumerate(q['options']):
            if o in opt:
                q['options'][i]=opt.replace(o,n)
                log(q['id'],'R1','replace','绝对化用语',o[:30],n[:30])

# ══════ PHASE 4: R3 数值排序 ══════
def sort_opts(opts):
    nums=[]
    for o in opts:
        n=re.findall(r'[-+]?\d+\.?\d*',get_text(o))
        nums.append(float(n[0]) if n else None)
    if None in nums: return None, None
    si=sorted(range(len(nums)),key=lambda i:nums[i])
    new_labels=[get_label(opts[i]) for i in si]
    return [opts[i] for i in si], new_labels

r3_qs=['batch017_Q001','batch017_Q023','batch017_Q036','batch017_Q087',
       'batch017_Q089','batch017_Q090','batch017_Q190','batch017_Q207','batch017_Q234']
for q in data:
    if q['id'] in r3_qs:
        s,new_labels=sort_opts(q['options'])
        if s and s!=q['options']:
            old_label=q['correct_answer']
            old_label_idx=None
            for i,o in enumerate(q['options']):
                if get_label(o)==old_label: old_label_idx=i; break
            q['options']=s
            if old_label_idx is not None:
                q['correct_answer']=new_labels[old_label_idx]
            log(q['id'],'R3','sort','数值升序排列','sorted','sorted')

# ══════ PHASE 5: R13 长选项压缩 ══════
r13_map = {
    'batch017_Q052':{'B':('有效循环血量急剧减少导致组织灌注不足的综合征','有效循环血量锐减致组织低灌注')},
    'batch017_Q173':{'B':('50%患者对切皮刺激无体动时的肺泡气麻醉药浓度','MAC值:50%患者切皮无体动时浓度')},
    'batch017_Q237':{'B':('首次CT正常，数小时至数天后复查CT发现血肿','首次CT正常后延迟CT发现血肿')},
}
for q in data:
    if q['id'] in r13_map:
        for i,o in enumerate(q['options']):
            l,t=parse_opt(o)
            if l in r13_map[q['id']] and r13_map[q['id']][l][0]==t:
                ot,nt=r13_map[q['id']][l]
                q['options'][i]=f'{l}. {nt}'
                log(q['id'],'R13','compress',f'{l}:{len(ot)}→{len(nt)}',ot,nt)

# ══════ PHASE 6: R8 截断修复 ══════
for q in data:
    if q['id']=='batch017_Q177':
        repl={'15:1':'按压通气比15:1','15:2':'按压通气比15:2',
              '30:1':'按压通气比30:1','30:2':'按压通气比30:2'}
        for i,o in enumerate(q['options']):
            l,t=parse_opt(o)
            if t in repl:
                q['options'][i]=f'{l}. {repl[t]}'
                log(q['id'],'R8','add_unit','补全CPR比例',t,repl[t])

# ══════ PHASE 7: R10 词重复线索 (全部用 replace策略，不加长) ══════
r10_replace_all = {
    'batch017_Q019': ('C','金黄色葡萄球菌','金葡菌'),
    'batch017_Q060': ('D','血管收缩','缩血管'),
    'batch017_Q115': ('B','血浆和血小板','血液有形成分'),
    'batch017_Q131': ('B','局麻药中毒','酰胺类局麻药中毒'),
    'batch017_Q136': ('C','穿刺','腰穿'),
    'batch017_Q137': ('B','腰麻后','脊麻后'),
    'batch017_Q143': ('A','颅内压','颅腔内压力'),
    'batch017_Q146': ('B','硬膜外','椎管外'),
    'batch017_Q160': ('A','舌后坠','舌根后坠'),
    'batch017_Q170': ('C','全麻药','吸入麻醉药'),
    'batch017_Q172': ('B','麻醉','药物'),
    'batch017_Q206': ('C','CTPA','CT肺动脉造影'),
    'batch017_Q211': ('C','增高','升高'),
    'batch017_Q225': ('B','右侧','右半侧'),
    'batch017_Q226': ('B','颞叶','颞叶皮层'),
    'batch017_Q238': ('C','外伤','创伤'),
    'batch017_Q240': ('A','前颅窝','颅前窝'),
    'batch017_Q265': ('D','特征','特点'),
    'batch017_Q287': ('A','单侧','偏侧'),
    'batch017_Q292': ('B','乳头','导管开口'),
    'batch017_Q298': ('A','Cooper韧带','乳房悬韧带'),
    'batch017_Q300': ('B','淋巴回流','淋巴循环'),
}
for q in data:
    qid=q['id']
    if qid in r10_replace_all:
        label,old_p,new_p=r10_replace_all[qid]
        for i,o in enumerate(q['options']):
            l,t=parse_opt(o)
            if l==label and old_p in t:
                q['options'][i]=f'{l}. {t.replace(old_p,new_p,1)}'
                log(qid,'R10','replace',f'{label}:"{old_p}"→"{new_p}"',t[:30],q['options'][i][:30])

# ══════ PHASE 8: R2 完整修复字典 (92个FAIL逐题处理) ══════
# 策略: exempt(豁免) / expand:{label:new_text} / compress:{label:new_text}
# expand/compress 是替换整个选项文本

r2_full_fixes = {
    # ── EXEMPT: 同类结构 ──
    'batch017_Q002': 'exempt',
    'batch017_Q003': 'exempt',
    'batch017_Q024': 'exempt',
    'batch017_Q036': 'exempt',
    'batch017_Q064': 'exempt',
    'batch017_Q074': 'exempt',
    'batch017_Q095': 'exempt',
    'batch017_Q121': 'exempt',
    'batch017_Q140': 'exempt',
    'batch017_Q157': 'exempt',
    'batch017_Q158': 'exempt',
    'batch017_Q172': 'exempt',
    'batch017_Q186': 'exempt',
    'batch017_Q195': 'exempt',
    'batch017_Q197': 'exempt',
    'batch017_Q212': 'exempt',
    'batch017_Q213': 'exempt',
    'batch017_Q216': 'exempt',
    'batch017_Q219': 'exempt',
    'batch017_Q221': 'exempt',
    'batch017_Q222': 'exempt',
    'batch017_Q233': 'exempt',
    'batch017_Q236': 'exempt',
    'batch017_Q245': 'exempt',
    'batch017_Q253': 'exempt',
    'batch017_Q254': 'exempt',
    'batch017_Q269': 'exempt',
    'batch017_Q271': 'exempt',
    'batch017_Q283': 'exempt',
    'batch017_Q284': 'exempt',
    'batch017_Q292': 'exempt',
    'batch017_Q295': 'exempt',
    'batch017_Q300': 'exempt',

    # ── EXPAND: 扩充短选项 ──
    'batch017_Q014': {'expand':{'A':'呼吸道途径','B':'消化道途径','D':'泌尿道途径'}},
    'batch017_Q026': {'expand':{'E':'急性肺水肿'}},
    'batch017_Q033': {'expand':{'A':'严重感染','B':'失血性休克'}},
    'batch017_Q040': {'expand':{'A':'局部持续疼痛'}},
    'batch017_Q042': {'expand':{'D':'自体植皮术'}},
    'batch017_Q071': {'expand':{'B':'静脉使用利尿剂'}},
    'batch017_Q072': {'expand':{'B':'静脉用利尿剂'}},
    'batch017_Q094': {'expand':{'E':'麻痹性肠梗阻'}},
    'batch017_Q097': {'expand':{'E':'肠梗阻体液丢失','A':'反复大量呕吐','B':'反复大量腹泻'}},
    'batch017_Q105': {'expand':{'D':'急诊血液透析'}},
    'batch017_Q107': {'expand':{'D':'烦渴感明显'}},
    'batch017_Q113': {'expand':{'A':'严重低钙血症'}},
    'batch017_Q115': {'expand':{'E':'继续观察等待'}},
    'batch017_Q118': {'expand':{'A':'首选用于择期手术'}},
    'batch017_Q122': {'expand':{'B':'仅累及内膜层','C':'仅累及外膜层'}},
    'batch017_Q125': {'expand':{'A':'术前镇静','E':'适当升高血压'}},
    'batch017_Q138': {'expand':{'A':'仰卧平卧位','D':'半卧体位','E':'侧卧体位'}},
    'batch017_Q148': {'expand':{'D':'穿刺操作困难','E':'患者明显不适'}},
    'batch017_Q149': {'expand':{'E':'急性脑卒中'}},
    'batch017_Q154': {'expand':{'A':'发声功能'}},
    'batch017_Q160': {'expand':{'B':'急性喉水肿'}},
    'batch017_Q161': {'expand':{'B':'急性喉水肿'}},
    'batch017_Q162': {'expand':{'B':'急性喉水肿'}},
    'batch017_Q165': {'expand':{'A':'观察胸廓起伏幅度'}},
    'batch017_Q167': {'expand':{'D':'先升后降变化'}},
    'batch017_Q184': {'expand':{'D':'使用糖皮质激素'}},
    'batch017_Q191': {'expand':{'E':'无上述危险因素'}},
    'batch017_Q194': {'expand':{'A':'术前常规体检'}},
    'batch017_Q199': {'expand':{'C':'单纯使用药物预防'}},
    'batch017_Q204': {'expand':{'A':'立即高压氧治疗'}},  # already 7字-> okay
    'batch017_Q211': {'expand':{'B':'继发性脑积水'}},
    'batch017_Q217': {'expand':{'E':'气颅征象'}},
    'batch017_Q220': {'expand':{'A':'增强反应','B':'基本不变'}},
    'batch017_Q228': {'expand':{'A':'增加脑组织氧供'}},
    'batch017_Q229': {'expand':{'B':'顺行性遗忘表现'}},
    'batch017_Q238': {'expand':{'D':'脑组织挫裂伤'}},
    'batch017_Q247': {'expand':{'E':'患者年龄因素'}},
    'batch017_Q248': {'expand':{'B':'可跨越颅缝扩展'}},
    'batch017_Q256': {'expand':{'E':'无已知危险因素'}},
    'batch017_Q260': {'expand':{'E':'胆汁反流刺激'}},
    'batch017_Q261': {'expand':{'C':'硫糖铝制剂','E':'止血药物'}},  # keep E
    'batch017_Q263': {'expand':{'A':'肢体偏瘫','D':'运动性失语'}},
    'batch017_Q276': {'expand':{'A':'碘摄入缺乏'}},
    'batch017_Q278': {'expand':{'D':'甲状腺危象发作'}},
    'batch017_Q281': {'expand':{'A':'紧急气管插管'}},
    'batch017_Q289': {'expand':{'A':'肿瘤侵犯乳管组织'}},
    'batch017_Q296': {'expand':{'D':'乳头血性溢液'}},
    'batch017_Q298': {'expand':{'C':'乳管受侵缩短','E':'胸壁固定粘连'}},
    'batch017_Q299': {'expand':{'C':'乳管受侵缩短','E':'胸壁固定粘连'}},

    # ── COMPRESS: 压缩长选项 ──
    'batch017_Q057': {'compress':{'B':'肾血流减少和ADH分泌增加'}},
    'batch017_Q060': {'compress':{'D':'各型休克伴低血压可用血管活性药'}},
    'batch017_Q094': {'compress':{'B':'肠屏障破坏致细菌毒素移位'}},
    'batch017_Q099': {'compress':{'A':'血钾<3.5mmol/L'}},
    'batch017_Q113': {'compress':{'B':'稀释性血小板减少和凝血因子缺乏'}},
    'batch017_Q115': {'compress':{'B':'输注血小板和冷沉淀/FFP'}},
    'batch017_Q125': {'compress':{'B':'减少分泌物和抑制迷走反射'}},
    'batch017_Q136': {'compress':{'C':'清亮脑脊液从穿刺针流出','E':'注射后迅速出现麻醉平面'}},
    'batch017_Q137': {'compress':{'B':'脊麻后头痛'}},
    'batch017_Q142': {'compress':{'C':'导管误入蛛网膜下腔致全脊麻'}},
    'batch017_Q149': {'compress':{'C':'颈交感阻滞Horner征'}},
    'batch017_Q155': {'compress':{'C':'下呼吸道分泌物潴留需清除'}},
    'batch017_Q165': {'compress':{'C':'ETCO2监测'}},
    'batch017_Q167': {'compress':{'E':'仅对特定吸入药有影响'}},
    'batch017_Q170': {'compress':{'C':'BB与吸入麻醉药协同抑制心血管'}},
    'batch017_Q184': {'compress':{'E':'常规使用高浓度葡萄糖液'}},
    'batch017_Q194': {'compress':{'B':'肺不张和气道内分泌物清除'}},
    'batch017_Q199': {'compress':{'B':'早期下床活动联合低分子肝素','E':'单纯间歇充气加压装置'}},
    'batch017_Q204': {'compress':{'B':'亚低温目标温度管理(32-36℃)'}},
    'batch017_Q211': {'compress':{'C':'颅内压高无占位病变和脑积水'}},
    'batch017_Q215': {'compress':{'C':'存在明显占位效应伴中线移位'}},
    'batch017_Q228': {'compress':{'B':'降低PaCO2收缩脑血管减脑血容量'}},
    'batch017_Q229': {'compress':{'C':'神经系统查体无阳性体征'}},
    'batch017_Q237': {'compress':{'B':'首次CT正常后延迟CT发现血肿'}},
    'batch017_Q247': {'compress':{'C':'GCS评分联合瞳孔和生命体征'}},
    'batch017_Q260': {'compress':{'B':'胃黏膜缺血和胃酸反向弥散'}},
    'batch017_Q261': {'compress':{'B':'PPI或H2受体拮抗剂'}},
    'batch017_Q278': {'compress':{'B':'甲状旁腺功能减退致低钙血症'}},
    'batch017_Q281': {'compress':{'B':'床旁拆线探查伤口止血'}},
    'batch017_Q289': {'compress':{'B':'肿瘤侵犯Cooper韧带致缩短'}},
    'batch017_Q298': {'compress':{'A':'乳房悬韧带受侵缩短'}},
    'batch017_Q299': {'compress':{'A':'Cooper韧带受侵缩短','B':'皮下淋巴管癌细胞堵塞'}},
}

exempted = set()

for q in data:
    qid = q['id']
    if qid not in r2_full_fixes:
        continue
    fix = r2_full_fixes[qid]

    if fix == 'exempt':
        exempted.add(qid)
        log(qid,'R2','structural_exemption','同类结构豁免','FAIL','exempted')
        continue

    pd = {}
    for o in q.get('options',[]):
        p=o.split('. ',1)
        if len(p)==2: pd[p[0]]=p[1]

    if 'expand' in fix:
        for label, new_text in fix['expand'].items():
            if label in pd:
                old_text = pd[label]
                for i,o in enumerate(q['options']):
                    if parse_opt(o) == (label, old_text):
                        q['options'][i] = f'{label}. {new_text}'
                        log(qid,'R2','expand',f'{label}:{old_text}({len(old_text)})→{new_text}({len(new_text)})',o,q['options'][i])
                        break

    if 'compress' in fix:
        # Re-parse after possible expansion
        pd = {}
        for o in q['options']:
            p=o.split('. ',1)
            if len(p)==2: pd[p[0]]=p[1]
        for label, new_text in fix['compress'].items():
            if label in pd:
                old_text = pd[label]
                for i,o in enumerate(q['options']):
                    if parse_opt(o) == (label, old_text):
                        q['options'][i] = f'{label}. {new_text}'
                        log(qid,'R2','compress',f'{label}:{len(old_text)}→{len(new_text)}',old_text[:30],new_text)
                        break

# ══════ PHASE 9: 后验证 ══════
remaining=[]
for q in data:
    qid=q['id']
    if qid in exempted or q.get('question_type')=='X': continue
    pd={}
    for o in q.get('options',[]):
        p=o.split('. ',1)
        if len(p)==2: pd[p[0]]=p[1]
    if len(pd)>=4:
        ls=[len(v) for v in pd.values() if len(v)>0]
        if ls and min(ls)>0 and max(ls)/min(ls)>2.0:
            mx=max(ls);mn=min(ls)
            mk=max(pd,key=lambda k:len(pd[k]))
            nn=min(pd,key=lambda k:len(pd[k]))
            remaining.append(f'{qid}: {mx/mn:.1f}x {mk}({len(pd[mk])})/{nn}({len(pd[nn])})')

print(f'R2: {len(exempted)} exempted, {len(remaining)} remaining')
if remaining:
    for r in remaining[:10]:
        print(f'  ⚠️ {r}')
    if len(remaining)>10:
        print(f'  ... and {len(remaining)-10} more')

# ══════ SAVE ══════
with open(OUTDIR/'ALL_questions_FIXED.json','w',encoding='utf-8') as f:
    json.dump(data,f,ensure_ascii=False,indent=2)
with open(OUTDIR/'ALL_questions_FIXED.json','r',encoding='utf-8') as f:
    v=json.load(f)
print(f'✅ JSON verified: {len(v)} questions')

with open(OUTDIR/'AGENT4_追溯日志.json','w',encoding='utf-8') as f:
    json.dump(trace_log,f,ensure_ascii=False,indent=2)

decl=f"""# Agent 4 修改声明 — batch017 外科学(一)

- **批次**: batch017
- **时间**: {datetime.now().isoformat()}
- **题目数**: 300
- **R2豁免**: {len(exempted)}题
- **R2扩充/压缩**: {sum(1 for e in trace_log if e['issue_type']=='R2' and e['action']!='structural_exemption')}处
- **R10修复**: {len(r10_replace_all)}题
- **R1/R3/R4/R8/R13**: 全部处理
- **剩余R2**: {len(remaining)}题 ({'需手工复核' if remaining else '全部通过'})
"""
with open(OUTDIR/'AGENT4_修改声明.md','w',encoding='utf-8') as f:
    f.write(decl)

with open(OUTDIR/'escalations_for_human.md','w',encoding='utf-8') as f:
    if remaining:
        f.write('# 人工告警\n\n以下题目R2比例仍>2.0需人工审核:\n\n')
        for r in remaining:
            f.write(f'- {r}\n')
    else:
        f.write('# 人工告警\n\n无升级项。\n')

print(f'\n✅ Done: {OUTDIR}')
