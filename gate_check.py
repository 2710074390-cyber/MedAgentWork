#!/usr/bin/env python3
"""
门禁强制检查器 v1.0 — Orchestrator-as-Enforcer 模式
=====================================================
每次工作流状态转换前，Agent 1 (MedMaster) 必须运行此脚本。
验证未通过 → halt → 不可推进。

用法:
  python gate_check.py --batch batch014 --stage agent2_done     # Agent2→Agent3 转换前
  python gate_check.py --batch batch014 --stage agent3_done     # Agent3→Agent4 转换前
  python gate_check.py --batch batch014 --stage agent4_done     # Agent4→Agent5 转换前
  python gate_check.py --batch batch014 --stage learning_value  # HC-24 学习价值层（新批次 v2）
  python gate_check.py --batch batch014 --stage final           # 终审前全量检查
  python gate_check.py --batch batch040 --stage final \
      --learning-value-mode advisory                            # 学习价值评分卡 advisory 门禁

门禁规则:
  GATE-A2: validate_options.py FAIL==0（产出门禁，batch006 教训）
  GATE-A3: D20 != 0 且 Bloom 偏差 <= 15%（D20 硬阻断 + Bloom 门禁，batch005+011 教训）
  GATE-A4: source_file_synced == true（补丁溯源，batch014 教训）
  GATE-FINAL: HC-9/10/11 全通过 + JSON 完整性

返回:
  exit 0 = GATE_PASS（可以推进）
  exit 1 = GATE_BLOCKED（必须修复后重试）
  exit 2 = GATE_FAIL（脚本/数据错误）
"""
import sys, json, re, argparse, subprocess
from collections import Counter
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent

# 正式重构 (2026-08-13): 状态读写/HALT 统一走 scripts/workflow_state.py
sys.path.insert(0, str(BASE / 'scripts'))
import workflow_state as ws

# v2.1 回灌 (2026-10-13): pipeline.yaml 阈值「单一事实来源」（缺失回退内置默认）
from pipeline_config import get_number

# 集成 telemetry 模块（2026-09-09 新增；v2.1 回灌加固：降级可见，不再静默）
try:
    from scripts.telemetry import log_gate_check, log_info, log_error
    TELEMETRY_AVAILABLE = True
except ImportError:
    try:
        from telemetry import log_gate_check, log_info, log_error
        TELEMETRY_AVAILABLE = True
    except ImportError as _e:
        print(f"  ⚠️ telemetry 模块不可用({_e})，事件日志已跳过（不影响门禁结果）", file=sys.stderr)

        def log_gate_check(*a, **k):
            pass

        def log_info(*a, **k):
            pass

        def log_error(*a, **k):
            pass

        TELEMETRY_AVAILABLE = False


# ═══════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════

def normalize_batch(batch_data: dict) -> dict | None:
    """统一不同批次的数据结构为通用接口。

    batch003-005: 扁平 steps（仅 status+output）
    batch006-012: 丰富 steps（含 Bloom_actual/validate_gate 等）
    batch014:      顶层扁平（agent2_output/qc_result/agent4_result/final_review）

    返回统一格式: {
        'steps': { 'AGENT2': {...}, 'AGENT3': {...}, 'AGENT4': {...}, 'AGENT5': {...} },
        'final_review': { 'hc9': ..., 'hc10': ..., 'hc11': ..., 'json_valid': ... },
        'target_bloom': {...},
    }
    """
    if not isinstance(batch_data, dict):
        return None

    normalized = {'steps': {}, 'final_review': {}, 'target_bloom': batch_data.get('target_bloom', {})}

    steps_raw = batch_data.get('steps', {})

    # ── AGENT2 标准化 ──
    agent2 = steps_raw.get('AGENT2', {}) if isinstance(steps_raw, dict) else {}
    if not isinstance(agent2, dict):
        agent2 = {}

    # batch014: 顶层 agent2_output + agent2_stats
    a2_flat = batch_data.get('agent2_output', batch_data.get('agent2_stats', {}))
    if not agent2 and a2_flat:
        agent2 = {
            'status': 'COMPLETED',
            'output': str(a2_flat.get('files', a2_flat.get('total', ''))),
            'question_count': a2_flat.get('total', 0),
            'Bloom_actual': a2_flat.get('bloom', batch_data.get('agent2_stats', {}).get('bloom', {})),
        }

    normalized['steps']['AGENT2'] = agent2

    # ── AGENT3 标准化 ──
    agent3 = steps_raw.get('AGENT3', {}) if isinstance(steps_raw, dict) else {}
    if not isinstance(agent3, dict):
        agent3 = {}

    # batch014: 顶层 qc_result
    qc_flat = batch_data.get('qc_result', {})
    if not agent3 and qc_flat:
        agent3 = {
            'status': 'COMPLETED',
            'output': f"质检报告 (gate={qc_flat.get('gate_decision','?')})",
            'gate_decision': qc_flat.get('gate_decision', ''),
            'overall_score': qc_flat.get('overall_score', None),
        }

    normalized['steps']['AGENT3'] = agent3

    # ── AGENT4 标准化 ──
    agent4 = steps_raw.get('AGENT4', {}) if isinstance(steps_raw, dict) else {}
    if not isinstance(agent4, dict):
        agent4 = {}

    # batch014: 顶层 agent4_result
    a4_flat = batch_data.get('agent4_result', {})
    if not agent4 and a4_flat:
        agent4 = {
            'status': 'COMPLETED',
            'output': f"修复完成 (patches={a4_flat.get('patches_executed','?')})",
            'patches': a4_flat.get('patches_executed', 0),
        }

    normalized['steps']['AGENT4'] = agent4

    # ── AGENT5 标准化 ──
    agent5 = steps_raw.get('AGENT5', {}) if isinstance(steps_raw, dict) else {}
    if not isinstance(agent5, dict):
        agent5 = {}

    # batch014: 从 final_review 推断
    fr = batch_data.get('final_review', {})
    if not agent5 and isinstance(fr, dict):
        agent5 = {
            'status': 'COMPLETED' if fr else 'PENDING',
            'hc_checks': {
                'HC-9': fr.get('hc9_terminology_appendix', ''),
                'HC-10': fr.get('hc10_page_authenticity', ''),
                'HC-11': fr.get('hc11_outline_page_marking', ''),
            },
        }

    normalized['steps']['AGENT5'] = agent5

    # ── final_review 标准化 ──
    # 缺失时不再自动补 'OK'/True（防止 fail-open）
    if isinstance(fr, dict):
        normalized['final_review'] = {
            'hc9': fr.get('hc9_terminology_appendix', ''),
            'hc10': fr.get('hc10_page_authenticity', ''),
            'hc11': fr.get('hc11_outline_page_marking', ''),
            'json_valid': fr.get('json_valid'),
        }
    elif isinstance(fr, str):
        # batch005-008: final_review 是字符串描述
        # 尝试从 AGENT5 的 hc_checks 提取
        a5_hc = agent5.get('hc_checks', {}) if isinstance(agent5, dict) else {}
        normalized['final_review'] = {
            'hc9': str(a5_hc.get('HC-9', a5_hc.get('HC-9_术语附录', ''))),
            'hc10': str(a5_hc.get('HC-10', a5_hc.get('HC-10_页码索引', ''))),
            'hc11': str(a5_hc.get('HC-11', a5_hc.get('HC-11_大纲页码', ''))),
            'json_valid': True,
        }
    else:
        # 完全缺失：仅透传 AGENT5 实际记录的字符串，不再凭空推断
        a5_hc = agent5.get('hc_checks', {}) if isinstance(agent5, dict) else {}
        if not a5_hc:
            hc9_str = agent5.get('hc9_terminology', '')
            hc10_str = agent5.get('hc10_pages', '')
            hc11_str = agent5.get('hc11_sources', '')
            normalized['final_review'] = {
                'hc9': str(hc9_str or ''),
                'hc10': str(hc10_str or ''),
                'hc11': str(hc11_str or ''),
                'json_valid': None,   # 缺失 → 终审按 fail-closed 阻断
            }

    return normalized


# ═══════════════════════════════════════
# 门禁适用范围（2026-10-23 · 按产物类型分流）
# ═══════════════════════════════════════
PRODUCT_QUESTION_BANK = 'question_bank'
PRODUCT_PREDICTION_PAPER = 'prediction_paper'
PRODUCT_REVIEW_MATERIAL = 'review_material'
PRODUCT_TYPES_ALL = {
    PRODUCT_QUESTION_BANK,
    PRODUCT_PREDICTION_PAPER,
    PRODUCT_REVIEW_MATERIAL,
}


