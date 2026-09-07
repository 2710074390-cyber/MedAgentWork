# -*- coding: utf-8 -*-
"""fix_pass_v3: batch035 第三轮修复
1. 备份 ALL_questions_FIXED.json -> _bak_FIXED_v2.json
2. R13 x3 / R10 x5 / R2 x20 定向改写
3. M6-A1-008 重写为"淹溺程度分类"题（消除与 M4-A1-003 重复），撤其 GS-2023-041 标注
4. kaoyan 标注：撤销 7 条考点不符（M8-A1-001、M9-A1-001~006）
5. kaoyan 补标 16 条（全部经逐对核对 stem/options/answer/explanation 考点一致；mode=改编）
6. 自验：配额不变、kaoyan 计数=34、全部标注题解析含 [源:考研真题 GS-XXX]
"""
import json, shutil, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SRC = r'C:\Users\38063\Desktop\MedAgentWork\中间产物\batch035\ALL_questions_FIXED.json'
BAK = r'C:\Users\38063\Desktop\MedAgentWork\中间产物\batch035\_bak_FIXED_v2.json'

shutil.copy2(SRC, BAK)
print('备份 ->', BAK)

data = json.load(open(SRC, encoding='utf-8'))
byid = {q['id']: q for q in data}

def opts_dict(q):
    return {o['label']: o['text'] for o in q['options']}

def set_opts(q, newopts):
    """newopts: dict label->text，按 A..E 顺序写回"""
    labels = sorted(newopts.keys())
    q['options'] = [{'label': l, 'text': newopts[l]} for l in labels]
    q['option_polarities'] = {l: (l == q.get('answer')) for l in labels}

n_fail = 0

def fix_opts(qid, newopts):
    global n_fail
    q = byid.get(qid)
    if q is None:
        print('!! 未找到', qid); n_fail += 1; return
    set_opts(q, newopts)
    print('OK 选项改写', qid)

def fix_stem(qid, newstem):
    global n_fail
    q = byid.get(qid)
    if q is None:
        print('!! 未找到', qid); n_fail += 1; return
    q['stem'] = newstem
    print('OK 题干改写', qid)

# ---------------- R13 x3 ----------------
# M5-A1-003 心源性休克血流动力学：全组去单位（R9 不含 CI/PAWP，安全）
fix_opts('batch031-M5-A1-003', {
    'A': 'CI<1.5，PAWP<8',
    'B': 'CI<2.2，PAWP>18',
    'C': 'CI2.5~4，PAWP12~18',
    'D': 'CI>4.0，PAWP<10',
    'E': 'CI正常，PAWP>25',
})
# M8-A2-005 孕妇CPR：E 选项 21字 -> 19字（选项含义不变，仍为错误干扰项）
fix_opts('batch035-M8-A2-005', {
    'A': '孕妇应取仰卧位实施胸外按压',
    'B': '将患者整体向左侧倾斜15°~30°',
    'C': '胸外按压部位取胸骨下段',
    'D': '人工通气时无需压迫环状软骨',
    'E': '导管内径较非孕妇女大0.5~1.0mm',
})
# M8-A3-003 VF 处理：A 21字 -> 19字
fix_opts('batch035-M8-A3-003', {
    'A': '静注肾上腺素1mg,继续CPR后再除颤',
    'B': '静注硫酸镁2g,继续CPR后再次电除颤',
    'C': '静注利多卡因100mg,继续CPR',
    'D': '静注碳酸氢钠100ml,继续CPR',
    'E': '静注胺碘酮300mg,继续CPR后再除颤',
})

# ---------------- R10 x5 ----------------
# M3-A1-001：E"5周以上"->"不满3周"，使"3周"不再仅现于正确项 C
fix_opts('batch031-M3-A1-001', {
    'A': '1周以上', 'B': '2周以上', 'C': '3周以上', 'D': '4周以上', 'E': '不满3周',
})
# M4-A2-003：C 加入"血糖"，消除正确项 B"高血糖高渗状态"独享题干"血糖"线索
fix_opts('batch031-M4-A2-003', {
    'A': '糖尿病酮症酸中毒',
    'B': '高血糖高渗状态',
    'C': '急性胃肠炎伴血糖升高',
    'D': '水电解质紊乱',
    'E': '乳酸酸中毒',
})
# M7-B1-001：题干"打击"全部消解为"损伤/损伤性刺激"（D 含"打击"不再有题干线索）
fix_stem('batch035-M7-B1-001',
    'MODS发病机制中，强调机体遭受初次损伤后，经过一段时间再次出现损伤性刺激，炎症反应被放大而导致器官功能障碍的学说称为')
