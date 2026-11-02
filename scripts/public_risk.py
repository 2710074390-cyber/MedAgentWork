#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""public_risk.py — 公开风险清单（P8-S2，2026-11-02）

回答一个问题：**哪些对外可见/可部署的文件里，出现了 license 不明确的真题？**

做法不是"看文件名猜"，而是拿 license matrix 里的真题 qid 去**逐个文件匹配**：
命中的 qid 数、其中 license=unknown 的数量，就是这个文件的实际暴露面。

口径说明：
  - "公开站"= 部署目录下的文件（`index.html` 及站点资源）；
  - "可部署但未发布"= `最终产物/` 下的 HTML/MD，当前不在站点内，但一旦被打包就会公开；
  - Obsidian 产物默认视为私有库，不进本清单（除非显式 --include）。

用法：
  python scripts/public_risk.py
  python scripts/public_risk.py --include "Obsidian产物/**/*.md"
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
MATRIX = BASE / "reports/compliance/license_matrix_20261102.json"

# 站点根 + 可部署产物（会随站点/打包一起公开的东西）
DEFAULT_GLOBS = ["index.html", "最终产物/**/*.html", "最终产物/**/*.md"]
SITE_FILES = {"index.html"}


def load_real_qids() -> dict[str, dict]:
    data = json.loads(MATRIX.read_text(encoding="utf-8"))
    out = {}
    for r in data["rows"]:
        if r["real"]:
            out[r["qid"]] = r
    return out


def candidate_files(globs: list[str]) -> list[Path]:
    seen, files = set(), []
    for g in globs:
        for p in BASE.glob(g):
            if p.is_file() and p.suffix.lower() in (".html", ".htm", ".md", ".json"):
                key = p.resolve()
                if key not in seen:
                    seen.add(key)
                    files.append(p)
    return sorted(files)


def scan_file(path: Path, real: dict[str, dict]) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    hit = sorted({q for q in real if q in text})
    unknown = [q for q in hit if not real[q]["license_known"]]
    kinds = defaultdict(int)
    for q in unknown:
        kinds[real[q]["origin_kind"]] += 1
    try:
        rel = str(path.relative_to(BASE)).replace("\\", "/")
    except ValueError:
        rel = str(path).replace("\\", "/")
    return {
        "file": rel,
        "exposure": "公开站" if rel in SITE_FILES else "可部署未发布",
        "size_kb": round(path.stat().st_size / 1024, 1),
        "real_qids": len(hit),
        "unclear_qids": len(unknown),
        "unclear_by_origin": dict(kinds),
        "samples": unknown[:5],
        "hit_samples": hit[:5],
    }


def render_md(rows: list[dict], meta: dict) -> str:
    exposed = [r for r in rows if r["unclear_qids"] > 0]
    site = [r for r in exposed if r["exposure"] == "公开站"]
    lines = [
        "# 公开风险清单（P8-S2）", "",
        f"- 生成：{meta['generated_at']}",
        f"- 工具：`scripts/public_risk.py`",
        f"- 依据：`reports/compliance/license_matrix_20261102.json`（真题 {meta['real_total']} 题，其中 license 未记录 {meta['unknown_total']} 题）",
        f"- 扫描文件：{meta['scanned']} 个",
        "",
        f"**结论：公开站命中 {len(site)} 个文件，含 unclear 真题 {sum(r['unclear_qids'] for r in site)} 题；"
        f"可部署未发布文件命中 {len(exposed) - len(site)} 个。**",
        "",
        "## 1. 逐文件暴露面", "",
        "| 文件 | 暴露级别 | 真题 qid 数 | 其中 license 不明 | 来源构成 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        if r["real_qids"] == 0:
            continue
        kinds = "、".join(f"{k} {v}" for k, v in r["unclear_by_origin"].items()) or "—"
        lines.append(f"| `{r['file']}` | {r['exposure']} | {r['real_qids']} | **{r['unclear_qids']}** | {kinds} |")
    if not any(r["real_qids"] for r in rows):
        lines.append("| — | — | 0 | 0 | 扫描范围内无真题 qid |")

    lines += ["", "## 2. 处置建议", ""]
    if site:
        lines += [
            "### 2.1 公开站（需立即处置）", "",
            "| 文件 | 建议 |", "|---|---|",
        ]
        for r in site:
            lines.append(f"| `{r['file']}` | 下架含 unclear 真题的页面，或改为只放原创题；**下架/改写需用户确认后再执行** |")
    else:
        lines += [
            "### 2.1 公开站", "",
            "**当前公开站（`index.html`）未命中任何真题 qid** —— 站内是介绍页，不含题面。",
            "这意味着现阶段没有「公开即侵权」的暴露，风险集中在「下一步要不要把题库搬上站」这个决策上。",
            "",
        ]
    lines += [
        "### 2.2 可部署但未发布", "",
        "| 文件 | 建议 |", "|---|---|",
    ]
    for r in exposed:
        if r["exposure"] == "公开站":
            continue
        lines.append(
            f"| `{r['file']}` | {r['unclear_qids']} 题 license 不明；发布前须①补授权状态 ②或替换为原创题 ③或从构建产物中剔除 |")
    if not any(r["exposure"] == "可部署未发布" and r["unclear_qids"] for r in exposed):
        lines.append("| — | 无 |")
    lines += [
        "", "## 3. 局限（必须与结论一起读）", "",
        "1. **只按 qid 匹配**。题目若被复制到别的文件而丢了 qid，本工具**抓不到**（例如手动粘贴的题面）。",
        "2. **只管仓库内文件**。已经发布到 GitHub Pages / Cloudflare 的历史版本、镜像、CDN 缓存不在扫描范围。",
        "3. **不做法律定性**。license=unknown 意味着「仓库里没有记录」，不等于「不能发」，也不等于「能发」。",
        "4. 判定基于题目自带标注；漏标的真题会被当成原创，从而不被计入暴露面。",
        "",
        "---", "",
        "本清单只含文件路径、qid 与计数，不含任何用户数据。",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="公开风险清单（哪些文件含 unclear-license 真题）")
    ap.add_argument("--include", nargs="*", default=[], help="额外扫描的 glob（默认只扫站点与 最终产物）")
    ap.add_argument("--json", default=str(BASE / "reports/compliance/public_risk_20261102.json"))
    ap.add_argument("--md", default=str(BASE / "reports/compliance/public_risk_20261102.md"))
    args = ap.parse_args(argv)

    if not MATRIX.exists():
        print("[FAIL] 先运行 scripts/license_matrix.py 生成矩阵", file=sys.stderr)
        return 2
    real = load_real_qids()
    files = candidate_files(DEFAULT_GLOBS + args.include)
    rows = [r for r in (scan_file(f, real) for f in files) if r]

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "scripts/public_risk.py",
        "scanned": len(rows),
        "real_total": len(real),
        "unknown_total": sum(1 for r in real.values() if not r["license_known"]),
    }
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps({"meta": meta, "files": rows}, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    Path(args.md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.md).write_text(render_md(rows, meta), encoding="utf-8")

    site = [r for r in rows if r["exposure"] == "公开站" and r["unclear_qids"]]
    print(f"扫描 {len(rows)} 文件 | 公开站命中 {len(site)} | "
          f"可部署未发布命中 {sum(1 for r in rows if r['exposure'] != '公开站' and r['unclear_qids'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
