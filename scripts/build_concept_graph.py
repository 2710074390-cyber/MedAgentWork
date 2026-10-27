#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_concept_graph.py — 概念层建图（W1/W3）。

职责
    1. 自动发现各批次 kc_registry.json（中间产物/ 与 archive/中间产物/），按 (subject, batch) 去重。
    2. 归一节点：**从 display_id 重解析模块**（急诊注册表 module 字段全为 M00，不可信）。
    3. 建三类边：
       measures  题 × KC（先用注册表 question_ids 播种，W2 会带证据重建）
       prereq    同模块按教材页序相邻成链 + 模块链（全序子链，天然无环）
       ref       共享教师重点条号 / 页码重叠
    4. 拓扑校验并输出统计。

设计约束
    - 每条边必须带 evidence/basis，答不出"凭什么连"就不建边。
    - 只读注册表与题目，不写 最终产物/、不写 复习资料/。
    - 人工覆盖：question_bank/concept_prereq_overrides.json（{"add":[], "remove":[]}）。

用法
    python scripts/build_concept_graph.py --out question_bank/concept_graph.json
    python scripts/build_concept_graph.py --subject 急诊
    python scripts/build_concept_graph.py --no-prereq          # 只出节点与 measures
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

def _configure_stdio() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


BASE = Path(__file__).resolve().parent.parent
DEFAULT_OUT = BASE / "question_bank/concept_graph.json"
DEFAULT_REPORT = BASE / "reports/validate/concept_graph_build.json"
DEFAULT_OVERRIDES = BASE / "question_bank/concept_prereq_overrides.json"
REGISTRY_GLOBS = ("中间产物/*/pilot/kc_registry.json", "archive/中间产物/*/pilot/kc_registry.json")

MODULE_RE = re.compile(r"K-M(\d{2})-(\d{3})")


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def discover_registries() -> list[Path]:
    """扫描两处注册表，同一 (subject, batch) 只保留一份；中间产物/ 优先于 archive/。"""
    found: list[Path] = []
    for g in REGISTRY_GLOBS:
        found.extend(sorted(BASE.glob(g)))
    best: dict[tuple[str, str], Path] = {}
    for p in found:
        try:
            d = read_json(p)
        except Exception:
            continue
        key = (str(d.get("subject", "")), str(d.get("batch", "")))
        prev = best.get(key)
        if prev is None or ("archive" in str(prev) and "archive" not in str(p)):
            best[key] = p
    return [best[k] for k in sorted(best)]


def parse_module(card: dict) -> tuple[str, bool]:
    """返回 (模块, 是否修正了 module 字段)。"""
    for key in ("display_id", "kc_id"):
        m = MODULE_RE.search(str(card.get(key, "")))
        if m:
            return f"M{m.group(1)}", card.get("module") != f"M{m.group(1)}"
    return str(card.get("module") or "M00"), False


def page_key(node: dict) -> tuple:
    pages = node.get("source_pages") or []
    return (min(pages) if pages else 10**6, node["display_id"])


