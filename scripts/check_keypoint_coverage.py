#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_keypoint_coverage.py — 教师重点覆盖门禁（HC-20 / D0 · 2026-10-18）

用途
    机械核验「教师重点/复习大纲原文」里的**硬事实**（数值、时间窗、分级界值、
    剂量、百分比、长度/距离）是否在复习资料 MD 中**原样出现**，并核验每个教师重点
    编号条目都有落点锚点（`📌 重点原文（第X条）` / `（教师重点第X条）`）。
    根治"概括性改写导致教师重点细节丢失"。

驱动缺陷（batch039 实证）
    教师重点第15条「突发性聋应尽早进行听力学检查和专科评估，可在发病2周内考虑
    糖皮质激素初始治疗；恢复不完全者可在发病2～6周评估鼓室内糖皮质激素挽救治疗」
    在复习资料里被概括为「耳科急症，激素一线」——两个时间窗全部丢失。

判定
    FAIL  = 带单位的硬事实在复习资料中缺失（或重点编号条目缺锚点）→ 退出码 1，不得交付
    WARN  = 无单位裸数字、中文数字列举（三处/四度/五组）——本脚本不判定（人工复核）
    SKIPPED = 未提供教师重点原文 / 原文中无可判定硬事实 → 退出码 2（显式降级，不视为通过）

用法
    python scripts/check_keypoint_coverage.py \
        --keypoints "输入素材/大四上/{科目}/{科目}_教师重点_*.md" \
        --md "复习资料/{科目}教学计划版/{科目}_主复习资料.md" \
        [--allowlist <文件，每行一条可豁免的硬事实，'#' 开头为注释>] \
        [--no-anchors] [--json]

    教师重点原文支持 .md / .txt（.docx 请先转 md）。
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- 归一化
_TRANS = str.maketrans({
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
    "（": "(", "）": ")", "％": "%", "．": ".",
    "－": "-", "—": "-", "–": "-", "─": "-", "﹣": "-", "〜": "~", "～": "~",
    "Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "Ⅴ": "V",
    "Ⅵ": "VI", "Ⅶ": "VII", "Ⅷ": "VIII", "Ⅸ": "IX", "Ⅹ": "X",
})

# 单位同义（长词先替换，避免 "分钟"→"分" 后再被 "时" 误伤）
_UNIT_ALIASES = [
    ("厘米", "cm"), ("公分", "cm"), ("毫米", "mm"), ("分钟", "分"), ("小时", "时"),
    ("星期", "周"), ("个月", "月"), ("千克", "kg"), ("毫克", "mg"), ("毫升", "ml"),
    ("摄氏度", "度"), ("天", "日"), ("mins", "分"), ("min", "分"),
    ("hrs", "时"), ("hr", "时"), ("sec", "秒"), ("week", "周"), ("month", "月"),
    ("year", "年"), ("day", "日"), ("℃", "度"),
]

# 单位白名单（组合单位在前，避免 "mmHg" 被 "mm" 截断、"mg" 被 "g" 截断）
_UNITS = ("mmHg", "cmH2O", "IU", "cm", "mm", "mg", "kg", "ml", "dB", "Hz",
          "min", "%", "°", "度", "分", "时", "日", "周", "月", "年", "岁",
          "次", "倍", "条", "个", "组", "区", "期", "级", "张", "瓶", "支",
          "片", "g", "m")
_FACT_RE = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+)?(?:~\d+(?:\.\d+)?)*)(?:" + "|".join(_UNITS) + r")"
)
_SEP_RE = re.compile(r"[~\-–—─至到]")
_NUM_RE = re.compile(r"^\s*(\d+)\s*\\?\s*[\.、]\s*(.+)$")


def normalize(text: str) -> str:
    t = text.translate(_TRANS)
    for a, b in _UNIT_ALIASES:
        t = t.replace(a, b)
    t = _SEP_RE.sub("~", t)
    t = re.sub(r"[\s\u3000]+", "", t)   # 去空白（含数字与单位之间的空格）
    return t


