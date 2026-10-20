#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_site_freshness.py — 站点最新性契约门禁（HC-21 · 2026-10-19）

背景（batch040 实证）
    本地把 batch040 题库/复习资料 PDF 部署到生产后 3 分钟，另一次生产部署
    （来自本地没有的提交 4531093）把它顶掉 → 线上 index.html 回到旧版
    （5,791 题 / 8 科 / 无「教师重点版」条目），用户打开网站看不到新资料。
    根因：① 部署源不是「唯一事实源」；② 部署后没有任何「线上是否仍是本次内容」
    的机械校验；③ index.html 里硬编码的「N 科 / N 题」文案与数据数组各自维护，
    漏改一处就会出现「卡片有了、标题还写 8 科」的半更新状态。

本脚本三层校验（2026-10-20 契约更新：计数改由数据派生）
    L1 本地一致性（离线可跑）：① markup（<script>/<style> 之外）内**不得**出现
       任何「N 科 / N 题 / N,NNN」硬编码计数文案——它们一律由数据数组在渲染时派生，
       杜绝「卡片有了、标题还写 8 科」的半更新形态；② 必须存在 `const SITE_STATS`
       派生入口；③ 每条 pdf/md 路径必须在仓库内存在。
    L2 线上指纹一致性：拉取站点 index.html，比对数据数组条目数、本地每条路径是否
       都出现在线上、对外统计数字集合是否一致、派生入口是否存在（防「卡片没上线」）。
    L3 最新生产部署来源：要求「最新 Production/main 部署的 Source」== 期望提交
       （--expect-commit），否则说明已被更晚的部署顶替。

用法
    python scripts/check_site_freshness.py --offline
    python scripts/check_site_freshness.py
    python scripts/check_site_freshness.py --expect-commit bba5e49
    python scripts/check_site_freshness.py --base https://xxx.pages.dev/

退出码: 0 = PASS；1 = FAIL；2 = 环境/参数错误
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = 'https://med-review-site.pages.dev/'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/139.0 Safari/537.36')

KEY_TAG = '教师重点版'   # 与 index.html 中 S1_KEY_TAG 一致
SITE_STATS_RE = re.compile(r'\bconst\s+SITE_STATS\s*=')
# markup 内禁止出现的计数文案：N 科 / N 题 / N,NNN
COUNT_LIT_RE = re.compile(r'\d+\s*[科题]|\d{1,3},\d{3}')


def markup_region(html: str) -> str:
    """去掉 <script> / <style> 区块，只留下写给人看的静态文案区。"""
    out = re.sub(r'<script\b[\s\S]*?</script>', '', html, flags=re.I)
    return re.sub(r'<style\b[\s\S]*?</style>', '', out, flags=re.I)


# ────────────────────────── 解析工具 ──────────────────────────

def parse_arrays(html: str):
    """返回 (reviews, banks)：每个条目为 dict(name/path/tags)"""
    out = {}
    for arr in ('REVIEWS_S1', 'BANKS_S1'):
        m = re.search(r'const ' + arr + r'=\[(.*?)\n\];', html, re.S)
        body = m.group(1) if m else ''
        items = []
        for line in body.split('\n'):
            mm = re.search(r"\{name:'([^']*)',(?:pdf|md):'([^']*)'(.*)\},?\s*$", line.strip())
            if not mm:
                continue
            tags = re.findall(r"'([^']*)'", (re.search(r"tags:\[([^\]]*)\]", mm.group(3)) or
                                             re.match(r'', '')).group(1)) if 'tags:[' in mm.group(3) else []
            items.append({'name': mm.group(1), 'path': mm.group(2), 'tags': tags})
        out[arr] = items
    return out['REVIEWS_S1'], out['BANKS_S1']


def counts(html: str, arr_items):
    key = [i for i in arr_items if KEY_TAG in i['tags']]
    teach = [i for i in arr_items if KEY_TAG not in i['tags']]
    return len(arr_items), len(key), len(teach)


def stats_set(html: str):
    """页面所有「N,NNN」型对外数字集合"""
    return set(re.findall(r'(\d{1,3},\d{3})', html))


def problems_local(html: str, reviews, banks):
    p = []
    # 1) 计数单一事实来源：markup 内不得存在可漂移的硬编码计数文案
    lits = sorted({m.group(0) for m in COUNT_LIT_RE.finditer(markup_region(html))})
    if lits:
        p.append('markup 内仍有硬编码计数文案（应改为数据派生）：' + ', '.join(lits[:8]))
    # 2) 派生入口必须存在
    if not SITE_STATS_RE.search(html):
        p.append('未找到 const SITE_STATS —— 对外计数没有从数据数组派生（HC-21）')
    # 3) 每条 pdf/md 路径必须在仓库内存在
    for label, arr in (('复习资料', reviews), ('题库', banks)):
        for it in arr:
            if not (ROOT / it['path']).exists():
                p.append(f'{label}条目「{it["name"]}」的本地文件缺失：{it["path"]}')
    n_all_r, n_key_r, n_teach_r = counts(html, reviews)
    n_all_b, n_key_b, n_teach_b = counts(html, banks)
    return p, (n_all_r, n_key_r, n_teach_r), (n_all_b, n_key_b, n_teach_b)


