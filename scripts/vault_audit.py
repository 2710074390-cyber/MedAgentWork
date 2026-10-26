#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vault_audit.py —— Obsidian 库全量审计（只读）

产出：
  1. 断链（wikilink / md 相对链接指向不存在的目标）
  2. 孤儿笔记（无入链、且不在 _MOC 内）
  3. 同名文件（basename 冲突 → wikilink 歧义）
  4. 目录分布与体积
  5. 未被任何 MOC 覆盖的可见笔记

不修改任何文件；--json 输出到 reports/ 便于比对。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WIKI_RE = re.compile(r"!?\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")
MDLINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
CODE_FENCE_RE = re.compile(r"^```.*?^```", re.M | re.S)
INLINE_CODE_RE = re.compile(r"`[^`]*`")

# 已知附件后缀：只有这些才当文件路径处理，避免把 v1.0 之类当扩展名
ASSET_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".bmp", ".avif",
    ".pdf", ".docx", ".doc", ".xlsx", ".csv", ".mp4", ".html", ".json",
    ".txt", ".pptx", ".zip",
}

# 与 .obsidian/app.json 的 userIgnoreFilters 对齐（硬编码一份，避免解析复杂过滤语法）
IGNORE_PREFIX = [
    ".git", ".obsidian", ".dsh", ".github", ".workbuddy", ".workbuddy-ai",
    ".wrangler", ".pytest_cache", "__pycache__", ".trae-html-share-packages",
    "scripts", "tests", "functions", "schemas", "reports", "docs",
    "medagentwork-skill", "medagentwork-skill-extracted", "question_bank",
    "memory", "Prompt版本",
    "复习资料/_归档_旧写实产物", "复习资料/_归档_部署png中间产物",
    "复习资料/_试点插图", "复习资料/_配图需求", "复习资料/_MD修复备份",
    "GoldenSet",
]
IGNORE_NAMES = {
    "README.md", "CONTEXT.md", "SOUL.md", "USER.md",
    "medagentwork-skill-改进报告.md", "_tmp_release_notes_v2.1.md",
    "内科学_配图清单.md", "外科学（二）_配图清单.md", "妇产科学_配图清单.md",
    "急诊与灾难医学_配图清单.md", "耳鼻咽喉头颈外科学_配图清单.md",
}
# 体积大、非笔记的素材层：默认不计入「笔记库」统计，但列出
ASSET_DIRS = {"知识库素材", "assets", "复习资料", "Obsidian产物"}


def _load_filters() -> list[str]:
    """从 .obsidian/app.json 读取真实排除规则，脚本与 Obsidian 视图保持一致。"""
    cfg = ROOT / ".obsidian" / "app.json"
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        return list(data.get("userIgnoreFilters", []))
    except Exception:
        return []


def is_ignored(rel: Path) -> bool:
    s = rel.as_posix()
    if rel.name in IGNORE_NAMES:
        return True
    for raw in _load_filters():
        r = raw.strip()
        if not r or any(ch in r for ch in "*?[]"):
            continue
        rooted = r.startswith("/")          # "/xxx" = 相对 vault 根的路径规则
        p = r.strip("/")
        if not p:
            continue
        if rooted:
            if s == p or s.startswith(p + "/"):
                return True
        else:
            # 无前导斜杠：Obsidian 按文件名匹配（任意目录下同名文件）
            if rel.name == p or s == p or s.startswith(p + "/"):
                return True
    return False


def iter_notes(include_assets: bool):
    for p in ROOT.rglob("*.md"):
        rel = p.relative_to(ROOT)
        if is_ignored(rel):
            continue
        if not include_assets and rel.parts and rel.parts[0] in ASSET_DIRS:
            continue
        yield p, rel


