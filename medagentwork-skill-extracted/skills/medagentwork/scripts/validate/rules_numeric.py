"""
rules_numeric.py — 数值型校验规则 R1-R9
从 validate_options.py 拆分而来
"""
import re
from collections import defaultdict, Counter
from .contracts import FORBIDDEN_PATTERNS, NEGATION_WORDS, NUMERIC_PARAMS, is_x_type


def check_r1_forbidden(q: dict) -> list[dict]:
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
        if re.search(r'[（(][^）)]*[）)]\s*$', text) and not re.search(r'[（(]见上|见下|[）)]$', text):
            if re.search(r'[（(]见[上文下][）)]', text):
                issues.append({
                    'rule': 'R1',
                    'severity': 'WARN',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'选项末尾含括号说明后缀: "{text[-30:]}"',
                })
    return issues


def check_r2_length_ratio(q: dict) -> list[dict]:
    """R2: 选项长度异常检测 — 正确选项显著长于其他"""
    issues = []
    if is_x_type(q['type']):
        return issues
    opts = q.get('options', {})
    if len(opts) < 3:
        return issues
    answer = q.get('answer', '')
    if not answer or len(answer) != 1:
        return issues
    lengths = {k: len(v) for k, v in opts.items()}
    correct_len = lengths.get(answer, 0)
    if correct_len == 0:
        return issues
    other_lens = [l for k, l in lengths.items() if k != answer]
    if not other_lens:
        return issues
    min_other = min(other_lens)
    if min_other == 0:
        return issues
    ratio = correct_len / min_other
    if ratio > 2.0:
        issues.append({
            'rule': 'R2',
            'severity': 'FAIL',
            'target': f"{q['id']}.options",
            'detail': f'正确选项({answer})长度比{ratio:.1f}x (>2.0): {correct_len}字 vs {min_other}字',
        })
    elif ratio > 1.5:
        issues.append({
            'rule': 'R2',
            'severity': 'WARN',
            'target': f"{q['id']}.options",
            'detail': f'正确选项({answer})长度({correct_len}字)显著长于其他选项(均{min_other}字)',
        })
    return issues


def check_r3_numeric_sort(q: dict) -> list[dict]:
    """R3: 数值选项排序检测 — 数值选项应递增排列"""
    issues = []
    opts = q.get('options', {})
    numeric_opts = {}
    for letter, text in opts.items():
        m = re.match(r'^[\d.]+\s*(%|mmHg|mg/dL|mmol/L|pg/mL|mL/min)?', text.strip())
        if m:
            try:
                num = float(re.match(r'^[\d.]+', text.strip()).group())
                numeric_opts[letter] = num
            except (ValueError, AttributeError):
                pass
    if len(numeric_opts) < 3:
        return issues
    letters = sorted(numeric_opts.keys())
    values = [numeric_opts[l] for l in letters]
    if values != sorted(values):
        issues.append({
            'rule': 'R3',
            'severity': 'WARN',
            'target': f"{q['id']}.options",
            'detail': f'数值选项未按递增排序: {", ".join(f"{l}={numeric_opts[l]}" for l in letters)}',
        })
    return issues


def check_r4_negation_bold(q):
    """R4: 否定词加粗检测"""
    issues = []
    stem = q.get('question', '')
    if not stem:
        return issues

    has_negation = re.search(r'不包括|不正确|错误的|不属于|不是|除外|哪项不对|哪项错|描述错误|描述不正确', stem)
    if not has_negation:
        return issues

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
    count = len(q.get('options', {}))
    qtype = q.get('type', 'A1')

    if qtype in ('A1', 'A2', 'B1'):
        if count != 5:
            issues.append({
                'rule': 'R5',
                'severity': 'FAIL',
                'target': f"{q['id']}.options",
                'detail': f'{qtype}型题应有5个选项，实际{count}个',
            })
    elif is_x_type(qtype):
        if count < 4:
            issues.append({
                'rule': 'R5',
                'severity': 'FAIL',
                'target': f"{q['id']}.options",
                'detail': f'X型题应至少有4个选项，实际{count}个',
            })
    return issues


