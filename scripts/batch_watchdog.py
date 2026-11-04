#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_watchdog.py — 进展判据看门狗（SA-8）

为什么有这个脚本（2026-11-04，SA-8）：
    现有守卫是**计数器**：HALT、「单题≤2 轮 / 整批≤3 轮」、NOOP 检测。
    但在无效循环里打转的批次并没有崩溃——同一 FAIL 码连续几轮不降、补丁反复改同样的字段，
    计数器和传统监控都看不见。本脚本把判据从「次数」换成「进展」。

两类判据（都只读既有证据）：
    R1 同一门禁 + 同一失败原因连续 N 轮不降（默认 2）→ 无进展
    R2 补丁指纹重复（同题同字段/同操作反复出现）→ 原地打转
    R3 无效补丁（changes[].before == after）→ 空转

输出固定四问（论文「用自然语言问它为什么卡住」的机械化版）：
    {卡在哪一阶段, 重复的 FAIL 码, 已试过的补丁, 建议动作}

纪律（least privilege）：
    只读 reports/obs 遥测、AGENT4 追溯日志、reports/gate 报告；
    **绝不**改产物、不写 workflow_state、不改 review_queue；熔断动作只作为建议输出，
    由 batch_driver / 编排者按 HC-28「隔离该题 + 继续」执行。

用法：
    python scripts/batch_watchdog.py --batch batch045 [--json-out P] [--repeat-n 2] [--window 5] [--dry-run]
退出码：0 有进展 / 1 判定无进展（熔断建议） / 2 错误 / 3 证据不足
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if "pytest" not in sys.modules:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

OBS_DIR = BASE / "reports" / "obs"
GATE_DIR = BASE / "reports" / "gate"
DEFAULT_REPEAT_N = 2
DEFAULT_WINDOW = 5


def _load_jsonl(path: Path):
    rows = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except FileNotFoundError:
        return []
    return rows


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def normalize_reason(reason: str) -> str:
    """把原因文本归一为「码」：去掉数字/路径/题号等易变部分，保留判定语义。"""
    s = str(reason or "").strip()
    s = re.sub(r"batch\d{3}(-[A-Z])?", "batchXXX", s)
    s = re.sub(r"[A-Za-z]+-?Q?\d{2,}", "QID", s)
    s = re.sub(r"\d+(\.\d+)?", "N", s)
    s = re.sub(r"\s+", " ", s)
    return s[:160]


def gate_events(rows):
    """只保留 gate_check 事件（含 gate/status/stage），按时间排序。"""
    ev = [r for r in rows if str(r.get("event")) == "gate_check" and r.get("gate")]
    return sorted(ev, key=lambda r: str(r.get("ts") or ""))


def detect_repeated_blocks(events, repeat_n=DEFAULT_REPEAT_N, window=DEFAULT_WINDOW):
    """R1：同一门禁 + 同一归一化原因连续 N 次未通过（中间出现 PASS 即清零）。"""
    by_gate = {}
    for r in events:
        by_gate.setdefault(str(r.get("gate")), []).append(r)
    hits = []
    for gate, rows in by_gate.items():
        rows = rows[-max(window, repeat_n * 2):]
        streak = {}
        for r in rows:
            status = str(r.get("status") or "").upper()
            code = normalize_reason(r.get("reason"))
            if status == "PASS":
                streak = {}
                continue
            if status not in ("BLOCKED", "FAIL", "HALT"):
                continue
            key = code
            prev = streak.get(key)
            streak[key] = {
                "gate": gate,
                "reason": r.get("reason"),
                "code": code,
                "count": (prev["count"] + 1) if prev else 1,
                "first_ts": (prev["first_ts"] if prev else r.get("ts")),
                "last_ts": r.get("ts"),
                "stage": r.get("stage") or (prev or {}).get("stage"),
            }
        for key, item in streak.items():
            if item["count"] >= repeat_n:
                hits.append(item)
    hits.sort(key=lambda x: (-x["count"], x["gate"]))
    return hits


def _rel(p: Path, base: Path) -> str:
    try:
        return str(p.relative_to(base))
    except Exception:
        return str(p)


def find_trace_logs(batch: str, base: Path = BASE):
    pats = [
        f"最终产物/{batch}/*追溯日志*.json",
        f"archive/最终产物/{batch}/*追溯日志*.json",
        f"中间产物/{batch}/*追溯日志*.json",
        f"archive/中间产物/{batch}/*追溯日志*.json",
    ]
    seen, out = set(), []
    for pat in pats:
        for p in sorted(base.glob(pat)):
            if "_backup" in p.parts:
                continue
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                out.append(p)
    return out


def extract_patches(trace_paths, base: Path = BASE):
    """从追溯日志提取补丁：{qid|target, fields|operation, before_after_identical}。

    同一 patch_id（或同一操作+同一 detail）出现在多份日志副本（归档/备份）里
    **只算一次**——否则「同一补丁被存了两份」会被误判成「原地打转」。
    """
    rows = []
    seen = set()
    for p in trace_paths:
        data = _load_json(p)
        if not isinstance(data, dict):
            continue
        patches = data.get("patches") or data.get("patch_log") or []
        if not isinstance(patches, list):
            continue
        for patch in patches:
            if not isinstance(patch, dict):
                continue
            target = patch.get("question_id") or patch.get("target") or patch.get("patch_id") or "?"
            changes = patch.get("changes") if isinstance(patch.get("changes"), list) else []
            fields = sorted({str(c.get("field")) for c in changes if isinstance(c, dict) and c.get("field")})
            identical = bool(changes) and all(
                isinstance(c, dict) and c.get("before") == c.get("after") for c in changes)
            cap_id = str(patch.get("patch_id") or f"{target}|{patch.get('operation')}|{patch.get('detail')}")
            if cap_id in seen:
                continue
            seen.add(cap_id)
            rows.append({
                "source": _rel(p, base),
                "patch_id": cap_id,
                "target": str(target),
                "operation": str(patch.get("operation") or ""),
                "fields": fields,
                "fingerprint": f"{target}|{'+'.join(fields) if fields else patch.get('operation', '')}",
                "identical": identical,
            })
    return rows


