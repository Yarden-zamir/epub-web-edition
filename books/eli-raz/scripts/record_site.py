# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1"]
# ///
"""Record a built web edition for review: a short walk through the page (hero, chapter a06, the places map, the
footer) at phone and desktop width, light and dark. For each, it saves a video (.webm), a Playwright trace (.zip, with
screenshots; no DOM snapshots, which this long page makes very large), a screenshot of each step, and load timings
(timings.json: DOMContentLoaded, load, largest contentful paint, layout shift).

Map load (maps.json, videos in maps/): each map in a fresh phone visit with an empty cache, on the Chrome DevTools
"Fast 4G" profile with the CPU slowed 4 times. The visit waits until the page is idle, jumps to the map, and times the
first drawn tile and (then-and-now) the first drawn layer. It also counts the bytes of map files in the whole visit.
The server gzips text files, as the real host compresses them.

Usage: uv run scripts/record_site.py WEB_DIR OUT_DIR
Open a trace: uv run --with playwright==1.64.1 playwright show-trace OUT_DIR/<name>.zip
CI runs it in .github/workflows/check.yml (nightly, or by hand with record) and uploads OUT_DIR as an artifact. It checks nothing; it records.
"""
import functools
import gzip
import http.server
import io
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


GZIP = {".html", ".js", ".css", ".json", ".svg", ".csv", ".webmanifest"}
# Chrome DevTools "Fast 4G": 9 Mbit/s down, 1.5 Mbit/s up, 165 ms latency (the DevTools values, with their 0.9 and 2.75).
FAST_4G = {"offline": False, "latency": 165, "downloadThroughput": 9e6 / 8 * 0.9, "uploadThroughput": 1.5e6 / 8 * 0.9}
# A request is a map file when its address has one of these parts.
MAP_FILES = {"tiles": ".tile.opentopomap.org/", "library": "leaflet", "data": "/data/maps/", "layers": "/media/then-now/"}
# Wait in the page for the first loaded tile in the map box and, for then-and-now, the first shown layer image.
# Times are ms from the jump. A box that is still hidden (not drawn yet) has no tiles.
MAP_TIMES = """async ([jump, box, layered]) => {
  const library = typeof L !== 'undefined';
  document.querySelector(jump).scrollIntoView({ block: 'start', behavior: 'instant' });
  const t0 = performance.now(), found = { library_before_jump: library };
  const frame = () => new Promise(r => requestAnimationFrame(r));
  while (performance.now() - t0 < 60000) {
    await frame();
    const el = document.querySelector(box), ms = Math.round(performance.now() - t0);
    if (found.first_tile_ms === undefined && el?.querySelector('.leaflet-tile-loaded')) found.first_tile_ms = ms;
    if (layered && found.first_layer_ms === undefined
        && [...(el?.querySelectorAll('img.tn-layer') ?? [])].some(i => i.complete && i.naturalWidth && parseFloat(i.style.opacity) > 0)) found.first_layer_ms = ms;
    if (found.first_tile_ms !== undefined && (!layered || found.first_layer_ms !== undefined)) break;
  }
  return found;
}"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def send_head(self):  # noqa: ANN201 (the base class returns a file or None)
        path = Path(self.translate_path(self.path))
        if path.is_dir():
            path = path / "index.html"
        if path.suffix not in GZIP or not path.is_file() or "gzip" not in self.headers.get("Accept-Encoding", ""):
            return super().send_head()
        body = gzip.compress(path.read_bytes(), compresslevel=6, mtime=0)
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        return io.BytesIO(body)


def record_maps(browser, port: int) -> dict:  # noqa: ANN001 (a Playwright Browser)
    """Map load times and bytes, one fresh visit per map (see the module notes)."""
    base = f"http://127.0.0.1:{port}/"
    probe = browser.new_page()
    probe.goto(base, wait_until="domcontentloaded", timeout=120_000)
    maps = [("places", "#places", "#places-map", False)] + [
        (fig, f"#{fig}", f"#{fig}", kind == "then-now")
        for fig, kind in probe.evaluate("[...document.querySelectorAll('figure.has-map')].map(f => [f.id, f.querySelector('.map-figure').dataset.kind])")
    ]
    probe.close()
    results = {}
    for name, jump, box, layered in maps:
        # No service worker: its fetches skip the page's network profile and would hide the tile requests.
        context = browser.new_context(viewport={"width": 393, "height": 852}, is_mobile=True, has_touch=True, device_scale_factor=2,
                                      service_workers="block", record_video_dir=str(out / "maps"), record_video_size={"width": 393, "height": 852})
        page = context.new_page()
        cdp = context.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.send("Network.emulateNetworkConditions", FAST_4G)
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        urls: dict[str, str] = {}
        sizes = dict.fromkeys(MAP_FILES, 0)
        cdp.on("Network.requestWillBeSent", lambda e: urls.__setitem__(e["requestId"], e["request"]["url"]))

        def finished(e: dict) -> None:
            url = urls.get(e["requestId"], "")
            for part, needle in MAP_FILES.items():
                if needle in url:
                    sizes[part] += int(e["encodedDataLength"])
                    break

        cdp.on("Network.loadingFinished", finished)
        page.goto(base, wait_until="load", timeout=180_000)
        page.wait_for_timeout(3000)  # A reader on the first screen; idle work runs here.
        found = page.evaluate(MAP_TIMES, [jump, box, layered])
        page.wait_for_timeout(8000)  # Let the map finish its first view before the bytes are counted.
        results[name] = found | {"bytes": sizes | {"total": sum(sizes.values())}}
        video = page.video
        context.close()
        if video:
            video.save_as(str(out / "maps" / f"{name}.webm"))
            video.delete()
        print("map", name, results[name], flush=True)
    return results


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
    maps = record_maps(browser, srv.server_port)
    browser.close()
srv.shutdown()
(out / "timings.json").write_text(json.dumps(timings, indent=2) + "\n")
(out / "maps.json").write_text(json.dumps(maps, indent=2) + "\n")
