# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1"]
# ///
"""Check every map of a built web edition: the places map, the then-and-now view and the figure maps.

At phone (393, touch) and desktop (1280) width, light and dark:
each map must draw without script errors, keep the page from scrolling sideways and pass axe inside its box.
The places map opens a place card; the then-and-now view glides to each year and opens the side-by-side mode;
each figure map toggles to the printed image and back. Screenshots go to OUT_DIR.
--perf: on a phone with the CPU slowed 4 times (Chrome DevTools Protocol), page scroll, two-finger pinch,
the time control and a card open. Fails on a long task over 50 ms during these gestures; writes a trace to OUT_DIR.
--video: records the same tour at phone and desktop size to OUT_DIR/videos.
Usage: uv run scripts/check_maps.py WEB_DIR AXE_JS OUT_DIR [--perf] [--video]
"""
import functools
import http.server
import json
import sys
import threading
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

args = [a for a in sys.argv[1:] if not a.startswith("--")]
if len(args) != 3:
    sys.exit(__doc__)
web, AXE, out = Path(args[0]), Path(args[1]), Path(args[2])
if not (web / "index.html").is_file() or not AXE.is_file():
    sys.exit(f"missing {web / 'index.html'} or {AXE}")
out.mkdir(parents=True, exist_ok=True)
PHONE = {"viewport": {"width": 393, "height": 852}, "has_touch": True, "is_mobile": True, "device_scale_factor": 2}
DESKTOP = {"viewport": {"width": 1280, "height": 900}}
THEN_NOW = "#fig-a07-09"


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(web)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_port}/"
problems: list[str] = []


def bring(page: Page, selector: str, wait_for: str) -> None:
    """Scroll the element to the top of the view (below the bar) and wait until wait_for shows inside it."""
    page.evaluate("s => { const r = document.querySelector(s).getBoundingClientRect(); scrollTo({ top: r.top + scrollY - 70, behavior: 'instant' }); }", selector)
    page.locator(f"{selector} {wait_for}").first.wait_for(state="visible", timeout=20000)
    page.wait_for_timeout(1200)  # Tiles and images.
    page.evaluate("s => { const r = document.querySelector(s).getBoundingClientRect(); scrollTo({ top: r.top + scrollY - 70, behavior: 'instant' }); }", selector)
    page.wait_for_timeout(300)


def overflow(page: Page, where: str) -> None:
    extra = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    if extra > 0:
        problems.append(f"{where}: the page scrolls sideways by {extra} px")


def axe(page: Page, selector: str, where: str) -> None:
    found = page.evaluate("s => axe.run(document.querySelector(s), {resultTypes: ['violations']}).then(r => r.violations.map(v => v.id + ' ' + v.nodes.slice(0, 2).map(n => n.target.join(' ')).join(', ')))", selector)
    if found:
        problems.append(f"{where}: axe {found}")


def tour(page: Page, name: str, shots: bool) -> None:
    """Every map with its main interactions. With shots, a screenshot after each step."""
    snap = (lambda step: page.screenshot(path=str(out / f"{name}-{step}.png"))) if shots else (lambda step: None)
    bring(page, "#places", ".map-pin")
    snap("places")
    page.evaluate("openPlace('masada')")
    page.locator("#places :is(.place-popup, .map-sheet:not([hidden])) .pc-title").wait_for(timeout=10000)
    page.wait_for_timeout(700)
    snap("places-card")
    overflow(page, f"{name} places")

    figure_maps = page.eval_on_selector_all("figure.has-map", "els => els.map(e => e.id)")
    if THEN_NOW not in [f"#{f}" for f in figure_maps]:
        problems.append(f"{name}: no then-and-now figure {THEN_NOW}")
    bring(page, THEN_NOW, ".tn-time")
    page.locator(f"{THEN_NOW} .tn-loading").wait_for(state="hidden", timeout=30000)
    snap("then-now-1848")
    for i, year in ((2, "1945"), (3, "2026")):
        page.locator(f"{THEN_NOW} .tn-stops button:nth-child({i})").click()
        page.wait_for_timeout(1300)
        snap(f"then-now-{year}")
    page.locator(f"{THEN_NOW} .tn-modes button:nth-child(2)").click()
    page.locator(f"{THEN_NOW} .tn-panes .tn-map").first.wait_for(timeout=10000)
    page.wait_for_timeout(1500)
    snap("then-now-side")
    overflow(page, f"{name} then-now")
    page.locator(f"{THEN_NOW} .tn-modes button:nth-child(1)").click()

    for fig in figure_maps:
        if f"#{fig}" == THEN_NOW:
            continue
        bring(page, f"#{fig}", ".mf-map .map-pin")
        snap(fig)
        page.locator(f"#{fig} > .view-toggle button:nth-child(2)").click()
        if not page.locator(f"#{fig} > img").is_visible():
            problems.append(f"{name} {fig}: the printed image does not show")
        page.locator(f"#{fig} > .view-toggle button:nth-child(1)").click()
        overflow(page, f"{name} {fig}")


