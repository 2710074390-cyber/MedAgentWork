# -*- coding: utf-8 -*-
"""HC-27 概念标注契约测试：schema 条件必填、生成期门禁规则、源标注解析。

项目 runner（scripts/run_tests.py）直接调用无参测试函数，因此不用 pytest fixture。
"""
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))

import check_source_concepts as csc  # noqa: E402
import label_concepts as lc  # noqa: E402


def _q(**kw):
    d = {"stem": "x", "options": {"A": "a", "B": "b"}, "answer": "A"}
    d.update(kw)
    return d


def _c(role, kp, title, ev="题干直接问到这个概念"):
    return {"role": role, "keypoint": kp, "title": title, "evidence": ev}


def test_schema_requires_concepts_only_for_21():
    """2.1 必须有 concepts；A2+ 至少 2 条；2.0 老契约不受影响。"""
    try:
        import jsonschema
    except ImportError:
        return  # 本机默认解释器可能没有，跳过而不是失败
    schema = json.loads((BASE / "schemas/agent2_output.schema.json").read_text(encoding="utf-8"))
    v = jsonschema.Draft7Validator(schema)

    legacy = [_q(schema_version="2.0", type="A2")]
    assert not list(v.iter_errors(legacy)), "旧版 2.0 不应因缺 concepts 而失败"

    ok_a1 = [_q(schema_version="2.1", type="A1", keypoint_ref="第1条",
                concepts=[_c("primary", "第1条", "甲概念")])]
    assert not list(v.iter_errors(ok_a1)), "2.1 的 A1 单概念应通过"

    bad_a2 = [_q(schema_version="2.1", type="A2", keypoint_ref="第1条",
                 concepts=[_c("primary", "第1条", "甲概念")])]
    assert list(v.iter_errors(bad_a2)), "2.1 的 A2 单概念应被拦下"

    ok_a2 = [_q(schema_version="2.1", type="A2", keypoint_ref="第1条",
                concepts=[_c("primary", "第1条", "甲概念"), _c("differential", "第2条", "乙概念")])]
    assert not list(v.iter_errors(ok_a2)), "2.1 的 A2 双概念应通过"

    missing = [_q(schema_version="2.1", type="A1", keypoint_ref="第1条")]
    assert list(v.iter_errors(missing)), "2.1 缺 concepts 应被拦下"


def test_source_concept_rules():
    """S1–S6 每条规则都要能被触发。"""
    good = _q(schema_version="2.1", type="A2", keypoint_ref="第1条",
              concepts=[_c("primary", "第1条", "甲概念"), _c("differential", "第2条", "乙概念")])
    assert csc.check_question(good) == ([], []), "合规题不应报错"

    fails, _ = csc.check_question(_q(type="A2", keypoint_ref="第1条",
                                     concepts=[_c("primary", "第1条", "甲概念")]))
    assert any("S3" in f for f in fails), "A2 单概念应触发 S3"

    fails, _ = csc.check_question(_q(type="A1", keypoint_ref="第1条",
                                     concepts=[_c("primary", "第9条", "甲概念")]))
    assert any("S5" in f for f in fails), "锚点不一致应触发 S5"

    fails, _ = csc.check_question(_q(type="A1", keypoint_ref="第1条",
                                     concepts=[_c("primary", "第1条", "甲概念", ev="相关")]))
    assert any("S4" in f for f in fails), "证据过短应触发 S4"

    fails, _ = csc.check_question(_q(type="A1", keypoint_ref="第1条",
                                     concepts=[_c("primary", "第1条", "同名"), _c("related", "第2条", "同名")]))
    assert any("S6" in f for f in fails), "标题重复应触发 S6"

    fails, _ = csc.check_question(_q(type="A1", keypoint_ref="第1条",
                                     concepts=[_c("primary", "第1条", "甲"), _c("primary", "第2条", "乙")]))
    assert any("S2" in f for f in fails), "两个 primary 应触发 S2"

    fails, _ = csc.check_question(_q(type="A1"))
    assert any("S1" in f for f in fails), "缺 concepts 应触发 S1"


