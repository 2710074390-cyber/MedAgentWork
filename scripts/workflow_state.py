#!/usr/bin/env python3
"""
workflow_state.py — MedAgentWork workflow_state.json 统一读写模块 v1.0 (2026-08-13)

重构目标（正式重构 · 2026-08-13）:
  消除 ingest.py / save.py / gate_check.py 三处各自实现的
  read-modify-write 逻辑与 schema 漂移（FACT.md 缺陷 C），
  统一: 原子读写 / 血缘记录 / 按批次 HALT / 批次模板 / 旧数据迁移。

用法（作为库）:
  import workflow_state as ws
  state, err = ws.load_state()
  ws.add_lineage(state, 'batch026', 'agent2', 'path.json', 'md5')
  ws.save_state(state)

用法（CLI）:
  python workflow_state.py --check            # 结构校验 + 汇总
  python workflow_state.py --migrate          # 应用旧数据迁移并保存
  python workflow_state.py --migrate --dry-run  # 预览迁移，不写盘
  python workflow_state.py --show batch024    # 查看单批次

设计约束: 仅用标准库；不 print（库职责）；写盘必须原子（tmp + os.replace）。
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

STATE_SCHEMA_VERSION = 2  # v2 (2026-08-13): 批次结构统一 + 按批次 HALT + 去重键

STAGE_ORDER = ['agent2', 'agent3', 'agent4', 'agent5']
STAGE_NAMES = {
    'agent2': 'MedGen 出题',
    'agent3': 'MedQC 质检',
    'agent4': 'MedFix 修复',
    'agent5': 'MedReview 主复习资料',
}
KNOWN_TOP_KEYS = {
    'active_batch', 'halt', 'gate_system', 'system_config',
    'current_agent', 'status', 'schema_version', 'last_migrated',
    'merged_psychiatry',
}


# ──────────────────────────────────────────
# 路径与读写
# ──────────────────────────────────────────

def state_path(base=None):
    base = Path(base) if base else Path(__file__).resolve().parent.parent
    return base / 'workflow_state.json'


def load_state(base=None):
    """加载状态。返回 (state, err)：
      - 文件缺失: (None, '...不存在')
      - 解析失败: (None, 'JSON 解析失败: ...')
      - 成功:     (dict, None)，并应用内存级旧数据迁移（不落盘）
    """
    p = state_path(base)
    if not p.exists():
        return None, f'{p} 不存在'
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return None, f'JSON 解析失败: {e}'
    except Exception as e:
        return None, str(e)
    if not isinstance(data, dict):
        return None, f'顶层结构不是对象: {type(data).__name__}'
    data, _ = migrate_legacy(data)
    return data, None


def save_state(state, base=None):
    """原子写盘（tmp + os.replace），避免半写损坏。"""
    p = state_path(base)
    tmp = p.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


# ──────────────────────────────────────────
# 批次记录
# ──────────────────────────────────────────

def new_batch(batch_id, **fields):
    """统一批次结构模板。extra fields（subject/task_type/chapter 等）透传。"""
    batch = {
        'batch_id': batch_id,
        'status': 'IN_PROGRESS',
        'created': datetime.now().isoformat(),
        'workflow': 'Agent 2(MedGen)→Agent 3(MedQC)→Agent 4(MedFix)→Agent 5(MedReview)',
        'steps': {},
        'lineage': [],
    }
    batch.update(fields)
    return batch


def ensure_batch(state, batch_id):
    """取批次；不存在则创建（返回 (batch, created:bool)）。"""
    if not isinstance(state, dict):
        raise ValueError('state 必须是 dict')
    batch = state.get(batch_id)
    if isinstance(batch, dict):
        return batch, False
    batch = new_batch(batch_id)
    state[batch_id] = batch
    return batch, True


def add_lineage(state, batch_id, stage, filepath, file_md5,
                model='unknown', prompt_version='unknown'):
    """添加血缘记录并更新 steps/status。返回该批次 dict。

    stage: 'agent2'..'agent5'（小写）；steps 键为 STAGE.upper()。
    """
    batch, _ = ensure_batch(state, batch_id)
    if 'lineage' not in batch or not isinstance(batch['lineage'], list):
        batch['lineage'] = []

    entry = {
        'stage': f'{stage}_DONE',
        'input_file': str(filepath),
        'input_md5': file_md5,
        'agent_model': model,
        'prompt_version': prompt_version,
        'timestamp': datetime.now().isoformat(),
    }
    batch['lineage'].append(entry)

    if 'steps' not in batch or not isinstance(batch['steps'], dict):
        batch['steps'] = {}
    stage_key = stage.upper()
    batch['steps'][stage_key] = {
        'status': 'COMPLETED',
        'output': str(Path(filepath).name),
        'md5': file_md5,
        'model': model,
        'prompt_version': prompt_version,
    }
    batch['status'] = f'{stage_key}_DONE'
    return batch


def set_step(state, batch_id, stage_key, status='COMPLETED', **fields):
    """更新批次内某步骤的状态与附加字段。"""
    batch, _ = ensure_batch(state, batch_id)
    if 'steps' not in batch or not isinstance(batch['steps'], dict):
        batch['steps'] = {}
    step = dict(batch['steps'].get(stage_key, {}))
    step['status'] = status
    step.update(fields)
    batch['steps'][stage_key] = step
    batch['status'] = f'{stage_key}_{status}' if status == 'COMPLETED' else status
    return batch


def detect_next_stage(state, batch_id, stages=STAGE_ORDER):
    """推断批次下一个未完成阶段（save.py 约定）。全部完成返回 None。"""
    batch = state.get(batch_id)
    if not isinstance(batch, dict):
        return stages[0]
    steps = batch.get('steps')
    if not isinstance(steps, dict):
        return stages[0]
    for stage in stages:
        key = stage.upper()
        if key not in steps:
            return stage
        if steps[key].get('status') != 'COMPLETED':
            return stage
    return None


# ──────────────────────────────────────────
# HALT（按批次作用域，2026-08-13 修复）
# ──────────────────────────────────────────

def set_halt(state, batch_id, reason, agent):
    """设置 halt 信号（按批次作用域）。全局镜像携带 batch_id，
    其他批次不受影响（修复: batch024 误停整条管线事件）。"""
    state['halt'] = {
        'active': True,
        'batch_id': batch_id,
        'reason': reason,
        'agent': agent,
        'timestamp': datetime.now().isoformat(),
    }
    batch = state.get(batch_id)
    if isinstance(batch, dict):
        if 'gate_results' not in batch or not isinstance(batch['gate_results'], dict):
            batch['gate_results'] = {}
        batch['gate_results']['halt'] = {
            'active': True,
            'reason': reason,
            'agent': agent,
            'batch_id': batch_id,
        }
    return state


def clear_halt(state, batch_id):
    """清除 halt 信号（全局镜像 + 批次记录）。"""
    state['halt'] = {'active': False}
    batch = state.get(batch_id)
    if isinstance(batch, dict) and isinstance(batch.get('gate_results'), dict):
        batch['gate_results']['halt'] = {'active': False}
    return state


def check_halt(state, batch_id):
    """检查 halt：仅阻断同批次（或历史无 batch_id 的全局 halt）。"""
    halt = state.get('halt', {})
    if halt.get('active'):
        halt_batch = halt.get('batch_id')
        if halt_batch is None or halt_batch == batch_id:
            return {
                'gate': 'HALT',
                'status': 'BLOCKED',
                'reason': f"批次 {batch_id} 已停止: {halt.get('reason', '未知')} (触发Agent: {halt.get('agent', '?')})",
            }
    batch = state.get(batch_id)
    if isinstance(batch, dict):
        batch_halt = batch.get('gate_results', {}).get('halt', {})
        if batch_halt.get('active'):
            return {
                'gate': 'HALT',
                'status': 'BLOCKED',
                'reason': f"批次 {batch_id} 已停止: {batch_halt.get('reason', '未知')}",
            }
    return None


# ──────────────────────────────────────────
# 旧数据迁移与校验
# ──────────────────────────────────────────

def migrate_legacy(state):
    """内存级迁移旧批次结构，返回 (state, changes)。不落盘。"""
    changes = []
    if not isinstance(state, dict):
        return state, changes

    def is_batch_key(key):
        return isinstance(key, str) and key.startswith('batch')

    # 1. 非批次顶层键自愈: 移除被误注入的 batch_id（v1.0 bug: 曾把 halt/
    #    gate_system/system_config/merged_psychiatry 当批次注入 batch_id）
    for key in list(state.keys()):
        if not is_batch_key(key) and isinstance(state[key], dict):
            polluted = state[key].pop('batch_id', None)
            if polluted is not None:
                changes.append(f'{key}: 移除误注入 batch_id={polluted!r}')

    # 2. 批次级: steps 中大小写重复键（batch007 遗留 'completed'/'COMPLETED'）
    for key, batch in state.items():
        if not is_batch_key(key):
            continue
        if not isinstance(batch, dict):
            continue
        if batch.get('batch_id') is None:
            batch['batch_id'] = key
            changes.append(f'{key}: 补 batch_id')
        steps = batch.get('steps')
        if isinstance(steps, dict):
            for dup in [k for k in steps if k.lower() == 'completed' and k != 'COMPLETED']:
                if 'COMPLETED' in steps:
                    del steps[dup]
                    changes.append(f'{key}: 移除重复键 {dup!r}（保留 COMPLETED）')

    # 3. 顶层: schema 版本标记
    if state.get('schema_version') != STATE_SCHEMA_VERSION:
        changes.append(f'schema_version → {STATE_SCHEMA_VERSION}')
    return state, changes


def validate_state(state):
    """结构校验，返回问题列表（空列表 = 通过）。"""
    issues = []
    if not isinstance(state, dict):
        return ['state 顶层不是 dict']
    if state.get('schema_version') is None:
        issues.append('缺少 schema_version（可运行 --migrate 补齐）')

    # 大小写重复键检查（全树）
    def walk(d, path):
        if isinstance(d, dict):
            seen = {}
            for k, v in d.items():
                low = k.lower()
                if low in seen:
                    issues.append(f'{path}: 大小写重复键 {seen[low]!r}/{k!r}')
                seen[low] = k
                walk(v, f'{path}.{k}')
        elif isinstance(d, list):
            for i, v in enumerate(d):
                walk(v, f'{path}[{i}]')
    walk(state, 'state')

    for key, batch in state.items():
        if key in KNOWN_TOP_KEYS or not isinstance(batch, dict):
            continue
        if not str(key).startswith('batch') and key not in STAGE_NAMES:
            issues.append(f'{key}: 疑似非批次顶层键')
        if batch.get('batch_id') != key:
            issues.append(f'{key}: batch_id({batch.get("batch_id")!r}) 与键名不一致')
        steps = batch.get('steps')
        if steps is not None and not isinstance(steps, dict):
            issues.append(f'{key}: steps 不是 dict ({type(steps).__name__})')
    return issues


# ──────────────────────────────────────────
# CLI
# ──────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='workflow_state.json 统一读写/校验/迁移')
    parser.add_argument('--check', action='store_true', help='结构校验 + 汇总')
    parser.add_argument('--migrate', action='store_true', help='应用旧数据迁移并保存')
    parser.add_argument('--dry-run', action='store_true', help='迁移预览，不写盘')
    parser.add_argument('--show', metavar='BATCH_ID', help='查看单批次摘要')
    args = parser.parse_args()

    state, err = load_state()
    if err:
        print(f'✗ {err}')
        sys.exit(2)

    if args.show:
        batch = state.get(args.show)
        if not isinstance(batch, dict):
            print(f'✗ 批次 {args.show} 不存在')
            sys.exit(1)
        print(json.dumps(batch, ensure_ascii=False, indent=2))
        return

    if args.migrate or args.dry_run:
        # 直接读原始文件（绕过 load_state 的内存迁移），确保迁移可落盘
        try:
            with open(state_path(), 'r', encoding='utf-8') as f:
                raw = json.load(f)
        except Exception as e:
            print(f'✗ 读取状态失败: {e}')
            sys.exit(2)
        state, changes = migrate_legacy(raw)
        if not changes:
            print('✓ 无需迁移')
        else:
            for c in changes:
                print(f'  ↳ {c}')
        if not args.dry_run:
            state['schema_version'] = STATE_SCHEMA_VERSION
            state['last_migrated'] = datetime.now().isoformat()
            save_state(state)
            print(f'✓ 已保存（schema_version={STATE_SCHEMA_VERSION}）')
        return

    if args.check or True:
        issues = validate_state(state)
        batches = [k for k in state if isinstance(state[k], dict) and str(k).startswith('batch')]
        print(f'workflow_state.json: {len(batches)} 个批次 | schema_version={state.get("schema_version")}')
        if issues:
            print(f'⚠️ {len(issues)} 个问题:')
            for i in issues:
                print(f'  - {i}')
        else:
            print('✓ 结构校验通过')


if __name__ == '__main__':
    main()
