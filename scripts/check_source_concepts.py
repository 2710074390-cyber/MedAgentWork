#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_source_concepts.py — HC-27 概念标注门禁（生成期，零依赖）。

为什么单独做一个
    schemas/agent2_output.schema.json 已用 if/then 约束 concepts，但
    ingest.py 的 jsonschema 校验在默认解释器下**静默跳过**（本机 python 3.10 无 jsonschema），
    只靠 schema 等于没拦。本脚本不依赖任何第三方库，能在生成现场直接跑。

判定口径（按批次号，不追溯旧产物）
    batch < --min-batch（默认 44）且没有 2.1 题  → SKIP（退出码 2，显式降级，不当通过）
    batch >= --min-batch 且没有 2.1 题           → FAIL（新批次必须声明 schema_version=2.1）
    --require 强制要求（不论批次号）

检查项
    S1 concepts 存在且是数组、1–4 条
    S2 恰好 1 条 role=primary
    S3 A2/A3/A4/X ≥2 条；A1/B1/判断 ≥1 条
    S4 每条 role 合法、keypoint 非空、title ≥2 字、evidence ≥8 字
    S5 primary.keypoint 与本题 keypoint_ref 一致
    S6 同一题内 title 不重复

用法
    python scripts/check_source_concepts.py --file 中间产物/batch044/ALL_questions.json --batch batch044
    python scripts/check_source_concepts.py --file X --batch batch040        # 旧批次 → SKIP
    python scripts/check_source_concepts.py --file X --require               # 强制
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

def _configure_stdio() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


BASE = Path(__file__).resolve().parent.parent
DEFAULT_OUT = BASE / "reports/validate/source_concepts_check.json"
MULTI_TYPES = {"A2", "A3", "A4", "X"}
ROLES = {"primary", "differential", "related"}
BATCH_RE = re.compile(r"(\d+)")


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def qid_of(q: dict) -> str:
    return str(q.get("id") or q.get("question_id") or q.get("qid") or "?")


def kp_norm(v) -> str:
    """keypoint_ref / concepts[].keypoint 归一：取第一个元素、去空格。"""
    if isinstance(v, (list, tuple)):
        v = v[0] if v else ""
    return re.sub(r"\s+", "", str(v or ""))


def batch_num(batch: str) -> int:
    m = BATCH_RE.search(str(batch or ""))
    return int(m.group(1)) if m else 0


