import json

with open(r'c:\Users\38063\Desktop\MedAgentWork\中间产物\batch035\ALL_questions_FIXED.json', 'r', encoding='utf-8') as f:
    qs = json.load(f)
q_by_id = {q['id']: q for q in qs}

# Check all remaining R13 FAIL options (>20 chars)
print("=== R13 FAIL: Options > 20 chars ===")
for q in qs:
    qid = q['id']
    for opt in q['options']:
        if len(opt['text']) > 20:
            print(f"{qid} {opt['label']}: [{len(opt['text'])}] {opt['text']}")

print("\n=== R10 FAIL ===")
# Check batch031-M3-A1-001
q = q_by_id.get('batch031-M3-A1-001')
if q:
    print(f"batch031-M3-A1-001 (answer={q['answer']}):")
    print(f"  STEM: {q['stem'][:80]}")
    for opt in q['options']:
        print(f"  {opt['label']}: {opt['text']}")

# Check batch035-M10-B1-001
q = q_by_id.get('batch035-M10-B1-001')
if q:
    print(f"\nbatch035-M10-B1-001 (answer={q['answer']}):")
    print(f"  STEM: {q['stem'][:80]}")
    for opt in q['options']:
        print(f"  {opt['label']}: {opt['text']}")

# Check R8 FAIL
q = q_by_id.get('batch035-M7-A1-002')
if q:
    print(f"\nbatch035-M7-A1-002:")
    for opt in q['options']:
        print(f"  {opt['label']}: {opt['text']} ({len(opt['text'])}字)")