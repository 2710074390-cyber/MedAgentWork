#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spaced_schedule.py — M3/T7–T9：复习卡片构建 + SM-2 调度 + Anki 导出。

设计原则
    - 只读源复习资料/锚定清单/KC 注册表；新产物落 中间产物/batch040/pilot/。
    - 82 道自测与 90 行附录答案按「模块 + 卡片 ID」对账；缺答案不编造，写入缺口报告。
    - 125 条教师重点生成 cloze/recall 卡；每条重点至少 1 张卡。
    - SM-2 为试点基线；保留 FSRS 适配接口（未来替换）。
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

def _configure_stdio() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


BASE = Path(__file__).resolve().parent.parent
DEFAULT_REVIEW = BASE / "复习资料/耳鼻咽喉头颈外科学教师重点版/耳鼻咽喉头颈外科学教师重点版_主复习资料.md"
DEFAULT_KEYPOINTS = BASE / "输入素材/大四上/耳鼻咽喉头颈外科学/耳鼻咽喉头颈外科学_教师重点_锚定清单_20261019.md"
DEFAULT_KC = BASE / "中间产物/batch040/pilot/kc_registry.json"
DEFAULT_OUT = BASE / "中间产物/batch040/pilot"
DEFAULT_ITEMS = DEFAULT_OUT / "review_items.jsonl"
DEFAULT_STATE = DEFAULT_OUT / "schedule_state.json"

