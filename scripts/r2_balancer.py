#!/usr/bin/env python3
"""
R2选项平衡器 v2.0 — 绝后患版
原则：只扩充短选项，绝不截断长选项。
对任何 text[:n] 暴力截断零容忍。
可复用：python r2_balancer.py --file <path> [--batch <name>]
"""
import json, sys, re, argparse, os
from pathlib import Path

# v2.0 (2026-08-20 审查修复): 缺失该行时 GBK 控制台打印 ⚠/→ 等字符直接
# UnicodeEncodeError 崩溃（实测复现）
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 语义扩充词典 ──
# 原则：加领域限定词不加无意义后缀
EXPAND_MAP = {
    # 2-3字症状 → 拆分或加类属
    '胸痛': '胸部疼痛', '咯血': '咯血症状', '咳痰': '咳嗽咳痰',
    '发绀': '口唇发绀', '腹水': '腹腔积液', '水肿': '组织水肿',
    '黄疸': '皮肤黄疸', '发热': '发热症状', '盗汗': '夜间盗汗',
    # 2-3字疾病
    '肺癌': '支气管肺癌', '气胸': '自发性气胸', '肺炎': '肺部炎症',
    '哮喘': '支气管哮喘', '贫血': '贫血状态',
    # 2-3字药物/治疗
    '茶碱': '茶碱类药物', '戒烟': '戒烟干预', '吸氧': '氧疗干预',
    '利尿': '利尿治疗', '抗凝': '抗凝治疗',
    # 2-3字概念
    '休克': '分布性休克', '猝死': '心源性猝死',
    '是': '属于此类', '否': '不属于此类',
    # 英文缩写
    'COPD': '慢性阻塞性肺疾病', 'ARDS': '急性呼吸窘迫综合征',
    'DIC': '弥散性血管内凝血', 'ITP': '免疫性血小板减少症',
    'MDS': '骨髓增生异常综合征', 'SLE': '系统性红斑狼疮',
    'TTP': '血栓性血小板减少性紫癜',
}

def semantic_expand(text: str, min_target: int) -> str:
    """智能扩充：先查词典，再按规则扩展。绝不截断。"""
    if text in EXPAND_MAP and len(EXPAND_MAP[text]) >= min_target:
        return EXPAND_MAP[text]

    L = len(text)
    if L >= min_target:
        return text

    # 规则1: 2字症状 → 拆成双字词（如"胸痛"→"胸部疼痛"）
    if L == 2:
        # 尝试拆分
        if text in EXPAND_MAP:
            return EXPAND_MAP[text]
        return text  # 无法安全扩充，保持原样

    # 规则2: 2-3字疾病名 → 加"疾病""病变"
    if L <= 3 and any(kw in text for kw in ['炎','病','瘤','症','血','痰']):
        if not text.endswith('病变') and not text.endswith('疾病'):
            return text + '病变' if '病' not in text else text

    # 规则3: 2-3字药名 → 加"类药物"
    if L <= 3 and any(kw in text for kw in ['素','平','松','坦','林']):
        if '药物' not in text:
            return text + '类药物'

    return text  # 无法安全扩充则保持原样

def balance_options(questions, verbose=False):
    """对全部题目扩充短选项使max/min≤2.0。绝不截断。"""
    fixed_count = 0
    failed_ids = []

    for q in questions:
        opts = q['options']
        lengths = {o['label']: len(o['text']) for o in opts}
        mn, mx = min(lengths.values()), max(lengths.values())

        if mn == 0 or mx / mn <= 2.0:
            continue

        target_min = max(4, int(mx / 2.0))
        changed = False

        for o in opts:
            old_text = o['text']
            old_len = len(old_text)
            if old_len < target_min:
                new_text = semantic_expand(old_text, target_min)
                if new_text != old_text:
                    o['text'] = new_text
                    changed = True
                    if verbose:
                        print(f'  {q["id"]}.{o["label"]}: "{old_text}"({old_len}) → "{new_text}"({len(new_text)})')

        if changed:
            # 重新检查
            # v2.0 (2026-08-20 审查修复): min/max 赋值此前颠倒（mn2 取到最大值、
            # mx2 取到最小值 → mx2/mn2 = min/max ≤ 1 恒判成功、退出码恒 0，
            # 工具自欺）；且"初始已违反但扩充失败"的题此前被静默放过。
            lengths2 = {o['label']: len(o['text']) for o in opts}
            mn2, mx2 = min(lengths2.values()), max(lengths2.values())
            if mn2 > 0 and mx2 / mn2 <= 2.0:
                fixed_count += 1
            else:
                failed_ids.append((q['id'], mx2 / mn2))
        elif mn > 0 and mx / mn > 2.0:
            # 初始已违反 R2 但无法安全扩充（词典/规则都未命中）→ 如实计入失败
            failed_ids.append((q['id'], mx / mn))

    if failed_ids:
        print(f'⚠ {len(failed_ids)} questions still have R2 > 2.0 after expansion:')
        for qid, ratio in failed_ids[:10]:
            print(f'  {qid}: {ratio:.1f}x')
    if verbose:
        print(f'Fixed: {fixed_count}')
    return fixed_count, len(failed_ids)

def main():
    parser = argparse.ArgumentParser(description='R2平衡器 — 只扩充不截断')
    parser.add_argument('--file', required=True, help='JSON题库文件路径')
    parser.add_argument('--output', help='输出路径（默认覆盖原文件）')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    with open(args.file, 'r', encoding='utf-8') as f:
        questions = json.load(f)

    print(f'Processing {len(questions)} questions from {args.file}...')
    fixed, remaining = balance_options(questions, verbose=args.verbose)

    out_path = args.output or args.file
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    print(f'Done: {fixed} fixed, {remaining} still >2.0, saved to {out_path}')
    return 0 if remaining == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
