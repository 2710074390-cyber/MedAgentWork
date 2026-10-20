#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MedAgentWork — 视觉一致性检查（设计令牌合规门禁）

与 `verify_produce_rules.py` 同为门禁：产物进入 `大三下/` 前应通过。

检查项：
  [FAIL] 令牌缺失      —— 文件无 :root 令牌块（无法参与主题切换）
  [FAIL] 标题层级不完整 —— h1~h4 未全部定义（h2~h4 会落到浏览器默认样式）
  [FAIL] 主题不对称     —— 深色主题缺少浅色主题里存在的语义令牌
  [WARN] 硬编码色值     —— 绕过令牌直接写 hex/rgb，阈值见 --max-hardcoded
  [WARN] 非标尺度       —— 字号/圆角不在令牌尺度内

用法：
  python scripts/check_visual.py --all                # 扫描全部模板与产物
  python scripts/check_visual.py index.html scripts/quiz_template.html
  python scripts/check_visual.py --all --strict       # WARN 也计入退出码
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- 常量

# 默认扫描集：模板（源）+ 线上产物
DEFAULT_TARGETS = [
    "index.html",
    "scripts/quiz_template.html",
    "scripts/build_html_final_template.html",
    "scripts/render_qbank_html.py",
    "知识库素材/review_template.html",
    "知识库素材/render_review.py",
]

# 令牌尺度（与 design-tokens.css 保持一致）
ALLOWED_FONT_SIZES = {12.0, 13.0, 14.5, 16.0, 18.0, 22.0, 28.0, 34.0}
ALLOWED_RADII = {6.0, 10.0, 14.0, 999.0}
# 字号允许的浮动（rem/em/clamp 不参与检查）
FONT_TOLERANCE = 0.51

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
ROOT_RE = re.compile(r":root(?:\s*\[[^\]]*\])?\s*\{([^}]*)\}", re.S)
DARK_ROOT_RE = re.compile(
    r'(?::root(?:\s*\[[^\]]*\])?\s*,\s*)*:root\s*\[data-theme="(dark|obsidian)"\]\s*\{([^}]*)\}',
    re.S)
VAR_DEF_RE = re.compile(r"(--[\w-]+)\s*:")
VAR_USE_RE = re.compile(r"var\((--[\w-]+)")
FONT_SIZE_RE = re.compile(r"font-size\s*:\s*([\d.]+)px")
RADIUS_RE = re.compile(r"border-radius\s*:\s*([\d.]+)px")

# 允许硬编码的场景：SVG/图标/data-URI/meta 主题色/媒体查询内的物理值
ALLOW_LINE_PATTERNS = [
    re.compile(r"data:image/svg\+xml"),
    re.compile(r"<svg|</svg|fill=|stroke="),
    re.compile(r"<meta[^>]*theme-color"),
    re.compile(r"^\s*//|^\s*#(?!!)"),          # 代码注释
]


def is_allowed_line(line: str) -> bool:
    return any(p.search(line) for p in ALLOW_LINE_PATTERNS)


ROOT_OPEN_RE = re.compile(r':root(?:\s*\[[^\]]*\])?(?:\s*,\s*:root(?:\s*\[[^\]]*\])?)*\s*\{')


def token_block_lines(text: str) -> set[int]:
    """返回位于 :root 设计令牌声明块内的行号（0 基）。

    令牌定义本身就是全站配色的「单一事实来源」，不属于"绕过令牌的硬编码色值"——
    若把令牌块自身计为硬编码，门禁会把自己的规范源头判成违规。
    """
    nums: set[int] = set()
    for m in ROOT_OPEN_RE.finditer(text):
        i, depth = m.end(), 1
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            i += 1
        nums.update(range(text.count('\n', 0, m.start()), text.count('\n', 0, i) + 1))
    return nums


def extract_vars(css: str) -> set[str]:
    return {m.group(1) for m in VAR_DEF_RE.finditer(css)}


