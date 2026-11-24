# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1"]
# ///
"""Check every interactive explainer (explorable) of a built web edition, and take screenshots.

For each figure.has-explorable, at phone and desktop width, light and dark (reduced motion):
it must load without script or console errors, move with the arrow keys, follow a drag in the drawing,
announce a summary in its live region, reset, toggle to the printed image, and pass axe inside the figure.
Usage: uv run scripts/check_explorables.py WEB_DIR AXE_JS [SHOT_DIR]
"""
import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

web, AXE = Path(sys.argv[1]), Path(sys.argv[2])
shots = Path(sys.argv[3]) if len(sys.argv) > 3 else None
if not (web / "index.html").is_file() or not AXE.is_file():
    sys.exit(f"usage: check_explorables.py WEB_DIR AXE_JS [SHOT_DIR]; missing {web / 'index.html'} or {AXE}")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(web)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
problems: list[str] = []


def shot(page, locator, path: Path) -> None:
    """Viewport screenshot clipped to the element. Locator.screenshot waits for a stable box, and the reader's
    scroll effects keep some figures moving on touch screens. The viewport grows to fit a tall figure."""
    size = page.viewport_size
    height = page.evaluate("el => el.getBoundingClientRect().height", locator.element_handle())
    page.set_viewport_size({"width": size["width"], "height": max(size["height"], int(height) + 120)})
    page.evaluate("el => el.scrollIntoView({block: 'center'})", locator.element_handle())
    page.wait_for_timeout(300)
    box = page.evaluate("el => { const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; }",
                        locator.element_handle())
    page.screenshot(path=str(path), clip=box)
    page.set_viewport_size(size)

with sync_playwright() as p:
    browser = p.chromium.launch()
    for width, height in ((360, 740), (1280, 900)):
        for scheme in ("light", "dark"):
            page = browser.new_page(viewport={"width": width, "height": height}, color_scheme=scheme,
                                    reduced_motion="reduce", has_touch=width < 600)
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.goto(f"http://127.0.0.1:{srv.server_port}/", wait_until="load")
            ids = page.eval_on_selector_all("figure.has-explorable", "els => els.map(e => e.id)")
            if not ids:
                problems.append("no figure.has-explorable in the page")
            page.add_script_tag(path=str(AXE))
            for fig_id in ids:
                where = f"{fig_id} {width} {scheme}"
                fig = page.locator(f"#{fig_id}")
                fig.scroll_into_view_if_needed()
                slider = fig.locator("input[type=range]")
                try:
                    slider.wait_for(state="visible", timeout=8000)
                except Exception:
                    problems.append(f"{where}: explainer did not appear")
                    continue
                page.wait_for_timeout(800)
                start = slider.input_value()
                if shots:
                    shot(page, fig, shots / f"{fig_id}-{width}-{scheme}-start.png")
                slider.focus()
                for _ in range(10):
                    page.keyboard.press("ArrowRight")
                if slider.input_value() == start:
                    problems.append(f"{where}: arrow keys do not move the control")
                page.wait_for_timeout(300)
                live = fig.locator("[aria-live]").inner_text()
                if not live.strip():
                    problems.append(f"{where}: live region is empty after a keyboard move")
                fig.locator(".xp-reset").click()
                if slider.input_value() != start:
                    problems.append(f"{where}: reset does not restore {start}")
                handle = fig.locator(".xp-handle").first
                if handle.count():
                    box = handle.bounding_box()
                    if box is None:
                        problems.append(f"{where}: drag handle has no box")
                    else:
                        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                        # Drag down, then up: the start value may sit at either end of the range.
                        for sign in (1, -1):
                            page.mouse.move(cx, cy)
                            page.mouse.down()
                            for step in range(1, 11):
                                page.mouse.move(cx, cy + sign * step * 12)
                            page.mouse.up()
                            page.wait_for_timeout(200)
                            if slider.input_value() != start:
                                break
                        if slider.input_value() == start:
                            problems.append(f"{where}: dragging in the drawing does not change the value")
                if shots:
                    shot(page, fig, shots / f"{fig_id}-{width}-{scheme}-moved.png")
                violations = page.evaluate(
                    "sel => axe.run(document.querySelector(sel), {resultTypes: ['violations']})"
                    ".then(r => r.violations.map(v => v.id + ' ' + v.nodes.slice(0, 3).map(n => n.target.join(' ')).join(', ')))",
                    f"#{fig_id}")
                if violations:
                    problems.append(f"{where}: axe {violations}")
                fig.get_by_role("button", name="האיור המודפס").click()
                if not fig.locator(":scope > img").is_visible() or fig.locator(".explorable").is_visible():
                    problems.append(f"{where}: the toggle does not show the printed image")
                fig.get_by_role("button", name="הדגמה אינטראקטיבית").click()
            overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if overflow > 0:
                problems.append(f"{width} {scheme}: horizontal overflow {overflow}")
            if errors:
                problems.append(f"{width} {scheme}: errors {errors[:3]}")
            page.close()
    browser.close()
srv.shutdown()
print("\n".join(problems) or "explorables ok")
sys.exit(1 if problems else 0)
