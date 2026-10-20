#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_mobile.py — 站点移动端真机尺寸验证门禁（2026-10-20 新增）

为什么需要它
    站点的主要读者是手机上的医学生，但此前的移动端验证只在浏览器沙箱能给的
    一个宽度（约 314px）上做过「无横向溢出」这一项，覆盖不住：
    触控目标尺寸、iOS 聚焦自动放大、首屏可操作性、导航重叠、模态溢出。
    本脚本用 Playwright 在真实设备视口尺寸下逐项机械化核对，把"看着还行"
    变成"可复算的结论"。

验证矩阵（宽×高，默认 6 档；--quick 只跑前 3 档）
    360×640   小屏安卓（基线下限）
    375×812   iPhone SE3 / 13 mini
    390×844   iPhone 14 / 15
    414×896   iPhone Plus
    430×932   iPhone 15 Pro Max
    768×1024  平板竖屏
  × 3 条路由（/#/home、/#/s2、/#/s1 学期视图）

检查项
    [FAIL] MOBILE-OVERFLOW   水平溢出：documentElement.scrollWidth > innerWidth，
                             并列出越界元素（右缘越界 / 左缘为负）
    [FAIL] MOBILE-TAP        控件触控目标 < 44px（Apple HIG / ColorOS 人因基线）：
                             仅统计"控件"类元素（button / [role=tab] / 输入框 /
                             带 .btn 的链接 / 图标按钮 / 芯片 / 搜索清空），
                             纯正文内联文字链接不在此列
    [FAIL] MOBILE-ZOOM       iOS 聚焦自动放大风险：输入框/下拉/文本域的
                             computed font-size < 16px
    [FAIL] MOBILE-CONSOLE    页面 console error / pageerror（已剔除 /api/visits
                             这类"静态预览环境必然 404"的噪声）
    [WARN] MOBILE-FIRSTVIEW  首页搜索框与至少 1 条资源行是否落在首屏内
                             （≤430px 才判；超出首屏只是提示，不阻塞）
    [WARN] MOBILE-NAV        顶部导航子元素互相重叠

用法
    python scripts/check_mobile.py                 # 全矩阵
    python scripts/check_mobile.py --quick         # 只跑 360/375/390 三档，快
    python scripts/check_mobile.py --width 390     # 只跑指定宽度
    python scripts/check_mobile.py --json          # 机器可读输出

退出码: 0 = PASS（含 SKIPPED 降级）；1 = FAIL；2 = 环境不可用（显式 SKIPPED）

依赖
    Playwright（Python 版）+ 任一 Chromium 通道（bundled / msedge / chrome）。
    国内环境如缺浏览器内核，请用 channel 走本机已装 Edge/Chrome，避免下载：
        python scripts/check_mobile.py --channel msedge
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent

VIEWPORTS = [
    (360, 640, "小屏安卓"),
    (375, 812, "iPhone SE3 / 13 mini"),
    (390, 844, "iPhone 14 / 15"),
    (414, 896, "iPhone Plus"),
    (430, 932, "iPhone 15 Pro Max"),
    (768, 1024, "平板竖屏"),
]
ROUTES = [("/", "home"), ("/#/s2", "大三下"), ("/#/s1", "大四上")]
TAP_MIN = 44          # Apple HIG / ColorOS 人因研究基线（pt）
ZOOM_MIN_FS = 16.0    # iOS 聚焦自动放大阈值（px）
# 引擎噪声白名单：这些是站点「已优雅降级」的路径，不是页面缺陷——
#   /api/visits           静态预览环境没有 Functions，必然 404（线上有 KV，正常）
#   api.github.com        MedKit 版本号查询；国内常被限流/不可达，代码已回落
#                         「最新版见 GitHub」文案，属设计内的失败分支
CONSOLE_NOISE = ("/api/visits", "favicon", "api.github.com")

# 触控目标只算"控件"，正文内联文字链接豁免（HIG 的 44pt 针对可点控件）
TAP_SELECTOR = (
    "button,[role=tab],input[type=search],input[type=text],select,textarea,"
    "a.btn,.icon-act,.icon-btn,.chip-btn,.cap-more,.term-copy,.desk-clear,.search-clear,.m-btn"
)