def test_batch_gate_skip_and_enforce():
    """旧批次 SKIP、新批次 FAIL、声明 2.1 后按规则判。"""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        legacy = tmp / "legacy.json"
        legacy.write_text(json.dumps([_q(schema_version="2.0", type="A1")], ensure_ascii=False),
                          encoding="utf-8")
        out = tmp / "r.json"
        code = csc.main(["--file", str(legacy), "--batch", "batch043", "--out", str(out)])
        assert code == 2, "旧批次应 SKIP（退出码 2）"
        assert json.loads(out.read_text(encoding="utf-8"))["status"] == "SKIP"

        code = csc.main(["--file", str(legacy), "--batch", "batch044", "--out", str(out)])
        assert code == 1, "新批次无 2.1 应 FAIL"
        assert json.loads(out.read_text(encoding="utf-8"))["status"] == "FAIL"

        fresh = tmp / "fresh.json"
        fresh.write_text(json.dumps([_q(schema_version="2.1", type="A1", keypoint_ref="第1条",
                                       concepts=[_c("primary", "第1条", "甲概念")])],
                                    ensure_ascii=False), encoding="utf-8")
        code = csc.main(["--file", str(fresh), "--batch", "batch044", "--out", str(out)])
        assert code == 0, "合规 2.1 批次应通过"
        assert json.loads(out.read_text(encoding="utf-8"))["status"] == "PASS"


def test_label_from_source_resolution():
    """源标注要能解析到 kc_id，并保留 role 与证据。"""
    titles = {
        "T:K-M01-001": ("急诊五级分诊", "急诊五级分诊"),
        "T:K-M01-004": ("灾难检伤分类与四色标签", "灾难检伤分类与四色标签"),
    }
    kp_owner = {2: ["T:K-M01-001"], 3: ["T:K-M01-004"]}
    q = {
        "id": "T-M01-A2-001", "type": "A2",
        "concepts": [_c("primary", "第2条", "急诊五级分诊", ev="题干问Ⅱ类时限"),
                     _c("differential", "第3条", "灾难检伤分类与四色标签", ev="C 项套用Ⅲ类时限")],
    }
    row = lc.label_from_source(q, "T", titles, kp_owner, q["concepts"], 2)
    assert row["source"] == "declared"
    assert row["primary"] == "T:K-M01-001", row
    assert len(row["secondary"]) == 1
    assert row["secondary"][0]["kc_id"] == "T:K-M01-004"
    assert row["secondary"][0]["role"] == "differential"
    assert row["secondary"][0]["evidence"].startswith("HC-27 源标注")
    assert not row["needs_manual"]

    # 同一锚点挂多张卡：按标题重叠挑最像的那张
    titles2 = dict(titles)
    titles2["T:K-M01-005"] = ("急诊分诊流程", "急诊分诊流程")
    kp_owner2 = {2: ["T:K-M01-001", "T:K-M01-005"]}
    q2 = {"id": "T-M01-A1-009", "type": "A1",
          "concepts": [_c("primary", "第2条", "急诊五级分诊")]}
    row2 = lc.label_from_source(q2, "T", titles2, kp_owner2, q2["concepts"], 2)
    assert row2["primary"] == "T:K-M01-001", row2

    # 解析不到要进 unresolved，而不是静默丢弃
    q3 = {"id": "T-M01-A1-010", "type": "A1",
          "concepts": [_c("primary", "第99条", "图谱里没有的概念")]}
    row3 = lc.label_from_source(q3, "T", titles, kp_owner, q3["concepts"], 2)
    assert row3["primary"] is None
    assert row3["unresolved"] == ["图谱里没有的概念"]
    assert row3["needs_manual"]
