#!/usr/bin/env python3
"""
一次性重新索引所有教材科目，使用新版 embed_index.py（自动提取印刷页码）。
耗时约 10-15 分钟，需要 SILICONFLOW_API_KEY。
"""
import os, sys, json, time, traceback
from pathlib import Path

BASE = Path(r"C:\Users\38063\Desktop\MedAgentWork")
sys.path.insert(0, str(BASE / "知识库素材"))

from embed_index import (
    get_api_key, find_pdfs, detect_subject,
    process_pdf, embed_and_store, update_manifest,
    INDEX_STORE, META_DIR, TZ
)

# 需要重新索引的教材科目
TEXTBOOK_CODES = {
    "tcm", "neurology", "internal-med", "pediatrics", "surgery",
    "dermatology", "psychiatry", "doctor-patient",
}

def main():
    api_key = get_api_key()

    pdf_files = find_pdfs()
    manifest_path = INDEX_STORE / "index_manifest.json"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 筛选需要重新索引的科目
    to_reindex = []
    for pdf_path in pdf_files:
        subject, code, priority = detect_subject(pdf_path)
        if code in TEXTBOOK_CODES:
            to_reindex.append((pdf_path, subject, code, priority))
            # 标记为待重新索引
            if code in manifest:
                manifest[code]["status"] = "reindexing"

    if not to_reindex:
        print("所有教材科目已索引完毕。")
        return

    # 按 chunk 数排序（小科目优先，快速验证）
    def chunk_count(item):
        code = item[2]
        return manifest.get(code, {}).get("chunk_count", 9999)
    to_reindex.sort(key=chunk_count)

    print("=" * 60)
    print(f"重新索引 {len(to_reindex)} 个科目（启用教材印刷页码）")
    print("=" * 60)
    for _, subject, code, _ in to_reindex:
        chunks = manifest.get(code, {}).get("chunk_count", "?")
        print(f"  {code:<18s} {subject} ({chunks} chunks)")

    print()

    for pdf_path, subject, code, _ in to_reindex:
        print(f"\n{'='*60}")
        print(f"[REINDEX] {subject} ({code})")
        print(f"{'='*60}")

        try:
            chunks = process_pdf(pdf_path, subject, code)
            if not chunks:
                print(f"  [WARN] No chunks extracted")
                continue

            # Check how many pages got printed page numbers
            printed = sum(1 for c in chunks if c["meta"]["page_number"] != c["meta"]["pdf_page_number"])
            total_pages = len(set(c["meta"]["pdf_page_number"] for c in chunks))
            print(f"  Printed pages resolved: {printed}/{len(chunks)} chunks")

            embed_and_store(chunks, code, api_key)
            update_manifest(code, subject, len(chunks), pdf_path)

            # Mark as reindexed
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest[code]["page_number_source"] = "printed_textbook"
            manifest[code]["printed_pages_available"] = True
            manifest[code]["reindexed_at"] = manifest[code].get("indexed_at", "")
            manifest[code].pop("page_number_fix", None)
            manifest[code].pop("estimated_offset", None)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            print(f"  [OK] {subject} re-indexed with printed textbook page numbers")

        except Exception as e:
            print(f"\n[FAIL] {subject}: {e}")
            traceback.print_exc()
            continue

    print("\n" + "=" * 60)
    print("[DONE] All textbook subjects re-indexed")
    print("=" * 60)

    # Final manifest check
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    for code in TEXTBOOK_CODES:
        if code in manifest:
            m = manifest[code]
            print(f"  {code}: source={m.get('page_number_source','?')} status={m['status']}")

if __name__ == "__main__":
    main()
