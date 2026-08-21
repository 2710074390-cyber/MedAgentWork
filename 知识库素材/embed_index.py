#!/usr/bin/env python3
"""
MedAgentWork 知识库索引流水线
读取知识库素材/ 中的 PDF 教材 -> 分块 -> 嵌入 -> 存储元数据

依赖: pip install PyMuPDF requests numpy
嵌入: 硅基流动 API (BAAI/bge-m3)
"""

import os
import re
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

import fitz  # PyMuPDF
import requests

# Windows GBK console workaround
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ─── 配置 ───────────────────────────────────────────
API_BASE = "https://api.siliconflow.cn/v1"
EMBED_MODEL = "BAAI/bge-m3"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
BATCH_SIZE = 32
MAX_RETRIES = 3
CHUNK_SIZE_CHARS = 800
CHUNK_OVERLAP = 150
MIN_CHUNK_SIZE = 100
TZ = timezone(timedelta(hours=8))

BASE_DIR = Path(r"C:\Users\38063\Desktop\MedAgentWork")
KB_DIR = BASE_DIR / "知识库素材"
INDEX_STORE = KB_DIR / "index_store"
META_DIR = KB_DIR / "chunks_metadata"
CONFIG_DIR = KB_DIR / "configs"
GLOBAL_CONFIG = KB_DIR / "subject_config.json"

# ─── 学科配置加载 ─────────────────────────────────────

Auxiliary_CONFIG_MAP = {
    "heyincheng-jy1": "heyincheng-lecture_config.json",
    "heyincheng-jy2": "heyincheng-lecture_config.json",
    "heyincheng-jy3": "heyincheng-lecture_config.json",
    "heyincheng-zt1": "heyincheng-zhenti_config.json",
    "heyincheng-zt2": "heyincheng-zhenti_config.json",
    "zhaozhao-part1": "zhaozhao-tiyan_config.json",
    "zhaozhao-part2": "zhaozhao-tiyan_config.json",
}

def get_config_path(subject_code):
    """Resolve config file path for a subject code.
    Core subjects: configs/{code}_config.json
    Auxiliary: shared config per mapped group
    """
    if subject_code in Auxiliary_CONFIG_MAP:
        return CONFIG_DIR / Auxiliary_CONFIG_MAP[subject_code]
    config_file = CONFIG_DIR / f"{subject_code}_config.json"
    if config_file.exists():
        return config_file
    return None

def load_subject_config(subject_code):
    """Load per-subject chunk/retrieval config. Returns dict or None on any failure."""
    path = get_config_path(subject_code)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if "chunk_strategy" not in cfg and "retrieval_strategy" not in cfg:
            print(f"  [WARN] Config {path.name} missing required sections, using defaults")
            return None
        return cfg
    except json.JSONDecodeError as e:
        print(f"  [WARN] Config {path.name} JSON invalid: {e}, using defaults")
        return None
    except Exception as e:
        print(f"  [WARN] Config {path.name} load failed: {e}, using defaults")
        return None

# 科目代码映射 (subject name -> code + priority)
SUBJECT_MAP = {
    "内科学":   {"code": "internal-med", "priority": 0},
    "儿科学":   {"code": "pediatrics",    "priority": 0},
    "外科学":   {"code": "surgery",       "priority": 1},
    "神经病学": {"code": "neurology",     "priority": 1},
    "精神病学": {"code": "psychiatry",    "priority": 2},
    "皮肤性病学": {"code": "dermatology", "priority": 2},
    "中医学":   {"code": "tcm",           "priority": 2},
    "中医心理学": {"code": "tcm-psychology", "priority": 2},
    "认知神经科学": {"code": "cognitive-neuroscience", "priority": 2},
    "医患沟通": {"code": "doctor-patient","priority": 2},
}

# ─── 工具函数 ───────────────────────────────────────

def get_api_key():
    key = os.environ.get("SILICONFLOW_API_KEY")
    if not key:
        raise RuntimeError("未设置 SILICONFLOW_API_KEY 环境变量")
    return key


def api_request(endpoint, payload, api_key):
    url = f"{API_BASE}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt
            print(f"  [!] API request retry {attempt+1}/{MAX_RETRIES}, wait {wait}s: {e}")
            time.sleep(wait)


def batch_embed(texts, api_key):
    result = api_request("embeddings", {
        "model": EMBED_MODEL,
        "input": texts,
        "encoding_format": "float"
    }, api_key)
    return [item["embedding"] for item in result["data"]]


def detect_subject(filepath):
    name = filepath.stem
    for subject, info in SUBJECT_MAP.items():
        if subject in name:
            return subject, info["code"], info["priority"]
    return name, "unknown", 99


