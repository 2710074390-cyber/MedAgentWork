#!/usr/bin/env python3
"""
MedAgentWork 工程健康检查 v1.0
==============================
每周自动运行，检查工程完整性、一致性和可运行性。
技术参考：Google SRE 探针模式 + dbt 数据测试 + CI smoke test

用法:
  python healthcheck.py              # 快速模式（跳过慢速RAG导入）
  python healthcheck.py --full       # 完整模式（含RAG + GoldenSet回归）
  python healthcheck.py --json       # JSON 输出（适合 CI/cron）
  python healthcheck.py --fix        # 自动修复可修复的问题

检查维度（7 层）:
  A. 脚本存活性 — 所有 .py 文件可导入
  B. 文件完整性 — workflow_state 引用的文件存在，JSON 可解析
  C. 状态一致性 — 批次记录无断裂，无重复文件
  D. 目录结构   — 必要目录存在，根目录干净
  E. Prompt 同步 — clean/ 版本与 current 一致
  F. GoldenSet  — 金标准可用（--full 模式含回归）
  G. 知识库     — RAG 索引清单完整（--full 模式）
"""
import sys, json, os, subprocess, hashlib, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent

# ──────────────────────────────────────────
# 配置
# ──────────────────────────────────────────

REQUIRED_DIRS = [
    '输入素材', '中间产物', '质检报告', '最终产物', '复习资料',
    'GoldenSet', '知识库素材', 'Prompt版本', 'docs',
    'scripts', 'reports', 'memory',
]

ROOT_ALLOWED = {
    'CONTEXT.md', 'SOUL.md', 'USER.md', 'workflow_state.json',
    '操作流程.txt', '.gitignore',
    'validate_options.py', 'verify_page_numbers.py', 'ingest.py', 'healthcheck.py', 'save.py', 'gate_check.py',
    'regression_db.json',
}

ROOT_FORBIDDEN_EXT = {'.exe', '.msi', '.log', '.dll', '.bin'}
ROOT_FORBIDDEN_PREFIX = ('~', '._')

PROMPT_CURRENT = {
    'MedMaster': 'MedMaster_current_prompt.md',
    'MedGen': 'MedGen_current_prompt.md',
    'MedQC': 'MedQC_current_prompt.md',
    'MedFix': 'MedFix_current_prompt.md',
    'Agent5': 'Agent5_MedReview_Prompt.md',
}

CST = timezone(timedelta(hours=8))

