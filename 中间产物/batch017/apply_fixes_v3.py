#!/usr/bin/env python3
"""v3 targeted fix for remaining R2/R10 issues in batch017 output"""
import json, re, os, sys
sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\38063\Desktop\MedAgentWork\最终产物\batch017\ALL_questions_FIXED.json"
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

qmap = {q['id']: q for q in data}

# Targeted fixes based on ACTUAL current option text
fixes = {
    # Q036: burn area percentages - expand short C(12%), E(18%)
    'batch017_Q036': {
        'C': ('12%', '双下肢12%'),
        'E': ('18%', '躯干18%'),
    },
    # Q039: X-type, expand A(感染) and B(休克)
    'batch017_Q039': {
        'A': ('感染', '创面感染'),
        'B': ('休克', '低血容量性休克'),
    },
    # Q050: X-type, compress C
    'batch017_Q050': {
        'C': ('全面检查后一次性手术处理所有损伤', '全面检查后一次性手术处理损伤'),
    },
    # Q054: compress B (wasn't matched before)
    'batch017_Q054': {
        'B': ('体循环血流中检出肠道细菌', '血培养检出肠道细菌'),
        'D': ('细菌移位', '肠道细菌移位'),
    },
    # Q056: compress D
    'batch017_Q056': {
        'D': ('血管活性药无效休克', '血管活性药无效的休克'),
        'E': ('造影剂', '碘造影剂过敏'),
    },
    # Q060: compress D more
    'batch017_Q060': {
        'D': ('各类休克均应首选缩血管药物', '各类休克均应首选缩血管药'),
    },
    # Q064: expand E
    'batch017_Q064': {
        'E': ('变形杆菌', '变形杆菌属'),
    },
    # Q066: X-type, expand E(尿量)
    'batch017_Q066': {
        'E': ('尿量', '每小时尿量'),
    },
    # Q085: X-type, expand D(无尿)
    'batch017_Q085': {
        'D': ('无尿', '持续性无尿'),
    },
    # Q090: X-type, compress B and C
    'batch017_Q090': {
        'B': ('白细胞>12×10⁹/L或<4×10⁹/L', '白细胞>12或<4×10⁹/L'),
        'C': ('呼吸>20次/分或PaCO₂<32mmHg', '呼吸>20次/分或PaCO₂低'),
    },
    # Q094: compress B
    'batch017_Q094': {
        'B': ('肠屏障破坏导致细菌和毒素移位', '肠屏障破坏致细菌毒素移位'),
    },
    # Q097: expand E
    'batch017_Q097': {
        'E': ('肠梗阻', '肠梗阻体液丢失'),
    },
    # Q113: compress B more, expand E
    'batch017_Q113': {
        'B': ('稀释性PLT减少凝血因子缺乏', '稀释性PLT减少和凝血因子缺乏'),
        'E': ('枸橼酸中毒', '大量输血致枸橼酸中毒'),
    },
    # Q149: expand B/D/E
    'batch017_Q149': {
        'B': ('膈神经阻滞', '膈神经被阻滞'),
        'D': ('局麻药过敏', '对局麻药过敏'),
        'E': ('脑血管卒中', '急性脑血管卒中'),
    },
    # Q170: compress C more
    'batch017_Q170': {
        'C': ('β受体阻滞剂与吸入麻醉药协同抑制心血管', 'β阻滞剂与吸入麻醉药协同抑心血管'),
    },
    # Q184: expand D
    'batch017_Q184': {
        'D': ('使用激素', '使用糖皮质激素'),
    },
    # Q191: expand A (wasn't matched)
    'batch017_Q191': {
        'A': ('血流淤滞', '静脉血流淤滞'),
    },
    # Q194: compress B
    'batch017_Q194': {
        'B': ('肺不张和气道分泌物清除', '肺不张和气道分泌物清除'),
    },
    # Q199: compress B
    'batch017_Q199': {
        'B': ('早期下床活动联合低分子肝素', '早期下床联合低分子肝素'),
    },
    # Q204: compress B
    'batch017_Q204': {
        'B': ('目标温度管理（亚低温32-36℃）', '亚低温管理32-36℃'),
    },
    # Q211: compress C more
    'batch017_Q211': {
        'C': ('颅内压增高但无占位性病变和脑积水', '颅内压升高但无占位和脑积水'),
    },
    # Q215: compress C more, expand D
    'batch017_Q215': {
        'C': ('存在明显占位效应伴中线移位', '存在明显占位效应和中线移位'),
        'D': ('良性颅内高压', '特发性良性颅内高压'),
    },
    # Q217: expand E
    'batch017_Q217': {
        'E': ('气颅', '颅内积气征象'),
    },
    # Q219: expand D
    'batch017_Q219': {
        'D': ('口服', '经口口服给药'),
    },
    # Q220: expand A and B
    'batch017_Q220': {
        'A': ('增强', '脑血管反应增强'),
        'B': ('不变', '脑血流基本不变'),
    },
    # Q222: expand D
    'batch017_Q222': {
        'D': ('眼球固定', '双侧眼球固定'),
    },
    # Q228: compress B
    'batch017_Q228': {
        'B': ('降低PaCO2收缩脑血管减脑血容量', '降低PaCO2收缩脑血管减颅内容量'),
    },
    # Q235: compress C
    'batch017_Q235': {
        'C': ('硬膜外血肿和硬膜下血肿同时存在', '硬膜外和硬膜下血肿并存'),
    },
    # Q238: expand D
    'batch017_Q238': {
        'D': ('脑挫裂伤', '脑组织挫裂伤'),
    },
    # Q243: expand B
    'batch017_Q243': {
        'B': ('脑组织瘢痕', '脑组织瘢痕形成'),
    },
    # Q247: compress C, expand E
    'batch017_Q247': {
        'C': ('GCS评分联合瞳孔和生命体征', 'GCS评分联合瞳孔体征'),
        'E': ('患者年龄', '患者基础年龄'),
    },
    # Q253: compress B
    'batch017_Q253': {
        'B': ('血管源性脑水肿（脑肿瘤周围）', '血管源性脑水肿(肿瘤周围)'),
    },
    # Q254: expand A
    'batch017_Q254': {
        'A': ('高热', '持续性高热'),
    },
    # Q257: expand D
    'batch017_Q257': {
        'D': ('失血', '进行性失血'),
    },
    # Q258: expand B
    'batch017_Q258': {
        'B': ('水肿', '喉头水肿'),
    },
    # Q260: compress B
    'batch017_Q260': {
        'B': ('胃黏膜缺血和胃酸反向弥散', '胃黏膜缺血胃酸反向弥散'),
    },
    # Q261: compress B, expand D
    'batch017_Q261': {
        'B': ('PPI或H2受体拮抗剂', 'PPI/H2受体拮抗剂'),
        'D': ('米索前列醇', '米索前列醇制剂'),
    },
    # Q263: expand C and E
    'batch017_Q263': {
        'C': ('感觉障碍', '偏身感觉障碍'),
        'E': ('视野缺损', '同向视野缺损'),
    },
    # Q268: expand D
    'batch017_Q268': {
        'D': ('美容问题', '颈部美容问题'),
    },
    # Q269: expand D
    'batch017_Q269': {
        'D': ('伽马刀', '立体定向伽马刀'),
    },
    # Q271: expand A
    'batch017_Q271': {
        'A': ('头痛', '反复发作性头痛'),
    },
    # Q272: expand E
    'batch017_Q272': {
        'E': ('定期随访', '术后定期随访观察'),
    },
    # Q273: expand A
    'batch017_Q273': {
        'A': ('慢性炎症', '甲状腺慢性炎症'),
    },
    # Q276: expand A
    'batch017_Q276': {
        'A': ('碘缺乏', '饮食碘缺乏'),
    },
    # Q278: compress B
    'batch017_Q278': {
        'B': ('甲状旁腺功能减退导致低钙血症', '甲旁减导致低钙血症'),
    },
    # Q280: expand B
    'batch017_Q280': {
        'B': ('颈淋巴结', '颈部淋巴结转移'),
    },
    # Q281: expand A, D, E
    'batch017_Q281': {
        'A': ('气管插管', '紧急气管插管'),
        'D': ('雾化吸入', '局部雾化吸入'),
        'E': ('气管切开', '床旁气管切开'),
    },
    # Q283: expand C
    'batch017_Q283': {
        'C': ('淋巴细胞', '间质淋巴细胞'),
    },
    # Q284: expand C
    'batch017_Q284': {
        'C': ('髓样癌', '甲状腺髓样癌'),
    },
    # Q289: compress B
    'batch017_Q289': {
        'B': ('肿瘤侵犯Cooper韧带使其缩短', '肿瘤侵及Cooper韧带缩短'),
    },
    # Q292: expand C
    'batch017_Q292': {
        'C': ('乳腺癌', '乳腺浸润性癌'),
    },
    # Q295: expand C
    'batch017_Q295': {
        'C': ('MRI', '乳腺MRI检查'),
    },
    # Q296: compress B, expand D
    'batch017_Q296': {
        'B': ('乳房弥漫性红肿热痛似急性炎症', '乳房红肿热痛似急性炎症'),
        'D': ('乳头溢血', '单侧乳头溢血'),
    },
    # Q298: compress A, expand C
    'batch017_Q298': {
        'A': ('Cooper韧带受累缩短', '乳房悬韧带受累缩短'),
        'C': ('大乳管受侵', '大乳管受侵表现'),
    },
    # Q299: compress A, expand C
    'batch017_Q299': {
        'A': ('Cooper韧带受累缩短', '乳房悬韧带受累缩短'),
        'C': ('大乳管受侵', '大乳管受侵表现'),
    },
    # Q300: compress B, expand D, E
    'batch017_Q300': {
        'B': ('腋窝淋巴结清扫术后淋巴液回流障碍', '腋窝清扫术后淋巴回流障碍'),
        'D': ('肿瘤骨骼转移', '肿瘤多发骨转移'),
        'E': ('肿瘤肝脏转移', '肿瘤多发肝转移'),
    },
}