def check(browser, size: dict, label: str, scheme: str) -> None:
    name = f"{label}-{scheme}"
    page = browser.new_page(**size, color_scheme=scheme, reduced_motion="reduce")
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(URL, wait_until="load")
    page.add_script_tag(path=str(AXE))
    tour(page, name, shots=True)
    for selector in ("#places", *[f"#{f}" for f in page.eval_on_selector_all("figure.has-map", "els => els.map(e => e.id)")]):
        axe(page, selector, f"{name} {selector}")
    if errors:
        problems.append(f"{name}: errors {errors[:3]}")
    page.close()
    print(f"{name}: done", flush=True)


# Long tasks and frame times, measured in the page during each gesture.
WATCH = """window.__long = []; window.__frames = [];
new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__long.push(Math.round(e.duration)); }).observe({ type: 'longtask', buffered: false });
(function tick(t) { window.__frames.push(t); requestAnimationFrame(tick); })(performance.now());"""


def measure(page: Page, cdp, what: str, act) -> dict:
    page.evaluate("window.__long = []; window.__frames = []")
    act()
    page.wait_for_timeout(300)
    frames = page.evaluate("window.__frames")
    gaps = sorted(b - a for a, b in zip(frames, frames[1:]))
    result = {"gesture": what, "long_tasks_ms": page.evaluate("window.__long"),
              "median_frame_ms": round(gaps[len(gaps) // 2], 1) if gaps else None,
              "p95_frame_ms": round(gaps[int(len(gaps) * 0.95)], 1) if gaps else None}
    if any(t > 50 for t in result["long_tasks_ms"]):
        problems.append(f"perf {what}: long tasks {result['long_tasks_ms']}")
    print(json.dumps(result), flush=True)
    return result


def perf(browser) -> None:
    context = browser.new_context(**PHONE)
    page = context.new_page()
    page.goto(URL, wait_until="load")
    page.evaluate(WATCH)
    cdp = context.new_cdp_session(page)
    # Warm up first, so tile and image downloads do not count as interaction.
    bring(page, "#places", ".map-pin")
    bring(page, THEN_NOW, ".tn-time")
    page.locator(f"{THEN_NOW} .tn-loading").wait_for(state="hidden", timeout=30000)
    bring(page, "#places", ".map-pin")
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    browser.start_tracing(page=page, path=str(out / "perf-trace.json"), screenshots=False)
    box = page.evaluate("(() => { const r = document.querySelector('#places-map').getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; })()")
    results = [
        measure(page, cdp, "one-finger page scroll over the places map", lambda: cdp.send("Input.synthesizeScrollGesture", {
            "x": int(box["x"]), "y": int(box["y"]), "yDistance": -300, "speed": 800, "gestureSourceType": "touch"})),
    ]
    box = page.evaluate("(() => { const r = document.querySelector('#places-map').getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; })()")
    results.append(measure(page, cdp, "two-finger pinch on the places map", lambda: cdp.send("Input.synthesizePinchGesture", {
        "x": box["x"], "y": box["y"], "scaleFactor": 2.5, "relativeSpeed": 400, "gestureSourceType": "touch"})))
    results.append(measure(page, cdp, "open a place card", lambda: (page.evaluate("openPlace('masada')"), page.wait_for_timeout(1500))))
    bring(page, THEN_NOW, ".tn-time")

    def drag_time() -> None:
        r = page.evaluate(f"(() => {{ const r = document.querySelector('{THEN_NOW} .tn-time input').getBoundingClientRect(); return {{ x: r.x, y: r.y + r.height / 2, w: r.width }}; }})()")
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": r["x"] + 8, "y": r["y"]}]})
        for i in range(1, 41):
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": r["x"] + 8 + (r["w"] - 16) * i / 40, "y": r["y"]}]})
            page.wait_for_timeout(16)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        page.wait_for_timeout(800)

    results.append(measure(page, cdp, "drag the time control from 1848 to 2026", drag_time))
    results.append(measure(page, cdp, "glide to 1848 with the year button", lambda: (page.locator(f"{THEN_NOW} .tn-stops button").first.click(), page.wait_for_timeout(1500))))
    browser.stop_tracing()
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    (out / "perf.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    context.close()


def video(browser) -> None:
    for label, size in (("phone", PHONE), ("desktop", DESKTOP)):
        context = browser.new_context(**size, record_video_dir=str(out / "videos"), record_video_size=size["viewport"])
        page = context.new_page()
        page.goto(URL, wait_until="load")
        tour(page, label, shots=False)
        page.wait_for_timeout(500)
        path = page.video.path()
        context.close()
        Path(path).rename(out / "videos" / f"tour-{label}.webm")


with sync_playwright() as p:
    browser = p.chromium.launch()
    if "--perf" in sys.argv:
        perf(browser)
    if "--video" in sys.argv:
        video(browser)
    for label, size in (("phone", PHONE), ("desktop", DESKTOP)):
        for scheme in ("light", "dark"):
            check(browser, size, label, scheme)
    browser.close()
srv.shutdown()
print("\n".join(problems) or "maps ok")
sys.exit(1 if problems else 0)
