#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_concept_cards.py — 把 KC 节点落成 Obsidian 概念卡笔记（W5）。

为什么要有实体笔记
    K-ID 原本只是主复习资料里的 #### 标题，写成 [[K-M01-001]] 必然是死链。
    只有存在独立笔记，Obsidian 才会生成图谱节点与反链面板。
    本脚本生成的是**索引卡**（标题 + 记忆钩子 + 前置/后继 + 关联题号 + 回链），
    不复制卡片正文，正文仍以主复习资料为唯一来源（铁律④ 无副本）。

产物
    Obsidian产物/概念卡/{学科}/ {学科}-K-Mxx-xxx.md    每卡一篇
    Obsidian产物/概念索引/{学科}_概念卡索引.md           48 行表格
    _MOC/{学科}.md                                      末尾追加「概念卡」区块（幂等）

用法
    python scripts/build_concept_cards.py --subject 急诊
    python scripts/build_concept_cards.py --subject 急诊 --dry-run
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

def _configure_stdio() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


BASE = Path(__file__).resolve().parent.parent
DEFAULT_GRAPH = BASE / "question_bank/concept_graph.json"
CARD_DIR = BASE / "Obsidian产物/概念卡"
INDEX_DIR = BASE / "Obsidian产物/概念索引"

CARD_HEAD_RE = re.compile(r"^#{3,4}\s*\S*\s*(K-M\d{2}-\d{3})\s*[｜|]\s*(.+?)\s*(?:（(.*)）)?\s*$")
HOOK_LABELS = ("💡 记忆钩子", "🎯 一句话题眼")
TAG_RE = re.compile(r"<[^>]+>")
MOC_BLOCK_START = "## 概念卡"


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def strip_tags(s: str) -> str:
    return TAG_RE.sub("", s).strip()


