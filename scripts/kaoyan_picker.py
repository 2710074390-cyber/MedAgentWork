#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kaoyan_picker.py — 考研真题配额工具（HC-18，2026-08-21 新增）

职责：
  pick   — 从 GoldenSet/structured/ 检索某批次章节对应的考研真题候选（按关键词打分），
           上册（题干/选项, 1994-2024 西综真题试卷）与下册（贺银成精析, 含答案+解析）
           按 gs_id 配对后输出候选 JSON，供 MedGen 按 HC-18 配额（≈20%）引用/改编。
  check  — 终审机械化校验：统计题库 JSON 中 kaoyan_origin 占比，目标 20%（合格带 15%-25%），
           <15% 视为未达标（exit 1）。

用法：
  python scripts/kaoyan_picker.py pick  --subject 内科学 --keywords "心衰,心力衰竭" --target 20 --out 中间产物/batch028/kaoyan_candidates.json
  python scripts/kaoyan_picker.py check --file 最终产物/batch028/ALL_questions_FIXED.json [--out reports/validate/kaoyan_check_batch028.json]

数据要求（项目内既有的 GoldenSet 解析产物，见 GoldenSet/parse_goldenset.py v2.0）：
  GoldenSet/structured/GS_上册_2024.json   字段: gs_id/year/question_no/type/stem/options/answer/explanation/subject/source_file
  GoldenSet/structured/GS_下册_2025_1994.json 字段: gs_id/... answer/explanation（无题干/选项）
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE = Path(__file__).resolve().parent.parent
GS_DIR = BASE / 'GoldenSet' / 'structured'
UP_FILE = GS_DIR / 'GS_上册_2024.json'
LOW_FILE = GS_DIR / 'GS_下册_2025_1994.json'

QUALIFIED_MIN = 0.15   # HC-18 合格带下限
TARGET = 0.20          # HC-18 目标比例（1/5）
QUALIFIED_MAX = 0.25   # 上限（超出仅提示，不拦截）


def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def norm_text(s):
    """用于匹配的规范化文本：去空白/标点/LaTeX 残留"""
    if not isinstance(s, str):
        return ''
    s = re.sub(r'[\\$\\^_{}()（）·:,，。、；;：\s]', '', s)
    return s


def build_joined():
    """上册 × 下册 按 gs_id 配对；返回 [{gs_id, year, question_no, type, subject,
    stem, options, answer, explanation, source_file}]（仅保留有答案且含题干/选项者）"""
    upper = load_json(UP_FILE)
    lower = load_json(LOW_FILE)
    lower_by_id = {q['gs_id']: q for q in lower if q.get('answer')}
    out = []
    for q in upper:
        qid = q.get('gs_id', '')
        low = lower_by_id.get(qid)
        stem = (q.get('stem') or '').strip()
        options = q.get('options') or []
        if not stem or not options or not low:
            continue
        # 上册无答案 → 答案取下册（官方公布/贺银成精析）
        answer = (low.get('answer') or '').strip()
        if not answer:
            continue
        out.append({
            'gs_id': qid,
            'year': q.get('year'),
            'question_no': q.get('question_no'),
            'type': q.get('type', ''),
            'subject': q.get('subject', '未分类'),
            'stem': stem,
            'options': options,
            'answer': answer,
            'explanation': (low.get('explanation') or '').strip(),
            'source_file': '真题上册.md(题干)+真题下册.md(答案解析)',
        })
    return out


def score_candidate(q, keyword_terms, subject_aliases):
    """关键词重叠打分 + 学科字段命中加分"""
    text = norm_text(q['stem'] + q.get('explanation', '') + ''.join(q.get('options', [])))
    score = 0
    matched = []
    for term in keyword_terms:
        t = norm_text(term)
        if t and t in text:
            score += 1
            matched.append(term)
    for alias in subject_aliases:
        if q.get('subject') == alias or (alias in q.get('subject', '')):
            score += 2
            break
    return score, matched


