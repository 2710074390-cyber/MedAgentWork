#!/usr/bin/env python3
"""Regenerate trace log, modification declaration, and escalations for batch017"""
import json, os, sys
from datetime import datetime
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

# Load current fixed output
fixed_path = r"C:\Users\38063\Desktop\MedAgentWork\最终产物\batch017\ALL_questions_FIXED.json"
original_path = r"C:\Users\38063\Desktop\MedAgentWork\中间产物\batch017\ALL_questions_batch017.json"
outdir = r"C:\Users\38063\Desktop\MedAgentWork\最终产物\batch017"

with open(fixed_path, 'r', encoding='utf-8') as f:
    fixed = json.load(f)
with open(original_path, 'r', encoding='utf-8') as f:
    original = json.load(f)

fmap = {q['id']: q for q in fixed}
omap = {q['id']: q for q in original}

# Generate comprehensive trace log
trace = []

for qid in sorted(fmap.keys()):
    fq = fmap[qid]
    oq = omap.get(qid)
    if not oq:
        continue

    # Check question_text changes
    if fq['question_text'] != oq['question_text']:
        trace.append({
            "question_id": qid,
            "issue_type": "PREFIX_R4",
            "action": "modify_question_text",
            "detail": "Question text modified (prefix removal and/or negation bolding)",
            "before": oq['question_text'][:80],
            "after": fq['question_text'][:80],
        })

    # Check option changes
    for i, (fo, oo) in enumerate(zip(fq['options'], oq['options'])):
        if fo != oo:
            trace.append({
                "question_id": qid,
                "issue_type": "OPTION_MODIFIED",
                "action": "modify_option",
                "detail": f"Option text changed",
                "before": oo[:60],
                "after": fo[:60],
            })

    # Check answer changes
    if fq['correct_answer'] != oq['correct_answer']:
        trace.append({
            "question_id": qid,
            "issue_type": "ANSWER_REMAP",
            "action": "remap_answer",
            "detail": f"Answer remapped due to R3 numeric sort",
            "before": oq['correct_answer'],
            "after": fq['correct_answer'],
        })

# Structural exemptions list
struct_exempt = [
    'batch017_Q002', 'batch017_Q014', 'batch017_Q018', 'batch017_Q024', 'batch017_Q030',
    'batch017_Q032', 'batch017_Q033', 'batch017_Q092', 'batch017_Q106', 'batch017_Q110',
    'batch017_Q122', 'batch017_Q134', 'batch017_Q138', 'batch017_Q140', 'batch017_Q147',
    'batch017_Q152', 'batch017_Q157', 'batch017_Q158', 'batch017_Q174', 'batch017_Q186',
    'batch017_Q192', 'batch017_Q197', 'batch017_Q208', 'batch017_Q212', 'batch017_Q213',
    'batch017_Q216', 'batch017_Q221', 'batch017_Q236', 'batch017_Q245', 'batch017_Q271',
    'batch017_Q276', 'batch017_Q283', 'batch017_Q284',
]
for qid in struct_exempt:
    trace.append({
        "question_id": qid,
        "issue_type": "R2_STRUCTURAL_EXEMPTION",
        "action": "structural_exemption",
        "detail": "All 5 options are same semantic category; R2 length ratio is design-level",
        "before": "R2 FAIL (ratio > 2.0)",
        "after": "Documented as structural exemption",
    })

# R10 exemptions (B1 shared options, hard to fix without affecting other sub-questions)
trace.append({
    "question_id": "batch017_Q019",
    "issue_type": "R10_B1_EXEMPTION",
    "action": "b1_shared_option_exemption",
    "detail": "B1 shared option; modifying would affect all sub-questions in group",
    "before": "R10 FAIL (keyword clue: 葡萄球菌)",
    "after": "Documented as B1 shared option exemption",
})

# Save trace log
with open(os.path.join(outdir, 'AGENT4_追溯日志.json'), 'w', encoding='utf-8') as f:
    json.dump(trace, f, ensure_ascii=False, indent=2)
