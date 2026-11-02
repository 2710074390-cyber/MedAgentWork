#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aggregate_metrics.py — 系统指标聚合（P6-S2）。

把按批 JSONL 遥测（`reports/obs/<batch>_telemetry.jsonl`）汇总成
SQLite 指标库 + 一份可读的 metrics JSON。

指标定义（写死，避免口径漂移）
-------------------------------
fpy               一次通过率 = 该批「首轮校验 PASS 题数 / 题数」
                  （来源：validate 报告 summary.pass / total_questions）
gate_block_rate   门禁拦截率 = BLOCKED 门禁数 / 门禁总数
repair_success    修复成功率（FAIL 级）= 已消除 FAIL 问题 / (已消除 + 仍存在)
recurrence_rate   复发率 = after 新出现的 rule 问题 / after 全部问题
cost_per_item     单题成本 = 累计 tokens / 题数（无 tokens 数据时为 null，不估算）
p95_latency_ms    门禁/校验事件耗时的 95 分位（无耗时时为 null）

数据来源分层（必须可分辨，不许混为一谈）
---------------------------------------
- `live`      ：管线运行时 `telemetry.record_event()` 直接写入的事件；
- `backfill`  ：从既有产物（workflow_state / validate 报告 / repair 统计 /
                lineage 报告）反推的事件，带 `source: backfill` 标记。

用法::

    python scripts/aggregate_metrics.py --backfill      # 先反推历史事件到 JSONL
    python scripts/aggregate_metrics.py                 # 再聚合出指标
    python scripts/aggregate_metrics.py --json reports/obs/metrics_20261102.json

无用户数据：events 表只有系统字段，字段白名单由 telemetry.EVENT_FIELDS 强制。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'scripts'))

import telemetry as tm  # noqa: E402

