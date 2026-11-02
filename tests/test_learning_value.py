# -*- coding: utf-8 -*-
"""HC-24 学习价值层校验器回归测试。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

from check_learning_value import check_item, _normalize_options  # noqa: E402
from workflow_state import new_batch  # noqa: E402
import gate_check  # noqa: E402


def test_new_batch_defaults_to_schema_v2():
    b = new_batch('batch999-test')
    assert b['item_schema_version'] == '2.0'


def test_old_batch_gate_skips():
    r = gate_check.gate_item_learning_value('batch-legacy-test', {})
    assert r['status'] == 'PASS'
    assert r.get('skipped') is True


def test_v2_batch_without_final_json_blocks():
    r = gate_check.gate_item_learning_value(
        '_no_such_v2_batch',
        {'item_schema_version': '2.0', 'steps': {'AGENT2': {'status': 'COMPLETED'}}},
    )
    assert r['status'] == 'BLOCKED'


def test_v2_non_qbank_batch_skips():
    r = gate_check.gate_item_learning_value('_review_only_batch', {'item_schema_version': '2.0'})
    assert r['status'] == 'PASS'
    assert r.get('skipped') is True


def _valid_positive():
    return {
        'id': 'TEST-A1-001',
        'type': 'A1',
        'polarity': 'positive',
        'stem': '心衰诊断金标准是什么',
        'teacher_anchor': '心衰诊断金标准是利钠肽升高并存在结构性心脏病证据，心衰诊断金标准需要结合症状体征与利钠肽。',
        'options': [
            {'label': 'A', 'text': '错误选项甲', 'is_correct': False},
            {'label': 'B', 'text': '正确选项乙', 'is_correct': True},
            {'label': 'C', 'text': '错误选项丙', 'is_correct': False},
        ],
        'answer': 'B',
        'learning_value': {
            'correct_rationale': '心衰诊断金标准需要结合患者症状体征、利钠肽水平升高以及结构性心脏病客观证据，不能仅凭单一症状或单一影像指标作出诊断，必须综合判断。',
            'per_option': [
                {'label': 'A', 'truth': False, 'why': '该选项只描述单一症状，不能作为心衰诊断金标准，缺少利钠肽与结构证据。', 'misconception_id': 'MC-T-01', 'misconception': '把单一症状当成诊断金标准'},
                {'label': 'B', 'truth': True, 'why': '该选项完整覆盖症状体征、利钠肽升高与结构性心脏病证据，符合诊断组合要求。', 'misconception_id': None, 'misconception': None},
                {'label': 'C', 'truth': False, 'why': '该选项把影像表现孤立使用，证据不足，不能替代症状、利钠肽与结构证据的组合。', 'misconception_id': 'MC-T-02', 'misconception': '把影像表现孤立当成金标准'},
            ],
            'key_takeaway': '心衰诊断必须组合症状体征、利钠肽与结构证据，任何单一指标都不能作为金标准。',
            'source_quote': '心衰诊断金标准需要结合症状体征与利钠肽。',
            'source_quote_status': 'exact',
            'anchor_status': 'verified',
            'quality_flags': [],
            'review_status': 'draft',
        },
    }


def test_valid_positive_pass():
    r = check_item(_valid_positive())
    assert r['status'] == 'PASS', r


def test_negative_polarity_truth_inverted():
    q = _valid_positive()
    q['id'] = 'TEST-NEG-001'
    q['stem'] = '下列不属于心衰诊断金标准的是'
    q['polarity'] = 'negative'
    q['answer'] = 'C'
    q['options'] = [
        {'label': 'A', 'text': '利钠肽升高', 'is_correct': False},
        {'label': 'B', 'text': '结构性心脏病证据', 'is_correct': False},
        {'label': 'C', 'text': '单一症状即可确诊', 'is_correct': True},
    ]
    q['learning_value']['per_option'] = [
        {'label': 'A', 'truth': True, 'why': '利钠肽升高确实是心衰诊断组合的一部分，但本题问“不属于”，不能选它。', 'misconception_id': 'MC-T-03', 'misconception': '忽略“不属于”而选正确陈述'},
        {'label': 'B', 'truth': True, 'why': '结构证据确实是诊断组合的一部分，但本题问“不属于”，不能选它。', 'misconception_id': 'MC-T-03', 'misconception': '忽略“不属于”而选正确陈述'},
        {'label': 'C', 'truth': False, 'why': '单一症状不能确诊心衰，因此它才是“不属于”的选项，需结合利钠肽与结构证据。', 'misconception_id': None, 'misconception': None},
    ]
    q['teacher_anchor'] = '下列不属于心衰诊断金标准的是单一症状即可确诊。'
    q['learning_value']['source_quote'] = '单一症状即可确诊'
    r = check_item(q)
    # 本用例只验「truth 反转」：反选题里答案(错误说法) truth=False、干扰项(正确说法) truth=True。
    # 该题没写 source_anchor，历史口径下给 WARN 是预期行为（P2-S4 起锚点才成为 2.2+ 必填项）。
    assert r['negative'] is True
    assert r['status'] != 'FAIL', r['issues']
    assert r['mc_total'] == 0, '反选题不该被计入错误认知分母'
    assert r['reverse_anchor_total'] == 2
    assert not any('truth' in i['detail'] or '极性' in i['detail'] for i in r['issues'])


def test_missing_per_option_fails_r14():
    q = _valid_positive()
    q['learning_value']['per_option'] = q['learning_value']['per_option'][:2]
    r = check_item(q)
    assert r['status'] == 'FAIL'
    assert any(i['rule'] == 'R14' for i in r['issues'])


def test_exact_quote_empty_fails_r16():
    q = _valid_positive()
    q['learning_value']['source_quote'] = ''
    q['learning_value']['source_quote_status'] = 'exact'
    r = check_item(q)
    assert r['status'] == 'FAIL'
    assert any(i['rule'] == 'R16' for i in r['issues'])


def test_list_answer_supported():
    q = _valid_positive()
    q['answer'] = ['B']
    r = check_item(q)
    assert r['status'] == 'PASS', r


def test_dict_options_without_is_correct_are_normalized():
    q = _valid_positive()
    q['options'] = {'A': '错误选项甲', 'B': '正确选项乙', 'C': '错误选项丙'}
    r = check_item(q)
    assert r['status'] == 'PASS', r
    assert _normalize_options({'A': 'x', 'B': 'y'}, 'A')[0]['is_correct'] is True


# ── R20 / HC-29 干扰项机制标签（P2-S3 · AC-P2-04，2026-11-02）─────

def _v22_item(mech='similar_presentation', schema_version='2.2'):
    q = _valid_positive()
    q['schema_version'] = schema_version
    for p in q['learning_value']['per_option']:
        p['distractor_mechanism'] = mech if p['truth'] is False else None
    return q


def test_r20_v22_all_tagged_passes():
    r = check_item(_v22_item())
    assert r['status'] == 'PASS', r['issues']
    assert r['mechanism_required'] is True
    assert r['mechanism_covered'] == 2 and r['mechanism_missing'] == 0


def test_r20_v22_missing_tag_fails():
    q = _v22_item()
    for p in q['learning_value']['per_option']:
        if p['truth'] is False:
            p.pop('distractor_mechanism')
            break
    r = check_item(q)
    assert r['status'] == 'FAIL'
    assert any(i['rule'] == 'R20' and '缺 distractor_mechanism' in i['detail'] for i in r['issues'])


def test_r20_v22_illegal_tag_fails():
    r = check_item(_v22_item(mech='made_up_mechanism'))
    assert r['status'] == 'FAIL'
    assert any(i['rule'] == 'R20' and '非法' in i['detail'] for i in r['issues'])


def test_r20_legacy_batch_is_skip_not_fail():
    """历史批次（2.1/无版本）不追溯：不因缺标签 FAIL，也不逐题挂 WARN。"""
    q = _valid_positive()  # 无 schema_version，也没有机制标签
    r = check_item(q)
    assert r['status'] == 'PASS', r['issues']
    assert r['mechanism_required'] is False
    assert r['mechanism_covered'] == 0
    assert not any(i['rule'] == 'R20' for i in r['issues'])
    assert not any(w['rule'] == 'R20' for w in r['warnings'])


def test_r20_correct_option_tag_is_ignored():
    """正确项的 distractor_mechanism 不计入覆盖率（只对干扰项要求）。"""
    q = _v22_item()
    for p in q['learning_value']['per_option']:
        if p['truth'] is True:
            p['distractor_mechanism'] = 'bogus_value'
    r = check_item(q)
    assert r['status'] == 'PASS', r['issues']


def test_r20_batch_summary_reports_coverage():
    from check_learning_value import audit_batch

    _, s = audit_batch([_v22_item(), _v22_item()])
    assert s['distractor_mechanism_required'] is True
    assert s['distractor_mechanism_status'] == 'PASS'
    assert s['distractor_mechanism_coverage'] == 1.0
    assert s['distractor_mechanism_total'] == 4


def test_r20_batch_summary_skips_legacy():
    from check_learning_value import audit_batch

    _, s = audit_batch([_valid_positive()])
    assert s['distractor_mechanism_required'] is False
    assert s['distractor_mechanism_status'] == 'SKIP'


# ── P2-S4：反选题的为真干扰项要锚点（不是错误认知）────────────

def _reverse_item(schema_version=None, anchor='教材 P142'):
    q = _valid_positive()
    q['id'] = 'TEST-NEG-ANCHOR'
    q['stem'] = '下列不属于心衰诊断金标准的是'
    q['polarity'] = 'negative'
    q['answer'] = 'C'
    q['options'] = [
        {'label': 'A', 'text': '利钠肽升高', 'is_correct': False},
        {'label': 'B', 'text': '结构性心脏病证据', 'is_correct': False},
        {'label': 'C', 'text': '单一症状即可确诊', 'is_correct': True},
    ]
    lv = q['learning_value']
    lv['per_option'] = [
        {'label': 'A', 'truth': True, 'why': 'y' * 25, 'source_anchor': anchor,
         'distractor_mechanism': 'direction_error'},
        {'label': 'B', 'truth': True, 'why': 'y' * 25, 'source_anchor': anchor,
         'distractor_mechanism': 'direction_error'},
        {'label': 'C', 'truth': False, 'why': 'y' * 25,
         'distractor_mechanism': 'direction_error'},
    ]
    if schema_version:
        q['schema_version'] = schema_version
    return q


def test_reverse_true_distractors_anchored_passes():
    r = check_item(_reverse_item())
    assert r['status'] != 'FAIL', r['issues']
    assert r['reverse_anchor_covered'] == 2
    assert r['reverse_anchor_total'] == 2


def test_reverse_v22_missing_anchor_fails():
    """v2.2 起反选题的为真干扰项必须逐项锚点 → 缺则 FAIL，不再只是 WARN。"""
    r = check_item(_reverse_item(schema_version='2.2', anchor=''))
    assert r['status'] == 'FAIL'
    assert any(i['rule'] == 'R15' and 'source_anchor' in i['detail'] for i in r['issues'])


def test_reverse_item_anchor_falls_back_to_answer_evidence():
    """题级 answer_evidence 可兜底（正确说法来自同一段原文）。"""
    q = _reverse_item(anchor='')
    q['learning_value']['answer_evidence'] = '教材 P142：利钠肽与结构证据共同构成诊断依据'
    r = check_item(q)
    assert r['status'] != 'FAIL', r['issues']
    assert r['reverse_anchor_covered'] == 2


def test_reverse_misconception_is_optional_but_indexed():
    """反选题写 misconception（说明陷阱）不报错，且要进 R19 的 ID 索引。"""
    q = _reverse_item()
    q['learning_value']['per_option'][0]['misconception_id'] = 'MC-NEG-1'
    q['learning_value']['per_option'][0]['misconception'] = '忽略否定词'
    r = check_item(q)
    assert r['status'] != 'FAIL', r['issues']
    assert 'MC-NEG-1' in str(r['misconceptions'] + 1) or r['misconceptions'] >= 1


def test_batch_summary_splits_two_coverages():
    from check_learning_value import audit_batch

    _, s = audit_batch([_valid_positive(), _reverse_item()])
    # _valid_positive 是 3 选项（答案 B）→ 2 个干扰项进错误认知分母；
    # _reverse_item 是 3 选项（答案 C）→ 2 个为真项进锚点分母。
    assert s['misconception_denominator'] == 2, '正选题干扰项进错误认知分母'
    assert s['reverse_anchor_denominator'] == 2, '反选题为真项进锚点分母'
    assert s['reverse_items'] == 1
    assert s['reverse_anchor_coverage'] == 1.0