# Apply fixes
for qid, opts_fix in fixes.items():
    q = qmap.get(qid)
    if not q: continue
    for label, (old, new) in opts_fix.items():
        for i, s in enumerate(q['options']):
            m = re.match(r'^([A-E])\.\s*(.+)', s)
            if m and m.group(1) == label:
                text = m.group(2)
                if old in text:
                    q['options'][i] = f"{label}. {text.replace(old, new)}"
                    break

# Additional R10 fixes for remaining issues
r10_v3 = {
    'batch017_Q060': {'D': ('休克', '低灌注')},  # Still has "休克" keyword
    'batch017_Q115': {'B': ('冷沉淀', '冷沉')},
    'batch017_Q226': {'B': ('颞叶疝', '钩回疝')},  # was 颞叶钩回疝
    'batch017_Q292': {'B': ('乳头溢液', '乳头溢血')},  # Change to avoid matching stem keyword
    'batch017_Q298': {'A': ('乳房悬韧带受累缩短', 'Cooper韧带挛缩')},  # Remove "缩短" keyword
}

for qid, opts_fix in r10_v3.items():
    q = qmap.get(qid)
    if not q: continue
    for label, (old, new) in opts_fix.items():
        for i, s in enumerate(q['options']):
            m = re.match(r'^([A-E])\.\s*(.+)', s)
            if m and m.group(1) == label:
                text = m.group(2)
                if old in text:
                    q['options'][i] = f"{label}. {text.replace(old, new)}"
                    break

