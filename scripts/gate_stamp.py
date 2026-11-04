#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁回执（gate stamp）与批次回执链（ledger）—— SA-12 / P0。

要解决的问题
------------
门禁脚本只在「有人调用它」时生效。第三方 Agent（或换一个模型/换一个宿主）完全可以
跳过 a3 门禁直接写产物：本地没有消费方校验，事后也查不出来。

本模块提供「产物 ↔ 门禁执行」的绑定原语：
- 每个阶段 PASS 后写一条回执：产物字节 sha256 + 门禁证据 sha256 + 门禁清单；
- 回执用 chain_prev 链式相连，head 为最后一条；删一条、改一条、插一条都会断链。

回执长这样::

    最终产物/batch048/_gate_ledger.json
    {
      "schema_version": "1.0",
      "batch": "batch048",
      "created_at": "...",
      "head": "sha256:...",
      "stamps": [
        {"seq": 1, "stage": "a2", "verdict": "PASS", "provenance": "driver",
         "ts": "...", "driver_version": "batch_driver@2026-11-04",
         "artifacts": [{"path": "中间产物/batch048/ALL_questions.json",
                        "sha256": "...", "bytes": 123}],
         "gate_reports": [{"path": "reports/validate/...", "sha256": "..."}],
         "gates": ["GATE-A2"], "hash": "sha256:...", "chain_prev": null}
      ]
    }

职责边界（诚实声明，别指望它做不到的事）
----------------------------------------
1. 回执能证明「产物与一次门禁执行绑定」；**不能**证明「执行者不可伪造」——有 shell
   的 Agent 理论上能伪造回执。真正的兜底是 CI 重跑（`gate_audit.py --recheck`）。
2. `reports/` 被 .gitignore 忽略，所以 `gate_reports` 是**尽力证据**（存在才校验），
   `artifacts` 才是硬绑定。
3. 本模块不做判定、不跑门禁、不写 workflow_state；只负责「记录 + 验真」。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

SCHEMA_VERSION = "1.0"
LEDGER_NAME = "_gate_ledger.json"

# 回执从 batch048 起强制；更早的批次是「历史遗留」，audit 只告警不失败。
# 选 048 的理由：045-047 已签收（不可追溯修改），048 是本机制落地后的第一个批次。
STAMP_REQUIRED_MIN_BATCH = 48

STAGES = ("r0", "r1", "a2", "a3", "a4", "lv", "a5", "r2", "r3", "final", "r4")

# 阶段 → 该阶段「必须被回执覆盖」的交付物（相对仓库根，{batch} 占位）。
# 一个阶段多个候选时取「存在的第一个」；都不存在则由调用方显式传入。
_STAGE_ARTIFACTS = {
    "a2": ["中间产物/{batch}/ALL_questions.json"],
    "a3": ["质检报告/{batch}/A3_质检报告.json", "质检报告/{batch}_质检报告.json"],
    "a4": ["最终产物/{batch}/ALL_questions_FIXED.json",
           "最终产物/{batch}/ALL_questions_FIXED.md"],
    "lv": ["最终产物/{batch}/ALL_questions_FIXED.json"],
    "final": ["最终产物/{batch}/ALL_questions_FIXED.json"],
}

# 判定优先级：FAIL 优先于 WARN，WARN 优先于 PASS
FAIL_CODES = (
    "LEDGER_CORRUPT",
    "CHAIN_BROKEN",
    "SEQ_MISMATCH",
    "STAGE_MISSING",
    "ARTIFACT_MISSING",
    "ARTIFACT_MISMATCH",
    "ARTIFACT_NOT_COVERED",
    "LEDGER_MISSING",
)


def batch_number(batch_id: str):
    m = re.search(r"(\d{3})", str(batch_id or ""))
    return int(m.group(1)) if m else None


def ledger_path(batch_id: str, base: Path = BASE) -> Path:
    return Path(base) / "最终产物" / batch_id / LEDGER_NAME


def rel(path, base: Path = BASE) -> str:
    """尽量转成仓库相对路径（POSIX 分隔符）；不在仓库内则原样返回。"""
    p = Path(path)
    try:
        return p.resolve().relative_to(Path(base).resolve()).as_posix()
    except Exception:
        return p.as_posix()


def file_sha256(path) -> str | None:
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stamp_hash(stamp: dict) -> str:
    body = {k: v for k, v in stamp.items() if k != "hash"}
    return "sha256:" + hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def new_ledger(batch_id: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "batch": batch_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "head": None,
        "stamps": [],
    }


def load_ledger(batch_id: str, base: Path = BASE, path=None):
    """返回 (ledger, error)。文件不存在 → (None, None)；不可解析 → (None, 错误说明)。"""
    p = Path(path) if path else ledger_path(batch_id, base)
    if not p.exists():
        return None, None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"{p}: {type(exc).__name__}: {exc}"
    if not isinstance(data, dict) or not isinstance(data.get("stamps"), list):
        return None, f"{p}: 不是合法的回执链（缺少 stamps 数组）"
    return data, None


