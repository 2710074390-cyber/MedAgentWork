#!/usr/bin/env python3
"""
MedAgentWork 配置鲁棒性校验脚本
检查所有学科配置的一致性和完整性：
  1. JSON 合法性
  2. regex pattern 可编译性
  3. 参数范围合理性
  4. manifest 与 config 的一致性
  5. 全局注册表完整性

用法:
  python validate_configs.py            # 全面校验
  python validate_configs.py --quick    # 仅 JSON + pattern 校验
  python validate_configs.py --subject internal-med  # 单科校验
"""

import json, re, sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(r"C:\Users\38063\Desktop\MedAgentWork")
KB_DIR = BASE_DIR / "知识库素材"
CONFIG_DIR = KB_DIR / "configs"
GLOBAL_CONFIG = KB_DIR / "subject_config.json"
MANIFEST_PATH = KB_DIR / "index_store" / "index_manifest.json"

# ── 参数合理范围 ──
PARAM_RANGES = {
    "chunk_size": (200, 2000),
    "overlap": (40, 400),
    "min_chunk_size": (30, 500),
    "numeric_threshold": (1, 5),
    "top_k": (5, 50),
    "top_n": (1, 15),
    "score_threshold": (0.50, 0.90),
    "keyword_weight": (0.0, 1.0),
}

errors = []
warnings = []

def err(msg):
    errors.append(msg)
    print(f"  ❌ {msg}")

def warn(msg):
    warnings.append(msg)
    print(f"  ⚠️ {msg}")

def ok(msg):
    print(f"  ✅ {msg}")

# ── 1. 全局注册表校验 ──
print("=" * 60)
print("1. 全局注册表校验")
print("=" * 60)

if not GLOBAL_CONFIG.exists():
    err(f"全局注册表不存在: {GLOBAL_CONFIG}")
