#!/usr/bin/env python3
"""
MedAgentWork 自动 Runbook v1.0
==============================
已知故障模式 → 诊断 → 自动修复。
设计参考: Netflix Runbook / AWS Systems Manager Automation / SRE Playbook

用法:
  python scripts/runbook.py --diagnose              # 诊断模式 (只检测，不修复)
  python scripts/runbook.py --fix missing-steps      # 修复: 补写缺失步骤记录
  python scripts/runbook.py --fix orphan-batch       # 修复: 补录孤立批次
  python scripts/runbook.py --fix all                # 修复: 全部已知故障
  python scripts/runbook.py --dry-run                # 预览模式
"""
import sys, json, shutil, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent.parent
STATE_FILE = BASE / 'workflow_state.json'
CST = timezone(timedelta(hours=8))

# ─── 故障模式注册表 ─────────────────────────
# 每个故障: symptom (如何检测) + diagnosis (如何确认) + fix (如何修复) + severity

PATTERNS = {
    'missing-steps': {
        'name': 'workflow_state 缺少 AGENT3/AGENT4 步骤记录',
        'severity': 'P0_BLOCK',
        'diagnosis': '检查 batches[*].steps 是否含 AGENT3/AGENT4',
        'auto_fix': True,
        'description': '批次有 qc_result/agent4_result 顶层字段但无 steps.AGENT3/steps.AGENT4',
        'trigger_batches': ['batch014'],  # 已知受影响批次
    },
    'orphan-batch': {
        'name': '中间产物/最终产物目录不在 workflow_state 中',
        'severity': 'P1_WARN',
        'diagnosis': '对比文件系统目录与 workflow_state 的 batch 键',
        'auto_fix': True,
        'description': 'Agent 产出写入了目录但 workflow_state 未记录该批次',
    },
    'naming-split': {
        'name': '最终产物目录命名不一致 (如 batch012_中医学v3 vs batch012)',
        'severity': 'P1_WARN',
        'diagnosis': '检测最终产物/ 中是否有带中文后缀的目录名',
        'auto_fix': True,
        'description': '标准命名应为 {batch_id} 不含中文学科后缀',
    },
    'prompt-desync': {
        'name': 'clean/ Prompt 与 current 不同步',
        'severity': 'P2_INFO',
        'diagnosis': 'MD5 对比',
        'auto_fix': True,
        'script': 'scripts/maintenance.py --task prompts',
    },
    'root-pollution': {
        'name': '根目录散落文件超出允许列表',
        'severity': 'P2_INFO',
        'diagnosis': 'healthcheck.py D2-root',
        'auto_fix': True,
        'script': 'scripts/maintenance.py --task cleanup',
    },
    'cross-sync-drift': {
        'name': '跨工作区 CONTEXT.md 工具表不一致',
        'severity': 'P2_INFO',
        'diagnosis': 'scripts/maintenance.py --task cross',
        'auto_fix': True,
        'script': 'scripts/sync_tools.py',
    },
    'gate-stale': {
        'name': 'gate_results 显示 PASS 但步骤记录缺失 (手动改门禁但未修复根因)',
        'severity': 'P0_BLOCK',
        'diagnosis': '对比 gate_results[*].status 与 steps 是否存在对应步骤',
        'auto_fix': False,  # 需要人工确认
        'description': 'GATE 被手动改为 PASS 但实际步骤记录未补写 (本次修复的 batch014 问题)',
    },
}


# ─── 诊断引擎 ───────────────────────────────

