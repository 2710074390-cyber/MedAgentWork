#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""label_concepts.py — 一题多概念的 Q 矩阵标注（W2）。

方法（纯规则、可复核）
    primary    优先取 kc_question_map.jsonl 的 primary_kc；缺失则用 teacher_anchor 最长标题命中。
    secondary  拿同科所有 KC 标题（去标点后 ≥4 字）去匹配「解析 + 逐项解析 + 教师锚点」，
               命中即为候选；按命中处所在字段给 role：
                 出现在 per_option.why → differential（干扰项对应的鉴别概念）
                 只出现在解析/锚点   → related
               每题最多 2 条 secondary，长标题优先，且被包含关系取最长（避免"休克"命中"心源性休克"）。

为什么不用模型
    标题匹配的每条边都能给出命中句原文，审计时可直接回查；调模型不可复核、成本高、易编关系。
    匹配不到的疑难题落 manual_queue，交人工，不硬猜。

用法
    python scripts/label_concepts.py
    python scripts/label_concepts.py --subject 急诊
    python scripts/label_concepts.py --min-len 4 --max-secondary 2
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

def _configure_stdio() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


BASE = Path(__file__).resolve().parent.parent
DEFAULT_OUT = BASE / "question_bank/concept_labels.jsonl"
DEFAULT_REPORT = BASE / "reports/validate/concept_label_report.json"
DEFAULT_QUEUE = BASE / "reports/validate/concept_label_manual_queue.csv"
REGISTRY_GLOBS = ("中间产物/*/pilot/kc_registry.json", "archive/中间产物/*/pilot/kc_registry.json")

PUNCT_RE = re.compile(r"[\s　·、，,。；;：:（）()\[\]【】\-—/\\|｜“”\"'‘’]+")
SENT_SPLIT_RE = re.compile(r"[。；\n]")
MULTI_TYPES = {"A2", "A3", "A4", "X", "B1"}


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def norm(s: str) -> str:
    return PUNCT_RE.sub("", s or "")


def load_subjects() -> dict[str, dict]:
    """subject -> {batch, titles: {kc_id: (title, norm_title)}, questions_path, map_path}"""
    best: dict[tuple[str, str], Path] = {}
    for g in REGISTRY_GLOBS:
        for p in sorted(BASE.glob(g)):
            try:
                d = read_json(p)
            except Exception:
                continue
            key = (str(d.get("subject", "")), str(d.get("batch", "")))
            prev = best.get(key)
            if prev is None or ("archive" in str(prev) and "archive" not in str(p)):
                best[key] = p

    out: dict[str, dict] = {}
    for (subject, batch), p in best.items():
        d = read_json(p)
        titles = {}
        kp_owner: dict[int, list[str]] = {}
        for c in d.get("cards") or []:
            kc_id = str(c.get("kc_id") or f"{subject}:{c.get('display_id')}")
            titles[kc_id] = (str(c.get("title") or ""), norm(str(c.get("title") or "")))
            for kp in c.get("keypoints") or []:
                kp_owner.setdefault(int(kp), []).append(kc_id)
        meta = d.get("metadata") or {}
        qpath = meta.get("questions_path")
        if qpath and not Path(qpath).is_absolute():
            qpath = str(BASE / qpath)
        if not qpath or not Path(qpath).exists():
            cand = BASE / f"最终产物/{batch}/ALL_questions_FIXED.json"
            qpath = str(cand) if cand.exists() else None
        mpath = p.parent / "kc_question_map.jsonl"
        out[subject] = {
            "batch": batch, "registry": p, "titles": titles, "kp_owner": kp_owner,
            "questions": qpath, "map": mpath if mpath.exists() else None,
        }
    return out


def snippet(text: str, pos: int, width: int = 46) -> str:
    start = max(0, pos - 12)
    seg = text[start:start + width]
    return seg.replace("\n", " ").strip()


