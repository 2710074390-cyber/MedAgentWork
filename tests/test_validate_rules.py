"""validate_options R1-R13 规则黄金用例（pytest 兼容，纯 assert）。

用例来源：FACT.md 历史灾难样本（batch006 截断 / batch007 系统截断 /
batch014 缺单位回归 / NBME D18/D19 线索检测）+ 规则文档。
运行: python scripts/run_tests.py  或  python -m pytest tests/ -q
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import validate_options as vo


def _q(options, answer='A', stem='关于该疾病的治疗，以下哪项是正确的？', qtype='A1', qid='T-001'):
    return {'id': qid, 'type': qtype, 'question': stem, 'options': options, 'answer': answer}


def _sev(issues, rule):
    return [i['severity'] for i in issues if i['rule'] == rule]


# ── R1 禁止项 / 绝对化用语 ──

def test_r1_forbidden_all_of_above():
    q = _q({'A': '以上都是', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r1_forbidden(q), 'R1')


def test_r1_absolute_words_warn():
    q = _q({'A': '必须立即手术', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'WARN' in _sev(vo.check_r1_forbidden(q), 'R1')


# ── R2 长度比 ──

def test_r2_ratio_over_2_fail():
    q = _q({'A': '短', 'B': '这是一个非常长的选项内容超过两倍长度阈值', 'C': '中', 'D': '中', 'E': '中'}, answer='B')
    assert 'FAIL' in _sev(vo.check_r2_length_ratio(q), 'R2')


def test_r2_ratio_15_to_2_warn():
    q = _q({'A': '短选项内容', 'B': '中等长度选项内容测试', 'C': '中等长度选项', 'D': '中等长度选项', 'E': '中等长度选项'}, answer='B')
    sev = _sev(vo.check_r2_length_ratio(q), 'R2')
    assert sev and sev[0] == 'WARN'


# ── R3 数值排序 ──

def test_r3_numeric_not_sorted_warn():
    q = _q({'A': '3ml', 'B': '1ml', 'C': '2ml', 'D': '5ml', 'E': '4ml'})
    assert 'WARN' in _sev(vo.check_r3_numeric_sort(q), 'R3')


# ── R4 否定词加粗 ──

def test_r4_negation_not_bolded_warn():
    q = _q({'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
           stem='关于心衰的治疗，以下哪项不包括？')
    assert 'WARN' in _sev(vo.check_r4_negation_bold(q), 'R4')


# ── R5 选项数量 ──

def test_r5_a1_needs_five_options():
    q = _q({'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁'})
    assert 'FAIL' in _sev(vo.check_r5_option_count(q), 'R5')


# ── R7 截断（batch006 教训）──

def test_r7_double_dot_residue_fail():
    q = _q({'A': '治疗..', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r7_truncation(q), 'R7')


def test_r7_severe_truncation_fail():
    q = _q({'A': '致.', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r7_truncation(q), 'R7')


# ── R8 最小长度 / 助词结尾（batch007 教训）──

def test_r8_ends_with_conjunction_fail():
    q = _q({'A': '该患者需要立即给予抗凝治疗的', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r8_min_length(q), 'R8')


def test_r8_number_without_unit_warn():
    q = _q({'A': '血压120', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'WARN' in _sev(vo.check_r8_min_length(q), 'R8')


# ── R9 缺单位（batch014 教训）──

def test_r9_clinical_param_missing_unit_fail():
    q = _q({'A': 'LVEF<40', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r9_missing_unit(q), 'R9')


def test_r9_with_unit_no_issue():
    q = _q({'A': 'LVEF<40%', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert vo.check_r9_missing_unit(q) == []


# v2.1 (2026-08-20 审查修复): FEV1/FVC 是无量纲比值，0.7/<0.7 是标准 COPD 诊断表述
# （此前 'FVC' 子串先命中 → 假 FAIL；本用例是修复的回归防线）

def test_r9_fev1fvc_ratio_no_false_positive():
    q = _q({'A': 'FEV1/FVC<0.7', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert vo.check_r9_missing_unit(q) == []


def test_r9_fev1fvc_ratio_without_comparator_no_false_positive():
    q = _q({'A': 'FEV1/FVC 0.7', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert vo.check_r9_missing_unit(q) == []


def test_r9_fev1fvc_other_param_still_detected():
    # 同一选项内 FEV1/FVC 比值豁免，但其他缺单位参数仍应被检出
    q = _q({'A': 'FEV1/FVC<0.7，PaO2<60', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    sev = _sev(vo.check_r9_missing_unit(q), 'R9')
    assert 'FAIL' in sev
    assert any('PaO2' in i['detail'] for i in vo.check_r9_missing_unit(q))


def test_r9_bare_fvc_still_fail():
    # 裸 'FVC'（非 FEV1/FVC 复合）后跟无量纲数值仍应报缺单位（FVC 以 L 计量）
    q = _q({'A': 'FVC<1.5', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r9_missing_unit(q), 'R9')


# ── R10 词重复线索（NBME D18）──
# 注: 强制 n-gram 关键词提取（_JIEBA_AVAILABLE=False），使用例不依赖 jieba 分词版本

def test_r10_exclusive_keyword_fail():
    import scripts.validate.rules_structural as rs
    rs._JIEBA_AVAILABLE = False  # 确定性 n-gram 模式
    q = _q({'A': '肺栓塞应给予抗凝治疗', 'B': '给予对症支持', 'C': '观察随访', 'D': '口服止痛药', 'E': '卧床休息'},
           stem='肺栓塞首选治疗是')
    assert 'FAIL' in _sev(vo.check_r10_clue_repetition(q), 'R10')


# ── R11 收敛策略（NBME D19）──

def test_r11_convergence_warn():
    import scripts.validate.rules_structural as rs
    rs._JIEBA_AVAILABLE = False  # 确定性 n-gram 模式
    # 正确选项命中 9 个题干词；其他选项 0-1 个 → avg_other=0.5, max_other=1
    # 9 > 0.5×2 且 9 > 1×1.5 → 收敛策略触发
    q = _q({'A': '急性肺栓塞首选溶栓治疗', 'B': '困难病例', 'C': '呼吸支持', 'D': '卧床休息', 'E': '随访观察'},
           stem='急性肺栓塞患者突发呼吸困难，首选治疗是')
    assert 'WARN' in _sev(vo.check_r11_convergence(q), 'R11')


# ── R12 无意义后缀（HC-6 修复）──

def test_r12_meaningless_suffix_fail():
    q = _q({'A': '肺栓塞抗凝治疗（相关表现）', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r12_meaningless_suffix(q), 'R12')


# ── R13 长度上限（P2-S5：降级 + 条件从句豁免）──

def test_r13_single_option_over_20_warn_not_fail():
    """2026-11-02 降级：单纯超长从 FAIL 降为 WARN（不再阻断 gate）。"""
    q = _q({'A': '这是一个超过二十个字符的选项内容确实太长了', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    sev = _sev(vo.check_r13_length_ceiling(q), 'R13')
    assert 'WARN' in sev and 'FAIL' not in sev


def test_r13_conditional_clause_exempt():
    """含时间窗/适用人群限定的长选项：删短就改变医学含义 → 豁免为 INFO。"""
    q = _q({'A': '嵌顿3～4小时内、无腹膜刺激征者可行手法复位', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    issues = vo.check_r13_length_ceiling(q)
    hit = [i for i in issues if i['rule'] == 'R13' and i.get('exempted')]
    assert hit and hit[0]['severity'] == 'INFO'
    assert '豁免' in hit[0]['detail']


def test_r13_purpose_clause_exempt():
    q = _q({'A': '切开时注意深度，以免伤及气管后壁甚至食管造成严重并发症', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert any(i.get('exempted') for i in vo.check_r13_length_ceiling(q))


def test_r13_real_question_exempt_entirely():
    """真题原题：选项不得改写（HC-4b），长度规则整体豁免，且只出一条记录。"""
    q = _q({'A': '向后经乳突窦口通乳突窦及乳突小房故炎症可侵入深部', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    q['zhiyi_origin'] = {'source_id': 'CMExam-1', 'corpus': 'cmexam'}
    issues = vo.check_r13_length_ceiling(q)
    assert len(issues) == 1 and issues[0].get('origin_exempt') == '执业医师真题'
    assert issues[0]['severity'] == 'INFO'


def test_r13_original_question_not_exempted_by_origin():
    """原创题没有来源豁免，仍按长度判定（WARN）。"""
    q = _q({'A': '这是一个超过二十个字符的选项内容确实太长了', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    issues = vo.check_r13_length_ceiling(q)
    assert not any(i.get('origin_exempt') for i in issues)


def test_r13_avg_over_18_warn():
    q = _q({'A': '选项内容平均长度超过十八个字触发整体偏长告警', 'B': '另一个同样长度的选项内容也超过十八个字', 'C': '第三选项的内容长度也超过十八个字的阈值', 'D': '第四选项内容同样超过十八个字的阈值长度', 'E': '第五选项内容依旧超过十八个字的阈值长度'})
    assert 'WARN' in _sev(vo.check_r13_length_ceiling(q), 'R13')


def test_r13_x_type_skipped():
    q = _q({'A': '这是一个超过二十个字符的选项内容确实太长了', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'}, qtype='X')
    assert vo.check_r13_length_ceiling(q) == []


# ── 主引擎冒烟 ──

def test_validate_questions_smoke():
    questions = [_q({'A': '以上都是', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})]
    all_issues, summary = vo.validate_questions(questions, mode='full')
    assert summary['total_questions'] == 1
    assert summary['fail'] >= 1  # R1 命中的 FAIL 被计入


# ── S1 Schema 完整性 ──

def test_s1_missing_required_field():
    """测试缺少必填字段"""
    q = {'id': 'T-002', 'type': 'A1', 'options': {'A': '甲', 'B': '乙'}}
    issues = vo.check_s1_schema_completeness(q)
    assert any('question' in i['target'] for i in issues)


def test_s1_empty_options():
    """测试空选项"""
    q = {'id': 'T-003', 'type': 'A1', 'question': '测试题干', 'options': {}, 'answer': 'A'}
    issues = vo.check_s1_schema_completeness(q)
    assert any('options' in i['target'] for i in issues)


def test_s1_valid_question():
    """测试有效题目"""
    q = _q({'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'})
    issues = vo.check_s1_schema_completeness(q)
    assert issues == []


# ── S2 空值检测 ──

def test_s2_empty_stem():
    """测试空题干"""
    q = {'id': 'T-004', 'type': 'A1', 'question': '', 'options': {'A': '甲'}, 'answer': 'A'}
    issues = vo.check_s2_null_values(q)
    assert any('question' in i['target'] for i in issues)


def test_s2_empty_answer():
    """测试空答案"""
    q = {'id': 'T-005', 'type': 'A1', 'question': '测试题干', 'options': {'A': '甲'}, 'answer': ''}
    issues = vo.check_s2_null_values(q)
    assert any('answer' in i['target'] for i in issues)


# ── S4 绝对化用语 ──

def test_s4_absolute_language_in_stem():
    """测试题干中的绝对化用语"""
    q = _q({'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
           stem='以下哪项是绝对正确的？')
    issues = vo.check_s4_absolute_language(q)
    assert any('stem' in i['target'] for i in issues)


def test_s4_absolute_language_in_option():
    """测试选项中的绝对化用语"""
    q = _q({'A': '100%有效', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'})
    issues = vo.check_s4_absolute_language(q)
    assert any('option' in i['target'] for i in issues)


# ── X型题特殊规则 ──

def test_x_type_skip_r7():
    """测试X型题跳过R7截断检测"""
    q = _q({'A': '短', 'B': '中', 'C': '长', 'D': '更长'}, qtype='X')
    issues = vo.check_r7_truncation(q)
    assert issues == []


def test_x_type_skip_r8():
    """测试X型题跳过R8最小长度检测"""
    q = _q({'A': '短', 'B': '中', 'C': '长', 'D': '更长'}, qtype='X')
    issues = vo.check_r8_min_length(q)
    assert issues == []


# ── B1型题特殊规则 ──

def test_b1_shared_options():
    """测试B1型题共用选项"""
    q = {
        'id': 'T-006',
        'type': 'B1',
        'question': '第一个子题',
        'options': {'A': '共用选项A', 'B': '共用选项B', 'C': '共用选项C', 'D': '共用选项D', 'E': '共用选项E'},
        'answer': 'A',
        'b1_group': '13-14',
    }
    issues = vo.check_r5_option_count(q)
    assert issues == []  # B1型题应该有5个选项


# ═══════════════════════════════════════════════════════════
# P2-S3 批次级规则 X1/X2/X6 + S-STRUCT（2026-11-02）
# 说明：X 系列只在整批分布上判定，因此用例必须构造足够题量才具备统计意义。
# ═══════════════════════════════════════════════════════════

from scripts.validate import rules_batch as rb  # noqa: E402

_TH = dict(rb.DEFAULT_THRESHOLDS)


def _mk(qid, answer='A', opts=None, mc_id=None, mechanism=None, truth=True, **extra):
    """构造最小可判定题：opts 为 {label: text}，mc_id 只给 truth=False 的选项。"""
    opts = opts or {'A': '甲甲甲', 'B': '乙乙', 'C': '丙丙', 'D': '丁丁', 'E': '戊戊'}
    per_option = []
    for lab, txt in opts.items():
        po = {'label': lab, 'truth': (lab == answer), 'why': 'x' * 20}
        if lab != answer:
            po['misconception_id'] = (mc_id or f'{qid}-{lab}')
            po['misconception'] = f'{qid} 的错误认知 {lab}'
            po['distractor_mechanism'] = mechanism or 'similar_presentation'
        per_option.append(po)
    q = {'id': qid, 'type': 'A1', 'stem': '题干', 'options': opts,
         'answer': answer, 'learning_value': {'per_option': per_option}}
    q.update(extra)
    return q


def _balanced(n=25):
    """答案字母均匀分布、正确项不是最长、错误认知复用充分、答案位置无周期。

    答案字母用固定种子的乱序，而不是 `i % 5`：机械轮转虽然总量均匀，
    但位置可预测，会被 X10 判 VIOLATED（这正是 batch049 的缺陷）。
    """
    import random
    rnd = random.Random(20261125)
    seq = list('ABCDE') * n
    rnd.shuffle(seq)
    out = []
    for i in range(n * 5):
        lab = seq[i]
        # 正确项 8 字、干扰项 9 字 → 正确项永不唯一最长（X2 不误报）
        opts = {k: ('正确答案内容文字' if k == lab else '干扰项内容文字长度') for k in 'ABCDE'}
        out.append(_mk(f'BAL-{i:03d}', lab, opts, mc_id=f'MC-{i % 3}'))
    return out


# ── X1 答案字母分布 ──

def test_x1_balanced_passes():
    r = rb.check_answer_distribution(_balanced(20), _TH)
    assert r['status'] == 'PASS', r['violations']
    assert r['denominator'] == 100


def test_x1_skewed_letter_violates():
    items = [_mk(f'Q{i}') for i in range(20)]  # 全部答案 A
    r = rb.check_answer_distribution(items, _TH)
    assert r['status'] == 'VIOLATED'
    assert any(v['letter'] == 'A' and v['why'] == '偏高' for v in r['violations'])
    assert any(v['letter'] == 'D' and v['why'] == '偏低' for v in r['violations'])


def test_x1_multiselect_excluded_from_denominator():
    items = [_mk(f'Q{i}') for i in range(10)]
    items += [{'id': f'X{i}', 'type': 'X', 'stem': 'q',
               'options': {k: 'v' for k in 'ABCDE'}, 'answer': 'ABC'} for i in range(5)]
    r = rb.check_answer_distribution(items, _TH)
    assert r['denominator'] == 10, '多选不得计入单选分母'
    assert r['excluded_multi'] == 5


# ── X2 唯一最长 ──

def test_x2_all_correct_longest_violates():
    items = [_mk(f'Q{i}', 'A', {'A': '这是一个明显长于其他选项的正确选项内容', 'B': '短', 'C': '短', 'D': '短', 'E': '短'})
             for i in range(10)]
    r = rb.check_unique_longest(items, _TH)
    assert r['status'] == 'VIOLATED' and r['value'] == 1.0


def test_x2_correct_not_longest_passes():
    items = [_mk(f'Q{i}', 'A', {'A': '短', 'B': '这是一个很长的干扰项内容用于凑长度', 'C': '短', 'D': '短', 'E': '短'})
             for i in range(10)]
    r = rb.check_unique_longest(items, _TH)
    assert r['status'] == 'PASS' and r['value'] == 0.0


def test_x2_tie_is_not_unique_longest():
    """两个选项并列最长时，正确项不算「唯一最长」——猜答案的收益没有变高。"""
    items = [_mk(f'Q{i}', 'A', {'A': '一样长的内容啊', 'B': '一样长的内容啊', 'C': '短', 'D': '短', 'E': '短'})
             for i in range(5)]
    r = rb.check_unique_longest(items, _TH)
    assert r['value'] == 0.0


# ── X6 错误认知复用 ──

def test_x6_all_private_ids_violates():
    """每题 4 个全新 misconception_id → 复用率 0，标签退化为题内私有。"""
    items = [_mk(f'Q{i:03d}') for i in range(30)]
    r = rb.check_misconception_reuse(items, _TH)
    assert r['status'] == 'VIOLATED'
    assert r['distinct_ids'] == r['distractor_occurrences'] == 120
    assert r['reused_occurrences'] == 0


def test_x6_reuse_passes_threshold():
    items = [_mk(f'Q{i:03d}', mc_id=f'MC-{i % 2}') for i in range(30)]
    r = rb.check_misconception_reuse(items, _TH)
    assert r['status'] == 'PASS'
    assert r['value'] == 1.0 and r['reused_ids'] == 2


def test_x6_counts_missing_ids():
    items = [_mk(f'Q{i:03d}', mc_id=f'MC-{i % 2}') for i in range(4)]
    for po in items[0]['learning_value']['per_option']:
        if not po['truth']:
            po['misconception_id'] = None
    r = rb.check_misconception_reuse(items, _TH)
    assert r['missing_id_count'] == 4


# ── S-STRUCT 结构字段覆盖 ──

def test_struct_skips_legacy_batch():
    r = rb.check_structural_coverage([_mk('Q1'), _mk('Q2')])
    assert r['status'] == 'SKIP' and r['applicable'] is False
    assert '不追溯' in r['note']


def test_struct_v22_complete_passes():
    full = dict(difficulty_tier='L3', step_count=2, competing_dx=['急性心衰'],
                negative_cues=[], conditionals=['若合并肾功能不全'], schema_version='2.2')
    r = rb.check_structural_coverage([_mk('Q1', **full), _mk('Q2', **full)])
    assert r['status'] == 'PASS', r
    assert r['mechanism_coverage'] == 1.0


def test_struct_v22_missing_fields_violates():
    partial = dict(difficulty_tier='L3', schema_version='2.2')  # 缺 step_count 等
    r = rb.check_structural_coverage([_mk('Q1', **partial)])
    assert r['status'] == 'VIOLATED'
    assert 'step_count' in r['missing']
    assert 'difficulty_tier' not in r['missing']


def test_struct_v22_missing_mechanism_violates():
    full = dict(difficulty_tier='L2', step_count=1, competing_dx=['A'],
                negative_cues=[], conditionals=[], schema_version='2.2')
    q = _mk('Q1', **full)
    for po in q['learning_value']['per_option']:
        if not po['truth']:
            po['distractor_mechanism'] = None
    r = rb.check_structural_coverage([q])
    assert r['status'] == 'VIOLATED'
    assert r['mechanism_coverage'] == 0.0


# ── 汇总模式 ──

def test_audit_advisory_does_not_fail_exit():
    rep = rb.audit_batch([_mk(f'Q{i}') for i in range(10)], enforce=False)
    assert rep['status'] == 'ADVISORY' and rep['violated_rules']


def test_audit_enforce_turns_violation_into_fail():
    rep = rb.audit_batch([_mk(f'Q{i}') for i in range(10)], enforce=True)
    assert rep['status'] == 'FAIL'


def test_audit_clean_batch_passes():
    rep = rb.audit_batch(_balanced(20), enforce=True)
    assert rep['status'] == 'PASS', rep['violated_rules']


def test_options_normalizer_handles_all_legacy_shapes():
    shapes = [
        {'A': '甲', 'B': '乙'},
        [{'label': 'A', 'text': '甲'}, {'label': 'B', 'text': '乙'}],
        ['A. 甲', 'B．乙'],
        ['A、甲', 'B) 乙'],
    ]
    for s in shapes:
        got = rb.options({'options': s})
        assert got.get('A') == '甲' and got.get('B') == '乙', f'{s} → {got}'


# ═══════════════════════════════════════════════════════════
# P2-S4 反选题封顶 ≤15% + 为真干扰项逐项锚点（AC-P2-05）
# ═══════════════════════════════════════════════════════════

def test_reverse_detects_markdown_bold():
    """`**错误的**是` —— 星号插在词中间，不先去强调符就漏检。"""
    assert rb.stem_reverse({'stem': '下列关于耳镜的描述，**错误的**是？'})


def test_reverse_detects_html_bold():
    """`<b>不属于</b>` —— batch037 的 29 道反选题当年因这个写法全部漏检。"""
    assert rb.stem_reverse({'stem': '下列<b>不属于</b>牙周组织的是？'})
    assert rb.stem_reverse({'stem': '关于面神经五支的叙述，<b><b>错误</b>的是</b>？'})


def test_reverse_detects_question_position():
    assert rb.stem_reverse({'stem': '下列哪项检查结果最不可能出现？'})
    assert rb.stem_reverse({'stem': '胃黏膜屏障的组成中，不包括下列哪项？'})
    assert rb.stem_reverse({'stem': '下列哪一个不是有机磷中毒的M样表现？'})


def test_reverse_ignores_attributive_negation():
    """否定词作定语不是反选 —— 这两类曾凭空造出 26 道「反选题」。"""
    assert not rb.stem_reverse({'stem': '不宜手术的原发性肝癌患者，最常用的局部治疗是？'})
    assert not rb.stem_reverse({'stem': '使用二甲双胍的禁忌证是？'})


def test_polarity_field_wins_over_stem():
    """显式 polarity 优先：题干没典型否定词但标了 negative，仍算反选。"""
    q = {'stem': '该患儿不宜选用的检查是？', 'polarity': 'negative'}
    assert rb.is_reverse(q) == (True, 'polarity')


def test_x5_uses_union_not_polarity_only():
    """batch042 现象：题干是反选(polarity 没标)。
    只信 polarity 会算成 0%，等于把「标注没写」读成「题没问题」。"""
    items = [{'id': f'Q{i}', 'stem': '下列哪项不正确', 'polarity': 'positive',
              'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
              'answer': 'A'} for i in range(10)]
    r = rb.check_reverse_selection(items, _TH)
    assert r['numerator'] == 10
    assert r['by_signal']['polarity'] == 0.0
    assert r['by_signal']['stem'] == 1.0
    assert r['status'] == 'VIOLATED'


def test_x5_passes_below_threshold():
    items = [{'id': f'Q{i}', 'stem': '下列哪项最恰当', 'polarity': 'positive',
              'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
              'answer': 'A'} for i in range(20)]
    items.append({'id': 'R1', 'stem': '下列哪项不正确', 'polarity': 'negative',
                  'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
                  'answer': 'A'})
    r = rb.check_reverse_selection(items, _TH)
    assert r['status'] == 'PASS'
    assert r['numerator'] == 1 and r['denominator'] == 21


def test_x5_threshold_is_configurable():
    # 1 反选 / 10 题 = 10%：15% 上限下通过，5% 上限下超标
    items = [{'id': 'R1', 'stem': '下列哪项不正确', 'polarity': 'negative',
              'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
              'answer': 'A'}] + \
            [{'id': f'N{i}', 'stem': '下列哪项最恰当', 'polarity': 'positive',
              'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
              'answer': 'A'} for i in range(9)]
    r15 = rb.check_reverse_selection(items, dict(_TH, x5_reverse_max=0.15))
    r05 = rb.check_reverse_selection(items, dict(_TH, x5_reverse_max=0.05))
    assert r15['value'] == 0.1
    assert r15['status'] == 'PASS'
    assert r05['status'] == 'VIOLATED'


def test_distractor_labels_is_answer_complement_not_truth():
    """反选题里 truth=False 的是**答案本身**，干扰项是那 4 个为真说法。

    用 truth 判干扰项会把反选题的机制标签/错误认知要求到完全错误的位置。
    """
    q = {'stem': '下列哪项不正确', 'polarity': 'negative',
         'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'}, 'answer': 'C'}
    assert rb.distractor_labels(q) == {'A', 'B', 'D', 'E'}


def _rev_v22(**over):
    q = {
        'question_id': 'RV-M1-A1-001', 'type': 'A1', 'schema_version': '2.2',
        'stem': '下列关于耳镜的描述，错误的是', 'answer': 'C', 'polarity': 'negative',
        'difficulty_tier': 'L2', 'step_count': 1, 'competing_dx': ['外耳道炎'],
        'negative_cues': ['错误'], 'conditionals': [],
        'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
        'learning_value': {
            'answer_evidence': '',
            'per_option': [
                {'label': 'A', 'truth': True, 'why': 'y' * 20, 'source_anchor': '教材P12'},
                {'label': 'B', 'truth': True, 'why': 'y' * 20, 'source_anchor': '教材P12'},
                {'label': 'C', 'truth': False, 'why': 'y' * 20, 'misconception_id': 'MC-1',
                 'misconception': '误认为鼓膜正常', 'distractor_mechanism': 'direction_error'},
                {'label': 'D', 'truth': True, 'why': 'y' * 20, 'source_anchor': '教材P13'},
                {'label': 'E', 'truth': True, 'why': 'y' * 20, 'source_anchor': '教材P13'},
            ],
        },
    }
    q.update(over)
    return q


def test_x5a_passes_when_all_true_distractors_anchored():
    r = rb.check_reverse_option_anchors([_rev_v22()])
    assert r['status'] == 'PASS', r
    assert r['reverse_items'] == 1 and r['target_options'] == 4


def test_x5a_violates_on_missing_anchor():
    q = _rev_v22()
    q['learning_value']['per_option'][0]['source_anchor'] = ''
    r = rb.check_reverse_option_anchors([q])
    assert r['status'] == 'VIOLATED'
    assert r['coverage'] == 0.75
    assert 'RV-M1-A1-001:A' in r['missing']


def test_x5a_skips_historical_batch():
    q = _rev_v22()
    q['schema_version'] = '2.0'
    r = rb.check_reverse_option_anchors([q])
    assert r['status'] == 'SKIP' and r['applicable'] is False
    assert '不追溯' in r['note']


def test_struct_rule_uses_answer_complement_for_mechanism():
    """反选题的机制标签必须要求在那 4 个为真项上，不是答案项上。"""
    q = _rev_v22()
    for po in q['learning_value']['per_option']:
        if po['label'] in 'ABDE':
            po['distractor_mechanism'] = 'similar_presentation'
    r = rb.check_structural_coverage([q])
    assert r['mechanism_coverage'] == 1.0, r['mechanism_missing']
    assert r['status'] == 'PASS', r


def test_x5p_reports_polarity_mismatch():
    items = [
        {'id': 'A1', 'stem': '下列哪项不正确', 'polarity': 'positive', 'answer': 'A',
         'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'}},
        {'id': 'A2', 'stem': '下列哪项最恰当', 'polarity': 'positive', 'answer': 'A',
         'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'}},
    ]
    r = rb.check_polarity_consistency(items)
    assert r['mismatch'] == 1 and r['agree'] == 1
    assert r['sample'][0]['qid'] == 'A1'
    assert r['sample'][0]['stem_says'] == 'negative'


# ── 2026-11-03：WARN 不再导致非零退出码 ──────────────────

def test_warn_only_does_not_fail_exit_code():
    from scripts.validate.__main__ import exit_code

    assert exit_code({'fail': 0, 'warn': 3}) == 0
    assert exit_code({'fail': 0, 'warn': 3}, strict_warn=True) == 1
    assert exit_code({'fail': 1, 'warn': 0}) == 1
    assert exit_code(None) == 0


# ── 2026-11-25：X7 多选答案分布 / X8 难度-题型解耦 / X9 选项尾部模板 ──
#
# 三条规则的共同背景：batch049 的 250 题里，多选 18 题有 16 题答案是 ABCD、
# E 一次没当过答案；89 道 A2 有 88 道被标 L3/L4（难度成了题型的代理变量）；
# 133 题的选项被贴上同一句「等临床情况需鉴别」——为了压 X2「唯一最长」。

def _xq(i, ans, texts=None):
    texts = texts or {k: f'{k}项陈述内容{chr(65+i%26)}' for k in 'ABCDE'}
    return {'id': f'X{i:03d}', 'type': 'X', 'stem': f'多选题{i}',
            'options': {k: texts[k] for k in 'ABCDE'}, 'answer': ans,
            'difficulty_tier': 'L3', 'schema_version': '2.2'}


def test_x7_prefix_cluster_violates():
    """18 题全 ABCD / ABC：正确项永远是开头几位 → 盲选「ABCD」就能过。"""
    items = [_xq(i, 'ABCD') for i in range(16)] + [_xq(i, 'ABC') for i in range(16, 18)]
    r = rb.check_multi_answer_distribution(items, _TH)
    assert r['status'] == 'VIOLATED'
    assert r['prefix_cluster_share'] == 1.0
    assert any(v.get('letter') == 'E' for v in r['violations']), 'E 从不作答案必须点名'


def test_x7_balanced_passes():
    """正确项个数 2/3/4 混合、五个字母都被用到、组合各不相同。"""
    ans = ['AB', 'CD', 'AE', 'BD',
           'ACE', 'BDE', 'ACD', 'BCE', 'ABD', 'CDE', 'ABE', 'BCD',
           'ABCD', 'ABCE', 'ABDE', 'ACDE']
    r = rb.check_multi_answer_distribution([_xq(i, a) for i, a in enumerate(ans)], _TH)
    assert r['status'] == 'PASS', r['violations']


def test_x7_skips_small_sample():
    r = rb.check_multi_answer_distribution([_xq(i, 'ABCD') for i in range(3)], _TH)
    assert r['status'] == 'SKIP' and r['applicable'] is False


def _dq(i, qtype, tier, answer='A'):
    return {'id': f'D{i:04d}', 'type': qtype, 'stem': '题干', 'answer': answer,
            'options': {k: f'{k}选项内容{i}' for k in 'ABCDE'}, 'difficulty_tier': tier}


def test_x8_difficulty_collinear_with_type_violates():
    """A2 全难、A1 全易：难度不携带任何信息，看到题型就知道难度。"""
    items = ([_dq(i, 'A1', 'L1') for i in range(15)] + [_dq(i, 'A1', 'L2') for i in range(15)]
             + [_dq(i, 'A2', 'L3') for i in range(15)] + [_dq(i, 'A2', 'L4') for i in range(15)])
    r = rb.check_difficulty_type_decoupling(items, _TH)
    assert r['status'] == 'VIOLATED'
    assert any(v['metric'] == 'tier_min_share' and v['type'] == 'A2' and v['side'] == 'easy'
               for v in r['violations']), 'A2 没有简单题必须点名'


def test_x8_decoupled_passes():
    """每种题型都横跨四档（题量按全局目标配比），TVD 低即「难度独立于题型」。"""
    tiers = ['L1', 'L1', 'L2', 'L2', 'L2', 'L3', 'L3', 'L3', 'L3', 'L4', 'L4', 'L3']
    items = []
    for t in ('A1', 'A2'):
        for j, tier in enumerate(tiers * 2):
            items.append(_dq(len(items), t, tier))
    r = rb.check_difficulty_type_decoupling(items, _TH)
    assert r['status'] == 'PASS', r['violations']


def test_x8_skips_without_labels():
    items = [{'id': f'N{i}', 'type': 'A1', 'stem': 'q', 'answer': 'A',
              'options': {k: 'x' for k in 'ABCDE'}} for i in range(30)]
    r = rb.check_difficulty_type_decoupling(items, _TH)
    assert r['status'] == 'SKIP'


def test_x9_enum_tail_padding_violates():
    """为压 X2 给干扰项尾巴贴同一句套话：133/250 题的真实缺陷。"""
    items = []
    for i in range(30):
        opts = {k: f'{k}选项主体内容{i}' for k in 'ABCDE'}
        for k in 'ABCD':
            opts[k] = opts[k] + '等临床情况需鉴别'
        items.append({'id': f'P{i}', 'type': 'A1', 'stem': 'q', 'answer': 'A',
                      'options': opts, 'difficulty_tier': 'L2'})
    r = rb.check_option_template_pollution(items, _TH)
    assert r['status'] == 'VIOLATED'
    assert r['top_templates'][0]['template'] == '等:等临床情况需鉴别'
    assert r['correct_option_hits'] == 30, '正确项被污染必须单独计数'


def test_x9_disease_name_tail_is_not_template():
    """真实病名在几百题里必然重复尾巴，不能当套话误判。"""
    names = ['急性前葡萄膜炎', '慢性前葡萄膜炎', '肉芽肿性前葡萄膜炎']
    items = []
    for i in range(40):
        opts = {k: f'{k}项' + names[i % 3] for k in 'ABCDE'}
        items.append({'id': f'P{i}', 'type': 'A1', 'stem': 'q', 'answer': 'A',
                      'options': opts, 'difficulty_tier': 'L2'})
    r = rb.check_option_template_pollution(items, _TH)
    assert r['status'] == 'PASS', r['top_templates']


def test_x9_short_options_have_no_fingerprint():
    """「3个月」「正确」这类短选项不能塌成一个空指纹。"""
    items = [{'id': f'S{i}', 'type': 'A1', 'stem': 'q', 'answer': 'A',
              'options': {'A': '3个月', 'B': '6个月', 'C': '1年', 'D': '2年', 'E': '正确'}}
             for i in range(40)]
    r = rb.check_option_template_pollution(items, _TH)
    assert r['status'] == 'PASS'


def test_x1_binary_items_excluded_from_denominator():
    """判断题的 A/B 不是五选一偏倚，不能进单选分母。"""
    items = [{'id': f'T{i}', 'type': '判断', 'stem': 'q', 'answer': 'A',
              'options': {'A': '正确', 'B': '错误'}} for i in range(20)]
    items += [_mk(f'Q{i}', 'ABCDE'[i % 5]) for i in range(10)]
    r = rb.check_answer_distribution(items, _TH)
    assert r['denominator'] == 10
    assert r['excluded_binary'] == 20


def test_options_normalizer_labels_plain_string_list():
    """batch044 押题卷的形态：选项是无标号纯文本，按位置补 A–E。"""
    q = {'options': ['甲项内容', '乙项内容', '丙项内容', '丁项内容', '戊项内容'], 'answer': 'ABE'}
    assert rb.options(q)['C'] == '丙项内容'


def test_x10_letter_cycle_violates():
    """单选答案按 ABCDE 轮转：总量完美均匀，但位置完全可预测。"""
    qs = [{'id': f'C{i}', 'type': 'A1', 'stem': 'q', 'answer': 'ABCDE'[i % 5],
           'options': {k: f'{k}{i}' for k in 'ABCDE'}} for i in range(40)]
    r = rb.check_answer_position_periodicity(qs, _TH)
    assert r['status'] == 'VIOLATED'
    assert r['letter_cycle_fit'] == 1.0


def test_x10_binary_alternation_violates():
    """判断题 ABAB 交替：第 1、3、5 题永远是「正确」。"""
    qs = [{'id': f'T{i}', 'type': '判断', 'stem': 'q', 'answer': 'AB'[i % 2],
           'options': {'A': '正确', 'B': '错误'}} for i in range(30)]
    r = rb.check_answer_position_periodicity(qs, _TH)
    assert r['status'] == 'VIOLATED'
    assert r['binary_alternation_fit'] == 1.0


def test_x10_random_sequence_passes():
    import random
    rnd = random.Random(7)
    qs = [{'id': f'R{i}', 'type': 'A1', 'stem': 'q', 'answer': rnd.choice('ABCDE'),
           'options': {k: f'{k}{i}' for k in 'ABCDE'}} for i in range(120)]
    r = rb.check_answer_position_periodicity(qs, _TH)
    assert r['status'] == 'PASS', r['violations']


# ── 2026-11-25：新批次阻断（x_enforce_since）──

def _bad_multi_batch(n=16):
    """复刻 batch049 形态：多选答案恒 ABCD、选项贴同一句套话、单选字母轮转。"""
    items = []
    for i in range(n):
        opts = {k: f'{k}选项主体内容{i}' for k in 'ABCDE'}
        for k in 'ABCD':
            opts[k] = opts[k] + '等临床情况需鉴别'
        items.append({'id': f'X{i}', 'type': 'X', 'stem': 'q', 'answer': 'ABCD',
                      'options': opts, 'difficulty_tier': 'L3'})
    for i in range(30):
        items.append({'id': f'S{i}', 'type': 'A1', 'stem': 'q', 'answer': 'ABCDE'[i % 5],
                      'options': {k: f'{k}内容{i}' for k in 'ABCDE'}, 'difficulty_tier': 'L1'})
    return items


def test_blocking_rules_only_from_enforce_since():
    """同一份坏数据：batch049 只记录，batch051 起必须 FAIL。"""
    items = _bad_multi_batch()
    old = rb.audit_batch(items, batch='batch049')
    new = rb.audit_batch(items, batch='batch051')
    assert old['status'] == 'ADVISORY', old['violated_rules']
    assert old['blocking_rules'] == []
    assert new['status'] == 'FAIL'
    assert set(new['blocking_rules']) >= {'X7', 'X9', 'X10'}


def test_batch_number_parsing():
    assert rb.batch_number('batch051') == 51
    assert rb.batch_number('最终产物/batch052/x.json') == 52
    assert rb.batch_number('') is None


def test_x8_global_deviation_alone_does_not_block():
    """X8 的全局配比偏差属于理想值，不该卡住交付；只有 TVD/两侧占比阻断。"""
    check = {'rule': 'X8', 'status': 'VIOLATED',
             'violations': [{'metric': 'global_share', 'tier': 'L4'}]}
    assert rb._is_blocking(check, 'batch051', _TH) is False
    check2 = {'rule': 'X8', 'status': 'VIOLATED',
              'violations': [{'metric': 'type_tvd', 'type': 'A2'}]}
    assert rb._is_blocking(check2, 'batch051', _TH) is True


def test_enforce_flag_still_forces_fail_on_old_batch():
    rep = rb.audit_batch(_bad_multi_batch(), enforce=True, batch='batch049')
    assert rep['status'] == 'FAIL'


# ── 2026-11-25：X11 解析标号同步 / X12 难度自述自洽 ──

def _expl_q(i, ans='A', expl=None):
    opts = {k: f'{k}项内容{i}' for k in 'ABCDE'}
    expl = expl if expl is not None else (
        '解析正文。\n' + '\n'.join(f'{k}：该选项说明{i}' for k in 'ABCDE'))
    return {'id': f'E{i:03d}', 'question_id': f'E{i:03d}', 'type': 'A1', 'stem': 'q',
            'answer': ans, 'options': opts, 'explanation': expl,
            'difficulty_tier': 'L2', 'step_count': 1}


def test_x11_synced_passes():
    r = rb.check_explanation_labels([_expl_q(i) for i in range(20)], _TH)
    assert r['status'] == 'PASS', r['violations']


def test_x11_unordered_labels_violates():
    """重排了选项、解析行没跟着重排：标号序列变成 CABDE（结构层）。"""
    qs = [_expl_q(i) for i in range(20)]
    qs[0]['explanation'] = '解析正文。\nC：内容C\nA：内容A\nB：内容B\nD：内容D\nE：内容E'
    r = rb.check_explanation_labels(qs, _TH)
    assert r['status'] == 'VIOLATED'
    assert r['sample'][0]['qid'] == 'E000'
    assert r['sample'][0]['found'] == 'CABDE'


def test_x11_duplicate_label_violates():
    qs = [_expl_q(i) for i in range(20)]
    qs[1]['explanation'] = '解析正文。\nA：甲\nA：乙\nB：丙\nD：丁\nE：戊'
    r = rb.check_explanation_labels(qs, _TH)
    assert r['status'] == 'VIOLATED' and r['sample'][0]['qid'] == 'E001'


def test_x11_stale_per_option_violates_content_layer():
    """标号序列没问题，但解析正文与 per_option 绑定的选项对不上（内容层）。

    典型形态：只改了 explanation 的标号、漏改 learning_value.per_option。
    结构检查全过，只有把正文与 why 逐项比对才发现错位。
    """
    q = _expl_q(0)
    q['learning_value'] = {'per_option': [
        {'label': 'A', 'why': 'A 项的说明文字，讲的是甲内容'},
        {'label': 'B', 'why': 'B 项的说明文字，讲的是乙内容'},
        {'label': 'C', 'why': 'C 项的说明文字，讲的是丙内容'},
        {'label': 'D', 'why': 'D 项的说明文字，讲的是丁内容'},
        {'label': 'E', 'why': 'E 项的说明文字，讲的是戊内容'},
    ]}
    q['explanation'] = ('解析正文。\nA：C 项的说明文字，讲的是丙内容\n'
                        'B：B 项的说明文字，讲的是乙内容\nC：A 项的说明文字，讲的是甲内容\n'
                        'D：D 项的说明文字，讲的是丁内容\nE：E 项的说明文字，讲的是戊内容')
    qs = [q] + [_expl_q(i) for i in range(1, 20)]
    r = rb.check_explanation_labels(qs, _TH)
    assert r['status'] == 'VIOLATED'
    assert any(v.get('label') == 'A' for v in r['violations']), r['violations']



def test_x11_skips_when_no_per_option_lines():
    qs = [_expl_q(i, expl='只有一段解析，没有逐选项行。') for i in range(20)]
    r = rb.check_explanation_labels(qs, _TH)
    assert r['status'] == 'SKIP' and r['applicable'] is False


def test_x12_l1_with_three_steps_violates():
    qs = [_expl_q(i) for i in range(20)]
    qs[0]['difficulty_tier'] = 'L1'
    qs[0]['step_count'] = 3
    r = rb.check_difficulty_consistency(qs, _TH)
    assert r['status'] == 'VIOLATED' and r['contradictions'] == 1


def test_x12_l4_without_steps_or_cross_violates():
    qs = [_expl_q(i) for i in range(20)]
    qs[1]['difficulty_tier'] = 'L4'
    qs[1]['step_count'] = 2
    r = rb.check_difficulty_consistency(qs, _TH)
    assert r['status'] == 'VIOLATED'


def test_x12_l4_with_cross_concepts_passes():
    """L4 = 2 步但两个考点交叉：合法，不判矛盾。"""
    qs = [_expl_q(i) for i in range(20)]
    qs[1]['difficulty_tier'] = 'L4'
    qs[1]['step_count'] = 2
    qs[1]['concepts'] = [{'role': 'primary'}, {'role': 'differential'}]
    r = rb.check_difficulty_consistency(qs, _TH)
    assert r['status'] == 'PASS', r['violations']


def test_x9_boilerplate_phrase_tail_violates_single_item():
    """「…需鉴别」「…需结合临床」收尾：单条即判，不要求跨题复用。

    这类尾短语是解析语气，不是选项内容——学生看到的选项变成「请结合临床判断」，
    题目就不成立了。batch049 的 298 个选项就是这个形态。
    """
    qs = []
    for i in range(12):
        opts = {k: f'{k}选项内容{i}' for k in 'ABCDE'}
        if i == 0:
            opts['C'] = '过敏性结膜炎等临床情况需鉴别'
        if i == 1:
            opts['E'] = '需结合临床鉴别'
        qs.append({'id': f'B{i}', 'type': 'A1', 'stem': 'q', 'answer': 'A',
                   'options': opts, 'difficulty_tier': 'L2'})
    r = rb.check_option_template_pollution(qs, _TH)
    assert r['status'] == 'VIOLATED'
    assert r['boilerplate_tail_items'] == 2
    phrases = {p['phrase'] for p in r['boilerplate_tail_sample']}
    assert phrases & {'临床情况需鉴别', '结合临床鉴别'}, phrases


def test_x9_specific_differential_is_not_boilerplate():
    """「需与急性闭角型青光眼鉴别」带具体病名，是有效内容，不得误判。"""
    qs = []
    for i in range(12):
        opts = {k: f'{k}选项内容{i}' for k in 'ABCDE'}
        if i == 0:
            opts['B'] = '需与急性闭角型青光眼鉴别'
        qs.append({'id': f'C{i}', 'type': 'A1', 'stem': 'q', 'answer': 'A',
                   'options': opts, 'difficulty_tier': 'L2'})
    r = rb.check_option_template_pollution(qs, _TH)
    assert r['status'] == 'PASS', r['boilerplate_tail_sample']
