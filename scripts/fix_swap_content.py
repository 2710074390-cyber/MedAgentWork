# -*- coding: utf-8 -*-
"""Fix: keep A/B/C/D/E label order, swap option CONTENT to balance answer distribution"""
import json, os, re
random = __import__('random')
random.seed(42)

BASE = r"C:\Users\38063\Desktop\MedAgentWork"

# Reload from parts (original order before shuffle)
all_qs = []
for p in ['predict_qs_part1.json','predict_qs_part2.json','predict_qs_part3.json']:
    with open(os.path.join(BASE,'中间产物',p),'r',encoding='utf-8') as f:
        all_qs.extend(json.load(f))

print(f'Loaded {len(all_qs)} questions from original parts')

# Round-robin target labels
targets = (['A','B','C','D','E'] * 30)
ti = 0
ans_dist = {}

for q in all_qs:
    tp = q['type']
    opts = q.get('options', [])
    if not opts:
        continue

    old_ans = q['answer']

    if tp == 'X':
        for a in old_ans:
            ans_dist[a] = ans_dist.get(a, 0) + 1
        continue

    if tp == 'B1':
        parts = old_ans.split('/')
        new_parts = []
        for p in parts:
            target = targets[ti % len(targets)]; ti += 1
            new_parts.append(target)
        q['answer'] = '/'.join(new_parts)
        for p in new_parts:
            ans_dist[p] = ans_dist.get(p, 0) + 1
        continue

    if tp == '\u5224\u65ad':
        ans_dist[old_ans] = ans_dist.get(old_ans, 0) + 1
        continue

    # A1/A2/A3: single answer. Swap content to target label.
    target = targets[ti % len(targets)]; ti += 1

    if old_ans == target:
        ans_dist[target] = ans_dist.get(target, 0) + 1
        continue

    # Find indices
    old_idx = None; target_idx = None
    for i, o in enumerate(opts):
        if o['label'] == old_ans: old_idx = i
        if o['label'] == target: target_idx = i

    if old_idx is not None and target_idx is not None:
        # Swap text content between old_ans position and target position
        opts[old_idx]['text'], opts[target_idx]['text'] = \
            opts[target_idx]['text'], opts[old_idx]['text']
        q['answer'] = target

    ans_dist[target] = ans_dist.get(target, 0) + 1

# Print distribution
print("\n=== Answer Distribution (content-swapped) ===")
total = sum(ans_dist.values())
for k in sorted(ans_dist.keys()):
    pct = ans_dist[k]/total*100
    bar = '#' * int(pct)
    print(f'  {k}: {ans_dist[k]:3d} ({pct:5.1f}%) {bar}')

# Position check for A1/A2
pos_dist = {}
for q in all_qs:
    if q['type'] not in ('A1','A2'): continue
    a = q['answer']
    for i, o in enumerate(q.get('options',[])):
        if o['label'] == a:
            pos_dist[i+1] = pos_dist.get(i+1, 0) + 1
            break
print("\n=== A1/A2 Position Distribution ===")
for k in sorted(pos_dist.keys()):
    print(f'  Position {k}: {pos_dist[k]}')

# Save
out = os.path.join(BASE, '中间产物', 'predict_100q_final.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(all_qs, f, ensure_ascii=False, indent=2)
print(f'\nSaved to predict_100q_final.json')

# Rebuild JS data
js_items = []
qnum = 0
for q in all_qs:
    tp = q['type']; stem = q['stem']; ans = q['answer']
    opts = q['options']; exp = q['explanation']; src = q['source_page']; bl = q['bloom']

    if tp == 'A3':
        match = re.match(r'^(.*?)[\(\uff08]\s*1\s*[\)\uff09]', stem)
        if match:
            case_text = match.group(1).strip()
            js_items.append({"t":"c","n":qnum+1,"cs":case_text})
            sub_stems = re.split(r'[\(\uff08]\d+[\)\uff09]', stem)
            correct_opt_text = ""
            for o in opts:
                if o['label'] == ans: correct_opt_text = o['text']; break
            compound_parts = correct_opt_text.split('\uff1b') if '\uff1b' in correct_opt_text else [correct_opt_text]
            for si in range(1, len(sub_stems)):
                sub_stem = sub_stems[si].strip()
                if not sub_stem: continue
                qnum += 1
                sub_opts = []
                for o in opts:
                    full = o['text']; parts = full.split('\uff1b') if '\uff1b' in full else [full]
                    sub_opts.append({"l":o['label'],"x":parts[si-1].strip() if si-1<len(parts) else parts[-1].strip()})
                js_items.append({"t":"q","n":qnum,"tp":"A3","s":f"({si}) {sub_stem}","o":sub_opts,"c":[ans],"ex":exp,"sr":src,"bl":bl})
        else:
            qnum += 1
            js_items.append({"t":"q","n":qnum,"tp":tp,"s":stem,"o":[{"l":o["label"],"x":o["text"]} for o in opts],"c":list(ans) if tp=='X' else [ans],"ex":exp,"sr":src,"bl":bl})

    elif tp == 'B1':
        ans_parts = ans.split('/')
        sub_stems = re.split(r'[\(\uff08]\d+[\)\uff09]', stem)
        prefix = sub_stems[0].strip()
        if prefix and len(prefix) > 5:
            js_items.append({"t":"b","n":qnum+1,"lb":prefix})
        sub_parts = [s.strip() for s in sub_stems[1:] if s.strip()]
        for si, sub_stem in enumerate(sub_parts):
            qnum += 1
            sub_ans = ans_parts[si] if si < len(ans_parts) else ans_parts[-1]
            js_items.append({"t":"q","n":qnum,"tp":"B1","s":f"({si+1}) {sub_stem}","o":[{"l":o["label"],"x":o["text"]} for o in opts],"c":[sub_ans],"ex":exp,"sr":src,"bl":bl})

    elif tp == 'X':
        qnum += 1
        js_items.append({"t":"q","n":qnum,"tp":tp,"s":stem,"o":[{"l":o["label"],"x":o["text"]} for o in opts],"c":list(ans),"ex":exp,"sr":src,"bl":bl})

    elif tp == '\u5224\u65ad':
        qnum += 1
        js_items.append({"t":"q","n":qnum,"tp":tp,"s":stem,"o":[{"l":"A","x":"\u6b63\u786e"},{"l":"B","x":"\u9519\u8bef"}],"c":[ans],"ex":exp,"sr":src,"bl":bl})

    else:
        qnum += 1
        js_items.append({"t":"q","n":qnum,"tp":tp,"s":stem,"o":[{"l":o["label"],"x":o["text"]} for o in opts],"c":[ans],"ex":exp,"sr":src,"bl":bl})

total_q = sum(1 for x in js_items if x['t'] == 'q')
print(f'JS items: {len(js_items)}, Questions: {total_q}')

js_parts = [json.dumps(item, ensure_ascii=False) for item in js_items]
js_data = '[\n' + ',\n'.join(js_parts) + '\n]'
with open(os.path.join(BASE,'中间产物','predict_js_string.txt'),'w',encoding='utf-8') as f:
    f.write(js_data)
print(f'JS data saved: {len(js_data):,} chars')