def check_r6_numeric_discrimination(q):
    """R6: 数值区分度检测 — 相似数值选项过多"""
    issues = []
    if is_x_type(q['type']):
        return issues
    opts = q.get('options', {})
    numeric_vals = []
    for letter, text in opts.items():
        m = re.match(r'^([\d.]+)', text.strip())
        if m:
            try:
                num = float(m.group(1))
                numeric_vals.append((letter, num))
            except ValueError:
                pass
    if len(numeric_vals) < 3:
        return issues
    vals = [v for _, v in numeric_vals]
    val_range = max(vals) - min(vals)
    avg_val = sum(vals) / len(vals)
    if avg_val > 0 and val_range / avg_val < 0.1:
        issues.append({
            'rule': 'R6',
            'severity': 'WARN',
            'target': f"{q['id']}.options",
            'detail': f'数值选项过于集中(范围{val_range:.1f}, 均值{avg_val:.1f}): {", ".join(f"{l}={v}" for l, v in numeric_vals)}',
        })
    return issues


def check_r7_truncation(q):
    """R7: 截断检测 — 选项文本过短可能被截断"""
    issues = []
    if is_x_type(q['type']):
        return issues
    opts = q.get('options', {})
    for letter, text in opts.items():
        stripped = text.strip()
        if stripped.endswith('..'):
            issues.append({
                'rule': 'R7',
                'severity': 'FAIL',
                'target': f"{q['id']}.option{letter}",
                'detail': f'选项以".."结尾，疑似截断残留: "{stripped}"',
            })
            continue
        if stripped.endswith('.'):
            core_len = len(stripped) - 1
            if core_len <= 2:
                issues.append({
                    'rule': 'R7',
                    'severity': 'FAIL',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'选项疑似被严重截断(仅{core_len}字): "{stripped}"',
                })
            elif core_len <= 7:
                issues.append({
                    'rule': 'R7',
                    'severity': 'FAIL' if core_len <= 4 else 'WARN',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'选项以句号结尾且偏短({core_len}字)，疑似截断: "{stripped}"',
                })
    return issues


def check_r8_min_length(q):
    """R8: 最小长度检测 — 选项过短"""
    issues = []
    if is_x_type(q['type']):
        return issues

    legit_terms = {'妄想', '幻觉', '障碍', '减退', '缺乏', '低落', '焦虑', '恐惧',
                   '躁狂', '抑郁', '木僵', '违拗', '缄默', '痴呆', '谵妄', '强迫',
                   '疑病', '失眠', '嗜睡', '人格', '自知力', 'PTSD', 'OCD', 'AD'}

    suspicious_ends = {'的', '了', '等', '与', '或', '及', '对', '为', '于', '和', '是'}

    for letter, text in q.get('options', {}).items():
        stripped = text.strip()
        tlen = len(stripped)

        if re.match(r'^[\d.%\u2103/\-～~约]+[天周月年岁日小时分钟mgml次°]*$', stripped):
            continue

        if tlen <= 6 and any(term in stripped for term in legit_terms):
            continue

        if tlen >= 6 and stripped[-1] in suspicious_ends:
            issues.append({
                'rule': 'R8',
                'severity': 'FAIL',
                'target': f"{q['id']}.option{letter}",
                'detail': f'选项以"{stripped[-1]}"结尾且长度{tlen}字，疑似截断: "{stripped}"',
            })
            continue

        if stripped.endswith(('，', '、', ',')):
            issues.append({
                'rule': 'R8',
                'severity': 'FAIL',
                'target': f"{q['id']}.option{letter}",
                'detail': f'选项以逗号/顿号结尾，疑似截断为半句: "{stripped}"',
            })
            continue

        if 0 < tlen < 3 and stripped not in ('无', '有', '是', '否'):
            issues.append({
                'rule': 'R8',
                'severity': 'WARN',
                'target': f"{q['id']}.option{letter}",
                'detail': f'选项过短({tlen}字): "{stripped}"',
            })

    return issues


