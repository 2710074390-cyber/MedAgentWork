#!/usr/bin/env python3
"""
CMB 数据下载与导入器 v1.0
========================
从 HuggingFace FreedomIntelligence/CMB 下载 CMB-val (280题) 和 CMB-Clin (74例)，
转换为 GoldenSet 统一 Schema。

CMB-val: 280 题，带 solution & explanation
CMB-Clin: 74 例复杂临床推理病例

输出：
  - GoldenSet/Layer1_扩展层/CMB_val_280.json
  - GoldenSet/Layer2_临床推理/CMB_clin_74.json
"""

import json, sys, io, os
from pathlib import Path
from datetime import datetime

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE = Path(r"C:\Users\38063\Desktop\MedAgentWork\GoldenSet")

# ── 方式一：HuggingFace datasets 库 ─────────────────────
def load_from_huggingface():
    """通过 HF datasets 库加载（推荐，结构最完整）"""
    try:
        from datasets import load_dataset
        print("[INFO] 正在从 HuggingFace 加载 CMB-Exam (val split)...")
        exam_val = load_dataset("FreedomIntelligence/CMB", "exam", split="validation")
        print(f"[INFO] 加载完成: {len(exam_val)} 条 CMB-val 记录")

        print("[INFO] 正在加载 CMB-Clin...")
        clin = load_dataset("FreedomIntelligence/CMB", "clin", split="train")
        print(f"[INFO] 加载完成: {len(clin)} 条 CMB-Clin 记录")

        return exam_val, clin
    except Exception as e:
        print(f"[WARN] HuggingFace 加载失败: {e}")
        return None, None


