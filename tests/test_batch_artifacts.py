#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_artifacts.py 测试：批次产物入库判定（P1-3）。

全部用 tmp_path + 真 git init，不依赖真实仓库与网络。
覆盖：白名单分类 / _backup 与 .html 排除 / 历史批次与已归档批次 SKIP /
必需文件未入库 FAIL / stage 后转 PASS / dry-run 不落盘 / 缺回执链的 missing_required。
"""
import subprocess
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
if str(BASE / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE / "scripts"))

import batch_artifacts as ba  # noqa: E402

BATCH = "batch048"
LEGACY = "batch045"


def _repo(tmp_path: Path) -> Path:
    """初始化一个最小 git 仓库（只 init，不 commit）。"""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True,
                   capture_output=True)
    return tmp_path


def _mk(batch_dir: Path, name: str, text: str = "{}") -> Path:
    p = batch_dir / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _full_batch(tmp_path: Path, batch: str = BATCH) -> Path:
    """造一个「证据齐全」的批次目录（回执链真实绑定 FIXED，不是空壳）。"""
    import gate_stamp as gs
    d = tmp_path / "最终产物" / batch
    fixed = _mk(d, "ALL_questions_FIXED.json", "[]")
    ledger = gs.new_ledger(batch)
    gs.append_stamp(ledger, "a4", artifacts=[fixed])
    gs.write_ledger(ledger, tmp_path)
    _mk(d, f"{batch}_A4_追溯日志.json", "{}")
    _mk(d, "review_queue.json", "{}")
    _mk(d, "ALL_questions_FIXED.md", "# 题库")
    _mk(d, f"{batch}_签收单.md", "# 签收")
    _mk(d, "AGENT4_修改声明.md", "# 声明")
    return d


# ── 分类 ────────────────────────────────────────────────
def test_classify_splits_required_deliverable_and_other(tmp_path):
    d = _full_batch(tmp_path)
    _mk(d, "_backup/ALL_questions_FIXED.json", "[]")   # 备份目录排除
    _mk(d, "ALL_questions_FIXED.html", "<html>")        # HC-19 后不再产 html，排除
    _mk(d, "AGENT4_修改声明.md", "# 声明")
    _mk(d, "临时笔记.txt", "x")

    info = ba.classify(BATCH, tmp_path)
    req = {x["name"] for x in info["required"]}
    dlv = {x["name"] for x in info["deliverable"]}
    oth = {x["name"] for x in info["other"]}

    assert req == {"_gate_ledger.json", "ALL_questions_FIXED.json",
                   f"{BATCH}_A4_追溯日志.json", "review_queue.json"}
    assert dlv == {"ALL_questions_FIXED.md", f"{BATCH}_签收单.md", "AGENT4_修改声明.md"}
    assert oth == {"临时笔记.txt"}
    # 排除项任何一类都不该出现
    all_names = req | dlv | oth
    assert "ALL_questions_FIXED.html" not in all_names


def test_classify_ignores_backup_directory_entirely(tmp_path):
    d = _full_batch(tmp_path)
    _mk(d, "_backup/review_queue.json", "{}")
    info = ba.classify(BATCH, tmp_path)
    assert not [x for x in info["required"] + info["deliverable"] if "_backup" in x["path"]]


# ── SKIP 两种 ───────────────────────────────────────────
def test_check_legacy_batch_skips(tmp_path):
    _repo(tmp_path)
    _full_batch(tmp_path, LEGACY)
    r = ba.check(LEGACY, tmp_path)
    assert r["verdict"] == "SKIP"
    assert r["code"] == "LEGACY_NOT_REQUIRED"


def test_check_archived_batch_skips(tmp_path):
    _repo(tmp_path)
    r = ba.check("batch099", tmp_path)
    assert r["verdict"] == "SKIP"
    assert r["code"] == "BATCH_DIR_ABSENT"


# ── FAIL / PASS ─────────────────────────────────────────
def test_check_fails_when_required_untracked(tmp_path):
    _repo(tmp_path)
    _full_batch(tmp_path)
    r = ba.check(BATCH, tmp_path)
    assert r["verdict"] == "FAIL"
    assert r["code"] == "ARTIFACT_UNTRACKED"
    assert len(r["untracked_required"]) == 4
    assert not r["missing_required"]


def test_stage_then_check_passes(tmp_path):
    _repo(tmp_path)
    _full_batch(tmp_path)
    res = ba.stage(BATCH, tmp_path)
    assert res["error"] is None
    assert len(res["added"]) == 7              # 4 必需 + 3 交付
    r = ba.check(BATCH, tmp_path)
    assert r["verdict"] == "PASS"
    assert r["code"] == "ARTIFACTS_TRACKED"


def test_stage_dry_run_does_not_touch_index(tmp_path):
    _repo(tmp_path)
    _full_batch(tmp_path)
    res = ba.stage(BATCH, tmp_path, dry_run=True)
    assert res["dry_run"] and len(res["added"]) == 7
    # 索引没动：check 仍是 FAIL
    assert ba.check(BATCH, tmp_path)["verdict"] == "FAIL"


def test_missing_ledger_is_reported_separately(tmp_path):
    """产物在但回执链不在：这是「跳过门禁」，不是「忘了 add」。"""
    _repo(tmp_path)
    d = tmp_path / "最终产物" / BATCH
    _mk(d, "ALL_questions_FIXED.json", "[]")
    _mk(d, "review_queue.json", "{}")
    r = ba.check(BATCH, tmp_path)
    assert r["verdict"] == "FAIL"
    assert any("_gate_ledger.json" in p for p in r["missing_required"])


def test_require_deliverable_flags_untracked_md(tmp_path):
    _repo(tmp_path)
    d = _full_batch(tmp_path)
    # 只把必需文件入库，交付件故意漏掉
    for name in ("_gate_ledger.json", "ALL_questions_FIXED.json",
                 f"{BATCH}_A4_追溯日志.json", "review_queue.json"):
        subprocess.run(["git", "add", "--", f"最终产物/{BATCH}/{name}"],
                       cwd=str(tmp_path), check=True, capture_output=True)
    assert ba.check(BATCH, tmp_path)["verdict"] == "PASS"
    strict = ba.check(BATCH, tmp_path, require_deliverable=True)
    assert strict["verdict"] == "FAIL"
    assert len(strict["untracked_deliverable"]) == 3


def test_stage_refuses_legacy_batch(tmp_path):
    _repo(tmp_path)
    _full_batch(tmp_path, LEGACY)
    res = ba.stage(LEGACY, tmp_path)
    assert res["error"] and "历史批次不回填" in res["error"]


# ── CLI 退出码契约 ──────────────────────────────────────
def test_cli_check_exit_codes(tmp_path, capsys):
    _repo(tmp_path)
    _full_batch(tmp_path)
    assert ba.main(["check", "--batch", BATCH, "--base", str(tmp_path)]) == 1
    capsys.readouterr()
    ba.main(["stage", "--batch", BATCH, "--base", str(tmp_path)])
    capsys.readouterr()
    assert ba.main(["check", "--batch", BATCH, "--base", str(tmp_path)]) == 0


def test_cli_rejects_missing_base(tmp_path, capsys):
    assert ba.main(["check", "--batch", BATCH, "--base", str(tmp_path / "nope")]) == 2
    assert "[ERROR]" in capsys.readouterr().err


# ── 2026-11-05 复核修正的回归 ───────────────────────────
def test_agent4_trace_log_naming_is_required(tmp_path):
    """真实产物名是 AGENT4_追溯日志.json；白名单必须按后缀匹配（原来只认 *_A4_*）。"""
    d = _repo(tmp_path) / "最终产物" / BATCH
    _mk(d, "_gate_ledger.json", '{"schema_version":"1.0","stamps":[]}')
    _mk(d, "ALL_questions_FIXED.json", "[]")
    _mk(d, "AGENT4_追溯日志.json", "{}")
    _mk(d, "review_queue.json", "{}")
    names = {x["name"] for x in ba.classify(BATCH, tmp_path)["required"]}
    assert "AGENT4_追溯日志.json" in names
    assert len(ba.check(BATCH, tmp_path)["untracked_required"]) == 4


def test_ledger_bound_artifact_is_required_without_whitelist_match(tmp_path):
    """押题卷之类名字不在白名单里的产物，只要回执绑定就必须入库。"""
    import gate_stamp as gs
    root = _repo(tmp_path)
    d = root / "最终产物" / BATCH
    art = _mk(d, "押题卷_急诊与灾难医学_100题.json", "[]")
    _mk(d, "review_queue.json", "{}")
    ledger = gs.new_ledger(BATCH)
    gs.append_stamp(ledger, "a4", artifacts=[art])
    gs.write_ledger(ledger, root)

    names = {x["name"] for x in ba.classify(BATCH, tmp_path)["required"]}
    assert "押题卷_急诊与灾难医学_100题.json" in names
    assert "_gate_ledger.json" in names
    # 没有 ALL_questions_FIXED.json 也不算缺（由回执绑定决定，不按文件名硬编码）
    r = ba.check(BATCH, tmp_path)
    assert r["verdict"] == "FAIL" and not r["missing_required"], r
    assert ba.stage(BATCH, tmp_path)["error"] is None
    assert ba.check(BATCH, tmp_path)["verdict"] == "PASS"


def test_ledger_bound_missing_file_is_reported(tmp_path):
    """回执绑定过、但现在文件没了 → 报 missing_required（证据链断了，不是忘了 add）。"""
    import gate_stamp as gs
    root = _repo(tmp_path)
    d = root / "最终产物" / BATCH
    art = _mk(d, "ALL_questions_FIXED.json", "[]")
    ledger = gs.new_ledger(BATCH)
    gs.append_stamp(ledger, "a4", artifacts=[art])
    gs.write_ledger(ledger, root)
    art.unlink()
    r = ba.check(BATCH, tmp_path)
    assert r["verdict"] == "FAIL"
    assert any("ALL_questions_FIXED.json" in p for p in r["missing_required"]), r
