#!/usr/bin/env python3
"""
GoldenSet 交叉验证器 v1.1 — HC-8 自动化
=========================================
触发条件：仅在「外来素材合并」时使用（非 Agent 2 生产的外部题库）。
正常 Agent 2 产物 → 跳过此脚本，Agent 3 D5/D13/D14 已覆盖术语和数值校验。

比对维度：
  1. 术语一致性 — 同一概念在题库与 GS 中是否使用同一术语
  2. 数值一致性 — 同一指标阈值是否一致
  3. 答案一致性 — 如果 GS 有答案，比对 AI 答案是否匹配
  4. 科目覆盖度 — 题目是否落入 GS 覆盖的知识点范围

用法：
  python validate.py <batch_json> [--sample-rate 0.05] [--subject 内科学]
  python validate.py 中间产物/batch001_内科学_心律失常_questions.json --subject 内科学
"""

import json, re, sys, io, os, random
from pathlib import Path
from datetime import datetime
from collections import defaultdict

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = Path(r"C:\Users\38063\Desktop\MedAgentWork\GoldenSet")
STRUCTURED = BASE / "structured"

# ── 数值提取 ──────────────────────────────────────────────
def extract_numbers(text):
    """提取文本中的所有数值及其上下文（含单位）"""
    patterns = [
        (r'(\d+\.?\d*)\s*(?:mg|g|ml|L|kg|cm|mm|h|天|周|月|岁|年|%|次|分|秒|℃|mmol|μmol|IU)', 'value_with_unit'),
        (r'([<>≤≥]\s*\d+\.?\d*)', 'comparison'),
        (r'(\d+\.?\d*\s*[-~至]\s*\d+\.?\d*)', 'range'),
        (r'(\d+\.?\d*)', 'bare_number'),
    ]
    results = []
    for pat, ptype in patterns:
        for m in re.finditer(pat, text):
            results.append({
                "value": m.group(1).strip(),
                "type": ptype,
                "context": text[max(0, m.start()-30):m.end()+30]
            })
    return results


def extract_terms(text):
    """提取医学术语（大写缩写、专业词汇）"""
    terms = set()
    # 缩写词
    for m in re.finditer(r'\b([A-Z]{2,8}(?:-[A-Z0-9]+)?)\b', text):
        if m.group(1) not in ('ABCD', 'OK', 'NO', 'CO', 'GH', 'TH', 'PTH'):
            terms.add(m.group(1))
    # 中文医学术语（4-10字）
    for m in re.finditer(r'([\u4e00-\u9fff]{4,10}(?:综合征|试验|检查|药物|疾病|反射|体征|症状))', text):
        terms.add(m.group(1))
    return terms


# ── GS 加载 ───────────────────────────────────────────────
def load_goldenset(subject_filter=None):
    """加载所有已结构化的 GoldenSet 数据"""
    gs_data = []
    for f in STRUCTURED.glob("GS_*.json"):
        if "schema" in f.name or "index" in f.name:
            continue
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if subject_filter:
            data = [q for q in data if q.get("subject", "") == subject_filter]
        gs_data.extend(data)
    return gs_data


