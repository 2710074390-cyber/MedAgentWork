#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批次产物入库（P1-3）—— 把「签收批次必须入库」变成可执行判定。

要解决的问题
------------
`reports/` 被 gitignore，`最终产物/` 又没有入库纪律，结果是：
CI 的 `gate_audit --changed-only` 只能看见「已提交」的批次。一个批次在本地跑完四道门禁、
回执链也写了，只要没 `git add`，CI 就完全不知道它存在 —— 中央兜底失效。

政策（2026-11-05 用户裁定）
--------------------------
- **历史批次（≤ batch047）不回填**，已入库的保持原样，不进不出；
- **batch048 起，签收后的「产物 + 回执链」必须入库**；
- 入库范围按白名单（见下），`_backup/`、`*.html`、`*.tmp` 等一律不入库。

为什么用白名单而不是 `.gitignore` 黑名单
----------------------------------------
黑名单只能挡住你想到的文件；白名单漏了会立刻在 `check` 里暴露。
本模块的 `check` 是判定真源：`signoff_batch.py` 用它决定签收后暂存什么，
`gate_audit.py --require-tracked` 用它决定 CI 是否判红。

职责边界
--------
1. 只做「列清单 / 暂存 / 验是否被跟踪」三件事，不改产物、不写回执链、不提交。
2. `stage` 只 `git add`，不 `git commit`：提交时机与拆分由人决定。
3. 已归档批次（`最终产物/{batch}/` 不存在）一律 SKIP——归档后路径变了，
   证据绑定由 `archive/{batch}_归档说明.md` 的映射负责，不在本模块追溯。

用法
----
    python scripts/batch_artifacts.py list  --batch batch048
    python scripts/batch_artifacts.py stage --batch batch048 --dry-run
    python scripts/batch_artifacts.py stage --batch batch048
    python scripts/batch_artifacts.py check --batch batch048          # exit 1 = 有必需文件未入库
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))

import gate_stamp as gs  # noqa: E402  批次号判定（required_for）唯一真源

# 必需：缺一个就无法在 CI 上复现「这批真的过了门禁」
# 注意 2026-11-05 复核修正：追溯日志的真实文件名有两种（AGENT4_追溯日志.json /
# {batch}_A4_追溯日志.json），原来的 "*A4_追溯日志.json" 匹配不到 AGENT4_ 前缀，
# 导致「必需=4 类」实际只有 3 类生效。这里按后缀匹配，两种命名都算必需。
REQUIRED_PATTERNS = (
    "_gate_ledger.json",          # 回执链（P0）：产物字节 + 门禁执行的绑定
    "ALL_questions_FIXED.json",   # 题目批次的主交付物（押题卷等另由回执绑定）
    "*追溯日志.json",             # A4 溯源（HC-13 source_file_synced）
    "review_queue.json",          # 人工复核队列（HC-28 交付必须带队列）
)

# 交付/说明：有就入库，缺失不算失败
DELIVERABLE_PATTERNS = (
    "ALL_questions_FIXED.md",     # 人读交付件
    "*签收单.md",
    "AGENT4_修改声明.md",
    "A4_补丁明细.json",
    "escalations_for_human.md",
)

# 即使被白名单通配命中也不入库
EXCLUDE_DIRS = ("_backup",)
EXCLUDE_SUFFIXES = (".tmp", ".bak", ".html")


def batch_dir(batch: str, base: Path = BASE) -> Path:
    return Path(base) / "最终产物" / batch


def _matches(name: str, patterns) -> bool:
    return any(fnmatch(name, pat) for pat in patterns)


def _iter_files(batch: str, base: Path = BASE):
    """遍历批次目录下的文件（跳过 _backup 等排除目录与排除后缀）。"""
    d = batch_dir(batch, base)
    if not d.is_dir():
        return
    for p in sorted(d.rglob("*")):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(d).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts[:-1]):
            continue
        if p.suffix.lower() in EXCLUDE_SUFFIXES:
            continue
        yield p


def ledger_bound_paths(batch: str, base: Path = BASE):
    """回执链里记录的、位于本批次目录内的产物（相对路径，无论文件是否还在）。

    为什么需要它：押题卷 / 复习资料批次的产物名各不相同（如 押题卷_xxx_100题.json），
    按文件名白名单会漏判。回执是「这批过了什么门禁」的唯一记录，按它来定证据最准。
    """
    ledger, err = gs.load_ledger(batch, base)
    if err or ledger is None:
        return []
    d = batch_dir(batch, base)
    out = []
    for st in ledger.get("stamps") or ():
        for art in st.get("artifacts") or ():
            raw = str(art.get("path") or "")
            if not raw:
                continue
            p = Path(raw) if Path(raw).is_absolute() else Path(base) / raw
            if batch_dir(batch, base).is_dir():
                try:
                    p.resolve().relative_to(d.resolve())
                except Exception:
                    continue
            rel_p = gs.rel(p, base)
            if rel_p not in out:
                out.append(rel_p)
    return out


