#!/usr/bin/env python3
"""
索引 MinerU OCR 产物（full.md）→ 向量知识库。
替代 PDF→文本 步骤，直接从 Markdown 分块嵌入。

用法：python scripts/index_exercise_md.py
"""
import os, sys, json, re, time, traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE = Path(r"C:\Users\38063\Desktop\MedAgentWork")
sys.path.insert(0, str(BASE / "知识库素材"))

from embed_index import (
    get_api_key, chunk_text, embed_and_store, update_manifest,
    detect_chapter_section, count_numeric_values, has_table_marker,
    INDEX_STORE, META_DIR, TZ
)

KB_DIR = BASE / "知识库素材"
CONFIG_DIR = KB_DIR / "configs"
TZ = timezone(timedelta(hours=8))

EXERCISE_MD = [
    {
        "md_path": KB_DIR / "外科学/外科学学习指导与习题集_OCR_full.md",
        "subject": "外科学（习题集）",
        "code": "surgery-exercise",
        "config": "surgery-exercise_config.json",
    },
    {
        "md_path": KB_DIR / "精神病学/精神病学学习指导与习题集_OCR_full.md",
        "subject": "精神病学（习题集）",
        "code": "psychiatry-exercise",
        "config": "psychiatry-exercise_config.json",
    },
]


def load_config(config_filename):
    path = CONFIG_DIR / config_filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def process_markdown(md_path, subject, subject_code, config=None):
    """Process OCR markdown into chunks, similar to process_pdf but for text."""
    print(f"\n[MD] Processing: {md_path.name}")

    cs = config.get("chunk_strategy", {}) if config else {}
    chunk_size = cs.get("chunk_size", 800)
    overlap = cs.get("overlap", 150)
    min_chunk_size = cs.get("min_chunk_size", 100)
    numeric_threshold = cs.get("numeric_threshold", 2)
    enrich_fields = cs.get("metadata_enrichment", [])

    # Compile protect patterns
    protect_patterns = []
    for rule in cs.get("special_rules", []):
        if rule.get("type") == "pattern_protect" and rule.get("pattern"):
            try:
                protect_patterns.append(re.compile(rule["pattern"], re.IGNORECASE))
            except re.error:
                pass

    if config:
        print(f"  [CONFIG] chunk={chunk_size} overlap={overlap} min={min_chunk_size} "
              f"num_th={numeric_threshold} enrich={enrich_fields}")

    # Read full markdown
    text = md_path.read_text(encoding="utf-8")

    # Split by markdown headers for page-like segments
    # Each ## or # header starts a new "page" segment
    segments = re.split(r'\n(?=#{1,3}\s)', text)
    segments = [s.strip() for s in segments if s.strip()]

    if not segments:
        print("  [WARN] Empty content")
        return []

    print(f"  Segments: {len(segments)}")

    all_chunks = []
    for si, seg in enumerate(segments):
        chapter, ch_num, section = detect_chapter_section(seg)
        text_chunks = chunk_text(seg, chunk_size=chunk_size, overlap=overlap,
                                 min_chunk_size=min_chunk_size,
                                 numeric_threshold=numeric_threshold,
                                 protect_patterns=protect_patterns)

        for ci, chunk_text_content in enumerate(text_chunks):
            meta = {
                "chunk_id": "",
                "subject": subject,
                "subject_code": subject_code,
                "chapter": chapter or "",
                "chapter_num": ch_num,
                "section": section or "",
                "page_number": si + 1,  # segment number as pseudo-page
                "pdf_page_number": si + 1,
                "has_table": has_table_marker(chunk_text_content),
                "has_numeric_data": count_numeric_values(chunk_text_content) > 0,
                "textbook": f"{subject}(MinerU OCR)",
                "char_count": len(chunk_text_content),
                "chunk_index": ci,
                "source_type": "ocr_markdown",
                "indexed_at": datetime.now(TZ).isoformat(),
            }

            # Enrich metadata (same logic as embed_index.py)
            if "has_scale" in enrich_fields:
                meta["has_scale"] = bool(re.search(r'(评分|量表|scale|score)', chunk_text_content, re.I))
            if "has_diagnostic_criteria" in enrich_fields:
                meta["has_diagnostic_criteria"] = bool(re.search(r'(诊断标准|诊断条目|符合.*条|诊断依据)', chunk_text_content))
            if "has_procedure" in enrich_fields:
                meta["has_procedure"] = bool(re.search(r'(手术|术式|切口|入路|切除|吻合|重建|修补)', chunk_text_content))
            if "has_staging" in enrich_fields:
                meta["has_staging"] = bool(re.search(r'(分期|分型|TNM|Garden|Neer)', chunk_text_content))
            if "has_indications" in enrich_fields:
                meta["has_indications"] = bool(re.search(r'(适应证|禁忌证|适应症|禁忌症)', chunk_text_content))
            if "has_question" in enrich_fields:
                meta["has_question"] = bool(re.search(r'(A1型题|A2型题|B1型题|X型题|单选题|多选题|题干|参考答案)', chunk_text_content))
            if "has_kaodian" in enrich_fields:
                meta["has_kaodian"] = bool(re.search(r'(参考答案|解析|★|考点|解题思路)', chunk_text_content))
            if "has_drug_info" in enrich_fields:
                meta["has_drug_info"] = bool(re.search(r'(用药|剂量|mg|μg|口服|静脉|肌注|首选药物)', chunk_text_content))
            if "has_numeric_data" in enrich_fields:
                meta["has_numeric_data"] = count_numeric_values(chunk_text_content) > 0

            all_chunks.append({"meta": meta, "text": chunk_text_content})

    # Assign chunk_ids
    for item in all_chunks:
        m = item["meta"]
        ch = f"ch{m['chapter_num']:02d}" if m['chapter_num'] else "chxx"
        m["chunk_id"] = f"{subject_code}_{ch}_s{m['page_number']:04d}_c{m['chunk_index']:04d}"

    print(f"  Chunks: {len(all_chunks)}")
    return all_chunks


