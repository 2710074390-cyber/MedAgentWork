#!/usr/bin/env python3
"""索引认知神经科学 full.md → 分块 → 嵌入 → 存储"""
import os, re, json, sys, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests, numpy as np

# ─── 配置 ──────────────────────────────
API_BASE = "https://api.siliconflow.cn/v1"
EMBED_MODEL = "BAAI/bge-m3"
BATCH_SIZE = 32
MAX_RETRIES = 3
TZ = timezone(timedelta(hours=8))

BASE_DIR = Path(r"C:\Users\38063\Desktop\MedAgentWork")
KB_DIR = BASE_DIR / "知识库素材"
INDEX_STORE = KB_DIR / "index_store"
META_DIR = KB_DIR / "chunks_metadata"

SUBJECT = "认知神经科学"
SUBJECT_CODE = "cognitive-neuroscience"

# 从配置加载参数
CONFIG_FILE = KB_DIR / "configs" / f"{SUBJECT_CODE}_config.json"
with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

CS = cfg["chunk_strategy"]
CHUNK_SIZE = CS.get("chunk_size", 600)
OVERLAP = CS.get("overlap", 150)
MIN_CHUNK = CS.get("min_chunk_size", 60)
NUM_THRESHOLD = CS.get("numeric_threshold", 2)

# 编译保护模式
PROTECT_PATTERNS = []
for rule in CS.get("special_rules", []):
    if rule.get("type") == "pattern_protect" and rule.get("pattern"):
        try:
            PROTECT_PATTERNS.append(re.compile(rule["pattern"], re.IGNORECASE))
        except re.error as e:
            print(f"  [WARN] Invalid pattern: {e}")

print(f"Config: chunk={CHUNK_SIZE} overlap={OVERLAP} min={MIN_CHUNK}")
print(f"Protect patterns: {len(PROTECT_PATTERNS)}")

# ─── API ──────────────────────────────
def get_api_key():
    key = os.environ.get("SILICONFLOW_API_KEY")
    if not key:
        raise RuntimeError("未设置 SILICONFLOW_API_KEY 环境变量")
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
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt
            print(f"  [!] Retry {attempt+1}/{MAX_RETRIES}, wait {wait}s: {e}")
            time.sleep(wait)

def batch_embed(texts, api_key):
    result = api_request("embeddings", {
        "model": EMBED_MODEL,
        "input": texts,
        "encoding_format": "float"
    }, api_key)
    return [item["embedding"] for item in result["data"]]

# ─── 分块 ──────────────────────────────
def count_numeric(text):
    patterns = [
        r'\d+[~\-]\d+', r'\d+\.?\d*\s*[%％]',
        r'\d+\.?\d*\s*(?:mg|g|ml|L|μg|ng|U|IU|mm|cm|次|天|周|月|年|岁|分|小时|日)',
        r'\d+\.?\d*\s*(?:mmol|μmol|mmHg|kPa)', r'[><≥≤]\s*\d+',
    ]
    return sum(len(re.findall(p, text)) for p in patterns)

def split_sentences(text):
    parts = re.split(r'(?<=[。；\n])', text)
    return [p for p in parts if p.strip()]

def chunk_text(text, chunk_size, overlap, min_chunk, numeric_threshold, protect_patterns):
    sentences = split_sentences(text)
    chunks = []
    current = ""

    def _is_protected(sent):
        if count_numeric(sent) >= numeric_threshold:
            return True
        for pat in protect_patterns:
            if pat.search(sent):
                return True
        return False

    for sent in sentences:
        if _is_protected(sent):
            if current:
                if len(current) >= min_chunk:
                    chunks.append(current.strip())
                elif chunks:
                    chunks[-1] = chunks[-1] + " " + current.strip()
                else:
                    chunks.append(current.strip())
            chunks.append(sent.strip())
            current = ""
            continue

        if len(current) + len(sent) > chunk_size:
            if len(current) >= min_chunk:
                chunks.append(current.strip())
                overlap_text = current[-overlap:] if len(current) > overlap else current
                current = overlap_text + sent
            else:
                current += sent
        else:
            current += sent

    if current and len(current) >= min_chunk:
        chunks.append(current.strip())
    elif current and chunks:
        chunks[-1] = chunks[-1] + " " + current.strip()

    return chunks

def detect_chapter(text):
    m = re.search(r'第[一二三四五六七八九十百\d]+章\s*[^\n]{0,30}', text)
    if m:
        ch = m.group().strip()
        num_m = re.search(r'[\d]+', ch)
        ch_num = int(num_m.group()) if num_m else 0
        return ch, ch_num
    return "", 0

def detect_section(text):
    m = re.search(r'第[一二三四五六七八九十\d]+节\s*[^\n]{0,30}', text)
    return m.group().strip() if m else ""

# ─── 读取与分块 ─────────────────────────
FULL_MD = KB_DIR / "认知神经科学" / "full.md"
print(f"\nReading: {FULL_MD}")
with open(FULL_MD, 'r', encoding='utf-8') as f:
    content = f.read()
print(f"Total: {len(content):,} chars, {len(content.split(chr(10))):,} lines")

# 先按章节标题分割
chapter_pattern = re.compile(r'(?=^# .+$)', re.MULTILINE)
sections = chapter_pattern.split(content)