def write_ledger(ledger: dict, base: Path = BASE, path=None) -> str:
    p = Path(path) if path else ledger_path(ledger.get("batch", ""), base)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(p))
    return str(p)


def expected_artifacts(batch_id: str, stage: str, base: Path = BASE):
    """该阶段「应当被回执覆盖」的交付物（只返回存在的；都不存在返回空）。"""
    out = []
    for pat in _STAGE_ARTIFACTS.get(stage, []):
        p = Path(base) / pat.format(batch=batch_id)
        if p.exists():
            out.append(p)
    return out


def append_stamp(ledger: dict, stage: str, artifacts=(), gate_reports=(),
                 gates=(), provenance="driver", note=None,
                 driver_version="batch_driver", ts=None) -> dict:
    """追加一条回执并更新 head。artifacts / gate_reports 接受路径字符串或 Path。"""
    if stage not in STAGES:
        raise ValueError(f"未知阶段: {stage!r}（允许 {STAGES}）")
    arts = []
    for a in artifacts or ():
        p = Path(a)
        arts.append({"path": a if isinstance(a, str) and not Path(a).is_absolute() else rel(p),
                     "sha256": file_sha256(p), "bytes": p.stat().st_size if p.is_file() else None})
    reps = []
    for r in gate_reports or ():
        p = Path(r)
        reps.append({"path": r if isinstance(r, str) and not Path(r).is_absolute() else rel(p),
                     "sha256": file_sha256(p)})
    prev = ledger["stamps"][-1] if ledger["stamps"] else None
    stamp = {
        "seq": len(ledger["stamps"]) + 1,
        "stage": stage,
        "verdict": "PASS",
        "provenance": provenance,
        "ts": ts or datetime.now().isoformat(timespec="seconds"),
        "driver_version": driver_version,
        "artifacts": arts,
        "gate_reports": reps,
        "gates": list(gates or ()),
        "note": note,
        "chain_prev": prev.get("hash") if prev else None,
    }
    stamp["hash"] = _stamp_hash(stamp)
    ledger["stamps"].append(stamp)
    ledger["head"] = stamp["hash"]
    return stamp


def verify_chain(ledger: dict):
    """校验回执链自洽：顺序号、每条自身哈希、chain_prev 衔接、head。返回问题列表。"""
    issues = []
    stamps = ledger.get("stamps") or []
    prev_hash = None
    for i, st in enumerate(stamps, 1):
        where = f"#{i}({st.get('stage')})"
        if st.get("seq") != i:
            issues.append({"id": "SEQ_MISMATCH", "detail": f"{where} seq={st.get('seq')} 期望 {i}"})
        if st.get("chain_prev") != prev_hash:
            issues.append({"id": "CHAIN_BROKEN",
                           "detail": f"{where} chain_prev={st.get('chain_prev')} 期望 {prev_hash}"})
        recomputed = _stamp_hash(st)
        if st.get("hash") != recomputed:
            issues.append({"id": "CHAIN_BROKEN", "detail": f"{where} 内容被改动（哈希不符）"})
        prev_hash = st.get("hash")
    if stamps and ledger.get("head") != stamps[-1].get("hash"):
        issues.append({"id": "CHAIN_BROKEN", "detail": "head 与最后一条回执不符"})
    return issues


def verify_artifacts(stamp: dict, base: Path = BASE):
    """校验某条回执里记录的产物是否仍是当时那份（字节级）。返回问题列表。"""
    issues = []
    for art in stamp.get("artifacts") or ():
        p = Path(base) / art["path"] if not Path(art["path"]).is_absolute() else Path(art["path"])
        if not p.is_file():
            issues.append({"id": "ARTIFACT_MISSING", "detail": f"{art['path']} 不存在（回执已记录）"})
            continue
        actual = file_sha256(p)
        if actual != art.get("sha256"):
            issues.append({"id": "ARTIFACT_MISMATCH",
                           "detail": f"{art['path']} sha256={str(actual)[:12]}… 回执={str(art.get('sha256'))[:12]}…"
                                     "（产物在此之后被改过，需重跑该阶段门禁）"})
    return issues


def find_stamp(ledger: dict, stage: str):
    """取该阶段最后一条回执（同阶段重跑时以最新为准）。"""
    hits = [s for s in ledger.get("stamps") or [] if s.get("stage") == stage]
    return hits[-1] if hits else None


