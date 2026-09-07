import json

with open(r'c:\Users\38063\Desktop\MedAgentWork\中间产物\batch035\ALL_questions_FIXED.json', 'r', encoding='utf-8') as f:
    qs = json.load(f)
q_by_id = {q['id']: q for q in qs}

# Check R10/FAIL questions
r10_ids = ['batch031-M3-A1-001', 'batch035-M7-A2-004', 'batch035-M7-B1-001', 'batch035-M10-B1-001', 'batch031-M6-B1-002']
for qid in r10_ids:
    q = q_by_id.get(qid)
    if q:
        print(f'=== {qid} (answer={q["answer"]}) ===')
        print(f'STEM: {q["stem"][:80]}')
        for opt in q['options']:
            print(f'  {opt["label"]}: {opt["text"]}')
        print()

# Check R1
print('=== batch035-M7-A1-002 ===')
q = q_by_id.get('batch035-M7-A1-002')
if q:
    print(f'STEM: {q["stem"][:80]}')
    for opt in q['options']:
        print(f'  {opt["label"]}: {opt["text"]}')

# Check R2 FAIL questions
print('\n=== R2 FAIL questions ===')
for qid in sorted(q_by_id.keys()):
    q = q_by_id[qid]
    opts = q['options']
    lengths = {opt['label']: len(opt['text']) for opt in opts}
    if min(lengths.values()) == 0:
        continue
    max_len = max(lengths.values())
    min_len = min(lengths.values())
    ratio = max_len / min_len
    if ratio > 2.0:
        max_opt = max(lengths, key=lengths.get)
        min_opt = min(lengths, key=lengths.get)
        print(f'{qid}: ratio={ratio:.1f}x, {max_opt}={max_len} vs {min_opt}={min_len}')
        for opt in q['options']:
            print(f'  {opt["label"]}: {opt["text"]} ({len(opt["text"])}字)')
        print()