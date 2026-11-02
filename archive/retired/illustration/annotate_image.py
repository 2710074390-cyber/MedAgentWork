# -*- coding: utf-8 -*-
"""
annotate_image.py — 医学写实插图中文标注工具（YAML 驱动，项目级）

两种标注模式：
- overlay（默认）：白底圆角覆盖块 + 文字，用于盖住原图乱码/英文标注后重写中文
- label（新增）：无背景块，深色文字 + 白色描边直接写在图上，不遮挡图片内容
                   （出版物解剖图谱标准样式，适合干净底图/图谱图的标注）

通用参数：
- box：千分比相对坐标 [x1,y1,x2,y2]（0-1000，左上原点），与分辨率无关
- text：支持 \n 换行（多行标注）
- anchor：可选引导线终点 [x,y]（千分比），从标注框边缘画线指向结构
- mode："overlay"（默认）或 "label"
- label 模式额外参数：stroke_width（默认 3）、stroke_fill（默认 #FFFFFF）

用法：
    python scripts/annotate_image.py annotate_configs/xxx.yaml
    python scripts/annotate_image.py config1.yaml config2.yaml
"""
import sys
import os
import io
import argparse

import yaml
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

FONT_PATH = r'C:\Windows\Fonts\msyhbd.ttc'   # 微软雅黑 Bold

# 字体路径取自单一配置源 medillustration_config.yaml（P1-4 / P2-8），缺失时回退默认
try:
    from medillustration_config import fonts as _fonts_cfg
    _f = _fonts_cfg()
    if _f.get('bold'):
        FONT_PATH = _f['bold']
except Exception:
    pass
TEXT_COLOR = '#1A1B1C'
LINE_COLOR = '#333333'
DEFAULT_BG = '#FFFFFF'
DEFAULT_PADDING = 8   # overlay 模式覆盖框外扩像素
DEFAULT_STROKE_WIDTH = 3
DEFAULT_STROKE_FILL = '#FFFFFF'


def rel_to_px(rel, size):
    """千分比 -> 像素"""
    return int(round(rel / 1000.0 * size))


def fit_font(draw, font_path, text_lines, box_w, box_h, stroke_w=0):
    """自适应字号：不超框宽、不超框高（label 模式需扣除描边宽度）"""
    avail_w = box_w - stroke_w * 2
    avail_h = box_h - stroke_w * 2
    font_size = int(avail_h / len(text_lines) * 0.92)
    font_size = max(12, font_size)
    while font_size > 12:
        font = ImageFont.truetype(font_path, font_size)
        max_lw = max(draw.textlength(line, font=font) for line in text_lines)
        if max_lw <= avail_w * 0.98 and font_size * 1.25 * len(text_lines) <= avail_h * 1.02:
            break
        font_size -= 1
    return ImageFont.truetype(font_path, font_size)


def draw_anchor_line(draw, anchor, x1, y1, x2, y2, w, h, line_color):
    """绘制引导线（overlay 和 label 模式共用）"""
    ax, ay = [rel_to_px(anchor[0], w), rel_to_px(anchor[1], h)]
    ex = min(max(ax, x1), x2)
    ey = min(max(ay, y1), y2)
    if x1 <= ax <= x2 and y1 <= ay <= y2:
        ex, ey = (x1 + x2) / 2, (y1 + y2) / 2
    draw.line([(ex, ey), (ax, ay)], fill=line_color, width=2)
    r = 3
    draw.ellipse([ax - r, ay - r, ax + r, ay + r], fill=line_color)


def draw_fix(img, draw, fix, font_path):
    """绘制单条标注"""
    w, h = img.size
    text = fix.get('text', '').strip()
    if not text:
        return

    mode = fix.get('mode', 'overlay')
    x1, y1, x2, y2 = [rel_to_px(v, w if i % 2 == 0 else h) for i, v in enumerate(fix['box'])]

    if mode == 'label':
        # label 模式：无背景块，描边文字直接写在图上
        stroke_w = fix.get('stroke_width', DEFAULT_STROKE_WIDTH)
        stroke_fill = fix.get('stroke_fill', DEFAULT_STROKE_FILL)
        text_color = fix.get('text_color', TEXT_COLOR)
        lines = text.split('\n')
        font = fit_font(draw, font_path, lines, x2 - x1, y2 - y1, stroke_w=stroke_w)
        line_h = int(font.size * 1.3) + stroke_w
        total_h = line_h * len(lines)
        y = y1 + (y2 - y1 - total_h) / 2 + stroke_w / 2
        for line in lines:
            lw = draw.textlength(line, font=font)
            draw.text(
                (x1 + (x2 - x1 - lw) / 2, y),
                line, font=font, fill=text_color,
                stroke_width=stroke_w, stroke_fill=stroke_fill,
            )
            y += line_h
    else:
        # overlay 模式（默认）：白底覆盖块 + 文字
        pad = fix.get('padding', DEFAULT_PADDING)
        bg = fix.get('background', DEFAULT_BG)
        x1 -= pad; y1 -= pad; x2 += pad; y2 += pad
        draw.rounded_rectangle([x1, y1, x2, y2], radius=8, fill=bg)
        lines = text.split('\n')
        font = fit_font(draw, font_path, lines, x2 - x1, y2 - y1)
        line_h = int(font.size * 1.3)
        total_h = line_h * len(lines)
        y = y1 + (y2 - y1 - total_h) / 2
        for line in lines:
            lw = draw.textlength(line, font=font)
            draw.text((x1 + (x2 - x1 - lw) / 2, y), line, font=font, fill=fix.get('text_color', TEXT_COLOR))
            y += line_h

    # 引导线（可选，两种模式都支持）
    anchor = fix.get('anchor')
    if anchor:
        draw_anchor_line(draw, anchor, x1, y1, x2, y2, w, h, fix.get('line_color', LINE_COLOR))


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
        mode_tag = fix.get('mode', 'overlay')
        print(f"  ✔ [{mode_tag}] {fix.get('text', '').replace(chr(10), ' ')[:30]}  box={fix['box']}")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, 'PNG')
    print(f'✅ 已生成: {out_path}  ({img.size[0]}x{img.size[1]}, {len(fixes)} 处标注)')
    return out_path


def main():
    parser = argparse.ArgumentParser(description='医学写实插图中文标注工具（overlay 覆盖 / label 描边）')
    parser.add_argument('configs', nargs='+', help='一个或多个 YAML 配置文件')
    args = parser.parse_args()
    for cfg in args.configs:
        print(f'📋 处理: {cfg}')
        process(cfg)


if __name__ == '__main__':
    main()
