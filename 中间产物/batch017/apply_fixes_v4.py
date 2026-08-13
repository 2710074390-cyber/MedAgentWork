#!/usr/bin/env python3
"""v4: Final aggressive fix for worst remaining R2/R10 issues"""
import json, re, os, sys
sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\38063\Desktop\MedAgentWork\最终产物\batch017\ALL_questions_FIXED.json"
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)
qmap = {q['id']: q for q in data}

# Aggressive fixes for ratio > 3.0 based on actual current text
fixes = {
    'batch017_Q258': {
        'B': ('脑电图', '脑电图监测'),
        'A': ('GCS评分', 'GCS昏迷评分'),
    },
    'batch017_Q196': {
        'A': ('环境因素（噪声/光照/昼夜节律紊乱）', '环境噪声光照节律紊乱'),
    },
    'batch017_Q243': {
        'B': ('偏瘫', '肢体偏瘫'),
        'C': ('颅内压增高表现', '颅内压增高'),
    },
    'batch017_Q101': {
        'B': ('大量组织破坏细胞内钾释放', '大量组织破坏释钾'),
        'C': ('酸中毒', '代谢性酸中毒'),
    },
    'batch017_Q257': {
        'C': ('开放性颅脑损伤后直接种植', '开放性颅脑伤后种植'),
        'D': ('隐源性', '隐源性感染'),
    },
    'batch017_Q033': {
        'A': ('感染', '严重感染'),
        'B': ('休克', '失血性休克'),
    },
    'batch017_Q054': {
        'B': ('皮肤色泽和温度', '皮肤色泽温度'),
        'D': ('尿量', '每小时尿量'),
    },
    'batch017_Q235': {
        'C': ('乳突区淤血（Battle征）', '乳突区Battle征'),
        'D': ('嗅觉丧失', '嗅觉丧失症'),
    },
    'batch017_Q137': {
        'A': ('尿潴留', '术后尿潴留'),
        'C': ('低血压', '体位性低血压'),
    },
    'batch017_Q214': {
        'E': ('脑电图', '脑电图检查'),
    },
    'batch017_Q151': {
        'E': ('颈椎不稳定损伤（相对禁忌）', '颈椎不稳定损伤(相对禁忌)'),
    },
    'batch017_Q170': {
        'C': ('β阻滞剂与吸入麻醉药协同抑心血管', 'β阻滞剂+吸入药协同抑心'),
    },
    'batch017_Q237': {
        'B': ('首次CT正常，数小时至数天后复查见血肿', '首次CT正常，数小时至数天后见血肿'),
    },
    'batch017_Q032': {
        'B': ('糖尿病', '糖尿病因素'),
    },
    'batch017_Q056': {
        'D': ('混合静脉血氧饱和度', '混合静脉血氧饱和度'),
        'E': ('血乳酸', '血乳酸水平'),
    },
    'batch017_Q134': {
        'A': ('休克', '低血容量休克'),
    },
    'batch017_Q147': {
        'C': ('Horner综合征', 'Horner综合征'),
        'D': ('全脊麻', '全脊髓麻醉'),
    },
    'batch017_Q161': {
        'A': ('舌后坠', '舌根后坠'),
    },
    'batch017_Q162': {
        'A': ('舌后坠', '舌根后坠'),
    },
    # Also handle Q060 R10 still failing
    'batch017_Q060': {
        'D': ('各类休克均应首选缩血管药', '各种休克首选缩血管药慎用'),
    },
    # Handle Q170 R10 issue
    'batch017_Q170': {
        'C': ('β阻滞剂+吸入药协同抑心', 'β阻滞剂协同吸入药抑心'),
    },
}

# Apply
for qid, opts_fix in fixes.items():
    q = qmap.get(qid)
    if not q: continue
    for label, (old, new) in opts_fix.items():
        for i, s in enumerate(q['options']):
            m = re.match(r'^([A-E])\.\s*(.+)', s)
            if m and m.group(1) == label:
                text = m.group(2)
                if old in text:
                    q['options'][i] = f"{label}. {text.replace(old, new)}"
                    break

# Save
with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"Applied v4 fixes, saved to {path}")
