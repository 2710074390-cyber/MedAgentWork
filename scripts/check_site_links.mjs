/**
 * check_site_links.mjs — 站点下载/预览链接门禁
 *
 * 原理：不"猜"路径，而是把 index.html 里的脚本真正执行一遍（stub DOM），
 *      用页面自己的 urlAt()/BASE 逻辑解析出每个按钮点击后请求的 URL，
 *      再逐个探测线上/本地是否存在。
 *
 * 用法：
 *   node check_site_links.mjs <index.html> [--base https://site/] [--json]
 *
 * 退出码：0 = 全部可达；1 = 存在断链（fail-closed）
 */
import fs from "node:fs";
import path from "node:path";

const file = process.argv[2];
if (!file) { console.error("用法: node check_site_links.mjs <index.html> [--base URL]"); process.exit(2); }
const argv = process.argv.slice(3);
const BASE_URL = (() => { const i = argv.indexOf("--base"); return i >= 0 ? argv[i + 1] : null; })();
const AS_JSON = argv.includes("--json");

const html = fs.readFileSync(file, "utf8");
const realFetch = globalThis.fetch;   // 必须在 stub 之前抓住真实 fetch
const realTimers = {                       // undici 内部依赖真实的定时器对象（有 .unref()）
  setTimeout: globalThis.setTimeout, clearTimeout: globalThis.clearTimeout,
  setInterval: globalThis.setInterval, clearInterval: globalThis.clearInterval,
};

/* ---------- 1. 抽出唯一一段 <script> ---------- */
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (scripts.length !== 1) { console.error(`[X] 期望 1 段 script，实际 ${scripts.length} 段`); process.exit(2); }
const src = scripts[0];

/* ---------- 2. 切到卡片渲染完成处（之后全是 DOM 副作用） ---------- */
const CUT = "$('#grid-exam').innerHTML=";
const cutAt = src.indexOf(CUT);
if (cutAt < 0) { console.error("[X] 找不到切点 " + CUT); process.exit(2); }
const core = src.slice(0, cutAt);

/* ---------- 3. stub DOM，执行核心脚本 ---------- */
const stub = {
  innerHTML: "", textContent: "", className: "", value: "", scrollTop: 0, onclick: null,
  dataset: {}, style: { setProperty() {} },
  classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
  addEventListener() {}, appendChild() {}, remove() {}, click() {}, focus() {}, print() {},
  querySelector() { return stub; }, querySelectorAll() { return []; }, closest() { return null; },
  getBoundingClientRect() { return { left: 0, top: 0 }; },
};
const g = globalThis;
g.document = {
  querySelector: () => stub, querySelectorAll: () => [], createElement: () => stub,
  getElementById: () => stub, addEventListener() {}, body: stub, documentElement: stub,
  readyState: "complete", write() {}, close() {},
};
g.window = { addEventListener() {}, open: () => null, scrollTo() {}, focus() {}, print() {}, document: g.document,
  localStorage: { getItem: () => null, setItem() {} }, matchMedia: () => ({ matches: false, addEventListener() {} }) };
g.location = { hash: "", href: "", replace() {} };
g.IntersectionObserver = class { constructor() {} observe() {} unobserve() {} disconnect() {} };
g.setInterval = () => 0;
g.clearInterval = () => {};
g.setTimeout = () => 0;
g.clearTimeout = () => {};
g.requestAnimationFrame = () => 0;
g.fetch = () => Promise.reject(new Error("stub"));

