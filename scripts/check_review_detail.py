#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_review_detail.py — 复习资料详细度契约门禁（HC-26）。

解决的问题
    旧版复习资料「有重点、有数字、有表格」，但读者读一遍仍答不出：
    这是什么、为什么会这样、怎么认、怎么确诊、怎么治、和谁鉴别。
    本脚本把「详细度」从主观感受变成可核验的结构契约：
    每个考点必须回答固定的临床推理问题，并配可检索的自测答案；
    每个模块必须有案例、对比表、因果链与展开区；
    课程安排版每一讲必须有目标、课前、重点、机制、案例、自测、时间与衔接。

判定
    PASS  = 达到 profile 的详细度阈值
    WARN  = 未达目标但未触及阻断线（advisory 下 FAIL 也降级为 WARN）
    FAIL  = 核心考点缺关键推理槽位 / 自测无答案 / 模块缺块，enforce 下阻断

用法
    python scripts/check_review_detail.py \
        --md "复习资料/耳鼻咽喉头颈外科学教师重点版/耳鼻咽喉头颈外科学教师重点版_主复习资料.md" \
        --mode auto --profile release_teacher_keypoint \
        --json-out reports/validate/review_detail_ent.json \
        --md-out reports/validate/review_detail_ent.md

    python scripts/check_review_detail.py --md <课程安排版.md> --mode course_schedule --profile release_teaching_plan
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# 契约定义
# ---------------------------------------------------------------------------

TIER_ORDER = {"core": 0, "familiar": 1, "aware": 2}
TIER_WEIGHT = {"core": 3.0, "familiar": 2.0, "aware": 1.0}
TIER_LABEL = {"core": "🔴 掌握", "familiar": "🟡 熟悉", "aware": "🟢 了解"}

# 九个学习槽位 = 读者读一遍后应能回答的问题
SLOT_LABEL = {
    "locate": "定位（是什么/在哪）",
    "mechanism": "机制（为什么）",
    "recognize": "识别（怎么认）",
    "diagnose": "诊断（怎么查/确诊）",
    "manage": "处置（怎么治）",
    "differentiate": "鉴别（和谁混）",
    "pitfall": "易错（哪里错）",
    "mnemonic": "记忆钩子（怎么记）",
    "selftest": "自测（能否回忆）",
    "case": "案例（能否迁移）",
}

# 兼容旧版标签（v5.6 教师版）与新版契约标签（v6 / HC-26）
SLOT_ALIASES = {
    "locate": ("🎯 定位", "🎯 一句话题眼", "定位", "定义", "概念与定位"),
    "mechanism": ("🧬 机制", "🧬 为什么", "机制", "第一性原理", "病理生理", "发生机制"),
    "recognize": ("👁 识别", "识别", "临床表现", "典型表现", "症状与体征", "临床特征", "怎么认"),
    "diagnose": ("🔍 诊断", "诊断", "检查", "确诊", "评估", "诊断标准"),
    "manage": ("🩺 处置", "🩺 下一步", "处置", "治疗", "处理", "管理", "治疗原则"),
    "differentiate": ("⚖️ 鉴别", "鉴别", "对比", "区分", "鉴别诊断"),
    "pitfall": ("🚨 易错", "🚨 红线", "易错", "陷阱", "红线", "注意事项"),
    "mnemonic": ("🧠 记忆钩子", "记忆钩子", "记忆", "口诀", "一句话记住"),
    "case": ("🏥 案例", "🏥 病例", "案例", "病例", "临床情境", "情境", "病例分析"),
    "selftest": ("🔄 自测", "自测", "主动回忆", "练习", "课后任务"),
}

# 分级详细度：掌握级必须回答全部问题；熟悉级保留临床主干；了解级只要求认得与鉴别
REQUIRED_SLOTS = {
    "core": ("locate", "mechanism", "recognize", "diagnose", "manage",
             "differentiate", "pitfall", "mnemonic", "case", "selftest"),
    "familiar": ("locate", "mechanism", "recognize", "diagnose", "manage",
                 "differentiate", "selftest"),
    "aware": ("locate", "recognize", "differentiate", "selftest"),
}

