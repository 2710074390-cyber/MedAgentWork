#!/usr/bin/env python3
"""
MedAgentWork — 插图占位/文件一致性门禁（GATE-A6 · HC-19）

检查主复习资料 MD 中的插图占位符与 images_webp/ 文件的一致性。
由 MedMaster 在「阶段五·五 生图验收」与「阶段五 终审」执行。
示例：
  python scripts/check_inline_images.py --md 复习资料/内科学教学计划版/内科学_主复习资料_合订本.md
  python scripts/check_inline_images.py --md ... --img-dir 复习资料/{科目}教学计划版/images_webp --list .../{科目}_配图清单.md

退出码：0=通过（或仅有警告）；1=FAIL（缺失文件 / 语法错误 / 图号断号重复 / 清单不一致 /
        非 WebP 引用 / images_webp 孤儿文件 / 图谱复用未登记源图号）

检查项：
  C1 占位符语法：![图N：图注](images_webp/xxx.webp)（alt 以"图N：/图N:"开头，路径在 images_webp/ 下）
  C2 文件存在：引用的图片文件必须存在
  C3 图号唯一且连续：从 1 开始无重复、无断号；「存量/占位」登记（--exempt-file）中的图号豁免断号并输出"待回填清单"
  C4 无残留占位：正文不得出现「（此处应有图）」「待插入」「TODO: 图」等
  C5 配图清单一致性（--list 时）：清单图号集合 == MD 占位符图号集合（兼容「图N」与「N」两种编号列）
  C6 警告：单张图片 > 500KB（超部署预算）；存量登记文件单独标注为「存量·待重制」，图谱占位未标图号
  C7 引用格式：MD 引用必须是 images_webp/*.webp（发布规范）；引用 png/jpg 等 → FAIL
  C8 孤儿文件：images_webp/ 下存在未被 MD 引用且未登记「留档」的文件 → FAIL（单一产物权属）
  C9 图谱复用登记：配图清单中「底图来源=图谱复用」的行必须登记真实源图号（否则 FAIL），
     且须在登记文件中标记「复核=通过」（人工 Read 目视核验画面后才放行，否则 WARN）
"""

import argparse
import re
import sys
from pathlib import Path

try:  # Windows 控制台 GBK 下友好显示中文
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

FIG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
ALT_RE = re.compile(r"^图(\d+)[：:]\s*(.+)$")
RESIDUE_RE = re.compile(r"此处应有图|待插入图|占位图|TODO[:：]?\s*图|(此处|缺)图")
LIST_ROW_RE = re.compile(r"^\|\s*图?(\d+)\s*\|", re.MULTILINE)  # 兼容「图N」与「N」
REG_ROW_RE = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|$"
)

# 门禁参数取自单一配置源 medillustration_config.yaml（P1-4 / P2-8）
try:
    from medillustration_config import load as _load_cfg
    _gate_cfg = (_load_cfg().get("gate") or {})
except Exception:
    _gate_cfg = {}
VOLUME_KB = int(_gate_cfg.get("volume_kb", 500))
WEBP_ONLY = bool(_gate_cfg.get("webp_only", True))
EXEMPT_REGISTRY = _gate_cfg.get("exempt_registry") or None

FAIL = []
WARN = []


def load_registry(exempt_file: Path | None) -> dict:
    """读取存量与占位登记：返回
    { 'exempt_c3': {(subject, fig_no): (type, note, todo)},
      'filenames': {filename: (subject, type, note, todo, review)} }
    """
    out = {"exempt_c3": {}, "filenames": {}}
    if not exempt_file or not exempt_file.exists():
        return out
    for line in exempt_file.read_text(encoding="utf-8").splitlines():
        m = REG_ROW_RE.match(line)
        if not m:
            continue
        subject, fig_no_s, fname, typ, note, todo, review = [c.strip() for c in m.groups()]
        if not subject or subject in ("科目", "---"):
            continue
        fig_no = int(fig_no_s) if fig_no_s.isdigit() else None
        if fig_no is not None and typ in ("存量", "占位"):
            out["exempt_c3"][(subject, fig_no)] = (typ, note, todo)
        if fname and fname != "—" and fname != "-":
            out["filenames"][fname] = (subject, typ, note, todo, review)
    return out


