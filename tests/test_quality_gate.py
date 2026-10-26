# -*- coding: utf-8 -*-
"""HC-25 全流程质量门禁测试。"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
import quality_gate as qg  # noqa: E402


def test_aggregate_modes():
    ok = [qg.check_item("a", "PASS", "ok")]
    warn = [qg.check_item("a", "WARN", "warn")]
    fail = [qg.check_item("a", "FAIL", "bad")]
    assert qg.aggregate(ok, "enforce")[0] == "PASS"
    assert qg.aggregate(warn, "enforce")[0] == "WARN"
    assert qg.aggregate(fail, "enforce")[0] == "BLOCKED"
    assert qg.aggregate(fail, "advisory")[0] == "WARN"
    assert qg.aggregate([qg.check_item("s", "SKIP", "skip", required=False)], "advisory")[0] == "WARN"


def test_r0_gate_pass():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "r0.json"
        proc = subprocess.run(
            [sys.executable, "scripts/quality_gate.py", "--stage", "r0",
             "--batch", "batch040", "--mode", "advisory", "--out", str(out)],
            cwd=BASE, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["stage"] == "r0"
        assert report["status"] in ("PASS", "WARN")


def test_r3_release_enforce_blocks_current_pilot():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "r3.json"
        proc = subprocess.run(
            [sys.executable, "scripts/quality_gate.py", "--stage", "r3",
             "--batch", "batch040", "--profile", "release_teacher_keypoint",
             "--mode", "enforce", "--out", str(out)],
            cwd=BASE, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        assert proc.returncode == 1, proc.stdout + proc.stderr
        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["status"] == "BLOCKED"
        assert report["blocking"]


def test_r2_gate_advisory_never_blocks():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "r2.json"
        proc = subprocess.run(
            [sys.executable, "scripts/quality_gate.py", "--stage", "r2",
             "--batch", "batch040", "--profile", "pilot", "--mode", "advisory", "--out", str(out)],
            cwd=BASE, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["status"] in ("PASS", "WARN")
        assert report["mode"] == "advisory"
        assert {c["id"] for c in report["checks"]} >= {"r1.baseline", "r2.kc_registry", "r2.scorecard"}
