# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1"]
# ///
"""Smoke test a built web edition before publishing.

Usage: uv run scripts/smoke_site.py WEB_DIR AXE_JS [--axe-full]
AXE_JS is axe.min.js of axe-core 4.14.0. The browser is the Chromium of Playwright 1.64.1:
uv run --with playwright==1.64.1 playwright install --only-shell chromium

Live views (every run): one phone page jumps to each map, chart and explainer and fails on a script error.
Quick (default): two pages load the site once each, a phone page and a desktop page. Each checks for script errors
and horizontal overflow at its widths (360 and 393, or 1280), then runs axe in light and dark mode (with reduced
motion, so scroll animations do not cause false hits) on a fixed sample (SAMPLE) plus every section of the book whose
HTML has not passed axe before on this machine (hashes in $ELI_RAZ_CACHE/axe-ok, default ~/.cache/eli-raz).
Known limit: a CSS or JS change leaves the section HTML as it was, so the quick test checks it only on the sample.
CI's nightly run (--axe-full) checks the whole page.
--axe-full: a fresh load at every width and scheme, and axe on the whole page.
"""
import asyncio
import functools
import http.server
import os
import sys
import threading
import time
from pathlib import Path

from playwright.async_api import Browser, Page, async_playwright

args = [a for a in sys.argv[1:] if not a.startswith("--")]
FULL = "--axe-full" in sys.argv[1:]
if len(args) != 2 or not (Path(args[0]) / "index.html").is_file() or not Path(args[1]).is_file():
    sys.exit(__doc__)
web, AXE = Path(args[0]), Path(args[1])
SIZES = ((360, 740), (393, 852), (1280, 900))
SCHEMES = ("light", "dark")
# Parts that every quick run checks: header, hero, one rich chapter (table, figures, notes), the places map, the
# navigator and search dialogs, the footer.
SAMPLE = ["#nav", "#top", "#a06", "#places", "#toc-dialog", "#search-dialog", "footer"]
AXE_OK = Path(os.environ.get("ELI_RAZ_CACHE", Path.home() / ".cache" / "eli-raz")) / "axe-ok" / "axe-4.14.0"
# Each violation with the selectors of its first three elements, so a failed run says where to look.
# data-render-all turns off content-visibility, so axe sees every chapter as rendered (it misreads skipped ones).
AXE_RUN = """(include) => (document.documentElement.setAttribute('data-render-all', ''), axe.run(include ? {include: include.map(s => [s])} : document, {resultTypes: ['violations']})
  .then(r => r.violations.map(v => v.id + ' ' + v.nodes.slice(0, 3).map(n => n.target.join(' ')).join(', '))))"""