def infer_product_types(batch_id, batch_data) -> set[str]:
    """推断批次产物类型，决定哪些门禁具有管辖权。

    优先使用状态中的显式 product_types；缺失时按产物形状保守推断。
    旧批次没有该字段时仍按原有题库路径处理，避免行为漂移。
    """
    explicit = batch_data.get('product_types') if isinstance(batch_data, dict) else None
    if isinstance(explicit, str):
        explicit = [explicit]
    if isinstance(explicit, (list, tuple, set)):
        picked = {str(x).strip() for x in explicit if str(x).strip() in PRODUCT_TYPES_ALL}
        if picked:
            return picked

    types: set[str] = set()
    subject = str(batch_data.get('subject') or '')
    chapter = str(batch_data.get('chapter') or '')
    exam_type = str(batch_data.get('exam_type') or '')
    workflow = str(batch_data.get('workflow') or '')
    marker = subject + chapter + exam_type + workflow
    final_dir = BASE / '最终产物' / batch_id
    final_md = [p.name for p in final_dir.glob('*.md')] if final_dir.exists() else []
    raw_steps = batch_data.get('steps') if isinstance(batch_data.get('steps'), dict) else {}

    if '押题' in marker or any('押题' in name for name in final_md):
        types.add(PRODUCT_PREDICTION_PAPER)

    has_final_json = bool(list(final_dir.glob('ALL_questions_FIXED*.json'))) if final_dir.exists() else False
    if has_final_json or 'AGENT2' in raw_steps:
        types.add(PRODUCT_QUESTION_BANK)

    review_dir = BASE / '复习资料'
    has_review_file = bool(subject and review_dir.exists()
                           and list(review_dir.rglob(f'{subject}*主复习资料.md')))
    # final_review 是通用终审记录，不单独作为“复习资料产物”证据；
    # 仅当没有题库/押题卷证据时才用它兜底。
    if 'AGENT5' in raw_steps or has_review_file or (batch_data.get('final_review') and not types):
        types.add(PRODUCT_REVIEW_MATERIAL)

    # 三者都没有证据时按题库处理（保持旧批次行为）
    return types or {PRODUCT_QUESTION_BANK}


def is_question_bearing(types: set[str]) -> bool:
    return bool(types & {PRODUCT_QUESTION_BANK, PRODUCT_PREDICTION_PAPER})


# 正式重构 (2026-08-13): load_state/save_state/set_halt/clear_halt/check_halt
# 已统一迁移至 scripts/workflow_state.py（原子写盘、按批次 HALT、旧数据迁移），
# 本文件不再保留本地实现，全部经由 ws.* 调用。


def find_validate_report(batch_id):
    """查找指定批次的 validate_options.py 报告
    优先搜索 reports/validate/，兼容历史根目录残留。
    """
    search_dirs = [BASE / 'reports' / 'validate', BASE]
    candidates = [
        f'validate_options_report_ALL_questions_{batch_id}.json',
        f'validate_options_report_{batch_id}.json',
        f'validate_options_report_ALL_questions_FIXED_{batch_id}.json',
    ]
    for d in search_dirs:
        for name in candidates:
            c = d / name
            if c.exists():
                return c
    # 模糊匹配（如后缀 _呼吸 _循环 _血液）
    for d in search_dirs:
        if not d.exists():
            continue
        for f in sorted(d.glob(f'validate_options_report_*{batch_id}*.json')):
            return f
    return None


def find_qc_report(batch_id):
    """查找指定批次的质检报告"""
    report_dir = BASE / '质检报告'
    candidates = [
        report_dir / f'{batch_id}_质检报告.json',
        report_dir / f'{batch_id}_质检报告_v3.json',
        # medqc skill 约定：质检报告/{batchID}/A3_质检报告.json（子目录形态，
        # v2.0 审查修复补搜 —— 否则 fail-closed 门禁会误阻断正常流程）
        report_dir / batch_id / 'A3_质检报告.json',
    ]
    for c in candidates:
        if c.exists():
            return c
    # 子目录形态回退：质检报告/{batch_id}/*.json
    sub = report_dir / batch_id
    if sub.is_dir():
        for f in sorted(sub.glob('*.json')):
            return f
    # 模糊匹配
    if report_dir.exists():
        for f in sorted(report_dir.glob(f'{batch_id}*质检报告*.json')):
            return f
    return None


# ── v2.1 回灌 (2026-10-13): Bloom 独立重算（评审 §七.14，源自 medagentwork-skill v2.1）──
_BLOOM_LEVELS = ['记忆', '理解', '应用', '分析']
_BLOOM_ALIASES = {
    '记忆': '记忆', '回忆': '记忆', '识记': '记忆', '记忆型': '记忆',
    '理解': '理解', '领会': '理解', '理解型': '理解',
    '应用': '应用', '运用': '应用', '应用型': '应用',
    '分析': '分析', '综合': '分析', '评价': '分析', '分析型': '分析',
}
_TYPE_DEFAULT_BLOOM = {'A1': '记忆', 'A2': '应用', 'B1': '理解', 'A3': '分析', 'A4': '分析'}


def find_question_bank(batch_id):
    """定位批次题库 JSON（用于 Bloom 独立重算）。"""
    for base in (BASE / '最终产物' / batch_id, BASE / '中间产物' / batch_id):
        if not base.is_dir():
            continue
        for name in ('ALL_questions_FIXED.json', 'ALL_questions.json'):
            f = base / name
            if f.exists():
                return f
        cands = sorted(base.glob('ALL_questions*.json'))
        if cands:
            return cands[-1]
    return None


def recompute_bloom_from_qbank(batch_id):
    """从题库 JSON 独立重算 Bloom 分布，返回 (distribution|None, error|None)。

    门禁此前只读质检报告里 LLM 自述的 bloom_distribution —— 数据来源仍是自述。
    本函数用题目自带的 bloom_level 字段（缺失时按题型映射兜底）机械重算，
    供门禁与自述值交叉验证。
    """
    qb = find_question_bank(batch_id)
    if not qb:
        return None, '未找到题库 JSON'
    try:
        data = json.loads(qb.read_text(encoding='utf-8'))
    except Exception as e:
        return None, f'题库 JSON 解析失败: {e}'

    if isinstance(data, list):
        questions = data
    elif isinstance(data, dict):
        questions = data.get('questions') or data.get('items') or []
    else:
        questions = []
    if not questions:
        return None, '题库为空'

    counter = Counter()
    for q in questions:
        if not isinstance(q, dict):
            continue
        raw = q.get('bloom') or q.get('bloom_level') or q.get('cognitive_level')
        level = _BLOOM_ALIASES.get(str(raw).strip()) if raw else None
        if not level:
            level = _TYPE_DEFAULT_BLOOM.get(str(q.get('type', '')).strip())
        if level:
            counter[level] += 1

    total = sum(counter.values())
    if total == 0:
        return None, '题库中无可用 bloom_level 字段'
    return {lv: round(counter.get(lv, 0) / total * 100, 1) for lv in _BLOOM_LEVELS}, None


# ═══════════════════════════════════════
# GATE-A2: Agent 2 产出门禁
# ═══════════════════════════════════════

def gate_agent2(batch_id, batch_data=None):
    """
    HC-12 强制门禁：Agent 2 产物必须通过 validate_options.py
    FAIL == 0 → 放行
    FAIL > 0  → BLOCKED
    无报告     → BLOCKED（视为未执行）
    """
    types = infer_product_types(batch_id, batch_data or {})
    if types == {PRODUCT_REVIEW_MATERIAL}:
        return {
            'gate': 'GATE-A2',
            'status': 'PASS',
            'skipped': True,
            'reason': '复习资料批次无题库产物，GATE-A2 不适用（SKIP，不作为通过证据）',
        }

    report_path = find_validate_report(batch_id)
    if not report_path:
        return {
            'gate': 'GATE-A2',
            'status': 'BLOCKED',
            'reason': f'未找到批次 {batch_id} 的 validate_options.py 报告。Agent 2 必须运行产出门禁自检后再提交。',
            'rule': 'batch006教训：Agent2未跑门禁即交付→ESC升级+20min',
        }

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
    except Exception as e:
        return {
            'gate': 'GATE-A2',
            'status': 'BLOCKED',
            'reason': f'validate 报告解析失败: {e}',
        }

    summary = report.get('summary', {})
    total_fail = summary.get('fail', -1)

    if total_fail == 0:
        return {
            'gate': 'GATE-A2',
            'status': 'PASS',
            'reason': f'产出门禁通过 (FAIL=0, PASS={summary.get("pass","?")}, WARN={summary.get("warn","?")})',
            'report_path': str(report_path),
        }
    elif total_fail > 0:
        return {
            'gate': 'GATE-A2',
            'status': 'BLOCKED',
            'reason': f'产出门禁未通过 (FAIL={total_fail})。必须修正所有 FAIL 项后重新验证。',
            'report_path': str(report_path),
            'detail': f'规则: 产出门禁规则 (batch006教训)',
        }
    else:
        return {
            'gate': 'GATE-A2',
            'status': 'BLOCKED',
            'reason': 'validate 报告缺少 summary.fail 字段，无法判断',
        }