def question_texts(q: dict) -> dict[str, str]:
    lv = q.get("learning_value") or {}
    why = "；".join(str(o.get("why") or "") for o in (lv.get("per_option") or []))
    return {
        "stem": str(q.get("stem") or q.get("question") or ""),
        "explanation": str(q.get("explanation") or ""),
        "anchor": str(q.get("teacher_anchor") or ""),
        "rationale": str(lv.get("correct_rationale") or ""),
        "why": why,
    }


def _overlap(a: str, b: str) -> int:
    """共享 2 字片段数，用于在同一锚点下的多张卡里选出标题最接近的那张。"""
    if not a or not b:
        return 0
    sa = {a[i:i + 2] for i in range(len(a) - 1)}
    sb = {b[i:i + 2] for i in range(len(b) - 1)}
    return len(sa & sb)


def resolve_concept(entry: dict, titles: dict, kp_owner: dict[int, list[str]]) -> tuple[str | None, str | None, str]:
    """把生成期写的 concepts[] 一条解析成 kc_id。返回 (kc_id, confidence, basis)。"""
    kp_raw = entry.get("keypoint")
    if isinstance(kp_raw, (list, tuple)):
        kp_raw = kp_raw[0] if kp_raw else ""
    m = re.search(r"(\d+)", str(kp_raw or ""))
    cands = kp_owner.get(int(m.group(1)), []) if m else []
    nt = norm(str(entry.get("title") or ""))
    if cands:
        if len(cands) == 1:
            return cands[0], "high", "keypoint_unique"
        best = max(cands, key=lambda k: _overlap(nt, titles[k][1]))
        score = _overlap(nt, titles[best][1])
        return best, ("high" if score >= 2 else "medium"), "keypoint_title"
    if nt:
        hits = [k for k, v in titles.items() if v[1] and (nt in v[1] or v[1] in nt)]
        if len(hits) == 1:
            return hits[0], "medium", "title_fallback"
        if hits:
            best = max(hits, key=lambda k: len(titles[k][1]))
            return best, "low", "title_ambiguous"
    return None, None, "unresolved"


def label_from_source(q: dict, subject: str, titles: dict, kp_owner: dict[int, list[str]],
                      declared: list, max_secondary: int) -> dict:
    """HC-27：题目自带 concepts[]，只做解析与校验，不再推断。"""
    primary, primary_ev = None, ""
    secondary, unresolved = [], []
    for entry in declared:
        if not isinstance(entry, dict):
            continue
        kc, conf, basis = resolve_concept(entry, titles, kp_owner)
        if not kc:
            unresolved.append(str(entry.get("title") or "?"))
            continue
        ev = str(entry.get("evidence") or "").strip()
        if entry.get("role") == "primary" and primary is None:
            primary = kc
            primary_ev = ev or "题目主概念（HC-27 源标注）"
            continue
        if len(secondary) < max_secondary:
            secondary.append({
                "kc_id": kc,
                "role": str(entry.get("role") or "related"),
                "confidence": conf,
                "basis": f"source_{basis}",
                "evidence": f"HC-27 源标注：{ev}" if ev else "HC-27 源标注",
            })
    return {
        "qid": str(q.get("id") or q.get("question_id") or ""),
        "subject": subject, "type": str(q.get("type") or ""),
        "primary": primary,
        "primary_evidence": primary_ev,
        "secondary": secondary,
        "method": "source_concepts",
        "source": "declared",
        "unresolved": unresolved,
        "needs_manual": primary is None or bool(unresolved),
    }


