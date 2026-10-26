#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pilot_baseline.py — 试点基线冻结与复现（T1）。

用途
    对 batch040/耳鼻喉教师版试点的 6 个输入文件生成 SHA256 与结构化计数，
    产出 baseline_manifest.json + baseline_report.md；verify 命令用于试点期间
    确认源文件未被悄悄改动。

用法
    python scripts/pilot_baseline.py --batch batch040 \
        --out 中间产物/batch040/pilot/baseline_manifest.json
    python scripts/pilot_baseline.py verify \
        --manifest 中间产物/batch040/pilot/baseline_manifest.json

判定
    build  : 输入缺失/JSON 不可解析 → exit 2
    verify : 任一 SHA256 或关键计数不一致 → exit 1；全部一致 → exit 0
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

def _configure_stdio() -> None:
    """仅在 CLI 入口重配 stdout；import 时保持 pytest capture 可用。"""
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


BASE = Path(__file__).resolve().parent.parent
DEFAULT_BATCH = "batch040"
DEFAULT_OUT = BASE / "中间产物" / DEFAULT_BATCH / "pilot" / "baseline_manifest.json"

# 试点输入（路径相对工作区根目录）
INPUTS = {
    "review": "复习资料/耳鼻咽喉头颈外科学教师重点版/耳鼻咽喉头颈外科学教师重点版_主复习资料.md",
    "questions": "最终产物/batch040/ALL_questions_FIXED.json",
    "keypoints": "输入素材/大四上/耳鼻咽喉头颈外科学/耳鼻咽喉头颈外科学_教师重点_锚定清单_20261019.md",
    "blueprint": "中间产物/batch040/出题蓝图_batch040.md",
    "learning_value": "中间产物/batch040/learning_value_v2/items_v2_progress.json",
    "pilot": "中间产物/batch040/learning_value_pilot/item_v2_pilot.json",
}