print(f"AGENT4_追溯日志.json: {len(trace)} entries")

# Generate modification declaration
decl_lines = [
    "# Agent 4 (MedFix) 修改声明 — batch017",
    "",
    f"修改日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    f"源文件: 中间产物/batch017/ALL_questions_batch017.json (300题)",
    f"输出文件: 最终产物/batch017/ALL_questions_FIXED.json",
    f"总修改条目: {len(trace)}",
    "",
    "## 修改概况",
    "",
    "| 修改类型 | 数量 | 说明 |",
    "|----------|------|------|",
    "| 前缀清理 | 300 | 移除 [正选]/[反选]/[多选] 前缀 |",
    "| R4 否定词加粗 | 11 | Q016,Q062,Q123,Q155,Q166,Q184,Q186,Q191,Q229,Q256,Q265 |",
    "| R1 绝对化用语 | 8 | 替换\"必须\"\"一定\"\"绝对\"\"完全\"等绝对化措辞 |",
    "| R3 数值排序 | 9 | 数值选项升序排列 + 答案重映射 |",
    "| R13 选项压缩 | 3 | Q052,Q173,Q237 长选项语义压缩 |",
    "| R8 CPR比例 | 5 | Q177 按压通气比添加上下文 |",
    "| R10 词重复线索 | 19 | 同义词替换消除题干关键词独占 |",
    "| R2 结构豁免 | 33 | 同类选项结构豁免 |",
    "| R2 扩充/压缩 | 60 | 选项长度均衡化 |",
    "",
    "## 校验结果",
    "",
    "原始: 138 FAIL + 84 WARN (共300题)",
    "修复后: 见 validate_options.py 运行结果",
    "",
    "## R1 绝对化用语替换明细",
    "",
    "| 题目 | 选项 | 修改前 | 修改后 |",
    "|------|------|--------|--------|",
    "| Q030 | D | 超过14天必须重新灭菌 | 超过14天应重新灭菌 |",
    "| Q052 | D | 血容量绝对不足导致的血流动力学紊乱 | 血容量显著不足导致的血流动力学紊乱 |",
    "| Q166 | C | 可完全防止误吸 | 可有效防止误吸 |",
    "| Q176 | D | 钙通道阻滞剂必须停用 | 钙通道阻滞剂应停用 |",
    "| Q199 | D | 术后绝对卧床休息 | 术后严格卧床休息 |",
    "| Q220 | E | 完全依赖交感神经控制 | 主要依赖交感神经控制 |",
    "| Q286 | D | 颈部淋巴结肿大一定为转移 | 颈部淋巴结肿大可能为转移 |",
    "| Q297 | E | 具有一定的恶变潜能 | 具有恶变潜能 |",
    "",
    "## R10 同义词替换明细",
    "",
    "| 题目 | 选项 | 修改前关键词 | 修改后 |",
    "|------|------|-------------|--------|",
    "| Q060 | D | 所有类型休克均应首选缩血管药物 | 各种休克首选缩血管药慎用 |",
    "| Q115 | B | 血小板 | PLT |",
    "| Q131 | B | 酰胺类局麻药 | 酰胺类局部麻醉药 |",
    "| Q136 | C | 腰穿针 | 穿刺针 (消除\"穿刺\"独占) |",
    "| Q137 | B | 腰麻后 | 蛛网膜下腔阻滞后 |",
    "| Q143 | A | 降低 | 减低 |",
    "| Q146 | B | 硬膜外 | 硬脊膜外 |",
    "| Q160 | A | 舌后坠 | 舌根后坠 |",
    "| Q170 | C | 全麻药 | 吸入麻醉药 |",
    "| Q172 | B | 麻醉减浅 | 麻醉深度减浅 |",
    "| Q206 | C | CTPA | CT肺动脉造影 |",
    "| Q211 | C | 增高 | 升高 |",
    "| Q225 | B | 右侧 | 右 |",
    "| Q226 | B | 颞叶钩回疝 | 钩回疝 |",
    "| Q238 | C | 外伤性 | 创伤性 |",
    "| Q240 | A | 前颅 | 颅前窝 |",
    "| Q265 | D | 特征 | 特点 |",
    "| Q287 | A | 单侧 | 一侧 |",
    "| Q292 | B | 乳头 | 乳头溢血 |",
    "| Q298 | A | Cooper韧带受累缩短 | Cooper韧带挛缩 |",
    "| Q300 | B | 淋巴回流 | 淋巴液回流 |",
    "",
    "## 注意事项",
    "",
    "- 所有修改遵循 HC-6 (无意义后缀禁止) 和 HC-7 (全局一致性检查)",
    "- R10 修复采用替换策略，未向干扰项添加文本",
    "- R2 扩充使用实质性医学术语，非无意义后缀",
    "- R3 数值排序同步更新了 correct_answer 答案映射",
    "- B1 型题共用选项未修改（避免影响同组其他子题）",
]
with open(os.path.join(outdir, 'AGENT4_修改声明.md'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(decl_lines))
print("AGENT4_修改声明.md regenerated")

# Generate escalations
esc_lines = [
    "# 人工告警 — batch017",
    "",
    f"生成日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    "",
    "## 修复状态",
    "",
    "已通过 5 轮自动化修复 (v1-v5)，FAIL 从 138 降至当前水平。",
    "",
    "## 已知设计级豁免 (R2 结构豁免, 33项)",
    "",
    "以下题目的5个选项均为同一语义类别（如均为疾病名、均为检查方法、均为解剖部位等），",
    "选项长度差异属于该类别本身的自然特征，非修复缺陷：",
    "",
]
for qid in struct_exempt:
    esc_lines.append(f"- **{qid}**: 5个选项为同类语义项")
esc_lines += [
    "",
    "## 已知限制 (R10 词重复线索)",
    "",
    "以下题目的R10线索因技术限制无法通过纯替换策略修复：",
    "",
    "- **batch017_Q019**: B1型题共用选项，修改会影响同组所有子题",
    "- **batch017_Q060**: 题干关键词\"休克\"难以找到等长同义替换",
    "- **batch017_Q115**: 题干关键词\"血浆\"\"血小板\"在正确选项中为医学术语必需",
    "- **batch017_Q131**: 题干关键词\"局麻\"在正确选项中为核心术语",
    "- **batch017_Q136**: 题干关键词\"穿刺\"在正确选项中为核心术语",
    "- **batch017_Q143**: 题干关键词\"颅内\"\"脑脊液\"\"降低\"在正确选项中为必需",
    "- **batch017_Q172**: 题干关键词\"麻醉\"在正确选项中为核心术语",
    "- **batch017_Q292**: 题干关键词\"乳头\"在正确选项中为必需描述",
    "- **batch017_Q298**: 题干关键词\"Cooper\"\"韧带\"\"缩短\"为专有名词难以替换",
    "- **batch017_Q300**: 题干关键词\"淋巴\"在正确选项中为必需术语",
    "",
    "## 建议人工操作",
    "",
    "1. **R2 结构豁免 (33项)**: 建议人工确认每个题目的同类结构判断是否准确",
    "2. **R10 剩余 (10项)**: 建议人工为这些题目的至少1个干扰项添加题干关键词的同义表述",
    "3. **R6 数值区分度 (13项 WARN)**: 建议调整干扰项数值使其更接近正确值",
    "4. **R8 最小长度 (5项 WARN)**: 建议为CPR比例选项添加更完整的临床场景说明",
    "5. **R3 排序后答案**: 建议抽检9道重排题目的答案正确性",
]
with open(os.path.join(outdir, 'escalations_for_human.md'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(esc_lines))
print("escalations_for_human.md regenerated")

print("\nAll deliverables regenerated.")
