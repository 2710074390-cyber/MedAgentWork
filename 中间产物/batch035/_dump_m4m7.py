#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\38063\Desktop\MedAgentWork'
with open(BASE + r'\中间产物\batch035\ALL_questions_FIXED.json', encoding='utf-8') as f:
    fixed = json.load(f)
by_suffix = {}
for q in fixed:
    by_suffix[q['id'].split('-', 1)[1]] = q

for sid in ['M4-A2-002', 'M7-A1-006', 'M7-A1-007', 'M7-A1-001', 'M7-A1-002', 'M7-A1-004', 'M7-A1-005', 'M7-B1-001', 'M7-B1-002']:
    q = by_suffix.get(sid)
    print('=== %s | %s | ans=%s | topic=%s' % (q['id'], q['type'], q.get('answer'), q.get('topic')))
    print('   stem: %s' % q['stem'][:150])
    print('   opts: %s' % ' | '.join(o['text'] for o in q['options'])[:220])
    print()

with open(BASE + r'\中间产物\batch035\kaoyan_candidates_emergency.json', encoding='utf-8') as f:
    kc = json.load(f)
for c in kc['candidates']:
    if c['gs_id'] in ('GS-2015-108', 'GS-2018-070', 'GS-2014-063', 'GS-2014-096'):
        print('--- GS %s 完整解析:' % c['gs_id'])
        print((c.get('explanation') or '')[:1200])
        print()