def check_question(q: dict) -> tuple[list[str], list[str]]:
    """返回 (fails, warns)。"""
    fails: list[str] = []
    warns: list[str] = []
    qid = qid_of(q)
    qtype = str(q.get("type") or q.get("question_type") or "")
    concepts = q.get("concepts")

    if not isinstance(concepts, list) or not concepts:
        fails.append(f"{qid}: S1 缺 concepts")
        return fails, warns
    if len(concepts) > 4:
        fails.append(f"{qid}: S1 concepts 超过 4 条（{len(concepts)}）")

    primaries = [c for c in concepts if isinstance(c, dict) and c.get("role") == "primary"]
    if len(primaries) != 1:
        fails.append(f"{qid}: S2 primary 数量 = {len(primaries)}，应为 1")

    need = 2 if qtype in MULTI_TYPES else 1
    if len(concepts) < need:
        fails.append(f"{qid}: S3 {qtype or '未知题型'} 只有 {len(concepts)} 条概念，需 ≥{need}")

    titles = []
    for i, c in enumerate(concepts):
        if not isinstance(c, dict):
            fails.append(f"{qid}: S4 第{i + 1}条不是对象")
            continue
        role = str(c.get("role") or "")
        if role not in ROLES:
            fails.append(f"{qid}: S4 第{i + 1}条 role 非法（{role}）")
        if not kp_norm(c.get("keypoint")):
            fails.append(f"{qid}: S4 第{i + 1}条 keypoint 为空")
        title = str(c.get("title") or "").strip()
        if len(title) < 2:
            fails.append(f"{qid}: S4 第{i + 1}条 title 少于 2 字")
        titles.append(title)
        ev = str(c.get("evidence") or "").strip()
        if len(ev) < 8:
            fails.append(f"{qid}: S4 第{i + 1}条 evidence 少于 8 字（「{ev}」）")

    dup = [t for t, n in Counter(titles).items() if t and n > 1]
    if dup:
        fails.append(f"{qid}: S6 概念标题重复 {dup}")

    if len(primaries) == 1:
        pk = kp_norm(primaries[0].get("keypoint"))
        ref = kp_norm(q.get("keypoint_ref"))
        if ref and pk != ref:
            fails.append(f"{qid}: S5 primary.keypoint（{pk}）≠ keypoint_ref（{ref}）")

    if qtype in MULTI_TYPES and len(concepts) >= 2:
        if not any(c.get("role") == "differential" for c in concepts if isinstance(c, dict)):
            warns.append(f"{qid}: {qtype} 有多个概念但没有 differential（可能都写成 related）")

    return fails, warns


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HC-27 概念标注门禁")
    ap.add_argument("--file", required=True)
    ap.add_argument("--batch", default="")
    ap.add_argument("--min-batch", type=int, default=44,
                    help="从该批次号起强制 schema_version=2.1（默认 44）")
    ap.add_argument("--require", action="store_true", help="不论批次号，一律要求 2.1")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"ERROR —— 文件不存在：{path}")
        return 2
    data = read_json(path)
    if not isinstance(data, list):
        print(f"ERROR —— 应为 JSON 数组，实际 {type(data).__name__}")
        return 2

    versions = Counter(str(q.get("schema_version") or "未声明") for q in data)
    has_21 = any(str(q.get("schema_version") or "") == "2.1" for q in data)
    need_21 = args.require or batch_num(args.batch) >= args.min_batch

    if not has_21 and not need_21:
        msg = (f"SKIP —— 本批 {len(data)} 题无 schema_version=2.1（历史契约 {dict(versions)}），"
               f"HC-27 不追溯")
        print(msg)
        report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
                  "file": str(path), "batch": args.batch, "status": "SKIP",
                  "reason": msg, "versions": dict(versions)}
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    if not has_21 and need_21:
        msg = (f"FAIL —— 批次 {args.batch or '(未提供)'} 属于 HC-27 生效范围，"
               f"但没有任何题声明 schema_version=2.1（实际 {dict(versions)}）")
        print(msg)
        report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
                  "file": str(path), "batch": args.batch, "status": "FAIL",
                  "reason": msg, "versions": dict(versions)}
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    fails: list[str] = []
    warns: list[str] = []
    checked = 0
    by_type = Counter()
    concept_counts = Counter()
    for q in data:
        if str(q.get("schema_version") or "") != "2.1":
            continue
        checked += 1
        by_type[str(q.get("type") or "?")] += 1
        concept_counts[len(q.get("concepts") or [])] += 1
        f, w = check_question(q)
        fails += f
        warns += w

    status = "FAIL" if fails else ("WARN" if warns else "PASS")
    multi_ok = sum(1 for q in data
                   if str(q.get("schema_version") or "") == "2.1"
                   and str(q.get("type") or "") in MULTI_TYPES
                   and len(q.get("concepts") or []) >= 2)
    multi_pool = sum(1 for q in data
                     if str(q.get("schema_version") or "") == "2.1"
                     and str(q.get("type") or "") in MULTI_TYPES)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generator": "scripts/check_source_concepts.py",
        "file": str(path), "batch": args.batch, "status": status,
        "versions": dict(versions), "checked": checked, "total": len(data),
        "by_type": dict(by_type), "concepts_per_question": dict(sorted(concept_counts.items())),
        "multi_type_total": multi_pool, "multi_type_with_2plus": multi_ok,
        "multi_type_rate": round(multi_ok / multi_pool, 4) if multi_pool else None,
        "fails": fails[:80], "warn_count": len(warns), "warns": warns[:40],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"HC-27 概念标注门禁：{status}")
    print(f"  版本分布 {dict(versions)}　检查 {checked}/{len(data)} 题")
    print(f"  A2+ 双概念率 {report['multi_type_rate']}（{multi_ok}/{multi_pool}）")
    if fails:
        print(f"  FAIL {len(fails)} 条，前 5：")
        for f in fails[:5]:
            print(f"    - {f}")
    if warns:
        print(f"  WARN {len(warns)} 条，前 3：")
        for w in warns[:3]:
            print(f"    - {w}")
    print(f"→ {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    _configure_stdio()
    raise SystemExit(main())