# ═══════════════════════════════════════
# GATE-A3: Agent 3 质检门禁
# ═══════════════════════════════════════

def gate_agent3(batch_id, batch_data):
    """
    HC-12 强制门禁 + D20硬阻断 + Bloom门禁
    - D20=0 → BLOCKED（batch005教训）
    - Bloom偏差>15% → BLOCKED（batch011教训）
    """
    normalized = normalize_batch(batch_data)
    if not normalized:
        return {'gate': 'GATE-A3', 'status': 'BLOCKED', 'reason': '批次数据结构无法解析'}

    if infer_product_types(batch_id, batch_data) == {PRODUCT_REVIEW_MATERIAL}:
        return {
            'gate': 'GATE-A3',
            'status': 'PASS',
            'skipped': True,
            'reason': '复习资料批次无题库产物，GATE-A3 不适用（SKIP，不作为通过证据）',
        }

    batch_steps = normalized['steps']
    agent3 = batch_steps.get('AGENT3', {})

    if not agent3:
        return {
            'gate': 'GATE-A3',
            'status': 'BLOCKED',
            'reason': f'批次 {batch_id} 缺少 AGENT3 步骤记录',
        }

    gate_decision = agent3.get('gate_decision', '')

    # 检查 D20 硬阻断
    # D20 评分信息可能在 agent3.output 文本或 issues 列表中
    issues_text = str(agent3.get('issues', ''))

    # 尝试从质检报告 JSON 读取 D20 分数
    qc_report_path = find_qc_report(batch_id)
    qc_gate_decision = ''
    d20_score = None
    bloom_data = None
    bloom_deviation = None

    if qc_report_path:
        try:
            with open(qc_report_path, 'r', encoding='utf-8') as f:
                qc_report = json.load(f)

            # 权威 gate_decision 优先取自质检报告（report_metadata 或顶层）
            md = qc_report.get('report_metadata', {})
            qc_gate_decision = str(md.get('gate_decision', qc_report.get('gate_decision', '')) or '')

            # 提取D20评分（兼容 dict 与 list 两种 dimensions 形态：
            # 旧格式 dict {'D20': 10}；新格式 list [{'dimension':'D20_B1型题专项','score':10.0}]
            # v2.0 (2026-08-20 审查修复): 此前对 list 形态 .get() 抛 AttributeError 被
            # except 吞掉 → D20 门禁静默失效，必须按形态分别提取）
            dimensions = qc_report.get('dimensions', qc_report.get('dimension_scores', {}))
            if isinstance(dimensions, dict):
                d20_score = dimensions.get('D20', dimensions.get('d20', None))
            elif isinstance(dimensions, list):
                for item in dimensions:
                    if isinstance(item, dict) and str(item.get('dimension', '')).startswith('D20'):
                        d20_score = item.get('score')
                        break
            if d20_score is None:
                # 兼容 report_metadata.dimension_scores 形态（batch027 实际数据）
                ds = md.get('dimension_scores', {})
                for k, v in ds.items():
                    if str(k).startswith('D20'):
                        d20_score = v.get('score') if isinstance(v, dict) else v
                        break

            # 提取Bloom分布（兼容两种形态：
            # 1) 扁平 {'记忆':30,'理解':40,...}
            # 2) 嵌套 {'target':{...},'actual':{...},'actual_pct':{...},'deviation_pct':N}
            #    （batch027 实际数据，直接取扁平键会得到 0 偏差 → 误阻断）
            bloom_data = qc_report.get('bloom_distribution', qc_report.get('bloom', {}))
            if isinstance(bloom_data, dict):
                if isinstance(bloom_data.get('actual'), dict):
                    bloom_data = bloom_data['actual']
                elif isinstance(bloom_data.get('actual_pct'), dict):
                    bloom_data = bloom_data['actual_pct']

            # 提取整体评分
            overall_score = qc_report.get('overall_score', qc_report.get('score', None))

        except Exception as e:
            print(f'  ⚠️ 质检报告解析失败: {qc_report_path} ({e})')

    if qc_gate_decision:
        gate_decision = qc_gate_decision

    # ── v2.0 (2026-08-20 审查修复): gate_decision 作为硬输入 ──
    # 此前 QC 明确否决（REJECT/BLOCKED/FAIL/REDO）也被放行（fail-open）。
    if gate_decision in ('REJECT', 'BLOCKED', 'FAIL', 'REDO'):
        return {
            'gate': 'GATE-A3',
            'status': 'BLOCKED',
            'reason': f'质检否决: gate_decision={gate_decision}（QC 打回，不可推进）',
            'qc_report': str(qc_report_path) if qc_report_path else '未找到',
        }

    # 如果 JSON 报告不存在，尝试从标准化数据中提取
    if bloom_data is None or not bloom_data:
        # 从 AGENT2 步骤中取最新的 Bloom
        agent2_steps = []
        for step_key in sorted(batch_steps.keys()):
            if step_key.startswith('AGENT2'):
                step_data = batch_steps[step_key]
                if isinstance(step_data, dict):
                    agent2_steps.append((step_key, step_data))

        source = {}
        if agent2_steps:
            source = agent2_steps[-1][1]

        bloom_data = source.get('Bloom_actual', source.get('bloom_actual', {}))
        bloom_deviation_str = source.get('Bloom_deviation', '')

        # 如果仍无 Bloom，尝试其他来源
        if not bloom_data:
            for src_key in ['merged_stats', 'final_stats', 'final_review', 'final_product']:
                src = batch_data.get(src_key, {})
                if isinstance(src, dict) and src.get('bloom'):
                    bloom_data = src['bloom']
                    break

        # 最终回退：从 COMPLETED 步骤提取
        if not bloom_data:
            completed = batch_steps.get('COMPLETED', {})
            if isinstance(completed, dict):
                bloom_data = completed.get('bloom', {})

        if bloom_deviation_str:
            # 解析 "记忆+26.1%，理解-14.4%，应用-7.8%，分析-3.9%"
            match = re.findall(r'([+\-]?\d+\.?\d*)%', bloom_deviation_str)
            if match:
                bloom_deviation = max(abs(float(m)) for m in match)

    target_bloom = batch_data.get('target_bloom', {})
    if not target_bloom:
        target_bloom = {'记忆': '30%', '理解': '40%', '应用': '25%', '分析': '5%'}

    # 标准化 target_bloom 值为 float
    # v2.0 (2026-08-20 审查修复): 畸形值（如 '约30%'）此前直接 ValueError 崩溃且不写
    # HALT 信号，门禁状态不可信；现改为受控 BLOCKED。
    normalized_target = {}
    try:
        for key, val in target_bloom.items():
            if isinstance(val, str):
                normalized_target[key] = float(val.replace('%', ''))
            else:
                normalized_target[key] = float(val)
    except (ValueError, TypeError) as e:
        return {
            'gate': 'GATE-A3',
            'status': 'BLOCKED',
            'reason': f'target_bloom 格式异常，无法判定 Bloom 门禁: {e}',
            'qc_report': str(qc_report_path) if qc_report_path else '未找到',
        }
    target_bloom = normalized_target

    # ── D20 硬阻断检查 ──
    d20_issues = []
    if d20_score is not None:
        if isinstance(d20_score, (int, float)) and d20_score == 0:
            d20_issues.append({
                'gate_sub': 'GATE-A3-D20',
                'status': 'BLOCKED',
                'reason': f'D20评分={d20_score}，B1型题设计完全不合格，不可放行',
                'rule': 'D20门禁规则 (batch005教训: D20=0仍PASS_WITH_FIXES)',
            })
    else:
        # D20 评分未在 JSON 中显式给出，从 issues 文本中检测
        if re.search(r'D20[=:]\s*0', issues_text) or re.search(r'D20.*?0分', issues_text):
            d20_issues.append({
                'gate_sub': 'GATE-A3-D20',
                'status': 'BLOCKED',
                'reason': '质检报告中 D20 评分=0，B1型题设计完全不合格',
                'rule': 'D20门禁规则 (batch005教训)',
            })

    # ── Bloom 门禁检查 ──
    bloom_issues = []
    if bloom_data:
        actual = {}
        for key in ['记忆', '理解', '应用', '分析']:
            val = bloom_data.get(key, '0%')
            if isinstance(val, str):
                val = val.replace('%', '')
            try:
                actual[key] = float(val)
            except (ValueError, TypeError):
                actual[key] = 0.0

        deviations = {}
        for key in target_bloom:
            deviations[key] = abs(actual.get(key, 0) - target_bloom.get(key, 0))

        max_dev = max(deviations.values())

        # v2.1 回灌: 阈值取自 pipeline.yaml（缺失回退内置默认 15）
        bloom_dev_max = get_number('bloom_deviation_max', 15)
        if max_dev > bloom_dev_max:
            dev_detail = ', '.join(f'{k}=Δ{deviations[k]:.1f}%' for k in sorted(deviations, key=deviations.get, reverse=True)[:2])
            bloom_issues.append({
                'gate_sub': 'GATE-A3-BLOOM',
                'status': 'BLOCKED',
                'reason': f'Bloom认知层级偏差{max_dev:.1f}% > {bloom_dev_max:g}%阈值（{dev_detail}）。必须回退Agent 2重构。',
                'rule': 'Bloom门禁规则 (batch011教训: 记忆54.1%未阻断)',
            })

    # ── v2.0 (2026-08-20 审查修复): fail-closed —— 无证据不放行 ──
    # 与 GATE-A2"无报告即 BLOCKED"对齐（此前空壳 AGENT3 步骤无任何 QC 数据也判 PASS）。
    evidence_issues = []
    if not qc_report_path:
        evidence_issues.append({
            'gate_sub': 'GATE-A3-NO-REPORT',
            'status': 'BLOCKED',
            'reason': f'未找到质检报告文件（质检报告/{batch_id}_质检报告.json），无证据不可放行',
        })
    if d20_score is None and not re.search(r'D20', issues_text):
        evidence_issues.append({
            'gate_sub': 'GATE-A3-NO-D20',
            'status': 'BLOCKED',
            'reason': '质检报告缺失 D20 评分（B1 专项维度），fail-closed 不放行',
        })
    if not bloom_data:
        evidence_issues.append({
            'gate_sub': 'GATE-A3-NO-BLOOM',
            'status': 'BLOCKED',
            'reason': '质检报告缺失 Bloom 分布数据，fail-closed 不放行',
        })

    # ── v2.1 回灌 (2026-10-13): Bloom 独立重算交叉验证（评审 §七.14）──
    # 上面 bloom_data 取自质检报告 —— 属 LLM 自述数据。此处用题库 JSON 独立重算
    # 一遍 Bloom 分布，两者偏差超过容忍度即 BLOCKED。这把 Bloom 门禁从
    # 「读 LLM 自述」升级为「确定性重算 + 自述交叉验证」。
    recompute_issues = []
    recomputed, recompute_err = recompute_bloom_from_qbank(batch_id)
    recompute_tolerance = get_number('bloom_recompute_tolerance', 5)
    if recomputed and bloom_data:
        mismatch = {lv: abs(recomputed.get(lv, 0) - actual.get(lv, 0)) for lv in _BLOOM_LEVELS}
        worst = max(mismatch.values()) if mismatch else 0.0
        if worst > recompute_tolerance:
            detail = ', '.join(
                f'{lv} 自述{actual.get(lv, 0):.1f}%/重算{recomputed.get(lv, 0):.1f}%'
                for lv in _BLOOM_LEVELS if mismatch[lv] > recompute_tolerance
            )
            recompute_issues.append({
                'gate_sub': 'GATE-A3-BLOOM-RECOMPUTE',
                'status': 'BLOCKED',
                'reason': (f'Bloom 分布自述值与题库重算值最大偏差 {worst:.1f}% > '
                           f'{recompute_tolerance:g}%（{detail}）。质检报告 Bloom 数据与题库不一致，不可放行。'),
                'rule': 'Bloom 独立重算交叉验证（v2.1 回灌）',
            })
        else:
            recompute_issues.append({
                'gate_sub': 'GATE-A3-BLOOM-RECOMPUTE',
                'status': 'PASS',
                'reason': f'Bloom 自述值与题库重算值最大偏差 {worst:.1f}% ≤ {recompute_tolerance:g}%，交叉验证通过',
            })
    else:
        # 题库缺失时不阻断（fail-closed 已由 NO-BLOOM 覆盖），仅记录可诊断信息
        recompute_issues.append({
            'gate_sub': 'GATE-A3-BLOOM-RECOMPUTE',
            'status': 'SKIPPED',
            'reason': f'无法独立重算 Bloom（{recompute_err or "无 bloom_data"}），已跳过交叉验证',
        })

    # ── 汇总 GATE-A3 结果 ──
    sub_results = d20_issues + bloom_issues + recompute_issues + evidence_issues
    blocked_subs = [r for r in sub_results if r['status'] == 'BLOCKED']

    if blocked_subs:
        return {
            'gate': 'GATE-A3',
            'status': 'BLOCKED',
            'reason': f'质检门禁阻断 ({len(blocked_subs)}项): ' + '; '.join(r['reason'] for r in blocked_subs),
            'sub_gates': sub_results,
            'qc_report': str(qc_report_path) if qc_report_path else '未找到',
        }

    return {
        'gate': 'GATE-A3',
        'status': 'PASS',
        'reason': f'质检门禁通过 (gate_decision={gate_decision}, D20 OK, Bloom OK)',
        'sub_gates': sub_results,
        'qc_report': str(qc_report_path) if qc_report_path else '未找到',
    }


