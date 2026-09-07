# -*- coding: utf-8 -*-
"""探查 gate_check.py 的 final 阶段判定逻辑"""
import re, sys
sys.stdout.reconfigure(encoding='utf-8')
src = open('gate_check.py', encoding='utf-8').read()
for pat in ['final_review', 'hc9', 'hc10', 'hc11', 'GATE-FINAL', 'json_valid', 'run_gate_final', 'def run_gate']:
    idxs = [m.start() for m in re.finditer(re.escape(pat), src)]
    print(pat, len(idxs), '处')
i = src.find('run_gate_final')
if i < 0:
    # 找 final 相关函数定义
    for m in re.finditer(r'def (\w+)\(', src):
        name = m.group(1)
        if 'final' in name.lower() or 'review' in name.lower() or 'gate5' in name.lower():
            print('候选函数:', name, '@', m.start())
# 打印 main 中 final 分支
j = src.find("'final'")
while j >= 0:
    seg = src[max(0, j-200):j+200]
    if 'stage' in seg or 'args' in seg or 'run_gate' in seg:
        print('=== @', j, '===')
        print(seg)
        break
    j = src.find("'final'", j+1)
