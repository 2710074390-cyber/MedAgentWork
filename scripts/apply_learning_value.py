#!/usr/bin/env python3
"""apply_learning_value.py — 把已审 v2 学习价值层合并回最终题库 JSON。

规则：
- 只更新 --ids-file 指定的题；未指定则更新 --v2 中全部题。
- 保留原 explanation 到 legacy_explanation；新 explanation 由 learning_value 渲染。
- 写入采用 tmp + os.replace 原子写。
- 输出 merge log（逐题记录、前后字段、来源文件）。

用法：
  python scripts/apply_learning_value.py \
    --final 最终产物/batch040/ALL_questions_FIXED.json \
    --v2 中间产物/batch040/learning_value_v2/items_v2_progress.json \
    --ids-file 中间产物/batch040/learning_value_v2/second_pass_sample20.json \
    --report 最终产物/batch040/learning_value_v2_merge_log.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = Path(__file__).resolve().parent.parent


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def render_explanation(q: dict) -> str:
    lv = q.get("learning_value") or {}
    lines = [f"【正确答案】{lv.get('correct_rationale', '').strip()}", "", "【逐项解析】"]
    for p in lv.get("per_option", []):
        line = f"{p.get('label')}. {str(p.get('why') or '').strip()}"
        if p.get("misconception"):
            line += f"（错误认知：{p['misconception']}）"
        lines.append(line)
    lines.append("")
    take = str(lv.get("key_takeaway") or "").strip()
    if take:
        lines.append(f"【鉴别规则】{take}")
    quote = str(lv.get("source_quote") or "").strip()
    if quote:
        lines.append(f"【来源】{quote}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", required=True)
    ap.add_argument("--v2", required=True)
    ap.add_argument("--ids-file", default="", help="JSON 数组文件，取其中的 id；为空则合并 v2 全部")
    ap.add_argument("--out", default="", help="默认覆盖 --final")
    ap.add_argument("--report", default="", help="合并日志 JSON")
    args = ap.parse_args()

    final_path = Path(args.final)
    out_path = Path(args.out) if args.out else final_path
    report_path = Path(args.report) if args.report else final_path.parent / "learning_value_v2_merge_log.json"

    final = load_json(final_path)
    v2 = load_json(Path(args.v2))
    by_v2 = {q.get("id"): q for q in v2 if isinstance(q, dict)}

    if args.ids_file:
        ids = [q.get("id") for q in load_json(Path(args.ids_file)) if isinstance(q, dict)]
        target = set(ids)
    else:
        target = set(by_v2)

    before = {}
    merged = []
    for q in final:
        qid = q.get("id")
        if qid not in target or qid not in by_v2:
            continue
        src = by_v2[qid]
        before[qid] = {
            "explanation_len": len(str(q.get("explanation") or "")),
            "teacher_anchor": q.get("teacher_anchor", ""),
            "keypoint_ref": q.get("keypoint_ref", []),
            "review_status": q.get("review_status", ""),
        }
        q["legacy_explanation"] = q.get("legacy_explanation") or q.get("explanation", "")
        q["learning_value"] = src.get("learning_value", {})
        q["learning_value"]["review_status"] = "approved"
        q["learning_value"]["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
        q["teacher_anchor"] = src.get("teacher_anchor", q.get("teacher_anchor", ""))
        q["keypoint_ref"] = src.get("keypoint_ref", q.get("keypoint_ref", []))
        q["review_status"] = "approved"
        q["explanation"] = render_explanation(q)
        merged.append(qid)

    atomic_write(out_path, final)

    report = {
        "merged_at": datetime.now().isoformat(timespec="seconds"),
        "final_source": str(final_path),
        "v2_source": str(args.v2),
        "out": str(out_path),
        "requested": len(target),
        "merged": len(merged),
        "missing": sorted(target - set(merged)),
        "items": [],
    }
    for qid in merged:
        q = next(x for x in final if x.get("id") == qid)
        report["items"].append({
            "id": qid,
            "before": before[qid],
            "after": {
                "explanation_len": len(q.get("explanation") or ""),
                "teacher_anchor": q.get("teacher_anchor", ""),
                "keypoint_ref": q.get("keypoint_ref", []),
                "review_status": q.get("review_status", ""),
                "source_quote_status": (q.get("learning_value") or {}).get("source_quote_status"),
                "anchor_status": (q.get("learning_value") or {}).get("anchor_status"),
            },
        })
    if report_path:
        atomic_write(report_path, report)

    print(f"合并 {len(merged)} / 请求 {len(target)} 题 → {out_path}")
    if report["missing"]:
        print("缺失：", report["missing"])
    print(f"合并日志：{report_path}")
    return 0 if not report["missing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