def build(registries: list[Path], with_prereq: bool, overrides: dict,
          labels: dict[str, dict] | None = None) -> tuple[dict, dict]:
    nodes: list[dict] = []
    measures: list[dict] = []
    ref_raw: list[dict] = []
    subjects: list[dict] = []
    fixed_modules: list[str] = []
    seen_kc: set[str] = set()

    for reg_path in registries:
        reg = read_json(reg_path)
        subject = str(reg.get("subject", ""))
        batch = str(reg.get("batch", ""))
        meta = reg.get("metadata") or {}
        cards = reg.get("cards") or []
        stats_before = len(nodes)
        q_counter: Counter = Counter()

        for card in cards:
            display = str(card.get("display_id") or "")
            module, fixed = parse_module(card)
            if fixed:
                fixed_modules.append(f"{subject}:{display}({card.get('module')}→{module})")
            kc_id = str(card.get("kc_id") or f"{subject}:{display}")
            if kc_id in seen_kc:
                continue
            seen_kc.add(kc_id)
            qids = list(card.get("question_ids") or [])
            for q in qids:
                q_counter[kc_id] += 1
            nodes.append({
                "kc_id": kc_id,
                "display_id": display,
                "subject": subject,
                "module": module,
                "title": str(card.get("title") or ""),
                "keypoints": list(card.get("keypoints") or []),
                "source_pages": list(card.get("source_pages") or []),
                "review_anchor": str(card.get("review_anchor") or ""),
                "content_chars": int(card.get("content_chars") or 0),
                "status": str(card.get("status") or "active"),
                "weight": 0,
                "hub": 0,
                "prereq": [],
                "lens": [],
                "questions": [],
                "batch": batch,
                "registry": str(reg_path.relative_to(BASE)),
            })
            for q in qids:
                measures.append({
                    "qid": q, "kc_id": kc_id, "role": "primary",
                    "evidence": "kc_registry.question_ids", "confidence": "registry",
                })

        # ref 边：同科内 共享 keypoint 或 页码重叠
        subj_nodes = [n for n in nodes[stats_before:]]
        for i in range(len(subj_nodes)):
            for j in range(i + 1, len(subj_nodes)):
                a, b = subj_nodes[i], subj_nodes[j]
                shared_kp = sorted(set(a["keypoints"]) & set(b["keypoints"]))
                if shared_kp:
                    ref_raw.append({"from": a["kc_id"], "to": b["kc_id"], "basis": "same_keypoint",
                                    "evidence": "共享教师重点第" + "、".join(str(k) for k in shared_kp) + "条"})
                    continue
                pages_a, pages_b = set(a["source_pages"]), set(b["source_pages"])
                overlap = sorted(pages_a & pages_b)
                if overlap and len(overlap) >= 1 and len(pages_a) + len(pages_b) <= 6:
                    ref_raw.append({"from": a["kc_id"], "to": b["kc_id"], "basis": "same_page",
                                    "evidence": "页码重叠 P" + "、".join(str(p) for p in overlap)})

        subjects.append({
            "subject": subject,
            "batch": batch,
            "registry": str(reg_path.relative_to(BASE)),
            "module_weights": meta.get("blueprint_weights") or {},
            "stats": {"nodes": len(nodes) - stats_before, "questions": sum(q_counter.values())},
        })

    # labels 优先：有标注就用标注重建 measures（带证据），否则保留注册表播种
    if labels:
        valid = {n["kc_id"] for n in nodes}
        rebuilt: list[dict] = []
        for qid, row in labels.items():
            p = row.get("primary")
            if p in valid:
                rebuilt.append({
                    "qid": qid, "kc_id": p, "role": "primary",
                    "evidence": str(row.get("primary_evidence")
                                    or "题目主概念（kc_question_map / 教师锚点标题命中）"),
                    "confidence": "high",
                })
            for s in row.get("secondary") or []:
                if s.get("kc_id") in valid:
                    rebuilt.append({
                        "qid": qid, "kc_id": s["kc_id"],
                        "role": s.get("role") or "related",
                        "evidence": str(s.get("evidence") or ""),
                        "confidence": s.get("confidence") or "medium",
                        "basis": s.get("basis") or "",
                    })
        if rebuilt:
            measures = rebuilt

    prim_by_kc: dict[str, list[str]] = defaultdict(list)
    for m in measures:
        if m["role"] == "primary":
            prim_by_kc[m["kc_id"]].append(m["qid"])
    for n in nodes:
        n["questions"] = sorted(prim_by_kc.get(n["kc_id"], []))
        n["weight"] = len(n["questions"])

    # prereq 边
    prereq: list[dict] = []
    if with_prereq:
        by_subj: dict[str, list[dict]] = defaultdict(list)
        for n in nodes:
            by_subj[n["subject"]].append(n)
        for subject, ns in by_subj.items():
            by_mod: dict[str, list[dict]] = defaultdict(list)
            for n in ns:
                by_mod[n["module"]].append(n)
            order = sorted(by_mod)
            for mi, mod in enumerate(order):
                chain = sorted(by_mod[mod], key=page_key)
                for a, b in zip(chain, chain[1:]):
                    pa = (a["source_pages"] or [None])[0]
                    pb = (b["source_pages"] or [None])[0]
                    prereq.append({
                        "from": a["kc_id"], "to": b["kc_id"], "basis": "page_order",
                        "evidence": f"{a['display_id']}(P{pa}) → {b['display_id']}(P{pb})",
                    })
                if mi + 1 < len(order):
                    nxt = sorted(by_mod[order[mi + 1]], key=page_key)
                    if chain and nxt:
                        prereq.append({
                            "from": chain[-1]["kc_id"], "to": nxt[0]["kc_id"],
                            "basis": "module_order",
                            "evidence": f"{mod} 末卡 → {order[mi + 1]} 首卡",
                        })

    # 人工覆盖
    for e in (overrides.get("remove") or []):
        prereq = [p for p in prereq if not (p["from"] == e.get("from") and p["to"] == e.get("to"))]
    for e in (overrides.get("add") or []):
        if e.get("from") and e.get("to"):
            prereq.append({"from": e["from"], "to": e["to"], "basis": "manual",
                           "evidence": str(e.get("reason") or "人工指定")})

    # 模块级前置（真正的学习门控；卡级边只表达阅读顺序）
    module_edges: list[dict] = []
    for s in subjects:
        mods = sorted({n["module"] for n in nodes if n["subject"] == s["subject"]})
        for a, b in zip(mods, mods[1:]):
            module_edges.append({
                "subject": s["subject"], "from": a, "to": b,
                "basis": "teaching_order", "strength": "hard",
                "evidence": f"教学顺序 {a} → {b}",
            })

    # 回填 prereq / hub
    idx = {n["kc_id"]: n for n in nodes}
    for p in prereq:
        if p["from"] in idx and p["to"] in idx and p["from"] != p["to"]:
            idx[p["to"]]["prereq"].append(p["from"])
    children: Counter = Counter()
    for p in prereq:
        children[p["from"]] += 1
    for n in nodes:
        n["prereq"] = sorted(set(n["prereq"]))
        n["hub"] = n["weight"] + children[n["kc_id"]]

    # ref 去重 + 每条最多 5 个
    seen_pair: set[tuple[str, str]] = set()
    prereq_pairs = {(p["from"], p["to"]) for p in prereq} | {(p["to"], p["from"]) for p in prereq}
    ref: list[dict] = []
    per_node: Counter = Counter()
    for e in sorted(ref_raw, key=lambda x: -idx[x["from"]]["weight"] if x["from"] in idx else 0):
        a, b = e["from"], e["to"]
        if a not in idx or b not in idx:
            continue
        key = tuple(sorted((a, b)))
        if key in seen_pair or key in prereq_pairs:
            continue
        if per_node[a] >= 5 or per_node[b] >= 5:
            continue
        seen_pair.add(key)
        per_node[a] += 1
        per_node[b] += 1
        ref.append(e)

    graph = {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generator": "scripts/build_concept_graph.py",
        "source_registries": [str(p.relative_to(BASE)) for p in registries],
        "subjects": subjects,
        "nodes": sorted(nodes, key=lambda n: (n["subject"], n["module"], n["display_id"])),
        "edges": {"measures": measures, "prereq": prereq, "ref": ref},
        "module_prereq": module_edges,
    }

    report = {
        "generated_at": graph["generated_at"],
        "registries": [str(p.relative_to(BASE)) for p in registries],
        "subjects": [s["subject"] for s in subjects],
        "nodes": len(nodes),
        "edges": {k: len(v) for k, v in graph["edges"].items()},
        "module_fixed": fixed_modules,
        "module_fixed_count": len(fixed_modules),
        "modules_by_subject": {
            s: dict(sorted(Counter(n["module"] for n in nodes if n["subject"] == s).items()))
            for s in {n["subject"] for n in nodes}
        },
        "orphan_nodes": sorted(n["kc_id"] for n in nodes if n["weight"] == 0 and not n["prereq"]),
        "empty_title": sorted(n["kc_id"] for n in nodes if not n["title"]),
        "measures_by_role": dict(Counter(m["role"] for m in measures)),
        "measures_by_confidence": dict(Counter(m.get("confidence") for m in measures)),
    }
    return graph, report


