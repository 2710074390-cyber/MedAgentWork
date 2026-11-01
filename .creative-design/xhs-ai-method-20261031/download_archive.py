# -*- coding: utf-8 -*-
"""Download the 8 delivered images into the local asset folder and verify 3:4 size."""
import urllib.request
from pathlib import Path
from PIL import Image

OUT = Path(r"C:\Users\38063\Desktop\MedAgentWork\assets\小红书配图")
OUT.mkdir(parents=True, exist_ok=True)

IMAGES = [
    ("第一篇-1-封面-AI题库出完我为什么不直接刷.png", "https://aka.doubaocdn.com/s/tnGV3VGEzd"),
    ("第一篇-2-流程-多角色与门禁.png", "https://aka.doubaocdn.com/s/GRMV8sReal"),
    ("第一篇-3-案例-反选与答案位置.png", "https://aka.doubaocdn.com/s/PV8IRHdNZk"),
    ("第一篇-4-实操-五步清单.png", "https://aka.doubaocdn.com/s/SywMhmuq3t"),
    ("第二篇-1-封面-AI整理复习资料我加了几道检查.png", "https://aka.doubaocdn.com/s/YJlSX13QLa"),
    ("第二篇-2-流程-多角色与检查关卡.png", "https://aka.doubaocdn.com/s/N9FK40UnKo"),
    ("第二篇-3-版式-一页复习笔记.png", "https://aka.doubaocdn.com/s/xq682GI18A"),
    ("第二篇-4-清单-复习资料最后检查.png", "https://aka.doubaocdn.com/s/CvEAX3OZTE"),
]

for name, url in IMAGES:
    dst = OUT / name
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        dst.write_bytes(r.read())
    with Image.open(dst) as im:
        w, h = im.size
    ratio = h / w
    ok = abs(ratio - 4 / 3) < 0.02
    print(f"{name}: {w}x{h} ratio={ratio:.3f} {'OK' if ok else 'RATIO-WARN'}")
