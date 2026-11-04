#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中央兜底批次门禁审计（gate audit）—— P0-C。

要解决的问题
------------
scripts/gate_stamp.py 只解决「记录 + 验真」：门禁 PASS 后写一条链式回执，
消费方可以验上游。但没有任何中央视角的兜底——某个批次被第三方 Agent 整个跳过
（没写回执、没跑门禁），只要没人主动查，就永远查不出来。

本脚本是「中央兜底审计 + CI 强制」的执行体：
1. 发现需要审计的批次（显式 / 全量 / 本次改动）；
2. 逐批判定回执链：缺链、断链、产物被改、补录回执；
3. --recheck 时对存在的题目数组产物重跑确定性门禁（python -m scripts.validate），
   这是唯一能对抗伪造回执的兜底手段（见 gate_stamp 的职责边界声明）。

用法
----
    python scripts/gate_audit.py (--batch ID | --all | --changed-only)
                               [--strict] [--recheck] [--json-out F]
                               [--base PATH] [--since REV] [--limit N]

判定口径（逐批）
----------------
情形                     结论
-------------------------  -------------------------------------------------
回执链不可解析           FAIL LEDGER_CORRUPT
无回执链，batch>=048     FAIL LEDGER_MISSING（该批次起回执是强制的）
无回执链，batch<048      WARN LEGACY_UNSTAMPED（--strict 时升为 FAIL）
回执链为空（0 条）       同「无回执链」处理（空链不构成任何门禁证明）
链问题                   FAIL CHAIN_BROKEN / SEQ_MISMATCH
回执记录产物不存在        WARN ARTIFACT_ABSENT（中间产物常不入库，不能算失败）
回执记录产物 sha256 不符  FAIL ARTIFACT_MISMATCH
provenance=backfill      WARN STAGE_BACKFILL（补录：门禁是否真跑过无法证明）
--recheck rc=1           FAIL RECHECK_FAILED
--recheck rc 非 0/1      ERROR RECHECK_ERROR（复检环境异常，审计无法完成）
-------------------------  -------------------------------------------------

退出码：0 无 FAIL；1 有 FAIL（含 ERROR，审计无法完成等同不通过）；
2 用法/环境错误（参数、--base 不存在、报告写盘失败等）。

批次发现
--------
- --batch ID：显式指定，接受 batch048 / 048。
- --all：扫描 最终产物/、中间产物/、质检报告/ 下的 batchNNN 目录并集。
- --changed-only：跑 git diff --name-only <since> HEAD（默认 HEAD~1），
  只保留落在 最终产物/、中间产物/、质检报告/、复习资料/ 下且路径
  含 batchNNN 的条目；基线版本解析不到时回退为「所有已有回执链的批次」，
  并在输出与 JSON 报告里标注 fallback。

约定
----
- 不 import 第三方库；import gate_audit 无副作用（CI 与单测要复用纯函数）。
- 路径一律通过 gate_stamp.rel 与 --base 相对拼接，保证能在临时目录里工作。
- --base 只影响「读哪棵树」，复检命令仍以仓库根为 cwd 执行。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:  # 以脚本方式运行 / 单测把 scripts/ 加进 sys.path 时
    import gate_stamp
except ImportError:  # pragma: no cover - 包上下文（python -m scripts.gate_audit）
    from scripts import gate_stamp

BASE = Path(__file__).resolve().parent.parent

# --all 的扫描根目录（回执链只可能出现在 最终产物/ 下，但历史批次可能只有中间产物）
BATCH_ROOTS = ("最终产物", "中间产物", "质检报告")
# --changed-only 的路径过滤根目录（复习资料 只有 a5 批次，回执可能缺失）
CHANGED_ROOTS = ("最终产物", "中间产物", "质检报告", "复习资料")

BATCH_DIR_RE = re.compile(r"batch(\d{3})")
BATCH_ID_RE = re.compile(r"(?:batch)?(\d{3})", re.IGNORECASE)

DEFAULT_SINCE = "HEAD~1"
RECHECK_TIMEOUT = 120
GIT_TIMEOUT = 60

