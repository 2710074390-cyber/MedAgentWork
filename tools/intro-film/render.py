"""MedAgentWork 介绍片渲染器。

用法：
    python render.py --format wide        # 1920x1080
    python render.py --format tall        # 1080x1350
    python render.py --format wide --probe 60   # 只渲染前 60 帧试速
    python render.py --audio              # 只生成音轨

产物：
    assets/intro/medagentwork-intro-16x9.mp4
    assets/intro/medagentwork-intro-4x5.mp4
    assets/intro/poster-16x9.webp / .jpg
    assets/intro/poster-4x5.webp / .jpg
"""
import argparse
import asyncio
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent.parent
OUT = SITE / "assets" / "intro"
CACHE = ROOT / ".cache"
CACHE.mkdir(exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

WIDE = {"width": 1920, "height": 1080}
TALL = {"width": 1080, "height": 1350}
FPS = 30
DUR = 58.0
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def chromium_exe():
    """playwright 自带的 headless shell 可能缺失，回退到本机已装的 chromium。"""
    import os
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH",
                    Path.home() / "AppData" / "Local" / "ms-playwright"))
    cands = sorted(root.glob("chromium-*/chrome-win64/chrome.exe"), reverse=True)
    return str(cands[0]) if cands else None


async def render_audio():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chromium_exe())
        pg = await b.new_page(viewport={"width": 800, "height": 600})
        await pg.goto((ROOT / "audio.html").as_uri())
        await pg.wait_for_function("window.__ready === true || window.__err", timeout=120000)
        err = await pg.evaluate("window.__err || ''")
        if err:
            raise RuntimeError(err)
        b64 = await pg.evaluate("window.__wav")
        await b.close()
    wav = base64.b64decode(b64)
    path = CACHE / "soundtrack.wav"
    path.write_bytes(wav)
    print(f"[audio] {path}  {len(wav)/1024/1024:.2f} MB")
    return path


async def grab(engine, fmt, t, path):
    pg = engine["page"]
    await pg.evaluate("t => window.__seek(t)", t * 1000)
    await pg.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
    await pg.screenshot(path=str(path))


async def render_frames(fmt, probe=None, start=0, end=None):
    size = WIDE if fmt == "wide" else TALL
    frames_dir = CACHE / f"frames-{fmt}"
    frames_dir.mkdir(exist_ok=True)
    # 直接覆盖同名帧（整目录批量删除会触发宿主的批量删除保护）
    total = int(DUR * FPS)
    if probe:
        total = min(total, probe)
    begin = max(0, int(start))
    stop = total if end is None else min(total, int(end))

    started = time.time()
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chromium_exe())
        pg = await b.new_page(viewport=size, device_scale_factor=1)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.goto((ROOT / "index.html").as_uri() + f"?format={fmt}")
        await pg.wait_for_function("window.__ready === true", timeout=30000)
        engine = {"page": pg}
        for i in range(begin, stop):
            await grab(engine, fmt, i / FPS, frames_dir / f"{i:05d}.png")
            if (i - begin) % 150 == 0 and i > begin:
                el = time.time() - started
                print(f"[{fmt}] {i}/{stop}  {el:.0f}s  ({el/(i-begin)*1000:.0f} ms/frame)", flush=True)
        await b.close()
        if errors:
            print("[warn] page errors:", errors, file=sys.stderr)
    print(f"[{fmt}] frames done in {time.time()-started:.0f}s -> {frames_dir}")
    return frames_dir, total


def encode(fmt, frames_dir, total, audio=None):
    name = "medagentwork-intro-16x9.mp4" if fmt == "wide" else "medagentwork-intro-4x5.mp4"
    out = OUT / name
    cmd = [FFMPEG, "-y", "-framerate", str(FPS), "-i", str(frames_dir / "%05d.png")]
    if audio:
        cmd += ["-i", str(audio)]
    cmd += [
        "-c:v", "libx264", "-preset", "slow", "-crf", "22",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        "-movflags", "+faststart", "-g", "60",
    ]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "112k", "-shortest"]
    cmd += [str(out)]
    subprocess.run(cmd, check=True)
    print(f"[encode] {out}  {out.stat().st_size/1024/1024:.2f} MB")
    return out


async def make_poster(fmt):
    size = WIDE if fmt == "wide" else TALL
    suffix = "16x9" if fmt == "wide" else "4x5"
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chromium_exe())
        pg = await b.new_page(viewport=size, device_scale_factor=1)
        await pg.goto((ROOT / "index.html").as_uri() + f"?format={fmt}&clean=1")
        await pg.wait_for_function("window.__ready === true")
        await pg.evaluate("window.__seek(4900)")
        await pg.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
        png = CACHE / f"poster-{suffix}.png"
        await pg.screenshot(path=str(png))
        await b.close()
    # webp + jpg 双份
    for ext, codec in (("webp", "libwebp"), ("jpg", "mjpeg")):
        target = OUT / f"poster-{suffix}.{ext}"
        q = ["-quality", "82"] if ext == "webp" else ["-q:v", "3"]
        cmd = [FFMPEG, "-y", "-i", str(png), "-c:v", codec] + q + [str(target)]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[poster] {target}  {target.stat().st_size/1024:.0f} KB")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["wide", "tall", "both"], default="both")
    ap.add_argument("--probe", type=int, default=0)
    ap.add_argument("--audio", action="store_true")
    ap.add_argument("--skip-frames", action="store_true")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--frames-only", action="store_true")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=0)
    args = ap.parse_args()

    if args.audio:
        await render_audio()
        return

    audio = None if args.no_audio else await render_audio()
    formats = ["wide", "tall"] if args.format == "both" else [args.format]
    for fmt in formats:
        if args.skip_frames:
            frames_dir = CACHE / f"frames-{fmt}"
            total = int(DUR * FPS)
        else:
            frames_dir, total = await render_frames(
                fmt, args.probe or None, args.start, args.end or None
            )
        if not args.probe and not args.frames_only:
            encode(fmt, frames_dir, total, audio)
            await make_poster(fmt)


if __name__ == "__main__":
    asyncio.run(main())
