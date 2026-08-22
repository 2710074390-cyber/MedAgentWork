#!/usr/bin/env python3
"""
索引人卫习题集 PDF（学习指导与习题集）—— 独立于教材正文的索引空间。

内科学第3版、外科学第4版、精神病学第5版，每科独立 subject_code + config。
索引后注册到 manifest，可在 search_kb.py 中按科目检索。

耗时：~5-8分钟/科（取决于 PDF 大小），需要 SILICONFLOW_API_KEY。
用法：python scripts/index_exercise_pdfs.py
"""

import os
import sys
import json
import time
import traceback
from pathlib import Path

# 将 embed_index.py 所在目录加入 path
BASE = Path(r"C:\Users\38063\Desktop\MedAgentWork")
sys.path.insert(0, str(BASE / "知识库素材"))

from embed_index import (
    get_api_key, process_pdf, embed_and_store, update_manifest,
    INDEX_STORE, META_DIR, TZ
)

# ─── 习题集映射：PDF文件名 → (学科名, subject_code) ───

EXERCISE_PDFS = [
    {
        "filename": "01. 内科学学习指导与习题集 第3版.pdf",
        "folder": "内科学",
        "subject": "内科学（习题集）",
        "code": "internal-med-exercise",
        "config": "internal-med-exercise_config.json",
    },
    {
        "filename": "02. 外科学学习指导与习题集 第4版.pdf",
        "folder": "外科学",
        "subject": "外科学（习题集）",
        "code": "surgery-exercise",
        "config": "surgery-exercise_config.json",
    },
    {
        "filename": "11. 精神病学学习指导与习题集 第5版.pdf",
        "folder": "精神病学",
        "subject": "精神病学（习题集）",
        "code": "psychiatry-exercise",
        "config": "psychiatry-exercise_config.json",
    },
]

KB_DIR = BASE / "知识库素材"
CONFIG_DIR = KB_DIR / "configs"


def load_exercise_config(config_filename):
    """加载习题集个性化配置"""
    config_path = CONFIG_DIR / config_filename
    if not config_path.exists():
        print(f"  [WARN] Config not found: {config_path}, using defaults")
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    api_key = get_api_key()

    print("=" * 60)
    print("人卫习题集索引流水线")
    print(f"待索引：{len(EXERCISE_PDFS)} 科")
    print("=" * 60)

    # 显示各科信息
    for item in EXERCISE_PDFS:
        pdf_path = KB_DIR / item["folder"] / item["filename"]
        exists = "✓" if pdf_path.exists() else "✗ 未找到"
        print(f"  {item['code']:<28s} {item['filename'][:40]:<42s} {exists}")

    if not all((KB_DIR / item["folder"] / item["filename"]).exists() for item in EXERCISE_PDFS):
        print("\n[ERROR] 部分 PDF 文件不存在，请检查路径。")
        return

    print()

    # 逐科索引
    results = {}
    for item in EXERCISE_PDFS:
        pdf_path = KB_DIR / item["folder"] / item["filename"]

        print(f"\n{'='*60}")
        print(f"[INDEX] {item['subject']} ({item['code']})")
        print(f"  Source: {item['folder']}/{item['filename']}")
        print(f"{'='*60}")

        try:
            # 加载个性化配置
            config = load_exercise_config(item["config"])
            if config:
                cs = config.get("chunk_strategy", {})
                rs = config.get("retrieval_strategy", {})
                print(f"  [CONFIG] v{config.get('version','?')} "
                      f"chunk={cs.get('chunk_size','?')} "
                      f"overlap={cs.get('overlap','?')} "
                      f"top_k={rs.get('top_k','?')} "
                      f"hybrid={rs.get('hybrid_search','?')} "
                      f"kw_weight={rs.get('keyword_weight','?')}")
            else:
                print(f"  [CONFIG] 使用默认参数（chunk=800, overlap=150）")

            # 处理 PDF → chunks
            chunks = process_pdf(pdf_path, item["subject"], item["code"], config)

            if not chunks:
                print(f"  [WARN] No chunks extracted from {item['filename']}")
                results[item["code"]] = {"status": "empty", "chunks": 0}
                continue

            # 统计印刷页码解析
            printed = sum(1 for c in chunks if c["meta"]["page_number"] != c["meta"]["pdf_page_number"])
            total_pages = len(set(c["meta"]["pdf_page_number"] for c in chunks))
            print(f"  Pages: {total_pages} (印刷页码解析: {printed}/{len(chunks)} chunks)")

            # 标记 Q&A 相关元数据
            q_count = 0
            ans_count = 0
            for c in chunks:
                text = c["text"]
                if not c["meta"].get("has_question"):
                    if any(kw in text for kw in ["A1型题", "A2型题", "B1型题", "X型题", "题干", "单选题", "多选题"]):
                        c["meta"]["has_question"] = True
                        q_count += 1
                if not c["meta"].get("has_kaodian"):
                    if any(kw in text for kw in ["参考答案", "解析", "★", "考点", "解题思路"]):
                        c["meta"]["has_kaodian"] = True
                        ans_count += 1

            print(f"  Chunks: {len(chunks)} (含题目: {q_count}, 含答案/解析: {ans_count})")

            # 嵌入 + 存储
            embed_and_store(chunks, item["code"], api_key)

            # 更新 manifest
            update_manifest(item["code"], item["subject"], len(chunks), pdf_path, config)

            # 标记习题集来源
            manifest_path = INDEX_STORE / "index_manifest.json"
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            if item["code"] in manifest:
                manifest[item["code"]]["source_type"] = "exercise_collection"
                manifest[item["code"]]["publisher"] = "人民卫生出版社"
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

    # ─── 最终汇总 ───
    print("\n" + "=" * 60)
    print("[SUMMARY] 人卫习题集索引结果")
    print("=" * 60)
    for item in EXERCISE_PDFS:
        r = results.get(item["code"], {"status": "unknown"})
        status_icon = "✓" if r["status"] == "ok" else "✗"
        print(f"  {status_icon} {item['code']:<28s} {r['status']:<6s} {r.get('chunks', 'N/A')} chunks")
    print("=" * 60)

    # 输出注册信息供 Agent 2/3/5 使用
    register_path = BASE / "中间产物" / "exercise_index_registry.json"
    register_path.parent.mkdir(parents=True, exist_ok=True)
    with open(register_path, "w", encoding="utf-8") as f:
        json.dump({
            "indexed_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "subjects": [
                {
                    "code": item["code"],
                    "subject": item["subject"],
                    "linked_textbook": item["code"].replace("-exercise", ""),
                    "status": results.get(item["code"], {}).get("status", "unknown"),
                    "chunks": results.get(item["code"], {}).get("chunks", 0),
                }
                for item in EXERCISE_PDFS
            ]
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[REGISTRY] {register_path}")


if __name__ == "__main__":
    main()
