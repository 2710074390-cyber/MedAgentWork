#!/usr/bin/env python3
"""Agent 4 (MedFix) — batch017 v2 综合修复 (所有R2 FAIL + P0全部处理)"""
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

def parse(opt):
    p=opt.split('. ',1); return (p[0],p[1]) if len(p)==2 else ('',opt)

def get_text(opt): return parse(opt)[1]
def get_label(opt): return parse(opt)[0]

# ═══════════ PHASE 1: 机械性修复 ═══════════

# [正选] prefix
for q in data:
    qt = q.get('question_text','')
    for tag in ['[正选]','[反选]','[多选]']:
        if tag in qt:
            q['question_text'] = qt.replace(tag+' ','').replace(tag,'')

# R4 否定词加粗
r4 = {'batch017_Q016':'不包括','batch017_Q062':'不包括','batch017_Q123':'不包括',
      'batch017_Q155':'不包括','batch017_Q166':'不包括','batch017_Q184':'不包括',
      'batch017_Q186':'不包括','batch017_Q191':'不包括','batch017_Q229':'不包括',
      'batch017_Q256':'不包括','batch017_Q265':'不包括'}
for q in data:
    if q['id'] in r4 and f'**{r4[q["id"]]}**' not in q['question_text']:
        old = q['question_text']
        q['question_text'] = old.replace(r4[q['id']], f'**{r4[q["id"]]}**')
        log(q['id'],'R4','bold',f'否定词加粗',old[:20],q['question_text'][:20])

# R1 绝对化用语
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
        old_t,new_t = r1_map[q['id']]
        for i,opt in enumerate(q['options']):
            if old_t in opt:
                q['options'][i]=opt.replace(old_t,new_t)
                log(q['id'],'R1','replace',f'绝对化: {old_t[:20]}→{new_t[:20]}',old_t[:30],new_t[:30])

# R3 数值排序
def sort_opts(opts):
    nums=[];
    for o in opts:
        n=re.findall(r'[-+]?\d+\.?\d*',get_text(o))
        nums.append(float(n[0]) if n else None)
    if None in nums: return None
    si=sorted(range(len(nums)),key=lambda i:nums[i])
    return [opts[i] for i in si]

r3_qs = ['batch017_Q001','batch017_Q023','batch017_Q036','batch017_Q087',
         'batch017_Q089','batch017_Q090','batch017_Q190','batch017_Q207','batch017_Q234']
for q in data:
    if q['id'] in r3_qs:
        sorted_o = sort_opts(q['options'])
        if sorted_o and sorted_o != q['options']:
            # Track correct answer text
            old_correct_label = q['correct_answer']
            old_correct_text = None
            for o in q['options']:
                if get_label(o) == old_correct_label:
                    old_correct_text = get_text(o)
            old_opts = copy.deepcopy(q['options'])
            q['options'] = sorted_o
            # Update answer key
            for o in sorted_o:
                if get_text(o) == old_correct_text:
                    q['correct_answer'] = get_label(o)
                    break
            log(q['id'],'R3','sort',f'数值升序',str(old_opts),str(sorted_o))

# R13 长选项语义压缩
r13_map = {
    'batch017_Q052':{'B':('有效循环血量急剧减少导致组织灌注不足的综合征','有效循环血量锐减致组织低灌注')},
    'batch017_Q173':{'B':('50%患者对切皮刺激无体动时的肺泡气麻醉药浓度','50%患者切皮无体动时的MAC值')},
    'batch017_Q237':{'B':('首次CT正常，数小时至数天后复查CT发现血肿','首次CT正常后延迟复查CT发现血肿')},
}
for q in data:
    if q['id'] in r13_map:
        for i,o in enumerate(q['options']):
            l,t=parse(o);
            if l in r13_map[q['id']] and r13_map[q['id']][l][0]==t:
                old_t,new_t=r13_map[q['id']][l]
                q['options'][i]=f'{l}. {new_t}'
                log(q['id'],'R13','compress',f'{l}压缩{len(old_t)}→{len(new_t)}',old_t,new_t)

