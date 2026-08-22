# -*- coding: utf-8 -*-
"""
anchor_bank.py — E-2 + E-3：CMExam 难度锚点库 / 先验表 / 融合估计器（零 API 成本）
================================================================================
对应《最终优化建议.md》§2.1（锚点+先验双通道）、§2.3（三重自洽校验）、§7（边界声明）。

运行环境（重要）：
  C:/Users/38063/AppData/Local/Programs/Python/Python312/python.exe
  （torch 2.12 + sentence-transformers 5.5.1 已装；默认 python3.10 无 torch）

子命令（按序执行）：
  1) download     从 GitHub 镜像下载 CMExam test_with_annotations.csv + train.csv
  2) embed        本地嵌入 6,811 锚点题（BAAI/bge-small-zh-v1.5 走 hf-mirror，CPU 约 5-15 分钟）
  2b) embed_train 本地嵌入 54,497 道 train 桥接题 → bridges.npz（扩池，CPU 约 60-90 分钟）
  3) anchor       自产题 → top-5 相似锚点（test 直接 + train 两跳桥接）→ 融合难度 + 校验报告
  4) check        单独重跑三重自洽校验（anchor 会自动附带）

用法示例：
  python anchor_bank.py download
  python anchor_bank.py embed --limit 500     # 小样本先验证
  python anchor_bank.py embed                 # 全量
  python anchor_bank.py embed_train           # 桥接扩池（可选）
  python anchor_bank.py anchor --limit 20     # 小样本先验证
  python anchor_bank.py anchor --output question_bank/calibrated_difficulty.expanded.jsonl
                                                # 写新文件，不覆盖已交付的校准产物
  python anchor_bank.py check

产物（遵守根目录白名单铁律）：
  知识库素材/cmexam/data/test_with_annotations.csv   原始数据
  知识库素材/cmexam/anchors_embeds.npz               锚点嵌入矩阵
  知识库素材/cmexam/anchors_meta.jsonl               锚点元数据（难度/学科/题型）
  question_bank/difficulty_prior.json                先验表 P(难度|学科×能力域×单多选)
  question_bank/calibrated_difficulty.jsonl          逐题融合结果（qid 可并回 registry）
  reports/anchor_check_report.json                   三重校验报告

难度语义（边界声明 §7）：
  CMExam Difficulty level 1-5 基于真实考生通过率（human performance）。
  映射 P 值：1→0.85  2→0.70  3→0.55  4→0.40  5→0.25
  本脚本输出是「外部人工证据支撑的先验估计」，禁止对外标注为实测难度。
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import urllib.request
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

ROOT = r'C:\Users\38063\Desktop\MedAgentWork'
DATA_DIR = os.path.join(ROOT, '知识库素材', 'cmexam', 'data')
BANK_DIR = os.path.join(ROOT, '知识库素材', 'cmexam')
QB_DIR = os.path.join(ROOT, 'question_bank')
REPORT_DIR = os.path.join(ROOT, 'reports')

TEST_CSV = os.path.join(DATA_DIR, 'test_with_annotations.csv')
TRAIN_CSV = os.path.join(DATA_DIR, 'train.csv')
EMBEDS_NPZ = os.path.join(BANK_DIR, 'anchors_embeds.npz')
META_JSONL = os.path.join(BANK_DIR, 'anchors_meta.jsonl')
BRIDGES_NPZ = os.path.join(BANK_DIR, 'bridges.npz')
BRIDGES_META = os.path.join(BANK_DIR, 'bridges_meta.jsonl')
PRIOR_JSON = os.path.join(QB_DIR, 'difficulty_prior.json')
CALIB_JSONL = os.path.join(QB_DIR, 'calibrated_difficulty.jsonl')
CALIB_BAK = os.path.join(QB_DIR, 'calibrated_difficulty.testonly.jsonl')
CHECK_JSON = os.path.join(REPORT_DIR, 'anchor_check_report.json')
REGISTRY = os.path.join(QB_DIR, 'registry.jsonl')

# CMExam 难度 1-5 → P 值（真实考生通过率近似带）
DIFF_P = {'1': 0.85, '2': 0.70, '3': 0.55, '4': 0.40, '5': 0.25}

# 自产题 qid 前缀/batch → CMExam 学科 × 能力域 映射（未列出的 fallback 到全局先验）
# 自产题全部为临床课程（执医考试范畴）→ Clinical Medicine
SUBJ_MAP = {
    'YHGT':      {'discipline': '临床医学', 'competency': None},  # 医患沟通 → 全能力域加权
    'NRO':       {'discipline': '临床医学', 'competency': '疾病诊断和鉴别诊断'},
    'PSY':       {'discipline': '临床医学', 'competency': '疾病诊断和鉴别诊断'},
    'psy':       {'discipline': '临床医学', 'competency': '疾病诊断和鉴别诊断'},
}


def log(msg):
    print('[anchor_bank]', msg)


# ---------------------------------------------------------------- 1. download
def cmd_download(args):
    os.makedirs(DATA_DIR, exist_ok=True)
    base = ('https://raw.githubusercontent.com/williamliujl/CMExam/'
            'main/data/')
    targets = [('test_with_annotations.csv', TEST_CSV),
               ('train.csv', TRAIN_CSV)]
    failed = []
    for fname, dst in targets:
        url = base + fname
        mirrors = [
            'https://gh-proxy.com/' + url,
            'https://ghproxy.net/' + url,
            'https://mirror.ghproxy.com/' + url,
            url,
        ]
        if os.path.exists(dst) and not args.force:
            log('已存在 %s（%.1f MB），跳过。--force 可重下'
                % (dst, os.path.getsize(dst) / 1e6))
            continue
        ok = False
        for m in mirrors:
            host = m.split('/')[2]
            try:
                log('下载 %s · 尝试镜像: %s' % (fname, host))
                req = urllib.request.Request(m, headers={'User-Agent': 'Mozilla/5.0'})
                data = urllib.request.urlopen(req, timeout=600).read()
                open(dst, 'wb').write(data)
                log('下载完成 %.1f MB → %s' % (len(data) / 1e6, dst))
                ok = True
                break
            except Exception as e:
                log('  失败: %s %s' % (type(e).__name__, str(e)[:100]))
        if not ok:
            failed.append(fname)
    if failed:
        sys.exit('下载失败: %s。可手动下载放到 %s' % (', '.join(failed), DATA_DIR))


# ---------------------------------------------------------------- 2. embed
def load_bank():
    """读锚点题 → (meta_list, valid_flag)。难度/学科非法的行剔除。"""
    rows = list(csv.DictReader(open(TEST_CSV, encoding='utf-8')))
    metas = []
    for i, r in enumerate(rows):
        d = str(r.get('Difficulty level', '')).strip()
        if d not in DIFF_P:
            continue
        ans = (r.get('Answer') or '').strip()
        metas.append({
            'bank_id': i,
            'question': (r.get('Question') or '').strip(),
            'options': (r.get('Options') or '').replace('\n', ' ').strip(),
            'answer': ans,
            'is_multi': len(ans) > 1,
            'difficulty': d,
            'p': DIFF_P[d],
            'discipline': r.get('Medical Discipline', '').strip(),
            'competency': r.get('Area of Competency', '').strip(),
        })
    return metas


def cmd_embed(args):
    import numpy as np
    os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
    from sentence_transformers import SentenceTransformer

    if not os.path.exists(TEST_CSV):
        sys.exit('先运行: python anchor_bank.py download')

    metas = load_bank()
    if args.limit:
        metas = metas[:args.limit]
    log('锚点题 %d 道（Difficulty 1-5 已映射 P 值）' % len(metas))
    dist = Counter(m['difficulty'] for m in metas)
    log('难度分布: ' + json.dumps(dict(sorted(dist.items())), ensure_ascii=False))

    log('加载 BAAI/bge-small-zh-v1.5（hf-mirror，首次约 95MB）...')
    model = SentenceTransformer('BAAI/bge-small-zh-v1.5')
    texts = [(m['question'] + ' ' + m['options'])[:512] for m in metas]
    log('嵌入 %d 段文本（CPU 约 %d 分钟）...' % (len(texts), max(len(texts) // 800, 1)))
    emb = model.encode(texts, batch_size=64, normalize_embeddings=True,
                       show_progress_bar=True).astype('float32')

    np.savez_compressed(EMBEDS_NPZ, embeds=emb)
    with open(META_JSONL, 'w', encoding='utf-8') as f:
        for m in metas:
            f.write(json.dumps(m, ensure_ascii=False) + '\n')
    log('嵌入矩阵 %s → %s' % (str(emb.shape), EMBEDS_NPZ))
    log('锚点元数据 → %s' % META_JSONL)


# ------------------------------------------------------- 2b. embed_train（扩池）
def load_train():
    """读 train.csv（无难度标注）。只作桥接题，不能直接当锚点。"""
    rows = list(csv.DictReader(open(TRAIN_CSV, encoding='utf-8')))
    metas = []
    dropped = 0
    for i, r in enumerate(rows):
        q = (r.get('Question') or '').strip()
        ans = (r.get('Answer') or '').strip()
        opts = (r.get('Options') or '').replace('\n', ' ').strip()
        if not q or not ans or not opts:
            dropped += 1
            continue
        metas.append({
            'bank_id': i, 'question': q, 'options': opts,
            'answer': ans, 'is_multi': len(ans) > 1,
        })
    return metas, dropped


def cmd_embed_train(args):
    import numpy as np
    os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
    from sentence_transformers import SentenceTransformer

    if not os.path.exists(TRAIN_CSV):
        sys.exit('先运行: python anchor_bank.py download')
    if not (os.path.exists(EMBEDS_NPZ) and os.path.exists(META_JSONL)):
        sys.exit('先运行: python anchor_bank.py embed')

    train, dropped = load_train()
    if args.limit:
        train = train[:args.limit]
    n_multi = sum(1 for m in train if m['is_multi'])
    log('train 桥接题 %d 道（剔除无效 %d 行；多选 %d / 单选 %d）'
        % (len(train), dropped, n_multi, len(train) - n_multi))

    log('加载 BAAI/bge-small-zh-v1.5 ...')
    model = SentenceTransformer('BAAI/bge-small-zh-v1.5')
    texts = [(m['question'] + ' ' + m['options'])[:512] for m in train]
    log('嵌入 %d 段文本（CPU 约 %d 分钟）...'
        % (len(texts), max(len(texts) // 800, 1)))
    tremb = model.encode(texts, batch_size=64, normalize_embeddings=True,
                         show_progress_bar=True).astype('float32')

    # 预计算桥接索引：每道 train 题 → 同题型 test 池内 top-5 锚点
    metas = [json.loads(l) for l in open(META_JSONL, encoding='utf-8')]
    bank = np.load(EMBEDS_NPZ)['embeds']
    t_multi = np.array([m['is_multi'] for m in metas])
    pools = {False: np.where(~t_multi)[0], True: np.where(t_multi)[0]}
    bidx = np.full((len(train), 5), -1, dtype=np.int32)
    bsim = np.zeros((len(train), 5), dtype=np.float32)
    CHUNK = 2000
    for lo in range(0, len(train), CHUNK):
        chunk = tremb[lo:lo + CHUNK]
        sims = chunk @ bank.T
        for row in range(chunk.shape[0]):
            cm = train[lo + row]['is_multi']
            pool = pools[cm]
            ps = sims[row][pool]
            k = min(5, len(ps))
            top = np.argpartition(-ps, max(k - 1, 0))[:k]
            order = top[np.argsort(-ps[top])]
            bidx[lo + row, :len(order)] = pool[order]
            bsim[lo + row, :len(order)] = ps[order]
        log('桥接索引 %d / %d' % (min(lo + CHUNK, len(train)), len(train)))

    np.savez_compressed(BRIDGES_NPZ, train_embeds=tremb,
                        bridge_idx=bidx, bridge_sim=bsim)
    with open(BRIDGES_META, 'w', encoding='utf-8') as f:
        for m in train:
            f.write(json.dumps({'bank_id': m['bank_id'],
                                'question': m['question'][:80],
                                'answer': m['answer'],
                                'is_multi': m['is_multi']}, ensure_ascii=False) + '\n')
    good = (bsim[:, 0] >= 0.65).sum()
    log('桥接池 → %s（top-1 桥接相似度 ≥0.65 的 %d 题）' % (BRIDGES_NPZ, good))
    log('桥接元数据（截断存储）→ %s' % BRIDGES_META)


# ---------------------------------------------------------------- 3. prior
def build_prior(metas):
    """P(难度|学科×能力域×单多选)。样本不足的组合回退到学科级、再回退全局。"""
    cells = defaultdict(list)
    for m in metas:
        key = (m['discipline'], m['competency'], m['is_multi'])
        cells[key].append(m['p'])
    prior = {'_meta': {
        'source': 'CMExam test_with_annotations.csv',
        'n_questions': len(metas),
        'fallback_chain': 'discipline×competency×multi → discipline×multi → global',
    }}
    for (d, c, multi), ps in cells.items():
        prior['%s|%s|%s' % (d, c, multi)] = {
            'mean_p': round(sum(ps) / len(ps), 4), 'n': len(ps)}
    # 学科级与全局兜底
    by_d = defaultdict(list)
    for m in metas:
        by_d[(m['discipline'], m['is_multi'])].append(m['p'])
    for (d, multi), ps in by_d.items():
        prior['%s|*|%s' % (d, multi)] = {
            'mean_p': round(sum(ps) / len(ps), 4), 'n': len(ps)}
    for multi in (False, True):
        ps = [m['p'] for m in metas if m['is_multi'] == multi] or [m['p'] for m in metas]
        prior['*|*|%s' % multi] = {
            'mean_p': round(sum(ps) / len(ps), 4), 'n': len(ps)}
    return prior


def lookup_prior(prior, discipline, competency, is_multi):
    for key in ('%s|%s|%s' % (discipline, competency, is_multi),
                '%s|*|%s' % (discipline, is_multi),
                '*|*|%s' % is_multi,
                '*|*|%s' % (not is_multi)):
        if key in prior and key != '_meta':
            return prior[key]['mean_p'], key
    return 0.55, 'default'


# ---------------------------------------------------------------- 自产题加载
STEM_KEYS = ('question_text', 'stem', 'question', '题干')
OPT_KEYS = ('options',)

# 题库历史归档目录：registry 相对路径可能指向已搬家的旧位置
_ARCHIVE_BASES = ('archive',
                  os.path.join('archive', '复习资料历史_20260819'),
                  os.path.join('archive', '复习资料历史_20260813'))


def resolve_file(rel):
    """registry 相对路径 → 实际文件。三级兜底：
    ① ROOT / 归档基址直连 ② 全树按末两级路径匹配 ③ 全树按文件名匹配。"""
    rel = rel.replace('/', os.sep)
    for base in [ROOT] + [os.path.join(ROOT, b) for b in _ARCHIVE_BASES]:
        p = os.path.join(base, rel)
        if os.path.exists(p):
            return p
    tail = os.sep.join(rel.split(os.sep)[-2:])
    name = rel.split(os.sep)[-1]
    by_name = None
    for root, dirs, files in os.walk(ROOT):
        if name in files:
            p = os.path.join(root, name)
            if p.endswith(tail):
                return p
            if by_name is None:
                by_name = p
    return by_name


def load_own_questions():
    """registry 2074 题 → 完整题干。题库文件已归档到 archive/ 下，路径自适应。"""
    rows = [json.loads(l) for l in open(REGISTRY, encoding='utf-8')]
    cache = {}
    out = []
    for r in rows:
        p = resolve_file(r.get('file', ''))
        stem = None
        if p and p not in cache:
            try:
                cache[p] = json.load(open(p, encoding='utf-8'))
            except Exception:
                cache[p] = None
        bank = cache.get(p) if p else None
        if isinstance(bank, list) and 0 <= r.get('index', -1) < len(bank):
            q = bank[r['index']]
            for k in STEM_KEYS:
                if q.get(k):
                    stem = str(q[k])
                    break
        if not stem:
            stem = r.get('stem_snippet', '')
        out.append({
            'qid': r['qid'],
            'type': r.get('type', ''),
            'stem': stem,
            'is_multi': r.get('type') == 'X',
            'prefix': re.split(r'[-_]', r['qid'])[0],
        })
    return out


def own_subject(prefix):
    m = SUBJ_MAP.get(prefix)
    if m:
        return m
    low = prefix.lower()
    for k, v in SUBJ_MAP.items():
        if low.startswith(k.lower()):
            return v
    return {'discipline': '临床医学', 'competency': None}


# ---------------------------------------------------------------- 4. anchor+fuse
def cmd_anchor(args):
    import numpy as np
    if not (os.path.exists(EMBEDS_NPZ) and os.path.exists(META_JSONL)):
        sys.exit('先运行: python anchor_bank.py embed')

    metas = [json.loads(l) for l in open(META_JSONL, encoding='utf-8')]
    bank_emb = np.load(EMBEDS_NPZ)['embeds']
    prior = build_prior(metas)
    os.makedirs(QB_DIR, exist_ok=True)
    prior_text = json.dumps(prior, ensure_ascii=False, indent=1)
    try:
        unchanged = open(PRIOR_JSON, encoding='utf-8').read() == prior_text
    except OSError:
        unchanged = False
    if unchanged:
        log('先验表内容未变，跳过重写（%d 个组合）' % (len(prior) - 1))
    else:
        open(PRIOR_JSON, 'w', encoding='utf-8').write(prior_text)
        log('先验表（%d 个组合）→ %s' % (len(prior) - 1, PRIOR_JSON))

    own = load_own_questions()
    if args.limit:
        own = own[:args.limit]
    log('自产题 %d 道，检索 top-5 锚点...' % len(own))

    os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('BAAI/bge-small-zh-v1.5')
    own_emb = model.encode([q['stem'][:512] for q in own], batch_size=64,
                           normalize_embeddings=True, show_progress_bar=True
                           ).astype('float32')

    sims = own_emb @ bank_emb.T                     # (N_own, N_test)
    # 题型分池检索：X 型只在 CMExam X 型池内检索，单选只在单选池。
    # 不分池时 X 型题几乎必然命中单选锚点，题型难度信号被稀释（校验②失败根因）。
    t_multi = np.array([m['is_multi'] for m in metas])
    t_pools = {False: np.where(~t_multi)[0], True: np.where(t_multi)[0]}

    # 桥接池（可选）：train 题无难度标注，仅作 own→train→test 两跳桥接。
    # 链路有效相似度 = sim(own,桥) × sim(桥,test锚点)，乘积天然惩罚长链。
    use_bridge = os.path.exists(BRIDGES_NPZ) and os.path.exists(BRIDGES_META)
    if use_bridge:
        bz = np.load(BRIDGES_NPZ)
        train_emb = bz['train_embeds']
        b_idx, b_sim = bz['bridge_idx'], bz['bridge_sim']
        r_meta = [json.loads(l) for l in open(BRIDGES_META, encoding='utf-8')]
        r_multi = np.array([m['is_multi'] for m in r_meta])
        r_pools = {False: np.where(~r_multi)[0], True: np.where(r_multi)[0]}
        pool_desc = ('test %d 直接锚点 + train %d 桥接题（含链路乘积）'
                     % (len(metas), len(r_meta)))
    else:
        pool_desc = ('仅 test %d 直接锚点（未发现桥接池；跑 embed_train 可扩池）'
                     % len(metas))
    log('检索池: ' + pool_desc)

    results = []
    for i, q in enumerate(own):
        # 直接锚点：同题型 test 池 top-10
        tp = t_pools[q['is_multi']]
        d_sims = sims[i][tp]
        d_top = np.argsort(-d_sims)[:10]
        cand = {}   # test_idx -> (有效相似度, 来源)
        for j in d_top:
            cand[int(tp[j])] = (float(d_sims[j]), 'direct')
        # 桥接锚点：own→train(同题型 top-8)→其 top-5 test 锚点
        if use_bridge:
            rp = r_pools[q['is_multi']]
            rs = (own_emb[i] @ train_emb.T)[rp]
            k8 = min(8, len(rs))
            r_top = np.argpartition(-rs, k8 - 1)[:k8]
            for j in r_top:
                s1 = float(rs[j])
                g = int(rp[j])
                for b in range(5):
                    tix = int(b_idx[g, b])
                    if tix < 0:
                        continue
                    eff = s1 * float(b_sim[g, b])
                    if tix not in cand or eff > cand[tix][0]:
                        cand[tix] = (eff, 'chain')
        # 汇总：同一 test 锚点去重取最大，按有效相似度取 top-5
        top5 = sorted(cand.items(), key=lambda kv: -kv[1][0])[:5]
        top_idx = [t for t, _ in top5]
        anchor_ps = [metas[t]['p'] for t in top_idx]
        anchor_p = float(np.median(anchor_ps))      # top-5 难度中位数
        max_sim = top5[0][1][0]
        source = top5[0][1][1]
        subj = own_subject(q['prefix'])
        prior_p, prior_key = lookup_prior(prior, subj['discipline'],
                                          subj['competency'], q['is_multi'])
        flag = None
        if max_sim >= 0.80:
            p, conf = anchor_p, 'high'
        elif max_sim >= 0.65:
            p, conf = 0.6 * anchor_p + 0.4 * prior_p, 'medium'
        else:
            p, conf = prior_p, 'low'
            flag = 'low_similarity'
        if max_sim >= 0.65 and abs(anchor_p - prior_p) > 0.25:
            flag = (flag + '+anchor_prior_conflict') if flag else 'anchor_prior_conflict'
        results.append({
            'qid': q['qid'],
            'type': q['type'],
            'max_sim': round(max_sim, 4),
            'anchor_source': source,
            'anchor_p': round(anchor_p, 4),
            'anchor_difficulties': [metas[t]['difficulty'] for t in top_idx],
            'prior_p': round(prior_p, 4),
            'prior_key': prior_key,
            'calibrated_p': round(float(p), 4),
            'calibration_confidence': conf,
            'calibration_flag': flag,
        })

    # 备份上一版结果（diff 用），宁可留痕不可静默覆盖；仅默认输出路径才触发备份
    out_path = os.path.abspath(args.output) if args.output else CALIB_JSONL
    if out_path == CALIB_JSONL and os.path.exists(CALIB_JSONL) \
            and not os.path.exists(CALIB_BAK):
        import shutil
        shutil.copy2(CALIB_JSONL, CALIB_BAK)
        log('旧结果备份 → %s' % CALIB_BAK)

    with open(out_path, 'w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    log('逐题融合结果 → %s' % out_path)
    src_dist = Counter(r['anchor_source'] for r in results)
    log('锚点来源: %s' % json.dumps(dict(src_dist), ensure_ascii=False))
    _report(metas, results, args.report or None)
    _stats(results)


def _stats(results):
    n = len(results)
    conf = Counter(r['calibration_confidence'] for r in results)
    flags = Counter(r['calibration_flag'] for r in results if r['calibration_flag'])
    avg_p = sum(r['calibrated_p'] for r in results) / max(n, 1)
    log('置信分布: %s' % json.dumps(dict(conf), ensure_ascii=False))
    log('flag 分布: %s' % json.dumps(dict(flags), ensure_ascii=False))
    log('卷面平均 P ≈ %.3f（目标带 0.55-0.65）' % avg_p)
    if flags.get('anchor_prior_conflict'):
        log('注意: %d 题锚点-先验冲突 >0.25，需 MedQC 复检'
            % flags.get('anchor_prior_conflict'))


# ---------------------------------------------------------------- 5. check
def cmd_check(args):
    if not (os.path.exists(CALIB_JSONL) and os.path.exists(PRIOR_JSON)):
        sys.exit('先运行: python anchor_bank.py anchor')
    results = [json.loads(l) for l in open(CALIB_JSONL, encoding='utf-8')]
    metas = [json.loads(l) for l in open(META_JSONL, encoding='utf-8')]
    _report(metas, results)


def _report(metas, results, path=None):
    """三重自洽校验（最终优化建议 §2.3）+ 报告落盘。"""
    from scipy.stats import spearmanr
    os.makedirs(REPORT_DIR, exist_ok=True)
    report_path = path or CHECK_JSON
    checks = {}

    # ① 锚点-先验一致性（有锚点子集：max_sim ≥ 0.65；按题型分池报告）
    anchored = [r for r in results if r['max_sim'] >= 0.65]
    detail = {}
    overall_pass = False
    for label, sub in [('总体', anchored),
                       ('单选池', [r for r in anchored if r['type'] != 'X']),
                       ('X型池', [r for r in anchored if r['type'] == 'X'])]:
        if len(sub) >= 30:
            rho, pv = spearmanr([r['anchor_p'] for r in sub],
                                [r['prior_p'] for r in sub])
            detail[label] = {'n': len(sub), 'rho': round(float(rho), 4),
                             'p_value': round(float(pv), 5)}
        else:
            detail[label] = {'n': len(sub), 'skipped': '样本不足'}
    rho_all = detail.get('总体', {}).get('rho')
    checks['1_anchor_prior_spearman'] = {
        'threshold': 0.35,
        'pass': bool(rho_all is not None and rho_all >= 0.35),
        'detail': detail,
        'note': ('先验表为学科×能力域×题型粗粒度兜底，池内逐题分辨率有限属设计使然；'
                 '若总体 FAIL 但各池结构合理，结论为先验仅可兜底、难度主信号应以锚点通道为准'),
    }

    # ② 结构合理性：X 型 hard 率（P<0.45）应高于 A1 型
    def hard_rate(t):
        sub = [r for r in results if r['type'] == t]
        if len(sub) < 20:
            return None
        return sum(1 for r in sub if r['calibrated_p'] < 0.45) / len(sub), len(sub)
    x_h, a1_h = hard_rate('X'), hard_rate('A1')
    if x_h and a1_h:
        checks['2_hard_rate_X_gt_A1'] = {
            'X_hard_rate': round(x_h[0], 4), 'A1_hard_rate': round(a1_h[0], 4),
            'pass': bool(x_h[0] > a1_h[0])}
    else:
        checks['2_hard_rate_X_gt_A1'] = {'skipped': '题型样本不足'}

    # ③ 考频-难度合理性：blueprint 为基础学科维度，自产题为临床课程，维度不交叠
    checks['3_freq_vs_difficulty'] = {
        'skipped': ('blueprint.json 为基础学科（生理/生化/病理…）权重，'
                    '自产题库为临床课程（NRO/PSY/YHGT…），无共享章节键；'
                    '待 L4 作答数据积累后以「章节实测答对率」替代')}

    passed = sum(1 for c in checks.values() if c.get('pass'))
    ran = sum(1 for c in checks.values() if 'pass' in c)
    report = {
        'generated_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
        'n_results': len(results), 'n_bank': len(metas),
        'checks': checks,
        'summary': '%d/%d 项通过，其余 skipped（原因见各项）' % (passed, ran),
        'boundary': 'calibrated_p 为 CMExam 人工标注锚点+先验表的外部先验估计，非本库实测',
    }
    json.dump(report, open(report_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    log('校验报告 → %s' % report_path)
    for k, v in checks.items():
        log('  %s: %s' % (k, json.dumps(v, ensure_ascii=False)))


def main():
    ap = argparse.ArgumentParser(description='CMExam 难度锚点库（零 API 成本）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('download').add_argument('--force', action='store_true',
                                            help='已存在也重新下载')
    pe = sub.add_parser('embed')
    pe.add_argument('--limit', type=int, default=0, help='只嵌入前 N 题（验证用）')
    pt = sub.add_parser('embed_train')
    pt.add_argument('--limit', type=int, default=0, help='只嵌入前 N 题（验证用）')
    pa = sub.add_parser('anchor')
    pa.add_argument('--limit', type=int, default=0, help='只处理前 N 道自产题（验证用）')
    pa.add_argument('--output', default='',
                    help='融合结果输出文件（默认 question_bank/calibrated_difficulty.jsonl）')
    pa.add_argument('--report', default='',
                    help='校验报告输出文件（默认 reports/anchor_check_report.json）')
    sub.add_parser('check')
    args = ap.parse_args()
    {'download': cmd_download, 'embed': cmd_embed, 'embed_train': cmd_embed_train,
     'anchor': cmd_anchor, 'check': cmd_check}[args.cmd](args)


if __name__ == '__main__':
    main()
