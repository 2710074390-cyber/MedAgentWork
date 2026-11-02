"""Patch 契约与 Diff 审计的回归测试（P5-S2 / P5-S3）。

运行: python scripts/run_tests.py test_patch_integrity
或:   python -m pytest tests/test_patch_integrity.py -q
"""
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
for p in (str(BASE), str(BASE / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_patch_integrity as cpi  # noqa: E402


def _q(qid='Q1', **over):
    q = {'id': qid, 'type': 'A1', 'stem': '题干', 'answer': 'A',
         'options': [{'label': 'A', 'text': '甲'}, {'label': 'B', 'text': '乙'}],
         'explanation': '解析', 'teacher_anchor': '原文引文',
         'source_page': '教材P1', 'keypoint_ref': ['第1条']}
    q.update(over)
    return q


def _write(items):
    d = tempfile.mkdtemp()
    p = Path(d) / 'q.json'
    p.write_text(json.dumps(items, ensure_ascii=False), encoding='utf-8')
    return p


# ── 不可变字段（AC-P5-01）──────────────────────────────────

def test_immutable_answer_change_is_violation():
    b = _write([_q()])
    a = _write([_q(answer='B')])
    r = cpi.audit(b, a, tag='t')
    assert r['result'] == 'FAIL'
    assert r['counts']['immutable_violations'] == 1
    assert 'answer' in r['violations'][0]['fields']


def test_immutable_teacher_anchor_is_violation():
    b = _write([_q()])
    a = _write([_q(teacher_anchor='被改过的引文')])
    r = cpi.audit(b, a, tag='t')
    assert r['result'] == 'FAIL'
    assert any('teacher_anchor' in v['fields'] for v in r['violations'])


def test_immutable_source_page_and_keypoint():
    b = _write([_q()])
    a = _write([_q(source_page='教材P99', keypoint_ref=['第9条'])])
    r = cpi.audit(b, a, tag='t')
    fields = {f for v in r['violations'] for f in v['fields']}
    assert {'source_page', 'keypoint_ref'} <= fields


def test_real_question_stem_is_immutable():
    b = _write([_q(kaoyan_origin='GS-001')])
    a = _write([_q(kaoyan_origin='GS-001', stem='被改写的真题题干')])
    r = cpi.audit(b, a, tag='t')
    assert r['result'] == 'FAIL'
    assert any('stem(真题题干)' in v['fields'] for v in r['violations'])


def test_real_question_detected_by_marker():
    q = _q()
    q['stem'] = '题干 [源:考研真题 GS-001]'
    assert cpi.is_real_question(q) is True
    assert cpi.is_real_question(_q()) is False


def test_allowed_field_change_passes():
    b = _write([_q()])
    a = _write([_q(explanation='重写过的解析', options=[
        {'label': 'A', 'text': '甲（改）'}, {'label': 'B', 'text': '乙'}])])
    r = cpi.audit(b, a, tag='t')
    assert r['result'] == 'PASS'
    assert r['counts']['changed'] == 1
    assert set(r['records'][0]['changed_fields']) == {'explanation', 'options'}


def test_unclassified_field_rejected():
    b = _write([_q()])
    a = _write([_q(unknown_field='x')])
    r = cpi.audit(b, a, tag='t')
    assert r['counts']['unclassified_fields'] == 1
    assert r['result'] == 'FAIL'


# ── diff 审计：声明字段 vs 实际（P5-S3）────────────────────

def test_undeclared_change_rejected():
    b = _write([_q()])
    a = _write([_q(explanation='新解析', options=[
        {'label': 'A', 'text': '甲2'}, {'label': 'B', 'text': '乙'}])])
    r = cpi.audit(b, a, declared={'Q1': ['explanation']}, tag='t')
    assert r['result'] == 'FAIL'
    assert r['undeclared'][0]['fields'] == ['options']


def test_declared_change_matching_actual_passes():
    b = _write([_q()])
    a = _write([_q(explanation='新解析')])
    r = cpi.audit(b, a, declared={'Q1': ['explanation']}, tag='t')
    assert r['result'] == 'PASS'
    assert r['records'][0]['declared_fields'] == ['explanation']


def test_declared_immutable_is_still_violation():
    """声明了也不许改不可变字段 —— 声明不能豁免契约。"""
    b = _write([_q()])
    a = _write([_q(answer='B')])
    r = cpi.audit(b, a, declared={'Q1': ['answer']}, tag='t')
    assert r['result'] == 'FAIL'
    assert r['counts']['immutable_violations'] == 1


def test_added_and_removed_items_tracked():
    b = _write([_q('Q1'), _q('Q2')])
    a = _write([_q('Q1'), _q('Q3')])
    r = cpi.audit(b, a, tag='t')
    assert r['added_ids'] == ['Q3']
    assert r['removed_ids'] == ['Q2']
    assert r['counts']['items_patched'] == 1


def test_sha256_before_after_recorded():
    b = _write([_q()])
    a = _write([_q(explanation='改了')])
    r = cpi.audit(b, a, tag='t')
    rec = r['records'][0]
    assert len(rec['sha256_before']) == 64 and len(rec['sha256_after']) == 64
    assert rec['sha256_before'] != rec['sha256_after']


# ── no-op 检测（AC-P5-04）──────────────────────────────────

def test_noop_detected_on_identical_file():
    p = _write([_q()])
    r = cpi.audit(p, p, tag='t')
    r['noop'] = cpi.detect_noop(r)
    assert r['file_identical'] is True
    assert r['noop']['status'] == 'NOOP'


def test_noop_detected_on_same_content_different_file():
    b = _write([_q()])
    a = _write([_q()])
    r = cpi.audit(b, a, tag='t')
    r['noop'] = cpi.detect_noop(r)
    assert r['noop']['status'] == 'NOOP'
    assert r['counts']['changed'] == 0


def test_effective_patch_not_flagged_noop():
    b = _write([_q()])
    a = _write([_q(explanation='真改了')])
    r = cpi.audit(b, a, tag='t')
    r['noop'] = cpi.detect_noop(r)
    assert r['noop']['status'] == 'EFFECTIVE'


def test_cli_noop_exit_code_is_nonzero():
    p = _write([_q()])
    rc = cpi.main(['--before', str(p), '--after', str(p), '--noop', '--quiet',
                   '--json', str(Path(tempfile.mkdtemp()) / 'r.json')])
    assert rc == 1


# ── 修复统计（AC-P5-05）───────────────────────────────────

def test_repair_stats_shapes_and_definitions():
    b = _write([_q(explanation='')])
    a = _write([_q(explanation='补齐了解析的说明文字，长度足够')])
    s = cpi.repair_stats(b, a)
    for k in ('before', 'after', 'fixed', 'persist', 'repair_success_rate',
              'recurrence_rate', 'per_severity', 'per_rule', 'definitions'):
        assert k in s
    assert 0.0 <= s['repair_success_rate'] <= 1.0
    assert 0.0 <= s['recurrence_rate'] <= 1.0
    assert 'FAIL' in s['per_severity'] and 'WARN' in s['per_severity']


# ── 真实样本（只读历史，不修改）─────────────────────────────

def test_batch045_sample_has_zero_immutable_violations():
    """AC-P5-01：历史 patch 样本上不可变字段违例 = 0。"""
    b = BASE / '中间产物/batch045/ALL_questions_pilot_draft.json'
    a = BASE / '中间产物/batch045/ALL_questions_pilot_revised_v5.json'
    if not (b.exists() and a.exists()):
        import unittest
        raise unittest.SkipTest('batch045 样本不存在')
    r = cpi.audit(b, a, tag='batch045')
    assert r['counts']['immutable_violations'] == 0, r['violations']


def test_batch046_a4_is_noop():
    """AC-P5-04 的真实样本：batch046 的 A2→A4 内容零变化。"""
    b = BASE / '中间产物/batch046/ALL_questions.json'
    a = BASE / '最终产物/batch046/ALL_questions_FIXED.json'
    if not (a.exists() and b.exists()):
        import unittest
        raise unittest.SkipTest('batch046 样本不存在')
    r = cpi.audit(b, a, tag='batch046')
    r['noop'] = cpi.detect_noop(r)
    assert r['noop']['status'] == 'NOOP', 'A4 交付与 A2 输入字节相同，应判 no-op'
