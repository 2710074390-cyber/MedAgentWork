#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析教师重点锚定清单第四节，输出 125 条账本 + 短锚点清单。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "输入素材/大四上/耳鼻咽喉头颈外科学/耳鼻咽喉头颈外科学_教师重点_锚定清单_20261019.md"
OUT = Path(__file__).resolve().parent

text = SRC.read_text(encoding="utf-8", errors="replace")
# 取第四节到第五节之间
start = text.index("## 四、统一锚定清单")
end = text.index("## 五、原始标号对照")
body = text[start:end]

pat = re.compile(r"^(\d+)\.\s*【([^】]+)】(.+?)〔([^〕]+)〕\s*$", re.M)
items = []
for m in pat.finditer(body):
    num = int(m.group(1))
    src_tag = m.group(2)
    verbatim = m.group(3).strip()
    origin = m.group(4)
    items.append({
        "source_id": num,
        "src": src_tag,
        "verbatim": verbatim,
        "origin_label": origin,
        "chars": len(verbatim),
    })

print(f"解析条目数：{len(items)}")
short = [it for it in items if it["chars"] < 60]
print(f"不足 60 字：{len(short)}")
for it in short:
    print(f"  第{it['source_id']}条（{it['chars']}字）：{it['verbatim'][:50]}")
missing = [n for n in range(1, 126) if n not in {i["source_id"] for i in items}]
print("缺号：", missing)
(OUT / "keypoints_raw.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
