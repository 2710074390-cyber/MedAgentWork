/**
 * /drill/* → 参赛版刷题（medkit-web-contest，WorkBuddy Sites 应用）。
 *
 * 2026-10-29 替换：老线上版（senior-quiz-app，带账号的 FastAPI + SQLite）退役，
 * 历史做题数据**不迁移**（用户决策：直接替换）。站点上的「做题」入口链接不必改
 * ——全部指向 /drill，由这里跳过去。
 *
 * 参赛版是纯前端 SPA，应用宿主对**每个请求**都校验 ?sharecode=（不带即 403「链接不完整」）；
 * 首次带 sharecode 访问会种 __wb_rsc cookie（30 天、HttpOnly、SameSite=None），
 * 之后页面里的相对请求（js / css / data/questions.json）靠 cookie 放行。
 * 已实测（2026-10-29，curl）：带该 cookie 裸取 /js/store.js 与 /data/questions.json 均 200。
 *
 * 所以这里只做一件事：/drill/* → 302 → 带 sharecode 的入口页。
 * 浏览器之后全部直连源站，不过 Cloudflare 这一跳（理由同 2026-10-20：
 * 反代链路每次往返实测 1.4~7.5 秒，直连只要 0.45 秒）。
 * 保留 #hash：老入口可能带页签锚点（如 /drill#learn）。
 * 2026-10-20 的 /drill/api/* 反代分支与 522「正在唤醒」兜底页随老版一并退役——
 * 参赛版零后端、零 API，SW 里的旧缓存页自然过期。
 */

const ENTRY = "https://medkit-study-app.app.workbuddy.host/?sharecode=A3MSLC6PSQ";

export async function onRequest(context) {
  const { hash } = new URL(context.request.url);
  return new Response(null, {
    status: 302,
    headers: {
      location: ENTRY + (hash || ""),
      // 302 可缓存 5 分钟：源站域名/分享码变更时最多 5 分钟生效
      "cache-control": "public, max-age=300",
    },
  });
}
