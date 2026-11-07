#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_driver.py — 批次门禁唯一确定性执行面（SA-4）

为什么有这个脚本（2026-11-04，SA-4）：
    17 个门禁脚本的「跑哪个 / 按什么顺序 / 怎么解读 / 失败回退给谁」，此前写在
    .dsh/skills/medbatch/SKILL.md 的命令清单里，由 LLM 每次解读；同一门禁的判定还被
    3 处代码各写一遍。本脚本把这些收成一条命令：
        plan（只打印）→ check（执行 + 归一化四态）→ 结构化 JSON 证据

纪律（不可违反，见 reports/实施步骤与验收标准_调度与上下文层_20261104.md §0.2）：
    1. 不新增判定逻辑：判定一律以 gate_check / quality_gate / 各子门禁报告为准；
    2. 不改既有脚本退出码；per-script 映射见 EXIT_MAP；
    3. 解析失败 → unparsed[] + BLOCKED，绝不默认 PASS；
    4. --dry-run 只做存在性/可读性预检，不执行门禁、不写任何文件；
    5. 阶段图复用 gate_check.stage_sequence / infer_product_types，不另立第二套；
    6. PASS 才写回执：回执按 chain_prev 链式绑定「产物字节哈希 + 门禁证据哈希」，下游消费前
       先验上游回执（P0 防跳过，原语见 scripts/gate_stamp.py）。

用法：
    python scripts/batch_driver.py plan  --batch batch048 [--json]
    python scripts/batch_driver.py check --batch batch048 [--stage auto|r0|r1|a2|a3|a4|lv|a5|r2|r3|final|r4]
                                         [--json-out P] [--dry-run] [--no-halt] [--no-state-write]
                                         [--timeout 300] [--fail-fast]
                                         [--no-stamp] [--no-preflight] [--ledger P] [--base P]
    python scripts/batch_driver.py selftest [--fixture tests/fixtures/gates] [--json]
    python scripts/batch_driver.py brief   --batch batch048 --stage a3

H1/H2（2026-11-07，跨宿主可移植编排）：
    check 在 PASS 时按 plan 确定性给出 next_stage / next_action，并为下一阶段写
    中间产物/{batch}/_handoff/{stage}.json。交接包只描述「读什么 / 写什么 / 过什么门禁」，
    不含任何宿主工具名；哈希复用 gate_stamp.file_sha256。DSH / WorkBuddy / Trae / 人工
    消费同一份包，差异只在 host_level（见 scripts/host_bootstrap.py 桩标记）。