def classify(batch: str, base: Path = BASE) -> dict:
    """把批次目录下的现存文件分成 required / deliverable / other 三类。

    other 只做展示（例如 A4 补丁明细的变体名），不参与 stage —— 白名单之外的文件
    默认不入库，宁可漏报让人补白名单，也不让噪音进版本库。
    """
    required, deliverable, other = [], [], []
    for p in _iter_files(batch, base):
        item = {"path": gs.rel(p, base), "name": p.name, "bytes": p.stat().st_size}
        if _matches(p.name, REQUIRED_PATTERNS):
            required.append(item)
        elif _matches(p.name, DELIVERABLE_PATTERNS):
            deliverable.append(item)
        else:
            other.append(item)

    # 回执链绑定的产物一律升级为「必需」（白名单之外的名字也不漏）。
    bound = set(ledger_bound_paths(batch, base))
    if bound:
        promoted = [x for x in other if x["path"] in bound]
        other = [x for x in other if x["path"] not in bound]
        required.extend(promoted)
        known = {x["path"] for x in required + deliverable}
        for path in sorted(bound - known):
            p = Path(base) / path
            if p.is_file():
                required.append({"path": path, "name": p.name, "bytes": p.stat().st_size})
    return {"batch": batch, "dir": gs.rel(batch_dir(batch, base), base),
            "required": required, "deliverable": deliverable, "other": other}


def stage_paths(batch: str, base: Path = BASE):
    """要 `git add` 的路径（必需 + 交付）。返回绝对路径列表。"""
    info = classify(batch, base)
    return [Path(base) / x["path"] for x in info["required"] + info["deliverable"]]


def is_tracked(path: Path, base: Path = BASE) -> bool:
    """该文件是否已被 git 跟踪。用退出码判定，不解析（中文路径会被 git 转义）。"""
    rel_p = gs.rel(path, base)
    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", rel_p],
        cwd=str(base), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode == 0


def check(batch: str, base: Path = BASE, require_deliverable: bool = False) -> dict:
    """检查批次产物入库状态。返回结构化结论（不改任何文件）。

    verdict:
      - SKIP  批次目录不存在（已归档）或批次 < STAMP_REQUIRED_MIN_BATCH（历史批次）
      - PASS  必需文件（及可选交付件）均已被 git 跟踪
      - FAIL  存在未入库的必需文件
    """
    report = {"batch": batch, "verdict": "PASS", "code": "ARTIFACTS_TRACKED",
              "dir": gs.rel(batch_dir(batch, base), base), "required": [], "deliverable": [],
              "untracked_required": [], "untracked_deliverable": [], "missing_required": []}
    if not batch_dir(batch, base).is_dir():
        report.update(verdict="SKIP", code="BATCH_DIR_ABSENT",
                      detail="批次目录不存在（已归档或未产出），不追溯")
        return report
    if not gs.required_for(batch):
        report.update(verdict="SKIP", code="LEGACY_NOT_REQUIRED",
                      detail=f"批次号 < {gs.STAMP_REQUIRED_MIN_BATCH:03d}，历史批次不回填")
        return report

    info = classify(batch, base)
    report["required"] = [x["path"] for x in info["required"]]
    report["deliverable"] = [x["path"] for x in info["deliverable"]]

    # 回执链是硬要求；它绑定的产物（见 classify）是硬证据。
    # 不再硬编码 ALL_questions_FIXED.json —— 押题卷/复习资料批次的产物名不同，
    # 硬编码会把合法批次判成「必需文件不存在」而永远无法入库。
    if not any(x["name"] == "_gate_ledger.json" for x in info["required"]):
        report["missing_required"].append(f"{report['dir']}/_gate_ledger.json")
    bound = ledger_bound_paths(batch, base)
    for path in bound:
        if not (Path(base) / path).is_file():
            report["missing_required"].append(path)
    if not bound:
        # 回执在、却一条产物都没绑定：门禁证据不完整（例如只有 r0/r1 空回执），
        # 不能因为「文件名对不上白名单」就静默算通过。
        report["missing_required"].append(
            f"{report['dir']}/（回执链未绑定任何产物：门禁证据不完整）")

    for x in info["required"]:
        if not is_tracked(Path(base) / x["path"], base):
            report["untracked_required"].append(x["path"])
    for x in info["deliverable"]:
        if not is_tracked(Path(base) / x["path"], base):
            report["untracked_deliverable"].append(x["path"])

    if report["untracked_required"] or report["missing_required"]:
        report["verdict"], report["code"] = "FAIL", "ARTIFACT_UNTRACKED"
        report["detail"] = (f"{len(report['untracked_required'])} 个必需文件未入库"
                           f"，{len(report['missing_required'])} 个必需文件不存在")
    elif require_deliverable and report["untracked_deliverable"]:
        report["verdict"], report["code"] = "FAIL", "ARTIFACT_UNTRACKED"
        report["detail"] = f"{len(report['untracked_deliverable'])} 个交付件未入库"
    else:
        report["detail"] = "必需文件已全部入库"
    return report


