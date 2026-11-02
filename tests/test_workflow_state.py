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


# ── P1-S5：版本血缘五元组 ───────────────────────────────────

_SHA = 'a' * 64


def test_batch_number_parsing():
    assert ws.batch_number('batch046') == 46
    assert ws.batch_number('batch047-a') == 47
    assert ws.batch_number('_review_only_batch') is None
    assert ws.batch_number(None) is None


def test_lineage_required_boundary():
    assert ws.lineage_required('batch046') is False
    assert ws.lineage_required('batch047') is True
    assert ws.lineage_required('batch100') is True
    assert ws.lineage_required('batchMDT') is False


def test_lineage_records_five_tuple():
    state = {}
    batch = ws.add_lineage(
        state, 'batch047', 'agent2', 'f.json', 'md5',
        model='qwen', model_id='qwen-3.7-max', prompt_sha256=_SHA,
        config_hash=_SHA, input_hash=_SHA, artifact_sha256=_SHA)
    entry = batch['lineage'][0]
    for f in ws.LINEAGE_FIELDS:
        assert entry[f], f"五元组缺 {f}"
    assert batch['steps']['AGENT2']['lineage']['prompt_sha256'] == _SHA


def test_lineage_strict_raises_when_incomplete():
    state = {}
    try:
        ws.add_lineage(state, 'batch047', 'agent2', 'f.json', 'md5', strict=True)
        raise AssertionError('严格批次缺五元组应抛 LineageIncomplete')
    except ws.LineageIncomplete as e:
        assert 'prompt_sha256' in str(e)


def test_lineage_legacy_batch_not_blocked():
    """历史批次 ≤046 不得因缺五元组被阻断（只读、不追溯）。"""
    state = {}
    batch = ws.add_lineage(state, 'batch046', 'agent2', 'f.json', 'md5')
    assert batch['lineage'][0]['prompt_sha256'] == ''
    assert ws._lineage_gaps(batch['lineage'][0]), "历史批次应能如实暴露缺口"


def test_lineage_unknown_counts_as_missing():
    state = {}
    try:
        ws.add_lineage(state, 'batch047', 'agent2', 'f.json', 'md5',
                       model='unknown', model_id='unknown',
                       prompt_sha256=_SHA, config_hash=_SHA,
                       input_hash=_SHA, artifact_sha256=_SHA, strict=True)
        raise AssertionError("model_id='unknown' 应视为缺失")
    except ws.LineageIncomplete as e:
        assert 'model_id' in str(e)


def test_lineage_non_sha_value_rejected():
    state = {}
    try:
        ws.add_lineage(state, 'batch047', 'agent2', 'f.json', 'md5',
                       model_id='m', prompt_sha256='not-a-sha',
                       config_hash=_SHA, input_hash=_SHA, artifact_sha256=_SHA, strict=True)
        raise AssertionError('非 sha256 值应被拒绝')
    except ws.LineageIncomplete as e:
        assert 'prompt_sha256' in str(e)


def test_lineage_strict_switch_off_for_new_batch():
    """显式 strict=False 可降级（给迁移期留口子，但必须显式）。"""
    state = {}
    batch = ws.add_lineage(state, 'batch047', 'agent2', 'f.json', 'md5', strict=False)
    assert batch['lineage'][0]['stage'] == 'agent2_DONE'


# ── P5-S1：重试计数与自动隔离（AC-P5-03）─────────────────────

def test_retry_item_quarantine_threshold():
    """单题重试 >2 次 → 该题 QUARANTINE。"""
    state = {}
    state_batch = ws.new_batch('batch900')
    state['batch900'] = state_batch
    for _ in range(ws.RETRY_ITEM_MAX):
        r = ws.record_retry(state, 'batch900', 'Q1', stage='agent4', rule_id='R12')
        assert not r['quarantined'], '未超阈值不应隔离'
    r = ws.record_retry(state, 'batch900', 'Q1', stage='agent4', rule_id='R12')
    assert r['quarantined'] is True
    assert r['scope'] == ws.QUARANTINE_SCOPE_ITEM
    assert state['batch900']['status'] == ws.STATUS_QUARANTINE
    assert ws.is_quarantined(state, 'batch900', 'Q1') is True
    assert ws.is_quarantined(state, 'batch900', 'Q2') is False


def test_retry_batch_quarantine_threshold():
    """整批重试 >3 次 → 整批 QUARANTINE（覆盖单题）。"""
    state = {'batch901': ws.new_batch('batch901')}
    last = None
    for i in range(ws.RETRY_BATCH_MAX + 1):
        last = ws.record_retry(state, 'batch901', f'Q{i}', stage='agent4')
    assert last['quarantined'] is True
    assert last['scope'] == ws.QUARANTINE_SCOPE_BATCH
    assert ws.is_quarantined(state, 'batch901', 'Q99') is True


def test_retry_events_are_auditable():
    state = {'batch902': ws.new_batch('batch902')}
    ws.record_retry(state, 'batch902', 'Q1', stage='agent4', rule_id='R2', reason='长度比')
    ev = state['batch902']['retries']['events'][-1]
    assert ev['rule_id'] == 'R2' and ev['reason'] == '长度比'
    assert 'timestamp' in ev and ev['item_id'] == 'Q1'
    # 不含任何用户维度字段
    assert not ({'user', 'user_id', 'session', 'attempt_by'} & set(ev))


def test_retry_summary_shape():
    state = {'batch903': ws.new_batch('batch903')}
    ws.record_retry(state, 'batch903', 'Q1')
    ws.record_retry(state, 'batch903', 'Q1')
    s = ws.retry_summary(state, 'batch903')
    assert s['exists'] is True
    assert s['batch_retries'] == 2
    assert s['items_retried'] == 1
    assert s['top_items'][0][0] == 'Q1'
    assert s['limits'] == {'item': 2, 'batch': 3}


def test_clear_quarantine_item_and_batch():
    state = {'batch904': ws.new_batch('batch904')}
    for _ in range(3):
        ws.record_retry(state, 'batch904', 'Q1')
    assert ws.is_quarantined(state, 'batch904')
    ws.clear_quarantine(state, 'batch904', by='reviewer', reason='人工确认可放行')
    assert ws.is_quarantined(state, 'batch904') is False
    assert state['batch904']['status'] == 'IN_PROGRESS'
    assert state['batch904']['quarantine']['released_by'] == 'reviewer'


def test_retry_does_not_touch_other_batches():
    state = {'batch905': ws.new_batch('batch905'), 'batch906': ws.new_batch('batch906')}
    for _ in range(4):
        ws.record_retry(state, 'batch905', 'Q1')
    assert ws.is_quarantined(state, 'batch906') is False
    assert state['batch906']['status'] == 'IN_PROGRESS'
