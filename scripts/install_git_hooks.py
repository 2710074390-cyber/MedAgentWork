#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安装/卸载 git pre-commit 钩子（P2 防跳过 · 零依赖版）。

为什么要自己装，而不是只留 `.pre-commit-config.yaml`
-----------------------------------------------------
`pre-commit` 框架要先 `pip install pre-commit && pre-commit install` 才生效；本机两个
解释器都没有这个包，等于「配了但没跑」。而批次是在本机跑的，本地这一层不能悬空。
所以这里直接往 `.git/hooks/pre-commit` 写一个最小 shell 脚本：

    #!/bin/sh
    exec python scripts/gate_audit.py --staged --require-tracked

它不依赖任何 Python 包，git 自己会调用。**如果以后装了 pre-commit 框架**，
`pre-commit install` 会覆盖这个文件——那时改用 `.pre-commit-config.yaml` 里的
`batch-gate-staged`（内容等价），两者不要同时用。

只管住一件事
------------
提交前，对「暂存区涉及」的批次验回执链 + 检查 batch048+ 产物是否都进了索引。
不跑 `--recheck`（内容复检留给 CI，本地要快）。

用法
----
    python scripts/install_git_hooks.py --dry-run     # 看会写什么
    python scripts/install_git_hooks.py               # 安装（已有他方钩子会先备份）
    python scripts/install_git_hooks.py --uninstall   # 卸载（只删本脚本写入的）
"""
from __future__ import annotations

import argparse
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
MARKER = "# medagentwork-gate: pre-commit 批次门禁审计（P2，可用 scripts/install_git_hooks.py --uninstall 移除）"

HOOK_BODY = f"""#!/bin/sh
{MARKER}
# 只审暂存区涉及的批次：回执链是否完整、batch048+ 的产物+回执是否都进了索引。
# 不含 --recheck（内容复检在 CI 的 batch-gate job）。
exec python scripts/gate_audit.py --staged --require-tracked
"""


def hooks_dir(base: Path = BASE) -> Path:
    """用 git 自己问 hooks 路径：支持 worktree / 自定义 core.hooksPath。"""
    proc = subprocess.run(["git", "rev-parse", "--git-path", "hooks"], cwd=str(base),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "git rev-parse 失败").strip())
    p = Path(proc.stdout.strip())
    return p if p.is_absolute() else (Path(base) / p)


def is_ours(path: Path) -> bool:
    try:
        return MARKER in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def install(base: Path = BASE, dry_run: bool = False) -> dict:
    result = {"hook": None, "action": None, "backup": None, "error": None}
    try:
        d = hooks_dir(base)
    except RuntimeError as exc:
        result["error"] = str(exc)
        return result
    hook = d / "pre-commit"
    result["hook"] = str(hook)

    if hook.exists() and not is_ours(hook):
        result["action"] = "backup-and-install"
        result["backup"] = str(hook.with_suffix(f".bak.{datetime.now():%Y%m%d%H%M%S}"))
        if not dry_run:
            shutil.copy2(hook, result["backup"])
    elif hook.exists():
        result["action"] = "overwrite-own"
    else:
        result["action"] = "create"

    if dry_run:
        return result
    d.mkdir(parents=True, exist_ok=True)
    hook.write_text(HOOK_BODY, encoding="utf-8", newline="\n")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return result


def uninstall(base: Path = BASE, dry_run: bool = False) -> dict:
    result = {"hook": None, "action": None, "error": None}
    try:
        hook = hooks_dir(base) / "pre-commit"
    except RuntimeError as exc:
        result["error"] = str(exc)
        return result
    result["hook"] = str(hook)
    if not hook.exists():
        result["action"] = "absent"
    elif not is_ours(hook):
        result["action"] = "refuse-foreign"
        result["error"] = "该钩子不是本脚本写入的，拒绝删除（请手工处理）"
    else:
        result["action"] = "remove"
        if not dry_run:
            hook.unlink()
    return result


def main(argv=None) -> int:
    for _s in (sys.stdout, sys.stderr):  # Windows 控制台 GBK 兜底
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="安装/卸载 git pre-commit 钩子（P2 防跳过）")
    ap.add_argument("--base", default=None, help="仓库根（默认脚本所在仓库）")
    ap.add_argument("--dry-run", action="store_true", help="只看会做什么，不写文件")
    ap.add_argument("--uninstall", action="store_true", help="移除本脚本写入的钩子")
    args = ap.parse_args(argv)

    base = Path(args.base).resolve() if args.base else BASE
    if not base.is_dir():
        print(f"[ERROR] --base 不是目录：{base}", file=sys.stderr)
        return 2

    r = uninstall(base, args.dry_run) if args.uninstall else install(base, args.dry_run)
    if r.get("error"):
        print(f"[ERROR] {r['error']}")
        return 2

    prefix = "[dry-run] " if args.dry_run else ""
    if args.uninstall:
        print(f"{prefix}卸载：{r['hook']}（{r['action']}）")
        return 0

    print(f"{prefix}钩子：{r['hook']}（{r['action']}）")
    if r.get("backup"):
        print(f"{prefix}原钩子已备份：{r['backup']}")
    print("\n验证（不产生提交）：")
    print("  git hook run pre-commit")
    print("\n提示：本钩子只做本地拦截；真正的兜底是 CI 的 batch-gate 与 deploy 前置审计。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