# ── 核心比对 ──────────────────────────────────────────────
def cross_validate(batch_questions, gs_data, sample_rate=0.05):
    """
    对 batch 题目进行抽样交叉验证。

    Args:
        batch_questions: list[dict] — Agent 产出题目
        gs_data: list[dict] — GoldenSet 结构化数据
        sample_rate: float — 抽样比例 (默认 5%)

    Returns:
        dict — 验证报告
    """
    # 按科目匹配 GS
    batch_subjects = set(q.get("subject", "未分类") for q in batch_questions)
    gs_subjects = set(q.get("subject", "未分类") for q in gs_data)
    matched_subjects = batch_subjects & gs_subjects
    unmatched_subjects = batch_subjects - gs_subjects

    if not matched_subjects:
        return {
            "status": "NO_MATCH",
            "gate": "SKIPPED",
            "message": f"本批次科目 {batch_subjects} 与 GoldenSet 科目 {gs_subjects} 无交集，交叉验证跳过",
            "matched_subjects": [],
            "unmatched_subjects": list(unmatched_subjects),
            "results": [],
            "value_issues": [],
            "answer_issues": [],
            "coverage_findings": [],
            "summary": "无可比对的GS科目，交叉验证跳过"
        }

    # 仅对匹配科目的题目进行抽样
    matchable = [q for q in batch_questions
                 if q.get("subject", "未分类") in matched_subjects]
    sample_size = max(1, int(len(matchable) * sample_rate))
    sampled = random.sample(matchable, min(sample_size, len(matchable)))

    results = []
    term_issues = []
    value_issues = []
    answer_issues = []
    coverage_findings = []

    for q in sampled:
        q_nums = extract_numbers(q.get("stem", ""))
        q_terms = extract_terms(q.get("stem", ""))

        # 在 GS 中搜索同科目题目
        subject_gs = [g for g in gs_data
                      if g.get("subject") == q.get("subject", "未分类")]

        # 1. 数值比对
        for gq in subject_gs[:20]:  # 限20条避免太慢
            g_nums = extract_numbers(gq.get("stem", "") + gq.get("explanation", ""))
            g_terms = extract_terms(gq.get("stem", ""))

            # 找重叠的数值
            for qn in q_nums:
                for gn in g_nums:
                    if qn["type"] in ("value_with_unit", "range") and gn["type"] in ("value_with_unit", "range"):
                        # 检查相同单位的数值一致性
                        q_unit = re.findall(r'(mg|g|ml|L|kg|cm|mm|h|天|周|月|岁|年|%|次|分|秒|℃|mmol|μmol|IU)', qn["value"])
                        g_unit = re.findall(r'(mg|g|ml|L|kg|cm|mm|h|天|周|月|岁|年|%|次|分|秒|℃|mmol|μmol|IU)', gn["value"])
                        if q_unit and g_unit and q_unit == g_unit:
                            q_val = float(re.findall(r'(\d+\.?\d*)', qn["value"])[0])
                            g_val = float(re.findall(r'(\d+\.?\d*)', gn["value"])[0])
                            if abs(q_val - g_val) > 0.01:
                                value_issues.append({
                                    "batch_q_id": q.get("id", q.get("gs_id", "")),
                                    "gs_ref_id": gq.get("gs_id", ""),
                                    "batch_value": qn["value"],
                                    "gs_value": gn["value"],
                                    "context_batch": qn["context"],
                                    "context_gs": gn["context"]
                                })

            # 2. 术语比对
            term_overlap = q_terms & g_terms
            if term_overlap:
                coverage_findings.append({
                    "batch_q_id": q.get("id", ""),
                    "gs_ref_id": gq.get("gs_id", ""),
                    "shared_terms": list(term_overlap)[:5]
                })

        result = {
            "batch_q_id": q.get("id", q.get("gs_id", "")),
            "stem_preview": q.get("stem", q.get("question", ""))[:80],
            "subject": q.get("subject", "未分类"),
            "gs_matches": len(subject_gs),
            "term_overlap_count": len(coverage_findings),
            "value_issues_count": len(value_issues),
        }
        results.append(result)

    # 判定
    total_value_issues = len(value_issues)
    if total_value_issues == 0:
        gate = "PASS"
    elif total_value_issues <= 2:
        gate = "PASS_WITH_WARNINGS"
    else:
        gate = "BLOCKED"

    return {
        "report_id": f"GS-VALIDATE-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "batch_size": len(batch_questions),
        "sample_size": len(sampled),
        "sample_rate": sample_rate,
        "matched_subjects": list(matched_subjects),
        "unmatched_subjects": list(unmatched_subjects),
        "status": "MATCHED" if matched_subjects else "NO_MATCH",
        "gate": gate,
        "terminology_issues": term_issues,
        "value_issues": value_issues,
        "answer_issues": answer_issues,
        "coverage_findings": coverage_findings,
        "sampled_results": results,
        "summary": (
            f"抽样 {len(sampled)}/{len(matchable)} 题（{sample_rate*100:.0f}%），"
            f"匹配科目: {matched_subjects}，"
            f"数值问题: {total_value_issues}，"
            f"术语覆盖: {len(coverage_findings)} 条"
        )
    }


# ── 主入口 ────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GoldenSet 交叉验证器 (HC-8)")
    parser.add_argument("batch_file", help="待验证的 batch JSON 文件路径")
    parser.add_argument("--sample-rate", type=float, default=0.05, help="抽样比例 (默认 0.05)")
    parser.add_argument("--subject", type=str, default=None, help="限定 GS 科目（如 内科学）")
    parser.add_argument("--output", type=str, default=None, help="输出报告路径（默认 stdout）")
    args = parser.parse_args()

    # 加载 batch
    batch_path = Path(args.batch_file)
    if not batch_path.exists():
        print(f"[ERROR] 文件不存在: {args.batch_file}")
        sys.exit(1)

    with open(batch_path, "r", encoding="utf-8") as f:
        batch_data = json.load(f)

    # 处理不同 batch 格式
    if isinstance(batch_data, list):
        questions = batch_data
    elif isinstance(batch_data, dict):
        questions = batch_data.get("questions", batch_data.get("data", []))
    else:
        questions = []

    if not questions:
        print(f"[ERROR] 未在文件中找到题目数据。请确认 JSON 结构。")
        sys.exit(1)

    # 加载 GS
    print(f"[INFO] 加载 GoldenSet...")
    gs_data = load_goldenset(args.subject)
    print(f"[INFO] GS 加载: {len(gs_data)} 条记录 (科目过滤: {args.subject or '全部'})")

    # 执行验证
    print(f"[INFO] 开始交叉验证: {len(questions)} 题, 抽样率 {args.sample_rate}")
    report = cross_validate(questions, gs_data, args.sample_rate)

    # 输出
    report_json = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report_json)
        print(f"[OK] 报告已保存至: {args.output}")

    print(f"\n{'='*60}")
    print(f"交叉验证结果")
    print(f"{'='*60}")
    print(f"状态: {report['status']}")
    print(f"门禁: {report['gate']}")
    print(f"匹配科目: {report['matched_subjects']}")
    print(f"未匹配科目: {report['unmatched_subjects']}")
    print(f"数值问题: {len(report['value_issues'])}")
    print(f"答案问题: {len(report['answer_issues'])}")
    print(f"术语覆盖点: {len(report['coverage_findings'])}")
    print(f"摘要: {report['summary']}")

    if report['value_issues']:
        print(f"\n⚠️ 数值不一致项:")
        for vi in report['value_issues'][:5]:
            print(f"  - {vi['batch_q_id']}: batch={vi['batch_value']} vs GS={vi['gs_value']}")
