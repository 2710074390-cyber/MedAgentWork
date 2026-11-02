"""
rules_structural.py — 结构型校验规则 R10-R13 + B1/JS1/S3
从 validate_options.py 拆分而来
"""
import os
import re
import sys
from collections import defaultdict, Counter
from .contracts import STEM_STOP_WORDS, is_x_type

# v2.1 回灌 (2026-10-13): 阈值单一事实来源 — 运行时从 pipeline.yaml thresholds 段读取
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from pipeline_config import get_number  # noqa: E402

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


REAL_SOURCE_TYPES = ('考研真题', '执业医师真题', '真题', '考研原题', '执医真题')


def origin_kind(q: dict) -> str:
    """返回真题来源类型（空串=原创）。

    存在意义：真题的题干/选项**不允许为了满足形式规则而改写**（HC-4b / 原题保真），
    因此长度类规则对真题必须整体豁免——否则规则会逼着人改原题。
    """
    if q.get('kaoyan_origin'):
        return '考研真题'
    if q.get('zhiyi_origin'):
        return '执业医师真题'
    if q.get('zhiyi_pdf_origin'):
        return '执业医师历年真题'
    st = str(q.get('source_type') or '')
    return st if st in REAL_SOURCE_TYPES else ''


CONDITIONAL_PATTERNS = [
    ('时间/年龄窗', r'\d+\s*[～~\-－至]\s*\d+\s*(小时|分钟|天|日|周|月|年|岁)'),
    ('适用人群', r'^(?:[^，。；]{0,12})?(者|病人|患者)[，,：:]'),
    ('特殊人群', r'(妊娠|哺乳|孕妇|儿童|小儿|婴儿|婴幼儿|新生儿|老年|产妇)'),
    ('器官功能', r'(肝|肾|心|肺|脑)功能(不全|损害|衰竭|减退)'),
    ('合并症', r'(合并|伴有|伴|继发|并发)[^，。；]{0,10}(不全|障碍|衰竭|感染|休克|出血|疾病|高血压|糖尿病)'),
    ('条件从句', r'(若|如果|假如|一旦|如|当|在)[^，。；]{0,16}(时|者|则|应|需|可|不|，)'),
    ('目的从句', r'(以免|以防|避免|防止)[^，。；]{2,}'),
    ('因果从句', r'(因|由于)[^，。；]{2,}(故|因此|所以)'),
    ('时段限定', r'(在|于)[^，。；]{0,10}(时|情况下|条件下|期间)'),
]


def conditional_feature(text: str) -> str:
    """判断选项是否含"删短就改变医学含义"的限定，返回特征名（空串=无）。

    只认**改变结论**的限定，不认任意长句：见 check_r13_length_ceiling 的说明。
    模式按特异性从高到低排列，返回第一个命中项，便于在证据里写清"豁免理由"。
    """
    t = str(text or '').strip()
    if not t:
        return ''
    for name, pat in CONDITIONAL_PATTERNS:
        if re.search(pat, t):
            return name
    return ''


def check_r13_length_ceiling(q):
    """R13: 选项长度上限检测（2026-11-02 降级 + 条件从句豁免，P2-S5）

    变更理由（AC-P2-06）：原实现把"超过 20 字"一律判 FAIL，但医学选项里有一类
    **删短就错**的长选项——它们长在限定条件上：

        「嵌顿3～4小时内、无腹膜刺激征者可行手法复位」   ← 时间窗 + 适用人群
        「一旦形成脓肿，一般常选用口外切口进行切开引流」  ← 条件从句
        「切开时注意深度，以免伤及气管后壁」             ← 目的从句（防并发症）

    把这三类判 FAIL，等于要求作者删掉安全边界，属于误伤。因此：
      - 命中条件/因果/时间窗/人群限定时 → `exempted=True` + severity=INFO（只记录，不拦）
      - 其余超长 → severity=**WARN**（降级，不再 FAIL）

    为什么是降级而不是删规则：R13 防的是"矫枉过正"（把选项硬凑长来掩盖区分度不足），
    这类问题真实存在；但它的严重度低于 R2（正确项/最短干扰项长度比）——R2 保留为 FAIL，
    由它守住"靠长度猜答案"这条硬线。
    """
    issues = []
    if q.get('type', '') in ('X', 'X型'):
        return issues

    opts = q.get('options', {})
    lengths = [len(v) for v in opts.values() if v]
    if not lengths:
        return issues

    avg_len = sum(lengths) / len(lengths)

    # v2.1 回灌: 阈值取自 pipeline.yaml（缺失回退内置默认 20 / 18）
    length_max = get_number('option_length_max', 20)
    avg_max = get_number('option_avg_max', 18)

    oversize = [(lab, txt) for lab, txt in opts.items() if txt and len(txt) > length_max]

    # 第一层豁免：真题原题。选项不可改写，长度规则无从施加（HC-4b 原题保真）。
    # 注意：只有**确实有选项超长**时才出具豁免记录；否则每道真题都会冒一条 INFO，
    # 把校验输出淹掉（这是初版的实现错误，2026-11-02 修正）。
    origin = origin_kind(q)
    if origin and (oversize or avg_len > avg_max):
        return [{
            'rule': 'R13',
            'severity': 'INFO',
            'exempted': True,
            'origin_exempt': origin,
            'target': f"{q['id']}.options",
            'detail': (f'真题原题（{origin}）：超长 {len(oversize)} 项、均长 {avg_len:.1f} 字，'
                       f'但选项不得改写 → R13 整体豁免'),
        }]

    for letter, text in opts.items():
        tlen = len(text)
        if tlen <= length_max:
            continue
        feature = conditional_feature(text)
        if feature:
            issues.append({
                'rule': 'R13',
                'severity': 'INFO',
                'exempted': True,
                'target': f"{q['id']}.option{letter}",
                'detail': (f'选项 {tlen} 字超过 {length_max:g} 字，但含「{feature}」限定，'
                           f'删短会改变医学含义 → 豁免'),
            })
        else:
            issues.append({
                'rule': 'R13',
                'severity': 'WARN',
                'target': f"{q['id']}.option{letter}",
                'detail': f'选项过长({tlen}字 > {length_max:g}字)，疑似矫枉过正: "{text[:30]}..."',
            })

    if avg_len > avg_max:
        issues.append({
            'rule': 'R13',
            'severity': 'WARN',
            'target': f"{q['id']}.options",
            'detail': f'选项平均长度{avg_len:.1f}字 > {avg_max:g}字，整体偏长（防过度加长）',
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
