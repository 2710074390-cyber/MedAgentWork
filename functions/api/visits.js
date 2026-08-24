/**
 * 访问计数器 — GET /api/visits
 *
 * 规则：
 *  - 默认：把 KV 中的 `total_v1` 加 1，并返回累计值（每次打开首页计 1 次）
 *  - 站长免计：请求带 Cookie `maw_owner=1`（由前端 ?noself=1 在本机设置一次）
 *    或查询参数 `noself` 时，不计数，只返回当前累计值
 *  - 未绑定 KV（如 Preview 部署）时返回 { total: null }，前端显示「—」，站点不完全依赖本功能
 *
 * 说明：KV 的读-改-写不是原子的，极端并发下可能丢失极少量计数；对班级级访问量无影响。
 */
const KEY = 'total_v1';

export async function onRequestGet({ env, request }) {
  const url = new URL(request.url);
  const cookies = request.headers.get('Cookie') || '';
  const skip = cookies.includes('maw_owner=1') || url.searchParams.has('noself');

  const json = (data) =>
    new Response(JSON.stringify(data), {
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store',
      },
    });

  // KV 未绑定（例如 Preview 部署）或读取异常：不计数，返回 null 让前端降级显示
  if (!env.VISITS) return json({ total: null, skip });

  try {
    const cur = parseInt((await env.VISITS.get(KEY)) || '0', 10) || 0;
    const total = skip ? cur : cur + 1;
    if (!skip) await env.VISITS.put(KEY, String(total));
    return json({ total, skip });
  } catch (e) {
    return json({ total: null, skip });
  }
}
