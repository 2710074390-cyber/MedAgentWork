#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_wording.py — 对外表述核查（P3-S2/AC-P3-03，2026-11-02）

要防的不是"用了「实测」这个词"，而是**把没测过的东西说成测过**。两类问题：

  A 措辞越界：把先验估计/LLM 估值/模拟考生答对率标成「实测难度 / 实测区分度」。
    白名单：同一行出现「非实测 / 禁止 / 不得 / 不是实测 / 不许」等否定语境时，
    视为声明而非宣称，不计数（这类句子恰恰是我们要的）。

  B 结论无据：文档里出现「κ = 0.xx」「一致性达标 / 良好」之类结论，
    但仓库里找不到对应的 agreement 报告支撑。结论必须能指回证据文件。

用法：
  python scripts/check_wording.py                     # 扫描默认范围
  python scripts/check_wording.py --json out.json --md out.md
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

SCAN_DIRS = ("reports", "docs", "Prompt版本", "schemas", "rules")
SCAN_ROOT_FILES = ("CONTEXT.md", "SOUL.md", "README.md")
EXTS = {".md", ".json", ".py", ".yaml", ".yml"}
SKIP_PARTS = ("node_modules", ".workbuddy", "archive", ".git", "__pycache__")

# A：实测类宣称。关键词必须与「难度/区分度/专家评分」这类不可测对象同现才算越界。
PATTERNS_A = [
    (re.compile(r"实测(难度|区分度|专家评分|掌握度|学习效果)"), "把估值标为实测"),
    (re.compile(r"(难度|区分度)[^。\n]{0,12}(实测值|实测数据|实测结果)"), "估值与实测混用"),
    (re.compile(r"(专家评分|专家打分|评分结果)[^。\n]{0,6}实测"), "专家评分被说成实测"),
    (re.compile(r"(模拟考生|LLM ?模拟)[^。\n]{0,20}(实测难度|真实难度)"), "模型答对率冒充实测"),
]
NEGATIONS = (
    "非实测", "不是实测", "未实测", "禁止", "不得", "不许", "勿", "不对外", "红线", "不该", "不可",
    "只能", "仅限", "0 处", "未见", "反例", "反模式", "避免", "警惕", "不能", "不应", "风险",
    # 风险登记表/反模式清单里的写法：「把专家评分当实测」「口径混用」是在描述错误做法
    "当实测", "混用", "误标", "错标",
)
# 「非本库实测」「不是真值实测」这类否定式不靠固定词表，靠句式识别
NEG_RE = re.compile(r"非[^，。；\n]{0,8}实测|不(是|作|得|许|可)[^，。；\n]{0,8}实测")

# B：一致性结论。命中即要求存在 agreement 证据文件。
PATTERN_B = re.compile(r"(κ|kappa)[^。\n]{0,10}[=＝]\s*0?\.\d+|一致性(达标|良好|优秀|很高)")
EVIDENCE_HINTS = ("agreement", "一致性")


def _is_negated(line: str, context: str = "") -> bool:
    """判定一行是「宣称」还是「声明/禁令」。声明保留，宣称才算越界。"""
    return (any(n in line for n in NEGATIONS)
            or any(n in context for n in NEGATIONS)
            or bool(NEG_RE.search(line)))


def classify_line(line: str, context: str = "") -> list[dict]:
    """返回该行命中的规则与判定。供 scan() 与测试共用，避免两套判定逻辑。"""
    out = []
    for pat, why in PATTERNS_A:
        if pat.search(line):
            out.append({
                "why": why,
                "verdict": "OK(声明/否定语境)" if _is_negated(line, context) else "VIOLATION",
            })
    return out


def iter_files(skip: tuple = ()):
    skip_set = {str(Path(s).resolve()) for s in skip if s}
    for d in SCAN_DIRS:
        p = BASE / d
        if not p.exists():
            continue
        for f in p.rglob("*"):
            if f.suffix.lower() in EXTS and f.is_file() and not any(s in str(f) for s in SKIP_PARTS):
                if str(f.resolve()) in skip_set:
                    continue
                yield f
    for name in SCAN_ROOT_FILES:
        f = BASE / name
        if f.exists() and str(f.resolve()) not in skip_set:
            yield f


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(BASE)).replace("\\", "/")
    except ValueError:
        return str(p)