# 判定码优先级：同一批次多个问题时取「最严重且最靠前」的作为总代码。
CODE_PRIORITY = {
    "LEDGER_CORRUPT": 0,
    "LEDGER_MISSING": 1,
    "CHAIN_BROKEN": 2,
    "SEQ_MISMATCH": 3,
    "STAGE_MISSING": 4,
    "ARTIFACT_MISMATCH": 5,
    "RECHECK_FAILED": 6,
    "RECHECK_ERROR": 7,
    "LEGACY_UNSTAMPED": 8,
    "ARTIFACT_ABSENT": 9,
    "STAGE_BACKFILL": 10,
}

# 「产物在、回执不在」检查覆盖的交付物阶段。lv/a5 与 a4 共用产物或按 schema 条件出现，
# 交给 driver 的 preflight 管，audit 这里只盯「一定有产物」的四段。
COVERAGE_STAGES = ("a2", "a3", "a4", "final")


# ---------------------------------------------------------------------------
# 批次发现
# ---------------------------------------------------------------------------
def normalize_batch_id(value):
    """把 batch048 / 048 归一成 batch048；不合法返回 None。"""
    m = BATCH_ID_RE.fullmatch(str(value or "").strip())
    return f"batch{m.group(1)}" if m else None


def discover_batches(base: Path = BASE):
    """扫描 最终产物/中间产物/质检报告 下的 batchNNN 目录并集（按批次号排序）。"""
    found = {}
    for root in BATCH_ROOTS:
        d = Path(base) / root
        if not d.is_dir():
            continue
        try:
            children = sorted(d.iterdir())
        except OSError:
            continue
        for p in children:
            if not p.is_dir():
                continue
            m = BATCH_DIR_RE.fullmatch(p.name)
            if m:
                found[p.name] = int(m.group(1))
    return sorted(found, key=lambda b: (found[b], b))


def ledger_batches(base: Path = BASE):
    """扫出「已有回执链」的批次（--changed-only 基线解析失败时的回退集合）。"""
    found = {}
    for root in CHANGED_ROOTS:
        d = Path(base) / root
        if not d.is_dir():
            continue
        try:
            children = sorted(d.iterdir())
        except OSError:
            continue
        for p in children:
            if not p.is_dir():
                continue
            m = BATCH_DIR_RE.fullmatch(p.name)
            if not m:
                continue
            if (p / gate_stamp.LEDGER_NAME).is_file():
                found[p.name] = int(m.group(1))
    return sorted(found, key=lambda b: (found[b], b))


def batches_from_changed_paths(paths):
    """纯函数：把 git diff --name-only 的路径列表解析成批次 id 列表。

    规则（与 CLI 契约一致）：只保留落在 最终产物/ 中间产物/ 质检报告/ 复习资料/
    之下、且路径里含 batchNNN 的条目；去重后按批次号排序。
    """
    found = {}
    for raw in paths or ():
        p = str(raw or "").strip().replace("\\", "/")
        while p.startswith("./"):
            p = p[2:]
        if not p or p.startswith("/"):
            continue
        if p.split("/", 1)[0] not in CHANGED_ROOTS:
            continue
        m = BATCH_DIR_RE.search(p)
        if not m:
            continue
        batch = f"batch{m.group(1)}"
        found[batch] = int(m.group(1))
    return sorted(found, key=lambda b: (found[b], b))


def git_changed_paths(since: str = DEFAULT_SINCE, base: Path = BASE):
    """跑 git diff --name-only <since> HEAD。返回 (paths, error)；失败时 paths 为 None。"""
    cmd = ["git", "diff", "--name-only", str(since), "HEAD"]
    try:
        proc = subprocess.run(
            cmd, cwd=str(base), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT,
        )
    except FileNotFoundError:
        return None, "git 不可用（未安装或不在 PATH）"
    except subprocess.TimeoutExpired:
        return None, f"git diff 超时（>{GIT_TIMEOUT}s，since={since}）"
    except OSError as exc:
        return None, f"git 调用失败：{exc}"
    if proc.returncode != 0:
        tail = ((proc.stderr or "").strip().splitlines() or [""])[-1][:200]
        return None, f"git diff {since} HEAD 失败(rc={proc.returncode})：{tail}"
    return [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()], None


