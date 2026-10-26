#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""review_scorecard.py — 复习资料 12 维学习价值评分卡（T5–T6）。

输入
    - 复习资料 MD
    - KC 注册表 + 题目映射
    - 200 题学习价值初检报告
    - 人工 rubric（1/3/5 分锚点 + 证据）

输出
    - review_scorecard_<subject>_<date>.json
    - review_scorecard_<subject>_<date>.md
    - 供 gate_check.py 的 GATE-FINAL-LEARNING-VALUE 读取（advisory/enforce）

用法
    python scripts/review_scorecard.py --subject ent --batch batch040 \
      --review "复习资料/.../主复习资料.md" \
      --kc "中间产物/batch040/pilot/kc_registry.json" \
      --learning-value "reports/validate/learning_value_v2_batch040_20261022.json" \
      --rubric "中间产物/batch040/pilot/review_score_rubric.json" \
      --out "reports/validate/review_scorecard_ent_20261022.json" \
      --md-out "reports/validate/review_scorecard_ent_20261022.md"
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
DEFAULT_REVIEW = BASE / "复习资料/耳鼻咽喉头颈外科学教师重点版/耳鼻咽喉头颈外科学教师重点版_主复习资料.md"
DEFAULT_KC = BASE / "中间产物/batch040/pilot/kc_registry.json"
DEFAULT_LEARNING_VALUE = BASE / "reports/validate/learning_value_v2_batch040_20261022.json"
DEFAULT_RUBRIC = BASE / "中间产物/batch040/pilot/review_score_rubric.json"
DEFAULT_OUT = BASE / "reports/validate/review_scorecard_ent_20261022.json"
DEFAULT_MD = BASE / "reports/validate/review_scorecard_ent_20261022.md"

CRITICAL_DIMS = {2, 3, 8}
TARGET = 4.6


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path):
    return json.loads(read_text(path))


def repo_path(value) -> Path:
    """把仓库内相对路径跨平台解析：兼容 Windows 反斜杠与 POSIX 斜杠。"""
    if not value:
        return Path("")
    p = Path(str(value).replace("\\", "/"))
    return p if p.is_absolute() else BASE / p


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_json(path: Path, data) -> None:
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2))


def _status(value: float, ok: float, warn: float, *, higher_is_better: bool = True) -> str:
    if higher_is_better:
        if value >= ok:
            return "ok"
        return "warn" if value >= warn else "fail"
    if value <= ok:
        return "ok"
    return "warn" if value <= warn else "fail"


def _metric(value, display: str, status: str, threshold: str, source: str, note: str = "") -> dict:
    return {
        "value": value,
        "display": display,
        "status": status,
        "threshold": threshold,
        "source": source,
        "note": note,
    }


