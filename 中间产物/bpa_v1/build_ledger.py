#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从交付 MD 反查生成 keypoint ledger（source_id → 卡片/行号/锚点文本）。"""
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
MD = ROOT / "Obsidian产物/教师重点蓝图版/耳鼻咽喉头颈外科学_教师重点蓝图版_主复习资料.md"
KP = ROOT / "输入素材/大四上/耳鼻咽喉头颈外科学/耳鼻咽喉头颈外科学_教师重点_锚定清单_20261019.md"
OUT = Path(__file__).resolve().parent / "keypoint_ledger.jsonl"

raw = KP.read_text(encoding="utf-8")
start, end = raw.index("## 四、统一锚定清单"), raw.index("## 五、原始标号对照")
src = {}
for m in re.finditer(r"^(\d+)\.\s*【([^】]+)】(.+?)〔([^〕]+)〕\s*$", raw[start:end], re.M):
    src[int(m.group(1))] = {"verbatim": m.group(3).strip(), "origin": m.group(4), "src": m.group(2)}

lines = MD.read_text(encoding="utf-8").splitlines()
cur_mod = cur_card = cur_title = ""
rows = []
for i, ln in enumerate(lines, 1):
    m = re.match(r"^## 模块(\d+)：(.+)$", ln)
    if m:
        cur_mod = f"M{m.group(1).zfill(2)}"
    m = re.match(r"^#### (🔴|🟡|🟢) (K-M\d\d-\d+)｜(.+)$", ln)
    if m:
        cur_card, cur_title = m.group(2), m.group(3)
    m = re.match(r"^📌 重点原文（第(\d+)条）：(.+)$", ln)
    if m:
        sid = int(m.group(1))
        anchor = m.group(2)
        verbatim = src.get(sid, {}).get("verbatim", "")
        rows.append({
            "kid": cur_card,
            "source_id": sid,
            "source_origin": src.get(sid, {}).get("origin", ""),
            "module": cur_mod,
            "verbatim": verbatim,
            "anchor_line": i,
            "anchor_text": "📌 重点原文（第%d条）：%s" % (sid, anchor),
            "anchor_chars": len(anchor),
            "anchor_self_contained": len(anchor) >= 60,
            "status": "covered_full",
            "date": "2026-10-22",
        })

with OUT.open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

covered = {r["source_id"] for r in rows}
print(f"ledger 行数：{len(rows)}｜覆盖条号：{len(covered)}/125｜缺号：{sorted(set(range(1,126))-covered)}")
short = [r for r in rows if r["anchor_chars"] < 60]
print(f"锚点 <60 字：{len(short)} 条")
for r in short:
    print(f"  第{r['source_id']}条 ({r['anchor_chars']}字) {r['kid']}: {r['anchor_text'][:60]}")
print("输出：", OUT)
