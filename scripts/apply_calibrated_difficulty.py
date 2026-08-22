#!/usr/bin/env python3
"""
apply_calibrated_difficulty.py — expanded 校准值回写 registry（2026-08-21 · 终审修订版）

依据《交接终审报告_20260821.md》§三：
  - 3.1 红线修订：registry 已于 8/20 被写入 test-only 旧值 → 本工具性质为
    「备份后整体刷新校准五字段」（不再是「只新增不覆盖」）
  - 3.2 回写纪律：去重前禁止 qid join（497 重复 qid 有歧义）；**registry 已于
    8/21 去重为每 qid 唯一行**，此后 qid join 安全，行数不一致（expanded 4,917
    行 > registry 4,296 行）属预期，按 qid 映射回写
  - 补写 anchor_source 字段（chain/direct 溯源，终审建议）
  - 写前备份 registry.jsonl（registry_backup_YYYYMMDD_HHMMSS.jsonl 命名惯例）

说明：calibrated_p 是「CMExam 人工标注锚点 + 先验表」的外部先验估计，非本库实测。
允许：组卷配平、异常题筛查、推送排序；禁止：对外标注为「实测难度」。

用法:
  python scripts/apply_calibrated_difficulty.py --dry-run   # 预览（不写盘）
  python scripts/apply_calibrated_difficulty.py             # 执行（自动备份 + 原子写）
  python scripts/apply_calibrated_difficulty.py --input question_bank/calibrated_difficulty.expanded.jsonl
"""
import sys, json, shutil, argparse, os
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).resolve().parent.parent
REGISTRY = BASE / 'question_bank' / 'registry.jsonl'
CALIBRATED = BASE / 'question_bank' / 'calibrated_difficulty.expanded.jsonl'

NEW_FIELDS = ['calibrated_p', 'calibration_confidence', 'calibration_flag', 'max_sim', 'prior_key']


def load_lines(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    return lines


def main():
    parser = argparse.ArgumentParser(description='expanded 校准值回写 registry（备份 + 刷新五字段 + anchor_source）')
    parser.add_argument('--dry-run', action='store_true', help='预览：只报告匹配情况，不写盘')
    parser.add_argument('--input', default=str(CALIBRATED), help='校准源文件（默认 expanded）')
    args = parser.parse_args()

    cal_path = Path(args.input)
    if not REGISTRY.exists():
        print(f'✗ registry 不存在: {REGISTRY}')
        sys.exit(2)
    if not cal_path.exists():
        print(f'✗ 校准源不存在: {cal_path}（先运行 anchor_bank.py anchor --output ...）')
        sys.exit(2)

    reg_lines = load_lines(REGISTRY)
    cal_lines = load_lines(cal_path)

    # qid 唯一性检查（去重后应为唯一；若仍有重复 qid 则拒绝，防错位）
    cal_by_qid = {}
    dup_in_cal = 0
    for cl in cal_lines:
        c = json.loads(cl)
        q = c['qid']
        if q in cal_by_qid:
            dup_in_cal += 1
        cal_by_qid[q] = c

    reg_qids = [json.loads(rl)['qid'] for rl in reg_lines]
    dup_in_reg = len(reg_qids) - len(set(reg_qids))
    if dup_in_reg:
        print(f'✗ registry 仍有 {dup_in_reg} 个重复 qid，先执行去重再回写（禁 qid join）')
        sys.exit(2)
    if dup_in_cal:
        print(f'⚠ 校准源内有 {dup_in_cal} 个重复 qid（将取最后一行）')

    # 按 qid 映射回写
    out_lines = []
    matched = 0
    unmatched = []
    for rl in reg_lines:
        rec = json.loads(rl)
        cal = cal_by_qid.get(rec['qid'])
        if cal is None:
            unmatched.append(rec['qid'])
            out_lines.append(json.dumps(rec, ensure_ascii=False))
            continue
        for f in NEW_FIELDS:
            rec[f] = cal.get(f)
        if 'anchor_source' in cal:
            rec['anchor_source'] = cal['anchor_source']
        out_lines.append(json.dumps(rec, ensure_ascii=False))
        matched += 1

    print(f'✓ 匹配 {matched}/{len(reg_lines)} 行（按 qid join；校准源 {len(cal_lines)} 行）')
    print(f'  刷新字段: {", ".join(NEW_FIELDS)} + anchor_source')
    if unmatched:
        print(f'  ⚠ {len(unmatched)} 行未在校准源找到，保留原值: {unmatched[:5]}')

    if args.dry_run:
        print('（dry-run：未写盘）')
        return

    # 写前备份
    backup = BASE / 'question_bank' / f"registry_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    shutil.copy2(REGISTRY, backup)
    print(f'✓ 备份: {backup.name}')

    # 原子写
    tmp = REGISTRY.with_name(REGISTRY.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out_lines) + '\n')
    os.replace(tmp, REGISTRY)
    print(f'✓ 已回写: {REGISTRY.name}（{len(out_lines)} 行）')


if __name__ == '__main__':
    main()
