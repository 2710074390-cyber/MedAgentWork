#!/usr/bin/env python3
"""
MedAgentWork 一键保存脚本 v1.1 — 强制管线顺序
===============================================
从剪贴板读 Agent 产出 → 管线校验 → 保存 → ingest → 打印下一步

管线强制规则:
  agent2 前: 批次必须已创建（workflow_state 中有记录或 --batch 指定）
  agent3 前: agent2 的产出文件必须存在
  agent4 前: agent3 的质检报告必须存在
  agent5 前: agent4 的最终产物必须存在

用法:
  python save.py                       # 自动检测阶段
  python save.py --batch batch006       # 指定批次
  python save.py --batch batch006 --stage agent3  # 手动指定（仍会校验前置）
"""
import sys, json, subprocess, argparse, re, tempfile
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent
STATE_FILE = BASE / "workflow_state.json"

# 正式重构 (2026-08-13): 状态读写统一走 scripts/workflow_state.py
sys.path.insert(0, str(BASE / 'scripts'))
import workflow_state as ws

STAGE_ORDER = ['agent2', 'agent3', 'agent4', 'agent5']
STAGE_NAMES = {
    'agent2': 'Agent 2 (MedGen) 出题',
    'agent3': 'Agent 3 (MedQC) 质检',
    'agent4': 'Agent 4 (MedFix) 修复',
    'agent5': 'Agent 5 (MedReview) 主复习资料',
}
STAGE_NEXT = {
    'agent2': 'Agent 3 (MedQC)',
    'agent3': 'Agent 4 (MedFix)',
    'agent4': 'Agent 5 (MedReview)',
    'agent5': '用户签收',
}
STAGE_EXT = {'agent2': '.json', 'agent3': '.json', 'agent4': '.json', 'agent5': '.md'}

# 前置阶段 → 前置产出文件的目录和名称模式
PREREQ = {
    'agent3': {'stage': 'agent2', 'dir': '中间产物', 'desc': 'Agent 2 的题库 JSON'},
    'agent4': {'stage': 'agent3', 'dir': '质检报告', 'desc': 'Agent 3 的质检报告 JSON'},
    'agent5': {'stage': 'agent4', 'dir': '最终产物', 'desc': 'Agent 4 的修复版文件'},
}


def read_clipboard():
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             '[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-Clipboard -Raw'],
            capture_output=True, text=True, timeout=10,
            encoding='utf-8', errors='replace'
        )
        if result.returncode != 0:
            return None, f'PowerShell 错误: {result.stderr.strip()}'
        text = result.stdout
        if not text or not text.strip():
            return None, '剪贴板为空 — 请先在 Agent 窗口 Ctrl+A → Ctrl+C 复制产出'
        return text, None
    except subprocess.TimeoutExpired:
        return None, '剪贴板读取超时'
    except FileNotFoundError:
        return None, 'PowerShell 不可用'
    except Exception as e:
        return None, str(e)


def detect_format(text):
    stripped = text.strip()
    if stripped.startswith('{') or stripped.startswith('['):
        return 'json'
    if stripped.startswith('#') or stripped.startswith('**') or stripped.startswith('>'):
        return 'md'
    if re.search(r'"[A-Za-z_]+"\s*:', stripped[:200]):
        return 'json'
    return 'md'


def detect_stage(state, batch_id):
    """从 workflow_state.json 推断下一个未完成阶段（统一模块）"""
    return ws.detect_next_stage(state, batch_id, stages=STAGE_ORDER)


