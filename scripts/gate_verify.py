#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_verify.py — 消费方验上游：验真阶段门槛回执（P0-B）

要解决的问题
------------
gate_stamp.py 只提供「记录 + 验真」原语，但下游 Agent（MedFix / MedReview /
编排者 / 人工复核）需要一条能直接跑的命令回答三件事：

1. 上游阶段到底有没有真正跑过门禁？（回执在不在、链是否自洽）
2. 我拿到的产物是不是门禁通过时的那一份？（字节级 sha256）
3. 被拒了下一步该跑什么命令？

本脚本就是那个「消费方入口」：不重算判定、不跑门禁、不写回执链，只把
gate_stamp.verify() 的结论翻译成可执行的 CLI 结论 + 完整 JSON 报告。

用法
----
    # 未传 --artifact：用该阶段「应有产物」做覆盖校验（a5/r* 无预期产物时 SKIP）
    python scripts/gate_verify.py --batch batch048 --stage a3

    # 校验指定产物是否被该阶段回执覆盖（相对仓库根或绝对路径均可）
    python scripts/gate_verify.py --batch batch048 --stage a3 \
        --artifact 质检报告/batch048/A3_质检报告.json

    # 机器消费：完整 JSON 报告；CI / 子 Agent 只读 --quiet 的一行结论
    python scripts/gate_verify.py --batch batch048 --stage a3 \
        --json-out reports/gate/verify_batch048_a3.json
    python scripts/gate_verify.py --batch batch048 --stage a3 --quiet

    # 严格模式：补录（provenance=backfill）回执不算通过；WARN 也算失败
    python scripts/gate_verify.py --batch batch048 --stage a4 --strict

退出码
------
0 = PASS / WARN（--strict 时 WARN 视为失败 → 1）
1 = FAIL
2 = 参数 / 环境错误

职责边界（诚实声明，别指望它做不到的事）
----------------------------------------
1. 判定唯一来源是 gate_stamp.verify()；本脚本只做参数归一、覆盖校验的分支
   选择、人类可读输出与退出码映射，不另立第二套判定口径。
2. 覆盖校验路径统一按 --base（默认仓库根）解析成绝对路径再交给
   gate_stamp.verify()——后者的 rel() 固定以仓库根为基准。