def compute_metrics(review_path: Path, kc_path: Path, learning_value_path: Path) -> dict:
    import kc_registry as kc

    md_text = read_text(review_path)
    cards = kc.parse_review_cards(md_text)
    registry = read_json(kc_path)
    meta_kp = registry.get("metadata", {}).get("keypoints_path")
    if meta_kp:
        # 显式归一化 Windows 反斜杠，避免 POSIX runner 把整段当作单个文件名。
        kp_path = Path(str(meta_kp).replace("\\", "/"))
        if not kp_path.is_absolute():
            kp_path = BASE / kp_path
    else:
        kp_path = (BASE / "输入素材" / "大四上" / "耳鼻咽喉头颈外科学"
                   / "耳鼻咽喉头颈外科学_教师重点_锚定清单_20261019.md")
    keypoint_items = kc.parse_keypoint_items(read_text(kp_path))
    map_path = kc_path.with_name("kc_question_map.jsonl")
    qmap = []
    if map_path.exists():
        for line in read_text(map_path).splitlines():
            if line.strip():
                qmap.append(json.loads(line))

    cards_total = len(cards)
    cards_with_kp = sum(1 for c in cards if c.get("keypoints"))
    content_chars = sum(c.get("content_chars", 0) for c in cards)
    modules = len(set(c.get("module") for c in cards if c.get("module")))
    keypoint_ids = {int(k) for c in cards for k in (c.get("keypoints") or [])}
    kp_coverage = len(keypoint_ids & set(keypoint_items)) / max(1, len(keypoint_items))

    callouts = len(re.findall(r"^> \[!", md_text, re.M))
    expand_blocks = len(re.findall(r"^#### 🔬 展开", md_text, re.M))
    table_rows = len(re.findall(r"^\|", md_text, re.M))
    images = md_text.count("![")
    ascii_blocks = md_text.count("```") // 2
    selftests = md_text.count("（答案见附录五）")
    appendix_start = md_text.find("## 附录五：主动回忆答案")
    appendix_rows = 0
    if appendix_start >= 0:
        appendix_rows = len(re.findall(r"^\|\s*(?:\d+|补)\s*\|", md_text[appendix_start:], re.M))
    # 真实答案覆盖：按模块 + 卡片 ID 对账，而不是“附录行数 >= 自测数”的粗判
    import spaced_schedule as ss
    prompts = ss.parse_self_tests(md_text)
    rows_a = ss.parse_appendix_rows(md_text)
    matched, gaps, extras = ss.reconcile(prompts, rows_a)
    recall_matched = len(matched)
    recall_total = len(prompts)

    questions_total = len(qmap) or (len(registry.get("cards", [])) and
                                    sum(len(c.get("question_ids") or []) for c in registry["cards"]) +
                                    sum(len(p.get("question_ids") or []) for p in registry.get("provisional", [])))
    mapped = sum(1 for r in qmap if r.get("primary_kc"))
    provisional_rows = sum(1 for r in qmap if r.get("mapping_method") == "provisional")
    needs_review = sum(1 for r in qmap if r.get("review_status") == "needs_review")
    content_only = sum(1 for c in registry.get("cards", []) if c.get("status") == "content_only")
    kc_total = len(registry.get("cards", []))
    provisional_kcs = len(registry.get("provisional", []))
    aliases_path = kc_path.with_name("kc_aliases.json")
    alias_count = len(read_json(aliases_path)) if aliases_path.exists() else 0

    lv_summary = {}
    if learning_value_path.exists():
        lv_summary = read_json(learning_value_path).get("summary", {})
    source_exact = float(lv_summary.get("source_quote_exact_rate", 0.0))
    anchor_verified = float(lv_summary.get("anchor_verified_rate", 0.0))
    r18_count = int(lv_summary.get("anchor_low_overlap_count", 0))

    # 蓝图四口径：卡片/字数/重点/题量 vs 卷面权重
    weights = kc.parse_blueprint_weights(md_text)
    by_mod = defaultdict(lambda: {"cards": 0, "chars": 0, "kp": set(), "questions": 0})
    for c in cards:
        m = by_mod[c["module"]]
        m["cards"] += 1
        m["chars"] += c.get("content_chars", 0)
        m["kp"].update(c.get("keypoints") or [])
    for r in qmap:
        by_mod[r.get("module", "M00")]["questions"] += 1
    max_dev = 0.0
    for mod, weight in weights.items():
        if weight <= 0:
            continue
        m = by_mod[mod]
        for key, value in (
            ("cards", m["cards"]),
            ("chars", m["chars"]),
            ("kp", len(m["kp"])),
            ("questions", m["questions"]),
        ):
            total = {
                "cards": cards_total,
                "chars": content_chars,
                "kp": len(keypoint_ids),
                "questions": questions_total,
            }[key]
            share = value / total if total else 0.0
            rel = abs(share - weight / 100.0) / (weight / 100.0)
            max_dev = max(max_dev, rel)

    # 其他可用性指标
    teacher_dir = review_path.parent
    html_available = 1.0 if list(teacher_dir.glob("*.html")) else 0.0
    schedule_coverage = 1.0 if (BASE / "中间产物/batch040/pilot/review_items.jsonl").exists() else 0.0
    feedback_coverage = 1.0 if (BASE / "中间产物/batch040/pilot/pilot_review.html").exists() else 0.0
    diagnostic_available = 1.0 if list((BASE / "中间产物/batch040/pilot").glob("diagnostic*")) else 0.0
    learner_outcome_available = 1.0 if list((BASE / "reports/validate").glob("pilot_analysis*.md")) else 0.0

    questions_path = None
    meta_q = registry.get("metadata", {}).get("questions_path")
    if meta_q:
        p = repo_path(meta_q)
        if p.exists():
            questions_path = p
    case_count = 0
    if questions_path:
        for q in read_json(questions_path):
            if isinstance(q, dict) and str(q.get("type")) == "案例":
                case_count += 1

    m = {
        "cards": _metric(cards_total, f"{cards_total} 张", "info", "—", "review MD"),
        "content_chars": _metric(content_chars, f"{content_chars:,} 字符", "info", "—", "review MD"),
        "modules": _metric(modules, f"{modules} 模块", "info", "—", "review MD"),
        "keypoint_coverage_rate": _metric(
            round(kp_coverage, 4), f"{len(keypoint_ids & set(keypoint_items))}/{len(keypoint_items)}",
            _status(kp_coverage, 1.0, 0.95), "=100%", "KC registry"),
        "kc_mapping_rate": _metric(
            round(mapped / max(1, questions_total), 4), f"{mapped}/{questions_total}",
            _status(mapped / max(1, questions_total), 1.0, 0.95), "=100%", "kc_question_map"),
        "source_quote_exact_rate": _metric(
            round(source_exact, 4), f"{source_exact:.1%}", _status(source_exact, 0.95, 0.90),
            "≥95%", "learning_value_v2 report"),
        "anchor_verified_rate": _metric(
            round(anchor_verified, 4), f"{anchor_verified:.1%}", _status(anchor_verified, 0.90, 0.70),
            "≥90%", "learning_value_v2 report"),
        "r18_low_overlap_count": _metric(r18_count, f"{r18_count} 题", "warn" if r18_count else "ok",
                                          "=0", "learning_value_v2 report"),
        "source_anchor_rate": _metric(
            round(cards_with_kp / max(1, cards_total), 4), f"{cards_with_kp}/{cards_total}",
            _status(cards_with_kp / max(1, cards_total), 0.95, 0.85), "≥95%", "review MD"),
        "recall_answer_coverage": _metric(
            round(recall_matched / max(1, recall_total), 4),
            f"{recall_matched}/{recall_total} 匹配（缺口 {len(gaps)}，多余 {len(extras)}）",
            _status(recall_matched / max(1, recall_total), 1.0, 0.95), "≥95%",
            "review MD + appendix5", "按模块 + 卡片 ID 对账；缺口不编造"),
        "callout_density": _metric(round(callouts / max(1, modules), 2), f"{callouts / max(1, modules):.2f}/模块",
                                    _status(callouts / max(1, modules), 4.0, 2.0), "≥4/模块", "review MD"),
        "expand_density": _metric(round(expand_blocks / max(1, modules), 2), f"{expand_blocks / max(1, modules):.2f}/模块",
                                   _status(expand_blocks / max(1, modules), 2.0, 1.0), "≥2/模块", "review MD"),
        "table_density": _metric(round(table_rows / max(1, modules), 1), f"{table_rows / max(1, modules):.1f} 行/模块",
                                  "info", "—", "review MD"),
        "ascii_blocks": _metric(ascii_blocks, f"{ascii_blocks} 个", "info", "—", "review MD"),
        "image_count": _metric(images, f"{images} 张", "warn" if images == 0 else "ok", "—", "review MD"),
        "blueprint_max_rel_dev": _metric(
            round(max_dev, 4), f"{max_dev:.1%}", _status(max_dev, 0.20, 0.50, higher_is_better=False),
            "≤20%", "review MD + kc_question_map", "卡片/字数/重点/题量四口径最大相对偏差"),
        "content_only_ratio": _metric(
            round(content_only / max(1, kc_total), 4), f"{content_only}/{kc_total}",
            _status(content_only / max(1, kc_total), 0.15, 0.25, higher_is_better=False),
            "≤15%", "kc_registry"),
        "provisional_ratio": _metric(
            round(provisional_rows / max(1, questions_total), 4), f"{provisional_rows}/{questions_total}",
            _status(provisional_rows / max(1, questions_total), 0.10, 0.20, higher_is_better=False),
            "≤10%", "kc_question_map"),
        "needs_review_ratio": _metric(
            round(needs_review / max(1, questions_total), 4), f"{needs_review}/{questions_total}",
            _status(needs_review / max(1, questions_total), 0.10, 0.25, higher_is_better=False),
            "≤10%", "kc_question_map"),
        "kc_alias_count": _metric(alias_count, f"{alias_count} 条", "info", "—", "kc_aliases"),
        "case_question_count": _metric(case_count, f"{case_count} 题", "info", "—", "question bank"),
        "illness_script_count": _metric(0, "0 个", "warn", "≥10 个（P2）", "review MD"),
        "html_available": _metric(html_available, "有" if html_available else "无", "ok" if html_available else "warn",
                                   "教师版 HTML", "teacher dir"),
        "schedule_coverage": _metric(schedule_coverage, "未实现" if not schedule_coverage else "已实现",
                                      "unknown" if not schedule_coverage else "ok", "D3", "pilot artifacts"),
        "feedback_coverage": _metric(feedback_coverage, "未实现" if not feedback_coverage else "已实现",
                                      "unknown" if not feedback_coverage else "ok", "D8", "pilot artifacts"),
        "diagnostic_available": _metric(diagnostic_available, "未实现" if not diagnostic_available else "已实现",
                                         "unknown" if not diagnostic_available else "ok", "D2", "pilot artifacts"),
        "learner_outcome_available": _metric(learner_outcome_available, "未实现" if not learner_outcome_available else "已实现",
                                               "unknown" if not learner_outcome_available else "ok", "A8", "pilot reports"),
    }
    return m


