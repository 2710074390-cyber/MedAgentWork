# -*- coding: utf-8 -*-
"""v2：网格热区统计定位结构坐标（不依赖 scipy）"""
import io, sys, os, json
import numpy as np
from PIL import Image
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RAW = r'C:\Users\38063\Desktop\MedAgentWork\复习资料\口腔科学教学计划版\raw'

def load(name):
    im = Image.open(os.path.join(RAW, name)).convert('RGB')
    return im, np.asarray(im).astype(int)

def grid_stats(a, mask, nx=20, ny=20):
    H, W = a.shape[:2]
    stats = []
    for j in range(ny):
        for i in range(nx):
            x0, x1 = int(W * i / nx), int(W * (i + 1) / nx)
            y0, y1 = int(H * j / ny), int(H * (j + 1) / ny)
            n = int(mask[y0:y1, x0:x1].sum())
            if n > 0:
                stats.append({'cx': round((x0 + x1) / 2 / W * 1000),
                              'cy': round((y0 + y1) / 2 / H * 1000),
                              'n': n})
    return stats

def yel(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (r > 190) & (g > 160) & (b < 150) & (r > b + 60)

def red(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (r > 200) & (g < 145) & (b < 145) & (r - g > 70)

def nonwhite(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (r < 245) | (g < 245) | (b < 245)

def angle_buckets(mask, k=10):
    """相对质心按角度分桶取每桶最远点"""
    ys, xs = np.where(mask)
    if len(ys) < 100:
        return []
    cy, cx = ys.mean(), xs.mean()
    ang = np.degrees(np.arctan2(-(ys - cy), xs - cx)) % 360
    dist = (xs - cx) ** 2 + (ys - cy) ** 2
    pts = []
    for bi in range(k):
        lo, hi = bi * 360 / k, (bi + 1) * 360 / k
        sel = (ang >= lo) & (ang < hi)
        if sel.sum() == 0:
            continue
        j = np.argmax(dist[sel])
        idx = np.where(sel)[0][j]
        pts.append({'ang': round((lo + hi) / 2), 'x': round(xs[idx] / mask.shape[1] * 1000),
                    'y': round(ys[idx] / mask.shape[0] * 1000)})
    return pts

def xband_ycentroid(a, mask, nx=16):
    """按 x 分桶，输出每桶非白像素 y 质心与总量（阶梯图定位）"""
    H, W = a.shape[:2]
    out = []
    for i in range(nx):
        x0, x1 = int(W * i / nx), int(W * (i + 1) / nx)
        seg = mask[:, x0:x1]
        n = int(seg.sum())
        if n == 0:
            out.append({'x': round((x0 + x1) / 2 / W * 1000), 'n': 0, 'ycen': None})
            continue
        ys, _ = np.where(seg)
        out.append({'x': round((x0 + x1) / 2 / W * 1000), 'n': n,
                    'ycen': round(ys.mean() / H * 1000)})
    return out

def analyze(name):
    im, a = load(name)
    H, W = a.shape[:2]
    res = {'file': name}
    if 'nerve' in name:
        m = yel(a)
        res['angle_pts'] = angle_buckets(m, 10)
        res['nerve_grid'] = grid_stats(a, m, 10, 10)
    elif 'gvp' in name:
        m = nonwhite(a)
        res['xband'] = xband_ycentroid(a, m, 16)
        # 深棕/暗色（牙周袋、骨吸收）
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        dark = (r < 215) & (g < 165) & (b < 160) & (r > 90)
        res['dark_grid'] = grid_stats(a, dark, 16, 12)
        # 粉色牙龈（近牙颈）
        pink = (r > 215) & (g > 165) & (g < 215) & (b > 160) & (b < 215)
        res['pink_grid'] = grid_stats(a, pink, 16, 12)
    elif 'rau' in name:
        m = red(a)
        res['red_grid'] = grid_stats(a, m, 16, 16)
        res['red_n'] = int(m.sum())
    elif 'precancer' in name:
        m = red(a)
        res['red_grid'] = grid_stats(a, m, 16, 16)
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        white = (r > 240) & (g > 225) & (b > 210) & ((r < 255) | (g < 255))
        res['white_grid'] = grid_stats(a, white, 16, 16)
    elif 'prosthesis' in name:
        m = nonwhite(a)
        res['xband'] = xband_ycentroid(a, m, 14)
    elif 'facial' in name:
        m = nonwhite(a)
        res['xband'] = xband_ycentroid(a, m, 10)
    return res

names = ['m01_facial_nerve_raw.jpg', 'm03_gvp_raw.jpg', 'm04_rau_raw.jpg',
         'm04_precancer_raw_v2.jpg', 'm05_prosthesis_raw_v2.jpg', 'm09_facial_palsy_raw.jpg']
out = [analyze(n) for n in names]
print(json.dumps(out, ensure_ascii=False, indent=1))