# M8-A2-002：题干"距离呼救已约6分钟"->"已有较长时间"，消除正确项 B 独享"分钟"
fix_stem('batch035-M8-A2-002',
    '男性，55岁，院外发生心脏骤停，未被目击。急救人员到达现场时距离呼救已有较长时间。此时应首先采取的急救措施是')
# M10-B1-001：题干去"紧急"，使"救援"为 A/B/C 共有，消除正确项 A 独享线索
fix_stem('batch035-M10-B1-001',
    '灾难发生后第5天，救援工作重点主要针对创伤伤员进行救治。此期属于灾难救援的')

# ---------------- R2 x20 ----------------
fix_opts('batch035-M2-A1-007', {
    'A': '瞳孔较前扩大', 'B': '皮肤干燥、颜面潮红', 'C': '心率较前增快',
    'D': '肺部啰音消失', 'E': '瞳孔明显扩大伴意识模糊',
})
fix_opts('batch031-M3-A2-002', {
    'A': '肺炎并发胸膜炎', 'B': '急性肺栓塞', 'C': '自发性气胸',
    'D': '急性心肌梗死', 'E': '大量胸腔积液',
})
fix_opts('batch031-M3-A2-003', {
    'A': '支气管哮喘急性发作', 'B': '自发性气胸', 'C': '左心衰竭伴肺水肿',
    'D': '急性肺栓塞', 'E': '急性呼吸窘迫综合征',
})
fix_opts('batch031-M3-A3-001', {
    'A': '直立位胸部X线片', 'B': '胸部CT', 'C': '心电图检查',
    'D': '动脉血气分析', 'E': '诊断性胸腔穿刺',
})
fix_opts('batch031-M4-A1-003', {
    'A': '流行性乙型脑炎', 'B': '重症中暑', 'C': '有机磷农药中毒',
    'D': '中毒性细菌性痢疾', 'E': '流行性脑脊髓膜炎',
})
fix_opts('batch031-M4-A1-005', {
    'A': '糖尿病酮症酸中毒', 'B': '尿毒症昏迷', 'C': '脑出血',
    'D': '肝性脑病', 'E': '镇静催眠药中毒',
})
fix_opts('batch031-M4-A1-006', {
    'A': '大脑皮质', 'B': '脑干脑桥', 'C': '基底节区及内囊',
    'D': '小脑齿状核', 'E': '丘脑区域',
})
fix_opts('batch031-M4-A2-005', {
    'A': '单纯性高热抽搐', 'B': '复杂性高热抽搐', 'C': '化脓性脑膜炎',
    'D': '癫痫发作', 'E': '低钙性抽搐',
})
# M4-A2-006：低血糖昏迷处理。D/E 均加长使 min>=9 -> 15/9=1.67
fix_opts('batch031-M4-A2-006', {
    'A': '静注50%葡萄糖40~60ml',
    'B': '静脉滴注0.9%氯化钠溶液',
    'C': '肌内注射胰高血糖素1mg',
    'D': '快速静脉注射甘露醇',
    'E': '静脉注射地西泮10mg',
})
fix_opts('batch031-M4-A3-001', {
    'A': '左侧壳核-内囊', 'B': '右侧壳核内囊左侧', 'C': '丘脑区域',
    'D': '脑桥', 'E': '小脑半球',
})
fix_opts('batch031-M4-X-001', {
    'A': '低血糖症', 'B': '高钠血症', 'C': '黏液性水肿昏迷',
    'D': '帕金森病', 'E': '脓毒症',
})
fix_opts('batch031-M5-A1-005', {
    'A': '革兰氏阴性杆菌感染', 'B': '深部真菌感染', 'C': '病毒感染',
    'D': '立克次体感染', 'E': '革兰氏阳性球菌感染',
})
fix_opts('batch035-M7-A1-003', {
    'A': 'Tilney', 'B': 'Eiseman', 'C': 'Fry（弗雷）',
    'D': 'Marshall', 'E': 'Sauaia',
})
fix_opts('batch035-M7-A2-002', {
    'A': '单纯肺部感染', 'B': '全身炎症反应综合征', 'C': '急性脓毒症',
    'D': '感染性休克', 'E': '多器官功能障碍',
})
fix_opts('batch035-M7-X-001', {
    'A': '年龄≥55岁', 'B': '创伤严重度评分≥25分', 'C': '大量反复输血',
    'D': '持续存在感染病灶', 'E': '长期营养不良',
})
fix_opts('batch035-M8-X-002', {
    'A': '冠心病心肌梗死', 'B': '严重低钾血症', 'C': '张力性气胸',
    'D': '淹溺（溺水）', 'E': '药物中毒',
})
fix_opts('batch035-M9-A1-004', {
    'A': '上臂下1/3处', 'B': '上臂中1/3处', 'C': '上臂上1/3处',
    'D': '上臂中下1/3交界处', 'E': '肘关节部位',
})
fix_opts('batch035-M9-A3-003', {
    'A': '急性应激障碍', 'B': '创伤应激障碍', 'C': '广泛性焦虑障碍',
    'D': '抑郁障碍', 'E': '适应障碍',
})
fix_opts('batch035-M10-X-001', {
    'A': '饮用水供应系统破坏', 'B': '食物短缺和燃料短缺', 'C': '水源污染与破坏',
    'D': '居住环境破坏人口迁徙', 'E': '对媒介生物生态平衡影响',
})

