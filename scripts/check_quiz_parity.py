#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_quiz_parity.py — 刷题版 HTML 发布门禁。

校验：
1. HTML 数据岛的题目与 MD 重抽取结果 1:1（ID、题干、答案、来源）。
2. 每道题都能回链到真实卡片锚点 card-K-...
3. 单文件零外部资源（无 script src / link href / @import / url(http）。
4. 页内 ID 不重复；刷题容器、键盘/读屏、打印/减弱动效样式存在。
5. 配置的 build_id 与 MD 内容哈希一致，考试日期格式有效。

用法：
    python scripts/check_quiz_parity.py \
      --md "复习资料/急诊与灾难医学教师重点版/急诊与灾难医学教师重点版_主复习资料.md" \
      --html "大四上/复习资料/急诊与灾难医学教师重点版_刷题版.html"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from review_quiz import build_payload


def _fail(msg: str, fails: list[str]) -> None:
    fails.append(msg)


def check(md_path: Path, html_path: Path) -> tuple[list[str], dict]:
    fails: list[str] = []
    if not md_path.exists():
        return [f"MD 不存在：{md_path}"], {}
    if not html_path.exists():
        return [f"HTML 不存在：{html_path}"], {}

    md_text = md_path.read_text(encoding="utf-8")
    expected = build_payload(md_text, str(md_path))
    expected_items = expected.get("items") or []
    if not expected_items:
        return ["MD 未抽取到任何题目"], {}

    html = html_path.read_text(encoding="utf-8")

    # ---- 数据岛 ----
    m_items = re.search(r'<script type="application/json" id="quiz-items">(.*?)</script>', html, re.S)
    m_config = re.search(r'<script type="application/json" id="quiz-config">(.*?)</script>', html, re.S)
    if not m_items:
        return ["HTML 缺少 quiz-items 数据岛"], {}
    if not m_config:
        return ["HTML 缺少 quiz-config 数据岛"], {}
    try:
        actual_items = json.loads(m_items.group(1))
    except Exception as exc:
        return [f"quiz-items JSON 解析失败：{exc}"], {}
    try:
        config = json.loads(m_config.group(1))
    except Exception as exc:
        return [f"quiz-config JSON 解析失败：{exc}"], {}

    if not isinstance(actual_items, list):
        return ["quiz-items 不是数组"], {}
    if len(actual_items) != len(expected_items):
        _fail(f"题量不一致：MD {len(expected_items)} / HTML {len(actual_items)}", fails)

    # ---- 1:1 内容对账 ----
    by_id = {str(x.get("item_id")): x for x in actual_items}
    if len(by_id) != len(actual_items):
        _fail("HTML 题目 item_id 存在重复", fails)
    for exp in expected_items:
        item_id = exp["item_id"]
        got = by_id.get(item_id)
        if not got:
            _fail(f"HTML 缺少题目 {item_id}", fails)
            continue
        for key in ("card_id", "module", "tier", "q", "a", "src"):
            if str(got.get(key, "")) != str(exp.get(key, "")):
                _fail(f"{item_id} 字段 {key} 与 MD 不一致", fails)

    # ---- 卡片锚点 ----
    card_ids = {x["card_id"] for x in expected_items}
    anchors = set(re.findall(r'id="card-(K-[A-Z0-9]+-\d+)"', html))
    missing_anchors = sorted(card_ids - anchors)
    if missing_anchors:
        _fail(f"缺少卡片锚点：{', '.join(missing_anchors[:10])}", fails)

    # ---- 页内 ID 唯一 ----
    html_ids = re.findall(r'\sid="([^"]+)"', html)
    dups = sorted({x for x in html_ids if html_ids.count(x) > 1})
    if dups:
        _fail(f"HTML 重复 id：{', '.join(dups[:10])}", fails)

    # ---- 零外部资源 ----
    if re.search(r'<script[^>]+src=', html):
        _fail("存在外部 script src", fails)
    if re.search(r'<link[^>]+href=', html):
        _fail("存在外部 link href", fails)
    if "@import" in html:
        _fail("存在 CSS @import", fails)
    if re.search(r'url\(\s*["\']?https?://', html):
        _fail("存在外部 CSS url()", fails)

    # ---- 交互/无障碍/打印 ----
    required = {
        "quiz-overlay": 'id="quiz-overlay"',
        "quiz-toggle": 'id="quiz-toggle"',
        "quiz-answer": 'id="quiz-answer"',
        "quiz-rate": 'id="quiz-rate"',
        "quiz-file": 'id="quiz-file"',
        "aria-live": 'aria-live="polite"',
        "dialog-role": 'role="dialog"',
        "print-css": "@media print",
        "reduced-motion": "prefers-reduced-motion",
    }
    for name, needle in required.items():
        if needle not in html:
            _fail(f"缺少 {name}（{needle}）", fails)

    # ---- 配置 ----
    if config.get("build_id") != expected.get("content_hash"):
        _fail("quiz-config.build_id 与 MD 内容哈希不一致", fails)
    exam_date = str(config.get("exam_date", ""))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", exam_date):
        _fail(f"exam_date 格式无效：{exam_date}", fails)
    if int(config.get("daily_new", 0) or 0) < 0:
        _fail("daily_new 不能为负", fails)
    if int(config.get("total_items", -1)) != len(expected_items):
        _fail("quiz-config.total_items 与题量不一致", fails)

    info = {
        "items": len(expected_items),
        "cards": len(card_ids),
        "modules": len({x["module"] for x in expected_items}),
        "build_id": config.get("build_id"),
        "exam_date": exam_date,
        "size_kb": round(len(html.encode("utf-8")) / 1024, 1),
    }
    return fails, info


def main() -> int:
    parser = argparse.ArgumentParser(description="刷题版 HTML 发布门禁")
    parser.add_argument("--md", required=True)
    parser.add_argument("--html", required=True)
    args = parser.parse_args()
    fails, info = check(Path(args.md), Path(args.html))
    if fails:
        print(f"[FAIL] quiz parity：{len(fails)} 项")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(
        f"[PASS] quiz parity：{info['items']} 题 / {info['cards']} 卡 / "
        f"{info['modules']} 模块 / {info['size_kb']} KB / 考试 {info['exam_date']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
