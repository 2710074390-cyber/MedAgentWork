"""Validate an independent, read-only evidence bundle."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_bundle(batch, evidence_dir):
    root = Path(evidence_dir).resolve()
    issues, files, fingerprint = [], {}, {}

    def issue(code, message, severity="BLOCKED"):
        issues.append({"code": code, "severity": severity, "message": message})

    def safe_file(name):
        if not isinstance(name, str) or not name or "\\" in name or PureWindowsPath(name).is_absolute() or PureWindowsPath(name).drive or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
            issue("UNSAFE_PATH", str(name))
            return None
        path = root / name
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except (ValueError, OSError, RuntimeError):
            issue("UNSAFE_PATH", name)
            return None
        if not path.is_file():
            issue("FILE_MISSING", name)
            return None
        try:
            digest = sha256_file(path)
        except OSError as exc:
            issue("FILE_UNREADABLE", f"{name}: {exc}")
            return None
        files[relative] = digest
        fingerprint[relative] = digest
        return path

    def load(path, jsonl=False):
        if path is None:
            return None
        try:
            return read_jsonl(path) if jsonl else read_json(path)
        except (OSError, UnicodeError, ValueError) as exc:
            issue("INVALID_JSON", f"{path.name}: {exc}")
            return None

    def required(obj, fields, label):
        if not isinstance(obj, dict):
            issue("INVALID_RECORD", label)
            return False
        valid = True
        for field in fields:
            value = obj.get(field)
            if not isinstance(value, str) or not value.strip():
                issue("MISSING_FIELD", f"{label}.{field}")
                valid = False
        return valid

    manifest_path = root / "manifest.json"
    if not manifest_path.exists() and (not root.exists() or (root.is_dir() and not any(root.iterdir()))):
        return {"batch": batch, "status": "SKIPPED_NOT_ENABLED", "issues": [], "files": {}, "bundle_sha256": None, "generated_at": datetime.now(timezone.utc).isoformat()}
    manifest = load(safe_file("manifest.json"))
    sources, claims, conflicts = [], [], []
    enabled = False
    if isinstance(manifest, dict):
        required(manifest, ("schema_version", "batch", "status", "sources_file", "claims_file", "conflicts_file", "created_at"), "manifest")
        if manifest.get("batch") != batch:
            issue("BATCH_MISMATCH", "manifest.batch")
        enabled = manifest.get("enabled_for_generation")
        if not isinstance(enabled, bool):
            issue("MISSING_FIELD", "manifest.enabled_for_generation")
        canonical = {k: v for k, v in manifest.items() if k != "bundle_sha256"}
        if "manifest.json" in fingerprint:
            fingerprint["manifest.json"] = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        for field, kind in (("sources_file", "sources"), ("claims_file", "claims"), ("conflicts_file", "conflicts")):
            if not isinstance(manifest.get(field), str) or not manifest[field].strip():
                continue
            value = load(safe_file(manifest[field]), kind != "conflicts")
            if value is not None and not isinstance(value, list):
                issue("INVALID_RECORD", field)
                value = None
            if kind == "sources": sources = value or []
            elif kind == "claims": claims = value or []
            else: conflicts = value or []
    elif manifest is not None:
        issue("INVALID_RECORD", "manifest")

    source_map, extracted = {}, {}
    for index, source in enumerate(sources):
        label = f"sources[{index}]"
        required(source, ("source_id", "source_type", "publisher", "title", "url", "accessed_at", "status"), label)
        if not isinstance(source, dict): continue
        sid = source.get("source_id")
        if isinstance(sid, str) and sid:
            if sid in source_map: issue("DUPLICATE_SOURCE_ID", sid)
            else: source_map[sid] = source
        for key in ("snapshot", "extracted"):
            path_key, hash_key = key + "_path", key + "_sha256"
            if path_key not in source and hash_key not in source: continue
            expected = source.get(hash_key)
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
                issue("MISSING_HASH", f"{label}.{hash_key}")
            path = safe_file(source.get(path_key))
            if path is not None:
                if isinstance(expected, str) and sha256_file(path) != expected.lower(): issue("HASH_MISMATCH", str(source.get(path_key)))
                if key == "extracted" and isinstance(sid, str):
                    try: extracted[sid] = path.read_text(encoding="utf-8")
                    except (OSError, UnicodeError): issue("INVALID_TEXT", str(source.get(path_key)))

    claim_map = {}
    for index, claim in enumerate(claims):
        label = f"claims[{index}]"
        required(claim, ("claim_id", "batch", "claim", "support_quote", "support_scope", "evidence_level", "conflict_status", "review_status"), label)
        if not isinstance(claim, dict): continue
        cid = claim.get("claim_id")
        if isinstance(cid, str) and cid:
            if cid in claim_map: issue("DUPLICATE_CLAIM_ID", cid)
            else: claim_map[cid] = claim
        if claim.get("batch") != batch: issue("BATCH_MISMATCH", label)
        refs = claim.get("source_ids")
        if not isinstance(refs, list) or not refs or any(not isinstance(x, str) or not x.strip() for x in refs):
            issue("INVALID_SOURCE_IDS", label)
            refs = []
        for ref in refs:
            if ref not in source_map: issue("UNKNOWN_SOURCE_ID", f"{label}: {ref}")
        quote = claim.get("support_quote")
        if isinstance(quote, str) and quote.strip() and refs and not any(ref in extracted and quote in extracted[ref] for ref in refs):
            issue("QUOTE_NOT_FOUND", label)
        if claim.get("review_status") not in ("reviewed", "approved", "resolved"):
            issue("REVIEW_PENDING", label, "WARN")
        if claim.get("conflict_status") not in ("none", "resolved"):
            severity = "WARN" if claim.get("risk_level") == "low" else "BLOCKED"
            issue("UNRESOLVED_CONFLICT", label, severity)

    for index, conflict in enumerate(conflicts):
        label = f"conflicts[{index}]"
        if not isinstance(conflict, dict) or not isinstance(conflict.get("claim_id"), str) or not isinstance(conflict.get("status"), str) or not conflict.get("status"):
            issue("INVALID_CONFLICT", label)
            continue
        cid = conflict["claim_id"]
        claim = claim_map.get(cid)
        if claim is None:
            issue("UNKNOWN_CLAIM_ID", label)
            continue
        if conflict["status"] != "resolved":
            severity = "WARN" if claim.get("risk_level") == "low" else "BLOCKED"
            issue("UNRESOLVED_CONFLICT", label, severity)
            if claim.get("conflict_status") == "resolved": issue("CONFLICT_STATUS_MISMATCH", label)
        elif claim.get("conflict_status") not in ("resolved", "none"):
            issue("CONFLICT_STATUS_MISMATCH", label)

    bundle_hash = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest() if fingerprint else None
    if isinstance(manifest, dict) and "bundle_sha256" in manifest and manifest["bundle_sha256"] != bundle_hash:
        issue("BUNDLE_HASH_MISMATCH", "manifest.bundle_sha256")
    if enabled is True and (not sources or not claims): issue("EMPTY_ENABLED_BUNDLE", "enabled bundle requires sources and claims")
    if bool(sources) != bool(claims): issue("INCOMPLETE_BUNDLE", "sources and claims must both be present")
    if any(item["severity"] == "BLOCKED" for item in issues): status = "BLOCKED"
    elif not sources and not claims and enabled is False: status = "SKIPPED_NOT_ENABLED"
    elif issues: status = "WARN"
    else: status = "PASS"
    return {"batch": batch, "status": status, "issues": issues, "files": dict(sorted(files.items())), "bundle_sha256": bundle_hash, "generated_at": datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root, out = Path(args.evidence_dir).resolve(), Path(args.out).resolve()
    if out == root or root in out.parents:
        parser.error("--out must be outside the evidence directory")
    report = validate_bundle(args.batch, root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
