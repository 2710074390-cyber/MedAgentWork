#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch035 修复 pass v2 —— 格式化门禁清零
- 全局: 去除选项前导"主要"填充; 选项按 A-E 排序; X 型答案字母规范化
- 定向: 31 题 46 处 R13/R2 FAIL 逐一重写（保持医学内容、答案字母、数值不变）
- 输出: ALL_questions_FIXED.json（先备份）
"""
import json, sys, shutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(__file__).resolve().parent
SRC = BASE / 'ALL_questions_FIXED.json'
BAK = BASE / '_bak_FIXED_v1.json'

# 定向重写: (id, label) -> 新文本
REWRITE = {
    # M1-A1-004: R13 B/C/D 过长
    ('batch035-M1-A1-004', 'B'): '救治时间窗内早期目标治疗，具时限急迫性',
    ('batch035-M1-A1-004', 'C'): '早期纠正器官功能紊乱可逆转，具机制可逆性',
    ('batch035-M1-A1-004', 'D'): '急诊症状零乱复杂，需跨专科综合分析',
    # M2-A1-008: R2 E/C
    ('batch035-M2-A1-008', 'A'): '肝脏',
    ('batch035-M2-A1-008', 'B'): '肾脏',
    ('batch035-M2-A1-008', 'E'): '中枢神经',
    # M2-A1-011: R2 A/B/D
    ('batch035-M2-A1-011', 'A'): '血液透析',
    ('batch035-M2-A1-011', 'B'): '血液灌流',
    ('batch035-M2-A1-011', 'D'): 'CRRT',
    # M2-A2-002: R2 A/D
    ('batch035-M2-A2-002', 'A'): '动脉血气分析',
    ('batch035-M2-A2-002', 'C'): '颅脑CT检查',
    ('batch035-M2-A2-002', 'D'): '常规心电图',
    ('batch035-M2-A2-002', 'E'): '血电解质测定',
    # M2-A2-004: R2 A/E
    ('batch035-M2-A2-004', 'A'): '清水洗胃液',
    ('batch035-M2-A2-004', 'B'): '2%碳酸氢钠溶液',
    ('batch035-M2-A2-004', 'C'): '高锰酸钾洗胃液',
    ('batch035-M2-A2-004', 'D'): '生理盐水洗胃液',
    ('batch035-M2-A2-004', 'E'): '温开水洗胃液',
    # M2-B1-003: R2 D
    ('batch035-M2-B1-003', 'D'): 'CRRT',
    # M3-A1-001: R2 E + 语义
    ('batch031-M3-A1-001', 'A'): '1周以上',
    ('batch031-M3-A1-001', 'B'): '2周以上',
    ('batch031-M3-A1-001', 'C'): '3周以上',
    ('batch031-M3-A1-001', 'D'): '4周以上',
    ('batch031-M3-A1-001', 'E'): '5周以上',
    # M3-A1-003: R2 A + R13 无
    ('batch031-M3-A1-003', 'A'): '呼吸频率明显加快',
    ('batch031-M3-A1-003', 'B'): '呼吸窘迫,一般吸氧不缓解',
    # M4-A1-006: R2 A/B/E
    ('batch031-M4-A1-006', 'A'): '大脑皮质',
    ('batch031-M4-A1-006', 'B'): '脑干脑桥',
    ('batch031-M4-A1-006', 'C'): '基底节区及内囊',
    ('batch031-M4-A1-006', 'E'): '丘脑区',
    # M4-A1-009: R2 C/D
    ('batch031-M4-A1-009', 'C'): '先天性动脉瘤破裂',
    ('batch031-M4-A1-009', 'D'): '血液系统疾病',
    # M4-A2-003: R2 C
    ('batch031-M4-A2-003', 'C'): '急性胃肠炎伴脱水',
    # M4-A2-006: R2 A/E
    ('batch031-M4-A2-006', 'A'): '静注50%葡萄糖40~60ml',
    ('batch031-M4-A2-006', 'D'): '静脉注射甘露醇',
    ('batch031-M4-A2-006', 'E'): '静脉注射地西泮',
    # M5-A1-003: R13 A/B/C/D + R2 + 排序
    ('batch031-M5-A1-003', 'A'): 'CI<1.5，PAWP<8mmHg',
    ('batch031-M5-A1-003', 'B'): 'CI<2.2，PAWP>18mmHg',
    ('batch031-M5-A1-003', 'C'): 'CI2.5~4，PAWP12~18mmHg',
    ('batch031-M5-A1-003', 'D'): 'CI>4.0，PAWP<10mmHg',
    ('batch031-M5-A1-003', 'E'): 'CI正常，PAWP>25mmHg',
    # M5-X-001: R2 B + 排序 + 答案规范化
    ('batch031-M5-X-001', 'A'): '尿量≥0.5ml/(kg·h)',
    ('batch031-M5-X-001', 'B'): '中心静脉或混合静脉血氧饱和度≥70%',
    ('batch031-M5-X-001', 'C'): '中心静脉压达到8～12mmHg',
    ('batch031-M5-X-001', 'D'): '平均动脉压≥65mmHg',
    ('batch031-M5-X-001', 'E'): '尿量≥100ml/h',
    # M5-X-002: R2 A/D
    ('batch031-M5-X-002', 'A'): '神志淡漠,反应迟钝,意识模糊',
    ('batch031-M5-X-002', 'D'): '尿量减少甚至无尿',
    # M6-A1-002: R2 E
    ('batch031-M6-A1-002', 'E'): '出汗仅补水,致低钠低氯血症',
    # M6-A2-003: R2 E
    ('batch031-M6-A2-003', 'E'): '切断电源,使触电者脱离电源',
    # M6-A3-001: R2 B/C/D
    ('batch031-M6-A3-001', 'B'): '非劳力性热射病',
    ('batch031-M6-A3-001', 'C'): '中暑热衰竭',
    ('batch031-M6-A3-001', 'D'): '中暑热痉挛',
    # M6-A3-002: R13 D + 排序
    ('batch031-M6-A3-002', 'A'): '2小时内降至39℃以下即可',
    ('batch031-M6-A3-002', 'B'): '4小时内缓慢降至38.5℃以下',
    ('batch031-M6-A3-002', 'C'): '10分钟内降至36℃以下',
    ('batch031-M6-A3-002', 'D'): '40分钟内至39℃,2小时内至38.5℃',
    ('batch031-M6-A3-002', 'E'): '60分钟内降至37℃以下',
    # M7-B1-001: R2 A/B/E
    ('batch035-M7-B1-001', 'A'): '缺血再灌注损伤学说',
    ('batch035-M7-B1-001', 'B'): '炎症反应失控学说',
    ('batch035-M7-B1-001', 'E'): '基因调控学说',
    # M8-A1-002: R2
    ('batch035-M8-A1-002', 'A'): '心室颤动',
    ('batch035-M8-A1-002', 'B'): '无脉性室速',
    ('batch035-M8-A1-002', 'C'): '心室静止',
    # M8-A1-011: R2
    ('batch035-M8-A1-011', 'A'): '动脉收缩压(SBP)',
    ('batch035-M8-A1-011', 'B'): '呼气末CO2分压(PetCO2)',
    ('batch035-M8-A1-011', 'C'): '中心静脉压(CVP)',
    ('batch035-M8-A1-011', 'D'): '肺动脉楔压(PAWP)',
    ('batch035-M8-A1-011', 'E'): '血乳酸水平(Lac)',
    # M8-A2-001: R2
    ('batch035-M8-A2-001', 'A'): '拨打急救电话等待专业救援',
    ('batch035-M8-A2-001', 'B'): '判断无反应启动EMSS开始CPR',
    ('batch035-M8-A2-001', 'C'): '立即行气管插管通气',
    ('batch035-M8-A2-001', 'D'): '立即实施电除颤治疗',
    ('batch035-M8-A2-001', 'E'): '立即将患者送往医院',
    # M8-A2-002: R13 B + R2
    ('batch035-M8-A2-002', 'A'): '立即实施电除颤治疗',
    ('batch035-M8-A2-002', 'B'): '先做5组CPR约2分钟再分析心律',
    ('batch035-M8-A2-002', 'C'): '立即行气管插管通气',
    ('batch035-M8-A2-002', 'D'): '立即静脉注射肾上腺素',
    ('batch035-M8-A2-002', 'E'): '立即建立静脉通道',
    # M8-A2-003: R2
    ('batch035-M8-A2-003', 'A'): '立即行气管切开术',
    ('batch035-M8-A2-003', 'B'): '腹部冲击法(Heimlich)',
    ('batch035-M8-A2-003', 'C'): '立即行气管插管术',
    ('batch035-M8-A2-003', 'D'): '立即给予高流量吸氧',
    ('batch035-M8-A2-003', 'E'): '立即行胸部冲击法',
    # M8-A2-004: R2 D
    ('batch035-M8-A2-004', 'D'): '立即实施电除颤',
    # M8-A2-005: R13 B/E + R2
    ('batch035-M8-A2-005', 'B'): '将患者整体向左侧倾斜15°~30°',
    ('batch035-M8-A2-005', 'E'): '气管导管内径较非孕妇女大0.5~1.0mm',
    # M8-A2-006: R13 B
    ('batch035-M8-A2-006', 'B'): '过度通气PaCO2降至25~30mmHg',
    # M8-A3-002: R13 C + R2
    ('batch035-M8-A3-002', 'B'): '立即再次行电除颤',
    ('batch035-M8-A3-002', 'C'): '行5组CPR约2分钟再查心律脉搏',
    ('batch035-M8-A3-002', 'E'): '立即行气管插管术',
    # M8-A3-003: R13 E + 排序
    ('batch035-M8-A3-003', 'A'): '静注肾上腺素1mg,继续CPR后再次电除颤',
    ('batch035-M8-A3-003', 'B'): '静注硫酸镁2g,继续CPR后再次电除颤',
    ('batch035-M8-A3-003', 'C'): '静注利多卡因100mg,继续CPR',
    ('batch035-M8-A3-003', 'D'): '静注碳酸氢钠100ml,继续CPR',
    ('batch035-M8-A3-003', 'E'): '静注胺碘酮300mg,继续CPR后再除颤',
    # M8-B1-001: R2
    ('batch035-M8-B1-001', 'A'): '1倍剂量',
    ('batch035-M8-B1-001', 'B'): '2~2.5倍剂量',
    ('batch035-M8-B1-001', 'C'): '3~4倍剂量',
    ('batch035-M8-B1-001', 'D'): '5倍剂量',
    ('batch035-M8-B1-001', 'E'): '无需调整剂量',
    # M8-X-001: R2
    ('batch035-M8-X-001', 'A'): '识别心脏骤停并启动急救系统',
    ('batch035-M8-X-001', 'B'): '立即行心肺复苏',
    ('batch035-M8-X-001', 'C'): '尽早实施电除颤',
    # M9-X-002: R2
    ('batch035-M9-X-002', 'A'): '心肺复苏',
    ('batch035-M9-X-002', 'B'): '止血技术',
    ('batch035-M9-X-002', 'C'): '包扎技术',
    ('batch035-M9-X-002', 'D'): '固定技术',
    ('batch035-M9-X-002', 'E'): '搬运技术',
    # M10-A1-001: R2
    ('batch035-M10-A1-001', 'A'): '仅指自然灾害，非人为',
    ('batch035-M10-A1-001', 'B'): '超出地区承受能力需外部援助',
    ('batch035-M10-A1-001', 'C'): '仅指人为事故及骚乱',
    ('batch035-M10-A1-001', 'D'): '仅指传染病暴发流行',
    ('batch035-M10-A1-001', 'E'): '仅指战争及武装冲突',
    # M10-B1-001: R2 B
    ('batch035-M10-B1-001', 'B'): '持续救援期',
    # M11-A1-001: R13 C/E
    ('batch035-M11-A1-001', 'C'): '现场救援人员易致心理创伤,需早期干预',
    ('batch035-M11-A1-001', 'E'): '现场救援优先保障伤员,救援人员安全其次',
    # X 答案规范化
    ('batch031-M5-X-001', '__answer__'): 'ABCD',
}

def main():
    with open(SRC, encoding='utf-8') as f:
        fixed = json.load(f)
    shutil.copy2(SRC, BAK)
    print(f'备份 → {BAK.name}')

    changed = 0
    for q in fixed:
        qid = q['id']
        # 1) 定向重写
        for o in q['options']:
            key = (qid, o['label'])
            if key in REWRITE:
                new = REWRITE[key]
                if o['text'] != new:
                    print(f'  改写 {qid} {o["label"]}: {o["text"]} → {new}')
                    o['text'] = new
                    changed += 1
        ak = (qid, '__answer__')
        if ak in REWRITE:
            if q.get('answer') != REWRITE[ak]:
                print(f'  答案 {qid}: {q.get("answer")} → {REWRITE[ak]}')
                q['answer'] = REWRITE[ak]
                changed += 1
        # 2) 去除前导"主要"
        for o in q['options']:
            if o['text'].startswith('主要'):
                new = o['text'][2:]
                print(f'  去主要 {qid} {o["label"]}: {o["text"]} → {new}')
                o['text'] = new
                changed += 1
        # 3) 选项按 A-E 排序
        q['options'].sort(key=lambda x: x['label'])
        # 4) X 型答案字母规范化
        if q.get('type') == 'X' and q.get('answer'):
            q['answer'] = ''.join(sorted(q['answer']))

    with open(SRC, 'w', encoding='utf-8') as f:
        json.dump(fixed, f, ensure_ascii=False, indent=1)
    print(f'完成，共 {changed} 处修改，输出 → {SRC.name}')

if __name__ == '__main__':
    main()