def verify(batch_id: str, stage: str, base: Path = BASE, path=None,
           require_artifacts=None, allow_backfill=True) -> dict:
    """验真一个阶段的回执。返回结构化结论（不改任何文件）。

    verdict: PASS / WARN（回执为补录或无可校验产物）/ FAIL
    """
    report = {
        "batch": batch_id,
        "stage": stage,
        "verdict": "PASS",
        "code": "STAMP_OK",
        "ledger": None,
        "stamp_seq": None,
        "checks": [],
        "issues": [],
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }

    def add(cid, status, detail):
        report["checks"].append({"id": cid, "status": status, "detail": detail})

    ledger, err = load_ledger(batch_id, base, path)
    report["ledger"] = str(Path(path) if path else ledger_path(batch_id, base))
    if err:
        report["verdict"], report["code"] = "FAIL", "LEDGER_CORRUPT"
        add("ledger", "FAIL", err)
        return report
    if ledger is None:
        report["verdict"], report["code"] = "FAIL", "LEDGER_MISSING"
        add("ledger", "FAIL", f"没有回执链：{report['ledger']}（该批次可能跳过了门禁）")
        return report
    add("ledger", "PASS", f"{len(ledger['stamps'])} 条回执")

    chain_issues = verify_chain(ledger)
    report["issues"] += chain_issues
    add("chain", "FAIL" if chain_issues else "PASS",
        "; ".join(i["detail"] for i in chain_issues) or "链完整")

    stamp = find_stamp(ledger, stage)
    if stamp is None:
        report["verdict"], report["code"] = "FAIL", "STAGE_MISSING"
        add("stage", "FAIL", f"回执链里没有 {stage} 阶段（跳过了该门禁）")
        return report
    report["stamp_seq"] = stamp.get("seq")
    add("stage", "PASS", f"seq={stamp.get('seq')} provenance={stamp.get('provenance')}")

    art_issues = verify_artifacts(stamp, base)
    report["issues"] += art_issues
    add("artifacts", "FAIL" if art_issues else "PASS",
        "; ".join(i["detail"] for i in art_issues) or f"{len(stamp.get('artifacts') or [])} 个产物字节一致")

    if require_artifacts:
        covered = {Path(a["path"]).as_posix() for a in stamp.get("artifacts") or ()}
        missing = [x for x in require_artifacts if rel(x) not in covered]
        if missing:
            report["issues"].append({"id": "ARTIFACT_NOT_COVERED",
                                     "detail": "回执未覆盖: " + ", ".join(missing)})
            add("coverage", "FAIL", "回执未覆盖: " + ", ".join(missing))
        else:
            add("coverage", "PASS", "目标产物已被回执覆盖")

    hard = [i for i in report["issues"] if i["id"] in FAIL_CODES]
    if hard:
        report["verdict"] = "FAIL"
        report["code"] = next(c for c in FAIL_CODES if any(i["id"] == c for i in hard))
        return report
    if stamp.get("provenance") == "backfill" and not allow_backfill:
        report["verdict"], report["code"] = "FAIL", "STAGE_BACKFILL"
        add("provenance", "FAIL", "回执为补录（门禁未被真正执行）")
        return report
    if stamp.get("provenance") == "backfill":
        report["verdict"], report["code"] = "WARN", "STAGE_BACKFILL"
        add("provenance", "WARN", "回执为补录：门禁是否真跑过无法证明")
        return report
    return report


def required_for(batch_id: str) -> bool:
    """该批次是否属于「必须有回执」的范围（batch048 起）。"""
    n = batch_number(batch_id)
    return n is not None and n >= STAMP_REQUIRED_MIN_BATCH


def _show(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="查看/校验批次门禁回执链")
    ap.add_argument("action", choices=["show", "verify"])
    ap.add_argument("--batch", "-b", required=True)
    ap.add_argument("--stage", "-s", default=None, choices=list(STAGES))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.action == "verify":
        if not args.stage:
            ap.error("verify 需要 --stage")
        r = verify(args.batch, args.stage)
        print(json.dumps(r, ensure_ascii=False, indent=2) if args.json
              else f"{args.batch}/{args.stage}: {r['verdict']} {r['code']}")
        return 0 if r["verdict"] != "FAIL" else 1
    ledger, err = load_ledger(args.batch)
    if err or ledger is None:
        print(f"[ERROR] {err or '没有回执链'}")
        return 2
    if args.stage:
        st = find_stamp(ledger, args.stage)
        print(json.dumps(st, ensure_ascii=False, indent=2) if st else f"没有 {args.stage} 回执")
        return 0 if st else 1
    rows = [{"seq": s["seq"], "stage": s["stage"], "ts": s["ts"], "provenance": s["provenance"],
             "artifacts": [a["path"] for a in s.get("artifacts") or ()]}
            for s in ledger["stamps"]]
    print(json.dumps({"batch": args.batch, "head": ledger["head"], "stamps": rows},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_show())