# ---------------------------------------------------------------------------
# 逐批判定
# ---------------------------------------------------------------------------
def _add_issue(entry: dict, code: str, verdict: str, detail: str) -> None:
    entry["issues"].append({"id": code, "verdict": verdict, "detail": detail})


def _pick_code(issues, verdict: str) -> str:
    """该判定档位下优先级最高的判定码；没有则 OK。"""
    pool = [
        (CODE_PRIORITY.get(i["id"], 99), n, i["id"])
        for n, i in enumerate(issues)
        if i["verdict"] == verdict
    ]
    return min(pool)[2] if pool else "OK"


def finalize(entry: dict) -> None:
    """按 issues 汇总 batch 条目的 verdict / code（FAIL > ERROR > WARN > PASS）。"""
    issues = entry["issues"]
    if any(i["verdict"] == "FAIL" for i in issues):
        entry["verdict"] = "FAIL"
    elif any(i["verdict"] == "ERROR" for i in issues):
        entry["verdict"] = "ERROR"
    elif any(i["verdict"] == "WARN" for i in issues):
        entry["verdict"] = "WARN"
    else:
        entry["verdict"] = "PASS"
    entry["code"] = _pick_code(issues, entry["verdict"])


def _artifact_path(art: dict, base: Path = BASE) -> Path:
    """回执里的产物路径 → 实际路径。

    绝对路径原样；相对路径优先相对 --base。若 base 下不存在，再回退到仓库根——
    因为 gate_stamp.append_stamp 落盘相对路径时用的是仓库根（默认 BASE），
    用 --base 审计「仓库的子目录/复制树」时需要这层兼容。
    """
    p = Path(str(art.get("path") or ""))
    if p.is_absolute():
        return p
    cand = Path(base) / p
    if cand.is_file():
        return cand
    repo_cand = BASE / p
    return repo_cand if repo_cand.is_file() else cand


def batch_status(batch_id: str, base: Path = BASE) -> str:
    """读 workflow_state 的批次状态；读不到就返回空串（audit 不因状态文件缺失而失败）。"""
    try:
        import workflow_state as ws
        state, err = ws.load_state(base)
        if err or not isinstance(state, dict):
            return ""
        return str((state.get(batch_id) or {}).get("status") or "").upper()
    except Exception:
        return ""


def check_stage_coverage(entry: dict, batch_id: str, ledger: dict, base: Path,
                         approved: bool) -> None:
    """产物在、回执不在 = 跳过门禁（P0 的核心判据之一）。

    签收（APPROVED）批次必须整链齐全；未签收批次可能正在流程中，只告警不阻断。
    """
    for stage in COVERAGE_STAGES:
        arts = gate_stamp.expected_artifacts(batch_id, stage, base)
        if not arts or gate_stamp.find_stamp(ledger, stage) is not None:
            continue
        verdict = "FAIL" if (gate_stamp.required_for(batch_id) and approved) else "WARN"
        _add_issue(entry, "STAGE_MISSING", verdict,
                   f"{stage} 产物已存在（{gate_stamp.rel(arts[0], base)}）但回执链里没有 {stage} 阶段"
                   "（该阶段门禁可能被跳过；先跑 batch_driver.py check --stage " + stage + "）")


