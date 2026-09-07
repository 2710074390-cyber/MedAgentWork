#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\38063\Desktop\MedAgentWork'
with open(BASE + r'\中间产物\batch035\ALL_questions_FIXED.json', encoding='utf-8') as f:
    fixed = json.load(f)

ko = [q for q in fixed if q.get('kaoyan_origin')]
print('带 kaoyan_origin 题数:', len(ko))
from collections import Counter
print('模块分布:', dict(Counter(q['module'] for q in ko)))
for q in sorted(ko, key=lambda x: (x['module'], x['id'])):
    ko_ = q['kaoyan_origin']
    gs = ko_.get('gs_id') if isinstance(ko_, dict) else ko_
    mode = ko_.get('mode') if isinstance(ko_, dict) else '?'
    print('  %s | %s | gs=%s | mode=%s' % (q['id'], q['module'], gs, mode))
