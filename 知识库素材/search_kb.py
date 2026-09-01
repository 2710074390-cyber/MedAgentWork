#!/usr/bin/env python3
"""
MedAgentWork 知识库检索脚本 — 两阶段检索
Stage 1: 硅基流动 embed 查询 → numpy cosine similarity → top-20
Stage 2: 硅基流动 rerank API → top-5

用法:
  python search_kb.py "心房颤动的CHA2DS2-VASc评分"                    # 搜索全部科目
  python search_kb.py "新生儿黄疸光疗指征" --subject 儿科学            # 限定科目
  python search_kb.py "补液张力计算" --subject 儿科学 --top 10        # 返回更多结果
  python search_kb.py -f queries.txt --subject 内科学                  # 批量查询
"""

import os, re, json, sys, time, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ─── 配置 ───────────────────────────────────────────
API_BASE = "https://api.siliconflow.cn/v1"
EMBED_MODEL = "BAAI/bge-m3"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
TOP_K_RETRIEVAL = 20   # Stage 1: how many to recall
TOP_N_RERANK = 5        # Stage 2: how many to return
SCORE_THRESHOLD = 0.70  # minimum rerank score to include
MAX_RETRIES = 3
TZ = timezone(timedelta(hours=8))

# 缓存（2026-08-20 成本优化 P1）：
#   检索是付费 API（embed + rerank 每查询两次调用）。相同查询在
#   MedGen 检索 / MedReview 检索 / 跨批次复用时反复付费。
#   磁盘缓存 key = hash(subject + query + 参数)，命中则 0 API 调用。
CACHE_ENABLED = True      # --no-cache 可关闭
CACHE_EMBED = True        # 是否缓存 embed 结果（同一查询重复 embed 免调用）

BASE_DIR = Path(r"C:\Users\38063\Desktop\MedAgentWork")
KB_DIR = BASE_DIR / "知识库素材"
INDEX_STORE = KB_DIR / "index_store"
META_DIR = KB_DIR / "chunks_metadata"
LOG_DIR = KB_DIR / "retrieval_log"
CONFIG_DIR = KB_DIR / "configs"
CACHE_DIR = KB_DIR / "cache"

# 科目名 → subject_code 映射
SUBJECT_ALIASES = {
    "内科学": "internal-med",
    "儿科学": "pediatrics",
    "外科学": "surgery",
    "神经病学": "neurology",
    "精神病学": "psychiatry",
    "皮肤性病学": "dermatology",
    "中医学": "tcm",
    "中医心理学": "tcm-psychology",
    "认知神经科学": "cognitive-neuroscience",
    "医患沟通": "doctor-patient",
    "贺银成讲义上": "heyincheng-jy1",
    "贺银成讲义中": "heyincheng-jy2",
    "贺银成讲义下": "heyincheng-jy3",
    "贺银成真题上": "heyincheng-zt1",
    "贺银成真题下": "heyincheng-zt2",
    "昭昭上": "zhaozhao-part1",
    "昭昭下": "zhaozhao-part2",
    # 人卫习题集（2026-07-03 新增）
    "内科习题集": "internal-med-exercise",
    "外科习题集": "surgery-exercise",
    "精神科习题集": "psychiatry-exercise",
    "内科学习题集": "internal-med-exercise",
    "外科学习题集": "surgery-exercise",
    "精神病学习题集": "psychiatry-exercise",
    # 大四上新增（2026-09-01）
    "口腔科学": "stomatology",
    "眼科学": "ophthalmology",
}

Auxiliary_CONFIG_MAP_SEARCH = {
    "heyincheng-jy1": "heyincheng-lecture_config.json",
    "heyincheng-jy2": "heyincheng-lecture_config.json",
    "heyincheng-jy3": "heyincheng-lecture_config.json",
    "heyincheng-zt1": "heyincheng-zhenti_config.json",
    "heyincheng-zt2": "heyincheng-zhenti_config.json",
    "zhaozhao-part1": "zhaozhao-tiyan_config.json",
    "zhaozhao-part2": "zhaozhao-tiyan_config.json",
}