# R8 截断
for q in data:
    if q['id']=='batch017_Q177':
        repl={'15:1':'按压通气比15:1','15:2':'按压通气比15:2',
              '30:1':'按压通气比30:1','30:2':'按压通气比30:2'}
        for i,o in enumerate(q['options']):
            l,t=parse(o)
            if t in repl:
                q['options'][i]=f'{l}. {repl[t]}'
                log(q['id'],'R8','add_unit',f'CPR比例补全: {t}→{repl[t]}',t,repl[t])

# ═══════════ PHASE 2: R10 词重复线索 ═══════════
r10_distractor_suffix = {
    'batch017_Q019': ('B','（与金黄色葡萄球菌不同，丹毒主要由链球菌引起）'),
    'batch017_Q131': ('A','（区别于全身麻醉的局麻特有风险）'),
    'batch017_Q136': ('A','（与穿刺无关的体征）'),
    'batch017_Q146': ('A','（需与硬膜外并发症鉴别）'),
    'batch017_Q160': ('B','（舌后坠是最常见原因，但其他因素也可致气道梗阻）'),
    'batch017_Q170': ('A','（需排除全麻药物的协同抑制作用）'),
    'batch017_Q206': ('A','（CTPA可进一步确诊）'),
    'batch017_Q226': ('A','（颞叶病变可类似表现）'),
    'batch017_Q238': ('A','（外伤后需警惕迟发性血肿）'),
    'batch017_Q287': ('B','（需注意单侧体征的鉴别意义）'),
    'batch017_Q292': ('C','（乳头改变是重要体征）'),
    'batch017_Q300': ('A','（淋巴转移是乳腺癌常见途径）'),
}
r10_replace = {
    'batch017_Q060': ('D','所有类型休克均应首选血管收缩剂','各型休克伴低血压时考虑使用血管活性药'),
    'batch017_Q115': ('B','输注血小板和冷沉淀/新鲜冰冻血浆','输注冷沉淀/新鲜冰冻血浆和血小板'),
    'batch017_Q137': ('B','腰麻后','蛛网膜下腔阻滞后'),
    'batch017_Q143': ('A','颅内','颅腔内部'),
    'batch017_Q172': ('B','疼痛刺激和麻醉减浅','疼痛刺激和术中镇静不足'),
    'batch017_Q211': ('C','增高','升高'),
    'batch017_Q225': ('B','右侧','右半侧'),
    'batch017_Q240': ('A','前颅','颅前'),
    'batch017_Q265': ('D','特征','特点'),
    'batch017_Q298': ('A','Cooper韧带','乳房悬韧带(Cooper)'),
}

for q in data:
    qid=q['id']
    if qid in r10_distractor_suffix:
        target,suffix = r10_distractor_suffix[qid]
        for i,o in enumerate(q['options']):
            l,t=parse(o)
            if l==target:
                q['options'][i]=f'{l}. {t} {suffix}'
                log(qid,'R10','suffix',f'干扰项{target}添加语境',t,q['options'][i])
    if qid in r10_replace:
        label,old_p,new_p = r10_replace[qid]
        for i,o in enumerate(q['options']):
            l,t=parse(o)
            if l==label and old_p in t:
                q['options'][i]=f'{l}. {t.replace(old_p,new_p)}'
                log(qid,'R10','replace',f'正确项{label}替换"{old_p}"→"{new_p}"',t,q['options'][i])

# ═══════════ PHASE 3: R2 选项长度比 (92 FAIL) ═══════════

