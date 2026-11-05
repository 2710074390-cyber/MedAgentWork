#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批次签收（可选）：把交付题库的 release 状态由「待人工」转为「可发布」，并留签收回执。

batch048+ 额外前置：HC-22 配额 / R0–R3 质量门禁 / P9 模式元数据 / Bloom 目标必须通过。

2026-11-03 政策：A/B 级 + 确定性门禁通过默认 publishable，签收不再是发布必需环节；
本脚本保留为可选的批次级授权留痕。

这不是「把字段改成 publishable 就算完」，而是把一次人工授权动作固化成可审计记录：

  前置（任一不满足即拒绝，不做部分签收）
    1. 批次存在于 workflow_state；
    2. 四道确定性门禁 GATE-A2/A3/A4/FINAL 均为 PASS；
    3. 最终产物 `ALL_questions_FIXED*.json` 存在且唯一；
    4. 每题 evidence_grade ∈ {A, B}；无「高风险 + C 级」题（HC-28 要求这类必须 quarantined）。

  动作
    - `release.disposition → publishable`、`reason_code → NONE`；
    - `human_check` 写清「谁、何时、依据什么、没做什么」——签收是发布授权，不等于医学正确性背书；
    - `evidence_grade` **不动**：签收不能把 B 升成 A，等级取决于证据本身；
    - 批次 `status → APPROVED`，并写入 `signoff` 记录；
    - 签收前先把 FIXED 备份到 `.tmp/`，便于回溯。

  之后必须重跑（脚本会打印命令，不代跑，避免隐式改证据）
    build_a4_report.py → ingest.py --stage agent4 → gate_check --stage agent4_done → --stage final

用法
    python scripts/signoff_batch.py --batch batch047 --by "用户本人（项目负责人）" --note "…"
    python scripts/signoff_batch.py --batch batch047 --by "…" --dry-run   # 只看会改什么
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'scripts'))
import workflow_state as ws  # noqa: E402