def load_rubric(path: Path) -> dict:
    data = read_json(path)
    dims = data.get("dimensions")
    if not isinstance(dims, list) or len(dims) != 12:
        raise ValueError("rubric 必须包含 12 个 dimensions")
    ids = {int(d.get("id", 0)) for d in dims}
    if ids != set(range(1, 13)):
        raise ValueError(f"rubric id 必须为 1..12，实际 {sorted(ids)}")
    weight_sum = sum(float(d.get("weight", 0)) for d in dims)
    if abs(weight_sum - 100.0) > 0.01:
        raise ValueError(f"rubric 权重合计必须为 100，实际 {weight_sum}")
    for d in dims:
        if not 0 <= float(d.get("score", -1)) <= 5:
            raise ValueError(f"dimension {d.get('id')} score 必须在 0–5")
        if not d.get("evidence"):
            raise ValueError(f"dimension {d.get('id')} 缺 evidence")
    return data


def build_scorecard(subject: str, batch: str, review_path: Path, rubric_path: Path,
                    kc_path: Path, learning_value_path: Path) -> dict:
    rubric = load_rubric(rubric_path)
    metrics = compute_metrics(review_path, kc_path, learning_value_path)
    dims = []
    for d in rubric["dimensions"]:
        score = float(d["score"])
        weight = float(d["weight"])
        refs = d.get("metric_refs") or []
        metric_evidence = []
        for ref in refs:
            if ref in metrics:
                metric_evidence.append(f"{ref}={metrics[ref]['display']}（{metrics[ref]['status']}）")
        dims.append({
            "id": int(d["id"]),
            "name": d["name"],
            "weight": weight,
            "score": score,
            "weighted": round(weight * score / 100.0, 4),
            "method": "manual+auto",
            "evidence": list(d.get("evidence") or []) + metric_evidence,
            "notes": d.get("notes", ""),
            "metric_refs": refs,
        })
    overall = round(sum(d["weighted"] for d in dims), 2)
    warnings = []
    for key, m in metrics.items():
        if m["status"] in ("fail", "warn"):
            warnings.append(f"{key}={m['display']}（{m['status']}，阈值 {m['threshold']}）")
    for key in ("schedule_coverage", "feedback_coverage", "diagnostic_available", "learner_outcome_available"):
        if metrics[key]["status"] == "unknown":
            warnings.append(f"{key}=未实现（unknown，后续阶段）")
    critical = [d for d in dims if d["id"] in CRITICAL_DIMS]
    critical_low = [d for d in critical if d["score"] < 3.5]
    if overall < 3.5 or critical_low:
        gate = "ADVISORY_WARN"
    elif any(m["status"] == "fail" for m in metrics.values()):
        gate = "ADVISORY_PASS"
    else:
        gate = "ADVISORY_PASS"
    blocking = []
    if any(d["score"] < 3.0 for d in critical):
        gate = "ADVISORY_FAIL"
        blocking = [f"critical dimension {d['id']} {d['name']}={d['score']}" for d in critical if d["score"] < 3.0]
    return {
        "schema_version": 1,
        "subject": subject.upper(),
        "batch": batch,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "review_path": str(review_path.relative_to(BASE)) if review_path.is_relative_to(BASE) else str(review_path),
        "rubric_path": str(rubric_path.relative_to(BASE)) if rubric_path.is_relative_to(BASE) else str(rubric_path),
        "overall": overall,
        "target": TARGET,
        "gate": gate,
        "gate_mode": "advisory",
        "dimensions": dims,
        "metrics": metrics,
        "warnings": warnings,
        "blocking_issues": blocking,
        "reviewers": rubric.get("reviewers", []),
        "limitations": "12 维分数为专家 rubric，不是学习者结果测量；目标 4.6 为设计目标，不是承诺。",
    }


