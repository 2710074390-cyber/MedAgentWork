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
        [--no-anchors] [--json] [--source-text <原始教师文本，可重复>]

    --source-text 为可选、非阻断的文字来源审计；不提供时不会核验来源。
    --adaptive 启用严格逐条核验：--source-text 必须恰有一个可读取的教师原文文件，
    其中须有与旧清单对应的连续编号块（从1起至少5条）。每条资料须各有一行
    `📌 重点原文（第X条）：原文条目正文`，逐字照录；教材补写另用单行
    `📚 教材补写（第X条）：补写内容`。仅在同编号补写行核对旧清单的非原文事实。
    本模式不支持 --no-anchors 或 --allowlist；编号块须唯一且每条占一行，
    块外仅允许空行和不含硬事实的 Markdown 标题。结果仅为文本及数值词面检查，
    不证明语义完整或医学正确；无法可靠对应时失败。
    多个来源独立匹配，不跨文件拼接；仅比较文字，不判断医学正确性。
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


def audit_sources(md_text, paths):
    sources, errors = [], []
    for path in paths:
        try:
            text = Path(path).read_text(encoding="utf-8")
            if not text.strip():
                raise ValueError("文件为空")
            sources.append((path, text))
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append({"path": path, "error": str(exc)})
    results = []
    for number, texts in drop_lines(md_text).items():
        for text in texts:
            # 仅去除空白，不使用硬事实的单位同义词及标点转换。
            compact = re.sub(r"\s+", "", text)
            exact = [path for path, source in sources if text and text in source]
            formatted = [path for path, source in sources
                         if compact and compact in re.sub(r"\s+", "", source)]
            if exact:
                status, matches = "exact", exact
            elif formatted:
                status, matches = "formatting_only", formatted
            elif not compact or errors or not sources:
                status, matches = "unverified", []
            else:
                status, matches = "not_found", []
            results.append({"number": number, "text": text, "status": status,
                            "sources": matches})
    return {"sources": list(paths), "errors": errors, "results": results}


def adaptive_items(text, label, errors):
    lines = text.splitlines()
    entries = [(i, _NUM_RE.match(line)) for i, line in enumerate(lines) if _NUM_RE.match(line)]
    numbers = [int(match.group(1)) for _, match in entries]
    if len(numbers) < 5 or numbers != list(range(1, len(numbers) + 1)):
        errors.append(f"{label}须有唯一连续编号块（从1起至少5条），未核实")
        return None
    first, last = entries[0][0], entries[-1][0]
    entry_lines = {i for i, _ in entries}
    for i, line in enumerate(lines):
        if i in entry_lines or not line.strip():
            continue
        if (i < first or i > last) and re.match(r"^ {0,3}#{1,6}\s+\S", line) and not facts_of(line):
            continue
        errors.append(f"{label}第{i + 1}行包含块外或续行内容，未核实")
    return [(int(match.group(1)), lines[i].strip()) for i, match in entries]


