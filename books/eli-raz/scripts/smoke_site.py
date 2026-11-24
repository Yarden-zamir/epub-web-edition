# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1"]
# ///
"""Smoke test a built web edition before publishing: loads at phone and desktop width, light and dark.

Fails on a script error, horizontal overflow, or an axe violation (with reduced motion, so scroll animations do not cause false hits).
Usage: uv run scripts/smoke_site.py WEB_DIR AXE_JS
AXE_JS is axe.min.js of axe-core 4.14.0. The browser is the Chromium of Playwright 1.64.1:
uv run --with playwright==1.64.1 playwright install --only-shell chromium
"""
import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

web, AXE = Path(sys.argv[1]), Path(sys.argv[2])
if not (web / "index.html").is_file() or not AXE.is_file():
    sys.exit(f"usage: smoke_site.py WEB_DIR AXE_JS; missing {web / 'index.html'} or {AXE}")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(web)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
problems = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    for width, height in ((360, 740), (393, 852), (1280, 900)):
        for scheme in ("light", "dark"):
            page = browser.new_page(viewport={"width": width, "height": height}, color_scheme=scheme, reduced_motion="reduce")
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{srv.server_port}/", wait_until="load")
            page.wait_for_timeout(1500)
            overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            page.add_script_tag(path=str(AXE))
            # Each violation with the selectors of its first three elements, so a failed run says where to look.
            violations = page.evaluate("axe.run(document, {resultTypes: ['violations']}).then(r => r.violations.map(v => v.id + ' ' + v.nodes.slice(0, 3).map(n => n.target.join(' ')).join(', ')))")
            if errors or overflow > 0 or violations:
                problems.append(f"{width} {scheme}: errors {errors[:2]} overflow {overflow} axe {violations}")
            page.close()
    browser.close()
srv.shutdown()
print("\n".join(problems) or "smoke ok")
sys.exit(1 if problems else 0)
