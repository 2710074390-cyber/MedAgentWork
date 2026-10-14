# -*- coding: utf-8 -*-
"""
render_diagram.py — 医学复习资料「图谱通道」确定性图示渲染器（YAML 驱动，Pillow 自绘）

定位
----
流程 / 决策 / 对比 / 时序 / 分型类知识点不再交给文生图模型（文字、箭头、步骤
数量必然出错），改为「内容 YAML（节点/关系/文字取自教材）→ 本脚本确定性渲染
→ PNG / WebP」，结构与文字 100% 可控、可复核、可复现。与 annotate_image.py
同属程序化图片管线：AI 只负责设计内容，不负责画。

支持图型（type）
---------------
- flow     流程/时序：steps 顺序节点 + 方向箭头（direction: horizontal|vertical）
- compare  对比/鉴别：items 并列分栏（2-4 栏最佳，无箭头）
- grid     分型网格：items 等大卡片，cols 指定列数（无箭头）
- waveform ECG 波形（P2-9）：beat 采样点确定性绘制 P-QRS-T，天然保证波形比例与
  波长正确、零幻觉；替代 ②卡通手画线稿。YAML：

      type: waveform
      title: 正常心电图波形
      beats: 3                       # 连续心动周期数（默认 3）
      wave_h: 720                    # 波形区高度（默认 680）
      beat:                          # 一个心动周期的采样点（x 0~1 周期内，y 0~1 顶部=0）
        - {label: P, x: 0.12, y: 0.30}
        - {label: Q, x: 0.26, y: 0.40}
        - {label: R, x: 0.30, y: 0.05}    # R 峰最高（y 最小）
        - {label: S, x: 0.35, y: 0.42}
        - {label: T, x: 0.68, y: 0.26}
      color: red                     # 可选，波形颜色（默认红）
      output: annotated/xxx.png
      webp: images_webp/xxx.webp

视觉
----
扁平色块（flat）：白底、柔和平涂、深色粗描边标题带、圆角卡片；固定医学色板，
与 AI 扁平卡通无字底图共用同一套色彩语言。

YAML 示例
---------
    type: flow                       # flow | compare | grid
    title: 休克·微循环三期变化
    subtitle: 急诊与灾难医学 M5       # 可选
    note: 依据人卫《急诊与灾难医学》  # 可选，底部灰字
    direction: horizontal            # 仅 flow：horizontal（默认）| vertical
    numbered: true                   # 仅 flow：标题带前加序号，默认 true
    cols: 3                          # 仅 grid：每行卡片数
    output: annotated/xxx.png        # 相对科目目录（配置位于 diagram_configs/ 时）
    webp: images_webp/xxx.webp       # 可选，同时输出 1600px q82 的部署版
    steps:                           # compare/grid 用 items
      - title: 缺血缺氧期（代偿）
        color: blue                  # blue/teal/green/orange/yellow/red/purple/gray
        lines:
          - 微动脉、毛细血管前括约肌收缩
          - 真毛细血管网关闭，灌少于流

用法
----
    python scripts/render_diagram.py diagram_configs/xxx.yaml
    python scripts/render_diagram.py a.yaml b.yaml
"""
import sys
import os
import io
import argparse

import yaml
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ---------- 工程常量（与 annotate_image.py / 压缩规范对齐） ----------
FONT_BOLD = r'C:\Windows\Fonts\msyhbd.ttc'      # 微软雅黑 Bold（标题）
FONT_REG = r'C:\Windows\Fonts\msyh.ttc'        # 微软雅黑 Regular（正文，缺失回退 Bold）
CANVAS_W = 2048                                # PNG 画布宽（与标注管线一致）
WEBP_W = 1600                                  # 部署版宽
WEBP_Q = 82
MARGIN = 72
GAP = 32
RADIUS = 26
ARROW_W = 56                                   # 相邻卡片间箭头占位
TITLE_FS = 60
SUB_FS = 34
CARD_TITLE_FS = 40
BODY_FS = 34
BODY_FS_NARROW = 30                            # 每行 ≥4 栏时正文字号
NOTE_FS = 30
CARD_PAD = 30
BAND_PAD_X = 24
BODY_LINE_GAP = 12
TEXT_DARK = '#1A1B1C'
TEXT_GRAY = '#5C6470'
ARROW_COLOR = '#8A94A6'
BG_WHITE = '#FFFFFF'

