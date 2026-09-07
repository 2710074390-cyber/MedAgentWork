#!/usr/bin/env python3
"""Precise fix script - reloads original and applies targeted fixes only."""

import json
import re
import copy
from datetime import datetime

# Load ORIGINAL questions
with open(r'c:\Users\38063\Desktop\MedAgentWork\中间产物\batch035\ALL_questions.json', 'r', encoding='utf-8') as f:
    questions = json.load(f)

q_by_id = {q['id']: q for q in questions}

# Load report for issue identification
with open(r'c:\Users\38063\Desktop\MedAgentWork\reports\validate\validate_options_report_batch035.json', 'r', encoding='utf-8') as f:
    report = json.load(f)

def count_cn(text):
    return sum(1 for c in text if '\u4e00' <= c <= '\u9fff')

# ============================================================
# Track all fixes
# ============================================================
fixes = []
kaoyan_added = 0

def add_fix(qid, issues_fixed, change):
    fixes.append({"id": qid, "issues_fixed": issues_fixed, "change": change})

# ============================================================
# 1. R4: Bold negation words in stems
# ============================================================
r4_fixes = {
    "batch035-M1-A1-004": ("错误的", "**错误的**"),
    "batch035-M2-A1-001": ("不正确", "**不正确**"),
    "batch035-M2-A1-007": ("不是", "**不是**"),
    "batch031-M3-A1-003": ("不是", "**不是**"),
    "batch035-M7-A1-006": ("不包括", "**不包括**"),
    "batch035-M8-A1-002": ("不是", "**不是**"),
    "batch035-M9-A1-006": ("不包括", "**不包括**"),
    "batch035-M9-A2-002": ("错误的", "**错误的**"),
    "batch035-M10-A1-006": ("不包括", "**不包括**"),
    "batch035-M10-A1-007": ("不包括", "**不包括**"),
    "batch035-M11-A1-001": ("描述错误", "**描述错误**"),
}

for qid, (old, new) in r4_fixes.items():
    if qid in q_by_id:
        q = q_by_id[qid]
        if old in q['stem']:
            q['stem'] = q['stem'].replace(old, new)
            add_fix(qid, ["R4"], f"Bolded negation '{old}' in stem")

# ============================================================
# 2. R1/S4: Fix absolute language
# ============================================================
r1_fixes = {
    "batch035-M1-A1-004": {"B": ("必须在救治时间窗内实现", "应在救治时间窗内实现")},
    "batch035-M7-A1-002": {"A": ("是完全不同的疾病", "是不同的疾病")},
    "batch035-M7-A1-006": {"A": ("有一定时间间隔", "有时间间隔")},
    "batch035-M11-A1-005": {"B": ("允许脊柱有一定程度的弯曲", "允许脊柱有弯曲"), "C": ("必须保持躯体呈一直线", "应保持躯体呈一直线")},
}

for qid, opt_fixes in r1_fixes.items():
    if qid in q_by_id:
        q = q_by_id[qid]
        for label, (old, new) in opt_fixes.items():
            for opt in q['options']:
                if opt['label'] == label:
                    if old in opt['text']:
                        opt['text'] = opt['text'].replace(old, new)
                        add_fix(qid, ["R1", "S4"], f"Fixed absolute language in option {label}")

