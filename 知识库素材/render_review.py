#!/usr/bin/env python3
"""
MedAgentWork — 主复习资料 HTML 渲染器
将 Agent 5 产出的 Markdown 复习手册转换为精美的自包含 HTML 页面。

用法:
    python render_review.py 复习资料/精神病学_主复习资料.md
    python render_review.py 复习资料/精神病学_主复习资料.md -o output/精神病学_复习手册.html
    python render_review.py 复习资料/精神病学_主复习资料.md --dark  # 默认暗色模式

依赖: Python 标准库 (无外部依赖)
"""

import re
import sys
import json
import html as html_module
from pathlib import Path
from datetime import datetime

# Windows UTF-8 encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


# ============================================================
# CSS (从模板提取, 自包含)
# ============================================================

CSS = r"""
/* ============================================================
   MedAgentWork — 主复习资料 HTML 渲染模板
   设计理念：专业医学教材 + 现代网页阅读体验
   零外部依赖，离线可用
   ============================================================ */

/* ----- CSS Custom Properties ----- */
:root {
  --bg-primary: #fafbfc;
  --bg-secondary: #ffffff;
  --bg-tertiary: #f0f2f5;
  --bg-callout: #f8f9fb;
  --text-primary: #1a1a2e;
  --text-secondary: #4a5568;
  --text-tertiary: #718096;
  --border: #e2e8f0;
  --border-light: #edf2f7;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.10);
  --color-master: #dc2626;
  --color-master-bg: #fef2f2;
  --color-master-border: #fecaca;
  --color-familiar: #d97706;
  --color-familiar-bg: #fffbeb;
  --color-familiar-border: #fde68a;
  --color-understand: #059669;
  --color-understand-bg: #ecfdf5;
  --color-understand-border: #a7f3d0;
  --color-warning: #d97706;
  --color-warning-bg: #fffbeb;
  --color-warning-border: #fcd34d;
  --color-tip: #7c3aed;
  --color-tip-bg: #f5f3ff;
  --color-tip-border: #c4b5fd;
  --color-info: #2563eb;
  --color-info-bg: #eff6ff;
  --color-info-border: #93c5fd;
  --color-success: #059669;
  --color-success-bg: #ecfdf5;
  --color-success-border: #6ee7b7;
  --accent: #2563eb;
  --accent-light: #dbeafe;
  --hero-gradient: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #7c3aed 100%);
  --font-body: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", "WenQuanYi Micro Hei", sans-serif;
  --font-mono: "SF Mono", "Cascadia Code", "Fira Code", "Consolas", monospace;
  --line-height: 1.8;
  --content-width: 720px;
  --sidebar-width: 260px;
  --header-height: 56px;
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;
}

[data-theme="dark"] {
  --bg-primary: #0f1117;
  --bg-secondary: #161822;
  --bg-tertiary: #1e2030;
  --bg-callout: #1a1c2a;
  --text-primary: #e2e4e9;
  --text-secondary: #a0a6b5;
  --text-tertiary: #6b7280;
  --border: #2a2d3a;
  --border-light: #222433;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.5);
  --color-master-bg: #3b1219;
  --color-master-border: #5c1f24;
  --color-familiar-bg: #3b2f0a;
  --color-familiar-border: #5c4a1a;
  --color-understand-bg: #0a2e1f;
  --color-understand-border: #1a4a30;
  --color-warning-bg: #3b2f0a;
  --color-warning-border: #5c4a1a;
  --color-tip-bg: #1e123b;
  --color-tip-border: #3a2560;
  --color-info-bg: #0a1e3b;
  --color-info-border: #1a3a5c;
  --color-success-bg: #0a2e1f;
  --color-success-border: #1a4a30;
  --accent-light: #1a2e4a;
  --hero-gradient: linear-gradient(135deg, #0a1628 0%, #16233f 50%, #241d40 100%);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html {
  scroll-behavior: smooth;
  scroll-padding-top: var(--header-height);
}

body {
  font-family: var(--font-body);
  font-size: 15px;
  line-height: var(--line-height);
  color: var(--text-primary);
  background: var(--bg-primary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#progress-bar {
  position: fixed;
  top: 0; left: 0; height: 3px;
  background: linear-gradient(90deg, var(--color-master), var(--accent), var(--color-understand));
  z-index: 1000;
  transition: width 100ms linear;
}

#top-header {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: var(--header-height);
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  z-index: 900;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

#top-header .title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

#top-header .actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.theme-toggle {
  width: 36px; height: 36px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  transition: all var(--transition-fast);
  color: var(--text-secondary);
}
.theme-toggle:hover {
  background: var(--accent-light);
  color: var(--accent);
}

#sidebar-toggle {
  display: none;
  width: 36px; height: 36px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-tertiary);
  cursor: pointer;
  font-size: 18px;
  color: var(--text-secondary);
}

#sidebar {
  position: fixed;
  top: var(--header-height);
  left: 0;
  width: var(--sidebar-width);
  height: calc(100vh - var(--header-height));
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  z-index: 800;
  padding: 16px 0;
  transition: transform var(--transition-normal);
}

#sidebar::-webkit-scrollbar { width: 4px; }
#sidebar::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

.sidebar-section {
  padding: 8px 20px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-tertiary);
}

.sidebar-link {
  display: block;
  padding: 8px 20px 8px 24px;
  font-size: 13px;
  color: var(--text-secondary);
  text-decoration: none;
  border-left: 3px solid transparent;
  transition: all var(--transition-fast);
  line-height: 1.5;
}
.sidebar-link:hover {
  color: var(--text-primary);
  background: var(--bg-tertiary);
  border-left-color: var(--border);
}
.sidebar-link.active {
  color: var(--accent);
  background: var(--accent-light);
  border-left-color: var(--accent);
  font-weight: 600;
}
.sidebar-link .badge {
  display: inline-block;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: 6px;
  font-weight: 600;
  vertical-align: middle;
}
.badge-master { background: var(--color-master-bg); color: var(--color-master); }
.badge-familiar { background: var(--color-familiar-bg); color: var(--color-familiar); }
.badge-understand { background: var(--color-understand-bg); color: var(--color-understand); }

#main-content {
  margin-left: var(--sidebar-width);
  margin-top: var(--header-height);
  padding: 40px 48px 80px;
  max-width: calc(var(--content-width) + 96px);
}

/* Hero Banner */
.hero-banner {
  background: var(--hero-gradient);
  border-radius: 16px;
  padding: 36px 40px;
  margin-bottom: 40px;
  color: #fff;
  position: relative;
  overflow: hidden;
}
.hero-banner::after {
  content: '';
  position: absolute;
  top: -50%; right: -20%;
  width: 400px; height: 400px;
  background: rgba(255,255,255,0.05);
  border-radius: 50%;
}
.hero-banner h1 {
  font-size: 28px;
  font-weight: 800;
  margin-bottom: 8px;
  position: relative;
  z-index: 1;
}
.hero-banner .meta {
  font-size: 14px;
  opacity: 0.85;
  position: relative;
  z-index: 1;
}
.hero-banner .meta-tags {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
  position: relative;
  z-index: 1;
}
.hero-banner .meta-tag {
  display: inline-block;
  padding: 3px 12px;
  border-radius: 20px;
  background: rgba(255,255,255,0.15);
  font-size: 12px;
  backdrop-filter: blur(4px);
}

/* Section Title */
.section-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 48px 0 20px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--border);
  display: flex;
  align-items: center;
  gap: 10px;
}
.section-title:first-of-type {
  margin-top: 0;
}

/* Module Card */
.module-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 32px;
  margin-bottom: 32px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition-normal);
  scroll-margin-top: calc(var(--header-height) + 20px);
}
.module-card:hover {
  box-shadow: var(--shadow-md);
}

.module-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}
.module-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}
.module-stats {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.module-stat {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.stat-master { background: var(--color-master-bg); color: var(--color-master); }
.stat-familiar { background: var(--color-familiar-bg); color: var(--color-familiar); }
.stat-understand { background: var(--color-understand-bg); color: var(--color-understand); }

.module-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--text-tertiary);
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.module-meta span { display: flex; align-items: center; gap: 4px; }

/* Importance Badge */
.importance-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  margin-right: 6px;
  vertical-align: middle;
  letter-spacing: 0.02em;
}
.imp-master { background: var(--color-master-bg); color: var(--color-master); border: 1px solid var(--color-master-border); }
.imp-familiar { background: var(--color-familiar-bg); color: var(--color-familiar); border: 1px solid var(--color-familiar-border); }
.imp-understand { background: var(--color-understand-bg); color: var(--color-understand); border: 1px solid var(--color-understand-border); }

/* Callout Blocks */
.callout {
  border-radius: 8px;
  padding: 16px 20px;
  margin: 16px 0;
  border-left: 4px solid;
  font-size: 14px;
  line-height: 1.7;
}
.callout-title {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.callout-warning {
  background: var(--color-warning-bg);
  border-color: var(--color-warning);
}
.callout-warning .callout-title { color: var(--color-warning); }

.callout-tip {
  background: var(--color-tip-bg);
  border-color: var(--color-tip);
}
.callout-tip .callout-title { color: var(--color-tip); }

.callout-info {
  background: var(--color-info-bg);
  border-color: var(--color-info);
}
.callout-info .callout-title { color: var(--color-info); }

.callout-success {
  background: var(--color-success-bg);
  border-color: var(--color-success);
}
.callout-success .callout-title { color: var(--color-success); }

/* Accordion */
.accordion {
  border: 1px solid var(--border);
  border-radius: 8px;
  margin: 12px 0;
  overflow: hidden;
}
.accordion summary {
  padding: 14px 20px;
  cursor: pointer;
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-tertiary);
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
  user-select: none;
  transition: background var(--transition-fast);
}
.accordion summary::-webkit-details-marker { display: none; }
.accordion summary::before {
  content: '▸';
  display: inline-block;
  transition: transform var(--transition-fast);
  font-size: 10px;
  color: var(--text-tertiary);
}
.accordion[open] summary::before {
  transform: rotate(90deg);
}
.accordion summary:hover {
  background: var(--accent-light);
}
.accordion .accordion-body {
  padding: 16px 20px;
  font-size: 14px;
  line-height: 1.8;
}

/* Blockquote */
blockquote {
  border-left: 3px solid var(--accent);
  margin: 16px 0;
  padding: 12px 20px;
  background: var(--accent-light);
  border-radius: 0 8px 8px 0;
  font-size: 14px;
  color: var(--text-secondary);
}

/* Code */
code {
  background: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.9em;
  color: var(--color-tip);
}

/* Tables */
.table-wrapper {
  overflow-x: auto;
  margin: 16px 0;
  border-radius: 8px;
  border: 1px solid var(--border);
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
thead {
  background: var(--bg-tertiary);
}
th {
  padding: 10px 14px;
  text-align: left;
  font-weight: 700;
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 2px solid var(--border);
  white-space: nowrap;
  text-transform: none;
}
td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-light);
  color: var(--text-primary);
  vertical-align: top;
}
tr:nth-child(even) td {
  background: var(--bg-callout);
}
tr:last-child td {
  border-bottom: none;
}

/* Fill-in-blank */
.fill-blank {
  display: inline-block;
  min-width: 60px;
  border-bottom: 2px dashed var(--accent);
  padding: 0 4px;
  margin: 0 2px;
  cursor: pointer;
  transition: all var(--transition-fast);
  color: transparent;
  position: relative;
}
.fill-blank.revealed {
  color: var(--color-understand);
  border-bottom-color: var(--color-understand);
  font-weight: 600;
}
.fill-blank::after {
  content: '（点击显示）';
  position: absolute;
  left: 4px;
  top: 0;
  color: var(--text-tertiary);
  font-size: 12px;
  pointer-events: none;
}
.fill-blank.revealed::after {
  display: none;
}

/* Back to Top */
#back-to-top {
  position: fixed;
  bottom: 24px; right: 24px;
  width: 44px; height: 44px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  border: none;
  cursor: pointer;
  font-size: 20px;
  box-shadow: var(--shadow-md);
  z-index: 700;
  opacity: 0;
  transform: translateY(10px);
  transition: all var(--transition-normal);
  display: flex;
  align-items: center;
  justify-content: center;
}
#back-to-top.visible {
  opacity: 1;
  transform: translateY(0);
}
#back-to-top:hover {
  background: #1d4ed8;
  transform: translateY(-2px);
}

/* Sidebar overlay */
#sidebar-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  z-index: 790;
}

/* Print */
@media print {
  #progress-bar, #top-header, #sidebar, #sidebar-overlay, #sidebar-toggle, #back-to-top, .theme-toggle {
    display: none !important;
  }
  #main-content {
    margin-left: 0;
    margin-top: 0;
    padding: 0;
    max-width: 100%;
  }
  .module-card, .hero-banner {
    box-shadow: none;
    break-inside: avoid;
    border: 1px solid #ddd;
  }
  .hero-banner {
    background: #f0f4ff !important;
    color: #1a1a2e !important;
  }
  .hero-banner .meta-tag {
    background: #e2e8f0;
    color: #1a1a2e;
  }
  body { font-size: 12px; background: #fff; }
  /* 打印折叠展开（2026-08-21 修复）：全部折叠区强制展开，避免打印丢内容 */
  .accordion .accordion-body { display: block !important; }
  .accordion:not([open]) > .accordion-body { display: block !important; }
  .fill-blank { color: var(--color-understand); border-bottom: 1px solid #999; }
  .fill-blank::after { display: none; }
}

/* Responsive */
@media (max-width: 1024px) {
  #main-content {
    padding: 24px 20px 60px;
  }
  .hero-banner {
    padding: 24px 20px;
    border-radius: 12px;
  }
  .hero-banner h1 { font-size: 22px; }
}

@media (max-width: 768px) {
  #sidebar {
    transform: translateX(-100%);
    box-shadow: var(--shadow-lg);
  }
  #sidebar.open {
    transform: translateX(0);
  }
  #sidebar-overlay.show {
    display: block;
  }
  #sidebar-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
  }
  #main-content {
    margin-left: 0;
    padding: 16px 12px 60px;
    max-width: 100%;
  }
  .module-card {
    padding: 20px 16px;
  }
  .hero-banner {
    border-radius: 10px;
    padding: 20px 16px;
  }
  .hero-banner h1 { font-size: 20px; }
  #back-to-top { bottom: 16px; right: 16px; }
}

.sr-only {
  position: absolute; width: 1px; height: 1px;
  padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0,0,0,0); border: 0;
}
"""