def evaluate_batch(batch_id: str, base: Path = BASE, strict: bool = False):
    """判定一个批次。返回 (entry, recheck_candidates)。

    entry 形如 {batch, verdict, code, issues, stamps, recheck}；
    recheck_candidates 是「存在且哈希一致」的产物路径，供 --recheck 重跑门禁。
    """
    entry = {
        "batch": batch_id,
        "verdict": "PASS",
        "code": "OK",
        "issues": [],
        "stamps": 0,
        "recheck": [],
    }
    candidates = []

    ledger, err = gate_stamp.load_ledger(batch_id, base)
    if err:
        _add_issue(entry, "LEDGER_CORRUPT", "FAIL", f"回执链不可解析：{err}")
        finalize(entry)
        return entry, candidates

    if ledger is None:
        _missing(entry, batch_id, base, strict, "没有回执链")
        finalize(entry)
        return entry, candidates

    stamps = ledger.get("stamps") or []
    entry["stamps"] = len(stamps)
    if not stamps:
        # 空链不构成任何门禁证明：按「无回执」口径处理，避免「建个空链就绕过」。
        _missing(entry, batch_id, base, strict, "回执链为空（0 条回执）")
        finalize(entry)
        return entry, candidates

    for issue in gate_stamp.verify_chain(ledger):
        cid = issue.get("id")
        if cid not in ("CHAIN_BROKEN", "SEQ_MISMATCH"):
            cid = "CHAIN_BROKEN"
        _add_issue(entry, cid, "FAIL", str(issue.get("detail") or ""))

    backfill_seqs = []
    for st in stamps:
        if st.get("provenance") == "backfill":
            backfill_seqs.append(st.get("seq"))
        for art in st.get("artifacts") or ():
            p = _artifact_path(art, base)
            label = str(art.get("path") or p)
            if not p.is_file():
                _add_issue(entry, "ARTIFACT_ABSENT", "WARN",
                           f"seq={st.get('seq')} {label} 不存在（中间产物常不入库，不等同失败）")
                continue
            actual = gate_stamp.file_sha256(p)
            expected = str(art.get("sha256") or "")
            if actual != expected:
                _add_issue(entry, "ARTIFACT_MISMATCH", "FAIL",
                           f"seq={st.get('seq')} {label} sha256={str(actual)[:12]}… 回执={expected[:12]}…"
                           "（回执之后产物被改过，需重跑该阶段门禁）")
                continue
            candidates.append(p)
    check_stage_coverage(entry, batch_id, ledger, base,
                         batch_status(batch_id, base) == "APPROVED")
    if backfill_seqs:
        seqs = ",".join(str(s) for s in backfill_seqs)
        _add_issue(entry, "STAGE_BACKFILL", "WARN",
                   f"seq={seqs} 为补录回执（门禁是否真正执行过无法证明）")

    finalize(entry)
    return entry, candidates


def _missing(entry: dict, batch_id: str, base: Path, strict: bool, why: str) -> None:
    """「没有回执链」的统一口径：强制批次 FAIL，历史遗留批次 WARN（--strict 升 FAIL）。"""
    ledger_rel = gate_stamp.rel(gate_stamp.ledger_path(batch_id, base), base)
    if gate_stamp.required_for(batch_id):
        _add_issue(entry, "LEDGER_MISSING", "FAIL",
                   f"{batch_id}（>=batch{gate_stamp.STAMP_REQUIRED_MIN_BATCH:03d}）{why}："
                   f"{ledger_rel}（该批次必须由 batch_driver 写回执，可能跳过了门禁）")
        return
    verdict = "FAIL" if strict else "WARN"
    tail = "（--strict 已升级为 FAIL）" if strict else "（历史遗留批次，默认仅告警，不影响退出码）"
    _add_issue(entry, "LEGACY_UNSTAMPED", verdict,
               f"{batch_id} 早于 batch{gate_stamp.STAMP_REQUIRED_MIN_BATCH:03d}，{why}："
               f"{ledger_rel}{tail}")


# ---------------------------------------------------------------------------
# 复检：重跑确定性门禁
# ---------------------------------------------------------------------------
def is_question_array(data) -> bool:
    """是否「题目数组」：非空 JSON list 且元素都是对象（避免对非题目产物误跑门禁）。"""
    return isinstance(data, list) and bool(data) and all(isinstance(x, dict) for x in data)


