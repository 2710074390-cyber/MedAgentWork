#!/usr/bin/env python3
"""Recovery: re-index subjects that had batch failures due to rate limiting."""
import os, re, json, sys, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import fitz, requests, numpy as np

API_BASE = "https://api.siliconflow.cn/v1"
EMBED_MODEL = "BAAI/bge-m3"
BATCH_SIZE = 32
BATCH_SLEEP = 2.5          # increased from 0.15s to avoid 429
CHUNK_SIZE_CHARS = 800
CHUNK_OVERLAP = 150
MIN_CHUNK_SIZE = 100
MAX_RETRIES = 5             # increased from 3
TZ = timezone(timedelta(hours=8))

BASE_DIR = Path(r"C:\Users\38063\Desktop\MedAgentWork")
KB_DIR = BASE_DIR / "知识库素材"
INDEX_STORE = KB_DIR / "index_store"
META_DIR = KB_DIR / "chunks_metadata"

# subjects to recover
RECOVER = {
    "神经病学": "neurology",
    "中医学":   "tcm",
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
            if resp.status_code == 429 and attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)  # 2, 4, 8, 16, 32s
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

def chunk_text(text):
    sentences = split_sentences(text)
    chunks, current = [], ""
    for sent in sentences:
        if count_numeric_values(sent) >= 3:
            if current:
                if len(current) >= MIN_CHUNK_SIZE: chunks.append(current.strip())
                elif chunks: chunks[-1] = chunks[-1] + " " + current.strip()
                else: chunks.append(current.strip())
            chunks.append(sent.strip()); current = ""; continue
        if has_table_marker(sent):
            if current:
                if len(current) >= MIN_CHUNK_SIZE: chunks.append(current.strip())
                elif chunks: chunks[-1] = chunks[-1] + " " + current.strip()
            current = sent; continue
        if len(current) + len(sent) > CHUNK_SIZE_CHARS:
            if len(current) >= MIN_CHUNK_SIZE:
                chunks.append(current.strip())
                overlap_text = current[-CHUNK_OVERLAP:] if len(current) > CHUNK_OVERLAP else current
                current = overlap_text + sent
            else: current += sent
        else: current += sent
    if current and len(current) >= MIN_CHUNK_SIZE: chunks.append(current.strip())
    elif current and chunks: chunks[-1] = chunks[-1] + " " + current.strip()
    return chunks

def detect_chapter_section(text):
    chapter = section = ""; ch_num = 0
    ch_m = re.search(r'第[一二三四五六七八九十百\d]+章\s*[^\n]{0,30}', text)
    if ch_m:
        chapter = ch_m.group().strip()
        num_m = re.search(r'[\d]+', chapter)
        if num_m: ch_num = int(num_m.group())
    sec_m = re.search(r'第[一二三四五六七八九十\d]+节\s*[^\n]{0,30}', text)
    if sec_m: section = sec_m.group().strip()
    return chapter, ch_num, section

def extract_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    pages = [{"page_num": i+1, "text": page.get_text("text")}
             for i, page in enumerate(doc) if page.get_text("text").strip()]
    doc.close()
    return pages

def process_and_embed(pdf_path, subject, subject_code, api_key):
    print(f"\n[RECOVER] {subject} ({subject_code})")
    pages = extract_pdf(pdf_path)
    print(f"  Pages: {len(pages)}")

    all_chunks = []
    for page in pages:
        chapter, ch_num, section = detect_chapter_section(page["text"])
        for ci, chunk in enumerate(chunk_text(page["text"])):
            all_chunks.append({
                "meta": {
                    "subject": subject, "subject_code": subject_code,
                    "chapter": chapter or "", "chapter_num": ch_num,
                    "section": section or "", "page_number": page["page_num"],
                    "has_table": has_table_marker(chunk),
                    "has_numeric_data": count_numeric_values(chunk) > 0,
                    "textbook": f"{subject}(v10)" if "10" in str(pdf_path) else subject,
                    "char_count": len(chunk), "chunk_index": ci,
                    "indexed_at": datetime.now(TZ).isoformat(),
                },
                "text": chunk
            })

    # update chunk_ids
    for item in all_chunks:
        m = item["meta"]
        ch = f"ch{m['chapter_num']:02d}" if m['chapter_num'] else "chxx"
        m["chunk_id"] = f"{subject_code}_{ch}_p{m['page_number']:04d}_c{m['chunk_index']:04d}"

    total = len(all_chunks)
    print(f"  Chunks: {total}")

    embeddings, failed = [], 0
    for i in range(0, total, BATCH_SIZE):
        batch = all_chunks[i:i+BATCH_SIZE]
        texts = [item["text"] for item in batch]
        try:
            vecs = batch_embed(texts, api_key)
            for j, item in enumerate(batch):
                item["embedding"] = vecs[j]
                embeddings.append(item)
        except Exception as e:
            failed += len(batch)
            print(f"  [FAIL] batch {i//BATCH_SIZE} ({len(batch)} items): {e}")

        if i + BATCH_SIZE < total:
            print(f"  Progress: {min(i+BATCH_SIZE, total)}/{total} (sleep {BATCH_SLEEP}s)")
            time.sleep(BATCH_SLEEP)
        else:
            print(f"  Progress: {total}/{total}")

    print(f"  Stored: {len(embeddings)}/{total} (lost: {failed})")

    # save
    META_DIR.mkdir(parents=True, exist_ok=True)
    meta_file = META_DIR / f"{subject_code}_chunks.jsonl"
    with open(meta_file, "w", encoding="utf-8") as f:
        for item in embeddings:
            meta = item["meta"].copy(); meta["text"] = item["text"]
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")

    vec_file = INDEX_STORE / subject_code / "embeddings.npy"
    vec_file.parent.mkdir(parents=True, exist_ok=True)
    vecs_array = np.array([item["embedding"] for item in embeddings], dtype=np.float32)
    np.save(vec_file, vecs_array)

    print(f"  Saved: {meta_file} / {vec_file}")
    return len(embeddings)

def main():
    api_key = get_api_key()

    manifest_path = INDEX_STORE / "index_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # find PDFs for subjects that need recovery
    for entry in KB_DIR.iterdir():
        if not entry.is_dir(): continue
        for pdf in entry.glob("*.pdf"):
            for subject, code in RECOVER.items():
                if subject in pdf.stem and manifest.get(code, {}).get("status") in ("indexed", "partial"):
                    print("=" * 60)
                    print(f"Recovering: {subject} ({code})")
                    count = process_and_embed(pdf, subject, code, api_key)
                    manifest[code]["chunk_count"] = count
                    manifest[code]["status"] = "indexed"
                    manifest[code]["indexed_at"] = datetime.now(TZ).isoformat()
                    manifest[code].pop("needs_reindex", None)
                    print(f"  Done: {count} chunks stored")

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("[DONE] Recovery complete")
    for code, info in manifest.items():
        print(f"  {code}: {info['chunk_count']} chunks [{info['status']}]")

if __name__ == "__main__":
    main()