JS = r"""
// Theme Toggle
const html = document.documentElement;
const themeToggle = document.getElementById('theme-toggle');

function setTheme(theme) {
  html.setAttribute('data-theme', theme);
  themeToggle.textContent = theme === 'dark' ? '\u2600\uFE0F' : '\uD83C\uDF19';
  localStorage.setItem('med-review-theme', theme);
}

const DEFAULT_DARK = false;  // 由 render_review.py --dark 注入替换
const savedTheme = localStorage.getItem('med-review-theme');
if (savedTheme) {
  setTheme(savedTheme);
} else if (DEFAULT_DARK || window.matchMedia('(prefers-color-scheme: dark)').matches) {
  setTheme('dark');
}

themeToggle.addEventListener('click', () => {
  setTheme(html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
});

// Progress Bar
const progressBar = document.getElementById('progress-bar');
window.addEventListener('scroll', () => {
  const scrollTop = window.scrollY;
  const docHeight = document.documentElement.scrollHeight - window.innerHeight;
  const progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
  progressBar.style.width = Math.min(progress, 100) + '%';
});

// Back to Top
const backToTop = document.getElementById('back-to-top');
window.addEventListener('scroll', () => {
  backToTop.classList.toggle('visible', window.scrollY > 400);
});
backToTop.addEventListener('click', () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

// Sidebar Active Link
const sidebarLinks = document.querySelectorAll('.sidebar-link');
const sections = [];
sidebarLinks.forEach(link => {
  const href = link.getAttribute('href');
  if (href && href.startsWith('#')) {
    const target = document.getElementById(href.slice(1));
    if (target) sections.push({ link, target });
  }
});

function updateActiveLink() {
  const scrollPos = window.scrollY + 100;
  let activeLink = null;
  for (let i = sections.length - 1; i >= 0; i--) {
    if (sections[i].target.offsetTop <= scrollPos) {
      activeLink = sections[i].link;
      break;
    }
  }
  sidebarLinks.forEach(l => l.classList.remove('active'));
  if (activeLink) activeLink.classList.add('active');
}
window.addEventListener('scroll', updateActiveLink);
updateActiveLink();

// Mobile Sidebar
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebar-toggle');
const sidebarOverlay = document.getElementById('sidebar-overlay');

function openSidebar() {
  sidebar.classList.add('open');
  sidebarOverlay.classList.add('show');
  document.body.style.overflow = 'hidden';
}
function closeSidebar() {
  sidebar.classList.remove('open');
  sidebarOverlay.classList.remove('show');
  document.body.style.overflow = '';
}
sidebarToggle.addEventListener('click', openSidebar);
sidebarOverlay.addEventListener('click', closeSidebar);
sidebar.querySelectorAll('.sidebar-link').forEach(link => {
  link.addEventListener('click', () => {
    if (window.innerWidth <= 768) setTimeout(closeSidebar, 200);
  });
});

// Fill-in-blank: reveal all buttons
document.querySelectorAll('.module-card').forEach(card => {
  card.querySelectorAll('.reveal-all-btn').forEach(b => b.remove());
  const blanks = card.querySelectorAll('.fill-blank');
  if (blanks.length === 0) return;
  // 2026-08-21 修复：按钮工厂（cloneNode 不复制 addEventListener 监听器，旧实现挂载的是死按钮）
  function makeBtn() {
    const btn = document.createElement('button');
    btn.className = 'reveal-all-btn';
    btn.textContent = '\uD83D\uDC41\uFE0F \u663E\u793A\u5168\u90E8\u7B54\u6848';
    btn.style.cssText = 'display:inline-block;margin:12px 0 0 0;padding:6px 16px;border-radius:6px;border:1px solid var(--border);background:var(--bg-tertiary);color:var(--text-secondary);font-size:12px;cursor:pointer;font-family:var(--font-body);transition:all var(--transition-fast);';
    btn.addEventListener('mouseenter',()=>{btn.style.background='var(--accent-light)';btn.style.color='var(--accent)';});
    btn.addEventListener('mouseleave',()=>{btn.style.background='var(--bg-tertiary)';btn.style.color='var(--text-secondary)';});
    let revealed = false;
    btn.addEventListener('click',()=>{
      revealed = !revealed;
      blanks.forEach(b => { if(revealed) b.classList.add('revealed'); else b.classList.remove('revealed'); });
      btn.textContent = revealed ? '\uD83D\uDE48 \u9690\u85CF\u5168\u90E8\u7B54\u6848' : '\uD83D\uDC41\uFE0F \u663E\u793A\u5168\u90E8\u7B54\u6848';
    });
    return btn;
  }
  const recallH = Array.from(card.querySelectorAll('h3')).filter(h=>h.textContent.includes('\u4E3B\u52A8\u56DE\u5FC6'));
  let appended = false;
  recallH.forEach(h=>{ let el=h.nextElementSibling; if(el){ el.appendChild(makeBtn()); appended = true; } });
  if(!appended) card.appendChild(makeBtn()); // 无「主动回忆」模块时兜底挂卡片末尾
});

// Keyboard shortcuts
document.addEventListener('keydown',(e)=>{
  if(e.key==='t'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&document.activeElement===document.body)
    setTheme(html.getAttribute('data-theme')==='dark'?'light':'dark');
  if(e.key==='m'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&document.activeElement===document.body&&window.innerWidth<=768)
    sidebar.classList.contains('open')?closeSidebar():openSidebar();
});
"""


