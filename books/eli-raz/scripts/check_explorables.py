# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1"]
# ///
"""Check every interactive explainer (explorable) of a built web edition; take screenshots and videos.

For each figure.has-explorable, at phone and desktop width, light and dark (reduced motion):
it must load without script or console errors, move with the arrow keys (Shift: larger steps), follow a drag
in the drawing, announce a summary in its live region, reset, toggle to the printed image, and pass axe.
While a drag runs, the value line and the explanation must not move (stable numbers).
Touch, on a phone (is_mobile, real touch events through CDP): dragging the handle changes the value without
scrolling the page or selecting text; a swipe that starts on the handle does not scroll; one elsewhere on the drawing does.
Heavy parts, on by default in GitHub Actions (GITHUB_ACTIONS=true), or with --perf and VIDEO_DIR elsewhere:
- performance: at phone width with the CPU slowed 4 times, a scripted drag must cause no long task over 50 ms and keep
  the 95th percentile frame interval at or under 20 ms, or at or under the page's own floor on that machine: the same
  measure for plain mouse moves over the drawing without a drag (a CI runner without a GPU may not reach 60 fps at 4x for any page).
  --trace also saves a Chromium trace of each drag to SHOT_DIR;
- videos (VIDEO_DIR, in CI SHOT_DIR/videos): each explainer at phone size, dragged with real touch events, and at desktop
  size with a mouse, keys, a mark and reset (motion on).
No element of the book may reach past the viewport, and the page may not scroll sideways, during or after
interaction (each explainer moved through its full range). After a jump to an explainer's figure, the figure may
not move while the explainer replaces the printed image, nor when the toggle switches between the two.
Usage: uv run scripts/check_explorables.py WEB_DIR AXE_JS [SHOT_DIR [VIDEO_DIR]] [--perf] [--trace]
"""
import functools
import http.server
import os
import shutil
import sys
import threading
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ci = os.environ.get("GITHUB_ACTIONS") == "true"
perf = "--perf" in sys.argv or ci
trace = "--trace" in sys.argv
args = [a for a in sys.argv[1:] if a not in ("--perf", "--trace")]
web, AXE = Path(args[0]), Path(args[1])
shots = Path(args[2]) if len(args) > 2 else None
videos = Path(args[3]) if len(args) > 3 else (shots / "videos" if ci and shots else None)
if not (web / "index.html").is_file() or not AXE.is_file():
    sys.exit(f"usage: check_explorables.py WEB_DIR AXE_JS [SHOT_DIR [VIDEO_DIR]]; missing {web / 'index.html'} or {AXE}")
if shots:
    shots.mkdir(parents=True, exist_ok=True)
LONG_TASK_MS, P95_FRAME_MS = 50, 20


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(web)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_port}/"
problems: list[str] = []


def shot(page: Page, locator, path: Path) -> None:
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


def open_explainer(page: Page, fig_id: str):
    fig = page.locator(f"#{fig_id}")
    fig.scroll_into_view_if_needed()
    slider = fig.locator("input[type=range]")
    slider.wait_for(state="visible", timeout=15000)
    page.evaluate("el => el.scrollIntoView({block: 'start'})", fig.locator(".xp-stage").element_handle())
    page.wait_for_timeout(400)
    return fig, slider


def center_handle(page: Page, fig) -> None:
    """The site's fixed top bar covers the top of the viewport: keep the handle clear of it before a drag."""
    page.evaluate("el => el.scrollIntoView({block: 'center'})", fig.locator(".xp-handle").first.element_handle())
    page.wait_for_timeout(200)


