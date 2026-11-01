# -*- coding: utf-8 -*-
"""BPA v1.0 结构自检：8 模块 × 8 区块、卡片八行、自测数量、附录五件套。"""
import re, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MD = Path(r'C:/Users/38063/Desktop/MedAgentWork/Obsidian产物/教师重点蓝图版/急诊与灾难医学_教师重点蓝图版_主复习资料.md')
t = MD.read_text(encoding='utf-8')
mods = re.split(r'\n## (M0[1-8]) ', t)[1:]
pairs = list(zip(mods[0::2], mods[1::2]))
print(f'modules={len(pairs)}')

BLOCKS = ['🧩 前置知识检查', '🎯 30 秒摘要', '📋 考点卡群', '📊 对比速查', '🔗 因果链', '🌳 决策树', '📌 一页纸', '🔄 主动回忆']
FIELDS = ['📌 重点原文', '🎯 一句话题眼', '🧬 为什么', '🔗 机制链', '⚖️ 鉴别', '🚨 红线', '🩺 下一步', '🔄 自测']
fail = 0
total_cards = 0
for name, body in pairs:
    missing = [b for b in BLOCKS if b not in body]
    cards = re.findall(r'^#### .*?K-M\d{2}-\d{3}', body, re.M)
    total_cards += len(cards)
    bad = []
    for c in re.split(r'\n#### ', body)[1:]:
        for f in FIELDS:
            if f not in c:
                bad.append(f)
    recall = len(re.findall(r'^- Q-M\d{2}-\d{2}', body, re.M))
    status = 'PASS' if not missing and not bad and recall >= 8 else 'FAIL'
    if status == 'FAIL':
        fail += 1
    print(f'{name}: blocks_missing={missing} cards={len(cards)} field_missing={sorted(set(bad))} recall={recall} -> {status}')

appendix_ok = all(x in t for x in ['附录一 页码索引', '附录二 术语同义异名', '附录三 口诀', '附录四 数字锚', '附录五 主动回忆答案'])
print(f'cards_total={total_cards} appendix5={appendix_ok} star_star={t.count("**")} mermaid={t.count("```mermaid")}')
print('RESULT', 'PASS' if fail == 0 and appendix_ok else 'FAIL')