# ---------------- M6-A1-008 重写：淹溺程度分类 ----------------
q = byid['batch031-M6-A1-008']
q['topic'] = '淹溺程度分类'
q['stem'] = '溺水3～4分钟获救，神志丧失，无脉搏血压，面色苍白肿胀。按淹溺程度分类，该患者属于'
q['options'] = [
    {'label': 'A', 'text': '轻度淹溺：意识清楚，血压升高'},
    {'label': 'B', 'text': '中度淹溺：剧烈呛咳，意识模糊'},
    {'label': 'C', 'text': '重度淹溺：昏迷，四肢厥冷，口鼻血性泡沫'},
    {'label': 'D', 'text': '迟发性淹溺：初期症状轻，后出现肺水肿'},
    {'label': 'E', 'text': '浸渍综合征：低温液体致心律失常、晕厥'},
]
q['answer'] = 'C'
q['explanation'] = ('按临床表现将淹溺分为轻、中、重三度：轻度——落水片刻，吸入或吞入少量液体，'
    '反射性呼吸暂停，意识清楚，血压升高，心率加快；中度——溺水1～2分钟，水经呼吸道或消化道进入，'
    '剧烈呛咳、呕吐，意识模糊、烦躁，呼吸不规则或表浅，血压下降，心率减慢，反射减弱；'
    '重度——溺水3～4分钟，昏迷，面色发绀或苍白肿胀，眼球突出，四肢厥冷，血压测不到，口鼻血性泡沫，'
    '胃扩张、上腹膨隆，可有抽搐，呼吸心搏微弱或停止。本例溺水3～4分钟、神志丧失、无脉搏血压、'
    '面色苍白肿胀，符合重度淹溺。D迟发性淹溺指溺水后初期症状较轻，数小时至1天后出现肺水肿等表现；'
    'E浸渍综合征指较长时间浸于低温液体（中心体温低于35℃），出现心律失常、晕厥等表现。教材P177。')
q['source_page'] = '教材P177'
q['difficulty'] = '中等'
q['option_polarities'] = {'A': False, 'B': False, 'C': True, 'D': False, 'E': False}
q.pop('kaoyan_origin', None)
print('OK M6-A1-008 重写为淹溺程度分类题（撤 GS-2023-041）')

# ---------------- kaoyan：撤销 7 条考点不符 ----------------
for qid in ['batch035-M8-A1-001',
            'batch035-M9-A1-001', 'batch035-M9-A1-002', 'batch035-M9-A1-003',
            'batch035-M9-A1-004', 'batch035-M9-A1-005', 'batch035-M9-A1-006']:
    q = byid.get(qid)
    if q and 'kaoyan_origin' in q:
        q.pop('kaoyan_origin')
        # 若解析含误挂的 [源:] 一并去除
        expl = q.get('explanation', '')
        if '[源:考研真题' in expl:
            import re as _re
            q['explanation'] = _re.sub(r'\[源:考研真题 [^\]]+\]', '', expl).rstrip('。') + '。'
        print('OK 撤标注', qid)
    else:
        print('!! 待撤标注未找到', qid); n_fail += 1

