#!/usr/bin/env python3
"""
paper_builder.py — 组卷公式 v1.1（2026-08-21 · 终审修订，DSH 待办 #6）

组卷权重 = 考频权重(blueprint) × 难度配平(calibrated_p) × NFD 过滤
（公式声明与 scripts/pipeline.yaml 的 paper_assembly 节保持一致）

v1.1 变更（《交接终审报告_20260821.md》§四 #6）：
  - **难度读 expanded**：calibrated_difficulty.expanded.jsonl 按 qid 覆盖 registry
    校准五字段（registry 刷新滞后时以 expanded 为准），并记录覆盖统计
  - **MedQC 复检处置接入**（reports/conflict_recheck_20260821.json）：
      anchor_prior_conflict 题按处置分流：
        KEEP_PRIOR  → 入卷，难度取 prior_p（锚点误配，按先验处置）
        KEEP_ANCHOR → 入卷，难度取 expanded 融合值
        FLAG_MEDFIX / UNCERTAIN / 无处置记录 → 排除（待修复/待人工，不入正式卷）
  - 卷面 P 目标 [0.55, 0.65]：CMExam 源整体偏易（avg_p≈0.68）→ 配平向 hard 侧偏移

规则（v1.0 保留）：
  1. 硬过滤：NFD≥2（源 JSON 的 non_functioning_distractors）不入卷；
     calibration_flag=anchor_prior_conflict（未处置）不入正式卷
  2. 考频权重：学科权重 = blueprint by_subject.refs 归一化（跨学科综合卷）；
     单科卷内 top_referenced 高频真题 stem 与题目 stem 命中 → 权重 ×1.5
  3. 置信度加权：high=1.0 / medium=0.7 / low=0.4（low 少入正式卷）
  4. 类型配额：--type-weights（默认 A1:0.4,A2:0.25,A3:0.15,B1:0.1,X:0.1）
  5. 答案位置平衡：A/B/C/D 贪心纠偏（目标均匀 ≤25%±5%）
  6. 难度配平：卷面 P=mean(calibrated_p) 目标区间 [--p-min, --p-max]

输出：
  --output 默认 最终产物/押题卷_{subject}_{N}题.json
    格式兼容 scripts/quiz_template.html 的 QUESTIONS 数组
  （stats 字段带 paper_meta 供报告参考；统计报告写 reports/paper/）

用法:
  python scripts/paper_builder.py --subject 内科学 --count 50 --dry-run
  python scripts/paper_builder.py --subject 内科学 --count 100
  python scripts/paper_builder.py --all --count 60 --type-weights A1:0.3,A2:0.3,A3:0.15,B1:0.1,X:0.15
"""
import sys, json, os, argparse, random
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'scripts'))
import qbank

REGISTRY = BASE / 'question_bank' / 'registry.jsonl'
EXPANDED = BASE / 'question_bank' / 'calibrated_difficulty.expanded.jsonl'
RECHECK = BASE / 'reports' / 'conflict_recheck_20260821.json'
STATE_FILE = BASE / 'workflow_state.json'
BLUEPRINT = BASE / '知识库素材' / 'blueprint.json'
OUTPUT_DIR = BASE / '最终产物'
REPORT_DIR = BASE / 'reports' / 'paper'

DEFAULT_TYPE_WEIGHTS = {'A1': 0.40, 'A2': 0.25, 'A3': 0.15, 'B1': 0.10, 'X': 0.10}
CONF_WEIGHT = {'high': 1.0, 'medium': 0.7, 'low': 0.4, None: 0.5}
HIGH_FREQ_BOOST = 1.5
P_MIN, P_MAX = 0.55, 0.65
BALANCE_ROUNDS = 40
CAL_FIELDS = ('calibrated_p', 'calibration_confidence', 'calibration_flag', 'max_sim', 'prior_key', 'anchor_source')


# ── 数据加载 ────────────────────────────────────────────

