#!/usr/bin/env python3
"""
MedAgentWork 自动维护脚本 v1.0
==============================
定时任务入口，覆盖日常运维的 6 项检查 + 自动修复。

设计原则：
  - 每次运行都输出 JSON 报告到 reports/maintenance_*.json
  - 能自动修复的不告警（静默修复 + 日志记录）
  - 不能自动修复的清晰告警

用法:
  python scripts/maintenance.py                    # 标准维护（日常）
  python scripts/maintenance.py --sync-prompts     # 强制同步 Prompt clean 版本
  python scripts/maintenance.py --cleanup-root     # 强制清理根目录
  python scripts/maintenance.py --archive-batches  # 归档已完成批次
  python scripts/maintenance.py --full             # 完整模式（含 GoldenSet 回归）
  python scripts/maintenance.py --json             # 仅输出 JSON
"""
import sys, json, os, shutil, hashlib, argparse, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent.parent
CST = timezone(timedelta(hours=8))

# ── 配置 ──────────────────────────────────────

ROOT_ALLOWED_FILES = {
    'CONTEXT.md', 'SOUL.md', 'USER.md', 'workflow_state.json',
    '操作流程.txt', '.gitignore',
    'validate_options.py', 'verify_page_numbers.py', 'ingest.py',
    'healthcheck.py', 'save.py', 'gate_check.py',
    'TODO.md',  # 用户个人待办清单
}

# 报告文件绝不允许出现在根目录（铁律①+⑤）
ROOT_FORBIDDEN_PREFIXES = ('validate_options_report_', 'healthcheck_', 'maintenance_', 'gate_check_')

TEMP_PATTERNS = ['temp_', '_b1_', '_extra_', '_num_', '_short_',
                 '_targets_', '_trunc_', 'batch011_fix', 'fix_batch',
                 'qc_analysis_batch', 'r2_balancer']

# 报告子目录（铁律②）
REPORT_SUBDIRS = {
    'validate': 'validate_options_report_',
    'healthcheck': 'healthcheck_',
    'maintenance': 'maintenance_',
    'gate': 'gate_check_',
}

PROMPT_MAPPING = {
    'MedMaster_current_prompt.md': 'MedMaster_prompt.md',
    'MedGen_current_prompt.md': 'MedGen_prompt.md',
    'MedQC_current_prompt.md': 'MedQC_prompt.md',
    'MedFix_current_prompt.md': 'MedFix_prompt.md',
    'Agent5_MedReview_Prompt.md': 'Agent5_MedReview_Prompt.md',
}

CROSS_WORKSPACES = [
    Path('C:/Users/38063/Desktop/Web-AI/CONTEXT.md'),
    Path('C:/Users/38063/Desktop/web-med/CONTEXT.md'),
    Path('C:/Users/38063/Desktop/agent-ppt/CONTEXT.md'),
    Path('C:/Users/38063/Desktop/黑曜石/CONTEXT.md'),
    Path('C:/Users/38063/Desktop/测试/CONTEXT.md'),
    Path('C:/Users/38063/Desktop/MedAgentWork/CONTEXT.md'),
]

HEALTHCHECK_SCRIPT = BASE / 'healthcheck.py'
GATE_CHECK_SCRIPT = BASE / 'gate_check.py'
REPORTS_DIR = BASE / 'reports'


def md5_file(filepath):
    h = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def safe_json_load(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f), None
    except Exception as e:
        return None, str(e)


# ═══════════════════════════════════════
# M1: Prompt 版本同步
# ═══════════════════════════════════════