PROBE_JS = """() => {
  const de = document.documentElement;
  const W = window.innerWidth, H = window.innerHeight;
  const describe = el => {
    const c = el.className && typeof el.className === 'string'
      ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '';
    const t = (el.textContent || '').trim().slice(0, 14);
    return el.tagName.toLowerCase() + c + (t ? ' «' + t + '»' : '');
  };
  // 位于「横向滚动容器」（如芯片横滑区、宽表横滑区）内的元素允许超出视口——
  // 那是设计好的可横滑区域，不算页面水平溢出。
  const inHScroller = el => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === 'auto' || ox === 'scroll') return true;
    }
    return false;
  };

  // 1) 水平溢出：越界元素清单
  const over = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.offsetParent === null && getComputedStyle(el).position !== 'fixed') continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    if (r.right > W + 1 || r.left < -1) {
      if (inHScroller(el)) continue;
      over.push({ who: describe(el), left: Math.round(r.left), right: Math.round(r.right) });
      if (over.length >= 8) break;
    }
  }

  // 2) 触控目标（输入框按"它所在的容器"实测——真正被手指点的是 label / .search / .desk-input）
  const target = el => (el.matches('input,select,textarea')
    ? (el.closest('label, .search, .desk-input') || el) : el);
  const small = [];
  for (const raw of document.querySelectorAll(`%TAP_SELECTOR%`)) {
    const el = target(raw);
    if (el.offsetParent === null) continue;
    const r = el.getBoundingClientRect();
    if (r.height < %TAP_MIN% - 1) {
      small.push({ who: describe(el), h: Math.round(r.height), w: Math.round(r.width) });
      if (small.length >= 10) break;
    }
  }

  // 3) iOS 聚焦放大风险
  const zoom = [];
  for (const el of document.querySelectorAll('input,select,textarea')) {
    if (el.offsetParent === null) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < %ZOOM_MIN%) zoom.push({ who: describe(el), fontSize: fs });
  }

  // 4) 首屏可操作性（首页看检索台；学期视图看工具条 + 首行）
  const inView = el => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return r.top >= -1 && r.bottom <= H + 1;
  };
  const firstView = {
    search: inView(document.querySelector('.desk-input input') || document.querySelector('.tools .search input')),
    firstRow: inView(document.querySelector('#inv-list .inv-row:not([hidden])')
                 || document.querySelector('.res-list .res-row:not([hidden])')),
  };

  // 5) 导航重叠
  const navBoxes = [];
  for (const el of document.querySelectorAll('.nav-in > * .brand, .nav-in .nav-right, .nav-in .nav-links')) {
    if (el.offsetParent === null) continue;
    const r = el.getBoundingClientRect();
    navBoxes.push({ who: describe(el), left: Math.round(r.left), right: Math.round(r.right) });
  }
  let navOverlap = null;
  for (let i = 0; i < navBoxes.length; i++) {
    for (let j = i + 1; j < navBoxes.length; j++) {
      const a = navBoxes[i], b = navBoxes[j];
      if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2) navOverlap = [a.who, b.who];
    }
  }

  // 6) 粘性筛选条（学期视图）：滚动后是否仍贴在导航下沿，以及它吃掉了多少首屏
  let sticky = null;
  const tools = document.querySelector('.tools');
  if (tools && tools.offsetParent !== null && getComputedStyle(tools).position === 'sticky') {
    const navEl = document.querySelector('.nav');
    const expected = Math.round(navEl ? navEl.getBoundingClientRect().height : 60);
    const natural = Math.round(tools.getBoundingClientRect().top);
    const maxScroll = Math.max(0, (document.scrollingElement || de).scrollHeight - H);
    const targetScroll = Math.min(600, Math.max(0, maxScroll - 40));
    // 站点开了 scroll-behavior:smooth；不临时改 auto 的话，scrollTo 之后立刻读 scrollY
    // 仍是 0（平滑动画还没起步），会把"能不能粘住"测成假失败。
    const prevBehavior = de.style.scrollBehavior;
    de.style.scrollBehavior = 'auto';
    window.scrollTo(0, targetScroll);
    const scrolled = Math.round(window.scrollY);
    const rect = tools.getBoundingClientRect();
    window.scrollTo(0, 0);
    de.style.scrollBehavior = prevBehavior;
    sticky = {
      expected, natural, targetScroll, scrolled,
      actual: Math.round(rect.top), height: Math.round(rect.height),
      ok: scrolled > 0 && Math.abs(rect.top - expected) <= 2,
    };
  }

  // 7) 内容渲染完整性：渲染块被改写后最容易出现的失效是"页面看着完好、其实一行都没渲染"
  const activeView = document.querySelector('.view.active') || document;
  const content = {
    invRows: document.querySelectorAll('#inv-list .inv-row').length,
    viewRows: activeView.querySelectorAll('.res-list .res-row').length,
    deskStat: (document.querySelector('#desk-stat') || {}).textContent || '',
    chips: activeView.querySelectorAll('.chip-btn').length,
  };

  return {
    viewportW: W, viewportH: H, scrollW: de.scrollWidth,
    overflowPx: Math.max(0, de.scrollWidth - W),
    over, small, zoom, firstView, navOverlap, sticky, content,
  };
}"""


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # 静音访问日志
        pass


