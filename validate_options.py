#!/usr/bin/env python3
"""
选项设计机械化校验器 v1.0 — HC-7 子规则硬编码检测
用法:
  python validate_options.py --batch batch005
  python validate_options.py --file path/to/file.json
  python validate_options.py --batch batch004 --verbose
"""
import json, sys, re, argparse
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent
OUTPUT_BASE = BASE / 'reports' / 'validate'  # v2.1 (2026-08-13): 对齐铁律⑤，报告不再写根目录


# ──────────────────────────────────────────
# 解析器：JSON 格式（batch004 风格）
# ──────────────────────────────────────────

def parse_json_file(filepath):
    """解析 JSON 格式的题库文件，返回题目列表
    支持两种格式:
      - batch004 风格: {"question": "...", "options": ["A. text", ...]}
      - batch006 风格: {"stem": "...", "options": [{"label": "A", "text": "..."}]}
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        return []

    questions = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # 兼容多种字段名: question (batch004) / stem (batch006) / question_text (batch017) / 题干 (batch020)
        stem = item.get('question') or item.get('stem') or item.get('question_text') or item.get('题干', '')
        if not stem:
            continue
        q = {
            'id': item.get('id', '?'),
            'type': item.get('type') or item.get('question_type', 'A1'),
            'question': stem,
            'options_raw': item.get('options', []),
            'answer': item.get('answer') or item.get('correct_answer', ''),
            'analysis': item.get('analysis', '') or item.get('explanation', '') or item.get('解析', ''),
            'module': item.get('module', ''),
            'bloom': item.get('bloom') or item.get('bloom_level', ''),
            'difficulty': item.get('difficulty', ''),
        }
        # 标准化选项：兼容两种格式
        opts = {}
        for opt in q['options_raw']:
            if isinstance(opt, dict):
                # batch006 风格: {"label": "A", "text": "..."}
                label = opt.get('label', '')
                text = opt.get('text', '')
                if label and text:
                    opts[label] = text.strip()
            elif isinstance(opt, str):
                # batch004 风格: "A. text"
                m = re.match(r'^([A-E])\.\s*(.+)', opt)
                if m:
                    opts[m.group(1)] = m.group(2).strip()
                else:
                    opts[str(len(opts))] = opt.strip()
        q['options'] = opts
        questions.append(q)
    return questions


# ──────────────────────────────────────────
# 解析器：Markdown 格式（batch005 风格）
# ──────────────────────────────────────────

def parse_md_file(filepath):
    """解析 Markdown 格式的题库文件，返回题目列表"""
    text = filepath.read_text(encoding='utf-8')
    lines = text.split('\n')

    questions = []
    b1_groups = {}  # group_key -> shared_options dict
    current_b1_group = None  # 当前活跃的 B1 组

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 检测题目头: **N005-001 [A1型] [正选]** 或 **N004-001** [A1型]
        header_match = re.match(r'\*\*(N\d+-\d+)\*?\s*\[(\w+)型\](?:\s*\[([正反]?选)\])?', line)
        if not header_match:
            i += 1
            continue

        qid = header_match.group(1)
        qtype = header_match.group(2)
        polarity = header_match.group(3) or '正选'

        # 非 B1 型题时，重置当前 B1 组
        if qtype != 'B1':
            current_b1_group = None

        q = {
            'id': qid,
            'type': qtype,
            'polarity': polarity,
            'question': '',
            'options': {},
            'answer': '',
            'analysis': '',
            'module': '',
            'b1_group': None,
            'b1_shared_options': None,
        }

        i += 1

        # B1型: 检测共用选项声明 （13-14共用选项）
        if qtype == 'B1' and i < len(lines):
            shared_match = re.match(r'[（(](\d+)-(\d+)共用选项[）)]', lines[i].strip())
            if shared_match:
                group_start = shared_match.group(1)
                group_end = shared_match.group(2)
                q['b1_group'] = f"{group_start}-{group_end}"
                current_b1_group = q['b1_group']
                i += 1
                # 下一行是共用选项: A. xxx  B. xxx  C. xxx ...
                if i < len(lines):
                    shared_line = lines[i].strip()
                    # 解析行内选项: A. xxx  B. xxx
                    shared_opts = {}
                    for opt_m in re.finditer(r'([A-E])\.\s*(\S+(?:\s+\S+)*?)(?=\s+[A-E]\.|$)', shared_line):
                        shared_opts[opt_m.group(1)] = opt_m.group(2).strip()
                    if not shared_opts:
                        # 回退: 用 - A. 格式
                        for opt_m in re.finditer(r'([A-E])\.\s*(.+?)(?=\s+-\s+[A-E]\.|$)', shared_line):
                            shared_opts[opt_m.group(1)] = opt_m.group(2).strip()
                    q['b1_shared_options'] = shared_opts
                    b1_groups[q['b1_group']] = shared_opts
                    i += 1
            else:
                # B1 子题（非组首题），继承当前活跃组
                if current_b1_group:
                    q['b1_group'] = current_b1_group

        # 收集题干和选项
        stem_lines = []
        while i < len(lines):
            line_i = lines[i].strip()

            # 检测子题标识: N005-117：... 或 N005-118：...
            sub_q_match = re.match(r'(N\d+-\d+)[：:]\s*(.+)', line_i)
            if sub_q_match and qtype == 'B1':
                # 这是 B1 组的子题，设置题干，继续收集答案
                q['question'] = sub_q_match.group(2).strip()
                i += 1
                continue

            # 检测 - A. 格式的选项
            opt_match = re.match(r'^-\s*([A-E])\.\s*(.+)', line_i)
            if opt_match:
                q['options'][opt_match.group(1)] = opt_match.group(2).strip()
                i += 1
                continue

            # 检测答案行
            ans_match = re.match(r'^答案[：:]\s*([A-E]+)', line_i)
            if ans_match:
                q['answer'] = ans_match.group(1)
                i += 1
                continue

            # 检测解析行
            ana_match = re.match(r'^解析[：:]\s*(.+)', line_i)
            if ana_match:
                q['analysis'] = ana_match.group(1)
                i += 1
                break

            # 分隔符
            if line_i == '---':
                i += 1
                break

            # 其他非空行归入题干
            if line_i and not line_i.startswith('**') and not line_i.startswith('#'):
                stem_lines.append(line_i)
            elif line_i.startswith('**'):
                # 下一个题目开始了，当前题目结束
                break

            i += 1

        if stem_lines:
            q['question'] = ' '.join(stem_lines)

        # B1型: 如果没有独立选项，使用共用选项
        if qtype == 'B1' and not q['options']:
            if q['b1_shared_options']:
                q['options'] = q['b1_shared_options']
            elif q.get('b1_group') and q['b1_group'] in b1_groups:
                q['options'] = b1_groups[q['b1_group']]
            elif current_b1_group and current_b1_group in b1_groups:
                q['options'] = b1_groups[current_b1_group]

        # 如果题干和选项都为空，跳过
        if not q['question'] and not q['options']:
            continue

        questions.append(q)

    return questions


# ──────────────────────────────────────────
# 校验规则
# ──────────────────────────────────────────

# 禁止项正则
FORBIDDEN_PATTERNS = [
    (r'以上都是|以上都不是|以上都对|以上都不对|以上均对|以上均不对|以上全对|以上全不对', 'FAIL', '禁止"以上都是/都不是"变体'),
    (r'总是|从不|所有(?![\u4e00-\u9fff])|必须|完全|绝对|一定|永远|绝不', 'WARN', '绝对化用语'),
]

# 否定词正则
NEGATION_WORDS = r'(?<!\*{2})(?:不包括|不正确|错误|不属于|不是|除外|哪项不对|哪项错|描述错)(?!\*{2})'


def check_r1_forbidden(q):
    """R1: 禁止项检测"""
    issues = []
    for letter, text in q['options'].items():
        for pattern, severity, desc in FORBIDDEN_PATTERNS:
            if re.search(pattern, text):
                issues.append({
                    'rule': 'R1',
                    'severity': severity,
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'{desc}: "{text[:30]}..."' if len(text) > 30 else f'{desc}: "{text}"',
                })
        # 末尾括号后缀
        if re.search(r'[（(][^）)]*[）)]\s*$', text) and not re.search(r'[（(]见上|见下|[）)]$', text):
            # 排除正常的括号内容（如药物剂量说明），仅检测说明性后缀
            if re.search(r'[（(]见[上文下][）)]', text):
                issues.append({
                    'rule': 'R1',
                    'severity': 'WARN',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'选项末尾括号说明: "{text}"',
                })
    return issues


def check_r2_length_ratio(q):
    """R2: 选项长度比检测"""
    issues = []
    opts = q['options']
    if len(opts) < 2:
        return issues

    lengths = {k: len(v) for k, v in opts.items()}
    if min(lengths.values()) == 0:
        return issues  # 空选项，其他规则会捕获

    max_len = max(lengths.values())
    min_len = min(lengths.values())
    ratio = max_len / min_len

    if ratio > 2.0:
        max_opt = max(lengths, key=lengths.get)
        min_opt = min(lengths, key=lengths.get)
        issues.append({
            'rule': 'R2',
            'severity': 'FAIL',
            'target': f"{q['id']}.options",
            'detail': f'选项长度比 {ratio:.1f}x (>2.0): {max_opt}={max_len}字 vs {min_opt}={min_len}字',
        })
    elif ratio > 1.5:
        max_opt = max(lengths, key=lengths.get)
        min_opt = min(lengths, key=lengths.get)
        issues.append({
            'rule': 'R2',
            'severity': 'WARN',
            'target': f"{q['id']}.options",
            'detail': f'选项长度比 {ratio:.1f}x (>1.5): {max_opt}={max_len}字 vs {min_opt}={min_len}字',
        })
    return issues


def check_r3_numeric_sort(q):
    """R3: 数值排序检测"""
    issues = []
    opts = q['options']
    if len(opts) < 3:
        return issues

    # 提取每个选项的首个数值
    numbers = []
    all_numeric = True
    for letter in sorted(opts.keys()):
        text = opts[letter]
        nums = re.findall(r'[-+]?\d+\.?\d*', text)
        if nums:
            numbers.append(float(nums[0]))
        else:
            all_numeric = False
            break

    if not all_numeric or len(numbers) < 3:
        return issues

    # 检查是否升序或降序
    is_ascending = all(numbers[i] <= numbers[i+1] for i in range(len(numbers)-1))
    is_descending = all(numbers[i] >= numbers[i+1] for i in range(len(numbers)-1))

    if not is_ascending and not is_descending:
        issues.append({
            'rule': 'R3',
            'severity': 'WARN',
            'target': f"{q['id']}.options",
            'detail': f'数值选项未按升序/降序排列: {numbers}',
        })
    return issues


def check_r4_negation_bold(q):
    """R4: 否定词加粗检测"""
    issues = []
    stem = q['question']
    if not stem:
        return issues

    # 检查题干是否含否定词
    has_negation = re.search(r'不包括|不正确|错误的|不属于|不是|除外|哪项不对|哪项错|描述错误|描述不正确', stem)
    if not has_negation:
        return issues

    # 检查否定词是否被 ** ** 包裹
    bold_negation = re.search(r'\*\*.*?(?:不包括|不正确|错误|不属于|不是|除外|哪项不对|哪项错|描述错误|描述不正确).*?\*\*', stem)
    if not bold_negation:
        issues.append({
            'rule': 'R4',
            'severity': 'WARN',
            'target': f"{q['id']}.stem",
            'detail': f'否定词"{has_negation.group()}"未加粗',
        })
    return issues


def check_r5_option_count(q):
    """R5: 选项数量检测"""
    issues = []
    count = len(q['options'])
    qtype = q.get('type', 'A1')

    if qtype in ('A1', 'A2', 'B1'):
        if count != 5:
            issues.append({
                'rule': 'R5',
                'severity': 'FAIL',
                'target': f"{q['id']}.options",
                'detail': f'{qtype}型题应有5个选项，实际{count}个',
            })
    elif qtype == 'X':
        if count < 4:
            issues.append({
                'rule': 'R5',
                'severity': 'FAIL',
                'target': f"{q['id']}.options",
                'detail': f'X型题应至少有4个选项，实际{count}个',
            })
    return issues


def extract_numbers(text):
    """从文本中提取所有数值"""
    return [float(n) for n in re.findall(r'[-+]?\d+\.?\d*', text)]


def check_r6_numeric_discrimination(q):
    """R6: 数值型干扰项区分度"""
    issues = []
    answer = q.get('answer', '')
    opts = q['options']

    if not answer or len(answer) > 1:
        return issues  # 多选题跳过

    correct_text = opts.get(answer, '')
    correct_nums = extract_numbers(correct_text)
    if not correct_nums:
        return issues

    correct_val = correct_nums[0]
    if correct_val == 0:
        return issues  # 避免除零

    for letter, text in opts.items():
        if letter == answer:
            continue
        distractor_nums = extract_numbers(text)
        for dval in distractor_nums:
            if dval == 0:
                continue
            ratio = max(correct_val, dval) / min(correct_val, dval)
            if ratio > 5:
                issues.append({
                    'rule': 'R6',
                    'severity': 'WARN',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'数值区分度不足: 正确值{correct_val} vs 干扰值{dval}，比值{ratio:.1f}x (>5x)',
                })
                break  # 每题每选项只报一次
    return issues


def check_r7_truncation(q):
    """R7: 选项截断检测（batch006教训：ESC修复过度截断272个选项为2字残片）

    检测特征：
    - 选项以句号结尾且长度<8字（截断典型特征，如"单个毛囊及其周."）
    - 选项以".."双点结尾（明显残留截断标记）
    - 选项为单字+句号（如"致.化.破.一."，严重截断）
    """
    issues = []
    if q['type'] == 'X型':
        return issues

    for letter, text in q.get('options', {}).items():
        stripped = text.strip()
        # 检测双点截断残留
        if stripped.endswith('..'):
            issues.append({
                'rule': 'R7',
                'severity': 'FAIL',
                'target': f"{q['id']}.option{letter}",
                'detail': f'选项以".."结尾，疑似截断残留: "{stripped}"',
            })
            continue

        # 检测以句号结尾的短选项（截断特征）
        if stripped.endswith('.'):
            core_len = len(stripped) - 1  # 不含句号的实际内容长度
            if core_len <= 2:
                # 1-2字+句号 = 严重截断
                issues.append({
                    'rule': 'R7',
                    'severity': 'FAIL',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'选项疑似被严重截断(仅{core_len}字): "{stripped}"',
                })
            elif core_len <= 7:
                # 3-7字+句号 = 疑似截断
                issues.append({
                    'rule': 'R7',
                    'severity': 'FAIL' if core_len <= 4 else 'WARN',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'选项以句号结尾且偏短({core_len}字)，疑似截断: "{stripped}"',
                })

    return issues

def check_r8_min_length(q):
    """R8: 选项最小长度与截断防护（batch007教训：Agent2系统性10字截断漏检）

    检测特征：
    - 选项以连接词/助词结尾（的/和/与/或/及/在/被/将/对/向/于）且长度<12字
    - 选项含数字但缺乏时间/剂量单位（天/周/月/年/岁/小时/分钟/mg/ml/%/次）
    - 选项以逗号/顿号结尾（明显截断为半句）
    - 排除：纯数值选项（如"5%"）、合理短术语（如精神科症状名）
    """
    issues = []
    if q['type'] == 'X型':
        return issues

    # Known short psychiatric terms that are legitimate
    legit_terms = {'妄想', '幻觉', '障碍', '减退', '缺乏', '低落', '焦虑', '恐惧',
                   '躁狂', '抑郁', '木僵', '违拗', '缄默', '痴呆', '谵妄', '强迫',
                   '疑病', '失眠', '嗜睡', '人格', '自知力', 'PTSD', 'OCD', 'AD'}

    # Suspicious word endings (Chinese function words that shouldn't end a complete option)
    suspicious_ends = {'的', '和', '与', '或', '及', '在', '被', '将', '对', '向', '于'}

    for letter, text in q.get('options', {}).items():
        stripped = text.strip()
        tlen = len(stripped)

        # Skip pure numeric/percentage options
        import re
        if re.match(r'^[\d.%\u2103/\-～~约]+[天周月年岁日小时分钟mgml次°]*$', stripped):
            continue

        # Skip legitimate short psychiatric terms
        if tlen <= 6 and any(term in stripped for term in legit_terms):
            continue

        # Check 1: ends with suspicious conjunction/preposition (mid-sentence)
        if tlen >= 6 and stripped[-1] in suspicious_ends:
            issues.append({
                'rule': 'R8',
                'severity': 'FAIL',
                'target': f"{q['id']}.option{letter}",
                'detail': f'选项以"{stripped[-1]}"结尾且长度{tlen}字，疑似截断: "{stripped}"',
            })
            continue

        # Check 2: ends with comma/pause (mid-list cut)
        if tlen >= 6 and stripped.endswith(('、', '，', '（')):
            issues.append({
                'rule': 'R8',
                'severity': 'FAIL',
                'target': f"{q['id']}.option{letter}",
                'detail': f'选项以"{stripped[-1]}"结尾，疑似列表截断: "{stripped}"',
            })
            continue

        # Check 3: contains numbers but no unit (potential missing time/dose unit)
        has_digit = bool(re.search(r'\d+', stripped))
        has_unit = bool(re.search(r'[天周月年岁日小时分钟°mgl%次mL℃]', stripped))
        if has_digit and not has_unit and tlen < 10:
            # Exclude receptor names like 5-HT, D2
            if not re.search(r'[A-Z]\d|5-HT|D\d|B\d', stripped):
                issues.append({
                    'rule': 'R8',
                    'severity': 'WARN',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'选项含数值但缺少时间/剂量单位({tlen}字): "{stripped}"',
                })

    return issues

def check_r9_missing_unit(q):
    """R9: 数值缺单位检测（batch014教训：诊断值/生理参数/时间数值缺少必需单位）

    检测特征：
    - 临床参数缩写后跟比较符+数字但无单位 (如 "LVEF小于40"→应为"LVEF小于40%")
    - 生理阈值数字后缺单位 (如 "PaO2小于60"→应为"PaO2小于60mmHg")
    - 时间/频率描述数字后缺单位 (如 "控制在9"→应为"控制在90分钟")

    排除：纯数字ID、页码引用(P123)、年份(2024年)、百分比已有%标记
    """
    issues = []
    if q['type'] == 'X型':
        return issues

    # ── 临床参数缩写列表（通常后跟单位 %/mmHg/cmH2O 等）──
    clinical_params = [
        'LVEF', 'FEV1', 'FVC', 'FEV1/FVC', 'PaO2', 'PaCO2', 'SaO2', 'SpO2',
        'PEF', 'TLC', 'RV', 'DLCO', 'BNP', 'NT-proBNP', 'HbA1c',
        'INR', 'PT', 'APTT', 'TT', 'D-二聚体',
        'CRP', 'ESR', 'PCT', 'CK-MB', 'cTnI', 'cTnT', 'ALT', 'AST',
        'Cr', 'BUN', 'eGFR', 'K\\+', 'Na\\+', 'Ca2\\+', 'Cl\\-',
        'pH', 'HCO3', 'BE', '乳酸', '血糖', '血钾', '血钠', '血钙',
    ]

    # ── 时间/频率上下文词（通常后跟 分钟/小时/天/次/分 等）──
    time_contexts = [
        '频率', '速率', '次数', '控制在', '维持在', '时间窗',
        '门球时间', '按压', '通气', '按压.*通气',
        '每分钟', '每小时', '每天',
    ]

    # 已知豁免模式
    exemption_patterns = [
        r'P\d{2,4}',           # 教材页码
        r'\d{4}年',             # 年份
        r'N\d{3}-\d{3}',       # 题目ID
        r'\d+%',               # 已有百分比
        r'\d+\s*[次分秒时天周月年岁]',  # 已有中文单位
        r'\d+\s*[mkc]?[gGlL]',  # 已有剂量单位
        r'\d+\s*mm\s*Hg',      # 已有mmHg
        r'\d+\s*cm\s*H2O',     # 已有cmH2O
        r'\d+\s*[°℃]',         # 已有温度
        r'\d+\s*mmol',         # 已有mmol
        r'\d+\s*[×x]\s*\d+',   # 乘法格式 (如 3×10^9)
    ]

    for letter, text in q.get('options', {}).items():
        stripped = text.strip()

        # 跳过纯数值选项
        if re.match(r'^[\d.%\-～~约><=<>≥≤]+$', stripped):
            continue

        # 跳过已有完整豁免模式的选项
        if any(re.search(pat, stripped) for pat in exemption_patterns):
            continue

        # Check 1: 临床参数 + 比较符 + 数值 + (缺单位)
        for param in clinical_params:
            # Pattern: LVEF<40, PaO2<60, FEV1≤80
            param_pattern = re.compile(
                rf'{param}\s*[<>≤≥]?\s*(\d+\.?\d*)\s*(?![％%]|mm\s*Hg|cm\s*H2O|mmHg)'
            )
            m = param_pattern.search(stripped)
            if m:
                num_val = m.group(1)
                # 跳过小数（如 FEV1/FVC 0.7 是比值）
                if param in ('FEV1/FVC',) and float(num_val) < 10:
                    continue
                expected_unit = '%' if param in ('LVEF', 'FEV1', 'FVC', 'FEV1/FVC', 'PEF', 'TLC', 'RV', 'DLCO', 'HbA1c') else 'mmHg'
                # Check 1a: 临床参数缩写在比较符后缺单位 → 明确事实错误 → FAIL
                issues.append({
                    'rule': 'R9',
                    'severity': 'FAIL',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'临床参数"{param}"后数值{num_val}缺少单位(应为{expected_unit})，属事实错误: "{stripped[:40]}"',
                })
                break  # 每题每选项只报一次

        # Check 2: 时间/频率上下文 + 数值 + (缺时间单位)
        for ctx in time_contexts:
            ctx_pattern = re.compile(
                rf'{ctx}\s*[：:]*\s*[<>≤≥]?\s*(\d+\.?\d*)\s*'
                rf'(?!(次/分|/min|分钟|小时|[天周月年岁秒日]|mmHg|%|mL|mg|°C|℃))'
            )
            m = ctx_pattern.search(stripped)
            if m:
                num_val = m.group(1)
                # 排除页码引用
                if re.search(rf'P{num_val}', stripped):
                    continue
                # CPR/急救类上下文缺单位 → FAIL；其他 → WARN
                severity = 'FAIL' if any(kw in ctx for kw in ['按压', '通气', '门球时间', '时间窗']) else 'WARN'
                issues.append({
                    'rule': 'R9',
                    'severity': severity,
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'时间/频率上下文"{ctx}"后数值{num_val}缺少单位(如分钟/次/天等): "{stripped[:40]}"',
                })
                break

        # Check 3: 诊断名/术语后直接跟"小于/大于"+"数字"但无单位
        # 如 "急性心肌梗死小于6小时" vs "LVEF小于40%" (后者有%就不触发)
        # 此模式较宽泛，仅对特定诊断类术语触发
        threshold_pattern = re.compile(
            r'(?:PaO2|PaCO2|SaO2|LVEF|BNP|血糖|血压|心率|呼吸|体温|氧合)\s*[<>≤≥]?\s*(\d+\.?\d*)\s*$'
        )
        m = threshold_pattern.search(stripped)
        if m:
            num = m.group(1)
            if '.' not in num and int(num) < 1000:  # 避免四位数年份
                # 生理参数阈值缺单位 → 明确事实错误 → FAIL
                issues.append({
                    'rule': 'R9',
                    'severity': 'FAIL',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'生理参数阈值{num}缺少单位(如mmHg/次分/%/mmol/L等)，属事实错误: "{stripped[:40]}"',
                })

    return issues


def check_js1_json_integrity(questions, filepath=None):
    """JS1: JSON 完整性检测 — 检查 JSON 结构是否完整、无截断残留

    检测特征：
    - JSON 根级是否为有效 list/dict
    - 是否包含截断残留 (..., .., 等)
    - 每道题的 options 字典键是否使用 A-E 标签
    - 是否有空选项值或缺失关键字段
    """
    issues = []

    # 如果传入的是已解析的题目列表
    if not questions:
        issues.append({
            'rule': 'JS1',
            'severity': 'FAIL',
            'target': '_file',
            'detail': '题库文件解析后为空（可能 JSON 结构损坏或文件为空）',
        })
        return issues

    # 检查每个题目的结构完整性
    truncation_indicators = ['...', '..', '…']

    for q in questions:
        qid = q.get('id', '?')

        # JS1-1: 检查题干是否包含截断标记
        stem = q.get('question', '')
        for ti in truncation_indicators:
            if stem.rstrip().endswith(ti) and len(stem) < 30:
                issues.append({
                    'rule': 'JS1',
                    'severity': 'FAIL',
                    'target': f'{qid}.stem',
                    'detail': f'题干疑似截断（以"{ti}"结尾）: "{stem[:50]}"',
                })

        # JS1-2: 检查选项标签是否为标准 A-E
        opts = q.get('options', {})
        valid_labels = set('ABCDE')
        actual_labels = set(opts.keys())
        if actual_labels and not actual_labels.issubset(valid_labels):
            weird = actual_labels - valid_labels
            issues.append({
                'rule': 'JS1',
                'severity': 'WARN',
                'target': f'{qid}.options',
                'detail': f'选项标签非标准A-E: {sorted(weird)}',
            })

        # JS1-3: 检查答案键是否合法（X型list/B1型含/分隔符均合法）
        answer = q.get('answer', '')
        if isinstance(answer, list):
            # X型多选：answer为列表，逐个检查
            for a in answer:
                if not isinstance(a, str) or not all(c in 'ABCDE' for c in a):
                    issues.append({
                        'rule': 'JS1',
                        'severity': 'WARN',
                        'target': f'{qid}.answer',
                        'detail': f'答案键列表含非A-E元素: "{a}"',
                    })
        elif answer and not all(c in 'ABCDE/' for c in str(answer)):
            issues.append({
                'rule': 'JS1',
                'severity': 'WARN',
                'target': f'{qid}.answer',
                'detail': f'答案键包含非A-E字符: "{answer}"',
            })

        # JS1-4: 检查选项值是否为空字符串（截断后的空值）
        for letter, text in opts.items():
            if text is None or (isinstance(text, str) and text.strip() == ''):
                issues.append({
                    'rule': 'JS1',
                    'severity': 'FAIL',
                    'target': f'{qid}.option{letter}',
                    'detail': f'选项{letter}值为空（可能为截断残留）',
                })

    # JS1-5: 根级 JSON 有效性（如果提供了文件路径）
    if filepath:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                raw = f.read()
            # 检测 YAML 前端元数据
            if raw.strip().startswith('---'):
                issues.append({
                    'rule': 'JS1',
                    'severity': 'FAIL',
                    'target': '_file',
                    'detail': f'文件{Path(filepath).name}包含YAML前端元数据(---块)，应为纯JSON数组',
                })
            # 检测括号不配对
            open_braces = raw.count('{')
            close_braces = raw.count('}')
            open_brackets = raw.count('[')
            close_brackets = raw.count(']')
            if open_braces != close_braces:
                issues.append({
                    'rule': 'JS1',
                    'severity': 'FAIL',
                    'target': '_file',
                    'detail': f'JSON括号不配对: {{{open_braces} / {close_braces}}}',
                })
            if open_brackets != close_brackets:
                issues.append({
                    'rule': 'JS1',
                    'severity': 'FAIL',
                    'target': '_file',
                    'detail': f'JSON方括号不配对: [{open_brackets} / {close_brackets}]',
                })
        except Exception:
            pass

    return issues


def check_s1_schema_completeness(q):
    """S1: Schema 完整性校验 + 字段类型验证 (P2'-2增强: 类型检查)"""
    issues = []
    required = [
        ('id', '题目ID'),
        ('type', '题型标记'),
        ('question', '题干'),
        ('answer', '答案键'),
    ]
    for field, label in required:
        val = q.get(field)
        if val is None:
            issues.append({
                'rule': 'S1',
                'severity': 'FAIL',
                'target': f"{q.get('id', '?')}.{field}",
                'detail': f'必填字段缺失: {label}',
            })
    # 选项组存在且非空
    opts = q.get('options', {})
    if not opts:
        issues.append({
            'rule': 'S1',
            'severity': 'FAIL',
            'target': f"{q.get('id', '?')}.options",
            'detail': '选项组为空或缺失',
        })

    # ── P2'-2 字段类型验证 ──
    # answer 字段: str（单选/判断）或 list（X型多选）
    answer = q.get('answer')
    qtype = q.get('type', '')
    if answer is not None:
        if isinstance(answer, list):
            # X型多选：answer 为列表，检查是否为合法选项字母列表
            if qtype not in ('X', 'X型'):
                issues.append({
                    'rule': 'S1-TYPE',
                    'severity': 'WARN',
                    'target': f"{q['id']}.answer",
                    'detail': f'answer 为列表但题型非X型: type="{qtype}"',
                })
            for a in answer:
                if not isinstance(a, str) or not re.match(r'^[A-E]$', a):
                    issues.append({
                        'rule': 'S1-TYPE',
                        'severity': 'FAIL',
                        'target': f"{q['id']}.answer",
                        'detail': f'answer 列表含非法元素: {a}',
                    })
        elif not isinstance(answer, str):
            issues.append({
                'rule': 'S1-TYPE',
                'severity': 'FAIL',
                'target': f"{q['id']}.answer",
                'detail': f'answer 字段类型错误: 期望 str 或 list，实际 {type(answer).__name__}',
            })
        elif not re.match(r'^[A-E/]+$', answer):
            # 非A-E字符（排除空字符串已在S2检查）；允许 / 分隔符（B1型）
            if answer.strip():
                issues.append({
                    'rule': 'S1-TYPE',
                    'severity': 'WARN',
                    'target': f"{q['id']}.answer",
                    'detail': f'answer 值非标准A-E: "{answer}"',
                })

    # options 字段必须是 dict
    if not isinstance(opts, dict):
        issues.append({
            'rule': 'S1-TYPE',
            'severity': 'FAIL',
            'target': f"{q.get('id', '?')}.options",
            'detail': f'options 字段类型错误: 期望 dict，实际 {type(opts).__name__}',
        })

    # type 字段必须是已知题型
    qtype = q.get('type', '')
    valid_types = {'A1', 'A2', 'A3', 'A4', 'B1', 'X', 'X型', '判断', 'A1型', 'A2型', 'A3型', 'A4型', 'B1型'}
    if qtype and qtype not in valid_types:
        issues.append({
            'rule': 'S1-TYPE',
            'severity': 'WARN',
            'target': f"{q.get('id', '?')}.type",
            'detail': f'题型标记非标准值: "{qtype}" (期望: A1/A2/A3/A4/B1/X/判断)',
        })

    # bloom 字段（如果存在）必须是有效值
    bloom = q.get('bloom', '')
    valid_bloom = {'记忆', '理解', '应用', '分析', 'memory', 'comprehension', 'application', 'analysis',
                   'knowledge', 'understanding', 'remember', 'understand', 'apply', 'analyze'}
    if bloom and bloom not in valid_bloom:
        issues.append({
            'rule': 'S1-TYPE',
            'severity': 'WARN',
            'target': f"{q.get('id', '?')}.bloom",
            'detail': f'Bloom层级非标准值: "{bloom}" (期望: 记忆/理解/应用/分析)',
        })

    # question_count 字段（如果存在）必须是数字
    if 'question_count' in q:
        qc = q.get('question_count')
        if not isinstance(qc, (int, float)):
            issues.append({
                'rule': 'S1-TYPE',
                'severity': 'WARN',
                'target': f"{q.get('id', '?')}.question_count",
                'detail': f'question_count 类型错误: {type(qc).__name__}',
            })

    return issues


def check_s2_null_values(q):
    """S2: Null/空值检测——必填字段值非空"""
    issues = []
    checks = [
        ('id', '题目ID'),
        ('question', '题干'),
        ('answer', '答案键'),
    ]
    for field, label in checks:
        val = q.get(field, '')
        if val is None or (isinstance(val, str) and val.strip() == ''):
            issues.append({
                'rule': 'S2',
                'severity': 'FAIL',
                'target': f"{q.get('id', '?')}.{field}",
                'detail': f'必填字段值为空: {label}',
            })
    # 选项值非空
    for letter, text in q.get('options', {}).items():
        if not text or not text.strip():
            issues.append({
                'rule': 'S2',
                'severity': 'FAIL',
                'target': f"{q.get('id', '?')}.option{letter}",
                'detail': f'选项{letter}内容为空',
            })
    # ── P2'-2 字段值类型验证 ──
    # 检查 options 的值类型（必须是 str）
    for letter, text in q.get('options', {}).items():
        if text is not None and not isinstance(text, str):
            issues.append({
                'rule': 'S2-TYPE',
                'severity': 'FAIL',
                'target': f"{q.get('id', '?')}.option{letter}",
                'detail': f'选项{letter}类型错误: 期望 str，实际 {type(text).__name__}',
            })

    # 检查 analysis/explanation 字段类型（如果有值）
    analysis = q.get('analysis', q.get('explanation', ''))
    if analysis is not None and not isinstance(analysis, str):
        issues.append({
            'rule': 'S2-TYPE',
            'severity': 'WARN',
            'target': f"{q.get('id', '?')}.analysis",
            'detail': f'解析字段类型错误: 期望 str，实际 {type(analysis).__name__}',
        })

    return issues


def check_s3_placeholder_pages(questions):
    """S3: HC-10 占位符页码检测——跨题目频次分析"""
    issues = []
    if len(questions) < 4:
        return issues

    page_counter = Counter()
    chapter_only_count = 0

    for q in questions:
        text = q.get('analysis', '') + ' ' + q.get('question', '')
        # 提取教材页码 P##
        pages = re.findall(r'P(\d{2,4})', text)
        for p in pages:
            page_counter[p] += 1
        # 检测章节号代替页码
        if re.search(r'教材[第]?[一二三四五六七八九十\d]+章(?!.*P\d)', text):
            chapter_only_count += 1

    total = len(questions)

    # 单一页码占比 ≥50% → 占位符嫌疑
    for page, count in page_counter.most_common(3):
        ratio = count / total
        if ratio >= 0.5:
            issues.append({
                'rule': 'S3',
                'severity': 'FAIL',
                'target': '_cross_question',
                'detail': f'占位符页码嫌疑(HC-10): P{page} 出现在 {count}/{total} 题 ({ratio:.0%})，≥50% 阈值',
            })
            break

    # 章节号代替页码（≥30% 题目）
    if chapter_only_count >= total * 0.3:
        issues.append({
            'rule': 'S3',
            'severity': 'WARN',
            'target': '_cross_question',
            'detail': f'{chapter_only_count}/{total} 题使用章节号代替教材页码 (HC-10/ HC-11)',
        })

    return issues


def check_s4_absolute_language(q):
    """S4: 绝对化用语检测——题干 + 选项全面扫描 (HC-17 / NBME 规则)"""
    issues = []
    # 比 R1 更全面的绝对化用语列表
    absolute_patterns = [
        (r'一定(?!程度上|范围内|条件下)', '绝对化用语"一定"'),
        (r'(?<!\*\*)绝对(?!值|期|不应期|乏期)', '绝对化用语"绝对"'),
        (r'必定', '绝对化用语"必定"'),
        (r'肯定(?!性|的|鉴|诊断)', '绝对化用语"肯定"'),
        (r'绝不', '绝对化用语"绝不"'),
        (r'永远', '绝对化用语"永远"'),
        (r'100%', '绝对化用语"100%"'),
        (r'无一例外', '绝对化用语"无一例外"'),
        (r'毫无', '绝对化用语"毫无"'),
        (r'百分百', '绝对化用语"百分百"'),
    ]

    # 检查题干
    stem = q.get('question', '')
    for pattern, desc in absolute_patterns:
        if re.search(pattern, stem):
            issues.append({
                'rule': 'S4',
                'severity': 'WARN',
                'target': f"{q['id']}.stem",
                'detail': f'{desc} 出现在题干中',
            })

    # 检查选项
    for letter, text in q.get('options', {}).items():
        for pattern, desc in absolute_patterns:
            if re.search(pattern, text):
                snippet = text[:50] + '...' if len(text) > 50 else text
                issues.append({
                    'rule': 'S4',
                    'severity': 'WARN',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'{desc}: "{snippet}"',
                })

    return issues


# 静态预检（S1-S4, JS1, 2026-06-20 新增, 2026-06-23 扩展）
STATIC_CHECKS = [
    check_s1_schema_completeness,
    check_s2_null_values,
    check_s4_absolute_language,
]


# ──────────────────────────────────────────
# B1 型题专项检查
# ──────────────────────────────────────────

def find_b1_groups(questions):
    """将 B1 题按共用选项分组"""
    groups = defaultdict(list)
    for q in questions:
        if q.get('type') == 'B1' and q.get('b1_group'):
            groups[q['b1_group']].append(q)
    return groups


def check_b1_groups(questions):
    """B1 型题专项检查"""
    issues = []
    groups = find_b1_groups(questions)

    for group_key, group_qs in groups.items():
        if len(group_qs) < 2:
            continue

        # 获取共用选项（从第一题的 b1_shared_options 或 options）
        shared_opts = group_qs[0].get('b1_shared_options') or group_qs[0].get('options', {})
        if not shared_opts:
            continue

        # B1-1: 共用选项笼统度 — 所有选项 ≤ 2 字 或 ≥3 个选项 ≤ 2 字
        # 注：1字器官名（心/肝/脾/肺/肾）和2-3字穴位名虽短但具体，不视为笼统
        # 阈值设 ≤ 2 字：捕获 "表证/寒证/热证" 等大范畴，排除具体名词
        short_opts = [k for k, v in shared_opts.items() if len(v) <= 2]
        if len(short_opts) >= 3:
            issues.append({
                'rule': 'B1-1',
                'severity': 'WARN',
                'target': f"N{group_key}.shared_options",
                'detail': f'B1共用选项过于笼统: {len(short_opts)}个选项≤2字 ({", ".join(f"{k}={shared_opts[k]}" for k in short_opts)})',
            })

        # B1-2: 答案位置集中度 — ≥60% 子题答案为同一字母
        answers = [q['answer'] for q in group_qs if q.get('answer')]
        if answers:
            counter = Counter(answers)
            most_common_letter, most_common_count = counter.most_common(1)[0]
            ratio = most_common_count / len(answers)
            if ratio >= 0.6 and len(answers) >= 3:
                issues.append({
                    'rule': 'B1-2',
                    'severity': 'WARN',
                    'target': f"N{group_key}.answers",
                    'detail': f'B1答案集中: {most_common_count}/{len(answers)}题({ratio:.0%})答案为{most_common_letter}',
                })

        # B1-3: 子题覆盖度 — 答案覆盖 ≥ 3 个不同字母
        unique_answers = set(answers)
        if len(unique_answers) < 3 and len(answers) >= 3:
            issues.append({
                'rule': 'B1-3',
                'severity': 'WARN',
                'target': f"N{group_key}.coverage",
                'detail': f'B1答案覆盖不足: {len(answers)}题仅覆盖{len(unique_answers)}个选项位({",".join(sorted(unique_answers))})',
            })

    return issues


# ═══════════════════════════════════════
# R10-R12: NBME 选项设计检测 (P3 2026-06-24)
# ═══════════════════════════════════════

# ── 中文分词 ──
try:
    import jieba
    _JIEBA_AVAILABLE = True
except ImportError:
    _JIEBA_AVAILABLE = False

# 医学题干停用词（提问句式词 + 泛化医学术语，不参与 R10/R11 关键词提取）
_STEM_STOP_WORDS = {
    # 提问句式词
    '下列', '哪项', '哪一', '描述', '正确', '错误', '不正确', '不属于',
    '不包括', '关于', '的是', '一项', '以下', '其中', '属于', '上述',
    # 通用虚词
    '是', '的', '在', '和', '与', '或', '及', '对', '为', '有', '不',
    '该', '其', '此', '之', '等', '可', '中', '从', '所', '以', '但',
    '了', '也', '就', '都', '而', '要', '能', '会', '还', '将', '只',
    # 医学泛化词（太通用，不是有意义的"线索"）
    '患者', '疾病', '治疗', '方法', '表现', '症状', '检查', '诊断',
    '药物', '方案', '使用', '发生', '出现', '情况', '常见', '主要',
    '最', '较', '无', '未', '非', '应', '需', '需', '可能', '可以',
    '临床', '进行', '包括', '具有', '提示', '考虑', '首选', '确诊',
    '治疗', '症状', '因素', '综合征', '作用', '导致', '引起',
}


def _extract_stem_keywords(stem):
    """从题干中提取有意义的关键词（用于 D18/D19 检测）"""
    if _JIEBA_AVAILABLE:
        words = list(jieba.cut(stem))
    else:
        # 回退：简单2-4字n-gram
        words = []
        for n in (2, 3, 4):
            for i in range(len(stem) - n + 1):
                words.append(stem[i:i+n])

    # 过滤：长度≥2，非停用词，非纯数字/标点
    keywords = []
    for w in words:
        w = w.strip()
        if len(w) < 2:
            continue
        if w in _STEM_STOP_WORDS:
            continue
        if all(c in '0123456789.%-+×x,，。、；：！？（）[]【】' for c in w):
            continue
        keywords.append(w)

    # 去重，保持频率信息
    return list(dict.fromkeys(keywords))


def check_r10_clue_repetition(q):
    """R10: 词重复线索检测 (NBME D18)

    检测：题干中的关键词是否**仅**出现在正确选项中。
    如果存在仅正确选项含有的题干关键词 → FAIL（should_fix）。

    技术参考: NBME Item-Writing Guide — "clue to the answer"
    """
    issues = []
    stem = q.get('question', '')
    answer = q.get('answer', '')
    opts = q.get('options', {})

    if not stem or not answer or len(opts) < 2:
        return issues
    if len(answer) > 1:  # 多选题跳过（X型）
        return issues
    if q.get('type', '') in ('X', 'X型'):
        return issues

    # 提取题干关键词
    stem_keywords = _extract_stem_keywords(stem)
    if len(stem_keywords) < 3:
        return issues

    # 统计每个选项命中的关键词
    option_hits = {}
    for letter, text in opts.items():
        hits = [kw for kw in stem_keywords if kw in text]
        option_hits[letter] = set(hits)

    # 检测：哪些题干关键词仅出现在正确选项中
    correct_hits = option_hits.get(answer, set())
    others_hits = set()
    for letter, hits in option_hits.items():
        if letter != answer:
            others_hits.update(hits)

    exclusive_to_correct = correct_hits - others_hits

    if exclusive_to_correct:
        clues = list(exclusive_to_correct)[:3]
        issues.append({
            'rule': 'R10',
            'severity': 'FAIL',
            'target': f"{q['id']}.stem",
            'detail': f'题干关键词仅出现在正确选项({answer})中(词重复线索/NBME D18): {", ".join(clues)}',
        })

    return issues


def check_r11_convergence(q):
    """R11: 收敛策略检测 (NBME D19)

    检测：正确选项与题干的术语共享数是否显著高于其他选项。
    如果正确选项命中数 > 其他选项平均命中数 × 2 → WARN（should_fix）。

    技术参考: NBME — "convergence strategy" where test-wise students
    can identify the key by counting overlapping terms.
    """
    issues = []
    stem = q.get('question', '')
    answer = q.get('answer', '')
    opts = q.get('options', {})

    if not stem or not answer or len(opts) < 3:
        return issues
    if len(answer) > 1:
        return issues
    if q.get('type', '') in ('X', 'X型'):
        return issues

    stem_keywords = _extract_stem_keywords(stem)
    if len(stem_keywords) < 3:
        return issues

    # 统计每个选项的关键词命中数
    hit_counts = {}
    for letter, text in opts.items():
        hit_counts[letter] = sum(1 for kw in stem_keywords if kw in text)

    correct_hits = hit_counts.get(answer, 0)
    other_hits = [v for k, v in hit_counts.items() if k != answer]

    if not other_hits:
        return issues

    avg_other = sum(other_hits) / len(other_hits)
    max_other = max(other_hits)

    # 收敛检测：正确选项命中数 > 其他选项 平均的2倍 且 > 其他选项最大值的1.5倍
    if correct_hits >= 3 and avg_other > 0:
        if correct_hits > avg_other * 2 and correct_hits > max_other * 1.5:
            issues.append({
                'rule': 'R11',
                'severity': 'WARN',
                'target': f"{q['id']}.stem",
                'detail': f'收敛策略嫌疑(NBME D19): 正确选项({answer})命中{correct_hits}个题干词，其他选项avg={avg_other:.1f} max={max_other}',
            })

    return issues


def check_r12_meaningless_suffix(q):
    """R12: 无意义后缀检测 (HC-6修复规则)

    检测选项是否使用无意义括号后缀凑长度。
    匹配 "(相关表现)""(相关类型)""(见上文)" 等 → FAIL。

    驱动: batch006 教训 — Agent4 用无意义后缀凑长度而非实质性扩充
    """
    issues = []

    # 无意义后缀模式
    meaningless_patterns = [
        (r'[（(]相关表现[）)]', '(相关表现)'),
        (r'[（(]相关类型[）)]', '(相关类型)'),
        (r'[（(]相关疾病[）)]', '(相关疾病)'),
        (r'[（(]相关症状[）)]', '(相关症状)'),
        (r'[（(]相关检查[）)]', '(相关检查)'),
        (r'[（(]相关治疗[）)]', '(相关治疗)'),
        (r'[（(]见上文[）)]', '(见上文)'),
        (r'[（(]见下表[）)]', '(见下表)'),
    ]

    for letter, text in q.get('options', {}).items():
        for pattern, name in meaningless_patterns:
            if re.search(pattern, text):
                issues.append({
                    'rule': 'R12',
                    'severity': 'FAIL',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'无意义后缀凑长度(HC-6): {name} → 应替换为实质区分信息',
                })
                break  # 每选项只报一次

    return issues


def check_r13_length_ceiling(q):
    """R13: 选项长度上限检测 (防过度加长)

    检测:
    - 单选项 > 20字 → FAIL（矫枉过正典型特征）
    - 选项平均 > 18字 → WARN（整体偏长）

    驱动: batch007 v2 (18.9字) + batch009 (15.3字 M8方剂21.0字)
    """
    issues = []
    if q.get('type', '') in ('X', 'X型'):
        return issues

    opts = q.get('options', {})
    lengths = [len(v) for v in opts.values() if v]
    if not lengths:
        return issues

    avg_len = sum(lengths) / len(lengths)

    # 单选项上限检测
    for letter, text in opts.items():
        tlen = len(text)
        if tlen > 20:
            issues.append({
                'rule': 'R13',
                'severity': 'FAIL',
                'target': f"{q['id']}.option{letter}",
                'detail': f'选项过长({tlen}字 > 20字)，疑似矫枉过正: "{text[:30]}..."',
            })

    # 整体平均偏长
    if avg_len > 18:
        issues.append({
            'rule': 'R13',
            'severity': 'WARN',
            'target': f"{q['id']}.options",
            'detail': f'选项平均长度{avg_len:.1f}字 > 18字，整体偏长（防过度加长）',
        })

    return issues


# ──────────────────────────────────────────
# 主校验引擎
# ──────────────────────────────────────────

# 基础检查（R1-R13，原有机化规则 + P3新增）
BASIC_CHECKS = [
    check_r1_forbidden,
    check_r2_length_ratio,
    check_r3_numeric_sort,
    check_r4_negation_bold,
    check_r5_option_count,
    check_r7_truncation,   # R7: 截断检测（batch006教训）
    check_r8_min_length,   # R8: 最小长度与截断防护（batch007教训）
    check_r9_missing_unit,  # R9: 数值缺单位检测（batch014教训）
    check_r6_numeric_discrimination,
    check_r10_clue_repetition,    # R10: 词重复线索 (D18, NBME)
    check_r11_convergence,        # R11: 收敛策略 (D19, NBME)
    check_r12_meaningless_suffix, # R12: 无意义后缀 (HC-6修复)
    check_r13_length_ceiling,     # R13: 选项长度上限 (防过度加长)
]

# STATIC_CHECKS 定义在函数全部定义后（见文件末尾附近）


def validate_questions(questions, verbose=False, mode='basic', filepath=None):
    """对题目列表执行校验规则，返回 (issues_by_question, summary)

    mode: 'basic' = R1-R6 + B1 + R9（默认，向后兼容）
          'full'  = R1-R6 + B1 + JS1 + S1-S4（预检脚本升级）
    """
    all_issues = {}
    total_pass = 0
    total_warn = 0
    total_fail = 0

    checks = list(BASIC_CHECKS)
    if mode == 'full':
        checks.extend(STATIC_CHECKS)

    for q in questions:
        q_issues = []
        for check_fn in checks:
            q_issues.extend(check_fn(q))

        all_issues[q['id']] = q_issues

        fail_count = sum(1 for i in q_issues if i['severity'] == 'FAIL')
        warn_count = sum(1 for i in q_issues if i['severity'] == 'WARN')

        if fail_count > 0:
            total_fail += 1
        elif warn_count > 0:
            total_warn += 1
        else:
            total_pass += 1

    # B1 组检查（跨题目）
    b1_issues = check_b1_groups(questions)
    for issue in b1_issues:
        all_issues.setdefault('_b1_groups', []).append(issue)
        if issue['severity'] == 'FAIL':
            total_fail += 1
        elif issue['severity'] == 'WARN':
            total_warn += 1

    # full 模式：跨题目检查
    if mode == 'full':
        # S3 占位符页码检测（跨题目统计）
        s3_issues = check_s3_placeholder_pages(questions)
        for issue in s3_issues:
            all_issues.setdefault('_cross_question', []).append(issue)
            if issue['severity'] == 'FAIL':
                total_fail += 1
            elif issue['severity'] == 'WARN':
                total_warn += 1

        # JS1 JSON 完整性检测（文件级，2026-06-23 新增）
        js1_issues = check_js1_json_integrity(questions, filepath)
        for issue in js1_issues:
            all_issues.setdefault('_json_integrity', []).append(issue)
            if issue['severity'] == 'FAIL':
                total_fail += 1
            elif issue['severity'] == 'WARN':
                total_warn += 1

    summary = {
        'total_questions': len(questions),
        'pass': total_pass,
        'warn': total_warn,
        'fail': total_fail,
        'b1_groups_checked': len(find_b1_groups(questions)),
    }

    return all_issues, summary


def discover_files(batch_id):
    """发现指定批次的所有题库文件（优先使用 ALL_questions 合并文件，避免重复计数）"""
    batch_dir = BASE / "最终产物" / batch_id
    if not batch_dir.exists():
        # 也搜索中间产物
        batch_dir = BASE / "中间产物" / batch_id
    if not batch_dir.exists():
        return []

    # 优先查找 ALL_questions_FIXED 合并文件
    exclude_keywords = ('追溯', 'escalation', 'trace', '调用指令', 'module_')
    for name in ('ALL_questions_FIXED.json', 'ALL_questions_FIXED.md',
                 'ALL_questions.json', 'ALL_questions.md'):
        f = batch_dir / name
        if f.exists():
            return [f]

    # 回退：扫描所有文件（排除日志/告警/指令文件）
    files = []
    for ext in ('*.json', '*.md'):
        for f in sorted(batch_dir.glob(ext)):
            if any(kw in f.name for kw in ('追溯', 'escalation', 'trace', '调用指令')):
                continue
            files.append(f)
    return files


# ──────────────────────────────────────────
# 报告输出
# ──────────────────────────────────────────

def print_report(all_issues, summary, filepath):
    """打印控制台报告"""
    print(f"\n{'═'*60}")
    print(f"  选项设计机械化校验报告 — {filepath.name}")
    print(f"{'═'*60}\n")

    # 逐题输出
    for qid, issues in all_issues.items():
        if qid.startswith('_'):
            continue
        if not issues:
            continue
        fail_issues = [i for i in issues if i['severity'] == 'FAIL']
        warn_issues = [i for i in issues if i['severity'] == 'WARN']

        if fail_issues:
            icon = '✗'
        elif warn_issues:
            icon = '⚠️'
        else:
            icon = '✅'

        print(f"  {icon} {qid}")
        for issue in issues:
            sev_icon = '✗' if issue['severity'] == 'FAIL' else '⚠️'
            print(f"      {sev_icon} [{issue['rule']}] {issue['detail']}")

    # B1 组报告
    b1_issues = all_issues.get('_b1_groups', [])
    if b1_issues:
        print(f"\n  ── B1 型题专项检查 ──")
        for issue in b1_issues:
            sev_icon = '✗' if issue['severity'] == 'FAIL' else '⚠️'
            print(f"  {sev_icon} [{issue['rule']}] {issue['target']}: {issue['detail']}")

    # JS1 JSON 完整性报告
    js1_issues = all_issues.get('_json_integrity', [])
    if js1_issues:
        print(f"\n  ── JSON 完整性检查 ──")
        for issue in js1_issues:
            sev_icon = '✗' if issue['severity'] == 'FAIL' else '⚠️'
            print(f"  {sev_icon} [{issue['rule']}] {issue['target']}: {issue['detail']}")

    # 跨题目检查报告
    cross_issues = all_issues.get('_cross_question', [])
    if cross_issues:
        print(f"\n  ── 跨题目检查 ──")
        for issue in cross_issues:
            sev_icon = '✗' if issue['severity'] == 'FAIL' else '⚠️'
            print(f"  {sev_icon} [{issue['rule']}] {issue['target']}: {issue['detail']}")

    # 汇总
    print(f"\n{'─'*60}")
    print(f"  📊 汇总")
    print(f"  {'─'*56}")
    print(f"  题目总数:  {summary['total_questions']}")
    print(f"  ✅ 通过:   {summary['pass']}")
    print(f"  ⚠️ 告警:   {summary['warn']}")
    print(f"  ✗ 失败:    {summary['fail']}")
    if summary.get('b1_groups_checked', 0) > 0:
        print(f"  B1组数:    {summary['b1_groups_checked']}")

    # 规则命中统计
    rule_counts = Counter()
    for qid, issues in all_issues.items():
        for issue in issues:
            rule_counts[issue['rule']] += 1
    if rule_counts:
        print(f"\n  规则命中:")
        for rule, count in sorted(rule_counts.items()):
            print(f"    {rule}: {count} 处")

    print(f"{'═'*60}\n")


def save_json_report(all_issues, summary, filepath, batch_id, mode='basic'):
    """保存 JSON 报告"""
    report = {
        'report_metadata': {
            'report_id': f'OPTVAL-{datetime.now().strftime("%Y%m%d")}-{batch_id or "file"}',
            'validation_date': datetime.now().isoformat(),
            'source_file': str(filepath),
            'validator_version': '2.0',
            'check_mode': 'full (R1-R9+B1+JS1+S1-S4)' if mode == 'full' else 'basic (R1-R9+B1)',
        },
        'summary': summary,
        'issues': [],
    }

    for qid, issues in all_issues.items():
        for issue in issues:
            report['issues'].append({
                'question_id': qid,
                'rule': issue['rule'],
                'severity': issue['severity'],
                'target': issue['target'],
                'detail': issue['detail'],
            })

    output_path = OUTPUT_BASE / f"validate_options_report_{batch_id or filepath.stem}.json"
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"  📄 JSON 报告已保存: {output_path}")
    return output_path


