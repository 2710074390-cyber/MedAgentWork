#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install_git_hooks.py 测试：pre-commit 钩子的安装/卸载契约（P2）。

全部在 tmp_path 里 git init，不碰真实仓库的 .git/hooks。
覆盖：创建 / 幂等覆盖自己的 / 外来钩子先备份 / 卸载只删自己的 /
      --dry-run 不落盘 / 钩子内容含正确的审计命令。
"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE / "scripts"))

import install_git_hooks as igh  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True, capture_output=True)
    return tmp_path


def _hook(tmp_path: Path) -> Path:
    return igh.hooks_dir(tmp_path) / "pre-commit"


def test_install_creates_executable_hook_with_audit_command(tmp_path):
    _repo(tmp_path)
    r = igh.install(tmp_path)
    assert r["error"] is None
    assert r["action"] == "create"
    hook = _hook(tmp_path)
    assert hook.is_file()
    body = hook.read_text(encoding="utf-8")
    assert "gate_audit.py --staged --require-tracked" in body
    assert body.startswith("#!/bin/sh")
    assert igh.is_ours(hook)


def test_install_is_idempotent(tmp_path):
    _repo(tmp_path)
    igh.install(tmp_path)
    r = igh.install(tmp_path)
    assert r["action"] == "overwrite-own"
    assert r["backup"] is None


def test_install_backs_up_foreign_hook(tmp_path):
    _repo(tmp_path)
    hook = _hook(tmp_path)
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho foreign\n", encoding="utf-8")

    r = igh.install(tmp_path)
    assert r["action"] == "backup-and-install"
    assert Path(r["backup"]).is_file()
    assert "echo foreign" in Path(r["backup"]).read_text(encoding="utf-8")
    assert igh.is_ours(hook)


def test_uninstall_refuses_foreign_hook(tmp_path):
    _repo(tmp_path)
    hook = _hook(tmp_path)
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho other\n", encoding="utf-8")

    r = igh.uninstall(tmp_path)
    assert r["action"] == "refuse-foreign"
    assert r["error"]
    assert hook.exists()


def test_uninstall_removes_own_hook(tmp_path):
    _repo(tmp_path)
    igh.install(tmp_path)
    r = igh.uninstall(tmp_path)
    assert r["action"] == "remove"
    assert not _hook(tmp_path).exists()


def test_uninstall_when_absent_is_noop(tmp_path):
    _repo(tmp_path)
    r = igh.uninstall(tmp_path)
    assert r["action"] == "absent"
    assert r["error"] is None


def test_dry_run_does_not_write(tmp_path):
    _repo(tmp_path)
    r = igh.install(tmp_path, dry_run=True)
    assert r["action"] == "create"
    assert not _hook(tmp_path).exists()


def test_cli_exit_codes(tmp_path, capsys):
    _repo(tmp_path)
    assert igh.main(["--base", str(tmp_path)]) == 0
    assert igh.main(["--base", str(tmp_path), "--uninstall"]) == 0
    assert igh.main(["--base", str(tmp_path / "nope")]) == 2