else:
    try:
        with open(GLOBAL_CONFIG, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except json.JSONDecodeError as e:
        err(f"全局注册表 JSON 非法: {e}")
        registry = None

    if registry:
        if "schema_version" not in registry:
            err("全局注册表缺少 schema_version")
        subjects = registry.get("subjects", {})
        ok(f"schema_version={registry.get('schema_version', '?')}, {len(subjects)} subjects")

        for code in subjects:
            subj_dir = KB_DIR / code.replace("internal-med", "内科学")  # naive guess
            # Just check the subject entry has required fields
            entry = subjects[code]
            for field in ["name", "priority", "index_status", "config_version"]:
                if field not in entry:
                    err(f"{code}: 缺少字段 '{field}'")

# ── 2. 各学科配置文件校验 ──
print(f"\n{'=' * 60}")
print("2. 各学科配置文件校验")
print("=" * 60)

CONFIG_FILES = sorted(CONFIG_DIR.glob("*_config.json"))
if not CONFIG_FILES:
    err(f"无配置文件在 {CONFIG_DIR}")

for cf in CONFIG_FILES:
    name = cf.name
    try:
        with open(cf, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        err(f"{name}: JSON 非法 — {e}")
        continue
    except Exception as e:
        err(f"{name}: 读取失败 — {e}")
        continue

    # 必须有 chunk_strategy + retrieval_strategy
    cs = cfg.get("chunk_strategy", {})
    rs = cfg.get("retrieval_strategy", {})
    if not cs:
        err(f"{name}: 缺少 chunk_strategy")
    if not rs:
        err(f"{name}: 缺少 retrieval_strategy")

    # 参数范围检查
    for param, (lo, hi) in PARAM_RANGES.items():
        val = cs.get(param) or rs.get(param)
        if val is not None:
            if not (lo <= val <= hi):
                err(f"{name}: {param}={val} 超出合理范围 [{lo}, {hi}]")

    # Pattern 编译检查
    pattern_ok = 0
    pattern_fail = 0
    for rule in cs.get("special_rules", []):
        if rule.get("type") == "pattern_protect" and rule.get("pattern"):
            try:
                re.compile(rule["pattern"], re.IGNORECASE)
                pattern_ok += 1
            except re.error as e:
                err(f"{name}: pattern '{rule['pattern'][:50]}' 编译失败 — {e}")
                pattern_fail += 1

    total_rules = len(cs.get("special_rules", []))
    status = f"chunk={cs.get('chunk_size')} top_n={rs.get('top_n')} rules={pattern_ok}/{total_rules}"
    if pattern_fail > 0:
        err(f"{name}: {status} (pattern FAIL)")
    else:
        ok(f"{name}: {status}")

# ── 3. Manifest 一致性 ──
print(f"\n{'=' * 60}")
print("3. Manifest 与配置一致性")
print("=" * 60)

if not MANIFEST_PATH.exists():
    err(f"Manifest 不存在: {MANIFEST_PATH}")
else:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for code, entry in manifest.items():
        m_config_ver = entry.get("subject_config_version", "unknown")
        m_chunk_size = entry.get("chunk_size", "?")
        m_chunk_count = entry.get("chunk_count", "?")

        # Resolve config path using the same logic as search_kb/embed_index
        AUX_MAP = {
            "heyincheng-jy1": "heyincheng-lecture_config.json",
            "heyincheng-jy2": "heyincheng-lecture_config.json",
            "heyincheng-jy3": "heyincheng-lecture_config.json",
            "heyincheng-zt1": "heyincheng-zhenti_config.json",
            "heyincheng-zt2": "heyincheng-zhenti_config.json",
            "zhaozhao-part1": "zhaozhao-tiyan_config.json",
            "zhaozhao-part2": "zhaozhao-tiyan_config.json",
        }
        cfg = None
        if code in AUX_MAP:
            cfg_path = CONFIG_DIR / AUX_MAP[code]
        else:
            cfg_path = CONFIG_DIR / f"{code}_config.json"

        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                pass

        if cfg:
            cfg_ver = cfg.get("version", "?")
            cfg_chunk = cfg.get("chunk_strategy", {}).get("chunk_size", "?")
            if str(m_chunk_size) != str(cfg_chunk):
                warn(f"{code}: manifest chunk={m_chunk_size} ≠ config chunk={cfg_chunk} — 可能需重新索引")
            elif m_config_ver != cfg_ver:
                warn(f"{code}: manifest config_ver={m_config_ver} ≠ config ver={cfg_ver}")
            else:
                ok(f"{code}: {m_chunk_count} chunks, chunk={m_chunk_size}, ver={m_config_ver} ✓")
        elif m_config_ver == "default":
            ok(f"{code}: {m_chunk_count} chunks, chunk={m_chunk_size} (default — no custom config)")
        else:
            warn(f"{code}: manifest references config but none found")

# ── 4. 索引文件完整性 ──
print(f"\n{'=' * 60}")
print("4. 索引文件完整性")
print("=" * 60)

for code, entry in manifest.items():
    vec_file = KB_DIR / "index_store" / code / "embeddings.npy"
    meta_file = KB_DIR / "chunks_metadata" / f"{code}_chunks.jsonl"

    vec_ok = vec_file.exists()
    meta_ok = meta_file.exists()

    if not vec_ok:
        err(f"{code}: embeddings.npy 缺失")
    if not meta_ok:
        err(f"{code}: chunks.jsonl 缺失")
    if vec_ok and meta_ok:
        ok(f"{code}: embeddings+chunks 完整")

# ── 5. RAG 检索端配置加载测试 ──
print(f"\n{'=' * 60}")
print("5. 检索端配置加载测试")
print("=" * 60)

# Simulate search_kb.py config loading (import-free to avoid deps)
AUX_CONFIG_MAP_SEARCH = {
    "heyincheng-jy1": "heyincheng-lecture_config.json",
    "heyincheng-jy2": "heyincheng-lecture_config.json",
    "heyincheng-jy3": "heyincheng-lecture_config.json",
    "heyincheng-zt1": "heyincheng-zhenti_config.json",
    "heyincheng-zt2": "heyincheng-zhenti_config.json",
    "zhaozhao-part1": "zhaozhao-tiyan_config.json",
    "zhaozhao-part2": "zhaozhao-tiyan_config.json",
}

def get_config_path_search(code):
    if code in AUX_CONFIG_MAP_SEARCH:
        return CONFIG_DIR / AUX_CONFIG_MAP_SEARCH[code]
    p = CONFIG_DIR / f"{code}_config.json"
    return p if p.exists() else None

test_codes = ["internal-med", "surgery", "pediatrics", "neurology",
              "psychiatry", "dermatology", "tcm", "doctor-patient",
              "heyincheng-jy1", "heyincheng-zt1", "zhaozhao-part1", "nonexistent"]

for code in test_codes:
    path = get_config_path_search(code)
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            rs = cfg.get("retrieval_strategy", {})
            ok(f"{code:20s} → top_n={rs.get('top_n')} hybrid={rs.get('hybrid_search')} kw={rs.get('keyword_weight')}")
        except Exception as e:
            err(f"{code}: 加载失败 — {e}")
    else:
        if code == "nonexistent":
            ok(f"{code:20s} → None (正确地回退默认值)")
        else:
            err(f"{code}: 配置文件未找到")

# ── 总结 ──
print(f"\n{'=' * 60}")
print("校验总结")
print("=" * 60)
print(f"  错误: {len(errors)}")
print(f"  警告: {len(warnings)}")

if errors:
    print("\n❌ 存在 {len(errors)} 个错误，需要修复后继续。")
    sys.exit(1)
elif warnings:
    print(f"\n⚠️ 存在 {len(warnings)} 个警告，可继续但建议检查。")
    sys.exit(0)
else:
    print("\n✅ 全部校验通过。RAG 配置未发现问题。")
    sys.exit(0)