def label_one(q: dict, subject: str, titles: dict, primary_hint: str | None,
              min_len: int, max_secondary: int, kp_owner: dict[int, list[str]] | None = None) -> dict:
    declared = q.get("concepts")
    if isinstance(declared, list) and declared:
        return label_from_source(q, subject, titles, kp_owner or {}, declared, max_secondary)

    texts = question_texts(q)
    qtype = str(q.get("type") or "")
    pool = {k: v for k, v in titles.items() if len(v[1]) >= min_len}

    # --- primary ---
    primary = primary_hint if primary_hint in titles else None
    if not primary:
        anchor_norm = norm(texts["anchor"] + texts["stem"])
        best_len, best_id = 0, None
        for kc, (_, nt) in pool.items():
            if nt and nt in anchor_norm and len(nt) > best_len:
                best_len, best_id = len(nt), kc
        primary = best_id

    cands: dict[str, dict] = {}

    # 信号 A：同一教师重点条号被多张卡拥有 → 该题同时测到这些卡（最强，无需文本命中）
    for kp in (q.get("keypoint_ref") or []):
        m = re.search(r"(\d+)", str(kp))
        if not m:
            continue
        for kc in (kp_owner or {}).get(int(m.group(1)), []):
            if kc != primary and kc in titles:
                cands.setdefault(kc, {
                    "kc_id": kc, "role": "related", "confidence": "high", "basis": "keypoint_shared",
                    "evidence": f"题目覆盖教师重点第{m.group(1)}条，该条同时归属 {titles[kc][0]}",
                })

    # 信号 B：标题在「逐项解析 / 解析 / 锚点」中逐字命中
    hit_expl: dict[str, int] = {}
    hit_why: dict[str, int] = {}
    for kc, (_, nt) in pool.items():
        if kc == primary or not nt:
            continue
        idx = texts["why"].find(nt)
        if idx >= 0:
            hit_why[kc] = idx
            continue
        idx = (texts["explanation"] + texts["anchor"]).find(nt)
        if idx >= 0:
            hit_expl[kc] = idx

    for kc, idx in sorted(hit_why.items(), key=lambda x: -len(titles[x[0]][1])):
        if kc in cands:
            continue
        cands[kc] = {
            "kc_id": kc, "role": "differential", "confidence": "high", "basis": "title_exact",
            "evidence": f"逐项解析命中「{titles[kc][0]}」：{snippet(texts['why'], idx)}",
        }
    for kc, idx in sorted(hit_expl.items(), key=lambda x: -len(titles[x[0]][1])):
        if kc in cands:
            continue
        cands[kc] = {
            "kc_id": kc, "role": "related",
            "confidence": "high" if len(titles[kc][1]) >= 6 else "medium",
            "basis": "title_exact",
            "evidence": f"解析命中「{titles[kc][0]}」：{snippet(texts['explanation'] + texts['anchor'], idx)}",
        }

    # 信号 C：标题后 5 字（≥5 字、不含空格）命中 → 中置信，用于补全前述漏召
    body = texts["explanation"] + texts["why"] + texts["anchor"]
    for kc, (raw_title, nt) in sorted(pool.items(), key=lambda x: -len(x[1][0])):
        if kc == primary or kc in cands or " " in raw_title.strip():
            continue
        frag = raw_title.strip()[-5:]
        if len(frag) >= 5 and frag in body:
            pos = body.find(frag)
            cands[kc] = {
                "kc_id": kc, "role": "differential", "confidence": "medium", "basis": "title_suffix",
                "evidence": f"解析片段命中「{frag}」（{raw_title}）：{snippet(body, pos)}",
            }

    # 排序：keypoint_shared > high > medium；同级按标题长度降序
    ranked = sorted(
        cands.values(),
        key=lambda c: (c["basis"] != "keypoint_shared", c["confidence"] != "high", -len(titles[c["kc_id"]][0])),
    )
    secondary = ranked[:max_secondary]

    return {
        "qid": str(q.get("id") or q.get("question_id") or ""),
        "subject": subject, "type": qtype,
        "primary": primary,
        "secondary": secondary,
        "method": "rule_ensemble",
        "source": "inferred",
        "needs_manual": primary is None or (qtype in MULTI_TYPES and not secondary),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="一题多概念标注")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--report", default=str(DEFAULT_REPORT))
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE))
    ap.add_argument("--subject", default=None)
    ap.add_argument("--min-len", type=int, default=4)
    ap.add_argument("--max-secondary", type=int, default=2)
    args = ap.parse_args()

    subjects = load_subjects()
    if args.subject:
        subjects = {k: v for k, v in subjects.items() if k == args.subject}
    if not subjects:
        print("ERROR —— 无可用学科（需 kc_registry.json 且能找到题目文件）")
        return 2

    rows, queue, stats = [], [], {}
    for subject, cfg in subjects.items():
        if not cfg["questions"]:
            print(f"SKIP —— {subject} 找不到题目文件")
            continue
        questions = read_json(Path(cfg["questions"]))
        hint = {}
        if cfg["map"]:
            for line in cfg["map"].read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                d = json.loads(line)
                hint[str(d.get("question_id"))] = d.get("primary_kc")

        subj_rows = []
        for q in questions:
            row = label_one(q, subject, cfg["titles"], hint.get(str(q.get("id"))),
                            args.min_len, args.max_secondary, cfg.get("kp_owner"))
            subj_rows.append(row)
            if row["needs_manual"]:
                if not row["primary"]:
                    reason = "无主概念"
                elif row.get("unresolved"):
                    reason = "源标注未解析：" + "、".join(row["unresolved"])
                else:
                    reason = "A2+ 缺二级概念"
                queue.append([subject, row["qid"], row["type"], reason])
        rows.extend(subj_rows)

        multi_pool = [r for r in subj_rows if r["type"] in MULTI_TYPES]
        declared = [r for r in subj_rows if r.get("source") == "declared"]
        stats[subject] = {
            "batch": cfg["batch"],
            "questions": len(subj_rows),
            "with_primary": sum(1 for r in subj_rows if r["primary"]),
            "multi_label": sum(1 for r in subj_rows if r["secondary"]),
            "multi_pool": len(multi_pool),
            "multi_label_rate_A2plus": (
                round(sum(1 for r in multi_pool if r["secondary"]) / len(multi_pool), 4)
                if multi_pool else None
            ),
            "source_mode": "declared" if declared else "inferred",
            "declared_questions": len(declared),
            "declared_resolved": sum(1 for r in declared if r["primary"]),
            "unresolved_concepts": sum(len(r.get("unresolved") or []) for r in subj_rows),
            "secondary_avg": round(
                sum(len(r["secondary"]) for r in subj_rows) / max(1, len(subj_rows)), 2),
            "type_dist": dict(Counter(r["type"] for r in subj_rows)),
            "secondary_by_basis": dict(Counter(
                c["basis"] for r in subj_rows for c in r["secondary"])),
            "secondary_by_confidence": dict(Counter(
                c["confidence"] for r in subj_rows for c in r["secondary"])),
            "multi_label_by_type": {
                t: [sum(1 for r in subj_rows if r["type"] == t),
                    sum(1 for r in subj_rows if r["type"] == t and r["secondary"])]
                for t in sorted({r["type"] for r in subj_rows})
            },
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    with Path(args.queue).open("w", encoding="utf-8-sig", newline="") as f:
        import csv
        w = csv.writer(f)
        w.writerow(["subject", "qid", "type", "reason"])
        w.writerows(queue)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generator": "scripts/label_concepts.py",
        "min_len": args.min_len, "max_secondary": args.max_secondary,
        "subjects": stats,
        "total_questions": len(rows),
        "total_secondary_edges": sum(len(r["secondary"]) for r in rows),
        "manual_queue": len(queue),
    }
    write_json(Path(args.report), report)

    for s, st in stats.items():
        print(f"== {s} ({st['batch']}) 模式 {st['source_mode']}　题 {st['questions']}　"
              f"有主概念 {st['with_primary']}　多标签 {st['multi_label']}　"
              f"A2+ 多标签率 {st['multi_label_rate_A2plus']}")
        if st["declared_questions"]:
            print(f"   源标注 {st['declared_questions']} 题，已解析 {st['declared_resolved']}，"
                  f"未解析概念 {st['unresolved_concepts']} 个")
    print(f"二级边合计 {report['total_secondary_edges']}　人工队列 {len(queue)}")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    _configure_stdio()
    raise SystemExit(main())
