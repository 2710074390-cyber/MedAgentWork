#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_verify.py 测试：消费方验上游的验真 CLI（pytest 风格，纯 tmp_path）。

所有用例都用 gate_stamp 在 tmp_path 里造「产物 + 回执链」，不依赖真实批次；
覆盖 PASS / LEDGER_MISSING / STAGE_MISSING / ARTIFACT_MISMATCH /
ARTIFACT_NOT_COVERED / CHAIN_BROKEN（改内容 + 删中间回执）/ backfill 的
WARN→strict / --json-out 报告形状 / expected_artifacts 覆盖跳过分支 / 退出码契约。
"""
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
if str(BASE / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE / "scripts"))

import gate_stamp as gs  # noqa: E402
import gate_verify as gv  # noqa: E402

BATCH = "batch048"

# 阶段 → 该阶段产物的仓库相对路径（{b} 为批次 id）
ARTIFACTS = {
    "a2": "中间产物/{b}/ALL_questions.json",
    "a3": "质检报告/{b}/A3_质检报告.json",
    "a4": "最终产物/{b}/ALL_questions_FIXED.json",
    "lv": "最终产物/{b}/ALL_questions_FIXED.json",
    "a5": "复习资料/{b}/{b}_主复习资料.md",
    "final": "最终产物/{b}/ALL_questions_FIXED.json",
}


def _write(path: Path, text=None) -> Path:
    """写一个占位产物（内容无关，sha256 只要求前后一致）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text is not None else json.dumps({"stage": "x"}, ensure_ascii=False),
                    encoding="utf-8")
    return path


def _build(tmp_path, stages, provenance="driver"):
    """按阶段顺序造产物并追加回执；返回 {stage: 产物路径}。"""
    ledger = gs.new_ledger(BATCH)
    made = {}
    for stage in stages:
        rel = ARTIFACTS.get(stage, "最终产物/{b}/" + stage + ".json").format(b=BATCH)
        p = _write(tmp_path / rel)
        made[stage] = p
        gs.append_stamp(ledger, stage, artifacts=[p], provenance=provenance)
    gs.write_ledger(ledger, base=tmp_path)
    return made


def _run(argv):
    return gv.main(argv)


def _verify(tmp_path, stage, **kwargs):
    return gv.verify_stage(BATCH, stage, base=tmp_path, **kwargs)


def _issue_ids(report):
    return [i["id"] for i in report["issues"]]


