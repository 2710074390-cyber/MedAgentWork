# -*- coding: utf-8 -*-
"""
medillustration_config.py — 单一配置源加载器（P1-4 / P2-8）

读取 MedAgentWork/medillustration_config.yaml，供 render_diagram / annotate_image /
export_webp / check_inline_images 等脚本统一引用，禁止在脚本中散落硬编码常量。
"""
from pathlib import Path
import yaml

_CFG = None


def load():
    """返回配置 dict；找不到配置时返回 {}（各脚本回退到自带默认常量）。"""
    global _CFG
    if _CFG is not None:
        return _CFG
    here = Path(__file__).resolve().parent
    candidates = [here.parent, here.parent.parent, here, Path.cwd()]
    for p in candidates:
        cand = p / "medillustration_config.yaml"
        if cand.exists():
            try:
                _CFG = yaml.safe_load(cand.read_text(encoding="utf-8")) or {}
                _CFG["_path"] = str(cand)
                return _CFG
            except Exception as e:  # 配置损坏时降级为空配置，不阻断脚本
                print(f"[medillustration_config] 读取失败，回退默认常量：{e}")
                _CFG = {}
                return _CFG
    _CFG = {}
    return _CFG


def colors(cfg=None):
    """返回 {键: 深色主色} 映射（config.colors），缺失时为空 dict。"""
    cfg = cfg if cfg is not None else load()
    return (cfg.get("colors") or {})


def canvas(cfg=None):
    """返回画布/压缩参数 dict。"""
    cfg = cfg if cfg is not None else load()
    return (cfg.get("canvas") or {})


def fonts(cfg=None):
    cfg = cfg if cfg is not None else load()
    return (cfg.get("fonts") or {})
