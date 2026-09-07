#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\38063\Desktop\MedAgentWork'
with open(BASE + r'\中间产物\batch035\ALL_questions_FIXED.json', encoding='utf-8') as f:
    fixed = json.load(f)
by_id = {q['id']: q for q in fixed}

ids = [
    'batch035-M2-A1-013','batch035-M2-A2-002','batch035-M2-A2-004','batch035-M2-X-004',
    'batch035-M2-X-001','batch035-M2-A2-006','batch035-M4-X-001','batch035-M4-X-002',
    'batch035-M3-B1-002','batch035-M4-A1-005','batch035-M7-A1-003','batch035-M5-A2-004',
    'batch035-M1-B1-001','batch035-M10-A1-001','batch035-M4-A1-011','batch035-M8-X-001',
    'batch035-M4-A2-005','batch035-M4-A2-006','batch035-M2-A2-007',
    'batch035-M2-A3-002','batch035-M2-A3-003',
]
for qid in ids:
    q = by_id[qid]
    print('=== %s | %s | ans=%s | topic=%s' % (qid, q['type'], q.get('answer'), q.get('topic')))
    print('  stem:', q['stem'][:200])
    print('  opts:', ' | '.join(o['text'] for o in q['options']))
    print('  expl:', (q.get('explanation') or '')[:220])
    print()
