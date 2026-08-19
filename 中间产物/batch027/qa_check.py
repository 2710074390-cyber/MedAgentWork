# -*- coding: utf-8 -*-
"""Final QA: schema completeness + dedup vs batch014."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

NEW = Path(r"C:\Users\38063\Desktop\MedAgentWork\中间产物\batch027\ALL_questions.json")
OLD = Path(r"C:\Users\38063\Desktop\MedAgentWork\archive\中间产物\batch014\ALL_questions_batch014_呼吸.json")

with open(NEW, encoding="utf-8") as f:
    new = json.load(f)
with open(OLD, encoding="utf-8") as f:
    old = json.load(f)

# 1) schema completeness
REQUIRED = ["id", "module", "module_name", "topic", "type", "polarity", "bloom",
            "stem", "options", "answer", "explanation", "source_page", "difficulty",
            "option_polarities"]
missing = []
for q in new:
    for k in REQUIRED:
        if k not in q or q[k] in (None, ""):
            missing.append((q.get("id"), k))
print("schema missing:", missing if missing else "NONE")

# options: 5 options, labels A-E, option_polarities keys match
opt_issues = []
for q in new:
    labels = [o["label"] for o in q["options"]]
    if labels != ["A", "B", "C", "D", "E"]:
        opt_issues.append((q["id"], "labels", labels))
    if q["type"] != "X" and len(q["options"]) != 5:
        opt_issues.append((q["id"], "count", len(q["options"])))
    if set(q["option_polarities"].keys()) != {"A", "B", "C", "D", "E"}:
        opt_issues.append((q["id"], "polarity_keys", list(q["option_polarities"].keys())))
print("option issues:", opt_issues if opt_issues else "NONE")

# answer validity vs option_polarities
ans_issues = []
for q in new:
    correct = {k for k, v in q["option_polarities"].items() if v}
    if q["type"] == "X":
        expect = set(q["answer"])
        if expect != correct:
            ans_issues.append((q["id"], q["answer"], sorted(correct)))
    else:
        if len(q["answer"]) != 1 or q["answer"] not in correct:
            ans_issues.append((q["id"], q["answer"], sorted(correct)))
print("answer issues:", ans_issues if ans_issues else "NONE")

# A3 id pattern
import re
a3 = [q["id"] for q in new if q["type"] == "A3"]
print("A3 ids:", a3)
bad_a3 = [i for i in a3 if not re.fullmatch(r"batch027-M\d-A3-\d{3}[abc]", i)]
print("A3 pattern issues:", bad_a3 if bad_a3 else "NONE")

# 2) dedup vs batch014: stem equality / option-set equality / stem similarity
old_stems = set(q.get("stem", "") for q in old)
old_opt_sets = set()
for q in old:
    txts = tuple(sorted(o.get("text", "") for o in q.get("options", []) if isinstance(o, dict)))
    old_opt_sets.add(txts)

exact_stem = [q["id"] for q in new if q["stem"] in old_stems]
print("exact stem dup:", exact_stem if exact_stem else "NONE")

def norm(s):
    return set(s.replace("？", "").replace("?", "").replace("，", "").replace(",", "").split())

sim_hits = []
for q in new:
    ns = norm(q["stem"])
    if len(ns) < 3:
        continue
    for oq in old:
        no = norm(oq.get("stem", ""))
        if not no:
            continue
        inter = len(ns & no) / len(ns | no)
        if inter >= 0.7:
            sim_hits.append((q["id"], round(inter, 2), q["stem"][:30], oq.get("stem", "")[:30]))
print("stem similarity >=0.7:", sim_hits if sim_hits else "NONE")

# option set overlap
new_opt_sets = set()
for q in new:
    txts = tuple(sorted(o.get("text", "") for o in q.get("options", [])))
    new_opt_sets.add(txts)
shared_opt_sets = new_opt_sets & old_opt_sets
print("shared identical option-sets:", len(shared_opt_sets), "->", list(shared_opt_sets)[:5])

# 3) source_page distribution (S3 safeguard)
from collections import Counter
pages = Counter()
for q in new:
    m = re.search(r"P(\d{2,4})", q.get("source_page", ""))
    if m:
        pages[m.group(1)] += 1
top = pages.most_common(3)
print("top source pages:", top, "| max ratio:", round(top[0][1] / len(new), 2) if top else 0)