def check_images(md_path: Path, img_dir: Path, list_path: Path | None,
                 exempt_file: Path | None) -> None:
    text = md_path.read_text(encoding="utf-8")
    subject = md_path.parent.name
    subject_key = subject.replace("教学计划版", "")   # 登记表科目用短名，兼容目录名
    reg = load_registry(exempt_file)

    def reg_c3(sub, n):
        for key in (sub, sub + "教学计划版"):
            if (key, n) in reg["exempt_c3"]:
                return reg["exempt_c3"][(key, n)]
        return None

    def reg_file(fname):
        return reg["filenames"].get(fname)

    # ---- C1 占位符语法 ----
    matches = FIG_RE.findall(text)
    refs = []  # (fig_no, alt, rel_path)
    for alt, rel in matches:
        m = ALT_RE.match(alt)
        if not m:
            FAIL.append(f"C1 alt 不符「图N：图注」：{alt!r}（{rel}）")
            continue
        fig_no = int(m.group(1))
        rel_clean = rel.strip()
        if not rel_clean.startswith("images_webp/"):
            FAIL.append(f"C1 路径不在 images_webp/ 下：{rel_clean!r}")
        if not rel_clean.lower().endswith((".webp", ".png", ".jpg", ".jpeg")):
            FAIL.append(f"C1 非图片扩展名：{rel_clean!r}")
            continue
        refs.append((fig_no, alt, rel_clean))

    # ---- C7 引用格式：必须 webp（发布规范，配置 webp_only）----
    for fig_no, alt, rel in refs:
        if WEBP_ONLY and not rel.lower().endswith(".webp"):
            FAIL.append(f"C7 引用非 WebP（发布规范要求 images_webp/*.webp）：图{fig_no} → {rel}")

    # ---- C2 文件存在 ----
    missing = []
    for fig_no, alt, rel in refs:
        f = md_path.parent / rel
        if not f.exists():
            missing.append((fig_no, rel))
            FAIL.append(f"C2 文件缺失：图{fig_no} → {rel}")
        elif f.stat().st_size > VOLUME_KB * 1024:
            tag = "存量·待重制" if reg_file(f.name) else "体积超标"
            WARN.append(f"C6 {tag}（>{VOLUME_KB}KB）：{rel}（{f.stat().st_size // 1024}KB）")

    # ---- C3 图号唯一且连续（含存量豁免 + 待回填清单）----
    nums = [n for n, _, _ in refs]
    if len(nums) != len(set(nums)):
        dup = [n for n in nums if nums.count(n) > 1]
        FAIL.append(f"C3 图号重复：{sorted(set(dup))}")
    backlog = []
    if nums:
        expected = list(range(1, max(nums) + 1))
        missing_nums = sorted(set(expected) - set(nums))
        still_missing = []
        for n in missing_nums:
            hit = reg_c3(subject_key, n)
            if hit:
                typ, note, todo = hit
                backlog.append((n, typ, note, todo))
            else:
                still_missing.append(n)
        if still_missing:
            FAIL.append(f"C3 图号不连续：缺 {still_missing}")

    # ---- C4 残留占位 ----
    for m in RESIDUE_RE.finditer(text):
        line_no = text[: m.start()].count("\n") + 1
        WARN.append(f"C4 疑似残留占位（L{line_no}）：…{m.group(0)}…")

    # ---- C5 配图清单一致性（兼容「图N」编号列；只解析主「一览」表，忽略后续补充章节）----
    if list_path:
        lt = Path(list_path)
        if lt.exists():
            lines = lt.read_text(encoding="utf-8").splitlines()
            list_nums = set()
            in_table = False
            for line in lines:
                if in_table and line.startswith("#"):
                    break
                if not in_table and line.strip().startswith("|") and "底图来源" in line:
                    in_table = True
                    continue
                if in_table:
                    m = LIST_ROW_RE.match(line)
                    if m:
                        list_nums.add(int(m.group(1)))
            md_nums = set(nums)
            only_list = sorted(list_nums - md_nums)
            only_md = sorted(md_nums - list_nums)
            if only_list:
                FAIL.append(f"C5 清单有但 MD 未引用：{only_list}")
            if only_md:
                FAIL.append(f"C5 MD 引用但清单未列：{only_md}")
        else:
            FAIL.append(f"C5 配图清单不存在：{list_path}")

        # ---- C9 图谱复用登记（P2-7 入闸；只查主「一览」表）----
        lines = lt.read_text(encoding="utf-8").splitlines()
        header = None
        header_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("|") and "底图来源" in line:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                header = {name: i for i, name in enumerate(cells)}
                header_idx = i
                break
        if header is not None and "底图来源" in header:
            src_idx = header["底图来源"]
            for line in lines[header_idx + 1:]:
                if line.startswith("#"):
                    break
                if not line.strip().startswith("|") or "---" in line:
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) <= src_idx:
                    continue
                src = cells[src_idx]
                if "图谱复用" not in src:
                    continue
                fname_cell = ""
                for key in ("文件名", "图名"):
                    if key in header:
                        fname_cell = cells[header[key]].strip().strip("`")
                        break
                if not re.search(r"图\d{2,}", src):
                    FAIL.append(f"C9 图谱复用未登记源图号：{fname_cell or line.strip()[:40]}（底图来源={src}）")
                else:
                    hit = reg_file(fname_cell)
                    if not hit or hit[4] != "通过":
                        WARN.append(f"C9 图谱复用待人工复核（登记复核=通过后才放行）：{fname_cell}（{src}）")

    # ---- C6 图谱占位未标图号（提示）----
    for fig_no, alt, rel in refs:
        if "图谱" in alt and not re.search(r"图\d{2,3}", alt.split("：")[-1] if "：" in alt else alt):
            WARN.append(f"C6 图谱类占位 alt 未含图谱图号：图{fig_no} {alt}")

    # ---- C8 孤儿文件：images_webp 内未被引用且未登记「留档」----
    if img_dir.exists():
        referenced = {Path(r).name for _, _, r in refs}
        orphan = []
        for f in sorted(img_dir.iterdir()):
            if f.is_dir():
                continue
            if f.name in referenced:
                continue
            hit = reg_file(f.name)
            if hit and hit[1] in ("留档", "存量"):
                continue
            orphan.append(f.name)
        if orphan:
            FAIL.append(f"C8 images_webp 孤儿文件（未被 MD 引用且未登记）：{', '.join(orphan[:60])}")

    print(f"检查 MD：{md_path}")
    print(f"占位符：{len(refs)} 张（图号 {min(nums) if nums else '-'}~{max(nums) if nums else '-'}）")
    print(f"缺失文件：{len(missing)} | 警告：{len(WARN)} | FAIL：{len(FAIL)}")
    if backlog:
        print("待回填清单（存量/占位豁免，仍须回填）:")
        for n, typ, note, todo in backlog:
            print(f"  图{n} [{typ}] {note or ''}  → {todo or '待回填'}")
    for w in WARN:
        print(f"  WARN {w}")
    for f in FAIL:
        print(f"  FAIL {f}")