def recheck_batch(batch_id: str, candidates, base: Path = BASE,
                  timeout: int = RECHECK_TIMEOUT):
    """对题目数组产物重跑 python -m scripts.validate。返回 (items, issues)。

    rc=0 通过；rc=1 FAIL RECHECK_FAILED；rc 非 0/1 或超时 ERROR RECHECK_ERROR。
    """
    items = []
    issues = []
    validator = BASE / "scripts" / "validate" / "__main__.py"
    if candidates and not validator.is_file():  # 防御：脚本被复制到没有门禁的树里
        issues.append({"id": "RECHECK_ERROR", "verdict": "ERROR",
                       "detail": f"找不到确定性门禁 {gate_stamp.rel(validator, BASE)}，无法复检"})
        return items, issues
    for p in candidates:
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not is_question_array(data):
            continue
        rel = gate_stamp.rel(p, base)
        cmd = [sys.executable, "-m", "scripts.validate",
               "--file", str(p), "--batch", batch_id]
        try:
            proc = subprocess.run(
                cmd, cwd=str(BASE), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            items.append({"path": rel, "rc": None, "status": "TIMEOUT"})
            issues.append({"id": "RECHECK_ERROR", "verdict": "ERROR",
                           "detail": f"{rel} 复检超时（>{timeout}s）"})
            continue
        except OSError as exc:
            items.append({"path": rel, "rc": None, "status": "ERROR"})
            issues.append({"id": "RECHECK_ERROR", "verdict": "ERROR",
                           "detail": f"{rel} 复检无法启动：{exc}"})
            continue
        rc = proc.returncode
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
        tail = tail[-1][:200] if tail else ""
        if rc == 0:
            items.append({"path": rel, "rc": 0, "status": "PASS"})
        elif rc == 1:
            items.append({"path": rel, "rc": 1, "status": "FAIL", "detail": tail})
            issues.append({"id": "RECHECK_FAILED", "verdict": "FAIL",
                           "detail": f"{rel} 重跑确定性门禁未通过：{tail}"})
        else:
            items.append({"path": rel, "rc": rc, "status": "ERROR", "detail": tail})
            issues.append({"id": "RECHECK_ERROR", "verdict": "ERROR",
                           "detail": f"{rel} 复检异常退出 rc={rc}：{tail}"})
    return items, issues


# ---------------------------------------------------------------------------
# 报告与输出
# ---------------------------------------------------------------------------
def format_human(report: dict) -> str:
    """人类可读汇总表：每批一行 + 非 PASS 批次的逐条明细。"""
    lines = [f"门禁回执审计 | mode={report['mode']} base={report['base']}"]
    if report.get("fallback"):
        lines.append("[FALLBACK] " + str(report.get("fallback_reason") or "")
                     + f" -> 回退审计所有已有回执链的批次（{len(report['batches'])} 个）")
    if not report["batches"]:
        lines.append("（没有发现需要审计的批次）")
    else:
        lines.append(f"{'批次':<10}{'判定':<8}{'代码':<20}{'回执':>6}{'问题':>6}  复检")
        for e in report["batches"]:
            items = e.get("recheck") or []
            if not report.get("recheck_enabled"):
                recheck_txt = "-"
            elif not items:
                recheck_txt = "无需复检"
            else:
                ok = sum(1 for i in items if i.get("status") == "PASS")
                recheck_txt = f"{ok}/{len(items)} 通过" + ("" if ok == len(items) else "  [!]")
            lines.append(f"{e['batch']:<10}{e['verdict']:<8}{e['code']:<20}"
                         f"{e['stamps']:>6}{len(e['issues']):>6}  {recheck_txt}")
    s = report["summary"]
    lines.append("-" * 72)
    lines.append(f"合计：PASS {s['pass']} / WARN {s['warn']} / FAIL {s['fail']}"
                 + ("（FAIL 含 ERROR，审计无法完成等同不通过）" if report.get("has_error") else ""))
    for e in report["batches"]:
        if e["verdict"] == "PASS":
            continue
        for i in e["issues"]:
            lines.append(f"  [{e['batch']}] {i['verdict']} {i['id']}: {i['detail']}")
    return "\n".join(lines)


def write_json_report(report: dict, path) -> Path:
    """写 JSON 报告（自动创建父目录）。返回写入路径。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="中央兜底批次门禁审计（回执链校验 + 确定性门禁复检）")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--batch", "-b", metavar="ID",
                      help="只审计指定批次（batch048 / 048）")
    mode.add_argument("--all", action="store_true",
                      help="审计 最终产物/中间产物/质检报告 下的全部批次")
    mode.add_argument("--changed-only", action="store_true",
                      help="只审计本次 git diff 涉及的批次（基线不可解时回退为有回执的批次）")
    ap.add_argument("--strict", action="store_true",
                    help="把历史遗留缺回执（LEGACY_UNSTAMPED）从 WARN 升为 FAIL")
    ap.add_argument("--recheck", action="store_true",
                    help="对存在的题目数组产物重跑 python -m scripts.validate")
    ap.add_argument("--json-out", metavar="F", default=None, help="JSON 报告输出路径")
    ap.add_argument("--base", metavar="PATH", default=None,
                    help="仓库根（默认脚本所在仓库；临时目录审计用）")
    ap.add_argument("--since", metavar="REV", default=None,
                    help=f"--changed-only 的基线版本（默认 {DEFAULT_SINCE}）")
    ap.add_argument("--limit", type=int, default=None, metavar="N",
                    help="最多审计 N 个批次（按批次号升序）")
    return ap


def main(argv=None) -> int:
    """CLI 入口，返回退出码（0/1/2）。可被单测直接调用。"""
    for _s in (sys.stdout, sys.stderr):  # Windows 控制台 GBK：中文输出兜底
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:  # --help / 参数错误：正常返回退出码，不直接杀掉调用方
        code = exc.code
        return int(code) if isinstance(code, int) else 2

    base = Path(args.base).resolve() if args.base else BASE
    if not base.is_dir():
        print(f"[ERROR] --base 不是目录：{base}", file=sys.stderr)
        return 2
    if args.limit is not None and args.limit < 0:
        print("[ERROR] --limit 不能为负数", file=sys.stderr)
        return 2

    since = None
    fallback = False
    fallback_reason = None
    if args.batch:
        batch_id = normalize_batch_id(args.batch)
        if batch_id is None:
            print(f"[ERROR] 非法批次 ID：{args.batch!r}（示例 batch048）", file=sys.stderr)
            return 2
        mode = "batch"
        batches = [batch_id]
    elif args.all:
        mode = "all"
        batches = discover_batches(base)
    else:
        mode = "changed-only"
        since = args.since or DEFAULT_SINCE
        paths, err = git_changed_paths(since, base)
        if err:
            fallback = True
            fallback_reason = err
            batches = ledger_batches(base)
        else:
            batches = batches_from_changed_paths(paths)

    if args.limit is not None:
        batches = batches[:args.limit]

    entries = []
    for batch_id in batches:
        entry, candidates = evaluate_batch(batch_id, base, strict=args.strict)
        if args.recheck:
            items, issues = recheck_batch(batch_id, candidates, base=base)
            entry["recheck"] = items
            entry["issues"].extend(issues)
            finalize(entry)
        entries.append(entry)

    summary = {"pass": 0, "warn": 0, "fail": 0}
    for e in entries:
        if e["verdict"] == "PASS":
            summary["pass"] += 1
        elif e["verdict"] == "WARN":
            summary["warn"] += 1
        else:  # FAIL / ERROR 都算不通过
            summary["fail"] += 1

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "base": str(base),
        "since": since,
        "fallback": fallback,
        "fallback_reason": fallback_reason,
        "strict": bool(args.strict),
        "recheck_enabled": bool(args.recheck),
        "has_error": any(e["verdict"] == "ERROR" for e in entries),
        "batches": entries,
        "summary": summary,
    }

    print(format_human(report))

    if args.json_out:
        try:
            write_json_report(report, args.json_out)
        except OSError as exc:
            print(f"[ERROR] JSON 报告写盘失败：{exc}", file=sys.stderr)
            return 2

    return 1 if summary["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
