# -*- coding: utf-8 -*-
r"""shrink_pdf.py — 把人工导出的 PDF 压到 Cloudflare Pages 单文件上限以内。

只重压内嵌图片，**不重排版**：页数、封面、分页、字体、书签全部保持原样。
（对比：export_review_pdfs.py 是「重新渲染整个文档」，会把封面/分页换掉。）

用法：
  python scripts/shrink_pdf.py <src.pdf> -o <dst.pdf> [--limit-mib 25] [--min-quality 80]

依赖：PyMuPDF（本机装在 Python 3.12：C:\Users\38063\AppData\Local\Programs\Python\Python312\python.exe）
退出码：0 = 已 ≤ 上限；1 = 试完所有质量仍超限；2 = 参数/环境错误
"""
import argparse
import pathlib
import sys

try:
    import pymupdf
except ImportError:
    sys.exit(
        "shrink_pdf.py 需要 PyMuPDF（用于只重压内嵌图片、不改版面）。\n"
        "本机已装在 Python 3.12，请用它执行：\n"
        r'  "C:\Users\38063\AppData\Local\Programs\Python\Python312\python.exe" '
        "scripts\\shrink_pdf.py <src.pdf> -o <dst.pdf>\n"
        "安装：pip install pymupdf"
    )

QUALITIES = (92, 90, 88, 86, 84, 82, 80, 78, 76)


def image_stats(doc):
    """统计内嵌图片：张数、总字节、是否带 alpha。"""
    seen = {}
    for pno in range(doc.page_count):
        for im in doc[pno].get_images(full=True):
            xref = im[0]
            if xref in seen:
                continue
            try:
                info = doc.extract_image(xref)
            except Exception:
                continue
            seen[xref] = info
    total = sum(len(v["image"]) for v in seen.values())
    return {"count": len(seen), "bytes": total}


def sample_text(doc, pages=(0, 1, 2)):
    out = []
    for p in pages:
        if p < doc.page_count:
            out.append(" ".join(doc[p].get_text().split()))
    return "|".join(out)


def shrink(src: pathlib.Path, dst: pathlib.Path, limit: int, min_q: int):
    ref = pymupdf.open(src)
    ref_pages = ref.page_count
    ref_text = sample_text(ref)
    ref_imgs = image_stats(ref)
    print(f"  源文件: {src.stat().st_size/1048576:.2f} MiB  {ref_pages} 页  "
          f"图片 {ref_imgs['count']} 张 / {ref_imgs['bytes']/1048576:.2f} MiB")
    ref.close()

    chosen = None
    for q in [x for x in QUALITIES if x >= min_q]:
        d = pymupdf.open(src)
        d.rewrite_images(quality=q)          # 只重压图片，不改 dpi、不改版面
        d.save(dst, garbage=4, deflate=True, clean=True)
        size = dst.stat().st_size
        # 断言「没有重排版」
        ok_pages = d.page_count == ref_pages
        ok_text = sample_text(d) == ref_text
        d.close()
        tag = "OK " if (size <= limit and ok_pages and ok_text) else "超限"
        print(f"    q={q}: {size/1048576:6.2f} MiB  页数一致={ok_pages} 文本一致={ok_text}  {tag}")
        if size <= limit and ok_pages and ok_text:
            chosen = q
            break
    if chosen is None:
        return None, dst.stat().st_size
    return chosen, dst.stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--limit-mib", type=float, default=25.0)
    ap.add_argument("--min-quality", type=int, default=80)
    a = ap.parse_args()

    src = pathlib.Path(a.src)
    dst = pathlib.Path(a.out)
    if not src.exists():
        print(f"[X] 源文件不存在: {src}"); return 2
    limit = int(a.limit_mib * 1048576)

    if src.stat().st_size <= limit:
        print(f"  源文件 {src.stat().st_size/1048576:.2f} MiB 已在上限内，直接复制（零损失）")
        dst.write_bytes(src.read_bytes())
        print(f"[OK] {dst}  {dst.stat().st_size/1048576:.2f} MiB")
        return 0

    q, size = shrink(src, dst, limit, a.min_quality)
    if q is None:
        print(f"[X] 试到 q={a.min_quality} 仍为 {size/1048576:.2f} MiB，超过上限 "
              f"{a.limit_mib} MiB。请改走外部托管或拆册。")
        return 1
    print(f"[OK] {dst}  q={q}  {size/1048576:.2f} MiB  "
          f"（省 {(1 - size/src.stat().st_size)*100:.0f}%）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
