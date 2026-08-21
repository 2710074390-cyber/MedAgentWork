#!/usr/bin/env python3
"""Index mineru-extracted markdown files (贺银成讲义 + 真题) into the knowledge base."""
import os, re, json, sys, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests, numpy as np

API_BASE = "https://api.siliconflow.cn/v1"
EMBED_MODEL = "BAAI/bge-m3"
BATCH_SIZE = 32
BATCH_SLEEP = 2.5
CHUNK_SIZE_CHARS = 800
CHUNK_OVERLAP = 150
MIN_CHUNK_SIZE = 100
MAX_RETRIES = 5
TZ = timezone(timedelta(hours=8))

BASE_DIR = Path(r"C:\Users\38063\Desktop\MedAgentWork")
KB_DIR = BASE_DIR / "知识库素材"
INDEX_STORE = KB_DIR / "index_store"
META_DIR = KB_DIR / "chunks_metadata"
CONFIG_DIR = KB_DIR / "configs"

MINERU_DIR = Path(r"C:\Users\38063\Desktop\大三下\26贺银成\mineru_merged")

# Config mapping for auxiliary materials
AUX_CONFIG_MAP_MD = {
    "heyincheng-jy1": "heyincheng-lecture_config.json",
    "heyincheng-jy2": "heyincheng-lecture_config.json",
    "heyincheng-jy3": "heyincheng-lecture_config.json",
    "heyincheng-zt1": "heyincheng-zhenti_config.json",
    "heyincheng-zt2": "heyincheng-zhenti_config.json",
}

def load_subject_config_md(subject_code):
    if subject_code in AUX_CONFIG_MAP_MD:
        path = CONFIG_DIR / AUX_CONFIG_MAP_MD[subject_code]
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    return None

# Files to index
TO_INDEX = {
    "讲义上册": {"code": "heyincheng-jy1", "subject": "贺银成讲义上册", "priority": 1},
    "讲义中册": {"code": "heyincheng-jy2", "subject": "贺银成讲义中册", "priority": 1},
    "讲义下册": {"code": "heyincheng-jy3", "subject": "贺银成讲义下册", "priority": 1},
    "真题上册": {"code": "heyincheng-zt1", "subject": "贺银成真题上册", "priority": 0},
    "真题下册": {"code": "heyincheng-zt2", "subject": "贺银成真题下册", "priority": 0},
}

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
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"  [429] retry {attempt+1}/{MAX_RETRIES}, wait {wait}s")
                    time.sleep(wait)
                    continue
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2 ** (attempt + 1)
            print(f"  [!] retry {attempt+1}/{MAX_RETRIES}, wait {wait}s: {e}")
            time.sleep(wait)

def batch_embed(texts, api_key):
    result = api_request("embeddings", {
        "model": EMBED_MODEL, "input": texts, "encoding_format": "float"
    }, api_key)
    return [item["embedding"] for item in result["data"]]

def count_numeric_values(text):
    patterns = [
        r'\d+[~\-]\d+', r'\d+\.?\d*\s*[%％]',
        r'\d+\.?\d*\s*(?:mg|g|ml|L|μg|ng|U|IU|mm|cm|次|天|周|月|年|岁|分|小时|日)',
        r'\d+\.?\d*\s*(?:mmol|μmol|mmol/L|mg/dl|mmHg|kPa)', r'[><≥≤]\s*\d+',
    ]
    return sum(len(re.findall(p, text)) for p in patterns)

def has_table_marker(text):
    return bool(re.search(r'表\s*\d+|Table\s*\d+', text))

def split_sentences(text):
    parts = re.split(r'(?<=[。；\n])', text)
    return [p for p in parts if p.strip()]

def chunk_text(text, chunk_size=CHUNK_SIZE_CHARS, overlap=CHUNK_OVERLAP,
               min_chunk_size=MIN_CHUNK_SIZE, numeric_threshold=3,
               protect_patterns=None):
    sentences = split_sentences(text)
    chunks, current = [], ""
    if protect_patterns is None:
        protect_patterns = []

    def _is_protected(sent):
        if count_numeric_values(sent) >= numeric_threshold:
            return True
        if has_table_marker(sent):
            return True
        for pat in protect_patterns:
            if pat.search(sent):
                return True
        return False

    for sent in sentences:
        if _is_protected(sent):
            if current:
                if len(current) >= min_chunk_size: chunks.append(current.strip())
                elif chunks: chunks[-1] = chunks[-1] + " " + current.strip()
                else: chunks.append(current.strip())
            chunks.append(sent.strip()); current = ""; continue
        if len(current) + len(sent) > chunk_size:
            if len(current) >= min_chunk_size:
                chunks.append(current.strip())
                overlap_text = current[-overlap:] if len(current) > overlap else current
                current = overlap_text + sent
            else: current += sent
        else: current += sent
    if current and len(current) >= min_chunk_size: chunks.append(current.strip())
    elif current and chunks: chunks[-1] = chunks[-1] + " " + current.strip()
    return chunks

