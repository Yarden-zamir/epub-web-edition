# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1"]
# ///
"""Smoke test of the errata lane: the errata page and the open figure viewer, at phone and desktop width, light
and dark. Fails on a script error, horizontal overflow or an axe violation (with reduced motion).
scripts/smoke_site.py checks only the book page with nothing open.

Usage: uv run books/eli-raz/research/errata-lane/check_pages.py WEB_DIR AXE_JS [errata | viewer | figure ...]
"""
import asyncio
import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.async_api import Browser, async_playwright

web, AXE = Path(sys.argv[1]), Path(sys.argv[2])
ONLY = set(sys.argv[3:])  # Default: all three.
SIZES = ((360, 740), (1280, 900))
AXE_RUN = ("axe.run(document, {resultTypes: ['violations']}).then(r => r.violations.map(v => v.id + ' '"
           " + v.nodes.slice(0, 3).map(n => n.target.join(' ')).join(', ')))")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


async def check(browser: Browser, url: str, what: str, width: int, height: int, scheme: str) -> str | None:
    page = await browser.new_page(viewport={"width": width, "height": height}, color_scheme=scheme, reduced_motion="reduce")
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    await page.goto(url, wait_until="load")
    if what == "viewer":
        await page.locator("#row-4 .er-pill").first.click()
    if what == "figure":
        await page.wait_for_selector("#figure-dialog[open]")
    await page.wait_for_timeout(800)
    overflow = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    await page.add_script_tag(path=str(AXE))
    violations = await page.evaluate(AXE_RUN)
    await page.close()
    if errors or overflow > 0 or violations:
        return f"{what} {width} {scheme}: errors {errors[:2]} overflow {overflow} axe {violations}"
    print(f"ok {what} {width} {scheme}", flush=True)
    return None


async def main(base: str) -> list[str]:
    pages = {"errata": base + "errata/", "viewer": base + "errata/", "figure": base + "?photo=fig-a03-01"}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        results = []
        for what, url in [(w, u) for w, u in pages.items() if not ONLY or w in ONLY]:  # One page at a time: the book page is large.
            results += await asyncio.gather(*(check(browser, url, what, w, h, s) for w, h in SIZES for s in ("light", "dark")))
        await browser.close()
    return [r for r in results if r]


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(web)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
problems = asyncio.run(main(f"http://127.0.0.1:{srv.server_address[1]}/"))
srv.shutdown()
print("\n".join(problems) or "all pass")
sys.exit(1 if problems else 0)
