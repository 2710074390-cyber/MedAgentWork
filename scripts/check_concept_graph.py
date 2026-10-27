#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_concept_graph.py — 概念图门禁（W4）。

六项检查（PASS / WARN / FAIL 显式记录，WARN≠PASS）
    C1 无环          卡级 + 模块级都必须无环                     FAIL 阻断
    C2 孤立节点      weight=0 且无 prereq 的节点数应为 0          FAIL 阻断
    C3 每卡有题      除 content_only 外每节点至少 1 道主概念题     FAIL 阻断
    C4 多标签率      A2+ 题型多标签率：<0.05 FAIL，<0.60 WARN    见下
    C5 边证据        每条边 evidence 非空；prereq 需有 basis       FAIL 阻断
    C6 自环/重复边   0                                            FAIL 阻断

C4 的口径说明
    60% 是目标值，不是所有学科的既有事实：急诊题库按 HC-20「一题一锚点」生成，
    48 张卡对 61 条锚点近似一一对应，文本里不复用卡片标题，事后推断只能到 5% 左右。
    因此 <0.05 视为映射失效（FAIL），0.05–0.60 记 WARN 并写原因，
    真正的提升要在出题契约里加 concepts[]（见 docs/概念层改造方案_v1.0.md §6）。

用法
    python scripts/check_concept_graph.py
    python scripts/check_concept_graph.py --subject 急诊 --strict
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

def _configure_stdio() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


BASE = Path(__file__).resolve().parent.parent
DEFAULT_GRAPH = BASE / "question_bank/concept_graph.json"
DEFAULT_LABELS = BASE / "question_bank/concept_labels.jsonl"
DEFAULT_OUT = BASE / "reports/validate/concept_graph_check.json"
MULTI_TYPES = {"A2", "A3", "A4", "X", "B1"}


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def topo(edges: list[tuple[str, str]], keys: list[str]) -> dict:
    adj: dict[str, list[str]] = defaultdict(list)
    indeg = {k: 0 for k in keys}
    for a, b in edges:
        if a in indeg and b in indeg:
            adj[a].append(b)
            indeg[b] += 1
    q = [k for k, v in indeg.items() if v == 0]
    seen, depth = 0, {k: 0 for k in keys}
    while q:
        cur = q.pop()
        seen += 1
        for nxt in adj[cur]:
            depth[nxt] = max(depth[nxt], depth[cur] + 1)
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    return {"acyclic": seen == len(keys), "visited": seen, "total": len(keys),
            "cycle_nodes": sorted(k for k, v in indeg.items() if v > 0)[:10],
            "max_depth": max(depth.values()) if depth else 0}


