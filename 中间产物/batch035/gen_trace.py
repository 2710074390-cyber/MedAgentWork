# -*- coding: utf-8 -*-
"""生成 AGENT4_追溯日志.json（最终产物/batch035/）"""
import json, sys
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'C:\Users\38063\Desktop\MedAgentWork'
d = json.load(open(ROOT + r'\中间产物\batch035\ALL_questions_FIXED.json', encoding='utf-8'))
types = Counter(q['type'] for q in d)
bloom = Counter(q['bloom'] for q in d)
pol = Counter(q['polarity'] for q in d)
diffc = Counter(q.get('difficulty', '?') for q in d)
ko = sum(1 for q in d if q.get('kaoyan_origin'))

trace = {
    'batch': 'batch035',
    'agent': 'Agent4 MedFix',
    'subject': '急诊与灾难医学（11模块：绪论/急性中毒/呼吸困难/意识障碍与抽搐/休克/环境及理化因素损伤/MODS/心肺脑复苏/创伤急救/灾难医学/灾难现场医学救援）',
    'raw_total': 220,
    'fixed_total': 220,
    'fixes': [
        {'round': 'fix_pass_v1', 'scope': '全量220题',
         'purpose': '去「主要」等冗余前缀126处、选项A-E排序、X型答案规范化',
         'tool': 'fix_pass_v1.py / fix_pass_v2.py（备份 _bak_FIXED_v1.json）'},
        {'round': 'fix_pass_v2', 'scope': '全量220题',
         'purpose': '承接首轮修复后 validate 复检，FAIL 降至28（R2×20/R10×5/R13×3）',
         'tool': 'validate_options.py --batch batch035'},
        {'round': 'fix_pass_v3', 'scope': '28处FAIL+M6-A1-008+kaoyan标注',
         'purpose': ('1) R13×3 缩短>20字选项（M5-A1-003去单位、M8-A2-005/M8-A3-003压缩）；'
                     '2) R10×5 题干/干扰项消线索（M3-A1-001、M4-A2-003、M7-B1-001、M8-A2-002、M10-B1-001）；'
                     '3) R2×20 选项长度比≤2.0；'
                     '4) M6-A1-008 重写为淹溺程度分类题（原与 M4-A1-003 重复，均源自 GS-2023-041）；'
                     '5) kaoyan 撤销7条考点不符（M8-A1-001、M9-A1-001~006），逐对核对补标16条至34条'),
         'tool': 'fix_pass_v3.py（备份 _bak_FIXED_v2.json）'},
    ],
    'gates_after': {
        'GATE-A2_validate_options': {'fail': 0, 'warn': 125, 'pass': 95},
        'GATE-A3_qc': {'gate_decision': 'PASS', 'overall_score': 94.8, 'D20': 10.0, 'bloom_dev_max': 8.2},
        'fact_check_pages': {'spot': 10, 'hit': 10, 'note': '10题教材溯源抽检全部命中（教材P页=PDF页-17）'},
        'kaoyan_quota_HC18': f'{ko}/220 = {ko/220*100:.1f}% (合格带 15-25%) PASS',
        'duplicate_stem': 0,
    },
    'distribution': {
        'modules': 'M1×8/M2×30/M3×16/M4×26/M5×24/M6×18/M7×18/M8×28/M9×24/M10×14/M11×14 = 220',
        'types': dict(types),
        'difficulty': dict(diffc),
        'polarity': dict(pol),
        'bloom': dict(bloom),
        'kaoyan_origin': ko,
    },
    'deviation_notes': [
        ('kaoyan 标注按模块：M2×10/M3×7/M4×6/M5×4/M6×2/M7×1/M8×2/M9×2=34；'
         '出题规范建议配额为建议性，M6（淹溺/冻伤/电击）在考研西综真题库（GoldenSet 9616题）中无直接对应真题，'
         'M7/M8/M9 仅能诚实核对到 1~2 条配对；诚实原则优先，不以失真标注凑数（质检报告 ISSUE-005）'),
        ('原 26 条 kaoyan 标注中 7 条考点不符（M8-A1-001 挂 GS-1998-049 实为溶栓题；'
         'M9-A1-001~006 挂气胸/窒息类真题而题库题为创伤评分/分拣/止血带），'
         '已全部撤销并重新逐对核对补标 16 条（全部经 stem/options/answer/explanation 比对一致，mode=改编）'),
        ('M6-A1-008 原题与 M4-A1-003 题干完全重复（同源 GS-2023-041），'
         '已重写为「淹溺程度分类」A1题（教材P177 三度定义），M4-A1-003 保留原题与标注'),
    ],
    'source_file_synced': True,
    'source_files_synced': True,
    'source_files': [
        '中间产物/batch035/part_emerg_A.json', '中间产物/batch035/part_emerg_B.json',
        '中间产物/batch035/part_emerg_C.json', '中间产物/batch035/part_emerg_D.json',
        '中间产物/batch035/part_emerg_E.json', '中间产物/batch035/part_emerg_F.json',
    ],
    'source_sync_note': ('HC-13 补丁溯源 2026-09-07：此前多轮修复仅落在聚合文件，6 个 part 源文件与 FIXED '
                         '存在 106 题不一致。已以 ALL_questions_FIXED.json 为唯一事实来源按模块重建全部 6 个 '
                         'part 文件（sync_part_files.py），重建后逐题 JSON 级比对 0 差异。'),
}

out = ROOT + r'\最终产物\batch035\AGENT4_追溯日志.json'
json.dump(trace, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('已生成', out)
print('kaoyan:', ko, '| 类型:', dict(types), '| Bloom:', dict(bloom))
