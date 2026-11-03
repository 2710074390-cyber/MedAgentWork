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
import sys, json, os, shutil, argparse, re
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent
STATE_FILE = BASE / "workflow_state.json"

# 正式重构 (2026-08-13): 状态读写/血缘统一走 scripts/workflow_state.py
sys.path.insert(0, str(BASE / 'scripts'))
import workflow_state as ws
from utils import md5_file

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


def validate_json_structure(filepath, stage=None):
    """S1/S2 级快速预检：JSON 合法性 + 必填字段

    stage 用于区分「对象形态」的两类产物口径（2026-11-03 修正）：
      - agent3 质检报告：report_metadata + gate_decision
      - agent4 追溯日志：report_metadata + source_file_synced/source_files_synced（HC-13）
    此前不区分阶段，一律按质检报告要求 gate_decision，导致 A4 追溯日志被误判为
    「缺少 gate_decision」并卡在交互确认上。
    """
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
        meta = data.get('report_metadata')
        if stage == 'agent4':
            # A4 追溯日志（HC-12 追溯 / HC-13 溯源）
            if not isinstance(meta, dict):
                issues.append('A4 追溯日志缺少 report_metadata')
            if not (data.get('source_file_synced') or data.get('source_files_synced')):
                issues.append('A4 追溯日志缺少 source_file_synced/source_files_synced（HC-13）')
        else:
            # 质检报告 JSON
            if 'report_metadata' not in data:
                issues.append('质检报告缺少 report_metadata')
            if 'gate_decision' not in (meta if isinstance(meta, dict) else {}):
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

# P1-S4（2026-11-02）：schema 校验不得静默跳过。
# strict 模式：缺 jsonschema 直接判 FAIL，拒绝放行；
# degrade 模式（默认）：用零依赖兜底校验，但必须「显式告警 + 落盘证据」，
#   绝不允许像旧实现那样 except Exception: return [] 假装校验通过。
SCHEMA_STRICT_ENV = 'MEDAGENTWORK_SCHEMA_STRICT'
_DEGRADED_LOG = BASE / 'reports' / 'validate' / 'schema_degraded.jsonl'


def schema_strict() -> bool:
    return os.environ.get(SCHEMA_STRICT_ENV, '').strip().lower() in ('1', 'true', 'yes', 'on')