# 合并过短的section到前一个
merged = []
for s in sections:
    s = s.strip()
    if not s:
        continue
    if len(s) < 100 and merged:
        merged[-1] = merged[-1] + "\n" + s
    else:
        merged.append(s)
print(f"Sections: {len(sections)} → merged: {len(merged)}")

all_chunks = []
chapter = ""
ch_num = 0
for sec in merged:
    # 章节标题在section开头
    ch_match = re.match(r'^# (.+)$', sec, re.MULTILINE)
    if ch_match:
        chapter_name = ch_match.group(1).strip()
        ch, cn = detect_chapter(sec)
        if ch:
            chapter = ch
            ch_num = cn
        else:
            chapter = chapter_name
            ch_num = ch_num  # keep previous

    text_chunks = chunk_text(sec, CHUNK_SIZE, OVERLAP, MIN_CHUNK, NUM_THRESHOLD, PROTECT_PATTERNS)

    for ci, chunk in enumerate(text_chunks):
        section = detect_section(chunk)
        meta = {
            "chunk_id": "",
            "subject": SUBJECT,
            "subject_code": SUBJECT_CODE,
            "chapter": chapter or "",
            "chapter_num": ch_num,
            "section": section or "",
            "page_number": 0,
            "has_table": bool(re.search(r'表\s*\d+|Table', chunk)),
            "has_numeric_data": count_numeric(chunk) > 0,
            "textbook": "认知神经科学（PPT课件+教材）",
            "char_count": len(chunk),
            "chunk_index": ci,
            "indexed_at": datetime.now(TZ).isoformat(),
            # 元数据标注
            "has_syndrome": bool(re.search(r'(综合征|失认|失语|忽略|syndrome)', chunk)),
            "has_anatomy_pathway": bool(re.search(r'(通路|传导|投射|纤维|核团|皮层|脑区)', chunk)),
            "has_drug_info": bool(re.search(r'(用药|剂量|mg|μg|口服|静脉)', chunk)),
        }
        all_chunks.append({"meta": meta, "text": chunk})

# 更新chunk_id
for item in all_chunks:
    m = item["meta"]
    ch = f"ch{m['chapter_num']:02d}" if m['chapter_num'] else "chxx"
    m["chunk_id"] = f"{SUBJECT_CODE}_{ch}_c{m['chunk_index']:04d}"

print(f"Chunks: {len(all_chunks)}")
print(f"Avg chunk size: {sum(len(c['text']) for c in all_chunks)/max(len(all_chunks),1):.0f} chars")

# ─── 嵌入与存储 ─────────────────────────
api_key = get_api_key()

print(f"\n[EMBED] Starting with {EMBED_MODEL}...")
META_DIR.mkdir(parents=True, exist_ok=True)
meta_file = META_DIR / f"{SUBJECT_CODE}_chunks.jsonl"

total = len(all_chunks)
embeddings = []

for i in range(0, total, BATCH_SIZE):
    batch = all_chunks[i:i+BATCH_SIZE]
    texts = [item["text"] for item in batch]
    try:
        vecs = batch_embed(texts, api_key)
        for j, item in enumerate(batch):
            item["embedding"] = vecs[j]
            embeddings.append(item)
    except Exception as e:
        print(f"  [FAIL] batch {i//BATCH_SIZE}: {e}")
        continue

    progress = min(i+BATCH_SIZE, total)
    print(f"  Progress: {progress}/{total} ({progress*100//total}%)")
    if i + BATCH_SIZE < total:
        time.sleep(0.15)

# 写入元数据 JSONL (不含向量)
with open(meta_file, "w", encoding="utf-8") as f:
    for item in embeddings:
        meta = item["meta"].copy()
        meta["text"] = item["text"]
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")

# 向量存为 numpy
vecs_array = np.array([item["embedding"] for item in embeddings], dtype=np.float32)
vec_file = INDEX_STORE / SUBJECT_CODE / "embeddings.npy"
vec_file.parent.mkdir(parents=True, exist_ok=True)
np.save(vec_file, vecs_array)

print(f"\n[OK] Stored: {len(embeddings)} items")
print(f"     Metadata: {meta_file}")
print(f"     Vectors:  {vec_file} ({vecs_array.nbytes/1024/1024:.1f}MB)")

# ─── 更新清单 ──────────────────────────
manifest_path = INDEX_STORE / "index_manifest.json"
manifest = {}
if manifest_path.exists():
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

manifest[SUBJECT_CODE] = {
    "subject": SUBJECT,
    "status": "indexed",
    "chunk_count": len(embeddings),
    "source_file": "full.md (PPT课件+PDF教材合并)",
    "model": EMBED_MODEL,
    "chunk_size": CHUNK_SIZE,
    "overlap": OVERLAP,
    "subject_config_version": cfg.get("version", "1.0"),
    "config_source": str(CONFIG_FILE),
    "indexed_at": datetime.now(TZ).isoformat(),
}

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

# 保存配置快照
config_snapshot = INDEX_STORE / SUBJECT_CODE / "index_config.json"
config_snapshot.parent.mkdir(parents=True, exist_ok=True)
with open(config_snapshot, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)

print(f"\n[MANIFEST] Updated: {manifest_path}")
print(f"[DONE] 认知神经科学索引完成！")