# 扁平医学色板：(浅底, 深色标题带/描边)。语义：blue 结构/通路、green 正常/代偿、
# orange 进展/警示、red 病变/衰竭、teal 对照、purple 特殊、yellow 分期、gray 中性
PALETTE = {
    'blue':   ('#DCEBFA', '#2F6DB5'),
    'teal':   ('#D7F0EC', '#2E8B80'),
    'green':  ('#DFF1E2', '#3F9A57'),
    'orange': ('#FCE6D6', '#D17A3C'),
    'yellow': ('#FAF0CF', '#A98A26'),
    'red':    ('#F9DEDE', '#C0504D'),
    'purple': ('#EDE1F7', '#8A5CB8'),
    'gray':   ('#E9ECEF', '#5C6470'),
}
DEFAULT_COLOR = 'blue'

# ---- 读取单一配置源（medillustration_config.yaml）覆盖默认常量（P1-4 / P2-8）----
try:
    from medillustration_config import load as _load_cfg
    _cfg = _load_cfg()
    if _cfg:
        _fnt = _cfg.get('fonts') or {}
        _cv = _cfg.get('canvas') or {}
        if _fnt.get('bold'):
            FONT_BOLD = _fnt['bold']
        if _fnt.get('regular'):
            FONT_REG = _fnt['regular']
        if _cv.get('png_width'):
            CANVAS_W = int(_cv['png_width'])
        if _cv.get('webp_width'):
            WEBP_W = int(_cv['webp_width'])
        if _cv.get('webp_quality'):
            WEBP_Q = int(_cv['webp_quality'])
        _cols = _cfg.get('colors') or {}
        for _k in PALETTE:
            if _cols.get(_k):
                PALETTE[_k] = (PALETTE[_k][0], _cols[_k])
except Exception as _e:  # 配置缺失/损坏时回退默认常量，不阻断渲染
    print(f"[render_diagram] 配置加载失败，使用默认常量：{_e}")


def load_fonts():
    reg = FONT_REG if os.path.exists(FONT_REG) else FONT_BOLD
    return {
        'title': ImageFont.truetype(FONT_BOLD, TITLE_FS),
        'sub': ImageFont.truetype(reg, SUB_FS),
        'card_title': ImageFont.truetype(FONT_BOLD, CARD_TITLE_FS),
        'body': ImageFont.truetype(reg, BODY_FS),
        'note': ImageFont.truetype(reg, NOTE_FS),
    }


# 用一个离屏 draw 做文字测量（第一遍布局用）
_MEASURE = ImageDraw.Draw(Image.new('RGB', (10, 10)))


def text_w(text, font):
    return _MEASURE.textlength(text, font=font)


def wrap_line(text, font, max_w):
    """按宽度折行：中文逐字、英文/数字按词，保留显式 \\n。"""
    out = []
    for raw in str(text).split('\n'):
        if not raw:
            out.append('')
            continue
        # 先分词：CJK 单字一个 token；ASCII 连续词、空格各为一个 token
        tokens, i = [], 0
        while i < len(raw):
            ch = raw[i]
            if ch.isspace():
                tokens.append(ch)
                i += 1
            elif ord(ch) < 128:
                j = i
                while j < len(raw) and ord(raw[j]) < 128 and not raw[j].isspace():
                    j += 1
                tokens.append(raw[i:j])
                i = j
            else:
                tokens.append(ch)
                i += 1
        cur = ''
        for tok in tokens:                        # 逐 token 试排，超宽就换行
            trial = cur + tok
            if text_w(trial, font) > max_w and cur.strip():
                out.append(cur.rstrip())
                cur = '' if tok.isspace() else tok.lstrip()
            else:
                cur = trial
        out.append(cur.rstrip())
    return out or ['']


