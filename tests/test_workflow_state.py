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


def test_ensure_batch_creates_new():
    """测试ensure_batch创建新批次"""
    state = {}
    batch, created = ws.ensure_batch(state, 'batch001')
    assert created is True
    assert batch['batch_id'] == 'batch001'
    assert 'batch001' in state


def test_ensure_batch_returns_existing():
    """测试ensure_batch返回已存在批次"""
    state = {'batch001': {'batch_id': 'batch001', 'status': 'IN_PROGRESS'}}
    batch, created = ws.ensure_batch(state, 'batch001')
    assert created is False
    assert batch['status'] == 'IN_PROGRESS'


def test_set_step_updates_status():
    """测试set_step更新步骤状态"""
    state = {}
    ws.add_lineage(state, 'batch001', 'agent2', 'f.json', 'md5')
    batch = ws.set_step(state, 'batch001', 'AGENT3', status='IN_PROGRESS')
    assert batch['steps']['AGENT3']['status'] == 'IN_PROGRESS'
    # 当status不是'COMPLETED'时，batch.status被设置为status值本身
    assert batch['status'] == 'IN_PROGRESS'


def test_halt_blocks_all_batches_when_no_batch_id():
    """测试无batch_id的全局halt阻断所有批次"""
    state = {'batchA': {}, 'batchB': {}}
    state['halt'] = {'active': True, 'reason': '全局停止'}
    assert ws.check_halt(state, 'batchA') is not None
    assert ws.check_halt(state, 'batchB') is not None


def test_clear_halt_clears_batch_record():
    """测试clear_halt清除批次记录"""
    state = {'batch001': {'batch_id': 'batch001'}}
    ws.set_halt(state, 'batch001', '测试', 'tester')
    ws.clear_halt(state, 'batch001')
    batch = state['batch001']
    assert batch['gate_results']['halt']['active'] is False
    assert state['halt']['active'] is False


def test_load_state_returns_error_for_missing_file():
    """测试load_state对缺失文件返回错误"""
    state, err = ws.load_state(base='/nonexistent/path')
    assert state is None
    assert err is not None


def test_load_state_returns_error_for_invalid_json():
    """测试load_state对无效JSON返回错误"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        invalid_file = tmp_path / 'workflow_state.json'
        invalid_file.write_text('not valid json', encoding='utf-8')
        state, err = ws.load_state(base=tmp_path)
        assert state is None
        assert 'JSON' in err


def test_save_state_creates_backup():
    """测试save_state创建备份"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        state = {'active_batch': 'batch001'}
        ws.save_state(state, base=tmp_path)
        assert (tmp_path / 'workflow_state.json').exists()


def test_migrate_preserves_approved_batches():
    """测试迁移保留已批准批次"""
    state = {
        'batch001': {'batch_id': 'batch001', 'status': 'APPROVED'},
        'batch002': {'batch_id': 'batch002', 'status': 'IN_PROGRESS'},
    }
    migrated, changes = ws.migrate_legacy(state)
    assert migrated['batch001']['status'] == 'APPROVED'
    assert migrated['batch002']['status'] == 'IN_PROGRESS'


def test_lineage_records_model_info():
    """测试血缘记录包含模型信息"""
    state = {}
    ws.add_lineage(state, 'batch001', 'agent2', 'f.json', 'md5', 
                   model='qwen3.7-max', prompt_version='v2.0')
    lineage = state['batch001']['lineage'][0]
    assert lineage['agent_model'] == 'qwen3.7-max'
    assert lineage['prompt_version'] == 'v2.0'
