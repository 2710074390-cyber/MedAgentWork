# -*- coding: utf-8 -*-
"""
compose_atlas.py — 出版图谱「多面板拼接 + 中文小标题带 + 程序标注」确定性合成器

定位
----
通道①「《人体解剖学彩色图谱》复用」专用：一张复习图往往需要把图谱中相邻的
2-3 个解剖视图拼成一张（如「鼓室外侧壁 + 鼓室内侧壁 + 听小骨」），或需要在
出版图上程序化叠加虚线轮廓/中文标注（如梅尼埃病「内淋巴积水」扩张边界）。
本脚本 YAML 驱动、纯 Pillow 确定性输出，不调文生图，可复现、可复核。

与其他脚本分工
--------------
- render_diagram.py  通道③：从零自绘流程/对比/分型图（无原始底图）
- annotate_image.py  通道①②：单张底图上叠文字 label/overlay
- compose_atlas.py   通道①：多张图谱面板拼接 + 小标题带 + 虚线标注（本脚本）

YAML 示例
---------
    title: 耳的应用解剖（外耳·中耳）        # 可选，顶部总标题
    output: annotated/01_xxx.png           # 相对科目目录（配置放 compose_configs/）
    webp: images_webp/01_xxx.webp          # 可选，同时出 1600px q82 部署版
    trim: true                             # 面板自动裁掉近白边，默认 true
    rows:
      - height: 1100                       # 可选，本行图片区目标高（px），超宽自动等比缩
        panels:
          - image: raw/01_鼓室外侧壁.jpg
            caption: 鼓室外侧壁（鼓膜与听骨链）
      - panels:                            # 不指定 height 时，按合并宽高比铺满行宽
          - image: raw/a.jpg
            caption: 鼓室内侧壁（前庭窗·蜗窗）
          - image: raw/b.jpg
            caption: 听小骨
            marks:                         # 可选：相对该面板（裁白边后）的千分比标注
              - type: ellipse              # ellipse | rect
                box: [120, 300, 480, 620]   # x1,y1,x2,y2，千分比 0-1000
                color: "#D14343"
                width: 6
                dash: [16, 12]             # 虚线 [实长, 空长]，默认实线
                label: 内淋巴积水扩张（示意）
                label_xy: [500, 250]       # 文字位置（千分比），可省略

用法
----
    python scripts/compose_atlas.py compose_configs/xxx.yaml
    python scripts/compose_atlas.py a.yaml b.yaml
"""
import sys
import os
import io
import math
import argparse

import yaml
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ---------- 工程常量（与 render_diagram.py 对齐） ----------
FONT_BOLD = r'C:\Windows\Fonts\msyhbd.ttc'
FONT_REG = r'C:\Windows\Fonts\msyh.ttc'
CANVAS_W = 2048
WEBP_W = 1600
WEBP_Q = 82
MARGIN = 56
GAP = 32
CAP_GAP = 14
TITLE_FS = 58
CAP_FS = 32
MARK_LABEL_FS = 34
TEXT_DARK = '#1A1B1C'
TEXT_GRAY = '#5C6470'
CAP_BG = '#EAF0F6'
CAP_DEEP = '#2F4863'
BG_WHITE = '#FFFFFF'

_MEASURE = ImageDraw.Draw(Image.new('RGB', (10, 10)))


def font(size, bold=True):
    path = FONT_BOLD if bold else (FONT_REG if os.path.exists(FONT_REG) else FONT_BOLD)
    return ImageFont.truetype(path, size)


F_TITLE = font(TITLE_FS, True)
F_CAP = font(CAP_FS, True)
F_MARK = font(MARK_LABEL_FS, True)


def text_w(text, fnt):
    return _MEASURE.textlength(text, font=fnt)