def detect_chapter_section(text):
    chapter = ""
    section = ""
    ch_num = 0
    ch_m = re.search(r'第[一二三四五六七八九十百\d]+章\s*[^\n]{0,30}', text)
    if ch_m:
        chapter = ch_m.group().strip()
        num_m = re.search(r'[\d]+', chapter)
        if num_m:
            ch_num = int(num_m.group())
    sec_m = re.search(r'第[一二三四五六七八九十\d]+节\s*[^\n]{0,30}', text)
    if sec_m:
        section = sec_m.group().strip()
    return chapter, ch_num, section


def extract_printed_pagenum(text):
    """
    从 PDF 页面的文本内容中提取教材印刷页码。
    教材页码通常出现在页面顶部的运行标题中，有以下几种模式：
    1. '本章数字资源 38' → 38（章首页）
    2. '第一章 导论 19' → 19（中/西医药教材常见格式）
    3. '12 上篇' → 12（中医药教材常见格式）
    4. '第二章 神经系统的解剖... 9' → 9（西医教材常见格式）
    5. 纯数字开头行 '29'（某些教材页眉独立成行）

    返回印刷页码（int），如果无法提取返回 None。
    """
    text_stripped = text.strip()

    # 模式1: 本章数字资源...数字（章首页，数字即教材页码）
    # 例："本章数字资源 本章思维导图 3 第二章 神经系统的解剖..."
    m = re.search(r'本章数字资源[^。]*?(\d+)', text_stripped[:200])
    if m:
        return int(m.group(1))

    # 模式2: 第X章 + 名称 + 空格 + 数字（正文页标准格式）
    # 例："第一章 导论 11" 或 "第二章 神经系统的解剖 9"
    m = re.search(r'第[一二三四五六七八九十百\d]+章\s+\S+\s+(\d+)', text_stripped[:200])
    if m:
        return int(m.group(1))

    # 模式3: 数字 + 上篇/下篇（中医药教材）
    m = re.search(r'^\s*(\d+)\s+上[篇编]', text_stripped[:100])
    if m:
        return int(m.group(1))

    # 模式4: 独立数字（某些教材页码单独成行在页眉）
    lines = text_stripped.split('\n')
    for line in lines[:3]:
        line = line.strip()
        m = re.match(r'^(\d+)$', line)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 1000:
                return n

    # 模式5: 数字 + 表名/图名（如 "38 表1-3"）
    m = re.search(r'^\s*(\d+)\s+表\s*\d+', text_stripped[:100])
    if m:
        return int(m.group(1))

    # 模式6: 页面顶部 "数字 空格 非数字" 如 "29 "开头的正文页
    m = re.search(r'^\s*(\d{1,3})\s+[^\d\s]', text_stripped[:80])
    if m:
        n = int(m.group(1))
        if 1 <= n <= 600:
            return n

    return None


def count_numeric_values(text):
    patterns = [
        r'\d+[~\-]\d+',
        r'\d+\.?\d*\s*[%％]',
        r'\d+\.?\d*\s*(?:mg|g|ml|L|μg|ng|U|IU|mm|cm|次|天|周|月|年|岁|分|小时|日)',
        r'\d+\.?\d*\s*(?:mmol|μmol|mmol/L|mg/dl|mmHg|kPa)',
        r'[><≥≤]\s*\d+',
    ]
    count = 0
    for p in patterns:
        count += len(re.findall(p, text))
    return count


def has_table_marker(text):
    return bool(re.search(r'表\s*\d+|Table\s*\d+', text))


# ─── 分块逻辑 ────────────────────────────────────────

def split_sentences(text):
    parts = re.split(r'(?<=[。；\n])', text)
    return [p for p in parts if p.strip()]


def chunk_text(text, chunk_size=CHUNK_SIZE_CHARS, overlap=CHUNK_OVERLAP,
               min_chunk_size=MIN_CHUNK_SIZE, numeric_threshold=3,
               protect_patterns=None):
    """
    Split text into chunks with config-driven protection rules.
    protect_patterns: list of compiled regex patterns — matching sentences won't be split.
    """
    sentences = split_sentences(text)
    chunks = []
    current = ""

    if protect_patterns is None:
        protect_patterns = []

    def _is_protected(sent):
        """Check if sentence matches any protection pattern."""
        if count_numeric_values(sent) >= numeric_threshold:
            return True
        if has_table_marker(sent):
            return True
        for pat in protect_patterns:
            if pat.search(sent):
                return True
        return False

    for sent in sentences:
        # 保护段落不拆分（数值密集 / 表格 / 模式匹配）
        if _is_protected(sent):
            if current:
                if len(current) >= min_chunk_size:
                    chunks.append(current.strip())
                elif chunks:
                    chunks[-1] = chunks[-1] + " " + current.strip()
                else:
                    chunks.append(current.strip())
            chunks.append(sent.strip())
            current = ""
            continue

        if len(current) + len(sent) > chunk_size:
            if len(current) >= min_chunk_size:
                chunks.append(current.strip())
                overlap_text = current[-overlap:] if len(current) > overlap else current
                current = overlap_text + sent
            else:
                current += sent
        else:
            current += sent

    if current and len(current) >= min_chunk_size:
        chunks.append(current.strip())
    elif current and chunks:
        chunks[-1] = chunks[-1] + " " + current.strip()

    return chunks


