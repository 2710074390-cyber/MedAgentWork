import json
import re
from pathlib import Path

p = Path(__file__).resolve().parent

def load(name):
    return json.loads((p / name).read_text(encoding='utf-8'))

def save(name, data):
    path = p / name
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

original = load('original_Q001_Q036_fixed.json') + load('original_Q037_Q072_fixed.json')
candidates = load('real_question_candidates_draft.json')
blueprint = load('question_blueprint_v3.json')['逐题计划']
answers = load('answer_position_plan.json')
plan = {x['item_id']: x for x in load('real_question_plan.json')['selected']}
verification = load('逐题核验结果.json')
verified = {x['item_id']: x for group in ('qualified', 'unqualified', 'unknown') for x in verification[group]}
assert len(original) == 72 and len(candidates) == 28 and len(blueprint) == 100
assert all(q['id'] == f'batch046-Q{i:03d}' and q['answer'] == answers[i-1] for i, q in enumerate(original, 1))
assert all(b['答案位置'] == answers[i] for i,b in enumerate(blueprint))

# Plan references are retrieval hints only; they do not establish semantic alignment.
def score(c, b):
    v = plan[c['item_id']]
    refs = {int(n) for s in v.get('keypoint_refs', []) for n in re.findall(r'\d+', str(s))}
    answer = c['answer'] == b['答案位置']
    typ = v.get('question_type') == b['题型']
    ref = bool(refs.intersection(b['教师重点']))
    return 100 * answer + 10 * typ + 10 * ref

# Maximum-weight one-to-one matching, implemented by subset-free augmenting paths.
n = len(candidates)
cost = [[-score(c, b) for b in blueprint[72:]] for c in candidates]
u = [0]*(n+1); v = [0]*(n+1); match = [0]*(n+1); way = [0]*(n+1)
for i in range(1, n+1):
    match[0] = i; j0 = 0; minv = [10**9]*(n+1); used = [False]*(n+1)
    while True:
        used[j0] = True; i0 = match[j0]; delta = 10**9; j1 = 0
        for j in range(1, n+1):
            if not used[j]:
                cur = cost[i0-1][j-1]-u[i0]-v[j]
                if cur < minv[j]: minv[j] = cur; way[j] = j0
                if minv[j] < delta: delta = minv[j]; j1 = j
        for j in range(n+1):
            if used[j]: u[match[j]] += delta; v[j] -= delta
            else: minv[j] -= delta
        j0 = j1
        if match[j0] == 0: break
    while True:
        j1 = way[j0]; match[j0] = match[j1]; j0 = j1
        if j0 == 0: break
assignment = {match[j]-1: blueprint[71+j] for j in range(1,n+1)}

quarantine = {
 'ZP-2009-3-87-84':'答案B/E竞争，单选唯一性存疑',
 'ZP-2022-0-31-144':'题干不完整，原页未核',
 'ZP-2016-2-43-86':'计划答案及唯一性存在医学疑问',
 'ZP-2016-2-3-121':'来源编号不符、病例组不完整且题干疑截断',
 'ZP-2012-1-3-115':'共享病例和编号未核，题干不完整及答案存疑',
 'ZP-2019-3-6-72':'多个危重征象，最佳答案争议待盲审',
 'ZP-2015-2-47-88':'疑似OCR错误，未核原页',
 'ZY-T-6583':'法律伦理题，急救仅为背景，与急诊技术考点不等同',
 'KY-GS-2020-108':'医学人道主义题，急救仅为背景，与心搏骤停或晕厥考点不等同',
 'KY-GS-2002-048':'核验记录提示A/E均可能成立，单选唯一性争议',
 'KY-GS-2019-049':'逐题核验判定unqualified，四选项与模板冲突，原答案出处未核',
 'ZP-2009-2-140-138':'腹膜炎不等同急性胰腺炎考点',
 'KY-GS-2010-086':'腹膜炎不等同急性胰腺炎考点，四选项模板冲突',
 'ZP-2015-4-9-8':'中毒型感染不等同外源性毒物中毒，考点范围存疑',
}
items=[]; gate=list(original); slots=[]
for i,c in enumerate(candidates):
    b=assignment[i]; pp=plan[c['item_id']]; vv=verified[c['item_id']]
    refs={int(n) for s in pp.get('keypoint_refs',[]) for n in re.findall(r'\d+',str(s))}
    differences=[]
    if c['answer'] != b['答案位置']: differences.append('答案字母不符')
    if pp.get('question_type') != b['题型']: differences.append('计划记载题型与题位不同，原题型未独立确认')
    if not refs.intersection(b['教师重点']): differences.append('计划检索考点与题位不同')
    else: differences.append('计划检索考点有交集，但语义适配未经核实')
    if len(c['options']) != 5: differences.append(f"原候选{len(c['options'])}选项，与五选项模板冲突；未补项")
    differences.append('原卷、答案、医学、授权尚未完成独立核验')
    status='quarantine' if c['item_id'] in quarantine or vv in verification['unqualified'] else 'unplaced_review_candidate'
    item={'proposed_slot_id':b['题位ID'],'placement_status':status,'qualified':False,'quarantine_reason':quarantine.get(c['item_id']),'candidate_verbatim':c,'verification':vv,'planned_candidate_type':pp.get('question_type'),'planned_candidate_keypoints':pp.get('keypoint_refs',[]),'slot_plan':b,'differences':differences}
    items.append(item)
    slots.append({'slot_id':b['题位ID'],'status':'blocked_unfilled','proposed_candidate_id':c['item_id'],'candidate_status':status,'differences':differences})
    # Validation projection only: preserve source stem, answer, option text and order.
    gate.append({'id':b['题位ID'],'sequence':b['题序'],'stem':c['stem'],'options':[{'label':chr(65+j),'text':text,'is_correct':chr(65+j)==c['answer']} for j,text in enumerate(c['options'])],'answer':c['answer'],'review_status':status,'candidate_id':c['item_id']})
slots.sort(key=lambda x:x['slot_id']); items.sort(key=lambda x:x['proposed_slot_id']); gate.sort(key=lambda x:x['sequence'])
report={'batch':'batch046','status':'BLOCKED_NOT_RELEASED','method':'仅按答案字母、计划记载题型与检索重点交集进行最大权重一对一建议；计划检索标签不证明实际适配。所有建议均非落位。','counts':{'original_draft':72,'candidates':28,'placed_candidates':0,'qualified_candidates':0,'quarantine':sum(x['placement_status']=='quarantine' for x in items)},'global_blockers':['28条均未完成原卷、答案、医学或版权独立核验','题型与考点的语义适配未获得证据','全部建议仅为候选对应，不作为题库落位或合格数'],'slots':slots}
draft={'batch':'batch046','status':'REVIEW_DRAFT_BLOCKED_NOT_RELEASED','notice':'仅72题原创待审及28条独立候选；候选建议题位不构成实际落位或合格；未经医学和权利核验。','original_questions':original,'unfilled_slots':slots,'independent_candidates':items}
save('batch046_100_review_draft.json',draft)
save('batch046_placement_blockers.json',report)
save('batch046_validation_projection.json',gate)
print(json.dumps(report['counts'],ensure_ascii=False))
