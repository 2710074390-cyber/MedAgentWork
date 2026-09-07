import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

base = r'c:\Users\38063\Desktop\MedAgentWork\中间产物\batch035'
parts = [
    'part_emerg_A.json',  # M1+M2: 38
    'part_emerg_B.json',  # M3+M4: 42
    'part_emerg_C.json',  # M5+M6: 42
    'part_emerg_D.json',  # M7+M8: 46
    'part_emerg_E.json',  # M9+M10: 38
    'part_emerg_F.json',  # M11: 14
    # Total: 220
]

all_questions = []
seen_ids = set()
errors = []
kaoyan_count = 0

for fname in parts:
    fpath = os.path.join(base, fname)
    if not os.path.exists(fpath):
        errors.append(f'MISSING: {fname}')
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f'JSON ERROR in {fname}: {e}')
            continue
    
    if not isinstance(data, list):
        errors.append(f'NOT A LIST: {fname}')
        continue
    
    for q in data:
        qid = q.get('id', 'NO_ID')
        if qid in seen_ids:
            errors.append(f'DUPLICATE ID: {qid} in {fname}')
        seen_ids.add(qid)
        
        if 'kaoyan_origin' in q:
            kaoyan_count += 1
        
        # Validate required fields
        required = ['id', 'module', 'module_name', 'topic', 'type', 'polarity', 'bloom', 'stem', 'options', 'answer', 'explanation', 'source_page', 'difficulty', 'option_polarities']
        for field in required:
            if field not in q:
                errors.append(f'MISSING FIELD {field} in {qid}')
        
        # Validate options
        opts = q.get('options', [])
        if len(opts) != 5:
            errors.append(f'WRONG OPTION COUNT in {qid}: {len(opts)}')
        
        # Validate answer
        ans = q.get('answer', '')
        if q.get('type') == 'X':
            for ch in ans:
                if ch not in 'ABCDE':
                    errors.append(f'INVALID X ANSWER in {qid}: {ans}')
                    break
        else:
            if ans not in 'ABCDE':
                errors.append(f'INVALID ANSWER in {qid}: {ans}')
        
        # Validate option_polarities
        op = q.get('option_polarities', {})
        for k in ['A', 'B', 'C', 'D', 'E']:
            if k not in op:
                errors.append(f'MISSING POLARITY {k} in {qid}')
        
        all_questions.append(q)

# Module counts
module_counts = {}
type_counts = {}
bloom_counts = {}
for q in all_questions:
    m = q.get('module', '?')
    t = q.get('type', '?')
    b = q.get('bloom', '?')
    module_counts[m] = module_counts.get(m, 0) + 1
    type_counts[t] = type_counts.get(t, 0) + 1
    bloom_counts[b] = bloom_counts.get(b, 0) + 1

# Expected module quotas
expected = {
    'M1': 8, 'M2': 30, 'M3': 16, 'M4': 26, 'M5': 24, 'M6': 18,
    'M7': 18, 'M8': 28, 'M9': 24, 'M10': 14, 'M11': 14
}

print('=' * 60)
print(f'MERGE REPORT: batch035 急诊与灾难医学')
print('=' * 60)
print(f'Total questions: {len(all_questions)}')
print(f'Errors: {len(errors)}')
print(f'Kaoyan origin: {kaoyan_count} ({kaoyan_count/len(all_questions)*100:.1f}%)')
print()

print('--- Module Counts ---')
total = 0
for m in sorted(module_counts.keys()):
    actual = module_counts[m]
    exp = expected.get(m, '?')
    status = '✅' if actual == exp else f'❌ (expected {exp})'
    print(f'  {m}: {actual} {status}')
    total += actual
print(f'  Total: {total}')

print()
print('--- Type Counts ---')
for t in sorted(type_counts.keys()):
    print(f'  {t}: {type_counts[t]}')
print(f'  Total: {sum(type_counts.values())}')

print()
print('--- Bloom Distribution ---')
for b in ['记忆', '理解', '应用', '分析']:
    cnt = bloom_counts.get(b, 0)
    print(f'  {b}: {cnt} ({cnt/len(all_questions)*100:.1f}%)')

print()
if errors:
    print('--- ERRORS ---')
    for e in errors[:30]:
        print(f'  ❌ {e}')
    if len(errors) > 30:
        print(f'  ... and {len(errors)-30} more')
else:
    print('✅ ALL VALIDATIONS PASSED')

# Write merged file
out_path = os.path.join(base, 'ALL_questions.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(all_questions, f, ensure_ascii=False, indent=2)
print(f'\nWritten to: {out_path}')