#!/usr/bin/env python3
"""
utils.py — MedAgentWork 公共工具模块 v1.0

消除 healthcheck.py / ingest.py / maintenance.py 等文件中
重复定义的工具函数（铁律④ 无副本原则）。

用法:
    from scripts.utils import md5_file, safe_json_load, SUBJECT_TO_CODE
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ──────────────────────────────────────────
# 常量定义
# ──────────────────────────────────────────

# 学科名称 → 知识库代码映射（verify_page_numbers.py / fact_check.py 共用）
SUBJECT_TO_CODE = {
    "内科学": "internal-med", "儿科学": "pediatrics", "外科学": "surgery",
    "神经病学": "neurology", "精神病学": "psychiatry",
    "皮肤性病学": "dermatology", "中医学": "tcm", "医患沟通": "doctor-patient",
}


def md5_file(filepath) -> str | None:
    """计算文件 MD5 哈希值。失败返回 None。"""
    h = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def safe_json_load(filepath):
    """安全加载 JSON 文件，返回 (data, error)。
    
    成功: (dict|list, None)
    失败: (None, str)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f'JSON 解析失败: {e}'
    except Exception as e:
        return None, str(e)


def ensure_dir(path: Path) -> Path:
    """确保目录存在，不存在则创建。返回路径。"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative_to(path: Path, base: Path) -> str:
    """尝试获取相对于 base 的路径字符串。失败返回绝对路径字符串。"""
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)
