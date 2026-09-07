import json, sys
sys.stdout.reconfigure(encoding='utf-8')

base = r'c:\Users\38063\Desktop\MedAgentWork\中间产物\batch035'

# Load ALL_questions
with open(f'{base}/ALL_questions.json', 'r', encoding='utf-8') as f:
    questions = json.load(f)

# Extract used gs_ids
used_gs_ids = set()
for q in questions:
    ko = q.get('kaoyan_origin')
    if isinstance(ko, dict):
        gs_id = ko.get('gs_id', '')
        if gs_id:
            used_gs_ids.add(gs_id)

# Load kaoyan candidates
with open(f'{base}/kaoyan_candidates_emergency.json', 'r', encoding='utf-8') as f:
    kc_data = json.load(f)

candidates = kc_data['candidates']
print(f'Kaoyan candidates total: {len(candidates)}')
print(f'Used gs_ids: {len(used_gs_ids)}')

# Find unused candidates
unused = []
for c in candidates:
    gs_id = c.get('gs_id', '')
    if gs_id not in used_gs_ids:
        kw = c.get('matched_keywords', '')
        if isinstance(kw, list):
            kw = ', '.join(kw)
        unused.append({
            'gs_id': gs_id,
            'year': c.get('year', ''),
            'keywords': kw,
            'stem': c.get('stem', '')[:60]
        })

print(f'\nUnused candidates: {len(unused)}')
for u in unused:
    print(f'  {u["gs_id"]} ({u["year"]}) [{u["keywords"]}]: {u["stem"]}...')

# Check module distribution of kaoyan
module_ko = {}
for q in questions:
    m = q['module']
    has_ko = 'kaoyan_origin' in q
    module_ko[m] = module_ko.get(m, {'total': 0, 'ko': 0})
    module_ko[m]['total'] += 1
    if has_ko:
        module_ko[m]['ko'] += 1

print('\n--- Kaoyan by Module ---')
for m in sorted(module_ko.keys()):
    info = module_ko[m]
    pct = info['ko'] / info['total'] * 100
    marker = '⚠️' if pct < 10 and info['ko'] == 0 else '✅'
    print(f'  {m}: {info["ko"]}/{info["total"]} ({pct:.0f}%) {marker}')