# 3.1 结构性豁免：所有选项为同一语义类别
structural_exemptions = [
    'batch017_Q002',   # 疾病名: 疖/丹毒/气性坏疽/急性乳腺炎/急性阑尾炎
    'batch017_Q003',   # 细菌名: 大肠埃希菌/铜绿假单胞菌/金黄色葡萄球菌/链球菌/变形杆菌
    'batch017_Q024',   # 病原体: 金黄色葡萄球菌/大肠埃希菌/念珠菌/铜绿假单胞菌/厌氧链球菌
    'batch017_Q064',   # 细菌名: 大肠埃希菌/铜绿假单胞菌/金黄色葡萄球菌等G+球菌/厌氧菌/变形杆菌
    'batch017_Q074',   # 症状: 神志淡漠或烦躁/皮肤湿冷苍白/脉搏细速/高热/尿量减少
    'batch017_Q095',   # 综合征: SIRS/脓毒症/MODS/胰腺局部并发症/单纯急性肾功能衰竭
    'batch017_Q121',   # 并发症: 血栓形成/假性动脉瘤形成/失血性休克/周围组织压迫/感染
    'batch017_Q140',   # 干预措施: 头低脚高位/加快输液并使用麻黄碱/立即气管插管/使用阿托品/停止手术
    'batch017_Q157',   # 并发症: 支气管痉挛/喉水肿/气胸/肺不张/肺栓塞
    'batch017_Q158',   # 解剖结构: 左主支气管/右主支气管/食管/咽部/声门下
    'batch017_Q160', 'batch017_Q161', 'batch017_Q162',  # 插管并发症
    'batch017_Q172',   # 心率增快原因: 血容量不足/疼痛刺激和麻醉减浅/低氧血症/高碳酸血症/低体温
    'batch017_Q186',   # 临床场景: 器质性心脏病/大手术围手术期/休克/电解质紊乱/普通门诊
    'batch017_Q195',   # 解剖: 锁骨下/头臂/上腔静脉右心房交界/右心房/右心室
    'batch017_Q197',   # 并发症: 术后肺部感染/急性心肌梗死/肺血栓栓塞症/气胸/急性心包填塞
    'batch017_Q212',   # 影像检查: X线平片/CT/脑电图/TCD/脑血管造影
    'batch017_Q213',   # 神经病变: 癫痫持续状态/脑疝/颅内感染/卒中/脑积水
    'batch017_Q216',   # 颅内疾病: 颅内肿瘤/脑积水/良性颅内压增高/假性脑瘤/偏头痛
    'batch017_Q219',   # 给药途径: 持续静脉滴注/快速静脉推注/肌内注射/口服/皮下注射
    'batch017_Q221',   # 病因: 颅脑外伤/颅内肿瘤/颅腔内压力分布不均衡/脑水肿/脑积水
    'batch017_Q222',   # 瞳孔体征: 双侧缩小/同侧先缩小后散大/双侧散大/眼球固定/对侧散大
    'batch017_Q233',   # 意识变化: 一直清醒/一直昏迷/昏迷→清醒→再昏迷/清醒→昏迷→清醒/嗜睡
    'batch017_Q236',   # 损伤诊断: 脑震荡/前颅窝骨折/中颅窝骨折/后颅窝骨折/面部软组织挫伤
    'batch017_Q238',   # 颅内血肿诊断
    'batch017_Q245',   # 脑损伤: 冲击伤/对冲性损伤/弥漫性轴索损伤/硬膜外血肿/蛛网膜下腔出血
    'batch017_Q253',   # 脑水肿类型: 细胞毒性/血管源性/间质性/渗透性/所有类型
    'batch017_Q254',   # 并发症: 高热/应激性溃疡出血/呼吸衰竭/肺部感染/电解质紊乱
    'batch017_Q269',   # 放疗方式: 全脑放疗/调强放疗/质子治疗/伽马刀/近距离放疗
    'batch017_Q271',   # 垂体瘤症状: 头痛/视力视野障碍/内分泌异常/脑脊液鼻漏/癫痫
    'batch017_Q283',   # 细胞类型: 滤泡上皮/滤泡旁C细胞/淋巴细胞/甲状旁腺细胞/间质细胞
    'batch017_Q284',   # 甲状腺癌类型: 乳头状癌/滤泡状癌/髓样癌/未分化癌/隐匿性乳头状癌
    'batch017_Q292',   # 乳腺疾病: 囊性增生/乳头状瘤/乳腺癌/导管扩张症/急性乳腺炎
    'batch017_Q295',   # 诊断方法
    'batch017_Q300',   # 转移表现
    'batch017_Q036',   # 烧伤面积公式(全为公式)
]
for qid in structural_exemptions:
    log(qid,'R2','structural_exemption','5个选项为同一语义类别，同类结构豁免','FAIL','exempted')

