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
 'M4-A3-002','M4-A3-003','M4-A1-001','M4-A1-002','M4-A1-004','M4-A1-009','M4-A1-010','M4-A1-012','M4-X-003',
 'M7-A1-008','M7-A2-001','M7-A3-001','M7-A3-002','M7-X-002','M7-A2-003','M7-A2-004',
 'M5-X-002','M5-A3-001','M5-A3-002','M5-A3-003','M5-A1-003','M5-A1-005','M5-A1-006','M5-A1-007','M5-A1-011',
 'M6-A3-001','M6-A3-002','M6-A1-003','M6-A1-007','M6-X-002','M6-A1-005',
 'M8-A2-005','M8-A2-006','M8-A3-001','M8-A3-002','M8-A3-003','M8-X-002','M8-X-003','M8-X-004','M8-B1-001','M8-A1-005','M8-A1-006','M8-A1-007','M8-A1-008','M8-A1-009','M8-A1-011','M8-A1-012','M8-A1-013',
 'M9-A1-007','M9-A1-008','M9-A1-009','M9-A1-010','M9-A1-011','M9-A2-002','M9-A2-003','M9-A2-005','M9-A3-001','M9-A3-002','M9-X-001','M9-X-002',
 'M10-A1-002','M10-A1-003','M10-A1-004','M10-A1-005','M10-A1-006','M10-A1-007','M10-A2-001','M10-A2-002','M10-A2-003','M10-B1-001','M10-X-001','M10-X-002','M10-X-003',
 'M11-A1-001','M11-A1-002','M11-A1-003','M11-A1-004','M11-A1-005','M11-A2-001','M11-A2-002','M11-A3-001','M11-A3-002','M11-A3-003','M11-B1-001','M11-X-001','M11-X-002','M11-X-003',
]
for sid in ids:
    q = by_suffix.get(sid)
    if not q:
        print('=== %s NOT FOUND' % sid); continue
    print('=== %s | %s | ans=%s | topic=%s' % (q['id'], q['type'], q.get('answer'), q.get('topic')))
    print('   stem: %s' % q['stem'][:150])
    print('   opts: %s' % ' | '.join(o['text'] for o in q['options'])[:220])
    print('   expl: %s' % (q.get('explanation') or '')[:180])
    print()
