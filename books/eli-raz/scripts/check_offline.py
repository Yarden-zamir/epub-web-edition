# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1", "pillow==13.0.0"]  # Pillow: tools/build_web.py, which the update check imports.
# ///
"""Check offline reading of a built web edition in Chromium (Playwright).

1. First visit in a browser tab, then offline (context offline and the server stopped): the page, its script,
   search and the images seen before still work; an image never seen shows an empty box, not a broken icon.
2. Installed app (standalone): the whole book saves in the background; offline, every book image loads.
3. Update: a new deploy (changed text and image) shows at once online; the old caches go; offline shows the new
   version.

Usage: uv run books/eli-raz/scripts/check_offline.py WEB_DIR [SCREENSHOT_DIR]
WEB_DIR is the built site (books/eli-raz/dist/release/web). Exits 1 on the first failed check.
"""

import functools
import http.server
import importlib.util
import json
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import BrowserContext, Page, TimeoutError, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
web = Path(sys.argv[1]).resolve()
shots = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
if not (web / "sw.js").is_file():
    sys.exit(__doc__)


class Server:
    """A local server whose folder can change between requests (a deploy) and that can stop (no network)."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        outer = self

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(outer.folder), **kwargs)

            def end_headers(self):
                self.send_header("Cache-Control", "max-age=0, must-revalidate")  # As the live host serves pages.
                super().end_headers()

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what, flush=True)
    if not ok:
        sys.exit(1)


def shot(page: Page, name: str) -> None:
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(shots / f"{name}.png"))


def controlled(page: Page) -> None:
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=60_000)


CACHE_COUNTS = """async () => {
  const out = {};
  for (const name of await caches.keys()) out[name] = (await (await caches.open(name)).keys()).length;
  return out;
}"""
# Book images in the page that finished loading with real pixels (a placeholder is 1 px wide).
IMAGES = """(selector) => [...document.querySelectorAll(selector)].map((img) => ({
  src: img.getAttribute('src'), complete: img.complete, width: img.naturalWidth }))"""


def load_all_images(page: Page) -> list[dict]:
    """Make every lazy book image load, then report each one."""
    page.evaluate("document.querySelectorAll('.book img').forEach((img) => { img.loading = 'eager'; })")
    page.wait_for_function("[...document.querySelectorAll('.book img')].every((img) => img.complete)", timeout=180_000)
    return page.evaluate(IMAGES, ".book img")


def search_works(page: Page) -> bool:
    page.keyboard.press("/")
    page.fill("#search-input", "בולען")
    page.wait_for_function("document.querySelectorAll('#search-results li').length > 0", timeout=20_000)
    page.click("#search-dialog [data-close]")
    page.wait_for_function("!document.getElementById('search-dialog').open")
    return True


def offline_reload(context: BrowserContext, page: Page) -> list[str]:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    context.set_offline(True)
    page.reload(wait_until="load")
    page.wait_for_timeout(1500)
    return errors


def file_list(folder: Path) -> dict:
    text = (folder / "sw.js").read_text(encoding="utf-8")
    start = text.index("const FILES = ") + len("const FILES = ")
    return json.loads(text[start:text.index(";\n", start)])


def first_visit(p, folder: Path) -> None:
    server = Server(folder)
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 393, "height": 852}, reduced_motion="reduce")
    page = context.new_page()
    page.goto(server.url, wait_until="load")
    controlled(page)
    caches = page.evaluate(CACHE_COUNTS)
    shell = sum(1 for _, (_, kind) in file_list(folder).items() if kind == "shell")
    check(any(name.startswith("reader-shell-") and n == shell for name, n in caches.items()), f"first visit saves the shell ({shell} files): {caches}")
    # Read a little: the first chapter's photo enters the media cache.
    first = page.locator(".book figure img").locator("visible=true").first
    first.scroll_into_view_if_needed()
    page.wait_for_function("(img) => img.complete && img.naturalWidth > 1", arg=first.element_handle(), timeout=30_000)
    seen = first.get_attribute("src")
    server.stop()
    errors = offline_reload(context, page)
    check(not errors, f"offline page runs without script errors {errors[:2]}")
    check(page.locator(".book .doc").count() > 10, "offline page shows the book")
    check(search_works(page), "offline search finds results")
    img = page.locator(f'.book img[src="{seen}"]').first
    img.scroll_into_view_if_needed()
    page.wait_for_function("(img) => img.complete", arg=img.element_handle())
    check(img.evaluate("(img) => img.naturalWidth") > 1, f"an image read before shows offline ({seen})")
    shot(page, "offline-first-visit-phone")
    unseen = page.locator(".book img").locator("visible=true").last
    unseen.scroll_into_view_if_needed()
    page.wait_for_function("(img) => img.complete", arg=unseen.element_handle())
    check(unseen.evaluate("(img) => img.naturalWidth") == 1, "an image never read shows an empty box offline")
    shot(page, "offline-unseen-image-phone")
    browser.close()


def installed_app(p, folder: Path) -> None:
    server = Server(folder)
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
    # The installed app: Chromium cannot emulate display-mode, so the page sees navigator.standalone (as on iOS).
    context.add_init_script("Object.defineProperty(navigator, 'standalone', { value: true })")
    page = context.new_page()
    page.goto(server.url, wait_until="load")
    controlled(page)
    media = sum(1 for _, (_, kind) in file_list(folder).items() if kind == "media")
    page.wait_for_selector(".toast", timeout=300_000)
    shot(page, "installed-saved-toast-desktop")
    counts = page.evaluate(CACHE_COUNTS)
    check(counts.get("reader-media") == media, f"installed app saves every book image ({counts.get('reader-media')} of {media})")
    check(not any("download/" in u for u in page.evaluate("async () => (await Promise.all((await caches.keys()).map(async (n) => (await (await caches.open(n)).keys()).map((r) => r.url)))).flat()")),
          "the EPUB download is never cached")
    server.stop()
    offline_reload(context, page)
    # Video thumbnails come from YouTube without CORS, so they are not saved; the videos need a network anyway.
    images = [i for i in load_all_images(page) if not i["src"].startswith("https://")]
    broken = [i["src"] for i in images if i["width"] <= 1]
    check(not broken, f"offline, all {len(images)} book images load {broken[:3]}")
    page.locator("#a10").scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    shot(page, "installed-offline-desktop")
    browser.close()


def update_cycle(p, folder: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        v1, v2 = Path(tmp) / "v1", Path(tmp) / "v2"
        shutil.copytree(folder, v1, ignore=shutil.ignore_patterns("download"))
        shutil.copytree(v1, v2)
        # Deploy v2: a corrected sentence and a replaced image under the same name, then the worker list again.
        page_html = (v2 / "index.html").read_text(encoding="utf-8")
        marker = "<p id="
        at = page_html.index(marker, page_html.index('id="a06"'))
        page_html = page_html[:at] + '<p class="update-check">תיקון שנפרס עכשיו</p>' + page_html[at:]
        (v2 / "index.html").write_text(page_html, encoding="utf-8")
        image = next(path for path, (_, kind) in file_list(v2).items() if kind == "media" and path.startswith("book/"))
        (v2 / image).write_bytes((v2 / image).read_bytes() + b"\0")
        spec = importlib.util.spec_from_file_location("build_web", ROOT / "tools" / "build_web.py")
        build_web = importlib.util.module_from_spec(spec)
        sys.modules["build_web"] = build_web
        spec.loader.exec_module(build_web)
        spec = importlib.util.spec_from_file_location("offline", ROOT / "tools" / "web" / "99_offline.py")
        offline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(offline)
        offline.write(SimpleNamespace(out=v2, report={}))

        server = Server(v1)
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 393, "height": 852}, reduced_motion="reduce")
        page = context.new_page()
        page.goto(server.url, wait_until="load")
        controlled(page)
        page.evaluate("(src) => fetch(src)", image)  # The image enters the media cache as v1.
        old = page.evaluate(CACHE_COUNTS)
        server.folder = v2
        page.reload(wait_until="load")
        check(page.locator(".update-check").count() == 1, "online, the new deploy shows at once")
        page.evaluate("navigator.serviceWorker.getRegistration().then((r) => r.update())")
        page.wait_for_function("""async (old) => {
          const names = await caches.keys();
          return names.some((n) => n.startsWith('reader-shell-') && !old.includes(n)) && !names.some((n) => old.includes(n) && n.startsWith('reader-shell-'));
        }""", arg=list(old), timeout=60_000, polling=500)
        stale = f"{image}?v={file_list(v1)[image][0]}"
        gone = "async (key) => !(await (await caches.open('reader-media')).keys()).some((r) => r.url.endsWith(key))"
        try:
            page.wait_for_function(gone, arg=stale, timeout=30_000, polling=500)
        except TimeoutError:
            check(False, "the changed image's old copy is deleted on activate")
        check(True, "the changed image's old copy is deleted on activate")
        server.stop()
        errors = offline_reload(context, page)
        check(not errors and page.locator(".update-check").count() == 1, f"offline after the update shows the new version {errors[:2]} {page.title()!r} {page.evaluate(CACHE_COUNTS)}")
        page.locator(".update-check").scroll_into_view_if_needed()
        shot(page, "update-offline-phone")
        browser.close()


with sync_playwright() as p:
    first_visit(p, web)
    installed_app(p, web)
    update_cycle(p, web)
print("offline ok")