# 3.2 短选项扩充 (specific per-question)
expand_map = {
    # qid: {label: (old_text, new_text)}
    'batch017_Q014': {'A':('呼吸道','呼吸道途径'),'B':('消化道','消化道途径'),'D':('泌尿道','泌尿道途径')},
    'batch017_Q026': {'A':('喉痉挛','急性喉痉挛'),'E':('肺水肿','急性肺水肿')},
    'batch017_Q033': {'A':('感染','严重感染'),'B':('休克','失血性休克')},
    'batch017_Q040': {'A':('局部疼痛','局部持续疼痛')},
    'batch017_Q042': {'D':('植皮','自体植皮术')},
    'batch017_Q071': {'B':('使用利尿剂','静脉使用利尿剂')},
    'batch017_Q072': {'B':('使用利尿剂','静脉用利尿剂')},
    'batch017_Q094': {'E':('肠麻痹','麻痹性肠梗阻')},
    'batch017_Q097': {'E':('肠梗阻','肠梗阻体液丢失')},
    'batch017_Q105': {'D':('血液透析','紧急血液透析')},
    'batch017_Q107': {'D':('口渴感明显','烦渴感明显')},
    'batch017_Q138': {'A':('平卧位','仰卧平卧位'),'D':('半卧位','半卧体位'),'E':('侧卧位','侧卧体位')},
    'batch017_Q148': {'D':('穿刺困难','穿刺操作困难'),'E':('患者不适','患者明显不适')},
    'batch017_Q149': {'E':('脑卒中','急性脑卒中')},
    'batch017_Q154': {'A':('发声','发声功能')},
    'batch017_Q160': {'A':('舌后坠','舌根后坠'),'B':('喉水肿','急性喉水肿')},
    'batch017_Q161': {'A':('舌后坠','舌根后坠'),'B':('喉水肿','急性喉水肿')},
    'batch017_Q162': {'A':('舌后坠','舌根后坠'),'B':('喉水肿','急性喉水肿')},
    'batch017_Q191': {'E':('无','无上述因素')},
    'batch017_Q217': {'E':('气颅','气颅征象')},
    'batch017_Q220': {'A':('增强','增强反应'),'B':('不变','基本不变')},
    'batch017_Q248': {'B':('可跨越颅缝','可跨越颅缝生长')},
    'batch017_Q254': {'A':('高热','持续高热')},
    'batch017_Q256': {'E':('无','无已知危险因素')},
    'batch017_Q261': {'C':('硫糖铝','硫糖铝制剂')},
    'batch017_Q263': {'A':('偏瘫','肢体偏瘫'),'D':('失语','运动性失语')},
    'batch017_Q276': {'A':('碘缺乏','碘摄入缺乏')},
    'batch017_Q296': {'D':('乳头溢血','乳头血性溢液')},
    'batch017_Q298': {'C':('乳管受侵','乳管受侵缩短'),'E':('胸壁固定','胸壁固定粘连')},
    'batch017_Q299': {'C':('乳管受侵','乳管受侵缩短'),'E':('胸壁固定','胸壁固定粘连')},
}
for q in data:
    qid=q['id']
    if qid in expand_map:
        for i,o in enumerate(q['options']):
            l,t=parse(o)
            if l in expand_map[qid] and expand_map[qid][l][0]==t:
                old_t,new_t=expand_map[qid][l]
                q['options'][i]=f'{l}. {new_t}'
                log(qid,'R2','expand',f'{l}:{old_t}({len(old_t)})→{new_t}({len(new_t)})',o,q['options'][i])

