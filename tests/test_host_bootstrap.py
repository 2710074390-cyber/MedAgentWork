#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""host_bootstrap 测试：三宿主入口生成 / 漂移检测 / 不误删他方文件。

全部在 tmp_path 造一个「迷你仓库 + 迷你 home」，不碰真实 ~/.workbuddy。
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
if str(BASE / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE / "scripts"))

import host_bootstrap as hb  # noqa: E402

AGENTS = "# AGENTS\n\n唯一入口（测试夹具）。\n"


def _skill(root: Path, name: str, desc: str = None):
    d = root / ".dsh" / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {json.dumps(desc or (name + ' 技能'), ensure_ascii=False)}\n"
        "whenToUse: 测试\n"
        "---\n"
        f"# {name} 正文\n",
        encoding="utf-8")
    return d / "SKILL.md"


def _repo(tmp_path: Path):
    base = tmp_path / "repo"
    base.mkdir()
    (base / "AGENTS.md").write_text(AGENTS, encoding="utf-8")
    _skill(base, "alpha")
    _skill(base, "beta")
    home = tmp_path / "home"
    home.mkdir()
    return base, home


def _sha(path: Path) -> str:
    return hb.sha256_text(path)


# ── 生成 / 就绪 ─────────────────────────────────────────
def test_check_fails_before_install(tmp_path):
    base, home = _repo(tmp_path)
    rep = hb.check(["trae", "workbuddy"], base, home)
    assert rep["summary"]["fail"] == 2
    for h in rep["hosts"]:
        assert h["verdict"] == "FAIL"
        assert all(e["status"] == "MISSING" for e in h["entries"])
    assert hb.main(["check", "--hosts", "trae,workbuddy",
                    "--base", str(base), "--home", str(home)]) == 1


def test_install_then_check_passes(tmp_path):
    base, home = _repo(tmp_path)
    res = hb.install(["trae", "workbuddy"], base, home)
    assert res["error"] is None and len(res["written"]) == 3   # 1 条规则 + 2 个技能
    rep = hb.check(["dsh", "trae", "workbuddy"], base, home)
    assert rep["summary"]["fail"] == 0, rep
    assert (base / ".workbuddy" / "skills" / "alpha" / "SKILL.md").is_file()   # 项目级（入库）
    assert (base / ".trae" / "rules" / hb.TRAE_RULE_NAME).is_file()


def test_install_is_idempotent(tmp_path):
    base, home = _repo(tmp_path)
    hb.install(["trae", "workbuddy"], base, home)
    again = hb.install(["trae", "workbuddy"], base, home)
    assert again["written"] == [] and len(again["unchanged"]) == 3


# ── 漂移 ────────────────────────────────────────────────
def test_source_change_marks_stale(tmp_path):
    base, home = _repo(tmp_path)
    hb.install(["trae", "workbuddy"], base, home)
    _skill(base, "alpha", "改过的描述")          # 源变了，桩没重生成
    rep = hb.check(["workbuddy"], base, home)
    alpha = next(e for e in rep["hosts"][0]["entries"] if e["name"] == "alpha")
    assert alpha["status"] == "STALE"
    assert rep["summary"]["fail"] == 1
    # 重跑 install 即恢复
    hb.install(["workbuddy"], base, home)
    assert hb.check(["workbuddy"], base, home)["summary"]["fail"] == 0


def test_agents_change_marks_trae_stale(tmp_path):
    base, home = _repo(tmp_path)
    hb.install(["trae"], base, home)
    (base / "AGENTS.md").write_text(AGENTS + "追加一行\n", encoding="utf-8")
    rep = hb.check(["trae"], base, home)
    assert rep["hosts"][0]["entries"][0]["status"] == "STALE"


# ── 不静默覆盖 / 不误删 ─────────────────────────────────
def test_foreign_file_is_refused_then_force_allowed(tmp_path):
    base, home = _repo(tmp_path)
    target = base / ".workbuddy" / "skills" / "alpha" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("# 别人的技能\n", encoding="utf-8")
    res = hb.install(["workbuddy"], base, home)
    assert res["error"] and res["skipped"][0]["reason"] == "foreign"
    assert target.read_text(encoding="utf-8") == "# 别人的技能\n"     # 没被覆盖
    rep = hb.check(["workbuddy"], base, home)
    assert any(e["status"] == "FOREIGN" for e in rep["hosts"][0]["entries"])
    hb.install(["workbuddy"], base, home, force=True)
    assert hb.MARKER in target.read_text(encoding="utf-8")


def test_uninstall_removes_only_ours(tmp_path):
    base, home = _repo(tmp_path)
    hb.install(["trae", "workbuddy"], base, home)
    foreign = base / ".trae" / "rules" / "user-own.md"
    foreign.write_text("# 用户自己的规则\n", encoding="utf-8")
    res = hb.uninstall(["trae", "workbuddy"], base, home)
    assert res["error"] is None and len(res["removed"]) == 3
    assert foreign.is_file()                                    # 他方文件保留
    assert not (base / ".trae" / "rules" / hb.TRAE_RULE_NAME).exists()


