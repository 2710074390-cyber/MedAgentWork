#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\38063\Desktop\MedAgentWork'
with open(BASE + r'\中间产物\batch035\kaoyan_candidates_emergency.json', encoding='utf-8') as f:
    kc = json.load(f)
for i, c in enumerate(kc['candidates'], 1):
    print('[%02d] %s (%s) [%s] ans=%s' % (i, c['gs_id'], c.get('year'), c.get('type'), c.get('answer')))
    print('    stem: %s' % (c.get('stem') or '')[:130])
    print('    opts: %s' % json.dumps(c.get('options'), ensure_ascii=False)[:180])
    print('    expl: %s' % (c.get('explanation') or '')[:150])
