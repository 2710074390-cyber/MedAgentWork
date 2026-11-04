#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_batch_context.py — 批次上下文构建器（SA-6）

为什么有这个脚本（2026-11-04，SA-6）：
    每个 Agent 起步按 SKILL「必读清单」整份读 CONTEXT.md / SOUL.md / USER.md / Prompt，
    5 个 Agent 合计 268,749 tok/批，其中共享基线被读 5 遍 = 191,884 tok（71%）。
    本脚本把「本批真正需要的那一页」压成 中间产物/{batch}/_ctx.md（≤8,000 chars），
    教师重点原文只留 ID 索引（_kpidx.jsonl sidecar），原文用 ctx_fetch.py 按 ID 取。

纪律：
    - 不改任何源文件；只新增 _ctx.md / _kpidx.jsonl（派生物，随批次归档）；
    - 不替代原文：_kpidx.jsonl 是 sidecar，check_keypoint_coverage.py 仍直接读原文；
    - 预算硬上限（默认 8,000 chars）：超限先降级（截短 KP 索引），仍超 → exit 1。

用法：
    python scripts/build_batch_context.py --batch batch048 [--out-dir 中间产物/batch048]
                                          [--json-out P] [--max-chars 8000] [--force]
退出码：0 成功 / 1 输入缺失或超预算 / 2 错误
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

if "pytest" not in sys.modules:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import workflow_state as ws  # noqa: E402

MAX_CTX_CHARS = 8000
KP_PATTERN = re.compile(r"^[ \t]*(\d{1,3})[.、][ \t]*(.+?)[ \t]*\r?$", re.M)


def subject_core(subject: str) -> str:
    s = str(subject or "").strip()
    s = re.sub(r"[（(].*?[)）]", "", s).strip()
    return s or "未知科目"


def find_keypoints(base: Path, subject: str):
    core = subject_core(subject)
    candidates = []
    for pat in (f"输入素材/**/{core}*锚定清单*.md", f"输入素材/**/{core}*教师重点*.md",
                f"输入素材/**/{core}*重点*.md"):
        candidates += sorted(base.glob(pat))
    if not candidates:
        return None
    candidates.sort(key=lambda p: ("锚定清单" not in p.name, -p.stat().st_size))
    return candidates[0]


def parse_keypoint_items(text: str):
    """解析教师重点锚定清单 → [{no, text, line, offset, chars}]。

    只取「统一锚定清单」小节之后的连续编号行；用 finditer 取精确字符偏移，
    保证 ctx_fetch 能逐字取回原文（不依赖换行符风格）。
    """
    heading = None
    for m in re.finditer(r"^#{1,4}.*统一锚定清单.*$", text, re.M):
        heading = m.start()
    start = heading if heading is not None else 0
    raw_items = []
    for m in KP_PATTERN.finditer(text, start):
        body = m.group(2).strip()
        if len(body) < 4:
            continue
        raw_items.append({
            "no": int(m.group(1)),
            "text": body,
            "line": text.count("\n", 0, m.start(2)) + 1,
            "offset": m.start(2),
            "chars": len(m.group(2)),
        })
    if not raw_items:
        return []
    by_no = {}
    for it in raw_items:
        by_no.setdefault(it["no"], it)
    seq, n = [], 1
    while n in by_no:
        seq.append(by_no[n])
        n += 1
    return seq or raw_items


def _gate_status_rows(data: dict):
    rows = []
    gr = data.get("gate_results") if isinstance(data.get("gate_results"), dict) else {}
    for name in ("GATE-A2", "GATE-A3", "GATE-A4", "GATE-LV", "GATE-FINAL"):
        if name in gr:
            rows.append((name, str(gr[name].get("status") or "?")))
    return rows


def _relevant_hc(data: dict, types):
    hc = []
    q = bool({"question_bank", "prediction_paper"} & set(types))
    if q:
        hc += [("HC-12", "门禁执行面 = batch_driver.py（唯一）", "§SOUL#HC-12 门禁强制"),
               ("HC-22", "考研族/执医族各 15%–25%；reduced/cancelled/deferred 须写理由", "§SOUL#HC-22 真题检索与双族配额"),
               ("HC-24", "学习价值层逐项/错误认知覆盖 100%，引文逐字", "§SOUL#HC-24 题目学习价值层契约"),
               ("HC-27", "每题 concepts：1 条 primary + 至少 1 条 differential", "§SOUL#HC-27 概念标注强制"),
               ("HC-28", "一次跑完，不等待人工；人工项只入 review_queue", "§SOUL#HC-28 一次跑完与人工复核队列分离"),
               ("HC-29", "干扰项机制 8 类枚举（逐字，不可摘要）", "§SOUL#HC-29 干扰项生成协议"),
               ("HC-13", "追溯日志顶层 source_file_synced=true", "§SOUL#HC-13 补丁溯源")]
    if "review_material" in types:
        hc += [("HC-20", "教师重点逐条覆盖，📌 落点条号取锚定清单连续编号", "§SOUL#HC-20 教师重点原文锚定与逐条覆盖"),
               ("HC-26", "九槽位/模块八块/课程八块，不得凑字数", "§SOUL#HC-26 复习资料详细度契约"),
               ("HC-21", "站点发布最新性（签收后）", "§SOUL#HC-21 站点发布最新性契约")]
    seen, out = set(), []
    for item in hc:
        if item[0] not in seen:
            seen.add(item[0])
            out.append(item)
    return out


