#!/usr/bin/env python3
"""合并精神病学三个批次: batch007(242) + batch023(70) + batch026(19) → 331题统一题库"""

import json
import os
import sys

BASE = r'C:\Users\38063\Desktop\MedAgentWork'

# Input paths
PATHS = {
    'batch007': os.path.join(BASE, 'archive', '最终产物', 'batch007', 'ALL_questions_v3_FINAL.json'),
    'batch023': os.path.join(BASE, '最终产物', 'batch023', 'ALL_questions_FIXED.json'),
    'batch026': os.path.join(BASE, '中间产物', 'batch026_analysis', 'batch026_analysis_questions.json'),
}

def normalize(q, source):
    """Normalize question to canonical schema"""
    mod = q.get('module', q.get('module_id', ''))
    ans = q.get('answer_key', q.get('correct_answer', ''))
    qt = q.get('question_type', q.get('type', ''))
    bl = q.get('bloom_level', q.get('bloom', ''))

    return {
        'question_id': q.get('question_id', ''),
        'module': mod,
        'question_type': qt,
        'polarity': q.get('polarity', ''),
        'bloom_level': bl,
        'source_anchors': q.get('source_anchors', ''),
        'source_pages': q.get('source_pages', ''),
        'priority_level': q.get('priority_level', ''),
        'stem': q.get('stem', ''),
        'options': q.get('options', []),
        'option_polarities': q.get('option_polarities', []),
        'answer_key': ans,
        'explanation': q.get('explanation', ''),
        'difficulty_index': q.get('difficulty_index', None),
        'discrimination_index': q.get('discrimination_index', None),
        'non_functioning_distractors': q.get('non_functioning_distractors', []),
        'batch_source': source
    }

def main():
    merged = []

    for source, path in PATHS.items():
        print(f'Reading {source}...')
        data = json.load(open(path, 'r', encoding='utf-8'))
        normalized = [normalize(q, source) for q in data]
        merged.extend(normalized)
        print(f'  {len(normalized)} questions')

    # Dedup check
    ids = [q['question_id'] for q in merged]
    dups = set([i for i in ids if ids.count(i) > 1])
    if dups:
        print(f'WARNING: {len(dups)} duplicate IDs found!')
        for d in sorted(dups):
            print(f'  {d}')
    else:
        print('Dedup check: PASS (0 duplicates)')

    # Stats
    types = {}
    blooms = {}
    mods = {}
    sources = {}
    for q in merged:
        types[q['question_type']] = types.get(q['question_type'], 0) + 1
        blooms[q['bloom_level']] = blooms.get(q['bloom_level'], 0) + 1
        mods[q['module']] = mods.get(q['module'], 0) + 1
        sources[q['batch_source']] = sources.get(q['batch_source'], 0) + 1

    print(f'\n=== 合并统计 ===')
    print(f'总题数: {len(merged)}')
    print(f'题型分布: {json.dumps(types, ensure_ascii=False, indent=2)}')
    print(f'模块分布: {json.dumps(dict(sorted(mods.items())), ensure_ascii=False, indent=2)}')
    print(f'Bloom分布: {json.dumps(blooms, ensure_ascii=False, indent=2)}')
    print(f'来源分布: {json.dumps(sources, ensure_ascii=False, indent=2)}')

    # Bloom percentages
    total = len(merged)
    for b, c in sorted(blooms.items()):
        print(f'  {b}: {c}/{total} = {c/total*100:.1f}%')

    # Save
    outdir = os.path.join(BASE, '复习资料')
    os.makedirs(outdir, exist_ok=True)

    outpath = os.path.join(outdir, '精神病学_统一题库_331题.json')
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    size_kb = os.path.getsize(outpath) / 1024
    print(f'\n✅ 已保存: {outpath} ({size_kb:.1f} KB)')

    # Verify
    check = json.load(open(outpath, 'r', encoding='utf-8'))
    assert len(check) == len(merged), f'Mismatch: {len(check)} != {len(merged)}'
    print(f'✅ 验证通过: {len(check)} 题完整可读')

if __name__ == '__main__':
    main()
