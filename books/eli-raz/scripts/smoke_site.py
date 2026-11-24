# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1"]
# ///
"""Smoke test a built web edition before publishing: loads at phone and desktop width, light and dark.

Fails on a script error, horizontal overflow, or an axe violation (with reduced motion, so scroll animations do not cause false hits).
The six width and colour-scheme checks run at the same time, each in its own page.
Usage: uv run scripts/smoke_site.py WEB_DIR AXE_JS
AXE_JS is axe.min.js of axe-core 4.14.0. The browser is the Chromium of Playwright 1.64.1:
uv run --with playwright==1.64.1 playwright install --only-shell chromium
"""
import asyncio
import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.async_api import Browser, async_playwright

web, AXE = Path(sys.argv[1]), Path(sys.argv[2])
if not (web / "index.html").is_file() or not AXE.is_file():
    sys.exit(f"usage: smoke_site.py WEB_DIR AXE_JS; missing {web / 'index.html'} or {AXE}")
SIZES = ((360, 740), (393, 852), (1280, 900))
SCHEMES = ("light", "dark")
# Each violation with the selectors of its first three elements, so a failed run says where to look.
AXE_RUN = "axe.run(document, {resultTypes: ['violations']}).then(r => r.violations.map(v => v.id + ' ' + v.nodes.slice(0, 3).map(n => n.target.join(' ')).join(', ')))"


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


async def check(browser: Browser, url: str, width: int, height: int, scheme: str) -> str | None:
    """One width and colour scheme: the problem line, or None when the page passes."""
    page = await browser.new_page(viewport={"width": width, "height": height}, color_scheme=scheme, reduced_motion="reduce")
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    await page.goto(url, wait_until="load")
    await page.wait_for_timeout(1500)
    overflow = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    await page.add_script_tag(path=str(AXE))
    violations = await page.evaluate(AXE_RUN)
    await page.close()
    if errors or overflow > 0 or violations:
        return f"{width} {scheme}: errors {errors[:2]} overflow {overflow} axe {violations}"
    return None


async def main(url: str) -> list[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        results = await asyncio.gather(*(check(browser, url, w, h, s) for w, h in SIZES for s in SCHEMES))
        await browser.close()
    return [r for r in results if r]


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(web)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
problems = asyncio.run(main(f"http://127.0.0.1:{srv.server_port}/"))
srv.shutdown()
print("\n".join(problems) or "smoke ok")
sys.exit(1 if problems else 0)