def parse_review_cards(review: Path) -> dict[str, dict]:
    """从主复习资料抽出卡片块：display_id -> {title, meta, body, hook, line}"""
    cards: dict[str, dict] = {}
    cur = None
    buf: list[str] = []
    for i, line in enumerate(review.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        m = CARD_HEAD_RE.match(line)
        if m:
            if cur:
                cur["body"] = "\n".join(buf).strip()
                cards[cur["display_id"]] = cur
            cur = {"display_id": m.group(1), "title": m.group(2).strip(),
                   "meta": (m.group(3) or "").strip(), "line": i,
                   "heading_full": line.lstrip("#").strip()}
            buf = []
            continue
        if line.startswith("###") and not line.startswith("####"):
            if cur:
                cur["body"] = "\n".join(buf).strip()
                cards[cur["display_id"]] = cur
                cur, buf = None, []
            continue
        if cur is not None:
            buf.append(line)
    if cur:
        cur["body"] = "\n".join(buf).strip()
        cards[cur["display_id"]] = cur

    for c in cards.values():
        c["hook"] = ""
        for line in c["body"].splitlines():
            plain = strip_tags(line)
            for lab in HOOK_LABELS:
                if plain.startswith(lab) or plain.lstrip().startswith(lab):
                    c["hook"] = plain.split("：", 1)[-1].strip() if "：" in plain else plain[len(lab):].strip()
                    break
            if c["hook"]:
                break
    return cards


def resolve_review(graph: dict, subject: str) -> Path | None:
    for n in graph["nodes"]:
        if n["subject"] == subject:
            reg = BASE / n["registry"]
            if reg.exists():
                meta = read_json(reg).get("metadata") or {}
                rp = str(meta.get("review_path") or "").replace("\\", "/")
                if rp:
                    p = BASE / rp
                    if p.exists():
                        return p
            break
    return None


def fmt_list(xs) -> str:
    return "[" + ", ".join(str(x) for x in xs) + "]"


def build_note(node: dict, card: dict, children: list[str], refs: list[str],
               subject: str, index_stem: str, review_stem: str, moc_stem: str) -> str:
    link = lambda kc: f"[[{kc.split(':')[0]}-{kc.split(':')[-1]}|{kc.split(':')[-1]}]]"
    kps = "、".join(f"第{k}条" for k in node["keypoints"]) or "—"
    pages = "、".join(f"P{p}" for p in node["source_pages"]) or "—"
    prereq = node["prereq"]
    prereq_txt = "、".join(link(x) for x in prereq) if prereq else "无（模块起点）"
    child_txt = "、".join(link(x) for x in children) if children else "—"
    ref_txt = "、".join(link(x) for x in refs) if refs else "—"
    qs = node["questions"]
    q_txt = "\n".join(f"- `{q}`" for q in qs) if qs else "- （暂无主概念题）"

    return f"""---
title: "{node['display_id']} {node['title']}"
kc_id: {node['kc_id']}
subject: {node['subject']}
module: {node['module']}
keypoints: {fmt_list(node['keypoints'])}
source_pages: {fmt_list(node['source_pages'])}
weight: {node['weight']}
status: {node['status']}
tags: [概念卡, {subject}]
---

# {node['display_id']} {node['title']}

> 模块 {node['module']}｜教师重点{kps}｜教材{pages}｜关联 {node['weight']} 题

**💡 记忆钩子**：{card.get('hook') or '（主资料未提供，回看卡片正文）'}

**⬅️ 前置**：{prereq_txt}
**➡️ 后继**：{child_txt}
**🔗 同页/同锚点关联**：{ref_txt}

**📝 关联题目**（{len(qs)}）：
{q_txt}

**📖 正文**：{f"[[{review_stem}#{card['heading_full']}|回主复习资料对应卡片]]" if card.get('heading_full') else review_stem}（第 {card.get('line', '?')} 行附近）

---
🔙 [[{index_stem}|概念卡索引]]　·　[[_MOC/{moc_stem}|{moc_stem} 学科图谱]]
"""


def resolve_moc(subject: str) -> Path | None:
    """学科名可能是简写（急诊），MOC 文件名是全称（急诊与灾难医学），以文件为准。"""
    exact = BASE / f"_MOC/{subject}.md"
    if exact.exists():
        return exact
    hits = sorted((BASE / "_MOC").glob(f"{subject}*.md"))
    return hits[0] if hits else None


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 Obsidian 概念卡")
    ap.add_argument("--graph", default=str(DEFAULT_GRAPH))
    ap.add_argument("--subject", default="急诊")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    graph = read_json(Path(args.graph))
    subject = args.subject
    nodes = [n for n in graph["nodes"] if n["subject"] == subject]
    if not nodes:
        print(f"ERROR —— 图中没有学科 {subject}")
        return 2

    review = resolve_review(graph, subject)
    if not review:
        print("ERROR —— 找不到该学科的主复习资料（registry.metadata.review_path）")
        return 2
    cards = parse_review_cards(review)
    print(f"主资料 {review.relative_to(BASE)}　抽到卡片 {len(cards)} 张")

    by_id = {n["kc_id"]: n for n in nodes}
    children: dict[str, list[str]] = {k: [] for k in by_id}
    for n in nodes:
        for p in n["prereq"]:
            if p in children:
                children[p].append(n["kc_id"])
    ref_adj: dict[str, list[str]] = {k: [] for k in by_id}
    for e in graph["edges"]["ref"]:
        if e["from"] in ref_adj:
            ref_adj[e["from"]].append(e["to"])
        if e["to"] in ref_adj:
            ref_adj[e["to"]].append(e["from"])

    moc = resolve_moc(subject)
    if not moc:
        print(f"ERROR —— 找不到 _MOC/{subject}*.md")
        return 2
    folder_name = moc.stem
    index_stem = f"{folder_name}_概念卡索引"

    out_dir = CARD_DIR / folder_name
    missing = [n["display_id"] for n in nodes if n["display_id"] not in cards]

    written = 0
    for n in sorted(nodes, key=lambda x: x["display_id"]):
        card = cards.get(n["display_id"], {})
        text = build_note(n, card, children.get(n["kc_id"], []), ref_adj.get(n["kc_id"], []),
                          subject, index_stem, review.stem, folder_name)
        path = out_dir / f"{subject}-{n['display_id']}.md"
        if not args.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        written += 1

    # 索引页
    rows = ["| K-ID | 标题 | 模块 | 题数 | 教师重点 | 教材页 | 前置 |",
            "|---|---|---|---|---|---|---|"]
    for n in sorted(nodes, key=lambda x: x["display_id"]):
        kps = "、".join(str(k) for k in n["keypoints"]) or "—"
        pages = "、".join(str(p) for p in n["source_pages"]) or "—"
        pre = "、".join(x.split(":")[-1] for x in n["prereq"]) or "—"
        rows.append(f"| [[{subject}-{n['display_id']}\\|{n['display_id']}]] | {n['title']} | "
                    f"{n['module']} | {n['weight']} | {kps} | {pages} | {pre} |")
    total_q = sum(n["weight"] for n in nodes)
    index = f"""---
title: "{subject} · 概念卡索引"
tags: [概念索引, {subject}]
---

# {subject} · 概念卡索引

> {len(nodes)} 张概念卡，覆盖 {total_q} 道主概念题。K-ID 与题库 `keypoint_ref`、主复习资料卡片标题一一对应。
> 生成脚本：`scripts/build_concept_cards.py`（重跑会覆盖，不要手改表格）

## 怎么用

- 想看某个概念被哪些题考过 → 点 K-ID，进卡片看「关联题目」
- 想按学习顺序读 → 看「前置」列，从 `—` 的卡开始
- 想知道哪里薄弱 → 待 P1 学习器接入后，本页会显示掌握度热力

{chr(10).join(rows)}

---
🔙 [[{review.stem}|主复习资料]]　·　[[_MOC/{folder_name}|{folder_name} 学科图谱]]
"""
    index_path = INDEX_DIR / f"{index_stem}.md"
    if not args.dry_run:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(index, encoding="utf-8")

    # MOC 回链（幂等）
    if not args.dry_run:
        text = moc.read_text(encoding="utf-8")
        block = (f"\n{MOC_BLOCK_START}\n\n"
                 f"- [[{index_stem}|概念卡索引（{len(nodes)} 张）]]\n"
                 f"- 每张卡含：记忆钩子 · 前置/后继 · 关联题号 · 回主资料\n")
        text = re.sub(rf"\n{MOC_BLOCK_START}[\s\S]*?(?=\n## |\n---|\Z)", "", text)
        text = text.replace("\n---\n🔙", f"{block}\n---\n🔙") if "\n---\n🔙" in text else text + block
        moc.write_text(text, encoding="utf-8")

    print(f"写出概念卡 {written} 张 → {out_dir}")
    print(f"索引页 → {index_path}")
    print(f"MOC 回链 → {moc}")
    if missing:
        print(f"WARN —— {len(missing)} 张卡在主资料里找不到标题：{missing[:5]}")
    return 0


if __name__ == "__main__":
    _configure_stdio()
    raise SystemExit(main())
