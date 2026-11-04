#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ctx_fetch.py — 上下文指针取数（SA-6）

为什么有这个脚本（2026-11-04，SA-6）：
    「给对象发 ID、只内联引用」的落地件。Agent 不再整份读 CONTEXT/SOUL/教师重点原文，
    而是先拿 中间产物/{batch}/_ctx.md，需要某条规则/某条原文时按 ID 取 ≤2,000 chars。

支持四种指针：
    §SOUL#HC-22                 取 SOUL.md 中该小节（到下一个同级或更高级标题前）
    §CONTEXT#文件管理原则        任意 md 的命中标题小节
    KP-batch048-007             按 _kpidx.jsonl 定位教师重点原文（逐字，含字符偏移校验）
    ART:batch047/A3#L40-L90     产物文件行区间；文件不在原位时自动回退 archive/

退出码：0 命中 / 1 未找到 / 2 文件不可读
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

if "pytest" not in sys.modules:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

FILE_ALIAS = {"SOUL": "SOUL.md", "CONTEXT": "CONTEXT.md", "USER": "USER.md", "README": "README.md"}

# 产物角色 → glob 模式（glob 同时覆盖原位与 archive/ 回退；顺序即优先级）
ART_ROLES = {
    "a2": ["中间产物/{b}/ALL_questions.json"],
    "a3": ["质检报告/{b}/A3_质检报告.json", "质检报告/{b}_质检报告.json", "质检报告/{b}/*A3*.json"],
    "a4": ["最终产物/{b}/ALL_questions_FIXED.json"],
    "md": ["最终产物/{b}/ALL_questions_FIXED.md"],
    "log": ["最终产物/{b}/AGENT4_追溯日志.json"],
    "plan": ["中间产物/{b}/real_question_plan.json"],
    "lv": ["reports/validate/learning_value_{b}_final.json", "reports/validate/learning_value_{b}.json"],
    "gate": ["reports/gate/gate_check_{b}.json"],
}

KP_RE = re.compile(r"^KP-(batch\d{3})-(\d{3})$")
ART_RE = re.compile(r"^ART:(batch\d{3})/([A-Za-z0-9_]+)(?:#L(\d+)(?:-L?(\d+))?)?$")
SEC_RE = re.compile(r"^§([^#]+)#(.+)$")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _truncate(text: str, max_chars: int):
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + f"\n…（已截断，原 {len(text)} chars；继续读请加 --max-chars）", True


def resolve_section(base: Path, name: str, section: str, max_chars: int):
    path = base / FILE_ALIAS.get(name.strip().upper(), name.strip())
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    lines = _read(path).splitlines()
    idx = None
    level = 0
    for i, ln in enumerate(lines):
        s = ln.lstrip()
        if s.startswith("#") and section in ln:
            idx = i
            level = len(ln) - len(ln.lstrip("#"))
            break
    if idx is None:
        raise KeyError(f"未找到小节「{section}」于 {path.name}")
    out = [lines[idx]]
    for ln in lines[idx + 1:]:
        s = ln.lstrip()
        if s.startswith("#"):
            if len(ln) - len(ln.lstrip("#")) <= level:
                break
        out.append(ln)
    body = "\n".join(out).strip()
    text, truncated = _truncate(body, max_chars)
    return {"kind": "section", "pointer": f"§{name}#{section}", "source": str(path),
            "chars": len(text), "truncated": truncated, "text": text}


def _kp_index_candidates(base: Path, batch: str, index: str | None):
    if index:
        return [Path(index)]
    return [base / "中间产物" / batch / "_kpidx.jsonl",
            base / "archive" / "中间产物" / batch / "_kpidx.jsonl"]