def sync_prompts(dry_run=False):
    """同步 clean/ 目录中的 Prompt 到 current 版本"""
    prompt_dir = BASE / 'Prompt版本'
    clean_dir = prompt_dir / 'clean'
    results = []

    if not clean_dir.exists():
        return [{'check': 'prompt-sync', 'status': 'FAIL', 'detail': 'clean/ 目录不存在'}]

    for cur_name, clean_name in PROMPT_MAPPING.items():
        cur_file = prompt_dir / cur_name
        clean_file = clean_dir / clean_name

        if not cur_file.exists():
            results.append({'check': f'prompt-missing-{cur_name}', 'status': 'WARN',
                           'detail': f'当前版本缺失: {cur_name}'})
            continue

        cur_md5 = md5_file(cur_file)
        clean_md5 = md5_file(clean_file) if clean_file.exists() else None

        if clean_md5 is None:
            # clean 文件不存在，创建它
            if dry_run:
                results.append({'check': f'prompt-missing-clean-{clean_name}', 'status': 'WARN',
                               'detail': f'clean/{clean_name} 不存在，需创建'})
            else:
                os.makedirs(clean_dir, exist_ok=True)
                shutil.copy2(cur_file, clean_file)
                results.append({'check': f'prompt-created-{clean_name}', 'status': 'FIXED',
                               'detail': f'已创建 clean/{clean_name} ← {cur_name}'})
        elif cur_md5 != clean_md5:
            if dry_run:
                results.append({'check': f'prompt-desync-{clean_name}', 'status': 'WARN',
                               'detail': f'clean/{clean_name} 不同步 (current={cur_md5[:8]}, clean={clean_md5[:8]})'})
            else:
                shutil.copy2(cur_file, clean_file)
                new_md5 = md5_file(clean_file)
                results.append({'check': f'prompt-synced-{clean_name}', 'status': 'FIXED',
                               'detail': f'已同步 clean/{clean_name} ← {cur_name} (MD5: {new_md5[:8]})'})
        else:
            results.append({'check': f'prompt-ok-{clean_name}', 'status': 'PASS',
                           'detail': f'clean/{clean_name} 已同步'})

    return results


# ═══════════════════════════════════════
# M2: 根目录清理
# ═══════════════════════════════════════

def cleanup_root(dry_run=False):
    """清理根目录多余文件 + __pycache__"""
    results = []

    # 清理 __pycache__（铁律⑥）
    pycache = BASE / '__pycache__'
    if pycache.exists():
        if dry_run:
            results.append({'check': 'root-pycache', 'status': 'WARN', 'detail': '__pycache__/ 待清理'})
        else:
            shutil.rmtree(pycache)
            results.append({'check': 'root-pycache', 'status': 'FIXED', 'detail': '已删除 __pycache__/'})

    for item in BASE.iterdir():
        if item.name.startswith('.') or item.is_dir():
            continue

        should_keep = item.name in ROOT_ALLOWED_FILES
        is_forbidden_prefix = any(item.name.startswith(p) for p in ROOT_FORBIDDEN_PREFIXES)

        if should_keep:
            continue

        # 分类处理
        is_temp = any(item.name.startswith(p) for p in TEMP_PATTERNS)
        is_forbidden_report = is_forbidden_prefix
        is_script = item.suffix == '.py'

        if dry_run:
            results.append({'check': 'root-cleanup', 'status': 'WARN',
                           'detail': f'根目录多余: {item.name} (待移动/删除)'})
        else:
            if is_temp:
                item.unlink()
                results.append({'check': 'root-cleanup', 'status': 'FIXED',
                               'detail': f'已删除临时文件: {item.name}'})
            elif is_forbidden_report:
                # 报告文件 → 移入对应的 reports/ 子目录（铁律②+⑤）
                dest_subdir = None
                for subdir, prefix in REPORT_SUBDIRS.items():
                    if item.name.startswith(prefix):
                        dest_subdir = subdir
                        break
                if dest_subdir:
                    dest = REPORTS_DIR / dest_subdir / item.name
                else:
                    dest = REPORTS_DIR / item.name
                os.makedirs(dest.parent, exist_ok=True)
                shutil.move(str(item), str(dest))
                results.append({'check': 'root-cleanup', 'status': 'FIXED',
                               'detail': f'已移动报告 → reports/{dest.parent.name}/{item.name}'})
            elif is_script:
                dest = BASE / 'scripts' / item.name
                shutil.move(str(item), str(dest))
                results.append({'check': 'root-cleanup', 'status': 'FIXED',
                               'detail': f'已移动脚本 → scripts/{item.name}'})
            else:
                results.append({'check': 'root-cleanup', 'status': 'WARN',
                               'detail': f'未知类型文件: {item.name} (未自动处理)'})

    if not [r for r in results if r['status'] in ('FIXED', 'WARN')]:
        results.append({'check': 'root-cleanup', 'status': 'PASS', 'detail': '根目录干净'})

    return results