def cmd_pick(args):
    if not UP_FILE.exists() or not LOW_FILE.exists():
        print(f'✗ 缺少 GoldenSet 解析产物：{GS_DIR}')
        print('  请先运行 python GoldenSet/parse_goldenset.py（或用 tools/goldenset/parse_goldenset.py）')
        sys.exit(2)
    joined = build_joined()
    keyword_terms = [k.strip() for k in re.split(r'[,，;；\s]+', args.keywords or '') if k.strip()]
    subject_aliases = [a.strip() for a in re.split(r'[,，;；\s]+', args.subject or '') if a.strip()]
    # 学科名派生短别名：内科学 → 内科；外科学 → 外科；神经病学 → 神经
    derived = []
    for a in subject_aliases:
        for short in (a[:-1], a[:2]):
            if short and short not in subject_aliases and short not in derived:
                derived.append(short)
    subject_aliases += derived

    scored = []
    for q in joined:
        s, matched = score_candidate(q, keyword_terms, subject_aliases)
        if s > 0:
            scored.append((s, q, matched))

    # 排序：分数降序 → 年份降序（优先近年）；同分时保留年份多样性优先
    scored.sort(key=lambda x: (-x[0], -(x[1]['year'] or 0)))

    target = max(1, int(args.target))
    picked = []
    for s, q, matched in scored:
        if len(picked) >= target:
            break
        rec = dict(q)
        rec['score'] = s
        rec['matched_keywords'] = matched
        rec['kaoyan_origin'] = {
            'gs_id': q['gs_id'],
            'year': q['year'],
            'source': f"{q['year']}考研西综·第{q['question_no']}题",
            'mode': '原题',   # MedGen 引用后按实际改为 原题/改编
        }
        picked.append(rec)

    result = {
        'generated_at': 'kaoyan_picker',
        'rule': 'HC-18 考研真题配额（目标 20%，合格带 15%-25%）',
        'subject': args.subject or '',
        'keywords': keyword_terms,
        'target': target,
        'candidates_total_scored': len(scored),
        'candidates': picked,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print(f'✅ 已生成考研真题候选：{out}')
    print(f'  检索总库（有题干+选项+答案）：{len(joined)} 条')
    print(f'  关键词命中候选：{len(scored)} 条 → 输出 Top {len(picked)} 条')
    for r in picked[:10]:
        print(f"    {r['gs_id']} [{r['subject']}] {r['stem'][:38]}…")
    if len(picked) < target:
        print(f'  ⚠️ 命中不足：仅 {len(picked)}/{target}（该章节考研真题覆盖可能有限，其余以原创补齐，'
              f'并在批次统计中注明）')
    return 0


def cmd_check(args):
    data = load_json(Path(args.file))
    questions = data if isinstance(data, list) else data.get('questions', [])
    if not questions:
        print(f'✗ 题库为空或格式不符：{args.file}')
        sys.exit(2)
    total = len(questions)
    kaoyan = [q for q in questions if q.get('kaoyan_origin')]
    ratio = len(kaoyan) / total if total else 0
    ok = QUALIFIED_MIN <= ratio <= QUALIFIED_MAX + 0.05
    report = {
        'file': args.file,
        'rule': 'HC-18 考研真题配额',
        'total': total,
        'kaoyan_count': len(kaoyan),
        'ratio': round(ratio, 4),
        'target': TARGET,
        'qualified_band': [QUALIFIED_MIN, QUALIFIED_MAX],
        'pass': ok,
        'warn': ratio > QUALIFIED_MAX + 0.05,  # 超出上限仅提示
    }
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f'✅ 报告已写入：{out}')
    print(f'📊 HC-18 考研真题配额检查：{args.file}')
    print(f'  题目总数：{total}；考研原题：{len(kaoyan)}（占比 {ratio*100:.1f}%）')
    print(f'  目标：{TARGET*100:.0f}%（合格带 {QUALIFIED_MIN*100:.0f}%-{QUALIFIED_MAX*100:.0f}%）')
    if ok:
        print('  ✅ PASS：考研真题占比达标')
    else:
        print(f'  ✗ FAIL：占比 {ratio*100:.1f}% < {QUALIFIED_MIN*100:.0f}% 下限，'
              f'需补充考研真题或说明「该章节无真题覆盖」')
    if report['warn']:
        print(f'  ⚠️ WARN：占比 {ratio*100:.1f}% 超过上限 {QUALIFIED_MAX*100:.0f}%，'
              f'注意保持原创题比例')
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description='考研真题配额工具（HC-18）')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_pick = sub.add_parser('pick', help='检索并输出考研真题候选')
    p_pick.add_argument('--subject', default='', help='学科名（如 内科学/外科学/神经病学），用于匹配加分')
    p_pick.add_argument('--keywords', default='', help='章节关键词，逗号分隔（如 "心衰,心力衰竭"）')
    p_pick.add_argument('--target', type=int, default=10, help='目标候选数（= 批次题数 × 0.2）')
    p_pick.add_argument('--out', required=True, help='输出 JSON 路径（中间产物/{batchID}/kaoyan_candidates.json）')
    p_pick.set_defaults(func=cmd_pick)

    p_check = sub.add_parser('check', help='终审校验题库 kaoyan_origin 占比')
    p_check.add_argument('--file', required=True, help='题库 JSON（纯数组或含 questions 字段）')
    p_check.add_argument('--out', default='', help='可选：报告 JSON 输出路径')
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == '__main__':
    main()