FACT_RE = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+)?(?:~\d+(?:\.\d+)?)*)"
    r"(?:mmHg|cmH2O|IU|cm|mm|mg|kg|ml|dB|Hz|min|%|°|度|分|时|日|周|月|年|岁|"
    r"次|倍|条|个|组|区|期|级|张|瓶|支|片|g|m)"
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path):
    return json.loads(read_text(path))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_json(path: Path, data) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    write_text(path, "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""))


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_self_tests(md_text: str) -> list[dict]:
    """解析 `<b>🔄 自测</b>：...（答案见附录五）`，记录模块/卡片/行号。"""
    lines = md_text.splitlines()
    module = None
    card = None
    prompts = []
    for i, line in enumerate(lines, 1):
        m = re.match(r"^## 模块(\d+)：", line)
        if m:
            module = f"M{int(m.group(1)):02d}"
            card = None
            continue
        m = re.match(r"^#### .*?(K-M\d{2}-\d{3})", line)
        if m:
            card = m.group(1)
            continue
        m = re.search(r"<b>🔄 自测</b>：(.+?)（答案见附录五）", line)
        if m:
            prompts.append({
                "module": module or "M00",
                "card": card or "",
                "line": i,
                "prompt": strip_html(m.group(1)),
            })
    return prompts


def parse_appendix_rows(md_text: str) -> list[dict]:
    """解析附录五的 `| 题 | 答案 | 卡片 |` 行。"""
    start = md_text.find("## 附录五：主动回忆答案")
    if start < 0:
        return []
    seg = md_text[start:]
    rows = []
    for m in re.finditer(r"^### (M\d{2})[^\n]*\n(.*?)(?=^### |\Z)", seg, re.M | re.S):
        module = m.group(1)
        body = m.group(2)
        for r in re.finditer(r"^\|\s*(\d+|补)\s*\|\s*(.+?)\s*\|\s*(K-M\d{2}-\d{3})\s*\|", body, re.M):
            rows.append({
                "module": module,
                "num": r.group(1),
                "answer": r.group(2).strip(),
                "card": r.group(3),
            })
    return rows


def reconcile(prompts: list[dict], rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """按 (module, card) 顺序匹配；匹配不到 → gap；未使用 → appendix_only。"""
    by_card = defaultdict(list)
    for idx, row in enumerate(rows):
        by_card[(row["module"], row["card"])].append((idx, row))
    matched = []
    gaps = []
    used = set()
    for p in prompts:
        bucket = by_card.get((p["module"], p["card"]), [])
        if bucket:
            idx, row = bucket.pop(0)
            used.add(idx)
            matched.append({"prompt": p, "row": row})
        else:
            gaps.append(p)
    extras = [row for idx, row in enumerate(rows) if idx not in used]
    return matched, gaps, extras


def parse_keypoint_items(text: str) -> dict[int, dict]:
    start = text.find("## 四、统一锚定清单")
    end = text.find("## 五、原始标号对照", start if start >= 0 else 0)
    seg = text[start:end] if start >= 0 and end > start else text
    items = {}
    for line in seg.splitlines():
        m = re.match(r"^(\d+)\.\s*【([^】]+)】(.+)$", line)
        if not m:
            continue
        n = int(m.group(1))
        items[n] = {
            "id": n,
            "source": m.group(2),
            "text": re.sub(r"〔[^〕]+〕\s*$", "", m.group(3)).strip(),
        }
    return items


def build_keypoint_items(md_text: str, keypoint_items: dict[int, dict]) -> list[dict]:
    import kc_registry as kc

    cards = kc.parse_review_cards(md_text)
    by_kp = {}
    for card in cards:
        for kp in card.get("keypoints") or []:
            by_kp.setdefault(int(kp), card)

    items = []
    for kp in sorted(keypoint_items):
        target = keypoint_items[kp]
        card = by_kp.get(kp)
        kc_id = f"ENT:{card['display_id']}" if card else f"ENT:KP-{kp:03d}"
        module = card["module"] if card else "M00"
        pages = card.get("pages") if card else []
        text = target["text"]
        m = FACT_RE.search(text)
        if m:
            front = text[:m.start()] + "{{c1::" + m.group(0) + "}}" + text[m.end():]
            item_type = "cloze"
        else:
            front = f"教师重点第{kp}条（{module}）：请复述本条核心要点（提示：{text[:24]}…）"
            item_type = "keypoint_recall"
        items.append({
            "item_id": f"ENT-KP-{kp:03d}",
            "kc_id": kc_id,
            "module": module,
            "type": item_type,
            "front": front,
            "back": text,
            "source_quote": text,
            "source_page": f"P{pages[0]}" if pages else "",
            "tags": ["ENT", module, kc_id, f"教师重点第{kp}条"],
            "origin": "keypoint",
            "status": "active",
        })
    return items


def build_recall_items(matched: list[dict]) -> list[dict]:
    items = []
    counter = defaultdict(int)
    for pair in matched:
        p = pair["prompt"]
        row = pair["row"]
        module = p["module"]
        counter[module] += 1
        items.append({
            "item_id": f"ENT-RECALL-{module}-{counter[module]:03d}",
            "kc_id": f"ENT:{p['card']}",
            "module": module,
            "type": "recall",
            "front": p["prompt"],
            "back": row["answer"],
            "source_quote": row["answer"],
            "source_page": "",
            "tags": ["ENT", module, f"ENT:{p['card']}", "appendix5"],
            "origin": "appendix5",
            "status": "active",
        })
    return items


def dedupe(items: list[dict]) -> tuple[list[dict], int]:
    seen = set()
    out = []
    for item in items:
        key = (item["kc_id"], re.sub(r"\s+", "", item["front"]))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out, len(items) - len(out)


def init_state(items: list[dict], existing: dict | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    state = existing or {"schema_version": 1, "items": {}}
    state.setdefault("schema_version", 1)
    state.setdefault("items", {})
    for item in items:
        state["items"].setdefault(item["item_id"], {
            "due": today.isoformat(),
            "interval": 0,
            "ease": 2.5,
            "reps": 0,
            "lapses": 0,
            "last_rating": None,
            "last_reviewed": None,
        })
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return state


def sm2_update(state: dict, rating: int, today: date) -> dict:
    ease = float(state.get("ease", 2.5))
    interval = int(state.get("interval", 0))
    reps = int(state.get("reps", 0))
    lapses = int(state.get("lapses", 0))
    if rating <= 0:
        interval = 1
        reps = 0
        lapses += 1
        ease = max(1.3, ease - 0.20)
    elif rating == 1:
        interval = 1 if reps == 0 else max(1, round(interval * 1.2))
        reps += 1
        ease = max(1.3, ease - 0.15)
    elif rating == 2:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 3
        else:
            interval = max(1, round(interval * ease))
        reps += 1
    else:
        if reps == 0:
            interval = 2
        elif reps == 1:
            interval = 5
        else:
            interval = max(1, round(interval * ease * 1.3))
        reps += 1
        ease = min(3.0, ease + 0.15)
    return {
        "due": (today + timedelta(days=interval)).isoformat(),
        "interval": interval,
        "ease": round(ease, 2),
        "reps": reps,
        "lapses": lapses,
        "last_rating": rating,
        "last_reviewed": today.isoformat(),
    }


def load_items(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in read_text(path).splitlines() if x.strip()]


def load_state(path: Path) -> dict:
    return read_json(path) if path.exists() else {"schema_version": 1, "items": {}}


def write_reconciliation(path: Path, prompts: list[dict], rows: list[dict],
                         matched: list[dict], gaps: list[dict], extras: list[dict]) -> None:
    by_mod = defaultdict(lambda: {"prompts": 0, "rows": 0, "matched": 0, "gaps": 0, "extras": 0})
    for p in prompts:
        by_mod[p["module"]]["prompts"] += 1
    for r in rows:
        by_mod[r["module"]]["rows"] += 1
    for x in matched:
        by_mod[x["prompt"]["module"]]["matched"] += 1
    for x in gaps:
        by_mod[x["module"]]["gaps"] += 1
    for x in extras:
        by_mod[x["module"]]["extras"] += 1
    lines = [
        "# 主动回忆答案对账报告",
        "",
        f"> 自测题 {len(prompts)} ｜ 附录答案行 {len(rows)} ｜ 匹配 {len(matched)} ｜ 缺答案 {len(gaps)} ｜ 附录多余行 {len(extras)}",
        "> 缺答案不编造；缺答案题不进入复习队列，列入下一批补写清单。",
        "",
        "## 分模块",
        "",
        "| 模块 | 自测 | 答案行 | 匹配 | 缺答案 | 多余行 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for mod in sorted(by_mod):
        m = by_mod[mod]
        lines.append(f"| {mod} | {m['prompts']} | {m['rows']} | {m['matched']} | {m['gaps']} | {m['extras']} |")
    lines += ["", "## 缺答案自测（不进入队列）", ""]
    if gaps:
        lines += ["| 题号 | 模块 | 卡片 | 题干 |", "|---|---|---|---|"]
        for p in gaps:
            lines.append(f"| L{p['line']} | {p['module']} | {p['card']} | {p['prompt']} |")
    else:
        lines.append("无。")
    lines += ["", "## 附录多余行（未匹配自测）", ""]
    if extras:
        lines += ["| 模块 | 题号 | 卡片 | 答案（前 60 字） |", "|---|---|---|---|"]
        for r in extras:
            lines.append(f"| {r['module']} | {r['num']} | {r['card']} | {r['answer'][:60]} |")
    else:
        lines.append("无。")
    lines += ["", "## 处置", "",
              "- 匹配题：进入 `review_items.jsonl`（origin=appendix5）。",
              "- 缺答案题：不进入队列，下一批补写附录答案后重新对账。",
              "- 多余行：保留在报告中，供下一批补自测题或人工确认。",
              ""]
    write_text(path, "\n".join(lines))


def cmd_build(args) -> int:
    md_text = read_text(Path(args.review))
    prompts = parse_self_tests(md_text)
    rows = parse_appendix_rows(md_text)
    matched, gaps, extras = reconcile(prompts, rows)
    kp_items = parse_keypoint_items(read_text(Path(args.keypoints)))
    kp_cards = build_keypoint_items(md_text, kp_items)
    recall_items = build_recall_items(matched)
    items, duplicates = dedupe(recall_items + kp_cards)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "review_items.jsonl", items)
    write_reconciliation(out / "answer_reconciliation.md", prompts, rows, matched, gaps, extras)
    existing = None if args.reset_state else load_state(Path(args.state))
    state = init_state(items, existing)
    write_json(Path(args.state), state)
    print(f"✅ 卡片：{len(items)} 张（recall {len(recall_items)} + keypoint {len(kp_cards)}；去重 {duplicates}）")
    print(f"   自测对账：{len(prompts)} 题 / 匹配 {len(matched)} / 缺答案 {len(gaps)} / 多余行 {len(extras)}")
    print(f"   队列：{out / 'review_items.jsonl'}")
    print(f"   对账：{out / 'answer_reconciliation.md'}")
    print(f"   状态：{args.state}")
    return 0


def cmd_schedule(args) -> int:
    items = load_items(Path(args.items))
    state = load_state(Path(args.state))
    due = args.date or date.today().isoformat()
    due_items = []
    for item in items:
        st = state.get("items", {}).get(item["item_id"], {})
        if st.get("due", due) <= due:
            due_items.append({
                "item_id": item["item_id"],
                "kc_id": item["kc_id"],
                "type": item["type"],
                "front": item["front"],
                "due": st.get("due", due),
                "reps": st.get("reps", 0),
            })
    # 新卡优先：避免旧卡 due 排序把新卡饿死
    due_items.sort(key=lambda x: (x["reps"] > 0, x["due"], x["item_id"]))
    due_items = due_items[: args.limit]
    print(json.dumps({"date": due, "due_count": len(due_items), "items": due_items},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_grade(args) -> int:
    items = {x["item_id"]: x for x in load_items(Path(args.items))}
    if args.item not in items:
        print(f"[FAIL] 未知 item：{args.item}", file=sys.stderr)
        return 1
    state = load_state(Path(args.state))
    today = date.fromisoformat(args.date) if args.date else date.today()
    st = state.setdefault("items", {}).setdefault(args.item, {
        "due": today.isoformat(), "interval": 0, "ease": 2.5,
        "reps": 0, "lapses": 0, "last_rating": None, "last_reviewed": None,
    })
    updated = sm2_update(st, args.rating, today)
    state["items"][args.item] = updated
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_json(Path(args.state), state)
    print(json.dumps({"item_id": args.item, "rating": args.rating, **updated}, ensure_ascii=False, indent=2))
    return 0


def cmd_stats(args) -> int:
    items = load_items(Path(args.items))
    state = load_state(Path(args.state))
    today = args.date or date.today().isoformat()
    rows = state.get("items", {})
    due = sum(1 for i in items if rows.get(i["item_id"], {}).get("due", today) <= today)
    new = sum(1 for i in items if rows.get(i["item_id"], {}).get("reps", 0) == 0)
    learned = len(items) - new
    intervals = [rows.get(i["item_id"], {}).get("interval", 0) for i in items if rows.get(i["item_id"], {}).get("reps", 0) > 0]
    print(json.dumps({
        "total": len(items), "due": due, "new": new, "learned": learned,
        "avg_interval": round(sum(intervals) / len(intervals), 2) if intervals else 0,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_export_anki(args) -> int:
    items = load_items(Path(args.items))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Front", "Back", "Tags", "Source"])
        for item in items:
            writer.writerow([
                item["front"], item["back"], " ".join(item.get("tags") or []),
                item.get("source_page") or item.get("origin", ""),
            ])
    print(f"✅ Anki CSV：{len(items)} 行 → {out}")
    return 0


def cmd_simulate(args) -> int:
    items = load_items(Path(args.items))
    state = init_state(items, None, date.fromisoformat(args.start) if args.start else date.today())
    start = date.fromisoformat(args.start) if args.start else date.today()
    exposures = defaultdict(int)
    for day in range(args.days):
        today = start + timedelta(days=day)
        due = []
        for item in items:
            st = state["items"][item["item_id"]]
            if st["due"] <= today.isoformat():
                due.append((st.get("reps", 0) > 0, st["due"], item["item_id"]))
        due.sort()
        for _, _, item_id in due[: args.daily]:
            state["items"][item_id] = sm2_update(state["items"][item_id], 2, today)
            exposures[item_id] += 1
    once = sum(1 for i in items if exposures[i["item_id"]] >= 1)
    twice = sum(1 for i in items if exposures[i["item_id"]] >= 2)
    print(json.dumps({
        "days": args.days, "daily": args.daily, "total": len(items),
        "exposed_once": once, "exposed_twice": twice,
    }, ensure_ascii=False, indent=2))
    return 0

def main() -> int:
    _configure_stdio()
    ap = argparse.ArgumentParser(description="M3 复习卡片与 SM-2 调度")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--review", default=str(DEFAULT_REVIEW))
    b.add_argument("--keypoints", default=str(DEFAULT_KEYPOINTS))
    b.add_argument("--out", default=str(DEFAULT_OUT))
    b.add_argument("--state", default=str(DEFAULT_STATE))
    b.add_argument("--reset-state", action="store_true")

    s = sub.add_parser("schedule")
    s.add_argument("--items", default=str(DEFAULT_ITEMS))
    s.add_argument("--state", default=str(DEFAULT_STATE))
    s.add_argument("--date", default="")
    s.add_argument("--limit", type=int, default=20)

    g = sub.add_parser("grade")
    g.add_argument("--items", default=str(DEFAULT_ITEMS))
    g.add_argument("--state", default=str(DEFAULT_STATE))
    g.add_argument("--item", required=True)
    g.add_argument("--rating", type=int, choices=[0, 1, 2, 3], required=True)
    g.add_argument("--date", default="")

    st = sub.add_parser("stats")
    st.add_argument("--items", default=str(DEFAULT_ITEMS))
    st.add_argument("--state", default=str(DEFAULT_STATE))
    st.add_argument("--date", default="")

    a = sub.add_parser("export-anki")
    a.add_argument("--items", default=str(DEFAULT_ITEMS))
    a.add_argument("--out", default=str(DEFAULT_OUT / "anki_ent_pilot.csv"))

    sim = sub.add_parser("simulate")
    sim.add_argument("--items", default=str(DEFAULT_ITEMS))
    sim.add_argument("--days", type=int, default=14)
    sim.add_argument("--daily", type=int, default=30)
    sim.add_argument("--start", default="")

    args = ap.parse_args()
    return {
        "build": cmd_build, "schedule": cmd_schedule, "grade": cmd_grade,
        "stats": cmd_stats, "export-anki": cmd_export_anki, "simulate": cmd_simulate,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
