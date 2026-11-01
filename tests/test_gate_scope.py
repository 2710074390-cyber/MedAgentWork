# -*- coding: utf-8 -*-
"""门禁适用范围与阶段路由回归测试（2026-10-23）。"""
import sys
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

import gate_check  # noqa: E402
from quality_gate import check_item_learning_value  # noqa: E402


def test_a2_strict_binding_passes_actual_input(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    source = tmp_path / '中间产物' / 'batch100' / 'ALL_questions.json'
    source.parent.mkdir(parents=True)
    source.write_text('[]', encoding='utf-8')
    report_dir = tmp_path / 'reports' / 'validate'
    report_dir.mkdir(parents=True)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    (report_dir / 'validate_options_report_batch100.json').write_text(json.dumps({
        'report_metadata': {'batch_id': 'batch100', 'stage': 'A2', 'source_file': str(source), 'source_sha256': sha},
        'summary': {'fail': 0},
    }), encoding='utf-8')
    batch = {'product_types': ['question_bank'], 'evidence_binding_mode': 'strict'}
    assert gate_check.gate_agent2('batch100', batch)['status'] == 'PASS'


def test_a2_strict_binding_blocks_cross_batch_and_missing_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    report_dir = tmp_path / 'reports' / 'validate'
    report_dir.mkdir(parents=True)
    source = tmp_path / '最终产物' / 'batch099' / 'ALL_questions.json'
    source.parent.mkdir(parents=True)
    source.write_text('[]', encoding='utf-8')
    (report_dir / 'validate_options_report_batch100.json').write_text(json.dumps({
        'report_metadata': {'source_file': str(source)}, 'summary': {'fail': 0},
    }), encoding='utf-8')
    result = gate_check.gate_agent2('batch100', {'product_types': ['question_bank'], 'evidence_binding_mode': 'strict'})
    assert result['status'] == 'BLOCKED'
    assert '证据绑定失败' in result['reason']


def test_a2_legacy_report_remains_compatible(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    report_dir = tmp_path / 'reports' / 'validate'
    report_dir.mkdir(parents=True)
    (report_dir / 'validate_options_report_batch043.json').write_text(json.dumps({
        'summary': {'fail': 0}, 'report_metadata': {'source_file': 'old.json'},
    }), encoding='utf-8')
    result = gate_check.gate_agent2('batch043', {'product_types': ['question_bank']})
    assert result['status'] == 'PASS'


def test_mode_fail_closed_and_legacy_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    assert not gate_check._is_strict_batch('batch044', {})
    assert not gate_check._is_strict_batch('batch044-A', {})
    # 非标准批次 ID（测试/复核伪批次）不得被误判为新批次
    assert not gate_check._is_strict_batch('batchMDT', {})
    assert not gate_check._is_strict_batch('_review_only_batch', {})
    assert not gate_check._is_strict_batch('batch-legacy-test', {})
    for mode in (None, '', 'legacy', 'Strict', 1):
        batch = {'product_types': ['question_bank'], 'steps': {'AGENT3': {}, 'AGENT4': {}}}
        if mode is not None:
            batch['evidence_binding_mode'] = mode
        for gate in (gate_check.gate_agent2, gate_check.gate_agent3, gate_check.gate_agent4):
            result = gate('batch045', batch)
            assert result['status'] == 'BLOCKED'
            assert 'evidence_binding_mode' in result['reason']


def test_strict_stage_bindings_and_ambiguity(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    batch_id = 'batch100'
    intermediate = tmp_path / '中间产物' / batch_id / 'ALL_questions.json'
    final = tmp_path / '最终产物' / batch_id / 'ALL_questions_FIXED.json'
    for path in (intermediate, final):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('[]', encoding='utf-8')
    def report(stage, path):
        return {'report_metadata': {'batch_id': batch_id, 'stage': stage,
                'source_file': str(path), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
    for stage, path in [('A2', intermediate), ('A3', intermediate), ('A4', final)]:
        evidence = report(stage, path)
        assert not gate_check._batch_binding_issues(batch_id, evidence, None, stage, True)
        evidence['report_metadata']['stage'] = 'wrong'
        assert gate_check._batch_binding_issues(batch_id, evidence, None, stage, True)
        evidence = report(stage, path)
        path.write_text('[1]', encoding='utf-8')
        assert gate_check._batch_binding_issues(batch_id, evidence, None, stage, True)
        path.write_text('[]', encoding='utf-8')
    assert gate_check._batch_binding_issues(batch_id, report('A3', final), None, 'A3', True)
    (intermediate.parent / 'ALL_questions_extra.json').write_text('[]', encoding='utf-8')
    assert gate_check._batch_binding_issues(batch_id, report('A2', intermediate), None, 'A2', True)


def test_a4_strict_trace_and_new_batch(tmp_path, monkeypatch):
    import workflow_state
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    batch = workflow_state.new_batch('batch100', product_types=['question_bank'])
    batch['steps']['AGENT4'] = {'output': '追溯日志'}
    final = tmp_path / '最终产物' / 'batch100' / 'ALL_questions_FIXED.json'
    final.parent.mkdir(parents=True)
    final.write_text('[]', encoding='utf-8')
    final.with_suffix('.md').write_text('ok', encoding='utf-8')
    source = tmp_path / '中间产物' / 'batch100' / 'ALL_questions.json'
    source.parent.mkdir(parents=True)
    source.write_text('[]', encoding='utf-8')
    qc = tmp_path / '质检报告' / 'batch100' / 'A3_质检报告.json'
    qc.parent.mkdir(parents=True)
    qc.write_text(json.dumps({'report_metadata': {'batch_id': 'batch100', 'stage': 'A3',
                  'source_file': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}}), encoding='utf-8')
    trace = final.parent / 'AGENT4_追溯日志.json'
    evidence = {'report_metadata': {'batch_id': 'batch100', 'stage': 'A4', 'source_file': str(final),
                'source_sha256': hashlib.sha256(final.read_bytes()).hexdigest(),
                'a2_input_file': str(source), 'a2_input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'a3_report_file': str(qc), 'a3_report_sha256': hashlib.sha256(qc.read_bytes()).hexdigest()}, 'source_file_synced': True}
    trace.write_text(json.dumps(evidence), encoding='utf-8')
    assert gate_check.gate_agent4('batch100', batch)['status'] == 'PASS'
    for field in ('a2_input_file', 'a2_input_sha256', 'a3_report_file', 'a3_report_sha256'):
        altered = json.loads(json.dumps(evidence))
        altered['report_metadata'].pop(field)
        trace.write_text(json.dumps(altered), encoding='utf-8')
        assert gate_check.gate_agent4('batch100', batch)['status'] == 'BLOCKED'
    trace.write_text(json.dumps(evidence), encoding='utf-8')
    source.write_text('[2]', encoding='utf-8')
    assert gate_check.gate_agent4('batch100', batch)['status'] == 'BLOCKED'
    source.write_text('[]', encoding='utf-8')
    original_qc = qc.read_text(encoding='utf-8')
    altered_qc = json.loads(original_qc)
    altered_qc['report_metadata']['stage'] = 'A2'
    qc.write_text(json.dumps(altered_qc), encoding='utf-8')
    evidence['report_metadata']['a3_report_sha256'] = hashlib.sha256(qc.read_bytes()).hexdigest()
    trace.write_text(json.dumps(evidence), encoding='utf-8')
    assert gate_check.gate_agent4('batch100', batch)['status'] == 'BLOCKED'
    qc.write_text(original_qc, encoding='utf-8')
    final.write_text('[1]', encoding='utf-8')
    assert gate_check.gate_agent4('batch100', batch)['status'] == 'BLOCKED'
    trace.write_text('{', encoding='utf-8')
    assert gate_check.gate_agent4('batch100', batch)['status'] == 'BLOCKED'


def test_real_reporter_and_a3_gate(tmp_path, monkeypatch):
    from scripts.validate import reporter
    import workflow_state
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    monkeypatch.setattr(reporter, 'OUTPUT_BASE', tmp_path / 'reports' / 'validate')
    batch = workflow_state.new_batch('batch100', product_types=['question_bank'])
    batch['steps']['AGENT3'] = {'status': 'COMPLETED'}
    source = tmp_path / '中间产物' / 'batch100' / 'ALL_questions.json'
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps([{'bloom': '理解'}]), encoding='utf-8')
    path = reporter.save_json_report({}, {'fail': 0}, source, source.stem)
    assert gate_check.gate_agent2('batch100', batch)['status'] == 'PASS'
    metadata = json.loads(path.read_text(encoding='utf-8'))['report_metadata']
    metadata['stage'] = 'A3'
    qc = tmp_path / '质检报告' / 'batch100' / 'A3_质检报告.json'
    qc.parent.mkdir(parents=True)
    qc.write_text(json.dumps({'report_metadata': metadata, 'dimensions': {'D20': 1},
                              'bloom_distribution': {'理解': 100}}), encoding='utf-8')
    batch['target_bloom'] = {'理解': 100}
    assert gate_check.gate_agent3('batch100', batch)['status'] == 'PASS'
    qc.with_name('第二质检报告.json').write_text(qc.read_text(encoding='utf-8'), encoding='utf-8')
    assert gate_check.gate_agent3('batch100', batch)['status'] == 'BLOCKED'


def test_infer_prediction_paper_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    final_dir = tmp_path / '最终产物' / 'predtest'
    final_dir.mkdir(parents=True)
    (final_dir / 'ALL_questions_FIXED.json').write_text('[]', encoding='utf-8')
    (final_dir / '耳鼻咽喉头颈外科学·期末押题卷.md').write_text('# x', encoding='utf-8')
    types = gate_check.infer_product_types('predtest', {'subject': '耳鼻咽喉头颈外科学（期末押题卷）'})
    assert types == {gate_check.PRODUCT_PREDICTION_PAPER, gate_check.PRODUCT_QUESTION_BANK}


def test_infer_review_only_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    types = gate_check.infer_product_types('reviewtest', {'subject': '某复习资料', 'final_review': {'hc9': 'PASS'}})
    assert types == {gate_check.PRODUCT_REVIEW_MATERIAL}


def test_prediction_final_skips_review_appendices(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    final_dir = tmp_path / '最终产物' / 'predtest'
    final_dir.mkdir(parents=True)
    (final_dir / 'ALL_questions_FIXED.json').write_text('[]', encoding='utf-8')
    batch = {
        'product_types': ['prediction_paper'],
        'subject': '耳鼻咽喉头颈外科学（期末押题卷）',
        'final_review': {'json_valid': True},
    }
    r = gate_check.gate_final('predtest', batch)
    assert r['status'] == 'PASS', r


def test_review_final_still_requires_hc9_hc10_hc11(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    batch = {'subject': '某复习资料', 'final_review': {'json_valid': True}}
    r = gate_check.gate_final('reviewtest', batch)
    assert r['status'] == 'BLOCKED'
    blocked = {s['gate_sub'] for s in r.get('sub_gates', []) if s['status'] == 'BLOCKED'}
    assert {'GATE-FINAL-HC9', 'GATE-FINAL-HC10', 'GATE-FINAL-HC11'} <= blocked


def test_review_only_batch_skips_a2_a3_a4(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    batch = {'product_types': ['review_material']}
    assert gate_check.gate_agent2('reviewtest', batch).get('skipped') is True
    assert gate_check.gate_agent3('reviewtest', batch).get('skipped') is True
    assert gate_check.gate_agent4('reviewtest', batch).get('skipped') is True


def test_stage_sequence_inserts_learning_value_for_v2():
    seq = gate_check.stage_sequence('x', {'item_schema_version': '2.0', 'product_types': ['question_bank']})
    assert seq == ['agent2_done', 'agent3_done', 'agent4_done', 'learning_value', 'final']
    seq_legacy = gate_check.stage_sequence('x', {'product_types': ['question_bank']})
    assert 'learning_value' not in seq_legacy


def test_detect_current_stage_routes_to_learning_value():
    state = {
        'batchv2': {
            'item_schema_version': '2.0',
            'steps': {
                'AGENT2': {'status': 'COMPLETED'},
                'AGENT3': {'status': 'COMPLETED'},
                'AGENT4': {'status': 'COMPLETED'},
            },
        }
    }
    assert gate_check.detect_current_stage(state, 'batchv2') == 'learning_value'
    state['batchv2']['gate_results'] = {'GATE-LV': {'status': 'PASS'}}
    assert gate_check.detect_current_stage(state, 'batchv2') == 'final'


def test_item_learning_value_fresh_temporary_report(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    target = tmp_path / '最终产物' / 'batch045' / 'ALL_questions_FIXED.json'
    target.parent.mkdir(parents=True)
    target.write_text('[]', encoding='utf-8')
    old = tmp_path / 'reports' / 'validate' / 'learning_value_batch045.json'
    old.parent.mkdir(parents=True)
    old.write_text('old', encoding='utf-8')
    summary = {'fail': 0, 'per_option_coverage': 1, 'misconception_coverage': 1,
               'source_quote_exact_rate': 1, 'quote_verified_rate': 1, 'anchor_verified_rate': 1}
    state = {'code': 0, 'batch': 'batch045', 'hash': hashlib.sha256(target.read_bytes()).hexdigest(), 'write': True}
    def run(cmd, **kwargs):
        assert cmd[cmd.index('--batch') + 1] == 'batch045'
        path = Path(cmd[cmd.index('--out') + 1])
        assert path != old
        if state['write']:
            path.write_text(json.dumps({'batch': state['batch'], 'input_sha256': state['hash'], 'summary': summary}), encoding='utf-8')
        return SimpleNamespace(returncode=state['code'], stderr='', stdout='')
    monkeypatch.setattr(gate_check.subprocess, 'run', run)
    batch = {'product_types': ['question_bank']}
    assert gate_check.gate_item_learning_value('batch045', batch)['status'] == 'PASS'
    for change in ({'code': 2}, {'batch': 'batch044'}, {'hash': 'stale'}, {'write': False}):
        previous = state.copy()
        state.update(change)
        assert gate_check.gate_item_learning_value('batch045', batch)['status'] == 'BLOCKED'
        state.update(previous)
    assert old.read_text(encoding='utf-8') == 'old'


def test_new_batch_learning_value_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    for schema in ('2.1', None):
        data = {'product_types': ['question_bank'], 'item_schema_version': schema}
        result = gate_check.gate_item_learning_value('batch045', data)
        assert result['status'] == 'BLOCKED'
        assert '题库 JSON' in result['reason']
    other = {'product_types': ['review_material'], 'item_schema_version': '2.1'}
    assert gate_check.gate_item_learning_value('batch045', other)['skipped']
    assert gate_check.gate_item_learning_value('batch044', {'product_types': ['question_bank']})['skipped']


def test_quality_gate_flags_misconception_conflicts(tmp_path):
    report = tmp_path / 'lv.json'
    report.write_text(
        '{"summary":{"fail":0,"per_option_coverage":1.0,"misconception_coverage":1.0,'
        '"source_quote_exact_rate":1.0,"quote_verified_rate":1.0,'
        '"misconception_id_conflicts":1,"anchor_verified_rate":1.0}}',
        encoding='utf-8',
    )
    args = type('Args', (), {'learning_value': str(report), 'questions': '', 'batch': 'batch043'})()
    profile = {'thresholds': {
        'source_quote_exact_min': 0.95,
        'quote_verified_min': 0.95,
        'misconception_conflict_max': 0,
        'anchor_verified_warn': 0.9,
        'anchor_verified_block': 0.8,
    }}
    r = check_item_learning_value(args, profile, 'enforce')
    assert r['status'] == 'FAIL'
    assert '冲突=1' in r['reason']


def test_question_blueprint_hard_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    folder = tmp_path / '中间产物' / 'batch046'
    folder.mkdir(parents=True)
    plan = list('ABCDE' * 20)
    questions = [{'answer': a, 'bloom': b, 'type': t} for a, b, t in zip(
        plan, ['记忆'] * 20 + ['理解'] * 25 + ['应用'] * 35 + ['分析'] * 20,
        ['A1'] * 30 + ['A2'] * 45 + ['A3'] * 25)]
    config = {'bloom_targets': {'记忆': [0, 20], '理解': [25, 25], '应用': [35, 35], '分析': [20, 20]},
              'type_targets': {'A1': [30, 30], 'A2': [45, 45], 'A3': [25, 25], 'A4': [0, 0]},
              'type_group_targets': {'A3+A4': [25, 25]}}
    batch = {'question_blueprint_gate': config}
    def write():
        (folder / 'ALL_questions.json').write_text(json.dumps(questions, ensure_ascii=False), encoding='utf-8')
        (folder / 'answer_position_plan.json').write_text(json.dumps(plan), encoding='utf-8')
    write()
    assert gate_check.gate_question_blueprint('batch046', batch)['status'] == 'PASS'
    assert gate_check.gate_question_blueprint('batch046', {}) is None
    questions[0]['bloom'] = ''
    write()
    assert 'Bloom' in gate_check.gate_question_blueprint('batch046', batch)['reason']
    questions[0]['bloom'] = '记忆'
    questions[0]['answer'] = 'B'
    write()
    assert '计划' in gate_check.gate_question_blueprint('batch046', batch)['reason']
    plan[0:3] = ['A', 'A', 'A']
    for i in range(3):
        questions[i]['answer'] = 'A'
    write()
    assert '连续三题' in gate_check.gate_question_blueprint('batch046', batch)['reason']
    questions.pop()
    write()
    assert gate_check.gate_final('batch046', {**batch, 'status': 'APPROVED'})['status'] == 'BLOCKED'
    assert gate_check.gate_question_blueprint('batch046', {'question_blueprint_gate': {}})['status'] == 'BLOCKED'


def test_question_blueprint_type_group_gate_over_limit_and_legacy_compat(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_check, 'BASE', tmp_path)
    folder = tmp_path / '中间产物' / 'batch046'
    folder.mkdir(parents=True)
    plan = list('ABCDE' * 20)
    questions = [{'answer': answer, 'bloom': bloom, 'type': kind} for answer, bloom, kind in zip(
        plan, ['记忆'] * 20 + ['理解'] * 25 + ['应用'] * 35 + ['分析'] * 20,
        ['A1'] * 30 + ['A2'] * 45 + ['A3'] * 25)]
    (folder / 'ALL_questions.json').write_text(json.dumps(questions, ensure_ascii=False), encoding='utf-8')
    (folder / 'answer_position_plan.json').write_text(json.dumps(plan), encoding='utf-8')
    base = {'bloom_targets': {'记忆': [0, 20], '理解': [25, 25], '应用': [35, 35], '分析': [20, 20]},
            'type_targets': {'A1': [29, 30], 'A2': [45, 45], 'A3': [25, 25], 'A4': [0, 2]}}
    assert gate_check.gate_question_blueprint('batch046', {'question_blueprint_gate': base})['status'] == 'PASS'
    grouped = {**base, 'type_group_targets': {'A3+A4': [25, 25]}}
    result = gate_check.gate_question_blueprint('batch046', {'question_blueprint_gate': grouped})
    assert result['status'] == 'PASS'
    questions[0]['type'] = 'A4'
    (folder / 'ALL_questions.json').write_text(json.dumps(questions, ensure_ascii=False), encoding='utf-8')
    result = gate_check.gate_question_blueprint('batch046', {'question_blueprint_gate': grouped})
    assert result['status'] == 'BLOCKED'
    assert '题型组合 A3+A4 题数 26' in result['reason']
    grouped['type_group_targets'] = {}
    assert gate_check.gate_question_blueprint('batch046', {'question_blueprint_gate': grouped})['status'] == 'PASS'