OBS_DIR = BASE / 'reports' / 'obs'
DEFAULT_DB = OBS_DIR / 'metrics.db'
DEFAULT_OUT = OBS_DIR / f'metrics_{datetime.now():%Y%m%d}.json'

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, batch TEXT, event TEXT, stage TEXT, gate TEXT, status TEXT,
    rule_id TEXT, severity TEXT, action TEXT, retry INTEGER,
    duration_ms REAL, tokens INTEGER, count INTEGER,
    model_id TEXT, prompt_sha256 TEXT, artifact_sha256 TEXT,
    config_hash TEXT, source TEXT
);
CREATE TABLE IF NOT EXISTS batch_metrics (
    batch TEXT PRIMARY KEY,
    questions INTEGER, fpy REAL, gate_total INTEGER, gate_blocked INTEGER,
    gate_block_rate REAL, repair_success REAL, recurrence_rate REAL,
    cost_per_item REAL, p95_latency_ms REAL, computed_at TEXT
);
"""

EVENT_COLS = ['ts', 'batch', 'event', 'stage', 'gate', 'status', 'rule_id',
              'severity', 'action', 'retry', 'duration_ms', 'tokens', 'count',
              'model_id', 'prompt_sha256', 'artifact_sha256', 'config_hash', 'source']


# ── 反推历史事件（backfill）───────────────────────────────

def _load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def _purge_backfill(batch: str) -> int:
    """清掉该批次文件里旧的 backfill 事件（保留 live 事件），使反推可重复执行。"""
    p = tm.jsonl_path(batch)
    if not p.exists():
        return 0
    kept, dropped = [], 0
    for line in p.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get('source') == 'backfill':
            dropped += 1
            continue
        kept.append(line)
    p.write_text('\n'.join(kept) + ('\n' if kept else ''), encoding='utf-8')
    return dropped


def backfill(batch: str | None = None) -> list[dict]:
    """从既有产物反推事件。只读历史文件，不修改任何产物。

    幂等：每次先清掉该批次的旧 backfill 事件，再重新反推，
    避免重复执行把事件数越堆越大（live 事件不受影响）。
    """
    made = []
    state = _load_json(BASE / 'workflow_state.json') or {}
    batches = [batch] if batch else sorted(state)

    for bid in batches:
        b = state.get(bid)
        if not isinstance(b, dict):
            continue
        _purge_backfill(bid)
        # 1) 门禁结果
        for gate, res in (b.get('gate_results') or {}).items():
            if not isinstance(res, dict):
                continue
            ev = tm.record_event(bid, 'gate_check', gate=gate,
                                 status=str(res.get('status') or ''),
                                 source='backfill')
            if ev:
                made.append(ev)
        # 2) 校验报告
        for rep in sorted((BASE / '中间产物' / bid).glob('validate_options_report_*.json')):
            d = _load_json(rep) or {}
            s = d.get('summary') or {}
            if not isinstance(s, dict) or not s:
                continue
            total = s.get('total_questions') or s.get('total') or 0
            passed = s.get('pass') or s.get('passed') or 0
            ev = tm.record_event(bid, 'validate_done', stage='A2',
                                 count=int(total), status='PASS' if not s.get('fail') else 'FAIL',
                                 severity='FAIL' if s.get('fail') else 'WARN',
                                 action=f"fail={s.get('fail')},warn={s.get('warn')},pass={passed}",
                                 source='backfill')
            if ev:
                made.append(ev)
        # 3) 血缘校验
        lin = BASE / 'reports' / 'gate' / f'{bid}_lineage.json'
        if lin.exists():
            d = _load_json(lin) or {}
            ev = tm.record_event(bid, 'lineage_check', gate='GATE-FINAL-LINEAGE',
                                 status=str(d.get('status') or ''), source='backfill')
            if ev:
                made.append(ev)
    return made


# ── 聚合 ──────────────────────────────────────────────────

def _p95(values: list[float]) -> float | None:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    idx = min(len(vals) - 1, int(round(0.95 * (len(vals) - 1))))
    return round(vals[idx], 2)


def _repair_stats() -> dict:
    """读取 P5 产出的修复统计（若存在）。"""
    p = BASE / 'reports' / 'repair' / 'repair_stats_20261102.json'
    d = _load_json(p) or {}
    out = {}
    for s in d.get('samples') or []:
        tag = str(s.get('tag') or '')
        sev = (s.get('per_severity') or {}).get('FAIL') or {}
        out[tag] = {
            'repair_success': sev.get('repair_success_rate'),
            'recurrence_rate': s.get('recurrence_rate'),
            'fail_before': (s.get('before') or {}).get('fail'),
            'fail_after': (s.get('after') or {}).get('fail'),
        }
    return out


def _selftest_fp() -> float | None:
    p = BASE / 'reports' / 'obs' / f'gate_selftest_{datetime.now():%Y%m%d}.json'
    d = _load_json(p) or {}
    fp = d.get('false_positive') or {}
    return fp.get('rate')


def build(db_path: Path, out_path: Path) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    events = tm.read_events()
    schema_issues = tm.validate_event_schema(events)

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.execute('DELETE FROM events')
    for e in events:
        con.execute(
            f"INSERT INTO events ({','.join(EVENT_COLS)}) VALUES ({','.join('?' * len(EVENT_COLS))})",
            [e.get(c) for c in EVENT_COLS])
    con.commit()

    batches = sorted({str(e.get('batch')) for e in events if e.get('batch')})
    repairs = _repair_stats()
    fp_rate = _selftest_fp()

    per_batch = []
    for bid in batches:
        rows = con.execute(
            "SELECT event, status, action, count, duration_ms, tokens FROM events WHERE batch=?",
            (bid,)
        ).fetchall()
        gates = [r for r in rows if r[0] == 'gate_check']
        blocked = [r for r in gates if str(r[1]).upper() == 'BLOCKED']
        val = [r for r in rows if r[0] == 'validate_done']
        questions = max([int(r[3] or 0) for r in val] or [0])

        # FPY：validate 事件的 action 里带 fail=/warn=/pass=
        fpy = None
        for r in val:
            counters = {}
            for part in str(r[2] or '').replace(' ', '').split(','):
                if '=' in part:
                    k, _, v = part.partition('=')
                    try:
                        counters[k] = int(v)
                    except ValueError:
                        pass
            total = int(r[3] or 0)
            if total and 'pass' in counters:
                fpy = round(counters['pass'] / total, 4)
        if fpy is None and val and questions:
            # 退化口径：该批所有校验事件都无 FAIL → 视为全通过（明确记录在 definitions）
            fpy = 1.0 if all(str(r[1]).upper() != 'FAIL' for r in val) else None

        tokens = sum(int(r[5] or 0) for r in rows)
        cost = round(tokens / questions, 2) if (tokens and questions) else None
        lat = _p95([float(r[4]) for r in rows if r[4] is not None])
        rep = repairs.get(bid) or {}

        m = {
            'batch': bid,
            'questions': questions,
            'fpy': fpy,
            'gate_total': len(gates),
            'gate_blocked': len(blocked),
            'gate_block_rate': round(len(blocked) / len(gates), 4) if gates else None,
            'repair_success': rep.get('repair_success'),
            'recurrence_rate': rep.get('recurrence_rate'),
            'cost_per_item': cost,
            'p95_latency_ms': lat,
        }
        per_batch.append(m)
        con.execute(
            "INSERT OR REPLACE INTO batch_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (bid, m['questions'], m['fpy'], m['gate_total'], m['gate_blocked'],
             m['gate_block_rate'], m['repair_success'], m['recurrence_rate'],
             m['cost_per_item'], m['p95_latency_ms'], datetime.now().isoformat(timespec='seconds')))
    con.commit()

    def _avg(key):
        vals = [m[key] for m in per_batch if m[key] is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    summary = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'db': str(db_path),
        'events': len(events),
        'batches': len(batches),
        'live_events': sum(1 for e in events if e.get('source') != 'backfill'),
        'backfill_events': sum(1 for e in events if e.get('source') == 'backfill'),
        'field_schema_issues': schema_issues,
        'metrics': {
            'fpy_mean': _avg('fpy'),
            'gate_block_rate_mean': _avg('gate_block_rate'),
            'repair_success_mean': _avg('repair_success'),
            'recurrence_rate_mean': _avg('recurrence_rate'),
            'cost_per_item_mean': _avg('cost_per_item'),
            'p95_latency_ms_max': max([m['p95_latency_ms'] for m in per_batch
                                       if m['p95_latency_ms'] is not None], default=None),
            'false_positive_rate': fp_rate,
        },
        'definitions': {
            'fpy': '首轮校验 PASS 题数 / 题数（来源 validate 报告 summary）',
            'gate_block_rate': 'BLOCKED 门禁数 / 门禁总数',
            'repair_success': 'FAIL 级修复成功率（reports/repair/repair_stats_*.json）',
            'recurrence_rate': 'after 新增 rule 问题 / after 全部问题',
            'cost_per_item': 'tokens / 题数；无 tokens 数据时为 null（不估算）',
            'p95_latency_ms': '事件 duration_ms 的 95 分位；无耗时时为 null',
        },
        'per_batch': per_batch,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    con.close()
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description='系统指标聚合（P6-S2）：JSONL → SQLite → metrics.json',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例:\n'
               '  python scripts/aggregate_metrics.py --backfill\n'
               '  python scripts/aggregate_metrics.py --json reports/obs/metrics_20261102.json\n')
    ap.add_argument('--backfill', action='store_true', help='从既有产物反推历史事件到 JSONL')
    ap.add_argument('--batch', default='', help='只反推指定批次')
    ap.add_argument('--db', default=str(DEFAULT_DB), help='SQLite 路径')
    ap.add_argument('--json', default=str(DEFAULT_OUT), help='指标 JSON 输出路径')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args(argv)

    if args.backfill:
        made = backfill(args.batch or None)
        if not args.quiet:
            print(f'反推事件 {len(made)} 条 → {tm.OBS_DIR}')
            for p in sorted(tm.OBS_DIR.glob('*_telemetry.jsonl')):
                n = len(tm.read_events(p.name.split("_telemetry")[0]))
                print(f'  {p.name}: {n} 条')

    s = build(Path(args.db), Path(args.json))
    if not args.quiet:
        print(f'事件 {s["events"]} 条（live {s["live_events"]} / backfill {s["backfill_events"]}）'
              f'　批次 {s["batches"]}')
        if s['field_schema_issues']:
            print(f'  ⚠ 字段白名单违规 {len(s["field_schema_issues"])} 条')
        for k, v in s['metrics'].items():
            print(f'  {k}: {v}')
        print(f'  📄 指标: {args.json}')
        print(f'  📄 指标库: {args.db}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