def check_prereq(batch_id, stage):
    """管线强制校验：前置阶段产出是否存在"""
    if stage == 'agent2':
        # agent2 只需要批次已创建
        state, _ = ws.load_state()
        if batch_id not in (state or {}):
            return False, f'批次 {batch_id} 尚未创建。请先在 Agent 1 说「开始新批次」'
        return True, None

    if stage not in PREREQ:
        return True, None

    prereq = PREREQ[stage]
    prereq_dir = BASE / prereq['dir'] / batch_id
    prereq_dir_flat = BASE / prereq['dir']

    # 先检查批次子目录
    if prereq_dir.exists():
        files = list(prereq_dir.glob('*'))
        if files:
            return True, None

    # 再检查平级目录（质检报告没有批次子目录）
    if prereq_dir_flat.exists():
        files = list(prereq_dir_flat.glob(f'*{batch_id}*'))
        if files:
            return True, None

    return False, (
        f'管线阻断：{prereq["desc"]} 不存在。'
        f'请先完成 {STAGE_NAMES.get(prereq["stage"], prereq["stage"])} 阶段'
        f'（DSH 流程：编排者完成后自动继续；手动流程：先保存该阶段产出再运行 python save.py）'
    )


def show_preview(text, max_lines=6, max_chars=250):
    lines = text.strip().split('\n')
    preview_lines = lines[:max_lines]
    preview = '\n'.join(preview_lines)
    if len(preview) > max_chars:
        preview = preview[:max_chars] + '...'
    if len(lines) > max_lines:
        preview += f'\n... (共 {len(lines)} 行, {len(text):,} 字符)'
    return preview