# ─── PDF 处理 ────────────────────────────────────────

def extract_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if text.strip():
            pages.append({"page_num": i + 1, "text": text})
    doc.close()
    return pages


def process_pdf(pdf_path, subject, subject_code, config=None):
    """Process a PDF into chunks. If config dict is provided, use subject-specific params."""
    print(f"\n[PDF] Processing: {pdf_path.name}")

    # 从配置提取分块参数
    cs = config.get("chunk_strategy", {}) if config else {}
    chunk_size = cs.get("chunk_size", CHUNK_SIZE_CHARS)
    overlap = cs.get("overlap", CHUNK_OVERLAP)
    min_chunk_size = cs.get("min_chunk_size", MIN_CHUNK_SIZE)
    numeric_threshold = cs.get("numeric_threshold", 3)
    enrich_fields = cs.get("metadata_enrichment", [])

    # 编译 pattern_protect 规则
    protect_patterns = []
    for rule in cs.get("special_rules", []):
        if rule.get("type") == "pattern_protect" and rule.get("pattern"):
            try:
                protect_patterns.append(re.compile(rule["pattern"], re.IGNORECASE))
            except re.error as e:
                print(f"  [WARN] Invalid pattern '{rule['pattern']}': {e}")

    if config:
        print(f"  [CONFIG] chunk={chunk_size} overlap={overlap} min={min_chunk_size} "
              f"num_th={numeric_threshold} enrich={enrich_fields} protect_rules={len(protect_patterns)}")

    pages = extract_pdf(pdf_path)
    print(f"  Pages with text: {len(pages)}")

    all_chunks = []
    for page in pages:
        text = page["text"]
        chapter, ch_num, section = detect_chapter_section(text)
        text_chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap,
                                 min_chunk_size=min_chunk_size,
                                 numeric_threshold=numeric_threshold,
                                 protect_patterns=protect_patterns)

        # 提取教材印刷页码（替代 PDF 阅读器页码）
        printed_pn = extract_printed_pagenum(text)
        page_number = printed_pn if printed_pn is not None else page["page_num"]

        for ci, chunk in enumerate(text_chunks):
            meta = {
                "chunk_id": "",
                "subject": subject,
                "subject_code": subject_code,
                "chapter": chapter or "",
                "chapter_num": ch_num,
                "section": section or "",
                "page_number": page_number,
                "pdf_page_number": page["page_num"],
                "has_table": has_table_marker(chunk),
                "has_numeric_data": count_numeric_values(chunk) > 0,
                "textbook": f"{subject}(v10)" if "10" in str(pdf_path) else subject,
                "char_count": len(chunk),
                "chunk_index": ci,
                "indexed_at": datetime.now(TZ).isoformat(),
            }
            # 学科个性化元数据标注
            if "has_scale" in enrich_fields:
                meta["has_scale"] = bool(re.search(r'(评分|量表|scale|score)', chunk, re.I))
            if "has_diagnostic_criteria" in enrich_fields:
                meta["has_diagnostic_criteria"] = bool(re.search(r'(诊断标准|诊断条目|符合.*条|诊断依据)', chunk))
            if "has_procedure" in enrich_fields:
                meta["has_procedure"] = bool(re.search(r'(手术|术式|切口|入路|切除|吻合|重建|修补)', chunk))
            if "has_staging" in enrich_fields:
                meta["has_staging"] = bool(re.search(r'(分期|分型|TNM|Garden|Neer)', chunk))
            if "has_milestone" in enrich_fields:
                meta["has_milestone"] = bool(re.search(r'(发育|里程碑|抬头|独坐|站立|行走|语言)', chunk))
            if "has_formula" in enrich_fields:
                meta["has_formula"] = bool(re.search(r'(方剂|方名|组成|功用|主治|配伍|汤|散|丸|丹)', chunk))
            if "has_acupoint" in enrich_fields:
                meta["has_acupoint"] = bool(re.search(r'(腧穴|穴位|定位|归经|刺灸法|进针|得气|灸法|经穴)', chunk))
            if "has_syndrome" in enrich_fields:
                meta["has_syndrome"] = bool(re.search(r'(综合征|syndrome)', chunk, re.I))
            if "has_anatomy_pathway" in enrich_fields:
                meta["has_anatomy_pathway"] = bool(re.search(r'(传导通路|神经通路|纤维联系|投射|交叉)', chunk))
            if "has_morphology" in enrich_fields:
                meta["has_morphology"] = bool(re.search(r'(斑疹|丘疹|斑块|结节|风团|水疱|大疱|糜烂|溃疡|鳞屑)', chunk))
            if "has_law" in enrich_fields:
                meta["has_law"] = bool(re.search(r'(第.{1,10}条|法律责任|应当|应当|处罚|民法|刑法)', chunk))
            if "has_model" in enrich_fields:
                meta["has_model"] = bool(re.search(r'(模型|model|SPIKES|Kalamazoo|Calgary)', chunk, re.I))
            if "has_drug_info" in enrich_fields:
                meta["has_drug_info"] = bool(re.search(r'(用药|剂量|mg|μg|口服|静脉|肌注|皮下|po|iv|im)', chunk))
            if "has_kaodian" in enrich_fields:
                meta["has_kaodian"] = bool(re.search(r'(考点|重点|真题|常考|必考)', chunk))
            if "has_question" in enrich_fields:
                meta["has_question"] = bool(re.search(r'(题干|选项|答案|解析|A型|B型|X型)', chunk))
            if "has_mnemonic" in enrich_fields:
                meta["has_mnemonic"] = bool(re.search(r'(口诀|记忆|速记|顺口溜|歌诀)', chunk))
            if "has_age_specific" in enrich_fields:
                meta["has_age_specific"] = bool(re.search(r'(新生儿|婴儿|幼儿|学龄前|学龄期|青春期|月龄|年龄)', chunk))

            all_chunks.append({"meta": meta, "text": chunk})

    # 更新 chunk_id（使用教材印刷页码）
    for item in all_chunks:
        m = item["meta"]
        ch = f"ch{m['chapter_num']:02d}" if m['chapter_num'] else "chxx"
        m["chunk_id"] = f"{subject_code}_{ch}_p{m['page_number']:04d}_c{m['chunk_index']:04d}"

    print(f"  Chunks: {len(all_chunks)}")
    return all_chunks


