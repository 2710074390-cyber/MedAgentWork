"""契约 schema 正反例测试（jsonschema，pytest 兼容）。

运行: python scripts/run_tests.py  或  python -m pytest tests/ -q
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import jsonschema


def _load_schema(name):
    with open(BASE / 'schemas' / name, encoding='utf-8') as f:
        return json.load(f)


def _valid(schema, data):
    jsonschema.Draft7Validator(schema).validate(data)


def test_agent2_positive():
    _valid(_load_schema('agent2_output.schema.json'), [{
        'question_id': 'TEST-M1-A1-001', 'type': 'A1', 'polarity': 'positive',
        'bloom_level': 'memory', 'module': 'M1', 'stem': '题干',
        'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
        'answer_key': 'C', 'explanation': '解析', 'source_pages': ['P12'],
    }])


def test_agent2_legacy_fields_ok():
    # 旧契约字段（question/answer/correct_answer）也应通过
    _valid(_load_schema('agent2_output.schema.json'), [{
        'id': 'T1', 'type': 'A1', 'question': '题干',
        'options': [{'label': 'A', 'text': '甲'}, {'label': 'B', 'text': '乙'},
                    {'label': 'C', 'text': '丙'}, {'label': 'D', 'text': '丁'},
                    {'label': 'E', 'text': '戊'}],
        'answer': 'C',
    }])


def test_agent2_negative_missing_options():
    from jsonschema import ValidationError
    schema = _load_schema('agent2_output.schema.json')
    try:
        _valid(schema, [{'stem': '题干'}])
        raise AssertionError('缺少 options 应触发 ValidationError')
    except ValidationError:
        pass


def test_agent3_positive():
    _valid(_load_schema('agent3_output.schema.json'), {
        'report_metadata': {'gate_decision': 'PASS_WITH_FIXES', 'overall_score': 82.5},
        'dimensions': {'D20': 1},
        'bloom_distribution': {'记忆': 30, '理解': 40, '应用': 25, '分析': 5},
        'issues': [{'question_id': 'T1', 'severity': 'major', 'rule': 'D17', 'detail': 'x'}],
    })


def test_agent3_negative_gate_decision():
    from jsonschema import ValidationError
    schema = _load_schema('agent3_output.schema.json')
    try:
        _valid(schema, {'report_metadata': {'gate_decision': 'MAYBE'}})
        raise AssertionError('非法 gate_decision 应报错')
    except ValidationError:
        pass


def test_agent4_object_form_with_hc13():
    _valid(_load_schema('agent4_output.schema.json'), {
        'source_file_synced': True,
        'execution_metadata': {},
        'patch_log': [{'patch_id': 'P1', 'status': 'EXECUTED'}],
        'final_gate': 'PASS',
    })


def test_agent4_array_form():
    _valid(_load_schema('agent4_output.schema.json'), [
        {'question_id': 'T1', 'issue_type': 'D17', 'action': 'fix', 'detail': 'x'},
    ])


def test_agent4_negative_missing_hc13():
    from jsonschema import ValidationError
    schema = _load_schema('agent4_output.schema.json')
    try:
        _valid(schema, {'execution_metadata': {}})  # 无 source_file_synced
        raise AssertionError('缺 HC-13 字段应报错')
    except ValidationError:
        pass