# Elements of the book that reach past the viewport (with overlay scrollbars a full-bleed figure ends exactly at
# its edges), and the page's own sideways overflow. Run during and after interaction.
TOO_WIDE = """() => {
  const vw = document.documentElement.clientWidth, out = [];
  const name = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.classList.length ? '.' + [...e.classList].slice(0, 2).join('.') : '');
  if (document.documentElement.scrollWidth > vw) out.push('page ' + document.documentElement.scrollWidth + ' > ' + vw);
  for (const el of document.querySelectorAll('#read *')) {
    const r = el.getBoundingClientRect();
    if (!r.width || (r.left >= -1 && r.right <= vw + 1)) continue;
    const parent = el.parentElement.getBoundingClientRect();
    if (parent.left < -1 || parent.right > vw + 1) continue; // Report the outermost element only.
    out.push(name(el) + ' [' + Math.round(r.left) + ', ' + Math.round(r.right) + '] in ' + vw);
    if (out.length >= 3) break;
  }
  return out;
}"""


def too_wide(page: Page, where: str, when: str) -> None:
    for item in page.evaluate(TOO_WIDE):
        problems.append(f"{where}: wider than the viewport {when}: {item}")


def drag(page: Page, fig, steps: int, dy: float, pause: int = 0) -> bool:
    """Drag the first handle down (dy > 0) or up; True if the value changed."""
    slider = fig.locator("input[type=range]")
    before = slider.input_value()
    center_handle(page, fig)
    box = fig.locator(".xp-handle").first.bounding_box()
    if box is None:
        return False
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(cx, cy)
    page.mouse.down()
    for step in range(1, steps + 1):
        page.mouse.move(cx, cy + dy * step)
        if pause:
            page.wait_for_timeout(pause)
    page.mouse.up()
    page.wait_for_timeout(300)
    return slider.input_value() != before