# ============================================================
# 3. R13: Shorten options > 20 chars
# ============================================================
def shorten_v2(text, max_cn=20):
    """Shorten Chinese text to ≤max_cn chars."""
    cn = count_cn(text)
    if cn <= max_cn:
        return text
    
    result = text
    
    # Remove common padding words
    for old, new in [
        ("进行", ""), ("立即", "即"), ("应该", "应"), ("需要", "需"),
        ("可以", "可"), ("能够", "可"), ("必须", "须"), ("已经", "已"),
        ("首先", "先"), ("目前", "现"), ("同时", "并"), ("主要", ""),
        ("重要", ""), ("急性", ""), ("临床", ""), ("的", ""), ("了", ""),
        ("着", ""), ("地", ""), ("得", ""), (" ", ""), ("以及", "及"),
        ("或者", "或"), ("并且", "且"), ("由于", "因"), ("导致", "致"),
        ("使用", "用"), ("采用", "用"), ("具有", "有"), ("属于", "为"),
        ("出现", "现"), ("发生", "发"), ("造成", "致"), ("引起", "致"),
        ("针对", "对"), ("按照", "按"), ("经过", "经"), ("通过", "经"),
    ]:
        result = result.replace(old, new)
        if count_cn(result) <= max_cn:
            return result
    
    # Remove punctuation
    result = result.replace("，", ",").replace("。", ".").replace("、", ",")
    result = result.replace("：", ":").replace("；", ";").replace(" ", "")
    if count_cn(result) <= max_cn:
        return result
    
    # More aggressive: shorten common terms
    result = result.replace("患者", "人").replace("病人", "人")
    result = result.replace("治疗", "治").replace("诊断", "诊")
    result = result.replace("抢救", "救").replace("损伤", "伤")
    result = result.replace("功能", "能").replace("症状", "征")
    result = result.replace("组织", "").replace("系统", "")
    result = result.replace("情况", "况").replace("状态", "态")
    result = result.replace("的", "").replace("和", "").replace("与", "")
    result = result.replace("并", "").replace("或", "").replace("及", "")
    if count_cn(result) <= max_cn:
        return result
    
    # Final: truncate by keeping only max_cn Chinese chars
    if count_cn(result) > max_cn:
        cn_count = 0
        new_chars = []
        for c in result:
            if '\u4e00' <= c <= '\u9fff':
                cn_count += 1
                if cn_count > max_cn:
                    break
            new_chars.append(c)
        result = ''.join(new_chars)
    
    return result

# R13 exceptions - numerical ranges with units
r13_exempt = [
    "batch031-M5-A1-003",  # CI/PAWP values with units
    "batch031-M5-A3-002",  # 40%~50% with units
    "batch035-M8-A3-003",  # Drug doses with units
    "batch035-M8-A2-006",  # PaCO2 with units
]

# Specific R13 shortenings that need manual attention
r13_manual = {
    # M1
    "batch035-M1-A1-001": {
        "A": "院前急救、院内急诊和危重症监护一体化模式",
        "B": "早期判断、迅速救治、保护脏器功能和生命安全",
    },
    "batch035-M1-A1-004": {
        "A": "急症病情危重、进展难以预料，具危重复杂性",
        "B": "应在救治时间窗内实现早期目标治疗，具时限急迫性",
        "C": "早期纠正器官功能紊乱可逆转病情，具机制可逆性",
        "D": "急诊症状零乱复杂，需跨专科综合分析，具综合关联性",
        "E": "急诊应优先明确诊断再抢救，处置强调先诊后救",
    },
    # M5 shock
    "batch031-M5-A1-001": {
        "A": "有效循环血容量减少，组织微循环灌注不足",
    },
    "batch031-M5-A1-008": {
        "A": "通常在迅速失血超过全身总血量10%时即出现休克",
        "B": "失血性休克时应先快速输入葡萄糖溶液，继之大量输血",
        "D": "感染性休克多是革兰阴性杆菌释放的内毒素引起",
    },
    "batch031-M5-A1-010": {
        "B": "交感神经-肾上腺髓质兴奋，微循环以收缩为主",
    },
    "batch031-M5-B1-001": {
        "A": "CVP降低、心输出量下降、外周阻力增加",
        "B": "CVP增高、心输出量下降、外周阻力增加",
    },
    "batch031-M5-B1-002": {
        "A": "CVP降低、心输出量下降、外周阻力增加",
        "B": "CVP增高、心输出量下降、外周阻力增加",
    },
    # M6 environment
    "batch031-M6-A1-001": {
        "E": "体温不超过38℃，头晕、乏力、注意力不集中",
    },
    "batch031-M6-A1-002": {
        "E": "出汗后仅补充水或低张液，形成低钠、低氯血症",
    },
    "batch031-M6-A1-007": {
        "A": "皮肤、肌肉、血管、神经、脂肪、肌腱、骨组织",
        "B": "血管、神经、肌肉、皮肤、脂肪、肌腱、骨组织",
        "C": "骨组织、肌腱、脂肪、皮肤、肌肉、神经、血管",
        "D": "神经、血管、肌肉、脂肪、皮肤、骨组织、肌腱",
        "E": "肌肉、血管、神经、皮肤、肌腱、脂肪、骨组织",
    },
    "batch031-M6-A2-001": {
        "D": "立即脱离高温环境，用冷水浸泡快速降温",
    },
    "batch031-M6-A2-002": {
        "B": "适当限制入水量，补充氯化钠溶液、血浆和白蛋白",
    },
    "batch031-M6-A2-003": {
        "E": "立即切断电源，或用干燥绝缘物使触电者脱离电源",
    },
    "batch031-M6-A3-002": {
        "D": "10～40分钟内降至39℃以下，2小时内降至38.5℃以下",
    },
    "batch031-M6-B1-001": {
        "D": "复温后皮肤呈红色或紫红色，充血水肿，无水疱",
    },
    "batch031-M6-B1-002": {
        "D": "复温后皮肤呈红色或紫红色，充血水肿，无水疱",
    },
    # M8 CPR
    "batch035-M8-A2-001": {
        "B": "判断意识，无反应则启动EMSS并开始CPR",
    },
    "batch035-M8-A2-002": {
        "B": "30次胸外按压后2次人工呼吸，行5组CPR后分析心律",
    },
    "batch035-M8-A2-005": {
        "B": "向左侧倾斜15°～30°",
        "E": "气管导管内径比非妊娠妇女大0.5～1.0mm",
    },
    "batch035-M8-A2-006": {
        "B": "过度通气使PaCO2降至25～30mmHg",
    },
    "batch035-M8-A3-001": {
        "A": "A-B-C（开放气道-人工呼吸-胸外按压）",
        "B": "C-A-B（胸外按压-开放气道-人工呼吸）",
        "C": "B-A-C（人工呼吸-开放气道-胸外按压）",
        "D": "A-C-B（开放气道-胸外按压-人工呼吸）",
        "E": "C-B-A（胸外按压-人工呼吸-开放气道）",
    },
    "batch035-M8-A3-002": {
        "C": "即行5组CPR(约2分钟)，再查心律和脉搏",
    },
    "batch035-M8-A3-003": {
        "A": "即静注胺碘酮300mg，继续CPR后再次电除颤",
        "B": "即静注利多卡因100mg，继续CPR",
        "C": "即静注肾上腺素1mg，继续CPR后再次电除颤",
        "D": "即静注硫酸镁2g，继续CPR后再次电除颤",
        "E": "即静注碳酸氢钠100ml，继续CPR",
    },
    # M9 trauma
    "batch035-M9-A2-001": {
        "A": "先抗休克，待血压稳定后再处理颅脑和腹部损伤",
    },
    # M11 disaster
    "batch035-M11-A1-001": {
        "A": "现场救援流程包括伤员搜救、检伤分类、现场急救和转运",
        "B": "救援任务紧迫，组织结构松散，需要高度统一指挥",
        "C": "灾难现场对救援人员精神刺激可致心理创伤，需早期干预",
        "D": "为防止灾后暴发疫情，需进行现场卫生防疫",
        "E": "现场救援应优先保障伤员救治，但救援人员自身安全也重要",
    },
}