# ═══════════════════════════════════════
# M3: 中间产物归档
# ═══════════════════════════════════════

def archive_completed_batches(dry_run=False, days_since=7):
    """将已签收批次移入根级 archive/（铁律③）"""
    results = []

    state_path = BASE / 'workflow_state.json'
    state, err = safe_json_load(state_path)
    if err:
        return [{'check': 'archive', 'status': 'FAIL', 'detail': f'无法加载状态: {err}'}]

    now = datetime.now(CST)
    archive_root = BASE / 'archive'

    for stage_dir_name in ('中间产物', '最终产物', '质检报告'):
        stage_path = BASE / stage_dir_name
        if not stage_path.exists():
            continue

        for batch_dir in stage_path.iterdir():
            if not batch_dir.is_dir() or batch_dir.name == 'archive':
                continue

            batch_id = batch_dir.name

            # 检查批次状态
            batch_data = state.get(batch_id, {})
            if not isinstance(batch_data, dict):
                continue

            batch_status = batch_data.get('status', '')

            # 只归档已签收的批次
            if batch_status not in ('APPROVED', 'SUPERSEDED'):
                continue

            # 检查时间（避免归档太新的批次）
            approved_str = batch_data.get('approved_at', '')
            if approved_str:
                try:
                    approved_at = datetime.fromisoformat(approved_str.replace('Z', '+00:00'))
                    if (now - approved_at).days < days_since:
                        continue  # 太新，不归档
                except (ValueError, TypeError):
                    pass

            if dry_run:
                results.append({'check': f'archive-{batch_id}', 'status': 'INFO',
                               'detail': f'{stage_dir_name}/{batch_id} 可归档 (status={batch_status})'})
            else:
                # 使用根级 archive/ → archive/中间产物/batchXXX/（铁律③）
                dest = archive_root / stage_dir_name / batch_dir.name
                if dest.exists():
                    results.append({'check': f'archive-{batch_id}', 'status': 'WARN',
                                   'detail': f'{stage_dir_name}/{batch_id} 存档目标已存在，跳过'})
                else:
                    os.makedirs(dest.parent, exist_ok=True)
                    shutil.move(str(batch_dir), str(dest))
                    results.append({'check': f'archive-{batch_id}', 'status': 'FIXED',
                                   'detail': f'已归档 {stage_dir_name}/{batch_id} → archive/{stage_dir_name}/{batch_dir.name}'})

    if not [r for r in results if r['status'] in ('FIXED', 'WARN', 'INFO')]:
        results.append({'check': 'archive', 'status': 'PASS', 'detail': '无待归档批次'})

    return results


# ═══════════════════════════════════════
# M4: 跨工作区 CONTEXT 同步检查
# ═══════════════════════════════════════

