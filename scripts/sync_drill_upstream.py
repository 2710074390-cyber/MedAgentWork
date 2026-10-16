#!/usr/bin/env python
"""同步「网页刷题」代理上游（/drill → WorkBuddy Sites 沙箱）。

背景：`functions/drill/[[path]].js` 把 `/drill/*` 反代到外部「发布应用(Sites)」应用。
每当在 WorkBuddy 重新发布 `medkit-web-v2` 拿到新的分享链接（sandbox 域名）时，
若域名与当前 UPSTREAM 不同，须同步本文件，否则 /drill 仍指向旧应用。

用法：
  python scripts/sync_drill_upstream.py --url https://senior-quiz-app.app.workbuddy.host
  python scripts/sync_drill_upstream.py --url <新链接> --commit --push
  python scripts/sync_drill_upstream.py --url <新链接> --dry-run   # 只看差异
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TARGET = BASE / "functions" / "drill" / "[[path]].js"
_PAT = re.compile(r'(const\s+UPSTREAM\s*=\s*")([^"]*)(";)')


def main() -> int:
    ap = argparse.ArgumentParser(description="更新 /drill 代理 UPSTREAM")
    ap.add_argument("--url", required=True, help="新的沙箱分享链接（scheme+host，可带尾部 /）")
    ap.add_argument("--dry-run", action="store_true", help="只显示差异，不写盘")
    ap.add_argument("--commit", action="store_true", help="写入后 git commit")
    ap.add_argument("--push", action="store_true", help="commit 后 git push origin main")
    a = ap.parse_args()

    url = a.url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        print("URL 必须以 http(s):// 开头", file=sys.stderr)
        return 2
    if not TARGET.is_file():
        print(f"未找到 {TARGET}", file=sys.stderr)
        return 2

    text = TARGET.read_text(encoding="utf-8")
    m = _PAT.search(text)
    if not m:
        print("未找到 UPSTREAM 声明行", file=sys.stderr)
        return 2

    old = m.group(2)
    if old == url:
        print(f"UPSTREAM 已是目标值：{url}（无需改动）")
        return 0

    print(f"UPSTREAM:\n  {old}\n→ {url}")
    if a.dry_run:
        print("(--dry-run，未写盘)")
        return 0

    TARGET.write_text(_PAT.sub(lambda mm: mm.group(1) + url + mm.group(3), text, count=1),
                      encoding="utf-8", newline="\n")
    print(f"已更新 {TARGET.relative_to(BASE)}")

    if a.commit:
        subprocess.run(["git", "-C", str(BASE), "add", "--", "functions/drill"], check=True)
        subprocess.run(["git", "-C", str(BASE), "commit", "-m",
                        f"fix(drill): 代理 UPSTREAM 切换到 {url}"], check=True)
        print("已提交")
        if a.push:
            subprocess.run(["git", "-C", str(BASE), "push", "origin", "main"], check=True)
            print("已推送（GitHub Actions 将重部 Cloudflare Pages）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
