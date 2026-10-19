"""短片排版体检：截图 + 溢出检测（临时）。"""
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / ".cache" / "chk"
OUT.mkdir(parents=True, exist_ok=True)
EXE = r"C:/Users/38063/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe"

MEASURE = """() => {
  const st = document.getElementById('stage');
  const scenes = [...document.querySelectorAll('.scene')]
      .filter(e => parseFloat(getComputedStyle(e).opacity) > .04);
  let bottom = 0;
  scenes.forEach(sc => [...sc.querySelectorAll('*')].forEach(e => {
    if (parseFloat(getComputedStyle(e).opacity) < .04) return;
    const b = e.getBoundingClientRect();
    if (b.height > 0 && b.bottom > bottom) bottom = b.bottom;
  }));
  return { vh: st.getBoundingClientRect().height, bottom: Math.round(bottom), n: scenes.length };
}"""

SHOTS = {
    "pipeline": [3.0, 12.0, 22.0, 36.0],
    "gate": [3.0, 13.0, 25.0, 38.0],
    "rag": [3.0, 12.0, 24.0, 34.0],
}


async def main():
    films = sys.argv[1:] or list(SHOTS)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=EXE)
        for key in films:
            for fmt, w, h in (("wide", 1920, 1080), ("tall", 1080, 1350)):
                pg = await b.new_page(viewport={"width": w, "height": h})
                errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                await pg.goto((ROOT / "index.html").as_uri() + f"?f={key}&format={fmt}")
                await pg.wait_for_function("window.__ready === true")
                for t in SHOTS[key]:
                    await pg.evaluate("t => window.__seek(t*1000)", t)
                    await pg.evaluate(
                        "new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
                    m = await pg.evaluate(MEASURE)
                    over = m["bottom"] - m["vh"]
                    flag = "OVER" if over > 0 else "ok"
                    print(f"[{key}/{fmt}] t={t:>5} bottom={m['bottom']:>5} vh={m['vh']} "
                          f"over={over:+d} {flag}")
                    await pg.screenshot(path=str(OUT / f"{key}-{fmt}-{t:.0f}.png"))
                if errs:
                    print(f"[{key}/{fmt}] errors={errs}")
                await pg.close()
        await b.close()


asyncio.run(main())