# 默认阈值（policy 可覆盖）
DEFAULT_THRESHOLDS = {
    "core_min_chars": 900,
    "familiar_min_chars": 550,
    "aware_min_chars": 250,
    "core_min_units": 12,
    "familiar_min_units": 7,
    "aware_min_units": 4,
    "core_max_chars": 3200,
    "familiar_max_chars": 2400,
    "aware_max_chars": 1600,
    "overall_pass": 0.90,
    "overall_warn": 0.70,
    "core_slot_min": 1.0,
    "card_pass_min": 0.90,
    "selftest_answer_min": 1.0,
    "module_block_min": 1.0,
    "case_module_min": 1.0,
}

# 课程安排版：每一讲必须有的 8 个块
SCHEDULE_BLOCKS = {
    "objectives": ("学习目标", "教学目标", "本周目标", "课时目标"),
    "pre": ("课前", "前置知识", "预习", "准备"),
    "keypoints": ("课堂重点", "重点内容", "教学内容", "核心内容"),
    "mechanism": ("机制", "原理", "病理生理", "为什么"),
    "case": ("案例", "病例", "临床情境", "情境"),
    "selftest": ("自测", "练习", "课后任务", "课后自测"),
    "time": ("学时", "课时", "时间预算", "分钟", "预计"),
    "link": ("衔接", "前后", "关联", "下周", "承上启下"),
}

MODULE_BLOCKS = {
    "pre": ("前置知识", "课前准备", "复习入口"),
    "summary": ("30 秒摘要", "高收益摘要", "学习目标", "核心摘要"),
    "table": ("对比表",),
    "chain": ("因果链", "机制链", "病理生理链"),
    "case": ("案例", "病例", "临床情境"),
    "selftest": ("自测", "主动回忆"),
    "wrapup": ("本章小结", "一页纸", "小结"),
    "expand": ("🔬 展开",),
}

MODULE_REQUIRED = ("pre", "summary", "table", "chain", "case", "selftest", "wrapup", "expand")
MODULE_LABEL = {
    "pre": "前置知识", "summary": "模块摘要/学习目标", "table": "对比表（≥3 行）",
    "chain": "因果链", "case": "案例", "selftest": "自测", "wrapup": "本章小结",
    "expand": "展开区（≥2）",
}