def check_cross_workspace_sync():
    """检查 6 个工作区的 CONTEXT.md 工具路径表是否一致"""
    results = []

    existing = [w for w in CROSS_WORKSPACES if w.exists()]
    if len(existing) < 2:
        return [{'check': 'cross-sync', 'status': 'INFO',
                'detail': f'仅 {len(existing)} 个工作区存在，跳过交叉检查'}]

    # 读取所有 CONTEXT.md
    contexts = {}
    for w in existing:
        try:
            with open(w, 'r', encoding='utf-8') as f:
                contexts[str(w.parent.name)] = f.read()
        except Exception as e:
            results.append({'check': f'cross-read-{w.parent.name}', 'status': 'FAIL',
                           'detail': f'读取失败: {e}'})

    # 提取工具路径表
    def extract_tools_table(content):
        """从 CONTEXT.md 提取 | 工具 | 版本 | 路径 | 调用方式 | 表格"""
        lines = []
        in_table = False
        for line in content.split('\n'):
            if line.startswith('| 工具 |') or line.startswith('| **工具** |'):
                in_table = True
                continue
            if in_table:
                if line.startswith('|') and '|' in line[1:]:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 4 and parts[1] not in ('------', '工具', ''):
                        lines.append(line.strip())
                elif not line.startswith('|'):
                    in_table = False
        return lines

    # 比较
    tool_tables = {}
    for name, content in contexts.items():
        tool_tables[name] = extract_tools_table(content)

    # 用 MedAgentWork 作为基准
    base_name = 'MedAgentWork'
    base_tools = tool_tables.get(base_name, [])
    if not base_tools:
        results.append({'check': 'cross-sync-base', 'status': 'WARN',
                       'detail': '基准工作区 (MedAgentWork) 无工具表'})
    else:
        for name, tools in tool_tables.items():
            if name == base_name:
                continue
            if tools != base_tools:
                only_base = [t for t in base_tools if t not in tools]
                only_other = [t for t in tools if t not in base_tools]
                detail_parts = []
                if only_base:
                    detail_parts.append(f'{name} 缺少 {len(only_base)} 个工具条目')
                if only_other:
                    detail_parts.append(f'{name} 多余 {len(only_other)} 个工具条目')
                results.append({'check': f'cross-sync-{name}', 'status': 'WARN',
                               'detail': '; '.join(detail_parts)})
            else:
                results.append({'check': f'cross-sync-{name}', 'status': 'PASS',
                               'detail': f'{name} CONTEXT.md 工具表一致'})

    if not [r for r in results if r['status'] in ('FAIL', 'WARN')]:
        results.append({'check': 'cross-sync-all', 'status': 'PASS',
                       'detail': f'{len(existing)} 个工作区 CONTEXT.md 工具表一致'})

    return results


# ═══════════════════════════════════════
# M5: workflow_state 一致性修复
# ═══════════════════════════════════════

def fix_orphan_directories():
    """检测并修复文件系统与 workflow_state 的不一致"""
    results = []

    state_path = BASE / 'workflow_state.json'
    state, err = safe_json_load(state_path)
    if err:
        return [{'check': 'state-fix', 'status': 'FAIL', 'detail': f'无法加载状态: {err}'}]

    batches_in_state = {k: v for k, v in state.items()
                        if k not in ('active_batch', 'halt', 'system_config', 'gate_system')
                        and isinstance(v, dict)}

    # 检测文件系统中的批次目录
    for stage_dir_name in ('中间产物', '最终产物', '质检报告'):
        stage_path = BASE / stage_dir_name
        if not stage_path.exists():
            continue

        for batch_dir in stage_path.iterdir():
            if batch_dir.name == 'archive' or not batch_dir.is_dir():
                continue

            # 规范化批次名（去掉后缀如 _中医学v3）
            batch_name = batch_dir.name
            # 去掉中文后缀
            base_batch = batch_name.split('_中')[0].split('_神经')[0].split('_内')[0].split('_精神')[0].split('_外')[0]

            if batch_name not in batches_in_state and base_batch not in batches_in_state:
                results.append({'check': f'orphan-dir-{batch_name}', 'status': 'WARN',
                               'detail': f'{stage_dir_name}/{batch_name} 不在 workflow_state 中（孤儿目录）'})

    return results


# ═══════════════════════════════════════
# M6: Prompt 版本快照
# ═══════════════════════════════════════

