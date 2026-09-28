#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""audit_site_pdfs.py — 站点上的 PDF 是不是你人工导出的原件？

背景（2026-09-28）：`export_review_pdfs.py` 曾用 Chrome 无头打印生成的 PDF
覆盖了人工导出版，站点上挂了一个多月没人发现。
`verify_produce_rules.py` 只能断言「不是脚本生成的 + 不超体积」，
**不能**回答「这一份到底是不是我导出的那个文件」——本脚本补这一环：
把站点目录里每个 PDF 拿去和人工导出目录里的候选件做 sha256 比对。

判定分四档：
  ✅ 与原件逐字节相同            —— 你要的「原生 PDF」就是它
  🟡 同页数但内容不同            —— 通常是做过「只压图不重排」（shrink_pdf.py），符合预期
  ⚠️ 页数不同                    —— 可能是旧版本 / 不同内容，需要人工确认
  —  导出目录里没有候选件        —— 无法核对来源

用法：
  python scripts/audit_site_pdfs.py
  python scripts/audit_site_pdfs.py --user-dir "D:\我的导出" --user-dir "E:\另一处"
  python scripts/audit_site_pdfs.py --commit 0ed1686      # 对照某个提交（默认读工作区文件）

退出码：0 = 无 ⚠️；1 = 有 ⚠️ 或无法核对；2 = 环境问题
"""
import argparse
import hashlib
import io
import re
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SITE_SUBDIRS = ["大三下/题库", "大四上/复习资料", "大四上/题库"]
DEFAULT_USER_DIRS = [Path.home() / "Desktop" / "大四上", Path.home() / "Desktop" / "大三下"]


def norm(name: str) -> str:
    """归一化文件名用于模糊匹配：去 batch/版本/题数 前后缀与空白。"""
    s = Path(name).stem
    s = re.sub(r"^batch\d+_", "", s)
    s = re.sub(r"_batch\d+", "", s)
    s = re.sub(r"[_\s]*v\d+(\.\d+)?", "", s)
    s = re.sub(r"_\d+题", "", s)
    s = s.replace("（", "(").replace("）", ")")
    return re.sub(r"[\s_]", "", s)


def page_count(data: bytes):
    """页数。优先用 PyMuPDF；没有就用 /Type /Page 计数（够用于比对）。"""
    try:
        import pymupdf
        d = pymupdf.open(stream=data, filetype="pdf")
        n = d.page_count
        d.close()
        return n
    except Exception:
        return len(re.findall(rb"/Type\s*/Page[^s]", data))


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_site(rel: str, commit: str | None) -> bytes:
    if commit:
        return subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=ROOT,
                              capture_output=True).stdout
    p = ROOT / rel
    return p.read_bytes() if p.exists() else b""


def main() -> int:
    ap = argparse.ArgumentParser(description="核对站点 PDF 是否就是人工导出的原件")
    ap.add_argument("--user-dir", action="append", default=None,
                    help="人工导出目录（可多次；默认 Desktop\\大四上 + Desktop\\大三下）")
    ap.add_argument("--commit", default=None, help="对照某个提交（如 0ed1686）；默认读工作区")
    a = ap.parse_args()

    user_dirs = [Path(p) for p in a.user_dir] if a.user_dir else DEFAULT_USER_DIRS
    user_dirs = [d for d in user_dirs if d.exists()]
    if not user_dirs:
        print("[X] 一个导出目录都不存在：" + " / ".join(str(d) for d in DEFAULT_USER_DIRS))
        print("    用 --user-dir 指定你的导出目录。")
        return 2

    user_pdfs = [p for d in user_dirs for p in d.rglob("*.pdf") if p.is_file()]
    print(f"站点侧: {a.commit or '工作区'}   导出目录: {len(user_dirs)} 个 / {len(user_pdfs)} 个 PDF\n")

    site_pdfs = []
    for sub in SITE_SUBDIRS:
        d = ROOT / sub
        if d.exists():
            site_pdfs += sorted(d.glob("*.pdf"))
    if not site_pdfs:
        print("[X] 站点目录下一个 PDF 都没找到 —— 路径约定可能已变，审计失效")
        return 2

    warn = 0
    unknown = 0
    for sp in site_pdfs:
        rel = sp.relative_to(ROOT).as_posix()
        data = read_site(rel, a.commit)
        if not data:
            print(f"⚠️  {rel}：读不到内容"); warn += 1; continue
        s1, n1 = sha(data), page_count(data)

        exact = [u for u in user_pdfs if u.name == sp.name]
        cands = exact + [u for u in user_pdfs
                         if u not in exact and norm(u.name) == norm(sp.name)]
        if not cands:
            print(f"—   {rel}  {s1[:12]}  {n1:>4}页   导出目录无候选件（无法核对来源）")
            unknown += 1
            continue

        same = next((u for u in cands if sha(u.read_bytes()) == s1), None)
        if same:
            print(f"✅  {rel}  {s1[:12]}  {n1:>4}页   与原件逐字节相同  ← {same.parent.name}/{same.name}")
            continue

        # 找出页数最接近的候选
        scored = sorted(((abs(page_count(u.read_bytes()) - n1), u) for u in cands),
                        key=lambda x: x[0])
        d0, u0 = scored[0]
        n0 = page_count(u0.read_bytes())
        if d0 == 0:
            print(f"🟡  {rel}  {s1[:12]}  {n1:>4}页   同页数但内容不同（做过只压图？）  ← {u0.name}")
        else:
            print(f"⚠️  {rel}  {s1[:12]}  {n1:>4}页   页数不同：候选 {u0.name} 是 {n0} 页")
            warn += 1

    print(f"\n=== 审计结果：{len(site_pdfs)} 个站点 PDF · 需人工确认 {warn} · 无法核对来源 {unknown} ===")
    return 1 if warn else 0


if __name__ == "__main__":
    sys.exit(main())
