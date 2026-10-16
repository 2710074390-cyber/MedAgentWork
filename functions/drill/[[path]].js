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
 */

const UPSTREAM = "https://53863187380f488cb25b6f9dd0ba1dff.sg.agentos-app.run";

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

  const resp = await fetch(new URL(path + url.search, UPSTREAM), init);

  const outHeaders = new Headers(resp.headers);
  outHeaders.delete("content-encoding");
  outHeaders.delete("content-length");
  return new Response(resp.body, {
    status: resp.status,
    statusText: resp.statusText,
    headers: outHeaders,
  });
}
