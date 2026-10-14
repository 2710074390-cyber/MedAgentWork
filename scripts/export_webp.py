# -*- coding: utf-8 -*-
"""
export_webp.py — annotated PNG 批量导出 1600px q82 WebP 部署版

用法：
    python scripts/export_webp.py 复习资料/外科学教学计划版          # 导出该科目 annotated/ 下全部 PNG
    python scripts/export_webp.py 科目目录 a.png b.png              # 只导出指定文件（相对 annotated/）
输出：科目目录 images_webp/<同名>.webp，宽 1600、quality=82、method=6。
"""
import sys
import os
import io
from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 压缩参数取自单一配置源 medillustration_config.yaml（P1-4 / P2-8），缺失时回退默认
try:
    from medillustration_config import canvas as _canvas_cfg
    _c = _canvas_cfg()
    WEBP_W = int(_c.get('webp_width', 1600))
    QUALITY = int(_c.get('webp_quality', 82))
    METHOD = int(_c.get('webp_method', 6))
except Exception:
    WEBP_W = 1600
    QUALITY = 82
    METHOD = 6


def export_one(png_path, out_path):
    img = Image.open(png_path).convert('RGB')
    if img.width != WEBP_W:
        h = round(img.height * WEBP_W / img.width)
        img = img.resize((WEBP_W, h), Image.LANCZOS)
    img.save(out_path, 'WEBP', quality=QUALITY, method=METHOD)
    kb = os.path.getsize(out_path) / 1024
    print(f'  ✔ {os.path.basename(out_path)}  {img.width}x{img.height}  {kb:.0f}KB')


def main():
    subject_dir = sys.argv[1]
    ann_dir = os.path.join(subject_dir, 'annotated')
    webp_dir = os.path.join(subject_dir, 'images_webp')
    os.makedirs(webp_dir, exist_ok=True)
    if len(sys.argv) > 2:
        names = sys.argv[2:]
        files = [os.path.join(ann_dir, n if n.endswith('.png') else n + '.png') for n in names]
    else:
        files = [os.path.join(ann_dir, f) for f in sorted(os.listdir(ann_dir)) if f.endswith('.png')]
    print(f'📦 {subject_dir}: 导出 {len(files)} 张')
    for f in files:
        out = os.path.join(webp_dir, os.path.splitext(os.path.basename(f))[0] + '.webp')
        export_one(f, out)
    print('✅ 完成')


if __name__ == '__main__':
    main()
