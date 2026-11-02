#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_selftest.py — 门禁自测：黄金缺陷集检出率与误报率（P6-S3）。

为什么要有这个：
    规则改错了没人知道。`validate_options` 的 R1–R13 历史上出现过
    「分支恒为假、永不执行」的死代码（R1 的括号后缀分支），却因为
    从来没有一份「一定会被抓住的坏样本」而长期无人发现。
    本脚本用固定的黄金缺陷集回归门禁本身：**检出率掉了 = 规则坏了**。

缺陷集：`tests/fixtures/defects/defects.json`
    - 10 类缺陷 × 每类 ≥3 例（合成样本，不含真实考题答案）；
    - 5 条「应零问题」的好题，用于误报率。

指标
----
检出率 = 命中的例数 / 该类例数（命中 = 该题上报了预期规则）
hard 检出率 = 仅统计 severity=FAIL 的缺陷类
误报率 = 好题中被上报**任意问题**的题目 / 好题数（另单列 FAIL 级误报）

阈值（AC-P6-02/03）：hard 检出率 ≥95%，好题误报率 <5%。

用法::

    python scripts/gate_selftest.py
    python scripts/gate_selftest.py --json reports/obs/gate_selftest_20261102.json
    python scripts/gate_selftest.py --false-positive      # 只跑误报

退出码：0 = 达标；1 = 未达标；2 = 夹具不可读。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'scripts'))

FIXTURE = BASE / 'tests' / 'fixtures' / 'defects' / 'defects.json'
OUT_DIR = BASE / 'reports' / 'obs'

HARD_DETECTION_MIN = 0.95
FALSE_POSITIVE_MAX = 0.05


def run_rules(question: dict) -> list[dict]:
    """对单题跑完整规则集（R1–R13 + B1/JS1/S3 走批次级，这里只取单题规则）。"""
    from scripts.validate.engine import validate_questions

    by_q, _ = validate_questions([question], mode='full')
    issues = []
    for qid, lst in (by_q or {}).items():
        if qid.startswith('_'):
            continue
        for it in lst or []:
            if isinstance(it, dict):
                issues.append({'rule': str(it.get('rule', '?')),
                               'severity': str(it.get('severity', 'WARN')).upper(),
                               'detail': str(it.get('detail', ''))[:120]})
    return issues


def check_fixture(data: dict) -> list[str]:
    problems = []
    classes = data.get('classes') or []
    if len(classes) < 10:
        problems.append(f'缺陷类仅 {len(classes)} 类，要求 ≥10')
    for c in classes:
        n = len(c.get('cases') or [])
        if n < 3:
            problems.append(f"{c.get('id')} 仅 {n} 例，要求 ≥3")
        if not c.get('rule'):
            problems.append(f"{c.get('id')} 缺少 rule 字段")
    if len(data.get('good') or []) < 3:
        problems.append('好题样本 <3，无法计算误报率')
    return problems


