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
import re
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
        'item_schema_version': '2.0',
        'evidence_binding_mode': 'strict',
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


LINEAGE_REQUIRED_SINCE = 47
"""版本血缘五元组强制生效的最小批次号（P1-S5）。

batch046 及以前为只读历史批次，不追溯、不因缺字段阻断；
batch047 起，lineage 必须带齐 prompt_sha256 / model_id / config_hash /
input_hash / artifact_sha256，gate_check 会逐项校验。
"""
LINEAGE_FIELDS = ('prompt_sha256', 'model_id', 'config_hash', 'input_hash', 'artifact_sha256')
_SHA256_FIELDS = ('prompt_sha256', 'config_hash', 'input_hash', 'artifact_sha256')


class LineageIncomplete(ValueError):
    """严格批次写入血缘时缺少五元组字段。"""


def batch_number(batch_id) -> int | None:
    """从 batchNNN / batchNNN-后缀 中解析批次号；非标准 ID 返回 None。"""
    if batch_id is None:
        return None
    m = re.fullmatch(r'batch(\d+)(?:-[A-Za-z0-9]+)?', str(batch_id).strip())
    return int(m.group(1)) if m else None


def lineage_required(batch_id) -> bool:
    """该批次是否受五元组强制约束（batch047+）。"""
    n = batch_number(batch_id)
    return n is not None and n >= LINEAGE_REQUIRED_SINCE


def _lineage_gaps(entry: dict) -> list[str]:
    """返回五元组缺失/无效项（'unknown' 视为缺失，空串视为缺失）。"""
    gaps = []
    for f in LINEAGE_FIELDS:
        v = str(entry.get(f) or '').strip()
        if not v or v.lower() == 'unknown':
            gaps.append(f)
        elif f in _SHA256_FIELDS and not re.fullmatch(r'[0-9a-fA-F]{64}', v):
            gaps.append(f'{f}(非 sha256)')
    return gaps


def add_lineage(state, batch_id, stage, filepath, file_md5,
                model='unknown', prompt_version='unknown', *,
                prompt_sha256='', model_id='', config_hash='',
                input_hash='', artifact_sha256='', strict=None):
    """添加血缘记录并更新 steps/status。返回该批次 dict。

    stage: 'agent2'..'agent5'（小写）；steps 键为 STAGE.upper()。

    P1-S5（2026-11-02）：除原有 model/prompt_version 外，记录版本五元组
    prompt_sha256 / model_id / config_hash / input_hash / artifact_sha256。

    strict 语义（重要）：
      - strict=True  → 缺项立即抛 LineageIncomplete（写入口关）；
      - strict=False → 照常记录，缺项留空（历史批次 / 迁移期）；
      - strict=None  → 只看 MEDAGENTWORK_LINEAGE_STRICT 开关，**不按批次号自动开启**。
        批次号自动开启只在 gate 层生效（gate_check._lineage_issues，batch047+），
        这样旧调用方（历史批次、测试夹具 batch999）不会被写入口直接打断。
        真实管线由 ingest.py 显式传 strict=lineage_required(batch_id) 开闸。
    """
    if strict is None:
        strict = os.environ.get('MEDAGENTWORK_LINEAGE_STRICT', '').strip().lower() in ('1', 'true', 'yes', 'on')

    batch, _ = ensure_batch(state, batch_id)
    if 'lineage' not in batch or not isinstance(batch['lineage'], list):
        batch['lineage'] = []

    entry = {
        'stage': f'{stage}_DONE',
        'input_file': str(filepath),
        'input_md5': file_md5,
        'agent_model': model,
        'prompt_version': prompt_version,
        'prompt_sha256': prompt_sha256 or '',
        'model_id': model_id or (model if model and model != 'unknown' else ''),
        'config_hash': config_hash or '',
        'input_hash': input_hash or '',
        'artifact_sha256': artifact_sha256 or '',
        'timestamp': datetime.now().isoformat(),
    }

    if strict:
        gaps = _lineage_gaps(entry)
        if gaps:
            raise LineageIncomplete(
                f'{batch_id} 属严格批次（≥batch{LINEAGE_REQUIRED_SINCE:03d}），'
                f'血缘五元组缺项/无效: {", ".join(gaps)}；'
                '请补齐 prompt_sha256/model_id/config_hash/input_hash/artifact_sha256 后重试')

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
        'lineage': {k: entry[k] for k in LINEAGE_FIELDS},
    }
    batch['status'] = f'{stage_key}_DONE'
    return batch