def stage(batch: str, base: Path = BASE, dry_run: bool = False) -> dict:
    """`git add` 该批次的必需 + 交付文件。返回 {added, skipped, error}。

    只暂存、不提交；`reports/` 不在范围内（它本就被 gitignore）。
    """
    result = {"batch": batch, "added": [], "skipped": [], "error": None, "dry_run": dry_run}
    if not batch_dir(batch, base).is_dir():
        result["error"] = f"批次目录不存在：{gs.rel(batch_dir(batch, base), base)}（已归档？）"
        return result
    if not gs.required_for(batch):
        result["error"] = (f"批次号 < {gs.STAMP_REQUIRED_MIN_BATCH:03d}：历史批次不回填，"
                          "如需入库请手工 git add")
        return result

    paths = stage_paths(batch, base)
    todo = [p for p in paths if p.is_file()]
    if not todo:
        result["error"] = "没有可入库的文件（先产出产物并跑门禁）"
        return result
    result["skipped"] = [gs.rel(p, base) for p in paths if not p.is_file()]
    if dry_run:
        result["added"] = [gs.rel(p, base) for p in todo]
        return result

    proc = subprocess.run(
        ["git", "add", "--"] + [str(p) for p in todo],
        cwd=str(base), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        result["error"] = (proc.stderr or proc.stdout or "git add 失败").strip()
        return result
    result["added"] = [gs.rel(p, base) for p in todo]
    return result


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv=None) -> int:
    for _s in (sys.stdout, sys.stderr):  # Windows 控制台 GBK 兜底
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(
        description="批次产物入库：列清单 / git add / 校验是否已跟踪（P1-3）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python scripts/batch_artifacts.py list  --batch batch048\n"
               "  python scripts/batch_artifacts.py stage --batch batch048 --dry-run\n"
               "  python scripts/batch_artifacts.py check --batch batch048\n")
    ap.add_argument("action", choices=["list", "stage", "check"])
    ap.add_argument("--batch", "-b", required=True)
    ap.add_argument("--base", default=None, help="仓库根（临时目录测试用）")
    ap.add_argument("--dry-run", action="store_true", help="stage 只看会加什么")
    ap.add_argument("--require-deliverable", action="store_true",
                    help="check 时交付件未入库也判 FAIL")
    ap.add_argument("--json", action="store_true", help="输出 JSON（默认人读）")
    args = ap.parse_args(argv)

    base = Path(args.base).resolve() if args.base else BASE
    if not base.is_dir():
        print(f"[ERROR] --base 不是目录：{base}", file=sys.stderr)
        return 2

    if args.action == "list":
        info = classify(args.batch, base)
        if args.json:
            _print(info)
        else:
            print(f"{info['batch']}  {info['dir']}")
            for key, label in (("required", "必需"), ("deliverable", "交付"), ("other", "其它（不入库）")):
                rows = info[key]
                print(f"\n[{label}] {len(rows)} 个")
                for x in rows:
                    print(f"  {x['path']}  ({x['bytes']:,} B)")
        return 0

    if args.action == "stage":
        r = stage(args.batch, base, dry_run=args.dry_run)
        _print(r) if args.json else print(
            ("[dry-run] 将暂存：\n" if r["dry_run"] else "已暂存：\n")
            + "\n".join(f"  {x}" for x in r["added"])
            + (f"\n[!] {r['error']}" if r["error"] else "")
            + ("\n[提醒] 只 add 未 commit，提交时机由你决定" if not r["dry_run"] and r["added"] else ""))
        return 0 if r["error"] is None else 1

    r = check(args.batch, base, require_deliverable=args.require_deliverable)
    if args.json:
        _print(r)
    else:
        icon = {"PASS": "✅", "FAIL": "🛑", "SKIP": "⏭️"}[r["verdict"]]
        print(f"{icon} {r['batch']}: {r['verdict']} {r['code']} — {r['detail']}")
        for p in r["untracked_required"]:
            print(f"   ✗ 必需未入库: {p}")
        for p in r["missing_required"]:
            print(f"   ✗ 必需不存在: {p}")
        for p in r["untracked_deliverable"]:
            print(f"   ! 交付件未入库: {p}")
        if r["verdict"] == "FAIL":
            print(f"   ↳ 下一步: python scripts/batch_artifacts.py stage --batch {r['batch']}")
    return 0 if r["verdict"] != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())