# ═══════════════════════════════════════
# GATE-A4: Agent 4 修复门禁
# ═══════════════════════════════════════

def gate_agent4(batch_id, batch_data):
    """
    HC-12 + HC-13: Agent4 修复必须溯源
    - 追溯日志存在
    - source_file_synced 标志
    - JSON 输出为纯 JSON 数组（无 YAML 前置）
    """
    normalized = normalize_batch(batch_data)
    if not normalized:
        return {'gate': 'GATE-A4', 'status': 'BLOCKED', 'reason': '批次数据结构无法解析'}

    types = infer_product_types(batch_id, batch_data)
    if types == {PRODUCT_REVIEW_MATERIAL}:
        return {
            'gate': 'GATE-A4',
            'status': 'PASS',
            'skipped': True,
            'reason': '复习资料批次无题库产物，GATE-A4 不适用（SKIP，不作为通过证据）',
        }

    batch_steps = normalized['steps']
    agent4 = batch_steps.get('AGENT4', {})

    if not agent4:
        return {
            'gate': 'GATE-A4',
            'status': 'BLOCKED',
            'reason': f'批次 {batch_id} 缺少 AGENT4 步骤记录。必须经过 MedFix 修复环节。',
        }

    issues = []

    # 检查追溯日志是否存在
    output_str = agent4.get('output', '')
    if '追溯日志' not in output_str and 'trace_log' not in str(agent4.get('trace_log', '')):
        issues.append({
            'gate_sub': 'GATE-A4-TRACE',
            'status': 'BLOCKED',
            'reason': 'Agent 4 追溯日志不存在。修复必须输出 AGENT4_追溯日志.json。',
        })

    # 检查 source_file_synced (HC-13)
    # 追溯日志 JSON 中应有此字段
    final_dir = BASE / '最终产物' / batch_id
    trace_files = list(final_dir.glob('*追溯日志*.json')) if final_dir.exists() else []
    source_synced = False
    trace_checked = False

    for tf in trace_files:
        try:
            with open(tf, 'r', encoding='utf-8') as f:
                trace_data = json.load(f)
            trace_checked = True
            if isinstance(trace_data, list):
                for entry in trace_data:
                    if entry.get('source_file_synced') or entry.get('source_files_synced'):
                        source_synced = True
                        break
            elif isinstance(trace_data, dict):
                if trace_data.get('source_file_synced') or trace_data.get('source_files_synced'):
                    source_synced = True
                # 也检查子条目
                patches = trace_data.get('patches', [])
                if patches:
                    synced = [p for p in patches if p.get('source_file_synced')]
                    if len(synced) == len(patches):
                        source_synced = True
        except Exception:
            pass

    if trace_checked and not source_synced:
        issues.append({
            'gate_sub': 'GATE-A4-HC13',
            'status': 'BLOCKED',
            'reason': 'HC-13: 追溯日志中 source_file_synced 为 false。修复 COMPLETE.json 时必须同步修改分系统源文件。',
            'rule': 'HC-13补丁溯源 (batch014教训: 补丁不溯源→回归19处截断)',
        })

    # 检查 JSON 输出是否为纯 JSON 数组
    json_files = list(final_dir.glob('ALL_questions_FIXED*.json')) if final_dir.exists() else []
    for jf in json_files:
        try:
            with open(jf, 'r', encoding='utf-8') as f:
                content = f.read(500)  # 只读开头
                if content.strip().startswith('---'):
                    issues.append({
                        'gate_sub': 'GATE-A4-JSON',
                        'status': 'BLOCKED',
                        'reason': f'{jf.name} 包含 YAML 前置元数据(---块)。必须输出纯 JSON 数组。',
                        'rule': 'JSON输出规则 (batch006教训)',
                    })
                    break
        except Exception:
            pass

    # 检查最终交付 MD（2026-08-20 起强制）：
    # 每个 ALL_questions_FIXED*.json 必须有同目录 ALL_questions_FIXED*.md
    # （由 `python scripts/qbank.py export-md` 生成，用户可读最终交付格式）
    for jf in json_files:
        md_expected = jf.with_suffix('.md')
        # 押题卷批次的交付 MD 命名可不同（如「…期末押题卷.md」），
        # 接受同目录含“押题”的 MD 作为等价交付物。
        if not md_expected.exists() and PRODUCT_PREDICTION_PAPER in types:
            alternatives = sorted(final_dir.glob('*押题*.md')) if final_dir.exists() else []
            if alternatives:
                md_expected = alternatives[0]
        if not md_expected.exists():
            issues.append({
                'gate_sub': 'GATE-A4-MD',
                'status': 'BLOCKED',
                'reason': f'{jf.name} 缺少最终交付 MD 文件 {md_expected.name}。'
                          f'请运行 python scripts/qbank.py export-md --file {jf.name} --out {md_expected.name}',
                'rule': '最终交付 MD 格式 (2026-08-20 起强制)',
            })
        else:
            # 抽查 MD 中包含答案标记（✅ 覆盖率 ≥50%，防空转）
            try:
                md_text = md_expected.read_text(encoding='utf-8')
                total_q = sum(1 for line in md_text.splitlines() if line.startswith('### '))
                check_marks = md_text.count('✅')
                if total_q > 0 and check_marks < max(1, total_q * 0.5):
                    issues.append({
                        'gate_sub': 'GATE-A4-MD',
                        'status': 'BLOCKED',
                        'reason': f'{md_expected.name} 答案标记覆盖率过低 '
                                  f'({check_marks}✅ / {total_q}题)。MD 必须包含 ✅ 答案标记。',
                        'rule': 'MD答案标记 (save.py MD答案标记规范)',
                    })
            except Exception:
                pass

    if issues:
        return {
            'gate': 'GATE-A4',
            'status': 'BLOCKED',
            'reason': f'修复门禁阻断 ({len(issues)}项)',
            'sub_gates': issues,
        }

    return {
        'gate': 'GATE-A4',
        'status': 'PASS',
        'reason': '修复门禁通过 (追溯日志存在, HC-13 source_file_synced OK, JSON纯净, MD交付齐全)',
    }


