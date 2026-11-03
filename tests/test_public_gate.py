# -*- coding: utf-8 -*-
"""P8-S3 公开闸门测试（AC-P8-04）。

重点不是「现在能过」，而是「把最终产物加进白名单必须过不去」——
否则闸门只是装饰。
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

import public_gate as pg  # noqa: E402


# ── 白名单解析 ──────────────────────────────────────────────

def test_parse_deploy_yml_returns_entries():
    got = pg.parse_deploy_yml()
    assert "index.html" in got
    assert "assets" in got
    assert len(got) >= 8


def test_parse_deploy_ps1_returns_entries():
    got = pg.parse_deploy_ps1()
    assert "index.html" in got
    assert "assets" in got


def test_two_channels_share_same_whitelist():
    """CI 与本地部署必须同一口径，否则有一条通道在偷偷多传。"""
    assert set(pg.parse_deploy_yml()) == set(pg.parse_deploy_ps1())


def test_whitelist_does_not_contain_final_products():
    """最终产物 绝不能出现在白名单里。"""
    entries = pg.parse_deploy_yml() + pg.parse_deploy_ps1()
    for bad in ("最终产物", "中间产物", "scripts", "question_bank", "Obsidian产物", "docs"):
        assert bad not in entries, f"{bad} 不该在上传白名单"


# ── license 口径 ────────────────────────────────────────────

def test_declared_is_not_cleared():
    """有公开使用声明 ≠ 有授权凭证。这是闸门比 matrix 严的地方。"""
    assert pg.derive_status({"license": "public"}) == "declared"
    assert pg.derive_status({"license": "public_noncommercial"}) == "declared"
    assert pg.derive_status({"license": "unknown"}) == "unclear"
    assert pg.derive_status({}) == "unclear"


def test_explicit_cleared_wins():
    assert pg.derive_status({"license": "unknown", "license_status": "cleared"}) == "cleared"
    assert pg.derive_status({"license": "public", "license_status": "revoked"}) == "revoked"


def test_only_real_questions_indexed():
    rows = [
        {"qid": "Q1", "real": True, "license": "unknown"},
        {"qid": "Q2", "real": False, "license": "unknown"},
    ]
    idx = pg.qid_index(rows)
    assert "Q1" in idx and "Q2" not in idx


# ── G1 / G2 ────────────────────────────────────────────────

def test_g1_passes_on_real_repo():
    r = pg.check_whitelist_consistency(pg.parse_deploy_yml(), pg.parse_deploy_ps1())
    assert r["status"] == "PASS", r["problems"]


def test_g1_fails_when_channels_diverge():
    r = pg.check_whitelist_consistency(["index.html", "assets"], ["index.html"])
    assert r["status"] == "FAIL"
    assert any("仅 CI 上传" in p for p in r["problems"])


def test_g1_fails_when_unparsable():
    """白名单解析失败必须 FAIL —— 否则格式一变闸门就静默失效。"""
    r = pg.check_whitelist_consistency([], [])
    assert r["status"] == "FAIL"


def test_g2_root_output_dir_is_warn():
    assert pg.check_output_dir(".")["status"] == "WARN"
    assert pg.check_output_dir("./")["status"] == "WARN"


def test_g2_non_root_passes():
    assert pg.check_output_dir("dist")["status"] == "PASS"
    assert pg.check_output_dir("_stage")["status"] == "PASS"


# ── G3：核心断言 ────────────────────────────────────────────

def _write(tmp: Path, rel: str, text: str) -> Path:
    p = tmp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_g3_lists_question_bank_in_whitelist(tmp_path=None):
    """白名单里混入题库文件 → 只清点，不阻断（2026-11-03 授权不再作门禁）。"""
    import tempfile

    tmp = Path(tmp_path or tempfile.mkdtemp())
    f = _write(tmp, "site/bank.md", "见 batch032_M1_A1_021 此题")
    idx = {"batch032_M1_A1_021": {"real": True, "status": "unclear",
                                  "license": "unknown", "origin_kind": "kaoyan"}}
    r = pg.check_qid_exposure([f], idx, root=tmp)
    assert r["status"] == "INFO"
    assert r["blocked_count"] == 1
    assert r["blocked"][0]["qid"] == "batch032_M1_A1_021"
    assert "不再阻断" in r["note"]


def test_g3_ignores_original_questions(tmp_path=None):
    """原创题不进真题索引（清点为空）。"""
    import tempfile

    tmp = Path(tmp_path or tempfile.mkdtemp())
    f = _write(tmp, "site/bank.md", "见 batch032_M1_A1_999 此题")
    r = pg.check_qid_exposure([f], {}, root=tmp)
    assert r["status"] == "INFO" and r["blocked_count"] == 0


def test_g3_cleared_passes(tmp_path=None):
    import tempfile

    tmp = Path(tmp_path or tempfile.mkdtemp())
    f = _write(tmp, "site/bank.md", "见 batch032_M1_A1_021 此题")
    idx = {"batch032_M1_A1_021": {"real": True, "status": "cleared",
                                  "license": "cleared", "origin_kind": "kaoyan"}}
    r = pg.check_qid_exposure([f], idx, root=tmp)
    assert r["status"] == "INFO" and r["cleared"] == 1


def test_g3_declared_is_informational(tmp_path=None):
    """public_noncommercial 只清点，不再拦截（授权门禁已取消）。"""
    import tempfile

    tmp = Path(tmp_path or tempfile.mkdtemp())
    f = _write(tmp, "site/bank.md", "见 batch032_M1_A1_021 此题")
    idx = {"batch032_M1_A1_021": {"real": True, "status": "declared",
                                  "license": "public_noncommercial", "origin_kind": "kaoyan"}}
    assert pg.check_qid_exposure([f], idx, root=tmp)["status"] == "INFO"


def test_real_whitelist_is_clean():
    """当前仓库真实白名单内不得有任何未清权真题。"""
    entries = list(dict.fromkeys(pg.parse_deploy_yml() + pg.parse_deploy_ps1()))
    files = pg.expand_whitelist(entries)
    idx = pg.qid_index(pg.load_matrix()["rows"])
    r = pg.check_qid_exposure(files, idx)
    assert r["status"] == "INFO", r["blocked"][:5]
    assert r["blocked_count"] == 0, r["blocked"][:5]


# ── G4 裸题面 ──────────────────────────────────────────────

def test_g4_flags_bare_stem_without_qid(tmp_path=None):
    import tempfile

    tmp = Path(tmp_path or tempfile.mkdtemp())
    f = _write(tmp, "site/leak.html",
               "<p>下列哪项最恰当</p><p>A. 甲</p><p>参考答案：A</p>")
    r = pg.check_bare_stems([f], {}, root=tmp)
    assert r["status"] == "FAIL" and r["suspects"]


def test_g4_skips_index_and_qid_files(tmp_path=None):
    import tempfile

    tmp = Path(tmp_path or tempfile.mkdtemp())
    a = _write(tmp, "site/index.html", "下列哪项 参考答案 A. B.")
    b = _write(tmp, "site/ok.md", "batch032_M1_A1_001 下列哪项 参考答案")
    r = pg.check_bare_stems([a, b], {}, root=tmp)
    assert r["status"] == "PASS", r["suspects"]


# ── G6 判定 ────────────────────────────────────────────────

def test_classify_spa_fallback():
    assert pg.classify_response("text/html; charset=utf-8", b"<!DOCTYPE html><html>") == "SPA_FALLBACK"


def test_classify_markdown_is_exposed():
    """真返回 md 文件才是暴露 —— 这正是状态码看不出来的地方。"""
    assert pg.classify_response("text/markdown", b"# \xe5\x86\x85\xe7\xa7\x91") == "EXPOSED"
    assert pg.classify_response("application/octet-stream", b"\x00\x01") == "EXPOSED"


def test_classify_html_non_index():
    assert pg.classify_response("text/html", b"<html><body>hi") == "HTML"


def test_probe_url_quotes_chinese():
    """中文路径必须 percent-encode，否则 urllib 抛 UnicodeEncodeError。"""
    from urllib.parse import quote

    p = "最终产物/batch033/内科教学题库.md"
    assert quote(p, safe="/").startswith("%E6%9C%80%E7%BB%88")


# ── 端到端与退出码 ─────────────────────────────────────────

def test_run_returns_ok_on_real_repo(tmp_path=None):
    rep = pg.run()
    assert rep["status"] in ("PASS", "WARN")
    assert rep["public_unclear"] == 0
    ids = [c["id"] for c in rep["checks"]]
    assert ids[:4] == ["G1", "G2", "G3", "G4"]


def test_run_extra_path_is_inventoried_not_blocked():
    """模拟把 最终产物 加进白名单 → 授权只清点，不再整闸 FAIL（2026-11-03）。"""
    rep = pg.run(extra=["最终产物"])
    assert rep["status"] != "FAIL"
    assert rep["public_unclear"] > 0
    g3 = next(c for c in rep["checks"] if c["id"] == "G3")
    assert g3["real_qids_in_whitelist"] > 0


def test_main_exit_code_ok_when_only_license_inventory(tmp_path=None):
    """授权内容不再导致非 0 退出码。"""
    import tempfile

    tmp = Path(tempfile.mkdtemp())
    code = pg.main(["--extra", "最终产物", "--quiet",
                    "--json", str(tmp / "r.json"), "--md", str(tmp / "r.md")])
    assert code == 0
    data = json.loads((tmp / "r.json").read_text(encoding="utf-8"))
    assert data["status"] != "FAIL"


def test_report_md_mentions_license_policy():
    rep = pg.run()
    md = pg.render_md(rep)
    assert "declared" in md and "cleared" in md
    assert "不再" in md and "授权" in md, "报告必须写明授权已不作门禁"


# ── 数据源可得性（CI 上 reports/ 不进 git，这是关键）────────────

def test_live_scan_does_not_depend_on_reports_dir():
    """默认必须现扫题库：reports/ 被 .gitignore 忽略，CI 上快照不存在。"""
    mx = pg.load_matrix(prefer_snapshot=False)
    assert mx["source"] == "live-scan"
    assert not mx["missing"]
    assert len(mx["rows"]) > 1000
    assert mx["files"] >= 10


def test_live_scan_matches_snapshot_when_available():
    """现扫与快照口径必须一致，否则两个数字会互相打架。"""
    live = pg.qid_index(pg.load_matrix(prefer_snapshot=False)["rows"])
    if not pg.MATRIX.exists():
        return  # 快照可重建，不存在就跳过这条对比
    snap = pg.qid_index(pg.load_matrix(prefer_snapshot=True)["rows"])
    assert set(live) == set(snap)
    assert sum(1 for v in live.values() if v["status"] == "cleared") == \
           sum(1 for v in snap.values() if v["status"] == "cleared")


def test_matrix_unavailable_is_informational():
    """授权数据取不到只影响清点，不再阻断部署（2026-11-03）。"""
    from unittest.mock import patch

    with patch.object(pg, "load_matrix",
                      return_value={"rows": [], "missing": True,
                                    "error": "boom", "summary": {}, "source": "failed"}):
        rep = pg.run()
    assert rep["status"] != "FAIL"
    assert rep["checks"][0]["id"] == "G0"
    assert rep["checks"][0]["status"] == "INFO"