def snapshot_prompts():
    """创建当前 Prompt 的版本快照"""
    results = []
    prompt_dir = BASE / 'Prompt版本'
    snapshot_dir = prompt_dir / 'snapshots' / datetime.now(CST).strftime('%Y%m%d_%H%M%S')

    if not prompt_dir.exists():
        return [{'check': 'snapshot', 'status': 'FAIL', 'detail': 'Prompt版本/ 目录不存在'}]

    snapshot_dir.mkdir(parents=True, exist_ok=True)

    for cur_name in PROMPT_MAPPING.keys():
        cur_file = prompt_dir / cur_name
        if cur_file.exists():
            dest = snapshot_dir / cur_name
            shutil.copy2(cur_file, dest)
            f_md5 = md5_file(cur_file)
            results.append({'check': f'snapshot-{cur_name}', 'status': 'PASS',
                           'detail': f'已快照 {cur_name} (MD5: {f_md5[:8]})'})

    # 生成快照清单
    manifest = {
        'timestamp': datetime.now(CST).isoformat(),
        'files': {name: md5_file(prompt_dir / name) for name in PROMPT_MAPPING.keys()
                  if (prompt_dir / name).exists()},
    }
    with open(snapshot_dir / 'snapshot_manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    results.append({'check': 'snapshot-manifest', 'status': 'PASS',
                   'detail': f'快照保存至 snapshots/{snapshot_dir.name}/'})

    # 清理旧快照（保留最近 10 个）
    all_snapshots = sorted(
        [d for d in (prompt_dir / 'snapshots').iterdir() if d.is_dir()],
        key=lambda x: x.name, reverse=True
    )
    for old in all_snapshots[10:]:
        shutil.rmtree(old)
        results.append({'check': 'snapshot-cleanup', 'status': 'FIXED',
                       'detail': f'已清理旧快照: {old.name}'})

    return results


# ═══════════════════════════════════════
# 汇总执行
# ═══════════════════════════════════════

