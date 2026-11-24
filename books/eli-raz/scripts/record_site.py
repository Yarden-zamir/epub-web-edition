# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1"]
# ///
"""Record a built web edition for review: a short walk through the page (hero, chapter a06, the places map, the
footer) at phone and desktop width, light and dark. For each, it saves a video (.webm), a Playwright trace (.zip, with
screenshots; no DOM snapshots, which this long page makes very large), a screenshot of each step, and load timings
(timings.json: DOMContentLoaded, load, largest contentful paint, layout shift).

Usage: uv run scripts/record_site.py WEB_DIR OUT_DIR
Open a trace: uv run --with playwright==1.64.1 playwright show-trace OUT_DIR/<name>.zip
CI runs it in .github/workflows/check.yml (nightly, or by hand with record) and uploads OUT_DIR as an artifact. It checks nothing; it records.
"""
import functools
import http.server
import json
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

if len(sys.argv) != 3 or not (Path(sys.argv[1]) / "index.html").is_file():
    sys.exit(__doc__)
web, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
SIZES = {"phone": (393, 852), "desktop": (1280, 900)}
STEPS = ["#top", "#a06", "#places", "footer"]
# Largest contentful paint and layout shift come from buffered PerformanceObserver entries.
TIMINGS = """() => new Promise(done => {
  const nav = performance.getEntriesByType('navigation')[0];
  let lcp = 0, cls = 0;
  new PerformanceObserver(l => { for (const e of l.getEntries()) lcp = e.startTime; }).observe({type: 'largest-contentful-paint', buffered: true});
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value; }).observe({type: 'layout-shift', buffered: true});
  setTimeout(() => done({dom_content_loaded_ms: Math.round(nav.domContentLoadedEventEnd), load_ms: Math.round(nav.loadEventEnd),
                         largest_contentful_paint_ms: Math.round(lcp), layout_shift: Number(cls.toFixed(3))}), 500);
})"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(web)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
timings = {}
with sync_playwright() as p:
    browser = p.chromium.launch()
    for device, (width, height) in SIZES.items():
        for scheme in ("light", "dark"):
            name = f"{device}-{scheme}"
            context = browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme,
                                          record_video_dir=str(out / "video"), record_video_size={"width": width, "height": height})
            context.tracing.start(screenshots=True, snapshots=False)
            page = context.new_page()
            page.goto(f"http://127.0.0.1:{srv.server_port}/", wait_until="load", timeout=120_000)
            timings[name] = page.evaluate(TIMINGS)
            for step in STEPS:
                page.locator(step).first.scroll_into_view_if_needed()
                page.wait_for_timeout(800)
                page.screenshot(path=str(out / f"{name}-{step.strip('#')}.png"))
            context.tracing.stop(path=str(out / f"{name}.zip"))
            video = page.video
            context.close()  # Closing the context writes the video.
            if video:
                video.save_as(str(out / f"{name}.webm"))
                video.delete()
            print(name, timings[name], flush=True)
    browser.close()
srv.shutdown()
(out / "timings.json").write_text(json.dumps(timings, indent=2) + "\n")