def facts_of(text: str):
    """返回 {归一化硬事实: 出现次数}"""
    out = {}
    for m in _FACT_RE.finditer(normalize(text)):
        out[m.group(0)] = out.get(m.group(0), 0) + 1
    return out


def present(hay: str, fact: str) -> bool:
    """词边界匹配：前后不得紧邻数字/小数点，防 '2周' 误命中 '12周'"""
    return re.search(r"(?<![\d.])" + re.escape(fact) + r"(?![\d])", hay) is not None


def find_emphasis_items(lines):
    """末尾一段连续编号块（从 1 起、≥5 条、允许 1 行空行间隔）= 教师重点强调清单"""
    runs = []
    i = 0
    while i < len(lines):
        m = _NUM_RE.match(lines[i])
        if not m:
            i += 1
            continue
        run = [(int(m.group(1)), lines[i].strip())]
        expect = run[0][0] + 1
        j, blanks = i + 1, 0
        while j < len(lines):
            if not lines[j].strip():
                blanks += 1
                if blanks > 1:
                    break
                j += 1
                continue
            m2 = _NUM_RE.match(lines[j])
            if m2 and int(m2.group(1)) == expect:
                run.append((expect, lines[j].strip()))
                expect += 1
                blanks = 0
                j += 1
                continue
            break
        runs.append((run, j))
        i = j
    cand = [r for r, _ in runs if r and r[0][0] == 1 and len(r) >= 5]
    return cand[-1] if cand else None


def anchors_in(md_text: str):
    nums = set()
    for m in re.finditer(r"重点原文（第\s*([0-9]+)\s*条", md_text):
        nums.add(int(m.group(1)))
    for m in re.finditer(r"教师重点第\s*([0-9]+(?:[、,，/]\s*[0-9]+)*)\s*条", md_text):
        for x in re.split(r"[、,，/]", m.group(1)):
            if x.strip().isdigit():
                nums.add(int(x.strip()))
    return nums


# 落点行：`📌 重点原文（第X条）：{照录原文关键句}`（D0 强制格式，用于上下文级核验）
_ANCHOR_LINE_RE = re.compile(r"^\s*📌\s*重点原文[（(]第\s*(\d+)\s*条[）)][:：]?\s*(.*)$")