# ── PASS / 覆盖校验 ─────────────────────────────────────
def test_pass_with_expected_artifacts_and_exit_zero(tmp_path, capsys):
    _build(tmp_path, ["a2", "a3"])
    rc = _run(["--batch", BATCH, "--stage", "a3", "--base", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PASS" in out and "STAMP_OK" in out
    report = _verify(tmp_path, "a3")
    assert report["verdict"] == "PASS"
    assert report["code"] == "STAMP_OK"
    assert report["coverage_mode"] == "expected"
    assert report["coverage"]["status"] == "PASS"
    assert report["required_artifacts"] == ["质检报告/batch048/A3_质检报告.json"]
    assert report["exit_code"] == 0


def test_artifact_absolute_and_relative_paths_accepted(tmp_path):
    """--artifact 相对仓库根与绝对路径都接受（归一后都必须被回执覆盖）。"""
    made = _build(tmp_path, ["a2", "a3"])
    for artifact in (str(made["a3"]), "质检报告/batch048/A3_质检报告.json"):
        report = gv.verify_stage(BATCH, "a3", base=tmp_path, artifacts=[artifact])
        assert report["verdict"] == "PASS", artifact
        assert report["coverage_mode"] == "explicit"
        assert report["coverage"]["status"] == "PASS"


# ── FAIL：回执链缺失 / 阶段缺失 ─────────────────────────
def test_ledger_missing_fails_with_upstream_hint(tmp_path, capsys):
    rc = _run(["--batch", BATCH, "--stage", "a3", "--base", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "LEDGER_MISSING" in out
    assert "batch_driver.py check" in out
    report = _verify(tmp_path, "a3")
    assert report["verdict"] == "FAIL" and report["code"] == "LEDGER_MISSING"
    assert report["exit_code"] == 1
    assert "--stage a2" in report["next_command"]  # 提示先跑上游阶段


def test_stage_missing_points_to_upstream_stage(tmp_path, capsys):
    _build(tmp_path, ["a2"])
    rc = _run(["--batch", BATCH, "--stage", "a3", "--base", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "STAGE_MISSING" in out and "--stage a2" in out
    report = _verify(tmp_path, "a3")
    assert report["code"] == "STAGE_MISSING"
    assert any(c["id"] == "stage" and c["status"] == "FAIL" for c in report["checks"])


def test_ledger_corrupt_fails(tmp_path):
    p = gs.ledger_path(BATCH, tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    report = _verify(tmp_path, "a3")
    assert report["verdict"] == "FAIL"
    assert report["code"] == "LEDGER_CORRUPT"
    assert report["exit_code"] == 1


# ── FAIL：产物绑定 ──────────────────────────────────────
def test_artifact_mismatch_after_edit(tmp_path, capsys):
    made = _build(tmp_path, ["a2", "a3"])
    made["a3"].write_text(json.dumps({"tampered": True}), encoding="utf-8")
    rc = _run(["--batch", BATCH, "--stage", "a3", "--base", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "ARTIFACT_MISMATCH" in out and "重跑" in out
    report = _verify(tmp_path, "a3")
    assert report["code"] == "ARTIFACT_MISMATCH"
    assert "ARTIFACT_MISMATCH" in _issue_ids(report)


def test_explicit_artifact_not_covered(tmp_path, capsys):
    _build(tmp_path, ["a2", "a3"])
    stray = _write(tmp_path / "最终产物" / BATCH / "extra.json")
    rc = _run(["--batch", BATCH, "--stage", "a3", "--base", str(tmp_path),
               "--artifact", str(stray)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "ARTIFACT_NOT_COVERED" in out
    report = _verify(tmp_path, "a3", artifacts=[stray])
    assert report["code"] == "ARTIFACT_NOT_COVERED"
    coverage = next(c for c in report["checks"] if c["id"] == "coverage")
    assert coverage["status"] == "FAIL" and "extra.json" in coverage["detail"]


# ── FAIL：回执链自洽 ────────────────────────────────────
def test_chain_broken_when_stamp_content_tampered(tmp_path, capsys):
    _build(tmp_path, ["a2", "a3", "a4"])
    ledger, err = gs.load_ledger(BATCH, base=tmp_path)
    assert err is None
    ledger["stamps"][1]["note"] = "人工改过"
    gs.write_ledger(ledger, base=tmp_path)
    rc = _run(["--batch", BATCH, "--stage", "a4", "--base", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "CHAIN_BROKEN" in out
    report = _verify(tmp_path, "a4")
    assert report["code"] == "CHAIN_BROKEN"
    assert "CHAIN_BROKEN" in _issue_ids(report)


def test_chain_broken_when_middle_stamp_deleted(tmp_path):
    _build(tmp_path, ["a2", "a3", "a4"])
    ledger, err = gs.load_ledger(BATCH, base=tmp_path)
    assert err is None
    del ledger["stamps"][1]
    gs.write_ledger(ledger, base=tmp_path)
    report = _verify(tmp_path, "a4")
    ids = _issue_ids(report)
    assert report["verdict"] == "FAIL"
    assert report["code"] == "CHAIN_BROKEN"
    assert "SEQ_MISMATCH" in ids and "CHAIN_BROKEN" in ids


# ── WARN / --strict ─────────────────────────────────────
def test_backfill_warn_then_strict_fails(tmp_path, capsys):
    _build(tmp_path, ["a2", "a3"], provenance="backfill")
    rc = _run(["--batch", BATCH, "--stage", "a3", "--base", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0 and "WARN" in out and "STAGE_BACKFILL" in out
    report = _verify(tmp_path, "a3")
    assert report["verdict"] == "WARN" and report["code"] == "STAGE_BACKFILL"
    assert report["exit_code"] == 0
    strict = gv.verify_stage(BATCH, "a3", base=tmp_path, strict=True)
    assert strict["verdict"] == "FAIL"
    assert strict["code"] == "STAGE_BACKFILL"
    assert strict["exit_code"] == 1
    rc_strict = _run(["--batch", BATCH, "--stage", "a3", "--base", str(tmp_path), "--strict"])
    assert rc_strict == 1


def test_exit_code_contract_mapping():
    assert gv.exit_code_for({"verdict": "PASS"}) == 0
    assert gv.exit_code_for({"verdict": "WARN"}) == 0
    assert gv.exit_code_for({"verdict": "WARN"}, strict=True) == 1
    assert gv.exit_code_for({"verdict": "FAIL"}) == 1


# ── JSON 报告 / --quiet / --ledger ──────────────────────
def test_json_out_report_shape(tmp_path, capsys):
    _build(tmp_path, ["a2", "a3"])
    out_path = tmp_path / "reports" / "gate" / "verify.json"
    rc = _run(["--batch", BATCH, "--stage", "a3", "--base", str(tmp_path),
               "--json-out", str(out_path)])
    capsys.readouterr()
    assert rc == 0 and out_path.is_file()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    for key in ("batch", "stage", "verdict", "code", "checks", "issues",
                "ledger", "required_artifacts", "checked_at"):
        assert key in data, key
    assert data["batch"] == BATCH and data["stage"] == "a3"
    assert data["verdict"] == "PASS" and data["code"] == "STAMP_OK"
    assert isinstance(data["checks"], list) and data["checks"]
    assert data["required_artifacts"] == ["质检报告/batch048/A3_质检报告.json"]
    assert data["ledger"].endswith("_gate_ledger.json")
    assert data["exit_code"] == 0


def test_quiet_outputs_single_line(tmp_path, capsys):
    _build(tmp_path, ["a2", "a3"])
    rc = _run(["--batch", BATCH, "--stage", "a3", "--base", str(tmp_path), "--quiet"])
    out = capsys.readouterr().out
    assert rc == 0
    assert len(out.strip().splitlines()) == 1
    assert "PASS" in out


def test_custom_ledger_option(tmp_path):
    _build(tmp_path, ["a2", "a3"])
    custom = tmp_path / "custom" / "ledger.json"
    ledger, err = gs.load_ledger(BATCH, base=tmp_path)
    assert err is None
    gs.write_ledger(ledger, base=tmp_path, path=custom)
    gs.ledger_path(BATCH, tmp_path).unlink()  # 默认位置没有回执链，只有 --ledger 指向的那份
    report = gv.verify_stage(BATCH, "a3", base=tmp_path, ledger=custom)
    assert report["verdict"] == "PASS"
    assert report["ledger"] == str(custom.resolve())


# ── 覆盖校验 SKIP 分支 ──────────────────────────────────
def test_coverage_skipped_when_stage_has_no_expected_artifacts(tmp_path):
    """a5 不在 _STAGE_ARTIFACTS 里：无预期产物 → 覆盖校验 SKIP，不判失败。"""
    _build(tmp_path, ["a2", "a3", "a4", "lv", "a5"])
    report = _verify(tmp_path, "a5")
    assert report["verdict"] == "PASS"
    assert report["exit_code"] == 0
    assert report["coverage_mode"] == "skip"
    assert report["coverage"]["status"] == "SKIP"
    assert report["required_artifacts"] == []
    assert "跳过覆盖校验" in report["coverage"]["detail"]


def test_coverage_skipped_when_expected_artifact_absent(tmp_path):
    """阶段有候选产物但文件都不存在 → expected_artifacts 为空 → 覆盖 SKIP。"""
    ledger = gs.new_ledger(BATCH)
    a2 = _write(tmp_path / "中间产物" / BATCH / "ALL_questions.json")
    gs.append_stamp(ledger, "a2", artifacts=[a2])
    gs.append_stamp(ledger, "a3")  # 没有 质检报告/ 产物
    gs.write_ledger(ledger, base=tmp_path)
    report = _verify(tmp_path, "a3")
    assert report["verdict"] == "PASS"
    assert report["coverage_mode"] == "skip"
    assert report["coverage"]["status"] == "SKIP"
    assert report["exit_code"] == 0


# ── 退出码 2：参数 / 环境错误 ───────────────────────────
def test_exit_code_two_for_missing_base(tmp_path, capsys):
    rc = _run(["--batch", BATCH, "--stage", "a3", "--base", str(tmp_path / "missing")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "环境错误" in err


def test_invalid_stage_exits_two(tmp_path):
    with pytest.raises(SystemExit) as exc:
        _run(["--batch", BATCH, "--stage", "nope", "--base", str(tmp_path)])
    assert exc.value.code == 2
