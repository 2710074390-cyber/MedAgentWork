"""MedAgentWork 科普短片渲染器。

用法：
    python render.py --film pipeline|gate|rag|all   # 默认 all
    python render.py --film gate --format wide       # 只出某个画幅
    python render.py --probe 90                      # 只渲染前 90 帧试速
    python render.py --frames-only                   # 只出帧，不编码
    python render.py --skip-frames                   # 复用已渲染的帧，只编码

产物：
    assets/shorts/{film}-16x9.mp4  assets/shorts/{film}-4x5.mp4
    assets/shorts/poster-{film}-{16x9|4x5}.webp/.jpg
"""
import argparse
import asyncio
import base64
import os
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent.parent
OUT = SITE / "assets" / "shorts"
CACHE = ROOT / ".cache"
CACHE.mkdir(exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

WIDE = {"width": 1920, "height": 1080}
TALL = {"width": 1080, "height": 1350}
FPS = 30
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

FILMS = {
    "pipeline": {"dur": 40, "poster": 4.2},
    "gate": {"dur": 42, "poster": 4.2},
    "rag": {"dur": 38, "poster": 4.2},
}


def chromium_exe():
    """playwright 自带的 headless shell 可能缺失，回退到本机已装的 chromium。"""
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH",
                    Path.home() / "AppData" / "Local" / "ms-playwright"))
    cands = sorted(root.glob("chromium-*/chrome-win64/chrome.exe"), reverse=True)
    return str(cands[0]) if cands else None


async def render_audio(pw, film):
    b = await pw.chromium.launch(executable_path=chromium_exe())
    try:
        pg = await b.new_page(viewport={"width": 800, "height": 600})
        await pg.goto((ROOT / "audio.html").as_uri() + f"?f={film}")
        await pg.wait_for_function("window.__ready === true || window.__err", timeout=180000)
        err = await pg.evaluate("window.__err || ''")
        if err:
            raise RuntimeError(err)
        b64 = await pg.evaluate("window.__wav")
    finally:
        await b.close()
    wav = base64.b64decode(b64)
    path = CACHE / f"audio-{film}.wav"
    path.write_bytes(wav)
    print(f"[audio:{film}] {path.name} {len(wav)/1024/1024:.2f} MB", flush=True)
    return path


async def grab(page, t, path):
    await page.evaluate("t => window.__seek(t)", t * 1000)
    await page.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
    await page.screenshot(path=str(path))


async def render_frames(pw, film, fmt, probe=None, start=0, end=None):
    size = WIDE if fmt == "wide" else TALL
    frames_dir = CACHE / f"frames-{film}-{fmt}"
    frames_dir.mkdir(exist_ok=True)
    total = int(FILMS[film]["dur"] * FPS)
    if probe:
        total = min(total, probe)
    begin, stop = max(0, int(start)), (total if end is None else min(total, int(end)))

    started = time.time()
    b = await pw.chromium.launch(executable_path=chromium_exe())
    try:
        pg = await b.new_page(viewport=size, device_scale_factor=1)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.goto((ROOT / "index.html").as_uri() + f"?f={film}&format={fmt}")
        await pg.wait_for_function("window.__ready === true", timeout=30000)
        for i in range(begin, stop):
            await grab(pg, i / FPS, frames_dir / f"{i:05d}.png")
            if (i - begin) % 300 == 0 and i > begin:
                el = time.time() - started
                print(f"[{film}/{fmt}] {i}/{stop} {el:.0f}s "
                      f"({el/(i-begin)*1000:.0f} ms/frame)", flush=True)
        if errors:
            print("[warn] page errors:", errors, file=sys.stderr)
    finally:
        await b.close()
    print(f"[{film}/{fmt}] frames done in {time.time()-started:.0f}s", flush=True)
    return frames_dir, total


def encode(film, fmt, frames_dir, total, audio=None):
    suffix = "16x9" if fmt == "wide" else "4x5"
    out = OUT / f"{film}-{suffix}.mp4"
    cmd = [FFMPEG, "-y", "-framerate", str(FPS), "-i", str(frames_dir / "%05d.png")]
    if audio:
        cmd += ["-i", str(audio)]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "24",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
            "-movflags", "+faststart", "-g", "60", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "96k", "-shortest"]
    cmd += [str(out)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    print(f"[encode] {out.name} {out.stat().st_size/1024/1024:.2f} MB", flush=True)
    return out


async def make_poster(pw, film, fmt):
    size = WIDE if fmt == "wide" else TALL
    suffix = "16x9" if fmt == "wide" else "4x5"
    b = await pw.chromium.launch(executable_path=chromium_exe())
    try:
        pg = await b.new_page(viewport=size, device_scale_factor=1)
        await pg.goto((ROOT / "index.html").as_uri() + f"?f={film}&format={fmt}")
        await pg.wait_for_function("window.__ready === true")
        await pg.evaluate("t => window.__seek(t)", FILMS[film]["poster"] * 1000)
        await pg.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
        png = CACHE / f"poster-{film}-{suffix}.png"
        await pg.screenshot(path=str(png))
    finally:
        await b.close()
    for ext, codec, q in (("webp", "libwebp", ["-quality", "80"]), ("jpg", "mjpeg", ["-q:v", "4"])):
        target = OUT / f"poster-{film}-{suffix}.{ext}"
        subprocess.run([FFMPEG, "-y", "-i", str(png), "-c:v", codec] + q + [str(target)],
                       check=True, capture_output=True)
        print(f"[poster] {target.name} {target.stat().st_size/1024:.0f} KB", flush=True)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", default="all")
    ap.add_argument("--format", choices=["wide", "tall", "both"], default="both")
    ap.add_argument("--probe", type=int, default=0)
    ap.add_argument("--frames-only", action="store_true")
    ap.add_argument("--skip-frames", action="store_true")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=0)
    args = ap.parse_args()

    films = list(FILMS) if args.film == "all" else [args.film]
    formats = ["wide", "tall"] if args.format == "both" else [args.format]

    async with async_playwright() as pw:
        for film in films:
            audio = None if args.no_audio else await render_audio(pw, film)
            for fmt in formats:
                if args.skip_frames:
                    frames_dir = CACHE / f"frames-{film}-{fmt}"
                    total = int(FILMS[film]["dur"] * FPS)
                else:
                    frames_dir, total = await render_frames(
                        pw, film, fmt, args.probe or None, args.start, args.end or None)
                if not args.probe and not args.frames_only:
                    encode(film, fmt, frames_dir, total, audio)
                    await make_poster(pw, film, fmt)


if __name__ == "__main__":
    asyncio.run(main())