# ──────────────────────────────────────────
# 重试计数与自动隔离（P5-S1）
# ──────────────────────────────────────────

STATUS_QUARANTINE = 'QUARANTINE'
RETRY_ITEM_MAX = 2    # 单题重试 > 2 次 → 该题 QUARANTINE
RETRY_BATCH_MAX = 3   # 整批重试 > 3 次 → 整批 QUARANTINE
QUARANTINE_SCOPE_ITEM = 'item'
QUARANTINE_SCOPE_BATCH = 'batch'


def _retry_bucket(batch):
    """取（必要时初始化）批次的重试桶。"""
    r = batch.get('retries')
    if not isinstance(r, dict):
        r = {}
        batch['retries'] = r
    if not isinstance(r.get('items'), dict):
        r['items'] = {}
    if not isinstance(r.get('events'), list):
        r['events'] = []
    r.setdefault('batch', 0)
    return r


def record_retry(state, batch_id, item_id=None, stage='', rule_id='', reason=''):
    """记录一次重试，并在超阈值时自动把题目/批次置为 QUARANTINE。

    阈值（可用 pipeline_config 覆盖）：
      单题 >2 次、整批 >3 次 → 自动隔离，不再自动重试（转人工/重生成）。

    返回 {'batch_retries': int, 'item_retries': int|None,
          'quarantined': bool, 'scope': 'item'|'batch'|None, 'status': str}
    """
    item_max = _retry_limit('retry_item_max', RETRY_ITEM_MAX)
    batch_max = _retry_limit('retry_batch_max', RETRY_BATCH_MAX)

    batch, _ = ensure_batch(state, batch_id)
    bucket = _retry_bucket(batch)

    bucket['batch'] = int(bucket.get('batch') or 0) + 1
    item_count = None
    if item_id:
        item_count = int(bucket['items'].get(item_id) or 0) + 1
        bucket['items'][item_id] = item_count

    bucket['events'].append({
        'timestamp': datetime.now().isoformat(),
        'stage': stage,
        'item_id': item_id or '',
        'rule_id': rule_id or '',
        'reason': reason or '',
        'batch_retries': bucket['batch'],
        'item_retries': item_count,
    })

    scope = None
    if item_count is not None and item_count > item_max:
        scope = QUARANTINE_SCOPE_ITEM
        _mark_quarantine(batch, scope, item_id=item_id,
                         reason=f'单题重试 {item_count} 次 > {item_max}', stage=stage)
    if bucket['batch'] > batch_max:
        scope = QUARANTINE_SCOPE_BATCH
        _mark_quarantine(batch, scope, item_id=None,
                         reason=f'整批重试 {bucket["batch"]} 次 > {batch_max}', stage=stage)

    return {
        'batch_retries': bucket['batch'],
        'item_retries': item_count,
        'quarantined': bool(batch.get('quarantine')),
        'scope': scope,
        'status': batch.get('status', ''),
    }


def _retry_limit(key, default):
    try:
        import pipeline_config as pc

        return int(pc.get_number(key, default))
    except Exception:
        return default


