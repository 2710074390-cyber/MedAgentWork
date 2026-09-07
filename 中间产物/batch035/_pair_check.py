#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = r'C:\Users\38063\Desktop\MedAgentWork'
with open(BASE + r'\中间产物\batch035\kaoyan_candidates_emergency.json', encoding='utf-8') as f:
    kc = json.load(f)
cands = {c['gs_id']: c for c in kc['candidates']}
with open(BASE + r'\中间产物\batch035\ALL_questions_FIXED.json', encoding='utf-8') as f:
    fixed = json.load(f)
by_id = {q['id']: q for q in fixed}

def show_gs(gsid):
    c = cands[gsid]
    print('--- GS %s (%s) [%s] 答案=%s' % (gsid, c.get('year'), c.get('type'), c.get('answer')))
    print('  stem:', (c.get('stem') or '')[:150])
    print('  opts:', json.dumps(c.get('options'), ensure_ascii=False)[:250])
    print('  expl:', (c.get('explanation') or '')[:250])

pairs = [
    ('batch035-M2-A1-007', 'GS-2007-143'),
    ('batch035-M2-A3-001', 'GS-2015-068'),
    ('batch031-M4-A1-007', 'GS-2019-130'),
    ('batch031-M5-A1-001', 'GS-2003-076'),
    ('batch031-M4-A1-008', 'GS-1998-049'),
    ('batch031-M3-A1-005', 'GS-2019-061'),
    ('batch031-M3-A1-007', 'GS-2014-096'),
    ('batch035-M8-B1-002', 'GS-2014-045'),
    ('batch035-M9-A2-001', 'GS-2010-113'),
    ('batch035-M8-A1-010', 'GS-2018-047'),
]
for qid, gsid in pairs:
    q = by_id[qid]
    print('=== %s | %s | ans=%s | topic=%s' % (qid, q['type'], q.get('answer'), q.get('topic')))
    print('  stem:', q['stem'][:170])
    print('  opts:', ' | '.join(o['text'] for o in q['options']))
    show_gs(gsid)
    print()
