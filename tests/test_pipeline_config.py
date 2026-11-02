"""pipeline_config 配置单一事实来源的回归测试（P1-S3）。

运行: python scripts/run_tests.py test_pipeline_config
或:   python -m pytest tests/test_pipeline_config.py -q
"""
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
for p in (str(BASE), str(BASE / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pipeline_config as pc  # noqa: E402


def test_points_at_scripts_pipeline_yaml():
    """配置必须指向真实存在的那份文件（P1-S3 前指向仓库根，文件不存在）。"""
    assert pc.PIPELINE_YAML.name == "pipeline.yaml"
    assert pc.PIPELINE_YAML.parent.name == "scripts"
    assert pc.PIPELINE_YAML.exists(), f"配置文件不存在: {pc.PIPELINE_YAML}"


def test_yaml_thresholds_match_defaults():
    """落地时 thresholds 段取值必须等于内置默认 —— 保证行为零变化。"""
    import yaml  # PyYAML 为可选依赖；本机已具备

    doc = yaml.safe_load(pc.PIPELINE_YAML.read_text(encoding="utf-8"))
    section = doc.get("thresholds")
    assert isinstance(section, dict) and section, "pipeline.yaml 缺少顶层 thresholds 段"
    for k, v in section.items():
        if k in pc.DEFAULTS:
            assert pc.DEFAULTS[k] == v, f"{k}: yaml={v!r} != DEFAULTS={pc.DEFAULTS[k]!r}"


def test_effective_config_equals_defaults():
    cfg = pc.load_thresholds(force_reload=True)
    overridden = [k for k, v in cfg.items() if k in pc.DEFAULTS and v != pc.DEFAULTS[k]]
    assert not overridden, f"落地后出现非预期覆盖: {overridden}"


def test_option_length_two_scopes_are_distinct():
    """校验上限 20 与生成目标 18 是两个口径，不得合并。"""
    assert pc.get_threshold("option_length_max") == 20
    assert pc.get_threshold("option_length_target") == 18


def test_config_hash_stable_and_changes_with_value():
    h1 = pc.config_hash(force_reload=True)
    h2 = pc.config_hash(force_reload=True)
    assert h1 == h2 and len(h1) == 64
    # 用 DEFAULTS 的深拷贝模拟一次取值变更，验证指纹确实随值变化
    import copy

    saved = copy.deepcopy(pc.DEFAULTS)
    try:
        pc._cache = None
        cfg = dict(saved)
        cfg["bloom_deviation_max"] = 99
        pc._cache = cfg
        assert pc.config_hash() != h1
    finally:
        pc._cache = None
        pc.DEFAULTS.clear()
        pc.DEFAULTS.update(saved)


def test_file_sha256_reflects_missing_file():
    assert pc.file_sha256(BASE / "no_such_config_xyz.yaml") == ""
    assert len(pc.file_sha256()) == 64


def test_snapshot_shape():
    snap = pc.snapshot()
    for key in ("config_path", "config_exists", "config_file_sha256",
                "config_hash", "effective", "defaults", "overridden_keys"):
        assert key in snap
    assert snap["config_exists"] is True
    assert isinstance(snap["effective"], dict) and snap["effective"]


def test_print_config_json(tmpdir=None):
    d = tempfile.mkdtemp()
    out = Path(d) / "nested" / "config_snapshot.json"
    assert pc.main(["--print-config", "--quiet", "--json", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["config_hash"] and data["config_exists"] is True
    assert "r2_ratio_fail" in data["effective"]


def test_key_query():
    assert pc.main(["--key", "option_length_max", "--quiet"]) == 0


def test_check_mode_passes():
    assert pc.main(["--check", "--quiet"]) == 0


def test_missing_config_is_reported(tmp_path=None):
    """配置缺失必须显式报错（返回 2），不得静默走默认值。"""
    saved = pc.PIPELINE_YAML
    try:
        pc.PIPELINE_YAML = BASE / "no_such_pipeline.yaml"
        assert pc.main(["--check", "--quiet"]) == 2
    finally:
        pc.PIPELINE_YAML = saved
