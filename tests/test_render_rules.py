"""规则注册表 lint / 覆盖率 的回归测试（P1-S2）。

运行: python scripts/run_tests.py test_render_rules
或:   python -m pytest tests/test_render_rules.py -q
"""
import copy
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
for p in (str(BASE), str(BASE / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import render_rules  # noqa: E402


# ── 真实注册表：必须自洽 ────────────────────────────────────

def _reg():
    return render_rules.load_registry(render_rules.DEFAULT_REGISTRY)


def _codes(issues, level="error"):
    return [i["code"] for i in issues if i["level"] == level]


def test_registry_loads_rules():
    reg = _reg()
    assert isinstance(reg.get("rules"), list)
    assert len(reg["rules"]) >= 30, f"规则过少（{len(reg['rules'])}），注册表可能被裁剪"
    assert reg.get("registry_version")


def test_no_duplicate_rule_id():
    issues, _ = render_rules.lint(_reg())
    assert "L1_DUP_ID" not in _codes(issues), "规则 ID 重复（AC-P1-02）"


def test_no_duplicate_alias():
    issues, _ = render_rules.lint(_reg())
    bad = [c for c in _codes(issues) if c in ("L2_DUP_ALIAS", "L2_ALIAS_SHADOWS_ID")]
    assert not bad, f"别名重复或与 ID 撞名（AC-P1-02）: {bad}"


def test_hard_rules_have_detector_or_backlog():
    issues, stats = render_rules.lint(_reg())
    bad = [i for i in issues if i["code"] == "L3_HARD_NO_DETECTOR"]
    assert not bad, f"存在既无检测器又未登记 backlog 的 hard 规则: {[i['rule_id'] for i in bad]}"
    assert stats["hard"] > 0


def test_all_detectors_resolve():
    """注册表不能引用不存在的文件/函数/标签（否则等于「声称有检测器」）。"""
    issues, _ = render_rules.lint(_reg())
    bad = [i for i in issues if i["code"].startswith("L6_")]
    assert not bad, f"检测器无法解析: {[(i['code'], i['rule_id'], i['msg']) for i in bad]}"


def test_sources_traceable():
    issues, _ = render_rules.lint(_reg())
    assert "L5_UNKNOWN_SOURCE" not in _codes(issues)


def test_config_keys_consistent_with_defaults_and_yaml():
    """三处一致：registry.config_keys ↔ pipeline_config.DEFAULTS ↔ pipeline.yaml（AC-P1-04）。"""
    issues, _ = render_rules.lint(_reg())
    bad = [i for i in issues if i["code"].startswith("L7_") or i["code"].startswith("L8_")]
    assert not bad, f"阈值副本冲突: {[(i['code'], i['rule_id'], i['msg']) for i in bad]}"


def test_policy_bindings_resolve():
    issues, _ = render_rules.lint(_reg())
    bad = [i for i in issues if i["code"].startswith("L9_")]
    assert not bad, f"policy_bindings 引用不可解析: {[(i['code'], i['msg']) for i in bad]}"


def test_coverage_meets_ac():
    """AC-P1-03：hard 规则检测器覆盖率 ≥80%。"""
    cov = render_rules.coverage(_reg())
    assert cov["hard_total"] > 0
    assert cov["ratio"] >= 0.80, f"覆盖率 {cov['ratio']:.1%} < 80%，缺口: {cov['gaps']}"


def test_real_registry_has_zero_errors():
    issues, _ = render_rules.lint(_reg())
    assert not _codes(issues), f"注册表存在 lint 不一致项: {_codes(issues)}"


# ── 负例：lint 必须能抓到问题（否则等于没校验）──────────────

def _mini(rules, **kw):
    reg = {"schema_version": 1, "registry_version": "test", "rules": rules}
    reg.update(kw)
    return reg


def _rule(**kw):
    base = {"id": "X-1", "title": "t", "kind": "item", "severity": "soft", "status": "active"}
    base.update(kw)
    return base


def test_detect_duplicate_id():
    reg = _mini([_rule(id="X-1"), _rule(id="X-1")])
    issues, _ = render_rules.lint(reg)
    assert "L1_DUP_ID" in _codes(issues)


def test_detect_duplicate_alias():
    reg = _mini([_rule(id="X-1", aliases=["R9"]), _rule(id="X-2", aliases=["R9"])])
    issues, _ = render_rules.lint(reg)
    assert "L2_DUP_ALIAS" in _codes(issues)


def test_detect_alias_shadowing_id():
    reg = _mini([_rule(id="X-1"), _rule(id="X-2", aliases=["X-1"])])
    issues, _ = render_rules.lint(reg)
    assert "L2_ALIAS_SHADOWS_ID" in _codes(issues)


def test_detect_hard_without_detector():
    reg = _mini([_rule(id="X-1", severity="hard")])
    issues, _ = render_rules.lint(reg)
    assert "L3_HARD_NO_DETECTOR" in _codes(issues)


def test_semantic_backlog_suppresses_hard_error():
    reg = _mini([_rule(id="X-1", severity="hard",
                       detector={"type": "semantic", "reviewer": "专家"})],
                semantic_backlog=["X-1"])
    issues, _ = render_rules.lint(reg)
    assert "L3_HARD_NO_DETECTOR" not in _codes(issues)
    assert "L3_HARD_SEMANTIC_BACKLOG" in _codes(issues, "warn")


def test_detect_conflicting_direction():
    """同一字段被 min 与 max 双向约束且未声明 range_with → error。"""
    reg = _mini([
        _rule(id="X-1", target="len", direction="min"),
        _rule(id="X-2", target="len", direction="max"),
    ])
    issues, _ = render_rules.lint(reg)
    assert "L4_CONFLICT_DIRECTION" in _codes(issues)


def test_range_pair_declared_is_allowed():
    reg = _mini([
        _rule(id="X-1", target="len", direction="min", range_with="X-2"),
        _rule(id="X-2", target="len", direction="max", range_with="X-1"),
    ])
    issues, _ = render_rules.lint(reg)
    assert "L4_CONFLICT_DIRECTION" not in _codes(issues)


def test_detect_missing_detector_symbol():
    reg = _mini([_rule(id="X-1", severity="hard",
                       detector={"type": "python",
                                 "file": "scripts/validate/rules_numeric.py",
                                 "symbol": "check_not_exist_xyz"})])
    issues, _ = render_rules.lint(reg)
    assert "L6_DETECTOR_SYMBOL_MISSING" in _codes(issues)


def test_detect_missing_detector_file():
    reg = _mini([_rule(id="X-1", severity="hard",
                       detector={"type": "python", "file": "scripts/nope_xyz.py", "symbol": "f"})])
    issues, _ = render_rules.lint(reg)
    assert "L6_DETECTOR_FILE_MISSING" in _codes(issues)


def test_detect_missing_tag():
    reg = _mini([_rule(id="X-1", severity="hard",
                       detector={"type": "python",
                                 "file": "scripts/check_learning_value.py",
                                 "symbol": "check_item", "tag": "R99"})])
    issues, _ = render_rules.lint(reg)
    assert "L6_DETECTOR_TAG_MISSING" in _codes(issues)


def test_detect_bad_severity():
    bad = _rule(id="X-1")
    bad["severity"] = "urgent"
    issues, _ = render_rules.lint(_mini([bad]))
    assert "L0_BAD_SEVERITY" in _codes(issues)


# ── 渲染产物 ───────────────────────────────────────────────

def test_render_writes_expected_files():
    reg = _reg()
    with tempfile.TemporaryDirectory() as td:
        written = render_rules.render(reg, Path(td))
        names = {p.name for p in written}
        assert {"rule_index.json", "rules_table.md",
                "prompt_constraints.md", "config_thresholds.yaml"} <= names
        idx = (Path(td) / "rule_index.json").read_text(encoding="utf-8")
        assert '"rules"' in idx
        th = (Path(td) / "config_thresholds.yaml").read_text(encoding="utf-8")
        assert "thresholds:" in th and "r2_ratio_fail" in th


def test_render_does_not_touch_soul_or_prompt():
    """渲染只写 out_dir —— 不得直接改 SOUL.md / 提示词（P1-S2 约定）。"""
    soul = BASE / "SOUL.md"
    before = soul.read_bytes()
    reg = _reg()
    with tempfile.TemporaryDirectory() as td:
        render_rules.render(copy.deepcopy(reg), Path(td))
    assert soul.read_bytes() == before


def test_cli_check_returns_zero():
    assert render_rules.main(["--check", "--quiet", "--no-evidence"]) == 0
