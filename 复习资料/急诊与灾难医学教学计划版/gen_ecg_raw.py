# -*- coding: utf-8 -*-
"""
生成 16_可除颤心律 与 17_不可除颤心律 的无字底图（扁平矢量风格）。
两帧并排 ECG 波形，2048x1152 (16:9)。
"""
import os
import numpy as np
from PIL import Image, ImageDraw

W, H = 2048, 1152

# ---- 布局 ----
MARGIN = 90
DIVIDER_X = W // 2
GAP = 40
LEFT_X1 = MARGIN
LEFT_X2 = DIVIDER_X - GAP // 2
RIGHT_X1 = DIVIDER_X + GAP // 2
RIGHT_X2 = W - MARGIN

GRID_Y1 = 100
GRID_Y2 = H - 220          # 底部留标注区
Y_BASE = H // 2            # 波形基线

# ---- 色板（≤4 主色/图）----
WHITE       = (255, 255, 255)
GRID_MINOR  = (235, 235, 235)
GRID_MAJOR  = (215, 215, 215)
DIVIDER     = (170, 170, 170)

RED_WAVE    = (200, 40, 40)    # 图1 波形
GRAY_WAVE   = (90, 90, 90)     # 图2 PEA 波形
DARK_GRAY   = (70, 70, 70)     # 图2 等电位线
HEART_GRAY  = (185, 185, 185)  # 图2 心脏轮廓


def draw_grid(draw, x1, x2, y1, y2):
    """淡灰心电图纸网格"""
    for x in range(x1, x2 + 1, 20):
        draw.line([(x, y1), (x, y2)], fill=GRID_MINOR, width=1)
    for y in range(y1, y2 + 1, 20):
        draw.line([(x1, y), (x2, y)], fill=GRID_MINOR, width=1)
    for x in range(x1, x2 + 1, 100):
        draw.line([(x, y1), (x, y2)], fill=GRID_MAJOR, width=1)
    for y in range(y1, y2 + 1, 100):
        draw.line([(x1, y), (x2, y)], fill=GRID_MAJOR, width=1)


# ==================== 波形生成 ====================

def gen_vf(n, amp=85):
    """心室颤动：杂乱无章、大小各异的颤动波"""
    rng = np.random.RandomState(42)
    t = np.linspace(0, 1, n)
    sig = np.zeros(n)
    # 多频率叠加，幅度随机
    for _ in range(10):
        f = rng.uniform(4, 30)
        ph = rng.uniform(0, 2 * np.pi)
        a = rng.uniform(0.2, 1.0)
        sig += a * np.sin(2 * np.pi * f * t + ph)
    # 高频锯齿
    sig += rng.normal(0, 0.35, n)
    # 包络调制，模拟大小波交替
    env = 0.6 + 0.4 * np.sin(2 * np.pi * 3 * t + 1.5)
    sig *= env
    # 归一化
    peak = np.max(np.abs(sig))
    if peak > 0:
        sig = sig / peak * amp
    return sig


def gen_vt(n, n_complexes=6, amp=115):
    """无脉性室速：宽而规则的大 QRS 波群，无 P 波"""
    spacing = n / n_complexes
    sig = np.zeros(n)
    for i in range(n_complexes):
        c = i * spacing + spacing / 2
        # 宽 QRS：总宽约 spacing * 0.35（很宽）
        hw = spacing * 0.18   # 半宽
        for k in range(n):
            rel = (k - c) / hw
            if abs(rel) <= 1.5:
                # 主 R 波（高耸）
                if -0.6 <= rel <= 0.3:
                    sig[k] += amp * np.exp(-((rel - 0.02) / 0.22) ** 2)
                # S 波（深负向）
                if 0.1 <= rel <= 1.0:
                    sig[k] -= amp * 0.55 * np.exp(-((rel - 0.55) / 0.28) ** 2)
                # Q 波（小负向起始）
                if -1.0 <= rel <= -0.5:
                    sig[k] -= amp * 0.15 * np.exp(-((rel + 0.75) / 0.18) ** 2)
    return sig


def gen_normal_rhythm(n, n_complexes=9, amp=55):
    """有规则电活动（P-QRS-T），用于 PEA 面板"""
    spacing = n / n_complexes
    sig = np.zeros(n)
    for i in range(n_complexes):
        c = i * spacing + spacing / 2

        # P 波（小鼓包，QRS 前）
        pc = c - spacing * 0.28
        pw = spacing * 0.06
        for k in range(n):
            rel = (k - pc) / pw
            if abs(rel) <= 2:
                sig[k] += amp * 0.18 * np.exp(-rel ** 2 * 2.5)

        # QRS（窄而尖）
        qrs_hw = spacing * 0.035
        for k in range(n):
            rel = (k - c) / qrs_hw
            if rel > 0:
                sig[k] += amp * np.exp(-(rel / 0.6) ** 2)
            else:
                sig[k] -= amp * 0.35 * np.exp(-(rel / 0.6) ** 2)

        # T 波（圆钝鼓包，QRS 后）
        tc = c + spacing * 0.25
        tw = spacing * 0.09
        for k in range(n):
            rel = (k - tc) / tw
            if abs(rel) <= 2:
                sig[k] += amp * 0.28 * np.exp(-rel ** 2 * 1.8)
    return sig


