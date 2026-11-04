#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SA-8 测试：进展判据看门狗（零依赖，全部用临时目录构造证据）。"""
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE / "scripts"))

import batch_watchdog as wd  # noqa: E402

BATCH = "batch900"


def _make_base(events, traces=None):
    d = Path(tempfile.mkdtemp(prefix="wd_"))
    (d / "reports" / "obs").mkdir(parents=True)
    (d / "reports" / "gate").mkdir(parents=True)
    if events is not None:
        lines = [json.dumps(e, ensure_ascii=False) for e in events]
        (d / "reports" / "obs" / f"{BATCH}_telemetry.jsonl").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    if traces:
        td = d / "最终产物" / BATCH
        td.mkdir(parents=True)
        for i, patches in enumerate(traces):
            (td / f"trace{i}_追溯日志.json").write_text(
                json.dumps({"patches": patches}, ensure_ascii=False), encoding="utf-8")
    return d


def _blocked(ts, gate="GATE-A3", reason="D20=0", stage="a3"):
    return {"ts": ts, "event": "gate_check", "gate": gate, "stage": stage,
            "status": "BLOCKED", "reason": reason}


def _passed(ts, gate="GATE-A3", stage="a3"):
    return {"ts": ts, "event": "gate_check", "gate": gate, "stage": stage,
            "status": "PASS", "reason": "ok"}


def test_normalize_reason_groups_variants():
    a = wd.normalize_reason("批次 batch045 的 evidence_binding_mode 缺失或无效，必须为 strict")
    b = wd.normalize_reason("批次 batch048 的 evidence_binding_mode 缺失或无效，必须为 strict")
    assert a == b, (a, b)


def test_repeated_block_is_no_progress():
    d = _make_base([_blocked("1"), _blocked("2")])
    r = wd.analyze(BATCH, d)
    assert r["verdict"] == "NO_PROGRESS", r
    assert r["repeated_codes"][0]["count"] == 2
    assert r["stage"] == "a3"
    assert r["recommended"][0].startswith("阻断码")
    assert r["actions"][0]["type"] == "isolate_and_continue"


def test_pass_resets_streak():
    d = _make_base([_blocked("1"), _passed("2"), _blocked("3")])
    r = wd.analyze(BATCH, d)
    assert r["verdict"] == "PROGRESS", r


def test_duplicate_patch_fingerprint_is_no_progress():
    patches = [
        {"patch_id": "P1", "question_id": "Q1", "operation": "fix",
         "changes": [{"field": "stem", "before": "a", "after": "b"}]},
        {"patch_id": "P2", "question_id": "Q1", "operation": "fix",
         "changes": [{"field": "stem", "before": "a", "after": "b"}]},
    ]
    d = _make_base([], traces=[[], patches])
    r = wd.analyze(BATCH, d)
    assert r["verdict"] == "NO_PROGRESS", r
    assert r["tried_patches"][0]["count"] == 2
    assert r["actions"][0]["type"] == "stop_repeating_patch"


def test_same_patch_saved_twice_not_flagged():
    patch = {"patch_id": "P1", "question_id": "Q1", "operation": "fix",
             "changes": [{"field": "stem", "before": "a", "after": "b"}]}
    d = _make_base([], traces=[[patch], [patch]])
    r = wd.analyze(BATCH, d)
    assert r["verdict"] == "PROGRESS", r
    assert r["tried_patches"] == []


def test_ineffective_patch_flagged():
    patch = {"patch_id": "P9", "question_id": "Q9", "operation": "fix",
             "changes": [{"field": "stem", "before": "same", "after": "same"}]}
    d = _make_base([], traces=[[patch]])
    r = wd.analyze(BATCH, d)
    assert r["verdict"] == "NO_PROGRESS", r
    assert r["ineffective_patches"][0]["target"] == "Q9"
    assert r["actions"][0]["type"] == "discard_ineffective_patch"


def test_insufficient_evidence():
    d = _make_base(None)
    r = wd.analyze(BATCH, d)
    assert r["verdict"] == "INSUFFICIENT_EVIDENCE", r


def test_exit_code_mapping():
    d = _make_base([_blocked("1"), _blocked("2")])
    try:
        wd.main(["--batch", BATCH, "--dry-run"])
    except SystemExit as exc:
        assert exc.code == 1, exc.code


def test_never_writes_state_or_products():
    src = (BASE / "scripts" / "batch_watchdog.py").read_text(encoding="utf-8")
    for token in ("save_state", "set_halt", "review_queue.json", "ALL_questions_FIXED"):
        assert token not in src, token


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
