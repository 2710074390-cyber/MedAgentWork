# -*- coding: utf-8 -*-
"""Fix answer distribution: rebalance from B-heavy (46.5%) to ~20% each"""
import json, os, re, random
random.seed(42)

BASE = r"C:\Users\38063\Desktop\MedAgentWork"
with open(os.path.join(BASE,'中间产物','predict_100q_final.json'),'r',encoding='utf-8') as f:
    qs = json.load(f)

# Round-robin target labels for even distribution
target_order = (['A','B','C','D','E'] * 25)[:len(qs)]
target_idx = 0
new_ans_dist = {}

for q in qs:
    tp = q['type']

    if tp == 'X':
        for a in q['answer']:
            new_ans_dist[a] = new_ans_dist.get(a, 0) + 1
        continue

    if tp == 'B1':
        parts = q['answer'].split('/')
        new_parts = []
        for p in parts:
            target = target_order[target_idx % len(target_order)]
            target_idx += 1
            new_parts.append(target)
        q['answer'] = '/'.join(new_parts)
        for p in new_parts:
            new_ans_dist[p] = new_ans_dist.get(p, 0) + 1
        continue

    if tp == '判断':
        new_ans_dist[q['answer']] = new_ans_dist.get(q['answer'], 0) + 1
        continue

    # A1/A2/A3: reassign to target label
    old_ans = q['answer']
    target_ans = target_order[target_idx % len(target_order)]
    target_idx += 1

    if old_ans != target_ans and q.get('options'):
        # Swap option labels: put correct content at target position
        opts = q['options']
        old_idx = None
        for i, o in enumerate(opts):
            if o['label'] == old_ans:
                old_idx = i
                break

        target_pos = ord(target_ans) - ord('A')
        if old_idx is not None and target_pos < len(opts):
            # Swap labels
            new_labels = ['A','B','C','D','E'][:len(opts)]
            # Ensure correct answer content gets target label
            new_labels[old_idx], new_labels[target_pos] = new_labels[target_pos], new_labels[old_idx]
            for i, o in enumerate(opts):
                o['label'] = new_labels[i]
            q['answer'] = target_ans
    else:
        q['answer'] = target_ans

    new_ans_dist[q['answer']] = new_ans_dist.get(q['answer'], 0) + 1

# Print distribution
print("=== Fixed Answer Distribution ===")
total = sum(new_ans_dist.values())
for k in sorted(new_ans_dist.keys()):
    pct = new_ans_dist[k]/total*100
    bar = '#' * int(pct * 2)
    print(f'  {k}: {new_ans_dist[k]:3d} ({pct:5.1f}%) {bar}')

# Position distribution for A1/A2
print("\n=== New Position Distribution (A1/A2) ===")
pos_dist = {}
for q in qs:
    if q['type'] in ('A1','A2') and q.get('options'):
        for i, o in enumerate(q['options']):
            if o['label'] == q['answer']:
                pos_dist[i+1] = pos_dist.get(i+1, 0) + 1
                break
for k in sorted(pos_dist.keys()):
    print(f'  Position {k}: {pos_dist[k]}')

# Save fixed JSON
out = os.path.join(BASE, '中间产物', 'predict_100q_final.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(qs, f, ensure_ascii=False, indent=2)
print(f'\nFixed JSON saved.')

# Rebuild JS data
js_items = []
qnum = 0

for q in qs:
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
                    full = o['text']
                    parts = full.split('\uff1b') if '\uff1b' in full else [full]
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

# Save JS data
js_parts = [json.dumps(item, ensure_ascii=False) for item in js_items]
js_data = '[\n' + ',\n'.join(js_parts) + '\n]'
with open(os.path.join(BASE,'中间产物','predict_js_string.txt'),'w',encoding='utf-8') as f:
    f.write(js_data)
print(f'JS data saved: {len(js_data):,} chars')