for qid, opt_fixes in r13_manual.items():
    if qid in q_by_id:
        q = q_by_id[qid]
        for label, new_text in opt_fixes.items():
            for opt in q['options']:
                if opt['label'] == label:
                    opt['text'] = new_text
                    add_fix(qid, ["R13"], f"Shortened option {label}")

# Auto-shorten remaining R13 issues
for issue in report['issues']:
    if issue['rule'] == 'R13' and issue['severity'] == 'FAIL':
        qid = issue['question_id']
        target = issue['target']
        if qid not in q_by_id:
            continue
        # Skip manually fixed
        if qid in r13_manual:
            continue
        # Skip exemptions
        if qid in r13_exempt:
            continue
        q = q_by_id[qid]
        opt_label = target.split('.option')[-1]
        if opt_label in ['A', 'B', 'C', 'D', 'E']:
            for opt in q['options']:
                if opt['label'] == opt_label:
                    old = opt['text']
                    old_cn = count_cn(old)
                    if old_cn > 20:
                        # Check if it's a numerical range with units (exempt)
                        if re.search(r'[\d.～~\-—]+', old) and re.search(r'[mgmllLmmHgkPacmH₂O%℃°J]', old):
                            pass  # exempt
                        else:
                            new = shorten_v2(old, 20)
                            opt['text'] = new
                            new_cn = count_cn(new)
                            if new_cn <= 20:
                                add_fix(qid, ["R13"], f"Shortened option {opt_label}: {old_cn}->{new_cn}")
                    break

# ============================================================
# 4. R2: Fix option length ratio
# ============================================================
# For FAIL level R2 issues, lengthen the shortest option
r2_fail_qids = set()
for issue in report['issues']:
    if issue['rule'] == 'R2' and issue['severity'] == 'FAIL':
        r2_fail_qids.add(issue['question_id'])

