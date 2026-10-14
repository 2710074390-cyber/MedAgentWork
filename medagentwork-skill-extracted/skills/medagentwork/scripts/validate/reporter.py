"""
reporter.py — 报告输出（控制台 + JSON）
从 validate_options.py 拆分而来
"""
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

BASE = Path.cwd()
OUTPUT_BASE = BASE / 'reports' / 'validate'


def print_report(all_issues, summary, filepath):
    """打印控制台报告"""
    print(f"\n{'═'*60}")
    print(f"  选项设计机械化校验报告 — {filepath.name}")
    print(f"{'═'*60}\n")

    for qid, issues in all_issues.items():
        if qid.startswith('_'):
            continue
        if not issues:
            continue
        fail_issues = [i for i in issues if i['severity'] == 'FAIL']
        warn_issues = [i for i in issues if i['severity'] == 'WARN']

        if fail_issues:
            icon = '✗'
        elif warn_issues:
            icon = '⚠️'
        else:
            icon = '✅'

        print(f"  {icon} {qid}")
        for issue in issues:
            sev_icon = '✗' if issue['severity'] == 'FAIL' else '⚠️'
            print(f"      {sev_icon} [{issue['rule']}] {issue['detail']}")

    b1_issues = all_issues.get('_b1_groups', [])
    if b1_issues:
        print(f"\n  ── B1 型题专项检查 ──")
        for issue in b1_issues:
            sev_icon = '✗' if issue['severity'] == 'FAIL' else '⚠️'
            print(f"  {sev_icon} [{issue['rule']}] {issue['target']}: {issue['detail']}")

    js1_issues = all_issues.get('_json_integrity', [])
    if js1_issues:
        print(f"\n  ── JSON 完整性检查 ──")
        for issue in js1_issues:
            sev_icon = '✗' if issue['severity'] == 'FAIL' else '⚠️'
            print(f"  {sev_icon} [{issue['rule']}] {issue['target']}: {issue['detail']}")

    cross_issues = all_issues.get('_cross_question', [])
    if cross_issues:
        print(f"\n  ── 跨题目检查 ──")
        for issue in cross_issues:
            sev_icon = '✗' if issue['severity'] == 'FAIL' else '⚠️'
            print(f"  {sev_icon} [{issue['rule']}] {issue['target']}: {issue['detail']}")

    print(f"\n{'─'*60}")
    print(f"  📊 汇总")
    print(f"  {'─'*56}")
    print(f"  题目总数:  {summary['total_questions']}")
    print(f"  ✅ 通过:   {summary['pass']}")
    print(f"  ⚠️ 告警:   {summary['warn']}")
    print(f"  ✗ 失败:    {summary['fail']}")
    if summary.get('b1_groups_checked', 0) > 0:
        print(f"  B1组数:    {summary['b1_groups_checked']}")

    rule_counts = Counter()
    for qid, issues in all_issues.items():
        for issue in issues:
            rule_counts[issue['rule']] += 1
    if rule_counts:
        print(f"\n  规则命中:")
        for rule, count in sorted(rule_counts.items()):
            print(f"    {rule}: {count} 处")

    print(f"{'═'*60}\n")


def save_json_report(all_issues, summary, filepath, batch_id, mode='basic'):
    """保存 JSON 报告"""
    report = {
        'report_metadata': {
            'report_id': f'OPTVAL-{datetime.now().strftime("%Y%m%d")}-{batch_id or "file"}',
            'validation_date': datetime.now().isoformat(),
            'source_file': str(filepath),
            'validator_version': '2.0',
            'check_mode': 'full (R1-R13+B1+JS1+S3)' if mode == 'full' else 'basic (R1-R9+B1)',
        },
        'summary': summary,
        'issues': [],
    }

    for qid, issues in all_issues.items():
        for issue in issues:
            report['issues'].append({
                'question_id': qid,
                'rule': issue['rule'],
                'severity': issue['severity'],
                'target': issue['target'],
                'detail': issue['detail'],
            })

    output_path = OUTPUT_BASE / f"validate_options_report_{batch_id or filepath.stem}.json"
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"  📄 JSON 报告已保存: {output_path}")
    return output_path