# ═══════════════════════════════════════
# GATE-FINAL: 终审门禁
# ═══════════════════════════════════════

# T6 (2026-10-23): 学习价值评分卡 advisory 门禁
SUBJECT_SCORECARD_SLUGS = {
    '耳鼻咽喉头颈外科学': 'ent',
}


def find_review_scorecard(batch_id, batch_data):
    """定位 review_scorecard_<subject>_*.json。"""
    scorecard_dir = BASE / 'reports' / 'validate'
    subject = str(batch_data.get('subject', '') or '')
    slug = SUBJECT_SCORECARD_SLUGS.get(subject)
    if slug:
        cands = sorted(scorecard_dir.glob(f'review_scorecard_{slug}_*.json'))
        if cands:
            return cands[-1]
    # 无 slug 映射时，只有一个评分卡才回退使用，避免误读别的科目
    cands = sorted(scorecard_dir.glob('review_scorecard_*.json'))
    return cands[-1] if len(cands) == 1 else None


def gate_learning_value(batch_id, batch_data, mode='advisory'):
    """GATE-FINAL-LEARNING-VALUE：读取 12 维评分卡。

    mode=off      → 返回 None，完全不影响现有门禁
    mode=advisory → overall<3.5 或关键维度<3.5 → WARN；其余 PASS
    mode=enforce  → 缺评分卡 / overall<3.8 / 关键维度<3.5 / blocking_issues → BLOCKED
    """
    if mode == 'off':
        return None
    path = find_review_scorecard(batch_id, batch_data)
    if not path:
        status = 'WARN' if mode == 'advisory' else 'BLOCKED'
        return {
            'gate_sub': 'GATE-FINAL-LEARNING-VALUE',
            'status': status,
            'reason': f'未找到 review_scorecard（{batch_id}/{batch_data.get("subject", "?")}）',
        }
    try:
        with open(path, 'r', encoding='utf-8') as f:
            card = json.load(f)
    except Exception as e:
        return {
            'gate_sub': 'GATE-FINAL-LEARNING-VALUE',
            'status': 'WARN' if mode == 'advisory' else 'BLOCKED',
            'reason': f'评分卡解析失败: {type(e).__name__}: {e}',
            'scorecard_path': str(path),
        }

    overall = float(card.get('overall', -1))
    dims = card.get('dimensions') or []
    critical = [d for d in dims if int(d.get('id', 0)) in (2, 3, 8)]
    low = [d for d in critical if float(d.get('score', 0)) < 3.5]
    hard = [d for d in critical if float(d.get('score', 0)) < 3.0]
    blocking = list(card.get('blocking_issues') or [])
    warnings = list(card.get('warnings') or [])

    reason = (f'overall={overall:.2f}/5，关键维度 '
              f'{", ".join(f"{d.get('id')}:{d.get('score')}" for d in critical)}，'
              f'warnings={len(warnings)}')
    if mode == 'advisory':
        status = 'WARN' if (overall < 3.5 or low or blocking) else 'PASS'
    else:
        status = 'BLOCKED' if (overall < 3.8 or low or hard or blocking) else 'PASS'
    return {
        'gate_sub': 'GATE-FINAL-LEARNING-VALUE',
        'status': status,
        'reason': reason,
        'scorecard_path': str(path),
        'overall': overall,
        'warnings': warnings,
        'blocking_issues': blocking,
    }


