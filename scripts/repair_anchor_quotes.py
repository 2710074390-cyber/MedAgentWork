#!/usr/bin/env python3
"""repair_anchor_quotes.py — 用 DSH 从教师重点锚定清单中找逐字支持原文，生成可审计的锚点覆盖。

输入：
  --queue    JSON 数组（题目对象，至少含 id/stem/options/answer/teacher_anchor/source_page）
  --anchor   教师重点锚定清单 Markdown
输出：
  --out      合并后的 anchor_overrides.json（仅写入通过逐字校验的条目）
  --report   校验报告 JSON（verified / rejected / reasons）

规则：
  - source_quote 必须在锚定清单中逐字出现（仅忽略空白差异）；
  - teacher_anchor 必须包含 source_quote；
  - 找不到就返回 missing，不允许编造。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
DSH_CWD = Path(r"C:\Users\38063\Desktop\Web-AI\tools\dsh")
RAW_DIR = BASE / "中间产物" / "learning_value_raw"

PROMPT = """# 任务：为医学题目找“逐字支持原文”

你是医学考试命题与教材校对专家。请读取锚定清单文件：
{anchor_path}

为下面 {n} 道题找到能**逐字支持正确答案**的教师重点原文。只输出 JSON 数组，不要 Markdown 代码块，不要解释。

## 输出格式
[
  {{
    "id": "batch040-...",
    "teacher_anchor": "从锚定清单逐字复制的原文（可多句，但必须连续）",
    "keypoint_ref": ["第X条"] 或 ["补充·源②·..."],
    "source_quote": "teacher_anchor 中的逐字子串",
    "source_quote_status": "exact",
    "anchor_status": "verified",
    "note": "选择该条的理由（≤30字）"
  }}
]

## 硬规则
1. `source_quote` 必须是锚定清单中**逐字出现**的文本；不得改写、不得拼接不相邻句子、不得用题目解析冒充原文。
2. `teacher_anchor` 必须包含 `source_quote`，且语义上支持正确答案。
3. `keypoint_ref` 优先用第四节连续编号“第X条”；若原文只在源②/源③正文，用“补充·源X·...”格式。
4. 如果找不到逐字支持原文：`source_quote=""`，`source_quote_status="missing"`，`anchor_status="missing"`，在 `note` 说明。
5. 不要修改题目；不要输出题目以外的内容。

## 待处理题目

```json
{payload}
```
"""


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s or ""))


def build_prompt(items: list[dict], anchor_path: Path) -> str:
    payload = [{
        "id": q.get("id"),
        "type": q.get("type"),
        "module": q.get("module"),
        "stem": q.get("stem"),
        "options": [{"label": o.get("label"), "text": o.get("text")} for o in q.get("options", [])],
        "answer": q.get("answer"),
        "explanation": q.get("explanation"),
        "current_teacher_anchor": q.get("teacher_anchor", ""),
        "source_page": q.get("source_page", ""),
        "keypoint_ref": q.get("keypoint_ref", []),
    } for q in items]
    return PROMPT.format(n=len(items), anchor_path=anchor_path.as_posix(),
                         payload=json.dumps(payload, ensure_ascii=False, indent=2))


def call_dsh(prompt_path: Path, timeout: int = 900) -> str:
    prompt = (
        f"读取 {prompt_path.as_posix()}，严格按文件要求执行。"
        "只输出 JSON 数组，不要 Markdown 代码块，不要解释。"
    )
    cmd = f'npx dsh --profile headless "{prompt}"'
    r = subprocess.run(cmd, cwd=str(DSH_CWD), shell=True, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.stdout or ""


def parse_array(text: str):
    s, e = text.find("["), text.rfind("]")
    if s < 0 or e <= s:
        return None
    try:
        data = json.loads(text[s:e + 1])
        return data if isinstance(data, list) else None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True)
    ap.add_argument("--anchor", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--chunk-size", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0, help="0=全部；否则只处理前 N 题（配合 --skip-existing 分批跑）")
    ap.add_argument("--skip-existing", action="store_true", help="跳过 --out 中已有 id")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    queue = load_json(Path(args.queue))
    anchor_text = Path(args.anchor).read_text(encoding="utf-8")
    anchor_norm = norm(anchor_text)
    out_path = Path(args.out)
    existing = load_json(out_path) if out_path.exists() else {}
    overrides = dict(existing)
    if args.skip_existing:
        queue = [q for q in queue if q.get("id") not in overrides]
    if args.limit > 0:
        queue = queue[:args.limit]
    verified, rejected = [], []
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    chunks = [queue[i:i + args.chunk_size] for i in range(0, len(queue), args.chunk_size)]
    for ci, chunk in enumerate(chunks, 1):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prompt_path = RAW_DIR / f"repair_chunk{ci:03d}_{stamp}.md"
        prompt_path.write_text(build_prompt(chunk, Path(args.anchor)), encoding="utf-8")
        print(f"[{ci}/{len(chunks)}] {len(chunk)} 题 → {prompt_path.name}")
        if args.dry_run:
            continue
        try:
            stdout = call_dsh(prompt_path, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            rejected.extend({"id": q["id"], "reason": "dsh_timeout"} for q in chunk)
            continue
        raw_path = RAW_DIR / f"repair_chunk{ci:03d}_{stamp}.out.txt"
        raw_path.write_text(stdout, encoding="utf-8")
        patch = parse_array(stdout)
        if not patch:
            rejected.extend({"id": q["id"], "reason": "parse_error"} for q in chunk)
            continue
        by_id = {p.get("id"): p for p in patch if isinstance(p, dict)}
        for q in chunk:
            p = by_id.get(q["id"])
            if not p:
                rejected.append({"id": q["id"], "reason": "missing_in_output"})
                continue
            quote = str(p.get("source_quote") or "").strip()
            teacher = str(p.get("teacher_anchor") or "").strip()
            status = str(p.get("source_quote_status") or "").strip()
            if status != "exact" or not quote:
                rejected.append({"id": q["id"], "reason": "no_exact_quote", "note": p.get("note", "")})
                continue
            if norm(quote) not in anchor_norm:
                rejected.append({"id": q["id"], "reason": "quote_not_found", "quote": quote[:60]})
                continue
            if norm(quote) not in norm(teacher):
                rejected.append({"id": q["id"], "reason": "teacher_does_not_contain_quote"})
                continue
            overrides[q["id"]] = {
                "teacher_anchor": teacher,
                "keypoint_ref": p.get("keypoint_ref") or q.get("keypoint_ref", []),
                "note": p.get("note", "repair_anchor_quotes"),
                "source_quote": quote,
                "source_quote_status": "exact",
                "anchor_status": "verified",
            }
            verified.append({"id": q["id"], "keypoint_ref": overrides[q["id"]]["keypoint_ref"],
                             "quote": quote[:80]})
            print(f"  [OK] {q['id']} | {quote[:50]}...")
        # 每个 chunk 结束立即落盘，避免长任务超时丢失已验证结果
        out_path.write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8")

    out_path.write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "queue": args.queue,
        "anchor": args.anchor,
        "verified": verified,
        "rejected": rejected,
        "summary": {"queue": len(queue), "verified": len(verified), "rejected": len(rejected)},
    }
    rp = Path(args.report)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成：verified {len(verified)} / rejected {len(rejected)} → {out_path}")
    print(f"报告：{rp}")
    return 0 if not rejected else 1


if __name__ == "__main__":
    raise SystemExit(main())