def resolve_items(cfg):
    """三种图型统一成 items 列表；返回 (items, show_arrow)。"""
    t = cfg['type']
    if t == 'flow':
        items = cfg.get('steps', [])
        numbered = cfg.get('numbered', True)
        for idx, it in enumerate(items, 1):
            it.setdefault('color', DEFAULT_COLOR)
            if numbered and not it.get('badge'):
                it['badge'] = str(idx)
        return items, True
    if t in ('compare', 'grid'):
        items = cfg.get('items', [])
        for it in items:
            it.setdefault('color', DEFAULT_COLOR)
        return items, False
    raise ValueError(f"未知 type={t}，仅支持 flow / compare / grid")


def per_row_count(cfg, n):
    if cfg['type'] == 'flow' and cfg.get('direction') == 'vertical':
        return 1
    if cfg['type'] == 'grid':
        return max(1, int(cfg.get('cols', 3)))
    return min(n, 4)                               # flow/compare 每行最多 4 栏


def fit_band_title(title, max_w):
    """标题优先单行：40px 起逐档缩到 30px；仍超才按最小字号折行，避免孤字换行。"""
    fs = CARD_TITLE_FS
    font = ImageFont.truetype(FONT_BOLD, fs)
    while fs > 30 and text_w(title, font) > max_w:
        fs -= 2
        font = ImageFont.truetype(FONT_BOLD, fs)
    lines = [title] if text_w(title, font) <= max_w else wrap_line(title, font, max_w)
    return font, fs, lines


def measure_card(it, card_w, fonts, body_font, body_fs):
    """返回折行后的标题/正文行与卡片高（窄栏用更小正文字号避免孤字折行）。"""
    inner_w = card_w - 2 * CARD_PAD
    title = ((it['badge'] + '. ') if it.get('badge') else '') + it['title']
    tfont, tfs, title_lines = fit_band_title(title, inner_w - 2 * BAND_PAD_X)
    band_h = max(76, len(title_lines) * int(tfs * 1.35) + 28)
    body_lines = []
    bullet_w = text_w('· ', body_font)         # 绘制时的圆点前缀也要占宽
    for ln in it.get('lines', []) or []:
        body_lines.extend(wrap_line(ln, body_font, inner_w - bullet_w))
    body_h = len(body_lines) * int(body_fs * 1.5) if body_lines else 0
    card_h = band_h + CARD_PAD + body_h + CARD_PAD
    return {'title_lines': title_lines, 'body_lines': body_lines,
            'band_h': band_h, 'h': card_h, 'title_font': tfont, 'title_fs': tfs,
            'body_font': body_font, 'body_fs': body_fs}


def chunk_rows(items, per_row):
    return [items[i:i + per_row] for i in range(0, len(items), per_row)]


def layout(cfg, fonts):
    items, show_arrow = resolve_items(cfg)
    if not items:
        raise ValueError('steps/items 为空，无法渲染')
    n = len(items)
    pr = per_row_count(cfg, n)
    arrow_total = (pr - 1) * ARROW_W if show_arrow else 0
    card_w = (CANVAS_W - 2 * MARGIN - (pr - 1) * GAP - arrow_total) // pr
    body_fs = BODY_FS if pr <= 3 else BODY_FS_NARROW
    body_font = ImageFont.truetype(FONT_REG if os.path.exists(FONT_REG) else FONT_BOLD, body_fs)
    rows = chunk_rows(items, pr)

    # 标题区
    y = MARGIN
    title_lines = wrap_line(cfg.get('title', ''), fonts['title'], CANVAS_W - 2 * MARGIN)
    y += len(title_lines) * int(TITLE_FS * 1.35)
    if cfg.get('subtitle'):
        y += int(SUB_FS * 1.5)
    y += 20

    measured_rows = []
    for row in rows:
        row_cells = []
        row_h = 0
        for it in row:
            m = measure_card(it, card_w, fonts, body_font, body_fs)
            row_cells.append((it, m))
            row_h = max(row_h, m['h'])
        measured_rows.append(row_cells)
        y += row_h + (ARROW_W if show_arrow else 0) + GAP
    total_h = y - GAP
    if cfg.get('note'):
        total_h += int(NOTE_FS * 1.6)
    total_h += MARGIN
    return {'rows': measured_rows, 'card_w': card_w, 'show_arrow': show_arrow,
            'title_lines': title_lines, 'total_h': total_h}