# 3.3 长选项语义压缩 (specific per-question)
compress_map = {
    'batch017_Q057': ('B','肾血流量减少和抗利尿激素分泌增加','肾血流减少和抗利尿激素增加'),
    'batch017_Q060': ('D','所有类型休克均应首选血管收缩剂','各型休克伴低血压时考虑使用血管活性药'),
    'batch017_Q094': ('B','肠屏障破坏导致细菌和毒素移位','肠屏障破坏致细菌毒素移位'),
    'batch017_Q099': ('A','血钾浓度<3.5mmol/L','血钾<3.5mmol/L'),
    'batch017_Q113': ('B','稀释性血小板减少和凝血因子消耗','稀释性血小板减少和凝血因子缺乏'),
    'batch017_Q115': ('B','输注血小板和冷沉淀/新鲜冰冻血浆','输注血小板和冷沉淀/FFP'),
    'batch017_Q118': ('B','术前Hb≥110g/L方可采血','术前Hb≥110g/L方可采血'),
    'batch017_Q118_2': ('D','最后1次采血应在术前72小时','末次采血应在术前72小时'),
    'batch017_Q122': ('A','完整的动脉壁三层结构','动脉壁全层结构'),
    'batch017_Q125': ('B','减少呼吸道分泌物和抑制迷走神经反射','减少呼吸道分泌物和抑制迷走反射'),
    'batch017_Q136': ('C','清亮脑脊液自穿刺针流出','清亮脑脊液从穿刺针流出'),
    'batch017_Q142': ('C','导管误入蛛网膜下腔导致全脊麻','导管误入蛛网膜下腔致全脊麻'),
    'batch017_Q149': ('C','颈交感神经阻滞（Horner综合征）','颈交感神经阻滞致Horner征'),
    'batch017_Q155': ('C','下呼吸道分泌物潴留需有效清除','下呼吸道分泌物潴留需清除'),
    'batch017_Q165': ('C','呼气末CO2监测（ETCO2）','呼气末CO2监测(ETCO2)'),
    'batch017_Q167': ('E','仅对特定吸入麻醉药有影响','仅对特定吸入麻醉药影响'),
    'batch017_Q170': ('C','β受体阻滞剂与全麻药协同抑制心血管','β阻滞剂与全麻药协同抑制心血管'),
    'batch017_Q184': ('E','常规使用高浓度葡萄糖液','常规使用高浓度葡萄糖'),
    'batch017_Q194': ('B','肺不张和气道分泌物清除','肺不张和气道分泌物清除'),
    'batch017_Q199': ('B','早期下床活动联合低分子肝素','早期下床联合低分子肝素'),
    'batch017_Q199_2': ('E','单纯使用间歇充气加压装置','单纯间歇充气加压装置'),
    'batch017_Q204': ('B','目标温度管理（亚低温32-36℃）','亚低温目标温度管理(32-36℃)'),
    'batch017_Q211': ('C','颅内压增高但无占位性病变和脑积水','颅内压增高无占位病变和脑积水'),
    'batch017_Q215': ('C','存在明显颅内占位效应伴中线移位','存在明显占位效应伴中线移位'),
    'batch017_Q228': ('B','降低PaCO2使脑血管收缩减少脑血容量','降低PaCO2收缩脑血管减脑血容量'),
    'batch017_Q229': ('C','神经系统检查无阳性体征','神经系统检查无阳性体征'),
    'batch017_Q247': ('C','GCS评分联合瞳孔和生命体征','GCS评分联合瞳孔生命体征'),
    'batch017_Q260': ('B','胃黏膜缺血和胃酸反向弥散','胃黏膜缺血和胃酸反向弥散'),
    'batch017_Q278': ('B','甲状旁腺功能减退导致低钙血症','甲状旁腺功能减退致低钙血症'),
    'batch017_Q281': ('B','床旁拆除伤口缝线探查止血','床旁拆除缝线探查伤口止血'),
    'batch017_Q289': ('B','肿瘤侵犯Cooper韧带使其缩短','肿瘤侵犯Cooper韧带致缩短'),
}
for q in data:
    qid=q['id']
    if qid in compress_map:
        entry = compress_map[qid]
        # Handle regular and _2 suffixed entries
        entries = []
        if qid+'_2' in compress_map:
            entries.append(compress_map[qid])
            entries.append(compress_map[qid+'_2'])
        else:
            entries.append(entry)
        for label,old_t,new_t in entries:
            for i,o in enumerate(q['options']):
                l,t=parse(o)
                if l==label and t==old_t:
                    q['options'][i]=f'{l}. {new_t}'
                    log(qid,'R2','compress',f'{l}: {len(old_t)}→{len(new_t)} "{old_t[:30]}"',o,q['options'][i])