def check_r9_missing_unit(q):
    """R9: 数值缺单位检测"""
    issues = []
    if is_x_type(q['type']):
        return issues

    clinical_params = [
        'FEV1/FVC', 'LVEF', 'FEV1', 'FVC', 'PaO2', 'PaCO2', 'SaO2', 'SpO2',
        'PEF', 'TLC', 'RV', 'DLCO', 'BNP', 'NT-proBNP', 'HbA1c',
        'INR', 'PT', 'APTT', 'TT', 'D-二聚体',
        'CRP', 'ESR', 'PCT', 'CK-MB', 'cTnI', 'cTnT', 'ALT', 'AST',
        'Cr', 'BUN', 'eGFR', 'K\\+', 'Na\\+', 'Ca2\\+', 'Cl\\-',
        'pH', 'HCO3', 'BE', '乳酸', '血糖', '血钾', '血钠', '血钙',
    ]

    time_contexts = [
        '频率', '速率', '次数', '控制在', '维持在', '时间窗',
        '门球时间', '按压', '通气', '按压.*通气',
        '每分钟', '每小时', '每天',
    ]

    exemption_patterns = [
        r'P\d{2,4}',
        r'\d{4}年',
        r'N\d{3}-\d{3}',
        r'\d+%',
        r'\d+\s*[次分秒时天周月年岁]',
        r'\d+\s*[mkc]?[gGlL]',
        r'\d+\s*mm\s*Hg',
        r'\d+\s*cm\s*H2O',
        r'\d+\s*[°℃]',
        r'\d+\s*mmol',
        r'\d+\s*[×x]\s*\d+',
    ]

    for letter, text in q.get('options', {}).items():
        stripped = text.strip()

        if re.match(r'^[\d.%\-～~约><=<>≥≤]+$', stripped):
            continue

        if any(re.search(pat, stripped) for pat in exemption_patterns):
            continue

        for param in clinical_params:
            if param == 'FVC':
                param_pattern = re.compile(
                    r'(?<!FEV1/)FVC\s*[<>≤≥]?\s*(\d+\.?\d*)\s*(?![％%]|mm\s*Hg|cm\s*H2O|mmHg)'
                )
            else:
                param_pattern = re.compile(
                    rf'{param}\s*[<>≤≥]?\s*(\d+\.?\d*)\s*(?![％%]|mm\s*Hg|cm\s*H2O|mmHg)'
                )
            m = param_pattern.search(stripped)
            if m:
                num_val = m.group(1)
                if param == 'FEV1/FVC' and float(num_val) < 10:
                    continue
                expected_unit = '%' if param in ('LVEF', 'FEV1', 'FVC', 'FEV1/FVC', 'PEF', 'TLC', 'RV', 'DLCO', 'HbA1c') else 'mmHg'
                issues.append({
                    'rule': 'R9',
                    'severity': 'FAIL',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'临床参数"{param}"后数值{num_val}缺少单位(应为{expected_unit})，属事实错误: "{stripped[:40]}"',
                })
                break

        for ctx in time_contexts:
            ctx_pattern = re.compile(
                rf'{ctx}\s*[：:]*\s*[<>≤≥]?\s*(\d+\.?\d*)\s*'
                rf'(?!(次/分|/min|分钟|小时|[天周月年岁秒日]|mmHg|%|mL|mg|°C|℃))'
            )
            m = ctx_pattern.search(stripped)
            if m:
                num_val = m.group(1)
                if re.search(rf'P{num_val}', stripped):
                    continue
                severity = 'FAIL' if any(kw in ctx for kw in ['按压', '通气', '门球时间', '时间窗']) else 'WARN'
                issues.append({
                    'rule': 'R9',
                    'severity': severity,
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'时间/频率上下文"{ctx}"后数值{num_val}缺少单位(如分钟/次/天等): "{stripped[:40]}"',
                })
                break

        threshold_pattern = re.compile(
            r'(?:PaO2|PaCO2|SaO2|LVEF|BNP|血糖|血压|心率|呼吸|体温|氧合)\s*[<>≤≥]?\s*(\d+\.?\d*)\s*$'
        )
        m = threshold_pattern.search(stripped)
        if m:
            num = m.group(1)
            if '.' not in num and int(num) < 1000:
                issues.append({
                    'rule': 'R9',
                    'severity': 'FAIL',
                    'target': f"{q['id']}.option{letter}",
                    'detail': f'生理参数阈值{num}缺少单位(如mmHg/次分/%/mmol/L等)，属事实错误: "{stripped[:40]}"',
                })

    return issues


BASIC_NUMERIC_CHECKS = [
    check_r1_forbidden,
    check_r2_length_ratio,
    check_r3_numeric_sort,
    check_r4_negation_bold,
    check_r5_option_count,
    check_r6_numeric_discrimination,
    check_r7_truncation,
    check_r8_min_length,
    check_r9_missing_unit,
]