def diagnose():
    """运行所有故障模式诊断"""
    state = load_state()
    findings = []

    # 1. missing-steps
    batches = {k: v for k, v in state.items()
               if k not in ('active_batch', 'halt', 'system_config', 'gate_system')
               and isinstance(v, dict)}

    for batch_id, batch in batches.items():
        steps = batch.get('steps', {})

        # 检查是否有顶层 agent result 但无 steps 条目
        has_qc = bool(batch.get('qc_result'))
        has_a4 = bool(batch.get('agent4_result'))
        has_step_a3 = bool(steps.get('AGENT3'))
        has_step_a4 = bool(steps.get('AGENT4'))

        missing = []
        if has_qc and not has_step_a3:
            missing.append('AGENT3')
        if has_a4 and not has_step_a4:
            missing.append('AGENT4')

        if missing:
            findings.append({
                'pattern': 'missing-steps',
                'batch': batch_id,
                'missing': missing,
                'detail': f'顶层有 {"+".join(missing)} 结果但 steps 中缺少步骤记录',
            })

        # 检查 gate_stale: gate标记PASS但对应步骤记录缺失
        gate_results = batch.get('gate_results', {})
        for gate_id, gate_data in gate_results.items():
            if isinstance(gate_data, dict) and gate_data.get('status') == 'PASS':
                reason = gate_data.get('reason', '')
                # 只在实际步骤缺失时才标记 gate-stale
                step_key = 'AGENT3' if 'A3' in gate_id else ('AGENT4' if 'A4' in gate_id else None)
                step_exists = bool(steps.get(step_key)) if step_key else True
                if ('补写' in reason or '事后审计' in reason) and not step_exists:
                    findings.append({
                        'pattern': 'gate-stale',
                        'batch': batch_id,
                        'gate': gate_id,
                        'detail': f'{gate_id} 被手动标记PASS但步骤记录不存在',
                    })

    # 2. orphan-batch
    for stage_dir_name in ('中间产物', '最终产物'):
        stage_path = BASE / stage_dir_name
        if not stage_path.exists():
            continue
        for batch_dir in stage_path.iterdir():
            if batch_dir.name == 'archive' or not batch_dir.is_dir():
                continue
            # 去掉中文后缀
            base_name = batch_dir.name.split('_中')[0].split('_神经')[0].split('_内')[0].split('_精神')[0].split('_外')[0]
            if base_name not in batches and batch_dir.name not in batches:
                findings.append({
                    'pattern': 'orphan-batch',
                    'batch': batch_dir.name,
                    'location': f'{stage_dir_name}/{batch_dir.name}',
                })

    # 3. naming-split
    for batch_dir in (BASE / '最终产物').iterdir():
        if batch_dir.name == 'archive' or not batch_dir.is_dir():
            continue
        # 检测非标准命名 (含中文学科后缀)
        import re
        if re.search(r'[\u4e00-\u9fff]', batch_dir.name) and batch_dir.name != 'archive':
            # 如果同时存在标准命名的目录，说明是分裂
            base = batch_dir.name.split('_')[0]
            standard = BASE / '最终产物' / base
            if standard.exists():
                findings.append({
                    'pattern': 'naming-split',
                    'batch': batch_dir.name,
                    'standard_name': base,
                    'detail': f'最终产物/{batch_dir.name} 应与 {base}/ 合并',
                })

    return findings


# ─── 修复引擎 ───────────────────────────────

def fix_missing_steps(dry_run=False):
    """补写缺失的步骤记录"""
    state = load_state()
    fixed = []

    batches = {k: v for k, v in state.items()
               if k not in ('active_batch', 'halt', 'system_config', 'gate_system')
               and isinstance(v, dict)}

    for batch_id, batch in batches.items():
        steps = batch.get('steps', {})
        if not isinstance(steps, dict):
            steps = {}
            batch['steps'] = steps

        qc = batch.get('qc_result', {})
        a4 = batch.get('agent4_result', {})
        changed = False

        # 补写 AGENT3
        if qc and not steps.get('AGENT3'):
            if not dry_run:
                steps['AGENT3'] = {
                    'status': 'COMPLETED',
                    'output': f"质检报告 (gate={qc.get('gate_decision','?')})",
                    'gate_decision': qc.get('gate_decision', ''),
                    'overall_score': qc.get('overall_score', None),
                    'issues': f"{qc.get('total_patches','?')} patches",
                    'note': '[RUNBOOK AUTO-FIX] 从 qc_result 字段补写，时间为事后审计',
                }
            changed = True
            fixed.append(f'{batch_id}: 补写 AGENT3 步骤记录')

        # 补写 AGENT4
        if a4 and not steps.get('AGENT4'):
            if not dry_run:
                steps['AGENT4'] = {
                    'status': 'COMPLETED',
                    'output': f"修复完成 (patches={a4.get('patches_executed','?')})",
                    'patches_executed': a4.get('patches_executed', 0),
                    'polarity_violations': a4.get('polarity_violations', 0),
                    'escalations': a4.get('escalations', 0),
                    'note': '[RUNBOOK AUTO-FIX] 从 agent4_result 字段补写，时间为事后审计',
                }
            changed = True
            fixed.append(f'{batch_id}: 补写 AGENT4 步骤记录')

        # 同步 gate_results
        if changed and not dry_run:
            if 'gate_results' not in batch:
                batch['gate_results'] = {}
            batch['gate_results']['GATE-A3'] = {
                'status': 'PASS',
                'reason': 'AGENT3 步骤记录已补写 (RUNBOOK 自动修复)',
                'checked_at': datetime.now(CST).isoformat(),
            }
            batch['gate_results']['GATE-A4'] = {
                'status': 'PASS',
                'reason': 'AGENT4 步骤记录已补写 (RUNBOOK 自动修复)',
                'checked_at': datetime.now(CST).isoformat(),
            }

    if fixed and not dry_run:
        save_state(state)

    return fixed