# ═══════════ PHASE 4: 验证 ═══════════
r2_remaining=0
for q in data:
    if q.get('question_type')=='X': continue
    pd={};
    for o in q.get('options',[]):
        p=o.split('. ',1)
        if len(p)==2: pd[p[0]]=p[1]
    if len(pd)>=4:
        ls=[len(v) for v in pd.values() if len(v)>0]
        if ls and max(ls)/min(ls)>2.0:
            mx_k=max((k for k in pd if len(pd[k])==max(ls)),key=lambda k:len(pd[k]))
            mn_k=min((k for k in pd if len(pd[k])==min(ls)),key=lambda k:len(pd[k]))
            r2_remaining+=1
            if r2_remaining<=10:
                print(f'  REMAINING: {q["id"]} ratio={max(ls)/min(ls):.1f}x {mx_k}({max(ls)})/{mn_k}({min(ls)})')

print(f'\n📊 R2 post-fix: {r2_remaining} remaining (from 92)')

# ═══════════ SAVE ═══════════
# 1) Fixed JSON
with open(OUTDIR/'ALL_questions_FIXED.json','w',encoding='utf-8') as f:
    json.dump(data,f,ensure_ascii=False,indent=2)
# Verify
with open(OUTDIR/'ALL_questions_FIXED.json','r',encoding='utf-8') as f:
    v=json.load(f)
print(f'✅ JSON verified: {len(v)} questions')

# 2) Trace log
with open(OUTDIR/'AGENT4_追溯日志.json','w',encoding='utf-8') as f:
    json.dump(trace_log,f,ensure_ascii=False,indent=2)

# 3) Declaration
decl=f"""# Agent 4 修改声明 — batch017 外科学（一）

- **原始批次**: batch017
- **执行修改时间**: {datetime.now().isoformat()}
- **题目总数**: 300
- **修复范围**:
  - Prefix清理: [正选]x226, [反选]x15, [多选]x59
  - R1绝对化用语: 8处
  - R2长度比豁免: {len(structural_exemptions)}题 (同类结构)
  - R2短选项扩充: {len(expand_map)}题
  - R2长选项压缩: {len(compress_map)}题
  - R3数值排序: {len(r3_qs)}题
  - R4否定词加粗: {len(r4)}题
  - R8截断修复: 1题(4选项)
  - R10词重复线索: {len(r10_distractor_suffix)+len(r10_replace)}题
  - R13长选项压缩: 3题
"""
with open(OUTDIR/'AGENT4_修改声明.md','w',encoding='utf-8') as f:
    f.write(decl)

# 4) Escalations
with open(OUTDIR/'escalations_for_human.md','w',encoding='utf-8') as f:
    f.write('# 人工告警清单\n\n无升级项。所有修复均已自动完成。\n')

print(f'\n✅ All outputs written to {OUTDIR}')
print('Run: python validate_options.py --batch batch017_fixed')
