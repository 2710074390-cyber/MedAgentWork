#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""H1–H5 跨宿主可移植编排测试（scripts/run_tests.py 可直接发现）。

覆盖：driver 的确定性下一阶段、交接包与回执同源哈希、幂等/过期判定、
      包里无宿主工具名、桩 level 校验与 SCOPE_CONFLICT、三档回归矩阵。
"""
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE / "scripts"))

import batch_driver as bd        # noqa: E402
import host_bootstrap as hb      # noqa: E402
import host_matrix_check as hm   # noqa: E402


def _plan():
    _, data = bd.load_batch("batch048")
    return bd.plan_boundaries("batch048", data)[0], data


def test_next_boundary_is_deterministic():
    plan, _ = _plan()
    assert bd.next_boundary("a2", plan) == "a3"
    assert bd.next_boundary("r4", plan) is None
    assert bd.next_boundary("not-in-plan", plan) is None
    p = bd.build_payload("batch048", "a2", plan, ["question_bank"], [], "PASS", 0, {})
    assert p["next_stage"] == "a3" and p["next_action"] == "advance"
    p = bd.build_payload("batch048", "a2", plan, ["question_bank"], [], "BLOCKED", 1, {})
    assert p["next_stage"] == "a2" and p["next_action"] == "retry"
    p = bd.build_payload("batch048", "r4", plan, ["question_bank"], [], "PASS", 0, {})
    assert p["next_stage"] is None and p["next_action"] == "complete"


def test_handoff_sha_matches_ledger():
    """交接包与回执链必须共用同一份字节哈希，不能出现第二个真相源。"""
    plan, data = _plan()
    b = bd.build_handoff("batch048", "a3", plan, data)
    ledger = json.loads((BASE / "最终产物" / "batch048" / "_gate_ledger.json").read_text(encoding="utf-8"))
    a2 = next(s for s in ledger["stamps"] if s["stage"] == "a2")
    sha = next(a["sha256"] for a in a2["artifacts"] if a["path"].endswith("ALL_questions.json"))
    got = next(i["sha256"] for i in b["inputs"] if i["path"].endswith("ALL_questions.json"))
    assert got == sha


def test_handoff_write_is_idempotent_and_detects_stale():
    plan, data = _plan()
    b = bd.build_handoff("batch048", "a3", plan, data)
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        assert bd.write_handoff(b, root)["status"] == "written"
        assert bd.write_handoff(b, root)["status"] == "unchanged"
        p = bd.handoff_path("batch048", "a3", root)
        assert bd.handoff_stale(p) is False
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["inputs_fingerprint"] = "0" * 64
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        assert bd.handoff_stale(p) is True
        assert bd.handoff_stale(root / "missing.json") is None


def test_handoff_has_no_host_tool_names():
    plan, data = _plan()
    b = bd.build_handoff("batch048", "a3", plan, data)
    text = json.dumps(b, ensure_ascii=False)
    for word in hm.FORBIDDEN_TOOL_NAMES:
        assert word not in text, word
    assert b["parallel_safe"] == (b["write_scope"] != "question_bank")
    assert b["gate"].startswith("python scripts/batch_driver.py check")


def test_brief_l0_prints_all_commands():
    plan, data = _plan()
    b = bd.build_handoff("batch048", "a3", plan, data)
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "a3.json"
        p.write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert bd.main(["brief", "--batch", "batch048", "--stage", "a3", "--bundle", str(p)]) == 0
        out = buf.getvalue()
        assert b["gate"] in out and b["role_skill"] in out and "[OK] 包完好" in out


def test_host_bootstrap_level_and_scope_conflict():
    """临时仓库里造一对不同步的同名桩，验证 v2 level 校验与 SCOPE_CONFLICT。"""
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        base, home = root / "repo", root / "home"
        (base / ".dsh" / "skills" / "medmaster").mkdir(parents=True)
        (base / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
        skill = base / ".dsh" / "skills" / "medmaster" / "SKILL.md"
        skill.write_text("---\nname: medmaster\ndescription: t\n---\nbody\n", encoding="utf-8")

        hb.install(["workbuddy"], base, home, scope="project")
        hb.install(["workbuddy"], base, home, scope="user")
        rep = hb.check(["workbuddy"], base, home, scope="project")
        assert rep["hosts"][0]["verdict"] == "PASS"
        assert rep["hosts"][0]["level"] == "L2"
        assert not any(e["status"] == "WARN" for e in rep["hosts"][0]["entries"])

        # 源变更 → 只重生成项目级 → 用户级桩变旧
        skill.write_text("---\nname: medmaster\ndescription: t2\n---\nbody2\n", encoding="utf-8")
        hb.install(["workbuddy"], base, home, scope="project")
        rep = hb.check(["workbuddy"], base, home, scope="project")
        entries = rep["hosts"][0]["entries"]
        assert any(e["status"] == "WARN" and "SCOPE_CONFLICT" in e["detail"] for e in entries)

        # 抹掉 level= → v1 形态 → LEVEL_MISSING
        proj = hb.workbuddy_skills_dir(base, home, "project") / "medmaster" / "SKILL.md"
        proj.write_text(proj.read_text(encoding="utf-8").replace(" level=L2", ""), encoding="utf-8")
        rep = hb.check(["workbuddy"], base, home, scope="project")
        assert any(e["status"] == "LEVEL_MISSING" for e in rep["hosts"][0]["entries"])


def test_matrix_three_levels_share_one_bundle():
    rep = hm.run_matrix("batch048", "a3")
    assert rep.get("error") is None, rep.get("error")
    assert rep["ok"], json.dumps(rep["failed"], ensure_ascii=False)
    assert len(set(rep["levels"])) == 3
    assert any(r["check"] == "same_bundle_across_levels" and r["ok"] for r in rep["checks"])