def load_registry():
    """读取 registry.jsonl（含 calibrated 字段），按 qid 去重（stage=final 优先）。"""
    entries = {}
    with open(REGISTRY, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            qid = rec['qid']
            # final 优先；同 qid 重复时保留更高 stage
            cur = entries.get(qid)
            if cur is None or (rec.get('stage') == 'final' and cur.get('stage') != 'final'):
                entries[qid] = rec
    return entries


def load_batch_subjects():
    """workflow_state.json → {batch_id: subject}。"""
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        state = json.load(f)
    out = {}
    for key, batch in state.items():
        if str(key).startswith('batch') and isinstance(batch, dict):
            subj = batch.get('subject', '')
            if subj:
                out[key] = subj
    return out


def load_blueprint():
    """blueprint.json → (subject_weights, high_freq_stems)。"""
    if not BLUEPRINT.exists():
        return {}, []
    with open(BLUEPRINT, 'r', encoding='utf-8') as f:
        b = json.load(f)
    weights = {}
    for subj, info in (b.get('by_subject') or {}).items():
        refs = info.get('refs', 0)
        if refs > 0:
            weights[subj] = refs
    # 归一化
    total = sum(weights.values()) or 1
    weights = {k: v / total for k, v in weights.items()}
    stems = [t.get('stem', '') for t in (b.get('top_referenced') or []) if t.get('stem')]
    return weights, stems


def load_expanded():
    """calibrated_difficulty.expanded.jsonl → {qid: row}（难度主源，终审 #6）。"""
    if not EXPANDED.exists():
        return {}
    out = {}
    with open(EXPANDED, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out[rec['qid']] = rec
    return out


def load_recheck():
    """reports/conflict_recheck_*.json → {qid: {disposition, recommended_p}}（MedQC 处置）。"""
    if not RECHECK.exists():
        return {}
    try:
        with open(RECHECK, 'r', encoding='utf-8') as f:
            rep = json.load(f)
    except Exception:
        return {}
    out = {}
    for q in (rep.get('questions') or []):
        out[q.get('qid')] = {'disposition': q.get('disposition'), 'recommended_p': q.get('recommended_p')}
    return out


def load_question(rec):
    """按 registry 条目加载题目内容（含归档回退）。返回 (q, raw) 或 (None, None)。"""
    try:
        path = qbank.resolve_entry_path(rec.get('file', ''))
        if path is None or not path.exists():
            return None, None
        raw_list = qbank.load_json_file(str(path))
        if not isinstance(raw_list, list):
            return None, None
        idx = rec.get('index', 0)
        if idx >= len(raw_list):
            return None, None
        raw = raw_list[idx]
        q = qbank.parse_question(raw)
        return q, raw
    except Exception:
        return None, None


# ── 组卷公式 ────────────────────────────────────────────

def build_pool(subject, batch_subjects, high_freq_stems):
    """构建题目池：registry + expanded 难度 + MedQC 处置 + 源题目内容 + 权重。返回 (pool, excluded, stats)。"""
    registry = load_registry()
    expanded = load_expanded()
    recheck = load_recheck()
    pool = []
    excluded = []
    stats = {'expanded_override': 0, 'recheck_resolved': {'KEEP_PRIOR': 0, 'KEEP_ANCHOR': 0}, 'recheck_excluded': 0}

    for qid, rec in registry.items():
        batch = rec.get('batch', '')
        rec_subject = batch_subjects.get(batch, '')
        if subject and rec_subject != subject:
            continue

        q, raw = load_question(rec)
        if q is None or not q.get('stem'):
            excluded.append({'qid': qid, 'reason': '源文件不可解析'})
            continue

        # 硬过滤 1: NFD（源 JSON 有 non_functioning_distractors 且 ≥2）
        nfd = None
        if isinstance(raw, dict):
            nfd = raw.get('non_functioning_distractors')
        if isinstance(nfd, (int, float)) and nfd >= 2:
            excluded.append({'qid': qid, 'reason': f'NFD={nfd}≥2'})
            continue

        # 难度主源：expanded 按 qid 覆盖 registry 校准字段（终审 #6）
        meta = dict(rec)
        p_source = 'registry'
        ex = expanded.get(qid)
        if ex:
            for fld in CAL_FIELDS:
                if fld in ex:
                    meta[fld] = ex[fld]
            p_source = 'expanded'
            stats['expanded_override'] += 1

        # 硬过滤 2: 锚点-先验冲突题按 MedQC 处置分流（v1.1）
        flag = meta.get('calibration_flag')
        if flag == 'anchor_prior_conflict':
            disp = recheck.get(qid, {}).get('disposition')
            if disp == 'KEEP_PRIOR':
                pri = ex.get('prior_p') if ex else None
                meta['calibrated_p'] = float(pri) if isinstance(pri, (int, float)) else float(recheck[qid].get('recommended_p') or 0.6)
                meta['_p_source'] = 'resolved_keep_prior'
                stats['recheck_resolved']['KEEP_PRIOR'] += 1
            elif disp == 'KEEP_ANCHOR':
                meta['_p_source'] = 'resolved_keep_anchor'
                stats['recheck_resolved']['KEEP_ANCHOR'] += 1
            else:
                excluded.append({'qid': qid, 'reason': f'calibration_flag=anchor_prior_conflict（MedQC处置={disp or "无"}，待修复/待人工）'})
                stats['recheck_excluded'] += 1
                continue

        # 考频权重：高频真题 stem 命中 → 权重提升
        freq_boost = 1.0
        if high_freq_stems:
            stem = q.get('stem', '')
            if any(hs and hs[:12] in stem for hs in high_freq_stems):
                freq_boost = HIGH_FREQ_BOOST

        conf = meta.get('calibration_confidence')
        cal_p = meta.get('calibrated_p')
        if not isinstance(cal_p, (int, float)):
            cal_p = 0.6  # 缺失兜底（无 calibrated 的旧题）

        pool.append({
            'qid': qid,
            'type': q.get('type') or rec.get('type') or 'A1',
            'system': q.get('module') or '',
            'bloom': q.get('bloom_level') or '',
            'stem': q.get('stem', ''),
            'options': q.get('options') or {},
            'answer': q.get('answer') or '',
            'explanation': q.get('explanation') or '',
            'source': q.get('source_pages_raw') or '',
            'calibrated_p': float(cal_p),
            'confidence': conf,
            'flag': flag,
            'p_source': p_source,
            'weight': freq_boost * CONF_WEIGHT.get(conf, 0.5),
        })
    return pool, excluded, stats


def sample_paper(pool, count, type_weights):
    """按类型配额 + 权重 + 答案平衡采样。返回 (paper, 未满足配额说明)。"""
    by_type = {}
    for q in pool:
        by_type.setdefault(q['type'], []).append(q)

    paper = []
    ans_count = {'A': 0, 'B': 0, 'C': 0, 'D': 0}

    for t, w in type_weights.items():
        n = max(1, round(count * w)) if t in by_type else 0
        if n == 0:
            continue
        candidates = list(by_type[t])
        chosen = 0
        rng = random.Random(20260820)  # 固定种子，可复现
        while chosen < n and candidates:
            # 权重 ÷ 答案计数惩罚（维持答案平衡）
            scored = []
            for q in candidates:
                ans = q['answer'].upper()
                penalty = 1.0 / (1 + ans_count.get(ans, 0))
                scored.append((q['weight'] * penalty, q))
            scored.sort(key=lambda x: -x[0])
            # 前 20% 中随机挑，避免每次都取同一题
            top_n = max(1, len(scored) // 5)
            _, pick = scored[rng.randrange(min(top_n, len(scored)))]
            candidates.remove(pick)
            paper.append(pick)
            ans_count[pick['answer'].upper()] = ans_count.get(pick['answer'].upper(), 0) + 1
            chosen += 1

    return paper


def balance_difficulty(paper, pool, p_min, p_max, rounds=BALANCE_ROUNDS):
    """难度配平：卷面 P 落入目标区间；偏易→换入更难题，偏难→换入更易题。

    按**类型对齐**逐对替换（src 与候选必须同类型，否则 pool 记账错乱）；
    每轮每类型最多换一半，多轮迭代收敛。
    """
    def mean_p(items):
        vals = [q['calibrated_p'] for q in items]
        return sum(vals) / len(vals) if vals else 0.0

    pool_not_in = [q for q in pool if q['qid'] not in {p['qid'] for p in paper}]
    by_type_pool = {}
    for q in pool_not_in:
        by_type_pool.setdefault(q['type'], []).append(q)

    def swap_one(t, src_t, want_lower_p, p_ref):
        """从池中取同类型候选替换 src_t[0]（want_lower_p=True 表示要更难/更低 p）。"""
        if not src_t:
            return
        if want_lower_p:
            cands = [q for q in by_type_pool.get(t, []) if q['calibrated_p'] < p_min]
            if not cands:
                cands = [q for q in by_type_pool.get(t, []) if q['calibrated_p'] < p_ref - 0.02]
            if not cands:
                return
            cands.sort(key=lambda q: (q['calibrated_p'], -q['weight']))
        else:
            cands = [q for q in by_type_pool.get(t, []) if q['calibrated_p'] > p_max]
            if not cands:
                cands = [q for q in by_type_pool.get(t, []) if q['calibrated_p'] > p_ref + 0.02]
            if not cands:
                return
            cands.sort(key=lambda q: (-q['calibrated_p'], -q['weight']))
        old = src_t[0]
        new = cands[0]
        paper.remove(old)
        paper.append(new)
        by_type_pool[t].remove(new)
        by_type_pool[t].append(old)

    for _ in range(rounds):
        p = mean_p(paper)
        if p_min <= p <= p_max:
            break
        if p > p_max:
            # 卷面偏易 → 用更难题（低 p）替换高 p 题
            for t in sorted({q['type'] for q in paper if q['calibrated_p'] > p_max}):
                src_t = [q for q in paper if q['type'] == t and q['calibrated_p'] > p_max]
                n = min(len(src_t), max(1, len(src_t) // 2))
                for _ in range(n):
                    swap_one(t, src_t, True, p)
                    src_t = [q for q in paper if q['type'] == t and q['calibrated_p'] > p_max]
                    if not src_t:
                        break
        else:
            # 卷面偏难 → 用更易题（高 p）替换低 p 题
            for t in sorted({q['type'] for q in paper if q['calibrated_p'] < p_min}):
                src_t = [q for q in paper if q['type'] == t and q['calibrated_p'] < p_min]
                n = min(len(src_t), max(1, len(src_t) // 2))
                for _ in range(n):
                    swap_one(t, src_t, False, p)
                    src_t = [q for q in paper if q['type'] == t and q['calibrated_p'] < p_min]
                    if not src_t:
                        break

    return paper, mean_p(paper)


def to_template_questions(paper):
    """paper → quiz_template QUESTIONS 数组格式。"""
    out = []
    for q in paper:
        opts = q['options']
        labels = sorted(opts.keys()) if isinstance(opts, dict) else []
        options = [opts[l] for l in labels]
        out.append({
            'qid': q['qid'],
            'type': q['type'],
            'system': q['system'] or '',
            'bloom': q['bloom'] or '',
            'stem': q['stem'],
            'options': options,
            'answer': q['answer'],
            'explanation': q['explanation'] or '',
            'source': q['source'] or '',
            '_calibrated_p': round(q['calibrated_p'], 4),
            '_confidence': q['confidence'],
        })
    return out


# ── CLI ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='组卷公式 v1.0 — 考频 × 难度配平 × NFD 过滤')
    parser.add_argument('--subject', '-s', help='科目名（如 内科学）；不填则全科目')
    parser.add_argument('--count', '-n', type=int, default=100, help='目标题数（默认 100）')
    parser.add_argument('--type-weights', default=None,
                        help='类型配额，如 A1:0.4,A2:0.25,A3:0.15,B1:0.1,X:0.1')
    parser.add_argument('--p-min', type=float, default=P_MIN, help='卷面 P 下限（默认 0.55）')
    parser.add_argument('--p-max', type=float, default=P_MAX, help='卷面 P 上限（默认 0.65）')
    parser.add_argument('--output', '-o', default=None, help='输出 JSON 路径')
    parser.add_argument('--dry-run', action='store_true', help='只出统计，不写卷')
    args = parser.parse_args()

    # 类型配额解析
    type_weights = dict(DEFAULT_TYPE_WEIGHTS)
    if args.type_weights:
        tw = {}
        for part in args.type_weights.split(','):
            if ':' in part:
                k, v = part.split(':', 1)
                tw[k.strip()] = float(v)
        if tw:
            s = sum(tw.values())
            type_weights = {k: v / s for k, v in tw.items()}

    batch_subjects = load_batch_subjects()
    subj_weights, high_freq_stems = load_blueprint()
    print(f'[paper] blueprint: 学科权重 {len(subj_weights)} 个, 高频真题 {len(high_freq_stems)} 条')
    print(f'[paper] 批次科目映射: {len(batch_subjects)} 个批次')

    pool, excluded, pstats = build_pool(args.subject, batch_subjects, high_freq_stems)
    print(f'[paper] 题目池: {len(pool)} 题 | 排除: {len(excluded)} 题')
    print(f'[paper] 难度源: expanded 覆盖 {pstats["expanded_override"]} 题 | MedQC 处置: '
          f'KEEP_PRIOR {pstats["recheck_resolved"]["KEEP_PRIOR"]} / KEEP_ANCHOR {pstats["recheck_resolved"]["KEEP_ANCHOR"]} / 排除 {pstats["recheck_excluded"]}')
    for ex in excluded[:5]:
        print(f'    ✗ {ex["qid"]}: {ex["reason"]}')

    if not pool:
        print('✗ 题目池为空（科目名核对: 内科学/外科学/神经病学/精神病学/中医学/医患沟通…）')
        sys.exit(2)

    count = min(args.count, len(pool))
    paper = sample_paper(pool, count, type_weights)
    paper, final_p = balance_difficulty(paper, pool, args.p_min, args.p_max)
    paper.sort(key=lambda q: q['qid'])

    # 统计
    from collections import Counter
    types = Counter(q['type'] for q in paper)
    answers = Counter(q['answer'].upper() for q in paper)
    confs = Counter(q['confidence'] for q in paper)
    p_vals = [q['calibrated_p'] for q in paper]
    mean_p = sum(p_vals) / len(p_vals)

    print(f'\n[paper] 成卷 {len(paper)} 题')
    print(f'  卷面 P = {mean_p:.3f}（目标 [{args.p_min}, {args.p_max}]'
          f'{" ✅" if args.p_min <= mean_p <= args.p_max else " ⚠️ 未达区间"}）')
    print(f'  类型分布: {dict(types)}')
    print(f'  答案分布: {dict(answers)}')
    print(f'  置信度: {dict(confs)}')

    if args.dry_run:
        print('（dry-run：未写卷）')
        return

    # 输出卷（quiz_template QUESTIONS 兼容）
    questions = to_template_questions(paper)
    paper_meta = {
        'title': f'{args.subject or "综合"}押题卷（组卷公式 v1.1）',
        'generated_at': datetime.now().isoformat(),
        'subject': args.subject or '全部',
        'count': len(questions),
        'mean_p': round(mean_p, 4),
        'p_target': [args.p_min, args.p_max],
        'type_distribution': dict(types),
        'answer_distribution': dict(answers),
        'confidence_distribution': dict(confs),
        'excluded_count': len(excluded),
        'difficulty_source': 'calibrated_difficulty.expanded.jsonl（按 qid 覆盖 registry）',
        'expanded_override': pstats['expanded_override'],
        'recheck_resolved': pstats['recheck_resolved'],
        'recheck_excluded': pstats['recheck_excluded'],
    }
    output = {'paper_meta': paper_meta, 'questions': questions}
    out_path = args.output or str(OUTPUT_DIR / f'押题卷_{args.subject or "综合"}_{len(questions)}题.json')
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'\n✅ 试卷已输出: {out_path}')

    # 统计报告
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f'paper_{args.subject or "all"}_{len(questions)}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({'paper_meta': paper_meta, 'excluded': excluded[:200]}, f, ensure_ascii=False, indent=2)
    print(f'📊 统计报告: {report_path}')


if __name__ == '__main__':
    main()