def clean_mineru_md(text):
    """Remove MinerU artifacts from markdown."""
    # Remove HTML comments (page markers)
    text = re.sub(r'<!--[^>]*-->', '', text)
    # Remove image references
    text = re.sub(r'!\[.*?\]\(images/[^)]+\)', '', text)
    # Remove <details> blocks
    text = re.sub(r'<details>\s*<summary>.*?</summary>.*?</details>', '', text, flags=re.DOTALL)
    # Clean up extra blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove latex markers that don't render well in plain text
    text = text.replace('$\\geqslant$', '>=').replace('$\\leqslant$', '<=')
    # Remove standalone $ signs
    text = re.sub(r'\$\\([^)]*)\\', r'\\1', text)
    # Clean inline math (keep the text content)
    text = re.sub(r'\$([^$]+)\$', r'\1', text)
    return text.strip()

def detect_chapter_heading(text):
    """Detect chapter/section from markdown headings."""
    ch_m = re.search(r'^#{1,3}\s*(第[一二三四五六七八九十百\d]+[章篇节]|[A-Z][a-z]+\s+\d+|[一二三四五六七八九十]+、)', text, re.MULTILINE)
    if ch_m:
        return ch_m.group().strip('#').strip()
    return ""

def process_md(md_path, subject, subject_code, config=None):
    print(f"\n[MD] Processing: {subject}")

    cs = config.get("chunk_strategy", {}) if config else {}
    c_size = cs.get("chunk_size", CHUNK_SIZE_CHARS)
    c_overlap = cs.get("overlap", CHUNK_OVERLAP)
    c_min = cs.get("min_chunk_size", MIN_CHUNK_SIZE)
    c_num_th = cs.get("numeric_threshold", 3)

    protect_patterns = []
    for rule in cs.get("special_rules", []):
        if rule.get("type") == "pattern_protect" and rule.get("pattern"):
            try:
                protect_patterns.append(re.compile(rule["pattern"], re.IGNORECASE))
            except re.error as e:
                print(f"  [WARN] Invalid pattern '{rule['pattern']}': {e}")

    if config:
        print(f"  [CONFIG] chunk={c_size} overlap={c_overlap} min={c_min} num_th={c_num_th}"
              f" protect_rules={len(protect_patterns)}")

    with open(md_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    text = clean_mineru_md(raw)
    sections = re.split(r'\n\n+', text)
    sections = [s.strip() for s in sections if len(s.strip()) >= 20]

    all_chunks = []
    current_chapter = ""
    for sec in sections:
        heading = detect_chapter_heading(sec)
        if heading:
            current_chapter = heading
        chunks = chunk_text(sec, chunk_size=c_size, overlap=c_overlap,
                           min_chunk_size=c_min, numeric_threshold=c_num_th,
                           protect_patterns=protect_patterns)
        for ci, chunk in enumerate(chunks):
            all_chunks.append({
                "meta": {
                    "subject": subject, "subject_code": subject_code,
                    "chapter": current_chapter, "chapter_num": 0,
                    "section": "", "page_number": 0,
                    "has_table": has_table_marker(chunk),
                    "has_numeric_data": count_numeric_values(chunk) > 0,
                    "textbook": "贺银成考研西医综合辅导讲义",
                    "char_count": len(chunk), "chunk_index": ci,
                    "indexed_at": datetime.now(TZ).isoformat(),
                },
                "text": chunk
            })

    # assign chunk_ids
    for idx, item in enumerate(all_chunks):
        item["meta"]["chunk_id"] = f"{subject_code}_c{idx:05d}"

    print(f"  Sections: {len(sections)}, Chunks: {len(all_chunks)}")
    return all_chunks

def embed_and_store(chunks, subject_code, api_key):
    """嵌入并存储。返回 (stored_count, failed_batches)。

    v1.1 (2026-08-20 审查修复 C4，与 embed_index.py 同步): 批次失败计数并告警、
    全部失败抛错不写盘、meta/npy 原子写。
    """
    print(f"  [EMBED] {len(chunks)} chunks...")
    META_DIR.mkdir(parents=True, exist_ok=True)
    meta_file = META_DIR / f"{subject_code}_chunks.jsonl"

    total = len(chunks)
    embeddings = []
    failed_batches = 0

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i:i+BATCH_SIZE]
        texts = [item["text"] for item in batch]
        try:
            vecs = batch_embed(texts, api_key)
            for j, item in enumerate(batch):
                item["embedding"] = vecs[j]
                embeddings.append(item)
        except Exception as e:
            print(f"  [FAIL] batch {i//BATCH_SIZE}: {e}")
            failed_batches += 1

        if i + BATCH_SIZE < total:
            print(f"  Progress: {min(i+BATCH_SIZE, total)}/{total} (sleep {BATCH_SLEEP}s)")
            time.sleep(BATCH_SLEEP)
        else:
            print(f"  Progress: {total}/{total}")

    if failed_batches:
        print(f"  ⚠️ {failed_batches} 个批次嵌入失败 → partial 索引（{len(embeddings)}/{total}），"
              f"manifest 将标注 status=partial")
    if not embeddings:
        raise RuntimeError(f"{subject_code}: 全部批次嵌入失败，未写入任何数据")

    tmp_meta = meta_file.with_name(meta_file.name + '.tmp')
    with open(tmp_meta, "w", encoding="utf-8") as f:
        for item in embeddings:
            meta = item["meta"].copy(); meta["text"] = item["text"]
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
    os.replace(tmp_meta, meta_file)

    vec_file = INDEX_STORE / subject_code / "embeddings.npy"
    vec_file.parent.mkdir(parents=True, exist_ok=True)
    vecs_array = np.array([item["embedding"] for item in embeddings], dtype=np.float32)
    tmp_vec = vec_file.with_name(vec_file.name + '.tmp')
    np.save(tmp_vec, vecs_array)
    os.replace(tmp_vec, vec_file)

    print(f"  [OK] Stored: {len(embeddings)}")
    return len(embeddings), failed_batches

