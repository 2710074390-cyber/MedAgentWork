#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_site.py — 线上站（仓库版）Obsidian 第四主题浏览器实测"""
import io, sys, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
EXAM = ROOT / "大三下" / "押题卷" / "精神病学押题卷_2026.html"


def main():
    r = {}
    with sync_playwright() as p:
        b = p.chromium.launch(
            executable_path=r"C:\Users\38063\AppData\Local\Google\Chrome\Application\chrome.exe",
            headless=True,
        )
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        # ---- 1. index 四主题 ----
        pg.goto(ROOT.joinpath("index.html").resolve().as_uri(), wait_until="networkidle")
        pg.wait_for_timeout(400)
        r["index_theme_btns"] = pg.evaluate("[...document.querySelectorAll('.theme-btn')].map(b=>b.dataset.t)")
        pg.click('.theme-btn[data-t="obsidian"]')
        pg.wait_for_timeout(300)
        r["index_obsidian_theme"] = pg.evaluate("document.documentElement.getAttribute('data-theme')")
        r["index_obsidian_bg"] = pg.evaluate("getComputedStyle(document.body).backgroundColor")
        r["index_obsidian_card"] = pg.evaluate("getComputedStyle(document.querySelector('.card')).backgroundColor")
        r["index_obsidian_hero"] = pg.evaluate("getComputedStyle(document.querySelector('.masthead h1')).color")

        # ---- 2. 跨页继承：直接打开押题卷（新 tab，同 context 共享 localStorage） ----
        pg2 = ctx.new_page()
        pg2.goto(EXAM.resolve().as_uri(), wait_until="networkidle")
        pg2.wait_for_timeout(800)
        r["exam_inherit_theme"] = pg2.evaluate("document.documentElement.getAttribute('data-theme')")
        r["exam_qcount"] = pg2.evaluate("document.querySelectorAll('.question').length")

        # ---- 3. 押题卷树导航 ----
        pg2.click("#btn-tree")
        pg2.wait_for_timeout(500)
        r["tree_open"] = pg2.evaluate("document.documentElement.getAttribute('data-tree')")
        r["tree_groups"] = pg2.evaluate("[...document.querySelectorAll('.tree-group .g-name')].map(e=>e.textContent)")
        r["tree_items"] = pg2.evaluate("document.querySelectorAll('.t-item').length")
        before = pg2.evaluate("window.scrollY")
        pg2.evaluate("document.querySelectorAll('.tree-group').forEach(function(g){g.classList.remove('open')});var gs=document.querySelectorAll('.tree-group');gs[gs.length-1].classList.add('open');")
        pg2.wait_for_timeout(300)
        pg2.click(".tree-group.open .t-item >> nth=0")
        pg2.wait_for_timeout(1000)
        r["tree_click_scrolled"] = pg2.evaluate("window.scrollY") > before
        r["tree_click_flash"] = pg2.evaluate("!!document.querySelector('.tree-flash')")

        # ---- 4. 押题卷切换回默认（◐）后刷新保持 ----
        pg2.evaluate("window.scrollTo(0,0)")
        pg2.wait_for_timeout(600)  # topbar 恢复显示
        pg2.click("#btn-theme")
        pg2.wait_for_timeout(300)
        r["exam_toggle_back"] = pg2.evaluate("document.documentElement.getAttribute('data-theme')")  # null=default
        pg2.reload(wait_until="networkidle")
        pg2.wait_for_timeout(600)
        r["exam_reload_after_toggle"] = pg2.evaluate("document.documentElement.getAttribute('data-theme')")
        # 清掉测试残留，恢复干净状态
        pg2.evaluate("localStorage.removeItem('maw-theme')")

        # ---- 5. 三个原主题回归 ----
        pg.click('.theme-btn[data-t="classic"]')
        pg.wait_for_timeout(300)
        r["classic_bg"] = pg.evaluate("getComputedStyle(document.body).backgroundColor")
        pg.click('.theme-btn[data-t="night"]')
        pg.wait_for_timeout(300)
        r["night_bg"] = pg.evaluate("getComputedStyle(document.body).backgroundColor")

        r["js_errors"] = errors[:3]
        b.close()

    print(json.dumps(r, ensure_ascii=False, indent=2))
    ok = (
        r.get("index_theme_btns") == ["classic", "modern", "night", "obsidian"]
        and r.get("index_obsidian_theme") == "obsidian"
        and r.get("index_obsidian_bg") == "rgb(32, 32, 32)"
        and r.get("exam_inherit_theme") == "obsidian"
        and r.get("tree_open") == "1"
        and r.get("tree_items", 0) > 0
        and r.get("tree_click_scrolled") is True
        and r.get("tree_click_flash") is True
        and r.get("exam_reload_after_toggle") != "obsidian"
        and r.get("night_bg") != "rgb(32, 32, 32)"
        and not r.get("js_errors")
    )
    print("\n=== 验证结果:", "PASS ✔" if ok else "FAIL ✘", "===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
