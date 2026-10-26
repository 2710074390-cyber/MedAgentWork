# -*- coding: utf-8 -*-
"""门禁适用范围与阶段路由回归测试（2026-10-23）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

import gate_check  # noqa: E402
from quality_gate import check_item_learning_value  # noqa: E402


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


def test_quality_gate_flags_misconception_conflicts(tmp_path):
    report = tmp_path / 'lv.json'
    report.write_text(
        '{"summary":{"fail":0,"per_option_coverage":1.0,"misconception_coverage":1.0,'
        '"source_quote_exact_rate":1.0,"quote_verified_rate":1.0,'
        '"misconception_id_conflicts":1,"anchor_verified_rate":1.0}}',
        encoding='utf-8',
    )
    args = type('Args', (), {'learning_value': str(report), 'questions': '', 'batch': 'x'})()
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