# ---------- 绘制 ----------
def draw_arrow_right(draw, x, y, h):
    cy = y + h // 2
    draw.line([(x, cy), (x + ARROW_W - 18, cy)], fill=ARROW_COLOR, width=8)
    draw.polygon([(x + ARROW_W - 18, cy - 14), (x + ARROW_W, cy),
                  (x + ARROW_W - 18, cy + 14)], fill=ARROW_COLOR)


def draw_arrow_down(draw, x_center, y):
    draw.line([(x_center, y), (x_center, y + ARROW_W - 18)], fill=ARROW_COLOR, width=8)
    draw.polygon([(x_center - 14, y + ARROW_W - 18), (x_center + 14, y + ARROW_W - 18),
                  (x_center, y + ARROW_W)], fill=ARROW_COLOR)


def draw_card(draw, x, y, w, h, it, m, fonts):
    fill, deep = PALETTE.get(it.get('color', DEFAULT_COLOR), PALETTE[DEFAULT_COLOR])
    draw.rounded_rectangle([x, y, x + w, y + h], radius=RADIUS, fill=fill,
                           outline=deep, width=3)
    # 顶部深色标题带（仅上方圆角）
    band_h = m['band_h']
    draw.rounded_rectangle([x, y, x + w, y + band_h], radius=RADIUS, fill=deep)
    draw.rectangle([x, y + band_h - RADIUS, x + w, y + band_h], fill=deep)
    ty = y + 18
    for line in m['title_lines']:
        lw = text_w(line, m['title_font'])
        draw.text((x + (w - lw) / 2, ty), line, font=m['title_font'], fill='#FFFFFF')
        ty += int(m['title_fs'] * 1.35)
    # 正文（圆点与文字分开绘制，折行后的续行与首行对齐）
    by = y + band_h + CARD_PAD
    body_font = m['body_font']
    bullet_w = text_w('· ', body_font)
    for line in m['body_lines']:
        if line:
            draw.text((x + CARD_PAD, by), '·', font=body_font, fill=TEXT_DARK)
            draw.text((x + CARD_PAD + bullet_w, by), line,
                      font=body_font, fill=TEXT_DARK)
        by += int(m['body_fs'] * 1.5)


def render_waveform(cfg, fonts):
    """waveform 型：按采样点确定性绘制 ECG 波形（P-QRS-T），零幻觉。"""
    beat_pts = cfg.get('beat') or []
    if not beat_pts:
        raise ValueError('waveform 型必须提供 beat（一个心动周期采样点列表）')
    beats = int(cfg.get('beats', 3))
    wave_h = int(cfg.get('wave_h', 680))
    color = cfg.get('color', 'red')
    _, wave_col = PALETTE.get(color, PALETTE['red'])

    # 标题区（与 render() 对齐）
    title_lines = wrap_line(cfg.get('title', ''), fonts['title'], CANVAS_W - 2 * MARGIN)
    y = MARGIN + len(title_lines) * int(TITLE_FS * 1.35)
    if cfg.get('subtitle'):
        y += int(SUB_FS * 1.5)
    y += 30

    total_h = y + wave_h + 40
    if cfg.get('note'):
        total_h += int(NOTE_FS * 1.6)
    total_h += MARGIN
    img = Image.new('RGB', (CANVAS_W, total_h), BG_WHITE)
    d = ImageDraw.Draw(img)

    y = MARGIN
    for line in title_lines:
        lw = text_w(line, fonts['title'])
        d.text(((CANVAS_W - lw) / 2, y), line, font=fonts['title'], fill=TEXT_DARK)
        y += int(TITLE_FS * 1.35)
    if cfg.get('subtitle'):
        lw = text_w(cfg['subtitle'], fonts['sub'])
        d.text(((CANVAS_W - lw) / 2, y), cfg['subtitle'], font=fonts['sub'], fill=TEXT_GRAY)
        y += int(SUB_FS * 1.5)
    y += 30

    x0, x1 = MARGIN, CANVAS_W - MARGIN
    baseline = y + int(0.72 * wave_h)
    d.line([(x0, baseline), (x1, baseline)], fill=TEXT_GRAY, width=3)  # 基线
    beat_w = (x1 - x0) / beats

    # 小格参考线（每 1/8 周期一条浅灰竖线）
    for i in range(1, beats * 8):
        gx = x0 + i * beat_w / 8
        d.line([(gx, y), (gx, y + wave_h)], fill='#ECF0F5', width=2)

    lab_font = fonts['card_title'] if 'card_title' in fonts else fonts['title']
    for b in range(beats):
        pts = []
        for p in beat_pts:
            px = x0 + (b + p['x']) * beat_w
            py = y + int(p['y'] * 0.72 * wave_h)
            pts.append((px, py))
        # 周期起点/终点接到基线
        full = [(x0 + b * beat_w, baseline)] + pts + [(x0 + (b + 1) * beat_w, baseline)]
        d.line(full, fill=wave_col, width=7, joint='curve')
        for p, (px, py) in zip(beat_pts, pts):
            label = p.get('label', '')
            if not label:
                continue
            lw = text_w(label, lab_font)
            above = py <= baseline
            ly = py - int(1.15 * NOTE_FS) if above else py + 6
            d.text((px - lw / 2, ly), label, font=lab_font, fill=TEXT_DARK)

    y2 = y + wave_h + 20
    if cfg.get('note'):
        lw = text_w(cfg['note'], fonts['note'])
        d.text(((CANVAS_W - lw) / 2, y2), cfg['note'], font=fonts['note'], fill=TEXT_GRAY)
    return img