def drop_lines(md_text: str):
    """返回 {重点编号: [落点行正文, ...]}"""
    out = {}
    for ln in md_text.splitlines():
        m = _ANCHOR_LINE_RE.match(ln)
        if m:
            out.setdefault(int(m.group(1)), []).append(m.group(2))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="教师重点覆盖门禁（HC-20 / D0）")
    ap.add_argument("--keypoints", help="教师重点/复习大纲原文（.md/.txt）")
    ap.add_argument("--md", required=False, help="主复习资料 MD")
    ap.add_argument("--allowlist", help="豁免清单（每行一条硬事实，# 开头为注释）")
    ap.add_argument("--no-anchors", action="store_true", help="跳过编号条目锚点检查")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    print("=== 教师重点覆盖门禁 check_keypoint_coverage.py（HC-20 / D0）===")

    if not args.keypoints:
        print("SKIPPED —— 未提供 --keypoints（本批次无教师重点/复习大纲输入，不视为通过）")
        return 2
    kp = Path(args.keypoints)
    if not kp.exists():
        if args.keypoints.endswith((".docx", ".doc")):
            print(f"ERROR —— .docx 不受支持，请先转为 .md/.txt：{args.keypoints}")
        else:
            print(f"ERROR —— 教师重点原文不存在：{args.keypoints}")
        return 2
    if not args.md:
        print("ERROR —— 缺少 --md（主复习资料 MD）")
        return 2
    md_path = Path(args.md)
    if not md_path.exists():
        print(f"ERROR —— 主复习资料不存在：{args.md}")
        return 2

    kp_raw = kp.read_text(encoding="utf-8", errors="replace")
    md_raw = md_path.read_text(encoding="utf-8", errors="replace")
    md_norm = normalize(md_raw)

    allow = set()
    if args.allowlist and Path(args.allowlist).exists():
        for ln in Path(args.allowlist).read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                allow.add(normalize(ln))

    # --- 硬事实覆盖 ---
    kp_facts = facts_of(kp_raw)
    missing = sorted(f for f in kp_facts if f not in allow and not present(md_norm, f))
    allowed_hits = sorted(f for f in kp_facts if f in allow)

    # --- 强调清单：逐条落点 + 落点行上下文级硬事实核验 ---
    lines = kp_raw.splitlines()
    items = find_emphasis_items(lines)
    missing_anchors, partial, anchor_report = [], [], None
    if items:
        item_txt = {n: txt for n, txt in items}
        nums = [n for n, _ in items]
        drop = drop_lines(md_raw)
        markers = anchors_in(md_raw)
        if not args.no_anchors:
            missing_anchors = [n for n in nums if n not in drop]
        for n in nums:
            if n in drop:          # 有落点行 → 上下文级核验（防"别处命中"的假通过）
                seg = normalize("".join(drop[n]))
                for f in facts_of(item_txt[n]):
                    if f not in allow and not present(seg, f):
                        partial.append((n, f))
        anchor_report = {
            "items": f"1..{max(nums)}（{len(nums)} 条）",
            "drop_lines": sorted(drop),
            "markers": sorted(markers),
            "missing_anchors": missing_anchors,
            "partial_facts": partial,
        }
    else:
        print("  ℹ️ 未检测到连续编号的「强调清单」块 → 逐条锚点检查 SKIPPED（仅做全文级硬事实覆盖）")

    fails = list(missing) + [f"落点行未照录：第{n}条·{f}" for n, f in partial]
    if missing_anchors:
        fails.append(f"缺落点行条目 {missing_anchors}")

    ok = not fails
    n_fail = len(set(fails))

    print(f"  教师重点原文：{kp}")
    print(f"  复习资料      ：{md_path}")
    print(f"  硬事实（带单位）：{len(kp_facts)} 类 · 缺失 {len(missing)}"
          + (f" · 豁免 {len(allowed_hits)}" if allowed_hits else ""))
    if missing:
        print("  ❌ 缺失硬事实（必须补写到复习资料对应考点，原样保留）：")
        for f in missing:
            print(f"     - {f}")
    if anchor_report and not args.no_anchors:
        print(f"  强调清单：{anchor_report['items']} · 落点行 {anchor_report['drop_lines'] or '无'}"
              f" · 考点锚点 {anchor_report['markers'] or '无'}")
        if missing_anchors:
            print(f"  ❌ 缺落点行的重点条目：{missing_anchors}"
                  "（每条重点须补 `📌 重点原文（第X条）：{照录原文关键句}`）")
    if partial:
        print("  ❌ 落点行未照录的硬事实（条目·事实）：")
        for n, f in partial:
            print(f"     - 第{n}条 · {f}")
    if allowed_hits:
        print(f"  ⚠️ 已豁免（allowlist，请确认理由已写在该文件注释里）：{allowed_hits}")

    print(f"\n=== 结果: {'PASS' if ok else 'FAIL'} · 缺失项 {n_fail} ===")
    if not ok:
        print("→ 回退 Agent 5：按 D0 在对应考点补 `📌 重点原文（第X条）：…` 落点行，"
              "原样保留数值/时间窗/并列与禁止结构；确非命题范围的细节写入 --allowlist 并注明理由。")

    if args.json:
        print(json.dumps({
            "keypoints": str(kp), "md": str(md_path),
            "facts_total": len(kp_facts), "missing": missing,
            "allowed": allowed_hits, "missing_anchors": missing_anchors,
            "partial_facts": anchor_report["partial_facts"] if anchor_report else [],
            "verdict": "PASS" if ok else "FAIL",
        }, ensure_ascii=False, indent=2))

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
