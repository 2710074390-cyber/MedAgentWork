# -*- coding: utf-8 -*-
"""
annotate_image.py — 医学写实插图中文标注修复工具（YAML 驱动）

用途：覆盖 AI 生成图内乱码英文标注区域，原位替换为正确中文标注。
- box 使用千分比相对坐标（0-1000，左上原点），与图像分辨率无关
- text 支持 \n 换行（多行标注）
- anchor 可选：引导线终点（千分比），从覆盖框边缘画线指向结构点
- 覆盖色默认纯白 #FFFFFF，可逐条覆盖

用法：
    python annotate_image.py annotate_configs/22_肝硬化门脉高压.yaml
    python annotate_image.py annotate_configs/*.yaml   (PowerShell 不支持，逐个传或写循环)
"""
import sys
import os
import io
import argparse

import yaml
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

FONT_PATH = r'C:\Windows\Fonts\msyhbd.ttc'   # 微软雅黑 Bold
TEXT_COLOR = '#1A1B1C'
LINE_COLOR = '#333333'
DEFAULT_BG = '#FFFFFF'
DEFAULT_PADDING = 8   # 覆盖框外扩像素


def rel_to_px(rel, size):
    """千分比 -> 像素"""
    return int(round(rel / 1000.0 * size))


def fit_font(draw, font_path, text_lines, box_w, box_h):
    """自适应字号：不超框宽、不超框高"""
    font_size = int(box_h / len(text_lines) * 0.92)
    font_size = max(12, font_size)
    while font_size > 12:
        font = ImageFont.truetype(font_path, font_size)
        max_lw = max(draw.textlength(line, font=font) for line in text_lines)
        if max_lw <= box_w * 0.98 and font_size * 1.25 * len(text_lines) <= box_h * 1.02:
            break
        font_size -= 1
    return ImageFont.truetype(font_path, font_size)


def draw_fix(img, draw, fix, font_path):
    """绘制单条标注修复"""
    w, h = img.size
    pad = fix.get('padding', DEFAULT_PADDING)
    bg = fix.get('background', DEFAULT_BG)
    text = fix.get('text', '').strip()
    if not text:
        return

    x1, y1, x2, y2 = [rel_to_px(v, w if i % 2 == 0 else h) for i, v in enumerate(fix['box'])]
    x1 -= pad; y1 -= pad; x2 += pad; y2 += pad

    # 覆盖乱码区域
    draw.rounded_rectangle([x1, y1, x2, y2], radius=8, fill=bg)

    # 居中绘制中文标注（多行）
    lines = text.split('\n')
    font = fit_font(draw, font_path, lines, x2 - x1, y2 - y1)
    line_h = int(font.size * 1.3)
    total_h = line_h * len(lines)
    y = y1 + (y2 - y1 - total_h) / 2
    for line in lines:
        lw = draw.textlength(line, font=font)
        draw.text((x1 + (x2 - x1 - lw) / 2, y), line, font=font, fill=fix.get('text_color', TEXT_COLOR))
        y += line_h

    # 引导线（可选）
    anchor = fix.get('anchor')
    if anchor:
        ax, ay = [rel_to_px(anchor[0], w), rel_to_px(anchor[1], h)]
        # 覆盖框边缘上离锚点最近的点
        ex = min(max(ax, x1), x2)
        ey = min(max(ay, y1), y2)
        # 把起点推到框边（若锚点在框内则画到框中心）
        if x1 <= ax <= x2 and y1 <= ay <= y2:
            ex, ey = (x1 + x2) / 2, (y1 + y2) / 2
        draw.line([(ex, ey), (ax, ay)], fill=fix.get('line_color', LINE_COLOR), width=2)
        r = 3
        draw.ellipse([ax - r, ay - r, ax + r, ay + r], fill=fix.get('line_color', LINE_COLOR))


def process(config_path):
    with open(config_path, encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    # 配置文件位于 annotate_configs/ 子目录，图片/输出路径相对其上一级（科目目录）
    base = os.path.dirname(os.path.dirname(os.path.abspath(config_path)))
    img_path = os.path.join(base, cfg['image']) if not os.path.isabs(cfg['image']) else cfg['image']
    out_path = os.path.join(base, cfg['output']) if not os.path.isabs(cfg['output']) else cfg['output']

    font_path = cfg.get('font', FONT_PATH)
    img = Image.open(img_path).convert('RGB')
    draw = ImageDraw.Draw(img)

    fixes = cfg.get('fixes', [])
    for fix in fixes:
        draw_fix(img, draw, fix, font_path)
        print(f"  ✔ {fix.get('text', '').replace(chr(10), ' ')[:30]}  box={fix['box']}")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, 'PNG')
    print(f'✅ 已生成: {out_path}  ({img.size[0]}x{img.size[1]}, {len(fixes)} 处修复)')
    return out_path


def main():
    parser = argparse.ArgumentParser(description='医学写实插图中文标注修复')
    parser.add_argument('configs', nargs='+', help='一个或多个 YAML 配置文件')
    args = parser.parse_args()
    for cfg in args.configs:
        print(f'📋 处理: {cfg}')
        process(cfg)


if __name__ == '__main__':
    main()
