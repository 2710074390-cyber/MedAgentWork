#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BPA v1.0 结构自检：模块区块、卡片字段、自测数量、附录五件套。"""
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
MD = ROOT / "Obsidian产物/教师重点蓝图版/耳鼻咽喉头颈外科学_教师重点蓝图版_主复习资料.md"
t = MD.read_text(encoding="utf-8")
lines = t.splitlines()

# 模块切分
mods = []
cur = None
for l in lines:
    m = re.match(r"^## 模块(\d+)：(.+)$", l)
    if m:
        cur = {"no": m.group(1), "name": m.group(2), "start": lines.index(l), "lines": []}
        mods.append(cur)
    elif cur is not None and l.startswith("## 附录"):
        cur = None
    if cur:
        cur["lines"].append(l)

print(f"模块数：{len(mods)}")
blocks = ["🧩 前置知识检查", "🎯 30 秒摘要", "📋 考点卡", "📊 对比速查", "🔗 因果链", "🌳 决策树", "📌 一页纸", "🔄 主动回忆"]
for m in mods:
    body = "\n".join(m["lines"])
    miss = [b for b in blocks if b not in body]
    cards = re.findall(r"^#### (🔴|🟡|🟢) (K-M\d\d-\d+)｜(.+)$", body, re.M)
    fields = {"锚点": "📌 重点原文", "题眼": "🎯 一句话题眼", "为什么": "🧬 为什么", "鉴别": "⚖️ 鉴别",
              "红线": "🚨 红线", "下一步": "🩺 下一步", "自测": "🔄 自测"}
    # 按卡片切段统计字段
    parts = re.split(r"^#### (?:🔴|🟡|🟢) K-M\d\d-\d+｜.*$", body, flags=re.M)[1:]
    fcount = {k: 0 for k in fields}
    for p in parts:
        for k, token in fields.items():
            if token in p:
                fcount[k] += 1
    n_ret = len(re.findall(r"^\d+\. ", body, re.M))
    print(f"  M{m['no']} {m['name'][:14]:<16} 卡{len(cards):>2} 区块缺{miss or '无'} 题{n_ret:>2} "
          f"字段{ {k: f'{v}/{len(parts)}' for k, v in fcount.items() if v < len(parts)} or '全'}")

# 附录
apps = re.findall(r"^## 附录([一二三四五])：(.+)$", t, re.M)
print("附录：", [(a, b) for a, b in apps])
print("卡片总数：", len(re.findall(r"^#### (?:🔴|🟡|🟢) K-M", t, re.M)))
print("锚点总数：", len(re.findall(r"^📌 重点原文（第", t, re.M)))
print("锚点覆盖条号数：", len(set(int(x) for x in re.findall(r"^📌 重点原文（第(\d+)条）", t, re.M))))