REQUIRED_GATES = ('GATE-A2', 'GATE-A3', 'GATE-A4', 'GATE-FINAL')
PUBLISHABLE_GRADES = ('A', 'B')
DEFAULT_HUMAN_CHECK = (
    '{by} 于 {ts} 签收本批 {n} 题。依据 HC-28（2026-11-03 修订）：A/B 级 + 确定性门禁'
    '通过默认可发布，**逐题人工医学核验不设为发布前置**；本签收仅作批次级发布授权留痕，'
    '不构成医学正确性背书。'
)
DEFAULT_ACTION = '已签收授权发布；归档至 archive/ 并纳入公开题库索引'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def write_note(batch_id: str, batch: dict, final_dir: Path) -> Path:
    """生成人可读的签收回执（Markdown）。内容全部取自 workflow_state 与实际文件，不手填。"""
    so = batch.get('signoff') or {}
    fixed = final_dir / 'ALL_questions_FIXED.json'
    items = json.loads(fixed.read_text(encoding='utf-8'))
    grades = sorted({str((q.get('release') or {}).get('evidence_grade')) for q in items})
    risks = sorted({str((q.get('release') or {}).get('risk_level')) for q in items})
    gates = batch.get('gate_results') or {}
    lineage = batch.get('lineage') or []

    L = [
        f'# {batch_id} 签收回执',
        '',
        '| 项 | 内容 |',
        '|---|---|',
        f"| 签收人 | {so.get('signed_by', '')} |",
        f"| 签收时间 | {so.get('signed_at', '')} |",
        f"| 签收范围 | {so.get('scope', '')} |",
        f"| 签收依据 | {so.get('basis', '')} |",
        f"| 签收说明 | {so.get('note') or '（无）'} |",
        '',
        '## 交付物',
        '',
        '| 文件 | SHA256 | 大小 |',
        '|---|---|---|',
    ]
    for p in sorted(final_dir.iterdir()):
        if not p.is_file():
            continue
        L.append(f'| `{p.name}` | `{sha256(p)[:16]}…` | {p.stat().st_size:,} B |')

    L += ['', '## 门禁结论', '', '| 门禁 | 状态 | 说明 |', '|---|---|---|']
    for g in REQUIRED_GATES:
        info = gates.get(g) or {}
        L.append(f"| {g} | {info.get('status', '—')} | {info.get('reason', '')} |")

    L += [
        '',
        '## 证据链',
        '',
        f'- 血缘记录 {len(lineage)} 条：' + '、'.join(
            f"{x.get('stage')}（{str(x.get('artifact_sha256'))[:12]}…）" for x in lineage),
        f"- 签收前交付 sha：`{so.get('delivery_sha256_before', '')}`",
        f"- 签收后交付 sha：`{so.get('delivery_sha256_after', '')}`",
        f"- 签收前备份：`{so.get('backup', '')}`",
        f"- 证据等级：{'、'.join(grades)}（签收不升级等级）｜风险：{'、'.join(risks)}",
        '',
        '## 未完成项（签收不覆盖）',
        '',
    ]
    for x in (so.get('not_done') or []):
        L.append(f'- {x}')
    L += [
        '- 由此 AC-P3-02（κ≥0.61）仍为开项，签收不改变该结论。',
        '',
        '> 本回执证明的是**发布授权**，不是医学正确性背书。HC-28：`release_status=READY` 仅表示发布门槛已过；'
        '临床使用中如发现错误，应回溯本回执的签收人与交付 sha，按修订流程处理，不得就地改文件。',
        '',
    ]
    out = final_dir / f'{batch_id}_签收单.md'
    out.write_text('\n'.join(L), encoding='utf-8')
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description='批次签收（release → publishable）')
    ap.add_argument('--batch', required=True)
    ap.add_argument('--by', default='', help='签收人（写实，不能留空或写「用户」）')
    ap.add_argument('--note', default='', help='签收依据/说明，可留空')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--note-only', action='store_true',
                    help='仅按现有 signoff 记录重生成签收回执 MD，不改任何 release 字段')
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

    if args.note_only:
        if not batch.get('signoff'):
            print(f'✗ 批次 {batch_id} 尚无签收记录，无法生成回执')
            return 2
        out = write_note(batch_id, batch, BASE / '最终产物' / batch_id)
        print(f'签收回执: {out.relative_to(BASE)}')
        return 0

    if not args.by.strip() or args.by.strip() in ('用户', 'user', '本人'):
        print('✗ 签收人必填且须写实（不能留空或写「用户/本人」）')
        return 2

    # ── 前置 1：门禁 ──
    gates = batch.get('gate_results') or {}
    failed = [g for g in REQUIRED_GATES
              if str((gates.get(g) or {}).get('status', '')).upper() != 'PASS']
    if failed:
        print(f'✗ 门禁未全部通过，拒绝签收：{failed}')
        for g in failed:
            print(f'    {g}: {(gates.get(g) or {}).get("status", "缺失")}')
        return 3

    # ── 前置 1.5：batch048+ 的发布前置契约（HC-22 / R0–R3 / P9 / Bloom）──
    try:
        import re as _re
        _num = _re.fullmatch(r'batch(\d+)(?:-[A-Za-z0-9]+)?', str(batch_id))
        if _num and int(_num.group(1)) >= 48:
            import gate_check as _gc
            for fn in (_gc.check_real_question_quota, _gc.check_quality_stages,
                       _gc.check_p9_metadata, _gc.check_bloom_target):
                r = fn(batch_id, batch)
                if r.get('status') == 'BLOCKED':
                    print(f"✗ 发布前置契约未满足（{r.get('gate_sub')}）：{r.get('reason')}")
                    return 5
                print(f"  ✅ {r.get('gate_sub')}: {r.get('status')}")
    except Exception as exc:
        print(f'✗ 发布前置契约检查失败：{type(exc).__name__}: {exc}')
        return 5

    # ── 前置 2：交付文件 ──
    final_dir = BASE / '最终产物' / batch_id
    cands = sorted(final_dir.glob('ALL_questions_FIXED*.json')) if final_dir.is_dir() else []
    if len(cands) != 1:
        print(f'✗ 最终产物缺失或存在歧义（{len(cands)} 个）')
        return 3
    fixed = cands[0]
    items = json.loads(fixed.read_text(encoding='utf-8'))
    if not isinstance(items, list) or not items:
        print('✗ 交付 JSON 不是非空数组')
        return 3

    # ── 前置 3：证据分级（HC-28 发布底线）──
    problems = []
    for q in items:
        rel = q.get('release') or {}
        grade = str(rel.get('evidence_grade') or '').upper()
        risk = str(rel.get('risk_level') or '').lower()
        if grade not in PUBLISHABLE_GRADES:
            problems.append(f"{q.get('id')}: evidence_grade={grade or '缺失'}")
        elif grade == 'C' and risk == 'high':
            problems.append(f"{q.get('id')}: 高风险 + C 级，应 quarantined")
    if problems:
        print(f'✗ 不满足 HC-28 发布底线（{len(problems)} 题）：')
        for p in problems[:10]:
            print(f'    - {p}')
        return 4

    before_sha = sha256(fixed)
    ts = datetime.now().isoformat(timespec='seconds')
    human_check = DEFAULT_HUMAN_CHECK.format(by=args.by, ts=ts, n=len(items))
    if args.note:
        human_check += f' 签收说明：{args.note}'

    print(f'批次      : {batch_id}（{len(items)} 题）')
    print(f'交付文件  : {fixed.relative_to(BASE)}')
    print(f'签收前 sha: {before_sha}')
    print(f'签收人    : {args.by}')
    print(f'证据等级  : {sorted({str((q.get("release") or {}).get("evidence_grade")) for q in items})}（不升级）')
    print(f'门禁      : {", ".join(f"{g}=PASS" for g in REQUIRED_GATES)}')

    if args.dry_run:
        will = sum(1 for q in items if (q.get('release') or {}).get('disposition') != 'publishable')
        print(f'\n[dry-run] 将改 disposition 的题数: {will}；不写任何文件')
        return 0

    # ── 备份 ──
    (BASE / '.tmp').mkdir(exist_ok=True)
    backup = BASE / '.tmp' / f'{batch_id}_fixed_before_signoff.json'
    shutil.copy2(fixed, backup)

    # ── 改 release ──
    changed = 0
    for q in items:
        rel = q.setdefault('release', {})
        if rel.get('disposition') == 'publishable':
            continue
        rel['disposition'] = 'publishable'
        rel['reason_code'] = 'NONE'
        rel['human_check'] = human_check
        rel['suggested_action'] = DEFAULT_ACTION
        changed += 1
    fixed.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding='utf-8')
    after_sha = sha256(fixed)

    # ── 批次状态 + 签收回执 ──
    batch['status'] = 'APPROVED'
    batch['signoff'] = {
        'signed_by': args.by,
        'signed_at': ts,
        'scope': f'{len(items)} 题（{batch_id}）',
        'basis': (f"HC-28 发布底线：证据 {'/'.join(sorted({str((q.get('release') or {}).get('evidence_grade')) for q in items}))}"
                  f" / 风险 {'/'.join(sorted({str((q.get('release') or {}).get('risk_level')) for q in items}))}"
                  f" / 四道确定性门禁 PASS（2026-11-03 起不再要求逐题人工核验）"),
        # 2026-11-03：逐题医学核验不再是未完成项；只保留真正未做的第二评分者/κ
        'not_done': ['第二评分者盲评（κ 不可计算）'],
        'note': args.note,
        'delivery_file': fixed.relative_to(BASE).as_posix(),
        'delivery_sha256_before': before_sha,
        'delivery_sha256_after': after_sha,
        'backup': backup.relative_to(BASE).as_posix(),
    }
    ws.save_state(state)

    print(f'签收后 sha: {after_sha}')
    print(f'改 disposition: {changed} 题；批次 status → APPROVED')
    print(f'备份      : {backup.relative_to(BASE)}')
    note = write_note(batch_id, batch, final_dir)
    print(f'签收回执  : {note.relative_to(BASE)}')
    print('\n下一步（必须按序，否则 A4 追溯日志的 source_sha256 会失配）：')
    print('  python 中间产物/batch047/build_a4_report.py')
    print('  "C:/Users/38063/AppData/Local/Programs/Python/Python312/python.exe" ingest.py \\')
    print(f'    中间产物/{batch_id}/AGENT4_追溯日志.json --batch {batch_id} --stage agent4 \\')
    print('    --model "DeepSeek-V4.1-Flash" --prompt-version "MedFix_current_prompt"')
    print(f'  python gate_check.py --batch {batch_id} --stage agent4_done')
    print(f'  python gate_check.py --batch {batch_id} --stage final')
    # P1-3：入库必须排在回执重建之后 —— 签收改了 FIXED 字节，回执按旧字节写的话，
    # 提交上去就是一份「产物与回执对不上」的证据，CI 会判 ARTIFACT_MISMATCH。
    print('\n入库（务必在回执重建后执行，否则会提交过期回执）：')
    print(f'  python scripts/batch_artifacts.py stage --batch {batch_id}')
    print(f'  python scripts/batch_artifacts.py check --batch {batch_id}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
