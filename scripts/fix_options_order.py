# -*- coding: utf-8 -*-
"""Proper fix: shuffle option order so correct answer position varies"""
import json, os, random
random.seed(42)

BASE = r"C:\Users\38063\Desktop\MedAgentWork"
with open(os.path.join(BASE,'中间产物','predict_100q_final.json'),'r',encoding='utf-8') as f:
    qs = json.load(f)

# For each question, shuffle option order, then reassign labels A-E
for q in qs:
    tp = q['type']
    if tp in ('X',): continue  # X type: keep order, already multi-select

    opts = q.get('options', [])
    if not opts or tp == '\u5224\u65ad': continue  # 判断: fixed A/B order

    # Remember which option text is correct
    old_ans_label = q['answer']
    correct_text = None
    for o in opts:
        if o['label'] == old_ans_label:
            correct_text = o['text']
            break

    if correct_text is None: continue

    # Collect all option texts, shuffle, ensure correct one gets a new position
    texts = [o['text'] for o in opts]

    # Round-robin target position for correct answer
    target_pos = random.randint(0, len(texts) - 1)

    # Remove correct text, shuffle others, insert at target position
    other_texts = [t for t in texts if t != correct_text]
    random.shuffle(other_texts)
    other_texts.insert(target_pos, correct_text)

    # Rebuild options with labels A-E
    new_opts = []
    labels = ['A','B','C','D','E'][:len(other_texts)]
    for i, text in enumerate(other_texts):
        new_opts.append({'label': labels[i], 'text': text})
        if text == correct_text:
            q['answer'] = labels[i]

    q['options'] = new_opts

# Verify
pos_dist = {}
ans_dist = {}
for q in qs:
    tp = q['type']
    if tp not in ('A1','A2'): continue
    a = q['answer']
    ans_dist[a] = ans_dist.get(a,0)+1
    for i, o in enumerate(q.get('options',[])):
        if o['label'] == a:
            pos_dist[i+1] = pos_dist.get(i+1,0)+1
            break

print("=== A1/A2 Answer Labels ===")
for k in sorted(ans_dist): print(f'  {k}: {ans_dist[k]}')
print("\n=== A1/A2 Correct Answer Position ===")
for k in sorted(pos_dist): print(f'  Position {k}: {pos_dist[k]}')

# Save
out = os.path.join(BASE, '中间产物', 'predict_100q_final.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(qs, f, ensure_ascii=False, indent=2)
print(f'\nSaved fixed data.')