def selftest(data: dict, only_fp: bool = False) -> dict:
    classes_out = []
    detected = total = hard_detected = hard_total = 0
    severity_mismatches = []

    if not only_fp:
        for c in data.get('classes') or []:
            rule = str(c.get('rule'))
            sev = str(c.get('severity', 'FAIL')).upper()
            hits, misses, sev_miss = [], [], []
            for case in c.get('cases') or []:
                issues = run_rules(case)
                rules_hit = {i['rule'] for i in issues}
                if rule in rules_hit:
                    actual = sorted({i['severity'] for i in issues if i['rule'] == rule})
                    hits.append({'id': case.get('id'), 'rules': sorted(rules_hit), 'actual_severity': actual})
                    # 缺陷集声明 FAIL、但规则实际只给 WARN/INFO → 这条"检出"是假的：
                    # 它在 gate 上不会阻断。2026-11-02 加此检查（R13 降级时暴露）。
                    if sev == 'FAIL' and 'FAIL' not in actual:
                        sev_miss.append({'id': case.get('id'), 'actual': actual})
                else:
                    misses.append({'id': case.get('id'), 'rules': sorted(rules_hit) or ['<无任何规则命中>']})
            n = len(hits) + len(misses)
            detected += len(hits)
            total += n
            if sev == 'FAIL':
                hard_detected += len(hits)
                hard_total += n
            severity_mismatches += [dict(m, cls=c.get('id'), rule=rule) for m in sev_miss]
            classes_out.append({
                'id': c.get('id'), 'rule': rule, 'severity': sev,
                'title': c.get('title'), 'cases': n,
                'detected': len(hits), 'rate': round(len(hits) / n, 4) if n else None,
                'misses': misses, 'severity_mismatch': sev_miss,
            })

    # 误报：好题
    fp_items = []
    for case in data.get('good') or []:
        issues = run_rules(case)
        if issues:
            fp_items.append({'id': case.get('id'), 'issues': issues})
    n_good = len(data.get('good') or [])
    fp_rate = round(len(fp_items) / n_good, 4) if n_good else None
    fp_fail = [f for f in fp_items if any(i['severity'] == 'FAIL' for i in f['issues'])]
    fp_fail_rate = round(len(fp_fail) / n_good, 4) if n_good else None

    overall = round(detected / total, 4) if total else None
    hard_rate = round(hard_detected / hard_total, 4) if hard_total else None
    ok_detect = hard_rate is None or hard_rate >= HARD_DETECTION_MIN
    ok_fp = fp_rate is None or fp_rate <= FALSE_POSITIVE_MAX
    ok_sev = not severity_mismatches

    return {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'fixture': str(FIXTURE),
        'detection': {
            'classes': len(classes_out), 'cases': total,
            'detected': detected, 'overall_rate': overall,
            'hard_cases': hard_total, 'hard_detected': hard_detected,
            'hard_rate': hard_rate, 'threshold': HARD_DETECTION_MIN,
            'pass': ok_detect,
            'severity_mismatches': severity_mismatches,
            'severity_consistent': ok_sev,
        },
        'false_positive': {
            'good_items': n_good, 'flagged': len(fp_items), 'rate': fp_rate,
            'fail_level_flagged': len(fp_fail), 'fail_level_rate': fp_fail_rate,
            'threshold': FALSE_POSITIVE_MAX, 'pass': ok_fp,
            'items': fp_items,
        },
        'per_class': classes_out,
        'result': 'PASS' if (ok_detect and ok_fp and ok_sev) else 'FAIL',
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description='门禁自测：黄金缺陷集检出率 / 误报率（P6-S3）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例:\n  python scripts/gate_selftest.py\n  python scripts/gate_selftest.py --false-positive\n')
    ap.add_argument('--fixture', default=str(FIXTURE), help='缺陷集路径')
    ap.add_argument('--json', default='', help='JSON 证据输出路径')
    ap.add_argument('--false-positive', action='store_true', help='只跑误报（好题）')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args(argv)

    p = Path(args.fixture)
    if not p.exists():
        print(f'[FAIL] 缺陷集不存在: {p}', file=sys.stderr)
        return 2
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'[FAIL] 缺陷集解析失败: {e}', file=sys.stderr)
        return 2

    problems = check_fixture(data)
    report = selftest(data, only_fp=args.false_positive)
    report['fixture_problems'] = problems
    if problems:
        report['result'] = 'FAIL'

    d = report['detection']
    fp = report['false_positive']
    if not args.quiet:
        if not args.false_positive:
            print(f"缺陷集：{d['classes']} 类 / {d['cases']} 例")
            for c in report['per_class']:
                flag = '✓' if c['detected'] == c['cases'] else '✗'
                print(f"  {flag} {c['rule']:<4} {c['title']:<24} {c['detected']}/{c['cases']}"
                      + ('' if c['detected'] == c['cases'] else f"　漏检: {[m['id'] for m in c['misses']]}"))
            print(f"检出率：总体 {d['overall_rate']:.1%}　hard {d['hard_rate']:.1%}"
                  f"（阈值 {HARD_DETECTION_MIN:.0%}）→ {'PASS' if d['pass'] else 'FAIL'}")
        print(f"误报：{fp['flagged']}/{fp['good_items']} 条好题被上报，率 {fp['rate']:.1%}"
              f"（阈值 <{FALSE_POSITIVE_MAX:.0%}）→ {'PASS' if fp['pass'] else 'FAIL'}")
        for it in fp['items']:
            print(f"  ✗ {it['id']}: {[i['rule'] for i in it['issues']]}")
        if problems:
            for x in problems:
                print(f'  ⚠ 夹具问题: {x}')
        print(f"结论：{report['result']}")

    out = Path(args.json) if args.json else OUT_DIR / f'gate_selftest_{datetime.now():%Y%m%d}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if not args.quiet:
        print(f'  📄 证据: {out}')
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