def serve_repo():
    """在后台线程起一个静态服务器，返回 (base_url, shutdown_fn)。"""
    handler = functools.partial(_QuietHandler, directory=str(ROOT))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_address[1]}", httpd.shutdown


def probe(page, url: str) -> dict:
    errors: list[str] = []

    def on_console(msg):
        loc = msg.location if isinstance(msg.location, dict) else {}
        url = loc.get("url", "") or ""
        # 静态预览环境必然 404 的噪声（如 /api/visits）：按 URL 与文本双路剔除，
        # 因为 Chromium 对失败资源的 console 文案不含 URL，只有 location 里有。
        if any(n in url or n in msg.text for n in CONSOLE_NOISE):
            return
        if msg.type == "error":
            errors.append(f"{msg.text[:160]} @ {url[-48:] if url else '-'}")

    page.on("console", on_console)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {str(e)[:200]}"))
    page.goto(url, wait_until="load", timeout=30000)
    page.wait_for_timeout(450)          # 让 render/reveal 跑完
    data = page.evaluate(
        PROBE_JS.replace("%TAP_SELECTOR%", TAP_SELECTOR)
        .replace("%TAP_MIN%", str(TAP_MIN))
        .replace("%ZOOM_MIN%", str(ZOOM_MIN_FS))
    )
    page.remove_listener("console", on_console)
    data["errors"] = errors
    return data


MODAL_JS = """() => {
  const m = document.getElementById('modal');
  const card = m.querySelector('.modal-card');
  const bar = m.querySelector('.modal-bar');
  const acts = m.querySelector('.m-actions');
  const W = window.innerWidth;
  const r = card ? card.getBoundingClientRect() : null;
  const small = [...m.querySelectorAll('.m-btn')].filter(x => x.offsetParent !== null)
    .map(x => ({ t: (x.textContent || '').trim(), h: Math.round(x.getBoundingClientRect().height) }))
    .filter(x => x.h < 43);
  return {
    opened: m.classList.contains('open'),
    rendered: !!m.querySelector('.md h1, .md h2, .md p'),
    isError: !!m.querySelector('.modal-error'),
    cardW: r ? Math.round(r.width) : 0,
    cardH: r ? Math.round(r.height) : 0,
    cardOverflowPx: r ? Math.max(0, Math.round(r.right) - W) : 0,
    barOverflowPx: bar ? Math.max(0, bar.scrollWidth - bar.clientWidth) : 0,
    smallBtns: small,
    viewportW: W,
  };
}"""


def probe_modal(page, url: str, wait_ms: int = 2000):
    """打开一次「在线阅读」模态：核对是否溢出视口、按钮是否够大、内容有没有渲染出来。"""
    page.goto(url, wait_until="load", timeout=30000)
    page.wait_for_timeout(350)
    hit = page.evaluate(
        """() => {
             const b = [...document.querySelectorAll('[data-act="preview"]')]
               .find(x => x.offsetParent !== null);
             if (!b) return false;
             b.click();
             return true;
           }"""
    )
    if not hit:
        return None
    page.wait_for_timeout(wait_ms)
    return page.evaluate(MODAL_JS)


