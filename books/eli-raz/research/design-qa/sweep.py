# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1"]
# ///
"""Design QA sweep: screenshots of every UI part at each width and color scheme, plus layout metrics."""
import functools, http.server, json, sys, threading, traceback
from pathlib import Path
from playwright.sync_api import sync_playwright

WEB = Path(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
ONLY = sys.argv[3].split(",") if len(sys.argv) > 3 else None
CHROME = Path.home() / ".cache/ms-playwright/chromium-1255/chrome-linux64/chrome"
AXE = Path.home() / "Github/epub-web-edition/main/.tools/axe/package/axe.min.js"
WIDTHS = {360: 760, 393: 852, 430: 932, 768: 1024, 1280: 860, 1600: 1000}

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(WEB)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_port}/"

METRICS_JS = r"""
() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !el.closest('[hidden],dialog:not([open]),[popover]:not(:popover-open),details:not([open]) > :not(summary)'); };
  const small = new Map();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const t = walker.currentNode; if (!t.textContent.trim()) continue;
    const el = t.parentElement; if (!el || !vis(el)) continue;
    if (el.closest('.leaflet-container, .facsimile, .visually-hidden, .skip-link, svg')) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 13) { const key = (el.className || el.tagName) + ' ' + fs + 'px'; small.set(key, (small.get(key) || 0) + 1); }
  }
  const taps = new Map();
  for (const el of document.querySelectorAll('a[href], button, summary, input')) {
    if (!vis(el) || el.closest('.facsimile, .leaflet-container, .leaflet-control-container')) continue;
    const r = el.getBoundingClientRect();
    if (r.height < 24 || r.width < 24) { const inline = getComputedStyle(el).display === 'inline' && el.closest('p, li, td, figcaption');
      if (inline) continue; const key = el.tagName + '.' + (el.className || '') + ` ${Math.round(r.width)}x${Math.round(r.height)}`; taps.set(key, (taps.get(key) || 0) + 1); }
  }
  const clipped = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('.leaflet-container, .facsimile, svg, .panel-list, .chart-area, .table-scroll')) continue;
    const s = getComputedStyle(el);
    if ((s.overflowX === 'hidden' || s.overflowX === 'clip' || s.textOverflow === 'ellipsis') && el.scrollWidth > el.clientWidth + 1 && vis(el))
      clipped.push((el.id ? '#' + el.id : el.tagName + '.' + el.className) + ` ${el.scrollWidth}>${el.clientWidth}`);
  }
  const wide = [];
  const vw = document.documentElement.clientWidth;
  for (const el of document.querySelectorAll('main *')) {
    if (el.closest('.leaflet-container, svg, .table-scroll, [style*="overflow"], .facsimile, figure.has-table, .text-table')) continue;
    const r = el.getBoundingClientRect(); if (!r.width) continue;
    if ((r.right > vw + 1 || r.left < -1) && vis(el)) wide.push((el.id ? '#' + el.id : el.tagName + '.' + el.className) + ` ${Math.round(r.left)}..${Math.round(r.right)}`);
  }
  return { overflow: document.documentElement.scrollWidth - vw, small: [...small], taps: [...taps], clipped: clipped.slice(0, 40), wide: wide.slice(0, 40) };
}
"""

def shot(page, name, el=None, full=False):
    path = OUT / f"{name}.jpg"
    try:
        if el is not None:  # Viewport shot with the element at the top: shows context and avoids element-shot offsets.
            el.evaluate("e => e.scrollIntoView({block: 'start'})"); page.wait_for_timeout(600)
            page.screenshot(path=path, type="jpeg", quality=72, animations="disabled", timeout=15000)
        else:
            page.screenshot(path=path, type="jpeg", quality=72, full_page=full, animations="disabled", timeout=15000)
    except Exception as e:
        print("shot failed", name, e)
    return path

def scroll_to(page, sel, block="start"):
    page.evaluate(f"(s) => {{ const e = document.querySelector(s); e.scrollIntoView({{block: '{block}'}}); }}", sel)
    page.wait_for_timeout(500)

def step(log, label, fn):
    try:
        fn()
    except Exception as e:
        log.append(f"{label}: {type(e).__name__}: {str(e)[:300]}")