def run_maintenance(dry_run=False, full=False, tasks=None):
    """执行维护任务

    可用 tasks:
      all      - 全部
      prompts  - Prompt 同步 + 快照
      cleanup   - 根目录清理 + 报告过期清理
      archive   - 批次归档
      cross     - 跨工作区同步检查
      state     - 孤儿目录检测
      health    - 运行 healthcheck
      reports   - 仅报告过期清理
    """
    if tasks is None:
        tasks = ['all']

    all_tasks = ['prompts', 'cleanup', 'archive', 'cross', 'state', 'health'] if 'all' in tasks else tasks
    results = []

    print(f"\n{'═'*60}")
    print(f"  MedAgentWork 自动维护")
    print(f"  运行时间: {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S CST')}")
    print(f"  模式: {'DRY RUN' if dry_run else 'LIVE'}{' (完整)' if full else ''}")
    print(f"  任务: {', '.join(all_tasks)}")
    print(f"{'═'*60}")

    for task in all_tasks:
        if task == 'prompts':
            print(f"\n  [M1] Prompt 版本同步...")
            r = sync_prompts(dry_run)
            results.extend(r)
            for item in r:
                icon = {'PASS': '✅', 'FIXED': '🔧', 'WARN': '⚠️', 'FAIL': '✗'}.get(item['status'], '❓')
                print(f"    {icon} {item['detail']}")

            # 自动快照
            if not dry_run:
                snap_r = snapshot_prompts()
                results.extend(snap_r)

        elif task == 'cleanup':
            print(f"\n  [M2] 根目录清理...")
            r = cleanup_root(dry_run)
            results.extend(r)
            for item in r:
                icon = {'PASS': '✅', 'FIXED': '🔧', 'WARN': '⚠️'}.get(item['status'], '❓')
                print(f"    {icon} {item['detail']}")

            # 同时清理超期报告（铁律②）
            print(f"\n  [M2b] 报告过期清理...")
            r2 = cleanup_old_reports(dry_run)
            results.extend(r2)
            for item in r2:
                icon = {'PASS': '✅', 'FIXED': '🔧', 'INFO': '📋', 'WARN': '⚠️'}.get(item['status'], '❓')
                print(f"    {icon} {item['detail']}")

        elif task == 'archive':
            print(f"\n  [M3] 批次归档...")
            r = archive_completed_batches(dry_run)
            results.extend(r)
            for item in r:
                icon = {'PASS': '✅', 'FIXED': '🔧', 'INFO': '📋', 'WARN': '⚠️'}.get(item['status'], '❓')
                print(f"    {icon} {item['detail']}")

        elif task == 'cross':
            print(f"\n  [M4] 跨工作区同步检查...")
            r = check_cross_workspace_sync()
            results.extend(r)
            for item in r:
                icon = {'PASS': '✅', 'WARN': '⚠️', 'FAIL': '✗', 'INFO': '📋'}.get(item['status'], '❓')
                print(f"    {icon} {item['detail']}")

        elif task == 'state':
            print(f"\n  [M5] 状态一致性检查...")
            r = fix_orphan_directories()
            results.extend(r)
            for item in r:
                icon = {'PASS': '✅', 'WARN': '⚠️', 'FAIL': '✗'}.get(item['status'], '❓')
                print(f"    {icon} {item['detail']}")

        elif task == 'reports':
            print(f"\n  [M7] 报告过期清理...")
            r = cleanup_old_reports(dry_run)
            results.extend(r)
            for item in r:
                icon = {'PASS': '✅', 'FIXED': '🔧', 'INFO': '📋', 'WARN': '⚠️'}.get(item['status'], '❓')
                print(f"    {icon} {item['detail']}")

        elif task == 'health':
            print(f"\n  [M6] 运行健康检查...")
            try:
                cmd = [sys.executable, str(HEALTHCHECK_SCRIPT)]
                if full:
                    cmd.append('--full')
                result = subprocess.run(cmd, capture_output=True, text=True,
                                       timeout=120, encoding='utf-8', errors='replace')
                print(result.stdout)
                if result.returncode != 0:
                    results.append({'check': 'health', 'status': 'WARN',
                                   'detail': f'健康检查发现问题 (exit={result.returncode})'})
                else:
                    results.append({'check': 'health', 'status': 'PASS', 'detail': '健康检查通过'})
            except subprocess.TimeoutExpired:
                results.append({'check': 'health', 'status': 'WARN', 'detail': '健康检查超时'})
            except Exception as e:
                results.append({'check': 'health', 'status': 'FAIL', 'detail': f'健康检查异常: {e}'})

    # 生成报告
    total_fix = sum(1 for r in results if r['status'] == 'FIXED')
    total_pass = sum(1 for r in results if r['status'] == 'PASS')
    total_warn = sum(1 for r in results if r['status'] in ('WARN', 'INFO'))
    total_fail = sum(1 for r in results if r['status'] == 'FAIL')

    summary = {
        'timestamp': datetime.now(CST).isoformat(),
        'tasks': all_tasks,
        'dry_run': dry_run,
        'total_fix': total_fix,
        'total_pass': total_pass,
        'total_warn': total_warn,
        'total_fail': total_fail,
    }

    print(f"\n{'─'*60}")
    print(f"  📊 维护完成: {total_fix}🔧 修复  {total_pass}✅ 通过  {total_warn}⚠️  {total_fail}✗")
    print(f"{'═'*60}\n")

    return results, summary


def save_report(results, summary):
    """保存维护报告到 reports/maintenance/（铁律②+⑤）"""
    maint_dir = REPORTS_DIR / 'maintenance'
    os.makedirs(maint_dir, exist_ok=True)
    report_path = maint_dir / f"maintenance_{datetime.now(CST).strftime('%Y%m%d_%H%M%S')}.json"

    report = {
        'summary': summary,
        'results': results,
    }
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  📄 报告已保存: {report_path}")
    return report_path


# ═══════════════════════════════════════
# 报告保留策略（铁律②）
# ═══════════════════════════════════════