def check_file(path: Path, max_hardcoded: int) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    res: dict = {"file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                 "fail": [], "warn": [], "info": {}}

    # ---- 1. 令牌块
    roots = ROOT_RE.findall(text)
    light_vars = extract_vars(roots[0]) if roots else set()
    if not roots:
        res["fail"].append("无 :root 令牌块 —— 无法参与主题切换")

    # ---- 2. 标题层级完整性
    declared = set()
    for m in re.finditer(r"(?:^|[\s,{}])(h[1-6])\s*(?:,[^{]*)?\{", text):
        declared.add(m.group(1))
    missing = [f"h{i}" for i in range(1, 5) if f"h{i}" not in declared]
    if missing:
        res["fail"].append(f"标题层级未定义 {', '.join(missing)} —— 会落到浏览器默认样式")

    # ---- 3. 主题对称性
    dark_m = DARK_ROOT_RE.search(text)
    if dark_m and light_vars:
        dark_vars = extract_vars(dark_m.group(2))
        # 只比较"语义层"令牌（浅色里定义、深色里也应覆盖）
        semantic = {v for v in light_vars
                    if not v.startswith(("--p-", "--h", "--duration", "--ease", "--font", "--radius-", "--focus"))}
        absent = sorted(semantic - dark_vars)
        if absent:
            res["fail"].append(f"深色主题缺 {len(absent)} 个语义令牌：{', '.join(absent[:8])}")

    # ---- 4. 硬编码色值（令牌块自身不计：那是配色的单一事实来源）
    tok_lines = token_block_lines(text)
    hard = [(i + 1, l.strip()) for i, l in enumerate(lines)
            if HEX_RE.search(l) and not is_allowed_line(l) and i not in tok_lines]
    res["info"]["hardcoded"] = len(hard)
    if len(hard) > max_hardcoded:
        res["warn"].append(f"硬编码色值 {len(hard)} 处（阈值 {max_hardcoded}）")

    # ---- 5. 尺度合规
    sizes = sorted({float(s) for s in FONT_SIZE_RE.findall(text)})
    bad_sizes = [s for s in sizes
                 if not any(abs(s - a) <= FONT_TOLERANCE for a in ALLOWED_FONT_SIZES)]
    if bad_sizes:
        res["warn"].append(f"非标字号 {len(bad_sizes)} 档：{bad_sizes[:10]}")
    radii = sorted({float(r) for r in RADIUS_RE.findall(text)})
    bad_radii = [r for r in radii if r not in ALLOWED_RADII]
    if bad_radii:
        res["warn"].append(f"非标圆角 {len(bad_radii)} 档：{bad_radii[:10]}")

    # ---- 6. 令牌覆盖率
    uses = len(VAR_USE_RE.findall(text))
    denom = uses + len(hard)
    res["info"]["vars"] = len(light_vars)
    res["info"]["var_uses"] = uses
    res["info"]["coverage"] = (uses / denom * 100) if denom else 0.0
    if denom and res["info"]["coverage"] < 70:
        res["warn"].append(f"令牌覆盖率仅 {res['info']['coverage']:.0f}%（<70%）")

    # ---- 7. 尺度档数（收敛度）
    res["info"]["font_steps"] = len(sizes)
    res["info"]["radius_steps"] = len(radii)
    if len(sizes) > 10:
        res["warn"].append(f"字号 {len(sizes)} 档（>10 档，建议收敛到 8 档内）")
    if len(radii) > 5:
        res["warn"].append(f"圆角 {len(radii)} 档（>5 档，建议收敛到 4 档内）")

    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--strict", action="store_true", help="WARN 也计入失败")
    ap.add_argument("--max-hardcoded", type=int, default=40)
    args = ap.parse_args()

    targets = DEFAULT_TARGETS if args.all else args.files
    if not targets:
        ap.print_help()
        return 1

    reports, n_fail, n_warn = [], 0, 0
    for rel in targets:
        p = Path(rel)
        if not p.is_absolute():
            p = ROOT / rel
        if not p.exists():
            print(f"  ✘ {rel} — 不存在")
            continue
        r = check_file(p, args.max_hardcoded)
        reports.append(r)
        n_fail += len(r["fail"])
        n_warn += len(r["warn"])

    print("\n" + "=" * 74)
    print(f"{'文件':<38}{'令牌':>5}{'引用':>6}{'覆盖':>7}{'字号':>5}{'圆角':>5}")
    print("-" * 74)
    for r in reports:
        i = r["info"]
        print(f"{r['file']:<38}{i.get('vars', 0):>5}{i.get('var_uses', 0):>6}"
              f"{i.get('coverage', 0):>6.0f}%{i.get('font_steps', 0):>5}{i.get('radius_steps', 0):>5}")
    print("=" * 74)

    for r in reports:
        if not r["fail"] and not r["warn"]:
            continue
        print(f"\n▸ {r['file']}")
        for f in r["fail"]:
            print(f"    ✘ FAIL  {f}")
        for w in r["warn"]:
            print(f"    ⚠ WARN  {w}")

    print(f"\nFAIL={n_fail}  WARN={n_warn}  文件={len(reports)}")
    if n_fail == 0 and (not args.strict or n_warn == 0):
        print("✅ 视觉门禁通过")
        return 0
    print("❌ 视觉门禁未通过")
    return 1


if __name__ == "__main__":
    sys.exit(main())