def _mark_quarantine(batch, scope, item_id=None, reason='', stage=''):
    q = batch.get('quarantine')
    if not isinstance(q, dict):
        q = {'status': STATUS_QUARANTINE, 'scope': scope, 'items': [], 'reasons': []}
        batch['quarantine'] = q
    q['status'] = STATUS_QUARANTINE
    # 批次级隔离覆盖题目级
    if scope == QUARANTINE_SCOPE_BATCH or q.get('scope') != QUARANTINE_SCOPE_BATCH:
        q['scope'] = scope
    if item_id and item_id not in q['items']:
        q['items'].append(item_id)
    if reason:
        q['reasons'].append({'at': datetime.now().isoformat(), 'stage': stage, 'reason': reason})
    q.setdefault('since', datetime.now().isoformat())
    batch['status'] = STATUS_QUARANTINE


def is_quarantined(state, batch_id, item_id=None):
    """批次/题目是否处于隔离状态。"""
    batch = state.get(batch_id) if isinstance(state, dict) else None
    if not isinstance(batch, dict):
        return False
    q = batch.get('quarantine')
    if not isinstance(q, dict) or q.get('status') != STATUS_QUARANTINE:
        return False
    if item_id:
        return q.get('scope') == QUARANTINE_SCOPE_BATCH or item_id in (q.get('items') or [])
    return True


def clear_quarantine(state, batch_id, by='', reason='', item_id=None):
    """人工解除隔离（留痕）。item_id 给定时只放行该题。"""
    batch = state.get(batch_id) if isinstance(state, dict) else None
    if not isinstance(batch, dict):
        return False
    q = batch.get('quarantine')
    if not isinstance(q, dict):
        return False
    if item_id:
        q['items'] = [i for i in (q.get('items') or []) if i != item_id]
        q.setdefault('released', []).append({
            'at': datetime.now().isoformat(), 'item_id': item_id, 'by': by, 'reason': reason})
        if q.get('items'):
            return True
    else:
        q['status'] = 'RELEASED'
        q['released_at'] = datetime.now().isoformat()
        q['released_by'] = by
        q['release_reason'] = reason
        if batch.get('status') == STATUS_QUARANTINE:
            batch['status'] = 'IN_PROGRESS'
        return True
    q['status'] = 'RELEASED'
    if batch.get('status') == STATUS_QUARANTINE:
        batch['status'] = 'IN_PROGRESS'
    return True


def retry_summary(state, batch_id):
    """重试计数可审计摘要（供 gate / 报告使用）。"""
    batch = state.get(batch_id) if isinstance(state, dict) else None
    if not isinstance(batch, dict):
        return {'batch': batch_id, 'exists': False}
    bucket = batch.get('retries') if isinstance(batch.get('retries'), dict) else {}
    items = bucket.get('items') or {}
    return {
        'batch': batch_id,
        'exists': True,
        'batch_retries': int(bucket.get('batch') or 0),
        'items_retried': len(items),
        'top_items': sorted(items.items(), key=lambda kv: -int(kv[1]))[:5],
        'events': len(bucket.get('events') or []),
        'quarantine': batch.get('quarantine') or None,
        'limits': {'item': _retry_limit('retry_item_max', RETRY_ITEM_MAX),
                   'batch': _retry_limit('retry_batch_max', RETRY_BATCH_MAX)},
    }


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
    # 实际写入版本号（防止 validate_state 持续告警）
    if state.get('schema_version') != STATE_SCHEMA_VERSION:
        state['schema_version'] = STATE_SCHEMA_VERSION
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

    # 校验失败非零退出
    if not args.check:
        parser.print_help()
        return

    issues = validate_state(state)
    batches = [k for k in state if isinstance(state[k], dict) and str(k).startswith('batch')]
    print(f'workflow_state.json: {len(batches)} 个批次 | schema_version={state.get("schema_version")}')
    if issues:
        print(f'⚠️ {len(issues)} 个问题:')
        for i in issues:
            print(f'  - {i}')
        sys.exit(1)
    print('✓ 结构校验通过')


if __name__ == '__main__':
    main()