def check_acyclic(graph: dict, strength: str | None = None) -> dict:
    """strength=None 全图；"hard" 只看硬前置（模块链），用于判断学习空间深度。"""
    nodes = [n["kc_id"] for n in graph["nodes"]]
    adj: dict[str, list[str]] = defaultdict(list)
    indeg = {k: 0 for k in nodes}
    for e in graph["edges"]["prereq"]:
        if strength and e.get("strength") != strength:
            continue
        if e["from"] in indeg and e["to"] in indeg:
            adj[e["from"]].append(e["to"])
            indeg[e["to"]] += 1
    q = [k for k, v in indeg.items() if v == 0]
    seen = 0
    depth = {k: 0 for k in nodes}
    while q:
        cur = q.pop()
        seen += 1
        for nxt in adj[cur]:
            depth[nxt] = max(depth[nxt], depth[cur] + 1)
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    cycles = sorted(k for k, v in indeg.items() if v > 0)
    return {"acyclic": seen == len(nodes), "visited": seen, "total": len(nodes),
            "cycle_nodes": cycles[:10], "max_depth": max(depth.values()) if depth else 0}


def check_module_acyclic(edges: list[dict]) -> dict:
    """模块级前置必须无环；有环说明学科模块划分自相矛盾。"""
    adj: dict[str, list[str]] = defaultdict(list)
    keys: set[str] = set()
    for e in edges:
        a, b = f"{e['subject']}:{e['from']}", f"{e['subject']}:{e['to']}"
        keys.update((a, b))
        adj[a].append(b)
    indeg = {k: 0 for k in keys}
    for a, bs in adj.items():
        for b in bs:
            indeg[b] += 1
    q = [k for k, v in indeg.items() if v == 0]
    seen = 0
    depth = {k: 0 for k in keys}
    while q:
        cur = q.pop()
        seen += 1
        for nxt in adj[cur]:
            depth[nxt] = max(depth[nxt], depth[cur] + 1)
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    return {"acyclic": seen == len(keys), "modules": len(keys),
            "cycle_nodes": sorted(k for k, v in indeg.items() if v > 0),
            "max_depth": max(depth.values()) if depth else 0}