def adaptive_visible_lines(text):
    in_comment = False
    fence = None
    for line in text.splitlines():
        if fence:
            if re.match(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*$", line):
                fence = None
            continue
        visible = ""
        pos = 0
        had_comment = in_comment or "<!--" in line
        while pos < len(line):
            if in_comment:
                end = line.find("-->", pos)
                if end < 0:
                    break
                in_comment = False
                pos = end + 3
            else:
                start = line.find("<!--", pos)
                if start < 0:
                    visible += line[pos:]
                    break
                visible += line[pos:start]
                in_comment = True
                pos = start + 4
        if had_comment:
            continue
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", visible)
        if marker:
            fence = marker.group(1)
            continue
        if re.match(r"^(?: {4}|\t| {0,3}>)", visible):
            continue
        yield visible


def adaptive_check(kp_raw, md_raw, paths, no_anchors, allowlist):
    errors = []
    items = adaptive_items(kp_raw, "旧清单", errors)
    source_items = None
    if no_anchors or allowlist:
        errors.append("自适应模式不支持 --no-anchors 或 --allowlist")
    if len(paths) != 1:
        errors.append("自适应模式需要恰好一个教师原文来源")
    else:
        try:
            source = Path(paths[0]).read_text(encoding="utf-8")
            source_items = adaptive_items(source, "教师原文", errors)
        except (OSError, UnicodeError) as exc:
            errors.append(f"教师原文未核实：{exc}")
    if not items or not source_items:
        errors.append("旧清单或教师原文缺少可识别的连续编号块，未核实")
    visible = "\n".join(adaptive_visible_lines(md_raw))
    drops = drop_lines(visible)
    supplements = {}
    for line in visible.splitlines():
        match = re.match(r"^\s*📚\s*教材补写[（(]第\s*(\d+)\s*条[）)][:：]\s*(.*)$", line)
        if match:
            supplements.setdefault(int(match.group(1)), []).append(match.group(2))
    partial = []
    if items and source_items:
        old = {n: _NUM_RE.match(text).group(2) for n, text in items}
        original = {n: _NUM_RE.match(text).group(2) for n, text in source_items}
        if set(old) != set(original):
            errors.append("旧清单与教师原文编号不一致，未核实")
        remaining = kp_raw.splitlines()
        for _, text in items:
            for index, line in enumerate(remaining):
                if line.strip() == text:
                    remaining[index] = ""
                    break
        if facts_of("\n".join(remaining)):
            errors.append("旧清单编号块外存在硬事实，未核实")
        for n in sorted(set(old) & set(original)):
            if not original[n].strip() or original[n] not in old[n]:
                errors.append(f"第{n}条旧清单未包含完整教师原文，未核实")
            if len(drops.get(n, [])) != 1 or drops[n][0] != original[n]:
                errors.append(f"第{n}条原文锚点缺失、重复或未逐字照录")
            extra_text = old[n].replace(original[n], "", 1) if original[n] in old[n] else old[n]
            for fact in facts_of(extra_text):
                if not any(present(normalize(text), fact) for text in supplements.get(n, [])):
                    partial.append((n, fact))
    return {"errors": errors, "partial_facts": partial,
            "scope": "仅文本及数值词面检查，不证明语义完整或医学正确性，需人工复核",
            "verdict": "FAIL" if errors or partial else "PASS"}


def main() -> int:
    ap = argparse.ArgumentParser(description="教师重点覆盖门禁（HC-20 / D0）")
    ap.add_argument("--keypoints", help="教师重点/复习大纲原文（.md/.txt）")
    ap.add_argument("--md", required=False, help="主复习资料 MD")
    ap.add_argument("--allowlist", help="豁免清单（每行一条硬事实，# 开头为注释）")
    ap.add_argument("--no-anchors", action="store_true", help="跳过编号条目锚点检查")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--adaptive", action="store_true", help="启用严格逐条自适应覆盖核验")
    ap.add_argument("--source-text", action="append", default=[],
                    help="原始教师文本（.md/.txt，可重复；仅非阻断来源审计）")
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

    kp_raw = kp.read_text(encoding="utf-8", errors="strict" if args.adaptive else "replace")
    md_raw = md_path.read_text(encoding="utf-8", errors="strict" if args.adaptive else "replace")
    if args.adaptive:
        result = adaptive_check(kp_raw, md_raw, args.source_text, args.no_anchors, args.allowlist)
        print(f"  自适应词面核验：{result['verdict']}（{result['scope']}）")
        for error in result["errors"]:
            print(f"  ❌ {error}")
        for number, fact in result["partial_facts"]:
            print(f"  ❌ 第{number}条教材补写缺少 {fact}")
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["verdict"] == "PASS" else 1
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

    source_audit = None
    if args.source_text:
        source_audit = audit_sources(md_raw, args.source_text)
        print("  来源审计（非阻断；仅文字匹配，不判断医学正确性）：")
        for error in source_audit["errors"]:
            print(f"     未读取来源 {error['path']}：{error['error']}")
        labels = {"exact": "精确匹配", "formatting_only": "仅排版规范化匹配",
                  "not_found": "未找到", "unverified": "未核验"}
        if not source_audit["results"]:
            print("     未检测到可审计的重点原文落点行，未核验")
        for result in source_audit["results"]:
            print(f"     第{result['number']}条：{labels[result['status']]}"
                  + (f" · 来源 {result['sources']}" if result['sources'] else ""))
        print("     未找到仅表示所提供的各来源中无匹配；来源可能不全或为截取文本。")

    print(f"\n=== 结果: {'PASS' if ok else 'FAIL'} · 缺失项 {n_fail} ===")
    if not ok:
        print("→ 回退 Agent 5：按 D0 在对应考点补 `📌 重点原文（第X条）：…` 落点行，"
              "原样保留数值/时间窗/并列与禁止结构；确非命题范围的细节写入 --allowlist 并注明理由。")

    if args.json:
        output = {
            "keypoints": str(kp), "md": str(md_path),
            "facts_total": len(kp_facts), "missing": missing,
            "allowed": allowed_hits, "missing_anchors": missing_anchors,
            "partial_facts": anchor_report["partial_facts"] if anchor_report else [],
            "verdict": "PASS" if ok else "FAIL",
        }
        if source_audit is not None:
            output["source_audit"] = source_audit
        print(json.dumps(output, ensure_ascii=False, indent=2))

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