# ── 方式二：GitHub 镜像下载 ──────────────────────────────
def load_from_github_mirror():
    """通过 GitHub 镜像下载 ZIP 文件"""
    import urllib.request
    import zipfile

    mirror_urls = [
        "https://mirror.ghproxy.com/https://github.com/FreedomIntelligence/CMB/archive/refs/heads/main.zip",
        "https://github.com/FreedomIntelligence/CMB/archive/refs/heads/main.zip",
    ]

    tmp_dir = BASE / ".tmp_cmb"
    tmp_dir.mkdir(exist_ok=True)

    for url in mirror_urls:
        try:
            print(f"[INFO] 尝试下载: {url}")
            zip_path = tmp_dir / "cmb.zip"
            urllib.request.urlretrieve(url, zip_path)

            print("[INFO] 解压...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_dir)

            # 查找 CMB.zip
            cmb_zip = tmp_dir / "CMB-main" / "data" / "CMB.zip"
            if cmb_zip.exists():
                print("[INFO] 找到 CMB.zip，解压数据...")
                data_dir = tmp_dir / "data"
                data_dir.mkdir(exist_ok=True)
                with zipfile.ZipFile(cmb_zip, "r") as zf:
                    zf.extractall(data_dir)

                # 加载 CMB-val
                val_files = list(data_dir.glob("*val*")) + list(data_dir.glob("*CMB-val*"))
                clin_files = list(data_dir.glob("*clin*")) + list(data_dir.glob("*CMB-clin*"))
                print(f"[INFO] 找到 val files: {val_files}")
                print(f"[INFO] 找到 clin files: {clin_files}")
                return val_files, clin_files
            break
        except Exception as e:
            print(f"[WARN] {url} 失败: {e}")
            continue

    return None, None


# ── Schema 映射 ──────────────────────────────────────────
def map_cmb_val_to_gs(cmb_item, idx):
    """将 CMB-val 条目映射为 GS Schema"""
    return {
        "gs_id": f"GS-CMB-VAL-{idx:04d}",
        "year": 2023,
        "exam_type": cmb_item.get("exam_type", ""),
        "exam_class": cmb_item.get("exam_class", ""),
        "question_no": idx + 1,
        "type": map_question_type(cmb_item.get("question_type", "")),
        "subject": cmb_item.get("exam_subject", ""),
        "stem": cmb_item.get("question", ""),
        "options": list(cmb_item.get("option", {}).values()),
        "answer": cmb_item.get("answer", ""),
        "explanation": cmb_item.get("solution", cmb_item.get("explanation", "")),
        "source_page": "",
        "bloom_level": "",
        "difficulty": "medium",
        "controversial": False,
        "source_file": "CMB-val (FreedomIntelligence/CMB, Apache-2.0)"
    }


def map_cmb_clin_to_gs(cmb_item, idx):
    """将 CMB-Clin 条目映射为 GS Schema"""
    return {
        "gs_id": f"GS-CMB-CLIN-{idx:04d}",
        "year": 2023,
        "exam_type": "临床推理",
        "exam_class": "病例分析",
        "question_no": idx + 1,
        "type": "案例分析",
        "subject": cmb_item.get("title", ""),
        "stem": f"{cmb_item.get('description', '')}\n\n{cmb_item.get('question', '')}",
        "options": [],
        "answer": cmb_item.get("answer", ""),
        "explanation": cmb_item.get("solution", ""),
        "source_page": "",
        "bloom_level": "分析",
        "difficulty": "hard",
        "controversial": False,
        "source_file": "CMB-Clin (FreedomIntelligence/CMB, Apache-2.0)"
    }


def map_question_type(cmb_type):
    """映射问题类型"""
    mapping = {
        "单项选择题": "A1",
        "多项选择题": "X型",
        "共用题干单选题": "A2",
        "共用选项单选题": "B型",
    }
    return mapping.get(cmb_type, "A1")


# ── 主入口 ────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"{'='*60}")
    print(f"CMB 数据下载与导入器 v1.0")
    print(f"执行时间: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    exam_val = None
    clin_data = None

    # 尝试 HF 下载
    print("[STEP 1] 尝试 HuggingFace 下载...")
    exam_val, clin_data = load_from_huggingface()

    # 如果 HF 失败，尝试 GitHub 镜像
    if exam_val is None:
        print("\n[STEP 2] HuggingFace 不可用，尝试 GitHub 镜像...")
        val_files, clin_files = load_from_github_mirror()
        if val_files:
            print(f"[INFO] 请手动从 {val_files} 加载 JSON 数据")
    else:
        # 转换 CMB-val
        print("\n[STEP 3] 转换 CMB-val → GS Schema...")
        gs_val = []
        for idx, item in enumerate(exam_val):
            gs_val.append(map_cmb_val_to_gs(item, idx))

        out_path = BASE / "Layer1_扩展层" / "CMB_val_280.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(gs_val, f, ensure_ascii=False, indent=2)

        # 统计
        subjects = {}
        for q in gs_val:
            s = q["subject"]
            subjects[s] = subjects.get(s, 0) + 1
        print(f"  总题数: {len(gs_val)}")
        print(f"  科目分布: {dict(sorted(subjects.items(), key=lambda x: -x[1])[:10])}")
        print(f"  ✅ 已保存: {out_path}")

        # 转换 CMB-Clin
        if clin_data:
            print("\n[STEP 4] 转换 CMB-Clin → GS Schema...")
            gs_clin = []
            for idx, item in enumerate(clin_data):
                gs_clin.append(map_cmb_clin_to_gs(item, idx))

            out_path = BASE / "Layer2_临床推理" / "CMB_clin_74.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(gs_clin, f, ensure_ascii=False, indent=2)
            print(f"  总例数: {len(gs_clin)}")
            print(f"  ✅ 已保存: {out_path}")
        else:
            print("\n[STEP 4] CMB-Clin 数据不可用，跳过")

    # 更新 Layer README
    print(f"\n{'='*60}")
    print("导入完成。请检查:")
    print(f"  Layer1_扩展层/CMB_val_280.json")
    print(f"  Layer2_临床推理/CMB_clin_74.json")
    print(f"{'='*60}")
