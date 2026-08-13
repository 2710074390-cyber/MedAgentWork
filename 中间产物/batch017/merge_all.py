import json, os

base = r'C:\Users\38063\Desktop\MedAgentWork\中间产物\batch017'
all_questions = []

for pf in ['ALL_questions_batch017.json', 'part2_第二篇.json', 'part3_第三篇.json', 'part4_第四篇.json']:
    path = os.path.join(base, pf)
    with open(path, 'r', encoding='utf-8') as f:
        qs = json.load(f)
    all_questions.extend(qs)
    print(f'Loaded {len(qs)} from {pf}')

total = len(all_questions)
print(f'\nTotal: {total} questions')

# Stats
bloom = {}
for q in all_questions:
    bl = q['bloom_level']
    bloom[bl] = bloom.get(bl, 0) + 1
print('\n=== Bloom Distribution ===')
for bl in ['记忆', '理解', '应用', '分析']:
    c = bloom.get(bl, 0)
    print(f'  {bl}: {c} ({c/total*100:.1f}%)')

qtypes = {}
for q in all_questions:
    qt = q['question_type']
    qtypes[qt] = qtypes.get(qt, 0) + 1
print('\n=== Question Types ===')
for qt in ['A1', 'A2', 'B1', 'X']:
    c = qtypes.get(qt, 0)
    print(f'  {qt}: {c} ({c/total*100:.1f}%)')

modules = {}
for q in all_questions:
    m = q['module']
    modules[m] = modules.get(m, 0) + 1
print('\n=== Module Distribution ===')
for m, c in sorted(modules.items(), key=lambda x: -x[1]):
    print(f'  {m}: {c}')

# Check IDs
ids = [q['id'] for q in all_questions]
dups = [i for i in ids if ids.count(i) > 1]
print(f'\nDuplicate IDs: {set(dups) if dups else "None"}')
missing = [f'batch017_Q{i:03d}' for i in range(1, 301) if f'batch017_Q{i:03d}' not in ids]
print(f'Missing IDs: {missing if missing else "None"}')

# Check MD answer marks
no_mark = [q['id'] for q in all_questions if '✅' not in str(q.get('options', []))]
print(f'Missing ✅ in options: {len(no_mark)} questions')

# R2 basic check
r2_issues = []
for q in all_questions:
    opts = q.get('options', [])
    lens = []
    for o in opts:
        text = o.split('. ', 1)[-1] if '. ' in o else o
        lens.append(len(text))
    if lens and max(lens) / min(lens) > 3.0:
        r2_issues.append((q['id'], lens, max(lens)/min(lens)))
print(f'\nR2 ratio > 3.0: {len(r2_issues)} questions')
for item in r2_issues[:10]:
    print(f'  {item[0]}: {item[1]} ratio={item[2]:.1f}')

# Write merged
output = os.path.join(base, 'ALL_questions_batch017.json')
with open(output, 'w', encoding='utf-8') as f:
    json.dump(all_questions, f, ensure_ascii=False, indent=2)

# Verify
with open(output, 'r', encoding='utf-8') as f:
    verify = json.load(f)
print(f'\nFinal file: {len(verify)} questions, {os.path.getsize(output):,} bytes')

# Clean up part files
for pf in ['part2_第二篇.json', 'part3_第三篇.json', 'part4_第四篇.json']:
    pp = os.path.join(base, pf)
    if os.path.exists(pp):
        os.remove(pp)
        print(f'Cleaned up: {pf}')