# ─── 嵌入与存储 ───────────────────────────────────────

def embed_and_store(chunks, subject_code, api_key):
    """嵌入并存储。返回 (embeddings, failed_batches)。

    v1.1 (2026-08-20 审查修复 C4): 此前批次嵌入失败被静默丢弃且 manifest 仍标
    indexed —— 部分索引被当完整索引服务（欠费/抖动后 KB 静默残缺）。
    现在：失败批次计数并告警；全部失败则抛错不写盘；meta/npy 原子写。
    """
    print(f"\n[EMBED] Starting ({subject_code})...")

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
            continue

        progress = min(i+BATCH_SIZE, total)
        print(f"  Progress: {progress}/{total}")
        if i + BATCH_SIZE < total:
            time.sleep(0.15)

    if failed_batches:
        print(f"  ⚠️ {failed_batches}/{max(1, (total+BATCH_SIZE-1)//BATCH_SIZE)} 个批次嵌入失败"
              f" → 生成的是 partial 索引（{len(embeddings)}/{total} chunks），"
              f"manifest 将标注 status=partial，检索端会告警")
    if not embeddings:
        raise RuntimeError(f"{subject_code}: 全部批次嵌入失败，未写入任何数据（索引保持原状）")

    # 原子写 JSONL（v1.1: tmp + os.replace，避免半写损坏）
    tmp_meta = meta_file.with_name(meta_file.name + '.tmp')
    with open(tmp_meta, "w", encoding="utf-8") as f:
        for item in embeddings:
            meta = item["meta"].copy()
            meta["text"] = item["text"]
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
    os.replace(tmp_meta, meta_file)

    # 向量存为 numpy（原子写）
    import numpy as np
    vecs_array = np.array([item["embedding"] for item in embeddings], dtype=np.float32)
    vec_file = INDEX_STORE / subject_code / "embeddings.npy"
    vec_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_vec = vec_file.with_name(vec_file.name + '.tmp')
    np.save(tmp_vec, vecs_array)
    os.replace(tmp_vec, vec_file)

    print(f"  [OK] Stored: {len(embeddings)} items")
    print(f"       Metadata: {meta_file}")
    print(f"       Vectors:   {vec_file}")
    return embeddings, failed_batches


