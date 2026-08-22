#!/usr/bin/env python3
"""
MedAgentWork 质量指标仪表盘 v1.0
===============================
追踪跨批次质量趋势，对标 pipeline.yaml SLO。
设计参考: Grafana / Datadog SLO Dashboard / dbt Elementary

用法:
  python scripts/metrics.py                    # 全批次指标汇总
  python scripts/metrics.py --trend            # 趋势分析
  python scripts/metrics.py --batch batch014   # 单批次详情
  python scripts/metrics.py --alerts           # SLO 违规告警
"""
import sys, json, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent.parent
CST = timezone(timedelta(hours=8))

# SLO 阈值 (来源: pipeline.yaml)
SLO = {
    'bloom_memory_max': 35,
    'bloom_application_min': 20,
    'bloom_deviation_max': 15,
    'validate_fail_max': 0,
    'answer_bias_max': 20,
    'option_avg_min': 6,
    'option_avg_max': 18,
    'gate_pass_required': True,
}


def load_state():
    with open(BASE / 'workflow_state.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def load_validate_reports():
    """加载所有 validate_options 报告"""
    reports = {}
    for f in BASE.glob('validate_options_report_*.json'):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            # 从文件名提取批次
            name = f.stem.replace('validate_options_report_', '')
            reports[name] = data
        except Exception:
            pass
    return reports


def extract_metrics(state):
    """从 workflow_state 提取所有批次的量化指标"""
    batches = {k: v for k, v in state.items()
               if k not in ('active_batch', 'halt', 'system_config', 'gate_system')
               and isinstance(v, dict)}

    metrics = []

    for batch_id, batch in sorted(batches.items()):
        m = {
            'batch': batch_id,
            'subject': batch.get('subject', '?'),
            'status': batch.get('status', 'UNKNOWN'),
            'created': batch.get('created', ''),
            'approved_at': batch.get('approved_at', ''),
        }

        # 题型与题数
        steps = batch.get('steps', {})
        completed = steps.get('COMPLETED', {})
        final_product = batch.get('final_product', {})
        merged = batch.get('merged_stats', batch.get('final_stats', {}))

        m['total'] = completed.get('total', merged.get('total', batch.get('target_count', 0)))

        # Bloom 分布
        bloom_sources = [
            completed.get('bloom'),
            merged.get('bloom'),
            steps.get('AGENT2_V2', {}).get('Bloom_actual'),
            steps.get('AGENT2', {}).get('Bloom_actual'),
        ]
        for bs in bloom_sources:
            if bs and isinstance(bs, dict):
                m['bloom'] = {k: float(str(v).replace('%', '')) for k, v in bs.items()}
                break

        # 选项长度
        opt_avg = completed.get('option_avg', '')
        if opt_avg:
            m['option_avg'] = float(str(opt_avg).replace('字', '').replace('~', ''))
        else:
            a2 = steps.get('AGENT2', {})
            opt_str = a2.get('option_avg', '')
            if opt_str:
                try:
                    m['option_avg'] = float(str(opt_str).split('→')[-1].replace('字', '').strip())
                except (ValueError, IndexError):
                    pass

        # Gate 结果
        gate_results = batch.get('gate_results', {})
        gates = {}
        for gk, gv in gate_results.items():
            if isinstance(gv, dict):
                gates[gk] = gv.get('status', '?')
        m['gates'] = gates

        # Agent 3 评分
        agent3 = steps.get('AGENT3', {})
        m['qc_score'] = agent3.get('overall_score', None)

        # Agent 4 统计
        agent4 = steps.get('AGENT4', {})
        m['agent4_patches'] = agent4.get('patches_executed', agent4.get('safe_auto', 0))
        m['agent4_rollbacks'] = agent4.get('rolled_back', 0)
        m['agent4_polarity'] = agent4.get('polarity_violations', 0)

        # Validate 结果
        a2_validate = steps.get('AGENT2', {}).get('validate_gate', '')
        if 'FAIL' in str(a2_validate):
            # 尝试解析 "FAIL (68P/93W/81F)"
            import re
            match = re.search(r'(\d+)F', str(a2_validate))
            m['validate_fail'] = int(match.group(1)) if match else None

        metrics.append(m)

    return metrics


def print_summary(metrics):
    """全批次汇总"""
    print(f"\n{'═'*70}")
    print(f"  MedAgentWork SLO 仪表盘 — {datetime.now(CST).strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═'*70}")
    print(f"  {'批次':<12} {'科目':<10} {'题数':>5} {'Bloom记忆':>8} {'Bloom应用':>8} {'选项avg':>7} {'QC':>5} {'A4Patch':>7} {'Gate':>10}")
    print(f"  {'─'*70}")

    for m in metrics:
        bloom = m.get('bloom', {})
        mem = f"{bloom.get('记忆', '?'):.0f}%" if bloom else '?'
        app = f"{bloom.get('应用', '?'):.0f}%" if bloom else '?'
        opt = f"{m['option_avg']:.1f}字" if m.get('option_avg') else '?'
        qc_raw = m.get('qc_score')
        qc = f"{float(qc_raw):.0f}" if qc_raw is not None else '?'
        patches = m.get('agent4_patches', '?')

        # Gate 状态
        gate_status = '✅' if all(v == 'PASS' for v in m.get('gates', {}).values()) else '⚠️'

        print(f"  {m['batch']:<12} {m['subject']:<10} {m['total']:>5} {mem:>8} {app:>8} {opt:>7} {qc:>5} {patches:>7} {gate_status:>10}")

    # SLO 合规检查
    print(f"\n  {'─'*70}")
    print(f"  SLO 合规检查:")
    alerts = []

    for m in metrics:
        bloom = m.get('bloom', {})
        if bloom:
            mem = bloom.get('记忆', 0)
            if mem > SLO['bloom_memory_max']:
                alerts.append(f"  ✗ {m['batch']}: Bloom 记忆层 {mem:.0f}% > {SLO['bloom_memory_max']}% (SLO)")

        if m.get('validate_fail') is not None and m.get('validate_fail', 0) > SLO['validate_fail_max']:
            alerts.append(f"  ✗ {m['batch']}: validate FAIL={m['validate_fail']} > {SLO['validate_fail_max']} (SLO)")

    if alerts:
        for a in alerts:
            print(a)
    else:
        print(f"  ✅ 所有批次 SLO 合规")

    print(f"{'═'*70}\n")


def print_trend(metrics):
    """趋势分析"""
    print(f"\n  Bloom 认知层级趋势:")
    print(f"  {'批次':<12}", end='')
    for m in metrics:
        print(f" {m['batch']:<12}", end='')
    print()

    for layer in ['记忆', '理解', '应用', '分析']:
        print(f"  {layer:<12}", end='')
        for m in metrics:
            bloom = m.get('bloom', {})
            val = bloom.get(layer, None)
            if val is not None:
                bar = '█' * min(int(val / 2), 20)
                print(f" {bar:<12}", end='')
            else:
                print(f" {'?':<12}", end='')
        print()

    # 选项长度趋势
    print(f"\n  选项平均长度趋势:")
    for m in metrics:
        opt = m.get('option_avg')
        if opt:
            bar = '█' * min(int(opt), 20)
            print(f"  {m['batch']:<12} {opt:>5.1f}字  {bar}")

    print()


def print_alerts(metrics):
    """SLO 违规告警 (只输出告警)"""
    alerts_found = False

    for m in metrics:
        bloom = m.get('bloom', {})
        issues = []

        if bloom:
            mem = bloom.get('记忆', 0)
            if mem > SLO['bloom_memory_max']:
                issues.append(f"Bloom 记忆层 {mem:.0f}% (SLO: ≤{SLO['bloom_memory_max']}%)")
            app = bloom.get('应用', 0)
            if app < SLO['bloom_application_min']:
                issues.append(f"Bloom 应用层 {app:.0f}% (SLO: ≥{SLO['bloom_application_min']}%)")

        opt = m.get('option_avg')
        if opt is not None:
            if opt < SLO['option_avg_min']:
                issues.append(f"选项平均 {opt:.1f}字 (SLO: ≥{SLO['option_avg_min']})")
            elif opt > SLO['option_avg_max']:
                issues.append(f"选项平均 {opt:.1f}字 (SLO: ≤{SLO['option_avg_max']})")

        if m.get('validate_fail') is not None and m.get('validate_fail', 0) > SLO['validate_fail_max']:
            issues.append(f"validate FAIL={m['validate_fail']} (SLO: 0)")

        if m.get('agent4_rollbacks', 0) > 0:
            issues.append(f"Agent4 回滚 {m['agent4_rollbacks']} 次")

        if issues:
            alerts_found = True
            print(f"\n  ✗ {m['batch']} ({m.get('subject','?')}):")
            for issue in issues:
                print(f"      {issue}")

    if not alerts_found:
        print("  ✅ 所有批次 SLO 合规，无告警")
    else:
        print(f"\n  ─ 建议行动:")

        # 智能建议
        mem_trend = []
        for m in metrics:
            bloom = m.get('bloom', {})
            if bloom.get('记忆'):
                mem_trend.append(bloom['记忆'])

        if len(mem_trend) >= 2 and mem_trend[-1] > mem_trend[-2] and mem_trend[-1] > 30:
            print(f"     Bloom 记忆层上升趋势 → 检查 Agent 2 Prompt 是否过于强调基础概念")
            print(f"     建议: 在 Agent 1 调用指令中提高 A2/A3 题型占比目标")


def main():
    parser = argparse.ArgumentParser(description='MedAgentWork SLO 仪表盘')
    parser.add_argument('--trend', action='store_true', help='趋势分析')
    parser.add_argument('--alerts', action='store_true', help='SLO 违规告警')
    parser.add_argument('--batch', help='单批次详情')
    args = parser.parse_args()

    state = load_state()
    metrics = extract_metrics(state)

    if args.alerts:
        print_alerts(metrics)
    elif args.trend:
        print_trend(metrics)
    elif args.batch:
        for m in metrics:
            if m['batch'] == args.batch:
                print(json.dumps(m, ensure_ascii=False, indent=2))
                break
    else:
        print_summary(metrics)


if __name__ == '__main__':
    main()
