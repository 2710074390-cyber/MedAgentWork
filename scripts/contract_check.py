#!/usr/bin/env python3
"""
Agent Contract Validator v1.0
=============================
验证各 Agent 产出是否符合 JSON Schema 约定。
参考: Pact Contract Testing / JSON Schema Validation

用法:
  python scripts/contract_check.py --agent agent2 --batch batch014
  python scripts/contract_check.py --agent agent3 --file 质检报告/batch014_质检报告.json
  python scripts/contract_check.py --all                     # 验证所有批次的完整契约链
"""
import sys, json, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent.parent
# v2.0 (2026-08-20 审查修复): 契约单一事实源收敛 —— 此前读 schemas/agent_contracts.json
# （旧合并契约，与 *_output.schema.json 漂移，对真实 batch027 全量误报 120 错误）。
# 现在直接读 ingest.py 实际校验用的 schemas/{agent}_output.schema.json。
SCHEMA_FILES = {
    'agent2_output': 'agent2_output.schema.json',
    'agent3_output': 'agent3_output.schema.json',
    'agent4_output': 'agent4_output.schema.json',
}
CST = timezone(timedelta(hours=8))


def load_schemas():
    out = {}
    for key, fname in SCHEMA_FILES.items():
        p = BASE / 'schemas' / fname
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                out[key] = json.load(f)
    return out


def validate_against_schema(data, schema, path=""):
    """用 jsonschema Draft7 校验，返回错误字符串列表。

    v2.0 (2026-08-20 审查修复): 弃用自研简化校验器（不支持 anyOf/items/$ref，
    且 bool 是 int 子类等误放行），直接复用与 ingest 相同的标准实现。
    """
    try:
        import jsonschema
    except ImportError:
        return [f'{path or "$"}: jsonschema 未安装，无法校验']
    try:
        jsonschema.Draft7Validator(schema).validate(data)
        return []
    except jsonschema.ValidationError as e:
        loc = '/'.join(str(p) for p in e.path) or path or '$'
        return [f'{loc}: {e.message}']


def find_agent_output(batch_id, agent_id):
    """查找指定批次的 Agent 产出文件"""
    if agent_id == 'agent2':
        candidates = [
            BASE / '中间产物' / batch_id / 'ALL_questions.json',
            BASE / '中间产物' / batch_id / 'ALL_questions_batch014.json',
            BASE / '中间产物' / batch_id / 'ALL_questions_v2.json',
            BASE / '中间产物' / batch_id / 'ALL_questions_v3.json',
        ]
    elif agent_id == 'agent3':
        candidates = [
            BASE / '质检报告' / f'{batch_id}_质检报告.json',
            BASE / '质检报告' / f'{batch_id}_质检报告_v3.json',
        ]
        # 模糊匹配
        qc_dir = BASE / '质检报告'
        if qc_dir.exists():
            for f in sorted(qc_dir.glob(f'{batch_id}*质检报告*.json')):
                candidates.append(f)
    elif agent_id == 'agent4':
        final_dir = BASE / '最终产物' / batch_id
        candidates = [
            final_dir / 'AGENT4_追溯日志.json',
        ]
        if final_dir.exists():
            candidates.extend(sorted(final_dir.glob('*追溯日志*.json')))
    elif agent_id == 'agent5':
        candidates = [
            BASE / '复习资料' / f'{batch_id}_主复习资料.md',
        ]
    else:
        return None

    for c in candidates:
        if c.exists():
            return c
    return None


def check_agent2(batch_id):
    """验证 Agent 2 产出"""
    schema = load_schemas()['agent2_output']['items']
    filepath = find_agent_output(batch_id, 'agent2')

    if not filepath:
        return {'agent': 'agent2', 'batch': batch_id, 'status': 'SKIP',
                'detail': '未找到 Agent 2 产出文件'}

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        return {'agent': 'agent2', 'batch': batch_id, 'status': 'FAIL',
                'detail': '产出不是 JSON 数组', 'file': str(filepath)}

    errors = []
    questions_with_errors = set()

    for item in data:
        item_errors = validate_against_schema(item, schema)
        if item_errors:
            qid = item.get('id', '?')
            questions_with_errors.add(qid)
            # 只记录前 10 个错误
            if len(errors) < 50:
                errors.extend(item_errors)

    return {
        'agent': 'agent2',
        'batch': batch_id,
        'file': str(filepath),
        'total_questions': len(data),
        'valid': len(data) - len(questions_with_errors),
        'invalid': len(questions_with_errors),
        'status': 'PASS' if len(questions_with_errors) == 0 else 'FAIL',
        'errors': errors[:20],
    }


