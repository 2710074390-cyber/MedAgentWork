#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_obsidian_theme.py — 浏览器实测 Obsidian 树主题系统（Playwright + 系统 Chrome）"""
import io
import sys
import json
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent / "最终产物"
SHOT = Path(__file__).resolve().parent.parent / "reports" / "theme_shots"
SHOT.mkdir(parents=True, exist_ok=True)

EXAM = BASE / "精神病学押题卷_2026.html"
INDEX = BASE / "index.html"


def url_of(p: Path) -> str:
    return p.resolve().as_uri()


def js(page, code):
    return page.evaluate(code)


def main():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Users\38063\AppData\Local\Google\Chrome\Application\chrome.exe",
            headless=True,
        )
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        # ---------- 1. 押题卷：默认主题 ----------
        page.goto(url_of(EXAM), wait_until="networkidle")
        page.wait_for_timeout(600)
        results["exam_default_theme"] = js(page, "document.documentElement.getAttribute('data-theme')")
        results["exam_default_qcount"] = js(page, "document.querySelectorAll('.question').length")
        results["exam_btn_count"] = js(page, "document.querySelectorAll('#topbar button').length")
        page.screenshot(path=str(SHOT / "01_exam_default.png"))

        # ---------- 2. 切换 Obsidian 主题 ----------
        page.click("#btn-theme")
        page.wait_for_timeout(400)
        results["exam_obsidian_theme"] = js(page, "document.documentElement.getAttribute('data-theme')")
        results["exam_obsidian_bg"] = js(page, "getComputedStyle(document.body).backgroundColor")
        results["exam_obsidian_font"] = js(page, "getComputedStyle(document.body).fontFamily.split(',')[0]")
        results["exam_btn_icon"] = js(page, "document.getElementById('btn-theme').textContent")
        page.screenshot(path=str(SHOT / "02_exam_obsidian.png"))

        # ---------- 3. 树形侧边栏 ----------
        page.click("#btn-tree")
        page.wait_for_timeout(500)
        results["tree_open"] = js(page, "document.documentElement.getAttribute('data-tree')")
        results["tree_panel_visible"] = js(page, "document.getElementById('tree-panel').getBoundingClientRect().left >= -1")
        results["tree_groups"] = js(page, "[...document.querySelectorAll('.tree-group .g-name')].map(e=>e.textContent)")
        results["tree_items"] = js(page, "document.querySelectorAll('.t-item').length")
        results["tree_first_item"] = js(page, "document.querySelector('.t-item') ? document.querySelector('.t-item .t-stem').textContent.slice(0,20) : null")
        results["tree_bg"] = js(page, "getComputedStyle(document.getElementById('tree-panel')).backgroundColor")
        page.screenshot(path=str(SHOT / "03_tree_obsidian.png"))

        # ---------- 4. 树条目点击跳转 ----------
        before_scroll = js(page, "window.scrollY")
        # 展开最后一个题型组，点第一个题目
        js(page, "document.querySelectorAll('.tree-group')[document.querySelectorAll('.tree-group').length-1].classList.add('open')")
        page.click(".tree-group:last-of-type .t-item")
        page.wait_for_timeout(1200)
        after_scroll = js(page, "window.scrollY")
        results["tree_click_scrolled"] = after_scroll > before_scroll
        results["tree_click_flash"] = js(page, "!!document.querySelector('.tree-flash')")
        results["tree_closed_after_click"] = js(page, "document.documentElement.getAttribute('data-tree') === null || document.documentElement.getAttribute('data-tree') === '0'")

        # ---------- 5. localStorage 持久化（刷新后主题保持） ----------
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(600)
        results["persist_theme"] = js(page, "document.documentElement.getAttribute('data-theme')")
        results["persist_errors"] = errors[:3]

        # ---------- 6. 入口页（先清 localStorage 测干净状态） ----------
        page.goto(url_of(INDEX), wait_until="networkidle")
        page.evaluate("localStorage.removeItem('maq_theme'); location.reload()")
        page.wait_for_timeout(600)
        results["index_default_theme"] = js(page, "document.documentElement.getAttribute('data-theme')")
        results["index_has_fab"] = js(page, "!!document.getElementById('theme-fab')")
        page.screenshot(path=str(SHOT / "04_index_default.png"))
        page.click("#theme-fab")
        page.wait_for_timeout(400)
        results["index_obsidian_theme"] = js(page, "document.documentElement.getAttribute('data-theme')")
        results["index_obsidian_bg"] = js(page, "getComputedStyle(document.body).backgroundColor")
        results["index_obsidian_card_bg"] = js(page, "getComputedStyle(document.querySelector('.card')).backgroundColor")
        page.screenshot(path=str(SHOT / "05_index_obsidian.png"))

        browser.close()

    print(json.dumps(results, ensure_ascii=False, indent=2))
    ok = (
        results.get("exam_obsidian_theme") == "obsidian"
        and results.get("tree_open") == "1"
        and results.get("tree_items", 0) > 0
        and results.get("tree_click_scrolled") is True
        and results.get("persist_theme") == "obsidian"
        and results.get("index_obsidian_theme") == "obsidian"
        and not results.get("persist_errors")
    )
    print("\n=== 验证结果:", "PASS ✔" if ok else "FAIL ✘", "===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
