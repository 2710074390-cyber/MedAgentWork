#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_pilot_review.py — M3/T10：离线复习 HTML（localStorage 进度）。

只读 review_items.jsonl，生成单文件 HTML；不采集 PII、不发外部请求。
"""
from __future__ import annotations

import argparse
import html
import io
import json
import sys
from pathlib import Path


def _configure_stdio() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


BASE = Path(__file__).resolve().parent.parent
DEFAULT_ITEMS = BASE / "中间产物/batch040/pilot/review_items.jsonl"
DEFAULT_OUT = BASE / "中间产物/batch040/pilot/pilot_review.html"
KEY = "medagentwork_pilot_ent_v1"


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<style>
:root{--bg:#f3f7f5;--card:#fff;--ink:#152522;--muted:#65756f;--line:#dbe6e1;--accent:#0b6e5f;--accent2:#c2711a;--ok:#2f7d5b;--risk:#a23b3b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Microsoft YaHei","PingFang SC",sans-serif;line-height:1.65}
.wrap{max-width:760px;margin:0 auto;padding:24px 18px 48px}
header{display:flex;justify-content:space-between;gap:14px;align-items:flex-end;margin-bottom:18px}
h1{font-size:22px;margin:0 0 2px}
.sub{color:var(--muted);font-size:12px}
.stats{font-size:12px;color:var(--muted);text-align:right}
.bar{height:8px;background:#e3ece8;border-radius:99px;overflow:hidden;margin:12px 0 18px}
.bar i{display:block;height:100%;width:0;background:var(--accent);transition:width .2s}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px;min-height:300px;display:flex;flex-direction:column}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.tag{font-size:11px;padding:2px 8px;border-radius:99px;background:#e7f2ef;color:var(--accent)}
.front{font-size:20px;font-weight:700;line-height:1.55;margin:4px 0 16px}
.back{display:none;border-top:1px dashed var(--line);padding-top:14px;color:var(--ink);font-size:16px;line-height:1.8;white-space:pre-wrap}
.back.show{display:block}
mark{background:#fbe7c8;color:#7a4c16;padding:0 2px;border-radius:3px}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:auto;padding-top:18px}
button{font:inherit;border:0;border-radius:9px;padding:9px 14px;cursor:pointer;background:var(--accent);color:#fff}
button.secondary{background:#e7f2ef;color:var(--accent)}
button.warn{background:#fbf1e3;color:#7a4c16}
button.risk{background:#f7e8e8;color:var(--risk)}
button:disabled{opacity:.45;cursor:not-allowed}
.rate{display:none;gap:8px;flex-wrap:wrap;margin-top:10px}
.rate.show{display:flex}
.rate button{flex:1;min-width:110px}
footer{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-top:18px}
footer button{background:#fff;color:var(--muted);border:1px solid var(--line);font-size:12px;padding:7px 10px}
.hint{font-size:11px;color:var(--muted);text-align:center;margin-top:12px}
@media(max-width:480px){.wrap{padding:16px 12px 36px}h1{font-size:19px}header{align-items:flex-start;flex-direction:column}.front{font-size:18px}.card{padding:16px;min-height:280px}.rate button{min-width:44%}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div><h1>__TITLE__</h1><div class="sub">离线复习 · 本地进度 · 不采集个人信息</div></div>
    <div class="stats" id="stats">—</div>
  </header>
  <div class="bar"><i id="bar"></i></div>
  <main class="card">
    <div class="tags" id="tags"></div>
    <div class="front" id="front">加载中…</div>
    <div class="back" id="back"></div>
    <div class="actions">
      <button id="show">显示答案</button>
      <button class="secondary" id="skip">跳过</button>
    </div>
    <div class="rate" id="rate">
      <button class="risk" data-r="0">0 忘了</button>
      <button class="warn" data-r="1">1 模糊</button>
      <button data-r="2">2 记得</button>
      <button class="secondary" data-r="3">3 很熟</button>
    </div>
  </main>
  <footer>
    <button id="export">导出进度</button>
    <button id="importBtn">导入进度</button>
    <input id="importFile" type="file" accept="application/json" style="display:none">
    <button id="reset">重置进度</button>
  </footer>
  <div class="hint">快捷键：空格显示答案 · 1/2/3/4 评分 · → 跳过</div>
</div>
<script>
const ITEMS = __DATA__;
const KEY = "__KEY__";
let state = JSON.parse(localStorage.getItem(KEY) || "{}");
let idx = 0;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
const cloze = (s) => esc(s).replace(/\{\{c1::(.+?)\}\}/g, "<mark>$1</mark>");
function current() { return ITEMS[idx]; }
function save() { localStorage.setItem(KEY, JSON.stringify(state)); }
function seen() { return Object.keys(state).filter(k => state[k] && state[k].seen).length; }
function updateStats() {
  $("stats").textContent = `${seen()} / ${ITEMS.length} 已看`;
  $("bar").style.width = `${ITEMS.length ? (seen()/ITEMS.length*100) : 0}%`;
}
function render() {
  const it = current();
  if (!it) {
    $("front").textContent = "本轮完成。可导出进度，或重置后重来。";
    $("back").textContent = ""; $("tags").innerHTML = "";
    $("show").disabled = true; $("skip").disabled = true;
    $("rate").classList.remove("show"); updateStats(); return;
  }
  $("tags").innerHTML = (it.tags || []).slice(0,4).map(t => `<span class="tag">${esc(t)}</span>`).join("");
  $("front").innerHTML = cloze(it.front);
  $("back").innerHTML = cloze(it.back);
  $("back").classList.remove("show");
  $("rate").classList.remove("show");
  $("show").disabled = false; $("skip").disabled = false;
  updateStats();
}
function reveal() { $("back").classList.add("show"); $("rate").classList.add("show"); $("show").disabled = true; }
function rate(r) {
  const it = current(); if (!it) return;
  state[it.item_id] = { seen:true, last_rating:r, updated_at:new Date().toISOString() };
  save(); idx++; render();
}
$("show").onclick = reveal;
$("skip").onclick = () => { idx++; render(); };
document.querySelectorAll("#rate button").forEach(b => b.onclick = () => rate(Number(b.dataset.r)));
$("export").onclick = () => {
  const blob = new Blob([JSON.stringify(state, null, 2)], {type:"application/json"});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = "medagentwork_pilot_ent_progress.json"; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};
$("importBtn").onclick = () => $("importFile").click();
$("importFile").onchange = (e) => {
  const f = e.target.files[0]; if (!f) return;
  const reader = new FileReader();
  reader.onload = () => { try { state = JSON.parse(reader.result); save(); render(); } catch (_) { alert("JSON 解析失败"); } };
  reader.readAsText(f);
};
$("reset").onclick = () => { if (confirm("清空本地进度？")) { state = {}; save(); idx = 0; render(); } };
document.addEventListener("keydown", (e) => {
  if (e.code === "Space") { e.preventDefault(); if (!$("show").disabled) reveal(); }
  else if (e.key === "ArrowRight") { idx++; render(); }
  else if (/^[1-4]$/.test(e.key)) { if ($("rate").classList.contains("show")) rate(Number(e.key)-1); }
});
render();
</script>
</body>
</html>
"""


def load_items(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def render(items: list[dict], title: str) -> str:
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    return (TEMPLATE
            .replace("__TITLE__", html.escape(title))
            .replace("__DATA__", data)
            .replace("__KEY__", KEY))


def main() -> int:
    _configure_stdio()
    ap = argparse.ArgumentParser(description="生成离线复习 HTML")
    ap.add_argument("--items", default=str(DEFAULT_ITEMS))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--title", default="耳鼻咽喉头颈外科学 · 教师重点版复习")
    args = ap.parse_args()
    items = load_items(Path(args.items))
    if not items:
        print(f"[FAIL] 无卡片：{args.items}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(items, args.title), encoding="utf-8")
    print(f"✅ 离线复习 HTML：{len(items)} 张 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
