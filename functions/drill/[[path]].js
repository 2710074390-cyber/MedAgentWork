/**
 * /drill/* → MedKit 刷题网页版（agentos 沙箱）反向代理。
 *
 * 为什么用代理而不是直接给外部链接：
 * - 同域：cookie（会话）落在 pages.dev 上，Set-Cookie 原样透传即生效；
 * - 用户看到的是 med-review-site.pages.dev/drill，与本站一体。
 *
 * 路径映射：/drill → / ；/drill/api/x → /api/x（查询串原样保留）。
 * 注意剥掉 content-encoding / content-length：Workers fetch 会自动解压，
 * 原样透传这两个头会让浏览器按压缩流解已解压的 body（花屏）。
 *
 * 2026-10-19：源站是单实例沙箱，空闲会休眠/重启，那一刻 Cloudflare 连不上
 * 源站就直接甩 522 官方错误页——用户只看到 “Connection timed out”，
 * 且页面不会自己恢复。这里兜住三件事：
 *   1) GET/HEAD 失败重试（300ms / 900ms 退避），挡住瞬断与刚唤醒的第一跳；
 *   2) 每个子请求 12s 超时，避免一次卡死把整个边缘请求拖穿；
 *   3) 仍旧失败时回自己的 503：页面站给一张「正在唤醒，几秒后自动重试」的卡，
 *      接口路径给 JSON 503（前端 toast 能直接显示 detail）。
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