def test_uninstall_refuses_foreign_target(tmp_path):
    base, home = _repo(tmp_path)
    foreign = base / ".trae" / "rules" / hb.TRAE_RULE_NAME
    foreign.parent.mkdir(parents=True)
    foreign.write_text("# 别人的\n", encoding="utf-8")
    res = hb.uninstall(["trae"], base, home)
    assert res["skipped"] and res["removed"] == []


# ── dsh 原生检查 / 内容契约 ─────────────────────────────
def test_dsh_check_requires_skills(tmp_path):
    base = tmp_path / "empty"
    base.mkdir()
    (base / "AGENTS.md").write_text(AGENTS, encoding="utf-8")
    rep = hb.check(["dsh"], base, tmp_path / "home")
    assert rep["hosts"][0]["verdict"] == "FAIL"
    assert any(e["status"] == "MISSING" for e in rep["hosts"][0]["entries"])


def test_trae_rule_has_always_apply_and_source_hash(tmp_path):
    base, home = _repo(tmp_path)
    hb.install(["trae"], base, home)
    text = (base / ".trae" / "rules" / hb.TRAE_RULE_NAME).read_text(encoding="utf-8")
    assert "alwaysApply: true" in text
    assert _sha(base / "AGENTS.md") in text
    assert "AGENTS.md" in text and "batch_driver.py" in text


def test_workbuddy_stub_keeps_skill_metadata(tmp_path):
    base, home = _repo(tmp_path)
    hb.install(["workbuddy"], base, home)
    text = (base / ".workbuddy" / "skills" / "beta" / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: beta\n")
    assert "description:" in text
    assert hb.MARKER in text and ".dsh/skills/beta/SKILL.md" in text


# ── 真实仓库 / CLI 契约 ─────────────────────────────────
def test_repo_entries_in_sync():
    """真仓库的 DSH + Trae + WorkBuddy 项目级入口必须与源同步（CI 也跑这条）。"""
    rep = hb.check(["dsh", "trae", "workbuddy"], BASE, Path.home())
    assert rep["summary"]["fail"] == 0, rep


def test_cli_unknown_host_exits_two(tmp_path):
    base, home = _repo(tmp_path)
    assert hb.main(["check", "--hosts", "bogus", "--base", str(base), "--home", str(home)]) == 2


def test_cli_json_report_shape(tmp_path, capsys):
    base, home = _repo(tmp_path)
    assert hb.main(["install", "--hosts", "trae", "--base", str(base),
                    "--home", str(home), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["written"]
    assert hb.main(["check", "--hosts", "trae", "--base", str(base),
                    "--home", str(home), "--json"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["summary"] == {"pass": 1, "fail": 0, "hosts": 1}
    assert {"host", "verdict", "entries"} <= set(rep["hosts"][0])


def test_user_scope_installs_to_home(tmp_path):
    """--scope user：装到 ~/.workbuddy/skills（本机便利，不入库）。"""
    base, home = _repo(tmp_path)
    res = hb.install(["workbuddy"], base, home, scope="user")
    assert res["error"] is None and len(res["written"]) == 2
    assert (home / ".workbuddy" / "skills" / "alpha" / "SKILL.md").is_file()
    assert not (base / ".workbuddy").exists()
    assert hb.check(["workbuddy"], base, home, scope="user")["summary"]["fail"] == 0


def test_both_scope_installs_both_copies(tmp_path):
    base, home = _repo(tmp_path)
    res = hb.install(["workbuddy"], base, home, scope="both")
    assert len(res["written"]) == 4                     # 2 技能 × 2 scope
    rep = hb.check(["workbuddy"], base, home, scope="both")
    assert len(rep["hosts"][0]["entries"]) == 4      # 2 技能 × 2 scope 都参与检查
    assert rep["summary"]["fail"] == 0


def test_project_and_user_drift_independent(tmp_path):
    """两个 scope 的桩各存一份：删掉项目级不会让用户级变 STALE。"""
    base, home = _repo(tmp_path)
    hb.install(["workbuddy"], base, home, scope="both")
    (base / ".workbuddy" / "skills" / "alpha" / "SKILL.md").unlink()
    rep = hb.check(["workbuddy"], base, home, scope="both")
    statuses = {e["path"]: e["status"] for e in rep["hosts"][0]["entries"]}
    assert any(s == "MISSING" for s in statuses.values())
    assert any(s == "PASS" for s in statuses.values())


def test_source_hash_is_line_ending_agnostic(tmp_path):
    """CRLF 与 LF 的同一份源必须得到同一 hash（否则 CI/Linux 会误判 STALE）。"""
    crlf = tmp_path / "crlf.md"
    lf = tmp_path / "lf.md"
    crlf.write_bytes(b"a\r\nb\r\n")
    lf.write_bytes(b"a\nb\n")
    assert hb.sha256_text(crlf) == hb.sha256_text(lf)
    other = tmp_path / "other.md"
    other.write_bytes(b"a\r\nc\r\n")
    assert hb.sha256_text(crlf) != hb.sha256_text(other)
