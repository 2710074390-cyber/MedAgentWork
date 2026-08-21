#!/usr/bin/env python3
"""
MedAgentWork 产物摄入脚本 v1.0 — 自动化中转 + 血缘追溯
用法:
  python ingest.py <文件路径> --batch batch006 --stage agent2
  python ingest.py <文件路径> --batch batch006 --stage agent2 --validate

阶段映射:
  agent2 → 中间产物/{batchID}/
  agent3 → 质检报告/{batchID}/
  agent4 → 最终产物/{batchID}/
  agent5 → 复习资料/
"""
import sys, json, hashlib, shutil, argparse, re
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent
STATE_FILE = BASE / "workflow_state.json"

# 正式重构 (2026-08-13): 状态读写/血缘统一走 scripts/workflow_state.py
sys.path.insert(0, str(BASE / 'scripts'))
import workflow_state as ws

STAGE_DIRS = {
    'agent2': '中间产物',
    'agent3': '质检报告',
    'agent4': '最终产物',
    'agent5': '复习资料',
}

STAGE_NEXT = {
    'agent2': 'Agent 3 (MedQC) — 质检',
    'agent3': 'Agent 4 (MedFix) — 修复',
    'agent4': 'Agent 5 (MedReview) — 主复习资料',
    'agent5': '用户签收 — 人工审查',
}


def md5_file(filepath):
    """计算文件 MD5"""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def validate_json_structure(filepath):
    """S1/S2 级快速预检：JSON 合法性 + 必填字段"""
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f'JSON 解析失败: {e}']

    if isinstance(data, list):
        # 题库 JSON（数组格式）— v1.1 (2026-08-13): 兼容两代字段命名
        # 旧: id/question/type/answer | 新: question_id/stem/question_type/answer_key
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                issues.append(f'[{i}] 非对象类型')
                continue
            qid = item.get('id') or item.get('question_id')
            stem = item.get('question') or item.get('stem') or item.get('question_text') or item.get('题干')
            qtype = item.get('type') or item.get('question_type')
            opts = item.get('options')
            ans = item.get('answer') or item.get('answer_key') or item.get('correct_answer')
            if not qid:
                issues.append(f'[{i}] 缺少必填字段: id/question_id')
            if not stem or (isinstance(stem, str) and stem.strip() == ''):
                issues.append(f'[{i}] 缺少必填字段: question/stem')
            if not qtype:
                issues.append(f'[{i}] 缺少必填字段: type/question_type')
            if opts is None or (isinstance(opts, list) and len(opts) == 0):
                issues.append(f'[{i}] 缺少必填字段: options 或选项组为空')
            if not ans:
                issues.append(f'[{i}] 缺少必填字段: answer/answer_key')
    elif isinstance(data, dict):
        # 质检报告 JSON
        if 'report_metadata' not in data:
            issues.append('质检报告缺少 report_metadata')
        if 'gate_decision' not in data.get('report_metadata', {}):
            issues.append('质检报告缺少 gate_decision')
    else:
        issues.append('JSON 顶层结构不是数组或对象')

    return issues


# ──────────────────────────────────────────
# 契约 schema 校验（正式重构 2026-08-13）
# schemas/agent2_output.schema.json 等为管线契约单一事实来源，
# 摄入时用 jsonschema 实际校验（修复 pipeline.yaml 死引用问题）。
# ──────────────────────────────────────────

SCHEMA_MAP = {
    'agent2': 'agent2_output.schema.json',
    'agent3': 'agent3_output.schema.json',
    'agent4': 'agent4_output.schema.json',
}


def validate_schema(filepath, stage):
    """契约 schema 校验（jsonschema）。schema 缺失/解析失败/库不可用时静默跳过。"""
    schema_file = BASE / 'schemas' / SCHEMA_MAP.get(stage, '')
    if not schema_file.exists():
        return []
    try:
        import jsonschema
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        return [f'schema[{stage}]: {"/".join(map(str, e.path)) or "$"}: {e.message}' for e in errors[:20]]
    except ImportError:
        return []
    except Exception:
        return []


def load_state():
    """加载 workflow_state.json（统一模块，含旧数据迁移）。

    v2.0 (2026-08-20 审查修复): 加载失败即中止 —— 此前出错时返回 {}，
    后续 save_state 会用近乎空的状态**整体覆写**含全部批次的
    workflow_state.json（24 批次状态与血缘静默丢失的数据丢失窗口）。
    """
    state, err = ws.load_state()
    if err:
        print(f"  ✗ {err}")
        print("  ✗ 状态加载失败，中止摄入（防止空状态覆写丢失全部批次）。")
        print("    如确认需要重建，请先备份 workflow_state.json 再手动处理。")
        sys.exit(3)
    return state


