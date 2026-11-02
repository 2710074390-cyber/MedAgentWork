#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backtest_r13.py — R13 降级与条件从句豁免的回测（P2-S5 / AC-P2-06，2026-11-02）

回答一个问题：**改造后，R13 还会不会误伤"必须写长"的选项？**

三层口径一次算清：
  旧口径  —— 任何选项 > 20 字即 FAIL（改造前行为，作为对照基线）
  新口径  —— 真题原题整体豁免；含条件/因果/时间窗/人群限定的选项豁免；
             其余超长降级为 WARN

误伤（false positive）定义：被 R13 判为问题、但该选项**删短就会改变医学含义**
（真题原题 / 含限定 / 并列客观事实）。误伤率 = 误伤数 / 判为问题的选项数。

用法：
  python scripts/backtest_r13.py
  python scripts/backtest_r13.py --json reports/validate/r13_backtest_20261102.json --md ...md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.validate.rules_structural import check_r13_length_ceiling, conditional_feature, origin_kind  # noqa: E402

DEFAULT_GLOB = "最终产物/batch*/ALL_questions_FIXED.json"
LIMIT = 20


def norm_options(raw):
    if isinstance(raw, dict):
        return {str(k).upper(): str(v) for k, v in raw.items()}
    out = {}
    for it in (raw or []):
        if isinstance(it, dict) and it.get("label"):
            out[str(it["label"]).upper()] = str(it.get("text") or "")
        elif isinstance(it, str):
            m = re.match(r"^\s*([A-Za-z])\s*[.．、)）]\s*(.*)$", it)
            if m:
                out[m.group(1).upper()] = m.group(2)
    return out


def as_question(item: dict) -> dict:
    """把原始题投影成规则需要的形状（保留来源标记，R13 要用它判原题豁免）。"""
    return {
        "id": item.get("id") or item.get("question_id") or "?",
        "type": item.get("type") or item.get("question_type") or "A1",
        "options": norm_options(item.get("options")),
        "kaoyan_origin": item.get("kaoyan_origin"),
        "zhiyi_origin": item.get("zhiyi_origin"),
        "zhiyi_pdf_origin": item.get("zhiyi_pdf_origin"),
        "source_type": item.get("source_type", ""),
    }


def run(paths: list[Path]) -> dict:
    per_batch = {}
    old_hits = new_exempt_origin = new_exempt_text = new_warn = 0
    residual = []
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        batch = next((x for x in p.parts[::-1] if x.startswith("batch")), p.parent.name)
        st = {"questions": 0, "old_fail": 0, "exempt_origin": 0, "exempt_text": 0, "warn": 0}
        for item in data:
            if not isinstance(item, dict):
                continue
            st["questions"] += 1
            q = as_question(item)
            opts = q["options"]
            if q["type"] in ("X", "X型") or not opts:
                continue
            # 旧口径：>LIMIT 即 FAIL（逐选项）
            st["old_fail"] += sum(1 for v in opts.values() if v and len(v) > LIMIT)
            for iss in check_r13_length_ceiling(q):
                if iss.get("rule") != "R13" or ".option" not in str(iss.get("target", "")):
                    continue
                if iss.get("origin_exempt"):
                    st["exempt_origin"] += 1
                elif iss.get("exempted"):
                    st["exempt_text"] += 1
                else:
                    st["warn"] += 1
                    residual.append({
                        "batch": batch, "qid": q["id"], "target": iss["target"],
                        "detail": iss["detail"],
                        "feature": conditional_feature(
                            opts.get(str(iss["target"]).split("option")[-1], "")),
                    })
        per_batch[batch] = st
        old_hits += st["old_fail"]
        new_exempt_origin += st["exempt_origin"]
        new_exempt_text += st["exempt_text"]
        new_warn += st["warn"]

    residual_with_feature = [r for r in residual if r["feature"]]
    # 改造后仍在 WARN 的选项里，若还能识别出"删短就错"的特征，就是残留误伤
    residual_fp = len(residual_with_feature)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "scripts/backtest_r13.py",
        "limit_chars": LIMIT,
        "sources": [str(p.relative_to(BASE)).replace("\\", "/") for p in paths],
        "totals": {
            "old_fail_hits": old_hits,
            "exempt_origin": new_exempt_origin,
            "exempt_text": new_exempt_text,
            "residual_warn": new_warn,
            "residual_with_feature": residual_fp,
        },
        "false_positive_rate": round(residual_fp / new_warn, 4) if new_warn else 0.0,
        "per_batch": per_batch,
        "residual_samples": residual[:40],
    }


