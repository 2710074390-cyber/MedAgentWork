# -*- coding: utf-8 -*-
"""HC 编号审计（P1-S6 / AC-P1-08）。

只做一件事：把「同一个 HC 编号被赋予了多个不同含义」的事实摆出来，
并给出每一处的原文位置，让治理有据可依。

为什么需要这个脚本而不是人工 grep：
  · `HC-6` 在 SOUL 里出现 5 次，其中 3 处是**不同 Agent 的不同规则**；
  · `HC-18` 有两处 `##` 级定义（配额 / 产物形态契约），一个编号两种义务；
  · `HC-19`、`HC-27`、`HC-29` 在提示词/skill 里被大量引用，但 SOUL 里没有定义。
人工看必然漏，而且没法回归——改完编号后没人能确认「双定义是不是真的没了」。

判定口径
--------
- **定义**：行首为 `## HC-x` 或表格行 `| **HC-x ...** |`（即真正规定义务的地方）
- **引用**：正文里出现的 `HC-x`，不算定义
- 同一编号有 ≥2 处定义 → `duplicate`
- 在提示词里被当规则用、但 SOUL 无定义 → `orphan_in_prompt`

用法
----
    python scripts/hc_audit.py            # 打印摘要
    python scripts/hc_audit.py --json reports/registry/hc_audit_20261102.json \
                              --md   reports/registry/hc_audit_20261102.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
SOUL = BASE / "SOUL.md"
PROMPT = BASE / "Prompt版本" / "MedGen_current_prompt.md"
SKILL_FILES = sorted((BASE / ".dsh" / "skills").rglob("SKILL.md")) if (BASE / ".dsh").exists() else []

# 定义行：`## HC-18 产物形态契约` 或 `| **HC-6** | Agent 1 | ...`
# 编号可带作用域后缀：HC-6.A1（Agent 1 的 HC-6）、HC-6.A4FIX。
# 作用域后缀是治理手段——同一编号在不同 Agent 下指不同义务时，用它区分，
# 而不是让一个编号背三个含义。
RE_SECTION = re.compile(r"^##\s+(HC-\d+[a-z]?(?:\.[A-Za-z0-9]+)?)(?:\s|：|:)(.*)$")
RE_TABLE = re.compile(r"^\|\s*\*\*(HC-\d+[a-z]?(?:\.[A-Za-z0-9]+)?)[^*]*\*\*\s*\|\s*([^|]*)\|")
RE_ANY = re.compile(r"HC-\d+[a-zA-Z]?(?:\.[A-Za-z0-9]+)?")

# 已废止标记：编号保留（别名可查），但不再计入活定义。
RETIRED_MARKERS = ("已废止", "已接管", "已由 HC-22", "superseded", "retired", "已废弃")

# 提示词里以 `### HC-x：标题` 形式出现的，属于「被当作规则使用」
RE_PROMPT_SECTION = re.compile(r"^###\s+(HC-\d+[a-z]?)[：:]\s*(.*)$")


def norm(num: str) -> str:
    """保留作用域后缀（HC-6.A1 与 HC-6.A4 是两个编号），去掉括号注释。"""
    m = re.match(r"(HC-\d+[a-z]?(?:\.[A-Za-z0-9]+)?)", num)
    return m.group(1) if m else num


def is_retired(line: str, title: str = "") -> bool:
    blob = f"{line} {title}"
    return any(m in blob for m in RETIRED_MARKERS)


def scan_soul(path: Path = SOUL) -> tuple[list[dict], list[dict]]:
    """返回 (定义列表, 引用列表)。"""
    defs, refs = [], []
    if not path.exists():
        return defs, refs
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = RE_SECTION.match(line)
        if m:
            defs.append({"number": norm(m.group(1)), "raw": m.group(1),
                         "line": i, "kind": "section", "title": m.group(2).strip()[:80],
                         "retired": is_retired(line, m.group(2))})
            continue
        m = RE_TABLE.match(line)
        if m:
            defs.append({"number": norm(m.group(1)), "raw": m.group(1),
                         "line": i, "kind": "table", "owner": m.group(2).strip()[:24],
                         "title": line.strip()[:80], "retired": is_retired(line)})
            continue
        for hit in RE_ANY.findall(line):
            refs.append({"number": norm(hit), "line": i})
    return defs, refs


def scan_prompt(path: Path = PROMPT) -> tuple[list[dict], list[dict]]:
    secs, refs = [], []
    if not path.exists():
        return secs, refs
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = RE_PROMPT_SECTION.match(line)
        if m:
            secs.append({"number": norm(m.group(1)), "line": i, "title": m.group(2).strip()[:70]})
            continue
        # 删除线里的编号是「别名对照表」的内容，不是引用：
        # `| PG-01 | ~~HC-1~~ | 主题 |` 说明旧编号已改，不能算它还活着。
        line = re.sub(r"~~[^~]*~~", "", line)
        for hit in RE_ANY.findall(line):
            refs.append({"number": norm(hit), "line": i})
    return secs, refs


def scan_skills(files: list[Path]) -> dict[str, int]:
    cnt: dict[str, int] = defaultdict(int)
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for hit in RE_ANY.findall(text):
            cnt[norm(hit)] += 1
    return dict(cnt)


def build() -> dict:
    soul_defs, soul_refs = scan_soul()
    prompt_secs, prompt_refs = scan_prompt()
    skill_cnt = scan_skills(SKILL_FILES)

    by_num: dict[str, list[dict]] = defaultdict(list)
    for d in soul_defs:
        by_num[d["number"]].append(d)

    retired_defs = {n: [d for d in v if d.get("retired")] for n, v in by_num.items()}
    retired_defs = {n: v for n, v in retired_defs.items() if v}
    # 只有「活定义」≥2 才算编号事故；已废止条目保留为别名，不再承担义务。
    duplicate = {n: [d for d in v if not d.get("retired")]
                 for n, v in by_num.items()}
    duplicate = {n: v for n, v in duplicate.items() if len(v) >= 2}

    prompt_nums = {s["number"] for s in prompt_secs} | {r["number"] for r in prompt_refs}
    # 孤儿 = 被当作规则引用（提示词或 skill），但 SOUL 里查不到定义。
    # 只查提示词会漏掉 HC-19：它只在 .dsh/skills 里出现，SOUL 里根本没有。
    # 父编号也算已定义：写了 HC-6.A1 / HC-6.A4 之后，裸 HC-6 的引用是合法别名，
    # 不能因为定义都带了作用域后缀就把父编号判成孤儿。
    defined = set(by_num) | {n.split(".")[0] for n in by_num}
    orphan_prompt = sorted(prompt_nums - defined)
    orphan_skill = sorted(set(skill_cnt) - defined)
    orphan = sorted(set(orphan_prompt) | set(orphan_skill))

    # 只有 SOUL 定义、任何地方都不再引用 → 可能是僵尸条目
    all_ref_nums = {r["number"] for r in soul_refs} | prompt_nums | set(skill_cnt)
    unused = sorted(n for n in by_num if n not in all_ref_nums - {n})

    numbers = sorted(by_num, key=lambda x: (int(re.sub(r"\D", "", x) or 0), x))
    rows = []
    for n in numbers:
        rows.append({
            "number": n,
            "defs": len(by_num[n]),
            "soul_lines": [d["line"] for d in by_num[n]],
            "titles": [d.get("title", "") for d in by_num[n]],
            "in_prompt": n in prompt_nums,
            "skill_refs": skill_cnt.get(n, 0),
        })
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "scripts/hc_audit.py",
        "sources": {"soul": str(SOUL.name), "prompt": str(PROMPT.relative_to(BASE)),
                    "skills": len(SKILL_FILES)},
        "soul_definition_count": len(soul_defs),
        "soul_numbers": len(by_num),
        "duplicate": {n: v for n, v in duplicate.items()},
        "duplicate_count": len(duplicate),
        "orphan_in_prompt": orphan_prompt,
        "orphan_in_skill": orphan_skill,
        "orphan": orphan,
        "orphan_count": len(orphan),
        "prompt_sections": prompt_secs,
        "rows": rows,
    }


def render_md(d: dict) -> str:
    L = [
        "# HC 编号审计（P1-S6 / AC-P1-08）", "",
        f"- 生成：{d['generated_at']}",
        f"- 工具：`{d['tool']}`",
        f"- SOUL 定义 {d['soul_definition_count']} 处，涉及 {d['soul_numbers']} 个编号",
        f"- **重复定义 {d['duplicate_count']} 个编号**　被引用但 SOUL 无定义 **{d['orphan_count']} 个**"
        f"（提示词 {len(d['orphan_in_prompt'])} / skill {len(d['orphan_in_skill'])}）",
        "",
        "---", "",
        "## 1. 重复定义（同一编号，多处义务）", "",
    ]
    if d["duplicate"]:
        L += ["| 编号 | 处数 | SOUL 行 | 各自含义 |", "|---|---|---|---|"]
        for n, v in sorted(d["duplicate"].items(), key=lambda kv: int(re.sub(r"\D", "", kv[0]) or 0)):
            titles = "；".join(f"L{x['line']} {x.get('title', '')[:40]}" for x in v)
            L.append(f"| **{n}** | {len(v)} | {', '.join(str(x['line']) for x in v)} | {titles} |")
    else:
        L.append("无。")

    L += ["", "### 逐条说明", ""]
    for n, v in sorted(d["duplicate"].items(), key=lambda kv: int(re.sub(r"\D", "", kv[0]) or 0)):
        L.append(f"**{n}**（{len(v)} 处）")
        for x in v:
            owner = f"责任方 `{x.get('owner')}`" if x.get("owner") else "小节"
            L.append(f"- L{x['line']}（{owner}）：{x.get('title', '')}")
        L.append("")

    L += ["---", "", "## 2. 被引用但 SOUL 无定义（孤儿编号）", ""]
    if d["orphan_in_skill"]:
        L += ["**只在 skill 里出现**（SOUL 里查不到，新 Agent 读 SOUL 会完全不知道有这条）："
              + "、".join(f"`{x}`" for x in d["orphan_in_skill"]), ""]
    if d["orphan_in_prompt"]:
        L += ["| 编号 | 提示词行 | 标题 |", "|---|---|---|"]
        for s in d["prompt_sections"]:
            if s["number"] in d["orphan_in_prompt"]:
                L.append(f"| **{s['number']}** | L{s['line']} | {s['title']} |")
        L += ["", "这些编号在提示词里被当硬约束使用，但 SOUL 里找不到定义——"
              "新 Agent 查 SOUL 查不到，只能靠读提示词猜。回写 SOUL 是本次治理的一项。"]
    else:
        L.append("无。")

    L += ["", "---", "", "## 3. 编号全景", "",
          "| 编号 | SOUL 定义处数 | 提示词 | skill 引用 | 备注 |", "|---|---|---|---|---|"]
    for r in d["rows"]:
        note = ""
        if r["defs"] >= 2:
            note = "**重复定义**"
        elif r["number"] in d["orphan"]:
            note = "SOUL 无定义"
        L.append(f"| {r['number']} | {r['defs']} | {'是' if r['in_prompt'] else '—'} | "
                 f"{r['skill_refs'] or '—'} | {note} |")

    L += ["", "---", "", "## 4. 治理动作", "",
          "按工作指令 P1-S6，处理三类问题：", "",
          "1. **重复定义**：不删原文、不改编号，只在 SOUL 里把「已失效」的那一处标注清楚"
          "（`HC-18` 配额条款已由 `HC-22` 接管，保留为别名以便 grep 命中）；"
          "同一编号下不同 Agent 的规则加作用域后缀（`HC-6.A1` / `HC-6.A4`）。",
          "2. **孤儿编号**：把 `HC-19`（插图契约）、`HC-27`（概念标注）、`HC-29`（干扰项协议）"
          "的定义回写 SOUL，与提示词对齐。",
          "3. **提示词编号**：提示词小节加 `PG-` 操作编号，`HC-` 保留为别名。"
          "`PG` 是「这一节在提示词里怎么操作」，`HC` 是「全局硬约束」——两者层级不同，"
          "混用会让同一个编号在不同文件里指不同的事。", "",
          "---", "",
          "*本报告只含编号、行号与标题，不含任何用户数据。*"]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HC 编号审计（P1-S6）")
    ap.add_argument("--json", default=str(BASE / "reports" / "registry" / "hc_audit_20261102.json"))
    ap.add_argument("--md", default=str(BASE / "reports" / "registry" / "hc_audit_20261102.md"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    d = build()
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.md).write_text(render_md(d), encoding="utf-8")

    if not args.quiet:
        print(f"SOUL 定义 {d['soul_definition_count']} 处 / {d['soul_numbers']} 个编号")
        print(f"重复定义 {d['duplicate_count']}: {sorted(d['duplicate'])}")
        print(f"SOUL 无定义但被引用 {d['orphan_count']}: {d['orphan']}")
        print(f"  其中仅提示词 {d['orphan_in_prompt']}")
        print(f"  其中仅 skill  {d['orphan_in_skill']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
