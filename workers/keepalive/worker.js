/**
 * medkit-keepalive —— 每 5 分钟戳一次刷题应用，防止 WorkBuddy 沙箱空闲休眠。
 *
 * 为什么不用 GitHub Actions 的 schedule：本仓定时任务实测延迟极大
 * （Security Audit 周日 00:00 UTC 的计划任务，03:56 UTC 才跑），
 * 撑不住 5 分钟粒度的保活。Cloudflare Cron 基本准点。
 *
 * 手动查看状态：直接浏览器打开本 Worker 的 workers.dev 地址（fetch 分支会回 JSON）。
 * 部署：scripts/deploy_keepalive.py（走 Workers API，不需要 wrangler/账号登录态）。
 */

const PING_URL = "https://senior-quiz-app.app.workbuddy.host/api/ping";

async function ping() {
  const started = Date.now();
  try {
    const r = await fetch(PING_URL, { cf: { cacheTtl: 0 } });
    const body = await r.text();
    return { ok: r.ok, status: r.status, body: body.trim().slice(0, 200), ms: Date.now() - started };
  } catch (err) {
    return { ok: false, status: 0, body: String(err), ms: Date.now() - started };
  }
}

export default {
  async scheduled(event, env, ctx) {
    const res = await ping();
    console.log(JSON.stringify({ at: new Date().toISOString(), ...res }));
    // 失败就抛：Workers 的 cron 指标里能看到红，不至于静默失效
    if (!res.ok) throw new Error("keepalive failed: " + res.body);
  },

  async fetch() {
    const res = await ping();
    return new Response(JSON.stringify(res, null, 2), {
      status: res.ok ? 200 : 503,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store",
      },
    });
  },
};
