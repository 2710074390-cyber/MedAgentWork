#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""host_matrix_check.py — 三档宿主回归矩阵（H5 · 2026-11-07）

验证一件事：**在完全不调用 LLM 的前提下**，L2 / L1 / L0 三种宿主能否从
「上一阶段 PASS」推进到「下一阶段的门禁命令」，且消费的是同一份交接包。

纪律：
  - 纯标准库；不写仓库文件（交接包落临时目录）；
  - 不改批次产物、不写回执、不跑门禁（只校验命令字符串）；
  - 断言「包里没有宿主工具名」，这是跨宿主方案的核心不变量。

用法：
    python scripts/host_matrix_check.py --matrix
    python scripts/host_matrix_check.py --matrix --batch batch048 --json
退出码：0 全通过 / 1 有失败 / 2 参数或环境错误
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE / "scripts"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import batch_driver as bd  # noqa: E402

FORBIDDEN_TOOL_NAMES = (
    "subagent", "read 工具", "后台运行", "PowerShell", "Bash 工具",
    "execute_command", "sendPrompt", "Task(",
)
LEVELS = ("L2", "L1", "L0")


def bundle_hash(bundle) -> str:
    body = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _checks_common(bundle, level, rows):
    def chk(name, cond, detail=""):
        rows.append({"level": level, "check": name, "ok": bool(cond), "detail": detail})

    text = json.dumps(bundle, ensure_ascii=False)
    hits = [t for t in FORBIDDEN_TOOL_NAMES if t in text]
    chk("no_host_tool_names", not hits, "命中：" + ", ".join(hits) if hits else "包里只有数据与命令")
    chk("role_skill_exists", (BASE / bundle["role_skill"]).is_file(), bundle["role_skill"])
    chk("gate_is_driver_check", bundle["gate"].startswith("python scripts/batch_driver.py check"),
        bundle["gate"])
    chk("preflight_is_gate_verify",
        bundle["preflight"] is None or bundle["preflight"].startswith("python scripts/gate_verify.py"),
        str(bundle["preflight"]))
    chk("write_scope_matches_parallel",
        bundle["parallel_safe"] == (bundle["write_scope"] != "question_bank"),
        f"{bundle['write_scope']} / parallel={bundle['parallel_safe']}")
    chk("done_criteria_present", len(bundle["done"]) >= 2, "；".join(bundle["done"]))
    chk("fingerprint_is_sha256", len(bundle.get("inputs_fingerprint") or "") == 64)
    chk("inputs_have_read", all(i.get("read") for i in bundle["inputs"]))


def _checks_l2(bundle, rows):
    rows.append({"level": "L2", "check": "parallel_safe_declared",
                 "ok": isinstance(bundle["parallel_safe"], bool),
                 "detail": "派生隔离子代理时按此字段决定是否并行"})


def _checks_l1(bundle, rows):
    ctx = BASE / bundle["ctx"]
    size = ctx.stat().st_size if ctx.is_file() else 0
    rows.append({"level": "L1", "check": "ctx_within_8k",
                 "ok": (not ctx.is_file()) or size <= 8192,
                 "detail": f"{bundle['ctx']} {size} bytes（不存在时视为由 build_batch_context 生成）"})
    need_selector = [i for i in bundle["inputs"] if i["read"] != "full" and not i.get("selector")]
    rows.append({"level": "L1", "check": "by_id_inputs_have_selector",
                 "ok": not need_selector,
                 "detail": "缺 selector：" + ", ".join(i["path"] for i in need_selector) if need_selector
                           else "非 full 读入均有 selector，单会话不整库读"})


def _checks_l0(bundle, rows):
    with tempfile.TemporaryDirectory(prefix="host_matrix_") as t:
        p = Path(t) / "a3.json"
        p.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = bd.main(["brief", "--batch", bundle["batch"],
                              "--stage", bundle["stage"], "--bundle", str(p)])
        except Exception as exc:  # brief 抛异常也算 L0 不可用
            rows.append({"level": "L0", "check": "brief_runs", "ok": False,
                         "detail": f"{type(exc).__name__}: {exc}"})
            return
        out = buf.getvalue()
        rows.append({"level": "L0", "check": "brief_runs", "ok": rc == 0,
                     "detail": f"exit {rc}；{len(out.splitlines())} 行"})
        rows.append({"level": "L0", "check": "brief_contains_gate",
                     "ok": bundle["gate"] in out, "detail": bundle["gate"]})
        rows.append({"level": "L0", "check": "brief_contains_role_skill",
                     "ok": bundle["role_skill"] in out, "detail": bundle["role_skill"]})


def run_matrix(batch: str = "batch048", stage: str = "a3"):
    try:
        _, data = bd.load_batch(batch)
    except Exception as exc:
        return {"ok": False, "error": f"load_batch({batch}): {exc}"}
    plan, _types = bd.plan_boundaries(batch, data)
    bundle = bd.build_handoff(batch, stage, plan, data)
    if bundle is None:
        return {"ok": False, "error": f"{stage} 不是派角色的阶段（纯门禁阶段不生成交接包）"}

    rows, hashes = [], []
    for level in LEVELS:
        # 每档重新构建一次，验证 driver 输出是确定性的（不是同一对象重复用）
        b = bd.build_handoff(batch, stage, plan, data)
        hashes.append(bundle_hash(b))
        _checks_common(b, level, rows)
        if level == "L2":
            _checks_l2(b, rows)
        elif level == "L1":
            _checks_l1(b, rows)
        else:
            _checks_l0(b, rows)

    rows.append({"level": "ALL", "check": "same_bundle_across_levels",
                 "ok": len(set(hashes)) == 1, "detail": ", ".join(h[:12] for h in hashes)})
    failed = [r for r in rows if not r["ok"]]
    return {
        "ok": not failed,
        "batch": batch,
        "stage": stage,
        "bundle_sha256": hashes[0],
        "levels": list(LEVELS),
        "checks": rows,
        "summary": f"{len(rows) - len(failed)}/{len(rows)} 通过",
        "failed": failed,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="三档宿主回归矩阵（H5）")
    ap.add_argument("--matrix", action="store_true", help="跑 L2/L1/L0 三档（默认也是全跑）")
    ap.add_argument("--batch", "-b", default="batch048")
    ap.add_argument("--stage", "-s", default="a3", choices=["a2", "a3", "a4", "a5"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rep = run_matrix(args.batch, args.stage)
    if rep.get("error"):
        print(f"[ERROR] {rep['error']}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(f"══ 三档宿主矩阵 ｜ {rep['batch']} / {rep['stage']} ｜ bundle {rep['bundle_sha256'][:12]}")
        cur = None
        for r in rep["checks"]:
            if r["level"] != cur:
                cur = r["level"]
                print(f"  [{cur}]")
            print(f"    {'✅' if r['ok'] else '🛑'} {r['check']}: {r['detail']}")
        print(f"══ {'PASS' if rep['ok'] else 'FAIL'} {rep['summary']}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