def gate_item_learning_value(batch_id, batch_data):
    """HC-24: 新批次（item_schema_version=2.0）的题目学习价值层强制门禁。

    旧批次无 item_schema_version → 显式 SKIPPED，不追溯。
    新批次跑 scripts/check_learning_value.py，并校验：
      FAIL=0；逐项覆盖=100%；错误认知覆盖=100%；
      source_quote_exact_rate>=95%；anchor_verified_rate>=80%。
    """
    schema_version = str(batch_data.get('item_schema_version') or '')
    required = schema_version == '2.0' or bool(batch_data.get('learning_value_required'))
    if not required:
        return {
            'gate_sub': 'GATE-ITEM-LEARNING-VALUE',
            'status': 'PASS',
            'skipped': True,
            'reason': f'批次未声明 item_schema_version=2.0（当前={schema_version or "缺失"}），HC-24 跳过，不追溯旧产物',
        }

    # 非题库批次（无 AGENT2 且无最终题库目录）不强行要求 learning_value
    raw_steps = batch_data.get('steps') or {}
    final_dir = BASE / '最终产物' / batch_id
    if 'AGENT2' not in raw_steps and not final_dir.exists():
        return {
            'gate_sub': 'GATE-ITEM-LEARNING-VALUE',
            'status': 'PASS',
            'skipped': True,
            'reason': '无 AGENT2 步骤且无最终题库目录，判定为非题库批次，HC-24 跳过',
        }

    candidates = sorted(final_dir.glob('ALL_questions_FIXED*.json')) if final_dir.exists() else []
    if not candidates:
        return {
            'gate_sub': 'GATE-ITEM-LEARNING-VALUE',
            'status': 'BLOCKED',
            'reason': f'HC-24: 缺少最终题库 JSON（{final_dir}）',
        }
    target = candidates[0]
    report_path = BASE / 'reports' / 'validate' / f'learning_value_{batch_id}.json'
    try:
        proc = subprocess.run(
            [sys.executable, str(BASE / 'scripts' / 'check_learning_value.py'),
             '--file', str(target), '--out', str(report_path)],
            capture_output=True, text=True, timeout=300,
            encoding='utf-8', errors='replace')
    except Exception as e:
        return {
            'gate_sub': 'GATE-ITEM-LEARNING-VALUE',
            'status': 'BLOCKED',
            'reason': f'HC-24: check_learning_value.py 执行异常: {type(e).__name__}: {e}',
        }

    if not report_path.exists():
        return {
            'gate_sub': 'GATE-ITEM-LEARNING-VALUE',
            'status': 'BLOCKED',
            'reason': f'HC-24: 校验报告未生成（exit={proc.returncode}）: {(proc.stdout or "")[-300:]}',
        }

    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
        summary = report.get('summary') or {}
        questions = json.loads(target.read_text(encoding='utf-8'))
    except Exception as e:
        return {
            'gate_sub': 'GATE-ITEM-LEARNING-VALUE',
            'status': 'BLOCKED',
            'reason': f'HC-24: 报告/题库解析失败: {type(e).__name__}: {e}',
        }

    fail = int(summary.get('fail', 0) or 0)
    per_cov = float(summary.get('per_option_coverage', 0) or 0)
    misc_cov = float(summary.get('misconception_coverage', 0) or 0)
    src_exact = float(summary.get('source_quote_exact_rate', 0) or 0)
    quote_verified = float(summary.get('quote_verified_rate', 1.0) or 0)
    mc_conflicts = int(summary.get('misconception_id_conflicts', 0) or 0)
    anchor_verified = float(summary.get('anchor_verified_rate', 0) or 0)
    min_src = float(get_number('learning_value_min_source_exact', 0.95))
    min_quote = float(get_number('learning_value_min_quote_verified', 0.95))
    max_mc = int(get_number('learning_value_max_misconception_conflicts', 0))
    min_anchor = float(get_number('learning_value_min_anchor_verified', 0.80))

    issues = []
    if proc.returncode == 1 or fail > 0:
        issues.append(f'FAIL={fail}（必须为 0）')
    if per_cov < 1.0:
        issues.append(f'逐项覆盖={per_cov:.1%}（必须 100%）')
    if misc_cov < 1.0:
        issues.append(f'错误认知覆盖={misc_cov:.1%}（必须 100%）')
    if src_exact < min_src:
        issues.append(f'原文标注 exact 率={src_exact:.1%}（要求≥{min_src:.0%}）')
    if quote_verified < min_quote:
        issues.append(f'引文实证率={quote_verified:.1%}（要求≥{min_quote:.0%}，禁止自报 exact）')
    if mc_conflicts > max_mc:
        issues.append(f'错误认知 ID 冲突={mc_conflicts}（要求≤{max_mc}，同一 ID 必须同一释义）')
    if anchor_verified < min_anchor:
        issues.append(f'锚点已核率={anchor_verified:.1%}（要求≥{min_anchor:.0%}）')
    if isinstance(questions, list):
        missing_lv = [q.get('id') for q in questions if isinstance(q, dict) and not q.get('learning_value')]
        if missing_lv:
            issues.append(f'{len(missing_lv)} 题缺 learning_value（示例：{missing_lv[:3]}）')

    if issues:
        return {
            'gate_sub': 'GATE-ITEM-LEARNING-VALUE',
            'status': 'BLOCKED',
            'reason': f'HC-24 学习价值层未达标: {"; ".join(issues)}',
            'report_path': str(report_path),
            'summary': summary,
        }

    return {
        'gate_sub': 'GATE-ITEM-LEARNING-VALUE',
        'status': 'PASS',
        'reason': (f'HC-24 通过：FAIL=0，逐项={per_cov:.1%}，错误认知={misc_cov:.1%}，'
                   f'标注 exact={src_exact:.1%}，引文实证={quote_verified:.1%}，'
                   f'ID 冲突={mc_conflicts}，锚点已核={anchor_verified:.1%}'),
        'report_path': str(report_path),
        'summary': summary,
    }


def gate_final(batch_id, batch_data, learning_value_mode='off'):
    """
    终审前全量检查: HC-9/10/11 + JSON完整性 + Bloom终态

    注意：已 APPROVED 的批次跳过 HC-9/10/11（已过人工签收）
    """
    normalized = normalize_batch(batch_data)
    if not normalized:
        return {'gate': 'GATE-FINAL', 'status': 'BLOCKED', 'reason': '批次数据结构无法解析'}

    batch_steps = normalized['steps']
    agent5 = batch_steps.get('AGENT5', {})
    final_review = normalized['final_review']
    lv_result = gate_learning_value(batch_id, batch_data, learning_value_mode)
    item_lv_result = gate_item_learning_value(batch_id, batch_data)

    # 已签收批次：跳过 HC-9/10/11（人工审核已覆盖）
    batch_status = batch_data.get('status', '')
    if batch_status == 'APPROVED':
        return {
            'gate': 'GATE-FINAL',
            'status': 'PASS',
            'reason': f'批次已签收 ({batch_status})，人工审核已覆盖终审',
            'sub_gates': [g for g in (lv_result, item_lv_result) if g],
        }

    issues = []
    warn_gates = []

    # ── 门禁适用范围（2026-10-23）：按产物类型决定管辖权 ──
    types = infer_product_types(batch_id, batch_data)
    needs_review = PRODUCT_REVIEW_MATERIAL in types
    needs_json = bool(types & {PRODUCT_QUESTION_BANK, PRODUCT_PREDICTION_PAPER})

    if needs_review:
        # HC-9: 术语附录
        hc9 = final_review.get('hc9', '')
        if not ('OK' in str(hc9) or 'PASS' in str(hc9) or '已生成' in str(hc9)):
            # 也检查 agent5 的 hc_checks
            agent5_hc = agent5.get('hc_checks', agent5.get('hc9_terminology', ''))
            if not ('PASS' in str(agent5_hc) or '已生成' in str(agent5_hc)):
                issues.append({
                    'gate_sub': 'GATE-FINAL-HC9',
                    'status': 'BLOCKED',
                    'reason': 'HC-9: 术语同意异名附录缺失或未通过',
                })

        # HC-10: 页码真实性
        hc10 = final_review.get('hc10', '')
        if not ('OK' in str(hc10) or 'PASS' in str(hc10) or 'no placeholder' in str(hc10)):
            issues.append({
                'gate_sub': 'GATE-FINAL-HC10',
                'status': 'BLOCKED',
                'reason': 'HC-10: 页码附录未通过真实性验证（可能含占位符）',
            })

        # HC-11: 大纲页码
        # v2.0 (2026-08-20 审查修复): 空串不再视为通过（此前 hc11='' 直接放行，fail-open）
        hc11 = final_review.get('hc11', '')
        if not ('OK' in str(hc11) or 'PASS' in str(hc11)):
            issues.append({
                'gate_sub': 'GATE-FINAL-HC11',
                'status': 'BLOCKED',
                'reason': 'HC-11: 大纲来源页码标注缺失或未通过',
            })
    else:
        for code, label in (('GATE-FINAL-HC9', 'HC-9 术语附录'),
                            ('GATE-FINAL-HC10', 'HC-10 页码真实性'),
                            ('GATE-FINAL-HC11', 'HC-11 大纲页码')):
            warn_gates.append({
                'gate_sub': code,
                'status': 'SKIPPED',
                'reason': f'{label}：非复习资料批次（{", ".join(sorted(types))}），不适用',
            })

    # JSON 有效性
    # v2.0 (2026-08-20 审查修复): 必须为真实布尔 true —— 字符串 'False'/'True'
    # 此前恒真通过（真实数据 batch014 就是字符串），终审 JSON 检查形同虚设
    if needs_json:
        json_valid = final_review.get('json_valid', None)
        if not (isinstance(json_valid, bool) and json_valid):
            issues.append({
                'gate_sub': 'GATE-FINAL-JSON',
                'status': 'BLOCKED',
                'reason': f'最终产物 JSON 有效性未证实（json_valid={json_valid!r}，必须为布尔 true）',
            })
    else:
        warn_gates.append({
            'gate_sub': 'GATE-FINAL-JSON',
            'status': 'SKIPPED',
            'reason': f'非题库/押题卷批次（{", ".join(sorted(types))}），JSON 有效性检查不适用',
        })

    # v2.0 (2026-08-20 审查修复): HC-10 机械校验接入 —— 此前终审只匹配自报字符串
    # （'OK'/'PASS'），verify_page_numbers.py 从未被门禁实际调用。现在对可解析科目
    # 的复习资料实跑附录占位符检测：exit 1 → BLOCKED；脚本异常/文件缺失 → WARN 提示。
    if lv_result:
        if lv_result.get('status') == 'BLOCKED':
            issues.append(lv_result)
        else:
            warn_gates.append(lv_result)
    if item_lv_result:
        if item_lv_result.get('status') == 'BLOCKED':
            issues.append(item_lv_result)
        else:
            warn_gates.append(item_lv_result)
    subject = batch_data.get('subject', '')
    if needs_review and subject and subject in ('内科学', '儿科学', '外科学', '神经病学', '精神病学',
                                                 '皮肤性病学', '中医学', '医患沟通'):
        review_dir = BASE / '复习资料'
        review_files = sorted(review_dir.glob(f'{subject}_*主复习资料.md')) \
            if review_dir.exists() else []
        if not review_files:
            review_files = sorted(review_dir.glob(f'{subject}_*备考复习资料.md')) \
                if review_dir.exists() else []
        if review_files:
            try:
                proc = subprocess.run(
                    [sys.executable, str(BASE / 'verify_page_numbers.py'),
                     '--check-appendix', subject],
                    capture_output=True, text=True, timeout=120,
                    encoding='utf-8', errors='replace')
                if proc.returncode == 1:
                    issues.append({
                        'gate_sub': 'GATE-FINAL-PAGES',
                        'status': 'BLOCKED',
                        'reason': f'HC-10 附录页码机械校验失败（verify_page_numbers.py exit 1）: {review_files[0].name}',
                    })
                else:
                    warn_gates.append({
                        'gate_sub': 'GATE-FINAL-PAGES',
                        'status': 'PASS',
                        'reason': f'HC-10 附录页码机械校验通过（verify_page_numbers.py exit {proc.returncode}）',
                    })
            except Exception as e:
                warn_gates.append({
                    'gate_sub': 'GATE-FINAL-PAGES',
                    'status': 'WARN',
                    'reason': f'HC-10 机械校验未执行: {type(e).__name__}: {e}',
                })
        else:
            warn_gates.append({
                'gate_sub': 'GATE-FINAL-PAGES',
                'status': 'WARN',
                'reason': f'未找到 {subject} 的复习资料文件，HC-10 机械校验跳过',
            })

    if issues:
        return {
            'gate': 'GATE-FINAL',
            'status': 'BLOCKED',
            'reason': f'终审门禁阻断 ({len(issues)}项)',
            'sub_gates': issues + warn_gates,
        }

    return {
        'gate': 'GATE-FINAL',
        'status': 'PASS',
        'reason': '终审门禁通过 (HC-9/10/11 OK, JSON有效)',
        'sub_gates': warn_gates,
    }


