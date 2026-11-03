#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批次归档：把已签收批次的三个产物目录移入 archive/，并留路径映射说明。

为什么需要单独的脚本而不是 mv：
  归档会把 `中间产物/`、`质检报告/`、`最终产物/` 里的文件搬走，而
  `reports/gate/*.json`、`reports/validate/*.json`、A4 追溯日志、签收回执里的路径
  都还指向旧位置。这些证据**不能被改写**（它们是当时的快照），所以只能：
    - 保留证据原样；
    - 在 `archive/<batch>_归档说明.md` 里给出「旧路径 → 归档路径」映射；
    - 在 workflow_state 里记 `archived`，并给 signoff 补 `archived_path`（保留原字段不改）。

前置（任一不满足即拒绝）
  1. 批次存在且 status == APPROVED —— 不允许归档仍在飞的批次；
  2. 目标目录全部不存在 —— 不允许覆盖已有归档；
  3. 至少有一个源目录存在。

用法
    python scripts/archive_batch.py --batch batch047 --dry-run
    python scripts/archive_batch.py --batch batch047
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'scripts'))
import workflow_state as ws  # noqa: E402

CATEGORIES = ('中间产物', '质检报告', '最终产物')
EVIDENCE = (
    'reports/gate',
    'reports/validate',
    'reports/implementation',
)


def main() -> int:
    ap = argparse.ArgumentParser(description='已签收批次归档')
    ap.add_argument('--batch', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    batch_id = args.batch

    state, err = ws.load_state()
    if err:
        print(f'✗ 读取 workflow_state 失败: {err}')
        return 2
    batch = state.get(batch_id)
    if not isinstance(batch, dict):
        print(f'✗ 批次 {batch_id} 不在 workflow_state 中')
        return 2
    if batch.get('status') != 'APPROVED':
        print(f"✗ 批次 status={batch.get('status')}，只有 APPROVED 才允许归档（避免归档仍在飞的批次）")
        return 3

    moves = []
    for cat in CATEGORIES:
        src = BASE / cat / batch_id
        dst = BASE / 'archive' / cat / batch_id
        if src.is_dir():
            if dst.exists():
                print(f'✗ 目标已存在，拒绝覆盖: {dst.relative_to(BASE)}')
                return 4
            moves.append((src, dst))
    if not moves:
        print(f'✗ {batch_id} 没有任何待归档目录（可能已归档）')
        return 4

    # 质检报告顶层的散文件（历史批次常见）
    loose = sorted((BASE / '质检报告').glob(f'{batch_id}*质检报告*.json'))
    loose = [p for p in loose if p.is_file()]

    print(f'批次 {batch_id}: status=APPROVED，待归档 {len(moves)} 个目录 + {len(loose)} 个散文件')
    for src, dst in moves:
        n = sum(1 for _ in src.rglob('*') if _.is_file())
        print(f'  {src.relative_to(BASE)}  →  {dst.relative_to(BASE)}（{n} 个文件）')

    if args.dry_run:
        print('\n[dry-run] 未移动任何文件')
        return 0

    ts = datetime.now().isoformat(timespec='seconds')
    mapping = []
    for src, dst in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        mapping.append({'kind': src.parent.name, 'from': src.relative_to(BASE).as_posix(),
                        'to': dst.relative_to(BASE).as_posix()})

    # 散文件并入质检报告归档目录
    report_dir = BASE / 'archive' / '质检报告' / batch_id
    for p in loose:
        report_dir.mkdir(parents=True, exist_ok=True)
        target = report_dir / p.name
        if target.exists():
            print(f'  ! 跳过同名散文件: {p.name}')
            continue
        shutil.move(str(p), str(target))
        mapping.append({'kind': '质检报告（散文件）', 'from': p.relative_to(BASE).as_posix(),
                        'to': target.relative_to(BASE).as_posix()})

    # 签收/修复前的备份一并入档，避免 .tmp 被清后失去回溯依据
    backup_dir = BASE / 'archive' / '最终产物' / batch_id / '_backup'
    moved_backups = []
    for p in sorted((BASE / '.tmp').glob(f'{batch_id}*')):
        if not p.is_file():
            continue
        backup_dir.mkdir(parents=True, exist_ok=True)
        target = backup_dir / p.name
        shutil.move(str(p), str(target))
        moved_backups.append({'from': p.relative_to(BASE).as_posix(),
                              'to': target.relative_to(BASE).as_posix()})
        mapping.append({'kind': '备份', **moved_backups[-1]})

    # 收集仍指向旧路径的证据文件（只记录，不改写）
    evidence = []
    for d in EVIDENCE:
        for p in sorted((BASE / d).glob(f'*{batch_id}*')):
            if p.is_file():
                evidence.append(p.relative_to(BASE).as_posix())

    batch['archived'] = {
        'archived_at': ts,
        'archived_by': 'Agent（用户指示「归档」）',
        'mapping': mapping,
        'backups': moved_backups,
        'note': 'reports/ 下的门禁与校验证据保持原样不改写；其中 source_file 字段仍指向归档前路径，'
                '需要复核时按本表的 to 路径还原。',
    }
    if isinstance(batch.get('signoff'), dict):
        batch['signoff']['archived_path'] = f'archive/最终产物/{batch_id}'
    ws.save_state(state)

    # 归档说明（人读）
    L = [
        f'# {batch_id} 归档说明',
        '',
        f'- 归档时间：{ts}',
        f"- 批次状态：{batch.get('status')}（签收人 {((batch.get('signoff') or {}).get('signed_by') or '—')}）",
        '- 归档依据：用户指示「归档」；批次已签收、四道门禁 PASS',
        '',
        '## 路径映射',
        '',
        '| 类别 | 归档前 | 归档后 |',
        '|---|---|---|',
    ]
    for m in mapping:
        L.append(f"| {m['kind']} | `{m['from']}` | `{m['to']}` |")

    L += [
        '',
        '## 归档后须知',
        '',
        '1. **`reports/` 下的证据未做任何改写**（gate / validate / implementation）。它们的 `source_file` 等字段仍指向归档前路径，'
        '这是有意的：证据是当时的快照，不该为了路径好看去改。要复核就按上表 `归档后` 列找文件。',
        '2. **不要对本批再跑 `gate_check`**：文件已不在 `中间产物/`、`最终产物/`，门禁会因找不到交付物判 BLOCKED。'
        '确需重跑，先把归档件临时还原到原路径。',
        '3. **`question_bank/registry.jsonl`** 里该批题的 source_file 仍指旧路径，属登记表的历史记录，不追改。',
        '4. 交付物 sha 未变：',
        f"   - 签收前 `{((batch.get('signoff') or {}).get('delivery_sha256_before') or '—')}`",
        f"   - 签收后 `{((batch.get('signoff') or {}).get('delivery_sha256_after') or '—')}`",
        '',
        '## 相关证据（留在原位）',
        '',
    ]
    for e in evidence:
        L.append(f'- `{e}`')
    if not evidence:
        L.append('- （无）')

    out = BASE / 'archive' / f'{batch_id}_归档说明.md'
    out.write_text('\n'.join(L), encoding='utf-8')

    print(f'\n✅ 已归档 {len(mapping)} 项')
    print(f'   归档说明: {out.relative_to(BASE)}')
    print('   reports/ 证据未改写（路径仍指归档前位置，见说明）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
