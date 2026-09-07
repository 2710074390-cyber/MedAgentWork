#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\38063\Desktop\MedAgentWork'
with open(BASE + r'\中间产物\batch035\ALL_questions_FIXED.json', encoding='utf-8') as f:
    fixed = json.load(f)
by_suffix = {}
for q in fixed:
    suffix = q['id'].split('-', 1)[1]
    by_suffix[suffix] = q

ids = [
    'M4-X-001','M4-X-002','M3-B1-002','M4-A1-005','M7-A1-003','M5-A2-004',
    'M1-B1-001','M10-A1-001','M4-A1-011','M8-X-001','M4-A2-005','M4-A2-006',
    'M2-A2-007','M2-A3-002','M2-A3-003','M7-X-001','M4-B1-002','M4-A1-006',
    'M2-X-002','M2-A1-010','M2-A2-003','M5-A1-010','M6-X-001','M4-B1-001',
]
for sid in ids:
    q = by_suffix.get(sid)
    if not q:
        print('=== %s NOT FOUND' % sid); continue
    print('=== %s | %s | ans=%s | topic=%s' % (q['id'], q['type'], q.get('answer'), q.get('topic')))
    print('  stem:', q['stem'][:200])
    print('  opts:', ' | '.join(o['text'] for o in q['options']))
    print('  expl:', (q.get('explanation') or '')[:220])
    print()
