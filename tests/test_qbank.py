"""qbank 解析器/注册表/去重 单元测试（pytest 兼容，纯 assert）。

运行: python scripts/run_tests.py  或  python -m pytest tests/ -q
"""
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'scripts'))
import qbank


def _mk(tmp, name, questions):
    p = Path(tmp) / name
    p.write_text(json.dumps(questions, ensure_ascii=False), encoding='utf-8')
    return p


# ── 解析器 ──

def test_parse_three_option_formats():
    q1 = qbank.parse_question({'question': '心衰诊断金标准?', 'options': {'A': 'a', 'B': 'b'},
                               'answer': 'A', 'id': 'T1'})
    q2 = qbank.parse_question({'stem': '心衰诊断金标准?',
                               'options': [{'label': 'A', 'text': 'a'}, {'label': 'B', 'text': 'b'}],
                               'answer_key': 'B', 'question_id': 'T2'})
    q3 = qbank.parse_question({'question_text': '心衰诊断金标准?',
                               'options': ['A. a', 'B. b'], 'correct_answer': 'C', 'id': 'T3'})
    assert q1 is not None and q2 is not None and q3 is not None
    assert q1['answer'] == 'A' and q2['answer'] == 'B' and q3['answer'] == 'C'
    assert q1['stem'] == q2['stem'] == q3['stem']
    assert 'A' in q1['options'] and 'B' in q2['options'] and 'A' in q3['options']


def test_parse_rejects_non_bank():
    assert qbank.parse_question({'report_metadata': {}}) is None
    assert qbank.parse_question({'options': {}}) is None  # 无题干
    assert qbank.extract_questions('/nonexistent.json') == []


def test_stem_hash_normalization():
    assert qbank.stem_hash('心衰诊断') == qbank.stem_hash('  心衰诊断  ')
    assert qbank.stem_hash('a  b') == qbank.stem_hash('a b')


# ── 注册表（临时目录隔离）──

def test_register_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        qbank._set_registry_base(tmp)
        try:
            qbank.init_registry_for_test()
            p = _mk(tmp, 'q1.json', [{'stem': '题一', 'options': {'A': 'a', 'B': 'b'}, 'answer': 'A'}])
            n1, d1 = qbank.register_file(p, 'batchT')
            assert n1 == 1 and not d1
            n2, d2 = qbank.register_file(p, 'batchT')  # 重复注册 → 幂等
            assert n2 == 0 and not d2
            s = qbank.stats()
            assert s['total'] == 1
        finally:
            qbank._set_registry_base(None)


def test_register_detects_cross_file_dup():
    with tempfile.TemporaryDirectory() as tmp:
        qbank._set_registry_base(tmp)
        try:
            qbank.init_registry_for_test()
            q1 = [{'stem': '完全相同的题干内容', 'options': {'A': 'a', 'B': 'b'}, 'answer': 'A'}]
            p1 = _mk(tmp, 'a1.json', q1)
            p2 = _mk(tmp, 'a2.json', q1)
            n1, _ = qbank.register_file(p1, 'batchX')
            n2, dups = qbank.register_file(p2, 'batchY')
            assert n1 == 1 and n2 == 1
            assert len(dups) == 1 and dups[0]['stem_hash'] == qbank.stem_hash('完全相同的题干内容')
            issues, warns, _ = qbank.check()
            assert len(warns) == 1  # 跨批次重复 → WARN
        finally:
            qbank._set_registry_base(None)


def test_check_ignore_pair():
    with tempfile.TemporaryDirectory() as tmp:
        qbank._set_registry_base(tmp)
        try:
            qbank.init_registry_for_test()
            q1 = [{'stem': '合并来源与合并结果共有的题干', 'options': {'A': 'a', 'B': 'b'}, 'answer': 'A'}]
            _ = _mk(tmp, 'src.json', q1)
            _ = _mk(tmp, 'merged.json', q1)
            qbank.register_file(Path(tmp) / 'src.json', 'batchA-ref')
            qbank.register_file(Path(tmp) / 'merged.json', 'batchB-merged')
            _, warns, _ = qbank.check()
            assert len(warns) == 1
            _, warns2, _ = qbank.check(ignore_pairs={frozenset({'batchA-ref', 'batchB-merged'})})
            assert len(warns2) == 0  # 已知合并关系豁免
        finally:
            qbank._set_registry_base(None)


def test_same_batch_multi_stage_is_info_not_warn():
    with tempfile.TemporaryDirectory() as tmp:
        qbank._set_registry_base(tmp)
        try:
            qbank.init_registry_for_test()
            q1 = [{'stem': '新旧版本共有的题干', 'options': {'A': 'a', 'B': 'b'}, 'answer': 'A'}]
            p1 = _mk(tmp, 'mid.json', q1)
            p2 = _mk(tmp, 'final.json', q1)
            qbank.register_file(p1, 'batchZ', stage='intermediate')
            qbank.register_file(p2, 'batchZ', stage='final')
            _, warns, infos = qbank.check()
            assert len(warns) == 0      # 同批次多版本不告警
            assert any('同批次多版本' in i for i in infos)
        finally:
            qbank._set_registry_base(None)
