"""
rules_static.py — 静态检查规则 S1-S4
从 validate_options.py 拆分而来
"""
import re
from .contracts import FORBIDDEN_PATTERNS, is_x_type


def check_s1_schema_completeness(q):
    """S1: Schema 完整性校验 + 字段类型验证"""
    issues = []
    required = [
        ('id', '题目ID'),
        ('type', '题型标记'),
        ('question', '题干'),
        ('answer', '答案'),
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
    opts = q.get('options', {})
    if not opts:
        issues.append({
            'rule': 'S1',
            'severity': 'FAIL',
            'target': f"{q.get('id', '?')}.options",
            'detail': '选项组为空或缺失',
        })

    answer = q.get('answer')
    if answer is not None:
        if isinstance(answer, str):
            if answer and not all(c in 'ABCDE' for c in answer.replace('/', '').replace(',', '')):
                issues.append({
                    'rule': 'S1',
                    'severity': 'WARN',
                    'target': f"{q.get('id', '?')}.answer",
                    'detail': f'答案格式异常(非A-E字母): {answer}',
                })
        elif isinstance(answer, list):
            for a in answer:
                if not isinstance(a, str) or not all(c in 'ABCDE' for c in a):
                    issues.append({
                        'rule': 'S1',
                        'severity': 'WARN',
                        'target': f"{q.get('id', '?')}.answer",
                        'detail': f'答案格式异常(列表项非A-E字母): {a}',
                    })
                    break

    return issues


def check_s2_null_values(q):
    """S2: 空值检测"""
    issues = []
    qid = q.get('id', '?')

    stem = q.get('question', '')
    if not stem or not stem.strip():
        issues.append({
            'rule': 'S2',
            'severity': 'FAIL',
            'target': f'{qid}.question',
            'detail': '题干为空',
        })

    answer = q.get('answer', '')
    if not answer or (isinstance(answer, str) and not answer.strip()):
        issues.append({
            'rule': 'S2',
            'severity': 'FAIL',
            'target': f'{qid}.answer',
            'detail': '答案为空',
        })

    opts = q.get('options', {})
    for letter, text in opts.items():
        if not text or not text.strip():
            issues.append({
                'rule': 'S2',
                'severity': 'WARN',
                'target': f'{qid}.option{letter}',
                'detail': f'选项{letter}内容为空',
            })

    return issues


def check_s4_absolute_language(q):
    """S4: 绝对化用语检测"""
    issues = []
    qid = q.get('id', '?')

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
        (r'百分之', '绝对化用语"百分之"'),
    ]

    stem = q.get('question', '')
    for pattern, desc in absolute_patterns:
        if re.search(pattern, stem):
            issues.append({
                'rule': 'S4',
                'severity': 'WARN',
                'target': f'{qid}.stem',
                'detail': f'{desc} 出现在题干中',
            })

    for letter, text in q.get('options', {}).items():
        for pattern, desc in absolute_patterns:
            if re.search(pattern, text):
                issues.append({
                    'rule': 'S4',
                    'severity': 'WARN',
                    'target': f'{qid}.option{letter}',
                    'detail': f'{desc} 出现在选项中',
                })
                break

    return issues


STATIC_CHECKS = [
    check_s1_schema_completeness,
    check_s2_null_values,
    check_s4_absolute_language,
]
