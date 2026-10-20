# -*- coding: utf-8 -*-
"""planner.py — 教师重点驱动的双配额 + 覆盖约束选题。"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from .retrieval import (
    ItemRetriever,
    KeyPoint,
    answer_bonus,
    keypoint_queries,
    keypoint_relevance,
    parse_keypoints,
    year_bonus,
)
from .schema import RealQuestion, read_jsonl

BASE = Path(__file__).resolve().parent.parent.parent
DEFAULT_INDEX_DIR = BASE / "question_bank" / "real_questions"


@dataclass
class Module:
    module_id: str
    name: str
    target: int
    text: str = ""


def parse_blueprint(path: str | Path | None, subject: str, target: int) -> list[Module]:
    """解析出题蓝图中的模块 × 题数表。"""
    if path:
        p = Path(path)
        if p.exists():
            modules: list[Module] = []
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s.startswith("|"):
                    continue
                cells = [c.strip() for c in s.strip("|").split("|")]
                if len(cells) < 3:
                    continue
                if not re.fullmatch(r"M\d+", cells[0]):
                    continue
                nums = []
                for c in cells[2:]:
                    c2 = c.replace("*", "").strip()
                    if re.fullmatch(r"\d+", c2):
                        nums.append(int(c2))
                if not nums:
                    continue
                modules.append(Module(
                    module_id=cells[0],
                    name=cells[1],
                    target=nums[-1],
                    text=" ".join(cells),
                ))
            if modules:
                return _scale_modules(modules, target)
    return [Module(module_id="ALL", name=subject, target=target, text=subject)]


def _scale_modules(modules: list[Module], target: int) -> list[Module]:
    total = sum(m.target for m in modules)
    if total <= 0:
        each = max(1, target // len(modules))
        for m in modules:
            m.target = each
        modules[0].target += target - sum(m.target for m in modules)
        return modules
    scaled = [max(1, round(m.target * target / total)) for m in modules]
    diff = target - sum(scaled)
    # 差额优先给最大的模块
    order = sorted(range(len(modules)), key=lambda i: -modules[i].target)
    i = 0
    while diff != 0 and modules:
        idx = order[i % len(order)]
        if diff > 0:
            scaled[idx] += 1
            diff -= 1
        elif scaled[idx] > 1:
            scaled[idx] -= 1
            diff += 1
        i += 1
        if i > 10000:
            break
    for m, n in zip(modules, scaled):
        m.target = n
    return modules


def _allocate_source(total: int, modules: list[Module]) -> dict[str, int]:
    """按模块题数比例分配来源配额。"""
    if not modules:
        return {}
    weight_sum = sum(m.target for m in modules) or len(modules)
    out: dict[str, int] = {}
    assigned = 0
    for m in modules:
        n = int(math.floor(total * m.target / weight_sum))
        out[m.module_id] = n
        assigned += n
    diff = total - assigned
    order = sorted(modules, key=lambda m: -m.target)
    i = 0
    while diff > 0 and order:
        out[order[i % len(order)].module_id] += 1
        diff -= 1
        i += 1
    return out


def _assign_keypoints_to_modules(keypoints: list[KeyPoint], modules: list[Module]) -> dict[str, list[KeyPoint]]:
    """按考点文本与模块名的词重叠分配；无重叠时给最大模块。"""
    assigned: dict[str, list[KeyPoint]] = {m.module_id: [] for m in modules}
    if not keypoints:
        return assigned
    if len(modules) == 1:
        assigned[modules[0].module_id] = list(keypoints)
        return assigned
    for kp in keypoints:
        text = kp.text
        best = None
        best_score = -1
        for m in modules:
            score = 0
            for token in re.split(r"[\s,，、；;：:（）()/]+", m.name + " " + m.text):
                token = token.strip()
                if len(token) >= 2 and token in text:
                    score += 1
            if score > best_score:
                best_score = score
                best = m
        if best is None:
            best = max(modules, key=lambda m: m.target)
        assigned[best.module_id].append(kp)
    return assigned


def _candidate_kp_refs(
    retriever: ItemRetriever,
    queries: list[str],
    kp: KeyPoint,
    subject: str,
    top_k: int = 40,
) -> list[tuple[float, RealQuestion, list[str]]]:
    """检索某考点，返回 (rrf, item, matched_queries) 并标注 kp_ref。"""
    results = retriever.search_multi(queries, top_k=top_k, subject=subject)
    out = []
    for score, item, matched in results:
        if exact_keypoint_bonus(item, kp.text) > 0.04 or any(kp.text[:12] in q for q in matched):
            out.append((score, item, matched))
    return out


def build_plan(
    subject: str,
    target: int,
    index_dir: str | Path = DEFAULT_INDEX_DIR,
    keypoints_path: str | Path | None = None,
    blueprint_path: str | Path | None = None,
    quota_kaoyan: float = 0.20,
    quota_zhiyi: float = 0.20,
    batch: str = "",
    top_k_per_keypoint: int = 40,
) -> dict:
    index_dir = Path(index_dir)
    items: list[RealQuestion] = []
    for name in ("kaoyan_items.jsonl", "zhiyi_items.jsonl"):
        p = index_dir / name
        if p.exists():
            items.extend(read_jsonl(p))
    if not items:
        raise FileNotFoundError(
            f"未找到题目索引：{index_dir}。先运行 "
            f"python scripts/real_question_cli.py build"
        )

    keypoints = parse_keypoints(keypoints_path) if keypoints_path else []
    modules = parse_blueprint(blueprint_path, subject, target)
    kp_by_module = _assign_keypoints_to_modules(keypoints, modules)
    retriever = ItemRetriever(items)

    req_kaoyan = round(target * quota_kaoyan)
    req_zhiyi = round(target * quota_zhiyi)
    # 选题按目标配额封顶；15%–25% 合格带只用于终审容忍，不用于多选
    max_kaoyan = req_kaoyan
    max_zhiyi = req_zhiyi
    kaoyan_caps = _allocate_source(req_kaoyan, modules)
    zhiyi_caps = _allocate_source(req_zhiyi, modules)

    selected: list[dict] = []
    used_ids: set[str] = set()
    candidate_ids: dict[str, set[str]] = {"kaoyan": set(), "zhiyi": set()}
    module_selected: dict[str, list[RealQuestion]] = {m.module_id: [] for m in modules}
    module_kp: dict[str, list[KeyPoint]] = kp_by_module
    uncovered_by_module: dict[str, set[str]] = {
        m.module_id: {kp.ref for kp in module_kp.get(m.module_id, [])} for m in modules
    }
    search_log: list[dict] = []
    source_counts = {"kaoyan": 0, "zhiyi": 0}

    for module in modules:
        pool: dict[str, dict] = {}
        kps = module_kp.get(module.module_id, [])
        query_sets = [(kp, keypoint_queries(kp)) for kp in kps]
        if not query_sets:
            query_sets = [(None, [module.name])]
        for kp, queries in query_sets:
            try:
                results = retriever.search_multi(
                    queries,
                    top_k=top_k_per_keypoint,
                    subject=subject,
                )
            except Exception as exc:  # 检索失败不应中断整批
                search_log.append({"module": module.module_id, "keypoint": kp.ref if kp else "", "error": str(exc)})
                continue
            search_log.append({
                "module": module.module_id,
                "keypoint": kp.ref if kp else "",
                "queries": len(queries),
                "hits": len(results),
            })
            for score, item, matched in results:
                # 有考点时按考点相关性过滤；无考点时按模块名相关性过滤
                rel = keypoint_relevance(item, kp.text if kp is not None else module.name)
                if rel <= 0:
                    continue
                rec = pool.setdefault(item.item_id, {
                    "item": item,
                    "score": score,
                    "relevance": rel,
                    "kp_scores": {},
                    "matched": list(matched),
                })
                if item.source in candidate_ids:
                    candidate_ids[item.source].add(item.item_id)
                rec["score"] = max(rec["score"], score)
                rec["relevance"] = max(rec.get("relevance", 0.0), rel)
                if kp is not None:
                    rec["kp_scores"][kp.ref] = max(rec["kp_scores"].get(kp.ref, 0.0), rel)

        # 贪心：先覆盖未覆盖考点，再取相关性
        module_target = module.target
        selected_here = module_selected[module.module_id]
        source_here = {"kaoyan": 0, "zhiyi": 0}
        # 小模块至少允许 1 题/来源，避免 floor 后为 0 导致整模块无真题
        local_cap = {
            "kaoyan": max(1, kaoyan_caps.get(module.module_id, 0)) if module_target >= 5 else 0,
            "zhiyi": max(1, zhiyi_caps.get(module.module_id, 0)) if module_target >= 5 else 0,
        }
        while len(selected_here) < module_target:
            best = None
            best_gain = -1.0
            for rec in pool.values():
                item: RealQuestion = rec["item"]
                if item.item_id in used_ids:
                    continue
                if item.source not in ("kaoyan", "zhiyi"):
                    continue
                if source_here[item.source] >= local_cap.get(item.source, 0):
                    # 本地来源配额已满，但另一来源可补足模块目标
                    continue
                if source_counts[item.source] >= (max_kaoyan if item.source == "kaoyan" else max_zhiyi):
                    continue
                uncovered = uncovered_by_module.get(module.module_id, set())
                # 一题最多认领 3 个考点，避免长考点文本导致「一题覆盖 30 条」
                active_refs = set(sorted(
                    rec.get("kp_scores", {}),
                    key=lambda r: -rec["kp_scores"].get(r, 0.0),
                )[:3])
                coverage_gain = sum(1.0 for ref in active_refs if ref in uncovered)
                relevance = (
                    rec["score"] * 10
                    + rec.get("relevance", 0.0) * 0.6
                    + year_bonus(item.year)
                    + answer_bonus(item.answer_confidence)
                )
                if item.source == "kaoyan":
                    relevance += 0.02
                gain = relevance + 0.8 * coverage_gain
                if gain > best_gain:
                    best_gain = gain
                    best = rec
            if best is None:
                break
            item = best["item"]
            used_ids.add(item.item_id)
            selected_here.append(item)
            source_here[item.source] += 1
            source_counts[item.source] += 1
            active_refs = set(sorted(
                best.get("kp_scores", {}),
                key=lambda r: -best["kp_scores"].get(r, 0.0),
            )[:3])
            uncovered_by_module[module.module_id] -= active_refs
            selected.append(_selected_record(item, module, best["score"], active_refs, best["matched"]))

        # 本地来源配额没填满时，允许另一来源补足模块目标（受全局 25% 上限约束）
        if len(selected_here) < module_target:
            for rec in sorted(pool.values(), key=lambda r: -(r["score"] * 10 + r.get("relevance", 0.0))):
                if len(selected_here) >= module_target:
                    break
                item: RealQuestion = rec["item"]
                if item.item_id in used_ids:
                    continue
                if source_counts[item.source] >= (max_kaoyan if item.source == "kaoyan" else max_zhiyi):
                    continue
                # 另一来源可补足模块目标，但不得让单模块超过题数上限
                if source_here[item.source] >= module_target:
                    continue
                used_ids.add(item.item_id)
                selected_here.append(item)
                source_here[item.source] += 1
                source_counts[item.source] += 1
                active_refs = set(sorted(
                    rec.get("kp_scores", {}),
                    key=lambda r: -rec["kp_scores"].get(r, 0.0),
                )[:3])
                uncovered_by_module[module.module_id] -= active_refs
                selected.append(_selected_record(item, module, rec["score"], active_refs, rec["matched"]))

    # 配额状态
    def status(req: int, got: int, available: int) -> dict:
        if got >= req:
            s = "met"
        elif available == 0:
            s = "unavailable"
        elif got >= available:
            s = "insufficient"   # 相关候选已全部用上
        else:
            s = "underfilled"    # 还有候选但未选，属异常
        return {"requested": req, "selected": got, "available": available, "status": s}

    # 可用量 = 本次检索实际进入候选池的题目数（按学科/相关性过滤后），不是全库数量
    available_kaoyan = len(candidate_ids["kaoyan"])
    available_zhiyi = len(candidate_ids["zhiyi"])
    uncovered = sorted({ref for refs in uncovered_by_module.values() for ref in refs})
    covered = [kp.ref for kp in keypoints if kp.ref not in uncovered]

    return {
        "batch": batch,
        "subject": subject,
        "target": target,
        "keypoints_file": str(keypoints_path or ""),
        "blueprint_file": str(blueprint_path or ""),
        "quotas": {"kaoyan": req_kaoyan, "zhiyi": req_zhiyi},
        "counts": {
            "selected": len(selected),
            "kaoyan": sum(1 for x in selected if x["source"] == "kaoyan"),
            "zhiyi": sum(1 for x in selected if x["source"] == "zhiyi"),
            "remaining_slots": max(0, target - len(selected)),
        },
        "quota_status": {
            "kaoyan": status(req_kaoyan, sum(1 for x in selected if x["source"] == "kaoyan"), available_kaoyan),
            "zhiyi": status(req_zhiyi, sum(1 for x in selected if x["source"] == "zhiyi"), available_zhiyi),
        },
        "keypoint_coverage": {
            "total": len(keypoints),
            "covered_by_plan": len(covered),
            "uncovered": uncovered,
        },
        "modules": [
            {
                "module_id": m.module_id,
                "name": m.name,
                "target": m.target,
                "selected": len(module_selected[m.module_id]),
                "keypoints": [kp.ref for kp in module_kp.get(m.module_id, [])],
            }
            for m in modules
        ],
        "selected": selected,
        "search_log": search_log,
    }


def _selected_record(item: RealQuestion, module: Module, score: float, kp_refs: set[str], matched: list[str]) -> dict:
    return {
        "item_id": item.item_id,
        "source": item.source,
        "source_id": item.source_id,
        "exam": item.exam,
        "year": item.year,
        "question_no": item.question_no,
        "subject": item.subject,
        "module": module.module_id,
        "module_name": module.name,
        "keypoint_refs": sorted(kp_refs),
        "stem": item.stem,
        "options": item.options,
        "answer": item.answer,
        "explanation": item.explanation,
        "question_type": item.question_type,
        "answer_confidence": item.answer_confidence,
        "license": item.license,
        "license_note": item.license_note,
        "mode": "原题",
        "score": round(float(score), 6),
        "matched_queries": matched[:3],
    }


def write_plan(plan: dict, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