def _audit_degraded(stage, filepath, mode, detail):
    """把降级校验落成证据（一行一条），让「没跑完整校验」可被审计发现。"""
    try:
        _DEGRADED_LOG.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'stage': stage,
            'file': str(filepath),
            'mode': mode,
            'detail': detail,
        }
        with open(_DEGRADED_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except Exception as e:  # 证据落盘失败不应阻断摄入，但必须喊出来
        print(f"  ⚠️ 降级校验证据写入失败({e})，请手工记录：stage={stage} file={filepath}",
              file=sys.stderr)


def _fallback_checks(filepath, stage):
    """jsonschema 缺失时的零依赖兜底校验。

    覆盖范围（刻意保持窄）：agent2 的数组顶层 + HC-27 概念标注 + 必填字段。
    不实现 JSON Schema 的 $ref/oneOf 等高级关键字 —— 因此它不是等价的 schema 校验，
    每次执行都会被 _audit_degraded 记录（P1-S4：可降级，但不可静默）。
    """
    errs = []
    try:
        data = json.loads(Path(filepath).read_text(encoding='utf-8'))
    except Exception as e:
        return [f'schema[{stage}]: 兜底校验无法解析 JSON: {e}']
    if not isinstance(data, list):
        return [f'schema[{stage}]: 顶层必须是题目数组，实际 {type(data).__name__}']

    if stage == 'agent2':
        required = ('id', 'type')
        for i, q in enumerate(data):
            if not isinstance(q, dict):
                errs.append(f'schema[agent2]: [{i}] 条目必须是对象')
                continue
            missing = [k for k in required if q.get(k) in (None, '')]
            if missing:
                errs.append(f'schema[agent2]: [{i}] 缺少必填字段 {missing}')
        # HC-27 概念标注（v2.1 起必填，零依赖可判定）
        try:
            sys.path.insert(0, str(BASE / 'scripts'))
            import check_source_concepts as csc
            for q in data:
                if not isinstance(q, dict):
                    continue
                if str(q.get('schema_version') or '') != '2.1':
                    continue
                fails, _ = csc.check_question(q)
                errs += [f'schema[agent2]: {x}' for x in fails]
        except Exception as e:
            errs.append(f'schema[agent2]: 兜底校验(concepts)不可用: {e}')
    return errs[:20]


def validate_schema(filepath, stage):
    """契约 schema 校验。

    返回错误列表（空 = 通过）。语义边界（P1-S4 起固定）：
      1. schema 文件缺失       → 显式 SKIP，stderr 告警 + 证据落盘，**不视为通过**
      2. schema/数据解析失败   → 返回错误（FAIL），不再吞成 []
      3. jsonschema 不可用     → strict: FAIL；degrade: 零依赖兜底 + 显式告警 + 证据
      4. 校验器自身异常        → 返回错误（FAIL）
    """
    schema_name = SCHEMA_MAP.get(stage, '')
    if not schema_name:
        print(f"  ⚠️ schema[{stage}]: 该阶段无契约文件（SKIP，不作为通过证据）", file=sys.stderr)
        _audit_degraded(stage, filepath, 'skip_no_contract', 'stage 无 SCHEMA_MAP 条目')
        return []
    schema_file = BASE / 'schemas' / schema_name
    if not schema_file.exists():
        print(f"  ⚠️ schema[{stage}]: 契约文件缺失 {schema_file}（SKIP，不作为通过证据）",
              file=sys.stderr)
        _audit_degraded(stage, filepath, 'skip_missing_schema', str(schema_file))
        return []

    try:
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except Exception as e:
        return [f'schema[{stage}]: 契约文件解析失败（{schema_name}）: {e}']

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return [f'schema[{stage}]: 待校验数据无法解析: {e}']

    try:
        import jsonschema
    except ImportError:
        if schema_strict():
            return [f'schema[{stage}]: 缺少 jsonschema 依赖，strict 模式拒绝放行'
                    f'（装 jsonschema 或设 {SCHEMA_STRICT_ENV}=0 降级）']
        errs = _fallback_checks(filepath, stage)
        print(f"  ⚠️ schema[{stage}]: 缺 jsonschema，已降级为零依赖兜底校验"
              f"（{len(errs)} 个问题）；设 {SCHEMA_STRICT_ENV}=1 可强制 FAIL",
              file=sys.stderr)
        _audit_degraded(stage, filepath, 'degraded_fallback', f'errors={len(errs)}')
        return errs

    try:
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        return [f'schema[{stage}]: {"/".join(map(str, e.path)) or "$"}: {e.message}'
                for e in errors[:20]]
    except Exception as e:
        return [f'schema[{stage}]: 校验器执行失败: {e}']


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


STAGE_PROMPT = {
    'agent2': 'Prompt版本/MedGen_current_prompt.md',
    'agent3': 'Prompt版本/MedQC_current_prompt.md',
    'agent4': 'Prompt版本/MedFix_current_prompt.md',
    'agent5': 'Prompt版本/Agent5_MedReview_Prompt.md',
}


def _sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def lineage_five_tuple(stage, input_path, artifact_path):
    """计算版本五元组（P1-S5）。

    prompt_sha256   —— 该阶段实际所用提示词文件的内容指纹（文件缺失则为空，由 gate 判定）
    config_hash     —— 当前生效阈值指纹（pipeline_config.config_hash）
    input_hash      —— 摄入源文件 sha256
    artifact_sha256 —— 落盘产物 sha256（未移动时与 input 相同）
    model_id        —— 由 --model 传入；strict 批次要求不得为 unknown
    """
    prompt_rel = STAGE_PROMPT.get(stage, '')
    prompt_path = BASE / prompt_rel if prompt_rel else None
    prompt_sha = ''
    if prompt_path and prompt_path.exists():
        try:
            prompt_sha = _sha256_file(prompt_path)
        except Exception as e:
            print(f"  ⚠️ 提示词指纹计算失败({e})，prompt_sha256 留空")
    try:
        import pipeline_config as pc
        cfg_hash = pc.config_hash()
    except Exception as e:
        print(f"  ⚠️ config_hash 计算失败({e})，留空")
        cfg_hash = ''
    try:
        input_hash = _sha256_file(input_path)
    except Exception:
        input_hash = ''
    try:
        artifact_sha = _sha256_file(artifact_path)
    except Exception:
        artifact_sha = input_hash
    return {'prompt_sha256': prompt_sha, 'config_hash': cfg_hash,
            'input_hash': input_hash, 'artifact_sha256': artifact_sha}


def add_lineage(state, batch_id, stage, filepath, file_md5, source=None, model='unknown'):
    """添加血缘记录（统一模块）：模型/Prompt 版本 + 版本五元组。

    P1-S5：batch047+ 走 strict —— 五元组缺项直接抛 LineageIncomplete，
    逼操作者显式声明 --model 与提示词版本，而不是让 unknown 一路流到交付。
    """
    if batch_id not in state:
        print(f"  ⚠️ 批次 {batch_id} 在 workflow_state.json 中不存在，创建新条目")

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

    five = lineage_five_tuple(stage, source or filepath, filepath)
    return ws.add_lineage(state, batch_id, stage, filepath, file_md5,
                          model=model, prompt_version=prompt_version,
                          model_id=model if model != 'unknown' else '',
                          strict=ws.lineage_required(batch_id), **five)


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
        issues = validate_json_structure(source, args.stage)
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
        # A4 的产物是追溯日志（HC-12/HC-13），命名保留「追溯日志」语义：
        # 此前叫 A4_修复版，导致 GATE-A4-TRACE 按 output 里是否含「追溯日志」判定时误判缺失
        'agent4': 'A4_追溯日志',
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
    try:
        batch = add_lineage(state, args.batch, args.stage, dest, file_md5,
                            model=args.model)
    except ws.LineageIncomplete as e:
        print(f"\n  🛑 血缘五元组不完整，已拒绝写入状态：")
        print(f"     {e}")
        print(f"     修正：重跑并显式指定 --model <模型ID>")
        print(f"     历史批次（≤batch{ws.LINEAGE_REQUIRED_SINCE - 1:03d}）不受此约束。")
        sys.exit(3)

    # 补充模型和 Prompt 版本（如果用户指定）
    if args.model != 'unknown':
        batch['lineage'][-1]['agent_model'] = args.model
        batch['lineage'][-1]['model_id'] = args.model
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