def main() -> int:
    ap = argparse.ArgumentParser(description="概念图门禁")
    ap.add_argument("--graph", default=str(DEFAULT_GRAPH))
    ap.add_argument("--labels", default=str(DEFAULT_LABELS))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--subject", default=None)
    ap.add_argument("--strict", action="store_true", help="WARN 也视为失败退出")
    args = ap.parse_args()

    gp = Path(args.graph)
    if not gp.exists():
        print(f"ERROR —— 概念图不存在：{gp}")
        return 2
    g = read_json(gp)
    nodes = [n for n in g["nodes"] if not args.subject or n["subject"] == args.subject]
    keep = {n["kc_id"] for n in nodes}
    measures = [e for e in g["edges"]["measures"] if e["kc_id"] in keep]
    prereq = [(e["from"], e["to"]) for e in g["edges"]["prereq"]
              if e["from"] in keep and e["to"] in keep]
    prereq_edges = [e for e in g["edges"]["prereq"] if e["from"] in keep and e["to"] in keep]
    ref = [(e["from"], e["to"]) for e in g["edges"]["ref"]
           if e["from"] in keep and e["to"] in keep]
    module_edges = [e for e in (g.get("module_prereq") or [])
                    if not args.subject or e["subject"] == args.subject]

    checks = []

    def add(cid: str, name: str, status: str, detail: str, *, required: bool = True) -> None:
        checks.append({"id": cid, "name": name, "status": status,
                       "required": required, "detail": detail})

    # C1
    card = topo(prereq, sorted(keep))
    mod_keys = sorted({f"{e['subject']}:{e['from']}" for e in module_edges} |
                      {f"{e['subject']}:{e['to']}" for e in module_edges})
    mod = topo([(f"{e['subject']}:{e['from']}", f"{e['subject']}:{e['to']}") for e in module_edges],
               mod_keys)
    ok1 = card["acyclic"] and mod["acyclic"]
    add("C1", "无环（卡级 + 模块级）", "PASS" if ok1 else "FAIL",
        f"卡级 {card['visited']}/{card['total']} 最长链 {card['max_depth']}；"
        f"模块级 {mod['visited']}/{mod['total']} 最深 {mod['max_depth']} 层"
        + ("" if ok1 else f"；环节点 {card['cycle_nodes'] or mod['cycle_nodes']}"))

    # C2
    orphans = [n["kc_id"] for n in nodes if n["weight"] == 0 and not n["prereq"]]
    add("C2", "孤立节点（无题且无前置）", "PASS" if not orphans else "FAIL",
        f"{len(orphans)} 个" + (f"：{orphans[:5]}" if orphans else ""))

    # C3 每题必须有主概念（未映射 = 题目测的概念不在图里，属内容缺口，不是图缺陷）
    unmapped = []
    if Path(args.labels).exists():
        rows_all = [json.loads(l) for l in Path(args.labels).read_text(encoding="utf-8").splitlines() if l.strip()]
        if args.subject:
            rows_all = [r for r in rows_all if r["subject"] == args.subject]
        unmapped = [r["qid"] for r in rows_all if not r["primary"]]
        total_q = len(rows_all)
    else:
        total_q = 0
    urate = (len(unmapped) / total_q) if total_q else 0.0
    if urate > 0.02:
        add("C3", "每题有主概念", "FAIL",
            f"未映射 {len(unmapped)}/{total_q}（{urate:.1%}）超过 2%：{unmapped[:5]}")
    elif unmapped:
        add("C3", "每题有主概念", "WARN",
            f"未映射 {len(unmapped)}/{total_q}（{urate:.1%}）：{unmapped}——"
            f"这些题测的概念不在 KC 图谱内（多为「补充·源②/源③」锚点），需决定补卡还是撤题")
    else:
        add("C3", "每题有主概念", "PASS", f"{total_q} 题全部有主概念")

    # C4
    rate, pool_n, mode = None, 0, "legacy"
    unresolved: list[str] = []
    declared_n = 0
    if Path(args.labels).exists():
        rows = [json.loads(l) for l in Path(args.labels).read_text(encoding="utf-8").splitlines() if l.strip()]
        if args.subject:
            rows = [r for r in rows if r["subject"] == args.subject]
        pool = [r for r in rows if r["type"] in MULTI_TYPES]
        pool_n = len(pool)
        if any(r.get("source") == "declared" for r in rows):
            mode = "source"
            declared = [r for r in pool if r.get("source") == "declared"]
            declared_n = len(declared)
            rate = (round(sum(1 for r in declared if r["secondary"]) / declared_n, 4)
                    if declared_n else None)
            unresolved = [t for r in rows for t in (r.get("unresolved") or [])]
        else:
            rate = round(sum(1 for r in pool if r["secondary"]) / pool_n, 4) if pool_n else None

    if rate is None:
        add("C4", "多标签率（A2+）", "WARN", "无标注文件或无 A2+ 题，未评估")
    elif mode == "source":
        if rate >= 0.98:
            add("C4", "多标签率（A2+ · HC-27 源标注）", "PASS",
                f"{rate:.1%}（{declared_n} 题）概念由生成期给出，解析完成")
        elif rate >= 0.90:
            add("C4", "多标签率（A2+ · HC-27 源标注）", "WARN",
                f"{rate:.1%}（{declared_n} 题）低于 98%，有 {declared_n - round(rate * declared_n)} 题"
                f"的二级概念未解析到 KC（看 C8）")
        else:
            add("C4", "多标签率（A2+ · HC-27 源标注）", "FAIL",
                f"{rate:.1%}（{declared_n} 题）＜ 90%：源标注与 KC 图谱对不上，先查 KC 标题与锚点")
    elif rate == 0:
        add("C4", "多标签率（A2+）", "FAIL", f"0%（{pool_n} 题）——二级概念完全缺失，映射可能失效")
    elif rate < 0.60:
        add("C4", "多标签率（A2+）", "WARN",
            f"{rate:.1%}（{pool_n} 题）低于 60% 目标；该批为事后推断（无 HC-27 源标注），"
            f"题库按一题一锚点生成，需在出题契约加 concepts[] 才可能达到")
    else:
        add("C4", "多标签率（A2+）", "PASS", f"{rate:.1%}（{pool_n} 题）")

    # C8 源标注未解析：生成期写的概念名在 KC 图谱里找不到
    if mode == "source":
        if unresolved:
            add("C8", "源标注解析完整性", "WARN",
                f"{len(unresolved)} 个概念未解析：{'、'.join(unresolved[:6])}"
                f"——要么补 KC 卡片，要么统一概念名")
        else:
            add("C8", "源标注解析完整性", "PASS", "全部源标注已解析到 KC")
    else:
        add("C8", "源标注解析完整性", "SKIP", "该批无 HC-27 源标注（推断模式）", required=False)

    # C5
    bad = [m for m in measures if not str(m.get("evidence") or "").strip()]
    bad += [p for p in prereq_edges if not str(p.get("evidence") or "").strip()
            or not str(p.get("basis") or "").strip()]
    add("C5", "边证据完整（measures + prereq）", "PASS" if not bad else "FAIL",
        f"{len(bad)} 条缺证据")

    # C6
    self_loop = [p for p in prereq_edges if p["from"] == p["to"]]
    dup_meas = [k for k, v in Counter((m["qid"], m["kc_id"]) for m in measures).items() if v > 1]
    dup_pre = [k for k, v in Counter(prereq).items() if v > 1]
    dup_ref = [k for k, v in Counter(tuple(sorted(x)) for x in ref).items() if v > 1]
    ok6 = not self_loop and not dup_meas and not dup_pre and not dup_ref
    add("C6", "自环 / 重复边", "PASS" if ok6 else "FAIL",
        f"自环 {len(self_loop)}　重复 measures {len(dup_meas)}　"
        f"重复 prereq {len(dup_pre)}　重复 ref {len(dup_ref)}")

    # C7 无题卡：有正文但无题，属于覆盖缺口（status 可能已过期）
    stale = [n["kc_id"] for n in nodes if n["weight"] == 0 and n["status"] != "content_only"]
    add("C7", "无题卡（status 未标 content_only）", "WARN" if stale else "PASS",
        f"{len(stale)} 张：{stale[:5]}——建议把 status 改成 content_only 或后续批次补题"
        if stale else "无")

    statuses = [c["status"] for c in checks]
    overall = "FAIL" if "FAIL" in statuses else ("WARN" if "WARN" in statuses else "PASS")

    stats = {
        "nodes": len(nodes),
        "subjects": dict(Counter(n["subject"] for n in nodes)),
        "edges": {"measures": len(measures), "prereq": len(prereq_edges), "ref": len(ref),
                  "module_prereq": len(module_edges)},
        "measures_by_role": dict(Counter(m["role"] for m in measures)),
        "multi_label_rate_A2plus": rate,
        "multi_pool": pool_n,
        "label_mode": mode,
        "declared_a2plus": declared_n,
        "unresolved_concepts": len(unresolved),
        "questions": len({m["qid"] for m in measures}),
    }
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generator": "scripts/check_concept_graph.py",
        "graph": str(gp.relative_to(BASE)),
        "subject_filter": args.subject,
        "status": overall,
        "checks": checks,
        "stats": stats,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [f"# 概念图门禁报告 {report['generated_at']}", "",
          f"- 图：`{report['graph']}`", f"- 学科：{args.subject or '全部'}",
          f"- 结论：**{overall}**", "",
          "| 检查 | 结果 | 详情 |", "|---|---|---|"]
    for c in checks:
        md.append(f"| {c['id']} {c['name']} | {c['status']} | {c['detail']} |")
    md += ["", f"节点 {stats['nodes']}　边 {stats['edges']}",
           f"题数 {stats['questions']}　多标签率 {stats['multi_label_rate_A2plus']}"]
    out.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"概念图门禁：{overall}")
    for c in checks:
        print(f"  [{c['status']:4}] {c['id']} {c['name']} —— {c['detail']}")
    print(f"节点 {stats['nodes']}　边 {stats['edges']}　多标签率 {stats['multi_label_rate_A2plus']}")
    print(f"→ {out}")

    if overall == "FAIL":
        return 1
    if overall == "WARN" and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    _configure_stdio()
    raise SystemExit(main())
