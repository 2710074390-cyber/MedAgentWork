"""
rules_structural.py — 结构型校验规则 R10-R13 + B1/JS1/S3
从 validate_options.py 拆分而来
"""
import re
from collections import defaultdict, Counter
from .contracts import STEM_STOP_WORDS, is_x_type

try:
    import jieba
    _JIEBA_AVAILABLE = True
except ImportError:
    _JIEBA_AVAILABLE = False


def _extract_stem_keywords(stem):
    """从题干中提取有意义的关键词"""
    if _JIEBA_AVAILABLE:
        words = list(jieba.cut(stem))
    else:
        words = []
        for n in (2, 3, 4):
            for i in range(len(stem) - n + 1):
                words.append(stem[i:i+n])

    keywords = []
    for w in words:
        w = w.strip()
        if len(w) < 2:
            continue
        if w in STEM_STOP_WORDS:
            continue
        if all(c in '0123456789.%-+×x,，。、；：！？（）[]【】' for c in w):
            continue
        keywords.append(w)

    return list(dict.fromkeys(keywords))


def check_r10_clue_repetition(q):
    """R10: 词重复线索检测 (NBME D18)"""
    issues = []
    stem = q.get('question', '')
    answer = q.get('answer', '')
    opts = q.get('options', {})

    if not stem or not answer or len(opts) < 2:
        return issues
    if len(answer) > 1:
        return issues
    if q.get('type', '') in ('X', 'X型'):
        return issues

    stem_keywords = _extract_stem_keywords(stem)
    if len(stem_keywords) < 3:
        return issues

    option_hits = {}
    for letter, text in opts.items():
        hits = [kw for kw in stem_keywords if kw in text]
        option_hits[letter] = set(hits)

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
    """R11: 收敛策略检测 (NBME D19)"""
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

    option_hits = {}
    for letter, text in opts.items():
        hits = sum(1 for kw in stem_keywords if kw in text)
        option_hits[letter] = hits

    correct_hits = option_hits.get(answer, 0)
    other_hits = [h for l, h in option_hits.items() if l != answer]
    if not other_hits:
        return issues
    avg_other = sum(other_hits) / len(other_hits)

    if avg_other > 0 and correct_hits > avg_other * 2:
        issues.append({
            'rule': 'R11',
            'severity': 'WARN',
            'target': f"{q['id']}.options",
            'detail': f'正确选项({answer})术语共享数({correct_hits})显著高于其他选项(均{avg_other:.1f})(收敛策略/NBME D19)',
        })

    return issues


def check_r12_meaningless_suffix(q):
    """R12: 无意义后缀检测"""
    issues = []
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
                    'detail': f'无意义后缀凑长度(HC-6): {name}，应替换为实质区分信息',
                })
                break
    return issues


def check_r13_length_ceiling(q):
    """R13: 选项长度上限检测"""
    issues = []
    if q.get('type', '') in ('X', 'X型'):
        return issues

    opts = q.get('options', {})
    lengths = [len(v) for v in opts.values() if v]
    if not lengths:
        return issues

    avg_len = sum(lengths) / len(lengths)

    for letter, text in opts.items():
        tlen = len(text)
        if tlen > 20:
            issues.append({
                'rule': 'R13',
                'severity': 'FAIL',
                'target': f"{q['id']}.option{letter}",
                'detail': f'选项过长({tlen}字 > 20字)，疑似矫枉过正: "{text[:30]}..."',
            })

    if avg_len > 18:
        issues.append({
            'rule': 'R13',
            'severity': 'WARN',
            'target': f"{q['id']}.options",
            'detail': f'选项平均长度{avg_len:.1f}字 > 18字，整体偏长（防过度加长）',
        })
    return issues


def check_b1_groups(questions):
    """B1 型题专项检查"""
    issues = []
    groups = defaultdict(list)
    for q in questions:
        if q.get('type') == 'B1' and q.get('b1_group'):
            groups[q['b1_group']].append(q)

    for group_key, group_qs in groups.items():
        if len(group_qs) < 2:
            continue

        shared_opts = group_qs[0].get('b1_shared_options') or group_qs[0].get('options', {})
        if not shared_opts:
            continue

        short_opts = [k for k, v in shared_opts.items() if len(v) <= 2]
        if len(short_opts) >= 3:
            issues.append({
                'rule': 'B1-1',
                'severity': 'WARN',
                'target': f"N{group_key}.shared_options",
                'detail': f'B1共用选项过于笼统: {len(short_opts)}个选项≤2字 ({", ".join(f"{k}={shared_opts[k]}" for k in short_opts)})',
            })

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

        unique_answers = set(answers)
        if len(unique_answers) < 3 and len(answers) >= 3:
            issues.append({
                'rule': 'B1-3',
                'severity': 'WARN',
                'target': f"N{group_key}.coverage",
                'detail': f'B1答案覆盖不足: {len(answers)}题仅覆盖{len(unique_answers)}个选项位({",".join(sorted(unique_answers))})',
            })

    return issues


def check_js1_json_integrity(questions, filepath=None):
    """JS1: JSON 完整性检测"""
    issues = []

    if not questions:
        issues.append({
            'rule': 'JS1',
            'severity': 'FAIL',
            'target': '_file',
            'detail': '题库文件解析后为空（可能 JSON 结构损坏或文件为空）',
        })
        return issues

    truncation_indicators = ['...', '..', '…']

    for q in questions:
        qid = q.get('id', '?')

        stem = q.get('question', '')
        for ti in truncation_indicators:
            if stem.rstrip().endswith(ti) and len(stem) < 30:
                issues.append({
                    'rule': 'JS1',
                    'severity': 'FAIL',
                    'target': f'{qid}.stem',
                    'detail': f'题干疑似截断（以"{ti}"结尾）: "{stem[:50]}"',
                })

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

        answer = q.get('answer', '')
        if isinstance(answer, list):
            for a in answer:
                if not isinstance(a, str) or not all(c in 'ABCDE' for c in a):
                    issues.append({
                        'rule': 'JS1',
                        'severity': 'WARN',
                        'target': f'{qid}.answer',
                        'detail': f'答案格式异常(列表项非A-E字母): {a}',
                    })
                    break
        elif isinstance(answer, str):
            if answer and not all(c in 'ABCDE' for c in answer.replace('/', '').replace(',', '')):
                pass

        for field in ('question', 'answer'):
            val = q.get(field, '')
            if isinstance(val, str) and len(val) > 0:
                for ti in truncation_indicators:
                    if ti in val[-5:]:
                        issues.append({
                            'rule': 'JS1',
                            'severity': 'WARN',
                            'target': f'{qid}.{field}',
                            'detail': f'{field}疑似截断（末尾含"{ti}"）',
                        })
                        break

    return issues


def check_s3_placeholder_pages(questions):
    """S3: 占位符页码检测"""
    issues = []
    page_pattern = re.compile(r'P\d{3,4}')
    for q in questions:
        stem = q.get('question', '')
        matches = page_pattern.findall(stem)
        if len(matches) > 2:
            issues.append({
                'rule': 'S3',
                'severity': 'WARN',
                'target': f"{q['id']}.stem",
                'detail': f'题干含{len(matches)}处页码引用: {", ".join(matches[:5])}',
            })
    return issues


STRUCTURAL_CHECKS = [
    check_r10_clue_repetition,
    check_r11_convergence,
    check_r12_meaningless_suffix,
    check_r13_length_ceiling,
]