def main() -> int:
    ap = argparse.ArgumentParser(description="插图占位/文件一致性门禁 (GATE-A6)")
    ap.add_argument("--md", required=True, help="主复习资料 MD 路径（必填）")
    ap.add_argument("--img-dir", default=None, help="images_webp 目录（默认 MD 同目录/images_webp）")
    ap.add_argument("--list", default=None, help="配图清单 MD 路径（可选，检查一一对应与图谱复用登记）")
    ap.add_argument("--exempt-file", default=None,
                    help="存量与占位登记文件（默认 复习资料/_配图需求/存量与占位登记.md）")
    args = ap.parse_args()

    md_path = Path(args.md)
    if not md_path.exists():
        print(f"FAIL MD 不存在：{md_path}")
        return 1

    img_dir = Path(args.img_dir) if args.img_dir else md_path.parent / "images_webp"
    exempt_file = None
    if args.exempt_file:
        exempt_file = Path(args.exempt_file)
    else:
        cand_cfg = None
        if EXEMPT_REGISTRY:
            p = Path(EXEMPT_REGISTRY)
            cand_cfg = p if p.is_absolute() else Path.cwd() / p
        cand_local = md_path.parent.parent / "_配图需求" / "存量与占位登记.md"
        exempt_file = cand_cfg if (cand_cfg and cand_cfg.exists()) else cand_local
    check_images(md_path, img_dir, Path(args.list) if args.list else None, exempt_file)

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
