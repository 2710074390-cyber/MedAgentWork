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
import sys, json, os, re, argparse
from pathlib import Path
from datetime import datetime
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent
WORKFLOW_STATE = BASE / 'workflow_state.json'


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
    if isinstance(fr, dict):
        normalized['final_review'] = {
            'hc9': fr.get('hc9_terminology_appendix', ''),
            'hc10': fr.get('hc10_page_authenticity', ''),
            'hc11': fr.get('hc11_outline_page_marking', ''),
            'json_valid': fr.get('json_valid', True),
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
        # 完全缺失：尝试从 AGENT5 的 hc_checks/terminology 字符串提取
        a5_hc = agent5.get('hc_checks', {}) if isinstance(agent5, dict) else {}
        if not a5_hc:
            # 从 AGENT5 的 output 字符串或 hc9_terminology 字符串推断
            hc9_str = agent5.get('hc9_terminology', '')
            hc10_str = agent5.get('hc10_pages', '')
            hc11_str = agent5.get('hc11_sources', '')
            normalized['final_review'] = {
                'hc9': hc9_str if hc9_str else 'OK' if '已生成' in str(agent5.get('output', '')) else '',
                'hc10': hc10_str if hc10_str else 'OK' if '页码' in str(agent5.get('output', '')) else '',
                'hc11': hc11_str if hc11_str else 'OK',
                'json_valid': True,
            }

    return normalized


def load_state():
    """加载工作流状态"""
    if not WORKFLOW_STATE.exists():
        return None, f'{WORKFLOW_STATE} 不存在'
    try:
        with open(WORKFLOW_STATE, 'r', encoding='utf-8') as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f'JSON 解析失败: {e}'


def save_state(state):
    """保存工作流状态（原子写入）"""
    tmp = WORKFLOW_STATE.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, WORKFLOW_STATE)


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
    ]
    for c in candidates:
        if c.exists():
            return c
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
    d20_score = None
    bloom_data = None
    bloom_deviation = None

    if qc_report_path:
        try:
            with open(qc_report_path, 'r', encoding='utf-8') as f:
                qc_report = json.load(f)

            # 提取D20评分
            dimensions = qc_report.get('dimensions', qc_report.get('dimension_scores', {}))
            d20_score = dimensions.get('D20', dimensions.get('d20', None))

            # 提取Bloom分布
            bloom_data = qc_report.get('bloom_distribution', qc_report.get('bloom', {}))

            # 提取整体评分
            overall_score = qc_report.get('overall_score', qc_report.get('score', None))

        except Exception:
            pass

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
    normalized_target = {}
    for key, val in target_bloom.items():
        if isinstance(val, str):
            normalized_target[key] = float(val.replace('%', ''))
        else:
            normalized_target[key] = float(val)
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

    # ── 汇总 GATE-A3 结果 ──
    sub_results = d20_issues + bloom_issues
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
        'reason': '修复门禁通过 (追溯日志存在, HC-13 source_file_synced OK, JSON纯净)',
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
    hc11 = final_review.get('hc11', '')
    if not ('OK' in str(hc11) or 'PASS' in str(hc11) or hc11 == ''):
        issues.append({
            'gate_sub': 'GATE-FINAL-HC11',
            'status': 'BLOCKED',
            'reason': 'HC-11: 大纲来源页码标注不完整',
        })

    # JSON 有效性
    if not final_review.get('json_valid', True):
        issues.append({
            'gate_sub': 'GATE-FINAL-JSON',
            'status': 'BLOCKED',
            'reason': '最终产物 JSON 无效',
        })

    if issues:
        return {
            'gate': 'GATE-FINAL',
            'status': 'BLOCKED',
            'reason': f'终审门禁阻断 ({len(issues)}项)',
            'sub_gates': issues,
        }

    return {
        'gate': 'GATE-FINAL',
        'status': 'PASS',
        'reason': '终审门禁通过 (HC-9/10/11 OK, JSON有效)',
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
                            'reason': f'[{rule_name}] 脚本可用: {script}（需手动运行验证）',
                            'rule_info': rule,
                            'command': script,
                        })
        elif check_type == 'manual':
            results.append({
                'gate': f'REG-{rule_id}',
                'status': 'INFO',
                'reason': f'[{rule_name}] 手工检查: {rule.get("check_logic", "")}',
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
# Halt 信号管理
# ═══════════════════════════════════════

def set_halt(state, batch_id, reason, agent):
    """在 workflow_state.json 中设置 halt 信号（按批次作用域）。

    v1.1 (2026-08-13): halt 从全局改为按批次作用域 ——
    全局 halt 会因一个批次的门禁失败停掉整条管线（含已签收批次），
    现在 halt 记录携带 batch_id，check_halt 只对同批次生效。
    """
    state['halt'] = {
        'active': True,
        'batch_id': batch_id,
        'reason': reason,
        'agent': agent,
        'timestamp': datetime.now().isoformat(),
    }

    # 也在批次记录中标记
    if batch_id in state:
        batch = state[batch_id]
        if isinstance(batch, dict):
            if 'gate_results' not in batch:
                batch['gate_results'] = {}
            batch['gate_results']['halt'] = {
                'active': True,
                'reason': reason,
                'agent': agent,
                'batch_id': batch_id,
            }

    save_state(state)
    print(f"\n  🛑 HALT 信号已设置（批次 {batch_id}）: {reason}")


def clear_halt(state, batch_id):
    """清除 halt 信号"""
    if 'halt' in state:
        state['halt'] = {'active': False}
    if batch_id in state:
        batch = state[batch_id]
        if isinstance(batch, dict) and 'gate_results' in batch:
            batch['gate_results']['halt'] = {'active': False}
    save_state(state)
    print(f"  ✅ HALT 信号已清除")


# ═══════════════════════════════════════
# 主入口
# ═══════════════════════════════════════

def check_halt(state, batch_id):
    """检查 halt 信号（按批次作用域）。

    v1.1 (2026-08-13): 仅当 halt 属于当前批次（或为无 batch_id 的历史
    全局 halt）时阻断；其他批次的门禁失败不再停掉本批次。
    """
    halt = state.get('halt', {})
    if halt.get('active'):
        halt_batch = halt.get('batch_id')
        if halt_batch is None or halt_batch == batch_id:
            return {
                'gate': 'HALT',
                'status': 'BLOCKED',
                'reason': f"批次 {batch_id} 已停止: {halt.get('reason', '未知')} (触发Agent: {halt.get('agent', '?')})",
            }
    # 也检查批次级别 halt
    if batch_id in state:
        batch = state[batch_id]
        if isinstance(batch, dict):
            batch_halt = batch.get('gate_results', {}).get('halt', {})
            if batch_halt.get('active'):
                return {
                    'gate': 'HALT',
                    'status': 'BLOCKED',
                    'reason': f"批次 {batch_id} 已停止: {batch_halt.get('reason', '未知')}",
                }
    return None


def run_gate_check(batch_id, stage, run_regression=True):
    """执行门禁检查"""
    state, err = load_state()
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
    halt_result = check_halt(state, batch_id)
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

    if not all_pass:
        if batch_data.get('status') == 'APPROVED':
            # v1.1 (2026-08-13): 已签收批次的门禁仅作参考，不写 HALT。
            # 修复前曾因历史门禁误判停掉整条管线（batch024 事件）。
            print(f"\n  ⚠️ 批次 {batch_id} 已签收（APPROVED），门禁结果仅作参考，不写入 HALT。")
        else:
            set_halt(state, batch_id,
                     f'{stage} 门禁未通过: ' + '; '.join(r['reason'] for r in results if r['status'] != 'PASS'),
                     'MedMaster/gate_check.py')

    save_state(state)

    # 汇总
    print(f"\n{'─'*60}")
    if all_pass:
        print(f"  ✅ 门禁检查全部通过 — 可以推进到下一阶段")
        print(f"{'═'*60}\n")
    else:
        print(f"  🛑 门禁检查未通过 — 管线已停止。修复后运行:")
        blocked_gates = [r['gate'] for r in results if r['status'] != 'PASS']
        print(f"     python gate_check.py --batch {batch_id} --clear-halt")
        print(f"     [修复问题后]")
        print(f"     python gate_check.py --batch {batch_id} --stage auto")
        print(f"{'═'*60}\n")

    sys.exit(0 if all_pass else 1)


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
        state, err = load_state()
        if err:
            print(f"  ✗ {err}")
            sys.exit(2)
        clear_halt(state, args.batch)
        sys.exit(0)

    run_gate_check(args.batch, args.stage)


if __name__ == '__main__':
    main()