def check_agent3(batch_id):
    """验证 Agent 3 质检报告"""
    schema = load_schemas()['agent3_output']
    filepath = find_agent_output(batch_id, 'agent3')

    if not filepath:
        return {'agent': 'agent3', 'batch': batch_id, 'status': 'SKIP',
                'detail': '未找到质检报告'}

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    errors = validate_against_schema(data, schema)

    return {
        'agent': 'agent3',
        'batch': batch_id,
        'file': str(filepath),
        # v2.0 (2026-08-20 审查修复): 契约违反此前只报 WARN 永不 FAIL，
        # 无法作为门禁；契约不符即 FAIL
        'status': 'PASS' if not errors else 'FAIL',
        'errors': errors,
    }


def check_agent4(batch_id):
    """验证 Agent 4 追溯日志"""
    schema = load_schemas()['agent4_output']
    filepath = find_agent_output(batch_id, 'agent4')

    if not filepath:
        return {'agent': 'agent4', 'batch': batch_id, 'status': 'SKIP',
                'detail': '未找到追溯日志'}

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Agent4 日志可能是数组或单个对象
    if isinstance(data, list):
        errors = []
        for entry in data:
            errors.extend(validate_against_schema(entry, schema))
    else:
        errors = validate_against_schema(data, schema)

    # 专门检查 source_file_synced (HC-13)
    synced = False
    if isinstance(data, list):
        synced = any(e.get('source_file_synced') for e in data if isinstance(e, dict))
    elif isinstance(data, dict):
        synced = data.get('source_file_synced', False)

    if not synced:
        errors.append('HC-13: source_file_synced 为 false — 补丁未溯源')

    return {
        'agent': 'agent4',
        'batch': batch_id,
        'file': str(filepath),
        'source_file_synced': synced,
        # v2.0 (2026-08-20 审查修复): HC-13 溯源违反是硬门禁，必须 FAIL
        'status': 'PASS' if not errors else 'FAIL',
        'errors': errors,
    }


def check_all():
    """检查所有批次的所有 Agent"""
    state_path = BASE / 'workflow_state.json'
    if not state_path.exists():
        print("workflow_state.json 不存在")
        return

    with open(state_path, 'r', encoding='utf-8') as f:
        state = json.load(f)

    batches = {k: v for k, v in state.items()
               if k not in ('active_batch', 'halt', 'system_config', 'gate_system')
               and isinstance(v, dict)}

    all_results = []

    for batch_id in sorted(batches.keys()):
        for agent_id in ['agent2', 'agent3', 'agent4']:
            if agent_id == 'agent2':
                r = check_agent2(batch_id)
            elif agent_id == 'agent3':
                r = check_agent3(batch_id)
            elif agent_id == 'agent4':
                r = check_agent4(batch_id)
            all_results.append(r)

    # 汇总
    passes = sum(1 for r in all_results if r['status'] == 'PASS')
    fails = sum(1 for r in all_results if r['status'] == 'FAIL')
    warns = sum(1 for r in all_results if r['status'] == 'WARN')
    skips = sum(1 for r in all_results if r['status'] == 'SKIP')

    print(f"\n{'═'*60}")
    print(f"  Agent Contract 验证 — 全部批次")
    print(f"  {passes} PASS  {warns} WARN  {fails} FAIL  {skips} SKIP")
    print(f"{'═'*60}")

    for r in all_results:
        if r['status'] == 'SKIP':
            continue
        icon = {'PASS': '✅', 'WARN': '⚠️', 'FAIL': '✗'}[r['status']]
        detail = ''
        if 'total_questions' in r:
            detail = f"({r['valid']}/{r['total_questions']} valid)"
        if 'source_file_synced' in r:
            detail = f"(source_synced={r['source_file_synced']})"
        print(f"  {icon} {r['agent']}.{r['batch']:12s} {detail}")
        if r.get('errors'):
            for e in r['errors'][:3]:
                print(f"      ↳ {e}")

    return all_results


def main():
    parser = argparse.ArgumentParser(description='Agent Contract Validator')
    parser.add_argument('--agent', choices=['agent2', 'agent3', 'agent4'],
                       help='检查特定 Agent')
    parser.add_argument('--batch', help='检查特定批次')
    parser.add_argument('--all', action='store_true', help='检查所有批次')
    args = parser.parse_args()

    if args.all:
        results = check_all()
        # v2.0 (2026-08-20 审查修复): 有 FAIL 即非零退出 —— 此前恒 exit 0，
        # 无法用于任何门禁/CI
        sys.exit(1 if any(r['status'] == 'FAIL' for r in results) else 0)
    elif args.agent and args.batch:
        if args.agent == 'agent2':
            r = check_agent2(args.batch)
        elif args.agent == 'agent3':
            r = check_agent3(args.batch)
        elif args.agent == 'agent4':
            r = check_agent4(args.batch)
        icon = {'PASS': '✅', 'WARN': '⚠️', 'FAIL': '✗', 'SKIP': '⏭️'}[r['status']]
        print(f"\n{icon} {r['agent']}.{r['batch']}: {r['status']}")
        if r.get('errors'):
            for e in r['errors'][:10]:
                print(f"  ↳ {e}")
        sys.exit(1 if r['status'] == 'FAIL' else 0)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
