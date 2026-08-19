# -*- coding: utf-8 -*-
"""Merge batch027 module JSON parts into ALL_questions.json (pure JSON array)."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(r"C:\Users\38063\Desktop\MedAgentWork\中间产物\batch027")
MODULES = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"]

all_q = []
for m in MODULES:
    p = BASE / f"{m}.json"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit(f"{p} is not a JSON array")
    all_q.extend(data)

out = BASE / "ALL_questions.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(all_q, f, ensure_ascii=False, indent=2)

# quick stats
from collections import Counter
types = Counter(q["type"] for q in all_q)
blooms = Counter(q["bloom"] for q in all_q)
modules = Counter(q["module"] for q in all_q)
neg = sum(1 for q in all_q if q.get("polarity") == "negative")
ids = [q["id"] for q in all_q]
print(f"TOTAL: {len(all_q)}")
print(f"types: {dict(types)}")
print(f"blooms: {dict(blooms)}")
print(f"modules: {dict(modules)}")
print(f"negative: {neg}")
print(f"dup ids: {len(ids) - len(set(ids))}")
print(f"written: {out}")