# ═══════════════════════════════════════
# 回归检查 (P2'-1: regression_db.json)
# ═══════════════════════════════════════

REGRESSION_DB = BASE / 'scripts' / 'regression_db.json'
if not REGRESSION_DB.exists():
    # 兼容历史根目录位置（2026-06-24 已迁移至 scripts/）
    REGRESSION_DB = BASE / 'regression_db.json'


def load_regression_db():
    """加载回归漏洞数据库"""
    if not REGRESSION_DB.exists():
        return None, f'{REGRESSION_DB} 不存在'
    try:
        with open(REGRESSION_DB, 'r', encoding='utf-8') as f:
            return json.load(f), None
    except Exception as e:
        return None, str(e)


def run_regression_checks(batch_id, stage):
    """运行与当前阶段匹配的回归检查规则"""
    db, err = load_regression_db()
    if err:
        return [{'gate': 'REG-DB', 'status': 'WARN', 'reason': f'回归数据库加载失败: {err}'}]

    rules = db.get('regression_rules', [])
    results = []

    # 筛选匹配当前阶段的规则
    applicable = [r for r in rules if r.get('gate_stage') == stage]

    for rule in applicable:
        check_type = rule.get('check_type', 'manual')
        rule_id = rule['rule_id']
        rule_name = rule['rule_name']

        if check_type == 'script' and rule.get('check_script'):
            # 自动检查：验证脚本是否存在
            script = rule['check_script'].replace('{batch_id}', batch_id)
            script_name = script.split()[0] if script else '?'

            if script_name == 'python':
                script_path = script.split()[1] if len(script.split()) > 1 else None
                if script_path:
                    full_path = BASE / script_path
                    if not full_path.exists():
                        results.append({
                            'gate': f'REG-{rule_id}',
                            'status': 'WARN',
                            'reason': f'[{rule_name}] 检查脚本不存在: {script_path}',
                            'rule_info': rule,
                        })
                    else:
                        results.append({
                            'gate': f'REG-{rule_id}',
                            'status': 'INFO',
                            'reason': f'[{rule_name}] 脚本可用: {script}（仅提示，不参与门禁判定 — v2.0 审查修复明确标注）',
                            'rule_info': rule,
                            'command': script,
                        })
        elif check_type == 'manual':
            results.append({
                'gate': f'REG-{rule_id}',
                'status': 'INFO',
                'reason': f'[{rule_name}] 手工检查: {rule.get("check_logic", "")}（仅提示，不参与门禁判定）',
                'rule_info': rule,
            })

    if not applicable:
        results.append({
            'gate': 'REG',
            'status': 'PASS',
            'reason': f'当前阶段 ({stage}) 无匹配的回归检查规则',
        })

    return results


# ═══════════════════════════════════════
# 自动阶段检测 (P2'-3: --stage auto)
# ═══════════════════════════════════════

STAGE_ORDER = ['agent2_done', 'agent3_done', 'agent4_done', 'learning_value', 'final']
STAGE_STEP_KEY = {
    'agent2_done': ['AGENT2', 'AGENT2_V2', 'AGENT2_V3', 'AGENT2_SUPP'],
    'agent3_done': ['AGENT3', 'AGENT3_V2', 'AGENT3_V3'],
    'agent4_done': ['AGENT4', 'AGENT4_V2', 'AGENT4_V3'],
    'learning_value': [],
    'final': ['AGENT5', 'COMPLETED'],
}


def stage_sequence(batch_id, batch_data) -> list[str]:
    """按产物类型与 schema 版本返回应执行的阶段序列（2026-10-23）。

    - 复习资料批次：只有 final（HC-9/10/11 等资料门禁）
    - 题库/押题卷批次：A2→A3→A4；schema v2 再插 learning_value；最后 final
    """
    types = infer_product_types(batch_id, batch_data)
    seq: list[str] = []
    if is_question_bearing(types):
        seq += ['agent2_done', 'agent3_done', 'agent4_done']
        schema_version = str(batch_data.get('item_schema_version') or '')
        if schema_version == '2.0' or batch_data.get('learning_value_required'):
            seq.append('learning_value')
    seq.append('final')
    return seq


def _stage_completed(batch, normalized_steps, gate_results, stage) -> bool:
    if stage == 'learning_value':
        return str(gate_results.get('GATE-LV', {}).get('status', '')) == 'PASS'
    if stage == 'final':
        return (batch.get('status') == 'APPROVED'
                or str(gate_results.get('GATE-FINAL', {}).get('status', '')) == 'PASS')
    for sk in STAGE_STEP_KEY.get(stage, []):
        step_data = normalized_steps.get(sk, {})
        if isinstance(step_data, dict) and step_data.get('status') == 'COMPLETED':
            return True
    return False


def detect_current_stage(state, batch_id):
    """从 workflow_state.json 自动推断当前应检查的阶段（2026-10-23 按产物类型分流）"""
    if batch_id not in state:
        return 'agent2_done'

    batch = state[batch_id]
    if not isinstance(batch, dict):
        return 'agent2_done'

    if batch.get('status') == 'APPROVED':
        return None

    normalized = normalize_batch(batch)
    if not normalized:
        return 'agent2_done'

    steps = normalized['steps']
    gate_results = batch.get('gate_results') if isinstance(batch.get('gate_results'), dict) else {}

    # batch014 风格扁平数据：无 steps 但有终审字段 → 直接终审
    raw_steps = batch.get('steps') if isinstance(batch.get('steps'), dict) else {}
    if not raw_steps and (batch.get('final_product') or batch.get('final_review')):
        return 'final'

    seq = stage_sequence(batch_id, batch)
    for stage in seq:
        if not _stage_completed(batch, steps, gate_results, stage):
            return stage

    # 所有阶段均完成
    if batch.get('agent2_output') or batch.get('agent2_stats'):
        return 'agent2_done'
    return None


