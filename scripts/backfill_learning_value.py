#!/usr/bin/env python3
"""backfill_learning_value.py — 用 DSH headless 为题目批量补写学习价值层（v2 草案）。

流程：
  1. 读取 最终产物/{batch}/ALL_questions_FIXED.json（或 --source）
  2. 按 chunk-size 切题，生成严格提示词文件
  3. 调用 `npx dsh --profile headless`，要求只输出 JSON 数组
  4. 解析、合并原题字段（stem/options/answer/...），补 is_correct
  5. 用 scripts/check_learning_value.py 的 check_item 逐题校验
  6. 增量写入 --out（可 --resume 续跑），原始输出留在 raw/

用法：
  python scripts/backfill_learning_value.py --batch batch040 --limit 12 --chunk-size 3 --exclude-pilot
  python scripts/backfill_learning_value.py --batch batch040 --chunk-size 3 --resume
  python scripts/backfill_learning_value.py --batch batch040 --dry-run --limit 6
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
SCRIPTS = BASE / "scripts"
sys.path.insert(0, str(SCRIPTS))
from check_learning_value import check_item  # noqa: E402

DSH_CWD = Path(r"C:\Users\38063\Desktop\Web-AI\tools\dsh")
RAW_DIR = BASE / "中间产物" / "learning_value_raw"
PILOT = BASE / "中间产物" / "batch040" / "learning_value_pilot" / "item_v2_pilot.json"

INSTRUCTIONS = """# 任务：为医学题目补写“学习价值层”

你是临床医学命题与学习科学专家。请为下面 {n} 道题补写结构化解析与错误认知字段。
**只输出严格 JSON 数组**，不要 Markdown 代码块，不要解释，不要改写题干/选项/答案。

## 硬规则

1. 只能使用题目中给出的 `stem`、`options`、`answer`、`explanation`、`teacher_anchor`、`source_page` 信息；不得引入未给出的数值、指南、药物剂量或研究结论。
2. `correct_rationale`：解释正确答案的机制/依据，至少 60 字；不要只复述答案。
3. `per_option`：必须覆盖全部选项，label 与输入完全一致。
   - 正确选项：`truth=true`，`misconception_id=null`，`misconception=null`；`why` 说明为什么对。
   - 错误选项：`truth=false`，`why` 至少 20 字，说明为什么错；`misconception_id` 用 `MC-ENT-XX` 格式；`misconception` 说明学生为什么会选它。
4. `key_takeaway`：可迁移到同类题的鉴别规则/记忆钩子，至少 30 字。
5. `source_quote`：从 `teacher_anchor` 中**逐字摘录**支持答案的句子；若 teacher_anchor 为空或与题目不匹配，`source_quote=""`，`source_quote_status` 写 `missing` 或 `mismatch`。
6. `source_quote_status`：`exact` / `paraphrase` / `missing` / `mismatch`。
7. `anchor_status`：`verified` / `partial` / `mismatch` / `missing`。
8. `quality_flags`：数组；记录“疑似双答案/锚点不匹配/来源不足/需人工裁定”等问题。没有则空数组。
9. 不要修改原题；输出中 `id` 必须与输入一致。
10. **反选题（polarity=negative）**：`truth` 表示该选项陈述本身是否为真，不是“是否为答案”。
    - 正确答案的选项 `truth=false`；其余选项 `truth=true`；
    - `misconception` 要解释学生为什么会误选这些“本身为真”的干扰项（通常是忽略了“不包括/错误/除外”）。

## 输出格式（只输出这个数组）

[
  {{
    "id": "batch040-...",
    "teacher_anchor": "原样复制输入的 teacher_anchor",
    "keypoint_ref": ["原样复制"],
    "learning_value": {{
      "correct_rationale": "...",
      "per_option": [
        {{"label": "A", "truth": false, "why": "...", "misconception_id": "MC-ENT-01", "misconception": "..."}},
        {{"label": "B", "truth": true, "why": "...", "misconception_id": null, "misconception": null}}
      ],
      "key_takeaway": "...",
      "source_quote": "...",
      "source_quote_status": "exact",
      "anchor_status": "verified",
      "quality_flags": [],
      "review_status": "pilot_unreviewed"
    }}
  }}
]

## 输入题目

