/**
 * /drill/* → MedKit 刷题网页版（agentos 沙箱）。
 *
 * 2026-10-20 起：**页面直接 302 到源站**，不再把整站反代过来。
 * 原因：反代链路是「浏览器 → Cloudflare 边缘 → 北京沙箱」，每次 API 往返实测
 * 1.4~7.5 秒；直连源站同一次调用只要 0.45 秒。刷题页一次会话要打几十次接口，
 * 这笔过路费省不得。站点上的「做题」入口链接不必改——点 /drill 就跳过去。
 *
 * 仍保留反代的部分：/drill/api/*。
 * 旧缓存页（SW 或浏览器里的 /drill 页面）仍在 pages.dev 域上，它的相对路径
 * 请求会打到 /drill/api/*；这条通道留着，老页面不会被一脚踢死。
 *
 * 路径映射：/drill → 302 → UPSTREAM/ ；/drill/api/x → 反代到 UPSTREAM/api/x。
 * 注意剥掉 content-encoding / content-length：Workers fetch 会自动解压，
 * 原样透传这两个头会让浏览器按压缩流解已解压的 body（花屏）。
 *
 * 2026-10-19 的 522 兜底（GET 重试 / 12s 超时 / 「正在唤醒」页）保留在反代分支上。
 */

const UPSTREAM = "https://senior-quiz-app.app.workbuddy.host";
const BACKOFF_MS = [300, 900];
const ORIGIN_TIMEOUT_MS = 12000;

/** 幂等请求才重试：POST /api/grade 重试会多记一次作答，宁可失败也不重放 */
function attempts(method) {
  return method === "GET" || method === "HEAD" ? BACKOFF_MS.length + 1 : 1;
}

export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  const path = url.pathname.replace(/^\/drill/, "") || "/";

  /* 页面类请求（GET/HEAD 且非 /api/）→ 直接跳源站，浏览器之后所有请求都在
     源站同域直连，不再经过 Cloudflare → 北京这一跳。302 让源站域名变更时
     不用等浏览器缓存过期太久。 */
  if ((request.method === "GET" || request.method === "HEAD") && !path.startsWith("/api/")) {
    return new Response(null, {
      status: 302,
      headers: {
        location: UPSTREAM + path + url.search,
        "cache-control": "public, max-age=300",
      },
    });
  }

  const headers = new Headers(request.headers);
  headers.delete("host");           // Host 由 fetch 目标决定，别把 pages.dev 的 Host 带给上游
  const init = { method: request.method, headers, redirect: "manual" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;       // 流式透传（POST /api/enter 等）
  }

  const target = new URL(path + url.search, UPSTREAM).toString();
  const tries = attempts(request.method);
  let lastError = null;

  for (let i = 0; i < tries; i += 1) {
    try {
      const resp = await fetch(target, {
        ...init,
        signal: AbortSignal.timeout(ORIGIN_TIMEOUT_MS),
      });
      const outHeaders = new Headers(resp.headers);
      outHeaders.delete("content-encoding");
      outHeaders.delete("content-length");
      return new Response(resp.body, {
        status: resp.status,
        statusText: resp.statusText,
        headers: outHeaders,
      });
    } catch (err) {
      lastError = err;
      if (i < tries - 1) {
        await new Promise((resolve) => setTimeout(resolve, BACKOFF_MS[i] || 900));
      }
    }
  }

  console.log(`[drill] origin unreachable: ${request.method} ${target} — ${lastError}`);
  return offline(path);
}

/** 源站不可达时的握手页：别再让用户对着 Cloudflare 的英文 522 发呆 */
function offline(path) {
  const retryAfter = "4";
  const base = {
    "cache-control": "no-store",
    "retry-after": retryAfter,
  };

  if (path.startsWith("/api/")) {
    return new Response(
      JSON.stringify({ detail: "刷题服务正在唤醒（约 5 秒），请稍后重试" }),
      { status: 503, headers: { ...base, "content-type": "application/json; charset=utf-8" } },
    );
  }

  const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>刷题服务正在唤醒</title>
<style>
  :root{--bg:#f6f7f9;--card:#fff;--text:#1a1d21;--muted:#6b7280;--line:#e5e7eb;--primary:#2f6bff}
  @media (prefers-color-scheme:dark){:root{--bg:#111418;--card:#1a1f24;--text:#e8eaed;--muted:#9aa3ad;--line:#2a3037;--primary:#4f8bff}}
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;
       background:var(--bg);color:var(--text);
       font:16px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",system-ui,sans-serif}
  .card{width:100%;max-width:380px;background:var(--card);border:1px solid var(--line);
        border-radius:18px;padding:26px 22px;text-align:center}
  h1{margin:0 0 8px;font-size:19px}
  p{margin:0 0 16px;color:var(--muted);font-size:14px}
  .bar{height:4px;border-radius:2px;background:var(--line);overflow:hidden;margin-bottom:18px}
  .bar i{display:block;height:100%;width:38%;border-radius:2px;background:var(--primary);
         animation:slide 1.15s ease-in-out infinite}
  @keyframes slide{0%{transform:translateX(-110%)}100%{transform:translateX(340%)}}
  a{display:block;min-height:48px;line-height:48px;border-radius:12px;background:var(--primary);
    color:#fff;text-decoration:none;font-weight:600;font-size:15px}
  .tip{margin-top:12px;font-size:12.5px;color:var(--muted)}
</style></head>
<body><div class="card">
  <h1>刷题服务正在唤醒</h1>
  <p>做题数据都在，只是服务刚睡醒。约 ${retryAfter} 秒后自动重试。</p>
  <div class="bar"><i></i></div>
  <a href="" id="again">立即重试</a>
  <div class="tip">若持续打不开，说明服务需要重新发布，请联系维护者。</div>
</div>
<script>setTimeout(function(){location.reload();}, ${Number(retryAfter) * 1000});</script>
</body></html>`;

  return new Response(html, {
    status: 503,
    headers: { ...base, "content-type": "text/html; charset=utf-8" },
  });
}