def render_md(card: dict, out_path: Path) -> None:
    bp = card.get("metrics", {}).get("blueprint_max_rel_dev", {}).get("display", "?")
    lines = [
        "# 复习资料学习价值评分卡 · 耳鼻咽喉头颈外科学（教师重点版）",
        "",
        f"> 生成：{card['generated_at']} ｜ 科目：{card['subject']} ｜ 批次：{card['batch']}",
        f"> 总分：**{card['overall']}/5** ｜ 目标：{card['target']}/5 ｜ Gate：**{card['gate']}**（{card['gate_mode']}）",
        "",
        "## 1. 12 维评分",
        "",
        "| # | 维度 | 权重 | 分数 | 加权 | 证据 |",
        "|---|---|---:|---:|---:|---|",
    ]
    for d in card["dimensions"]:
        ev = "<br>".join(str(x) for x in d["evidence"][:4])
        lines.append(f"| {d['id']} | {d['name']} | {d['weight']:.0f}% | {d['score']:.1f} | "
                     f"{d['weighted']:.2f} | {ev} |")
    lines += [
        "",
        "## 2. 自动指标",
        "",
        "| 指标 | 值 | 状态 | 阈值 | 来源 |",
        "|---|---|---|---|---|",
    ]
    order = {"fail": 0, "warn": 1, "unknown": 2, "ok": 3, "info": 4}
    for key, m in sorted(card["metrics"].items(), key=lambda kv: (order.get(kv[1]["status"], 9), kv[0])):
        lines.append(f"| {key} | {m['display']} | {m['status']} | {m['threshold']} | {m['source']} |")
    lines += [
        "",
        "## 3. 改进建议（Top 5）",
        "",
        "1. **content_only 19/85**：为 19 张无题卡补题，或在下一批明确标为 content-only；目标 ≤12 张。",
        "2. **anchor_verified 74%**：优先处理 26 题 R18 低主题覆盖与 R16 警告；目标 ≥90%。",
        "3. **expand_density 0 / image_count 0**：教师版补 D1–D5 展开区与 10–20 张可信图；先做图谱/确定性图。",
        f"4. **blueprint_max_rel_dev {bp}**：M07 字数与题量超配、M02/M04 内容欠配；先出配平报告，不删低权重条目。",
        "5. **schedule/feedback 未实现**：D3 间隔重复与 D8 交互式 HTML 尚未落地；这是记忆保持与反馈闭环的关键。",
        "",
        "## 4. 限制",
        "",
        f"- {card['limitations']}",
        "- 自动指标是证据，不单独决定总分；总分由人工 rubric 的 12 维加权。",
        "- 本评分卡不替代医学内容专家复核。",
        "",
        "## 5. 评审角色",
        "",
        "- " + "；".join(card.get("reviewers") or []),
        "",
        "## 6. 门禁",
        "",
        f"- `gate_check.py --learning-value-mode advisory` 读取本文件；advisory 只 WARN，不阻断。",
        f"- 当前 warnings：{len(card['warnings'])} 条；blocking_issues：{len(card['blocking_issues'])} 条。",
        "",
    ]
    atomic_write(out_path, "\n".join(lines))