def save_state(state):
    """保存 workflow_state.json（统一模块，原子写盘）"""
    ws.save_state(state)
    print(f"  📄 workflow_state.json 已更新")


def add_lineage(state, batch_id, stage, filepath, file_md5):
    """添加血缘记录（统一模块）；保留 Prompt 版本内容推断"""
    if batch_id not in state:
        print(f"  ⚠️ 批次 {batch_id} 在 workflow_state.json 中不存在，创建新条目")

    model = 'unknown'
    prompt_version = 'unknown'

    # 尝试从内容中提取 Prompt 版本标记
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(5000)
        pv_match = re.search(r'(?:prompt_version|Prompt版本|MedQC_v|MedGen_v|MedFix_v|MedReview_v)([\d.]+)', content)
        if pv_match:
            prompt_version = pv_match.group(0)
    except Exception:
        pass

    return ws.add_lineage(state, batch_id, stage, filepath, file_md5,
                          model=model, prompt_version=prompt_version)


def run_precheck(filepath, batch_id):
    """运行 validate_options.py full 模式（如果是题库文件）"""
    import subprocess
    validator = BASE / "validate_options.py"
    if not validator.exists():
        print("  ⚠️ validate_options.py 未找到，跳过预检")
        return

    print(f"\n  🔍 运行预检脚本 (full 模式)...")
    try:
        result = subprocess.run(
            [sys.executable, str(validator), '--file', str(filepath),
             '--mode', 'full'],
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace'
        )
        stdout = result.stdout or ''
        for line in stdout.split('\n'):
            if any(kw in line for kw in ['汇总', '题目总数', '通过', '告警', '失败']):
                print(f"  {line.strip()}")
        if result.returncode != 0:
            print(f"  ⚠️ 预检发现 FAIL 项，建议修复后再提交给下一步")
        else:
            print(f"  ✅ 预检通过")
    except Exception as e:
        print(f"  ⚠️ 预检脚本运行异常: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='MedAgentWork 产物摄入脚本 — 自动化中转 + 血缘追溯'
    )
    parser.add_argument('file', help='Agent 产出的文件路径')
    parser.add_argument('--batch', '-b', required=True, help='批次ID（如 batch006）')
    parser.add_argument('--stage', '-s', required=True,
                        choices=['agent2', 'agent3', 'agent4', 'agent5'],
                        help='产出阶段: agent2/agent3/agent4/agent5')
    parser.add_argument('--validate', '-V', action='store_true',
                        help='运行 validate_options.py full 模式预检')
    parser.add_argument('--model', '-m', default='unknown',
                        help='生成该产物的模型名（用于血缘追溯）')
    parser.add_argument('--prompt-version', '-p', default='unknown',
                        help='使用的 Prompt 版本（用于血缘追溯）')
    parser.add_argument('--no-move', action='store_true',
                        help='仅校验+记录血缘，不移动文件')
    args = parser.parse_args()

    source = Path(args.file)
    if not source.exists():
        print(f"  ✗ 文件不存在: {source}")
        sys.exit(2)

    print(f"{'═'*60}")
    print(f"  MedAgentWork 产物摄入")
    print(f"{'═'*60}")
    print(f"  批次:     {args.batch}")
    print(f"  阶段:     {args.stage} → {STAGE_NEXT.get(args.stage, '?')}")
    print(f"  源文件:   {source}")
    print(f"  文件大小: {source.stat().st_size:,} 字节")

    # 1. 计算 MD5
    file_md5 = md5_file(source)
    print(f"  MD5:      {file_md5}")

    # 2. JSON 结构预检（仅 JSON 文件）
    if source.suffix == '.json':
        print(f"\n  🩺 JSON 结构预检...")
        issues = validate_json_structure(source)
        # 2a. 契约 schema 校验（正式重构: schemas/*.schema.json 实时生效）
        schema_issues = validate_schema(source, args.stage)
        if schema_issues:
            print(f"  ⚠️ 契约 schema 发现 {len(schema_issues)} 个问题:")
            for issue in schema_issues[:10]:
                print(f"    - {issue}")
            issues += schema_issues
        if issues:
            print(f"  ✗ 发现 {len(issues)} 个结构问题:")
            for issue in issues[:10]:
                print(f"    - {issue}")
            if len(issues) > 10:
                print(f"    ... 还有 {len(issues) - 10} 个问题未显示")
            if not args.no_move:
                ans = input(f"\n  ⚠️ 存在结构问题，是否仍继续摄入？[y/N]: ")
                if ans.lower() != 'y':
                    print("  已取消")
                    sys.exit(2)
        else:
            print(f"  ✅ JSON 结构正常")

    # 3. 可选：运行 validate_options.py
    if args.validate:
        run_precheck(source, args.batch)

    # 4. 目标目录
    stage_dir = STAGE_DIRS.get(args.stage, '中间产物')
    dest_dir = BASE / stage_dir / args.batch
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 5. 标准化文件名
    ext = source.suffix
    stage_name_map = {
        'agent2': 'A2_题库',
        'agent3': 'A3_质检报告',
        'agent4': 'A4_修复版',
        'agent5': 'A5_主复习资料',
    }
    dest_name = f"{args.batch}_{stage_name_map.get(args.stage, args.stage)}{ext}"
    dest = dest_dir / dest_name

    # 6. 防覆盖 + GoldenSet 写保护
    if 'GoldenSet' in str(dest):
        print(f"\n  🛡️ GoldenSet 写保护：禁止通过 ingest 写入 GoldenSet/ 目录")
        print(f"  GoldenSet 只能由用户手动签收后移入。")
        sys.exit(4)

    if dest.exists() and not args.no_move:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = dest_name.replace(ext, f'_v{ts}{ext}')
        dest = dest_dir / backup_name
        print(f"\n  ⚠️  目标文件已存在，自动避免覆盖:")
        print(f"      原路径: {dest_dir / dest_name}")
        print(f"      新路径: {dest}")

    # 7. 复制文件
    if not args.no_move:
        shutil.copy2(source, dest)
        print(f"\n  📋 文件已复制到: {dest}")
    else:
        print(f"\n  📋 目标路径（未移动）: {dest}")

    # 7b. 统一题库注册（P0-1 qbank 数据层：agent2/agent4 的 JSON 题库自动入库）
    if not args.no_move and ext == '.json' and args.stage in ('agent2', 'agent4'):
        try:
            import qbank
            stage_tag = 'final' if args.stage == 'agent4' else 'intermediate'
            n, dups = qbank.register_file(dest, args.batch, stage=stage_tag)
            qbank.update_meta()
            if n:
                print(f"  📚 题库注册: {n} 题 → question_bank/registry.jsonl")
            if dups:
                print(f"  ⚠️ 与注册表重复 {len(dups)} 条（去重仅报告，不自动删除）:")
                for d in dups[:3]:
                    print(f"     「{d['stem']}」 ← {d.get('dup_with_file')}")
        except Exception as e:
            print(f"  ⚠️ 题库注册跳过: {e}")

    # 7. 更新 workflow_state.json
    state = load_state()
    batch = add_lineage(state, args.batch, args.stage, dest, file_md5)

    # 补充模型和 Prompt 版本（如果用户指定）
    if args.model != 'unknown':
        batch['lineage'][-1]['agent_model'] = args.model
    if args.prompt_version != 'unknown':
        batch['lineage'][-1]['prompt_version'] = args.prompt_version
    if args.model != 'unknown' or args.prompt_version != 'unknown':
        batch['steps'][args.stage.upper()]['model'] = args.model
        batch['steps'][args.stage.upper()]['prompt_version'] = args.prompt_version

    save_state(state)

    # 8. 打印下一步
    next_stage = STAGE_NEXT.get(args.stage, '完成')
    next_agent = {
        'agent2': 'Agent 3',
        'agent3': 'Agent 4',
        'agent4': 'Agent 5',
        'agent5': '用户',
    }.get(args.stage, '?')

    print(f"""
{'═'*60}
  📤 下一步：将产物交付给 {next_agent}
{'═'*60}

  产物已就绪: {dest}

  操作：将上述文件内容粘贴到 {next_agent} 的对话框中，
        并附上编排器（MedMaster）提供的调用指令。

  提示：运行以下命令查看当前批次状态:
    python -c "import json; s=json.load(open('workflow_state.json','r',encoding='utf-8')); print(json.dumps(s.get('{args.batch}','?'), indent=2, ensure_ascii=False))"
{'═'*60}
""")


if __name__ == '__main__':
    main()
