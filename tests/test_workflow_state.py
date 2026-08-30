"""workflow_state 统一状态模块单元测试（pytest 兼容，纯 assert）。

运行: python scripts/run_tests.py  或  python -m pytest tests/ -q
"""
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'scripts'))
import workflow_state as ws


def test_new_batch_template():
    b = ws.new_batch('batch999', subject='内科学')
    assert b['batch_id'] == 'batch999'
    assert b['status'] == 'IN_PROGRESS'
    assert b['subject'] == '内科学'
    assert b['steps'] == {} and b['lineage'] == []


def test_add_lineage_and_steps():
    state = {}
    batch = ws.add_lineage(state, 'batch999', 'agent2', '中间产物/batch999/x.json', 'md5abc')
    assert state['batch999'] is batch
    assert batch['status'] == 'AGENT2_DONE'
    assert batch['steps']['AGENT2']['md5'] == 'md5abc'
    assert batch['steps']['AGENT2']['status'] == 'COMPLETED'
    assert batch['lineage'][0]['stage'] == 'agent2_DONE'


def test_detect_next_stage():
    state = {}
    ws.add_lineage(state, 'batch999', 'agent2', 'f.json', 'm')
    assert ws.detect_next_stage(state, 'batch999') == 'agent3'
    ws.add_lineage(state, 'batch999', 'agent3', 'f.json', 'm')
    ws.add_lineage(state, 'batch999', 'agent4', 'f.json', 'm')
    ws.add_lineage(state, 'batch999', 'agent5', 'f.md', 'm')
    assert ws.detect_next_stage(state, 'batch999') is None
    assert ws.detect_next_stage(state, 'batch-missing') == 'agent2'


def test_halt_per_batch_scoping():
    state = {'batchA': {'batch_id': 'batchA'}, 'batchB': {'batch_id': 'batchB'}}
    ws.set_halt(state, 'batchA', '测试阻断', 'tester')
    assert ws.check_halt(state, 'batchA') is not None   # 同批次阻断
    assert ws.check_halt(state, 'batchB') is None       # 其他批次不受影响
    ws.clear_halt(state, 'batchA')
    assert ws.check_halt(state, 'batchA') is None


def test_legacy_global_halt_still_blocks():
    state = {'batchA': {'batch_id': 'batchA'}}
    state['halt'] = {'active': True, 'reason': '历史全局 halt（无 batch_id）'}
    assert ws.check_halt(state, 'batchA') is not None


def test_migrate_removes_duplicate_case_keys():
    state = {'batch007': {'batch_id': 'batch007', 'steps': {'completed': '2026-06-21', 'COMPLETED': {'status': 'OK'}}}}
    migrated, changes = ws.migrate_legacy(state)
    steps = migrated['batch007']['steps']
    assert 'completed' not in steps and 'COMPLETED' in steps
    assert any('completed' in c for c in changes)


def test_migrate_selfheals_polluted_batch_id():
    state = {'halt': {'active': False, 'batch_id': 'halt'},  # v1.0 bug 污染
             'gate_system': {'version': '1.0', 'batch_id': 'gate_system'}}
    migrated, changes = ws.migrate_legacy(state)
    assert 'batch_id' not in migrated['halt']
    assert 'batch_id' not in migrated['gate_system']
    assert any('误注入' in c for c in changes)


def test_migrate_does_not_touch_real_batches():
    state = {'batch005': {'batch_id': 'batch005', 'status': 'APPROVED'}}
    migrated, _ = ws.migrate_legacy(state)
    assert migrated['batch005']['batch_id'] == 'batch005'


def test_save_load_roundtrip_atomic():
    with tempfile.TemporaryDirectory() as tmp:
        state = {'active_batch': 'batch999', 'batch999': ws.new_batch('batch999')}
        ws.save_state(state, base=tmp)
        loaded, err = ws.load_state(base=tmp)
        assert err is None
        assert loaded['active_batch'] == 'batch999'
        assert loaded['batch999']['batch_id'] == 'batch999'
        # 无残留 tmp 文件
        assert not list(Path(tmp).glob('*.tmp'))


def test_validate_state_detects_issues():
    state = {'batchX': {'status': 'APPROVED'}}  # 缺 batch_id
    issues = ws.validate_state(state)
    assert any('batch_id' in i for i in issues)