def problems_online(local_html: str, online_html: str, reviews, banks):
    p = []
    o_r, o_b = parse_arrays(online_html)
    if len(o_r) != len(reviews):
        p.append(f'线上 REVIEWS_S1 {len(o_r)} 条 ≠ 本地 {len(reviews)} 条')
    if len(o_b) != len(banks):
        p.append(f'线上 BANKS_S1 {len(o_b)} 条 ≠ 本地 {len(banks)} 条')
    for it in reviews + banks:
        if it['path'] not in online_html:
            p.append(f'线上 index.html 未引用本地条目：{it["path"]}')
    ls, os_ = stats_set(local_html), stats_set(online_html)
    if ls != os_:
        p.append(f'线上/本地对外统计数字不一致：仅本地 {sorted(ls - os_)}；仅线上 {sorted(os_ - ls)}')
    if not SITE_STATS_RE.search(online_html):
        p.append('线上 index.html 缺少 const SITE_STATS 派生入口')
    return p


def newest_production_source(project='med-review-site'):
    """解析 wrangler pages deployment list，取最新 Production/main 部署的 Source（短 sha）。"""
    cmd = ['wrangler', 'pages', 'deployment', 'list', '--project-name', project]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                           encoding='utf-8', errors='replace', shell=True)
    except Exception as e:
        return None, f'调用 wrangler 失败：{e}'
    out = re.sub(r'\x1b\[[0-9;]*m', '', r.stdout or '')
    for line in out.splitlines():
        if 'Production' not in line or '│' not in line:
            continue
        cells = [c.strip() for c in line.split('│')]
        cells = [c for c in cells if c]
        if len(cells) < 4:
            continue
        src = cells[3]
        if re.fullmatch(r'[0-9a-f]{7,40}', src):
            return src, None
    return None, f'未能解析部署清单（exit={r.returncode}）'


def main() -> int:
    ap = argparse.ArgumentParser(description='站点最新性契约门禁（HC-21）')
    ap.add_argument('--base', default=DEFAULT_BASE)
    ap.add_argument('--offline', action='store_true', help='只跑本地一致性（L1）')
    ap.add_argument('--expect-commit', help='要求最新 Production/main 部署的 Source 等于该提交')
    ap.add_argument('--project', default='med-review-site')
    args = ap.parse_args()

    print('=== 站点最新性契约门禁 check_site_freshness.py（HC-21）===')
    idx = ROOT / 'index.html'
    if not idx.exists():
        print('ERROR —— 找不到 index.html')
        return 2
    html = idx.read_text(encoding='utf-8')
    reviews, banks = parse_arrays(html)
    print(f'  本地 index.html：REVIEWS_S1={len(reviews)} 条 / BANKS_S1={len(banks)} 条')

    fails = []
    p1, cr, cb = problems_local(html, reviews, banks)
    print(f'  L1 本地文案/数据一致性：{"OK" if not p1 else "FAIL"}'
          f' ｜复习资料 {cr[0]} 条（教师重点版 {cr[1]} / 教学计划版 {cr[2]}）'
          f' ｜题库 {cb[0]} 条（教师重点版 {cb[1]} / 教学题库 {cb[2]}）')
    for x in p1:
        print(f'    ❌ {x}')
    fails += p1

    if not args.offline:
        import urllib.request
        url = args.base.rstrip('/') + '/index.html?cb=' + str(int(time.time()))
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Cache-Control': 'no-cache'})
            online = urllib.request.urlopen(req, timeout=45).read().decode('utf-8', 'replace')
        except Exception as e:
            print(f'  L2 线上指纹：❌ 拉取失败 {type(e).__name__}: {e}')
            fails.append('线上不可达')
            online = None
        if online is not None:
            p2 = problems_online(html, online, reviews, banks)
            print(f'  L2 线上指纹一致性：{"OK" if not p2 else "FAIL"}（{len(online)} bytes）')
            for x in p2:
                print(f'    ❌ {x}')
            fails += p2

    if args.expect_commit:
        src, err = newest_production_source(args.project)
        if err:
            print(f'  L3 最新生产部署来源：❌ {err}')
            fails.append(err)
        elif src.startswith(args.expect_commit) or args.expect_commit.startswith(src):
            print(f'  L3 最新生产部署来源：OK（{src} == {args.expect_commit}）')
        else:
            msg = (f'最新生产部署来源 {src} ≠ 期望提交 {args.expect_commit}'
                   f' —— 线上已被更晚的部署顶替（这正是 batch040 的事故形态）')
            print(f'  L3 最新生产部署来源：❌ {msg}')
            fails.append(msg)

    print(f'\n=== 结果: {"PASS" if not fails else "FAIL"} · 问题 {len(fails)} 项 ===')
    if fails:
        print('→ 处置：① 先 `git fetch` 确认未落后 origin/main；② `git push` 使本地与 origin 同源；'
              '③ 重新部署（powershell scripts\\deploy_site.ps1）；④ 若他人/CI 已部署更新版本，'
              '先合并再部署，禁止用旧内容覆盖。')
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
