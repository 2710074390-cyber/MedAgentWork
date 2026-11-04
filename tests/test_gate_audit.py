#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_audit 零依赖测试（全部在临时目录构造证据，不碰真实批次）。

覆盖：LEDGER_MISSING / LEGACY_UNSTAMPED（含 --strict 升级）/ CHAIN_BROKEN /
      ARTIFACT_ABSENT / ARTIFACT_MISMATCH / STAGE_BACKFILL / 有效链 PASS /
      --all 多批发现与 --limit / --changed-only 路径解析（纯函数）与 fallback /
      --json-out 报告形状 / exit code 契约 / --recheck 只挑题目数组。
"""
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE / "scripts"))

import gate_audit as ga  # noqa: E402
import gate_stamp as gs  # noqa: E402


# ---------------------------------------------------------------------------
# 临时目录与证据构造
# ---------------------------------------------------------------------------
def _tmp():
    return Path(tempfile.mkdtemp(prefix="gate_audit_"))


def _write_artifact(base, batch, payload=None, name="ALL_questions.json", root="中间产物"):
    """写一个题目数组产物（默认是合法的 JSON list）。"""
    p = base / root / batch / name
    p.parent.mkdir(parents=True, exist_ok=True)
    body = [{"id": "q1", "stem": "题干"}] if payload is None else payload
    p.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return p


def _make_ledger(base, batch, stages=("a2",), artifacts=None, provenance="driver"):
    """用 gate_stamp 原语造一条回执链（产物传绝对路径，与 cwd 无关）。"""
    ledger = gs.new_ledger(batch)
    for st in stages:
        gs.append_stamp(ledger, st, artifacts=artifacts or (), provenance=provenance)
    gs.write_ledger(ledger, base)
    return ledger


def _audit(base, *extra):
    """跑 main() 并读回 JSON 报告，返回 (rc, report)。"""
    out = base / "audit.json"
    rc = ga.main(["--base", str(base), "--json-out", str(out), *extra])
    return rc, json.loads(out.read_text(encoding="utf-8"))


def _entry(report, batch):
    return next(e for e in report["batches"] if e["batch"] == batch)


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------
def test_ledger_missing_for_required_batch():
    """batch048 起无回执链 → FAIL LEDGER_MISSING，退出码 1。"""
    base = _tmp()
    rc, rep = _audit(base, "--batch", "048")  # 顺带验证批次 ID 归一
    assert rc == 1, rep
    entry = _entry(rep, "batch048")
    assert entry["verdict"] == "FAIL"
    assert entry["code"] == "LEDGER_MISSING"
    assert entry["stamps"] == 0
    assert rep["summary"] == {"pass": 0, "warn": 0, "fail": 1}


def test_legacy_unstamped_warn_then_strict_fails():
    """batch044 无回执 → WARN 且退出码 0；--strict 时升为 FAIL（退出码 1）。"""
    base = _tmp()
    rc, rep = _audit(base, "--batch", "batch044")
    assert rc == 0, rep
    entry = _entry(rep, "batch044")
    assert entry["verdict"] == "WARN"
    assert entry["code"] == "LEGACY_UNSTAMPED"
    assert rep["summary"] == {"pass": 0, "warn": 1, "fail": 0}

    rc, rep = _audit(base, "--batch", "batch044", "--strict")
    assert rc == 1
    entry = _entry(rep, "batch044")
    assert entry["verdict"] == "FAIL"
    assert entry["code"] == "LEGACY_UNSTAMPED"
    assert rep["summary"]["fail"] == 1


def test_chain_broken_fails():
    """回执内容被改动（自身哈希不符）→ FAIL CHAIN_BROKEN。"""
    base = _tmp()
    ledger = gs.new_ledger("batch048")
    gs.append_stamp(ledger, "a2")
    gs.append_stamp(ledger, "a3")
    ledger["stamps"][0]["ts"] = "2000-01-01T00:00:00"  # 篡改：回执哈希对不上
    gs.write_ledger(ledger, base)

    rc, rep = _audit(base, "--batch", "batch048")
    assert rc == 1
    entry = _entry(rep, "batch048")
    assert entry["verdict"] == "FAIL"
    assert entry["code"] == "CHAIN_BROKEN"
    assert entry["stamps"] == 2


def test_artifact_absent_warns_not_fails():
    """回执记录的产物不存在（中间产物常不入库）→ WARN，不阻断。"""
    base = _tmp()
    p = _write_artifact(base, "batch048")
    _make_ledger(base, "batch048", artifacts=[p])
    p.unlink()

    rc, rep = _audit(base, "--batch", "batch048")
    assert rc == 0, rep
    entry = _entry(rep, "batch048")
    assert entry["verdict"] == "WARN"
    assert entry["code"] == "ARTIFACT_ABSENT"
    assert rep["summary"]["fail"] == 0


def test_artifact_mismatch_fails():
    """回执之后产物被改 → FAIL ARTIFACT_MISMATCH。"""
    base = _tmp()
    p = _write_artifact(base, "batch048")
    _make_ledger(base, "batch048", artifacts=[p])
    p.write_text(json.dumps([{"id": "q1", "stem": "被改过的题干"}], ensure_ascii=False),
                 encoding="utf-8")

    rc, rep = _audit(base, "--batch", "batch048")
    assert rc == 1
    entry = _entry(rep, "batch048")
    assert entry["verdict"] == "FAIL"
    assert entry["code"] == "ARTIFACT_MISMATCH"


def test_backfill_stamp_warns():
    """provenance=backfill → WARN STAGE_BACKFILL（补录无法证明门禁真跑过）。"""
    base = _tmp()
    _make_ledger(base, "batch048", provenance="backfill")

    rc, rep = _audit(base, "--batch", "batch048")
    assert rc == 0
    entry = _entry(rep, "batch048")
    assert entry["verdict"] == "WARN"
    assert entry["code"] == "STAGE_BACKFILL"


def test_valid_chain_passes():
    """回执链完整 + 产物字节一致 → PASS，退出码 0。"""
    base = _tmp()
    p = _write_artifact(base, "batch048")
    _make_ledger(base, "batch048", stages=("a2", "a3"), artifacts=[p])

    rc, rep = _audit(base, "--batch", "batch048")
    assert rc == 0, rep
    entry = _entry(rep, "batch048")
    assert entry["verdict"] == "PASS"
    assert entry["code"] == "OK"
    assert entry["stamps"] == 2
    assert entry["issues"] == []
    assert entry["recheck"] == []


def test_all_discovers_multiple_batches_and_limit():
    """--all 扫三个目录并集，按批次号排序；--limit 截断。"""
    base = _tmp()
    (base / "最终产物" / "batch048").mkdir(parents=True)
    (base / "中间产物" / "batch049").mkdir(parents=True)
    (base / "质检报告" / "batch043").mkdir(parents=True)
    (base / "最终产物" / "视觉海报").mkdir(parents=True)  # 非批次目录，不应被发现

    rc, rep = _audit(base, "--all")
    assert rc == 1
    assert [e["batch"] for e in rep["batches"]] == ["batch043", "batch048", "batch049"]
    assert rep["summary"] == {"pass": 0, "warn": 1, "fail": 2}
    assert [e["code"] for e in rep["batches"]] == [
        "LEGACY_UNSTAMPED", "LEDGER_MISSING", "LEDGER_MISSING"]

    rc, rep = _audit(base, "--all", "--limit", "1")
    assert rc == 0  # 只剩历史遗留批次 → WARN 不阻断
    assert [e["batch"] for e in rep["batches"]] == ["batch043"]


def test_changed_paths_to_batches_pure():
    """--changed-only 的「改动路径→批次 id」是纯函数，不真的跑 git。"""
    paths = [
        "最终产物/batch048/ALL_questions_FIXED.json",
        "中间产物/batch049/ALL_questions.json",
        "质检报告/batch043/A3_质检报告.json",
        "复习资料/batch050/真题解析.md",
        "docs/batch051/plan.md",             # 不在审计根目录下 → 排除
        "scripts/gate_audit.py",             # 无批次号 → 排除
        "最终产物/视觉海报/cover.png",        # 无批次号 → 排除
        "最终产物/batch048/_gate_ledger.json",
        r"最终产物\batch046\ALL_questions_FIXED.json",  # Windows 分隔符
        "./中间产物/batch047/ALL_questions.json",        # 带 ./ 前缀
    ]
    assert ga.batches_from_changed_paths(paths) == [
        "batch043", "batch046", "batch047", "batch048", "batch049", "batch050"]
    assert ga.batches_from_changed_paths([]) == []
    assert ga.batches_from_changed_paths(["docs/batch099/a.md"]) == []


def test_changed_only_fallback_to_ledger_batches():
    """临时目录不是 git 仓库 → 基线不可解，回退为「所有已有回执链的批次」并标注 fallback。"""
    base = _tmp()
    p = _write_artifact(base, "batch048")
    _make_ledger(base, "batch048", artifacts=[p])

    rc, rep = _audit(base, "--changed-only")
    assert rc == 0, rep
    assert rep["mode"] == "changed-only"
    assert rep["fallback"] is True
    assert rep["fallback_reason"], "回退必须给出原因"
    assert rep["since"] == "HEAD~1"
    assert [e["batch"] for e in rep["batches"]] == ["batch048"]
    assert _entry(rep, "batch048")["verdict"] == "PASS"
    assert "[FALLBACK]" in ga.format_human(rep)


def test_json_out_report_shape():
    """--json-out 报告形状：顶层字段 + 每批字段 + base 解析。"""
    base = _tmp()
    p = _write_artifact(base, "batch048")
    _make_ledger(base, "batch048", artifacts=[p])

    rc, rep = _audit(base, "--batch", "batch048")
    assert rc == 0
    for key in ("generated_at", "mode", "base", "batches", "summary"):
        assert key in rep, key
    assert set(rep["summary"]) == {"pass", "warn", "fail"}
    assert rep["base"] == str(base.resolve())
    entry = rep["batches"][0]
    for key in ("batch", "verdict", "code", "issues", "stamps", "recheck"):
        assert key in entry, key
    assert json.loads(json.dumps(rep, ensure_ascii=False))["batches"][0]["batch"] == "batch048"


def test_recheck_skips_non_question_artifacts():
    """--recheck 只对题目数组（JSON list）跑门禁；非题目产物不触发子进程。"""
    base = _tmp()
    p = base / "中间产物" / "batch048" / "report.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"items": [], "note": "非题目数组"}, ensure_ascii=False),
                 encoding="utf-8")
    _make_ledger(base, "batch048", artifacts=[p])

    rc, rep = _audit(base, "--batch", "batch048", "--recheck")
    assert rc == 0, rep
    entry = _entry(rep, "batch048")
    assert entry["verdict"] == "PASS"
    assert entry["recheck"] == []       # 没有题目数组 → 不复检，也不报 ERROR
    assert rep["recheck_enabled"] is True
    assert ga.is_question_array([{"id": "q1"}]) is True
    assert ga.is_question_array({"id": "q1"}) is False
    assert ga.is_question_array([]) is False


def test_artifact_relative_to_repo_root_fallback():
    """gate_stamp 默认按仓库根落相对路径；--base 指向子目录时仍应解析到（回退 BASE）。"""
    fake_repo = _tmp() / "repo"
    sub = fake_repo / "subtree"
    p = fake_repo / "中间产物" / "batch048" / "ALL_questions.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps([{"id": "q1"}], ensure_ascii=False), encoding="utf-8")

    old_ga_base, old_gs_base = ga.BASE, gs.BASE
    try:
        ga.BASE = fake_repo
        gs.BASE = fake_repo  # append_stamp 的 rel() 以模块 BASE 为仓库根
        ledger = gs.new_ledger("batch048")
        gs.append_stamp(ledger, "a2", artifacts=[p])
        gs.write_ledger(ledger, sub)  # 回执链落在子目录树里
        rc, rep = _audit(sub, "--batch", "batch048")
    finally:
        ga.BASE, gs.BASE = old_ga_base, old_gs_base

    assert rc == 0, rep
    assert _entry(rep, "batch048")["verdict"] == "PASS"


def test_exit_code_contract():
    """用法/环境错误 → 2；缺链 → 1；历史遗留 → 0。"""
    assert ga.main([]) == 2                                          # 缺模式参数
    assert ga.main(["--batch", "bogus"]) == 2                        # 非法批次 ID
    assert ga.main(["--batch", "batch048", "--all"]) == 2            # 模式互斥
    assert ga.main(["--batch", "batch048", "--limit", "-1"]) == 2    # 非法 limit
    assert ga.main(["--batch", "batch048", "--base", "/no/such/dir"]) == 2
    assert ga.main(["--batch", "batch048", "--base", str(_tmp())]) == 1

def test_stage_missing_warns_for_inflight_batch():
    """产物在、该阶段没回执：未签收批次只告警（可能正在流程中）。"""
    base = _tmp()
    a2 = _write_artifact(base, "batch048")
    _make_ledger(base, "batch048", stages=("a2",), artifacts=[a2])
    qc = base / "质检报告" / "batch048" / "A3_质检报告.json"
    qc.parent.mkdir(parents=True, exist_ok=True)
    qc.write_text('{"gate_decision": "PASS"}', encoding="utf-8")
    rc, rep = _audit(base, "--batch", "batch048")
    entry = _entry(rep, "batch048")
    assert entry["verdict"] == "WARN" and entry["code"] == "STAGE_MISSING", entry
    assert rc == 0


def test_stage_missing_fails_for_approved_batch():
    """签收批次必须整链齐全：跳过 a3 直接写质检报告 → FAIL STAGE_MISSING。"""
    base = _tmp()
    (base / "workflow_state.json").write_text(
        json.dumps({"schema_version": 2, "batch048": {"status": "APPROVED"}}, ensure_ascii=False),
        encoding="utf-8")
    a2 = _write_artifact(base, "batch048")
    _make_ledger(base, "batch048", stages=("a2",), artifacts=[a2])
    qc = base / "质检报告" / "batch048" / "A3_质检报告.json"
    qc.parent.mkdir(parents=True, exist_ok=True)
    qc.write_text('{"gate_decision": "PASS"}', encoding="utf-8")
    rc, rep = _audit(base, "--batch", "batch048")
    entry = _entry(rep, "batch048")
    assert entry["verdict"] == "FAIL" and entry["code"] == "STAGE_MISSING", entry
    assert rc == 1


def test_stage_missing_ignores_absent_artifacts():
    """中间产物没入库时不能误报 STAGE_MISSING（只有产物在才要求回执）。"""
    base = _tmp()
    _make_ledger(base, "batch048", stages=("a2",), artifacts=[])
    rc, rep = _audit(base, "--batch", "batch048")
    entry = _entry(rep, "batch048")
    assert entry["verdict"] == "PASS", entry
    assert rc == 0