def main() -> int:
    _configure_stdio()
    ap = argparse.ArgumentParser(description="复习资料 12 维学习价值评分卡（T5–T6）")
    ap.add_argument("--subject", default="ent")
    ap.add_argument("--batch", default="batch040")
    ap.add_argument("--review", default=str(DEFAULT_REVIEW))
    ap.add_argument("--kc", default=str(DEFAULT_KC))
    ap.add_argument("--learning-value", default=str(DEFAULT_LEARNING_VALUE))
    ap.add_argument("--rubric", default=str(DEFAULT_RUBRIC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--md-out", default=str(DEFAULT_MD))
    args = ap.parse_args()

    try:
        card = build_scorecard(
            args.subject, args.batch,
            Path(args.review), Path(args.rubric), Path(args.kc), Path(args.learning_value),
        )
    except Exception as exc:
        print(f"[FAIL] 评分卡构建失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    try:
        from jsonschema import validate as js_validate
        schema_path = BASE / "schemas/review_score.schema.json"
        if schema_path.exists():
            js_validate(card, read_json(schema_path))
    except ImportError:
        pass
    except Exception as exc:
        print(f"[FAIL] schema 校验失败：{exc}", file=sys.stderr)
        return 2

    write_json(Path(args.out), card)
    render_md(card, Path(args.md_out))
    print(f"✅ 评分卡：{card['overall']}/5（目标 {card['target']}）｜ {card['gate']} ｜ "
          f"warnings {len(card['warnings'])} ｜ blocking {len(card['blocking_issues'])}")
    print(f"   JSON: {args.out}")
    print(f"   MD  : {args.md_out}")
    return 0 if card["gate"] != "ADVISORY_FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