with sync_playwright() as p:
    browser = p.chromium.launch()
    ids: list[str] = []
    for width, height in ((360, 740), (1280, 900)):
        for scheme in ("light", "dark"):
            page = browser.new_page(viewport={"width": width, "height": height}, color_scheme=scheme,
                                    reduced_motion="reduce", has_touch=width < 600)
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.goto(URL, wait_until="load", timeout=90000)
            ids = page.eval_on_selector_all("figure.has-explorable", "els => els.map(e => e.id)")
            if not ids:
                problems.append("no figure.has-explorable in the page")
            page.add_script_tag(path=str(AXE))
            for fig_id in ids:
                where = f"{fig_id} {width} {scheme}"
                try:
                    fig, slider = open_explainer(page, fig_id)
                except Exception:
                    problems.append(f"{where}: explainer did not appear")
                    continue
                start = slider.input_value()
                if shots:
                    shot(page, fig, shots / f"{fig_id}-{width}-{scheme}-start.png")
                slider.focus()
                page.keyboard.press("ArrowRight")
                one = float(slider.input_value()) - float(start)
                page.keyboard.press("Shift+ArrowRight")
                shifted = float(slider.input_value()) - float(start) - one
                if one <= 0 or shifted <= one:
                    problems.append(f"{where}: arrow keys do not step, or Shift does not take a larger step ({one}, {shifted})")
                page.wait_for_timeout(300)
                if not fig.locator("[aria-live]").inner_text().strip():
                    problems.append(f"{where}: live region is empty after a keyboard move")
                fig.locator(".xp-reset").click()
                page.wait_for_timeout(200)
                if slider.input_value() != start:
                    problems.append(f"{where}: reset does not restore {start}")
                if width > 600:
                    # Positions of the label, the unit and the explanation must not change in the middle of a drag.
                    # Positions inside the card (so a shift of the whole page is told apart), plus the card itself.
                    probe = """f => { const card = f.querySelector('.explorable').getBoundingClientRect();
                      const at = {card: [Math.round(card.left), Math.round(card.top)]};
                      for (const s of ['.xp-label-text', '.xp-num', '.xp-unit', '.xp-readout']) {
                        const r = f.querySelector(s).getBoundingClientRect();
                        at[s] = [Math.round(r.left - card.left), Math.round(r.top - card.top), Math.round(r.width)];
                      }
                      return at; }"""
                    center_handle(page, fig)
                    before = fig.evaluate(probe)
                    box = fig.locator(".xp-handle").bounding_box()
                    hx, hy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                    page.mouse.move(hx, hy); page.mouse.down()
                    shifted = []
                    for step in range(1, 13):
                        page.mouse.move(hx, hy + (step * 9 if fig_id == "fig-a14-07" else -step * 9))
                        page.wait_for_timeout(30)
                        now = fig.evaluate(probe)
                        moved = [f"{k} {before[k]}->{now[k]}" for k in now if k != "card" and now[k] != before[k]]
                        if moved:
                            shifted.append(f"step {step}: {', '.join(moved)}")
                        if now["card"] != before["card"]:
                            print(f"note {where}: the whole card moved on the page at step {step}: {before['card']} -> {now['card']}")
                    page.mouse.up(); page.wait_for_timeout(300)
                    if shifted:
                        problems.append(f"{where}: the value line or the explanation moved inside the card during a drag: {shifted[:3]}")
                # The full range, slowly, with the width checked while the drawing moves and after it settles.
                for value in (slider.get_attribute("max"), slider.get_attribute("min")):
                    slider.evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input')); el.dispatchEvent(new Event('change')); }", value)
                    page.wait_for_timeout(250)
                    too_wide(page, where, f"while moving to {value}")
                    page.wait_for_timeout(1300)
                    too_wide(page, where, f"after moving to {value}")
                if not (drag(page, fig, 10, 12) or drag(page, fig, 10, -12)):
                    problems.append(f"{where}: dragging in the drawing does not change the value")
                hit = page.evaluate("el => el.getBoundingClientRect().width", fig.locator(".xp-handle").first.element_handle())
                if hit < 44:
                    problems.append(f"{where}: handle touch target is {hit:.0f} px, under 44")
                marks = fig.locator(".xp-mark")
                if marks.count():
                    marks.last.click()
                    page.wait_for_timeout(200)
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

    # A jump to an explainer's figure (#id) keeps the figure where the jump put it while the explainer replaces the
    # printed image, and the toggle between the two does not move it either (scroll anchoring can shift the page).
    for width, height in ((393, 852), (1280, 900)):
        page = browser.new_page(viewport={"width": width, "height": height}, reduced_motion="reduce")
        for fig_id in ids:
            where = f"{fig_id} {width} jump"
            page.goto(f"{URL}#{fig_id}", wait_until="load", timeout=90000)
            fig = page.locator(f"#{fig_id}")
            top = lambda: page.evaluate("id => document.getElementById(id).getBoundingClientRect().top", fig_id)
            first = top()
            moved = 0.0
            for _ in range(20):  # The explainer loads as the figure nears the view, then swaps in.
                page.wait_for_timeout(150)
                moved = max(moved, abs(top() - first))
            if not fig.locator("input[type=range]").is_visible():
                problems.append(f"{where}: the explainer did not appear after a jump to its figure")
            elif moved > 2:
                problems.append(f"{where}: the figure moved {moved:.0f} px while the explainer replaced the printed image")
            for name in ("האיור המודפס", "הדגמה אינטראקטיבית"):
                before = top()
                fig.get_by_role("button", name=name).click()
                page.wait_for_timeout(300)
                if abs(top() - before) > 2:
                    problems.append(f"{where}: the figure moved {abs(top() - before):.0f} px on the toggle '{name}'")
        page.close()

    # Touch: a phone with real touch events through CDP.
    context = browser.new_context(viewport={"width": 393, "height": 852}, is_mobile=True, has_touch=True)
    page = context.new_page()
    page.goto(URL, wait_until="load", timeout=90000)
    cdp = context.new_cdp_session(page)

    def touch(kind: str, x: float = 0, y: float = 0) -> None:
        cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [] if kind == "touchEnd" else [{"x": x, "y": y}]})

    def finger(x: float, y: float, dy: float, steps: int = 20) -> None:
        touch("touchStart", x, y)
        for i in range(1, steps + 1):
            touch("touchMove", x, y + dy * i)
            page.wait_for_timeout(16)
        touch("touchEnd")
        page.wait_for_timeout(500)

    for fig_id in ids:
        where = f"{fig_id} touch"
        fig, slider = open_explainer(page, fig_id)
        page.evaluate("el => el.scrollIntoView({block: 'center'})", fig.locator(".xp-stage").element_handle())
        page.wait_for_timeout(600)
        box = fig.locator(".xp-handle").bounding_box()
        hx, hy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        y0, v0 = page.evaluate("scrollY"), slider.input_value()
        finger(hx, hy, 6)
        if slider.input_value() == v0:
            finger(hx, hy, -6)
        if slider.input_value() == v0:
            problems.append(f"{where}: a touch drag on the handle does not change the value")
        if page.evaluate("scrollY") != y0:
            problems.append(f"{where}: a touch drag on the handle scrolls the page")
        if page.evaluate("getSelection().toString()"):
            problems.append(f"{where}: a touch drag selects text")
        stage = fig.locator(".xp-stage").bounding_box()
        box = fig.locator(".xp-handle").bounding_box()
        hx = box["x"] + box["width"] / 2
        sx = stage["x"] + 30 if hx > stage["x"] + stage["width"] / 2 else stage["x"] + stage["width"] - 30
        y0 = page.evaluate("scrollY")
        finger(sx, stage["y"] + stage["height"] * 0.6, -8)
        if page.evaluate("scrollY") - y0 < 40:
            problems.append(f"{where}: a vertical swipe on the drawing away from the handle does not scroll the page")
    context.close()

    # Performance: phone size, CPU 4 times slower, motion on.
    page = browser.new_page(viewport={"width": 393, "height": 852}, reduced_motion="no-preference", has_touch=True)
    if perf:
        page.goto(URL, wait_until="load", timeout=90000)
    cdp = page.context.new_cdp_session(page)
    for fig_id in ids if perf else []:
        fig, _ = open_explainer(page, fig_id)
        page.wait_for_timeout(2500)  # Let the first-view hint finish.
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        start_frames = """() => {
          window.__long = []; window.__frames = []; window.__on = true;
          new PerformanceObserver(l => l.getEntries().forEach(e => window.__long.push(e.duration))).observe({type: 'longtask'});
          let last = performance.now();
          const tick = (now) => { window.__frames.push(now - last); last = now; if (window.__on) requestAnimationFrame(tick); };
          requestAnimationFrame(tick);
        }"""
        stop_frames = """() => {
          window.__on = false;
          const f = window.__frames.slice(3).sort((a, b) => a - b);
          return {long: Math.max(0, ...window.__long), p95: f[Math.floor(f.length * 0.95)] ?? 0, frames: f.length};
        }"""
        # Baseline: the same number of plain mouse moves (no button) over the drawing away from the handle.
        stage = fig.locator(".xp-stage").bounding_box()
        page.evaluate(start_frames)
        for i in range(1, 81):
            page.mouse.move(stage["x"] + 12, stage["y"] + 12 + (i % 40) * 2)
            page.wait_for_timeout(16)
        base = page.evaluate(stop_frames)
        page.evaluate(start_frames)
        if shots and trace:
            browser.start_tracing(page=page, path=str(shots / f"{fig_id}-trace.json"), screenshots=False)
        drag(page, fig, 40, 4, pause=16)
        drag(page, fig, 40, -4, pause=16)
        if shots and trace:
            browser.stop_tracing()
        stats = page.evaluate(stop_frames)
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
        floor = max(P95_FRAME_MS, base["p95"])
        print(f"perf {fig_id} at 4x CPU: drag longest task {stats['long']:.0f} ms, p95 frame {stats['p95']:.1f} ms "
              f"({stats['frames']} frames); page floor (mouse moves, no drag) p95 {base['p95']:.1f} ms, longest task {base['long']:.0f} ms")
        if stats["long"] > LONG_TASK_MS or stats["p95"] > floor + 0.5:
            problems.append(f"{fig_id}: slow drag at 4x CPU: longest task {stats['long']:.0f} ms, p95 frame {stats['p95']:.1f} ms (allowed {floor:.1f})")
    page.close()

    # Videos for review: scroll in (the hint plays), drag down and up, Shift steps, a mark, reset.
    if videos:
        videos.mkdir(parents=True, exist_ok=True)
        for name, size in (("phone", {"width": 393, "height": 852}), ("desktop", {"width": 1280, "height": 800})):
            for fig_id in ids:
                tmp = videos / "tmp"
                phone = name == "phone"
                context = browser.new_context(viewport=size, record_video_dir=str(tmp), record_video_size=size,
                                              reduced_motion="no-preference", has_touch=phone, is_mobile=phone)
                page = context.new_page()
                page.goto(URL, wait_until="load", timeout=90000)
                fig, slider = open_explainer(page, fig_id)
                page.evaluate("el => el.scrollIntoView({block: 'center'})", fig.locator(".xp-stage").element_handle())
                page.wait_for_timeout(2600)  # The first-view hint plays.
                if phone:
                    # A real finger drag on the handle, down then up: the page must stay still in the video.
                    tcdp = context.new_cdp_session(page)
                    for sign in (1, -1):
                        box = fig.locator(".xp-handle").bounding_box()
                        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                        tcdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
                        for i in range(1, 41):
                            tcdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y + sign * i * 4}]})
                            page.wait_for_timeout(30)
                        tcdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                        page.wait_for_timeout(600)
                else:
                    drag(page, fig, 30, 5, pause=30)
                    page.wait_for_timeout(500)
                    drag(page, fig, 30, -5, pause=30)
                    page.wait_for_timeout(500)
                slider.focus()
                for _ in range(3):
                    page.keyboard.press("Shift+ArrowRight")
                    page.wait_for_timeout(450)
                marks = fig.locator(".xp-mark")
                if marks.count():
                    marks.nth(marks.count() // 2).click()
                    page.wait_for_timeout(800)
                fig.locator(".xp-reset").click()
                page.wait_for_timeout(1000)
                video = page.video
                context.close()
                shutil.move(video.path(), videos / f"{fig_id}-{name}.webm")
                shutil.rmtree(tmp, ignore_errors=True)
        # PR media: the sinkhole explainer at phone width, light and dark: the level drops from 400 to 430 m while
        # the water flows (video), and stills at 400, 415 and 430 m.
        if "fig-a14-07" in ids:
            for scheme in ("light", "dark"):
                tmp = videos / "tmp"
                size = {"width": 393, "height": 852}
                context = browser.new_context(viewport=size, record_video_dir=str(tmp), record_video_size=size, color_scheme=scheme,
                                              reduced_motion="no-preference", has_touch=True, is_mobile=True)
                page = context.new_page()
                page.goto(URL, wait_until="load", timeout=90000)
                fig, slider = open_explainer(page, "fig-a14-07")
                page.evaluate("el => el.scrollIntoView({block: 'center'})", fig.locator(".xp-stage").element_handle())
                page.wait_for_timeout(2600)  # The first-view hint plays and ends.
                set_level = "(el, v) => { el.value = String(v); el.dispatchEvent(new Event('input')); el.dispatchEvent(new Event('change')); }"
                slider.evaluate(set_level, 400)
                page.wait_for_timeout(1500)
                for level in range(400, 431):
                    slider.evaluate(set_level, level)
                    page.wait_for_timeout(110)
                page.wait_for_timeout(2000)
                for level in (400, 415, 430):
                    slider.evaluate(set_level, level)
                    page.wait_for_timeout(700)
                    shot(page, fig.locator(".explorable"), videos / f"pr-sinkholes-phone-{scheme}-{level}.png")
                video = page.video
                context.close()
                shutil.move(video.path(), videos / f"pr-sinkholes-phone-{scheme}.webm")
                shutil.rmtree(tmp, ignore_errors=True)
    browser.close()
srv.shutdown()
print("\n".join(problems) or "explorables ok")
sys.exit(1 if problems else 0)
