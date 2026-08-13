#!/usr/bin/env python3
"""Bloom 认知层级实时采样器 v1.0 — 每50题采样，偏差>15%→halt"""
import json, sys, re, argparse
from pathlib import Path
from collections import Counter
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = Path(__file__).parent

DEFAULT_TARGET = {'记忆': 30.0, '理解': 40.0, '应用': 25.0, '分析': 5.0}
BLOOM_ALIASES = {
    '记忆': '记忆', '回忆': '记忆', '识记': '记忆', '记忆型': '记忆',
    '理解': '理解', '领会': '理解', '理解型': '理解',
    '应用': '应用', '运用': '应用', '应用型': '应用',
    '分析': '分析', '综合': '分析', '评价': '分析', '分析型': '分析',
}

def parse_questions(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data if isinstance(data, list) else []

def extract_bloom_level(q):
    bloom = q.get('bloom') or q.get('bloom_level') or q.get('cognitive_level', '')
    if not bloom:
        qtype = q.get('type') or q.get('question_type', '')
        if qtype in ('A3', 'A4'): return '分析'
        elif qtype == 'A2': return '应用'
        elif qtype == 'B1': return '理解'
        elif qtype == 'A1': return '记忆'
        return None
    return BLOOM_ALIASES.get(str(bloom).strip(), str(bloom).strip())

def sample_bloom(questions, target=None):
    if target is None: target = DEFAULT_TARGET
    total = len(questions)
    if total == 0: return {}, {}, {}
    counter = Counter()
    for q in questions:
        level = extract_bloom_level(q)
        if level: counter[level] += 1
    actual = {}
    for level in ['记忆', '理解', '应用', '分析']:
        actual[level] = counter.get(level, 0) / total * 100
    deviations = {}
    for level in ['记忆', '理解', '应用', '分析']:
        deviations[level] = actual.get(level, 0) - target.get(level, 0)
    recs = []
    if deviations.get('记忆', 0) > 15:
        recs.append({'action': 'HALT_A1', 'reason': f'记忆层 {actual["记忆"]:.1f}% vs 目标 {target["记忆"]}%，偏差 +{deviations["记忆"]:.1f}%', 'fix': '后续禁止A1型题，全部转为A2/A3/B1/X型'})
    if deviations.get('应用', 0) < -10:
        recs.append({'action': 'INCREASE_A2_A3', 'reason': f'应用层不足', 'fix': '后续每10题至少3题为A2/A3'})
    return actual, deviations, recs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', help='批次ID')
    parser.add_argument('--file', help='题库JSON路径')
    parser.add_argument('--threshold', type=float, default=15.0)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    filepath = None
    if args.file:
        filepath = Path(args.file)
    elif args.batch:
        d = BASE / '最终产物' / args.batch
        if d.exists():
            candidates = sorted(d.glob('ALL_questions*.json'))
            if candidates: filepath = candidates[-1]
        if not filepath:
            d2 = BASE / '中间产物' / args.batch
            if d2.exists():
                candidates = sorted(d2.glob('ALL_questions*.json'))
                if candidates: filepath = candidates[-1]
        if filepath: print(f"[{args.batch}] {filepath.name}", file=sys.stderr)
    if not filepath or not filepath.exists():
        print(f"ERROR: 找不到批次 {args.batch} 的题库文件", file=sys.stderr)
        sys.exit(2)
    questions = parse_questions(filepath)
    if not questions:
        print("ERROR: 无题目", file=sys.stderr)
        sys.exit(2)
    total = len(questions)
    sampled = questions[: (total // 50) * 50] if total > 100 else questions
    actual, deviations, recs = sample_bloom(sampled)
    max_dev = max(abs(v) for v in deviations.values())
    passed = max_dev <= args.threshold
    if args.json:
        print(json.dumps({
            'total': total, 'sampled': len(sampled),
            'actual': {k: round(v, 1) for k, v in actual.items()},
            'deviations': {k: round(v, 1) for k, v in deviations.items()},
            'max_dev': round(max_dev, 1), 'passed': passed,
            'recs': recs
        }, ensure_ascii=False, indent=2))
    else:
        print(f"{'层级':<8} {'实际%':>8} {'目标%':>8} {'偏差':>8} {'状态':>8}")
        print("-" * 45)
        for lv in ['记忆', '理解', '应用', '分析']:
            a = actual.get(lv, 0); t = DEFAULT_TARGET[lv]; d = deviations[lv]
            s = '⚠️超标' if abs(d) > 15 else ('⚡不足' if d < -10 else '✅正常')
            print(f"{lv:<8} {a:>7.1f}% {t:>7.1f}% {d:>+7.1f}% {s:>8}")
        print(f"\n最大偏差: {max_dev:.1f}% → {'PASS' if passed else 'BLOCKED'}")
        for r in recs:
            print(f"  [{r['action']}] {r['reason']}")
    sys.exit(0 if passed else 1)

if __name__ == '__main__':
    main()
