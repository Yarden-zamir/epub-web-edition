# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1"]
# ///
"""Check the errata lane of a built web edition: the errata page, its print viewer, the † popover, the "as printed"
mode and the figure viewer.

At phone (393, touch) and desktop (1280) width, light and dark: no script errors, no sideways scroll, axe on the
errata page, inside the open print viewer and inside the open figure viewer, and each interaction does what it
should (see tour()). Screenshots go to OUT_DIR.
--perf: on a phone with the CPU slowed 4 times, errata filter and search, the print viewer, the † popover, the
"as printed" switch, and figure viewer swipe, pinch and swipe down. Fails on a long task over 50 ms; writes
OUT_DIR/perf.json and a trace.
--video: records the same tour at phone and desktop size to OUT_DIR/videos.
Usage: uv run scripts/check_errata.py WEB_DIR AXE_JS OUT_DIR [--perf] [--video]
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
if not (web / "errata" / "index.html").is_file() or not AXE.is_file():
    sys.exit(f"missing {web / 'errata' / 'index.html'} or {AXE}")
out.mkdir(parents=True, exist_ok=True)
PHONE = {"viewport": {"width": 393, "height": 852}, "has_touch": True, "is_mobile": True, "device_scale_factor": 2}
DESKTOP = {"viewport": {"width": 1280, "height": 900}}
ROW = "#row-4"  # A verified row: "south of Hebron" -> "south of Bethlehem" in a06-p023.
FIGURE = "fig-a06-01"  # A photo with a caption, early in the book.


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(web)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_port}/"
problems: list[str] = []


def expect(ok: bool, what: str) -> None:
    if not ok:
        problems.append(what)


def overflow(page: Page, where: str) -> None:
    extra = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    expect(extra <= 0, f"{where}: the page scrolls sideways by {extra} px")


def axe(page: Page, selector: str, where: str) -> None:
    if not page.evaluate("typeof axe !== 'undefined'"):
        page.add_script_tag(path=str(AXE))
    found = page.evaluate("s => axe.run(document.querySelector(s), {resultTypes: ['violations']}).then(r => r.violations.map(v => v.id + ' ' + v.nodes.slice(0, 2).map(n => n.target.join(' ')).join(', ')))", selector)
    expect(not found, f"{where}: axe {found}")


def touch(cdp, kind: str, points: list[tuple[float, float]]) -> None:
    cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [{"x": x, "y": y, "id": i} for i, (x, y) in enumerate(points)]})


def drag(page: Page, cdp, start: tuple, end: tuple, second: tuple | None = None, steps: int = 12) -> None:
    """One finger from start to end, or two with second = (start2, end2)."""
    def at(t: float) -> list[tuple[float, float]]:
        pts = [(start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t)]
        if second:
            pts.append((second[0][0] + (second[1][0] - second[0][0]) * t, second[0][1] + (second[1][1] - second[0][1]) * t))
        return pts
    touch(cdp, "touchStart", at(0))
    for i in range(1, steps + 1):
        touch(cdp, "touchMove", at(i / steps))
        page.wait_for_timeout(16)
    touch(cdp, "touchEnd", [])


def flag(page: Page, js: str) -> bool:
    return bool(page.evaluate(js))


VIEWER_OPEN = "document.getElementById('figure-dialog').open"
ZOOMED = "document.getElementById('figure-dialog').hasAttribute('data-zoomed')"


def errata_tour(page: Page, name: str, snap, phone: bool, axe_too: bool) -> None:
    page.goto(URL + "errata/", wait_until="load")
    snap("errata")
    overflow(page, f"{name} errata page")
    if axe_too:
        axe(page, "body", f"{name} errata page")
    page.locator(".er-filter[data-filter='editor']").click()
    expect(page.locator(f"{ROW}").is_hidden(), f"{name}: the editor filter still shows a verified row")
    page.locator(".er-filter[data-filter='']").click()
    page.locator("#er-search").fill("Hebron")
    page.wait_for_timeout(200)
    expect(page.locator(".er-row:not([hidden])").count() >= 1 and page.locator(ROW).is_visible(), f"{name}: search 'Hebron' does not find row 4")
    page.locator("#er-search").fill("")
    page.locator(f"{ROW} .er-pill").first.click()
    page.wait_for_selector("#er-viewer[open] .erv-image.ready", timeout=10000)
    expect("south of Hebron" in page.locator("#erv-text mark.was").first.text_content(), f"{name}: the print viewer does not mark the printed words")
    snap("errata-viewer-line")
    if axe_too:
        axe(page, "#er-viewer", f"{name} print viewer")
    page.locator(".erv-tab").nth(1).click()
    page.wait_for_selector("#er-viewer .erv-image.ready[data-kind='page']", timeout=10000)
    page.locator("#erv-img").click()
    expect(flag(page, "document.getElementById('erv-image').classList.contains('zoomed')"), f"{name}: a click does not zoom the page image")
    snap("errata-viewer-page")
    page.go_back()
    page.wait_for_timeout(300)
    expect(not flag(page, "document.getElementById('er-viewer').open"), f"{name}: Back does not close the print viewer")

    # To the book: the jump highlights the place; the † opens its popover; "as printed" swaps the text.
    page.locator(f"{ROW} .er-go").click()
    page.wait_for_load_state("load")
    page.wait_for_timeout(500)
    expect("hl=" not in page.url and page.url.endswith("#a06-p023"), f"{name}: the jump address is {page.url}")
    mark = page.locator("#a06-p023 a.edition-mark")
    mark.click()
    page.wait_for_selector("#note-popover:popover-open .corr-pop", timeout=5000)
    expect("south of Hebron" in page.locator("#note-popover .corr-was").text_content(), f"{name}: the † popover lacks the printed form")
    snap("correction-popover")
    page.locator("#note-popover .corr-actions button").click()
    page.wait_for_selector(".printed-banner", timeout=5000)
    expect(page.locator("#a06-p023 span.edition-correction").text_content() == "south of Hebron", f"{name}: 'as printed' does not show the printed text")
    expect(mark.is_hidden(), f"{name}: 'as printed' still shows the † marks")
    snap("as-printed")
    overflow(page, f"{name} book as printed")
    page.reload(wait_until="load")
    expect(page.locator(".printed-banner").count() == 1, f"{name}: 'as printed' does not persist over a reload")
    page.locator(".printed-banner button").click()
    expect(page.locator("#a06-p023 span.edition-correction").text_content() == "south of Bethlehem", f"{name}: the banner does not restore the corrected text")


def figure_tour(page: Page, name: str, snap, phone: bool, axe_too: bool, cdp) -> None:
    page.goto(URL + f"?photo={FIGURE}", wait_until="load")
    page.wait_for_selector("#figure-dialog[open]", timeout=10000)
    page.wait_for_timeout(600)
    expect(f"photo={FIGURE}" in page.url, f"{name}: ?photo does not stay in the address while the viewer is open")
    expect(page.locator("#viewer-caption").text_content().strip() != "", f"{name}: the figure viewer shows no caption")
    snap("figure-viewer")
    overflow(page, f"{name} figure viewer")
    if axe_too:
        axe(page, "#figure-dialog", f"{name} figure viewer")
    w, h = page.viewport_size["width"], page.viewport_size["height"]
    if phone:
        drag(page, cdp, (w * 0.15, h * 0.45), (w * 0.85, h * 0.45))  # Finger moves right: the next image (right to left).
        page.wait_for_timeout(700)
        expect(f"photo={FIGURE}" not in page.url and "photo=" in page.url, f"{name}: a swipe does not step to the next figure")
        drag(page, cdp, (w * 0.4, h * 0.45), (w * 0.3, h * 0.45), second=((w * 0.6, h * 0.5), (w * 0.75, h * 0.5)))
        page.wait_for_timeout(400)
        expect(flag(page, ZOOMED), f"{name}: a pinch does not zoom")
        snap("figure-viewer-zoomed")
        page.keyboard.press("0")
        page.wait_for_timeout(400)
        drag(page, cdp, (w * 0.5, h * 0.35), (w * 0.5, h * 0.8), steps=10)
        page.wait_for_timeout(700)
        expect(not flag(page, VIEWER_OPEN), f"{name}: a swipe down does not close the figure viewer")
    else:
        page.keyboard.press("ArrowLeft")
        page.wait_for_timeout(600)
        expect(f"photo={FIGURE}" not in page.url, f"{name}: the left arrow does not step to the next figure")
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(600)
        expect(f"photo={FIGURE}" in page.url, f"{name}: the right arrow does not step back")
        box = page.locator("#viewer-img").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2  # The caption column takes one side.
        page.mouse.move(cx, cy)
        for _ in range(5):
            page.mouse.wheel(0, -120)
            page.wait_for_timeout(30)
        page.wait_for_timeout(300)
        expect(flag(page, ZOOMED), f"{name}: the wheel does not zoom")
        snap("figure-viewer-zoomed")
        page.mouse.dblclick(cx, cy)
        page.wait_for_timeout(400)
        expect(not flag(page, ZOOMED), f"{name}: a double click does not zoom out")
        page.go_back()
        page.wait_for_timeout(500)
        expect(not flag(page, VIEWER_OPEN), f"{name}: Back does not close the figure viewer")
    expect("photo=" not in page.url, f"{name}: the address keeps ?photo after the viewer closes")


def check(browser, size: dict, label: str, scheme: str) -> None:
    name = f"{label}-{scheme}"
    context = browser.new_context(**size, color_scheme=scheme, reduced_motion="reduce")
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    snap = lambda step: page.screenshot(path=str(out / f"{name}-{step}.png"))  # noqa: E731
    errata_tour(page, name, snap, label == "phone", axe_too=True)
    figure_tour(page, name, snap, label == "phone", axe_too=True, cdp=context.new_cdp_session(page) if label == "phone" else None)
    expect(not errors, f"{name}: errors {errors[:3]}")
    context.close()
    print(f"{name}: done", flush=True)


WATCH = """window.__long = []; window.__frames = [];
new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__long.push(Math.round(e.duration)); }).observe({ type: 'longtask', buffered: false });
(function tick(t) { window.__frames.push(t); requestAnimationFrame(tick); })(performance.now());"""


def measure(page: Page, what: str, act) -> dict:
    page.evaluate("window.__long = []; window.__frames = []")
    act()
    page.wait_for_timeout(300)
    frames = page.evaluate("window.__frames")
    gaps = sorted(b - a for a, b in zip(frames, frames[1:]))
    result = {"gesture": what, "long_tasks_ms": page.evaluate("window.__long"),
              "median_frame_ms": round(gaps[len(gaps) // 2], 1) if gaps else None,
              "p95_frame_ms": round(gaps[int(len(gaps) * 0.95)], 1) if gaps else None}
    expect(not any(t > 50 for t in result["long_tasks_ms"]), f"perf {what}: long tasks {result['long_tasks_ms']}")
    print(json.dumps(result), flush=True)
    return result


def perf(browser) -> None:
    context = browser.new_context(**PHONE)
    context.add_init_script(WATCH)
    page = context.new_page()
    cdp = context.new_cdp_session(page)
    results = []
    page.goto(URL + "errata/", wait_until="load")
    page.wait_for_timeout(800)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    browser.start_tracing(page=page, path=str(out / "perf-trace.json"), screenshots=False)
    results.append(measure(page, "errata filter, then all", lambda: (page.locator(".er-filter[data-filter='editor']").click(), page.locator(".er-filter[data-filter='']").click())))
    results.append(measure(page, "errata search keystrokes", lambda: page.locator("#er-search").press_sequentially("Hebron", delay=80)))
    page.locator("#er-search").fill("")
    results.append(measure(page, "open the print viewer", lambda: (page.locator(f"{ROW} .er-pill").first.click(), page.wait_for_timeout(800))))
    results.append(measure(page, "zoom the page image", lambda: (page.locator(".erv-tab").nth(1).click(), page.wait_for_timeout(600), page.locator("#erv-img").click(), page.wait_for_timeout(500))))
    browser.stop_tracing()
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    page.goto(URL + f"?photo={FIGURE}", wait_until="load")
    page.wait_for_selector("#figure-dialog[open]", timeout=10000)
    page.wait_for_timeout(1500)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    w, h = 393, 852
    results.append(measure(page, "figure viewer: swipe to the next image", lambda: (drag(page, cdp, (w * 0.15, h * 0.45), (w * 0.85, h * 0.45)), page.wait_for_timeout(700))))
    results.append(measure(page, "figure viewer: pinch", lambda: drag(page, cdp, (w * 0.4, h * 0.45), (w * 0.3, h * 0.45), second=((w * 0.6, h * 0.5), (w * 0.75, h * 0.5)))))
    results.append(measure(page, "figure viewer: pan while zoomed", lambda: drag(page, cdp, (w * 0.5, h * 0.5), (w * 0.3, h * 0.4))))
    page.keyboard.press("0")
    results.append(measure(page, "figure viewer: swipe down to close", lambda: (drag(page, cdp, (w * 0.5, h * 0.35), (w * 0.5, h * 0.8), steps=10), page.wait_for_timeout(700))))
    page.evaluate("document.querySelector('#a06-p023').scrollIntoView({block: 'center'})")
    page.wait_for_timeout(500)
    results.append(measure(page, "open a † popover", lambda: (page.locator("#a06-p023 a.edition-mark").click(), page.wait_for_timeout(500))))
    results.append(measure(page, "switch the book to 'as printed'", lambda: (page.locator("#note-popover .corr-actions button").click(), page.wait_for_timeout(600))))
    results.append(measure(page, "switch back to the corrected text", lambda: (page.locator(".printed-banner button").click(), page.wait_for_timeout(600))))
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    (out / "perf.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    context.close()


def video(browser) -> None:
    (out / "videos").mkdir(exist_ok=True)
    for label, size in (("phone", PHONE), ("desktop", DESKTOP)):
        context = browser.new_context(**size, record_video_dir=str(out / "videos"), record_video_size=size["viewport"])
        page = context.new_page()
        errata_tour(page, label, lambda step: None, label == "phone", axe_too=False)
        figure_tour(page, label, lambda step: None, label == "phone", axe_too=False,
                    cdp=context.new_cdp_session(page) if label == "phone" else None)
        page.wait_for_timeout(500)
        path = page.video.path()
        context.close()
        Path(path).rename(out / "videos" / f"errata-{label}.webm")


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
print("\n".join(problems) or "errata ok")
sys.exit(1 if problems else 0)