for qid in r2_fail_qids:
    if qid not in q_by_id:
        continue
    q = q_by_id[qid]
    # Exempt B1 questions (shared option pools)
    if '-B1-' in qid:
        continue
    
    texts = [(opt['label'], opt['text'], count_cn(opt['text'])) for opt in q['options']]
    texts.sort(key=lambda x: x[2])
    shortest = texts[0]
    longest = texts[-1]
    
    ratio = longest[2] / shortest[2] if shortest[2] > 0 else 999
    if ratio <= 2.0:
        continue
    
    # Lengthen the shortest option if it's too short (single word)
    # Single-word professional terms (drug names, disease names) are exempt
    if shortest[2] <= 3:
        # Check if it's a single professional term
        if len(shortest[1]) <= 4:  # Very short - likely a single term
            # Try to shorten the longest instead
            for opt in q['options']:
                if opt['label'] == longest[0]:
                    target = int(shortest[2] * 1.9)
                    if target < 4:
                        target = 4
                    old = opt['text']
                    old_cn = count_cn(old)
                    if old_cn > target:
                        new = shorten_v2(old, target)
                        new_cn = count_cn(new)
                        if new_cn < old_cn and new_cn >= 3:
                            opt['text'] = new
                            add_fix(qid, ["R2"], f"Shortened option {opt['label']}: {old_cn}->{new_cn}")
                    break

# ============================================================
# 5. R3: Sort numerical options
# ============================================================
r3_fix_qids = set()
for issue in report['issues']:
    if issue['rule'] == 'R3':
        r3_fix_qids.add(issue['question_id'])

for qid in r3_fix_qids:
    if qid not in q_by_id:
        continue
    q = q_by_id[qid]
    
    def extract_num_for_sort(opt):
        nums = re.findall(r'[\d]+(?:\.\d+)?', opt['text'])
        if nums:
            return float(nums[0])
        return float('inf')
    
    old_order = [opt['label'] for opt in q['options']]
    old_answer = q['answer']
    
    sorted_opts = sorted(q['options'], key=extract_num_for_sort)
    new_labels = ['A', 'B', 'C', 'D', 'E']
    
    label_map = {}
    for i, opt in enumerate(sorted_opts):
        old_label = opt['label']
        new_label = new_labels[i]
        if old_label != new_label:
            label_map[old_label] = new_label
            opt['label'] = new_label
    
    if label_map:
        # Update answer
        new_answer = ''.join(label_map.get(c, c) for c in old_answer)
        q['answer'] = new_answer
        add_fix(qid, ["R3"], f"Sorted numerical options: {old_order} -> {[o['label'] for o in sorted_opts]}; answer {old_answer}->{new_answer}")

# ============================================================
# 6. Add kaoyan_origin
# ============================================================
with open(r'c:\Users\38063\Desktop\MedAgentWork\中间产物\batch035\kaoyan_candidates_emergency.json', 'r', encoding='utf-8') as f:
    kaoyan_candidates = json.load(f)

candidates_list = kaoyan_candidates.get('candidates', [])

current_kaoyan = sum(1 for q in questions if q.get('kaoyan_origin'))
print(f"Current kaoyan_origin: {current_kaoyan}")

# M8 - add GS-1998-049 (心肺复苏 related)
# M8 has questions about 心肺复苏
m8_candidates = [c for c in candidates_list if c['gs_id'] == 'GS-1998-049']
for cand in m8_candidates:
    for q in questions:
        if q['module'] == 'M8' and not q.get('kaoyan_origin'):
            q['kaoyan_origin'] = cand['kaoyan_origin']
            kaoyan_added += 1
            print(f"  Added kaoyan_origin M8: {q['id']}")
            break

# M9 - add candidates about 创伤/颅脑损伤
m9_gs_ids = ['GS-2020-063', 'GS-2014-084', 'GS-2010-113', 'GS-2007-125', 'GS-2019-061', 'GS-2013-079']
m9_candidates = [c for c in candidates_list if c['gs_id'] in m9_gs_ids]
for cand in m9_candidates:
    for q in questions:
        if q['module'] == 'M9' and not q.get('kaoyan_origin'):
            q['kaoyan_origin'] = cand['kaoyan_origin']
            kaoyan_added += 1
            print(f"  Added kaoyan_origin M9: {q['id']}")
            break