def get_config_path(subject_code):
    if subject_code in Auxiliary_CONFIG_MAP_SEARCH:
        return CONFIG_DIR / Auxiliary_CONFIG_MAP_SEARCH[subject_code]
    config_file = CONFIG_DIR / f"{subject_code}_config.json"
    if config_file.exists():
        return config_file
    return None

def load_subject_config(subject_code):
    """Load per-subject config. Returns None on any failure (silent fallback to defaults)."""
    path = get_config_path(subject_code)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # 基本结构校验
        if "chunk_strategy" not in cfg and "retrieval_strategy" not in cfg:
            print(f"  [WARN] Config {path.name} missing required sections, falling back to defaults", file=sys.stderr)
            return None
        return cfg
    except json.JSONDecodeError as e:
        print(f"  [WARN] Config {path.name} JSON invalid: {e}, falling back to defaults", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [WARN] Config {path.name} load failed: {e}, falling back to defaults", file=sys.stderr)
        return None


def check_config_manifest_consistency(subject_code):
    """Return True if manifest entry is consistent with current config."""
    manifest_path = INDEX_STORE / "index_manifest.json"
    if not manifest_path.exists():
        return True  # no manifest → no conflict possible
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return True

    if subject_code not in manifest:
        return True

    entry = manifest[subject_code]
    m_ver = entry.get("subject_config_version", "unknown")
    if m_ver == "default" or m_ver == "unknown":
        return True  # no custom config used

    # Check if current config matches
    cfg = load_subject_config(subject_code)
    if cfg is None:
        return True  # no config to compare

    cfg_ver = cfg.get("version", "?")
    if m_ver != cfg_ver:
        print(f"  [WARN] Manifest config_ver={m_ver} ≠ current config ver={cfg_ver} "
              f"for {subject_code} — consider re-indexing", file=sys.stderr)
        return False
    return True

# ─── 缓存层（2026-08-20 新增 · 成本优化）─────────────

def _cache_key(parts):
    """稳定 cache key：hash(subject|query|参数|配置版本)。"""
    import hashlib
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_path(parts, suffix="json"):
    return CACHE_DIR / f"{_cache_key(parts)}.{suffix}"


def _cache_read(parts):
    """读缓存，返回 data 或 None。损坏/过期静默回退。"""
    if not CACHE_ENABLED:
        return None
    try:
        p = _cache_path(parts)
        if not p.exists():
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cache_write(parts, data):
    if not CACHE_ENABLED:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = _cache_path(parts)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def _cache_clear():
    """清空检索缓存（索引重建/参数调整后使用）。"""
    import shutil
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        print(f"  [CACHE] 已清空 {CACHE_DIR}")


def _config_sig(subject_code):
    """配置签名：索引重建后旧缓存自动失效。"""
    manifest_path = INDEX_STORE / "index_manifest.json"
    sig = "default"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            if subject_code in manifest:
                entry = manifest[subject_code]
                sig = f"{entry.get('config_version','?')}|{entry.get('chunk_size','?')}"
        except Exception:
            pass
    return sig


# ─── 加载索引 ────────────────────────────────────────

def get_api_key():
    key = os.environ.get("SILICONFLOW_API_KEY")
    if not key:
        raise RuntimeError("SILICONFLOW_API_KEY not set")
    return key


def api_request(endpoint, payload, api_key):
    url = f"{API_BASE}/{endpoint}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)


def embed_query(query_text, api_key):
    """Stage 1: embed the query（带缓存：同一查询免重复 API 调用）"""
    if CACHE_EMBED:
        cached = _cache_read(["embed", EMBED_MODEL, query_text])
        if cached is not None and "embedding" in cached:
            return np.array(cached["embedding"], dtype=np.float32)
    result = api_request("embeddings", {
        "model": EMBED_MODEL,
        "input": [query_text],
        "encoding_format": "float"
    }, api_key)
    emb = np.array(result["data"][0]["embedding"], dtype=np.float32)
    if CACHE_EMBED:
        _cache_write(["embed", EMBED_MODEL, query_text], {"embedding": emb.tolist()})
    return emb


def rerank(query, documents, api_key, top_n=TOP_N_RERANK):
    """Stage 2: rerank candidates"""
    if not documents:
        return []
    result = api_request("rerank", {
        "model": RERANK_MODEL,
        "query": query,
        "documents": documents,
        "top_n": min(top_n, len(documents)),
        "return_documents": True,
    }, api_key)
    return result.get("results", [])


def load_index(subject_code=None):
    """
    Load chunks and embeddings.
    If subject_code is specified, only load that subject.
    """
    manifest_path = INDEX_STORE / "index_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("index_manifest.json not found. Run embed_index.py first.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    all_chunks = []
    all_vectors = []

    codes_to_load = [subject_code] if subject_code else [
        k for k, v in manifest.items() if v.get("status") in ("indexed", "partial")
    ]

    for code in codes_to_load:
        if code not in manifest:
            print(f"  [WARN] {code} not in manifest, skipping")
            continue

        meta_file = META_DIR / f"{code}_chunks.jsonl"
        vec_file = INDEX_STORE / code / "embeddings.npy"

        if not meta_file.exists() or not vec_file.exists():
            print(f"  [WARN] Missing files for {code}, skipping")
            continue

        # Load metadata
        chunks = []
        with open(meta_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))

        # Load vectors
        vectors = np.load(vec_file)

        if len(chunks) != len(vectors):
            print(f"  [WARN] {code}: chunks({len(chunks)}) != vectors({len(vectors)}), truncating")
            min_len = min(len(chunks), len(vectors))
            chunks = chunks[:min_len]
            vectors = vectors[:min_len]

        all_chunks.extend(chunks)
        all_vectors.append(vectors)

    if not all_chunks:
        return [], None

    all_vectors = np.vstack(all_vectors) if all_vectors else np.array([])
    return all_chunks, all_vectors


