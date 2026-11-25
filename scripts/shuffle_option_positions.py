#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""shuffle_option_positions.py — 把答案位置打散到「均衡且不周期」，只换位置不改字。

为什么需要它
────────────
答案位置有两个彼此独立的缺陷，历史上各踩过一次：

1. **偏好**：作者习惯把正确项写在前面 → 多选 16/18 题答案是 ABCD，E 从不作答案。
   X1 只看字母总量，看不出来（总量可以很均匀）。
2. **轮转**：为了「修」偏好，装配器用 `A→B→C→D→E` 按题号循环派答案 → 总量完美，
   但第 1、6、11 题永远是 A（X10 实测一致率 99.5%）；判断 ABAB 交替同理。

两种都是**位置泄漏**：学生数题号就能答对。正确做法不是「按规则派」，而是
「位置与题号无关、总量仍然均衡」——本脚本用「带配额约束的随机分配」实现：
先算每个字母还差多少配额（把不能动的题算进去），再按配额随机挑位置。

它做什么 / 不做什么
──────────────────
· **只重排选项**并重算 `answer` 与所有按 label 索引的字段（`option_polarities`、
  `learning_value.per_option[].label`）。**一个字都不改**——batch049 的
  `等临床情况需鉴别` 就是「为了指标去改字」的教训。
· 跳过顺序本身有含义的题：数值型（须升/降序）、含流程/时间序词、判断题
  （A/B 是「正确/错误」，换位即改答案）、B1 配伍组与共用题干组。
· **不能**修正内容层面的缺陷：多选正确项个数恒定（恒 4 项）、判断题真值与题号交替。
  这两条只能改内容（多写 2/3 项正确的题、写一半错误陈述）；脚本会在报告里点名。

用法
────
  python scripts/shuffle_option_positions.py --file <JSON> --check      # 只看现状
  python scripts/shuffle_option_positions.py --file <JSON> --out x.json # 写新文件
  python scripts/shuffle_option_positions.py --file <JSON> --in-place   # 原地改

