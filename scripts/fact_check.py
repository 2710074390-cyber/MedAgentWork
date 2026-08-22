#!/usr/bin/env python3
"""
fact_check.py — 事实校验机械化 v1.0 (2026-08-13 · 架构 P1-1)

目的: 关闭"LLM 自证"后门 —— 把"LLM 说查过教材"变成机器可验证的闸门。

命令:
  pages   — 页码反查: 题目 source_pages 对照教材分块索引
            （知识库素材/chunks_metadata/{code}_chunks.jsonl 的真实 page_number）
  golden  — GoldenSet 交叉验证 (HC-8 机械化): 新题 vs 金标准(下册含答案解析)
            术语重叠(Jaccard) + 数值冲突检测

用法:
  python scripts/fact_check.py pages --file 最终产物/batch022/ALL_questions_FIXED.json --subject neurology
  python scripts/fact_check.py golden --file 最终产物/batch022/ALL_questions_FIXED.json --subject 神经病学
  python scripts/fact_check.py golden --file X --limit 50    # 抽样加速

设计约束: 仅标准库 + 复用 validate_options 关键词提取；函数接受 base 参数以便测试。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'scripts'))
sys.path.insert(0, str(BASE))

import qbank
import validate_options as vo

# 关键词提取复用 validate_options._extract_stem_keywords:
# jieba 可用时用真分词（本机已装，golden 交叉验证的默认路径）；
# 无 jieba 时自动回退 n-gram（确定性强，pages 命令不依赖关键词）。
# 注意: 切勿强制 _JIEBA_AVAILABLE=False —— n-gram 对短题干+泛化术语过度敏感
# （2026-08-13 实测: "中枢神经系统包括：" 与 Reynolds五联征题 containment=0.6 假阳性）

SUBJECT_TO_CODE = {
    '内科学': 'internal-med', '儿科学': 'pediatrics', '外科学': 'surgery',
    '神经病学': 'neurology', '精神病学': 'psychiatry',
    '皮肤性病学': 'dermatology', '中医学': 'tcm', '医患沟通': 'doctor-patient',
}

GOLDEN_FILE = BASE / 'GoldenSet' / 'structured' / 'GS_下册_2025_1994.json'


# ──────────────────────────────────────────
# 通用
# ──────────────────────────────────────────

def keywords(text):
    """题干/文本 → 关键词集合（jieba 真分词；无 jieba 时回退 n-gram）。"""
    return set(vo._extract_stem_keywords(str(text)))


def numeric_tokens(text):
    """提取数值元组集合。支持: 数值+单位、血压比 140/90。无单位裸数忽略。"""
    tokens = set()
    for m in re.finditer(
            r'(\d+(?:\.\d+)?)\s*'
            r'(%|ml|mL|mg|μg|ug|g|kg|L|mmHg|cmH2O|mmol/L|mmol|g/L|mg/dl|'
            r'次/分|次|天|周|月|年|岁|小时|分钟|秒|℃|°C|u|IU|dB)', text):
        value = float(m.group(1))
        unit = m.group(2).lower()
        if value == 0:
            continue
        tokens.add((value, unit))
    # 血压比（如 140/90mmHg）
    for m in re.finditer(r'(\d{2,3})\s*/\s*(\d{2,3})\s*(?:mmHg)?', text):
        tokens.add((f'{m.group(1)}/{m.group(2)}', 'bp'))
    return tokens


def load_questions(filepath):
    """读取题库文件（列表），解析为规范结构。"""
    data = qbank.load_json_file(filepath)
    if not isinstance(data, list):
        print(f'✗ 文件顶层不是数组: {filepath}')
        sys.exit(2)
    questions = []
    for i, raw in enumerate(data):
        q = qbank.parse_question(raw)
        if q is not None:
            q['qid'] = q['qid'] or f'{Path(filepath).stem}[{i}]'
            questions.append(q)
    if not questions:
        print(f'✗ 未解析到题目: {filepath}')
        sys.exit(2)
    return questions


# ──────────────────────────────────────────
# pages: 页码反查
# ──────────────────────────────────────────

def load_valid_pages(subject_code, kb_base=None):
    """从分块元数据加载有效页码集合。返回 (pages:set, max_page:int|None)。"""
    kb_base = Path(kb_base) if kb_base else BASE / '知识库素材'
    chunks_file = kb_base / 'chunks_metadata' / f'{subject_code}_chunks.jsonl'
    pages = set()
    if not chunks_file.exists():
        return pages, None
    with open(chunks_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = d.get('page_number')
            if isinstance(p, (int, float)) and p > 0:
                pages.add(int(p))
    return pages, (max(pages) if pages else None)


def check_pages(questions, subject_code, kb_base=None, valid_pages=None):
    """逐题页码校验。返回 issues 列表 [{qid, severity, detail}]。"""
    if valid_pages is None:
        valid_pages, _ = load_valid_pages(subject_code, kb_base)
    max_page = max(valid_pages) if valid_pages else None
    issues = []
    for q in questions:
        qid = q['qid']
        raw = q['source_pages_raw']
        nums = q['source_pages']
        if not raw or (isinstance(raw, list) and not raw) or (isinstance(raw, str) and not raw.strip()):
            issues.append({'qid': qid, 'severity': 'WARN', 'detail': '缺页码锚点 (HC-3)'})
            continue
        if not nums:
            # 有来源字段但无 P 前缀页码（如"指南2023"）→ 非教材页码来源
            issues.append({'qid': qid, 'severity': 'WARN',
                           'detail': f'来源非教材页码（{str(raw)[:30]}），无法反查'})
            continue
        for n in sorted(set(nums)):
            if n == 0:
                issues.append({'qid': qid, 'severity': 'FAIL', 'detail': '页码 P0 为占位符（HC-10）'})
            elif max_page and n > max_page:
                issues.append({'qid': qid, 'severity': 'FAIL',
                               'detail': f'页码 P{n} 超出教材范围 (最大 P{max_page})'})
            elif valid_pages and n not in valid_pages:
                issues.append({'qid': qid, 'severity': 'WARN',
                               'detail': f'页码 P{n} 不在教材分块索引中'})
    return issues


def run_pages(args):
    questions = load_questions(args.file)
    code = args.subject if args.subject in SUBJECT_TO_CODE.values() else SUBJECT_TO_CODE.get(args.subject, args.subject)
    pages, max_page = load_valid_pages(code)
    if not pages:
        print(f'⚠️ 教材分块索引不存在: chunks_metadata/{code}_chunks.jsonl（跳过页码反查）')
        return
    issues = check_pages(questions, code, valid_pages=pages)

    total = len(questions)
    with_pages = total - sum(1 for i in issues if i['detail'] == '缺页码锚点 (HC-3)')
    fails = [i for i in issues if i['severity'] == 'FAIL']
    warns = [i for i in issues if i['severity'] == 'WARN']
    print(f'{"═"*60}')
    print(f'  页码反查 — {Path(args.file).name} (subject={code})')
    print(f'{"═"*60}')
    print(f'  题目总数: {total} | 含页码: {with_pages} ({with_pages/total*100:.1f}%)')
    print(f'  ✗ FAIL {len(fails)} | ⚠️ WARN {len(warns)}')
    for i in (fails + warns)[:args.limit]:
        print(f'  [{"✗" if i["severity"]=="FAIL" else "⚠️"}] {i["qid"]}: {i["detail"]}')
    if len(fails) + len(warns) > args.limit:
        print(f'  ... 共 {len(fails) + len(warns)} 条')
    print(f'{"═"*60}')
    sys.exit(1 if fails else 0)


# ──────────────────────────────────────────
# golden: GoldenSet 交叉验证 (HC-8 机械化)
# ──────────────────────────────────────────

def load_golden(gs_path=None):
    """加载金标准（下册，含答案+解析）。"""
    gs_path = Path(gs_path) if gs_path else GOLDEN_FILE
    if not gs_path.exists():
        return []
    with open(gs_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    items = []
    for x in data:
        if not isinstance(x, dict):
            continue
        stem = x.get('stem') or x.get('stem_abbreviated') or ''
        if not stem:
            continue
        stem = _strip_gs_prefix(stem)
        items.append({
            'gs_id': x.get('gs_id', 'GS-?'),
            'year': x.get('year', ''),
            'stem': stem,
            'answer': str(x.get('answer', '')),
            'explanation': str(x.get('explanation', '')),
            'keywords': keywords(stem),
            'numbers': numeric_tokens(stem + str(x.get('explanation', ''))),
        })
    return items


def _strip_gs_prefix(stem):
    """剥离金标准 stem 的编号/选项前缀（'150. ABCD ①...' → '①...'）。

    GS 下册的 stem 是"题号+选项+①②③多子题打包块"，前缀是纯噪音
    （2026-08-13 实测: 'ABCD' 等 token 参与相似度计算污染匹配）。
    """
    s = str(stem).strip()
    s = re.sub(r'^\d+[\.、]?\s*[A-D]{1,4}\s*', '', s)
    return s.strip()


def golden_crosscheck(questions, gs_items, top_k=3, dup_threshold=0.85, sim_threshold=0.45,
                      min_inter=3, limit=None):
    """新题 vs 金标准。返回 results: [{qid, kind, gs_id, containment, jaccard, detail}]。

    kind: duplicate(疑似重复题) / conflict(术语相似但数值不一致) / similar(相似题,参考)

    校准 (2026-08-13, GS 下册 2754 题 + batch022 322 题实测):
    - GS stem 是多子题打包块(①②③)，低 inter 高 containment = 子题主题撞车，非真重复
    - 真重复（同题改写）: containment≈1.0, inter≥4（停用词过滤后短题干仅 4 词）
    - 误报样本: 脊髓型颈椎病 0.75/3、HPV 0.8、甲亢瘫痪 0.75 → 均 <0.85
    → duplicate: containment≥0.85 且 inter≥4；conflict: containment≥0.55 且双方数值≥2
    """
    results = []
    qs = questions[:limit] if limit else questions
    for q in qs:
        kws = keywords(q['stem'])
        if not kws:
            continue
        # 数值仅取 正确选项 + 解析（避免把全部干扰项数值混入导致必然交集）
        ans_text = q['options'].get(q['answer'], '')
        qnums = numeric_tokens(q['stem'] + ' ' + ans_text + ' ' + q['explanation'])
        scored = []
        for g in gs_items:
            inter = len(kws & g['keywords'])
            if inter < min_inter:
                continue
            cont = inter / max(min(len(kws), len(g['keywords'])), 1)
            if cont >= sim_threshold:
                j = inter / max(len(kws | g['keywords']), 1)
                scored.append((cont, j, inter, g))  # inter 随条目携带，防分类时读到残留值
        scored.sort(key=lambda x: -x[0])
        for cont, j, inter, g in scored[:top_k]:
            if cont >= dup_threshold and inter >= 4:
                results.append({'qid': q['qid'], 'kind': 'duplicate', 'gs_id': g['gs_id'],
                                'containment': round(cont, 2), 'jaccard': round(j, 2),
                                'detail': f'疑似与金标准重复: {g["stem"][:50]}'})
            else:
                shared = qnums & g['numbers']
                # 冲突需较强相似(≥0.55)且双方数值≥2个（弱匹配+单值年龄/时间撞车=噪音）
                if cont >= 0.55 and len(qnums) >= 2 and len(g['numbers']) >= 2 and not shared:
                    results.append({'qid': q['qid'], 'kind': 'conflict', 'gs_id': g['gs_id'],
                                    'containment': round(cont, 2), 'jaccard': round(j, 2),
                                    'detail': f'术语相似但数值不一致: 新题{qnums} vs 金标准{g["numbers"]} — 需人工核对'})
                else:
                    results.append({'qid': q['qid'], 'kind': 'similar', 'gs_id': g['gs_id'],
                                    'containment': round(cont, 2), 'jaccard': round(j, 2),
                                    'detail': f'相似题参考: {g["stem"][:50]}'})
    return results


def run_golden(args):
    questions = load_questions(args.file)
    gs_items = load_golden()
    if not gs_items:
        print(f'⚠️ 金标准未找到: {GOLDEN_FILE}')
        sys.exit(2)
    results = golden_crosscheck(questions, gs_items, limit=args.limit)
    dups = [r for r in results if r['kind'] == 'duplicate']
    conflicts = [r for r in results if r['kind'] == 'conflict']
    similars = [r for r in results if r['kind'] == 'similar']
    print(f'{"═"*60}')
    print(f'  GoldenSet 交叉验证 (HC-8) — {Path(args.file).name}')
    print(f'{"═"*60}')
    print(f'  新题: {len(questions)} | 金标准: {len(gs_items)} 题 (下册)')
    print(f'  疑似重复: {len(dups)} | 数值冲突: {len(conflicts)} | 相似参考: {len(similars)}')
    for r in dups + conflicts:
        icon = '🔁' if r['kind'] == 'duplicate' else '⚠️'
        print(f'  {icon} {r["qid"]} vs {r["gs_id"]} (containment={r["containment"]}, J={r["jaccard"]}): {r["detail"]}')
    for r in similars[:args.limit]:
        print(f'  📎 {r["qid"]} vs {r["gs_id"]} (containment={r["containment"]}, J={r["jaccard"]}): {r["detail"]}')
    print(f'{"═"*60}')
    sys.exit(1 if conflicts else 0)


# ──────────────────────────────────────────
# CLI
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='事实校验机械化 — 页码反查 + GoldenSet 交叉验证 (P1-1)')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_pages = sub.add_parser('pages', help='页码反查（对照教材分块索引）')
    p_pages.add_argument('--file', '-f', required=True)
    p_pages.add_argument('--subject', '-s', required=True, help='科目名或代码（如 神经病学 / neurology）')
    p_pages.add_argument('--limit', type=int, default=30)

    p_golden = sub.add_parser('golden', help='GoldenSet 交叉验证 (HC-8)')
    p_golden.add_argument('--file', '-f', required=True)
    p_golden.add_argument('--subject', '-s', default='', help='科目名（仅展示用，匹配不做科目过滤）')
    p_golden.add_argument('--limit', type=int, default=0, help='抽样题数（0=全部）')
    p_golden.add_argument('--top-k', type=int, default=3)

    args = parser.parse_args()
    if args.cmd == 'pages':
        run_pages(args)
    elif args.cmd == 'golden':
        run_golden(args)


if __name__ == '__main__':
    main()