def cosine_similarity_search(query_vec, doc_vectors, chunks, top_k=TOP_K_RETRIEVAL):
    """Fast cosine similarity using numpy"""
    # Normalize
    q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)
    d_norm = doc_vectors / (np.linalg.norm(doc_vectors, axis=1, keepdims=True) + 1e-8)
    scores = d_norm @ q_norm  # cosine similarity

    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        score = float(scores[idx])
        if score >= 0.3:  # loose pre-filter, reranker will refine
            chunk = chunks[idx].copy()
            chunk["_cosine_score"] = round(score, 4)
            chunk["_idx"] = int(idx)
            results.append(chunk)

    return results


# ─── 混合检索：关键词评分 ──────────────────────────────

def _tokenize_chinese(text):
    """Tokenize Chinese text into unigrams + bigrams + whole terms."""
    # Extract Chinese characters and alphanumeric sequences
    cleaned = re.sub(r'[^\u4e00-\u9fff\w]', '', text.lower())
    tokens = set()
    # characters (unigrams)
    for c in cleaned:
        if '\u4e00' <= c <= '\u9fff':
            tokens.add(c)
    # bigrams
    for i in range(len(cleaned) - 1):
        tokens.add(cleaned[i:i+2])
    # whole alphanumeric tokens
    for m in re.finditer(r'[a-z0-9]+', cleaned):
        tokens.add(m.group())
    return tokens


def keyword_match_score(query, chunks, query_tokens=None):
    """
    Compute keyword overlap score for each chunk.
    Returns numpy array of scores in [0, 1], same length as chunks.
    """
    if query_tokens is None:
        query_tokens = _tokenize_chinese(query)

    if not query_tokens:
        return np.zeros(len(chunks))

    scores = np.zeros(len(chunks))
    for i, chunk in enumerate(chunks):
        text = chunk.get("text", "").lower()
        # Exact match bonus
        exact_bonus = 0.0
        if query.lower() in text:
            exact_bonus = 0.3
        # Token overlap
        text_tokens = _tokenize_chinese(text)
        if text_tokens:
            overlap = len(query_tokens & text_tokens)
            jaccard = overlap / len(query_tokens | text_tokens)
            # Blend Jaccard with coverage
            coverage = overlap / len(query_tokens)
            scores[i] = min(1.0, 0.3 * jaccard + 0.4 * coverage + exact_bonus)
    return scores


