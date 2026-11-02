# -*- coding: utf-8 -*-
"""
pipeline_config.py — pipeline.yaml 阈值「单一事实来源」加载器（标准库实现）

为什么有这个模块（v2.1 回灌，源自 medagentwork-skill v2.1 / 评审 §6.4「风险」/ §七.7）：
    此前 R2 的 2.0/1.5、R13 的 20/18、GATE-A3 的 Bloom 15% 等阈值硬编码在
    rules_numeric.py / rules_structural.py / gate_check.py 中，与声明式配置
    只靠"巧合一致"维持 —— 改一处不会同步另一处。

本模块让规则层与门禁层在运行时从 pipeline.yaml 的 `thresholds:` 段读取阈值，
    读不到时回退到内置默认值（默认值与改造前硬编码取值一致，行为零回归）。

依赖策略：核心管线保持零第三方依赖。
    - 优先使用 PyYAML（若用户环境已安装）；
    - 不可用时使用内置「最小解析器」，只解析顶层 `thresholds:` 段
      （扁平 `key: value` 与行内列表 `key: [a, b, c]` 两种形态）。

主工作区说明（2026-11-02 修订 · P1-S3）：
    此前本模块指向「仓库根目录」的 pipeline.yaml，而真实配置文件一直在
    `scripts/pipeline.yaml` —— 结果是 thresholds 段**从未被读取**，
    所有阈值静默走内置默认值，与 gate_check.py 注释宣称的
    「pipeline.yaml 阈值单一事实来源」不符（规则漂移）。
    现改为读取与本模块同目录的 `scripts/pipeline.yaml`，并在该文件的
    顶层 `thresholds:` 段写入与内置默认**完全一致**的取值，
    因此本次修复对运行时行为零变化（见 reports/registry/config_snapshot_20261102.json）。
    如需调参，直接改 `scripts/pipeline.yaml` 的 thresholds 段即可全局生效。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

# scripts/ 目录内的 pipeline.yaml = 本文件同级（P1-S3 修订：原先指向仓库根，文件不存在）
_SCRIPTS_DIR = Path(__file__).resolve().parent
PIPELINE_YAML = _SCRIPTS_DIR / "pipeline.yaml"

# ── 内置默认值（与改造前各脚本硬编码值保持一致；缺失时回退）──
DEFAULTS: dict[str, object] = {
    "r2_ratio_fail": 2.0,        # R2 正确选项/最短干扰项 长度比 FAIL 阈值
    "r2_ratio_warn": 1.5,        # R2 长度比 WARN 阈值
    "option_length_max": 20,     # R13 单选项字数上限（FAIL）
    "option_avg_max": 18,        # R13 选项平均字数上限（WARN）
    "option_length_target": 18,  # 生成目标（提示词口径），与 option_length_max 不同：18 是「写多长」，20 是「超过即 FAIL」
    "bloom_deviation_max": 15,   # Bloom 单层偏差上限（%），超过则 BLOCKED
    "bloom_recompute_tolerance": 5,  # 门禁独立重算 Bloom 与质检报告自述值的允许偏差（%）
    "learning_value_min_source_exact": 0.95,   # HC-24: source_quote_status=exact 的最低占比
    "learning_value_min_quote_verified": 0.95,   # HC-24: exact 引文能在 teacher_anchor 逐字命中的最低占比
    "learning_value_max_misconception_conflicts": 0,  # HC-24: 同一 misconception_id 多种释义的允许数
    "learning_value_min_anchor_verified": 0.80,  # HC-24: anchor_status=verified 的最低占比
    "retry_item_max": 2,         # P5-S1: 单题重试超过该次数 → 该题 QUARANTINE
    "retry_batch_max": 3,        # P5-S1: 整批重试超过该次数 → 整批 QUARANTINE
    # P2-S3 批次级规则 X1/X2/X6（默认 advisory，阈值与门禁状态解耦）
    "x1_letter_min": 0.15,       # X1: 单个答案字母的最低占比
    "x1_letter_max": 0.30,       # X1: 单个答案字母的最高占比
    "x2_unique_longest_max": 0.30,   # X2: 正确项为「唯一最长项」的题目占比上限
    "x6_misconception_reuse_min": 0.20,  # X6: 被复用的错误认知 ID 占干扰项的最低比例
    "x5_reverse_max": 0.15,      # X5: 反选题（polarity=negative）占已标注题的占比上限
    "r8_legit_terms_default": [
        "妄想", "幻觉", "障碍", "减退", "缺乏", "低落", "焦虑", "恐惧",
        "躁狂", "抑郁", "木僵", "违拗", "缄默", "痴呆", "谵妄", "强迫",
        "疑病", "失眠", "嗜睡", "人格", "自知力", "PTSD", "OCD", "AD",
    ],
    "r8_legit_terms_tcm": [
        "气", "血", "津液", "阴阳", "表里", "寒热", "虚实", "风寒", "风热",
        "湿热", "痰浊", "瘀血", "气滞", "证", "脉", "舌",
    ],
    "r8_legit_terms_surgery": ["术", "疝", "痔", "瘘", "瘤", "囊肿", "脓肿"],
    "r8_legit_terms_psychiatry": ["妄想", "幻觉", "木僵", "谵妄", "PTSD", "OCD", "AD"],
}

_cache: dict[str, object] | None = None
_legit_cache: dict[str, frozenset] = {}


def _parse_scalar(raw: str):
    """把 YAML 行内值解析为 Python 对象（标量 / 行内列表）。"""
    s = raw.strip()
    if not s:
        return None
    # 去掉行尾注释（仅在值不是引号包裹时安全）
    if not (s.startswith(("'", '"')) or s.startswith("[")):
        s = re.split(r"\s+#", s, maxsplit=1)[0].strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in inner.split(",") if part.strip()]
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none", "~"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _parse_thresholds_minimal(text: str) -> dict[str, object]:
    """内置最小解析器：仅抽取顶层 `thresholds:` 段的扁平键值。

    不追求完整 YAML 兼容，只保证「阈值段」这一种受控写法可解析。
    """
    out: dict[str, object] = {}
    in_block = False
    block_indent = 0
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if not in_block:
            if indent == 0 and stripped.rstrip(":") == "thresholds" and stripped.endswith(":"):
                in_block = True
                block_indent = indent
            continue
        # 退出 thresholds 段：出现新的顶层键
        if indent <= block_indent and not stripped.startswith("#"):
            break
        if ":" not in stripped:
            continue
        key, _, raw_val = stripped.partition(":")
        out[key.strip()] = _parse_scalar(raw_val)
    return out


def load_thresholds(force_reload: bool = False) -> dict[str, object]:
    """读取 pipeline.yaml 的 thresholds 段，与内置默认值合并（配置优先）。"""
    global _cache
    if _cache is not None and not force_reload:
        return _cache

    loaded: dict[str, object] = {}
    if PIPELINE_YAML.exists():
        try:
            text = PIPELINE_YAML.read_text(encoding="utf-8")
            try:  # 优先 PyYAML（可选依赖）
                import yaml  # type: ignore

                data = yaml.safe_load(text) or {}
                section = data.get("thresholds") if isinstance(data, dict) else None
                if isinstance(section, dict):
                    loaded = dict(section)
            except ImportError:
                loaded = _parse_thresholds_minimal(text)
        except Exception as e:  # 配置损坏不应阻断管线，回退默认
            print(f"  ⚠️ pipeline.yaml 阈值解析失败，回退内置默认值: {e}")

    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in loaded.items() if v is not None})
    _cache = merged
    return merged


def get_threshold(key: str, default=None):
    """取单个阈值（配置 → 内置默认 → 调用方默认）。"""
    cfg = load_thresholds()
    if key in cfg and cfg[key] is not None:
        return cfg[key]
    return DEFAULTS.get(key, default)


def get_number(key: str, default: float) -> float:
    """取数值阈值，保证返回 float（配置写错类型时回退默认）。"""
    try:
        return float(get_threshold(key, default))
    except (TypeError, ValueError):
        return float(default)


def get_r8_legit_terms(subject: str | None = None) -> frozenset:
    """R8 短选项豁免词表。

    v2.1 回灌（评审 §6.5-P1.5 / §七.9）：原实现把精神科专属词表硬编码在
    rules_numeric.py 里，对中医、外科等科目会产生系统性误报/漏报。现改为：
        默认词表 ∪ 科目词表（科目取自题目 `subject` 字段或环境变量
        MEDAGENTWORK_SUBJECT）。
    """
    subject = (subject or os.environ.get("MEDAGENTWORK_SUBJECT") or "").strip().lower()
    cache_key = subject
    if cache_key in _legit_cache:
        return _legit_cache[cache_key]

    terms = set(get_threshold("r8_legit_terms_default", []) or [])
    if subject:
        # 科目别名归一化（配置用短码，题目里可能写中文全称）
        aliases = {
            "tcm": "tcm", "中医": "tcm", "中医学": "tcm",
            "surgery": "surgery", "外科": "surgery", "外科学": "surgery",
            "psychiatry": "psychiatry", "精神": "psychiatry", "精神科": "psychiatry",
            "精神病学": "psychiatry",
        }
        key = aliases.get(subject, subject)
        terms |= set(get_threshold(f"r8_legit_terms_{key}", []) or [])
    result = frozenset(t for t in terms if t)
    _legit_cache[cache_key] = result
    return result


def config_hash(force_reload: bool = False) -> str:
    """生效阈值的稳定指纹（供 lineage 五元组 / gate 校验使用）。

    对「合并后的生效配置」做 canonical JSON（排序键、UTF-8）sha256，
    因此默认值与配置项顺序变化不会改变指纹，只有取值变化才会。
    """
    cfg = load_thresholds(force_reload)
    payload = json.dumps(cfg, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path | str | None = None) -> str:
    """配置文件本身的 sha256；文件缺失返回空串（显式可辨，不伪装成有效值）。"""
    p = Path(path) if path else PIPELINE_YAML
    if not p.exists():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot() -> dict:
    """配置快照：路径、来源、生效值、双指纹。--print-config 与证据文件共用。"""
    cfg = load_thresholds()
    return {
        "config_path": str(PIPELINE_YAML),
        "config_exists": PIPELINE_YAML.exists(),
        "config_file_sha256": file_sha256(),
        "config_hash": config_hash(),
        "source": "pipeline.yaml thresholds 段（缺失键回退内置默认）",
        "effective": cfg,
        "defaults": dict(DEFAULTS),
        "overridden_keys": sorted(k for k, v in cfg.items() if k in DEFAULTS and v != DEFAULTS.get(k)),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI：--print-config 打印生效阈值与指纹；--check 只做可读性校验。"""
    import argparse

    ap = argparse.ArgumentParser(
        description="pipeline.yaml 阈值加载器（P1-S3 配置单一事实来源）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python scripts/pipeline_config.py --print-config\n"
               "  python scripts/pipeline_config.py --print-config --json reports/registry/config_snapshot.json\n"
               "  python scripts/pipeline_config.py --check\n")
    ap.add_argument("--print-config", action="store_true", help="打印配置路径、生效阈值、config_hash")
    ap.add_argument("--json", default="", help="把快照写入 JSON 文件")
    ap.add_argument("--key", default="", help="只打印单个阈值")
    ap.add_argument("--check", action="store_true", help="校验配置文件存在且可解析（不可解析返回 2）")
    ap.add_argument("--quiet", action="store_true", help="不打印正文（配合 --json 使用）")
    args = ap.parse_args(argv)

    if args.check:
        if not PIPELINE_YAML.exists():
            print(f"[FAIL] 配置文件不存在: {PIPELINE_YAML}", file=sys.stderr)
            return 2
        try:
            load_thresholds(force_reload=True)
        except Exception as exc:  # pragma: no cover
            print(f"[FAIL] 配置解析失败: {exc}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"[PASS] {PIPELINE_YAML} 可读，config_hash={config_hash()[:12]}")

    if args.key:
        if not args.quiet:
            print(get_threshold(args.key))
        return 0

    if args.print_config or args.json or not (args.check or args.key):
        snap = snapshot()
        if not args.quiet:
            print(f"配置文件: {snap['config_path']} (exists={snap['config_exists']})")
            print(f"文件 sha256: {snap['config_file_sha256'][:16] or '(文件缺失)'}")
            print(f"config_hash: {snap['config_hash']}")
            if snap["overridden_keys"]:
                print(f"⚠ 相对内置默认被覆盖的键: {', '.join(snap['overridden_keys'])}")
            else:
                print("相对内置默认无覆盖（生效值 == 内置默认）")
            print(json.dumps(snap["effective"], ensure_ascii=False, indent=2, default=str))
        if args.json:
            out = Path(args.json)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(snap, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            if not args.quiet:
                print(f"📄 快照: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