退出码：`--check` 下 X1 或 X10 的「非内容项」有违例 → 1；写入模式恒 0（除非解析失败）。
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
for p in (BASE, BASE / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from validate.rules_batch import (  # noqa: E402
        answer as _answer,
        options as _options,
        check_answer_distribution,
        check_answer_position_periodicity,
        check_multi_answer_distribution,
        thresholds,
    )
except Exception:  # pragma: no cover
    from scripts.validate.rules_batch import (  # type: ignore
        answer as _answer,
        options as _options,
        check_answer_distribution,
        check_answer_position_periodicity,
        check_multi_answer_distribution,
        thresholds,
    )

LETTERS = "ABCDE"
DEFAULT_SEED = 20261125
MAX_TRIES = 60

# 顺序有含义的题：换位置会让「升序 / 流程 / 时间」失效或改变语义
ORDERED_WORDS = re.compile(
    r"(首先|其次|然后|随后|最后|立即|第一步|第二步|第三步|早期|中期|晚期|"
    r"急性期|慢性期|前期|后期|序贯|先.*再.*|待.*后)"
)
NUMERIC_OPT = re.compile(r"^\s*[<>≤≥约]?\s*\d+(?:[.,]\d+)?\s*[^\d\s]{0,6}\s*$")


# ── 读写 ────────────────────────────────────────────────────

def load_items(path: str | Path) -> tuple[list[dict], dict | None, Path]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for k in ("questions", "items", "data"):
            if isinstance(data.get(k), list):
                return data[k], data, p
        raise SystemExit(f"[FAIL] {path} 是对象但没有 questions/items/data 数组")
    if not isinstance(data, list):
        raise SystemExit(f"[FAIL] {path} 不是数组也不是带 questions 的对象")
    return data, None, p


def save_items(items: list[dict], wrapper: dict | None, out: Path) -> None:
    if wrapper is None:
        payload: object = items
    else:
        payload = dict(wrapper)
        for k in ("questions", "items", "data"):
            if isinstance(wrapper.get(k), list):
                payload[k] = items
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


# ── 可动性判定 ──────────────────────────────────────────────

def is_ordered(q: dict) -> tuple[bool, str]:
    if str(q.get("type") or "") in ("判断", "B1"):
        return True, f"type={q.get('type')}（换位即改语义）"
    if q.get("case_group") or q.get("group_id"):
        return True, "共用题干组"
    opts = _options(q)
    texts = list(opts.values())
    if len(texts) < 3:
        return True, "选项不足 3 个"
    if sum(1 for t in texts if NUMERIC_OPT.match(t)) >= len(texts) - 1:
        return True, "数值型（须升/降序）"
    if any(ORDERED_WORDS.search(t) for t in texts):
        return True, "含流程/时间序词"
    if any(re.search(r"(以上.*都|均是|都不是|全部正确)", t) for t in texts):
        return True, "含集总项"
    return False, ""


# ── 配额分配 ────────────────────────────────────────────────

def allocate(work: list[dict], rnd: random.Random) -> dict[str, list[str]]:
    """给每道可动题分配「正确项应落在哪几个字母」，同时保住总量均衡。

    先算不可动题已经占掉多少，再把剩余配额按缺口随机分配——这样既不会像
    `i % 5` 那样与题号相关，也不会因为纯随机把某个字母压到 10% 以下。
    """
    plan: dict[str, list[str]] = {}
    fixed_single: Counter = Counter()
    fixed_multi: Counter = Counter()
    movable_single: list[str] = []
    movable_multi: list[tuple[str, int]] = []

    for i, q in enumerate(work):
        opts = _options(q)
        ans = [l for l in _answer(q) if l in opts]
        if not ans or len(opts) < 3:
            continue
        key = str(q.get("question_id") or q.get("id") or f"#{i}")
        ordered, _why = is_ordered(q)
        if ordered:
            (fixed_single if len(ans) == 1 else fixed_multi).update(ans)
        elif len(ans) == 1:
            movable_single.append(key)
        else:
            movable_multi.append((key, len(ans)))

    n_single = sum(fixed_single.values()) + len(movable_single)
    n_multi = sum(fixed_multi.values()) + sum(k for _k, k in movable_multi)

    # 单选：按缺口挑字母
    quota = {l: n_single / len(LETTERS) - fixed_single.get(l, 0) for l in LETTERS}
    rnd.shuffle(movable_single)
    for key in movable_single:
        pool = [l for l in LETTERS if quota[l] > 0] or list(LETTERS)
        pick = max(pool, key=lambda l: (quota[l], rnd.random()))
        plan[key] = [pick]
        quota[pick] -= 1

    # 多选：按「正确项出现次数」的缺口挑 k 个字母
    quota_m = {l: n_multi / len(LETTERS) - fixed_multi.get(l, 0) for l in LETTERS}
    rnd.shuffle(movable_multi)
    for key, k in movable_multi:
        order = sorted(LETTERS, key=lambda l: (-quota_m[l], rnd.random()))
        pick = sorted(order[:k])
        prefix = list(LETTERS[:k])
        if pick == prefix and rnd.random() < 0.7:
            alt = [l for l in LETTERS if l not in pick]
            swap_out = rnd.choice(pick)
            swap_in = rnd.choice(alt)
            pick = sorted([l for l in pick if l != swap_out] + [swap_in])
        plan[key] = pick
        for l in pick:
            quota_m[l] -= 1
    return plan


# ── 解析里的字母引用 ────────────────────────────────────────
#
# 这是本工具最容易出事的地方：选项换了位置，`explanation` 里「A：…」「B：…」这些
# 逐选项行如果不跟着改，解析就会整体错位——而且**不会报错**（机器读的是 answer，
# 人读的是解析，两边不一致只在人看的时候才暴露）。
# 所以重排必须同时做两件事：改标号 + 按新标号重排行顺序。

LINE_LABEL = re.compile(r"^([ \t]*)([A-E])([ \t]*[：:.、][ \t]*)(.*)$")
INLINE_OPTION = re.compile(r"选项[ \t]*([A-E])(?![A-Za-z])")
INLINE_ITEM = re.compile(r"(?<![A-Za-z0-9])([A-E])(?=项)")


def remap_text(text: str, mapping: dict[str, str], reorder_lines: bool = True) -> str:
    """把文本中的选项标号按 mapping 改写；逐选项行同时按新标号排序。"""
    if not isinstance(text, str) or not text:
        return text
    lines = text.split("\n")
    hits = [(i, LINE_LABEL.match(l)) for i, l in enumerate(lines)]
    hits = [(i, m) for i, m in hits if m]
    if hits and reorder_lines:
        rebuilt = []
        for _i, m in hits:
            old = m.group(2)
            new = mapping.get(old, old)
            rebuilt.append((new, f"{m.group(1)}{new}{m.group(3)}{m.group(4)}"))
        rebuilt.sort(key=lambda t: t[0])
        for (i, _m), (_new, txt) in zip(hits, rebuilt):
            lines[i] = txt
    out = "\n".join(lines)
    out = INLINE_OPTION.sub(lambda m: "选项" + mapping.get(m.group(1), m.group(1)), out)
    out = INLINE_ITEM.sub(lambda m: mapping.get(m.group(1), m.group(1)) + "项", out)
    return out


def unresolved_refs(text: str, labels: set[str]) -> int:
    """无法安全改写的裸字母引用数（如「A、C 项」只抓到后半截）。仅用于提示。"""
    if not isinstance(text, str):
        return 0
    bare = re.findall(r"(?<![A-Za-z0-9])([A-E])[、,，](?=[A-E])", text)
    return len(bare)


# ── 重排单题 ────────────────────────────────────────────────

def reorder_one(q: dict, slots: list[str]) -> bool:
    """把正确项搬到 slots 指定的字母位；其余选项保持相对次序。返回是否改动。"""
    raw = q.get("options")
    opts = _options(q)
    old_labels = list(opts.keys())
    ans = set(_answer(q)) & set(old_labels)
    if len(slots) != len(ans) or not ans:
        return False
    correct_old = [l for l in old_labels if l in ans]
    distractors = [l for l in old_labels if l not in ans]
    slot_set = set(slots)
    if len(slot_set) != len(slots):
        return False

    placement: dict[str, str] = {}
    corr_iter = iter(correct_old)
    dist_iter = iter(distractors)
    for slot in LETTERS[: len(old_labels)]:
        if slot in slot_set:
            placement[next(corr_iter)] = slot
        else:
            nxt = next(dist_iter, None)
            if nxt is None:
                return False
            placement[nxt] = slot

    if all(placement[l] == l for l in old_labels):
        return False

    new_order = sorted(old_labels, key=lambda l: placement[l])

    if isinstance(raw, dict):
        q["options"] = {placement[k]: raw[k] for k in new_order}
    elif isinstance(raw, list) and raw and isinstance(raw[0], dict):
        by_label = {str(o.get("label", "")).strip().upper(): o for o in raw}
        if any(k not in by_label for k in old_labels):
            return False
        moved = []
        for k in new_order:
            item = dict(by_label[k])
            item["label"] = placement[k]
            moved.append(item)
        q["options"] = sorted(moved, key=lambda o: o["label"])

    new_ans = sorted(placement[l] for l in correct_old)
    q["answer"] = new_ans if isinstance(q.get("answer"), list) else "".join(new_ans)

    # 解析、概念证据、总分理由里的字母引用必须一起搬（否则静默错位）
    if isinstance(q.get("explanation"), str):
        q["explanation"] = remap_text(q["explanation"], placement)
    lv0 = q.get("learning_value")
    if isinstance(lv0, dict) and isinstance(lv0.get("correct_rationale"), str):
        lv0["correct_rationale"] = remap_text(lv0["correct_rationale"], placement)
    for c in q.get("concepts") or []:
        if isinstance(c, dict) and isinstance(c.get("evidence"), str):
            c["evidence"] = remap_text(c["evidence"], placement, reorder_lines=False)
    for it in q.get("items") or []:  # B1/共用选项子题（正常不会走到，防御）
        if isinstance(it, dict) and isinstance(it.get("explanation"), str):
            it["explanation"] = remap_text(it["explanation"], placement)

    if isinstance(q.get("option_polarities"), dict):
        q["option_polarities"] = {placement.get(k, k): v
                                  for k, v in q["option_polarities"].items()}
    lv = q.get("learning_value")
    if isinstance(lv, dict):
        for po in lv.get("per_option") or []:
            if isinstance(po, dict) and isinstance(po.get("label"), str):
                lab = po["label"].strip().upper()
                po["label"] = placement.get(lab, lab)
    return True


# ── 校验 ────────────────────────────────────────────────────

def audit(items: list[dict]) -> dict:
    th = thresholds()
    return {
        "X1": check_answer_distribution(items, th),
        "X7": check_multi_answer_distribution(items, th),
        "X10": check_answer_position_periodicity(items, th),
    }


def position_ok(items: list[dict]) -> bool:
    """位置类指标：X1、X10 的字母周期、X7 的字母占比与前缀聚集。

    n_correct（正确项个数）与判断交替是**内容**决定，位置工具管不了，不算失败。
    """
    rep = audit(items)
    if rep["X1"]["status"] == "VIOLATED":
        return False
    if (rep["X10"].get("letter_cycle_fit") or 0) >= 0.90:
        return False
    bad = {v.get("metric") for v in rep["X7"].get("violations") or []}
    return not (bad & {"letter_share", "prefix_cluster"})


def metrics(items: list[dict]) -> str:
    rep = audit(items)
    bits = []
    for k, c in rep.items():
        if k == "X10":
            bits.append(f"X10={c['status']}(cycle={c.get('letter_cycle_fit')}"
                        f",判断交替={c.get('binary_alternation_fit')})")
        elif isinstance(c.get("value"), dict):
            bits.append(f"{k}={c['status']}(" +
                        "、".join(f"{lab}{d['share']:.0%}" for lab, d in c["value"].items()) + ")")
        else:
            bits.append(f"{k}={c['status']}")
    return "  ".join(bits)


def bare_ref_notes(items: list[dict], originals: list[dict]) -> list[str]:
    """重排后仍含「A、C 项」这类裸列表引用的题——机器不猜，交人工读一遍。"""
    risky = []
    for a, b in zip(originals, items):
        n = unresolved_refs(a.get("explanation") or "", set()) + \
            unresolved_refs(a.get("learning_value", {}).get("correct_rationale") or "", set())
        if n:
            risky.append(str(b.get("question_id") or b.get("id")))
    if not risky:
        return []
    return [f"{len(risky)} 题的解析里有「A、C 项」这类裸字母列表，已按单字母映射改写但可能读不通，"
            f"请人工过一遍：{', '.join(risky[:8])}{' …' if len(risky) > 8 else ''}"]


def residual_notes(items: list[dict]) -> list[str]:
    """位置工具修不了、只能改内容的缺陷——点名，不要让「跑过脚本」变成免责。"""
    rep = audit(items)
    notes = []
    for v in rep["X7"].get("violations") or []:
        if v.get("metric") in ("n_correct", "combo_share"):
            notes.append("多选内容：" + v["why"] + " → 需改写正确项个数/组合（写 2 项或 3 项正确的题）")
    if (rep["X10"].get("binary_alternation_fit") or 0) >= 0.90:
        notes.append("判断题真值与题号交替 → 需把约一半陈述改写成错误陈述，位置工具改不了")
    return notes


# ── 主流程 ──────────────────────────────────────────────────

def shuffle_batch(items: list[dict], seed: int = DEFAULT_SEED) -> tuple[list[dict], dict]:
    base = json.loads(json.dumps(items, ensure_ascii=False))
    best: tuple[list[dict], dict] | None = None
    try_seed = seed
    for _ in range(MAX_TRIES):
        rnd = random.Random(try_seed)
        work = json.loads(json.dumps(base, ensure_ascii=False))
        plan = allocate(work, rnd)
        changed = 0
        for i, q in enumerate(work):
            key = str(q.get("question_id") or q.get("id") or f"#{i}")
            slots = plan.get(key)
            if slots and reorder_one(q, slots):
                changed += 1
        stat = {"changed": changed, "seed": try_seed}
        if best is None:
            best = (work, stat)
        if position_ok(work):
            return work, stat
        # 记录「违例更少」的一次，避免最终给出一版更差的
        if best and len(audit(work)["X1"].get("violations") or []) < \
                len(audit(best[0])["X1"].get("violations") or []):
            best = (work, stat)
        try_seed += 1
    work, stat = best  # type: ignore[misc]
    stat["warning"] = f"{MAX_TRIES} 次尝试仍有位置类违例，请人工看报告"
    return work, stat


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="答案位置随机化（只换位置，不改选项文本）")
    ap.add_argument("--file", "-f", required=True, help="题库 JSON")
    ap.add_argument("--out", default="", help="输出路径")
    ap.add_argument("--in-place", action="store_true", help="原地写回 --file")
    ap.add_argument("--check", action="store_true", help="只报告，不改文件")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args(argv)

    items, wrapper, src = load_items(args.file)
    print(f"输入：{src}  {len(items)} 题")
    print(f"  现状：{metrics(items)}")

    notes = residual_notes(items)
    if args.check:
        ok = position_ok(items)
        print("  结论：" + ("位置类指标通过" if ok else "有位置泄漏（X1/X7字母占比/前缀/X10周期）"))
        for n in notes:
            print("  · " + n)
        return 0 if ok else 1

    work, stat = shuffle_batch(items, args.seed)
    print(f"  重排：改动 {stat['changed']} 题（种子 {stat['seed']}）")
    if stat.get("warning"):
        print("  ⚠️ " + stat["warning"])
    print(f"  之后：{metrics(work)}")
    for n in residual_notes(work):
        print("  · " + n)
    for n in bare_ref_notes(items, work):
        print("  · " + n)

    if args.in_place:
        save_items(work, wrapper, src)
        print(f"[OK] 已原地写回 {src}")
    elif args.out:
        out = Path(args.out)
        save_items(work, wrapper, out)
        print(f"[OK] 已写出 {out}")
    else:
        print("（未指定 --out / --in-place，仅演练）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
