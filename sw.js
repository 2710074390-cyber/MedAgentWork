/* MedAgentWork Service Worker（P2 · 渐进式离线）
   策略：
   - 导航请求 network-first：在线永远最新，离线回退应用壳（首页）
   - 静态资源（md/图片/字体等）stale-while-revalidate：先给缓存、后台刷新
   - PDF 一律不缓存（单文件可达 20MB+，避免撑爆配额）——离线可读的是手册 MD
   - 版本号变更即整体换血：旧缓存自动清理
   2026-10-19：修复"任意导航响应都写成 /index.html"的缓存串台问题——
   此前 /drill 等路由的响应会覆写首页离线副本；现在只缓存真正的首页。
*/
const VERSION = 'maw-v2';
const SHELL_CACHE = VERSION + '-shell';
const ASSET_CACHE = VERSION + '-assets';
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icon-192.png', '/icon-512.png'];
const ASSET_RE = /\.(?:md|txt|csv|png|jpe?g|webp|svg|css|js|woff2?)$/i;
const ASSET_MAX = 90;   /* 缓存条目上限，FIFO 淘汰 */

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(SHELL_CACHE)
      .then(c => c.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => !k.startsWith(VERSION)).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

async function trim(cache) {
  const keys = await cache.keys();
  if (keys.length > ASSET_MAX) {
    for (let i = 0; i < keys.length - ASSET_MAX; i++) await cache.delete(keys[i]);
  }
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  let u;
  try { u = new URL(req.url); } catch (_) { return; }
  if (u.origin !== location.origin) return;

  /* 导航：network-first，离线回退应用壳（首页） */
  if (req.mode === 'navigate') {
    const isShell = u.pathname === '/' || u.pathname === '/index.html';
    e.respondWith(
      fetch(req).then(r => {
        if (r.ok && isShell) {   /* 只缓存真正的首页：路由页响应不得覆写应用壳 */
          const cp = r.clone();
          caches.open(SHELL_CACHE).then(c => c.put('/index.html', cp)).catch(() => {});
        }
        return r;
      }).catch(() => caches.match('/index.html'))
    );
    return;
  }

  /* 静态资源：stale-while-revalidate */
  if (!ASSET_RE.test(u.pathname)) return;
  e.respondWith(
    caches.open(ASSET_CACHE).then(async c => {
      const hit = await c.match(req);
      const net = fetch(req).then(r => {
        if (r.ok) c.put(req, r.clone()).then(() => trim(c)).catch(() => {});
        return r;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