def update_manifest(subject_code, info, chunk_count, config=None, status="indexed"):
    INDEX_STORE.mkdir(parents=True, exist_ok=True)
    manifest_path = INDEX_STORE / "index_manifest.json"

    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    entry = {
        "subject": info["subject"],
        # v1.1 (2026-08-20 审查修复 C4): 支持 'partial'（部分批次嵌入失败）
        "status": status,
        "chunk_count": chunk_count,
        "source_file": f"{info['subject']}.md",
        "model": EMBED_MODEL,
        "rerank_model": "BAAI/bge-reranker-v2-m3",
        "chunk_size": config["chunk_strategy"]["chunk_size"] if config else CHUNK_SIZE_CHARS,
        "overlap": config["chunk_strategy"]["overlap"] if config else CHUNK_OVERLAP,
        "indexed_at": datetime.now(TZ).isoformat(),
    }
    if config:
        entry["subject_config_version"] = config.get("version", "1.0")
    else:
        entry["subject_config_version"] = "default"

    manifest[subject_code] = entry

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Index mineru markdown files")
    parser.add_argument("--force", "-f", action="store_true", help="Force re-index")
    args = parser.parse_args()

    api_key = get_api_key()

    manifest_path = INDEX_STORE / "index_manifest.json"
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    to_process = []
    for dirname, info in TO_INDEX.items():
        if not args.force and info["code"] in manifest and manifest[info["code"]].get("status") == "indexed":
            print(f"[SKIP] {info['subject']} (already indexed, use --force to re-index)")
            continue
        if args.force and info["code"] in manifest:
            print(f"[RE-INDEX] {info['subject']} (forced)")
        md_path = MINERU_DIR / dirname / f"{dirname}.md"
        if md_path.exists():
            to_process.append((md_path, info))
        else:
            print(f"[MISS] {md_path}")

    if not to_process:
        print("All files already indexed.")
        return

    to_process.sort(key=lambda x: x[1]["priority"])

    print("=" * 60)
    print(f"Indexing {len(to_process)} mineru markdown files | Force: {args.force}")
    print("=" * 60)

    for md_path, info in to_process:
        try:
            subj_config = load_subject_config_md(info["code"])
            if subj_config:
                print(f"[CONFIG] Loaded {info['code']}: v{subj_config.get('version', '?')}")
            chunks = process_md(md_path, info["subject"], info["code"], subj_config)
            if not chunks:
                print(f"  [WARN] No chunks")
                continue
            count, failed_batches = embed_and_store(chunks, info["code"], api_key)
            status = 'partial' if failed_batches else 'indexed'
            update_manifest(info["code"], info, count, subj_config, status=status)
        except Exception as e:
            import traceback
            print(f"[FAIL] {info['subject']}: {e}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("[DONE] Mineru markdown indexing complete")
    for code, entry in manifest.items():
        if code.startswith("heyincheng"):
            print(f"  {entry['subject']}: {entry['chunk_count']} chunks")

if __name__ == "__main__":
    main()