def resolve_kp(base: Path, pointer: str, max_chars: int, index: str | None = None):
    m = KP_RE.match(pointer)
    if not m:
        raise KeyError(f"KP 指针格式应为 KP-batchNNN-NNN: {pointer}")
    batch, no = m.group(1), m.group(2)
    idx_path = next((p for p in _kp_index_candidates(base, batch, index) if p.exists()), None)
    if idx_path is None:
        raise FileNotFoundError(f"未找到 KP 索引: 中间产物/{batch}/_kpidx.jsonl")
    rec = None
    for line in _read(idx_path).splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("id") == pointer:
            rec = row
            break
    if rec is None:
        raise KeyError(f"索引中无 {pointer}")
    src = base / rec["src"]
    if not src.exists():
        raise FileNotFoundError(f"原文不存在: {src}")
    text = _read(src)
    cand = text[rec["offset"]: rec["offset"] + rec["chars"]]
    if not cand.startswith(rec["text"][:12]):
        pos = text.find(rec["text"][:24])
        if pos < 0:
            raise KeyError(f"{pointer} 原文偏移校验失败（文件可能已变更）")
        cand = text[pos: pos + rec["chars"]]
    cand = cand.strip()
    out, truncated = _truncate(cand, max_chars)
    return {"kind": "kp", "pointer": pointer, "source": str(src), "line": rec["line"],
            "chars": len(out), "truncated": truncated, "text": out}


def resolve_art(base: Path, pointer: str, max_chars: int):
    m = ART_RE.match(pointer)
    if not m:
        raise KeyError(f"ART 指针格式应为 ART:batchNNN/ROLE[#Lx-Ly]: {pointer}")
    batch, role, start, end = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
    templates = ART_ROLES.get(role)
    if not templates:
        raise KeyError(f"未知产物角色 {role}（可用: {', '.join(sorted(ART_ROLES))}）")
    path = None
    for tpl in templates:
        pat = tpl.format(b=batch)
        for root in (base, base / "archive"):
            hits = sorted(root.glob(pat))
            if hits:
                path = hits[0]
                break
        if path:
            break
    if path is None:
        raise FileNotFoundError(f"{batch} 的 {role} 产物不存在（含 archive 回退）")
    lines = _read(path).splitlines()
    if start:
        s = max(1, int(start))
        e = min(len(lines), int(end)) if end else s
        body = "\n".join(lines[s - 1:e])
        locator = f"L{s}-L{e}"
    else:
        body = "\n".join(lines)
        locator = None
    text, truncated = _truncate(body, max_chars)
    return {"kind": "art", "pointer": pointer, "source": str(path), "locator": locator,
            "chars": len(text), "truncated": truncated, "text": text}


def fetch(pointer: str, base: Path = BASE, max_chars: int = 2000, index: str | None = None):
    ptr = pointer.strip()
    if ptr.startswith("§"):
        m = SEC_RE.match(ptr)
        if not m:
            raise KeyError("§ 指针格式应为 §FILE#小节名")
        return resolve_section(base, m.group(1), m.group(2), max_chars)
    if ptr.startswith("KP-"):
        return resolve_kp(base, ptr, max_chars, index)
    if ptr.startswith("ART:"):
        return resolve_art(base, ptr, max_chars)
    raise KeyError(f"无法识别的指针: {pointer}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="上下文指针取数（SA-6）")
    ap.add_argument("--id", required=True, help="指针：§SOUL#HC-22 / KP-batch048-001 / ART:batch047/A3#L1-L40")
    ap.add_argument("--max-chars", type=int, default=2000)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--index", default=None, help="自定义 _kpidx.jsonl 路径（默认按批次目录查找）")
    args = ap.parse_args(argv)

    try:
        res = fetch(args.id, BASE, args.max_chars, args.index)
    except (FileNotFoundError, KeyError) as exc:
        print(f"[NOT FOUND] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(res["text"])
        print(f"\n--- {res['pointer']} ｜ {res['source']}"
              f"{' ｜ ' + res['locator'] if res.get('locator') else ''} ｜ {res['chars']} chars", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