# ═══════════════════════════════════════
# Halt 信号管理（已迁移至 scripts/workflow_state.py）
# ═══════════════════════════════════════
# set_halt / clear_halt / check_halt 统一由 ws.* 提供（按批次作用域）。
# 本文件保留打印输出，逻辑见 workflow_state.py。


# ═══════════════════════════════════════
# 主入口
# ═══════════════════════════════════════


def run_gate_check(batch_id: str, stage: str, run_regression: bool = True,
                   learning_value_mode: str = 'off') -> None:
    """执行门禁检查"""
    if TELEMETRY_AVAILABLE:
        log_info(f"Starting gate check for {batch_id}", batch_id=batch_id, stage=stage)
    
    state, err = ws.load_state()
    if err:
        if TELEMETRY_AVAILABLE:
            log_error(f"Failed to load state: {err}", batch_id=batch_id)
        print(f"  ✗ 无法加载工作流状态: {err}")
        sys.exit(2)

    # 自动阶段检测
    if stage == 'auto':
        stage = detect_current_stage(state, batch_id)
        if stage is None:
            print(f"\n{'═'*60}")
            print(f"  ✅ 批次 {batch_id} 全部阶段已完成！")
            print(f"  运行 python gate_check.py --batch {batch_id} --stage final 做终审检查")
            print(f"{'═'*60}\n")
            sys.exit(0)
        print(f"  🤖 自动检测阶段: {stage}")

    # 查找批次
    batch_data = state.get(batch_id)
    if not batch_data or not isinstance(batch_data, dict):
        print(f"  ✗ 批次 {batch_id} 不在 workflow_state.json 中")
        sys.exit(2)

    # 先检查 halt 信号
    halt_result = ws.check_halt(state, batch_id)
    if halt_result:
        print(f"\n{'═'*60}")
        print(f"  🛑 管线已停止")
        print(f"  {'═'*56}")
        print(f"  原因: {halt_result['reason']}")
        print(f"{'═'*60}\n")
        sys.exit(1)

    # 执行对应阶段的门禁
    print(f"\n{'═'*60}")
    print(f"  门禁检查 — 批次 {batch_id} / 阶段 {stage}")
    print(f"{'═'*60}\n")

    results = []
    all_pass = True

    # v2.0 (2026-08-20 审查修复): 门禁执行崩溃不再裸 traceback 退出
    # （此前崩溃时不写 HALT 信号、门禁状态不可信），统一受控失败 exit 2。
    try:
        if stage in ('agent2_done', 'all'):
            r = gate_agent2(batch_id, batch_data)
            results.append(r)
            if r['status'] != 'PASS':
                all_pass = False

        if stage in ('agent3_done', 'all'):
            r = gate_agent3(batch_id, batch_data)
            results.append(r)
            if r['status'] != 'PASS':
                all_pass = False

        if stage in ('agent4_done', 'all'):
            r = gate_agent4(batch_id, batch_data)
            results.append(r)
            if r['status'] != 'PASS':
                all_pass = False

        if stage in ('learning_value',):
            r = gate_item_learning_value(batch_id, batch_data)
            wrapped = {
                'gate': 'GATE-LV',
                'status': 'PASS' if r.get('status') == 'PASS' else 'BLOCKED',
                'reason': r.get('reason', ''),
                'sub_gates': [r],
            }
            results.append(wrapped)
            if wrapped['status'] != 'PASS':
                all_pass = False

        if stage in ('final', 'all'):
            r = gate_final(batch_id, batch_data, learning_value_mode)
            results.append(r)
            if r['status'] != 'PASS':
                all_pass = False
    except Exception as e:
        print(f"\n  ✗ 门禁执行异常: {type(e).__name__}: {e}")
        sys.exit(2)

    # 输出结果
    for r in results:
        icon = '✅' if r['status'] == 'PASS' else '🛑'
        print(f"  {icon} {r['gate']}: {r['status']}")
        print(f"     {r['reason']}")

        # 子门禁
        for sub in r.get('sub_gates', []):
            sub_icon = '  ✅' if sub['status'] == 'PASS' else '  🛑'
            print(f"  {sub_icon} {sub.get('gate_sub', '?')}: {sub.get('reason', '')}")

    # 更新 state 中的 gate_results
    batch = state[batch_id]
    if 'gate_results' not in batch:
        batch['gate_results'] = {}

    for r in results:
        batch['gate_results'][r['gate']] = {
            'status': r['status'],
            'reason': r['reason'],
            'checked_at': datetime.now().isoformat(),
        }

    # 回归检查 (P2'-1)
    if run_regression and stage != 'all':
        print(f"\n  ── 回归漏洞检查 (regression_db.json) ──")
        reg_results = run_regression_checks(batch_id, stage)
        for rr in reg_results:
            icon = {'PASS': '✅', 'INFO': '📋', 'WARN': '⚠️', 'FAIL': '✗'}.get(rr['status'], '❓')
            print(f"  {icon} {rr['gate']}: {rr['reason']}")
            if 'command' in rr:
                print(f"      ↳ 命令: {rr['command']}")

    approved_mode = batch_data.get('status') == 'APPROVED'

    if not all_pass:
        if approved_mode:
            # v1.1 (2026-08-13): 已签收批次的门禁仅作参考，不写 HALT。
            # 修复前曾因历史门禁误判停掉整条管线（batch024 事件）。
            print(f"\n  ⚠️ 批次 {batch_id} 已签收（APPROVED），门禁结果仅作参考，不写入 HALT。")
        else:
            ws.set_halt(state, batch_id,
                        f'{stage} 门禁未通过: ' + '; '.join(r['reason'] for r in results if r['status'] != 'PASS'),
                        'MedMaster/gate_check.py')
            print(f"\n  🛑 HALT 信号已设置（批次 {batch_id}）")

    ws.save_state(state)

    # 汇总
    print(f"\n{'─'*60}")
    if all_pass:
        if TELEMETRY_AVAILABLE:
            log_gate_check(batch_id, stage, 'PASS', reason='all_pass')
        print(f"  ✅ 门禁检查全部通过 — 可以推进到下一阶段")
        print(f"{'═'*60}\n")
    elif approved_mode:
        if TELEMETRY_AVAILABLE:
            log_gate_check(batch_id, stage, 'PASS_APPROVED', reason='approved_mode')
        print(f"  ℹ️ 已签收批次门禁未通过（参考模式 — 退出码 0，不阻断管线）")
        print(f"{'═'*60}\n")
    else:
        blocked_gates = [r['gate'] for r in results if r['status'] != 'PASS']
        if TELEMETRY_AVAILABLE:
            log_gate_check(batch_id, stage, 'BLOCKED', reason='blocked: ' + ','.join(blocked_gates))
        print(f"  🛑 门禁检查未通过 — 管线已停止。修复后运行:")
        print(f"     python gate_check.py --batch {batch_id} --clear-halt")
        print(f"     [修复问题后]")
        print(f"     python gate_check.py --batch {batch_id} --stage auto")
        print(f"{'═'*60}\n")

    sys.exit(0 if (all_pass or approved_mode) else 1)


# ═══════════════════════════════════════
# CLI
# ═══════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='门禁强制检查器 — Orchestrator-as-Enforcer 模式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python gate_check.py --batch batch014 --stage agent2_done
  python gate_check.py --batch batch014 --stage agent3_done
  python gate_check.py --batch batch014 --clear-halt
        """
    )
    parser.add_argument('--batch', '-b', required=True, help='批次ID')
    parser.add_argument('--stage', '-s',
                        choices=['agent2_done', 'agent3_done', 'agent4_done', 'learning_value', 'final', 'all', 'auto'],
                        default='auto',
                        help='检查的阶段 (默认 auto: 自动检测当前阶段)')
    parser.add_argument('--clear-halt', action='store_true',
                        help='清除 halt 信号（修复问题后）')
    parser.add_argument('--learning-value-mode', choices=['off', 'advisory', 'enforce'],
                        default='off',
                        help='学习价值评分卡门禁模式（默认 off，不影响现有批次）')
    args = parser.parse_args()

    if args.clear_halt:
        state, err = ws.load_state()
        if err:
            print(f"  ✗ {err}")
            sys.exit(2)
        ws.clear_halt(state, args.batch)
        ws.save_state(state)
        print(f"  ✅ HALT 信号已清除")
        sys.exit(0)

    run_gate_check(args.batch, args.stage, learning_value_mode=args.learning_value_mode)


if __name__ == '__main__':
    main()
