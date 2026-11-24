# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1"]
# ///
"""Check the language feature of a built web edition in Chromium (Playwright).

The contract: a translation swaps element content by ID and keeps every ID, note link and site part; the chapter
switch, the element chip and the reading mode work; the mode stays in ?lang= and localStorage; the new controls
pass axe in light and dark.

Usage: uv run books/eli-raz/scripts/check_languages.py WEB_DIR AXE_JS [SCREENSHOT_DIR]
Exits 1 on the first failed check.
"""

import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import Page, TimeoutError, sync_playwright

web, AXE = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
shots = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else None
if not (web / "index.html").is_file() or not AXE.is_file():
    sys.exit(__doc__)
AXE_RUN = "axe.run(document, {resultTypes: ['violations']}).then(r => r.violations.map(v => v.id + ' ' + v.nodes.slice(0, 3).map(n => n.target.join(' ')).join(', ')))"
IDS_IN = "(id) => [...document.getElementById(id).querySelectorAll('[id]')].map((e) => e.id).sort().join()"


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what, flush=True)
    if not ok:
        sys.exit(1)


def shot(page: Page, name: str) -> None:
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(shots / f"{name}.png"))


def settle(page: Page) -> None:
    page.wait_for_timeout(700)  # Fetch and cross-fade.


def until(page: Page, js: str, what: str, arg: object = None) -> None:
    """Wait for a condition in the page (fetches and cross-fades take time on a busy machine), then report it."""
    try:
        page.wait_for_function(js, arg=arg, timeout=15_000)
    except TimeoutError:
        check(False, what)
    check(True, what)


def desktop(p, url: str) -> None:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url + "#a06-h", wait_until="load")
    settle(page)
    check(page.locator(".lang-bar").count() == 3, "each translated chapter has a switch")
    ids_before = page.evaluate(IDS_IN, "a06")

    # One element alone, from the chip in the margin.
    page.hover("#a06-p003")
    chip = page.locator(".lang-chip")
    chip.wait_for(state="visible")
    para = page.locator("#a06-p003").bounding_box()
    box = chip.bounding_box()
    check(box["x"] > para["x"] + para["width"], "the chip sits in the margin beside the element")
    shot(page, "languages-chip-desktop")
    chip.click()
    settle(page)
    until(page, "document.getElementById('a06-p003').lang === 'he'", "the chip shows the element in Hebrew")
    check(page.locator("#a06-p003.lang-single").count() == 1, "an element switched alone is marked")
    check(page.locator("#a06 .lang-note").is_visible(), "the AI translation note shows next to the switch")
    page.click("#a06-fnref1")
    page.wait_for_selector("#note-popover:popover-open")
    check(page.locator("#note-popover").inner_text().strip() != "", "the note link inside the swapped element opens its note")
    page.keyboard.press("Escape")
    shot(page, "languages-element-he-desktop")

    # The whole chapter.
    page.click("#a06 .lang-switch button[data-lang='he']")
    settle(page)
    ids = page.evaluate("JSON.parse(document.getElementById('translations-data').textContent).a06[0].ids")
    until(page, "(ids) => ids.map((id) => document.getElementById(id)).every((el) => (el.matches('figure') ? el.querySelector('figcaption') : el).lang === 'he')", "the chapter switch shows every element in Hebrew", ids)
    check(page.evaluate(IDS_IN, "a06") == ids_before, "every ID inside the chapter stays")
    check(page.locator("#a06-h .deep-link").count() == 1, "the heading keeps its link button")
    shot(page, "languages-chapter-he-desktop")
    page.reload(wait_until="load")
    settle(page)
    until(page, "document.getElementById('a06-p003').lang === 'he'", "the chapter choice survives a reload")

    # Reading mode: English.
    page.evaluate("scrollTo(0, document.getElementById('a06').offsetTop)")
    page.wait_for_selector(".lang-fab[data-shown]")
    page.click(".lang-fab")
    page.wait_for_selector("#lang-menu:popover-open")
    shot(page, "languages-menu-desktop")
    page.add_script_tag(path=str(AXE))
    violations = page.evaluate(AXE_RUN)
    check(not violations, f"axe passes with the menu open (light) {violations}")
    page.click(".lang-modes [data-mode='en']")
    page.wait_for_selector("#lang-menu:not(:popover-open)", state="attached")
    settle(page)
    check("lang=en" in page.url, f"the mode is in the address ({page.url})")
    until(page, "document.getElementById('a06-p003').lang === 'en'", "English mode shows the English chapter as printed")
    until(page, "document.getElementById('a10-p002').lang === 'en'", "English mode shows the translated Hebrew chapter")
    page.evaluate("goTo('a10-h')")
    settle(page)
    check(page.locator("#a10 .lang-note").inner_text() == "AI translation, not reviewed by a person", "the English note shows next to the switch")
    page.go_back()
    page.wait_for_timeout(300)
    check("lang=en" in page.url, "Back keeps the mode in the address")
    page.evaluate("goTo('a10-h')")
    settle(page)
    shot(page, "languages-a10-en-desktop")
    page.click("#a10-src1-ref")
    page.wait_for_selector("#note-popover:popover-open")
    check(page.locator("#note-popover .pop-body").get_attribute("lang") == "en", "a translated note opens in English")
    page.keyboard.press("Escape")
    page.goto(url + "#a06-h", wait_until="load")
    settle(page)
    until(page, "document.getElementById('a10-p002').lang === 'en' && location.search.includes('lang=en')", "the mode is kept in localStorage and put back in the address")
    check(not errors, f"no script errors {errors[:2]}")
    browser.close()


def phone(p, url: str) -> None:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 393, "height": 852}, color_scheme="dark", has_touch=True, is_mobile=True, reduced_motion="reduce")
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url + "?lang=en#a10-h", wait_until="load")
    settle(page)
    until(page, "document.getElementById('a10-p002').lang === 'en'", "a shared ?lang=en link opens in English")
    shot(page, "languages-a10-en-phone-dark")
    page.add_script_tag(path=str(AXE))
    violations = page.evaluate(AXE_RUN)
    check(not violations, f"axe passes in English mode (dark, phone) {violations}")
    page.locator("#a10-p003").tap()
    page.locator(".lang-chip").wait_for(state="visible")
    shot(page, "languages-chip-phone-dark")
    page.locator(".lang-chip").tap()
    settle(page)
    until(page, "document.getElementById('a10-p003').lang !== 'en'", "a tap on the chip shows the element as printed")
    page.mouse.wheel(0, 600)
    page.wait_for_timeout(400)
    check(page.locator(".lang-fab[data-tucked]").count() == 1, "the mode button steps aside while the reader scrolls down")
    check(not errors, f"no script errors {errors[:2]}")
    browser.close()


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(web)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
with sync_playwright() as p:
    desktop(p, f"http://127.0.0.1:{srv.server_port}/")
    phone(p, f"http://127.0.0.1:{srv.server_port}/")
srv.shutdown()
print("languages ok")
