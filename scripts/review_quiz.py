#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""review_quiz.py — 从 HC-26 复习资料 MD 抽取「卡内自测」题目与附录五答案。

设计边界：
- 只抽取卡片内 `<b>🔄 自测</b>` 的原子小问（1 卡 N 问 → N 个 item）。
- 答案只认附录五表格；不生成、不改写、不推测。
- 输出为 JSON 数据岛，供 render_review.py --quiz 内联进自包含 HTML。
- 任何「题目数 ≠ 答案数」都进入 warnings，并由 check_quiz_parity.py 阻断。

用法：
    python scripts/review_quiz.py --md <主复习资料.md> --json-out <items.json>
    python scripts/review_quiz.py --md <主复习资料.md> --report-out <report.md>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"
CIRCLED_CLASS = "[" + CIRCLED + "]"
CIRCLED_SPLIT = re.compile(CIRCLED_CLASS)
CARD_RE = re.compile(
    r"^####\s*(?P<tier>🔴|🟡|🟢)?\s*(?P<card>K-[A-Z0-9]+-\d+)\s*[｜|]\s*(?P<rest>.+?)\s*$",
    re.M,
)
TIER_MAP = {"🔴": "core", "🟡": "familiar", "🟢": "aware"}


@dataclass
class Card:
    card_id: str
    module: str
    tier: str
    title: str
    page: str
    keypoints: list[int] = field(default_factory=list)
    selftest: str = ""
    module_name: str = ""


@dataclass
class AnswerRow:
    qnum: int | None
    card_id: str
    answers: list[str]
    raw: str


def _split_circled(text: str) -> list[str]:
    """按 ①②③… 切分；没有编号时返回单段。"""
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in CIRCLED_SPLIT.split(text)]
    parts = [p for p in parts if p]
    if len(parts) <= 1:
        return [text]
    return parts