# ---------------- kaoyan：补标 16 条（逐对核对后，mode=改编） ----------------
NEW_TAGS = {
    'batch035-M2-A1-003':  ('GS-2003-025', 2003, 25),
    'batch035-M2-A1-004':  ('GS-2018-156', 2018, 156),
    'batch035-M2-A1-010':  ('GS-2021-130', 2021, 130),
    'batch035-M2-A2-004':  ('GS-2023-156', 2023, 156),
    'batch035-M2-X-004':   ('GS-2010-169', 2010, 169),
    'batch031-M3-A1-005':  ('GS-2024-062', 2024, 62),
    'batch031-M3-A1-007':  ('GS-2014-096', 2014, 96),
    'batch031-M3-A3-001':  ('GS-2018-070', 2018, 70),
    'batch031-M4-B1-002':  ('GS-2010-057', 2010, 57),
    'batch031-M6-A1-005':  ('GS-2003-079', 2003, 79),
    'batch031-M6-A1-006':  ('GS-2014-041', 2014, 41),
    'batch035-M7-X-001':   ('GS-1999-158', 1999, 158),
    'batch035-M8-A3-001':  ('GS-2019-049', 2019, 49),
    'batch035-M8-A1-009':  ('GS-1994-090', 1994, 90),
    'batch035-M9-A2-003':  ('GS-2007-162-2', 2007, 162),
    'batch035-M9-A2-004':  ('GS-2014-084', 2014, 84),
}
for qid, (gs, yr, no) in NEW_TAGS.items():
    q = byid.get(qid)
    if q is None:
        print('!! 补标目标未找到', qid); n_fail += 1; continue
    q['kaoyan_origin'] = {
        'gs_id': gs,
        'year': yr,
        'source': f'{yr}考研西综·第{no}题',
        'mode': '改编',
    }
    expl = q.get('explanation', '')
    src_tag = f'[源:考研真题 {gs}]'
    if '[源:考研真题' in expl:
        import re as _re
        expl = _re.sub(r'\[源:考研真题 [^\]]+\]', src_tag, expl)
    else:
        expl = expl.rstrip() + src_tag
    q['explanation'] = expl
    print('OK 补标', qid, '->', gs)

# ---------------- 自验 ----------------
from collections import Counter
mods = Counter(q['module'] for q in data)
types = Counter(q['type'] for q in data)
expect_mods = {'M1':8,'M2':30,'M3':16,'M4':26,'M5':24,'M6':18,'M7':18,'M8':28,'M9':24,'M10':14,'M11':14}
expect_types = {'A1':100,'A2':46,'A3':24,'B1':20,'X':30}
assert mods == expect_mods, f'模块配额变化: {mods}'
assert types == expect_types, f'题型配额变化: {types}'
print('配额 OK:', dict(mods), dict(types))

ko_count = 0
for q in data:
    if q.get('kaoyan_origin'):
        ko_count += 1
        if '[源:考研真题' not in q.get('explanation',''):
            print('!! 缺 [源:]', q['id']); n_fail += 1
print('kaoyan 标注数 =', ko_count, '(目标 34)')
if ko_count != 34:
    print('!! kaoyan 计数 != 34'); n_fail += 1

# 重复 stem 检查
stems = {}
for q in data:
    stems.setdefault(q['stem'], []).append(q['id'])
dups = {s: v for s, v in stems.items() if len(v) > 1}
if dups:
    print('!! 重复题干:', dups); n_fail += 1
else:
    print('无重复题干 OK')

# M6-A1-008 新题 R10 预检：题干关键词不得仅现于正确项
def ngrams(s, n):
    return {s[i:i+n] for i in range(len(s)-n+1)}
stem = byid['batch031-M6-A1-008']['stem']
kws = set()
for n in range(2, 6):
    kws |= ngrams(stem, n)
opts = {o['label']: o['text'] for o in byid['batch031-M6-A1-008']['options']}
ans = byid['batch031-M6-A1-008']['answer']
correct_hits = {k for k in kws if k in opts[ans]}
other_hits = set()
for l, t in opts.items():
    if l != ans:
        other_hits |= {k for k in kws if k in t}
excl = correct_hits - other_hits
print('M6-A1-008 R10 独占线索:', excl if excl else '无 ✓')

json.dump(data, open(SRC, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('已写回', SRC)
print('FAIL 数 =', n_fail)
sys.exit(1 if n_fail else 0)