def fix_orphan_batch(dry_run=False):
    """补录孤立批次到 workflow_state"""
    state = load_state()
    fixed = []

    batches = {k: v for k, v in state.items()
               if k not in ('active_batch', 'halt', 'system_config', 'gate_system')
               and isinstance(v, dict)}

    for stage_dir_name in ('中间产物', '最终产物'):
        stage_path = BASE / stage_dir_name
        if not stage_path.exists():
            continue
        for batch_dir in stage_path.iterdir():
            if batch_dir.name == 'archive' or not batch_dir.is_dir():
                continue
            if batch_dir.name not in batches:
                import re
                base_name = re.split(r'[_]', batch_dir.name)[0]
                if base_name not in batches:
                    if not dry_run:
                        # 创建最小记录
                        state[batch_dir.name] = {
                            'batch_id': batch_dir.name,
                            'subject': '自动补录',
                            'status': 'ORPHAN_DETECTED',
                            'created': datetime.now(CST).isoformat(),
                            'steps': {},
                            'note': '[RUNBOOK AUTO-FIX] 从文件系统检测到孤批次目录，自动补录',
                        }
                    fixed.append(f'{batch_dir.name}: 从 {stage_dir_name}/{batch_dir.name} 补录')

    if fixed and not dry_run:
        save_state(state)

    return fixed


# ─── 工具函数 ───────────────────────────────

def load_state():
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_state(state):
    """原子写入"""
    tmp = STATE_FILE.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    import os
    os.replace(tmp, STATE_FILE)


# ─── CLI ────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='MedAgentWork 自动 Runbook',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
故障模式:
  missing-steps    — 补写缺失的 AGENT3/AGENT4 步骤记录 (P0)
  orphan-batch     — 补录文件系统中的孤立批次目录 (P1)
  prompt-desync    — 同步 Prompt clean 版本 (P2)
  root-pollution   — 清理根目录多余文件 (P2)
  cross-sync-drift — 同步跨工作区工具表 (P2)
  all              — 执行所有可自动修复的故障

示例:
  python scripts/runbook.py --diagnose        # 诊断所有故障
  python scripts/runbook.py --fix all         # 修复全部
  python scripts/runbook.py --fix missing-steps --dry-run  # 预览
        """
    )
    parser.add_argument('--diagnose', '-d', action='store_true', help='诊断模式')
    parser.add_argument('--fix', '-f', choices=list(PATTERNS.keys()) + ['all'],
                       help='修复指定故障模式')
    parser.add_argument('--dry-run', '-n', action='store_true', help='预览模式')
    args = parser.parse_args()

    if args.diagnose:
        print(f"\n{'═'*60}")
        print(f"  Runbook 诊断 — {datetime.now(CST).strftime('%Y-%m-%d %H:%M')}")
        print(f"{'═'*60}\n")

        findings = diagnose()
        if not findings:
            print("  ✅ 未检测到已知故障模式")
        else:
            sev_icons = {'P0_BLOCK': '🔴', 'P1_WARN': '🟡', 'P2_INFO': '🟢'}
            for f in findings:
                icon = sev_icons.get(PATTERNS.get(f['pattern'], {}).get('severity', ''), '❓')
                detail = f.get('detail', '')
                print(f"  {icon} [{f['pattern']}] {f.get('batch','')}")
                if detail:
                    print(f"      {detail}")

            print(f"\n  ── 可自动修复: ")
            auto_fixable = [f for f in findings
                           if PATTERNS.get(f['pattern'], {}).get('auto_fix', False)]
            if auto_fixable:
                for f in auto_fixable:
                    print(f"     python scripts/runbook.py --fix {f['pattern']}")
            else:
                print(f"     无")

    elif args.fix:
        target = args.fix
        print(f"\n{'═'*60}")
        print(f"  Runbook 修复 — {target}")
        print(f"  模式: {'DRY RUN' if args.dry_run else 'LIVE'}")
        print(f"{'═'*60}\n")

        all_fixed = []

        if target in ('missing-steps', 'all'):
            fixed = fix_missing_steps(args.dry_run)
            all_fixed.extend(fixed)
            for f in fixed:
                print(f"  🔧 {f}")

        if target in ('orphan-batch', 'all'):
            fixed = fix_orphan_batch(args.dry_run)
            all_fixed.extend(fixed)
            for f in fixed:
                print(f"  🔧 {f}")

        if target in ('prompt-desync', 'all'):
            print(f"  🔧 prompt-desync: 执行 scripts/maintenance.py --task prompts")
            if not args.dry_run:
                import subprocess
                subprocess.run([sys.executable, str(BASE / 'scripts' / 'maintenance.py'),
                               '--task', 'prompts'])

        if target in ('root-pollution', 'all'):
            print(f"  🔧 root-pollution: 执行 scripts/maintenance.py --task cleanup")
            if not args.dry_run:
                import subprocess
                subprocess.run([sys.executable, str(BASE / 'scripts' / 'maintenance.py'),
                               '--task', 'cleanup'])

        if target in ('cross-sync-drift', 'all'):
            print(f"  🔧 cross-sync-drift: 执行 scripts/sync_tools.py")
            if not args.dry_run:
                import subprocess
                subprocess.run([sys.executable, str(BASE / 'scripts' / 'sync_tools.py')])

        if not all_fixed:
            print(f"  ✅ 无需修复或故障模式不匹配")
        else:
            print(f"\n  📊 修复了 {len(all_fixed)} 个问题")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