def _pending_boundaries(batch_id: str, data: dict):
    try:
        import batch_driver as bd
        plan, _ = bd.plan_boundaries(batch_id, data)
        pending = [b for b in plan if not bd._has_pass_evidence(b, batch_id, data)]
        return pending[:5], plan
    except Exception:
        return [], []


def _quota_note(base: Path, batch_id: str):
    p = base / "中间产物" / batch_id / "real_question_plan.json"
    if not p.exists():
        return "无 real_question_plan.json（HC-22 终审会判 BLOCKED，需 plan 或 reduced/cancelled 理由）"
    try:
        plan = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return "real_question_plan.json 不可解析"
    st = plan.get("quota_status") or plan.get("status") or "?"
    counts = plan.get("counts") or {}
    return f"quota_status={st}；counts={json.dumps(counts, ensure_ascii=False)[:120]}"


def compose_ctx(batch_id, data, items, kp_rel, base: Path, max_chars: int = MAX_CTX_CHARS):
    """纯函数：返回 (ctx_text, budget, warnings, indexed_kp)。"""
    warnings = []
    subject = str(data.get("subject") or "")
    types = data.get("product_types") or []
    schema = data.get("item_schema_version") or "—"
    target_bloom = data.get("target_bloom") or "—"
    p9 = data.get("p9_mode") or "—"

    sec1 = (f"# {batch_id} · {subject}\n\n"
            f"- product_types: {', '.join(types) if isinstance(types, list) else types} ｜ "
            f"item_schema_version: {schema} ｜ p9_mode: {p9} ｜ target_bloom: {target_bloom}\n"
            f"- status: {data.get('status')}\n")

    rows = _gate_status_rows(data)
    gate_tbl = "\n".join(f"| {g} | {s} |" for g, s in rows) or "| （尚无门禁记录） | — |"
    sec2 = f"## 门禁状态\n\n| 门 | 状态 |\n|---|---|\n{gate_tbl}\n"

    sec3 = ("## 路径契约（逐字，禁止改写）\n\n"
            f"- 教师重点锚定清单：{kp_rel}\n"
            f"- A2 产物：中间产物/{batch_id}/ALL_questions.json\n"
            f"- A3 产物：质检报告/{batch_id}/A3_质检报告.json\n"
            f"- A4 产物：最终产物/{batch_id}/ALL_questions_FIXED.json\n"
            f"- A4 追溯：最终产物/{batch_id}/AGENT4_追溯日志.json\n"
            f"- 交付 MD：最终产物/{batch_id}/ALL_questions_FIXED.md\n"
            f"- 复核队列：最终产物/{batch_id}/review_queue.json\n"
            f"- 证据目录：reports/gate/ ｜ reports/validate/\n"
            f"- 上下文索引：中间产物/{batch_id}/_kpidx.jsonl\n")

    def kp_block(limit):
        lines = ["## 教师重点索引（原文按 ID 取：ctx_fetch.py --id KP-…）", "",
                 "| KP-ID | 条 | 首 20 字 |", "|---|---|---|"]
        for it in items[:limit]:
            head = it["text"][:20].replace("|", "／")
            lines.append(f"| KP-{batch_id}-{it['no']:03d} | {it['no']} | {head} |")
        if limit < len(items):
            lines.append(f"| （其余 {len(items) - limit} 条同格式，按 ID 取） | | |")
        return "\n".join(lines) + "\n"

    hc = _relevant_hc(data, types)
    hc_lines = ["## 硬约束（只列本批涉及；规则原文勿摘要，按指针取逐字）", ""]
    for rid, one, ptr in hc:
        hc_lines.append(f"- **{rid}**：{one} → ctx_fetch.py --id '{ptr}'")
    hc_lines.append("- HC-29 八类机制标签、release.disposition 三值等**枚举字面量必须逐字**（不可摘要）")
    hc_lines.append("- source_file_synced 必须在追溯日志**顶层**；bloom_distribution.actual 必须是百分数扁平形态")
    sec5 = "\n".join(hc_lines) + "\n"

    pending, plan = _pending_boundaries(batch_id, data)
    todo = "## 待办（driver 计划中尚无 PASS 证据的 boundary）\n\n"
    todo += ("\n".join(f"{i}. {b}" for i, b in enumerate(pending, 1)) if pending
             else "1. （无待办或全部已通过）")
    todo += "\n"

    sec7 = ("## 本批特殊\n\n"
            f"- HC-22 配额：{_quota_note(base, batch_id)}\n"
            f"- driver 执行序列：{' → '.join(plan) if plan else '（见 batch_driver.py plan）'}\n")

    sec8 = ("## 指针用法（一次取 ≤2,000 chars）\n\n"
            "python scripts/ctx_fetch.py --id '§SOUL#HC-22'\n"
            f"python scripts/ctx_fetch.py --id 'KP-{batch_id}-001'\n"
            "python scripts/ctx_fetch.py --id 'ART:batch047/A3#L1-L40'\n")

    sections = {"抬头": sec1, "门禁状态": sec2, "路径契约": sec3, "教师重点索引": kp_block(len(items)),
                "硬约束": sec5, "待办": todo, "本批特殊": sec7, "指针用法": sec8}
    text = "\n".join(sections.values())

    limit = len(items)
    while len(text) > max_chars and limit > 0:
        step = max(1, limit // 4)
        limit = max(0, limit - step)
        sections["教师重点索引"] = kp_block(limit)
        text = "\n".join(sections.values())
        warnings.append(f"超预算降级：KP 索引截断到 {limit}/{len(items)} 条")
    if len(text) > max_chars:
        sections["硬约束"] = "## 硬约束\n\n- 见 rules/registry.yaml 与各 HC 指针（预算不足已折叠）\n"
        text = "\n".join(sections.values())
        warnings.append("超预算降级：硬约束摘要折叠为指针")
    budget = {k: len(v) for k, v in sections.items()}
    return text, budget, warnings, limit


def build(batch_id: str, base: Path = BASE, out_dir: Path | None = None,
          max_chars: int = MAX_CTX_CHARS, force: bool = False):
    state, err = ws.load_state()
    if err:
        raise RuntimeError(f"读取 workflow_state 失败: {err}")
    data = state.get(batch_id)
    if not isinstance(data, dict):
        raise KeyError(f"批次 {batch_id} 不在 workflow_state.json 中")

    kp = find_keypoints(base, str(data.get("subject") or ""))
    if kp is None:
        raise FileNotFoundError("未找到教师重点/锚定清单输入（HC-20 范围契约缺失）")
    kp_text = kp.read_text(encoding="utf-8", errors="replace")
    items = parse_keypoint_items(kp_text)
    if not items:
        raise ValueError(f"锚定清单未解析出条目: {kp}")

    kp_rel = kp.relative_to(base).as_posix()
    text, budget, warnings, limit = compose_ctx(batch_id, data, items, kp_rel, base, max_chars)
    if len(text) > max_chars:
        raise ValueError(f"上下文仍超预算：{len(text)} > {max_chars}（降级后）")

    target = out_dir or (base / "中间产物" / batch_id)
    target.mkdir(parents=True, exist_ok=True)
    ctx_path = target / "_ctx.md"
    if ctx_path.exists() and not force:
        warnings.append("_ctx.md 已存在（--force 才覆盖），本次重写")
    ctx_path.write_text(text, encoding="utf-8")

    with (target / "_kpidx.jsonl").open("w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps({
                "id": f"KP-{batch_id}-{it['no']:03d}",
                "batch": batch_id,
                "src": kp_rel,
                "line": it["line"],
                "offset": it["offset"],
                "chars": it["chars"],
                "no": it["no"],
                "text": it["text"],
                "sha256": hashlib.sha256(it["text"].encode("utf-8")).hexdigest(),
            }, ensure_ascii=False) + "\n")

    return {
        "batch": batch_id,
        "subject": data.get("subject"),
        "ctx_path": str(ctx_path),
        "ctx_chars": len(text),
        "max_chars": max_chars,
        "kp_source": kp_rel,
        "kp_count": len(items),
        "kp_indexed": limit,
        "budget": budget,
        "warnings": warnings,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="批次上下文构建器（SA-6）")
    ap.add_argument("--batch", "-b", required=True)
    ap.add_argument("--out-dir", default=None, help="默认 中间产物/{batch}")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--max-chars", type=int, default=MAX_CTX_CHARS)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    try:
        result = build(args.batch, BASE, Path(args.out_dir) if args.out_dir else None,
                       args.max_chars, args.force)
    except (RuntimeError, KeyError, FileNotFoundError, ValueError) as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ _ctx.md {result['ctx_chars']}/{result['max_chars']} chars ｜ KP {result['kp_count']} 条 "
          f"｜ 预算 {result['budget']}")
    for w in result["warnings"]:
        print(f"  ⚠ {w}")
    print(f"  ↳ {result['ctx_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