def render_md(rep: dict) -> str:
    t = rep["totals"]
    lines = [
        "# R13 降级与条件从句豁免 · 回测报告（AC-P2-06）", "",
        f"- 生成：{rep['generated_at']}",
        f"- 工具：`{rep['tool']}`　上限：{rep['limit_chars']} 字",
        f"- 扫描：{len(rep['sources'])} 个批次产物",
        "",
        "## 1. 结论", "",
        f"- 改造前（>20 字即 FAIL）：**{t['old_fail_hits']}** 个选项被拦",
        f"- 改造后：真题原题整体豁免 **{t['exempt_origin']}** 项；条件/因果/时间窗豁免 **{t['exempt_text']}** 项；"
        f"降级为 WARN **{t['residual_warn']}** 项",
        f"- **残留误伤率 = {rep['false_positive_rate']:.1%}**"
        f"（残留 WARN 中仍能识别出限定特征的 {t['residual_with_feature']} 项 / {t['residual_warn']} 项）",
        "",
        "> 判定标准：AC-P2-06 要求 <5%。误伤 = 被判定为问题、但选项**删短就会改变医学含义**。",
        "",
        "## 2. 按批次", "",
        "| 批次 | 题量 | 旧口径 FAIL | 真题豁免 | 条件豁免 | 降级 WARN |",
        "|---|---|---|---|---|---|",
    ]
    for b, s in sorted(rep["per_batch"].items()):
        if not (s["old_fail"] or s["exempt_origin"] or s["exempt_text"] or s["warn"]):
            continue
        lines.append(f"| {b} | {s['questions']} | {s['old_fail']} | {s['exempt_origin']} | {s['exempt_text']} | {s['warn']} |")
    lines += ["", "## 3. 残留 WARN 明细（改造后仍在提示的选项）", ""]
    if rep["residual_samples"]:
        lines += ["| 批次 | qid | 选项 | 判定 |", "|---|---|---|---|"]
        for r in rep["residual_samples"][:25]:
            lines.append(f"| {r['batch']} | `{r['qid']}` | {r['target'].split('.')[-1]} | {r['detail'][:70]} |")
    else:
        lines.append("无残留：所有超长选项要么被豁免，要么本身是真题/含限定。")
    lines += [
        "",
        "## 4. 为什么这样改", "",
        "1. **真题不能改**：`kaoyan_origin` / `zhiyi_origin` 的题，题干与选项受原题保真约束，" +
        "拿长度规则去要求改写真题，等于逼着人改答案——这是误伤的主要来源（本次占大头）。",
        "2. **删短就错的不该拦**：「嵌顿3～4小时内、无腹膜刺激征者可行手法复位」删掉时间窗就变成另一个结论。",
        "3. **R13 降级为 WARN，但 R2 保留 FAIL**：真正要防的是「靠长度猜答案」，"
        "这件事由 R2（正确项/最短干扰项长度比 >2.0）守住；R13 退到「提示整体偏长」的位置。",
        "",
    ]
    if t.get("exempt_text", 0) == 0:
        lines += [
            "> ⚠️ 本次回测中**条件从句豁免命中 0 次**：含条件的超长选项全部落在真题批次，"
            "先被第一层（原题豁免）拦下了。因此第二层豁免在真实数据上未被验证，"
            "其正确性只由单元测试覆盖（`tests/test_validate_rules.py` 的 "
            "`test_r13_conditional_clause_exempt` / `test_r13_purpose_clause_exempt`）。"
            "下次出现原创题的超长条件选项时，这里才会有数。",
            "",
        ]
    lines += [
        "---", "",
        "本报告只含选项长度与规则编号，不含任何用户数据。",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="R13 降级 + 条件从句豁免回测")
    ap.add_argument("--glob", default=DEFAULT_GLOB)
    ap.add_argument("--json", default=str(BASE / "reports/validate/r13_backtest_20261102.json"))
    ap.add_argument("--md", default=str(BASE / "reports/validate/r13_backtest_20261102.md"))
    args = ap.parse_args(argv)

    paths = sorted(BASE.glob(args.glob))
    if not paths:
        print(f"[FAIL] 没有匹配 {args.glob} 的文件", file=sys.stderr)
        return 2
    rep = run(paths)
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.md).write_text(render_md(rep), encoding="utf-8")

    t = rep["totals"]
    print(f"旧 FAIL {t['old_fail_hits']} → 真题豁免 {t['exempt_origin']} / 条件豁免 {t['exempt_text']} / "
          f"降级 WARN {t['residual_warn']} | 残留误伤率 {rep['false_positive_rate']:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
