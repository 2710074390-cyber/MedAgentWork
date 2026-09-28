# -*- coding: utf-8 -*-
"""export_review_pdfs.py — 批量导出 5 科教学计划版复习手册 PDF（v3 配图版）。

⚠️ 2026-09-28 起：本脚本产物**不是交付物**，禁止写入站点目录。
   它用 `chrome --headless=new --print-to-pdf` 生成的是「网页打印件」，
   会重新排版（封面/分页与人工导出版不同），且 /Creator 带 HeadlessChrome 指纹。
   2026-09-12 它就是这样把用户 09-01 人工导出的定稿版覆盖掉的。
   规范 §5.6：PDF 一律人工导出上传，脚本不得生成。
   站点上的 PDF 请用「人工导出 → scripts/shrink_pdf.py 压到 25 MiB 以内 → 上传」。
   本脚本仅供生成自查稿/预览稿，--out-dir 指向站点目录会被硬拒。

管线：render_review.py(MD→自包含HTML, --embed-images) → prepare_pdf_html.py(图片降采样JPEG)
      → Chrome headless 打印 PDF → PyMuPDF 校验（页数/含图页）→ 输出 manifest。

用法：python scripts/export_review_pdfs.py [--out-dir _scratch/pdf_export]
依赖：默认 python（render_review.py/prepare_pdf_html.py）；校验用 Python312（pymupdf）。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\38063\Desktop\MedAgentWork")
CHROME = r"C:\Users\38063\AppData\Local\Google\Chrome\Application\chrome.exe"
PY312 = r"C:\Users\38063\AppData\Local\Programs\Python\Python312\python.exe"
RENDER = ROOT / "知识库素材" / "render_review.py"
PREPARE = ROOT / "scripts" / "prepare_pdf_html.py"

SUBJECTS = [
    ("内科学教学计划版", "内科学_主复习资料_合订本.md", "内科学_主复习资料_合订本.pdf"),
    ("外科学教学计划版", "外科学（二）_主复习资料.md", "外科学（二）_主复习资料.pdf"),
    ("妇产科学教学计划版", "妇产科学_主复习资料.md", "妇产科学_主复习资料.pdf"),
    ("急诊与灾难医学教学计划版", "急诊与灾难医学_主复习资料.md", "急诊与灾难医学_主复习资料.pdf"),
    ("耳鼻咽喉头颈外科学教学计划版", "耳鼻咽喉头颈外科学_主复习资料.md", "耳鼻咽喉头颈外科学_主复习资料.pdf"),
]


def run(cmd, cwd=None, timeout=600):
    print(">>", " ".join(str(c) for c in cmd[:3]), "...")
    r = subprocess.run(cmd, cwd=str(cwd or ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0:
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        raise RuntimeError(f"命令失败: {cmd[0]} rc={r.returncode}")
    return r


def export_one(subj_dir, md_name, pdf_name, work_dir, out_dir):
    md = ROOT / "复习资料" / subj_dir / md_name
    html_raw = work_dir / f"{pdf_name}.raw.html"
    html_opt = work_dir / f"{pdf_name}.opt.html"
    pdf = out_dir / pdf_name
    run([sys.executable, str(RENDER), str(md), "-o", str(html_raw), "--embed-images"])
    run([sys.executable, str(PREPARE), str(html_raw), "-o", str(html_opt)])
    uri = "file:///" + str(html_opt).replace("\\", "/").replace(" ", "%20")
    run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf}", uri], timeout=900)
    return pdf


def verify(pdf_path: Path) -> dict:
    code = (
        "import pymupdf, json, sys\n"
        "d = pymupdf.open(sys.argv[1])\n"
        "imp = [i+1 for i in range(d.page_count) if d[i].get_images()]\n"
        "print(json.dumps({'pages': d.page_count, 'img_pages': len(imp)}, ensure_ascii=False))\n"
    )
    r = subprocess.run([PY312, "-c", code, str(pdf_path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return json.loads(r.stdout.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser(description="批量导出 5 科教学版复习手册 PDF")
    ap.add_argument("--out-dir", default=str(ROOT / "_scratch" / "pdf_export"),
                    help="PDF 输出目录（默认在站点目录之外；指向 大三下/ 或 大四上/ 会被拒绝）")
    ap.add_argument("--work-dir", default=str(ROOT / "_scratch" / "配图计划v3" / "pdf_export" / "work"))
    args = ap.parse_args()
    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path(args.work_dir); work_dir.mkdir(parents=True, exist_ok=True)

    # ---- 站点目录保护闸（2026-09-28）----
    # 本脚本用 `chrome --headless=new --print-to-pdf` 生成的是「网页打印件」，
    # 不是人工导出的原生 PDF（Creator 会带 HeadlessChrome 指纹），
    # 且会重新排版（封面/分页与人工导出版不同）。2026-09-12 它就是这么把
    # 用户 09-01 的人工导出版覆盖掉的。
    # 规范 §5.6：PDF 一律人工导出上传，脚本不得生成。故此处硬拒。
    # 注意：--out-dir 的相对路径按 CWD 解析，而站点目录按硬编码 ROOT 解析，
    # 两边基准不同，所以两种解释都要查一遍。
    raw_out = Path(args.out_dir)
    cands = {raw_out.resolve()}
    if not raw_out.is_absolute():
        cands.add((ROOT / raw_out).resolve())
    for site in (ROOT / "大三下", ROOT / "大四上"):
        site_r = site.resolve()
        hit = None
        for c in cands:
            try:
                c.relative_to(site_r)
                hit = c
                break
            except ValueError:
                continue
        if hit is None:
            continue
        print(f"[X] 拒绝执行：--out-dir 落在站点交付目录内\n"
              f"    指定: {raw_out}  → 解析为 {hit}\n"
              f"    站点: {site}\n\n"
              f"    规范 §5.6 要求 PDF 由人工导出上传，脚本不得生成（本脚本产物带\n"
              f"    HeadlessChrome 指纹，verify_produce_rules.py 会判 FAIL）。\n"
              f"    要生成自查用的 PDF，请把 --out-dir 指向站点目录之外，例如：\n"
              f"      --out-dir _scratch/pdf_export\n"
              f"    要把人工导出的 PDF 压到 Pages 25 MiB 上限内，用：\n"
              f"      python scripts/shrink_pdf.py <你导出的.pdf> -o <目标.pdf>")
        return 2

    manifest = []
    for subj_dir, md_name, pdf_name in SUBJECTS:
        print(f"\n=== {pdf_name} ===")
        pdf = export_one(subj_dir, md_name, pdf_name, work_dir, out_dir)
        st = verify(pdf)
        st["pdf"] = pdf_name
        st["size_mb"] = round(pdf.stat().st_size / 1024 / 1024, 1)
        manifest.append(st)
        print(f"✅ {pdf_name}: {st['pages']} 页 / 含图页 {st['img_pages']} / {st['size_mb']} MB")

    mf = work_dir / "manifest.json"
    mf.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成，manifest: {mf}")


if __name__ == "__main__":
    sys.exit(main())