def wrap_line(text, fnt, max_w):
    """中文逐字、英文按词折行。"""
    out = []
    for raw in str(text).split('\n'):
        tokens, i = [], 0
        while i < len(raw):
            ch = raw[i]
            if ch.isspace():
                tokens.append(ch); i += 1
            elif ord(ch) < 128:
                j = i
                while j < len(raw) and ord(raw[j]) < 128 and not raw[j].isspace():
                    j += 1
                tokens.append(raw[i:j]); i = j
            else:
                tokens.append(ch); i += 1
        cur = ''
        for tok in tokens:
            trial = cur + tok
            if text_w(trial, fnt) > max_w and cur.strip():
                out.append(cur.rstrip()); cur = '' if tok.isspace() else tok.lstrip()
            else:
                cur = trial
        out.append(cur.rstrip())
    return out or ['']


def trim_white(img, tol=246, pad=10):
    """裁掉近白边（扫描/提取图常有大片留白），返回裁切后的图。"""
    gray = img.convert('L')
    mask = gray.point(lambda p: 0 if p >= tol else 255)
    bbox = mask.getbbox()
    if not bbox:
        return img
    l, t, r, b = bbox
    l = max(0, l - pad); t = max(0, t - pad)
    r = min(img.width, r + pad); b = min(img.height, b + pad)
    return img.crop((l, t, r, b))


def dashed_ellipse(draw, box, color, width, dash):
    """沿椭圆周线画虚线：按角度采样，dash=[实长,空长]（像素）。"""
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    rx, ry = max(1.0, (x2 - x1) / 2), max(1.0, (y2 - y1) / 2)
    on, off = dash
    # 周长近似（Ramanujan），换算角度步长
    perim = math.pi * (3 * (rx + ry) - math.sqrt((3 * rx + ry) * (rx + 3 * ry)))
    n = max(60, int(perim))   # 采样点数 ~= 周长像素数，保证平滑
    step = 2 * math.pi / n
    seg_on = max(1, int(n * on / perim))
    seg_off = max(1, int(n * off / perim))
    i, drawing = 0, True
    while i < n:
        run = seg_on if drawing else seg_off
        pts = []
        for k in range(run):
            a = (i + k) * step
            pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        if drawing and len(pts) >= 2:
            draw.line(pts, fill=color, width=width, joint='curve')
        i += run
        drawing = not drawing


def dashed_rect(draw, box, color, width, dash):
    """虚线矩形：四条边分别按 dash 铺。"""
    x1, y1, x2, y2 = box
    on, off = dash
    def dline(p1, p2, horizontal):
        length = abs((p2[0] - p1[0]) if horizontal else (p2[1] - p1[1]))
        pos, draw_on = 0, True
        while pos < length:
            run = min(on, length - pos) if draw_on else min(off, length - pos)
            if draw_on:
                if horizontal:
                    draw.line([(p1[0] + pos, p1[1]), (p1[0] + pos + run, p1[1])],
                              fill=color, width=width)
                else:
                    draw.line([(p1[0], p1[1] + pos), (p1[0], p1[1] + pos + run)],
                              fill=color, width=width)
            pos += run
            draw_on = not draw_on
    dline((x1, y1), (x2, y1), True)
    dline((x2, y1), (x2, y2), False)
    dline((x2, y2), (x1, y2), True)
    dline((x1, y2), (x1, y1), False)


# ---------- 两遍布局：先量后排 ----------
def load_panel(panel, base, do_trim):
    src = panel['image']
    path = src if os.path.isabs(src) else os.path.join(base, src)
    im = Image.open(path).convert('RGB')
    if do_trim and panel.get('trim', True):
        im = trim_white(im)
    return im


def caption_block(text, disp_w):
    """图注按面板宽度自适应字号（32→22）：短图注优先压字号保单行，
    到最小字号仍超宽才折行，避免窄面板出现孤字/孤括号换行。"""
    if not text:
        return [], 0, None, 0
    avail = max(40, disp_w - 28)
    for fs in (CAP_FS, 30, 28, 26, 24, 22):
        fnt = font(fs, True)
        full = text_w(str(text).replace('\n', ''), fnt)
        if full <= avail or fs == 22:
            lines = [str(text)] if full <= avail else wrap_line(text, fnt, avail)
            h = len(lines) * int(fs * 1.32) + 18
            return lines, h, fnt, fs