def gen_asystole(n, amp=2.5):
    """心室静止：近平直等电位线，偶有微小波动"""
    rng = np.random.RandomState(99)
    # 极低频漂移 + 微小噪声
    t = np.linspace(0, 1, n)
    drift = 1.5 * np.sin(2 * np.pi * 1.5 * t)
    noise = rng.normal(0, 0.6, n)
    sig = drift + noise
    peak = np.max(np.abs(sig))
    if peak > 0:
        sig = sig / peak * amp
    return sig


def draw_wave(draw, wave, x_start, y_base, color, width=4):
    """把波形数组画成平滑折线"""
    pts = []
    for i, yv in enumerate(wave):
        x = x_start + i
        y = int(round(y_base - yv))
        pts.append((x, y))
    draw.line(pts, fill=color, width=width, joint="curve")


def draw_heart_x(draw, cx, cy, s=50, color=HEART_GRAY):
    """灰色心脏轮廓 + 叉号（表示无泵血）"""
    # 心形轮廓（两个圆弧顶 + 尖角底）
    # 左弧
    draw.arc([cx - s, cy - s, cx, cy + s // 4],
             start=200, end=340, fill=color, width=3)
    # 右弧
    draw.arc([cx, cy - s, cx + s, cy + s // 4],
             start=200, end=340, fill=color, width=3)
    # 底部尖角
    draw.line([(cx - s, cy + s // 6), (cx, cy + int(s * 1.15))],
              fill=color, width=3)
    draw.line([(cx + s, cy + s // 6), (cx, cy + int(s * 1.15))],
              fill=color, width=3)
    # 叉号
    d = int(s * 0.45)
    draw.line([(cx - d, cy - d // 2), (cx + d, cy + d // 2)],
              fill=color, width=4)
    draw.line([(cx - d, cy + d // 2), (cx + d, cy - d // 2)],
              fill=color, width=4)


# ==================== 出图 ====================

def make_img1():
    """可除颤心律：VF（左）+ VT（右），红色波形"""
    img = Image.new("RGB", (W, H), WHITE)
    dr = ImageDraw.Draw(img)

    draw_grid(dr, LEFT_X1, LEFT_X2, GRID_Y1, GRID_Y2)
    draw_grid(dr, RIGHT_X1, RIGHT_X2, GRID_Y1, GRID_Y2)
    dr.line([(DIVIDER_X, GRID_Y1), (DIVIDER_X, GRID_Y2)],
            fill=DIVIDER, width=2)

    # VF
    n_l = LEFT_X2 - LEFT_X1
    vf = gen_vf(n_l, amp=80)
    draw_wave(dr, vf, LEFT_X1, Y_BASE, RED_WAVE, width=4)

    # VT
    n_r = RIGHT_X2 - RIGHT_X1
    vt = gen_vt(n_r, n_complexes=6, amp=110)
    draw_wave(dr, vt, RIGHT_X1, Y_BASE, RED_WAVE, width=4)

    return img


def make_img2():
    """不可除颤心律：PEA（左）+ Asystole（右），灰色系"""
    img = Image.new("RGB", (W, H), WHITE)
    dr = ImageDraw.Draw(img)

    draw_grid(dr, LEFT_X1, LEFT_X2, GRID_Y1, GRID_Y2)
    draw_grid(dr, RIGHT_X1, RIGHT_X2, GRID_Y1, GRID_Y2)
    dr.line([(DIVIDER_X, GRID_Y1), (DIVIDER_X, GRID_Y2)],
            fill=DIVIDER, width=2)

    # PEA：规则电活动波形
    n_l = LEFT_X2 - LEFT_X1
    pea = gen_normal_rhythm(n_l, n_complexes=9, amp=50)
    draw_wave(dr, pea, LEFT_X1, Y_BASE, GRAY_WAVE, width=4)

    # 心脏轮廓+叉号（左面板上部）
    hx = (LEFT_X1 + LEFT_X2) // 2
    hy = GRID_Y1 + 90
    draw_heart_x(dr, hx, hy, s=48, color=HEART_GRAY)

    # Asystole：近平直
    n_r = RIGHT_X2 - RIGHT_X1
    asy = gen_asystole(n_r, amp=2.5)
    draw_wave(dr, asy, RIGHT_X1, Y_BASE, DARK_GRAY, width=4)

    return img


if __name__ == "__main__":
    base = r"C:\Users\38063\Desktop\MedAgentWork\复习资料\急诊与灾难医学教学计划版"
    raw_dir = os.path.join(base, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    p1 = os.path.join(raw_dir, "16_可除颤心律_raw.png")
    make_img1().save(p1)
    print(f"OK -> {p1}")

    p2 = os.path.join(raw_dir, "17_不可除颤心律_raw.png")
    make_img2().save(p2)
    print(f"OK -> {p2}")