def _clean_answer(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^答\s*[：:]\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_question(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"（答案见附录五）\s*$", "", text).strip()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_heading(rest: str) -> tuple[str, str, list[int]]:
    """从 `标题（教师重点第3、6条｜P285-287）` 拆出标题 / 页码 / 重点条号。"""
    rest = rest.strip()
    meta = ""
    title = rest
    if rest.endswith("）") and "（" in rest:
        title, meta = rest.rsplit("（", 1)
        title = title.strip()
        meta = meta[:-1].strip()
    page = ""
    pm = re.search(r"P\d+(?:\s*[-–—]\s*\d+)?(?:\s*[、,，]\s*P?\d+(?:\s*[-–—]\s*\d+)?)*", meta)
    if pm:
        page = pm.group(0).replace(" ", "")
    keypoints: list[int] = []
    km = re.search(r"第\s*([0-9、,，\s]+?)\s*条", meta)
    if km:
        keypoints = [int(x) for x in re.findall(r"\d+", km.group(1))]
    return title, page, keypoints


def parse_cards(md_text: str) -> tuple[list[Card], list[str]]:
    warnings: list[str] = []
    matches = list(CARD_RE.finditer(md_text))
    cards: list[Card] = []

    # 记录每个卡片标题之前最近的模块名（## 模块N：xxx）
    module_names: dict[str, str] = {}
    for m in re.finditer(r"^##\s*模块\s*(\d+)\s*[：:]\s*(.+?)\s*$", md_text, re.M):
        module_names[f"M{int(m.group(1)):02d}"] = m.group(2).strip()

    for idx, m in enumerate(matches):
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(md_text)
        block = md_text[start:end]
        # 截断到下一个 H2/H3，避免把模块尾部的主动回忆/小结吞进卡片块
        cut = re.search(r"^#{2,3}\s+", block[len(m.group(0)):], re.M)
        if cut:
            block = block[: len(m.group(0)) + cut.start()]

        card_id = m.group("card")
        tier = TIER_MAP.get(m.group("tier") or "", "core")
        if not m.group("tier"):
            warnings.append(f"{card_id}: 标题缺少分级 emoji，已按 core 处理")
        title, page, keypoints = _parse_heading(m.group("rest"))
        module = re.search(r"K-(M\d+)-\d+", card_id)
        module_id = module.group(1) if module else ""
        selftest_match = re.search(r"<b>🔄 自测</b>：(.+?)(?:（答案见附录五）|$)", block, re.S)
        selftest = _clean_question(selftest_match.group(1)) if selftest_match else ""
        if not selftest:
            warnings.append(f"{card_id}: 未找到自测行")
        cards.append(
            Card(
                card_id=card_id,
                module=module_id,
                tier=tier,
                title=title,
                page=page,
                keypoints=keypoints,
                selftest=selftest,
                module_name=module_names.get(module_id, ""),
            )
        )
    return cards, warnings


def parse_appendix(md_text: str) -> tuple[list[AnswerRow], list[str]]:
    warnings: list[str] = []
    start = md_text.find("## 附录五")
    if start < 0:
        return [], ["未找到「## 附录五」章节"]
    appendix = md_text[start:]
    current_module = ""
    rows: list[AnswerRow] = []
    for line in appendix.splitlines():
        line = line.strip()
        if line.startswith("### "):
            current_module = line[4:].strip()
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        if cells[0] in {"题", "#", "序号"}:
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        qnum = int(cells[0]) if cells[0].isdigit() else None
        card_id = cells[2].strip()
        if not re.match(r"K-[A-Z0-9]+-\d+", card_id):
            continue
        answers = [_clean_answer(x) for x in _split_circled(cells[1])]
        if not answers:
            warnings.append(f"{current_module} 第{cells[0]}行: 答案为空")
            continue
        rows.append(AnswerRow(qnum=qnum, card_id=card_id, answers=answers, raw=line))
    return rows, warnings


def _choose_row(rows: list[AnswerRow], n_questions: int) -> AnswerRow | None:
    if not rows:
        return None
    same = [r for r in rows if len(r.answers) == n_questions]
    if same:
        return same[0]
    # 退化：选答案数最接近的，但记录 warning 由调用方处理
    return sorted(rows, key=lambda r: abs(len(r.answers) - n_questions))[0]


def _tags_for(q: str, a: str, card: Card) -> list[str]:
    tags: list[str] = []
    text = q + " " + a
    if re.search(r"\d|mmHg|℃|次/分|小时|分钟|秒|%|ml|L\b|J\b|cm\b", text):
        tags.append("数字锚")
    if re.search(r"禁忌|禁用|不宜|禁止|严禁|不能|错误|易错", text):
        tags.append("易错")
    if re.search(r"鉴别|区别|区分|与.+不同|最可能|首选", text):
        tags.append("鉴别/决策")
    if re.search(r"机制|为什么|因为|导致|引起", text):
        tags.append("机制")
    if not tags:
        tags.append("概念")
    return tags[:3]


def build_items(cards: list[Card], rows: list[AnswerRow]) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    by_card: dict[str, list[AnswerRow]] = defaultdict(list)
    for row in rows:
        by_card[row.card_id].append(row)

    items: list[dict] = []
    seen_ids: set[str] = set()
    for card in cards:
        questions = _split_circled(card.selftest)
        questions = [_clean_question(q) for q in questions if _clean_question(q)]
        if not questions:
            continue
        chosen = _choose_row(by_card.get(card.card_id, []), len(questions))
        if chosen is None:
            warnings.append(f"{card.card_id}: 附录五无答案行（{len(questions)} 问）")
            continue
        if len(chosen.answers) != len(questions):
            warnings.append(
                f"{card.card_id}: 题目 {len(questions)} 问 / 答案 {len(chosen.answers)} 段，需人工核对"
            )
        for i, q in enumerate(questions, start=1):
            a = chosen.answers[i - 1] if i <= len(chosen.answers) else ""
            if not a:
                warnings.append(f"{card.card_id}#{i}: 答案缺失")
                continue
            item_id = f"{card.card_id}#{i}"
            if item_id in seen_ids:
                warnings.append(f"{item_id}: 重复 item_id")
                continue
            seen_ids.add(item_id)
            src = f"附录五 {card.module} 第{chosen.qnum}题" if chosen.qnum else f"附录五 {card.module}"
            if card.page:
                src += f" · {card.page}"
            items.append(
                {
                    "item_id": item_id,
                    "card_id": card.card_id,
                    "module": card.module,
                    "module_name": card.module_name,
                    "tier": card.tier,
                    "q_index": i,
                    "q": q,
                    "a": a,
                    "src": src,
                    "page": card.page,
                    "keypoints": card.keypoints,
                    "tags": _tags_for(q, a, card),
                }
            )
    return items, warnings


def build_payload(md_text: str, md_path: str = "") -> dict:
    cards, card_warnings = parse_cards(md_text)
    rows, row_warnings = parse_appendix(md_text)
    items, item_warnings = build_items(cards, rows)
    warnings = card_warnings + row_warnings + item_warnings

    card_questions = sum(len(_split_circled(c.selftest)) for c in cards)
    per_module_cards = Counter(c.module for c in cards)
    per_module_items = Counter(i["module"] for i in items)
    per_tier_items = Counter(i["tier"] for i in items)
    payload = {
        "schema_version": 1,
        "generator": "review_quiz.py",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_md": md_path,
        "content_hash": hashlib.sha1(md_text.encode("utf-8")).hexdigest()[:12],
        "stats": {
            "cards": len(cards),
            "questions": card_questions,
            "items": len(items),
            "modules": len(per_module_cards),
            "per_module_cards": dict(sorted(per_module_cards.items())),
            "per_module_items": dict(sorted(per_module_items.items())),
            "per_tier_items": dict(sorted(per_tier_items.items())),
            "missing_answers": len([w for w in warnings if "答案缺失" in w or "无答案行" in w]),
            "mismatched": len([w for w in warnings if "需人工核对" in w]),
        },
        "warnings": warnings,
        "items": items,
    }
    return payload


def _configure_stdio() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main() -> int:
    _configure_stdio()
    parser = argparse.ArgumentParser(description="从 HC-26 复习资料抽取卡内自测题")
    parser.add_argument("--md", required=True, help="主复习资料 Markdown")
    parser.add_argument("--json-out", help="输出 items JSON")
    parser.add_argument("--report-out", help="输出人读报告 Markdown")
    args = parser.parse_args()

    md_path = Path(args.md)
    if not md_path.exists():
        print(f"[FAIL] 文件不存在：{md_path}", file=sys.stderr)
        return 2
    md_text = md_path.read_text(encoding="utf-8")
    payload = build_payload(md_text, str(md_path))

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] items JSON：{out}")

    if args.report_out:
        s = payload["stats"]
        lines = [
            "# 复习资料卡内自测题抽取报告",
            "",
            f"- 源文件：`{md_path}`",
            f"- 内容哈希：`{payload['content_hash']}`",
            f"- 卡片：{s['cards']} · 模块：{s['modules']} · 题目：{s['items']}",
            f"- 每模块卡片：{s['per_module_cards']}",
            f"- 每模块题目：{s['per_module_items']}",
            f"- 分级题目：{s['per_tier_items']}",
            f"- 缺失答案：{s['missing_answers']} · 题答数不一致：{s['mismatched']}",
            "",
            "## 警告",
            "",
        ]
        lines.extend([f"- {w}" for w in payload["warnings"]] or ["- 无"])
        out = Path(args.report_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[OK] 抽取报告：{out}")

    s = payload["stats"]
    print(
        f"卡片 {s['cards']} / 题目 {s['items']} / 模块 {s['modules']} / "
        f"缺失答案 {s['missing_answers']} / 不一致 {s['mismatched']}"
    )
    if payload["warnings"]:
        for w in payload["warnings"][:20]:
            print(f"  [WARN] {w}")
        if len(payload["warnings"]) > 20:
            print(f"  ... 共 {len(payload['warnings'])} 条警告")
    return 1 if (s["missing_answers"] or s["mismatched"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
