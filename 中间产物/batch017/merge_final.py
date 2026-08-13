# -*- coding: utf-8 -*-
import json, os, sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\38063\Desktop\MedAgentWork\中间产物\batch017'

# Collect ALL JSON part files
part_files = []
for f in os.listdir(base):
    if f.endswith('.json') and f != 'ALL_questions_batch017.json':
        part_files.append(os.path.join(base, f))
    elif f == 'ALL_questions_batch017.json':
        part_files.insert(0, os.path.join(base, f))

print(f'Found {len(part_files)} part files:')
for pf in part_files:
    print(f'  {os.path.basename(pf)}')

all_qs = []
for pf in part_files:
    with open(pf, 'r', encoding='utf-8') as f:
        qs = json.load(f)
    all_qs.extend(qs)
    print(f'  Loaded {len(qs)} from {os.path.basename(pf)}')

total = len(all_qs)
print(f'\nTOTAL: {total} questions')

if total != 300:
    print(f'WARNING: Expected 300, got {total}')

# Remove duplicates by ID
seen = set()
unique = []
dups = []
for q in all_qs:
    if q['id'] not in seen:
        seen.add(q['id'])
        unique.append(q)
    else:
        dups.append(q['id'])

if dups:
    print(f'\nDUPLICATES removed: {dups}')
    all_qs = unique
    print(f'After dedup: {len(all_qs)} questions')

# Verify ID coverage
ids = set(q['id'] for q in all_qs)
expected = set(f'batch017_Q{i:03d}' for i in range(1, 301))
missing = expected - ids
extra = ids - expected
if missing:
    print(f'MISSING IDs: {sorted(missing)}')
if extra:
    print(f'EXTRA IDs: {sorted(extra)}')

# Sort by ID
all_qs.sort(key=lambda x: x['id'])

# Stats
bloom = {}
qtypes = {}
mods = {}
for q in all_qs:
    bl = q['bloom_level']
    bloom[bl] = bloom.get(bl, 0) + 1
    qt = q['question_type']
    qtypes[qt] = qtypes.get(qt, 0) + 1
    mods[q['module']] = mods.get(q['module'], 0) + 1

print(f'\n=== Bloom ===')
for bl in ['记忆', '理解', '应用', '分析']:
    c = bloom.get(bl, 0)
    print(f'  {bl}: {c} ({c/total*100:.1f}%)')

print(f'\n=== Types ===')
for qt in ['A1', 'A2', 'B1', 'X']:
    c = qtypes.get(qt, 0)
    print(f'  {qt}: {c} ({c/total*100:.1f}%)')

print(f'\n=== Modules ===')
for m, c in sorted(mods.items(), key=lambda x: -x[1]):
    print(f'  {m}: {c}')

# R2 check
r2_bad = 0
for q in all_qs:
    opts = q.get('options', [])
    lens = []
    for o in opts:
        text = o.split('. ', 1)[-1] if '. ' in o else o
        lens.append(len(text))
    if lens and max(lens) / min(lens) > 3.0:
        r2_bad += 1
print(f'\nR2 > 3.0: {r2_bad} questions')

# Write final
output = os.path.join(base, 'ALL_questions_batch017.json')
with open(output, 'w', encoding='utf-8') as f:
    json.dump(all_qs, f, ensure_ascii=False, indent=2)
size = os.path.getsize(output)
print(f'\nFinal file: {output}')
print(f'Questions: {len(all_qs)}')
print(f'Size: {size:,} bytes')

# Verify can be reloaded
with open(output, 'r', encoding='utf-8') as f:
    verify = json.load(f)
assert len(verify) == len(all_qs), f'Verify mismatch: {len(verify)} vs {len(all_qs)}'
print('Reload verify: OK')

# Clean up part files
for pf in part_files:
    if os.path.basename(pf) != 'ALL_questions_batch017.json':
        os.remove(pf)
        print(f'Cleaned: {os.path.basename(pf)}')

print('\nDONE!')