# ============================================================
# Markdown → HTML 转换器
# ============================================================

class ReviewRenderer:
    """将 MedAgentWork 主复习资料 Markdown 转换为精美 HTML"""

    def __init__(self, md_path: Path):
        self.md_path = md_path
        self.md_text = md_path.read_text(encoding='utf-8')
        self.lines = self.md_text.split('\n')
        self.subject_name = ""
        self.batch_id = ""
        self.sidebar_links = []  # (id, text, badge_class, badge_text)
        self.modules = []  # module info for sidebar

    def extract_metadata(self):
        """从 MD 头部提取科目名和批次"""
        for line in self.lines[:10]:
            if line.startswith('# '):
                self.subject_name = line[2:].strip().replace(' 高效复习手册', '').replace(' 主复习资料', '')
            if 'batch' in line.lower():
                m = re.search(r'batch\d+', line)
                if m:
                    self.batch_id = m.group()
        if not self.subject_name:
            self.subject_name = self.md_path.stem.replace('_主复习资料', '').replace('_备考复习资料', '')

    def parse_inline(self, text: str) -> str:
        """解析行内 Markdown 标记"""
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # Inline code
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        # Links
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        # Fill-in-blank (《答案》→ clickable span)
        text = re.sub(
            r'《([^》]+)》',
            r'<span class="fill-blank" onclick="this.classList.toggle(\'revealed\')">\1</span>',
            text
        )
        return text

    def make_id(self, text: str) -> str:
        """生成 HTML 锚点 ID"""
        # Remove emojis and special chars, keep Chinese/English/numbers
        text = re.sub(r'[^\u4e00-\u9fff\w\s-]', '', text)
        text = text.strip().lower().replace(' ', '-')
        return text or 'section'

    def detect_module_importance(self, text: str) -> str:
        """检测模块的重要性等级"""
        if '核心' in text or '⭐' in text or '★' in text:
            return 'master'
        if '重要' in text or '熟悉' in text:
            return 'familiar'
        return 'understand'

    def build_sidebar(self):
        """构建侧栏导航"""
        links = []
        in_module = False
        current_module_num = ""
        current_module_title = ""
        current_importance = "understand"

        for line in self.lines:
            # 科目导航
            if line.startswith('## ') and ('科目导航' in line or '怎么学' in line):
                links.append(('nav', '科目导航', '', ''))
            # 使用指南
            elif line.startswith('## ') and '使用指南' in line:
                links.append(('guide', '使用指南', '', ''))
            # 模块速览
            elif line.startswith('## ') and ('模块速览' in line or '知识框架' in line):
                links.append(('overview', '模块速览', '', ''))
            # 模块标题 (H2/H3: ## 模块X / ### M1：xxx)
            elif (line.startswith('## 模块') or line.startswith('## M') or
                  line.startswith('### M') or line.startswith('### 模块')):
                m = re.match(r'#{2,3}\s*(?:模块)?(\d+)[：:]\s*(.+)', line)
                if not m:
                    m = re.match(r'#{2,3}\s*M(\d+)\s+(.+)', line)
                if m:
                    current_module_num = m.group(1)
                    current_module_title = m.group(2).strip()
                    current_importance = self.detect_module_importance(line)
                    badge_map = {'master': ('badge-master', '核心'), 'familiar': ('badge-familiar', '重要'), 'understand': ('badge-understand', '了解')}
                    badge_class, badge_text = badge_map.get(current_importance, ('', ''))
                    mod_id = f'm{current_module_num}'
                    links.append((mod_id, f'M{current_module_num} {current_module_title[:12]}', badge_class, badge_text))
            # 附录
            elif line.startswith('## 附录') or line.startswith('## ') and '附录' in line:
                app_id = self.make_id(line)
                title = line[3:].strip()
                links.append((app_id, title[:20], '', ''))

        self.sidebar_links = links

    def render_sidebar_html(self) -> str:
        """生成侧栏 HTML"""
        parts = []
        nav_done = False
        modules_started = False
        appendix_started = False

        for item in self.sidebar_links:
            sid, text, badge_class, badge_text = item

            # Group sections
            if not nav_done and sid in ('nav', 'guide', 'overview'):
                if not parts or 'sidebar-section' not in parts[-1]:
                    parts.append('<div class="sidebar-section">📋 导航</div>')
                nav_done = False

            if not modules_started and sid.startswith('m') and sid[1:].isdigit():
                parts.append('<div class="sidebar-section" style="margin-top:12px">📚 模块</div>')
                modules_started = True

            if not appendix_started and '附录' in text:
                parts.append('<div class="sidebar-section" style="margin-top:12px">📎 附录</div>')
                appendix_started = True

            badge_html = f' <span class="badge {badge_class}">{badge_text}</span>' if badge_class else ''
            active = ' active' if sid == 'nav' else ''
            parts.append(f'<a href="#{sid}" class="sidebar-link{active}">{html_module.escape(text)}{badge_html}</a>')

        return '\n'.join(parts)

    def convert_block(self, lines: list[str], start: int) -> tuple[str, int]:
        """转换一个内容块，返回 (HTML, 下一个未处理的行号)"""
        i = start
        if i >= len(lines):
            return '', i

        line = lines[i]

        # Horizontal rule
        if line.strip() == '---' or line.strip() == '***':
            return '<hr style="border:none;border-top:1px solid var(--border);margin:24px 0">', i + 1

        # Blockquote / Callout
        if line.startswith('> '):
            buf = []
            while i < len(lines) and (lines[i].startswith('> ') or lines[i].strip() == '>'):
                buf.append(lines[i][2:] if lines[i].startswith('> ') else '')
                i += 1

            # Check if this is a callout block: > [!TYPE] Title
            callout_match = re.match(r'^\s*\[!(\w+)\]\s*(.*)', buf[0]) if buf else None
            if callout_match:
                callout_type = callout_match.group(1).lower()
                callout_title = callout_match.group(2).strip()
                # Map callout types
                type_map = {
                    'warning': 'warning',
                    'tip': 'tip',
                    'info': 'info',
                    'success': 'success',
                    'note': 'note',
                    'important': 'warning',
                    'danger': 'warning',
                    'caution': 'warning',
                    'example': 'info',
                }
                css_type = type_map.get(callout_type, 'info')
                body_lines = buf[1:]
                # Remove trailing empty lines
                while body_lines and not body_lines[-1].strip():
                    body_lines.pop()
                body = '<br>'.join(self.parse_inline(l) for l in body_lines if l.strip() or body_lines)
                if not callout_title:
                    callout_title = callout_type.upper()
                return f'<div class="callout callout-{css_type}"><div class="callout-title">{self.parse_inline(callout_title)}</div><p>{body}</p></div>', i

            # Regular blockquote
            content = '<br>'.join(self.parse_inline(l) for l in buf if l.strip())
            return f'<blockquote>{content}</blockquote>', i

        # Details/Summary (HTML in MD)
        if line.strip().startswith('<details'):
            buf = [line]
            i += 1
            depth = 1
            while i < len(lines) and depth > 0:
                if '<details' in lines[i]:
                    depth += 1
                if '</details>' in lines[i]:
                    depth -= 1
                buf.append(lines[i])
                i += 1
            raw = '\n'.join(buf)
            # Convert to accordion class
            raw = raw.replace('<details open>', '<details class="accordion" open>')
            raw = raw.replace('<details>', '<details class="accordion">')
            raw = raw.replace('<summary>', '<summary>')
            raw = raw.replace('</details>', '</details>')
            # Wrap body content
            raw = re.sub(r'</summary>\s*\n', '</summary>\n<div class="accordion-body">\n', raw)
            raw = re.sub(r'</details>', '</div>\n</details>', raw)
            return raw, i

        # Table
        if '|' in line and line.strip().startswith('|'):
            buf = []
            while i < len(lines) and '|' in lines[i] and lines[i].strip().startswith('|'):
                buf.append(lines[i])
                i += 1

            if len(buf) < 2:
                return self.parse_inline(buf[0]), i

            # Parse table
            rows = []
            for row_line in buf:
                cells = [c.strip() for c in row_line.strip().split('|')]
                cells = [c for c in cells if c]  # Remove empty from leading/trailing |
                if cells:
                    rows.append(cells)

            if not rows:
                return '', i

            # Check if second row is separator
            header_rows = 1
            if len(rows) > 1 and all(re.match(r'^[-:]+$', c) for c in rows[1]):
                header_rows = 2

            html_parts = ['<div class="table-wrapper"><table>']

            if header_rows >= 2:
                html_parts.append('<thead><tr>')
                for cell in rows[0]:
                    html_parts.append(f'<th>{self.parse_inline(cell)}</th>')
                html_parts.append('</tr></thead>')
                body_start = 2
            elif header_rows == 1:
                html_parts.append('<thead><tr>')
                for cell in rows[0]:
                    html_parts.append(f'<th>{self.parse_inline(cell)}</th>')
                html_parts.append('</tr></thead>')
                body_start = 1
            else:
                body_start = 0

            if body_start < len(rows):
                html_parts.append('<tbody>')
                for row in rows[body_start:]:
                    html_parts.append('<tr>')
                    for cell in row:
                        html_parts.append(f'<td>{self.parse_inline(cell)}</td>')
                    html_parts.append('</tr>')
                html_parts.append('</tbody>')

            html_parts.append('</table></div>')
            return '\n'.join(html_parts), i

        # Code block
        if line.strip().startswith('```'):
            lang = line.strip()[3:].strip()
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            code = html_module.escape('\n'.join(buf))
            return f'<pre style="background:var(--bg-tertiary);padding:16px;border-radius:8px;overflow-x:auto;font-size:13px;line-height:1.7;font-family:var(--font-mono)"><code>{code}</code></pre>', i

        # Unordered list
        if re.match(r'^[\s]*[-*+]\s', line):
            buf = []
            while i < len(lines) and (re.match(r'^[\s]*[-*+]\s', lines[i]) or re.match(r'^\s{2,}[-*+]\s', lines[i])):
                buf.append(lines[i])
                i += 1
            items = []
            for li in buf:
                content = re.sub(r'^\s*[-*+]\s+', '', li)
                items.append(f'<li>{self.parse_inline(content)}</li>')
            return f'<ul style="padding-left:20px;line-height:2;font-size:14px;color:var(--text-secondary)">\n{"".join(items)}\n</ul>', i

        # Ordered list
        if re.match(r'^\s*\d+[.)]\s', line):
            buf = []
            while i < len(lines) and re.match(r'^\s*\d+[.)]\s', lines[i]):
                buf.append(lines[i])
                i += 1
            items = []
            for li in buf:
                content = re.sub(r'^\s*\d+[.)]\s+', '', li)
                items.append(f'<li>{self.parse_inline(content)}</li>')
            return f'<ol style="padding-left:20px;line-height:2;font-size:14px;color:var(--text-secondary)">\n{"".join(items)}\n</ol>', i

        # Heading
        heading_match = re.match(r'^(#{1,6})\s+(.+)', line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()

            # Generate ID
            sid = self.make_id(text)

            # Detect module headings for special styling (H2 or H3)
            if level in (2, 3) and (text.startswith('模块') or re.match(r'M\d', text)):
                # Module heading → Section title + Module card
                m = re.match(r'(?:模块)?(\d+)[：:]\s*(.+)', text)
                if not m:
                    m = re.match(r'M(\d+)\s+(.+)', text)
                if m:
                    mod_num = m.group(1)
                    mod_title = m.group(2).strip()
                    importance = self.detect_module_importance(text)
                    border_style = ''
                    if importance == 'master':
                        border_style = ' style="border-left: 4px solid var(--color-master)"'
                    elif importance == 'familiar':
                        border_style = ' style="border-left: 4px solid var(--color-familiar)"'

                    # Extract stats from next few lines
                    stats_html = ''
                    peek_i = i + 1
                    while peek_i < min(i + 10, len(lines)):
                        pline = lines[peek_i]
                        stat_match = re.findall(r'掌握(\d+)个?|熟悉(\d+)个?|了解(\d+)个?', pline)
                        if stat_match:
                            stats = stat_match[0]
                            stat_parts = []
                            if stats[0]: stat_parts.append(f'<span class="module-stat stat-master">掌握 {stats[0]}</span>')
                            if stats[1]: stat_parts.append(f'<span class="module-stat stat-familiar">熟悉 {stats[1]}</span>')
                            if stats[2]: stat_parts.append(f'<span class="module-stat stat-understand">了解 {stats[2]}</span>')
                            if stat_parts:
                                stats_html = f'<div class="module-stats">{"".join(stat_parts)}</div>'
                            break
                        peek_i += 1

                    html_out = f'<h2 class="section-title" id="m{mod_num}">📘 模块{mod_num}：{html_module.escape(mod_title)}</h2>\n'
                    html_out += f'<div class="module-card"{border_style}>\n'
                    html_out += f'<div class="module-header"><h2>M{mod_num} · {html_module.escape(mod_title)}</h2>{stats_html}</div>\n'
                    self._current_module_open = True
                    self._current_module_num = mod_num
                    i += 1
                    return html_out, i

            # Regular heading
            tag = f'h{level}'
            font_sizes = {1: '28px', 2: '22px', 3: '16px', 4: '14px', 5: '13px', 6: '12px'}
            fs = font_sizes.get(level, '14px')
            # 重要性 emoji 标题（#### 🔴【掌握级】…）→ badge + 剥离 emoji 的标题
            imp_head = re.match(r'^(🔴|🟡|🟢)\s*(.+)', text)
            badge_html = ''
            if imp_head:
                bmap = {'🔴': ('imp-master', '掌握'), '🟡': ('imp-familiar', '熟悉'), '🟢': ('imp-understand', '了解')}
                bcls, btxt = bmap[imp_head.group(1)]
                badge_html = f'<span class="importance-badge {bcls}">{btxt}</span> '
                text = imp_head.group(2).strip()
            return f'<{tag} id="{sid}" style="font-size:{fs};margin:{24 if level<=2 else 16}px 0 {8 if level<=2 else 6}px;color:var(--text-primary);font-weight:700">{badge_html}{self.parse_inline(text)}</{tag}>', i + 1

        # Callout detection (⚠️, 💡, 🎯, etc.)
        callout_match = re.match(r'^(⚠️|💡|🎯|✅|❌|⚡|🧩|🔄|📊|📌|🔗|🧠|🏥)\s*(.+)', line)
        if callout_match:
            emoji = callout_match.group(1)
            content = callout_match.group(2)
            callout_map = {
                '⚠️': ('warning', '⚠️ 常见陷阱'),
                '💡': ('tip', '💡 记忆口诀'),
                '🎯': ('info', '🎯 高收益摘要'),
                '✅': ('success', '✅ 前置知识'),
                '❌': ('warning', '❌ 避坑提示'),
                '⚡': ('tip', '⚡ 快速补课'),
            }
            callout_type, callout_title = callout_map.get(emoji, ('info', emoji + ' 提示'))
            return f'<div class="callout callout-{callout_type}"><div class="callout-title">{callout_title}</div><p>{self.parse_inline(content)}</p></div>', i + 1

        # Importance badge detection
        importance_match = re.match(r'^(🔴|🟡|🟢)\s*(.+)', line)
        if importance_match:
            emoji = importance_match.group(1)
            content = importance_match.group(2)
            badge_map = {'🔴': ('imp-master', '掌握'), '🟡': ('imp-familiar', '熟悉'), '🟢': ('imp-understand', '了解')}
            badge_class, badge_text = badge_map.get(emoji, ('', ''))
            return f'<p style="margin:8px 0"><span class="importance-badge {badge_class}">{badge_text}</span> {self.parse_inline(content)}</p>', i + 1

        # Fill-in-blank (《...》 pattern from active recall)
        blank_match = re.findall(r'《([^》]+)》', line)
        if blank_match:
            result = line
            for blank_text in blank_match:
                replacement = f'<span class="fill-blank" onclick="this.classList.toggle(\'revealed\')">{html_module.escape(blank_text)}</span>'
                result = result.replace(f'《{blank_text}》', replacement)
            return f'<p style="margin:4px 0;line-height:2.2;font-size:14px">{self.parse_inline(result)}</p>', i + 1

        # Paragraph (non-empty, non-special)
        if line.strip():
            return f'<p style="margin:8px 0;line-height:1.8">{self.parse_inline(line)}</p>', i + 1

        # Empty line
        return '', i + 1

    def _preprocess_v3_callouts(self, text: str) -> str:
        """将 v3 风格 emoji 标题块转换为 v4 callout 语法。

        v3: ### ⚠️ 常见陷阱\\n\\n- 内容...\\n\\n### 下一节
        v4: > [!WARNING] 常见陷阱\\n> - 内容...\\n\\n### 下一节
        """
        # Map emoji headings to callout types
        heading_callout_map = {
            '⚠️': ('WARNING', '常见陷阱'),
            '💡': ('TIP', '记忆口诀'),
            '🎯': ('INFO', '高收益摘要'),
            '📌': ('INFO', '本章小结'),
            '🔗': ('NOTE', '深度链接'),
            '🧠': ('NOTE', '机制深挖'),
            '🏥': ('SUCCESS', '临床推理链'),
        }

        lines = text.split('\n')
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]

            # Detect v3 callout heading: ### ⚠️ 常见陷阱 or ### ⚠️ 常见陷阱（副标题）
            heading_match = re.match(r'^(#{2,4})\s+(⚠️|💡|🎯|📌|🔗|🧠|🏥|🔄)\s*(.+)', line)
            if heading_match:
                emoji = heading_match.group(2)
                rest = heading_match.group(3).strip()
                if emoji in heading_callout_map:
                    callout_type, default_title = heading_callout_map[emoji]
                    title = rest if rest else default_title

                    # Convert to callout blockquote
                    result.append(f'> [!{callout_type}] {title}')

                    # Collect following content until next heading or empty+heading
                    i += 1
                    while i < len(lines):
                        nxt = lines[i]
                        # Stop at next heading
                        if re.match(r'^#{1,4}\s', nxt):
                            break
                        # Stop at horizontal rule
                        if nxt.strip() in ('---', '***', '___'):
                            break
                        # Convert list items and paragraphs to blockquote
                        if nxt.strip():
                            result.append(f'> {nxt}')
                        else:
                            # Empty line within section: add empty blockquote line
                            # But check if next line is a heading
                            if i + 1 < len(lines) and re.match(r'^#{1,4}\s', lines[i + 1]):
                                break
                            result.append('>')
                        i += 1
                    result.append('')  # Blank line after callout
                    continue

            result.append(line)
            i += 1

        return '\n'.join(result)

    def convert(self, dark_mode: bool = False) -> str:
        """完整转换 MD → HTML"""
        self.extract_metadata()
        self.build_sidebar()

        # Preprocess v3-style callout headings to v4 format
        self.md_text = self._preprocess_v3_callouts(self.md_text)
        self.lines = self.md_text.split('\n')

        html_parts = []
        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html lang="zh-CN" data-theme="%s">' % ('dark' if dark_mode else 'light'))
        html_parts.append('<head>')
        html_parts.append('<meta charset="UTF-8">')
        html_parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html_parts.append(f'<title>{html_module.escape(self.subject_name)} · 高效复习手册</title>')
        html_parts.append(f'<style>{CSS}</style>')
        html_parts.append('</head>')
        html_parts.append('<body>')

        # Progress bar + Header
        html_parts.append('<div id="progress-bar" style="width:0%"></div>')
        html_parts.append('<header id="top-header">')
        html_parts.append('<button id="sidebar-toggle" aria-label="目录">☰</button>')
        html_parts.append(f'<span class="title">📖 {html_module.escape(self.subject_name)} · 高效复习手册</span>')
        html_parts.append('<div class="actions">')
        html_parts.append('<button class="theme-toggle" id="theme-toggle" aria-label="切换暗色模式" title="切换暗色/亮色模式">🌙</button>')
        html_parts.append('</div>')
        html_parts.append('</header>')

        # Sidebar
        html_parts.append('<div id="sidebar-overlay"></div>')
        html_parts.append('<nav id="sidebar">')
        html_parts.append(self.render_sidebar_html())
        html_parts.append('</nav>')

        # Main content
        html_parts.append('<main id="main-content">')

        # Hero banner
        tags = [
            f'<span class="meta-tag">📘 医学复习手册</span>',
            f'<span class="meta-tag">🎯 期末考试</span>',
        ]
        if self.batch_id:
            tags.insert(0, f'<span class="meta-tag">📦 {self.batch_id}</span>')

        html_parts.append('<div class="hero-banner">')
        html_parts.append(f'<h1>🧠 {html_module.escape(self.subject_name)} 高效复习手册</h1>')
        html_parts.append(f'<p class="meta">MedAgentWork 自动生成 | 教材浓缩型 | 分层阅读</p>')
        html_parts.append(f'<div class="meta-tags">{"".join(tags)}</div>')
        html_parts.append('</div>')

        # Process body content - skip the H1 title line since we have hero banner
        i = 0
        # Skip the H1 title
        while i < len(self.lines) and not self.lines[i].startswith('# '):
            i += 1
        if i < len(self.lines) and self.lines[i].startswith('# '):
            i += 1
        # Skip metadata blockquote lines after H1
        while i < len(self.lines) and (self.lines[i].startswith('> ') or self.lines[i].strip() == '>' or self.lines[i].strip() == ''):
            i += 1
        # Skip horizontal rules
        while i < len(self.lines) and self.lines[i].strip() == '---':
            i += 1

        # Now process remaining content
        # Track if we're inside a module card (to close it properly)
        self._current_module_open = False
        self._current_module_num = ""

        content_buf = []
        while i < len(self.lines):
            block_html, next_i = self.convert_block(self.lines, i)

            # Check if we're about to start a new module section (close previous card)
            if block_html and '<h2 class="section-title"' in block_html and '模块' in block_html:
                if self._current_module_open:
                    content_buf.append('</div> <!-- close module-card -->')
                    self._current_module_open = False

            # Check if next heading is not part of module (close card)
            if next_i < len(self.lines):
                nline = self.lines[next_i].strip()
                # If next is H2 that starts a new module or non-module section
                if nline.startswith('## ') and '模块' not in nline and not re.match(r'M\d', nline):
                    if self._current_module_open:
                        content_buf.append('</div> <!-- close module-card -->')
                        self._current_module_open = False
                # If next is H2 appendix
                if nline.startswith('## ') and '附录' in nline:
                    if self._current_module_open:
                        content_buf.append('</div> <!-- close module-card -->')
                        self._current_module_open = False

            if block_html:
                content_buf.append(block_html)
            i = next_i

        # Close any remaining open module card
        if self._current_module_open:
            content_buf.append('</div> <!-- close module-card -->')

        html_parts.extend(content_buf)

        html_parts.append('</main>')

        # Back to top button
        html_parts.append('<button id="back-to-top" aria-label="回到顶部" title="回到顶部">↑</button>')

        # JavaScript
        js = JS.replace('const DEFAULT_DARK = false;',
                        'const DEFAULT_DARK = %s;' % str(dark_mode).lower())
        html_parts.append(f'<script>{js}</script>')

        html_parts.append('</body>')
        html_parts.append('</html>')

        return '\n'.join(html_parts)