3. 本脚本只读：不写回执链、不改 workflow_state、不跑 git。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCRIPTS = BASE / "scripts"
for _p in (str(BASE), str(SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gate_stamp as gs  # noqa: E402  回执链唯一事实来源（记录 + 验真原语）

VERDICT_ICON = {"PASS": "✅", "WARN": "⚠️", "FAIL": "🛑"}
CHECK_ICON = {"PASS": "✓", "WARN": "!", "FAIL": "✗", "SKIP": "-"}


# ── 路径归一 ────────────────────────────────────────────
def prev_stage(stage: str):
    """按 gate_stamp.STAGES 的全局阶段序列取上一阶段（用于「先跑上游」提示）。"""
    try:
        idx = gs.STAGES.index(stage)
    except ValueError:
        return None
    return gs.STAGES[idx - 1] if idx > 0 else None


def driver_cmd(batch: str, stage: str) -> str:
    """重跑某阶段门禁的确定性命令（门禁唯一执行面）。"""
    return f"python scripts/batch_driver.py check --batch {batch} --stage {stage}"


def audit_cmd(batch: str) -> str:
    """中央兜底审计命令（链被删改时先看全局结论）。"""
    return f"python scripts/gate_audit.py --batch {batch}"


def normalize_path(value, base: Path) -> str:
    """把 --artifact / --ledger 归一成绝对路径。

    规则：相对路径按 --base（默认仓库根）解析；绝对路径原样 resolve。
    gate_stamp.append_stamp() 记录产物时也做 resolve + rel()，两处归一一致，
    覆盖校验才不会因为 Windows 大小写/斜杠/相对路径差异误判。
    """
    p = Path(value)
    if not p.is_absolute():
        p = Path(base) / p
    return str(p.resolve())


def normalize_artifacts(values, base: Path):
    """批量归一 --artifact 路径。"""
    return [normalize_path(v, base) for v in values]


# ── FAIL/WARN → 「怎么办」────────────────────────────────
def fix_hint_for(code: str, batch: str, stage: str, strict: bool = False):
    """把 verdict code 翻译成（fix hint, 下一步命令）。未知码给通用兜底。"""
    upstream = prev_stage(stage) or stage
    rerun = driver_cmd(batch, stage)
    if code == "LEDGER_MISSING":
        return ("该批次没有回执链（门禁执行未被记录，下游无法验真）："
                "先跑上游阶段生成回执，再重跑本阶段", driver_cmd(batch, upstream))
    if code == "LEDGER_CORRUPT":
        return (f"回执链 JSON 无法解析：检查 最终产物/{batch}/_gate_ledger.json 的编码/完整性"
                "（可从版本库恢复，禁止手工编辑）", audit_cmd(batch))
    if code == "STAGE_MISSING":
        return (f"回执链里没有 {stage} 阶段（该门禁被跳过）："
                f"先跑上游阶段 {upstream}，再重跑 {stage}", driver_cmd(batch, upstream))
    if code == "ARTIFACT_MISMATCH":
        return (f"回执记录的产物在门禁之后被改过：重跑 {stage} 阶段门禁，"
                "让回执重新绑定当前字节", rerun)
    if code == "ARTIFACT_MISSING":
        return (f"回执记录的产物已不存在：先重新产出该产物，再重跑 {stage} 阶段门禁", rerun)
    if code in ("CHAIN_BROKEN", "SEQ_MISMATCH"):
        return ("回执链被删/改（哈希或顺序不自洽）：从版本库恢复 _gate_ledger.json，"
                "或按审计结论重跑受影响阶段；不要手工编辑 ledger", audit_cmd(batch))
    if code == "ARTIFACT_NOT_COVERED":
        return (f"目标产物未被 {stage} 回执覆盖：核对产物路径是否写错；"
                f"确认无误后重跑 {stage} 阶段门禁", rerun)
    if code == "STAGE_BACKFILL":
        if strict:
            return ("回执是补录（provenance=backfill），--strict 下不算数："
                    "重跑该阶段门禁生成 driver 回执", rerun)
        return ("回执是补录（provenance=backfill），门禁是否真跑过无法证明"
                "（--strict 下判失败）：建议重跑该阶段门禁", rerun)
    return ("回执验真未通过：按 checks / issues 里的失败项修复后重跑该阶段门禁", rerun)


# ── 核心：委托 gate_stamp.verify + 覆盖校验分支选择 ──────
def verify_stage(batch: str, stage: str, base=BASE, ledger=None, artifacts=(), strict=False) -> dict:
    """验真一个阶段，返回可直接序列化的完整报告（不写任何文件）。

    覆盖校验分支：
    - 传了 --artifact：要求回执覆盖这些产物（相对仓库根或绝对路径均可）；
    - 未传：用 gate_stamp.expected_artifacts() 的「该阶段应有产物」做覆盖校验；
    - 该阶段本无预期产物（a5/r* 等）或产物均不存在：覆盖校验 SKIP，不判失败。
    """
    base = Path(base)
    ledger_arg = normalize_path(ledger, base) if ledger else None
    explicit = list(artifacts or ())

    if explicit:
        required = normalize_artifacts(explicit, base)
        mode = "explicit"
    else:
        required = [str(Path(p).resolve()) for p in gs.expected_artifacts(batch, stage, base)]
        mode = "expected" if required else "skip"

    report = gs.verify(
        batch_id=batch,
        stage=stage,
        base=base,
        path=ledger_arg,
        require_artifacts=required or None,
        allow_backfill=not strict,
    )

    # 补一条显式 coverage 记录：SKIP 也是「验过了，不适用」，避免消费方误以为漏检。
    if not any(c.get("id") == "coverage" for c in report["checks"]):
        if report["code"] in ("LEDGER_MISSING", "LEDGER_CORRUPT"):
            detail = "回执链缺失/损坏，覆盖校验未执行"
        elif mode == "skip":
            detail = "该阶段无预期产物（或产物均不存在），跳过覆盖校验"
        else:
            detail = "覆盖校验未执行"
        report["checks"].append({"id": "coverage", "status": "SKIP", "detail": detail})
    coverage = next(c for c in report["checks"] if c.get("id") == "coverage")

    report.update({
        "base": str(base),
        "strict": bool(strict),
        "coverage_mode": mode,
        "required_artifacts": [gs.rel(p, base) for p in required],
        "coverage": {"mode": mode, "status": coverage["status"], "detail": coverage["detail"]},
    })

    report["fix_hint"], report["next_command"] = (None, None)
    if report["verdict"] in ("FAIL", "WARN"):
        report["fix_hint"], report["next_command"] = fix_hint_for(
            report["code"], batch, stage, strict=strict)
    report["exit_code"] = exit_code_for(report, strict)
    return report


def exit_code_for(report: dict, strict: bool = False) -> int:
    """退出码映射：FAIL → 1；WARN 在 --strict 下 → 1；其余 PASS/WARN → 0。"""
    if report.get("verdict") == "FAIL":
        return 1
    if report.get("verdict") == "WARN" and strict:
        return 1
    return 0


# ── 输出 ────────────────────────────────────────────────
def format_human(report: dict, quiet: bool = False) -> str:
    """人类可读输出：结论 → 为什么 → 怎么办 + 下一步命令。"""
    batch, stage = report["batch"], report["stage"]
    verdict, code = report["verdict"], report["code"]
    if quiet:
        line = f"{batch}/{stage}: {verdict} {code}"
        if report.get("next_command"):
            line += f" | 下一步: {report['next_command']}"
        return line

    lines = [f"{VERDICT_ICON.get(verdict, '?')} {batch}/{stage} {verdict} {code}"]
    attention = [c for c in report.get("checks", ()) if c.get("status") in ("FAIL", "WARN")]
    if attention:
        for c in attention:
            lines.append(f"   {CHECK_ICON.get(c['status'], '?')} {c['id']}: {c['detail']}")
    else:
        summary = " · ".join(f"{c['id']}={c['status']}" for c in report.get("checks", ()))
        if report.get("stamp_seq"):
            summary += f" · 回执 seq={report['stamp_seq']}"
        lines.append(f"   检查: {summary}")
    if report.get("fix_hint"):
        lines.append(f"   ↳ 怎么办: {report['fix_hint']}")
    if report.get("next_command"):
        lines.append(f"   ↳ 下一步命令: {report['next_command']}")
    return "\n".join(lines)


def write_report(report: dict, json_out) -> str:
    """写完整 JSON 报告（父目录自动创建）。返回实际写入路径。"""
    out = Path(json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)


def _ensure_utf8_console() -> None:
    """Windows 控制台默认 cp936，emoji 会炸；仅在 CLI 场景兜底重配 stdout/stderr。"""
    if "pytest" in sys.modules:
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


# ── CLI ─────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="消费方验上游：验真阶段门槛回执（只读，不跑门禁）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python scripts/gate_verify.py --batch batch048 --stage a3\n"
               "  python scripts/gate_verify.py --batch batch048 --stage a3 "
               "--artifact 质检报告/batch048/A3_质检报告.json\n"
               "  python scripts/gate_verify.py --batch batch048 --stage a3 --quiet\n"
               "  python scripts/gate_verify.py --batch batch048 --stage a4 --strict "
               "--json-out reports/gate/verify_batch048_a4.json",
    )
    ap.add_argument("--batch", "-b", required=True, help="批次 id，如 batch048")
    ap.add_argument("--stage", "-s", required=True, choices=list(gs.STAGES),
                    help=f"阶段（{'/'.join(gs.STAGES)}）")
    ap.add_argument("--artifact", nargs="+", action="append", default=[], metavar="PATH",
                    help="要求回执覆盖的产物路径（相对仓库根或绝对路径；可多次/多个）")
    ap.add_argument("--json-out", default=None, metavar="FILE", help="写完整 JSON 报告")
    ap.add_argument("--ledger", default=None, metavar="PATH",
                    help="回执链路径（默认 <base>/最终产物/<batch>/_gate_ledger.json）")
    ap.add_argument("--strict", action="store_true",
                    help="严格模式：补录回执不算通过；WARN 也返回 1")
    ap.add_argument("--quiet", "-q", action="store_true", help="只输出一行结论")
    ap.add_argument("--base", default=str(BASE), metavar="PATH",
                    help=f"仓库基准目录（默认 {BASE}）")
    return ap


def _env_error(args, base: Path):
    """参数/环境预检；返回错误说明字符串，无问题返回 None（→ 退出码 2）。"""
    if not str(args.batch or "").strip():
        return "缺少 --batch"
    if not base.exists():
        return f"--base 不存在: {base}"
    if not base.is_dir():
        return f"--base 不是目录: {base}"
    if args.ledger and Path(normalize_path(args.ledger, base)).is_dir():
        return f"--ledger 指向目录而非回执文件: {args.ledger}"
    return None


def main(argv=None) -> int:
    # 先兜底控制台编码：argparse 的错误提示（stderr）也走这里，Windows cp936 下
    # 中文与 emoji 必须按 utf-8 输出才不炸。
    _ensure_utf8_console()
    args = build_parser().parse_args(argv)
    base = Path(args.base)
    err = _env_error(args, base)
    if err:
        print(f"[ERROR] 参数/环境错误: {err}", file=sys.stderr)
        return 2

    artifacts = [item for group in (args.artifact or ()) for item in group]
    report = verify_stage(args.batch, args.stage, base=base, ledger=args.ledger,
                          artifacts=artifacts, strict=args.strict)

    print(format_human(report, quiet=args.quiet))
    if args.json_out:
        try:
            write_report(report, args.json_out)
        except OSError as exc:
            print(f"[ERROR] 写 JSON 报告失败: {args.json_out}: {exc}", file=sys.stderr)
            return 2
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
