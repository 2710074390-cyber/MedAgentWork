# -*- coding: utf-8 -*-
"""HC-24 学习价值层校验器回归测试。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
    assert r['status'] == 'PASS', r


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
