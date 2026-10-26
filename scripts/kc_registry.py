#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kc_registry.py — KC 注册表与双向映射（T2–T4）。

职责
    1. 从复习资料 MD 抽取 85 张知识卡（K-ID、模块、重点条号、页码、正文）。
    2. 从 200 题中抽取 keypoint_ref / topic / teacher_anchor。
    3. 用「关键点精确 → 多卡评分 → 跨模块 → 主题规则 → 相似度 → provisional」
       六级策略建立题目 → KC 的主映射。
    4. 输出 kc_registry.json / kc_aliases.json / kc_question_map.jsonl /
       kc_mapping_report.md / kc_manual_queue.csv。
    5. check 校验契约、覆盖率、孤儿；query 回查任一 KC。

用法
    python scripts/kc_registry.py build \
      --subject ent --batch batch040 \
      --review "复习资料/.../耳鼻咽喉头颈外科学教师重点版_主复习资料.md" \
      --questions "最终产物/batch040/ALL_questions_FIXED.json" \
      --keypoints "输入素材/.../耳鼻咽喉头颈外科学_教师重点_锚定清单_20261019.md" \
      --rules "中间产物/batch040/pilot/kc_mapping_rules.json" \
      --out "中间产物/batch040/pilot"

    python scripts/kc_registry.py check --file "中间产物/batch040/pilot/kc_registry.json" --strict
    python scripts/kc_registry.py report --file "中间产物/batch040/pilot/kc_registry.json" \
      --map "中间产物/batch040/pilot/kc_question_map.jsonl" \
      --out "中间产物/batch040/pilot/kc_mapping_report.md"
    python scripts/kc_registry.py query --file "中间产物/batch040/pilot/kc_registry.json" \
      --kc "ENT:K-M03-001"
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

def _configure_stdio() -> None:
    """仅在 CLI 入口重配 stdout；import 时保持 pytest capture 可用。"""
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


BASE = Path(__file__).resolve().parent.parent
DEFAULT_SUBJECT = "ent"
DEFAULT_BATCH = "batch040"
DEFAULT_REVIEW = BASE / "复习资料/耳鼻咽喉头颈外科学教师重点版/耳鼻咽喉头颈外科学教师重点版_主复习资料.md"
DEFAULT_QUESTIONS = BASE / "最终产物/batch040/ALL_questions_FIXED.json"
DEFAULT_KEYPOINTS = BASE / "输入素材/大四上/耳鼻咽喉头颈外科学/耳鼻咽喉头颈外科学_教师重点_锚定清单_20261019.md"
DEFAULT_RULES = BASE / "中间产物/batch040/pilot/kc_mapping_rules.json"
DEFAULT_LEARNING_VALUE = BASE / "中间产物/batch040/learning_value_v2/items_v2_progress.json"
DEFAULT_ANCHOR_OVERRIDES = BASE / "中间产物/batch040/learning_value_v2/anchor_overrides.json"
DEFAULT_QUESTION_OVERRIDES = BASE / "中间产物/batch040/pilot/kc_question_overrides.json"
DEFAULT_OUT = BASE / "中间产物/batch040/pilot"

MODULE_WEIGHTS = {"M01": 8, "M02": 28, "M03": 24, "M04": 18, "M05": 14, "M06": 5, "M07": 3}
SUFFIXES = [
    "的诊断", "的体征", "的处理措施", "的确诊", "的临床分型", "的鉴别诊断", "的并发症",
    "的检查", "的影像评估", "的处理策略", "的特点", "的穿刺风险", "的预防措施",
    "的好发年龄", "的好发人群", "的病理特点", "的应用解剖与异物病理生理",
    "的临床与病理", "的病例诊断", "的类型", "的专科检查", "的位置",
]


# ---------------------------------------------------------------- io
def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path):
    return json.loads(read_text(path))


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_json(path: Path, data) -> None:
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else "")
    atomic_write(path, text)


# ---------------------------------------------------------------- text utils
def ngrams(text: str, n: int = 2) -> set[str]:
    s = re.sub(r"\s+", "", text or "")
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def page_numbers(value) -> set[int]:
    return {int(x) for x in re.findall(r"\d+", str(value or ""))}


def clean_title(title: str) -> str:
    return re.sub(r"（[^）]*）", "", title or "").strip()


def normalize_topic(topic: str, stem: str = "") -> str:
    base = (topic or stem or "未分类").strip()
    base = re.sub(r"【[^】]*】", "", base)
    base = re.sub(r"（[^）]*）", "", base)
    for suffix in SUFFIXES:
        base = base.replace(suffix, "")
    base = re.sub(r"[^\w\u4e00-\u9fa5-]", "", base).strip()
    return (base[:20] or "未分类")