def hybrid_rerank_candidates(candidates, query, keyword_weight=0.3):
    """
    Blend vector cosine scores with keyword scores for Stage 1 candidates.
    blended = (1 - keyword_weight) * cosine_score + keyword_weight * keyword_score

    Returns candidates re-sorted by blended score, with _kw_score and _blended_score added.
    """
    if not candidates or keyword_weight <= 0:
        for c in candidates:
            c["_kw_score"] = 0
            c["_blended_score"] = c.get("_cosine_score", 0)
        return candidates

    query_tokens = _tokenize_chinese(query)
    kw_scores = keyword_match_score(query, candidates, query_tokens)

    for i, c in enumerate(candidates):
        c["_kw_score"] = round(float(kw_scores[i]), 4)
        cosine = c.get("_cosine_score", 0)
        c["_blended_score"] = round((1 - keyword_weight) * cosine + keyword_weight * float(kw_scores[i]), 4)

    candidates.sort(key=lambda x: x["_blended_score"], reverse=True)
    return candidates


# ─── 检索接口 ────────────────────────────────────────

def enhance_query(query, config):
    """Expand query with synonym terms from subject config."""
    if not config:
        return [query]
    qe = config.get("query_enhancement", {})
    if not qe.get("synonym_expansion", False):
        return [query]
    term_map = qe.get("term_map", {})
    expanded = [query]
    for short, full in term_map.items():
        if short in query and full not in query:
            expanded.append(query.replace(short, full))
    return expanded


