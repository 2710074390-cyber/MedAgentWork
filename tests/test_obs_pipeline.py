"""系统遥测 / 指标聚合 / 门禁自测的回归测试（P6-S1~S3）。

运行: python scripts/run_tests.py test_obs_pipeline
或:   python -m pytest tests/test_obs_pipeline.py -q
"""
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
for p in (str(BASE), str(BASE / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import telemetry as tm  # noqa: E402
import gate_selftest as gs  # noqa: E402
import aggregate_metrics as am  # noqa: E402


def _obs_dir():
    d = Path(tempfile.mkdtemp())
    tm.OBS_DIR = d
    return d


# ── P6-S1 JSONL sink ──────────────────────────────────────

def test_record_event_writes_one_file_per_batch():
    d = _obs_dir()
    tm.record_event('batch900', 'gate_check', gate='GATE-A2', status='PASS')
    tm.record_event('batch901', 'gate_check', gate='GATE-A2', status='BLOCKED')
    files = sorted(p.name for p in d.glob('*_telemetry.jsonl'))
    assert files == ['batch900_telemetry.jsonl', 'batch901_telemetry.jsonl']


def test_record_event_rejects_user_fields():
    d = _obs_dir()
    assert tm.record_event('batch900', 'x', user_id='u1') is None
    assert tm.record_event('batch900', 'x', session_id='s1') is None
    assert not list(d.glob('*.jsonl')), '被拒收的事件不得落盘'


def test_record_event_rejects_non_whitelisted_field():
    _obs_dir()
    assert tm.record_event('batch900', 'x', foo='bar') is None


def test_record_event_accepts_whitelisted_fields():
    _obs_dir()
    ev = tm.record_event('batch900', 'validate_done', stage='A2', rule_id='R12',
                         severity='FAIL', action='fix', retry=1, duration_ms=12.5,
                         tokens=100, model_id='m', prompt_sha256='a' * 64,
                         artifact_sha256='b' * 64, count=100)
    assert ev is not None
    assert set(ev) <= tm.EVENT_FIELDS
    assert ev['rule_id'] == 'R12'


def test_kill_switch_stops_writing(monkeypatch=None):
    d = _obs_dir()
    import os

    os.environ['TELEMETRY_FILE'] = '0'
    try:
        assert tm.record_event('batch900', 'x', status='PASS') is None
        assert not list(d.glob('*.jsonl'))
    finally:
        os.environ.pop('TELEMETRY_FILE', None)


def test_batch_name_is_sanitized():
    _obs_dir()
    p = tm.jsonl_path('../../etc/passwd')
    assert '..' not in p.name and '/' not in p.name and '\\' not in p.name


def test_read_events_and_schema_check():
    _obs_dir()
    tm.record_event('batch900', 'gate_check', gate='GATE-A2', status='PASS')
    tm.record_event('batch900', 'validate_done', count=10)
    ev = tm.read_events('batch900')
    assert len(ev) == 2
    assert tm.validate_event_schema(ev) == []


def test_read_events_all_batches():
    _obs_dir()
    tm.record_event('batch900', 'gate_check', status='PASS')
    tm.record_event('batch901', 'gate_check', status='BLOCKED')
    assert len(tm.read_events()) == 2


# ── P6-S3 门禁自测 ────────────────────────────────────────

def test_fixture_meets_shape_requirements():
    data = json.loads(gs.FIXTURE.read_text(encoding='utf-8'))
    assert gs.check_fixture(data) == [], gs.check_fixture(data)
    assert len(data['classes']) >= 10
    for c in data['classes']:
        assert len(c['cases']) >= 3, c['id']


def test_selftest_detects_all_hard_classes():
    data = json.loads(gs.FIXTURE.read_text(encoding='utf-8'))
    r = gs.selftest(data)
    assert r['detection']['hard_rate'] >= gs.HARD_DETECTION_MIN, \
        [(c['rule'], c['misses']) for c in r['per_class'] if c['detected'] < c['cases']]


def test_selftest_false_positive_below_threshold():
    data = json.loads(gs.FIXTURE.read_text(encoding='utf-8'))
    r = gs.selftest(data)
    assert r['false_positive']['rate'] <= gs.FALSE_POSITIVE_MAX, r['false_positive']['items']
    assert r['result'] == 'PASS'


def test_selftest_detects_rule_regression():
    """把某类的 rule 改成不存在的规则号，自测必须掉下来（否则等于没测）。"""
    data = json.loads(gs.FIXTURE.read_text(encoding='utf-8'))
    data['classes'][0]['rule'] = 'R999'
    r = gs.selftest(data)
    assert r['result'] == 'FAIL'
    assert r['per_class'][0]['detected'] == 0


def test_selftest_flags_bad_fixture():
    data = {'classes': [{'id': 'X', 'rule': 'R1', 'cases': []}], 'good': []}
    assert gs.check_fixture(data), '缺例/缺好题必须被报出来'


# ── P6-S2 指标聚合 ────────────────────────────────────────

def test_aggregate_builds_metrics_and_sqlite():
    d = _obs_dir()
    tm.record_event('batch900', 'gate_check', gate='GATE-A2', status='PASS')
    tm.record_event('batch900', 'gate_check', gate='GATE-A3', status='BLOCKED')
    tm.record_event('batch900', 'validate_done', count=10, status='FAIL',
                    action='fail=2,warn=1,pass=8')
    db = d / 'm.db'
    out = d / 'm.json'
    s = am.build(db, out)
    assert db.exists() and out.exists()
    assert s['events'] == 3 and s['batches'] == 1
    row = s['per_batch'][0]
    assert row['batch'] == 'batch900'
    assert row['gate_total'] == 2 and row['gate_blocked'] == 1
    assert row['gate_block_rate'] == 0.5
    assert row['fpy'] == 0.8, row
    assert row['cost_per_item'] is None, '无 tokens 数据时必须为 null，不得估算'
    assert s['field_schema_issues'] == []


def test_aggregate_definitions_present():
    d = _obs_dir()
    tm.record_event('batch900', 'gate_check', status='PASS')
    s = am.build(d / 'm.db', d / 'm.json')
    for k in ('fpy', 'gate_block_rate', 'repair_success', 'recurrence_rate',
              'cost_per_item', 'p95_latency_ms'):
        assert k in s['definitions']


def test_aggregate_p95_latency():
    d = _obs_dir()
    for ms in (10, 20, 30, 40, 100):
        tm.record_event('batch900', 'gate_check', status='PASS', duration_ms=ms)
    s = am.build(d / 'm.db', d / 'm.json')
    assert s['per_batch'][0]['p95_latency_ms'] == 100.0


# ── P2-S5：缺陷集 severity 与规则实际级别必须一致（2026-11-02）──────
#
# 背景：R13 从 FAIL 降级为 WARN 后，缺陷集仍声明 FAIL，而自测只看"规则有没有命中"，
# 于是报出 hard 检出 100% —— 实际上那条缺陷在 gate 上根本不阻断。这是假绿。

def test_selftest_flags_severity_mismatch():
    data = {
        'classes': [{
            'id': 'D-TEST', 'rule': 'R13', 'severity': 'FAIL', 'title': '假硬规则',
            'cases': [
                {'id': 'S1', 'type': 'A1', 'question': '关于治疗，下列哪项正确',
                 'options': {'A': '这是一个超过二十个字符的选项内容确实太长了',
                             'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'}, 'answer': 'A'},
            ],
        }],
        'good': [],
    }
    r = gs.selftest(data)
    assert r['detection']['severity_mismatches'], '声明 FAIL 但实际 WARN，必须报不一致'
    assert r['detection']['severity_consistent'] is False
    assert r['result'] == 'FAIL'


def test_selftest_severity_consistent_when_declared_correctly():
    data = {
        'classes': [{
            'id': 'D-TEST2', 'rule': 'R13', 'severity': 'WARN', 'title': '降级后的 R13',
            'cases': [
                {'id': 'S2', 'type': 'A1', 'question': '关于治疗，下列哪项正确',
                 'options': {'A': '这是一个超过二十个字符的选项内容确实太长了',
                             'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'}, 'answer': 'A'},
            ],
        }],
        'good': [],
    }
    r = gs.selftest(data)
    assert r['detection']['severity_consistent'] is True
    assert r['detection']['severity_mismatches'] == []


def test_selftest_real_fixture_is_severity_consistent():
    """真实缺陷集必须与规则现状一致（R13 已降级，缺陷集不能还写 FAIL）。"""
    data = json.loads(gs.FIXTURE.read_text(encoding='utf-8'))
    r = gs.selftest(data)
    assert r['detection']['severity_consistent'] is True, r['detection']['severity_mismatches']