def main():
    api_key = get_api_key()

    print("=" * 60)
    print("人卫习题集 OCR Markdown 索引流水线")
    print(f"待索引：{len(EXERCISE_MD)} 科")
    print("=" * 60)

    for item in EXERCISE_MD:
        exists = "OK" if item["md_path"].exists() else "MISSING"
        print(f"  {item['code']:<28s} {item['md_path'].name:<45s} {exists}")

    if not all(item["md_path"].exists() for item in EXERCISE_MD):
        print("\n[ERROR] Some files missing!")
        return

    print()

    results = {}
    for item in EXERCISE_MD:
        print(f"\n{'='*60}")
        print(f"[INDEX] {item['subject']} ({item['code']})")
        print(f"  Source: {item['md_path'].name}")
        print(f"{'='*60}")

        try:
            config = load_config(item["config"])
            if config:
                cs = config.get("chunk_strategy", {})
                rs = config.get("retrieval_strategy", {})
                print(f"  [CONFIG] v{config.get('version','?')} "
                      f"chunk={cs.get('chunk_size','?')} "
                      f"overlap={cs.get('overlap','?')} "
                      f"hybrid={rs.get('hybrid_search','?')} "
                      f"kw_weight={rs.get('keyword_weight','?')}")

            chunks = process_markdown(item["md_path"], item["subject"], item["code"], config)

            if not chunks:
                print(f"  [WARN] No chunks")
                results[item["code"]] = {"status": "empty", "chunks": 0}
                continue

            # Stats
            q_count = sum(1 for c in chunks if c["meta"].get("has_question"))
            a_count = sum(1 for c in chunks if c["meta"].get("has_kaodian"))
            print(f"  Chunks: {len(chunks)} (含题目: {q_count}, 含答案/解析: {a_count})")

            embed_and_store(chunks, item["code"], api_key)
            update_manifest(item["code"], item["subject"], len(chunks), item["md_path"], config)

            # Mark as exercise collection
            manifest_path = INDEX_STORE / "index_manifest.json"
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            if item["code"] in manifest:
                manifest[item["code"]]["source_type"] = "exercise_collection_ocr"
                manifest[item["code"]]["publisher"] = "人民卫生出版社"
                manifest[item["code"]]["ocr_engine"] = "MinerU"
                manifest[item["code"]]["linked_textbook_code"] = item["code"].replace("-exercise", "")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            results[item["code"]] = {"status": "ok", "chunks": len(chunks)}
            print(f"  [OK] {item['subject']} 索引完成")

        except Exception as e:
            print(f"\n[FAIL] {item['subject']}: {e}")
            traceback.print_exc()
            results[item["code"]] = {"status": "fail", "error": str(e)}
            continue

    # Summary
    print("\n" + "=" * 60)
    print("[SUMMARY] OCR Markdown 索引结果")
    print("=" * 60)
    for item in EXERCISE_MD:
        r = results.get(item["code"], {})
        ok = "OK" if r.get("status") == "ok" else "FAIL"
        print(f"  {item['code']:<28s} {ok:<5s} {r.get('chunks', 'N/A')} chunks")
    print("=" * 60)


if __name__ == "__main__":
    main()