def search(query, api_key, subject=None, top_k=TOP_K_RETRIEVAL, top_n=TOP_N_RERANK,
           threshold=SCORE_THRESHOLD, config=None, hybrid_override=None, no_rerank=False):
    """
    Two-stage search with optional per-subject config.
    1. Embed query → cosine similarity → top-k candidates
    2. Rerank candidates → top-n results

    hybrid_override: True/False to force hybrid on/off, None to use config.
    no_rerank: True = 跳过付费 rerank，直接用 Stage1 余弦分数取 top_n（成本降级模式，
               2026-08-20：402 余额不足事件后提供，避免管线因 API 欠费中断）。
    缓存（2026-08-20）：完整检索结果按 (subject, query, 参数, 配置签名) 缓存，
               命中时零 API 调用；返回体带 "cached": true 标记。
    """
    subject_code = resolve_subject(subject) if subject else None

    # 从配置覆盖检索参数
    hybrid_search = False
    keyword_weight = 0.0
    if config and "retrieval_strategy" in config:
        rs = config["retrieval_strategy"]
        top_k = rs.get("top_k", top_k)
        top_n = rs.get("top_n", top_n)
        threshold = rs.get("score_threshold", threshold)
        hybrid_search = rs.get("hybrid_search", False)
        keyword_weight = rs.get("keyword_weight", 0.0)

    # CLI override for hybrid mode
    if hybrid_override is True:
        hybrid_search = True
        if keyword_weight <= 0:
            keyword_weight = 0.3  # default weight when forced
    elif hybrid_override is False:
        hybrid_search = False
        keyword_weight = 0.0

    # 缓存命中检查（key 含参数与配置签名，索引/参数变更自动失效）
    cache_parts = ["search", subject_code or "*", query, top_k, top_n,
                   round(threshold, 3), hybrid_search, keyword_weight, no_rerank,
                   _config_sig(subject_code)]
    cached = _cache_read(cache_parts)
    if cached is not None and "results" in cached:
        cached["cached"] = True
        return cached

    # 查询增强：同义词扩展
    queries = enhance_query(query, config)
    query_vec = embed_query(queries[0], api_key)  # 主查询 embedding

    chunks, doc_vectors = load_index(subject_code)

    if not chunks:
        result = {"query": query, "results": [], "error": "No chunks loaded"}
        _cache_write(cache_parts, result)
        return result

    # Stage 1: embed + cosine similarity
    candidates = cosine_similarity_search(query_vec, doc_vectors, chunks, top_k)

    # 同义词扩展查询也检索（加权合并）
    if len(queries) > 1:
        for extra_q in queries[1:]:
            extra_vec = embed_query(extra_q, api_key)
            extra_cands = cosine_similarity_search(extra_vec, doc_vectors, chunks,
                                                    max(top_k // 2, 5))
            # 合并去重（按 chunk_id），保留最高分
            seen_ids = {c.get("chunk_id", str(c["_idx"])) for c in candidates}
            for ec in extra_cands:
                eid = ec.get("chunk_id", str(ec["_idx"]))
                if eid not in seen_ids:
                    candidates.append(ec)
                    seen_ids.add(eid)
            # Trim back to top_k
            candidates.sort(key=lambda x: x.get("_cosine_score", 0), reverse=True)
            candidates = candidates[:top_k]

    if not candidates:
        result = {"query": query, "results": [], "stage1_hits": 0}
        _cache_write(cache_parts, result)
        return result

    # 混合检索：关键词重排 Stage 1 候选
    if hybrid_search and keyword_weight > 0:
        candidates = hybrid_rerank_candidates(candidates, query, keyword_weight)

    # 降级模式：跳过付费 rerank（成本优化）
    if no_rerank:
        final = []
        score_key = "_blended_score" if (hybrid_search and keyword_weight > 0) else "_cosine_score"
        for c in candidates[:top_n]:
            score = c.get(score_key, 0)
            if score >= 0.3:  # 余弦分数阈值（低于 rerank 阈值，属不同尺度）
                entry = {
                    "subject": c.get("subject", ""),
                    "chapter": c.get("chapter", ""),
                    "page_number": c.get("page_number", 0),
                    "pdf_page_number": c.get("pdf_page_number"),
                    "score": round(score, 4),
                    "text": c["text"],
                    "textbook": c.get("textbook", ""),
                    "chunk_id": c.get("chunk_id", ""),
                    "reranked": False,
                }
                final.append(entry)
        result = {
            "query": query,
            "subject_filter": subject,
            "stage1_candidates": len(candidates),
            "stage2_results": len(final),
            "results": final,
            "config_applied": config is not None,
            "hybrid_search": hybrid_search,
            "keyword_weight": keyword_weight,
            "no_rerank": True,
        }
        _cache_write(cache_parts, result)
        return result

    # Stage 2: rerank
    doc_texts = [c["text"] for c in candidates]
    rerank_results = rerank(query, doc_texts, api_key, top_n)

    # Build final results
    final = []
    for rr in rerank_results:
        idx = rr.get("index", 0)
        if idx < len(candidates):
            chunk = candidates[idx]
            score = rr.get("relevance_score", 0)
            if score >= threshold:
                entry = {
                    "subject": chunk.get("subject", ""),
                    "chapter": chunk.get("chapter", ""),
                    "page_number": chunk.get("page_number", 0),
                    "pdf_page_number": chunk.get("pdf_page_number"),
                    "score": round(score, 4),
                    "text": chunk["text"],
                    "textbook": chunk.get("textbook", ""),
                    "chunk_id": chunk.get("chunk_id", ""),
                }
                if hybrid_search:
                    entry["_cosine_score"] = chunk.get("_cosine_score", 0)
                    entry["_kw_score"] = chunk.get("_kw_score", 0)
                    entry["_blended_score"] = chunk.get("_blended_score", 0)
                final.append(entry)

    result = {
        "query": query,
        "subject_filter": subject,
        "stage1_candidates": len(candidates),
        "stage2_results": len(final),
        "results": final,
        "config_applied": config is not None,
        "hybrid_search": hybrid_search,
        "keyword_weight": keyword_weight,
    }
    _cache_write(cache_parts, result)
    return result


def resolve_subject(name):
    """Resolve Chinese subject name or abbreviation to code."""
    for alias, code in SUBJECT_ALIASES.items():
        if name in alias or alias in name:
            return code
    # Also check manifest codes
    manifest_path = INDEX_STORE / "index_manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        for code, info in manifest.items():
            if name in info.get("subject", ""):
                return code
    return name


def log_retrieval(query, results, subject):
    """Log retrieval for quality monitoring."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / datetime.now(TZ).strftime("retrieval_%Y%m%d.jsonl")
    entry = {
        "timestamp": datetime.now(TZ).isoformat(),
        "query": query,
        "subject_filter": subject,
        "num_results": len(results.get("results", [])),
        "top_score": results["results"][0]["score"] if results.get("results") else 0,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─── CLI ────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MedAgentWork Knowledge Base Search")
    parser.add_argument("query", nargs="?", help="Search query text")
    parser.add_argument("--subject", "-s", help="Subject filter (e.g. 内科学, 儿科学)")
    parser.add_argument("--top", "-k", type=int, default=TOP_N_RERANK, help="Number of results (default: 5)")
    parser.add_argument("--recall", "-r", type=int, default=TOP_K_RETRIEVAL, help="Stage 1 recall count (default: 20)")
    parser.add_argument("--file", "-f", help="Batch queries from file (one per line)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON only")
    parser.add_argument("--threshold", "-t", type=float, default=SCORE_THRESHOLD, help="Min score threshold (default: 0.70)")
    parser.add_argument("--hybrid", action="store_true", default=None, help="Enable hybrid keyword+vector search")
    parser.add_argument("--no-hybrid", dest="hybrid_disable", action="store_true", help="Disable hybrid search even if config says so")
    parser.add_argument("--no-cache", action="store_true", help="禁用检索/embed 磁盘缓存（默认开启，成本优化）")
    parser.add_argument("--no-rerank", action="store_true", help="跳过付费 rerank，用 Stage1 余弦分数（成本降级模式）")
    parser.add_argument("--cache-clear", action="store_true", help="清空检索缓存后退出（索引重建/参数调整后使用）")

    args = parser.parse_args()

    if args.cache_clear:
        _cache_clear()
        return

    if args.no_cache:
        global CACHE_ENABLED, CACHE_EMBED
        CACHE_ENABLED = False
        CACHE_EMBED = False

    if not args.query and not args.file:
        parser.print_help()
        return

    api_key = get_api_key()

    # Override threshold
    threshold = args.threshold

    queries = []
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]
    else:
        queries = [args.query]

    # 加载学科个性化配置
    subj_config = None
    if args.subject:
        subject_code = resolve_subject(args.subject)
        subj_config = load_subject_config(subject_code)
        # 检查索引是否与当前配置一致
        check_config_manifest_consistency(subject_code)
        if subj_config and not args.json:
            rs = subj_config.get("retrieval_strategy", {})
            h_mode = "ON (forced)" if args.hybrid else ("OFF (disabled)" if args.hybrid_disable else rs.get('hybrid_search', False))
            print(f"[CONFIG] {subject_code}: top_k={rs.get('top_k', args.recall)} "
                  f"top_n={rs.get('top_n', args.top)} "
                  f"hybrid={h_mode} "
                  f"kw_weight={rs.get('keyword_weight', 0)}")

    # Determine hybrid override
    hybrid_override = None
    if args.hybrid:
        hybrid_override = True
    elif args.hybrid_disable:
        hybrid_override = False

    all_results = {}
    cache_hits = 0
    for q in queries:
        if not args.json:
            print(f"\n[QUERY] {q}")
        results = search(q, api_key, args.subject, args.recall, args.top,
                         threshold, subj_config, hybrid_override,
                         no_rerank=args.no_rerank)
        all_results[q] = results
        if results.get("cached"):
            cache_hits += 1

        if not args.json:
            mode = "CACHE" if results.get("cached") else ("STAGE1-only" if results.get("no_rerank") else "2-stage")
            if results.get("error"):
                print(f"  [ERROR] {results['error']}")
                continue
            print(f"  [{mode}] Stage1: {results.get('stage1_candidates', 0)} candidates → Stage2: {results.get('stage2_results', 0)} results")
            for i, r in enumerate(results.get("results", [])):
                print(f"  [{i+1}] {r['subject']} 教材P{r['page_number']} | score={r['score']}")
                print(f"      {r['text'][:120]}...")
        else:
            # Log
            log_retrieval(q, results, args.subject)

    if not args.json and len(queries) > 1:
        print(f"\n  [CACHE] {cache_hits}/{len(queries)} 查询命中缓存（0 API 调用）")

    # Output final JSON
    output = {"queries": all_results} if len(queries) > 1 else all_results[queries[0]]
    out_path = BASE_DIR / "中间产物" / "kb_search_result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    if not args.json:
        print(f"\n[SAVED] {out_path}")


if __name__ == "__main__":
    main()
