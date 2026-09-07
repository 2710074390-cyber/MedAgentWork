# -*- coding: utf-8 -*-
"""HC-13 源文件同步：以 ALL_questions_FIXED.json 为唯一事实来源，
按模块重建 part_emerg_A~F.json，并逐题 JSON 级比对验证 0 差异。"""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

D = r'C:\Users\38063\Desktop\MedAgentWork\中间产物\batch035'
fixed = json.load(open(D + r'\ALL_questions_FIXED.json', encoding='utf-8'))

# 模块 → part 文件映射（原 6 组结构）
part_map = [
    ('A', ['M1', 'M2']),
    ('B', ['M3', 'M4']),
    ('C', ['M5', 'M6']),
    ('D', ['M7', 'M8']),
    ('E', ['M9', 'M10']),
    ('F', ['M11']),
]

def norm(q):
    """与 FIXED 完全一致的规范化（id 保留原前缀）。"""
    out = {
        'id': q['id'], 'module': q['module'], 'module_name': q['module_name'],
        'topic': q['topic'], 'type': q['type'], 'polarity': q['polarity'],
        'bloom': q['bloom'], 'stem': q['stem'], 'options': q['options'],
        'answer': q['answer'], 'explanation': q['explanation'],
        'source_page': q['source_page'], 'difficulty': q['difficulty'],
        'option_polarities': q['option_polarities'],
    }
    if 'kaoyan_origin' in q:
        out['kaoyan_origin'] = q['kaoyan_origin']
    return out

by_mod = {}
for q in fixed:
    by_mod.setdefault(q['module'], []).append(q)

total_written = 0
for letter, mods in part_map:
    part = []
    for m in mods:
        part.extend(norm(q) for q in by_mod.get(m, []))
    path = D + rf'\part_emerg_{letter}.json'
    json.dump(part, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    total_written += len(part)
    print(f'part_emerg_{letter}.json 写入 {len(part)} 题（{"+".join(mods)}）')

# 逐题 JSON 级比对：FIXED 全集 与 6 part 重建全集
rebuilt = []
for letter, mods in part_map:
    rebuilt += json.load(open(D + rf'\part_emerg_{letter}.json', encoding='utf-8'))
assert len(rebuilt) == len(fixed) == 220, f'数量不一致: {len(rebuilt)} vs {len(fixed)}'

diff = 0
fb = {q['id']: q for q in fixed}
for q in rebuilt:
    orig = fb[q['id']]
    if orig != q:
        diff += 1
        print('差异:', q['id'])
print(f'重建 {len(rebuilt)} 题，与 FIXED 逐题 JSON 比对差异 = {diff}')
assert diff == 0, 'part 同步存在差异'
print('HC-13 源文件同步完成：6 个 part 文件已与 ALL_questions_FIXED.json 完全一致')