def detect_duplicate_patches(patches, repeat_n=DEFAULT_REPEAT_N):
    groups = {}
    for row in patches:
        groups.setdefault(row["fingerprint"], []).append(row)
    hits = []
    for fp, rows in groups.items():
        if len(rows) >= repeat_n:
            hits.append({
                "fingerprint": fp,
                "target": rows[0]["target"],
                "operation": rows[0]["operation"],
                "fields": rows[0]["fields"],
                "count": len(rows),
                "sources": sorted({r["source"] for r in rows}),
            })
    hits.sort(key=lambda x: -x["count"])
    return hits


def detect_ineffective_patches(patches):
    return [r for r in patches if r["identical"]]


def analyze(batch: str, base: Path = BASE, repeat_n: int = DEFAULT_REPEAT_N,
            window: int = DEFAULT_WINDOW):
    obs = base / "reports" / "obs" / f"{batch}_telemetry.jsonl"
    events = gate_events(_load_jsonl(obs)) if obs.exists() else []
    traces = find_trace_logs(batch, base)
    patches = extract_patches(traces, base)
    repeated = detect_repeated_blocks(events, repeat_n, window)
    dup_patches = detect_duplicate_patches(patches, repeat_n)
    ineffective = detect_ineffective_patches(patches)

    has_evidence = bool(events) or bool(patches)
    no_progress = bool(repeated or dup_patches or ineffective)
    if not has_evidence:
        verdict = "INSUFFICIENT_EVIDENCE"
    elif no_progress:
        verdict = "NO_PROGRESS"
    else:
        verdict = "PROGRESS"

    stage = None
    if repeated:
        stage = repeated[0].get("stage")
    elif events:
        stage = events[-1].get("stage")

    actions = []
    if repeated:
        top = repeated[0]
        actions.append({
            "type": "isolate_and_continue",
            "reason": f"同一门禁 {top['gate']} 连续 {top['count']} 轮同一失败原因（{top['code']}）",
            "target": batch,
            "policy": "HC-28：隔离阻塞题 + 入 review_queue + 继续跑其余题，不整批停止",
        })
    if dup_patches:
        top = dup_patches[0]
        actions.append({
            "type": "stop_repeating_patch",
            "reason": f"补丁指纹重复 {top['count']} 次：{top['fingerprint']}",
            "target": top["target"],
            "policy": "换策略（重写题干/换干扰项机制），不要重复同一字段修复",
        })
    if ineffective:
        actions.append({
            "type": "discard_ineffective_patch",
            "reason": f"{len(ineffective)} 个补丁 before==after（空转）",
            "target": ineffective[0]["target"],
            "policy": "丢弃空转补丁，检查生成器是否未回写",
        })

    recommended = []
    if verdict == "NO_PROGRESS":
        first = repeated[0] if repeated else None
        code = (first["code"] if first else (dup_patches[0]["fingerprint"] if dup_patches else "PATCH_LOOP"))
        locator = str(obs.relative_to(base)) if obs.exists() else "reports/obs/"
        cmd = f"python scripts/batch_driver.py check --batch {batch} --stage auto"
        recommended = [f"阻断码：{code}", f"落点文件：{locator}", f"下一步命令：{cmd}"]

    return {
        "batch": batch,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "stage": stage,
        "repeated_codes": repeated,
        "tried_patches": dup_patches,
        "ineffective_patches": [{"target": r["target"], "source": r["source"]} for r in ineffective],
        "actions": actions,
        "recommended": recommended,
        "evidence": {
            "telemetry": str(obs.relative_to(base)) if obs.exists() else None,
            "trace_logs": [str(p.relative_to(base)) for p in traces],
            "gate_reports": [str(p.relative_to(base)) for p in sorted(
                (base / "reports" / "gate").glob(f"*{batch}*"))],
            "event_count": len(events),
            "patch_count": len(patches),
        },
        "thresholds": {"repeat_n": repeat_n, "window": window},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="进展判据看门狗（SA-8）")
    ap.add_argument("--batch", "-b", required=True)
    ap.add_argument("--json-out", default=None, help="默认 reports/gate/watchdog_{batch}.json")
    ap.add_argument("--repeat-n", type=int, default=DEFAULT_REPEAT_N)
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    try:
        result = analyze(args.batch, BASE, args.repeat_n, args.window)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    out = Path(args.json_out) if args.json_out else (GATE_DIR / f"watchdog_{args.batch}.json")
    if not args.dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    icon = {"PROGRESS": "✅", "NO_PROGRESS": "🛑", "INSUFFICIENT_EVIDENCE": "❔"}[result["verdict"]]
    print(f"{icon} {args.batch} ｜ {result['verdict']} ｜ 卡在 {result['stage'] or '—'}")
    for r in result["repeated_codes"]:
        print(f"  🔁 {r['gate']} × {r['count']}：{str(r['reason'])[:80]}")
    for p in result["tried_patches"]:
        print(f"  🔂 补丁重复 × {p['count']}：{p['fingerprint'][:100]}")
    for a in result["actions"]:
        print(f"  ➡️  {a['type']}（{a['target']}）：{a['reason']}")
    for line in result["recommended"]:
        print(f"  {line}")
    if not args.dry_run:
        print(f"  ↳ {out}")
    return {"PROGRESS": 0, "NO_PROGRESS": 1, "INSUFFICIENT_EVIDENCE": 3}[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