def layout_rows(cfg, base):
    do_trim = cfg.get('trim', True)
    content_w = CANVAS_W - 2 * MARGIN
    rows_out = []
    for row in cfg.get('rows', []):
        panels = []
        for p in row['panels']:
            im = load_panel(p, base, do_trim)
            panels.append({'cfg': p, 'img': im, 'asp': im.width / im.height})
        n = len(panels)
        gap_total = GAP * (n - 1)
        if row.get('height'):
            img_h = int(row['height'])
            widths = [int(img_h * p['asp']) for p in panels]
            if sum(widths) + gap_total > content_w:
                scale = content_w / (sum(widths) + gap_total)
                img_h = int(img_h * scale)
                widths = [int(w * scale) for w in widths]
        else:  # 等高等比铺满行宽
            sum_asp = sum(p['asp'] for p in panels)
            img_h = int((content_w - gap_total) / sum_asp)
            widths = [int(img_h * p['asp']) for p in panels]
        # 校正取整误差，差额加到最宽面板
        diff = content_w - (sum(widths) + gap_total)
        if diff != 0:
            k = max(range(n), key=lambda i: widths[i])
            widths[k] += diff
        cap_info, cap_h_max = [], 0
        for p, w in zip(panels, widths):
            info = caption_block(p['cfg'].get('caption'), w)
            cap_info.append(info); cap_h_max = max(cap_h_max, info[1])
        for p, w, (lines, ch, cfnt, cfs) in zip(panels, widths, cap_info):
            p['disp_w'] = w; p['cap_lines'] = lines; p['cap_h'] = ch
            p['cap_font'] = cfnt; p['cap_fs'] = cfs
        used_w = sum(widths) + GAP * (n - 1)
        x0 = MARGIN + max(0, (content_w - used_w) // 2)   # 不足行宽时整行居中
        rows_out.append({'panels': panels, 'img_h': img_h, 'x0': x0,
                         'row_h': img_h + (CAP_GAP + cap_h_max if cap_h_max else 0),
                         'cap_h_max': cap_h_max})
    return rows_out


def render(cfg, base):
    rows = layout_rows(cfg, base)
    # 标题高度
    y = MARGIN
    title_lines = []
    if cfg.get('title'):
        title_lines = wrap_line(cfg['title'], F_TITLE, CANVAS_W - 2 * MARGIN)
        y += len(title_lines) * int(TITLE_FS * 1.34) + 22
    total_h = y + sum(r['row_h'] for r in rows) + GAP * (len(rows) - 1) + MARGIN
    canvas = Image.new('RGB', (CANVAS_W, int(total_h)), BG_WHITE)
    d = ImageDraw.Draw(canvas)

    if title_lines:
        ty = MARGIN
        for line in title_lines:
            lw = text_w(line, F_TITLE)
            d.text(((CANVAS_W - lw) / 2, ty), line, font=F_TITLE, fill=TEXT_DARK)
            ty += int(TITLE_FS * 1.34)
        y = ty + 22

    for row in rows:
        x = row['x0']
        img_h = row['img_h']
        for p in row['panels']:
            w, h = p['disp_w'], img_h
            panel_img = p['img'].resize((w, h), Image.LANCZOS)
            canvas.paste(panel_img, (x, y))
            # 面板标注（marks，坐标按千分比映射到显示后的面板）
            for mk in p['cfg'].get('marks', []) or []:
                if mk.get('type') == 'note':
                    # 白底图例框：label_xy 为左上（千分比），w 为框宽（千分比）
                    note_w = int(mk.get('w', 380) / 1000 * w)
                    n_lines = wrap_line(mk['label'], F_MARK, note_w - 28)
                    lh = int(MARK_LABEL_FS * 1.3)
                    bw = max(text_w(ln, F_MARK) for ln in n_lines) + 30
                    bh = lh * len(n_lines) + 22
                    nx = x + mk['label_xy'][0] / 1000 * w
                    ny = y + mk['label_xy'][1] / 1000 * h
                    ncolor = mk.get('color', '#D14343')
                    d.rounded_rectangle([nx, ny, nx + bw, ny + bh], radius=12,
                                        fill='#FFFFFF', outline=ncolor, width=3)
                    ty = ny + 11
                    for ln in n_lines:
                        d.text((nx + 15, ty), ln, font=F_MARK, fill=ncolor)
                        ty += lh
                    continue
                bx1, by1, bx2, by2 = mk['box']
                mbox = [x + bx1 / 1000 * w, y + by1 / 1000 * h,
                        x + bx2 / 1000 * w, y + by2 / 1000 * h]
                color = mk.get('color', '#D14343')
                lw_ = int(mk.get('width', 6))
                dash = mk.get('dash')
                if mk.get('type', 'ellipse') == 'rect':
                    if dash:
                        dashed_rect(d, mbox, color, lw_, dash)
                    else:
                        d.rectangle(mbox, outline=color, width=lw_)
                else:
                    if dash:
                        dashed_ellipse(d, mbox, color, lw_, dash)
                    else:
                        d.ellipse(mbox, outline=color, width=lw_)
                if mk.get('label'):
                    lx, ly = mk.get('label_xy', [mk['box'][0], max(0, mk['box'][1] - 60)])
                    tx, ty_ = x + lx / 1000 * w, y + ly / 1000 * h
                    anchor = mk.get('anchor')
                    if anchor:
                        ax, ay = anchor
                        d.line([(tx, ty_ + MARK_LABEL_FS // 2),
                                (x + ax / 1000 * w, y + ay / 1000 * h)],
                               fill=color, width=4)
                    d.text((tx, ty_), mk['label'], font=F_MARK, fill=color,
                           stroke_width=4, stroke_fill='#FFFFFF')
            # 小标题带（居中浅底色块，字号随面板宽度自适应）
            if p['cap_lines']:
                cy = y + h + CAP_GAP
                lines = p['cap_lines']
                cfnt, cfs = p['cap_font'], p['cap_fs']
                line_h = int(cfs * 1.32)
                block_h = len(lines) * line_h + 14
                band = Image.new('RGB', (w, block_h), CAP_BG)
                bd = ImageDraw.Draw(band)
                bd.rounded_rectangle([0, 0, w - 1, block_h - 1], radius=14,
                                     fill=CAP_BG, outline=CAP_DEEP, width=2)
                ty = 7
                for line in lines:
                    lw = text_w(line, cfnt)
                    bd.text(((w - lw) / 2, ty), line, font=cfnt, fill=CAP_DEEP)
                    ty += line_h
                canvas.paste(band, (x, int(cy)))
            x += w + GAP
        y += row['row_h'] + GAP
    return canvas


def save_outputs(img, cfg, base):
    out = cfg['output']
    out_path = out if os.path.isabs(out) else os.path.join(base, out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, 'PNG')
    print(f'  ✔ PNG: {out_path}  ({img.size[0]}x{img.size[1]})')
    webp = cfg.get('webp')
    if webp:
        wp = webp if os.path.isabs(webp) else os.path.join(base, webp)
        os.makedirs(os.path.dirname(wp), exist_ok=True)
        h = round(img.size[1] * WEBP_W / img.size[0])
        img.resize((WEBP_W, h), Image.LANCZOS).save(wp, 'WEBP', quality=WEBP_Q, method=6)
        print(f'  ✔ WebP: {wp}  ({WEBP_W}x{h}, q={WEBP_Q})')


def process(config_path):
    with open(config_path, encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    if 'rows' not in cfg or 'output' not in cfg:
        raise ValueError(f'{config_path}: 必须含 rows 与 output 字段')
    base = os.path.dirname(os.path.dirname(os.path.abspath(config_path)))
    img = render(cfg, base)
    save_outputs(img, cfg, base)
    print(f'✅ compose: {cfg.get("title", "")}')


def main():
    parser = argparse.ArgumentParser(description='图谱多面板拼接合成器（rows/panels/caption/marks）')
    parser.add_argument('configs', nargs='+', help='一个或多个 YAML 配置')
    args = parser.parse_args()
    for p in args.configs:
        print(f'📋 合成: {p}')
        process(p)


if __name__ == '__main__':
    main()
