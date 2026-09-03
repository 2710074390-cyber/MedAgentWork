#!/usr/bin/env python3
"""
kaoyan_answer_fix.py — GoldenSet 考研真题「答案恢复」工具 v1.0 (2026-09-03)

背景（batch031 取证发现）:
  GoldenSet/parse_goldenset.py 的正则 ^(\\d{1,3})[.\\s、]\\s*([A-E]{1,5})\\s
  把贺银成答案册每题行首的「选项字母前缀」（如 `52. ABCD ①...`）误当作答案，
  导致结构化产物 GS_下册_*.json 中：
    - answer 字段全部退化为前缀（"ABCD"/"ABCDE"），非真实答案
    - detect_type_from_answer() 因 len(answer)>1 把大量 A 型题误标为 "X型"
  真实答案写在解析正文里，形如「故答 D」「答案为 A」「答案：BC」。

本工具从解析正文恢复真实答案，并做交叉校验，输出带置信度的答案表。
**不改动 GoldenSet 原始产物**（只读），输出独立 JSON。

用法:
  python scripts/kaoyan_answer_fix.py --out question_bank/kaoyan_answers.json
  python scripts/kaoyan_answer_fix.py --stats

设计约束: 仅标准库；只读 GoldenSet；置信度分级 high/medium 供人工复核。
"""
import sys, os, json, re, argparse, collections
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).resolve().parent.parent
GS_DIR = BASE / 'GoldenSet' / 'structured'

# 正面向标记：解析正文中明确给出正确选项
POS_PATTERNS = [
    re.compile(r'故答\s*([A-E]{1,5})(?![A-E])'),
    re.compile(r'答案为\s*([A-E]{1,5})(?![A-E])'),
    re.compile(r'答案\s*[是为:：]\s*([A-E]{1,5})(?![A-E])'),
    re.compile(r'故选\s*([A-E]{1,5})(?![A-E])'),
]
# 负面向标记：明确排除的选项（用于交叉验证，不单独作为答案）
NEG_PATTERN = re.compile(r'故不答\s*([A-E]{1,5})(?![A-E])')

PREFIX_RE = re.compile(r'^([A-E]{1,5})$')


def norm_options(options):
    """把 options 归一为字母列表长度。options 可能是 [str] 或 [{label,text}]。"""
    if isinstance(options, list):
        return len(options)
    return 0


def extract_answer(entry):
    """
    从单条下册条目恢复答案。
    返回 (answer:str|None, confidence:str, evidence:str)
    """
    expl = entry.get('explanation') or ''
    raw = (entry.get('answer') or '').strip()
    prefix = raw if PREFIX_RE.match(raw) else ''

    hits = []  # (pattern_idx, letters)
    for i, p in enumerate(POS_PATTERNS):
        for m in p.finditer(expl):
            hits.append((i, m.group(1), m.group(0)))

    if not hits:
        return None, '', ''

    letters = set(prefix) if prefix else set('ABCDE')
    valid = [(i, g, e) for i, g, e in hits if set(g) <= letters]
    if not valid:
        return None, '', ''

    # 排除被「故不答」否定的字母（仅当候选为单字母时应用）
    negs = set()
    for m in NEG_PATTERN.finditer(expl):
        negs |= set(m.group(1))

    # 取优先级最高（模式序号最小）且信息最完整的命中
    best = None
    for i, g, e in sorted(valid, key=lambda x: (x[0], -len(x[1]))):
        if len(g) == 1 and g in negs:
            continue  # 与「故不答」冲突，跳过
        best = (g, e)
        break
    if not best:
        return None, '', ''

    ans, ev = best
    # 置信度：前缀内唯一命中 + 单字母 → high；多字母 → medium（多选需人工复核）
    conf = 'high' if (len(ans) == 1 and prefix) else 'medium'
    return ''.join(sorted(ans)), conf, ev


def load_lower():
    files = sorted(GS_DIR.glob('GS_下册_*.json'))
    out = []
    for f in files:
        try:
            out.extend(json.load(open(f, encoding='utf-8')))
        except Exception as e:
            print(f'  ! 跳过 {f.name}: {e}')
    return out


def build_map():
    lower = load_lower()
    result = {}
    stats = collections.Counter()
    for e in lower:
        ans, conf, ev = extract_answer(e)
        stats['total'] += 1
        if ans:
            stats[f'conf_{conf}'] += 1
            result[e['gs_id']] = {
                'gs_id': e['gs_id'],
                'year': e.get('year'),
                'question_no': e.get('question_no'),
                'subject': e.get('subject'),
                'answer_recovered': ans,
                'answer_raw_prefix': e.get('answer'),
                'confidence': conf,
                'evidence': ev,
                'explanation': e.get('explanation', ''),
            }
        else:
            stats['unrecovered'] += 1
    return result, stats


def main():
    ap = argparse.ArgumentParser(description='GoldenSet 考研真题答案恢复（修复行首选项前缀误判）')
    ap.add_argument('--out', default=str(BASE / 'question_bank' / 'kaoyan_answers.json'),
                    help='输出答案表 JSON')
    ap.add_argument('--stats', action='store_true', help='仅打印统计')
    args = ap.parse_args()

    m, st = build_map()
    print(f"下册条目 {st['total']} 条")
    print(f"  恢复答案: {st['conf_high'] + st['conf_medium']} 条 "
          f"(high {st['conf_high']} / medium {st['conf_medium']})")
    print(f"  未恢复:   {st['unrecovered']} 条")
    if args.stats:
        return
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(m, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'✅ 已写出 {args.out}（{len(m)} 条）')


if __name__ == '__main__':
    main()
