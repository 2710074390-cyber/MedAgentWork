#!/usr/bin/env python
"""部署/更新 medkit-keepalive Worker（走 Cloudflare Workers API，不需要 wrangler）。

用法：
    set CF_API_TOKEN=...            # Windows cmd
    $env:CF_API_TOKEN="..."         # PowerShell
    export CF_API_TOKEN=...         # bash
    python scripts/deploy_keepalive.py           # 部署 + 设 cron
    python scripts/deploy_keepalive.py --status  # 只查现状
    python scripts/deploy_keepalive.py --delete  # 删掉 Worker（撤保活）

Token 权限只需要：Account → Workers Scripts → Edit
（Cloudflare 后台 → My Profile → API Tokens → Create Token → Edit Cloudflare Workers 模板即可）
账号 ID 不用手填：脚本会 GET /accounts 自动取（多账号时可用 CF_ACCOUNT_ID 指定）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
WORKER = BASE / "workers" / "keepalive" / "worker.js"
SCRIPT_NAME = "medkit-keepalive"
CRON = "*/5 * * * *"
API = "https://api.cloudflare.com/client/v4"


def auth_headers() -> dict[str, str]:
    """两种凭据都支持：
    - CF_API_TOKEN       推荐，Scoped Token，Bearer 认证
    - CF_API_KEY + CF_API_EMAIL   Global API Key（32 位十六进制）必须配邮箱，权限是整号，不推荐
    """
    tok = os.environ.get("CF_API_TOKEN", "").strip()
    if tok:
        return {"Authorization": f"Bearer {tok}"}
    key = os.environ.get("CF_API_KEY", "").strip()
    email = os.environ.get("CF_API_EMAIL", "").strip()
    if key and email:
        return {"X-Auth-Key": key, "X-Auth-Email": email}
    sys.exit("缺少凭据：CF_API_TOKEN（推荐），或 CF_API_KEY + CF_API_EMAIL")


def call(method: str, path: str, body: bytes | None = None,
         content_type: str | None = None) -> dict:
    req = urllib.request.Request(API + path, data=body, method=method)
    for k, v in auth_headers().items():
        req.add_header(k, v)
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = resp.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        sys.exit(f"HTTP {exc.code} {method} {path}\n{detail}")
    return json.loads(payload) if payload else {}


def account_id() -> str:
    explicit = os.environ.get("CF_ACCOUNT_ID", "").strip()
    if explicit:
        return explicit
    data = call("GET", "/accounts")
    accounts = data.get("result") or []
    if not accounts:
        sys.exit("这个 token 看不到任何账号——确认 token 是 Account 级权限、且账号下已开通 Workers")
    if len(accounts) > 1:
        names = ", ".join(f"{a['name']}({a['id']})" for a in accounts)
        sys.exit(f"token 能看到多个账号，请用 CF_ACCOUNT_ID 指定：{names}")
    return accounts[0]["id"]


def deploy(acct: str) -> None:
    meta = {"main_module": "index.js", "compatibility_date": "2024-01-01"}
    boundary = "----medkit" + uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"metadata\"\r\n"
        f"Content-Type: application/json\r\n\r\n{json.dumps(meta)}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"index.js\"; "
        f"filename=\"index.js\"\r\nContent-Type: application/javascript+module\r\n\r\n".encode(),
        WORKER.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    call("PUT", f"/accounts/{acct}/workers/scripts/{SCRIPT_NAME}",
         b"".join(parts), f"multipart/form-data; boundary={boundary}")
    print(f"✓ 脚本已上传：{SCRIPT_NAME}")

    call("PUT", f"/accounts/{acct}/workers/scripts/{SCRIPT_NAME}/schedules",
         json.dumps({"crons": [CRON]}).encode(), "application/json")
    print(f"✓ Cron 已设置：{CRON}（每 5 分钟）")


def status(acct: str) -> None:
    sched = call("GET", f"/accounts/{acct}/workers/scripts/{SCRIPT_NAME}/schedules")
    print("cron:", json.dumps(sched.get("result", sched), ensure_ascii=False))
    subs = call("GET", f"/accounts/{acct}/workers/subdomain")
    sub = (subs.get("result") or {}).get("subdomain")
    if sub:
        print(f"手动查看：https://{SCRIPT_NAME}.{sub}.workers.dev/")


def delete(acct: str) -> None:
    call("DELETE", f"/accounts/{acct}/workers/scripts/{SCRIPT_NAME}")
    print(f"✓ 已删除 {SCRIPT_NAME}（保活停止）")


def main() -> int:
    ap = argparse.ArgumentParser(description="部署 medkit-keepalive Cron Worker")
    ap.add_argument("--status", action="store_true", help="只看 cron 与访问地址")
    ap.add_argument("--delete", action="store_true", help="删除 Worker")
    a = ap.parse_args()

    acct = account_id()
    if a.status:
        status(acct)
    elif a.delete:
        delete(acct)
    else:
        if not WORKER.is_file():
            sys.exit(f"未找到 {WORKER}")
        deploy(acct)
        status(acct)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