# ──────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────

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
    """安全加载 JSON，返回 (data, error)"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f'JSON 解析失败: {e}'
    except Exception as e:
        return None, str(e)


# ──────────────────────────────────────────
# A. 脚本存活性
# ──────────────────────────────────────────

def check_script_importability():
    """检查所有 .py 脚本是否可以至少被 Python 编译"""
    results = []
    py_files = []
    for d in [BASE] + [BASE / 'GoldenSet'] + [BASE / '知识库素材']:
        if d.exists():
            py_files.extend(d.glob('*.py'))

    for f in sorted(set(py_files)):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                compile(fh.read(), f.name, 'exec')
            results.append({'file': str(f.relative_to(BASE)), 'status': 'PASS', 'detail': '语法编译通过'})
        except SyntaxError as e:
            results.append({'file': str(f.relative_to(BASE)), 'status': 'FAIL', 'detail': f'语法错误: {e}'})
        except Exception as e:
            results.append({'file': str(f.relative_to(BASE)), 'status': 'WARN', 'detail': f'编译警告: {e}'})
    return results


# ──────────────────────────────────────────
# B. 文件完整性
# ──────────────────────────────────────────

def check_json_validity():
    """检查所有 JSON 文件是否可解析"""
    results = []
    json_files = []
    for d in [BASE] + list(BASE.glob('*/**')):
        if d.is_dir() and '.git' not in str(d) and '__pycache__' not in str(d):
            json_files.extend(d.glob('*.json'))

    for f in sorted(set(json_files))[:100]:  # 限制 100 个避免超时
        data, err = safe_json_load(f)
        if err:
            results.append({'file': str(f.relative_to(BASE)), 'status': 'FAIL', 'detail': err})
        else:
            results.append({'file': str(f.relative_to(BASE)), 'status': 'PASS', 'detail': '解析成功'})
    return results


def check_workflow_references():
    """检查 workflow_state.json 中引用的文件是否存在"""
    results = []
    state_path = BASE / 'workflow_state.json'
    if not state_path.exists():
        return [{'file': 'workflow_state.json', 'status': 'FAIL', 'detail': '文件不存在'}]

    state, err = safe_json_load(state_path)
    if err:
        return [{'file': 'workflow_state.json', 'status': 'FAIL', 'detail': err}]

    for batch_id, batch in state.items():
        if batch_id in ('active_batch', 'system_config'):
            continue
        if not isinstance(batch, dict):
            continue

        # 检查 final_product 路径
        for product_key in ('fixed_md', 'fixed_json', 'trace_log', 'escalations'):
            fp = batch.get('steps', {}).get('final_product', {}).get(product_key, '')
            if fp:
                full = BASE / fp
                if not full.exists():
                    results.append({'file': fp, 'status': 'WARN',
                                    'detail': f'{batch_id} 引用的 {product_key} 不存在'})

        # 检查 agent 产出
        for agent_key in ('AGENT2', 'AGENT3', 'AGENT4', 'AGENT5', 'AGENT5_V2', 'AGENT5_V3'):
            agent_output = batch.get('steps', {}).get(agent_key, {}).get('output', '')
            if agent_output and not agent_output.startswith('修复版'):
                # 产出描述，检查是否指向具体文件
                pass

    if not results:
        results.append({'file': 'workflow_state.json', 'status': 'PASS', 'detail': '所有引用文件存在'})
    return results


# ──────────────────────────────────────────
# C. 状态一致性
# ──────────────────────────────────────────

def check_state_consistency():
    """检查批次记录的完整性和一致性"""
    results = []
    state_path = BASE / 'workflow_state.json'
    state, err = safe_json_load(state_path)
    if err:
        return [{'file': 'workflow_state.json', 'status': 'FAIL', 'detail': err}]

    batches = {k: v for k, v in state.items()
               if k not in ('active_batch', 'system_config') and isinstance(v, dict)}

    # C1: 检查中间产物和最终产物目录中的批次是否都在 state 中
    for stage_dir_name in ('中间产物', '最终产物'):
        stage_path = BASE / stage_dir_name
        if not stage_path.exists():
            continue
        for batch_dir in stage_path.iterdir():
            if batch_dir.name == 'archive' or not batch_dir.is_dir():
                continue
            if batch_dir.name not in batches:
                results.append({
                    'check': 'C1-orphan',
                    'status': 'WARN',
                    'detail': f'{stage_dir_name}/{batch_dir.name} 不在 workflow_state.json 中'
                })

    # C2: 检查是否有 batch 的 ALL_questions_FIXED 同时出现在中间产物和最终产物
    for batch_id in batches:
        mid = BASE / '中间产物' / batch_id / 'ALL_questions_FIXED.json'
        final = BASE / '最终产物' / batch_id / 'ALL_questions_FIXED.json'
        if mid.exists() and final.exists():
            mid_size = mid.stat().st_size
            final_size = final.stat().st_size
            if mid_size != final_size:
                results.append({
                    'check': 'C2-duplicate',
                    'status': 'WARN',
                    'detail': f'{batch_id} ALL_questions_FIXED 在中间产物({mid_size}B)和最终产物({final_size}B)都存在且大小不同'
                })

    # C3: 检查每批次的 actual_count 是否合理
    for batch_id, batch in batches.items():
        actual = batch.get('steps', {}).get('actual_count', 0)
        target = batch.get('target_count', 0)
        if actual and target and abs(actual - target) > target * 0.1:
            results.append({
                'check': 'C3-count',
                'status': 'WARN',
                'detail': f'{batch_id}: 实际{actual}题 vs 目标{target}题，偏差>{10}%'
            })

    if not [r for r in results if r['status'] in ('FAIL', 'WARN')]:
        results.append({'check': 'C-all', 'status': 'PASS', 'detail': '状态一致性检查通过'})
    return results


# ──────────────────────────────────────────
# D. 目录结构
# ──────────────────────────────────────────

def check_directory_structure():
    """检查必要目录存在，根目录干净"""
    results = []

    # D1: 必要目录
    for d in REQUIRED_DIRS:
        full = BASE / d
        if not full.exists():
            results.append({'check': 'D1-missing-dir', 'status': 'FAIL',
                            'detail': f'缺少必要目录: {d}/'})
    if not [r for r in results if r['check'] == 'D1-missing-dir']:
        results.append({'check': 'D1-dirs', 'status': 'PASS', 'detail': '所有必要目录存在'})

    # D2: 根目录干净度
    root_violations = []
    for item in BASE.iterdir():
        if item.name.startswith('.'):
            continue
        if item.is_file():
            if item.suffix in ROOT_FORBIDDEN_EXT:
                root_violations.append(str(item.name))
            elif item.name.startswith(ROOT_FORBIDDEN_PREFIX):
                root_violations.append(str(item.name))
            elif item.name not in ROOT_ALLOWED and item.suffix in ('.py', '.json', '.txt', '.log', '.md'):
                if not item.name.startswith('validate_options_report'):
                    root_violations.append(str(item.name))

    if root_violations:
        results.append({'check': 'D2-root', 'status': 'WARN',
                        'detail': f'根目录多余文件: {", ".join(root_violations)}'})
    else:
        results.append({'check': 'D2-root', 'status': 'PASS', 'detail': '根目录干净'})

    return results


# ──────────────────────────────────────────
# E. Prompt 同步
# ──────────────────────────────────────────

def check_prompt_sync():
    """检查 clean/ 版本是否与 current 一致"""
    results = []
    prompt_dir = BASE / 'Prompt版本'
    clean_dir = prompt_dir / 'clean'

    if not prompt_dir.exists():
        return [{'check': 'E-prompts', 'status': 'FAIL', 'detail': 'Prompt版本/ 目录不存在'}]

    # E1: 检查 current prompt 文件存在
    for agent, filename in PROMPT_CURRENT.items():
        current = prompt_dir / filename
        if not current.exists():
            results.append({'check': 'E1-missing', 'status': 'FAIL',
                            'detail': f'缺少 {agent} 当前 Prompt: {filename}'})

    # E2: 检查 clean/ 版本是否与 current MD5 匹配
    if clean_dir.exists():
        # 需要手动维护的映射: current → clean
        mapping = {
            'MedMaster_current_prompt.md': 'MedMaster_prompt.md',
            'MedGen_current_prompt.md': 'MedGen_prompt.md',
            'MedQC_current_prompt.md': 'MedQC_prompt.md',
            'MedFix_current_prompt.md': 'MedFix_prompt.md',
        }
        for cur_name, clean_name in mapping.items():
            cur_file = prompt_dir / cur_name
            clean_file = clean_dir / clean_name
            if cur_file.exists() and clean_file.exists():
                cur_md5 = md5_file(cur_file)
                clean_md5 = md5_file(clean_file)
                if cur_md5 != clean_md5:
                    results.append({'check': 'E2-outdated', 'status': 'WARN',
                                    'detail': f'clean/{clean_name} 与当前版本不同步 (MD5: {cur_md5[:8]} vs {clean_md5[:8]})'})

    if not [r for r in results if r['status'] in ('FAIL', 'WARN')]:
        results.append({'check': 'E-all', 'status': 'PASS', 'detail': 'Prompt 版本同步'})
    return results


# ──────────────────────────────────────────
# F. GoldenSet
# ──────────────────────────────────────────

def check_goldenset(full=False):
    """检查金标准可用性"""
    results = []
    gs_dir = BASE / 'GoldenSet'

    if not gs_dir.exists():
        return [{'check': 'F-gs', 'status': 'FAIL', 'detail': 'GoldenSet/ 目录不存在'}]

    # F1: 结构化金标准文件存在
    for required in ['structured/GS_index.json', 'structured/GS_schema.json',
                     'structured/GS_上册_2024.json', 'structured/GS_下册_2025_1994.json']:
        if not (gs_dir / required).exists():
            results.append({'check': 'F1-missing', 'status': 'WARN',
                            'detail': f'缺少金标准文件: {required}'})

    # F2: 回归测试（--full 模式）
    if full:
        regression_script = gs_dir / 'regression.py'
        if regression_script.exists():
            try:
                result = subprocess.run(
                    [sys.executable, str(regression_script)],
                    capture_output=True, text=True, timeout=120,
                    encoding='utf-8', errors='replace'
                )
                if result.returncode == 0:
                    results.append({'check': 'F2-regression', 'status': 'PASS',
                                    'detail': 'GoldenSet 回归测试通过'})
                else:
                    results.append({'check': 'F2-regression', 'status': 'FAIL',
                                    'detail': f'回归测试失败 (exit={result.returncode})'})
            except subprocess.TimeoutExpired:
                results.append({'check': 'F2-regression', 'status': 'WARN',
                                'detail': '回归测试超时 (>120s)'})
            except Exception as e:
                results.append({'check': 'F2-regression', 'status': 'WARN',
                                'detail': f'回归测试异常: {e}'})

    if not [r for r in results if r['status'] in ('FAIL', 'WARN')]:
        results.append({'check': 'F-all', 'status': 'PASS', 'detail': 'GoldenSet 正常'})
    return results


# ──────────────────────────────────────────
# G. 知识库
# ──────────────────────────────────────────

def check_knowledge_base(full=False):
    """检查 RAG 知识库索引完整性"""
    results = []
    kb_dir = BASE / '知识库素材'

    if not kb_dir.exists():
        return [{'check': 'G-kb', 'status': 'FAIL', 'detail': '知识库素材/ 目录不存在'}]

    # G1: 索引清单存在
    manifest = kb_dir / 'index_store' / 'index_manifest.json'
    if not manifest.exists():
        results.append({'check': 'G1-manifest', 'status': 'WARN', 'detail': 'index_manifest.json 不存在'})
    else:
        manifest_data, err = safe_json_load(manifest)
        if err:
            results.append({'check': 'G1-manifest', 'status': 'FAIL', 'detail': f'manifest 解析失败: {err}'})
        else:
            idx_count = len(manifest_data) if isinstance(manifest_data, dict) else 0
            results.append({'check': 'G1-manifest', 'status': 'PASS',
                            'detail': f'索引清单正常 ({idx_count} 个索引)'})

    # G2: search_kb.py 可用（--full 模式）
    if full:
        search_script = kb_dir / 'search_kb.py'
        if search_script.exists():
            try:
                result = subprocess.run(
                    [sys.executable, str(search_script), '--help'],
                    capture_output=True, text=True, timeout=30,
                    encoding='utf-8', errors='replace'
                )
                if result.returncode == 0:
                    results.append({'check': 'G2-search', 'status': 'PASS',
                                    'detail': 'search_kb.py 可用'})
                else:
                    results.append({'check': 'G2-search', 'status': 'FAIL',
                                    'detail': f'search_kb.py --help 失败 (exit={result.returncode})'})
            except Exception as e:
                results.append({'check': 'G2-search', 'status': 'WARN',
                                'detail': f'search_kb.py 测试异常: {e}'})

    if not [r for r in results if r['status'] in ('FAIL', 'WARN')]:
        results.append({'check': 'G-all', 'status': 'PASS', 'detail': '知识库正常'})
    return results


# ──────────────────────────────────────────
# 汇总输出
# ──────────────────────────────────────────

def run_healthcheck(full=False):
    """运行全部健康检查，返回 (results_by_section, summary)"""
    sections = {}

    print(f"\n{'═'*60}")
    print(f"  MedAgentWork 工程健康检查")
    print(f"  运行时间: {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S CST')}")
    print(f"  模式: {'完整' if full else '快速'}")
    print(f"{'═'*60}")

    # A
    print(f"\n  [A] 脚本存活性...", end=' ')
    r = check_script_importability()
    sections['A'] = r
    fails = sum(1 for x in r if x['status'] == 'FAIL')
    warns = sum(1 for x in r if x['status'] == 'WARN')
    total = len(r)
    print(f'{total} 个脚本: {total-fails-warns}✅ {warns}⚠️ {fails}✗')

    # B
    print(f"  [B] 文件完整性...", end=' ')
    r1 = check_json_validity()
    r2 = check_workflow_references()
    r = r1 + r2
    sections['B'] = r
    fails = sum(1 for x in r if x['status'] == 'FAIL')
    warns = sum(1 for x in r if x['status'] == 'WARN')
    print(f'{len(r1)} JSON + {len(r2)} 引用: {len(r)-fails-warns}✅ {warns}⚠️ {fails}✗')

    # C
    print(f"  [C] 状态一致性...", end=' ')
    r = check_state_consistency()
    sections['C'] = r
    fails = sum(1 for x in r if x['status'] == 'FAIL')
    warns = sum(1 for x in r if x['status'] == 'WARN')
    print(f'{len(r)-fails-warns}✅ {warns}⚠️ {fails}✗')

    # D
    print(f"  [D] 目录结构...", end=' ')
    r = check_directory_structure()
    sections['D'] = r
    fails = sum(1 for x in r if x['status'] == 'FAIL')
    warns = sum(1 for x in r if x['status'] == 'WARN')
    print(f'{len(r)-fails-warns}✅ {warns}⚠️ {fails}✗')

    # E
    print(f"  [E] Prompt 同步...", end=' ')
    r = check_prompt_sync()
    sections['E'] = r
    fails = sum(1 for x in r if x['status'] == 'FAIL')
    warns = sum(1 for x in r if x['status'] == 'WARN')
    print(f'{len(r)-fails-warns}✅ {warns}⚠️ {fails}✗')

    # F
    print(f"  [F] GoldenSet...", end=' ')
    r = check_goldenset(full)
    sections['F'] = r
    fails = sum(1 for x in r if x['status'] == 'FAIL')
    warns = sum(1 for x in r if x['status'] == 'WARN')
    print(f'{len(r)-fails-warns}✅ {warns}⚠️ {fails}✗')

    # G
    print(f"  [G] 知识库...", end=' ')
    r = check_knowledge_base(full)
    sections['G'] = r
    fails = sum(1 for x in r if x['status'] == 'FAIL')
    warns = sum(1 for x in r if x['status'] == 'WARN')
    print(f'{len(r)-fails-warns}✅ {warns}⚠️ {fails}✗')

    # 汇总
    all_results = []
    for r in sections.values():
        all_results.extend(r)

    total_fail = sum(1 for x in all_results if x['status'] == 'FAIL')
    total_warn = sum(1 for x in all_results if x['status'] == 'WARN')
    total_pass = sum(1 for x in all_results if x['status'] == 'PASS')

    summary = {
        'timestamp': datetime.now(CST).isoformat(),
        'mode': 'full' if full else 'quick',
        'sections': {k: {'pass': sum(1 for x in v if x['status']=='PASS'),
                         'warn': sum(1 for x in v if x['status']=='WARN'),
                         'fail': sum(1 for x in v if x['status']=='FAIL')}
                     for k, v in sections.items()},
        'total_pass': total_pass,
        'total_warn': total_warn,
        'total_fail': total_fail,
        'health': 'HEALTHY' if total_fail == 0 else ('DEGRADED' if total_fail <= 3 else 'UNHEALTHY'),
    }

    print(f"\n{'─'*60}")
    print(f"  📊 健康度: {summary['health']}")
    print(f"  ✅ {total_pass}  ⚠️ {total_warn}  ✗ {total_fail}")
    print(f"{'═'*60}\n")

    if total_warn or total_fail:
        print("  详细信息:")
        for section_name, r in sections.items():
            issues = [x for x in r if x['status'] in ('FAIL', 'WARN')]
            if issues:
                print(f"\n  [{section_name}]")
                for issue in issues:
                    icon = '✗' if issue['status'] == 'FAIL' else '⚠️'
                    loc = issue.get('file', issue.get('check', '?'))
                    print(f"    {icon} {loc}: {issue['detail']}")

    return sections, summary


def save_report(sections, summary):
    """保存健康检查报告"""
    report_dir = BASE / 'reports' / 'healthcheck'
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"healthcheck_{datetime.now(CST).strftime('%Y%m%d_%H%M%S')}.json"

    report = {
        'summary': summary,
        'details': {k: v for k, v in sections.items()},
    }
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  📄 报告已保存: {report_path}")


def auto_fix(sections):
    """尝试自动修复可修复的问题"""
    fixed = 0
    # 自动修复逻辑：删除已知多余文件等
    for section_name, results in sections.items():
        for r in results:
            if r['status'] == 'WARN' and 'validate_options_report_ALL' in r.get('detail', ''):
                f = BASE / r.get('file', '')
                if f.exists():
                    f.unlink()
                    fixed += 1
    if fixed:
        print(f"  🔧 自动修复了 {fixed} 个问题")
    return fixed


# ──────────────────────────────────────────
# CLI
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='MedAgentWork 工程健康检查 — 每周自检'
    )
    parser.add_argument('--full', '-f', action='store_true',
                        help='完整模式（含 RAG + GoldenSet 回归，较慢）')
    parser.add_argument('--json', '-j', action='store_true',
                        help='仅输出 JSON 摘要（适合 CI/cron）')
    parser.add_argument('--fix', action='store_true',
                        help='自动修复可修复的问题')
    args = parser.parse_args()

    sections, summary = run_healthcheck(full=args.full)

    if args.fix:
        auto_fix(sections)
        # 修复后重新检查
        sections, summary = run_healthcheck(full=args.full)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        save_report(sections, summary)

    sys.exit(0 if summary['health'] == 'HEALTHY' else 1)


if __name__ == '__main__':
    main()