def run(browser, w, mode):
    phone = w <= 430
    ctx = browser.new_context(viewport={"width": w, "height": WIDTHS[w]}, color_scheme=mode, has_touch=phone, is_mobile=phone,
                              device_scale_factor=2 if phone else 1)
    page = ctx.new_page()
    log, errors = [], []
    page.on("pageerror", lambda e: errors.append(str(e)[:200]))
    page.on("console", lambda m: m.type == "error" and errors.append("console: " + m.text[:200]))
    tag = f"{w}-{mode}"
    t0 = page.evaluate("performance.now()") if False else None
    page.goto(URL, wait_until="load"); page.add_style_tag(content="html{scroll-behavior:auto!important}"); page.wait_for_timeout(1800)
    shot(page, f"01-hero-{tag}")
    hero_h = page.evaluate("document.querySelector('.hero').offsetHeight")
    for frac, n in ((0.55, "a"), (0.92, "b"), (1.05, "c")):
        page.evaluate(f"window.scrollTo(0, {int(hero_h * frac)})"); page.wait_for_timeout(700)
        shot(page, f"02-header-{n}-{tag}")
    def contents():
        scroll_to(page, "#contents"); shot(page, f"03-contents-{tag}", page.locator("#contents"))
        dots = page.locator("#contents .place-dots").first
        dots.click(); page.wait_for_timeout(300)
        scroll_to(page, "#contents .place-pills:not([hidden])", "center"); shot(page, f"03b-place-pills-{tag}")
    step(log, "contents", contents)
    def places():
        scroll_to(page, "#places"); page.wait_for_timeout(3500)
        shot(page, f"04-places-{tag}", page.locator("#places"))
        page.locator("#places .leaflet-marker-icon").nth(0).click(); page.wait_for_timeout(1200)
        shot(page, f"04b-popup-{tag}")
        page.keyboard.press("Escape")
        page.evaluate("document.querySelector('.places-all').open = true"); page.wait_for_timeout(300)
        shot(page, f"04c-places-list-{tag}", page.locator(".places-all"))
        chip = page.locator(".map-chips button").first
        if chip.count():
            chip.click(); page.wait_for_timeout(2500); scroll_to(page, "#places-map", "center"); shot(page, f"04d-far-{tag}")
    step(log, "places", places)
    secs = ["#a02", "#s01", "#a06", "#a10", "#a01"] if not (w in (393, 1280) and mode == "light") else \
        page.evaluate("[...document.querySelectorAll('main section.chapter, main section.part, main section.frontispiece')].map(s => '#' + s.id)")
    for s in secs:
        step(log, s, lambda s=s: (scroll_to(page, s), page.wait_for_timeout(400), shot(page, f"05-open-{s[1:]}-{tag}")))
    for name, sel in (("poem", "#a07-poem1"), ("poem2", "#a24-poem1"), ("table", "#a06-t1"), ("datatable", "figure.has-table"),
                      ("chart", "figure.has-chart"), ("video", "figure.has-video"), ("withheld", ".withheld"),
                      ("edition-note", ".edition-note:not(.fx-mask-note)"), ("figure-photo", "#fig-a06-01"),
                      ("figure-inline", "#a10 figure.inline"), ("timeline-sec", ".timeline"), ("footer", "footer.footer")):
        def part(name=name, sel=sel):
            if not page.locator(sel).count(): log.append(f"{name}: none for {sel}"); return
            scroll_to(page, sel, "center"); page.wait_for_timeout(800)
            shot(page, f"06-{name}-{tag}", page.locator(sel).first)
        step(log, name, part)
    def footnote():
        ref = page.locator("a[role='doc-noteref']").first
        scroll_to(page, "a[role='doc-noteref']", "center"); ref.click(); page.wait_for_timeout(500); shot(page, f"07-footnote-{tag}")
        page.keyboard.press("Escape")
    step(log, "footnote", footnote)
    def term():
        scroll_to(page, "button.term", "center"); page.locator("button.term").first.click(); page.wait_for_timeout(500); shot(page, f"07b-term-{tag}")
        page.keyboard.press("Escape")
    step(log, "term", term)
    def heb_note():
        sel = "#a19 a[role='doc-noteref'], #a31 a[role='doc-noteref']"
        scroll_to(page, sel, "center"); page.locator(sel).first.click(); page.wait_for_timeout(500); shot(page, f"07c-footnote-he-{tag}")
        page.keyboard.press("Escape")
    step(log, "heb_note", heb_note)
    def toc():
        scroll_to(page, "#a14", "start"); page.wait_for_timeout(400)
        page.locator("[data-open='toc-dialog']").click(); page.wait_for_timeout(700); shot(page, f"08-toc-{tag}")
        page.locator("#toc-filter").fill("ים"); page.wait_for_timeout(400); shot(page, f"08b-toc-filter-{tag}")
        page.locator("#toc-filter").fill("zzz"); page.wait_for_timeout(300); shot(page, f"08c-toc-empty-{tag}")
        page.locator("#toc-filter").fill("")
        page.locator("#tab-timeline").click(); page.wait_for_timeout(500); shot(page, f"08d-timeline-{tag}")
        page.evaluate("document.querySelector('#toc-timeline').scrollTop = 1e6; document.querySelector('#toc-timeline .panel-list, #toc-timeline ol, #toc-timeline')?.scrollIntoView?.()")
        page.keyboard.press("End"); page.wait_for_timeout(300); shot(page, f"08e-timeline-end-{tag}")
        page.keyboard.press("Escape"); page.wait_for_timeout(300)
    step(log, "toc", toc)
    def search():
        page.locator("[data-open='search-dialog']").click(); page.wait_for_timeout(500); shot(page, f"09-search-empty-{tag}")
        page.locator("#search-input").fill("בולען"); page.wait_for_timeout(1500); shot(page, f"09b-search-{tag}")
        page.locator("#search-input").fill("עמ' 120"); page.wait_for_timeout(800); shot(page, f"09c-search-page-{tag}")
        page.locator("#search-input").fill("קשקשת"); page.wait_for_timeout(800); shot(page, f"09d-search-none-{tag}")
        page.keyboard.press("Escape"); page.keyboard.press("Escape"); page.wait_for_timeout(300)
    step(log, "search", search)
    def send():
        page.evaluate("window.scrollTo(0,0)"); page.wait_for_timeout(500)
        page.locator("#hero-download .split-more").click(); page.wait_for_timeout(500); shot(page, f"10-send-menu-{tag}")
        page.keyboard.press("Escape")
    step(log, "send", send)
    def viewer():
        scroll_to(page, "#fig-a06-01", "center"); page.locator("#fig-a06-01 img").click(); page.wait_for_timeout(1200); shot(page, f"11-viewer-{tag}")
        page.keyboard.press("Escape"); page.wait_for_timeout(300)
        scroll_to(page, "#a10 figure.inline", "center"); page.locator("#a10 figure.inline img").first.click(); page.wait_for_timeout(1200); shot(page, f"11b-viewer-inline-{tag}")
        page.keyboard.press("Escape")
    step(log, "viewer", viewer)
    page.evaluate("window.scrollTo(0,0)"); page.wait_for_timeout(300)
    metrics = page.evaluate(METRICS_JS)
    if not phone:
        def focus():
            page.goto(URL, wait_until="load"); page.wait_for_timeout(800)
            for i in range(1, 9):
                page.keyboard.press("Tab"); page.wait_for_timeout(150)
                if i in (1, 2, 3, 5, 7): shot(page, f"12-focus-{i}-{tag}")
        step(log, "focus", focus)
    ctx.close()
    return {"tag": tag, "errors": errors, "log": log, **metrics}

report = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=str(CHROME))
    for w in WIDTHS:
        for mode in ("light", "dark"):
            if ONLY and f"{w}-{mode}" not in ONLY: continue
            try:
                r = run(browser, w, mode)
            except Exception:
                r = {"tag": f"{w}-{mode}", "fatal": traceback.format_exc()[-800:]}
            report.append(r); print(json.dumps(r, ensure_ascii=False)[:1500], flush=True)
    browser.close()
(OUT / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
srv.shutdown()