退出码：0 PASS / 1 BLOCKED / 2 ERROR / 3 仅 SKIP-WARN；brief 的 3 = 包已过期
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCRIPTS = BASE / "scripts"
for _p in (str(BASE), str(SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

if "pytest" not in sys.modules:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import gate_check as gc          # noqa: E402  阶段图与产品类型唯一来源
import gate_stamp as gs          # noqa: E402  门禁回执链（P0 防跳过）
import workflow_state as ws      # noqa: E402

DEFAULT_TIMEOUT = 300
FIXTURE_DIR = BASE / "tests" / "fixtures" / "gates"
DRIVER_VERSION = "batch_driver/2026-11-04"
# 必须构成回执链的阶段：交付物阶段。r* 是过程门禁（报告在 reports/ 不入库），不强制。
HARD_CHAIN_STAGES = ("a2", "a3", "a4", "lv", "a5", "final")

# ── per-script 退出码映射（不改既有脚本，只在这里解释）────────────
# 值含义：PASS / WARN / FAIL / SKIP / ERROR
EXIT_MAP = {
    "gate_check": {0: "PASS", 1: "FAIL", 2: "ERROR"},
    "quality_gate": {0: "PASS", 1: "FAIL", 2: "ERROR"},
    "validate": {0: "PASS", 1: "FAIL", 2: "ERROR"},
    # 这两个脚本的 2 是 SKIP / 输入缺失，不是崩溃
    "check_source_concepts": {0: "PASS", 1: "FAIL", 2: "SKIP"},
    "check_keypoint_coverage": {0: "PASS", 1: "FAIL", 2: "SKIP"},
    "check_learning_value": {0: "PASS", 1: "FAIL", 2: "ERROR"},
    "check_review_detail": {0: "PASS", 1: "FAIL", 2: "ERROR"},
    "real_question_cli": {0: "PASS", 1: "FAIL", 2: "ERROR"},
    "check_patch_integrity": {0: "PASS", 1: "FAIL", 2: "ERROR"},
}

APIECES = {"PASS", "WARN", "FAIL", "SKIP", "ERROR"}

FIX_HINTS = {
    "SHAPE_BLOOM": "MedQC: bloom_distribution.actual 用百分数扁平形态并按 bloom 字段重算",
    "SHAPE_SYNCED": "MedFix: 把 source_file_synced 提到追溯日志顶层（写入 execution_metadata 不算）",
    "SHAPE_KP_NO": "MedReview: 条号改用锚定清单第四节连续编号，逐字照录该条原文",
    "HC22": "编排者: 跑 real_question_cli.py plan 补齐考研/执医双族配额，或写 reduced/cancelled 理由",
    "HC13": "MedFix: 补 source_file_synced=true 并同步溯源文件",
    "HC20": "MedReview: 补 📌 重点原文（第X条）落点行，保留数值/时间窗/界值",
    "HC26": "MedReview: 按 D6 九槽位/模块八块补写（诊断/处置/案例/自测答案）",
    "UNPARSABLE": "人工: 报告不可解析，先检查文件编码与 JSON 完整性",
    "MISSING": "上游: 先产出该阶段产物再跑门禁",
    "DRIVER": "编排者: driver 环境/参数问题，先看 unparsed[].raw",
    "CHAIN": "编排者: 上游缺回执/回执与产物不符 → 不要跳过，先跑 batch_driver.py check --stage <上游阶段>",
    "STAMP": "编排者: 回执写不进去 → 检查 最终产物/<batch>/ 可写，再重跑本 boundary",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _result(gate, status, code=None, severity=None, file=None, locator=None,
            fix_hint=None, owner=None, evidence=None, raw=None):
    """统一结果形状；status ∈ PASS/WARN/FAIL/SKIP。"""
    if severity is None:
        severity = None if status == "PASS" else status
    return {
        "gate": gate,
        "status": status,
        "severity": severity,
        "code": code,
        "file": file,
        "locator": locator,
        "fix_hint": fix_hint,
        "owner": owner,
        "evidence": evidence or {},
        "raw": (raw or "")[:2000] or None,
    }


def _hint(code, owner=None):
    if not code:
        return None
    for k, v in FIX_HINTS.items():
        if str(code).upper().startswith(k.upper()):
            return v
    return FIX_HINTS["DRIVER"]


def owner_for_gate(gate_name, fallback=None):
    g = str(gate_name or "")
    if "GATE-A2" in g:
        return "MedGen"
    if "GATE-A3" in g:
        return "MedQC"
    if "GATE-A4" in g:
        return "MedFix"
    if "GATE-A5" in g or "GATE-LV" in g:
        return "MedReview"
    return fallback or "orchestrator"


# ── 基础 IO ──────────────────────────────────────────────
def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _latest(pattern: str):
    hits = [Path(p) for p in glob.glob(str(BASE / pattern))]
    if not hits:
        return None
    return max(hits, key=lambda p: p.stat().st_mtime)


def _run(argv, timeout=DEFAULT_TIMEOUT):
    t0 = time.time()
    try:
        cp = subprocess.run(
            argv, cwd=str(BASE), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return cp.returncode, (cp.stdout or "") + (cp.stderr or ""), round((time.time() - t0) * 1000, 1)
    except subprocess.TimeoutExpired:
        return None, f"TIMEOUT after {timeout}s", round((time.time() - t0) * 1000, 1)
    except Exception as exc:  # 环境问题
        return None, f"EXEC_ERROR {type(exc).__name__}: {exc}", 0


def _py(*args):
    return [sys.executable, *[str(a) for a in args]]


def _mapped(script: str, rc):
    if rc is None:
        return "ERROR"
    return EXIT_MAP.get(script, {0: "PASS", 1: "FAIL", 2: "ERROR"}).get(int(rc), "ERROR")


# ── 批量上下文 ───────────────────────────────────────────
def batch_number(batch_id: str):
    m = re.search(r"(\d{3})", str(batch_id or ""))
    return int(m.group(1)) if m else None


def load_batch(batch_id: str):
    state, err = ws.load_state()
    if err:
        raise RuntimeError(f"读取 workflow_state 失败: {err}")
    data = state.get(batch_id)
    if not isinstance(data, dict):
        raise KeyError(f"批次 {batch_id} 不在 workflow_state.json 中")
    return state, data


def needs_learning_value(batch_data: dict) -> bool:
    """schema>=2.0 即需要 LV。

    注意（实测偏差，已登记）：gate_check.stage_sequence 只认 == '2.0'，
    2.1/2.2 批次会被漏掉；driver 按 medbatch 规则（>=2.0）补插，并保留 gate_check
    作为基础序列来源，避免另立第二套。
    """
    if batch_data.get("learning_value_required"):
        return True
    raw = str(batch_data.get("item_schema_version") or "").strip()
    try:
        return float(raw) >= 2.0
    except Exception:
        return False


def plan_boundaries(batch_id: str, batch_data: dict):
    """返回该批次的 boundary 序列（单一事实来源：gate_check.stage_sequence）。"""
    types = gc.infer_product_types(batch_id, batch_data)
    seq = gc.stage_sequence(batch_id, batch_data)
    num = batch_number(batch_id)
    out = []
    if num is not None and num >= gc.QUALITY_STAGE_MIN_BATCH:
        out += ["r0", "r1"]
    for s in seq:
        out.append({
            "agent2_done": "a2",
            "agent3_done": "a3",
            "agent4_done": "a4",
            "learning_value": "lv",
            "final": "final",
        }.get(s, s))
    if "review_material" in types and "a5" not in out:
        out.insert(out.index("final") if "final" in out else len(out), "a5")
    if gc.is_question_bearing(types) and needs_learning_value(batch_data) and "lv" not in out:
        out.insert(out.index("a4") + 1 if "a4" in out else max(len(out) - 1, 0), "lv")
    if num is not None and num >= gc.QUALITY_STAGE_MIN_BATCH:
        idx = out.index("final") if "final" in out else len(out)
        for extra in ("r2", "r3"):
            if extra not in out:
                out.insert(idx, extra)
                idx += 1
        if "r4" not in out:
            out.append("r4")
    return out, types


BOUNDARY_BRIEF = {
    "r0": "R0 需求评审（quality_gate advisory）",
    "r1": "R1 开发实现（quality_gate advisory）",
    "a2": "GATE-A2 结构自检（validate R1–R13）",
    "a3": "GATE-A3 质检裁决（形状归一 + gate_check）",
    "a4": "GATE-A4 修复裁决（NOOP/溯源 + gate_check）",
    "lv": "门禁LV 学习价值（check_learning_value + gate_check）",
    "a5": "门禁A5 复习资料（重点覆盖 + 详细度）",
    "r2": "R2 测试验证（quality_gate advisory --with-tests）",
    "r3": "R3 发布上线（quality_gate enforce）",
    "final": "终审（HC-22 配额 + R0–R3 + P9 + Bloom + gate_check final）",
    "r4": "R4 运行复盘（quality_gate r4 --commit）",
}


def _paths(batch_id: str):
    return {
        "a2": BASE / "中间产物" / batch_id / "ALL_questions.json",
        "a3a": BASE / "质检报告" / batch_id / "A3_质检报告.json",
        "a3b": BASE / "质检报告" / f"{batch_id}_质检报告.json",
        "a4": BASE / "最终产物" / batch_id / "ALL_questions_FIXED.json",
        "a4_md": BASE / "最终产物" / batch_id / "ALL_questions_FIXED.md",
        "a4_log": BASE / "最终产物" / batch_id / "AGENT4_追溯日志.json",
        "plan": BASE / "中间产物" / batch_id / "real_question_plan.json",
    }


# ── 回执链：让「跳过门禁」在下游硬阻断（P0）──────────────
def _gate_report_paths(results):
    """从门禁结果里收集可入库的证据文件（reports/ 下的报告）；库存的才算数。"""
    out = []
    for r in results:
        rep = (r.get("evidence") or {}).get("report")
        if not rep:
            continue
        p = Path(rep) if Path(str(rep)).is_absolute() else BASE / rep
        if p.is_file() and str(p) not in out:
            out.append(str(p))
    return out


def boundary_artifacts(ctx, boundary):
    """该 boundary 的交付物（写回执时按字节绑定）；a5 是复习资料 md。"""
    if boundary == "a5":
        md = _find_review_md(ctx.data)
        return [md] if md else []
    return gs.expected_artifacts(ctx.batch, boundary, ctx.base)


def preflight(ctx, boundary, plan):
    """verify-before-consume：消费上游产物前，先验上游阶段回执。

    返回 (results, evidence)。只要有一条前置回执不成立，调用方就不再执行 boundary
    ——「跳过 a3 直接跑 a4」在下游就是硬阻断，不指望 Agent 自觉。
    """
    evidence = {}
    if ctx.dry_run or not ctx.preflight or boundary not in plan:
        return [], evidence
    preds = [b for b in plan[: plan.index(boundary)] if b in HARD_CHAIN_STAGES]
    if not preds:
        return [], evidence

    ledger, err = gs.load_ledger(ctx.batch, ctx.base, ctx.ledger)
    if err:
        return [_result("CHAIN", "FAIL", code="LEDGER_CORRUPT", owner="orchestrator",
                        fix_hint=FIX_HINTS["CHAIN"], evidence={"detail": err})], evidence
    if ledger is None:
        if not gs.required_for(ctx.batch):
            evidence["chain_legacy"] = True
            print(f"ℹ️  {ctx.batch} 属历史批次（<{gs.STAMP_REQUIRED_MIN_BATCH:03d}），不强制回执链")
            return [], evidence
        # 回执链首次建立：为「已经存在产物」的上游阶段补录，链才能继续往下走。
        # 补录 = provenance=backfill，audit 会标 WARN——不假装它们验过门禁。
        ledger = gs.new_ledger(ctx.batch)
        backfilled = []
        for p in preds:
            arts = boundary_artifacts(ctx, p)
            if not arts:
                continue
            gs.append_stamp(ledger, p, artifacts=arts, gates=[], provenance="backfill",
                            note="P0 上线前已存在的阶段，补录；门禁当时是否真跑过无法证明",
                            driver_version=DRIVER_VERSION)
            backfilled.append(p)
        if backfilled:
            gs.write_ledger(ledger, ctx.base, ctx.ledger)
            evidence["chain_backfill"] = backfilled
            print(f"⚠️  回执链首次建立：补录 {', '.join(backfilled)}（provenance=backfill）")
        # 补录不了的阶段（产物已不存在）= 无法证明门禁执行过 → 仍然阻断，别把补录当免责
        missing = [p for p in preds if gs.find_stamp(ledger, p) is None]
        if missing:
            return [_result(f"CHAIN-{p}", "FAIL", code="STAGE_MISSING",
                            owner=owner_for_gate(f"GATE-{p.upper()}"), fix_hint=FIX_HINTS["CHAIN"],
                            evidence={"stage": p,
                                      "detail": f"{p} 阶段没有可补录的产物，无法证明门禁执行过"})
                    for p in missing], evidence
        return [_result("CHAIN", "PASS", code="CHAIN_BACKFILL",
                        evidence={"backfill": backfilled})], evidence

    rows, backfill = [], []
    for p in preds:
        rep = gs.verify(ctx.batch, p, base=ctx.base, path=ctx.ledger)
        if rep["verdict"] == "FAIL":
            detail = "; ".join(i["detail"] for i in rep["issues"]) or rep["code"]
            rows.append(_result(f"CHAIN-{p}", "FAIL", code=rep["code"],
                                owner=owner_for_gate(f"GATE-{p.upper()}"),
                                fix_hint=FIX_HINTS["CHAIN"],
                                evidence={"stage": p, "detail": detail,
                                          "next": f"batch_driver.py check --batch {ctx.batch} --stage {p}"}))
        elif rep["verdict"] == "WARN":
            backfill.append(p)
            rows.append(_result(f"CHAIN-{p}", "PASS", code="CHAIN_BACKFILL",
                                evidence={"stage": p, "seq": rep.get("stamp_seq")}))
        else:
            rows.append(_result(f"CHAIN-{p}", "PASS",
                                evidence={"stage": p, "seq": rep.get("stamp_seq")}))
    if backfill:
        evidence["chain_backfill"] = backfill
    return rows, evidence


def stamp_pass(ctx, boundary, results):
    """PASS 时把「本阶段产物 + 门禁证据」写入回执链。返回 (stamp_info, error)。"""
    if ctx.dry_run or not ctx.stamp:
        return None, None
    if not gs.required_for(ctx.batch):
        return {"skipped": f"legacy_batch<{gs.STAMP_REQUIRED_MIN_BATCH:03d}"}, None
    try:
        ledger, err = gs.load_ledger(ctx.batch, ctx.base, ctx.ledger)
        if err:
            return None, err
        if ledger is None:
            ledger = gs.new_ledger(ctx.batch)
        st = gs.append_stamp(
            ledger, boundary,
            artifacts=boundary_artifacts(ctx, boundary),
            gate_reports=_gate_report_paths(results),
            gates=[r["gate"] for r in results if r["status"] == "PASS"],
            driver_version=DRIVER_VERSION,
        )
        path = gs.write_ledger(ledger, ctx.base, ctx.ledger)
        return {"path": gs.rel(path, ctx.base), "seq": st["seq"], "stage": boundary,
                "artifacts": [a["path"] for a in st["artifacts"]],
                "gate_reports": len(st["gate_reports"]), "head": ledger["head"]}, None
    except Exception as exc:  # 回执写不进去 = 证据缺失，必须显式失败，不能静默 PASS
        return None, f"{type(exc).__name__}: {exc}"


def _find_keypoints(batch_id: str, batch_data: dict):
    subject = str(batch_data.get("subject") or "")
    pats = []
    if subject:
        pats += [f"输入素材/**/{subject}*教师重点*.md", f"输入素材/**/{subject}*锚定清单*.md",
                 f"输入素材/**/{subject}*重点*.md"]
    pats += [f"输入素材/{subject}/**/*教师重点*.md"] if subject else []
    for pat in pats:
        hits = sorted([Path(p) for p in glob.glob(str(BASE / pat))])
        if hits:
            return hits[0]
    return None


def _find_review_md(batch_data: dict):
    subject = str(batch_data.get("subject") or "")
    if not subject:
        return None
    hits = sorted([Path(p) for p in glob.glob(str(BASE / "复习资料" / "**" / f"{subject}*主复习资料.md"), recursive=True)])
    return hits[0] if hits else None


# ── 归一化器（SA-5 形状契约，纯函数，可 selftest）─────────────
BLOOM_KEYS = ("记忆", "理解", "应用", "分析")


def normalize_bloom(payload):
    """A3 报告 bloom_distribution → (status, code, note)。

    兼容：扁平百分数 / {actual:{...}} / {actual_pct:{...}} / 嵌套计数 {层级:{count,ratio}}
    嵌套计数可重算 → WARN（留痕）；不可重算 → FAIL。
    """
    if not isinstance(payload, dict):
        return "FAIL", "SHAPE_BLOOM", "报告不是对象"
    dist = payload.get("bloom_distribution")
    if dist is None:
        dist = payload
    if not isinstance(dist, dict):
        return "FAIL", "SHAPE_BLOOM", "bloom_distribution 不是对象"
    actual = dist.get("actual") or dist.get("actual_pct") or dist.get("percent")
    if isinstance(actual, dict):
        vals = list(actual.values())
        if all(isinstance(v, (int, float)) for v in vals):
            return "PASS", None, "actual 为扁平百分数"
        if all(isinstance(v, dict) and "count" in v for v in vals):
            total = sum(int(v.get("count") or 0) for v in vals)
            if total <= 0:
                return "FAIL", "SHAPE_BLOOM", "嵌套计数总和为 0，不可重算"
            pct = {k: round(100.0 * int(v.get("count") or 0) / total, 1) for k, v in actual.items()}
            s = sum(pct.values())
            if not (99.0 <= s <= 101.0):
                return "FAIL", "SHAPE_BLOOM", f"重算后合计 {s}% 异常"
            return "WARN", "SHAPE_BLOOM", f"嵌套计数形态，已按 count 重算为 {pct}"
        return "FAIL", "SHAPE_BLOOM", "actual 取值类型混杂"
    for key in BLOOM_KEYS:
        v = dist.get(key)
        if isinstance(v, (int, float)):
            return "PASS", None, "按层级扁平百分数"
        if isinstance(v, dict) and "count" in v:
            return "WARN", "SHAPE_BLOOM", "顶层层级含 count，建议改为扁平百分数"
    return "FAIL", "SHAPE_BLOOM", "未找到可识别的 bloom 分布"


def normalize_synced(trace):
    """AGENT4 追溯日志 → (status, code, note)。source_file_synced 必须在顶层。"""
    if not isinstance(trace, dict):
        return "FAIL", "SHAPE_SYNCED", "追溯日志不是对象"
    top = trace.get("source_file_synced")
    if top is None:
        top = trace.get("source_files_synced")
    if isinstance(top, bool):
        return ("PASS", None, "顶层 source_file_synced=true") if top else ("FAIL", "SHAPE_SYNCED", "顶层 source_file_synced=false")
    patches = trace.get("patches") or trace.get("patch_log") or []
    if isinstance(patches, list) and patches and all(isinstance(p, dict) and p.get("source_file_synced") is True for p in patches):
        return "PASS", None, "patches[] 全部 true"
    nested = trace.get("execution_metadata") or trace.get("metadata") or {}
    if isinstance(nested, dict) and ("source_file_synced" in nested or "source_files_synced" in nested):
        return "FAIL", "SHAPE_SYNCED", "source_file_synced 写在 execution_metadata 内部"
    return "FAIL", "SHAPE_SYNCED", "未找到顶层 source_file_synced"


def check_kp_numbering(md_text: str, kp_text: str):
    """📌 重点原文（第X条）→ (status, code, locator, note)。

    规则：落点条号必须取自锚定清单**第四节连续编号**；与印刷标号不一致 → FAIL。
    这里只做机械可判的部分：条号必须落在 1..N（N=清单条目数）且按出现顺序不跳号。
    """
    if not md_text or not kp_text:
        return "SKIP", None, None, "缺少 MD 或锚定清单"
    n = len(re.findall(r"^\s*(\d{1,3})[.、]", kp_text, flags=re.M))
    if n <= 0:
        return "SKIP", None, None, "锚定清单未识别出连续编号条目"
    nums = [int(x) for x in re.findall(r"📌[^\n]*?第\s*(\d{1,3})\s*条", md_text)]
    if not nums:
        return "FAIL", "SHAPE_KP_NO", None, "MD 中无「📌 重点原文（第X条）」落点"
    bad = [x for x in nums if x < 1 or x > n]
    if bad:
        return "FAIL", "SHAPE_KP_NO", f"越界条号 {bad[:5]}（清单共 {n} 条）", "条号超出锚定清单编号范围"
    prev = 0
    for x in nums:
        if x < prev:
            return "FAIL", "SHAPE_KP_NO", f"条号回退 {prev}→{x}", "落点顺序与清单不一致"
        prev = x
    return "PASS", None, None, f"{len(nums)} 个落点，条号 1..{n} 内"


def parse_gate_payload(payload, stage):
    """gate_check --json-out → list[result]"""
    if not isinstance(payload, dict) or not isinstance(payload.get("gates"), list):
        raise ValueError("gate_check JSON 缺少 gates[]")
    out = []
    for g in payload["gates"]:
        st = str(g.get("status") or "").upper()
        gate = str(g.get("gate") or f"GATE-{stage}")
        if st == "PASS":
            out.append(_result(gate, "PASS", evidence={"reason": g.get("reason"), "stage": stage}))
        elif st in ("SKIPPED", "SKIP"):
            out.append(_result(gate, "SKIP", code="SKIPPED", owner=owner_for_gate(gate), evidence={"reason": g.get("reason")}))
        else:
            out.append(_result(gate, "FAIL", code=gate, owner=owner_for_gate(gate),
                               fix_hint=_hint(gate), evidence={"reason": g.get("reason"), "stage": stage},
                               raw=str(g.get("reason") or "")))
    return out


def parse_quality_gate(payload):
    if not isinstance(payload, dict) or "status" not in payload:
        raise ValueError("quality_gate 报告缺少 status")
    st = str(payload["status"]).upper()
    checks = payload.get("checks") or []
    blocking = payload.get("blocking") or []
    code = None
    for c in checks:
        if str(c.get("status")).upper() == "FAIL":
            code = str(c.get("id") or "QUALITY_CHECK")
            break
    status = "PASS" if st == "PASS" else ("FAIL" if st == "BLOCKED" else ("WARN" if st == "WARN" else "FAIL"))
    return [_result(f"QUALITY-{payload.get('stage', '?').upper()}", status, code=code,
                    owner="orchestrator", fix_hint=_hint(code) if code else None,
                    evidence={"blocking": blocking, "warnings": payload.get("warnings") or []},
                    raw="; ".join(blocking)[:2000])]


def parse_validate_report(payload):
    if not isinstance(payload, dict):
        raise ValueError("validate 报告不是对象")
    summary = payload.get("summary") or {}
    fail = int(summary.get("fail") or 0)
    warn = int(summary.get("warn") or 0)
    issues = payload.get("issues") or []
    code = None
    locator = None
    for it in issues:
        if str(it.get("severity", "")).upper() == "FAIL":
            code = str(it.get("rule") or "VALIDATE")
            locator = it.get("question_id")
            break
    if fail:
        return [_result("GATE-A2", "FAIL", code=code or "VALIDATE", owner="MedGen",
                        locator=locator, fix_hint=_hint(code or "R"), evidence={"summary": summary},
                        raw=json.dumps(summary, ensure_ascii=False))]
    if warn:
        return [_result("GATE-A2", "WARN", code=code, owner="MedGen", evidence={"summary": summary})]
    return [_result("GATE-A2", "PASS", evidence={"summary": summary})]


def parse_lv_report(payload):
    summary = (payload or {}).get("summary") or {}
    fail = int(summary.get("fail") or 0)
    if fail:
        code = "HC24"
        for it in (payload.get("items") or []):
            if it.get("status") == "FAIL":
                issues = it.get("issues") or []
                if issues:
                    code = str(issues[0].get("rule") or code)
                break
        return [_result("GATE-LV", "FAIL", code=code, owner="MedFix", fix_hint=_hint(code),
                        evidence={"summary": summary}, raw=json.dumps(summary, ensure_ascii=False))]
    return [_result("GATE-LV", "PASS", evidence={"summary": summary})]


def parse_patch_integrity(payload):
    if not isinstance(payload, dict):
        raise ValueError("patch integrity 报告不是对象")
    result = str(payload.get("result") or "").upper()
    if result == "PASS":
        return [_result("GATE-A4-PATCH", "PASS", evidence={"noop": payload.get("noop")})]
    raw = json.dumps({k: payload.get(k) for k in ("violations", "undeclared", "noop", "file_identical")},
                     ensure_ascii=False)
    return [_result("GATE-A4-PATCH", "FAIL", code="HC13", owner="MedFix", fix_hint=_hint("HC13"),
                    evidence={"file_identical": payload.get("file_identical"), "noop": payload.get("noop")},
                    raw=raw)]


# ── 门禁执行适配器 ───────────────────────────────────────
class Ctx:
    def __init__(self, batch_id, batch_data, args):
        self.batch = batch_id
        self.data = batch_data
        self.dry_run = bool(args.dry_run)
        self.write_state = not bool(args.no_state_write)
        self.set_halt = not bool(args.no_halt)
        self.timeout = int(args.timeout)
        self.stamp = not bool(getattr(args, "no_stamp", False))
        self.preflight = not bool(getattr(args, "no_preflight", False))
        self.base = Path(getattr(args, "base", None) or BASE)
        self.ledger = getattr(args, "ledger", None)
        self.tmp = Path(tempfile.mkdtemp(prefix="batch_driver_"))
        self.started = time.time()

    def close(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)


def _gate_check(ctx, stage, extra_result=None):
    out = ctx.tmp / f"gate_{stage}.json"
    if ctx.dry_run:
        return [_result(f"GATE-{stage}", "SKIP", code="DRY_RUN", evidence={"dry_run": True})]
    argv = _py("gate_check.py", "--batch", ctx.batch, "--stage", stage, "--json-out", str(out))
    if not ctx.write_state:
        argv.append("--no-state-write")
    if not ctx.set_halt:
        argv.append("--no-halt")
    rc, text, ms = _run(argv, ctx.timeout)
    if rc is None:
        return [_result(f"GATE-{stage}", "FAIL", code="DRIVER_TIMEOUT", owner="orchestrator",
                        fix_hint=FIX_HINTS["DRIVER"], raw=text)]
    payload = _load_json(out)
    if payload is None:
        return [_result(f"GATE-{stage}", "FAIL", code="UNPARSABLE", owner="orchestrator",
                        fix_hint=FIX_HINTS["UNPARSABLE"], evidence={"exit_code": rc, "duration_ms": ms},
                        raw=text[-2000:])]
    res = parse_gate_payload(payload, stage)
    for r in res:
        r["evidence"].setdefault("duration_ms", ms)
    if payload.get("approved_mode"):
        # APPROVED 批次是参考模式（gate_check 退出码 0，不写 HALT）：不得记成 FAIL
        for r in res:
            if r["status"] == "FAIL":
                r["status"] = "SKIP"
                r["severity"] = "SKIP"
                r["code"] = "APPROVED_REFERENCE"
                r["fix_hint"] = None
                r["evidence"]["note"] = "已签收批次参考模式，不阻断"
    if rc == 2 and all(r["status"] == "PASS" for r in res):
        res.append(_result(f"GATE-{stage}-EXEC", "FAIL", code="DRIVER_ERROR", owner="orchestrator",
                           fix_hint=FIX_HINTS["DRIVER"], evidence={"exit_code": rc}, raw=text[-1000:]))
    return res


def boundary_a2(ctx):
    p = _paths(ctx.batch)["a2"]
    if not p.exists():
        return [_result("GATE-A2", "FAIL", code="MISSING_A2", owner="MedGen",
                        file=str(p), fix_hint=FIX_HINTS["MISSING"])]
    if ctx.dry_run:
        return [_result("GATE-A2", "PASS", code="DRY_RUN", evidence={"file": str(p), "dry_run": True})]
    argv = _py("-m", "scripts.validate", "--file", p, "--batch", ctx.batch)
    rc, text, ms = _run(argv, ctx.timeout)
    rep = _latest(f"reports/validate/validate_options_report_{ctx.batch}*.json")
    payload = _load_json(rep) if rep else None
    if payload is None:
        return [_result("GATE-A2", "FAIL", code="UNPARSABLE", owner="MedGen",
                        evidence={"exit_code": rc, "duration_ms": ms}, raw=text[-2000:])]
    res = parse_validate_report(payload)
    for r in res:
        r["evidence"].update({"report": str(rep.relative_to(BASE)), "exit_code": rc, "duration_ms": ms})
    return res


def boundary_a3(ctx):
    res = []
    a3 = _paths(ctx.batch)["a3a"]
    a3 = a3 if a3.exists() else _paths(ctx.batch)["a3b"]
    if not a3.exists():
        return [_result("GATE-A3", "FAIL", code="MISSING_A3", owner="MedQC",
                        file=str(a3), fix_hint=FIX_HINTS["MISSING"])]
    payload = _load_json(a3)
    if payload is None:
        return [_result("GATE-A3", "FAIL", code="UNPARSABLE", owner="MedQC",
                        file=str(a3), fix_hint=FIX_HINTS["UNPARSABLE"])]
    st, code, note = normalize_bloom(payload)
    res.append(_result("SHAPE-BLOOM", st, code=code, owner="MedQC",
                       file=str(a3), fix_hint=_hint(code) if code else None,
                       evidence={"note": note}))
    res += _gate_check(ctx, "agent3_done")
    return res


def boundary_a4(ctx):
    res = []
    paths = _paths(ctx.batch)
    fixed, log, md = paths["a4"], paths["a4_log"], paths["a4_md"]
    if not fixed.exists():
        return [_result("GATE-A4", "FAIL", code="MISSING_A4", owner="MedFix",
                        file=str(fixed), fix_hint=FIX_HINTS["MISSING"])]
    if not md.exists():
        return [_result("GATE-A4-MD", "FAIL", code="MISSING_MD_EXPORT", owner="MedFix",
                        file=str(md), fix_hint="MedFix: 复检后跑 qbank.py export-md 生成最终交付 MD")]
    trace = _load_json(log) if log.exists() else None
    if trace is None:
        return [_result("GATE-A4-HC13", "FAIL", code="MISSING_TRACE", owner="MedFix",
                        file=str(log), fix_hint=FIX_HINTS["HC13"])]
    st, code, note = normalize_synced(trace)
    res.append(_result("SHAPE-SYNCED", st, code=code, owner="MedFix",
                       file=str(log), fix_hint=_hint(code) if code else None, evidence={"note": note}))
    if not ctx.dry_run and paths["a2"].exists():
        out = ctx.tmp / "patch_integrity.json"
        argv = _py("scripts/check_patch_integrity.py", "--before", paths["a2"], "--after", fixed,
                   "--json", out, "--quiet")
        rc, text, ms = _run(argv, ctx.timeout)
        payload = _load_json(out)
        if payload is None:
            res.append(_result("GATE-A4-PATCH", "FAIL", code="UNPARSABLE", owner="MedFix",
                               evidence={"exit_code": rc, "duration_ms": ms}, raw=text[-1500:]))
        else:
            res += parse_patch_integrity(payload)
    res += _gate_check(ctx, "agent4_done")
    return res


def boundary_lv(ctx):
    res = []
    fixed = _paths(ctx.batch)["a4"]
    if not fixed.exists():
        return [_result("GATE-LV", "FAIL", code="MISSING_A4", owner="MedFix",
                        file=str(fixed), fix_hint=FIX_HINTS["MISSING"])]
    if ctx.dry_run:
        res.append(_result("GATE-LV", "SKIP", code="DRY_RUN", evidence={"dry_run": True}))
    else:
        out = ctx.tmp / "learning_value.json"
        argv = _py("scripts/check_learning_value.py", "--file", fixed, "--batch", ctx.batch, "--out", out)
        rc, text, ms = _run(argv, ctx.timeout)
        payload = _load_json(out)
        if payload is None:
            res.append(_result("GATE-LV", "FAIL", code="UNPARSABLE", owner="MedFix",
                               evidence={"exit_code": rc, "duration_ms": ms}, raw=text[-1500:]))
        else:
            res += parse_lv_report(payload)
        res += _gate_check(ctx, "learning_value")
    return res


def boundary_a5(ctx):
    res = []
    md = _find_review_md(ctx.data)
    kp = _find_keypoints(ctx.batch, ctx.data)
    if md is None:
        return [_result("GATE-A5", "FAIL", code="MISSING_REVIEW_MD", owner="MedReview",
                        fix_hint=FIX_HINTS["MISSING"])]
    if ctx.dry_run:
        return [_result("GATE-A5", "SKIP", code="DRY_RUN", evidence={"md": str(md), "dry_run": True})]
    if kp is not None:
        argv = _py("scripts/check_keypoint_coverage.py", "--keypoints", kp, "--md", md, "--json")
        rc, text, ms = _run(argv, ctx.timeout)
        status = _mapped("check_keypoint_coverage", rc)
        if status == "SKIP":
            res.append(_result("GATE-A5-KP", "SKIP", code="SKIPPED", owner="MedReview",
                               evidence={"exit_code": rc}))
        elif status == "PASS":
            res.append(_result("GATE-A5-KP", "PASS", evidence={"duration_ms": ms}))
        else:
            res.append(_result("GATE-A5-KP", "FAIL", code="HC20", owner="MedReview",
                               fix_hint=_hint("HC20"), evidence={"exit_code": rc}, raw=text[-1500:]))
    else:
        res.append(_result("GATE-A5-KP", "SKIP", code="NO_KEYPOINTS", owner="MedReview",
                           evidence={"reason": "无教师重点输入"}))
    out = ctx.tmp / "review_detail.json"
    argv = _py("scripts/check_review_detail.py", "--md", md, "--mode", "auto",
               "--profile", "release_teacher_keypoint", "--json-out", out)
    rc, text, ms = _run(argv, ctx.timeout)
    payload = _load_json(out)
    status = _mapped("check_review_detail", rc)
    if payload is None and status != "SKIP":
        res.append(_result("GATE-A5-DETAIL", "FAIL", code="UNPARSABLE", owner="MedReview",
                           evidence={"exit_code": rc, "duration_ms": ms}, raw=text[-1500:]))
    else:
        res.append(_result("GATE-A5-DETAIL", "PASS" if status == "PASS" else ("SKIP" if status == "SKIP" else "FAIL"),
                           code=None if status == "PASS" else ("SKIPPED" if status == "SKIP" else "HC26"),
                           owner="MedReview", fix_hint=_hint("HC26") if status != "PASS" else None,
                           evidence={"exit_code": rc, "duration_ms": ms}))
    return res


def boundary_quality(ctx, stage):
    if ctx.dry_run:
        return [_result(f"QUALITY-{stage.upper()}", "SKIP", code="DRY_RUN", evidence={"dry_run": True})]
    mode = "enforce" if stage == "r3" else "advisory"
    profile = "release_teacher_keypoint" if stage == "r3" else "pilot"
    out = ctx.tmp / f"quality_{stage}.json"
    argv = _py("scripts/quality_gate.py", "--stage", stage, "--batch", ctx.batch,
               "--profile", profile, "--mode", mode, "--out", out)
    if stage == "r2":
        argv.append("--with-tests")
    rc, text, ms = _run(argv, ctx.timeout)
    payload = _load_json(out)
    if payload is None:
        return [_result(f"QUALITY-{stage.upper()}", "FAIL", code="UNPARSABLE", owner="orchestrator",
                        evidence={"exit_code": rc, "duration_ms": ms}, raw=text[-2000:])]
    res = parse_quality_gate(payload)
    for r in res:
        r["evidence"].update({"report": str(out.relative_to(BASE)) if str(out).startswith(str(BASE)) else str(out),
                              "exit_code": rc, "duration_ms": ms, "mode": mode})
    return res


def boundary_final(ctx):
    res = []
    if ctx.dry_run:
        return [_result("GATE-FINAL", "SKIP", code="DRY_RUN", evidence={"dry_run": True})]
    paths = _paths(ctx.batch)
    if paths["plan"].exists() and paths["a4"].exists():
        out = ctx.tmp / "realq.json"
        argv = _py("scripts/real_question_cli.py", "check", "--file", paths["a4"],
                   "--plan", paths["plan"], "--out", out)
        rc, text, ms = _run(argv, ctx.timeout)
        payload = _load_json(out)
        if payload is None:
            res.append(_result("GATE-REALQ", "FAIL", code="UNPARSABLE", owner="orchestrator",
                               evidence={"exit_code": rc, "duration_ms": ms}, raw=text[-1500:]))
        else:
            failures = payload.get("failures") or []
            if failures:
                code = str(failures[0].get("code") or "HC22")
                res.append(_result("GATE-REALQ", "FAIL", code=code, owner="orchestrator",
                                   fix_hint=_hint(code), evidence={"failures": failures[:5]},
                                   raw=json.dumps(failures[:5], ensure_ascii=False)))
            else:
                res.append(_result("GATE-REALQ", "PASS", evidence={"duration_ms": ms}))
    else:
        res.append(_result("GATE-REALQ", "SKIP", code="NO_PLAN", owner="orchestrator",
                           evidence={"reason": "无 real_question_plan.json（或非题库批次）"}))
    res += _gate_check(ctx, "final")
    return res


def run_boundary(ctx, boundary):
    if boundary == "a2":
        return boundary_a2(ctx)
    if boundary == "a3":
        return boundary_a3(ctx)
    if boundary == "a4":
        return boundary_a4(ctx)
    if boundary == "lv":
        return boundary_lv(ctx)
    if boundary == "a5":
        return boundary_a5(ctx)
    if boundary in ("r0", "r1", "r2", "r3"):
        return boundary_quality(ctx, boundary)
    if boundary == "r4":
        return boundary_quality(ctx, "r4")
    if boundary == "final":
        return boundary_final(ctx)
    return [_result(f"UNKNOWN-{boundary}", "FAIL", code="DRIVER_UNKNOWN_BOUNDARY", owner="orchestrator",
                    fix_hint=FIX_HINTS["DRIVER"])]


# ── auto 路由：计划序列中第一个「无 PASS 证据」的 boundary ──────
def _has_pass_evidence(boundary, batch_id, batch_data):
    if boundary.startswith("r") and boundary in ("r0", "r1", "r2", "r3", "r4"):
        hit = _latest(f"reports/gate/quality_gate_{batch_id}_{boundary}_*.json")
        if not hit:
            return False
        payload = _load_json(hit) or {}
        return str(payload.get("status") or "").upper() != "BLOCKED"
    if boundary == "final":
        gr = (batch_data.get("gate_results") or {}).get("GATE-FINAL", {})
        return batch_data.get("status") == "APPROVED" or str(gr.get("status") or "").upper() == "PASS"
    gate_map = {"a2": "GATE-A2", "a3": "GATE-A3", "a4": "GATE-A4", "lv": "GATE-LV"}
    if boundary in gate_map:
        gr = (batch_data.get("gate_results") or {}).get(gate_map[boundary], {})
        return str(gr.get("status") or "").upper() == "PASS"
    return False


def resolve_auto(batch_id, batch_data, plan):
    if batch_data.get("status") == "APPROVED":
        return None
    for b in plan:
        if not _has_pass_evidence(b, batch_id, batch_data):
            return b
    return None


# ── Handoff bundle（H2）：宿主无关的「阶段执行包」──────────────
# 纪律：
#   1. 包里不含任何宿主工具名（subagent / read / bash…），只描述数据与命令；
#   2. 哈希一律复用 gate_stamp.file_sha256，与回执链同一真相源；
#   3. 内容完全确定（无时间戳），重复 check 产出同一字节；
#   4. --dry-run 不写任何文件。
STAGE_META = {
    "a2": {"owner": "MedGen", "role": "medgen",
           "prompt": "Prompt版本/MedGen_current_prompt.md",
           "write_scope": "question_bank", "read": "full"},
    "a3": {"owner": "MedQC", "role": "medqc",
           "prompt": "Prompt版本/MedQC_current_prompt.md",
           "write_scope": "report", "read": "by-id"},
    "a4": {"owner": "MedFix", "role": "medfix",
           "prompt": "Prompt版本/MedFix_current_prompt.md",
           "write_scope": "question_bank", "read": "by-id"},
    "a5": {"owner": "MedReview", "role": "medreview",
           "prompt": "Prompt版本/Agent5_MedReview_Prompt.md",
           "write_scope": "review_material", "read": "by-id"},
}
# r0/r1/lv/r2/r3/final/r4 是纯门禁阶段，不派角色 → 不生成交接包


def _stage_io(batch_id, stage, data):
    b = batch_id
    ctx = f"中间产物/{b}/_ctx.md"
    table = {
        "a2": ([ctx, f"中间产物/{b}/real_question_plan.json"],
               [f"中间产物/{b}/ALL_questions.json"]),
        "a3": ([ctx, f"中间产物/{b}/ALL_questions.json"],
               [f"质检报告/{b}/A3_质检报告.json"]),
        "a4": ([ctx, f"中间产物/{b}/ALL_questions.json", f"质检报告/{b}/A3_质检报告.json"],
               [f"最终产物/{b}/ALL_questions_FIXED.json",
                f"最终产物/{b}/ALL_questions_FIXED.md",
                f"最终产物/{b}/AGENT4_追溯日志.json"]),
        "a5": ([ctx], []),
    }
    ins, outs = table.get(stage, ([], []))
    if stage == "a5":
        md = _find_review_md(data or {})
        outs = [gs.rel(md, BASE)] if md else ["复习资料/<科目>教学计划版/<科目>_主复习资料.md"]
    # 保留全部声明的输入（不因文件暂未入库而删条目）：契约要回答「该阶段该读什么」，
    # 干净检出里中间产物不存在只是 exists=false，不能让 bundle 形状随环境变化。
    return ins, outs


def _fingerprint(rows):
    import hashlib
    body = json.dumps([r.get("sha256") for r in rows], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def handoff_path(batch_id, stage, base=BASE):
    return base / "中间产物" / batch_id / "_handoff" / f"{stage}.json"


def handoff_stale(path):
    """产物变了但包没重生成 → True；包不存在 → None；完好 → False。"""
    p = Path(path)
    if not p.is_file():
        return None
    d = _load_json(p)
    if not d:
        return True
    rows = []
    for i in d.get("inputs", []):
        f = BASE / i["path"]
        rows.append({"sha256": gs.file_sha256(f) if f.is_file() else None})
    return _fingerprint(rows) != d.get("inputs_fingerprint")


def build_handoff(batch_id, stage, plan, data):
    meta = STAGE_META.get(stage)
    if not meta:
        return None
    ins, outs = _stage_io(batch_id, stage, data)
    inputs = []
    for p in ins:
        f = BASE / p
        inputs.append({
            "path": p,
            "sha256": gs.file_sha256(f) if f.is_file() else None,
            "exists": f.is_file(),
            "read": meta["read"],
            "selector": "scripts/qbank.py subselect" if meta["read"] == "by-id" else None,
        })
    try:
        idx = plan.index(stage)
        prev = plan[idx - 1] if idx > 0 else None
    except ValueError:
        prev = None
    preflight = (f"python scripts/gate_verify.py --batch {batch_id} --stage {prev} --quiet"
                 if prev in HARD_CHAIN_STAGES else None)
    return {
        "schema_version": "1.0",
        "batch": batch_id,
        "stage": stage,
        "owner": meta["owner"],
        "role_skill": f".dsh/skills/{meta['role']}/SKILL.md",
        "prompt_ref": meta["prompt"],
        "ctx": f"中间产物/{batch_id}/_ctx.md",
        "inputs": inputs,
        "outputs": [{"path": p, "schema": p.rsplit(".", 1)[-1]} for p in outs],
        "preflight": preflight,
        "gate": f"python scripts/batch_driver.py check --batch {batch_id} --stage {stage}",
        "done": ([f"{outs[0]} 存在且可解析"] if outs else []) + ["gate 返回 exit 0"],
        "report_format": "三行：结论 / 落点路径 / 阻断原因",
        "write_scope": meta["write_scope"],
        "parallel_safe": meta["write_scope"] != "question_bank",
        "inputs_fingerprint": _fingerprint(inputs),
        "rebuild_if": "inputs_fingerprint 与当前文件不符 → 丢弃本包，重跑 driver check",
        "driver_version": DRIVER_VERSION,
    }


def write_handoff(bundle, base=BASE):
    """幂等写入；内容相同则不碰磁盘（重复 check 不改 mtime）。"""
    p = handoff_path(bundle["batch"], bundle["stage"], base)
    text = json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True)
    if p.is_file() and p.read_text(encoding="utf-8") == text:
        return {"path": gs.rel(p, base), "status": "unchanged", "stage": bundle["stage"]}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return {"path": gs.rel(p, base), "status": "written", "stage": bundle["stage"]}


def cmd_brief(args):
    """L0（纯手工宿主）用：把交接包打印成人读交接单，不调用任何 LLM。"""
    p = Path(args.bundle) if args.bundle else handoff_path(args.batch, args.stage)
    stale = handoff_stale(p)
    if stale is None:
        shown = gs.rel(p, BASE) if str(p).startswith(str(BASE)) else str(p)
        print(f"[!] 没有 {shown}；先跑："
              f"python scripts/batch_driver.py check --batch {args.batch} --stage auto")
        return 1
    d = _load_json(p)
    if not d:
        print(f"[!] 交接包无法解析：{p}")
        return 2
    print(f"══ 批次 {d['batch']} ｜ 阶段 {d['stage']} ｜ 执行者 {d['owner']}（宿主无关交接单）")
    print(f"规则正文：{d['role_skill']}")
    print(f"提示词：  {d['prompt_ref']}")
    print(f"起步上下文：{d['ctx']}（≤8k；L1 单会话每阶段重读一次）")
    print("读：")
    for i in d["inputs"]:
        mark = "OK" if i["exists"] else "缺失"
        print(f"  - [{i['read']}] {i['path']}  sha256={str(i['sha256'])[:12]}  {mark}")
    print("写：")
    for o in d["outputs"]:
        print(f"  - {o['path']}")
    if d.get("preflight"):
        print(f"先验回执：{d['preflight']}")
    print(f"阶段门禁：{d['gate']}")
    print("完成判据：" + "；".join(d["done"]))
    print(f"回报格式：{d['report_format']}")
    print(f"写范围：{d['write_scope']} ｜ 可并行：{d['parallel_safe']}")
    if stale:
        print("[!] 包已过期（产物 sha 变了）：重跑 driver check 后再使用")
        return 3
    print("[OK] 包完好")
    return 0


# ── 聚合与输出 ──────────────────────────────────────────
def aggregate(results):
    statuses = [r["status"] for r in results]
    if "ERROR" in statuses:
        return "ERROR", 2
    if "FAIL" in statuses:
        return "BLOCKED", 1
    if any(s == "WARN" for s in statuses):
        return "SKIP", 3
    if all(s == "SKIP" for s in statuses) and statuses:
        return "SKIP", 3
    return "PASS", 0


def next_boundary(boundary, plan):
    """计划序列中 boundary 之后的下一阶段；末尾或不在计划里返回 None。

    H1：以前「下一步派谁」由 LLM 读 SKILL 自行判断；这里把它变成确定性输出，
    宿主只需照 payload 的 next_stage / next_bundle 行动。
    """
    try:
        i = plan.index(boundary)
    except ValueError:
        return None
    return plan[i + 1] if i + 1 < len(plan) else None


def build_payload(batch_id, boundary, plan, types, results, verdict, exit_code, extra=None):
    failed = [r for r in results if r["status"] in ("FAIL", "WARN")]
    if verdict in ("BLOCKED", "SKIP", "ERROR"):
        next_stage = boundary
        next_action = "retry"
    else:
        next_stage = next_boundary(boundary, plan)
        next_action = "advance" if next_stage else "complete"
    return {
        "batch": batch_id,
        "product_types": sorted(types),
        "stage": boundary,
        "plan": plan,
        "generated_at": _now(),
        "verdict": verdict,
        "exit_code": exit_code,
        "next_stage": next_stage,
        "next_action": next_action,
        "next_bundle": (extra or {}).get("handoff", {}).get("path"),
        "halt": {"active": verdict == "BLOCKED", "reason": None, "source": "gate" if verdict == "BLOCKED" else None},
        "passed": [{"gate": r["gate"], "duration_ms": r["evidence"].get("duration_ms")}
                   for r in results if r["status"] == "PASS"],
        "failed": [{k: r[k] for k in ("gate", "code", "severity", "file", "locator", "fix_hint", "owner", "evidence", "raw")}
                   for r in results if r["status"] in ("FAIL", "WARN")],
        "skipped": [{"gate": r["gate"], "reason": (r["evidence"] or {}).get("reason") or r["code"] or "skipped"}
                    for r in results if r["status"] == "SKIP"],
        "unparsed": [{"gate": r["gate"], "exit_code": (r["evidence"] or {}).get("exit_code"), "raw": r["raw"]}
                     for r in results if r["code"] in ("UNPARSABLE", "DRIVER_TIMEOUT", "DRIVER_ERROR")],
        "evidence": extra or {},
    }


# ── 子命令 ──────────────────────────────────────────────
def cmd_plan(args):
    try:
        _, data = load_batch(args.batch)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    plan, types = plan_boundaries(args.batch, data)
    if args.json:
        print(json.dumps({"batch": args.batch, "product_types": sorted(types),
                          "schema_version": data.get("item_schema_version"),
                          "status": data.get("status"),
                          "boundaries": [{"stage": b, "what": BOUNDARY_BRIEF.get(b, b)} for b in plan]},
                         ensure_ascii=False, indent=2))
        return 0
    print(f"批次 {args.batch} ｜ 类型 {sorted(types)} ｜ schema {data.get('item_schema_version')} ｜ 状态 {data.get('status')}")
    for i, b in enumerate(plan, 1):
        print(f"  {i:2d}. {b:6s} {BOUNDARY_BRIEF.get(b, b)}")
    return 0


def cmd_check(args):
    started = time.time()
    try:
        _, data = load_batch(args.batch)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    plan, types = plan_boundaries(args.batch, data)
    boundary = args.stage
    if boundary == "auto":
        boundary = resolve_auto(args.batch, data, plan)
        if boundary is None:
            payload = build_payload(args.batch, "none", plan, types, [], "PASS", 0,
                                    {"reason": "批次已 APPROVED 或全部阶段已有 PASS 证据"})
            _emit(payload, args.json_out)
            print(f"✅ {args.batch} 已无待执行 boundary（APPROVED 或全部通过）")
            return 0
    elif boundary not in plan:
        print(f"[ERROR] boundary {boundary} 不在该批次计划序列中：{plan}", file=sys.stderr)
        return 2

    ctx = Ctx(args.batch, data, args)
    extra = {"dry_run": ctx.dry_run}
    try:
        # 先验上游回执：不成立就不跑本 boundary（跳过门禁 → 下游硬阻断）
        results, chain_ev = preflight(ctx, boundary, plan)
        extra.update(chain_ev)
        extra["preflight"] = {"enabled": ctx.preflight, "rows": len(results)}
        if not any(r["status"] == "FAIL" for r in results):
            results += run_boundary(ctx, boundary)
    finally:
        ctx.close()
    extra["duration_ms"] = round((time.time() - started) * 1000, 1)
    verdict, exit_code = aggregate(results)
    if verdict == "PASS":
        stamp, err = stamp_pass(ctx, boundary, results)
        if err:
            results.append(_result("STAMP", "FAIL", code="STAMP_WRITE_FAILED", owner="orchestrator",
                                   fix_hint=FIX_HINTS["CHAIN"], raw=err))
            verdict, exit_code = aggregate(results)
        elif stamp:
            extra["stamp"] = stamp
    if verdict == "PASS" and not ctx.dry_run:
        ns = next_boundary(boundary, plan)
        if ns:
            bundle = build_handoff(args.batch, ns, plan, data)
            if bundle:
                extra["handoff"] = write_handoff(bundle, ctx.base)
    payload = build_payload(args.batch, boundary, plan, types, results, verdict, exit_code, extra)
    _emit(payload, args.json_out)
    _print_summary(payload)
    return exit_code


def _emit(payload, json_out):
    if not json_out:
        return
    out = Path(json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_summary(payload):
    print(f"══ {payload['batch']} ｜ boundary {payload['stage']} ｜ {payload['verdict']}（exit {payload['exit_code']}）")
    for p in payload["passed"]:
        print(f"  ✅ {p['gate']}")
    for f in payload["failed"]:
        print(f"  🛑 {f['gate']}: {f['severity']} {f['code']} → {f['owner']}")
        if f["fix_hint"]:
            print(f"     ↳ {f['fix_hint']}")
    for s in payload["skipped"]:
        print(f"  ⏭️  {s['gate']}: {s['reason']}")
    for u in payload["unparsed"]:
        print(f"  ❓ {u['gate']}: 无法解析（exit {u['exit_code']}）")
    if payload["next_stage"]:
        _next_label = {"retry": "修复后重跑 boundary",
                       "advance": "下一 boundary",
                       "complete": "收尾"}.get(payload.get("next_action"), "下一步")
        print(f"  ➡️  {_next_label}: {payload['next_stage']}")
    if payload.get("next_bundle"):
        print(f"  📦 交接包：{payload['next_bundle']}（按包执行，无需宿主 subagent）")
    if payload["verdict"] == "BLOCKED":
        print("  🩺 若同一失败原因重复出现，跑 scripts/batch_watchdog.py --batch " + payload["batch"] + " 判进展")
    ev = payload.get("evidence") or {}
    st = ev.get("stamp") or {}
    if st.get("path"):
        print(f"  🔖 回执 seq={st['seq']} → {st['path']}（绑定产物 {len(st.get('artifacts') or [])} 个）")
    if ev.get("chain_backfill"):
        print(f"  ⚠️  回执补录 {', '.join(ev['chain_backfill'])}（provenance=backfill，audit 会标 WARN）")


# ── selftest：归一化器与解析器的固定夹具回归 ──────────────
SELFTEST_CASES = [
    ("bloom_flat_pass", "bloom", 1, "PASS"),
    ("bloom_nested", "bloom", 1, "WARN"),
    ("trace_synced_top", "synced", 1, "PASS"),
    ("trace_synced_nested", "synced", 1, "FAIL"),
    ("kp_printed_number", "kp", 1, "FAIL"),
    ("kp_ok", "kp", 1, "PASS"),
    ("gate_json_pass", "gate", 1, "PASS"),
    ("gate_json_blocked", "gate", 1, "FAIL"),
    ("quality_gate_warn", "quality", 1, "WARN"),
    ("validate_fail", "validate", 1, "FAIL"),
    ("garbage", "gate", 1, "FAIL"),
]


def _selftest_one(fixture_dir: Path, name: str, kind: str):
    d = fixture_dir / name
    if kind == "bloom":
        return normalize_bloom(_load_json(d / "input.json"))[0]
    if kind == "synced":
        return normalize_synced(_load_json(d / "input.json"))[0]
    if kind == "kp":
        md = (d / "md.md").read_text(encoding="utf-8")
        kp = (d / "kp.md").read_text(encoding="utf-8")
        return check_kp_numbering(md, kp)[0]
    if kind == "gate":
        payload = _load_json(d / "input.json")
        if payload is None:
            return "FAIL"
        return parse_gate_payload(payload, "agent3_done")[0]["status"]
    if kind == "quality":
        return parse_quality_gate(_load_json(d / "input.json"))[0]["status"]
    if kind == "validate":
        return parse_validate_report(_load_json(d / "input.json"))[0]["status"]
    raise ValueError(f"unknown kind {kind}")


def cmd_selftest(args):
    fixture_dir = Path(args.fixture)
    if not fixture_dir.is_absolute():
        fixture_dir = BASE / fixture_dir
    rows = []
    ok = True
    for name, kind, _n, expect in SELFTEST_CASES:
        try:
            got = _selftest_one(fixture_dir, name, kind)
        except Exception as exc:
            got = f"ERROR:{type(exc).__name__}"
        passed = (got == expect)
        ok = ok and passed
        rows.append({"fixture": name, "kind": kind, "expect": expect, "got": got, "ok": passed})
    exit_map = [("check_source_concepts", 2, "SKIP"), ("check_keypoint_coverage", 2, "SKIP"),
                ("gate_check", 2, "ERROR"), ("check_patch_integrity", 1, "FAIL")]
    for script, rc, expect in exit_map:
        got = _mapped(script, rc)
        passed = got == expect
        ok = ok and passed
        rows.append({"fixture": f"exit_map:{script}({rc})", "kind": "exit", "expect": expect,
                     "got": got, "ok": passed})
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"ok": ok, "total": len(rows), "rows": rows},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    for r in rows:
        print(f"  {'✅' if r['ok'] else '🛑'} {r['fixture']:<34} expect={r['expect']:<5} got={r['got']}")
    print(f"══ selftest {'PASS' if ok else 'FAIL'}（{sum(1 for r in rows if r['ok'])}/{len(rows)}）")
    return 0 if ok else 1


# ── CLI ─────────────────────────────────────────────────
def build_parser():
    ap = argparse.ArgumentParser(
        description="批次门禁唯一确定性执行面（SA-4）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n  python scripts/batch_driver.py plan --batch batch048\n"
               "  python scripts/batch_driver.py check --batch batch048 --dry-run --json-out reports/gate/driver_batch048.json\n"
               "  python scripts/batch_driver.py selftest --fixture tests/fixtures/gates",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="只打印将跑的门禁与顺序，不执行")
    p_plan.add_argument("--batch", "-b", required=True)
    p_plan.add_argument("--json", action="store_true")

    p_check = sub.add_parser("check", help="执行目标 boundary 并输出结构化结论")
    p_check.add_argument("--batch", "-b", required=True)
    p_check.add_argument("--stage", "-s", default="auto",
                         choices=["auto", "r0", "r1", "a2", "a3", "a4", "lv", "a5", "r2", "r3", "final", "r4"])
    p_check.add_argument("--json-out", default=None)
    p_check.add_argument("--dry-run", action="store_true")
    p_check.add_argument("--no-halt", action="store_true")
    p_check.add_argument("--no-state-write", action="store_true")
    p_check.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p_check.add_argument("--fail-fast", action="store_true", default=True)
    p_check.add_argument("--no-stamp", action="store_true",
                         help="不写门禁回执（仅调试用；会让下游无法验证本次执行）")
    p_check.add_argument("--no-preflight", action="store_true",
                         help="跳过上游回执验真（绕过防跳过机制，风险自负，payload 会留痕）")
    p_check.add_argument("--ledger", default=None, help="回执链路径覆盖（测试用；默认最终产物/<batch>/_gate_ledger.json）")
    p_check.add_argument("--base", default=None, help="仓库根覆盖（仅用于回执链解析，测试用）")

    p_self = sub.add_parser("selftest", help="判定器自测（固定夹具）")
    p_self.add_argument("--fixture", default=str(FIXTURE_DIR.relative_to(BASE)))
    p_self.add_argument("--json", default=None)

    p_brief = sub.add_parser("brief", help="打印某阶段的人读交接单（L0 宿主 / 人工接力）")
    p_brief.add_argument("--batch", "-b", required=True)
    p_brief.add_argument("--stage", "-s", required=True,
                         choices=["a2", "a3", "a4", "a5"])
    p_brief.add_argument("--bundle", default=None,
                         help="交接包路径覆盖（测试 / 自定义仓库用；默认按 batch+stage 推导）")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "plan":
        return cmd_plan(args)
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "selftest":
        return cmd_selftest(args)
    if args.cmd == "brief":
        return cmd_brief(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