TEXT_INPUTS = {"review", "keypoints", "blueprint"}
JSON_INPUTS = {"questions", "learning_value", "pilot"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- stats
def parse_review_stats(text: str) -> dict:
    """复习资料 MD 的结构计数。"""
    modules = len(re.findall(r"^## 模块\d+：", text, re.M))
    card_ids = re.findall(r"^#### .*?(K-M\d{2}-\d{3})", text, re.M)
    keypoints: set[int] = set()
    for m in re.finditer(r"^#### .*?K-M\d{2}-\d{3}.*?教师重点第([0-9、,，/]+)条", text, re.M):
        for x in re.split(r"[、,，/]", m.group(1)):
            if x.strip().isdigit():
                keypoints.add(int(x.strip()))
    for m in re.finditer(r"📌 重点原文（第(\d+)条）", text):
        keypoints.add(int(m.group(1)))

    appendix_start = text.find("## 附录五：主动回忆答案")
    appendix_rows = 0
    if appendix_start >= 0:
        tail = text[appendix_start:]
        appendix_rows = len(re.findall(r"^\|\s*(?:\d+|补)\s*\|", tail, re.M))

    return {
        "chars": len(text),
        "lines": text.count("\n") + 1,
        "modules": modules,
        "cards": len(set(card_ids)),
        "card_id_occurrences": len(card_ids),
        "keypoints": len(keypoints),
        "selftests": text.count("（答案见附录五）"),
        "appendix_answer_rows": appendix_rows,
        "callouts": len(re.findall(r"^> \[!", text, re.M)),
        "expand_blocks": len(re.findall(r"^#### 🔬 展开", text, re.M)),
        "images": text.count("!["),
        "table_rows": len(re.findall(r"^\|", text, re.M)),
        "ascii_blocks": text.count("```") // 2,
        "k_id_occurrences": len(re.findall(r"K-M\d{2}-\d{3}", text)),
    }


def parse_question_stats(data: list) -> dict:
    """200 题的结构计数。"""
    from collections import Counter

    modules = Counter()
    types = Counter()
    with_ref = 0
    supplemental = 0
    supplemental_questions = 0
    with_kc_slug = 0
    for q in data:
        if not isinstance(q, dict):
            continue
        modules[str(q.get("module") or "")] += 1
        types[str(q.get("type") or "")] += 1
        refs = q.get("keypoint_ref") or []
        if refs:
            with_ref += 1
        if any("补充" in str(r) for r in refs):
            supplemental += sum(1 for r in refs if "补充" in str(r))
            supplemental_questions += 1
        if q.get("kc_id"):
            with_kc_slug += 1
    return {
        "total": len(data),
        "keypoint_ref_present": with_ref,
        "modules": dict(sorted(modules.items())),
        "types": dict(sorted(types.items())),
        "supplemental_refs": supplemental,
        "supplemental_questions": supplemental_questions,
        "with_kc_slug": with_kc_slug,
    }


def parse_keypoint_stats(text: str) -> dict:
    """锚定清单第四节连续编号 1..125。"""
    start = text.find("## 四、统一锚定清单")
    end = text.find("## 五、原始标号对照", start if start >= 0 else 0)
    seg = text[start:end] if start >= 0 and end > start else ""
    items = re.findall(r"^(\d+)\.\s*【([^】]+)】", seg, re.M)
    ids = [int(n) for n, _ in items]
    from collections import Counter

    sources = Counter(src.split("·")[0] for _, src in items)
    return {
        "items": len(items),
        "first_id": min(ids) if ids else None,
        "last_id": max(ids) if ids else None,
        "continuous": sorted(ids) == list(range(1, len(ids) + 1)),
        "sources": dict(sorted(sources.items())),
    }


def parse_blueprint_stats(text: str) -> dict:
    """出题蓝图的模块×题型矩阵（每行最后一个数字=模块合计）。"""
    modules: dict[str, int] = {}
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            continue
        mod = re.sub(r"[*`\s]", "", cells[0])
        total = re.sub(r"[*`\s]", "", cells[-1])
        if re.fullmatch(r"M\d{2}", mod) and total.isdigit():
            modules[mod] = int(total)
    return {
        "modules": modules,
        "total": sum(modules.values()),
    }


def parse_learning_value_stats(data: list) -> dict:
    from collections import Counter

    status = Counter()
    source_quote = Counter()
    anchor = Counter()
    kc_ids = set()
    for q in data:
        if not isinstance(q, dict):
            continue
        lv = q.get("learning_value") or {}
        status[str(lv.get("review_status") or "missing")] += 1
        source_quote[str(lv.get("source_quote_status") or "missing")] += 1
        anchor[str(lv.get("anchor_status") or "missing")] += 1
        if q.get("kc_id"):
            kc_ids.add(str(q.get("kc_id")))
    return {
        "total": len(data),
        "review_status": dict(sorted(status.items())),
        "source_quote_status": dict(sorted(source_quote.items())),
        "anchor_status": dict(sorted(anchor.items())),
        "with_kc_slug": len(kc_ids),
    }


def parse_pilot_stats(data: list) -> dict:
    from collections import Counter

    status = Counter()
    source_quote = Counter()
    anchor = Counter()
    for q in data:
        if not isinstance(q, dict):
            continue
        lv = q.get("learning_value") or {}
        status[str(lv.get("review_status") or "missing")] += 1
        source_quote[str(lv.get("source_quote_status") or "missing")] += 1
        anchor[str(lv.get("anchor_status") or "missing")] += 1
    return {
        "total": len(data),
        "review_status": dict(sorted(status.items())),
        "source_quote_status": dict(sorted(source_quote.items())),
        "anchor_status": dict(sorted(anchor.items())),
    }


def stats_for(name: str, path: Path):
    if name in TEXT_INPUTS:
        return parse_review_stats(read_text(path)) if name == "review" else (
            parse_keypoint_stats(read_text(path)) if name == "keypoints" else parse_blueprint_stats(read_text(path))
        )
    data = json.loads(read_text(path))
    if name == "questions":
        return parse_question_stats(data)
    if name == "learning_value":
        return parse_learning_value_stats(data)
    if name == "pilot":
        return parse_pilot_stats(data)
    raise ValueError(f"unknown input: {name}")


def build_manifest(batch: str = DEFAULT_BATCH) -> dict:
    inputs = {}
    for name, rel in INPUTS.items():
        path = BASE / rel
        if not path.exists():
            raise FileNotFoundError(f"missing input[{name}]: {path}")
        text_lines = len(read_text(path).splitlines()) if name in TEXT_INPUTS else None
        inputs[name] = {
            "path": rel,
            "exists": True,
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "lines": text_lines,
            "stats": stats_for(name, path),
        }
    return {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "batch": batch,
        "scope": "耳鼻咽喉头颈外科学教师重点版（batch040）",
        "inputs": inputs,
        "summary": {
            "review_cards": inputs["review"]["stats"]["cards"],
            "review_keypoints": inputs["review"]["stats"]["keypoints"],
            "review_selftests": inputs["review"]["stats"]["selftests"],
            "review_appendix_rows": inputs["review"]["stats"]["appendix_answer_rows"],
            "questions": inputs["questions"]["stats"]["total"],
            "questions_with_keypoint_ref": inputs["questions"]["stats"]["keypoint_ref_present"],
            "supplemental_questions": inputs["questions"]["stats"]["supplemental_questions"],
            "keypoint_items": inputs["keypoints"]["stats"]["items"],
            "blueprint_total": inputs["blueprint"]["stats"]["total"],
            "learning_value_total": inputs["learning_value"]["stats"]["total"],
            "pilot_total": inputs["pilot"]["stats"]["total"],
        },
    }


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_report(manifest: dict, out: Path) -> None:
    lines = [
        "# MedAgentWork 试点基线冻结报告",
        "",
        f"> 批次：{manifest['batch']} ｜ 范围：{manifest['scope']} ｜ 生成：{manifest['generated_at']}",
        "> 用途：T1 基线冻结；任何源文件变动都会导致 `pilot_baseline.py verify` FAIL。",
        "",
        "## 1. 输入文件",
        "",
        "| 输入 | 路径 | SHA256（前 16 位） | 字节 | 行数 | 关键计数 |",
        "|---|---|---|---:|---:|---|",
    ]
    for name, info in manifest["inputs"].items():
        stats = info["stats"]
        if name == "review":
            key = f"{stats['cards']} 卡 / {stats['keypoints']} 重点 / {stats['selftests']} 自测 / {stats['appendix_answer_rows']} 答案行"
        elif name == "questions":
            key = f"{stats['total']} 题 / {stats['keypoint_ref_present']} 有引用 / {stats['supplemental_questions']} 含补充引用"
        elif name == "keypoints":
            key = f"{stats['items']} 条 / 连续={stats['continuous']}"
        elif name == "blueprint":
            key = f"{stats['total']} 题配额 / {len(stats['modules'])} 模块"
        elif name == "learning_value":
            key = f"{stats['total']} 题 / kc_id {stats['with_kc_slug']} 题 / exact {stats['source_quote_status'].get('exact', 0)}"
        else:
            key = f"{stats['total']} 题人工试点"
        lines.append(
            f"| {name} | `{info['path']}` | `{info['sha256'][:16]}` | {info['bytes']} | "
            f"{info['lines'] if info['lines'] is not None else '-'} | {key} |"
        )
    s = manifest["summary"]
    lines += [
        "",
        "## 2. 汇总",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 复习资料卡片 | {s['review_cards']} |",
        f"| 教师重点条数 | {s['review_keypoints']} |",
        f"| 主动回忆题 | {s['review_selftests']} |",
        f"| 附录答案行 | {s['review_appendix_rows']} |",
        f"| 题库题量 | {s['questions']} |",
        f"| 含补充引用题 | {s['supplemental_questions']} |",
        f"| 锚定清单条目 | {s['keypoint_items']} |",
        f"| 出题蓝图配额 | {s['blueprint_total']} |",
        f"| 题目 v2 数据 | {s['learning_value_total']} |",
        f"| 人工试点样本 | {s['pilot_total']} |",
        "",
        "## 3. 复现",
        "",
        "```bash",
        "python scripts/pilot_baseline.py verify \\",
        "  --manifest \"中间产物/batch040/pilot/baseline_manifest.json\"",
        "```",
        "",
        "> 说明：本报告只记录结构计数与哈希，不评价内容质量；12 维评分见 `review_scorecard`。",
        "",
    ]
    atomic_write(out, "\n".join(lines))


def verify_manifest(manifest_path: Path) -> bool:
    saved = json.loads(read_text(manifest_path))
    current = build_manifest(saved.get("batch", DEFAULT_BATCH))
    ok = True
    for name, old in saved.get("inputs", {}).items():
        new = current["inputs"].get(name)
        if not new:
            print(f"[FAIL] {name}: missing in current build")
            ok = False
            continue
        if old.get("sha256") != new.get("sha256"):
            print(f"[FAIL] {name}: sha256 changed")
            print(f"  saved  : {old.get('sha256')}")
            print(f"  current: {new.get('sha256')}")
            ok = False
        if old.get("stats") != new.get("stats"):
            print(f"[FAIL] {name}: stats changed")
            print(f"  saved  : {json.dumps(old.get('stats'), ensure_ascii=False)}")
            print(f"  current: {json.dumps(new.get('stats'), ensure_ascii=False)}")
            ok = False
    if ok:
        print("=== 基线校验 PASS：6 个输入 SHA256 与关键计数一致 ===")
    else:
        print("=== 基线校验 FAIL：源文件已变动，请升版本并重跑映射/评分 ===")
    return ok


def main() -> int:
    _configure_stdio()
    ap = argparse.ArgumentParser(description="试点基线冻结（T1）")
    ap.add_argument("--batch", default=DEFAULT_BATCH, help="批次号（无子命令时默认 build）")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="baseline_manifest.json 输出路径")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build", help="生成 baseline_manifest.json")
    b.add_argument("--batch", default=DEFAULT_BATCH)
    b.add_argument("--out", default=str(DEFAULT_OUT))
    v = sub.add_parser("verify", help="校验源文件未变动")
    v.add_argument("--manifest", required=True)
    args = ap.parse_args()

    if args.cmd == "verify":
        return 0 if verify_manifest(Path(args.manifest)) else 1

    batch = getattr(args, "batch", DEFAULT_BATCH)
    out = Path(getattr(args, "out", str(DEFAULT_OUT)))
    try:
        manifest = build_manifest(batch)
    except FileNotFoundError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"[FAIL] JSON 不可解析：{exc}", file=sys.stderr)
        return 2

    atomic_write(out, json.dumps(manifest, ensure_ascii=False, indent=2))
    report = out.with_name("baseline_report.md")
    write_report(manifest, report)
    s = manifest["summary"]
    print(f"✅ 基线已冻结：{s['review_cards']} 卡 / {s['review_keypoints']} 重点 / "
          f"{s['questions']} 题 / {s['review_selftests']} 自测")
    print(f"   manifest: {out}")
    print(f"   report  : {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