/* ---------- 4. 驱动：渲染每张卡，抽出 onclick 里的真实请求 ---------- */
const DRIVER = `
;globalThis.__probe = (function(){
  const targets = [];
  /* 兼容两种约定：旧版（BASE + urlAt 拼前缀）与新版（path 自带仓库根） */
  const ROOTBASE = (typeof BASE === "undefined") ? null : BASE;
  const HAS_URLAT = (typeof urlAt === "function");
  const resolve = (base, p) => HAS_URLAT ? urlAt(base, p) : encPath(p);

  function splitArgs(s){
    const out = []; let depth = 0, cur = "", q = null;
    for (const ch of s) {
      if (q) { cur += ch; if (ch === q) q = null; continue; }
      if (ch === "'" || ch === '"' || ch === "\`") { q = ch; cur += ch; continue; }
      if ("([{".includes(ch)) depth++;
      if (")]}".includes(ch)) depth--;
      if (ch === "," && depth === 0) { out.push(cur.trim()); cur = ""; continue; }
      cur += ch;
    }
    if (cur.trim()) out.push(cur.trim());
    return out;
  }
  function lit(s){ s = s.trim(); return (s[0] === "'" || s[0] === '"') ? s.slice(1, -1) : s; }

  function scan(fn, arr, label){
    arr.forEach((it, i) => {
      const h = fn(it, i);
      for (const m of h.matchAll(/onclick="([^"]+)"/g)) {
        const call = m[1];
        const mm = call.match(/^([A-Za-z_$][\\w$]*)\\((.*)\\)$/);
        if (!mm) { targets.push({label, name: it.name, handler: call, url: null, note: "无法解析"}); continue; }
        const fnName = mm[1], args = splitArgs(mm[2]);
        const p = lit(args[0]);
        let base, kind;
        if (fnName === "downloadFile") { base = args[3] ? lit(args[3]) : ROOTBASE; kind = "下载"; }
        else { base = ROOTBASE; kind = fnName === "viewOnline" ? "打开" : fnName === "printHTML" ? "打印" : fnName === "previewMD" ? "阅读" : "打印"; }
        targets.push({ label, name: it.name, kind, fn: fnName, path: p, base,
                       url: resolve(base, p), declaredBase: args[3] ? lit(args[3]) : null });
      }
    });
  }

  scan(examCard, EXAMS, "大三下·押题卷");
  scan(bankCard, BANKS, "大三下·题库");
  scan(reviewCard, REVIEWS, "大三下·复习资料");
  scan(reviewS1Card, REVIEWS_S1, "大四上·教学版资料");
  scan(bankCard, BANKS_S1, "大四上·题库");
  return { BASE: ROOTBASE, convention: HAS_URLAT ? "BASE+urlAt（旧）" : "仓库根相对（新）", targets };
})();
`;

new Function(core + DRIVER)();
/* 恢复真实定时器：undici 依赖 setTimeout 返回带 unref() 的 Timeout 对象 */
Object.assign(globalThis, realTimers);
const { BASE, convention, targets } = g.__probe;

/* ---------- 5. 探测 ---------- */
/* 只查状态码是不够的：Cloudflare Pages 在没有 404.html 时会把未命中路径
   回退成 index.html，返回 200 + text/html。所以必须同时断言 Content-Type。 */
const EXPECT = [
  [/\.pdf$/i, ["application/pdf"]],
  [/\.md$/i, ["text/markdown", "text/plain"]],
  [/\.html?$/i, ["text/html"]],
];
function expectTypes(u) {
  const e = EXPECT.find(([re]) => re.test(u));
  return e ? e[1] : null;               // null = 不约束
}
function mimeOk(u, ct) {
  const want = expectTypes(u);
  if (!want) return true;
  if (!ct) return false;
  return want.includes(ct.split(";")[0].trim().toLowerCase());
}

async function probe(u) {
  if (!u) return { status: "SKIP", note: "空路径" };
  if (!BASE_URL) {                                  // 本地文件模式：直接看仓库里文件在不在
    const f = path.resolve(path.dirname(file), decodeURIComponent(u));
    return fs.existsSync(f) ? { status: 200, bytes: fs.statSync(f).size, local: true }
                            : { status: 404, local: true };
  }
  try {
    const r = await realFetch(BASE_URL + u, { headers: { "User-Agent": "link-gate" } });
    return { status: r.status, type: r.headers.get("content-type"), bytes: Number(r.headers.get("content-length") || 0) };
  } catch (e) { return { status: "ERR", note: String(e) }; }
}

const results = [];
for (const t of targets) {
  const r = await probe(t.url);
  const ok = r.status === 200 && (r.local === true || mimeOk(t.url, r.type));
  results.push({ ...t, ...r, ok, expect: expectTypes(t.url) });
}

/* ---------- 6. 报告 ---------- */
/* "检查通过" 与 "检查没跑" 必须能区分：抽不到目标一律视为失败 */
if (targets.length === 0) { console.error("[X] 未抽到任何链接目标 —— 页面结构可能已变，门禁失效"); process.exit(2); }
const bad = results.filter(r => !r.ok);
if (AS_JSON) {
  console.log(JSON.stringify({ BASE, convention, total: results.length, bad: bad.length, results }, null, 2));
} else {
  console.log(`路径约定=${convention}  目标=${results.length}  异常=${bad.length}\n`);
  const groups = {};
  for (const r of results) (groups[r.label] ||= []).push(r);
  for (const [label, rs] of Object.entries(groups)) {
    const n = rs.filter(r => !r.ok).length;
    console.log(`【${label}】${rs.length} 项，异常 ${n}`);
    for (const r of rs) {
      const flag = r.ok ? "  OK " : " FAIL";
      console.log(`${flag} ${String(r.status).padStart(4)} ${String(r.type || "-").padEnd(28)} ${r.kind} ${r.name.padEnd(12)} ${r.url}`);
      if (!r.ok) console.log(`       ← 请求路径=${r.path}  期望类型=${JSON.stringify(r.expect)}`);
    }
    console.log("");
  }
}
process.exit(bad.length ? 1 : 0);
