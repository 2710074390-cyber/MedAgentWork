import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_evidence_bundle.py"


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    (root / "extracted").mkdir()
    text = b"The supported quotation is here."
    (root / "extracted" / "source.txt").write_bytes(text)
    manifest = {"schema_version": "1", "batch": "batch1", "status": "draft", "sources_file": "sources.jsonl", "claims_file": "claims.jsonl", "conflicts_file": "conflicts.json", "created_at": "2026-01-01", "enabled_for_generation": False}
    source = {"source_id": "s1", "source_type": "guideline", "publisher": "publisher", "title": "title", "url": "https://example.org", "accessed_at": "2026-01-01", "status": "available", "extracted_path": "extracted/source.txt", "extracted_sha256": hashlib.sha256(text).hexdigest()}
    claim = {"claim_id": "c1", "batch": "batch1", "claim": "claim", "source_ids": ["s1"], "support_quote": "supported quotation", "support_scope": "scope", "evidence_level": "level", "conflict_status": "none", "review_status": "reviewed", "risk_level": "high"}
    def save():
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (root / "sources.jsonl").write_text(json.dumps(source) + "\n", encoding="utf-8")
        (root / "claims.jsonl").write_text(json.dumps(claim) + "\n", encoding="utf-8")
        (root / "conflicts.json").write_text("[]", encoding="utf-8")
    save()
    return root, manifest, source, claim, save


def run(root, out):
    result = subprocess.run([sys.executable, str(SCRIPT), "--batch", "batch1", "--evidence-dir", str(root), "--out", str(out)], capture_output=True, text=True)
    return result, json.loads(out.read_text(encoding="utf-8"))


def test_pass_and_fingerprint(bundle, tmp_path):
    root, _, _, _, _ = bundle
    result, report = run(root, tmp_path / "report.json")
    assert result.returncode == 0 and report["status"] == "PASS"
    assert set(report["files"]) == {"manifest.json", "sources.jsonl", "claims.jsonl", "conflicts.json", "extracted/source.txt"}
    assert len(report["bundle_sha256"]) == 64
    (root / "extracted/source.txt").write_text("modified", encoding="utf-8")
    _, changed = run(root, tmp_path / "report.json")
    assert changed["status"] == "BLOCKED" and changed["bundle_sha256"] != report["bundle_sha256"]
    assert "HASH_MISMATCH" in {i["code"] for i in changed["issues"]}


@pytest.mark.parametrize("change,code", [
    ("batch", "BATCH_MISMATCH"), ("duplicate_source", "DUPLICATE_SOURCE_ID"),
    ("duplicate_claim", "DUPLICATE_CLAIM_ID"), ("missing_source", "UNKNOWN_SOURCE_ID"),
    ("claim_batch", "BATCH_MISMATCH"), ("quote", "QUOTE_NOT_FOUND"),
    ("empty_quote", "MISSING_FIELD"), ("traversal", "UNSAFE_PATH"),
    ("absolute", "UNSAFE_PATH"), ("missing_file", "FILE_MISSING"),
    ("conflict", "UNRESOLVED_CONFLICT"), ("metadata", "MISSING_FIELD"),
])
def test_invalid(bundle, tmp_path, change, code):
    root, manifest, source, claim, save = bundle
    if change == "batch": manifest["batch"] = "other"
    if change == "missing_source": claim["source_ids"] = ["absent"]
    if change == "claim_batch": claim["batch"] = "other"
    if change == "quote": claim["support_quote"] = "not present"
    if change == "empty_quote": claim["support_quote"] = ""
    if change == "traversal": source["extracted_path"] = "../outside"
    if change == "absolute": source["extracted_path"] = str((tmp_path / "outside").resolve())
    if change == "missing_file": source["extracted_path"] = "missing"
    if change == "metadata": source.pop("publisher")
    save()
    if change == "duplicate_source":
        with (root / "sources.jsonl").open("a", encoding="utf-8") as f: f.write(json.dumps(source) + "\n")
    if change == "duplicate_claim":
        with (root / "claims.jsonl").open("a", encoding="utf-8") as f: f.write(json.dumps(claim) + "\n")
    if change == "conflict": (root / "conflicts.json").write_text(json.dumps([{"claim_id": "c1", "status": "unresolved"}]), encoding="utf-8")
    result, report = run(root, tmp_path / "report.json")
    assert result.returncode == 1 and report["status"] == "BLOCKED"
    assert code in {i["code"] for i in report["issues"]}


def test_empty_and_enabled(bundle, tmp_path):
    root, manifest, _, _, save = bundle
    (root / "sources.jsonl").write_text("", encoding="utf-8")
    (root / "claims.jsonl").write_text("", encoding="utf-8")
    assert run(root, tmp_path / "report.json")[1]["status"] == "SKIPPED_NOT_ENABLED"
    manifest["enabled_for_generation"] = True
    save()
    (root / "sources.jsonl").write_text("", encoding="utf-8")
    (root / "claims.jsonl").write_text("", encoding="utf-8")
    assert run(root, tmp_path / "report.json")[1]["status"] == "BLOCKED"


def test_warn_and_read_only(bundle, tmp_path):
    root, _, _, claim, save = bundle
    claim["risk_level"] = "low"
    claim["conflict_status"] = "unresolved"
    save()
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    sentinel = tmp_path / "workflow_state.json"
    sentinel.write_text("untouched", encoding="utf-8")
    _, report = run(root, tmp_path / "report.json")
    assert report["status"] == "WARN"
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert sentinel.read_text(encoding="utf-8") == "untouched"