# Every book section (one per unit, plus the places section) with the SHA-256 of its HTML after the page scripts ran.
SECTION_HASHES = """async () => {
  const out = {};
  for (const s of document.querySelectorAll('main#read > .doc > section[id], main#read > section[id]')) {
    const bytes = new TextEncoder().encode(s.outerHTML);
    const hash = await crypto.subtle.digest('SHA-256', bytes);
    out['#' + s.id] = [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, '0')).join('');
  }
  return out;
}"""
# A busy machine (several worktrees checking at once) loads this long page slowly; the default 30 s is too short.
LOAD_TIMEOUT_MS = 120_000
FULL_AT_ONCE = 3  # Fresh full-page loads at the same time in --axe-full; six at once time out on a busy machine.
OVERFLOW = "document.documentElement.scrollWidth - document.documentElement.clientWidth"
# Width guard. body { overflow-x: clip } hides sideways overflow from OVERFLOW, and headless Chromium has no classic
# scrollbar, under which a 100vw block overhangs. So the guard narrows body by SCROLLBAR px (a classic scrollbar
# narrows the page, not 100vw) and lists the elements that pass the page edge, widest first. It skips fixed parts and
# everything inside a box that scrolls or clips on purpose (errata chips, table scroll boxes, maps).
SCROLLBAR = 15
WIDE = """(scrollbar) => {
  document.documentElement.setAttribute('data-render-all', '');
  document.body.style.marginRight = scrollbar + 'px';
  const page = document.body.getBoundingClientRect();
  const contained = (el) => {
    for (let a = el; a && a !== document.body; a = a.parentElement) {
      const s = getComputedStyle(a);
      if (s.position === 'fixed' || (a !== el && ['auto', 'scroll', 'hidden', 'clip'].includes(s.overflowX))) return true;
    }
    return false;
  };
  const out = [];
  for (const el of document.body.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    const over = Math.max(r.right - page.right, page.left - r.left);
    if (!r.width || over <= 1 || getComputedStyle(el).visibility === 'hidden' || contained(el)) continue;
    out.push(Math.round(over) + ' px ' + el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + [...el.classList].map(c => '.' + c).join(''));
  }
  document.body.style.marginRight = '';
  return out.sort((a, b) => parseInt(b) - parseInt(a)).slice(0, 5);
}"""
# axe builds its tree of the whole document before it looks at `include`, which costs most of a run on this long page.
# So after the overflow checks, the quick test removes the book parts that hold no target from the open page. The
# colours of a target come from its ancestors and the fixed bars, which stay.
KEEP_ONLY = """(targets) => {
  const keep = new Set(targets.map(t => document.querySelector(t)).filter(Boolean));
  for (const part of [...document.querySelectorAll('main#read > *')])
    if (![...keep].some(k => part === k || part.contains(k))) part.remove();
}"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


async def open_page(browser: Browser, url: str, width: int, height: int, scheme: str) -> tuple[Page, list[str]]:
    page = await browser.new_page(viewport={"width": width, "height": height}, color_scheme=scheme, reduced_motion="reduce")
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    await page.goto(url, wait_until="load", timeout=LOAD_TIMEOUT_MS)
    await page.wait_for_timeout(1500)
    await page.add_script_tag(path=str(AXE))
    return page, errors


async def full_check(browser: Browser, url: str, width: int, height: int, scheme: str, gate: asyncio.Semaphore) -> list[str]:
    async with gate:
        start = time.monotonic()
        page, errors = await open_page(browser, url, width, height, scheme)
        overflow = await page.evaluate(OVERFLOW)
        wide = await page.evaluate(WIDE, SCROLLBAR)
        violations = await page.evaluate(AXE_RUN, None)
        await page.close()
    print(f"{width} {scheme}: {time.monotonic() - start:.0f} s", flush=True)
    if errors or overflow > 0 or wide or violations:
        return [f"{width} {scheme}: errors {errors[:2]} overflow {overflow} wide {wide} axe {violations}"]
    return []


# The navigator's scroll box on each tab, with a classic scrollbar simulated: the box is 15 px narrower, as a scrollbar
# makes it (headless Chromium has none). A row wider than the box lets the panel scroll sideways.
NAVIGATOR_WIDTH = """async (scrollbar) => {
  const out = [];
  if (!document.getElementById('toc-dialog').open) document.querySelector('[data-open="toc-dialog"]').click();
  await new Promise(r => setTimeout(r, 400));
  for (const tab of document.querySelectorAll('#toc-dialog [role="tab"]')) {
    tab.click();
    await new Promise(r => setTimeout(r, 200));
    const box = document.getElementById(tab.getAttribute('aria-controls'));
    box.style.width = `calc(100% - ${scrollbar}px)`;
    const over = box.scrollWidth - box.clientWidth;
    if (over > 0) out.push(`${tab.textContent.trim()} tab: ${over} px wider than its scroll box`);
    box.style.width = '';
  }
  return out;
}"""


async def navigator_widths(browser: Browser, url: str) -> list[str]:
    """The width guard on the navigator dialog: every tab at every width."""
    page = await browser.new_page(viewport={"width": SIZES[0][0], "height": SIZES[0][1]}, reduced_motion="reduce")
    await page.goto(url, wait_until="load", timeout=LOAD_TIMEOUT_MS)
    problems = []
    for width, height in SIZES:
        await page.set_viewport_size({"width": width, "height": height})
        await page.wait_for_timeout(300)
        problems += [f"navigator {width}: {p}" for p in await page.evaluate(NAVIGATOR_WIDTH, SCROLLBAR)]
    await page.close()
    return problems


async def errata_widths(browser: Browser, url: str) -> list[str]:
    """The width guard on the errata page, at every width. A book without errata has no such page."""
    page = await browser.new_page(viewport={"width": SIZES[0][0], "height": SIZES[0][1]})
    response = await page.goto(url + "errata/", wait_until="load", timeout=LOAD_TIMEOUT_MS)
    problems = []
    if response and response.ok:
        for width, height in SIZES:
            await page.set_viewport_size({"width": width, "height": height})
            await page.wait_for_timeout(300)
            if wide := await page.evaluate(WIDE, SCROLLBAR):
                problems.append(f"errata {width}: wider than the page with a {SCROLLBAR} px scrollbar: {wide}")
    await page.close()
    return problems


async def quick_check(browser: Browser, url: str, sizes: list[tuple[int, int]], targets: list[str] | None) -> tuple[list[str], dict[str, str]]:
    """One load at the first size; the other widths and dark mode change the open page. targets None: sample only."""
    start = time.monotonic()
    page, errors = await open_page(browser, url, *sizes[0], "light")
    split = [f"load {time.monotonic() - start:.0f}"]
    hashes = await page.evaluate(SECTION_HASHES)
    if targets is None:
        targets = SAMPLE + [sel for sel, h in hashes.items() if sel not in SAMPLE and not (AXE_OK / h).exists()]
    problems = []
    for width, height in sizes:
        await page.set_viewport_size({"width": width, "height": height})
        await page.wait_for_timeout(300)
        if (overflow := await page.evaluate(OVERFLOW)) > 0:
            problems.append(f"{width}: overflow {overflow}")
        if wide := await page.evaluate(WIDE, SCROLLBAR):
            problems.append(f"{width}: wider than the page with a {SCROLLBAR} px scrollbar: {wide}")
        split.append(f"{width} {time.monotonic() - start:.0f}")
    width = sizes[-1][0]
    await page.evaluate(KEEP_ONLY, targets)
    for scheme in SCHEMES:
        await page.emulate_media(color_scheme=scheme)
        await page.wait_for_timeout(300)
        if violations := await page.evaluate(AXE_RUN, targets):
            problems.append(f"{width} {scheme}: axe {violations}")
        split.append(f"axe {scheme} {time.monotonic() - start:.0f}")
    problems += [f"{sizes[0][0]}: script error {e}" for e in errors[:2]]
    await page.close()
    print(f"{'/'.join(str(w) for w, _ in sizes)}: {time.monotonic() - start:.0f} s, axe on {len(targets)} parts ({', '.join(split)})", flush=True)
    return problems, {sel: hashes[sel] for sel in targets if sel in hashes}


# Figures with a live view drawn by a script: maps, charts, explainers. A broken one often fails only when drawn.
LIVE_VIEWS = "figure.has-map, figure.has-chart, figure.has-explorable"


async def live_views(browser: Browser, url: str) -> list[str]:
    """Load the book once at 393 px, jump to each figure with a live view the way the reader does, and report every
    page error and every console error of the site itself. Failed loads from other hosts (map tiles) do not count:
    a busy tile server must not fail the check."""
    start = time.monotonic()
    page = await browser.new_page(viewport={"width": 393, "height": 852}, reduced_motion="reduce")
    origin = url.rstrip("/")
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(f"page error: {e}"))
    page.on("console", lambda m: errors.append(f"console: {m.text}")
            if m.type == "error" and (m.location.get("url") or origin).startswith(origin) else None)
    await page.goto(url, wait_until="load", timeout=LOAD_TIMEOUT_MS)
    ids = await page.evaluate(f"[...document.querySelectorAll({LIVE_VIEWS!r})].map(f => f.id)")
    for fig in ids:
        before = len(errors)
        await page.evaluate("id => placeAtJumpLine(document.getElementById(id))", fig)
        await page.wait_for_timeout(700)  # Long enough for the draw that the jump starts (data fetch, map setup).
        errors[before:] = [f"#{fig}: {e}" for e in errors[before:]]
    await page.close()
    print(f"live views: {len(ids)} figures in {time.monotonic() - start:.0f} s", flush=True)
    return [f"393 live views: {e}" for e in errors[:5]]


async def main(url: str) -> list[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        if FULL:
            gate = asyncio.Semaphore(FULL_AT_ONCE)
            results = await asyncio.gather(*(full_check(browser, url, w, h, s, gate) for w, h in SIZES for s in SCHEMES))
            problems = [line for r in results for line in r] + await errata_widths(browser, url) + await live_views(browser, url)
            problems += await navigator_widths(browser, url)
            passed = {} if problems else await all_hashes(browser, url)
        else:
            phone, desktop, errata, live, navigator = await asyncio.gather(
                quick_check(browser, url, [SIZES[0], SIZES[1]], None),
                quick_check(browser, url, [SIZES[2]], None),
                errata_widths(browser, url),
                live_views(browser, url),
                navigator_widths(browser, url),
            )
            problems = phone[0] + desktop[0] + errata + live + navigator
            # A section counts as passed only when both pages checked it.
            passed = {sel: h for sel, h in phone[1].items() if desktop[1].get(sel) == h}
        await browser.close()
    if not problems:
        AXE_OK.mkdir(parents=True, exist_ok=True)
        for h in passed.values():
            (AXE_OK / h).touch()
    return problems


async def all_hashes(browser: Browser, url: str) -> dict[str, str]:
    page, _ = await open_page(browser, url, *SIZES[1], "light")
    hashes = await page.evaluate(SECTION_HASHES)
    await page.close()
    return hashes


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(web)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
problems = asyncio.run(main(f"http://127.0.0.1:{srv.server_port}/"))
srv.shutdown()
print("\n".join(problems) or "smoke ok")
sys.exit(1 if problems else 0)