# ---------------------------------------------------------------- parsers
def parse_review_cards(md_text: str) -> list[dict]:
    """解析 `### K-Mxx-xxx｜标题（教师重点第X条｜P..）` 卡片。"""
    lines = md_text.splitlines()
    cards: list[dict] = []
    module = None
    current = None
    body_start = None

    def finalize(end: int):
        nonlocal current
        if not current:
            return
        body = "\n".join(lines[body_start:end])
        current["body"] = body
        current["content_chars"] = len(body)
        current["keypoints"] = sorted(current["keypoints"])
        current["pages"] = sorted(set(current["pages"]))
        current["title_clean"] = clean_title(current["title"])
        cards.append(current)
        current = None

    for i, line in enumerate(lines):
        m = re.match(r"^## 模块(\d+)：(.+)$", line)
        if m:
            if current:
                finalize(i)
            module = f"M{int(m.group(1)):02d}"
            continue
        m = re.match(r"^#### .*?(K-M\d{2}-\d{3})[｜|](.+)$", line)
        if m:
            if current:
                finalize(i)
            rest = m.group(2)
            kps = set()
            km = re.search(r"教师重点第([0-9、,，/]+)条", rest)
            if km:
                for x in re.split(r"[、,，/]", km.group(1)):
                    if x.strip().isdigit():
                        kps.add(int(x.strip()))
            title = rest.split("（教师重点")[0].strip()
            pages = [int(x) for x in re.findall(r"P(\d+)", rest)]
            current = {
                "display_id": m.group(1),
                "module": module or "M00",
                "title": title,
                "keypoints": kps,
                "pages": pages,
                "line_start": i + 1,
            }
            body_start = i
            continue
        if current:
            for m in re.finditer(r"📌 重点原文（第(\d+)条）", line):
                current["keypoints"].add(int(m.group(1)))
            for p in re.findall(r"（P(\d+)）", line):
                current["pages"].append(int(p))
    if current:
        finalize(len(lines))
    return cards


def parse_keypoint_items(text: str) -> dict[int, dict]:
    """解析锚定清单第四节 1..125 连续条目。"""
    start = text.find("## 四、统一锚定清单")
    end = text.find("## 五、原始标号对照", start if start >= 0 else 0)
    seg = text[start:end] if start >= 0 and end > start else text
    items: dict[int, dict] = {}
    for line in seg.splitlines():
        m = re.match(r"^(\d+)\.\s*【([^】]+)】(.+)$", line)
        if not m:
            continue
        n = int(m.group(1))
        body = re.sub(r"〔[^〕]+〕\s*$", "", m.group(3)).strip()
        items[n] = {"id": n, "source": m.group(2), "text": body}
    return items


def load_questions(path: Path) -> list[dict]:
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"题库必须是 JSON 数组：{path}")
    return [q for q in data if isinstance(q, dict)]