CARD_ID_RE = re.compile(r"(K-M\d{2}-\d{3})")
MODULE_RE = re.compile(r"^##\s*模块(\d+)：(.+)$")
ANY_H2_RE = re.compile(r"^##\s+")
CARD_RE = re.compile(r"^####\s+(.+)$")
# v5 教学计划版：考点直接以 `🔴 【掌握级】…` 段落开头，没有四级标题
TIER_LINE_RE = re.compile(r"^(🔴|🟡|🟢)\s*【(掌握|熟悉|了解)级】\s*(.+)$")
ANCHOR_RE = re.compile(r"📌\s*重点原文[（(]第\s*(\d+)\s*条")
TABLE_ROW_RE = re.compile(r"^\|(?!\s*[-:| ]+\s*\|).+\|\s*$")
SELFTEST_RE = re.compile(r"🔄\s*(?:自测|主动回忆)|(?:自测|主动回忆)[：:]")
CODE_FENCE_RE = re.compile(r"^```")
SCHEDULE_RE = re.compile(
    r"^##\s*(第[0-9一二三四五六七八九十百]+(?:周|讲|次|课时)|Week\s*\d+|Lecture\s*\d+)"
    r"[:：]?\s*(.*)$", re.I,
)


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def _configure_stdio() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path):
    return json.loads(read_text(path))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_json(path: Path, data) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def strip_inline(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def effective_chars(text: str) -> int:
    """有效字符：去掉空白、锚点行、HTML 标签与 Markdown 标记。"""
    kept = []
    for line in text.splitlines():
        if ANCHOR_RE.search(line):
            continue
        kept.append(line)
    raw = "\n".join(kept)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = re.sub(r"[*_`#>|:\-\s]", "", raw)
    return len(raw)


def _strip_leading_symbols(text: str) -> str:
    """去掉行首 emoji / 符号 / 空白，保留中文、字母、数字。"""
    return re.sub(r"^[^\w\u4e00-\u9fff]+", "", text or "", flags=re.UNICODE).strip()


def _norm_label_line(raw: str) -> str:
    line = raw.strip()
    if not line or line.startswith("|"):
        return ""
    line = re.sub(r"^>+\s*", "", line)
    line = re.sub(r"^#{2,6}\s*", "", line)
    line = re.sub(r"\[![A-Za-z]+\]\s*", "", line)
    line = re.sub(r"</?b>", "", line)
    line = line.replace("**", "")
    line = re.sub(r"^[-+*\s]+", "", line)
    return _strip_leading_symbols(line)


def has_label(text: str, aliases: tuple[str, ...]) -> bool:
    for raw in text.splitlines():
        line = _norm_label_line(raw)
        if not line:
            continue
        for alias in aliases:
            alias_norm = _strip_leading_symbols(alias)
            if alias_norm and line.startswith(alias_norm):
                return True
    return False


def count_tables(text: str) -> int:
    return sum(1 for line in text.splitlines() if TABLE_ROW_RE.match(line.strip()))


def count_callouts(text: str) -> int:
    return len(re.findall(r"^>\s*\[!", text, re.M))


def count_expand(text: str) -> int:
    return len(re.findall(r"^####\s*🔬\s*展开", text, re.M))


def count_selftests(text: str) -> int:
    return sum(1 for line in text.splitlines() if SELFTEST_RE.search(line))


def has_chain(text: str) -> bool:
    if has_label(text, MODULE_BLOCKS["chain"]):
        return True
    # ASCII 因果链：同一代码块内同时出现箭头与纵向连接
    for m in re.finditer(r"```.*?```", text, re.S):
        block = m.group(0)
        if ("→" in block or "->" in block) and ("↓" in block or "v" in block):
            return True
    return False


def info_units(text: str) -> int:
    """信息单元 = 句子/条目 + 表格数据行 + 代码图块（去重计数）。"""
    body = "\n".join(line for line in text.splitlines() if not ANCHOR_RE.search(line))
    tables = count_tables(body)
    fences = len(re.findall(r"^```", body, re.M)) // 2
    no_tables = "\n".join(line for line in body.splitlines() if not line.strip().startswith("|"))
    no_code = re.sub(r"```.*?```", "", no_tables, flags=re.S)
    plain = strip_inline(no_code)
    sentences = [s for s in re.split(r"[。；！？\n]", plain) if len(s.strip()) >= 6]
    bullets = [ln for ln in no_code.splitlines()
               if re.match(r"^\s*(?:[-+*]|\d+[.、])\s+\S", ln) and len(strip_inline(ln)) >= 6]
    return max(len(sentences), len(bullets)) + tables + fences


def detect_tier(title: str) -> str:
    if "🔴" in title or "掌握级" in title:
        return "core"
    if "🟡" in title or "熟悉级" in title:
        return "familiar"
    if "🟢" in title or "了解级" in title:
        return "aware"
    return "familiar"


def clean_title(title: str) -> str:
    t = re.sub(r"^[🔴🟡🟢]\s*", "", title)
    t = re.sub(r"^【(?:掌握|熟悉|了解)级】\s*", "", t)
    t = re.split(r"（教师重点", t)[0]
    t = re.split(r"[｜|]", t)[0]
    return t.strip()


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

def parse_cards(md_text: str) -> tuple[list[dict], list[dict]]:
    """解析考点卡与模块。兼容 K-Mxx 编号版与 v5 通用标题版。"""
    lines = md_text.splitlines()
    modules: list[dict] = []
    cards: list[dict] = []

    module = None
    module_start = 0
    current = None
    body_start = 0
    seq = 0

    def finalize_card(end: int) -> None:
        nonlocal current
        if not current:
            return
        body = "\n".join(lines[body_start:end])
        current["body"] = body
        current["chars"] = effective_chars(body)
        current["units"] = info_units(body)
        current["keypoints"] = sorted(set(current["keypoints"]))
        current["pages"] = sorted(set(current["pages"]))
        current["title_clean"] = clean_title(current["title"])
        current["label"] = TIER_LABEL[current["tier"]]
        cards.append(current)
        current = None

    def finalize_module(end: int) -> None:
        nonlocal module
        if not module:
            return
        text = "\n".join(lines[module_start:end])
        module["text"] = text
        module["chars"] = effective_chars(text)
        modules.append(module)
        module = None

    def start_card(heading: str, i: int) -> None:
        nonlocal current, body_start, seq
        if current:
            finalize_card(i)
        seq += 1
        cid_m = CARD_ID_RE.search(heading)
        mod_id = module["id"] if module else "M00"
        cid = cid_m.group(1) if cid_m else f"C-{mod_id}-{seq:03d}"
        kps = []
        km = re.search(r"教师重点第([0-9、,，/]+)条", heading)
        if km:
            for x in re.split(r"[、,，/]", km.group(1)):
                if x.strip().isdigit():
                    kps.append(int(x.strip()))
        pages = [int(x) for x in re.findall(r"P(\d+)", heading)]
        current = {
            "id": cid,
            "module": mod_id,
            "tier": detect_tier(heading),
            "title": heading,
            "keypoints": kps,
            "pages": pages,
        }
        body_start = i + 1

    for i, line in enumerate(lines):
        m = MODULE_RE.match(line)
        if m:
            if current:
                finalize_card(i)
            if module:
                finalize_module(i)
            module = {"id": f"M{int(m.group(1)):02d}", "name": m.group(2).strip(),
                      "start_line": i + 1}
            module_start = i
            seq = 0
            continue
        if ANY_H2_RE.match(line):
            if current:
                finalize_card(i)
            if module:
                finalize_module(i)
            continue

        # v5 教学计划版：无 #### 标题，考点以 `🔴 【掌握级】…` 段落开头
        m = TIER_LINE_RE.match(line)
        if m:
            start_card(line.strip(), i)
            continue

        m = CARD_RE.match(line)
        if m:
            heading = m.group(1).strip()
            if heading.startswith("🔬 展开") or heading.startswith("🌳"):
                # 展开区/决策树属于当前卡片或模块内容，不截断卡片
                continue
            looks_card = bool(CARD_ID_RE.search(heading)) or "🔴" in heading \
                or "🟡" in heading or "🟢" in heading or "【掌握级】" in heading \
                or "【熟悉级】" in heading or "【了解级】" in heading
            if not looks_card:
                # `#### 二、…` 等章节标题：结束当前卡片，但不新建卡片
                if current:
                    finalize_card(i)
                continue
            start_card(heading, i)
            continue
    if current:
        finalize_card(len(lines))
    if module:
        finalize_module(len(lines))
    return cards, modules


def parse_schedule_units(md_text: str) -> list[dict]:
    lines = md_text.splitlines()
    starts = []
    for i, line in enumerate(lines):
        m = SCHEDULE_RE.match(line)
        if m:
            starts.append((i, m.group(1).strip(), m.group(2).strip()))
    units = []
    for idx, (i, key, title) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        body = "\n".join(lines[i + 1:end])
        units.append({
            "id": key,
            "title": title or key,
            "start_line": i + 1,
            "text": body,
            "chars": effective_chars(body),
            "units": info_units(body),
        })
    return units


def analyze_card(card: dict, answer_keys: set[tuple[str, str]], th: dict) -> dict:
    body = card["body"]
    tier = card["tier"]
    slots = {name: has_label(body, aliases) for name, aliases in SLOT_ALIASES.items()}
    slots["selftest"] = slots["selftest"] and (card["module"], card["id"]) in answer_keys
    if tier != "core":
        # 案例是掌握级专属要求；其他层级有则加分，无则不扣
        slots.pop("case", None)

    required = [s for s in REQUIRED_SLOTS[tier] if s != "selftest"]
    required.append("selftest")
    missing = [s for s in required if not slots.get(s)]
    min_chars = int(th.get(f"{tier}_min_chars", DEFAULT_THRESHOLDS[f"{tier}_min_chars"]))
    min_units = int(th.get(f"{tier}_min_units", DEFAULT_THRESHOLDS[f"{tier}_min_units"]))
    max_chars = int(th.get(f"{tier}_max_chars", DEFAULT_THRESHOLDS[f"{tier}_max_chars"]))
    deficits = []
    if missing:
        deficits.append("缺槽位：" + "、".join(SLOT_LABEL[s] for s in missing))
    if card["chars"] < min_chars:
        deficits.append(f"正文 {card['chars']} < {min_chars} 字符")
    if card["units"] < min_units:
        deficits.append(f"信息单元 {card['units']} < {min_units}")
    warnings = []
    if card["chars"] > max_chars:
        warnings.append(f"正文 {card['chars']} > {max_chars} 字符，建议拆分（认知负荷）")
    slot_ratio = (len(required) - len(missing)) / max(1, len(required))
    return {
        "id": card["id"],
        "module": card["module"],
        "tier": tier,
        "tier_label": card["label"],
        "title": card["title_clean"],
        "chars": card["chars"],
        "units": card["units"],
        "slots": {k: bool(v) for k, v in slots.items()},
        "missing_slots": missing,
        "slot_ratio": round(slot_ratio, 4),
        "pass": not deficits,
        "deficits": deficits,
        "warnings": warnings,
        "keypoints": card["keypoints"],
    }


def analyze_module(module: dict) -> dict:
    text = module["text"]
    present = {}
    present["pre"] = has_label(text, MODULE_BLOCKS["pre"])
    present["summary"] = has_label(text, MODULE_BLOCKS["summary"])
    present["table"] = count_tables(text) >= 3
    present["chain"] = has_chain(text)
    present["case"] = has_label(text, MODULE_BLOCKS["case"])
    present["selftest"] = has_label(text, MODULE_BLOCKS["selftest"]) or count_selftests(text) >= 1
    present["wrapup"] = has_label(text, MODULE_BLOCKS["wrapup"])
    present["expand"] = count_expand(text) >= 2
    missing = [b for b in MODULE_REQUIRED if not present[b]]
    return {
        "id": module["id"],
        "name": module["name"],
        "chars": module["chars"],
        "tables": count_tables(text),
        "callouts": count_callouts(text),
        "expand_blocks": count_expand(text),
        "selftests": count_selftests(text),
        "blocks": present,
        "missing_blocks": missing,
        "pass": not missing,
    }


def analyze_schedule_unit(unit: dict, th: dict) -> dict:
    text = unit["text"]
    blocks = {name: has_label(text, aliases) for name, aliases in SCHEDULE_BLOCKS.items()}
    # 自测必须带答案
    blocks["selftest"] = blocks["selftest"] and bool(
        re.search(r"答案[：:]|参考答案|答案见", text)
    )
    missing = [b for b in SCHEDULE_BLOCKS if not blocks[b]]
    min_chars = int(th.get("schedule_min_chars", 1200))
    min_units = int(th.get("schedule_min_units", 12))
    deficits = []
    if missing:
        deficits.append("缺区块：" + "、".join(SCHEDULE_BLOCKS[b][0] for b in missing))
    if unit["chars"] < min_chars:
        deficits.append(f"正文 {unit['chars']} < {min_chars} 字符")
    if unit["units"] < min_units:
        deficits.append(f"信息单元 {unit['units']} < {min_units}")
    return {
        "id": unit["id"],
        "title": unit["title"],
        "chars": unit["chars"],
        "units": unit["units"],
        "blocks": blocks,
        "missing_blocks": missing,
        "pass": not deficits,
        "deficits": deficits,
    }


# ---------------------------------------------------------------------------
# 阈值与评分
# ---------------------------------------------------------------------------

def load_thresholds(profile: str, policy_path: Path) -> dict:
    th = dict(DEFAULT_THRESHOLDS)
    try:
        import quality_policy
        policy = quality_policy.load_policy(policy_path)
        profile_data = quality_policy.get_profile(profile, policy)
        for key, value in (profile_data.get("thresholds") or {}).items():
            if key.startswith("review_detail_") or key.startswith("schedule_"):
                th[key.replace("review_detail_", "", 1)] = value
    except Exception:
        # 无 policy 时使用内置默认值，保证脚本可独立运行
        pass
    return th


def evaluate(cards: list[dict], modules: list[dict], units: list[dict],
             mode: str, th: dict, answer_keys: set[tuple[str, str]] | None = None) -> dict:
    answer_keys = answer_keys or set()
    if mode == "course_schedule":
        analyzed_units = [analyze_schedule_unit(u, th) for u in units]
        total = len(analyzed_units)
        passed = sum(1 for u in analyzed_units if u["pass"])
        chars = sum(u["chars"] for u in analyzed_units)
        units_total = sum(u["units"] for u in analyzed_units)
        overall = (passed / total) if total else 0.0
        status = "PASS"
        blocking = []
        warnings = []
        if overall < float(th["overall_warn"]):
            status = "FAIL"
            blocking.append(f"课程安排版详细度 {overall:.1%} < {th['overall_warn']:.0%}")
        elif overall < float(th["overall_pass"]):
            status = "WARN"
            warnings.append(f"课程安排版详细度 {overall:.1%} < {th['overall_pass']:.0%}")
        return {
            "mode": mode,
            "summary": {
                "units": total, "passed_units": passed,
                "overall": round(overall, 4),
                "content_chars": chars,
                "avg_chars": round(chars / max(1, total), 1),
                "info_units": units_total,
                "status": status,
            },
            "units": analyzed_units,
            "modules": [],
            "cards": [],
            "blocking": blocking,
            "warnings": warnings,
        }

    analyzed_cards = [analyze_card(c, answer_keys, th) for c in cards]
    analyzed_modules = [analyze_module(m) for m in modules]

    total = len(analyzed_cards)
    if not total:
        return {
            "mode": mode,
            "summary": {"cards": 0, "modules": len(modules), "overall": 0.0,
                        "status": "SKIP"},
            "cards": [], "modules": analyzed_modules,
            "blocking": [], "warnings": ["未解析到考点卡（无 K-Mxx 编号或无分级标题）"],
        }

    tier_counts = {t: sum(1 for c in analyzed_cards if c["tier"] == t) for t in TIER_ORDER}
    weighted = sum(TIER_WEIGHT[c["tier"]] * c["slot_ratio"] for c in analyzed_cards)
    weight_sum = sum(TIER_WEIGHT[c["tier"]] for c in analyzed_cards)
    card_slot_score = weighted / max(1.0, weight_sum)
    card_pass_ratio = sum(1 for c in analyzed_cards if c["pass"]) / total
    core_cards = [c for c in analyzed_cards if c["tier"] == "core"]
    core_slot_ratio = sum(1 for c in core_cards if not c["missing_slots"]) / max(1, len(core_cards))
    core_full_ratio = sum(1 for c in core_cards if c["pass"]) / max(1, len(core_cards))
    case_ratio = sum(1 for c in core_cards if c["slots"].get("case")) / max(1, len(core_cards))
    selftest_ratio = sum(1 for c in analyzed_cards if c["slots"].get("selftest")) / total

    if analyzed_modules:
        block_hits = sum(sum(1 for ok in m["blocks"].values() if ok) for m in analyzed_modules)
        block_total = len(analyzed_modules) * len(MODULE_REQUIRED)
        module_ratio = block_hits / max(1, block_total)
        case_module_ratio = sum(1 for m in analyzed_modules if m["blocks"]["case"]) / len(analyzed_modules)
    else:
        module_ratio = 1.0
        case_module_ratio = 1.0

    avg_chars = sum(c["chars"] for c in analyzed_cards) / total
    overall = (0.60 * card_slot_score + 0.15 * card_pass_ratio +
               0.15 * module_ratio + 0.10 * selftest_ratio)

    blocking: list[str] = []
    warnings: list[str] = []
    status = "PASS"
    if core_slot_ratio < float(th["core_slot_min"]):
        status = "FAIL"
        blocking.append(f"掌握级槽位完整率 {core_slot_ratio:.1%} < {th['core_slot_min']:.0%}")
    if card_pass_ratio < float(th["card_pass_min"]):
        status = "FAIL"
        blocking.append(f"卡片达标率 {card_pass_ratio:.1%} < {th['card_pass_min']:.0%}")
    if selftest_ratio < float(th["selftest_answer_min"]):
        status = "FAIL"
        blocking.append(f"自测答案覆盖 {selftest_ratio:.1%} < {th['selftest_answer_min']:.0%}")
    if module_ratio < float(th["module_block_min"]):
        status = "FAIL"
        blocking.append(f"模块块完整率 {module_ratio:.1%} < {th['module_block_min']:.0%}")
    if case_module_ratio < float(th["case_module_min"]):
        status = "FAIL"
        blocking.append(f"模块案例覆盖 {case_module_ratio:.1%} < {th['case_module_min']:.0%}")
    if overall < float(th["overall_warn"]):
        status = "FAIL"
        blocking.append(f"详细度总分 {overall:.1%} < {th['overall_warn']:.0%}")
    elif overall < float(th["overall_pass"]):
        if status == "PASS":
            status = "WARN"
        warnings.append(f"详细度总分 {overall:.1%} < {th['overall_pass']:.0%}")

    for c in analyzed_cards:
        warnings.extend(f"{c['id']}：{w}" for w in c["warnings"])

    return {
        "mode": mode,
        "summary": {
            "cards": total,
            "modules": len(analyzed_modules),
            "tier_counts": {TIER_LABEL[t]: tier_counts[t] for t in TIER_ORDER},
            "card_slot_score": round(card_slot_score, 4),
            "card_pass_ratio": round(card_pass_ratio, 4),
            "core_slot_ratio": round(core_slot_ratio, 4),
            "core_full_ratio": round(core_full_ratio, 4),
            "case_ratio": round(case_ratio, 4),
            "selftest_answer_ratio": round(selftest_ratio, 4),
            "module_block_ratio": round(module_ratio, 4),
            "case_module_ratio": round(case_module_ratio, 4),
            "content_chars": sum(c["chars"] for c in analyzed_cards),
            "avg_chars": round(avg_chars, 1),
            "overall": round(overall, 4),
            "status": status,
        },
        "cards": analyzed_cards,
        "modules": analyzed_modules,
        "blocking": blocking,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 答案匹配（复用 spaced_schedule 的模块+卡片对账）
# ---------------------------------------------------------------------------

def selftest_answer_keys(md_text: str) -> set[tuple[str, str]]:
    try:
        import spaced_schedule as ss
    except Exception:
        return set()
    prompts = ss.parse_self_tests(md_text)
    rows = ss.parse_appendix_rows(md_text)
    matched, _, _ = ss.reconcile(prompts, rows)
    return {(m["prompt"]["module"], m["prompt"]["card"]) for m in matched}


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def detect_mode(md_text: str, requested: str) -> str:
    if requested != "auto":
        return requested
    if len(parse_schedule_units(md_text)) >= 2:
        return "course_schedule"
    cards, _ = parse_cards(md_text)
    if any(c["keypoints"] for c in cards) or "教师重点" in md_text[:2000]:
        return "teacher_keypoint"
    return "module"


def render_md(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# 复习资料详细度报告（HC-26）",
        "",
        f"> 文件：{report['md_path']}",
        f"> 模式：{report['mode']} ｜ Profile：{report['profile']} ｜ 结论：<b>{s['status']}</b>",
        f"> 生成：{report['generated_at']} ｜ 契约：v{SCHEMA_VERSION}",
        "",
        "## 1. 总览",
        "",
        "| 指标 | 值 |",
        "|---|---|",
    ]
    for key in ("cards", "modules", "tier_counts", "content_chars", "avg_chars",
                "card_slot_score", "card_pass_ratio", "core_slot_ratio",
                "core_full_ratio", "selftest_answer_ratio", "module_block_ratio",
                "case_module_ratio", "overall"):
        if key in s:
            value = s[key]
            if isinstance(value, dict):
                value = "；".join(f"{k} {v}" for k, v in value.items())
            lines.append(f"| {key} | {value} |")
    lines += ["", "## 2. 阻断项", ""]
    lines += [f"- {x}" for x in report.get("blocking") or []] or ["无。"]
    lines += ["", "## 3. 卡片缺口（Top 20）", "",
              "| 卡片 | 层级 | 字符 | 单元 | 缺失槽位 | 其他缺口 |",
              "|---|---|---:|---:|---|---|"]
    bad = [c for c in report.get("cards", []) if not c["pass"]][:20]
    for c in bad:
        missing = "、".join(SLOT_LABEL[x] for x in c["missing_slots"]) or "—"
        other = "；".join(d for d in c["deficits"] if not d.startswith("缺槽位")) or "—"
        lines.append(f"| {c['id']} | {c['tier_label']} | {c['chars']} | {c['units']} | {missing} | {other} |")
    if not bad:
        lines.append("| — | — | — | — | — | — |")
    lines += ["", "## 4. 模块缺口", "",
              "| 模块 | 缺块 | 表格 | 展开区 | Callout | 自测 |",
              "|---|---|---:|---:|---:|---:|"]
    for m in report.get("modules", []):
        missing = "、".join(MODULE_LABEL[b] for b in m["missing_blocks"]) or "—"
        lines.append(f"| {m['id']} {m['name']} | {missing} | {m['tables']} | "
                     f"{m['expand_blocks']} | {m['callouts']} | {m['selftests']} |")
    if not report.get("modules"):
        lines.append("| — | — | — | — | — | — |")
    lines += [
        "",
        "## 5. 判定口径",
        "",
        "- 九个学习槽位：定位、机制、识别、诊断、处置、鉴别、易错、记忆钩子、自测；掌握级另需案例。",
        "- 详细 ≠ 字数：正文/信息单元是下限，超长会提示拆分（认知负荷）。",
        "- 自测必须能在附录中找到答案；无答案不算通过。",
        "- 本报告只读产物，不修改复习资料。",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    _configure_stdio()
    ap = argparse.ArgumentParser(description="复习资料详细度契约门禁（HC-26）")
    ap.add_argument("--md", required=True, help="主复习资料 MD")
    ap.add_argument("--mode", choices=["auto", "teacher_keypoint", "course_schedule", "module"],
                    default="auto")
    ap.add_argument("--profile", default="release_teacher_keypoint",
                    choices=["pilot", "release_teacher_keypoint", "release_teaching_plan"])
    ap.add_argument("--policy", default=str(BASE / "scripts/quality_policy.json"))
    ap.add_argument("--subject", default="ent")
    ap.add_argument("--json-out", default="")
    ap.add_argument("--md-out", default="")
    ap.add_argument("--advisory", action="store_true",
                    help="FAIL 不返回非零退出码（仅报告）")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    md_path = Path(args.md)
    if not md_path.exists():
        print(f"[ERROR] 复习资料不存在：{md_path}", file=sys.stderr)
        return 2

    md_text = read_text(md_path)
    mode = detect_mode(md_text, args.mode)
    th = load_thresholds(args.profile, Path(args.policy))

    cards, modules = parse_cards(md_text)
    units = parse_schedule_units(md_text) if mode == "course_schedule" else []
    answer_keys = selftest_answer_keys(md_text)
    report = evaluate(cards, modules, units, mode, th, answer_keys)
    report.update({
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "subject": args.subject,
        "profile": args.profile,
        "md_path": str(md_path),
        "thresholds": th,
    })

    try:
        from jsonschema import validate as js_validate
        schema_path = BASE / "schemas/review_detail.schema.json"
        if schema_path.exists():
            js_validate(report, read_json(schema_path))
    except ImportError:
        pass
    except Exception as exc:
        print(f"[FAIL] 详细度报告 schema 校验失败：{exc}", file=sys.stderr)
        return 2

    if args.md_out:
        write_text(Path(args.md_out), render_md(report))
    if args.json_out:
        write_json(Path(args.json_out), report)

    s = report["summary"]
    if not args.quiet:
        print(f"=== 复习资料详细度门禁（HC-26）｜{report['mode']}｜{args.profile} ===")
        for key in ("cards", "modules", "content_chars", "avg_chars", "card_slot_score",
                    "card_pass_ratio", "core_slot_ratio", "selftest_answer_ratio",
                    "module_block_ratio", "overall", "status"):
            if key in s:
                print(f"  {key}: {s[key]}")
        for x in report["blocking"]:
            print(f"  [BLOCK] {x}")
        if args.json_out:
            print(f"  JSON: {args.json_out}")
        if args.md_out:
            print(f"  MD  : {args.md_out}")

    if s["status"] == "FAIL" and not args.advisory:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
