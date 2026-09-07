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

ids = [
    'M3-A1-001','M3-A1-002','M3-A1-004','M3-A3-001','M3-A3-002','M3-X-002',
    'M2-B1-003','M8-A2-004','M9-X-003','M7-A2-002','M9-A3-003','M5-A1-004',
    'M5-B1-001','M5-A1-002','M8-A2-001','M9-A2-004','M6-A1-002','M8-A1-004',
    'M3-A1-006','M5-A1-009','M5-A1-008','M3-A2-001','M3-A2-002','M3-A2-003',
]
for sid in ids:
    q = by_suffix.get(sid)
    if not q:
        print('=== %s NOT FOUND' % sid); continue
    print('=== %s | %s | ans=%s | topic=%s | ko=%s' % (q['id'], q['type'], q.get('answer'), q.get('topic'), bool(q.get('kaoyan_origin'))))
    print('  stem:', q['stem'][:170])
    print('  opts:', ' | '.join(o['text'] for o in q['options']))
    print('  expl:', (q.get('explanation') or '')[:200])
    print()