def cleanup_old_reports(dry_run=False):
    """清理超期报告（healthcheck 7天, maintenance 30天）"""
    results = []
    now = datetime.now(CST)
    archive_root = BASE / 'archive' / 'reports'

    policies = {
        'healthcheck': 7,
        'maintenance': 30,
        'validate': None,   # 不按时间清理，随批次归档
        'gate': None,
    }

    for subdir_name, max_days in policies.items():
        subdir = REPORTS_DIR / subdir_name
        if not subdir.exists() or max_days is None:
            continue

        for report_file in subdir.iterdir():
            if not report_file.is_file():
                continue
            try:
                mtime = datetime.fromtimestamp(report_file.stat().st_mtime, tz=CST)
                age_days = (now - mtime).days
                if age_days > max_days:
                    if dry_run:
                        results.append({'check': f'report-expired-{subdir_name}', 'status': 'INFO',
                                       'detail': f'{report_file.name} 超期 {age_days}d (>{max_days}d)，待归档'})
                    else:
                        dest = archive_root / datetime.now(CST).strftime('%Y-%m') / subdir_name / report_file.name
                        os.makedirs(dest.parent, exist_ok=True)
                        shutil.move(str(report_file), str(dest))
                        results.append({'check': f'report-expired-{subdir_name}', 'status': 'FIXED',
                                       'detail': f'已归档超期报告 {report_file.name} ({age_days}d) → archive/reports/'})
            except Exception as e:
                results.append({'check': f'report-cleanup-error', 'status': 'WARN',
                               'detail': f'{report_file.name}: {e}'})

    if not [r for r in results if r['status'] in ('FIXED', 'INFO')]:
        results.append({'check': 'report-cleanup', 'status': 'PASS', 'detail': '报告无超期'})

    return results


def main():
    parser = argparse.ArgumentParser(
        description='MedAgentWork 自动维护脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
任务选择:
  python scripts/maintenance.py                        # 全部维护任务
  python scripts/maintenance.py --task prompts         # 仅 Prompt 同步
  python scripts/maintenance.py --task cleanup         # 仅根目录清理
  python scripts/maintenance.py --task archive         # 仅批次归档
  python scripts/maintenance.py --task cross           # 仅跨工作区检查
  python scripts/maintenance.py --task state           # 仅状态一致性检查
  python scripts/maintenance.py --task health          # 仅健康检查
  python scripts/maintenance.py --dry-run              # 预览模式（不实际修改）
  python scripts/maintenance.py --full                 # 完整模式（含 GoldenSet 回归）
  python scripts/maintenance.py --json                 # 仅 JSON 输出
        """
    )
    parser.add_argument('--task', '-t', choices=['all', 'prompts', 'cleanup', 'archive', 'cross', 'state', 'health', 'reports'],
                       default='all', help='维护任务 (默认 all)')
    parser.add_argument('--dry-run', '-n', action='store_true', help='预览模式，不实际修改文件')
    parser.add_argument('--full', '-f', action='store_true', help='完整模式 (含 GoldenSet 回归)')
    parser.add_argument('--json', '-j', action='store_true', help='仅输出 JSON')
    parser.add_argument('--sync-prompts', action='store_true', help='强制同步 Prompt (等价 --task prompts)')
    parser.add_argument('--cleanup-root', action='store_true', help='强制清理根目录 (等价 --task cleanup)')
    parser.add_argument('--archive-batches', action='store_true', help='归档已完成批次 (等价 --task archive)')
    args = parser.parse_args()

    # 兼容旧参数
    task = args.task
    if args.sync_prompts:
        task = 'prompts'
    elif args.cleanup_root:
        task = 'cleanup'
    elif args.archive_batches:
        task = 'archive'

    results, summary = run_maintenance(
        dry_run=args.dry_run,
        full=args.full,
        tasks=[task],
    )

    if args.json:
        print(json.dumps({'summary': summary, 'results': results}, ensure_ascii=False, indent=2))
    else:
        save_report(results, summary)

    sys.exit(0 if summary['total_fail'] == 0 else 1)


if __name__ == '__main__':
    main()
