# -*- coding: utf-8 -*-
"""HC-25 全流程质量门禁测试。"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
import quality_gate as qg  # noqa: E402


def test_release_adaptive_profile_is_explicit_and_enforce(monkeypatch):
    policy = qg._load_policy(BASE / "scripts" / "quality_policy.json")
    assert "release_adaptive" in policy["profiles"]
    assert "adaptive_coverage" in policy["profiles"]["release_adaptive"]["required_checks"]
    assert "adaptive_manual_review" in policy["profiles"]["release_adaptive"]["required_checks"]
    args = SimpleNamespace(batch="batch045", stage="r3", profile="release_adaptive",
                           with_tests=False, source_text=[], human_review="")
    with patch.object(qg, "infer_batch_products", return_value={"review_material"}), \
         patch.object(qg, "check_adaptive_coverage", return_value=qg.check_item("coverage", "PASS", "ok")) as coverage, \
         patch.object(qg, "check_adaptive_manual_review", return_value=qg.check_item("review", "PASS", "ok")) as review, \
         patch.object(qg, "check_review_items", return_value=qg.check_item("optional", "SKIP", "", required=False)):
        checks = qg.build_stage_checks(args, policy["profiles"]["release_adaptive"], "enforce")
    assert coverage.call_count == 1 and review.call_count == 1
    assert {item["id"] for item in checks} >= {"coverage", "review"}


def test_adaptive_coverage_requires_actual_pass_and_source(tmp_path):
    keypoints = tmp_path / "keypoints.md"
    review = tmp_path / "review.md"
    source = tmp_path / "source.md"
    for path in (keypoints, review, source):
        path.write_text("content", encoding="utf-8")
    args = SimpleNamespace(keypoints=str(keypoints), review=str(review), source_text=[str(source)])
    failed = {"returncode": 0, "stdout": "header\n{\"verdict\": \"FAIL\", \"errors\": [\"bad\"]}", "stderr": ""}
    with patch.object(qg, "run_cmd", return_value=failed):
        result = qg.check_adaptive_coverage(args, {})
    assert result["status"] == "FAIL"
    assert "预检 FAIL" in result["reason"] or "不可验证" in result["reason"]
    args.source_text = []
    result = qg.check_adaptive_coverage(args, {})
    assert result["status"] == "FAIL"


def test_adaptive_manual_review_requires_bound_nonempty_evidence(tmp_path):
    review = tmp_path / "review.md"
    keypoints = tmp_path / "keypoints.md"
    source = tmp_path / "source.md"
    review.write_text("review", encoding="utf-8")
    keypoints.write_text("keypoints", encoding="utf-8")
    source.write_text("source", encoding="utf-8")
    evidence_path = tmp_path / "human_review.json"
    args = SimpleNamespace(batch="batch045", review=str(review), keypoints=str(keypoints),
                           source_text=[str(source)], human_review=str(evidence_path))
    evidence = {
        "batch": "batch045",
        "review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
        "keypoints_sha256": hashlib.sha256(keypoints.read_bytes()).hexdigest(),
        "status": "APPROVED", "reviewer": "reviewer-1", "decision": "PASS",
        "evidence": "逐条核验记录",
        "reviewed_at": "2026-11-01T10:00:00+08:00",
        "source_paths": [str(source.resolve())],
        "source_sha256": {str(source.resolve()): hashlib.sha256(source.read_bytes()).hexdigest()},
    }
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    assert qg.check_adaptive_manual_review(args)["status"] == "PASS"
    for key in ("batch", "review_sha256", "keypoints_sha256", "status", "reviewer", "decision", "evidence", "reviewed_at"):
        original = evidence[key]
        evidence[key] = "" if isinstance(original, str) else "wrong"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        assert qg.check_adaptive_manual_review(args)["status"] == "FAIL"
        evidence[key] = original
    evidence["review_sha256"] = "stale"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    assert qg.check_adaptive_manual_review(args)["status"] == "FAIL"


def test_adaptive_manual_review_missing_evidence_blocks_even_advisory(tmp_path):
    args = SimpleNamespace(batch="batch045", review=str(tmp_path / "review.md"),
                           keypoints=str(tmp_path / "keypoints.md"), human_review="")
    assert qg.check_adaptive_manual_review(args)["status"] == "FAIL"
    assert qg.aggregate([qg.check_adaptive_manual_review(args)], "advisory")[0] == "WARN"


def test_strict_defaults_final_report_and_batch_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(qg, 'BASE', tmp_path)
    args = SimpleNamespace(batch='batch045', questions=str(qg.DEFAULT_QUESTIONS),
        learning_value=str(qg.DEFAULT_LEARNING_VALUE), kc=str(qg.DEFAULT_KC),
        baseline=str(qg.DEFAULT_BASELINE), rubric=str(qg.DEFAULT_RUBRIC),
        keypoints=str(qg.DEFAULT_KEYPOINTS), blueprint=str(qg.DEFAULT_BLUEPRINT),
        subject='ent', scorecard=str(qg.DEFAULT_SCORECARD), review=str(qg.DEFAULT_REVIEW))
    qg.derive_batch_defaults(args)
    assert args.learning_value.endswith('learning_value_batch045_final.json')
    assert 'batch045' in args.keypoints and 'batch045' in args.blueprint
    assert 'batch040' not in args.keypoints and 'batch040' not in args.blueprint


def test_release_hc27_scoped_to_question_bank():
    args = SimpleNamespace(batch='batch045', stage='r3', profile='release_teaching_plan', with_tests=False)
    profile = {'required_checks': []}
    with patch.object(qg, 'check_review_items', return_value=qg.check_item('optional', 'SKIP', '', required=False)), \
         patch.object(qg, 'check_source_concepts', return_value=qg.check_item('r2.source_concepts', 'PASS', '')) as hc27:
        with patch.object(qg, 'infer_batch_products', return_value={'question_bank'}):
            qg.build_stage_checks(args, profile, 'enforce')
            assert hc27.call_count == 1
        with patch.object(qg, 'infer_batch_products', return_value={'review_material'}):
            qg.build_stage_checks(args, profile, 'enforce')
            assert hc27.call_count == 1


def test_strict_boundary_matches_gate_check():
    import gate_check
    for batch in ("batch043", "batch044", "batch045", "batch045-A", "custom"):
        for mode in (None, "legacy", "strict", "invalid"):
            state = {"evidence_binding_mode": mode}
            with patch.object(qg, "_batch_state", return_value=state):
                assert qg._strict_batch(batch) == gate_check._is_strict_batch(batch, state)


def test_strict_generates_bound_learning_report(tmp_path):
    questions = tmp_path / "questions.json"
    report = tmp_path / "report.json"
    questions.write_text('[{}]', encoding="utf-8")
    args = SimpleNamespace(batch="batch045", questions=str(questions), learning_value=str(report))
    profile = {"thresholds": {"source_quote_exact_min": .95, "anchor_verified_block": .8, "anchor_verified_warn": .9}}
    result = qg.check_item_learning_value(args, profile, "enforce")
    assert result["status"] == "FAIL"
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["batch"] == "batch045"
    assert data["input_sha256"] == hashlib.sha256(questions.read_bytes()).hexdigest()


def test_required_review_detail_skip_blocks(tmp_path):
    review = tmp_path / "review.md"
    review.write_text("no cards", encoding="utf-8")
    args = SimpleNamespace(review=str(review), batch="batch045", profile="pilot")
    def skip(cmd):
        out = Path(cmd[cmd.index("--json-out") + 1])
        out.write_text(json.dumps({"summary": {"status": "SKIP"}}), encoding="utf-8")
        return {"returncode": 0}
    with patch.object(qg, "run_cmd", skip):
        result = qg.check_review_detail(args, {}, "enforce")
    assert result["status"] == "FAIL" and result["required"]
    assert qg.aggregate([result], "enforce")[0] == "BLOCKED"


def test_r3_rejects_pilot(tmp_path):
    argv = ["quality_gate.py", "--stage", "r3", "--profile", "pilot", "--out", str(tmp_path / "out.json")]
    with patch.object(sys, "argv", argv), patch.object(qg, "_configure_stdio"):
        assert qg.main() == 2
    assert not (tmp_path / "out.json").exists()


def test_new_batch_report_binding():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        questions, review = root / "questions.json", root / "review.md"
        lv, score = root / "lv.json", root / "score.json"
        questions.write_text('[{}]', encoding="utf-8")
        review.write_text('review', encoding="utf-8")
        kc, rubric, keypoints = root / "kc.json", root / "rubric.json", root / "keypoints.md"
        keypoints.write_text("keypoints", encoding="utf-8")
        kc.write_text(json.dumps({"metadata": {"keypoints_path": str(keypoints)}}), encoding="utf-8")
        rubric.write_text("{}", encoding="utf-8")
        args = SimpleNamespace(batch="batch045", subject="test", questions=str(questions), review=str(review),
                               learning_value=str(lv), scorecard=str(score), kc=str(kc), rubric=str(rubric))
        profile = {"thresholds": {"source_quote_exact_min": 0.9, "anchor_verified_block": 0.8,
                                  "anchor_verified_warn": 0.9, "critical_dim_min": 3,
                                  "scorecard_overall_enforce": 4, "scorecard_overall_advisory": 4}}
        assert qg.check_item_learning_value(args, profile, "enforce")["status"] == "FAIL"
        assert qg.check_scorecard(args, profile, "enforce")["status"] == "FAIL"
        summary = {"fail": 0, "per_option_coverage": 1, "misconception_coverage": 1,
                   "source_quote_exact_rate": 1, "anchor_verified_rate": 1}
        lv_data = {"batch": args.batch, "input_sha256": hashlib.sha256(questions.read_bytes()).hexdigest(), "summary": summary}
        score_data = {"batch": args.batch, "review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
                      "overall": 5, "dimensions": []}
        lv.write_text(json.dumps(lv_data), encoding="utf-8")
        import review_scorecard as producer
        score_data["input_hashes"] = producer.scorecard_inputs(review, rubric, kc, lv)
        score.write_text(json.dumps(score_data), encoding="utf-8")
        assert qg.check_item_learning_value(args, profile, "enforce")["status"] == "PASS"
        assert qg.check_scorecard(args, profile, "enforce")["status"] == "PASS"
        for path in (kc, rubric, keypoints, lv):
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            assert qg.check_scorecard(args, profile, "enforce")["status"] == "FAIL"
            path.write_bytes(original)
        for optional in (root / "kc_question_map.jsonl", root / "kc_aliases.json", root / "new.html"):
            optional.write_text("{}", encoding="utf-8")
            assert qg.check_scorecard(args, profile, "enforce")["status"] == "FAIL"
            optional.unlink()
        score_data["batch"] = "batch046"
        score.write_text(json.dumps(score_data), encoding="utf-8")
        assert qg.check_scorecard(args, profile, "enforce")["status"] == "FAIL"
        score_data["batch"] = "batch045"
        score.write_text(json.dumps(score_data), encoding="utf-8")
        questions.write_text('[{"changed":true}]', encoding="utf-8")
        review.write_text('changed', encoding="utf-8")
        assert qg.check_item_learning_value(args, profile, "enforce")["status"] == "FAIL"
        assert qg.check_scorecard(args, profile, "enforce")["status"] == "FAIL"
        args.batch = "batch043"
        assert qg.check_item_learning_value(args, profile, "enforce")["status"] == "PASS"
        assert qg.check_scorecard(args, profile, "enforce")["status"] == "PASS"
        args.batch = "batch045"
        review.unlink()
        with patch.object(qg, "infer_batch_products", return_value={"review_material"}):
            assert qg.check_scorecard(args, profile, "enforce")["status"] == "FAIL"


def test_report_producers_record_hashes():
    import review_scorecard as producer
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        questions = root / "questions.json"
        report = root / "lv.json"
        questions.write_text('[{}]', encoding="utf-8")
        proc = subprocess.run([sys.executable, str(BASE / "scripts/check_learning_value.py"),
                               "--file", str(questions), "--batch", "batch045", "--out", str(report)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert proc.returncode in (0, 1), proc.stderr
        data = json.loads(report.read_text(encoding="utf-8"))
        assert data["batch"] == "batch045"
        assert data["input_sha256"] == hashlib.sha256(questions.read_bytes()).hexdigest()
        inferred = root / "learning_value_batch045.json"
        proc = subprocess.run([sys.executable, str(BASE / "scripts/check_learning_value.py"),
                               "--file", str(questions), "--out", str(inferred)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert proc.returncode in (0, 1), proc.stderr
        assert json.loads(inferred.read_text(encoding="utf-8"))["batch"] == "batch045"
        review = root / "review.md"
        review.write_text("review", encoding="utf-8")
        keypoints = root / "keypoints.md"
        keypoints.write_text("keypoints", encoding="utf-8")
        kc = root / "kc"
        kc.write_text(json.dumps({"metadata": {"keypoints_path": str(keypoints)}}), encoding="utf-8")
        rubric_path = root / "rubric"
        rubric_path.write_text("{}", encoding="utf-8")
        rubric = {"dimensions": [], "reviewers": []}
        metrics = {key: {"status": "unknown"} for key in
                   ("schedule_coverage", "feedback_coverage", "diagnostic_available", "learner_outcome_available")}
        with patch.object(producer, "load_rubric", return_value=rubric), \
             patch.object(producer, "compute_metrics", return_value=metrics):
            card = producer.build_scorecard("x", "batch045", review, root / "rubric", root / "kc", report)
        assert card["batch"] == "batch045"
        assert card["review_sha256"] == hashlib.sha256(review.read_bytes()).hexdigest()


def test_source_report_freshness_and_binding():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "questions.json"
        path.write_text('[{"schema_version":"2.0"}]', encoding="utf-8")
        args = SimpleNamespace(questions=str(path), batch="batch043", stage="r2")
        assert qg.check_source_concepts(args)["status"] == "SKIP"
        args.questions = str(path.with_name("missing.json"))
        assert qg.check_source_concepts(args)["status"] == "FAIL"
        args.questions = str(path)
        def stale(cmd):
            out = Path(cmd[cmd.index("--out") + 1])
            out.write_text(json.dumps({"status": "PASS", "batch": "batch043", "input_sha256": "old"}), encoding="utf-8")
            return {"returncode": 0}
        with patch.object(qg, "run_cmd", stale):
            assert qg.check_source_concepts(args)["status"] == "FAIL"
        with patch.object(qg, "run_cmd", return_value={"returncode": 0}):
            assert qg.check_source_concepts(args)["status"] == "FAIL"


def test_review_detail_subprocess_failure():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "review.md"
        path.write_text("test", encoding="utf-8")
        args = SimpleNamespace(review=str(path), batch="batch040", stage="r2", profile="pilot")
        with patch.object(qg, "run_cmd", return_value={"returncode": 2}):
            assert qg.check_review_detail(args, {}, "enforce")["status"] == "FAIL"


def test_release_forces_enforce():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "report.json"
        questions = Path(td) / "questions.json"
        review = Path(td) / "review.md"
        questions.write_text("[]", encoding="utf-8")
        review.write_text("review", encoding="utf-8")
        argv = ["quality_gate.py", "--stage", "r3", "--batch", "batch045",
                "--questions", str(questions), "--review", str(review),
                "--mode", "advisory", "--out", str(out)]
        failed = [qg.check_item("test", "FAIL", "failed")]
        with patch.object(sys, "argv", argv), patch.object(qg, "_configure_stdio"), \
             patch.object(qg, "_load_policy", return_value={"profiles": {"release_teacher_keypoint": {}}}), \
             patch.object(qg, "derive_batch_defaults"), \
             patch.object(qg, "build_stage_checks", return_value=failed) as build:
            assert qg.main() == 1
            assert build.call_args.args[2] == "enforce"
        result = json.loads(out.read_text(encoding="utf-8"))
        assert result["mode"] == "enforce"
        assert result["input_sha256"] == {"questions": hashlib.sha256(questions.read_bytes()).hexdigest(),
                                          "review": hashlib.sha256(review.read_bytes()).hexdigest()}


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