def main() -> int:
    ap = argparse.ArgumentParser(description="概念层建图")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--report", default=str(DEFAULT_REPORT))
    ap.add_argument("--overrides", default=str(DEFAULT_OVERRIDES))
    ap.add_argument("--labels", default=str(BASE / "question_bank/concept_labels.jsonl"),
                    help="label_concepts.py 产物；存在则用标注重建 measures")
    ap.add_argument("--subject", default=None, help="只建某学科，如 急诊")
    ap.add_argument("--no-prereq", action="store_true")
    args = ap.parse_args()

    regs = discover_registries()
    if not regs:
        print("ERROR —— 未发现 kc_registry.json")
        return 2
    if args.subject:
        keep = []
        for p in regs:
            if str(read_json(p).get("subject", "")) == args.subject:
                keep.append(p)
        regs = keep
        if not regs:
            print(f"ERROR —— 无匹配学科：{args.subject}")
            return 2

    ov = {"add": [], "remove": []}
    ov_path = Path(args.overrides)
    if ov_path.exists():
        ov = {**ov, **read_json(ov_path)}

    labels = None
    lp = Path(args.labels)
    if lp.exists():
        labels = {}
        for line in lp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                labels[str(row.get("qid"))] = row

    graph, report = build(regs, not args.no_prereq, ov, labels)
    report["labels_source"] = str(lp) if labels else None
    report["acyclic"] = check_acyclic(graph)
    report["module_acyclic"] = check_module_acyclic(graph.get("module_prereq") or [])
    report["unique_qids"] = len({m["qid"] for m in graph["edges"]["measures"]})
    report["prereq_basis"] = dict(Counter(e.get("basis") for e in graph["edges"]["prereq"]))
    write_json(Path(args.out), graph)
    write_json(Path(args.report), report)

    print(f"注册表 {len(regs)} 份：{[str(p) for p in regs]}")
    print(f"节点 {report['nodes']}　边 {report['edges']}　去重题数 {report['unique_qids']}")
    print(f"前置边构成 {report['prereq_basis']}　模块前置 {len(graph['module_prereq'])} 条")
    print(f"模块修正 {report['module_fixed_count']} 处")
    print(f"模块分布 {report['modules_by_subject']}")
    print(f"卡级无环={report['acyclic']['acyclic']}（最长链 {report['acyclic']['max_depth']}）"
          f"　模块级无环={report['module_acyclic']['acyclic']}（最深 {report['module_acyclic']['max_depth']} 层）")
    print(f"孤立节点 {len(report['orphan_nodes'])}　空标题 {len(report['empty_title'])}")
    print(f"→ {args.out}")
    ok = report["acyclic"]["acyclic"] and report["module_acyclic"]["acyclic"]
    return 0 if ok else 1


if __name__ == "__main__":
    _configure_stdio()
    raise SystemExit(main())