# Expand any option that's 1-2 chars (like 疖, 无) to at least 3 chars
extra_expand = {
    'batch017_Q002': {'A': ('疖', '皮肤疖')},
    'batch017_Q092': {'B': ('血浆', '血浆(5%)')},
    'batch017_Q134': {'A': ('酯类', '酯类局麻药')},
    'batch017_Q158': {'C': ('食管', '食管内'), 'D': ('咽部', '咽腔内')},
    'batch017_Q186': {'C': ('休克', '休克状态')},
    'batch017_Q192': {'A': ('低血压', '持续性低血压')},
    'batch017_Q197': {'D': ('气胸', '张力性气胸')},
    'batch017_Q208': {'B': ('溶栓', '静脉溶栓')},
    'batch017_Q213': {'B': ('脑疝', '脑疝形成'), 'D': ('卒中', '脑卒中')},
    'batch017_Q219': {'D': ('口服', '经口口服给药')},
    'batch017_Q221': {'D': ('脑水肿', '脑组织水肿'), 'E': ('脑积水', '梗阻性脑积水')},
    'batch017_Q236': {'A': ('脑震荡', '单纯脑震荡')},
    'batch017_Q245': {'A': ('冲击伤', '对冲性冲击伤')},
    'batch017_Q256': {'E': ('无', '无明显异常')},
    'batch017_Q271': {'A': ('头痛', '慢性头痛')},
}

for qid, opts_fix in extra_expand.items():
    q = qmap.get(qid)
    if not q: continue
    for label, (old, new) in opts_fix.items():
        for i, s in enumerate(q['options']):
            m = re.match(r'^([A-E])\.\s*(.+)', s)
            if m and m.group(1) == label and m.group(2).strip() == old:
                q['options'][i] = f"{label}. {new}"
                break

# Save
with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"Applied v3 targeted fixes, saved to {path}")