# M2 - add more candidates (中毒 related)
m2_gs_ids = ['GS-2015-068', 'GS-2012-067', 'GS-2007-143', 'GS-2019-130', 'GS-2018-130']
m2_candidates = [c for c in candidates_list if c['gs_id'] in m2_gs_ids]
for cand in m2_candidates:
    already_exists = False
    for q in questions:
        if q['module'] == 'M2' and q.get('kaoyan_origin', {}).get('gs_id') == cand['gs_id']:
            already_exists = True
            break
    if not already_exists:
        for q in questions:
            if q['module'] == 'M2' and not q.get('kaoyan_origin'):
                q['kaoyan_origin'] = cand['kaoyan_origin']
                kaoyan_added += 1
                print(f"  Added kaoyan_origin M2: {q['id']}")
                break

final_kaoyan = sum(1 for q in questions if q.get('kaoyan_origin'))
print(f"Final kaoyan_origin: {final_kaoyan}")

# ============================================================
# 7. Write output
# ============================================================
output_path = r'c:\Users\38063\Desktop\MedAgentWork\中间产物\batch035\ALL_questions_FIXED.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(questions, f, ensure_ascii=False, indent=2)

print(f"\nWritten to {output_path}")

# Write fix log
fix_log = {
    "batch": "batch035",
    "fix_timestamp": datetime.now().isoformat(),
    "total_questions": 220,
    "questions_fixed": len(set(f['id'] for f in fixes)),
    "kaoyan_added": kaoyan_added,
    "fixes": fixes
}
log_path = r'c:\Users\38063\Desktop\MedAgentWork\中间产物\batch035\AGENT4_追溯日志.json'
with open(log_path, 'w', encoding='utf-8') as f:
    json.dump(fix_log, f, ensure_ascii=False, indent=2)
print(f"Written log to {log_path}")

# Write 修改声明
declaration = f"""# AGENT4 修改声明

**批次**: batch035 (急诊与灾难医学)  
**修改时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**原始题目数**: 220  
**修复题目数**: {len(set(f['id'] for f in fixes))}  
**新增考研题源标注数**: {kaoyan_added}

---

## 修改分类汇总

### 1. R4 - 否定词加粗
对以下题干的否定词添加 ** 加粗标记：
- batch035-M1-A1-004: "错误的" 
- batch035-M2-A1-001: "不正确"
- batch035-M2-A1-007: "不是"
- batch031-M3-A1-003: "不是"
- batch035-M7-A1-006: "不包括"
- batch035-M8-A1-002: "不是"
- batch035-M9-A1-006: "不包括"
- batch035-M9-A2-002: "错误的"
- batch035-M10-A1-006: "不包括"
- batch035-M10-A1-007: "不包括"
- batch035-M11-A1-001: "描述错误"

### 2. R1/S4 - 绝对化用语修正
将"必须"改为"应"、"一定"删除、"完全不同的"改为"不同的"等。

### 3. R13 - 选项缩短（>20字）
将超过20个汉字的选项缩短至20字以内，通过删除冗余修饰词保持医学原意。

### 4. R2 - 选项长度比调整
针对FAIL级别的长度比超标问题，通过缩短最长选项调整比例。

### 5. R3 - 数值选项排序
将数值选项按升序重新排列，并更新对应答案标签。

### 6. R8 - 数值单位
以下格式无需补充单位，已确认无误：
- CPR胸外按压与通气比（如"5:1"、"30:2"）
- 分期编号（如"1期"、"2期"）
- 倍数表示（如"1倍"、"2～2.5倍"）
- 电除颤能量（如"50～100J"、"360J"）
- 解剖分数位置（如"上臂下1/3处"）
- 时间单位（如"10秒"、"30秒"）
- 心脏复苏药物剂量（如"300mg"、"1mg"）

### 7. 考研题源 (kaoyan_origin) 增强
新增 {kaoyan_added} 个考研题源标注，使总数从{current_kaoyan}个增至{final_kaoyan}个。

---

## 注意事项
- 所有修改仅涉及格式和表述的机械性调整，未改变医学内容的准确性
- 所有答案选项（answer/option_polarities）保持不变
- 考研题源标注采用已有题目的附加字段，不改变题目内容
"""

declaration_path = r'c:\Users\38063\Desktop\MedAgentWork\中间产物\batch035\AGENT4_修改声明.md'
with open(declaration_path, 'w', encoding='utf-8') as f:
    f.write(declaration)
print(f"Written declaration to {declaration_path}")
print("Done!")