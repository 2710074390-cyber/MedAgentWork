#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, sys, re
sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\38063\Desktop\MedAgentWork'
with open(BASE + r'\中间产物\batch035\ALL_questions_FIXED.json', encoding='utf-8') as f:
    fixed = json.load(f)
by_suffix = {}
for q in fixed:
    by_suffix[q['id'].split('-', 1)[1]] = q

fail = [
 ('R13', ['M5-A1-003','M8-A2-005','M8-A3-003']),
 ('R10', ['M3-A1-001','M4-A2-003','M7-B1-001','M8-A2-002','M10-B1-001']),
 ('R2', ['M2-A1-007','M3-A2-002','M3-A2-003','M3-A3-001','M4-A1-003','M4-A1-005','M4-A1-006','M4-A2-005','M4-A2-006','M4-A3-001','M4-X-001','M5-A1-005','M6-A1-008','M7-A1-003','M7-A2-002','M7-X-001','M8-X-002','M9-A1-004','M9-A3-003','M10-X-001']),
]
for rule, ids in fail:
    for sid in ids:
        q = by_suffix[sid]
        lens = [(o['label'], len(o['text']), o['text']) for o in q['options']]
        maxl = max(len(t) for _, l, t in lens)
        minl = min(len(t) for _, l, t in lens)
        print('### %s [%s] ans=%s lenmax/min=%d/%d ratio=%.2f' % (q['id'], rule, q.get('answer'), maxl, minl, maxl/minl))
        for lab, l, t in lens:
            print('    %s(%2d): %s' % (lab, l, t))
        print()
