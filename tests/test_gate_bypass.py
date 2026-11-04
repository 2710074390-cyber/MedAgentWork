#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""防跳过门禁（P0）回归：跳过阶段必须在下游被硬阻断。

覆盖五个真实绕过场景（每个都对应一次「Agent 不按规则来」）：
    B1 跳过 a3，直接跑 a4/final        → preflight BLOCKED(STAGE_MISSING)
    B2 改了产物但不重跑门禁             → BLOCKED(ARTIFACT_MISMATCH)
    B3 删掉回执链但产物还在             → 首次运行只能补录，补不了的仍 BLOCKED
    B4 篡改已写回执（改判定/插一条）    → BLOCKED(CHAIN_BROKEN)
    B5 老批次（<048）没有回执链         → 不误伤：不阻断，只留痕

以及回执写入契约：PASS 才写、产物字节绑定、seq/chain_prev 递增、写失败必须显式失败。
"""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

BASE = Path(__file__).resolve().parent.parent
if str(BASE / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE / "scripts"))

import batch_driver as bd  # noqa: E402
import gate_stamp as gs  # noqa: E402

PLAN = ["a2", "a3", "a4", "lv", "final"]


def _tmp():
    return Path(tempfile.mkdtemp(prefix="gate_bypass_"))


def _ctx(tmp, batch="batch048", **kw):
    args = SimpleNamespace(
        dry_run=kw.pop("dry_run", False), no_state_write=True, no_halt=True,
        timeout=30, no_stamp=kw.pop("no_stamp", False),
        no_preflight=kw.pop("no_preflight", False),
        ledger=str(tmp / "最终产物" / batch / gs.LEDGER_NAME),
        base=str(tmp),
    )
    ctx = bd.Ctx(batch, kw.pop("data", {}) or {}, args)
    ctx.close = lambda: None  # 不删 tmp（base 指向 tmp）
    return ctx


def _art(tmp, batch="batch048", rel="中间产物/{b}/ALL_questions.json", body='[{"id":"Q1"}]'):
    p = tmp / rel.format(b=batch)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def _ledger(tmp, batch, stages, base_art=None):
    """造一条回执链。stages 里的每一步都用默认产物（存在才绑）。"""
    led = gs.new_ledger(batch)
    for st in stages:
        arts = base_art or []
        if not arts:
            got = gs.expected_artifacts(batch, st, tmp)
            arts = got
        gs.append_stamp(led, st, artifacts=arts, gates=[f"GATE-{st.upper()}"], ts=f"T-{st}")
    gs.write_ledger(led, tmp)
    return led


def _codes(rows):
    return [r["code"] for r in rows]


# ── B1：跳过 a3 直接跑 final ──────────────────────────────
def test_skip_stage_is_blocked():
    tmp = _tmp()
    _art(tmp)
    _art(tmp, rel="最终产物/{b}/ALL_questions_FIXED.json", body='[{"id":"Q1","fixed":1}]')
    # a3 质检报告不存在 → 链里没有 a3
    _ledger(tmp, "batch048", ["a2", "a4"])
    rows, _ev = bd.preflight(_ctx(tmp), "final", PLAN)
    fail = next(r for r in rows if r["status"] == "FAIL")
    assert fail["gate"] == "CHAIN-a3" and fail["code"] == "STAGE_MISSING", fail
    assert fail["owner"] == "MedQC"
    assert bd.aggregate(rows) == ("BLOCKED", 1)


# ── B2：改了产物但没重跑门禁 ─────────────────────────────
def test_modified_artifact_after_stamp_is_blocked():
    tmp = _tmp()
    p = _art(tmp)
    _ledger(tmp, "batch048", ["a2"])
    p.write_text('[{"id":"Q1"},{"id":"Q2"}]', encoding="utf-8")  # 事后加题
    rows, _ = bd.preflight(_ctx(tmp), "a3", PLAN)
    assert _codes(rows) == ["ARTIFACT_MISMATCH"], rows
    assert bd.aggregate(rows) == ("BLOCKED", 1)


# ── B3：删了回执链（想当没发生过）────────────────────────
def test_deleted_ledger_can_only_backfill_what_exists():
    tmp = _tmp()
    _art(tmp)  # a2 产物在，a3 报告不在
    ctx = _ctx(tmp)
    rows, ev = bd.preflight(ctx, "a3", PLAN)
    # 只有 a2 一个前置，可补录 → 放行但留痕
    assert not [r for r in rows if r["status"] == "FAIL"], rows
    assert ev.get("chain_backfill") == ["a2"]
    led, err = gs.load_ledger("batch048", tmp)
    assert err is None and led["stamps"][0]["provenance"] == "backfill"
    # 补录的链在 audit/verify 眼里是 WARN，不是 PASS
    rep = gs.verify("batch048", "a2", base=tmp)
    assert (rep["verdict"], rep["code"]) == ("WARN", "STAGE_BACKFILL")
    assert gs.verify("batch048", "a2", base=tmp, allow_backfill=False)["code"] == "STAGE_BACKFILL"


def test_deleted_ledger_cannot_certify_missing_predecessor():
    tmp = _tmp()
    _art(tmp, rel="最终产物/{b}/ALL_questions_FIXED.json")
    # a4 的前置 a2/a3 产物都不在 → 补录不出来 → 仍阻断
    rows, _ = bd.preflight(_ctx(tmp), "final", PLAN)
    fails = [r for r in rows if r["status"] == "FAIL"]
    assert {r["gate"] for r in fails} == {"CHAIN-a2", "CHAIN-a3"}, rows
    assert bd.aggregate(rows) == ("BLOCKED", 1)


# ── B4：篡改已写回执 ────────────────────────────────────
def test_tampered_stamp_breaks_chain():
    tmp = _tmp()
    _art(tmp)
    _ledger(tmp, "batch048", ["a2"])
    path = tmp / "最终产物" / "batch048" / gs.LEDGER_NAME
    data = json.loads(path.read_text(encoding="utf-8"))
    data["stamps"][0]["verdict"] = "WARN"  # 改判定但不改哈希
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rows, _ = bd.preflight(_ctx(tmp), "a3", PLAN)
    assert _codes(rows) == ["CHAIN_BROKEN"], rows


def test_inserted_stamp_breaks_chain():
    tmp = _tmp()
    _art(tmp)
    _ledger(tmp, "batch048", ["a2"])
    path = tmp / "最终产物" / "batch048" / gs.LEDGER_NAME
    data = json.loads(path.read_text(encoding="utf-8"))
    fake = dict(data["stamps"][0])
    fake["seq"] = 99  # 插一条伪造的
    data["stamps"].append(fake)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert {"CHAIN_BROKEN"} <= {i["id"] for i in gs.verify_chain(data)}


# ── B5：老批次不误伤 ────────────────────────────────────
def test_legacy_batch_not_blocked_without_ledger():
    tmp = _tmp()
    _art(tmp, batch="batch044")
    rows, ev = bd.preflight(_ctx(tmp, batch="batch044"), "a3", PLAN)
    assert rows == [] and ev.get("chain_legacy") is True


def test_legacy_batch_not_stamped():
    tmp = _tmp()
    _art(tmp, batch="batch044")
    ctx = _ctx(tmp, batch="batch044")
    info, err = bd.stamp_pass(ctx, "a2", [bd._result("GATE-A2", "PASS")])
    assert err is None and "skipped" in info
    assert not (tmp / "最终产物" / "batch044" / gs.LEDGER_NAME).exists()


# ── 回执写入契约 ────────────────────────────────────────
def test_stamp_written_on_pass_binds_bytes_and_chain():
    tmp = _tmp()
    a2 = _art(tmp)
    ctx = _ctx(tmp)
    info, err = bd.stamp_pass(ctx, "a2", [bd._result("GATE-A2", "PASS")])
    assert err is None and info["seq"] == 1 and info["artifacts"]
    led, _ = gs.load_ledger("batch048", tmp)
    assert led["stamps"][0]["artifacts"][0]["sha256"] == gs.file_sha256(a2)
    assert led["stamps"][0]["gates"] == ["GATE-A2"]
    # 第二阶段接上去：chain_prev 必须是第一条的哈希
    _art(tmp, rel="质检报告/{b}/A3_质检报告.json", body='{"gate_decision":"PASS"}')
    info2, err2 = bd.stamp_pass(ctx, "a3", [bd._result("GATE-A3", "PASS")])
    assert err2 is None and info2["seq"] == 2
    led, _ = gs.load_ledger("batch048", tmp)
    assert led["stamps"][1]["chain_prev"] == led["stamps"][0]["hash"]
    assert led["head"] == led["stamps"][1]["hash"]
    assert gs.verify_chain(led) == []


def test_stamp_not_written_on_dry_run_or_no_stamp():
    tmp = _tmp()
    _art(tmp)
    info, err = bd.stamp_pass(_ctx(tmp, dry_run=True), "a2", [bd._result("GATE-A2", "PASS")])
    assert (info, err) == (None, None)
    info2, err2 = bd.stamp_pass(_ctx(tmp, no_stamp=True), "a2", [bd._result("GATE-A2", "PASS")])
    assert (info2, err2) == (None, None)
    assert not (tmp / "最终产物" / "batch048" / gs.LEDGER_NAME).exists()


def test_stamp_write_failure_is_explicit():
    tmp = _tmp()
    _art(tmp)
    blocker = tmp / "最终产物"
    blocker.parent.mkdir(parents=True, exist_ok=True)
    blocker.write_text("not a dir", encoding="utf-8")  # 让 最终产物 无法作为目录创建
    ctx = _ctx(tmp)
    info, err = bd.stamp_pass(ctx, "a2", [bd._result("GATE-A2", "PASS")])
    assert info is None and err, (info, err)


def test_no_preflight_is_the_documented_escape_hatch():
    tmp = _tmp()
    _art(tmp)
    _ledger(tmp, "batch048", ["a4"])  # 链里没有 a2
    rows, ev = bd.preflight(_ctx(tmp, no_preflight=True), "final", PLAN)
    assert rows == [] and ev == {}


def test_hard_chain_stages_are_deliverable_stages():
    assert set(bd.HARD_CHAIN_STAGES) <= set(gs.STAGES)
    assert {"a2", "a3", "a4", "final"} <= set(bd.HARD_CHAIN_STAGES)
    assert "r0" not in bd.HARD_CHAIN_STAGES  # 过程门禁不强制回执


def test_verdict_codes_are_declared():
    """新增的失败码必须进 FAIL_CODES，否则 verify 会漏判成 PASS。"""
    for code in ("LEDGER_MISSING", "CHAIN_BROKEN", "STAGE_MISSING",
                 "ARTIFACT_MISMATCH", "ARTIFACT_MISSING", "ARTIFACT_NOT_COVERED"):
        assert code in gs.FAIL_CODES, code


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"  FAIL {name}: {exc}")
    raise SystemExit(1 if failures else 0)