# ─── 索引清单 ────────────────────────────────────────

def update_manifest(subject_code, subject, chunk_count, pdf_path, config=None, status="indexed"):
    INDEX_STORE.mkdir(parents=True, exist_ok=True)
    manifest_path = INDEX_STORE / "index_manifest.json"

    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    entry = {
        "subject": subject,
        # v1.1 (2026-08-20 审查修复 C4): status 支持 'indexed' / 'partial'
        # （部分批次嵌入失败时由调用方传入 'partial'，检索端据此告警）
        "status": status,
        "chunk_count": chunk_count,
        "source_file": pdf_path.name,
        "model": EMBED_MODEL,
        "rerank_model": RERANK_MODEL,
        "chunk_size": config["chunk_strategy"]["chunk_size"] if config else CHUNK_SIZE_CHARS,
        "overlap": config["chunk_strategy"]["overlap"] if config else CHUNK_OVERLAP,
        "indexed_at": datetime.now(TZ).isoformat(),
    }

    # 标注是否使用了个性化配置
    if config:
        entry["subject_config_version"] = config.get("version", "1.0")
        entry["config_source"] = str(get_config_path(subject_code))
        # 保存配置快照到索引目录
        config_snapshot_dir = INDEX_STORE / subject_code
        config_snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = config_snapshot_dir / "index_config.json"
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    else:
        entry["subject_config_version"] = "default"
        entry["config_source"] = "default (no subject_config.json)"

    manifest[subject_code] = entry

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n[MANIFEST] Updated: {manifest_path}")


# ─── CLI ────────────────────────────────────────────

def find_pdfs():
    """查找子目录中的PDF教材（仅科目子目录内，排除根目录非教材文件）"""
    pdfs = []
    for entry in KB_DIR.iterdir():
        if entry.is_dir():
            for pdf in entry.glob("*.pdf"):
                pdfs.append(pdf)
    return pdfs


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MedAgentWork Knowledge Base Index Pipeline")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Force re-index even for already indexed subjects")
    parser.add_argument("--subject", "-s", type=str,
                        help="Only index specified subject code (e.g. internal-med)")
    args = parser.parse_args()

    api_key = get_api_key()

    pdf_files = find_pdfs()

    if not pdf_files:
        print("[ERROR] No PDFs found in subject subdirectories")
        return

    # 按优先级排序
    def sort_key(f):
        _, _, pri = detect_subject(f)
        return pri

    pdf_files.sort(key=sort_key)

    print("=" * 60)
    print("MedAgentWork Knowledge Base Index Pipeline")
    print(f"Embed model: {EMBED_MODEL}")
    print(f"Chunk size: {CHUNK_SIZE_CHARS} chars (default) / overlap: {CHUNK_OVERLAP} chars")
    print(f"Pending: {len(pdf_files)} files | Force: {args.force} | Filter: {args.subject or 'all'}")
    print("=" * 60)

    # 加载已有清单
    manifest_path = INDEX_STORE / "index_manifest.json"
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    for pdf_path in pdf_files:
        subject, code, priority = detect_subject(pdf_path)

        # 科目过滤
        if args.subject and args.subject != code:
            continue

        if not args.force and code in manifest and manifest[code].get("status") == "indexed":
            print(f"\n[SKIP] {subject} (already indexed, use --force to re-index)")
            continue

        if args.force and code in manifest:
            print(f"\n[RE-INDEX] {subject} (forced)")

        try:
            # 加载学科个性化配置
            subj_config = load_subject_config(code)
            if subj_config:
                print(f"[CONFIG] Loaded {code}: v{subj_config.get('version', '?')}")
            else:
                print(f"[CONFIG] No custom config for {code}, using defaults")

            chunks = process_pdf(pdf_path, subject, code, subj_config)
            if not chunks:
                print(f"  [WARN] No chunks extracted")
                continue
            embeddings, failed_batches = embed_and_store(chunks, code, api_key)
            # v1.1 (2026-08-20 审查修复 C4): chunk_count 用实际入库数（此前用处理前
            # 总数，部分失败时 manifest 虚报）；status 标注 partial
            status = 'partial' if failed_batches else 'indexed'
            update_manifest(code, subject, len(embeddings), pdf_path, subj_config, status=status)
        except Exception as e:
            import traceback
            print(f"\n[FAIL] {subject}: {e}")
            traceback.print_exc()
            continue

    print("\n" + "=" * 60)
    print("[DONE] Index pipeline complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