# ============================================================
# Main
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='MedAgentWork — 主复习资料 HTML 渲染器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python render_review.py 复习资料/精神病学_主复习资料.md
  python render_review.py 复习资料/精神病学_主复习资料.md -o output/精神病学.html
  python render_review.py 复习资料/精神病学_主复习资料.md --dark
        """
    )
    parser.add_argument('input', help='输入的 Markdown 复习资料路径')
    parser.add_argument('-o', '--output', help='输出 HTML 文件路径 (默认: 同目录同名 .html)')
    parser.add_argument('--dark', action='store_true', help='默认使用暗色模式')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f'❌ 文件不存在: {input_path}')
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix('.html')

    # Render
    print(f'📖 读取: {input_path}')
    renderer = ReviewRenderer(input_path)
    html_content = renderer.convert(dark_mode=args.dark)

    # Write
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding='utf-8')
    print(f'✅ 已生成: {output_path}')
    print(f'   大小: {len(html_content):,} bytes')
    print(f'   科目: {renderer.subject_name}')
    if renderer.batch_id:
        print(f'   批次: {renderer.batch_id}')
    print(f'   模块: {len([l for l in renderer.sidebar_links if l[0].startswith("m") and l[0][1:].isdigit()])} 个')


if __name__ == '__main__':
    main()
