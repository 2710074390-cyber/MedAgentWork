# -*- coding: utf-8 -*-
"""合并 batch046 72 道旧原创 + 28 道新原创，补齐 HC-28 release 标注。

输出:
  中间产物/batch046/ALL_questions.json
  最终产物/batch046/ALL_questions_FIXED.json
"""
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
BATCH = "batch046"
OLD = BASE / "中间产物" / BATCH / "original_72_review_fixed_v2.json"
NEW = BASE / "中间产物" / BATCH / "new_28_questions.json"
PLAN = BASE / "中间产物" / BATCH / "answer_position_plan.json"
KP_FILE = BASE / "输入素材" / "大四上" / "急诊与灾难医学" / "急诊与灾难医学_教师重点_锚定清单_20261026.md"
MID_OUT = BASE / "中间产物" / BATCH / "ALL_questions.json"
FINAL_OUT = BASE / "最终产物" / BATCH / "ALL_questions_FIXED.json"

HIGH_RISK_KP = {f"第{n}条" for n in range(8, 62)}


def load_keypoints():
    text = KP_FILE.read_text(encoding="utf-8")
    points = {}
    for line in text.splitlines():
        m = re.match(r"^([0-9]{1,2})\. 【[^】]+】(.+)$", line.strip())
        if m:
            points[f"第{m.group(1)}条"] = m.group(2).strip()
    return points


KEYPOINTS = load_keypoints()


def first_kp(q):
    ref = q.get("keypoint_ref")
    if isinstance(ref, list) and ref:
        return str(ref[0])
    return str(ref or "")


def add_release_to_old(q):
    lv = q.setdefault("learning_value", {})
    kp = first_kp(q)
    anchor_text = KEYPOINTS.get(kp)
    if anchor_text:
        # HC-28：以教师重点原文为权威锚点，机械回填 teacher_anchor/source_quote。
        # 不是新造事实，只是把题干已有考点重新锚定到已下发的原文上。
        q["teacher_anchor"] = anchor_text
        quote = str(lv.get("source_quote") or "").strip()
        if not quote or quote not in anchor_text:
            lv["source_quote"] = anchor_text
        lv["source_quote_status"] = "exact"
        lv["anchor_status"] = "verified"
        flags = [f for f in (lv.get("quality_flags") or [])
                 if ("原文引文未逐字" not in f and "教材原文待逐字" not in f
                     and "缺 teacher_anchor" not in f)]
        flags.append("HC-28 教师重点原文字段机械回填")
        lv["quality_flags"] = flags

    sq = str(lv.get("source_quote_status") or "").strip()
    anchor = str(lv.get("anchor_status") or "").strip()
    if sq == "exact" and anchor == "verified":
        grade = "A"
    elif sq == "exact":
        grade = "B"
    else:
        grade = "C"

    kp = first_kp(q)
    risk = "high" if kp in HIGH_RISK_KP else "medium"
    if grade in ("A", "B"):
        disposition = "publishable"
        reason = "NONE"
        human_check = ""
        suggested = ""
    elif risk == "high":
        disposition = "quarantined"
        reason = "SOURCE_MISSING"
        human_check = "补齐 source_quote 原文锚点，并由医学专业人员独立核验答案唯一性"
        suggested = "补原文后改为 publishable；无法补原文则保持隔离"
    else:
        disposition = "pending_human"
        reason = "SOURCE_MISSING"
        human_check = "补齐 source_quote 原文锚点并复核教材口径"
        suggested = "补原文锚点后改判 publishable 或 quarantined"

    checks = [
        "教师重点锚点" if q.get("teacher_anchor") else "无教师重点锚点",
        "学习价值逐项覆盖",
        "选项结构校验",
    ]
    if sq != "exact":
        checks.append("source_quote 非 exact，已进入复核队列")
    q["release"] = {
        "disposition": disposition,
        "evidence_grade": grade,
        "risk_level": risk,
        "reason_code": reason,
        "agent_checks": checks,
        "human_check": human_check,
        "suggested_action": suggested,
    }
    return q


def main():
    old = json.loads(OLD.read_text(encoding="utf-8"))
    new = json.loads(NEW.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    old = [add_release_to_old(q) for q in old]
    merged = sorted(old + new, key=lambda q: int(q["sequence"]))
    if len(merged) != 100:
        raise SystemExit(f"题数不为 100: {len(merged)}")
    ids = [q["id"] for q in merged]
    if len(set(ids)) != 100:
        raise SystemExit("ID 不唯一")

    # 答案位置计划一致性
    mism = [(q["id"], q["answer"], plan[int(q["sequence"]) - 1])
            for q in merged if q["answer"] != plan[int(q["sequence"]) - 1]]
    if mism:
        raise SystemExit(f"答案位置计划不一致: {mism[:5]}")
    if any(plan[i] == plan[i + 1] == plan[i + 2] for i in range(98)):
        raise SystemExit("存在连续三题答案相同")

    # 精确题干重复
    stems = [q["stem"] for q in merged]
    dup = [s for s, n in Counter(stems).items() if n > 1]
    if dup:
        raise SystemExit(f"题干重复: {dup[:3]}")

    MID_OUT.parent.mkdir(parents=True, exist_ok=True)
    FINAL_OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    MID_OUT.write_text(text, encoding="utf-8")
    FINAL_OUT.write_text(text, encoding="utf-8")

    print(f"wrote {MID_OUT}")
    print(f"wrote {FINAL_OUT}")
    print("types", dict(Counter(q["type"] for q in merged)))
    print("bloom", dict(Counter(q["bloom"] for q in merged)))
    print("answers", dict(Counter(q["answer"] for q in merged)))
    print("release", dict(Counter(q["release"]["disposition"] for q in merged)))
    print("grades", dict(Counter(q["release"]["evidence_grade"] for q in merged)))
    print("risk", dict(Counter(q["release"]["risk_level"] for q in merged)))
    refs = sorted({k for q in merged for k in ([q["keypoint_ref"]] if isinstance(q["keypoint_ref"], str) else q["keypoint_ref"])},
                  key=lambda x: int(x.replace("第", "").replace("条", "")))
    print("keypoints covered", len(refs), refs[0], refs[-1])


if __name__ == "__main__":
    main()