# ──────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="选项设计机械化校验器 — HC-7 子规则硬编码检测"
    )
    parser.add_argument("--batch", "-b", help="批次ID（如 batch005）")
    parser.add_argument("--file", "-f", help="单个文件路径")
    parser.add_argument("--mode", "-m", choices=['basic', 'full'], default='full',
                        help='校验模式: basic=R1-R6+B1（快速）, full=R1-R6+B1+S1-S4（完整预检，默认）')
    parser.add_argument("--verbose", "-v", action="store_true", help="显示通过题目")
    args = parser.parse_args()

    if not args.batch and not args.file:
        parser.print_help()
        sys.exit(2)

    had_issues = False

    if args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"  ✗ 文件不存在: {filepath}")
            sys.exit(2)

        if filepath.suffix == '.json':
            questions = parse_json_file(filepath)
        elif filepath.suffix == '.md':
            questions = parse_md_file(filepath)
        else:
            print(f"  ✗ 不支持的文件格式: {filepath.suffix}")
            sys.exit(2)

        if not questions:
            print(f"  ⚠️ 未解析到任何题目: {filepath}")
            sys.exit(2)

        all_issues, summary = validate_questions(questions, args.verbose, mode=args.mode, filepath=str(filepath))
        print_report(all_issues, summary, filepath)
        batch_id = filepath.stem
        save_json_report(all_issues, summary, filepath, batch_id, mode=args.mode)

        if summary['fail'] > 0 or summary['warn'] > 0:
            had_issues = True

    elif args.batch:
        files = discover_files(args.batch)
        if not files:
            print(f"  ✗ 未找到批次 {args.batch} 的题库文件")
            sys.exit(2)

        print(f"  📁 批次 {args.batch}: 发现 {len(files)} 个文件")

        all_questions = []
        for filepath in files:
            print(f"  📄 解析: {filepath.name}")
            if filepath.suffix == '.json':
                qs = parse_json_file(filepath)
            elif filepath.suffix == '.md':
                qs = parse_md_file(filepath)
            else:
                continue
            all_questions.extend(qs)
            print(f"      → {len(qs)} 题")

        if not all_questions:
            print(f"  ⚠️ 未解析到任何题目")
            sys.exit(2)

        all_issues, summary = validate_questions(all_questions, args.verbose, mode=args.mode, filepath=str(files[0]))
        print_report(all_issues, summary, files[0])
        save_json_report(all_issues, summary, files[0], args.batch)

        if summary['fail'] > 0 or summary['warn'] > 0:
            had_issues = True

    sys.exit(1 if had_issues else 0)


if __name__ == "__main__":
    main()