def load_rules(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    data = read_json(path)
    rules = data.get("rules") if isinstance(data, dict) else data
    if not isinstance(rules, list):
        raise ValueError(f"规则文件必须是数组或 {{rules: []}}：{path}")
    return [r for r in rules if isinstance(r, dict) and r.get("pattern")]


def load_overrides(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    data = read_json(path)
    return data if isinstance(data, dict) else {}


def normalize_refs(question: dict) -> tuple[set[int], list[str]]:
    refs = question.get("keypoint_ref") or []
    if isinstance(refs, str):
        refs = [refs]
    nums: set[int] = set()
    supplemental: list[str] = []
    for ref in refs:
        s = str(ref)
        m = re.search(r"第(\d+)条", s)
        if m:
            nums.add(int(m.group(1)))
        elif "补充" in s:
            supplemental.append(s)
    return nums, supplemental


def parse_blueprint_weights(md_text: str) -> dict[str, int]:
    weights: dict[str, int] = {}
    for line in md_text.splitlines():
        # 只匹配“| M03 鼻科学 | 24% | ...”这种科目标题行；
        # 不匹配附录里的“| M03 | 萎缩性鼻炎滴鼻浓度 | 1%～3% ...”数值行。
        m = re.match(r"^\|\s*(M\d{2})\s+[^\|\s]", line)
        if not m:
            continue
        p = re.search(r"(\d+)%", line)
        if p:
            weights[m.group(1)] = int(p.group(1))
    return weights or dict(MODULE_WEIGHTS)


# ---------------------------------------------------------------- mapping
def score_card(question: dict, card: dict, nums: set[int]) -> dict:
    shared = len(nums & set(card["keypoints"]))
    score = shared * 5.0
    if question.get("module") == card["module"]:
        score += 3.0
    if page_numbers(question.get("source_page")) & set(card["pages"]):
        score += 2.0
    text = f"{question.get('topic', '')} {question.get('stem', '')[:80]}"
    title_sim = jaccard(ngrams(text), ngrams(card["title_clean"]))
    body_sim = jaccard(ngrams(text), ngrams(card["body"][:600]))
    score += title_sim * 4.0 + body_sim * 2.0
    return {
        "card": card,
        "score": round(score, 3),
        "shared": shared,
        "title_sim": round(title_sim, 3),
        "body_sim": round(body_sim, 3),
    }


def match_rule(question: dict, rules: list[dict]) -> dict | None:
    # 只用 topic + stem；不要把 module_name（如“气管、支气管与食管异物”）拼进来，
    # 否则“食管异物”规则会误命中所有 M06 题目。
    text = f"{question.get('topic', '')} {question.get('stem', '')}"
    for rule in rules:
        mod = rule.get("module")
        if mod not in (None, "*", question.get("module")):
            continue
        try:
            if re.search(str(rule["pattern"]), text):
                return rule
        except re.error:
            continue
    return None


def provisional_id(question: dict, subject: str, rule: dict | None = None) -> tuple[str, str]:
    if rule and rule.get("provisional"):
        kc_id = str(rule["provisional"])
        display = kc_id.split(":", 1)[1] if ":" in kc_id else kc_id
        return kc_id, display
    base = normalize_topic(question.get("topic", ""), question.get("stem", ""))
    display = f"SUPP-{question.get('module', 'M00')}-{base}"
    return f"{subject.upper()}:{display}", display


def make_result(question: dict, primary: dict | None = None, method: str = "provisional",
                confidence: str = "low", score: float = 0.0,
                secondary: list[dict] | None = None, candidates: list[dict] | None = None,
                review_status: str = "auto", notes: str = "",
                provisional: tuple[str, str] | None = None) -> dict:
    if provisional:
        primary_kc, display = provisional
        candidates = candidates or []
        return {
            "question_id": question["id"],
            "module": question.get("module", ""),
            "topic": question.get("topic", ""),
            "primary_kc": primary_kc,
            "secondary_kcs": [],
            "mapping_method": "provisional",
            "confidence": "low",
            "score": 0.0,
            "candidates": candidates,
            "review_status": "needs_review",
            "notes": notes or f"provisional KC: {display}",
        }
    assert primary is not None
    return {
        "question_id": question["id"],
        "module": question.get("module", ""),
        "topic": question.get("topic", ""),
        "primary_kc": primary["kc_id"],
        "secondary_kcs": [c["kc_id"] for c in (secondary or [])],
        "mapping_method": method,
        "confidence": confidence,
        "score": round(score, 3),
        "candidates": candidates or [],
        "review_status": review_status,
        "notes": notes,
    }


def rule_result(question: dict, rule: dict, cards: list[dict], subject: str) -> dict:
    if rule.get("provisional"):
        return make_result(question, provisional=provisional_id(question, subject, rule),
                           notes=f"topic rule {rule.get('id')}: {rule.get('reason', '')}")
    target = next((c for c in cards if c["kc_id"].upper() == str(rule.get("kc", "")).upper()), None)
    if target:
        secondary_ids = {str(x).upper() for x in (rule.get("secondary") or [])}
        secondary = [c for c in cards if c["kc_id"].upper() in secondary_ids]
        return make_result(question, target, "topic_rule", "high", 20.0, secondary,
                           notes=f"topic rule {rule.get('id')}: {rule.get('reason', '')}")
    return make_result(question, provisional=provisional_id(question, subject, rule),
                       notes=f"topic rule {rule.get('id')} target missing: {rule.get('kc')}")


def map_question(question: dict, cards: list[dict], rules: list[dict], subject: str) -> dict:
    nums, supplemental = normalize_refs(question)
    same = [c for c in cards if c["module"] == question.get("module") and set(c["keypoints"]) & nums]
    if len(same) == 1:
        card = same[0]
        return make_result(question, card, "keypoint_exact", "high", 10.0,
                           notes=f"shared keypoints: {sorted(nums & set(card['keypoints']))}")

    if len(same) > 1:
        # 多卡歧义时，人工主题规则优先于分数 top1；避免 M07 颈部肿块
        # 因共享第124条而被分到错误的卡。
        rule = match_rule(question, rules)
        if rule:
            return rule_result(question, rule, cards, subject)
        scored = sorted((score_card(question, c, nums) for c in same), key=lambda x: -x["score"])
        top, second = scored[0], scored[1]
        cands = [{"kc_id": x["card"]["kc_id"], "score": x["score"],
                  "title": x["card"]["title"]} for x in scored[:5]]
        margin = top["score"] - second["score"]
        status = "auto" if margin >= 1.0 else "needs_review"
        return make_result(
            question, top["card"], "keypoint_multi",
            "high" if status == "auto" else "medium",
            top["score"], [x["card"] for x in scored[1:3]], cands, status,
            notes=f"multi-card margin={margin:.2f}; shared={sorted(nums & set(top['card']['keypoints']))}",
        )

    cross = [c for c in cards if c["module"] != question.get("module") and set(c["keypoints"]) & nums]
    if cross:
        if len(cross) > 1:
            rule = match_rule(question, rules)
            if rule:
                return rule_result(question, rule, cards, subject)
        scored = sorted((score_card(question, c, nums) for c in cross), key=lambda x: -x["score"])
        top = scored[0]
        cands = [{"kc_id": x["card"]["kc_id"], "score": x["score"], "title": x["card"]["title"]}
                 for x in scored[:5]]
        status = "auto" if len(scored) == 1 else "needs_review"
        return make_result(question, top["card"], "cross_module",
                           "medium" if status == "auto" else "low",
                           top["score"], [x["card"] for x in scored[1:2]], cands, status,
                           notes=f"cross-module shared={sorted(nums & set(top['card']['keypoints']))}")

    rule = match_rule(question, rules)
    if rule:
        return rule_result(question, rule, cards, subject)

    # similarity fallback within module
    same_module = [c for c in cards if c["module"] == question.get("module")]
    scored = sorted((score_card(question, c, nums) for c in same_module), key=lambda x: -x["score"])
    if scored:
        top, second = scored[0], scored[1] if len(scored) > 1 else {"score": 0.0}
        sim = max(top["title_sim"], 0.7 * top["title_sim"] + 0.3 * top["body_sim"])
        margin = sim - max(second.get("title_sim", 0.0), 0.7 * second.get("title_sim", 0.0) + 0.3 * second.get("body_sim", 0.0))
        cands = [{"kc_id": x["card"]["kc_id"], "score": x["score"], "title": x["card"]["title"],
                  "title_sim": x["title_sim"], "body_sim": x["body_sim"]} for x in scored[:5]]
        if sim >= 0.35 and margin >= 0.10:
            return make_result(question, top["card"], "similarity", "medium", top["score"],
                               [x["card"] for x in scored[1:2]], cands, "needs_review",
                               notes=f"similarity={sim:.2f}, margin={margin:.2f}")
        if sim >= 0.25:
            return make_result(question, provisional=provisional_id(question, subject),
                               candidates=cands, notes=f"low similarity={sim:.2f}; provisional")

    return make_result(question, provisional=provisional_id(question, subject),
                       notes=f"no keypoint/rule/similarity match; supplemental={supplemental}")


# ---------------------------------------------------------------- registry
def build_registry(subject: str, batch: str, review_path: Path, questions_path: Path,
                   keypoints_path: Path, rules_path: Path | None,
                   learning_value_path: Path | None = None,
                   anchor_overrides_path: Path | None = None,
                   question_overrides_path: Path | None = None) -> tuple[dict, list[dict], dict]:
    md_text = read_text(review_path)
    cards_raw = parse_review_cards(md_text)
    keypoint_items = parse_keypoint_items(read_text(keypoints_path))
    questions = load_questions(questions_path)
    rules = load_rules(rules_path)
    weights = parse_blueprint_weights(md_text)

    # 人工确认的锚点/题级覆盖：先应用，再映射；不改源题库文件。
    overrides = {}
    overrides.update(load_overrides(anchor_overrides_path))
    overrides.update(load_overrides(question_overrides_path))
    for q in questions:
        o = overrides.get(q.get("id"))
        if not o:
            continue
        if o.get("keypoint_ref"):
            q["keypoint_ref"] = o["keypoint_ref"]
        if o.get("teacher_anchor"):
            q["teacher_anchor"] = o["teacher_anchor"]
        if o.get("note"):
            q["override_note"] = o["note"]

    # 题目 v2 数据里有 12 条语义 slug（如 ENT-M01-检查器械-额镜）；
    # 合并进来只用于 aliases 追溯，不覆盖源题库字段。
    if learning_value_path and learning_value_path.exists():
        lv_by_id = {x.get("id"): x for x in read_json(learning_value_path) if isinstance(x, dict)}
        for q in questions:
            extra = lv_by_id.get(q.get("id"))
            if extra:
                if extra.get("kc_id") and not q.get("kc_id"):
                    q["kc_id"] = extra["kc_id"]
                if extra.get("kc_path") and not q.get("kc_path"):
                    q["kc_path"] = extra["kc_path"]

    subject_code = subject.upper()
    for card in cards_raw:
        card["kc_id"] = f"{subject_code}:{card['display_id']}"
        card["title_clean"] = card.get("title_clean") or clean_title(card["title"])

    question_map: list[dict] = []
    for q in questions:
        if not q.get("id"):
            continue
        question_map.append(map_question(q, cards_raw, rules, subject))

    primary_by_kc: dict[str, list[str]] = defaultdict(list)
    secondary_by_kc: dict[str, list[str]] = defaultdict(list)
    aliases: dict[str, str] = {}
    for row, q in zip(question_map, questions):
        primary_by_kc[row["primary_kc"]].append(row["question_id"])
        for kc in row.get("secondary_kcs") or []:
            secondary_by_kc[kc].append(row["question_id"])
        if q.get("kc_id") and row.get("primary_kc"):
            aliases[str(q["kc_id"])] = row["primary_kc"]

    cards = []
    for card in cards_raw:
        qids = sorted(set(primary_by_kc.get(card["kc_id"], [])))
        secondary = sorted(set(secondary_by_kc.get(card["kc_id"], [])) - set(qids))
        status = "active" if qids or secondary else "content_only"
        cards.append({
            "kc_id": card["kc_id"],
            "display_id": card["display_id"],
            "subject": subject_code,
            "module": card["module"],
            "title": card["title"],
            "keypoints": card["keypoints"],
            "question_ids": qids,
            "secondary_question_ids": secondary,
            "source_pages": card["pages"],
            "review_anchor": f"L{card['line_start']}",
            "content_chars": card["content_chars"],
            "blueprint_weight": weights.get(card["module"], MODULE_WEIGHTS.get(card["module"], 0)),
            "status": status,
            "needs_content": False,
            "aliases": sorted(k for k, v in aliases.items() if v == card["kc_id"]),
            "notes": "",
            "version": 1,
        })

    provisional_rows = [r for r in question_map if r["mapping_method"] == "provisional"]
    provisional_by_kc: dict[str, list[dict]] = defaultdict(list)
    for row in provisional_rows:
        provisional_by_kc[row["primary_kc"]].append(row)
    provisional = []
    for kc_id, rows in sorted(provisional_by_kc.items()):
        first = rows[0]
        display = kc_id.split(":", 1)[1] if ":" in kc_id else kc_id
        provisional.append({
            "kc_id": kc_id,
            "display_id": display,
            "subject": subject_code,
            "module": first.get("module", "M00"),
            "title": normalize_topic(first.get("topic", "")),
            "keypoints": [],
            "question_ids": sorted(r["question_id"] for r in rows),
            "secondary_question_ids": [],
            "source_pages": [],
            "review_anchor": "",
            "content_chars": 0,
            "blueprint_weight": weights.get(first.get("module", ""), 0),
            "status": "question_only",
            "needs_content": True,
            "aliases": [],
            "notes": "题库覆盖但复习资料暂无独立卡；列入下一批补卡清单",
            "version": 1,
        })

    registry = {
        "schema_version": 1,
        "subject": subject_code,
        "batch": batch,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "cards": cards,
        "provisional": provisional,
        "metadata": {
            "review_path": str(review_path.relative_to(BASE)) if review_path.is_relative_to(BASE) else str(review_path),
            "questions_path": str(questions_path.relative_to(BASE)) if questions_path.is_relative_to(BASE) else str(questions_path),
            "keypoints_path": str(keypoints_path.relative_to(BASE)) if keypoints_path.is_relative_to(BASE) else str(keypoints_path),
            "rules_path": str(rules_path.relative_to(BASE)) if rules_path and rules_path.exists() and rules_path.is_relative_to(BASE) else str(rules_path or ""),
            "learning_value_path": str(learning_value_path.relative_to(BASE)) if learning_value_path and learning_value_path.exists() and learning_value_path.is_relative_to(BASE) else str(learning_value_path or ""),
            "anchor_overrides_path": str(anchor_overrides_path.relative_to(BASE)) if anchor_overrides_path and anchor_overrides_path.exists() and anchor_overrides_path.is_relative_to(BASE) else str(anchor_overrides_path or ""),
            "question_overrides_path": str(question_overrides_path.relative_to(BASE)) if question_overrides_path and question_overrides_path.exists() and question_overrides_path.is_relative_to(BASE) else str(question_overrides_path or ""),
            "card_count": len(cards),
            "provisional_count": len(provisional),
            "question_count": len(question_map),
            "keypoint_items": len(keypoint_items),
            "blueprint_weights": weights,
        },
    }
    return registry, question_map, {
        "keypoint_items": keypoint_items,
        "questions": questions,
        "rules": rules,
        "aliases": aliases,
        "weights": weights,
    }


# ---------------------------------------------------------------- check
def check_registry(registry: dict, question_map: list[dict], *,
                   expect_cards: int | None = None,
                   expect_keypoints: int | None = None,
                   expect_questions: int | None = None,
                   strict: bool = False) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        from jsonschema import validate as js_validate
        schema_path = BASE / "schemas/kc.schema.json"
        if schema_path.exists():
            js_validate(registry, read_json(schema_path))
    except ImportError:
        warnings.append("jsonschema 未安装，跳过 schema 校验")
    except Exception as exc:
        errors.append(f"schema 校验失败：{exc}")

    cards = registry.get("cards", [])
    provisional = registry.get("provisional", [])
    all_kcs = cards + provisional
    kc_ids = [k.get("kc_id") for k in all_kcs]
    dup_ids = [k for k, v in Counter(kc_ids).items() if v > 1]
    if dup_ids:
        errors.append(f"kc_id 重复：{dup_ids[:10]}")

    display_ids = [(k.get("subject"), k.get("display_id")) for k in all_kcs]
    dup_display = [k for k, v in Counter(display_ids).items() if v > 1]
    if dup_display:
        errors.append(f"display_id 重复：{dup_display[:10]}")

    if expect_cards is not None and len(cards) != expect_cards:
        errors.append(f"卡片数 {len(cards)} != 期望 {expect_cards}")

    keypoints = set()
    for k in all_kcs:
        keypoints.update(int(x) for x in (k.get("keypoints") or []))
    if expect_keypoints is not None:
        expected = set(range(1, expect_keypoints + 1))
        missing = sorted(expected - keypoints)
        extra = sorted(keypoints - expected)
        if missing:
            errors.append(f"未覆盖重点条号 {len(missing)} 个：{missing[:20]}")
        if extra:
            errors.append(f"越界重点条号：{extra[:20]}")

    mapped = [r for r in question_map if r.get("primary_kc")]
    missing_primary = [r.get("question_id") for r in question_map if not r.get("primary_kc")]
    if missing_primary:
        errors.append(f"缺主 KC 的题 {len(missing_primary)} 道：{missing_primary[:10]}")
    if expect_questions is not None and len(question_map) != expect_questions:
        errors.append(f"题数 {len(question_map)} != 期望 {expect_questions}")

    content_only = [k for k in cards if k.get("status") == "content_only"]
    provisional_rows = [r for r in question_map if r.get("mapping_method") == "provisional"]
    review_rows = [r for r in question_map if r.get("review_status") == "needs_review"]
    content_ratio = len(content_only) / len(cards) if cards else 0.0
    provisional_ratio = len(provisional_rows) / len(question_map) if question_map else 0.0
    if content_only:
        warnings.append(f"content_only 卡片 {len(content_only)}/{len(cards)}（{content_ratio:.1%}）")
    if provisional:
        warnings.append(f"provisional KC {len(provisional)} 个，覆盖 {len(provisional_rows)} 题（{provisional_ratio:.1%}）")
    if review_rows:
        warnings.append(f"需人工复核映射 {len(review_rows)} 题（{len(review_rows)/len(question_map):.1%}）")

    if strict:
        if content_ratio > 0.15:
            warnings.append(f"content_only 超过 15% 目标（{content_ratio:.1%}）")
        if len(provisional) > 8:
            warnings.append(f"provisional KC 超过 8 个（{len(provisional)}）")
        if provisional_ratio > 0.10:
            warnings.append(f"provisional 题占比超过 10%（{provisional_ratio:.1%}）")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "cards": len(cards),
        "provisional": len(provisional),
        "questions": len(question_map),
        "mapped": len(mapped),
        "keypoints": len(keypoints),
        "content_only": len(content_only),
        "content_ratio": round(content_ratio, 4),
        "provisional_ratio": round(provisional_ratio, 4),
        "review_rows": len(review_rows),
    }


def print_check(result: dict) -> None:
    print(f"=== KC 注册表校验 ===")
    print(f"  卡片 {result['cards']} ｜ provisional {result['provisional']} ｜ "
          f"题目 {result['questions']} ｜ 已映射 {result['mapped']} ｜ 重点 {result['keypoints']}")
    print(f"  content_only {result['content_only']} ({result['content_ratio']:.1%}) ｜ "
          f"provisional 题 {result['provisional_ratio']:.1%} ｜ 需复核 {result['review_rows']}")
    for w in result["warnings"]:
        print(f"  ⚠️ {w}")
    for e in result["errors"]:
        print(f"  ❌ {e}")
    print(f"=== 结果: {'PASS' if result['ok'] else 'FAIL'} ===")


# ---------------------------------------------------------------- report
def render_report(registry: dict, question_map: list[dict], extra: dict,
                  out_path: Path) -> dict:
    cards = registry.get("cards", [])
    provisional = registry.get("provisional", [])
    by_module: dict[str, dict] = defaultdict(lambda: {
        "cards": 0, "keypoints": 0, "questions": 0, "content_only": 0,
        "provisional": 0, "needs_review": 0, "methods": Counter(),
    })
    for c in cards:
        m = by_module[c["module"]]
        m["cards"] += 1
        m["keypoints"] += len(c.get("keypoints") or [])
        if c.get("status") == "content_only":
            m["content_only"] += 1
    for p in provisional:
        by_module[p["module"]]["provisional"] += 1
    for row in question_map:
        m = by_module[row.get("module", "M00")]
        m["questions"] += 1
        m["methods"][row.get("mapping_method", "?")] += 1
        if row.get("review_status") == "needs_review":
            m["needs_review"] += 1
    method_counts = Counter(r.get("mapping_method", "?") for r in question_map)
    content_only = [c for c in cards if c.get("status") == "content_only"]
    review_rows = [r for r in question_map if r.get("review_status") == "needs_review"]
    check = check_registry(registry, question_map, strict=False)

    lines = [
        "# KC 映射报告 · 耳鼻咽喉头颈外科学（batch040 试点）",
        "",
        f"> 生成：{registry.get('generated_at', '')} ｜ 卡片 {len(cards)} ｜ provisional {len(provisional)} ｜ 题目 {len(question_map)}",
        "> 本报告只记录映射事实与待复核项；不改源题库、不改教师重点原文。",
        "",
        "## 1. 总览",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 知识卡 | {len(cards)} |",
        f"| 教师重点条号 | {len(set().union(*[set(c.get('keypoints') or []) for c in cards])) if cards else 0} |",
        f"| 题目 | {len(question_map)} |",
        f"| 已映射主 KC | {check['mapped']} |",
        f"| provisional KC | {len(provisional)} |",
        f"| provisional 题 | {check['provisional_ratio']:.1%} |",
        f"| content_only 卡 | {len(content_only)}（{check['content_ratio']:.1%}） |",
        f"| 需人工复核映射 | {len(review_rows)}（{len(review_rows)/len(question_map):.1%}） |",
        "",
        "## 2. 映射方法分布",
        "",
        "| 方法 | 题数 |",
        "|---|---:|",
    ]
    for method, count in method_counts.most_common():
        lines.append(f"| {method} | {count} |")
    lines += [
        "",
        "## 3. 分模块",
        "",
        "| 模块 | 卡片 | 重点条号 | 主映射题 | content_only | provisional KC | 需复核 | 主要方法 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for mod in sorted(by_module):
        m = by_module[mod]
        main = ", ".join(f"{k}:{v}" for k, v in m["methods"].most_common(3)) or "-"
        lines.append(f"| {mod} | {m['cards']} | {m['keypoints']} | {m['questions']} | "
                     f"{m['content_only']} | {m['provisional']} | {m['needs_review']} | {main} |")

    lines += ["", "## 4. content_only 卡片（有内容、暂无题）", ""]
    if content_only:
        lines += ["| K-ID | 模块 | 标题 | 重点条号 |", "|---|---|---|---|"]
        for c in content_only:
            lines.append(f"| {c['display_id']} | {c['module']} | {c['title']} | "
                         f"{', '.join(str(x) for x in c.get('keypoints') or []) or '-'} |")
    else:
        lines.append("无。")

    lines += ["", "## 5. provisional KC（题有、卡无）", ""]
    if provisional:
        lines += ["| KC | 模块 | 标题 | 题数 | 题号（前 8） |", "|---|---|---|---:|---|"]
        for p in provisional:
            qids = p.get("question_ids") or []
            lines.append(f"| {p['display_id']} | {p['module']} | {p['title']} | {len(qids)} | "
                         f"{', '.join(qids[:8])} |")
    else:
        lines.append("无。")

    lines += ["", "## 6. 待人工复核映射（前 30）", ""]
    if review_rows:
        lines += ["| 题号 | 模块 | 主题 | 主 KC | 方法 | 候选 | 备注 |",
                  "|---|---|---|---|---|---|---|"]
        for r in review_rows[:30]:
            cands = "; ".join(f"{c.get('kc_id')}({c.get('score')})" for c in (r.get("candidates") or [])[:3])
            lines.append(f"| {r['question_id']} | {r.get('module', '')} | {r.get('topic', '')} | "
                         f"{r['primary_kc']} | {r.get('mapping_method')} | {cands or '-'} | {r.get('notes', '')} |")
        if len(review_rows) > 30:
            lines.append(f"| … | | | | | | 其余 {len(review_rows) - 30} 条见 kc_manual_queue.csv |")
    else:
        lines.append("无。")

    lines += ["", "## 7. 结论", ""]
    if check["ok"]:
        lines.append(f"- 主映射：{check['mapped']}/{check['questions']}，无缺主 KC 的题。")
        lines.append(f"- 重点覆盖：{check['keypoints']} 条。")
        lines.append(f"- 风险：content_only {check['content_ratio']:.1%}；provisional 题 {check['provisional_ratio']:.1%}；需复核 {check['review_rows']} 题。")
        lines.append("- 下一步：人工复核 `kc_manual_queue.csv`；provisional KC 列入下一批补卡清单；content_only 卡逐张确认保留/合并。")
    else:
        lines.append("- 存在硬错误，先修复 error 再交付。")
    lines += [
        "",
        "## 8. 规则来源",
        "",
        f"- 映射规则：`{registry.get('metadata', {}).get('rules_path', '')}`",
        f"- 输入复习资料：`{registry.get('metadata', {}).get('review_path', '')}`",
        f"- 输入题库：`{registry.get('metadata', {}).get('questions_path', '')}`",
        f"- 输入锚定清单：`{registry.get('metadata', {}).get('keypoints_path', '')}`",
        "",
    ]
    atomic_write(out_path, "\n".join(lines))
    return check


def write_manual_queue(question_map: list[dict], questions: list[dict], out_path: Path) -> int:
    qmap = {q.get("id"): q for q in questions}
    rows = [r for r in question_map if r.get("review_status") != "auto" or r.get("mapping_method") == "provisional"]
    fieldnames = [
        "question_id", "module", "topic", "stem", "keypoint_ref", "primary_kc",
        "mapping_method", "confidence", "candidates_json", "decision", "review_status", "note",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            q = qmap.get(r["question_id"], {})
            decision = "provisional_group" if r.get("mapping_method") == "provisional" else "auto_top1_needs_review"
            writer.writerow({
                "question_id": r["question_id"],
                "module": r.get("module", ""),
                "topic": r.get("topic", ""),
                "stem": (q.get("stem") or "").replace("\n", " ")[:160],
                "keypoint_ref": json.dumps(q.get("keypoint_ref") or [], ensure_ascii=False),
                "primary_kc": r.get("primary_kc", ""),
                "mapping_method": r.get("mapping_method", ""),
                "confidence": r.get("confidence", ""),
                "candidates_json": json.dumps(r.get("candidates") or [], ensure_ascii=False),
                "decision": decision,
                "review_status": r.get("review_status", ""),
                "note": r.get("notes", ""),
            })
    return len(rows)


def load_registry(path: Path) -> tuple[dict, list[dict]]:
    registry = read_json(path)
    map_path = path.with_name("kc_question_map.jsonl")
    rows = []
    if map_path.exists():
        for line in read_text(map_path).splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return registry, rows


# ---------------------------------------------------------------- cli
def cmd_build(args) -> int:
    subject = args.subject
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    review = Path(args.review)
    questions_path = Path(args.questions)
    keypoints = Path(args.keypoints)
    rules = Path(args.rules) if args.rules else None

    for p, label in [(review, "review"), (questions_path, "questions"), (keypoints, "keypoints")]:
        if not p.exists():
            print(f"[FAIL] {label} 不存在：{p}", file=sys.stderr)
            return 2

    registry, question_map, extra = build_registry(
        subject, args.batch, review, questions_path, keypoints, rules,
        Path(args.learning_value) if args.learning_value else None,
        Path(args.anchor_overrides) if args.anchor_overrides else None,
        Path(args.question_overrides) if args.question_overrides else None,
    )
    check = check_registry(
        registry, question_map,
        expect_cards=args.expect_cards,
        expect_keypoints=args.expect_keypoints,
        expect_questions=args.expect_questions,
        strict=False,
    )
    write_json(output / "kc_registry.json", registry)
    write_json(output / "kc_aliases.json", extra["aliases"])
    write_jsonl(output / "kc_question_map.jsonl", question_map)
    write_manual_queue(question_map, extra["questions"], output / "kc_manual_queue.csv")
    render_report(registry, question_map, extra, output / "kc_mapping_report.md")

    print(f"✅ KC 注册表：{len(registry['cards'])} 卡 + {len(registry['provisional'])} provisional；"
          f"{len(question_map)} 题；重点 {check['keypoints']}")
    print(f"   方法分布：{dict(Counter(r.get('mapping_method') for r in question_map))}")
    print(f"   content_only {check['content_only']} ({check['content_ratio']:.1%})；"
          f"provisional 题 {check['provisional_ratio']:.1%}；需复核 {check['review_rows']}")
    print(f"   输出：{output}")
    print_check(check)
    return 0 if check["ok"] else 1


def cmd_check(args) -> int:
    registry, question_map = load_registry(Path(args.file))
    result = check_registry(
        registry, question_map,
        expect_cards=args.expect_cards,
        expect_keypoints=args.expect_keypoints,
        expect_questions=args.expect_questions,
        strict=args.strict,
    )
    print_check(result)
    return 0 if result["ok"] else 1


def cmd_report(args) -> int:
    registry, question_map = load_registry(Path(args.file))
    out = Path(args.out)
    render_report(registry, question_map, {}, out)
    print(f"✅ 报告：{out}")
    return 0


def cmd_query(args) -> int:
    registry = read_json(Path(args.file))
    map_path = Path(args.file).with_name("kc_question_map.jsonl")
    qmap = {}
    if map_path.exists():
        for line in read_text(map_path).splitlines():
            if line.strip():
                row = json.loads(line)
                qmap[row["question_id"]] = row
    questions_path = Path(args.questions) if args.questions else DEFAULT_QUESTIONS
    questions = {q.get("id"): q for q in load_questions(questions_path)} if questions_path.exists() else {}
    all_kcs = registry.get("cards", []) + registry.get("provisional", [])
    target = next((k for k in all_kcs if k.get("kc_id") == args.kc or k.get("display_id") == args.kc), None)
    if not target:
        print(f"[FAIL] 未找到 KC：{args.kc}", file=sys.stderr)
        return 1
    ids = list(target.get("question_ids") or []) + list(target.get("secondary_question_ids") or [])
    detail = []
    for qid in ids:
        q = questions.get(qid, {})
        row = qmap.get(qid, {})
        detail.append({
            "question_id": qid,
            "stem": q.get("stem", ""),
            "type": q.get("type", ""),
            "module": q.get("module", ""),
            "keypoint_ref": q.get("keypoint_ref", []),
            "source_page": q.get("source_page", ""),
            "mapping_method": row.get("mapping_method", ""),
            "review_status": row.get("review_status", ""),
        })
    print(json.dumps({"kc": target, "questions": detail, "question_count": len(detail)},
                     ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    _configure_stdio()
    ap = argparse.ArgumentParser(description="KC 注册表与双向映射（T2–T4）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="构建 KC 注册表与映射")
    b.add_argument("--subject", default=DEFAULT_SUBJECT)
    b.add_argument("--batch", default=DEFAULT_BATCH)
    b.add_argument("--review", default=str(DEFAULT_REVIEW))
    b.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    b.add_argument("--keypoints", default=str(DEFAULT_KEYPOINTS))
    b.add_argument("--rules", default=str(DEFAULT_RULES))
    b.add_argument("--learning-value", default=str(DEFAULT_LEARNING_VALUE))
    b.add_argument("--anchor-overrides", default=str(DEFAULT_ANCHOR_OVERRIDES))
    b.add_argument("--question-overrides", default=str(DEFAULT_QUESTION_OVERRIDES))
    b.add_argument("--out", default=str(DEFAULT_OUT))
    b.add_argument("--expect-cards", type=int, default=85)
    b.add_argument("--expect-keypoints", type=int, default=125)
    b.add_argument("--expect-questions", type=int, default=200)

    c = sub.add_parser("check", help="校验注册表")
    c.add_argument("--file", required=True)
    c.add_argument("--expect-cards", type=int, default=85)
    c.add_argument("--expect-keypoints", type=int, default=125)
    c.add_argument("--expect-questions", type=int, default=200)
    c.add_argument("--strict", action="store_true")

    r = sub.add_parser("report", help="生成映射报告")
    r.add_argument("--file", required=True)
    r.add_argument("--map", default="")
    r.add_argument("--out", required=True)

    q = sub.add_parser("query", help="回查 KC")
    q.add_argument("--file", required=True)
    q.add_argument("--kc", required=True)
    q.add_argument("--questions", default=str(DEFAULT_QUESTIONS))

    args = ap.parse_args()
    if args.cmd == "build":
        return cmd_build(args)
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "query":
        return cmd_query(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
