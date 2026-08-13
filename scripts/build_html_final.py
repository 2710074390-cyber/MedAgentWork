# -*- coding: utf-8 -*-
import json, os

BASE = r"C:\Users\38063\Desktop\MedAgentWork"

with open(os.path.join(BASE,'中间产物','predict_js_string.txt'),'r',encoding='utf-8') as f:
    js_data = f.read()

with open(os.path.join(BASE,'中间产物','predict_js_data.json'),'r',encoding='utf-8') as f:
    items = json.load(f)
total_q = sum(1 for x in items if x['t'] == 'q')

# Read template
with open(__file__.replace('.py','_template.html'),'r',encoding='utf-8') as f:
    template = f.read()

html = template.replace('__JS_DATA__', js_data).replace('__TOTAL_Q__', str(total_q))

out_path = os.path.join(BASE, '最终产物', '神经病学押题卷_2026.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print('Generated:', out_path, f'({os.path.getsize(out_path):,} bytes)')