```json
{payload}
```
"""


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def apply_override(q: dict, overrides: dict) -> dict:
    """应用人工确认的锚点覆盖（不改源文件，保持可追溯）。"""
    o = overrides.get(q.get("id"))
    if not o:
        return q
    q = dict(q)
    if o.get("teacher_anchor"):
        q["teacher_anchor"] = o["teacher_anchor"]
    if o.get("keypoint_ref"):
        q["keypoint_ref"] = o["keypoint_ref"]
    q["anchor_override_note"] = o.get("note", "")
    return q


def build_prompt(items: list[dict], overrides: dict) -> str:
    payload = []
    for q in items:
        q = apply_override(q, overrides)
        payload.append({
            "id": q.get("id"),
            "type": q.get("type"),
            "module": q.get("module"),
            "module_name": q.get("module_name"),
            "stem": q.get("stem"),
            "options": [{"label": o.get("label"), "text": o.get("text")} for o in q.get("options", [])],
            "answer": q.get("answer"),
            "polarity": q.get("polarity", "positive"),
            "explanation": q.get("explanation"),
            "teacher_anchor": q.get("teacher_anchor", ""),
            "source_page": q.get("source_page", ""),
            "keypoint_ref": q.get("keypoint_ref", []),
            "difficulty": q.get("difficulty", ""),
            "bloom": q.get("bloom", ""),
        })
    return INSTRUCTIONS.format(n=len(items), payload=json.dumps(payload, ensure_ascii=False, indent=2))


def call_dsh(prompt_path: Path, timeout: int = 900) -> tuple[str, str]:
    prompt = (
        f"读取 {prompt_path.as_posix()}，严格按文件要求执行。"
        "只输出 JSON 数组，不要 Markdown 代码块，不要解释。"
    )
    cmd = f'npx dsh --profile headless "{prompt}"'
    r = subprocess.run(
        cmd, cwd=str(DSH_CWD), shell=True, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    return r.stdout or "", r.stderr or ""


def parse_array(text: str):
    s = text.find("[")
    e = text.rfind("]")
    if s < 0 or e <= s:
        return None
    try:
        data = json.loads(text[s:e + 1])
        return data if isinstance(data, list) else None
    except Exception:
        return None


def merge_item(raw: dict, patch: dict, overrides: dict) -> dict:
    q = apply_override(dict(raw), overrides)
    ans = str(q.get("answer") or "").strip().upper()
    q["options"] = [
        {"label": o.get("label"), "text": o.get("text"), "is_correct": str(o.get("label")) in ans}
        for o in q.get("options", [])
    ]
    q["teacher_anchor"] = patch.get("teacher_anchor", q.get("teacher_anchor", ""))
    q["keypoint_ref"] = patch.get("keypoint_ref", q.get("keypoint_ref", []))
    q["learning_value"] = patch.get("learning_value", {})
    q["legacy_explanation"] = q.get("explanation", "")
    q["review_status"] = "pilot_unreviewed"
    return q


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--source", default="", help="默认 最终产物/{batch}/ALL_questions_FIXED.json")
    ap.add_argument("--out", default="", help="默认 中间产物/{batch}/learning_value_v2/items_v2.json")
    ap.add_argument("--chunk-size", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="0=全部")
    ap.add_argument("--ids", default="", help="逗号分隔，只跑这些 id")
    ap.add_argument("--exclude-pilot", action="store_true", help="排除 item_v2_pilot.json 中的 id")
    ap.add_argument("--resume", action="store_true", help="跳过 --out 中已有 id")
    ap.add_argument("--dry-run", action="store_true", help="只生成提示词，不调用 DSH")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--overrides", default="", help="默认 中间产物/{batch}/learning_value_v2/anchor_overrides.json（存在时加载）")
    args = ap.parse_args()

    src = Path(args.source) if args.source else BASE / "最终产物" / args.batch / "ALL_questions_FIXED.json"
    out = Path(args.out) if args.out else BASE / "中间产物" / args.batch / "learning_value_v2" / "items_v2.json"
    override_path = Path(args.overrides) if args.overrides else BASE / "中间产物" / args.batch / "learning_value_v2" / "anchor_overrides.json"
    overrides = load_json(override_path) if override_path.exists() else {}
    out.parent.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_json(src)
    if not isinstance(rows, list):
        print("[FAIL] source 不是数组", file=sys.stderr)
        return 2

    selected = rows
    if args.ids:
        want = {x.strip() for x in args.ids.split(",") if x.strip()}
        selected = [q for q in rows if q.get("id") in want]
    if args.exclude_pilot and PILOT.exists():
        pilot_ids = {q.get("id") for q in load_json(PILOT)}
        selected = [q for q in selected if q.get("id") not in pilot_ids]
    if args.resume and out.exists():
        done = {q.get("id") for q in load_json(out)}
        selected = [q for q in selected if q.get("id") not in done]
    if args.limit > 0:
        selected = selected[:args.limit]

    if not selected:
        print("没有待处理题目。")
        return 0

    print(f"批次 {args.batch} | 待处理 {len(selected)} 题 | chunk={args.chunk_size} | dry-run={args.dry_run}")
    results = load_json(out) if (args.resume and out.exists()) else []
    done_ids = {q.get("id") for q in results}
    failures = []
    chunks = [selected[i:i + args.chunk_size] for i in range(0, len(selected), args.chunk_size)]

    for ci, chunk in enumerate(chunks, 1):
        ids = [q["id"] for q in chunk]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prompt_path = RAW_DIR / f"{args.batch}_chunk{ci:03d}_{stamp}.md"
        prompt_path.write_text(build_prompt(chunk, overrides), encoding="utf-8")
        print(f"\n[{ci}/{len(chunks)}] {len(chunk)} 题 → {prompt_path.name}")
        if args.dry_run:
            continue
        try:
            stdout, stderr = call_dsh(prompt_path, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print("  [FAIL] DSH 超时")
            failures.extend(ids)
            continue
        raw_path = RAW_DIR / f"{args.batch}_chunk{ci:03d}_{stamp}.out.txt"
        raw_path.write_text(stdout, encoding="utf-8")
        patch = parse_array(stdout)
        if not patch:
            print(f"  [FAIL] 无法解析 JSON；原始输出 {raw_path}")
            failures.extend(ids)
            continue
        by_id = {p.get("id"): p for p in patch if isinstance(p, dict)}
        for q in chunk:
            p = by_id.get(q["id"])
            if not p:
                print(f"  [FAIL] 缺少 {q['id']}")
                failures.append(q["id"])
                continue
            merged = merge_item(q, p, overrides)
            check = check_item(merged)
            results.append(merged)
            done_ids.add(q["id"])
            mark = check["status"]
            print(f"  [{mark}] {q['id']} | 中位 {check['median_chars']} 字 | R18 {check['anchor_overlap']:.3f}")
            if mark == "FAIL":
                for i in check["issues"]:
                    print(f"    - {i['rule']}: {i['detail']}")
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.dry_run:
        print("\n[dry-run] 提示词已生成，未调用 DSH。")
        return 0

    print(f"\n完成：输出 {len(results)} 题 → {out}")
    if failures:
        print(f"失败 {len(failures)} 题：{failures}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