def main() -> int:
    ap = argparse.ArgumentParser(description="站点移动端真机尺寸验证门禁")
    ap.add_argument("--quick", action="store_true", help="只跑前 3 档视口")
    ap.add_argument("--width", type=int, help="只跑指定宽度（用默认高度）")
    ap.add_argument("--channel", help="Chromium 通道：msedge / chrome（缺省用内置）")
    ap.add_argument("--base", help="直接验证线上站点（跳过本地静态服务器），如 https://med-review-site.pages.dev/")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # 显式降级：环境没有 Playwright
        print(f"⚠ SKIPPED —— 未安装 Playwright（{type(e).__name__}）：{e}")
        print("   安装：python -m pip install playwright -i https://pypi.tuna.tsinghua.edu.cn/simple")
        return 2

    viewports = VIEWPORTS[:3] if args.quick else VIEWPORTS
    if args.width:
        viewports = [(args.width, 844, f"指定 {args.width}px")]

    if args.base:
        base, shutdown = args.base.rstrip("/"), (lambda: None)   # 直连线上，无需本地服务器
    else:
        base, shutdown = serve_repo()
    rows, fails, warns = [], 0, 0

    try:
        with sync_playwright() as p:
            net = ROOT / "index.html"
            if not net.exists():
                print("ERROR —— 找不到 index.html")
                return 2
            try:
                browser = p.chromium.launch(channel=args.channel) if args.channel else p.chromium.launch()
            except Exception as e:
                print(f"⚠ SKIPPED —— 无法启动 Chromium：{str(e)[:160]}")
                print("   可用 --channel msedge 走本机已装 Edge（免下载内核）")
                return 2

            for w, h, label in viewports:
                ctx = browser.new_context(
                    viewport={"width": w, "height": h},
                    device_scale_factor=2, is_mobile=True, has_touch=True,
                )
                page = ctx.new_page()
                for route, rlabel in ROUTES:
                    d = probe(page, base + route)
                    r = {"viewport": f"{w}×{h}", "label": label, "route": rlabel}
                    r.update(d)

                    issues = []
                    if d["overflowPx"] > 0:
                        issues.append(("FAIL", "MOBILE-OVERFLOW",
                                       f"水平溢出 {d['overflowPx']}px"))
                    if d["over"]:
                        issues.append(("FAIL", "MOBILE-OVERFLOW",
                                       "越界元素：" + "；".join(
                                           f"{o['who']}({o['left']}→{o['right']})" for o in d["over"][:4])))
                    if d["small"]:
                        issues.append(("FAIL", "MOBILE-TAP",
                                       f"{len(d['small'])} 个控件 < {TAP_MIN}px：" + "；".join(
                                           f"{s['who']}={s['h']}px" for s in d["small"][:6])))
                    if d["zoom"]:
                        issues.append(("FAIL", "MOBILE-ZOOM",
                                       "iOS 聚焦放大风险：" + "；".join(
                                           f"{z['who']}={z['fontSize']}px" for z in d["zoom"])))
                    if d["errors"]:
                        issues.append(("FAIL", "MOBILE-CONSOLE",
                                       "；".join(d["errors"][:3])))
                    if d["navOverlap"]:
                        issues.append(("FAIL", "MOBILE-NAV",
                                       "导航重叠：" + " × ".join(d["navOverlap"])))
                    if w <= 430 and (d["firstView"]["search"] is False
                                     or d["firstView"]["firstRow"] is False):
                        issues.append(("WARN", "MOBILE-FIRSTVIEW",
                                       f"首屏内：搜索框={d['firstView']['search']} "
                                       f"首行={d['firstView']['firstRow']}"))
                    if d.get("sticky"):
                        st = d["sticky"]
                        if not st["ok"]:
                            issues.append(("FAIL", "MOBILE-STICKY",
                                           f"筛选条未贴住导航下沿（期望 top≈{st['expected']}px，"
                                           f"实测 {st['actual']}px；原位 {st['natural']}px，"
                                           f"滚动 {st['scrolled']}/{st['targetScroll']}px）"))
                        if st["height"] > 120:
                            issues.append(("WARN", "MOBILE-STICKY",
                                           f"常驻筛选条高 {st['height']}px（>120px，占用首屏偏多）"))
                    # 内容渲染完整性：下限阈值（只防"渲染块被改写后一行都没出来"，
                    # 不用精确值——精确值由 check_site_freshness 的数据数组一致性兜住）
                    c = d.get("content") or {}
                    if rlabel == "home":
                        if c.get("invRows", 0) < 28:
                            issues.append(("FAIL", "MOBILE-CONTENT",
                                           f"首页检索台只渲染出 {c.get('invRows')} 行（应≥28）"))
                        if not (c.get("deskStat") or "").strip():
                            issues.append(("FAIL", "MOBILE-CONTENT", "检索台计数文案为空"))
                    else:
                        if c.get("viewRows", 0) < 10:
                            issues.append(("FAIL", "MOBILE-CONTENT",
                                           f"{rlabel} 只渲染出 {c.get('viewRows')} 行资源（应≥10）"))
                        if c.get("chips", 0) < 2:
                            issues.append(("FAIL", "MOBILE-CONTENT",
                                           f"{rlabel} 筛选芯片只有 {c.get('chips')} 个（应≥2）"))
                    r["issues"] = issues
                    rows.append(r)
                ctx.close()

            # ---- 模态专项：窄屏最容易被撑破的地方 ----
            for w, h, label in ([(390, 844, "iPhone 14 / 15")] if args.quick
                                else [(390, 844, "iPhone 14 / 15"), (360, 640, "小屏安卓")]):
                ctx = browser.new_context(viewport={"width": w, "height": h},
                                          device_scale_factor=2, is_mobile=True, has_touch=True)
                page = ctx.new_page()
                md = probe_modal(page, base + "/#/s2")   # 只有大三下有可在线阅读的 Markdown 手册
                if md:
                    issues = []
                    if not md["opened"]:
                        issues.append(("FAIL", "MOBILE-MODAL", "模态未打开"))
                    if md["isError"]:
                        issues.append(("FAIL", "MOBILE-MODAL", "模态进入错误态（内容没渲染出来）"))
                    elif not md["rendered"]:
                        issues.append(("FAIL", "MOBILE-MODAL", "模态未渲染任何 Markdown 内容"))
                    if md["cardOverflowPx"] > 0:
                        issues.append(("FAIL", "MOBILE-MODAL",
                                       f"模态卡片右侧溢出视口 {md['cardOverflowPx']}px"))
                    if md["barOverflowPx"] > 0:
                        issues.append(("FAIL", "MOBILE-MODAL",
                                       f"模态工具条横向溢出 {md['barOverflowPx']}px"))
                    if md["smallBtns"]:
                        issues.append(("FAIL", "MOBILE-MODAL",
                                       f"{len(md['smallBtns'])} 个模态按钮 < {TAP_MIN}px：" + "；".join(
                                           f"{s['t']}={s['h']}px" for s in md["smallBtns"])))
                    rows.append({
                        "viewport": f"{w}×{h}", "label": label, "route": "模态 · 在线阅读",
                        "viewportW": md["viewportW"], "scrollW": md["viewportW"],
                        "overflowPx": md["cardOverflowPx"], "small": md["smallBtns"],
                        "zoom": [], "errors": [], "modal": md,
                        "firstView": {"search": None, "firstRow": None}, "navOverlap": None,
                        "issues": issues,
                    })
                ctx.close()
            browser.close()
    finally:
        shutdown()

    for r in rows:
        print(f"\n▸ {r['viewport']:>9} ({r['label']}) · {r['route']}  "
              f"scrollW={r['scrollW']} innerW={r['viewportW']} "
              f"溢出={r['overflowPx']}px 小目标={len(r['small'])} "
              f"缩放风险={len(r['zoom'])} 控制台错={len(r['errors'])}")
        for level, code, msg in r["issues"]:
            print(f"    {'✘' if level == 'FAIL' else '⚠'} {level:4} {code}  {msg}")
            if level == "FAIL":
                fails += 1
            else:
                warns += 1

    if args.json:
        print(json.dumps({"rows": rows, "fail": fails, "warn": warns},
                         ensure_ascii=False, indent=2))

    print("\n" + "=" * 74)
    print(f"移动端门禁：FAIL={fails}  WARN={warns}  组合={len(rows)}"
          f"（视口 {len(viewports)} × 路由 {len(ROUTES)}）")
    if fails:
        print("❌ 移动端门禁未通过")
        return 1
    print("✅ 移动端门禁通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