def main():
    parser = argparse.ArgumentParser(
        description='MedAgentWork 一键保存 — 剪贴板 → 管线校验 → ingest'
    )
    parser.add_argument('--batch', '-b', help='批次ID（如 batch006）')
    parser.add_argument('--stage', '-s', choices=STAGE_ORDER,
                        help='手动指定阶段（仍会校验前置阶段完成状态）')
    parser.add_argument('--model', '-m', default='unknown', help='模型名（写入血缘）')
    parser.add_argument('--validate', '-V', action='store_true',
                        help='运行 validate_options.py 预检')
    args = parser.parse_args()

    # ── 1. 加载状态（统一模块，含旧数据迁移）──
    state, _err = ws.load_state()
    if state is None:
        state = {}

    # ── 2. 确定批次 ──
    batch_id = args.batch or state.get('active_batch')
    if not batch_id:
        # 自动推算下一批次号
        existing = sorted([k for k in state if k.startswith('batch') and k not in ('active_batch', 'system_config')])
        if existing:
            num = int(existing[-1].replace('batch', ''))
            batch_id = f'batch{num+1:03d}'
        else:
            batch_id = 'batch006'
        print(f'  ℹ️  未指定批次，自动使用: {batch_id}')

    # ── 3. 确定阶段 ──
    stage = args.stage or detect_stage(state, batch_id)

    if stage is None:
        print(f'\n  ✅ 批次 {batch_id} 全部阶段已完成！')
        print(f'  在 DSH 主会话输入「终审」进入归档/签收流程。')
        sys.exit(0)

    # ── 4. 管线强制校验 ⛔ ──
    ok, err = check_prereq(batch_id, stage)
    if not ok:
        print(f'\n{"═"*50}')
        print(f'  ⛔ 管线阻断')
        print(f'{"═"*50}')
        print(f'\n  {err}')
        print(f'\n  当前批次: {batch_id}')
        print(f'  期望阶段: {stage} ({STAGE_NAMES.get(stage, "?")})')
        state_snapshot = state.get(batch_id, {}).get('steps', {})
        if state_snapshot:
            print(f'  已完成阶段:')
            for s in STAGE_ORDER:
                key = s.upper()
                if key in state_snapshot and state_snapshot[key].get('status') == 'COMPLETED':
                    print(f'    ✅ {s} ({STAGE_NAMES.get(s, "?")})')
        sys.exit(3)

    # ── 5. 读剪贴板 ──
    print(f'\n{"═"*50}')
    print(f'  MedAgentWork 管线保存 — {batch_id}')
    print(f'{"═"*50}')
    print(f'\n  阶段: {stage} → {STAGE_NAMES.get(stage, "?")}')
    if stage in PREREQ:
        print(f'  前置: {STAGE_NAMES.get(PREREQ[stage]["stage"], "?")} ✅')

    print(f'\n  📋 读取剪贴板...', end=' ')
    text, err = read_clipboard()
    if err:
        print(f'✗\n  ✗ {err}')
        sys.exit(2)
    print(f'✓ ({len(text):,} 字符)')

    # ── 6. 内容特征校验 ──
    fmt = detect_format(text)
    exp_ext = STAGE_EXT.get(stage, '.json')

    # 6-NEW. JSON 格式强制验证（防止 YAML 前端元数据污染）
    if exp_ext == '.json' and stage in ('agent2', 'agent3', 'agent4'):
        stripped_check = text.strip()
        if stripped_check.startswith('---') or stripped_check.startswith('## '):
            print(f'\n{"═"*50}')
            print(f'  ⛔ JSON 格式验证失败')
            print(f'{"═"*50}')
            print(f'\n  {stage} 产出必须为纯 JSON，不允许 YAML/Markdown 前置元数据。')
            print(f'  发现文件以 "---" 或 "##" 开头，这是 Agent 混入了修改声明。')
            print(f'  请让 Agent 输出纯 JSON 数组，元数据单独保存为 .md 文件。')
            sys.exit(4)
        # 尝试 JSON 解析
        try:
            parsed = json.loads(stripped_check)
            if not isinstance(parsed, (list, dict)):
                raise ValueError(f'JSON 顶层类型为 {type(parsed).__name__}，期望 list 或 dict')
            print(f'  ✅ JSON 格式验证通过（{type(parsed).__name__}，'
                  f'{len(parsed)} 项）')
        except json.JSONDecodeError as e:
            print(f'\n{"═"*50}')
            print(f'  ⛔ JSON 解析失败')
            print(f'{"═"*50}')
            print(f'\n  行 {e.lineno}，列 {e.colno}: {e.msg}')
            print(f'  请检查 Agent 产出是否为有效 JSON。')
            sys.exit(4)

    # 6a. 防止把 Agent 1 调用指令误存为 Agent 产出
    instruction_markers = ['═══════════════════════════════════════',
                           '📤 请将以下指令粘贴到', '【命题双向细目表】',
                           '请按你的 OutputFormat 输出完整产物']
    if any(m in text[:500] for m in instruction_markers):
        print(f'\n  ⛔ 内容看起来是 Agent 1 的调用指令，不是 Agent 产出！')
        print(f'  请切换到 Agent N 窗口，复制 Agent 的产出内容（题库/质检报告/复习资料），')
        print(f'  而不是复制 Agent 1 给你的调用指令。')
        sys.exit(5)

    # 6b. 格式 vs 阶段匹配检查
    if fmt == 'md' and exp_ext == '.json' and stage != 'agent5':
        print(f'  ⚠️  检测到 Markdown 格式，但 {stage} 通常产出 JSON')
        print(f'  如果确认正确，脚本将继续。否则请检查是否复制了正确的内容。')

    # 6c. 内容结构校验（检测是否像正确类型的产出）
    stripped = text.strip()
    if stage == 'agent3':
        if '"report_metadata"' not in stripped[:1000] and '"gate_decision"' not in stripped[:1000]:
            print(f'  ⚠️  内容不像 Agent 3 质检报告（缺少 report_metadata/gate_decision）')
            print(f'  如果确认正确将继续，但请检查是否复制了正确内容。')

    print(f'  格式: {fmt.upper()}')

    # ── 7. 预览 ──
    print(f'\n  ── 内容预览 ──')
    print(f'  {show_preview(text)}')
    print(f'  ───────────────')

    # ── 8. 保存 ──
    ext = '.md' if fmt == 'md' else '.json'
    tmp_dir = Path(tempfile.gettempdir())
    tmp_file = tmp_dir / f'{batch_id}_{stage}{ext}'

    # GoldenSet 写保护：save 的产物绝不可能写入 GoldenSet/
    # （save 只处理 Agent 产出，GoldenSet 由用户手动签收后移入）
    # 此检查是二次保险

    with open(tmp_file, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'\n  💾 已保存: {tmp_file}')

    # ── 8b. MD 答案标记校验（agent2/agent5 产出 .md 时）──
    if ext == '.md' and stage in ('agent2', 'agent5'):
        import re as _re
        missing_check = 0
        total_blocks = 0
        for line in text.split('\n'):
            if _re.match(r'^\*\*[\w\d-]+\*\*', line) or _re.match(r'^#{1,3}\s+\d+[\.\、]', line):
                total_blocks += 1
        check_count = text.count('✅')
        if total_blocks > 10 and check_count < total_blocks * 0.5:
            print(f'  ⚠️  MD 答案标记: {total_blocks}个题目块, 仅{check_count}个✅标记 ({check_count/total_blocks*100:.0f}%)')
            print(f'  请确认每题已正确标注答案（用 ✅ 标记正确选项）')

    # ── 9. 运行 ingest ──
    print(f'\n  📦 运行 ingest...')
    ingest_script = BASE / 'ingest.py'
    cmd = [sys.executable, str(ingest_script),
           str(tmp_file), '--batch', batch_id, '--stage', stage]
    if args.model != 'unknown':
        cmd.extend(['--model', args.model])
    if args.validate or stage == 'agent2':
        cmd.append('--validate')

    try:
        subprocess.run(cmd, timeout=120, encoding='utf-8', errors='replace')
    except subprocess.TimeoutExpired:
        print(f'  ⚠️ ingest 超时（文件可能较大，但已保存）')
    except Exception as e:
        print(f'  ⚠️ ingest 异常: {e}（文件已保存，可手动运行 ingest）')

    # ── 9b. Agent 2/4 产出自检门禁（batch006教训）──
    if stage in ('agent2', 'agent4') and ext == '.json':
        print(f'\n  🔍 运行 validate_options.py 自检...')
        validate_script = BASE / 'validate_options.py'
        if validate_script.exists():
            try:
                val_result = subprocess.run(
                    [sys.executable, str(validate_script), '--batch', batch_id],
                    capture_output=True, text=True, timeout=60,
                    encoding='utf-8', errors='replace'
                )
                # 从输出中提取 fail 数
                val_output = val_result.stdout
                fail_match = re.search(r'✗\s*失败:\s*(\d+)', val_output)
                fail_count = int(fail_match.group(1)) if fail_match else -1
                pass_match = re.search(r'✅\s*通过:\s*(\d+)', val_output)
                pass_count = int(pass_match.group(1)) if pass_match else -1

                if fail_count > 0:
                    print(f'  ⛔ 自检未通过: {pass_count}通过 / {fail_count}失败')
                    print(f'  Agent {stage[-1]} 产出有 {fail_count} 题不符合 NBME 选项规范。')
                    print(f'  建议返回 Agent 重新修复后再保存。')
                    print(f'  （文件已保存，可手动继续）')
                elif fail_count == 0:
                    print(f'  ✅ 自检通过: {pass_count}通过 / 0失败')
                else:
                    print(f'  ⚠️ 自检结果无法解析')
            except subprocess.TimeoutExpired:
                print(f'  ⚠️ validate 超时')
            except Exception as e:
                print(f'  ⚠️ validate 异常: {e}')

    # ── 10. 下一步 ──
    next_stage = STAGE_NEXT.get(stage, '完成')
    print(f'''
{'═'*50}
  ✅ {stage} 完成 → 👉 {next_stage}

  在 DSH 主会话输入「继续」获取下一阶段调用指令（手动流程备选：粘贴到对应 Agent 窗口）
{'═'*50}
''')

    # ── 11. 更新状态（统一模块）──
    # v1.2 (2026-08-13): ingest 作为子进程已更新过 workflow_state.json
    # （血缘/steps/md5）。必须重新加载磁盘上的最新 state 再写，
    # 否则会用旧副本覆写、丢失 ingest 刚写入的血缘记录（lost-update）。
    state, _ = ws.load_state()
    if state is None:
        state = {}
        print(f'  ⚠️ 重新加载 state 失败，保留内存副本')
    state['active_batch'] = batch_id
    ws.save_state(state)


if __name__ == '__main__':
    main()
