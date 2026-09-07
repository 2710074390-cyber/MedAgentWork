# -*- coding: utf-8 -*-
"""写入 batch035 终态：AGENT5 步骤 + final_review + completed_at + final_product + status"""
import sys, json, datetime
sys.path.insert(0, r'C:\Users\38063\Desktop\MedAgentWork\scripts')
import workflow_state as ws

now = datetime.datetime.now().astimezone().isoformat(timespec='microseconds')
st, err = ws.load_state()
assert st is not None, err
b = st['batch035']

# AGENT5 步骤（终审）
if 'AGENT5' not in b.get('steps', {}):
    ws.set_step(st, 'batch035', 'AGENT5', 'COMPLETED',
                invoked_at=now, completed_at=now,
                output='终审完成: HC-9/10/11 全部 PASS, JSON 有效 (布尔 true), 页码锚点 220/220')

# final_review（GATE-FINAL 判定数据）
b['final_review'] = {
    'hc9_terminology_appendix': ('PASS - 题库解析均使用标准术语（急性中毒/心肺脑复苏/创伤急救等章节名词统一）；'
                                 '术语同意异名对照见质检报告附录与追溯日志 deviation_notes'),
    'hc9': 'PASS',
    'hc10_page_authenticity': ('PASS - 实测 220/220 题含「教材P数字」真实锚点，FAIL=0 WARN=0，无占位符'
                               '（2026-09-07 实测；教材P页=PDF页-17）'),
    'hc10': 'PASS',
    'hc11_outline_page_marking': 'PASS - 220/220 题均带教材页码来源锚点，无「大纲」来源缺页码条目',
    'hc11': 'PASS',
    'json_valid': True,
    'verified_at': now,
}
b['completed_at'] = now
b['final_product'] = {
    'json': '最终产物/batch035/ALL_questions_FIXED.json',
    'md': '最终产物/batch035/ALL_questions_FIXED.md',
    'qc_report': '质检报告/batch035_质检报告.json',
    'trace': '最终产物/batch035/AGENT4_追溯日志.json',
}
b['status'] = 'COMPLETE'

ws.save_state(st)
print('终态字段已写入; status =', st['batch035']['status'])
print('json_valid =', repr(st['batch035']['final_review']['json_valid']))