def strip_code(text: str) -> str:
    """去掉围栏代码块与行内代码——里面的 [[...]] 是示例而非真链接。"""
    text = CODE_FENCE_RE.sub("", text)
    return INLINE_CODE_RE.sub("", text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--include-assets", action="store_true",
                    help="把 Obsidian产物/复习资料/知识库素材 也计入笔记统计")
    args = ap.parse_args()

    all_md = [p for p in ROOT.rglob("*.md")
              if not any(part in {".git", ".obsidian", "node_modules"} for part in p.parts)]
    # 全库 basename 索引（链接解析用，含被忽略的目录——Obsidian 的链接解析不认过滤器）
    by_basename = defaultdict(list)
    by_relpath = {}
    for p in all_md:
        rel = p.relative_to(ROOT)
        by_basename[p.stem].append(rel)
        by_relpath[rel.with_suffix("").as_posix()] = rel

    # 附件文件名索引（供 wikilink 按名兜底解析）
    asset_names = set()
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in ASSET_EXTS:
            asset_names.add(p.name)

    notes = list(iter_notes(args.include_assets))
    note_rels = {rel for _, rel in notes}

    broken = []
    ambiguous = []
    inbound = defaultdict(int)
    outbound_total = 0

    for p, rel in notes:
        text = strip_code(p.read_text(encoding="utf-8", errors="replace"))
        targets = []
        for m in WIKI_RE.finditer(text):
            targets.append(("wiki", m.group(1).strip()))
        for m in MDLINK_RE.finditer(text):
            t = m.group(1).strip()
            if t.startswith(("http://", "https://", "mailto:", "#")):
                continue
            targets.append(("md", t))

        for kind, t in targets:
            # 表格内的别名分隔符写作 \|，Obsidian 视为合法转义，需去掉尾部反斜杠
            t = t.rstrip("\\").split("|")[0].strip().rstrip("/")
            if not t:
                continue
            outbound_total += 1
            key = t
            if key.endswith(".md"):
                key = key[:-3]
            # 非 md 目标（图片/附件）：只有已知附件后缀才按文件系统判断，
            # 否则 `xxx_v1.0` 这类带点号的名字会被误当成文件扩展名。
            suffix = Path(t).suffix.lower()
            if suffix in ASSET_EXTS:
                local_file = (rel.parent / t)
                if local_file.exists() or (ROOT / t).exists():
                    continue
                # wikilink 图片可只写文件名，Obsidian 会全库按名兜底解析
                if kind == "wiki" and "/" not in t and t in asset_names:
                    continue
                broken.append({"note": rel.as_posix(), "target": t, "kind": "asset"})
                continue
            # 绝对（相对 vault 根）路径优先
            hit = by_relpath.get(key)
            if hit is None and "/" not in key:
                cands = by_basename.get(Path(key).name, [])
                if len(cands) == 1:
                    hit = cands[0]
                elif len(cands) > 1:
                    ambiguous.append({"note": rel.as_posix(), "target": t,
                                      "candidates": [c.as_posix() for c in cands]})
                    hit = cands[0]
            if hit is None:
                # 相对当前笔记目录
                local = (rel.parent / (key + ".md"))
                if local.exists():
                    hit = local
            if hit is None:
                broken.append({"note": rel.as_posix(), "target": t, "kind": kind})
            elif hit in note_rels:
                inbound[hit] += 1

    dup = {k: [c.as_posix() for c in v] for k, v in by_basename.items() if len(v) > 1}

    orphans = sorted(r.as_posix() for r in note_rels
                     if inbound.get(r, 0) == 0 and not r.parts[0] == "_MOC")

    # 目录分布
    dist = defaultdict(lambda: {"md": 0, "bytes": 0})
    for p, rel in notes:
        top = rel.parts[0] if len(rel.parts) > 1 else "(根目录)"
        dist[top]["md"] += 1
        dist[top]["bytes"] += p.stat().st_size

    print("=" * 62)
    print("Obsidian 库审计（只读）")
    print("=" * 62)
    print(f"纳入统计的笔记：{len(notes)} 个")
    print(f"全库 md 文件：{len(all_md)} 个（含被忽略目录）")
    print(f"出链总数：{outbound_total}")
    print()
    print("── 目录分布 ──")
    for k, v in sorted(dist.items(), key=lambda x: -x[1]["md"]):
        print(f"  {v['md']:>4} md  {v['bytes']/1024:>8.0f} KB   {k}")
    print()
    print(f"── 断链：{len(broken)} ──")
    for b in broken[:60]:
        print(f"  {b['note']}  ->  {b['target']}")
    if len(broken) > 60:
        print(f"  ... 另有 {len(broken)-60} 条")
    print()
    print(f"── 同名歧义：{len(ambiguous)} ──")
    seen = set()
    for a in ambiguous:
        sig = (a["target"], tuple(a["candidates"]))
        if sig in seen:
            continue
        seen.add(sig)
        print(f"  [[{a['target']}]] ← {a['note']}  候选={a['candidates']}")
    print()
    print(f"── 孤儿笔记（无入链）：{len(orphans)} ──")
    for o in orphans[:60]:
        print(f"  {o}")
    if len(orphans) > 60:
        print(f"  ... 另有 {len(orphans)-60} 个")
    print()
    print(f"── 同名文件（全库，{len(dup)} 组）──")
    for k, v in sorted(dup.items())[:40]:
        print(f"  {k}.md  x{len(v)}")
        for c in v:
            print(f"      {c}")

    if args.json:
        out = ROOT / args.json
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "notes": len(notes), "all_md": len(all_md),
            "broken": broken, "ambiguous": ambiguous,
            "orphans": orphans, "duplicates": dup,
            "dist": {k: v for k, v in dist.items()},
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
