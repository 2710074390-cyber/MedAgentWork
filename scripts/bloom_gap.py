#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bloom_gap.py — Bloom 补题计划（2026-11-03）。

用途：
  1. 出题前：按教师重点目标（默认 记忆/理解/应用/分析 = 20/20/45/15）计算每层应出多少题；
  2. 出题后：对比实际分布，给出「补哪些层、补多少题、可替换哪些层」的建议；
  3. 并入 100 题大卷前：改用蓝图目标（10/25/35/20）重新计算。

用法：
  python scripts/bloom_gap.py --file <题库JSON> --target 20,20,45,15
  python scripts/bloom_gap.py --file <题库JSON> --target 10,25,35,20 --out reports/validate/bloom_gap.md
"""
from __future__ import annotations

import argparse
import json
import math
import sys

# UTF-8 输出兜底（2026-11-03）：Windows 默认 GBK 控制台下 emoji 会抛 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LEVELS = ('记忆', '理解', '应用', '分析')


def _target_counts(n: int, target_pct: list[float]) -> dict[str, int]:
    """按目标百分比分配整数题数（最大余数法，保证总和 = n）。"""
    raw = [n * p / 100.0 for p in target_pct]
    base = [int(math.floor(x)) for x in raw]
    remain = n - sum(base)
    order = sorted(range(len(raw)), key=lambda i: (raw[i] - base[i]), reverse=True)
    for i in order[:remain]:
        base[i] += 1
    return dict(zip(LEVELS, base))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Bloom 补题计划')
    ap.add_argument('--file', required=True, help='题库 JSON（数组）')
    ap.add_argument('--target', default='20,20,45,15',
                    help='目标百分比：记忆,理解,应用,分析（默认教师重点 20/20/45/15）')
    ap.add_argument('--out', default='', help='Markdown 输出路径')
    args = ap.parse_args(argv)

    try:
        items = json.loads(Path(args.file).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'✗ 无法读取 {args.file}: {exc}')
        return 2
    if not isinstance(items, list) or not items:
        print('✗ 输入必须是非空题目数组')
        return 2
    total = len(items)
    try:
        pct = [float(x.strip()) for x in str(args.target).split(',')]
    except ValueError:
        print('✗ --target 格式应为 20,20,45,15')
        return 2
    if len(pct) != len(LEVELS) or sum(pct) <= 0:
        print('✗ --target 需要 4 个正数，分别对应 记忆/理解/应用/分析')
        return 2

    actual = {level: sum(1 for q in items if str(q.get('bloom') or '') == level) for level in LEVELS}
    target_counts = _target_counts(total, pct)
    rows = []
    for level, want in target_counts.items():
        have = actual[level]
        delta = want - have
        rows.append((level, have, want, delta))

    print(f'题库：{args.file}（{total} 题）')
    print(f'目标：{" / ".join(str(x) for x in pct)}（记忆/理解/应用/分析）')
    print('| 层级 | 现有 | 目标 | 差额 |')
    print('|---|---:|---:|---:|')
    for level, have, want, delta in rows:
        print(f'| {level} | {have} | {want} | {delta:+d} |')
    gaps = [(level, delta) for level, _, _, delta in rows if delta > 0]
    if gaps:
        print('\n补题建议：' + '；'.join(f'{level} 补 {n} 题' for level, n in gaps))
        surplus = [(level, -delta) for level, _, _, delta in rows if delta < 0]
        if surplus:
            print('可替换：' + '；'.join(f'{level} 减 {n} 题' for level, n in surplus))
    else:
        print('\n✅ 已达到目标分布，无需补题。')

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = [f'# Bloom 补题计划（{Path(args.file).name}）', '',
                 f'- 题量：{total}',
                 f'- 目标：{" / ".join(str(x) for x in pct)}（记忆/理解/应用/分析）', '',
                 '| 层级 | 现有 | 目标 | 差额 |', '|---|---:|---:|---:|']
        lines += [f'| {level} | {have} | {want} | {delta:+d} |' for level, have, want, delta in rows]
        if gaps:
            lines += ['', '## 补题', '',
                      '；'.join(f'{level} 补 {n} 题' for level, n in gaps) + '。']
            surplus = [(level, -delta) for level, _, _, delta in rows if delta < 0]
            if surplus:
                lines += ['', '可优先从超配层替换：' + '；'.join(f'{level} 减 {n} 题' for level, n in surplus) + '。']
        else:
            lines += ['', '已达到目标分布，无需补题。']
        lines += ['', '> 并入 100 题大卷时，请以蓝图目标（默认 10/25/35/20）重新运行本工具。', '']
        out.write_text('\n'.join(lines), encoding='utf-8')
        print(f'📄 计划已写入：{out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
