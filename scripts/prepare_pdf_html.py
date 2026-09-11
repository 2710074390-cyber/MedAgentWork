# -*- coding: utf-8 -*-
"""prepare_pdf_html.py — render_review.py 产物（自包含 HTML）打印前优化。

将 HTML 内联的 base64 图片统一降采样到 max_width（默认 1000px）并转 JPEG q88，
白底扁平化（webp 含 alpha 时先合成到白底），再把优化后的 base64 写回 HTML，
使 Chrome 无头打印 PDF 时不再以 1600px 无损 PNG 内嵌（约 21MB → 约 3MB）。

用法：python scripts/prepare_pdf_html.py <input.html> [-o output.html] [--max-width 1000] [--quality 88]
"""
import argparse
import base64
import io
import re
from pathlib import Path

from PIL import Image

IMG_RE = re.compile(r'(data:image/[a-zA-Z+]+;base64,)([A-Za-z0-9+/=]+)')


def optimize_html(src: Path, dst: Path, max_width: int, quality: int) -> int:
    text = src.read_text(encoding="utf-8")
    saved_bytes = 0
    replaced = 0

    def _repl(m):
        nonlocal saved_bytes, replaced
        prefix, b64 = m.group(1), m.group(2)
        try:
            data = base64.b64decode(b64)
            img = Image.open(io.BytesIO(data))
            img.load()
        except Exception:
            return m.group(0)  # 保持原样
        # 白底扁平化
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            bg.alpha_composite(img)
            img = bg.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")
        # 降采样
        w, h = img.size
        if w > max_width:
            img = img.resize((max_width, int(h * max_width / w)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        new_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        saved_bytes += len(b64) - len(new_b64)
        replaced += 1
        return "data:image/jpeg;base64," + new_b64

    out = IMG_RE.sub(_repl, text)
    dst.write_text(out, encoding="utf-8")
    print(f"替换图片: {replaced} 张 | 省去 base64 字节: {saved_bytes/1024/1024:.1f} MB")
    return replaced


def main():
    ap = argparse.ArgumentParser(description="render_review.py HTML 打印前图片优化")
    ap.add_argument("input", help="输入 HTML 路径")
    ap.add_argument("-o", "--output", default=None, help="输出 HTML 路径（默认 input.optimized.html）")
    ap.add_argument("--max-width", type=int, default=1000, help="图片最长边像素（默认 1000）")
    ap.add_argument("--quality", type=int, default=88, help="JPEG 质量（默认 88）")
    args = ap.parse_args()
    src = Path(args.input)
    dst = Path(args.output) if args.output else src.with_name(src.stem + ".optimized.html")
    n = optimize_html(src, dst, args.max_width, args.quality)
    if n == 0:
        print("警告：未找到任何内联图片，输出未优化")
        return 1
    print(f"已生成: {dst}（{dst.stat().st_size/1024/1024:.1f} MB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
