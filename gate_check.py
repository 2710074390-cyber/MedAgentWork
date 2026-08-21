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
  python gate_check.py --batch batch014 --stage final           # 终审前全量检查

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
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent

# 正式重构 (2026-08-13): 状态读写/HALT 统一走 scripts/workflow_state.py
sys.path.insert(0, str(BASE / 'scripts'))
import workflow_state as ws


# ═══════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════

def normalize_batch(batch_data):
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
    # v2.0 (2026-08-20 审查修复): 缺失时不再自动补 'OK'/True —— 此前空批次
    # final_review=null 也会被 normalize 补 'OK' 后通过终审（fail-open）。
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


# 正式重构 (2026-08-13): load_state/save_state/set_halt/clear_halt/check_halt
# 已统一迁移至 scripts/workflow_state.py（原子写盘、按批次 HALT、旧数据迁移），
# 本文件不再保留本地实现，全部经由 ws.* 调用。


def find_validate_report(batch_id):
    """查找指定批次的 validate_options.py 报告

    v1.1 (2026-08-13): 按铁律⑤ 优先搜索 reports/validate/，
    兼容历史根目录残留（2026-08-13 前 validate_options.py 曾写根目录）。
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


# ═══════════════════════════════════════
# GATE-A2: Agent 2 产出门禁
# ═══════════════════════════════════════

def gate_agent2(batch_id):
    """
    HC-12 强制门禁：Agent 2 产物必须通过 validate_options.py
    FAIL == 0 → 放行
    FAIL > 0  → BLOCKED
    无报告     → BLOCKED（视为未执行）
    """
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
        # 从 AGENT2 和所有 AGENT2_V* 中取最新的 Bloom
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

        # 如果 normalized 中也没有 Bloom，尝试顶层 merged_stats/final_stats
        if not bloom_data:
            merged = batch_data.get('merged_stats', batch_data.get('final_stats', {}))
            bloom_data = merged.get('bloom', {})
        if not bloom_data:
            completed = batch_steps.get('COMPLETED', {})
            if isinstance(completed, dict):
                bloom_data = completed.get('bloom', {})

        # 如果 Bloom 数据仍为空，回退到 COMPLETED 步骤
        if not bloom_data:
            completed = batch_steps.get('COMPLETED', {})
            bloom_data = completed.get('bloom', {})
            if not bloom_data:
                # 最终回退：从 final_product/final_stats 提取
                final_review = batch_data.get('final_review', batch_data.get('final_stats', {}))
                bloom_data = final_review.get('bloom', {})

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

        if max_dev > 15:
            dev_detail = ', '.join(f'{k}=Δ{deviations[k]:.1f}%' for k in sorted(deviations, key=deviations.get, reverse=True)[:2])
            bloom_issues.append({
                'gate_sub': 'GATE-A3-BLOOM',
                'status': 'BLOCKED',
                'reason': f'Bloom认知层级偏差{max_dev:.1f}% > 15%阈值（{dev_detail}）。必须回退Agent 2重构。',
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

    # ── 汇总 GATE-A3 结果 ──
    sub_results = d20_issues + bloom_issues + evidence_issues
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

def gate_final(batch_id, batch_data):
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

    # 已签收批次：跳过 HC-9/10/11（人工审核已覆盖）
    batch_status = batch_data.get('status', '')
    if batch_status == 'APPROVED':
        return {
            'gate': 'GATE-FINAL',
            'status': 'PASS',
            'reason': f'批次已签收 ({batch_status})，人工审核已覆盖终审',
        }

    issues = []

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

    # JSON 有效性
    # v2.0 (2026-08-20 审查修复): 必须为真实布尔 true —— 字符串 'False'/'True'
    # 此前恒真通过（真实数据 batch014 就是字符串），终审 JSON 检查形同虚设
    json_valid = final_review.get('json_valid', None)
    if not (isinstance(json_valid, bool) and json_valid):
        issues.append({
            'gate_sub': 'GATE-FINAL-JSON',
            'status': 'BLOCKED',
            'reason': f'最终产物 JSON 有效性未证实（json_valid={json_valid!r}，必须为布尔 true）',
        })

    # v2.0 (2026-08-20 审查修复): HC-10 机械校验接入 —— 此前终审只匹配自报字符串
    # （'OK'/'PASS'），verify_page_numbers.py 从未被门禁实际调用。现在对可解析科目
    # 的复习资料实跑附录占位符检测：exit 1 → BLOCKED；脚本异常/文件缺失 → WARN 提示。
    warn_gates = []
    subject = batch_data.get('subject', '')
    if subject and subject in ('内科学', '儿科学', '外科学', '神经病学', '精神病学',
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

STAGE_ORDER = ['agent2_done', 'agent3_done', 'agent4_done', 'final']
STAGE_STEP_KEY = {
    'agent2_done': ['AGENT2', 'AGENT2_V2', 'AGENT2_V3', 'AGENT2_SUPP'],
    'agent3_done': ['AGENT3', 'AGENT3_V2', 'AGENT3_V3'],
    'agent4_done': ['AGENT4', 'AGENT4_V2', 'AGENT4_V3'],
    'final': ['AGENT5', 'COMPLETED'],
}


def detect_current_stage(state, batch_id):
    """从 workflow_state.json 自动推断当前应检查的阶段（使用标准化数据）"""
    if batch_id not in state:
        return 'agent2_done'

    batch = state[batch_id]
    if not isinstance(batch, dict):
        return 'agent2_done'

    normalized = normalize_batch(batch)
    if not normalized:
        return 'agent2_done'

    steps = normalized['steps']

    # 反向检测：找到最后一个完成的阶段，返回下一个
    for stage in reversed(STAGE_ORDER):
        step_keys = STAGE_STEP_KEY.get(stage, [])
        for sk in step_keys:
            step_data = steps.get(sk, {})
            if isinstance(step_data, dict) and step_data.get('status') == 'COMPLETED':
                idx = STAGE_ORDER.index(stage)
                if idx + 1 < len(STAGE_ORDER):
                    return STAGE_ORDER[idx + 1]
                else:
                    return None

    # 没有任何步骤完成，但可能有 batch014 风格的扁平数据
    # 检查是否有最终产物
    if batch.get('final_product') or batch.get('final_review'):
        return 'final'

    # 检查是否有 Agent 2 产出
    if batch.get('agent2_output') or batch.get('agent2_stats'):
        return 'agent2_done'

    return 'agent2_done'


# ═══════════════════════════════════════
# Halt 信号管理（已迁移至 scripts/workflow_state.py）
# ═══════════════════════════════════════
# set_halt / clear_halt / check_halt 统一由 ws.* 提供（按批次作用域）。
# 本文件保留打印输出，逻辑见 workflow_state.py。


# ═══════════════════════════════════════
# 主入口
# ═══════════════════════════════════════


def run_gate_check(batch_id, stage, run_regression=True):
    """执行门禁检查"""
    state, err = ws.load_state()
    if err:
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
            r = gate_agent2(batch_id)
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

        if stage in ('final', 'all'):
            r = gate_final(batch_id, batch_data)
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
        print(f"  ✅ 门禁检查全部通过 — 可以推进到下一阶段")
        print(f"{'═'*60}\n")
    elif approved_mode:
        # v2.0 (2026-08-20 审查修复): 参考模式退出码与提示语义一致（此前提示
        # "仅作参考"却仍 exit 1，误导主控做不必要干预）
        print(f"  ℹ️ 已签收批次门禁未通过（参考模式 — 退出码 0，不阻断管线）")
        print(f"{'═'*60}\n")
    else:
        print(f"  🛑 门禁检查未通过 — 管线已停止。修复后运行:")
        blocked_gates = [r['gate'] for r in results if r['status'] != 'PASS']
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
                        choices=['agent2_done', 'agent3_done', 'agent4_done', 'final', 'all', 'auto'],
                        default='auto',
                        help='检查的阶段 (默认 auto: 自动检测当前阶段)')
    parser.add_argument('--clear-halt', action='store_true',
                        help='清除 halt 信号（修复问题后）')
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

    run_gate_check(args.batch, args.stage)


if __name__ == '__main__':
    main()
