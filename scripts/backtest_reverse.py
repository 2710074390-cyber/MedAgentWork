# -*- coding: utf-8 -*-
"""P2-S4 反选题回测（AC-P2-05）。

回答三个问题：
  1. 全库反选题占比是多少，有没有批次超过 15% 上限；
  2. 现有的 polarity 标注可不可信（标注 vs 题干设问的交叉核对）；
  3. 「4 个为真干扰项逐项锚点」在历史产物上到底是什么状况。

口径说明见 check_reverse_selection 的 docstring：分子取 polarity 与题干设问的
**并集**，宁可高估——用单一口径都会把问题算小（batch042 的 polarity 全标了
positive，只信标注会得出 0% 的假象）。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

from scripts.validate import rules_batch as rb  # noqa: E402

OUT_JSON = BASE / "reports" / "validate" / "reverse_selection_20261102.json"
OUT_MD = BASE / "reports" / "validate" / "reverse_selection_20261102.md"


def collect() -> dict:
    files = sorted((BASE / "最终产物").glob("batch*/ALL_questions_FIXED.json"))
    th = rb.thresholds()
    rows = []
    total_q = total_rev = 0
    neg_items = []
    for f in files:
        items = rb.load_items(f)
        r = rb.check_reverse_selection(items, th)
        cons = rb.check_polarity_consistency(items)
        total_q += r["denominator"]
        total_rev += r["numerator"]
        for q in items:
            if rb.polarity(q) == "negative" or rb.stem_reverse(q):
                lv = q.get("learning_value") or {}
                per = [p for p in (lv.get("per_option") or []) if isinstance(p, dict)]
                anchored = sum(1 for p in per
                               if str(p.get("source_anchor") or p.get("anchor") or "").strip())
                neg_items.append({
                    "batch": f.parent.name,
                    "qid": rb._qid(q, 0),
                    "has_per_option": bool(per),
                    "per_option": len(per),
                    "distractors": len(rb.distractor_labels(q)),
                    "anchored_options": anchored,
                    "item_evidence": bool(str(lv.get("answer_evidence") or "").strip()),
                    "polarity": rb.polarity(q) or "",
                    "stem_says": rb.stem_reverse(q),
                })
        rows.append({
            "batch": f.parent.name, "items": r["denominator"],
            "reverse": r["numerator"], "value": r["value"],
            "by_signal": r["by_signal"],
            "status": r["status"],
            "polarity_mismatch": cons["mismatch"], "polarity_agree": cons["agree"],
            "polarity_mismatch_rate": cons["value"],
        })
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "scripts/backtest_reverse.py",
        "threshold": th.get("x5_reverse_max", 0.15),
        "batches": rows,
        "totals": {"batches": len(rows), "items": total_q, "reverse": total_rev,
                   "value": round(total_rev / total_q, 4) if total_q else 0.0},
        "violated_batches": [r["batch"] for r in rows if r["status"] == "VIOLATED"],
        "reverse_items": neg_items,
    }


def anchor_stats(d: dict) -> dict:
    items = d["reverse_items"]
    n = len(items)
    with_per = sum(1 for r in items if r["has_per_option"])
    option_level = sum(r["anchored_options"] for r in items)
    distractor_total = sum(r["distractors"] for r in items)
    item_level = sum(1 for r in items if r["item_evidence"])
    return {
        "reverse_items": n,
        "with_per_option": with_per,
        "with_item_evidence": item_level,
        "distractor_options": distractor_total,
        "anchored_options": option_level,
        "option_level_coverage": round(option_level / distractor_total, 4) if distractor_total else 0.0,
        "item_level_coverage": round(item_level / n, 4) if n else 0.0,
    }


def render_md(d: dict, a: dict) -> str:
    t = d["totals"]
    limit = d["threshold"]
    L = [
        "# 反选题回测报告（P2-S4 / AC-P2-05）", "",
        f"- 生成：{d['generated_at']}",
        f"- 工具：`{d['tool']}`",
        f"- 上限：**{limit:.0%}**　结论：**{'FAIL' if d['violated_batches'] else 'PASS'}**",
        f"- 全库：{t['items']} 题，反选 **{t['reverse']}** 题 = **{t['value']:.1%}**",
        "",
        "---", "",
        "## 1. 逐批占比", "",
        "| 批次 | 题量 | 反选 | 占比 | polarity 口径 | 题干口径 | 结论 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in d["batches"]:
        bs = r["by_signal"]
        mark = "**超标**" if r["status"] == "VIOLATED" else "通过"
        L.append(f"| {r['batch']} | {r['items']} | {r['reverse']} | {r['value']:.1%} | "
                 f"{bs['polarity']:.1%} | {bs['stem']:.1%} | {mark} |")
    L.append(f"| **合计** | {t['items']} | {t['reverse']} | **{t['value']:.1%}** | — | — | — |")

    L += ["", "### 超标批次", ""]
    if d["violated_batches"]:
        for r in d["batches"]:
            if r["status"] != "VIOLATED":
                continue
            L.append(f"- **{r['batch']}**：{r['reverse']}/{r['items']} = {r['value']:.1%}"
                     f"（polarity {r['by_signal']['polarity']:.1%} / 题干 {r['by_signal']['stem']:.1%}）")
        L += ["", "这三个批次是历史产物，**不改写**：反选题不是错误，超过 15% 才是。",
              "下一批开批次时，X5 会在 `--batch-mode --batch-enforce` 下直接阻断。"]
    else:
        L.append("无。")

    L += ["", "---", "", "## 2. 为什么分子取「并集」而不是只看 polarity", "",
          "两种单口径都会把问题算小：", "",
          "| 批次 | 只看 polarity | 只看题干 | 并集 | 真相 |", "|---|---|---|---|---|"]
    for r in d["batches"]:
        bs = r["by_signal"]
        if abs(bs["polarity"] - bs["stem"]) < 0.02:
            continue
        gap = "polarity 漏标" if bs["polarity"] < bs["stem"] else "题干漏检"
        L.append(f"| {r['batch']} | {bs['polarity']:.1%} | {bs['stem']:.1%} | "
                 f"{r['value']:.1%} | {gap} |")
    L += ["", "batch042 的 18 道「下列哪项不正确」全部标了 `polarity=positive`——"
          "只看标注会得出 0%，等于把「标注没写」读成「题没问题」。",
          "反方向也有：batch037 的题干写成 `<b>不属于</b>`，正则不先去 HTML 标签就整批漏检。",
          "两个缺陷都会让数字变小、结论变好，所以门禁取并集。", "",
          "---", "", "## 3. 极性标注质量（X5-P，advisory）", "",
          "| 批次 | 一致 | 不一致 | 不一致率 |", "|---|---|---|---|"]
    for r in d["batches"]:
        if r["polarity_agree"] + r["polarity_mismatch"] == 0:
            continue
        L.append(f"| {r['batch']} | {r['polarity_agree']} | {r['polarity_mismatch']} | "
                 f"{r['polarity_mismatch_rate']:.1%} |")
    L += ["", "不一致项不一定是标注错，也可能是题干正则把「禁忌证是？」这类定语用法误判。"
          "所以要人工看样本，不能直接改数据。", "",
          "---", "", "## 4. 「4 个为真干扰项逐项锚点」的历史状况", "",
          f"- 反选题 {a['reverse_items']} 道，其中带 `per_option` 的 **{a['with_per_option']}** 道",
          f"- 带题级 `answer_evidence` 的 **{a['with_item_evidence']}** 道（{a['item_level_coverage']:.1%}）",
          f"- 选项级锚点：{a['anchored_options']} / {a['distractor_options']} = "
          f"**{a['option_level_coverage']:.1%}**", "",
          "这个数字低不是因为题目质量差，而是因为**字段当时不存在**："
          "schema 2.0 时代的产物没有 `per_option.source_anchor`，题级证据也只有 15.6% 写过。"
          "所以 X5-A 只在 `schema_version ≥ 2.2` 的批次上强制，历史批次 SKIP、不追溯。", "",
          "同一批数据上还发现一个语义错位：旧的 R15 对**所有**干扰项要求 "
          "`misconception_id`。而反选题的干扰项是那 4 个**正确说法**——"
          "逼它写「这句话错在哪」，等于让模型给真话编错误认知。"
          "2026-11-02 起按极性分流：反选题要 `source_anchor`（这句对的话出自哪段），"
          "`misconception` 改为可选（描述「学生为什么误选」，通常是忽略否定词）。", "",
          "---", "", "## 5. 提示词侧的约束", "",
          "`Prompt版本/MedGen_current_prompt.md` 的 HC-29 段已写入：", "",
          "- 整批反选题 ≤ 15%，超了改成正选（考同一个知识点，换个问法）；",
          "- 反选题的 4 个为真干扰项必须逐项 `source_anchor`，不能只给整题一个页码；",
          "- `polarity` 必须如实标注，反选题漏标会让 R15 的 truth 期望值整体反向。", "",
          "---", "",
          "*本报告只含题目 ID、批次数与占比，不含任何用户数据。*",
          ]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P2-S4 反选题回测")
    ap.add_argument("--json", default=str(OUT_JSON))
    ap.add_argument("--md", default=str(OUT_MD))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    d = collect()
    a = anchor_stats(d)
    d["anchor"] = a
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.md).write_text(render_md(d, a), encoding="utf-8")

    if not args.quiet:
        t = d["totals"]
        print(f"全库反选 {t['reverse']}/{t['items']} = {t['value']:.1%}（上限 {d['threshold']:.0%}）")
        print(f"超标批次: {d['violated_batches'] or '无'}")
        print(f"选项级锚点: {a['option_level_coverage']:.1%} "
              f"({a['anchored_options']}/{a['distractor_options']})")
    return 0 if not d["violated_batches"] else 1


if __name__ == "__main__":
    sys.exit(main())