def render(cfg, fonts):
    if cfg['type'] == 'waveform':
        return render_waveform(cfg, fonts)
    lay = layout(cfg, fonts)
    img = Image.new('RGB', (CANVAS_W, lay['total_h']), BG_WHITE)
    d = ImageDraw.Draw(img)

    y = MARGIN
    for line in lay['title_lines']:
        lw = text_w(line, fonts['title'])
        d.text(((CANVAS_W - lw) / 2, y), line, font=fonts['title'], fill=TEXT_DARK)
        y += int(TITLE_FS * 1.35)
    if cfg.get('subtitle'):
        lw = text_w(cfg['subtitle'], fonts['sub'])
        d.text(((CANVAS_W - lw) / 2, y), cfg['subtitle'], font=fonts['sub'], fill=TEXT_GRAY)
        y += int(SUB_FS * 1.5)
    y += 20

    cw = lay['card_w']
    for r_idx, row_cells in enumerate(lay['rows']):
        row_h = max(m['h'] for _, m in row_cells)
        x = MARGIN
        for c_idx, (it, m) in enumerate(row_cells):
            draw_card(d, x, y, cw, row_h, it, m, fonts)
            x += cw
            if lay['show_arrow'] and c_idx < len(row_cells) - 1:
                draw_arrow_right(d, x + (GAP - ARROW_W) // 2, y, row_h)
                x += GAP + ARROW_W
            else:
                x += GAP
        y += row_h
        if lay['show_arrow'] and r_idx < len(lay['rows']) - 1:
            draw_arrow_down(d, CANVAS_W // 2, y)
            y += ARROW_W
        y += GAP

    if cfg.get('note'):
        lw = text_w(cfg['note'], fonts['note'])
        d.text(((CANVAS_W - lw) / 2, y + 4), cfg['note'], font=fonts['note'], fill=TEXT_GRAY)
    return img


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
    if 'type' not in cfg or 'output' not in cfg:
        raise ValueError(f'{config_path}: 必须含 type 与 output 字段')
    # 配置位于 diagram_configs/ 子目录时，路径相对其上一级（科目目录），与 annotate 一致
    base = os.path.dirname(os.path.dirname(os.path.abspath(config_path)))
    fonts = load_fonts()
    img = render(cfg, fonts)
    save_outputs(img, cfg, base)
    print(f'✅ {cfg["type"]}: {cfg.get("title", "")}')


def main():
    parser = argparse.ArgumentParser(description='医学图谱通道确定性图示渲染（flow/compare/grid/waveform）')
    parser.add_argument('configs', nargs='+', help='一个或多个 YAML 配置文件')
    args = parser.parse_args()
    for p in args.configs:
        print(f'📋 渲染: {p}')
        process(p)


if __name__ == '__main__':
    main()
