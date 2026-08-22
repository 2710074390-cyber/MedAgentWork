#!/usr/bin/env python3
"""将合并题库导出为可读 Markdown"""

import json
import os

BASE = r'C:\Users\38063\Desktop\MedAgentWork'
inpath = os.path.join(BASE, '复习资料', '精神病学_统一题库_331题.json')
outpath = os.path.join(BASE, '复习资料', '精神病学_统一题库_331题.md')

data = json.load(open(inpath, 'r', encoding='utf-8'))

MODULE_NAMES = {
    'M1': '绪论', 'M2': '精神障碍的症状学', 'M3': '神经认知障碍',
    'M4': '精神活性物质所致精神障碍', 'M5': '精神分裂症及其他精神病性障碍',
    'M6': '抑郁障碍', 'M7': '双相及相关障碍', 'M8': '强迫及相关障碍',
    'M9': '躯体忧虑障碍及疑病障碍', 'M10': '应激相关障碍',
    'M11': '睡眠障碍', 'M12': '躯体治疗'
}

TYPE_NAMES = {'A1': 'A1型题', 'A2': 'A2型题', 'A3': 'A3型题', 'A4': 'A4型题',
              'B1': 'B1型题', 'X': 'X型题', '判断': '判断题'}

lines = []
lines.append('# 精神病学 统一题库（331题）')
lines.append('')
lines.append('> 合并批次：batch007(242) + batch023(70) + batch026(19) | 2026-07-04')
lines.append('> 12模块全覆盖 | 7种题型 | Bloom：记忆/理解/应用/分析')
lines.append('')
lines.append('---')
lines.append('')

# Group by module
from collections import defaultdict
by_module = defaultdict(list)
for q in data:
    by_module[q['module']].append(q)

seq = 0
for mod in sorted(by_module.keys()):
    qs = by_module[mod]
    mod_name = MODULE_NAMES.get(mod, mod)
    lines.append(f'## {mod} {mod_name}（{len(qs)}题）')
    lines.append('')

    for q in qs:
        seq += 1
        qt = q.get('question_type', '?')
        qt_name = TYPE_NAMES.get(qt, qt)
        bl = q.get('bloom_level', '?')
        src = q.get('batch_source', '?')
        lines.append(f'### {seq}. [{qt_name}] [{bl}] {q["question_id"]}')
        lines.append(f'> 来源：{src} | 模块：{mod} | 页码：{q.get("source_pages","")}')
        lines.append('')
        lines.append(f'**{q.get("stem","")}**')
        lines.append('')

        opts = q.get('options', [])
        if isinstance(opts, list):
            for o in opts:
                if isinstance(o, dict):
                    label = o.get('label', o.get('key', ''))
                    text = o.get('text', o.get('value', ''))
                    lines.append(f'{label}. {text}')
                else:
                    lines.append(str(o))
        lines.append('')

        ans = q.get('answer_key', '')
        if ans:
            lines.append(f'> **答案：{ans}**')
        else:
            lines.append(f'> **答案：(未标注)**')

        expl = q.get('explanation', '')
        if expl:
            if len(str(expl)) > 300:
                expl = str(expl)[:300] + '...'
            lines.append(f'> 解析：{expl}')

        lines.append('')
        lines.append('---')
        lines.append('')

# Write
with open(outpath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

size_kb = os.path.getsize(outpath) / 1024
print(f'Exported: {outpath}')
print(f'Lines: {len(lines)}')
print(f'Size: {size_kb:.1f} KB')