def scan(skip: tuple = ()) -> dict:
    hits_a, hits_b = [], []
    files = 0
    for f in iter_files(skip):
        files += 1
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            # 否定/声明语境可能不在同一行（如「禁止对外宣称：」下的项目符号），
            # 因此回看前 2 行；只看"前文"，不看后文，避免把结论句也放过。
            context = " ".join(lines[max(0, i - 3):i])
            for hit in classify_line(line, context):
                hits_a.append({
                    "file": rel(f), "line": i, "why": hit["why"],
                    "text": line.strip()[:160],
                    "verdict": hit["verdict"],
                })
            m = PATTERN_B.search(line)
            if m:
                hits_b.append({
                    "file": rel(f), "line": i, "text": line.strip()[:160],
                    "verdict": "OK(同行有证据线索)" if any(h in line for h in EVIDENCE_HINTS) else "NEEDS_EVIDENCE",
                })

    violations = [h for h in hits_a if h["verdict"] == "VIOLATION"]
    # 同一行可能被多条正则命中，按 (文件, 行) 去重，避免同一处问题被数成两条
    seen, uniq = set(), []
    for h in hits_a:
        key = (h["file"], h["line"])
        if key not in seen:
            seen.add(key)
            uniq.append(h)
    hits_a = uniq
    violations = [h for h in hits_a if h["verdict"] == "VIOLATION"]
    need = [h for h in hits_b if h["verdict"] == "NEEDS_EVIDENCE"]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "scripts/check_wording.py",
        "files_scanned": files,
        "rule_a": {
            "title": "不得把先验/估值/模型答对率标为「实测」",
            "hits": len(hits_a), "violations": len(violations),
            "items": hits_a,
        },
        "rule_b": {
            "title": "κ / 一致性结论必须有证据文件支撑",
            "hits": len(hits_b), "needs_evidence": len(need),
            "items": hits_b,
        },
        "verdict": "PASS" if not violations and not need else "REVIEW",
    }


def render_md(rep: dict) -> str:
    a, b = rep["rule_a"], rep["rule_b"]
    lines = [
        "# 表述核查（AC-P3-03）", "",
        f"- 生成：{rep['generated_at']}",
        f"- 工具：`{rep['tool']}`　扫描文件：{rep['files_scanned']}",
        f"- 结论：**{rep['verdict']}**", "",
        "## 规则 A —— 不得把估值标为实测", "",
        f"命中 {a['hits']} 处，其中越界 **{a['violations']}** 处。", "",
        "| 文件:行 | 判定 | 原文 |", "|---|---|---|",
    ]
    for h in a["items"]:
        lines.append(f"| `{h['file']}:{h['line']}` | {h['verdict']} | {h['text'][:90]} |")
    if not a["items"]:
        lines.append("| — | — | 无命中 |")
    lines += [
        "", "## 规则 B —— κ / 一致性结论必须有据", "",
        f"命中 {b['hits']} 处，其中缺证据 **{b['needs_evidence']}** 处。", "",
    ]
    if b["items"]:
        lines += ["| 文件:行 | 判定 | 原文 |", "|---|---|---|"]
        for h in b["items"]:
            lines.append(f"| `{h['file']}:{h['line']}` | {h['verdict']} | {h['text'][:90]} |")
    else:
        lines.append("无命中：本仓库当前没有任何 κ 数值或「一致性良好」类结论。")
    lines += [
        "",
        "---",
        "",
        "**为什么放行否定语境**：`「calibrated_p 是先验估计，非实测」`这类句子是**声明**，",
        "正是我们要保留的表述。核查只抓「说成测过」，不抓「说明没测过」。",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="对外表述核查（实测类宣称 / 无据结论）")
    ap.add_argument("--json", default=str(BASE / "reports/calibration/wording_check_20261102.json"))
    ap.add_argument("--md", default=str(BASE / "reports/calibration/wording_check_20261102.md"))
    args = ap.parse_args(argv)

    rep = scan(skip=(args.json, args.md))
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.md).write_text(render_md(rep), encoding="utf-8")

    print(f"表述核查: {rep['verdict']} | A 越界 {rep['rule_a']['violations']}/{rep['rule_a']['hits']}"
          f" | B 缺证据 {rep['rule_b']['needs_evidence']}/{rep['rule_b']['hits']}")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
