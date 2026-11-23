# /// script
# requires-python = ">=3.13"
# dependencies = ["playwright==1.64.1"]
# ///
"""Verify the EPUB, the web edition, the inventory and canonical-EPUB propagation.

Usage: uv run tools/verify.py
Writes dist/verify/report.json and screenshots. Exits 1 when a check fails.
Needs .tools/ (EPUBCheck, a Java runtime, axe-core) and a cached Playwright Chromium.
"""

import csv
import functools
import hashlib
import http.server
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_epub  # noqa: E402
import build_web  # noqa: E402

TOOLS = ROOT / ".tools"
DIST = ROOT / "dist"
OUT = DIST / "verify"
EPUB = DIST / "book.epub"
WEB = DIST / "web"
# Limit: Playwright 1.64.1 expects Chromium build 1248. The cache holds 1255, which works over CDP.
# Revisit when Playwright is upgraded or when a launch fails.
CHROMIUM = Path.home() / ".cache/ms-playwright/chromium-1255/chrome-linux64/chrome"
WEB_WIDTHS = (360, 768, 1280)
EPUB_WIDTHS = (320, 600, 1024)  # Phone reader app, 6-inch e-reader, tablet.
INITIAL_LOAD_BUDGET = 1_500_000  # Bytes before lazy images load.
PAGE_STATUSES = {"verified", "pending", "ambiguous"}


@dataclass
class Result:
    name: str
    ok: bool
    detail: object


results: list[Result] = []


def record(name: str, ok: bool, detail: object = None) -> None:
    results.append(Result(name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail and not ok else ""))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(folder: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(folder.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(folder).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


# ---------- EPUB ----------

def check_epubcheck() -> None:
    java = next(TOOLS.glob("jdk-*/bin/java"))
    report = OUT / "epubcheck.json"
    proc = subprocess.run(
        [java, "-jar", TOOLS / "epubcheck-5.4.0/epubcheck.jar", EPUB, "--json", report],
        capture_output=True, text=True,
    )
    messages = json.loads(report.read_text())["messages"]
    bad = [f"{m['severity']} {m['ID']}: {m['message']}" for m in messages if m["severity"] in ("FATAL", "ERROR", "WARNING")]
    record("epubcheck 5.4.0: no fatals, errors or warnings", proc.returncode == 0 and not bad, bad)


def check_reproducible() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        build_epub.build(ROOT / "epub-src", t / "a.epub")
        record("EPUB build is byte-reproducible", sha(t / "a.epub") == sha(EPUB))
        build_web.build(EPUB, t / "w1")
        build_web.build(EPUB, t / "w2")
        same = tree_hash(t / "w1") == tree_hash(t / "w2") == tree_hash(WEB)
        record("web build is byte-reproducible from the EPUB", same)


def epub_texts() -> dict[str, str]:
    """ID -> normalized text for every element with an ID in the EPUB spine."""
    with zipfile.ZipFile(EPUB) as z:
        book = build_web.read_book(z)
        texts: dict[str, str] = {}
        for item in book.spine:
            body = ET.fromstring(z.read(item.path)).find(f"{{{build_web.XHTML}}}body")
            assert body is not None
            for el in body.iter():
                if (el_id := el.attrib.get("id")) is not None:
                    texts[el_id] = build_web.clean_text(el)
        return texts


def check_inventory(texts: dict[str, str]) -> None:
    source = json.loads((ROOT / "inventory/source.json").read_text())
    pages = list(csv.DictReader((ROOT / "inventory/pages.csv").open(encoding="utf-8")))
    numbers = [int(p["page"]) for p in pages]
    record("inventory lists every source page once, in order", numbers == list(range(1, source["pages"] + 1)),
           {"expected": source["pages"], "listed": len(numbers)})
    missing_markers = [n for n in numbers if f"pg-{n}" not in texts]
    record("EPUB has a page marker for every source page", not missing_markers, missing_markers)
    unknown = [(p["page"], i) for p in pages for i in p["target_ids"].split() if i not in texts]
    record("inventory target IDs exist in the EPUB", not unknown, unknown)
    bad_status = [p["page"] for p in pages if p["status"] not in PAGE_STATUSES]
    record("inventory page statuses are valid", not bad_status, bad_status)

    assets = list(csv.DictReader((ROOT / "inventory/assets.csv").open(encoding="utf-8")))
    with zipfile.ZipFile(EPUB) as z:
        book = build_web.read_book(z)
        images = {i.path for i in book.items.values() if i.media_type.startswith("image/")}
        listed = {a["epub_path"] for a in assets}
        record("every EPUB image has a provenance row", images == listed,
               {"unlisted": sorted(images - listed), "absent": sorted(listed - images)})
        drift = [a["asset_id"] for a in assets
                 if hashlib.sha256(z.read(a["epub_path"])).hexdigest() != a["epub_sha256"]
                 or sha(ROOT / a["original_path"]) != a["original_sha256"]]
        record("EPUB images and originals match recorded checksums", not drift, drift)
    credit_mismatch = []
    with zipfile.ZipFile(EPUB) as z:
        for item in build_web.read_book(z).spine:
            for fig in ET.fromstring(z.read(item.path)).iter(f"{{{build_web.XHTML}}}figure"):
                credit = next((c for c in fig.iter() if c.attrib.get("class") == "credit"), None)
                row = next((a for a in assets if a["asset_id"] == fig.attrib.get("id")), None)
                printed = build_web.clean_text(credit) if credit is not None else ""
                if row is None or row["credit_as_printed"] != printed:
                    credit_mismatch.append(fig.attrib.get("id"))
    record("figure credits in the EPUB match the inventory as printed", not credit_mismatch, credit_mismatch)

    issues = list(csv.DictReader((ROOT / "inventory/issues.csv").open(encoding="utf-8")))
    open_issues = [i["id"] for i in issues if i["status"] not in ("accepted", "resolved")]
    pending = [p["page"] for p in pages if p["status"] != "verified"]
    complete = not open_issues and not pending and not source["synthetic"]
    results.append(Result("whole-book reconciliation complete", complete,
                          {"synthetic": source["synthetic"], "pending_pages": pending, "open_issues": open_issues}))
    print(f"{'DONE' if complete else 'OPEN'}  whole-book reconciliation (synthetic={source['synthetic']}, pending={len(pending)}, open issues={len(open_issues)})")


def check_epub_render(browser: Browser) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(EPUB) as z:
            z.extractall(tmp)
            spine = build_web.read_book(z).spine
        overflow: list[str] = []
        for width in EPUB_WIDTHS:
            page = browser.new_page(viewport={"width": width, "height": 900})
            for item in spine:
                page.goto((Path(tmp) / item.path).as_uri())
                page.wait_for_load_state("load")
                if page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"):
                    overflow.append(f"{item.path}@{width}")
                if item.path.endswith(("ch-01.xhtml", "ch-02.xhtml")):
                    page.screenshot(path=OUT / f"epub-{Path(item.path).stem}-{width}.png", full_page=True)
            page.close()
        record(f"EPUB documents reflow without horizontal scroll at {EPUB_WIDTHS}", not overflow, overflow)


# ---------- Web ----------

def serve(folder: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(folder)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


def check_parity(browser: Browser, url: str, texts: dict[str, str]) -> None:
    ctx = browser.new_context(java_script_enabled=False)
    page = ctx.new_page()
    page.goto(url)
    web: dict[str, str] = page.evaluate(
        """() => Object.fromEntries([...document.querySelectorAll('#reading [id]')]
             .map(e => [e.id, e.textContent.split(/\\s+/).filter(Boolean).join(' ')]))"""
    )
    ctx.close()
    web.pop("top", None)
    missing = sorted(texts.keys() - web.keys())
    extra = sorted(web.keys() - texts.keys())
    changed = sorted(i for i in texts.keys() & web.keys() if texts[i] != web[i])
    record("web text equals EPUB text for every ID (no JavaScript)", not (missing or extra or changed),
           {"missing": missing, "extra": extra, "changed": changed})


def axe(page: Page) -> list[dict[str, object]]:
    page.add_script_tag(path=str(TOOLS / "axe/package/axe.min.js"))
    result = page.evaluate("axe.run(document, {resultTypes: ['violations']})")
    return [{"id": v["id"], "impact": v["impact"], "nodes": len(v["nodes"])} for v in result["violations"]]


def check_web(browser: Browser, url: str) -> None:
    errors: list[str] = []
    overflow: list[str] = []
    violations: dict[str, list[dict[str, object]]] = {}
    for scheme in ("light", "dark"):
        for width in WEB_WIDTHS:
            ctx = browser.new_context(viewport={"width": width, "height": 860}, color_scheme=scheme)
            page = ctx.new_page()
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url)
            page.wait_for_load_state("networkidle")
            if page.evaluate("document.documentElement.scrollWidth > innerWidth"):
                overflow.append(f"{scheme}@{width}")
            if v := axe(page):
                violations[f"{scheme}@{width}"] = v
            page.screenshot(path=OUT / f"web-{scheme}-{width}.png")
            page.goto(url + "#fig-01-01")
            page.wait_for_timeout(300)
            page.screenshot(path=OUT / f"web-{scheme}-{width}-figure.png")
            ctx.close()
    record(f"web: no horizontal scroll at {WEB_WIDTHS} in light and dark", not overflow, overflow)
    record("web: axe-core 4.14.0 finds no violations", not violations, violations)
    record("web: no console errors", not errors, errors)


def check_interaction(browser: Browser, url: str) -> None:
    ctx = browser.new_context(viewport={"width": 1280, "height": 860})
    page = ctx.new_page()
    page.goto(url)
    page.keyboard.press("Tab")
    record("keyboard: first Tab focuses the skip link", page.evaluate("document.activeElement.className") == "skip-link")
    page.keyboard.press("Enter")
    record("keyboard: skip link moves focus to the text", page.evaluate("document.activeElement.id") == "reading")

    page.keyboard.press("/")
    page.keyboard.type("טבלה")
    page.wait_for_selector("#search-results a")
    first = page.get_attribute("#search-results a", "href")
    page.keyboard.press("Enter")
    page.wait_for_timeout(200)
    record("search: '/' opens search and Enter goes to the first hit",
           first is not None and page.evaluate("location.hash") == first and not page.is_visible("#search-dialog"),
           {"first": first, "hash": page.evaluate("location.hash")})

    page.click("#fig-01-01 img")
    src = page.get_attribute("#viewer-img", "src") or ""
    open_ = page.is_visible("#figure-dialog")
    page.keyboard.press("Escape")
    record("figure viewer opens the site-only original and closes with Escape",
           open_ and src.endswith("originals/fig-01-01.png") and not page.is_visible("#figure-dialog"), src)

    page.click("[data-open='toc-dialog']")
    page.click("#toc-dialog a[href='#ch-02']")
    page.wait_for_timeout(200)
    top = page.evaluate("document.getElementById('ch-02').getBoundingClientRect().top")
    record("contents panel link goes to the chapter", page.evaluate("location.hash") == "#ch-02" and 0 <= top < 200, top)
    ctx.close()

    ctx = browser.new_context(viewport={"width": 360, "height": 740})
    page = ctx.new_page()
    page.goto(url + "#fig-02-01")
    page.wait_for_timeout(300)
    top = page.evaluate("document.getElementById('fig-02-01').getBoundingClientRect().top")
    record("deep link opens at the figure", 0 <= top < 200, top)
    label = page.text_content("#current-page")
    record("current printed page follows the source PDF page markers", label == "עמוד 7", label)

    page.goto(url + "#p-02-002")
    page.wait_for_timeout(300)
    page.mouse.wheel(0, 10)
    page.wait_for_timeout(300)
    saved = page.evaluate("localStorage.getItem('position:' + document.documentElement.dataset.bookId)")
    page.goto(url)
    page.wait_for_timeout(300)
    record("reading position: return visit offers to continue at the saved place",
           saved is not None and page.is_visible("#resume") and "עמוד" in (page.text_content("#resume-go") or ""),
           {"saved": saved, "label": page.text_content("#resume-go")})
    ctx.close()


def check_performance(browser: Browser, url: str) -> None:
    ctx = browser.new_context(viewport={"width": 360, "height": 740})
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_load_state("networkidle")
    perf = page.evaluate(
        """() => {
          const nav = performance.getEntriesByType('navigation')[0];
          const res = performance.getEntriesByType('resource');
          return {bytes: nav.transferSize + res.reduce((s, r) => s + r.transferSize, 0),
                  requests: res.length + 1, dcl_ms: Math.round(nav.domContentLoadedEventEnd),
                  load_ms: Math.round(nav.loadEventEnd),
                  cls: performance.getEntriesByType('layout-shift').reduce((s, e) => s + e.value, 0)}
        }"""
    )
    ctx.close()
    record(f"performance: initial load under {INITIAL_LOAD_BUDGET} bytes", perf["bytes"] < INITIAL_LOAD_BUDGET, perf)
    results[-1].detail = perf


# ---------- Canonical EPUB propagation ----------

def check_propagation() -> None:
    marker = "שינוי פרטי לבדיקת הבנייה."  # "Private change for a build check."
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        src = t / "epub-src"
        shutil.copytree(ROOT / "epub-src", src)
        chapter = src / "OEBPS/text/ch-01.xhtml"
        before = chapter.read_text(encoding="utf-8")
        anchor = '<p id="p-01-004">'
        if before.count(anchor) != 1:
            raise SystemExit("propagation check: anchor paragraph p-01-004 not found once")
        chapter.write_text(before.replace(anchor, anchor + marker + " "), encoding="utf-8")
        new_sha = build_epub.build(src, t / "changed.epub")
        report = build_web.build(t / "changed.epub", t / "web")
        page = (t / "web/index.html").read_text(encoding="utf-8")
        search = json.loads((t / "web/search.json").read_text(encoding="utf-8"))
        hit = next((e for e in search if e["id"] == "p-01-004"), None)
        ok = (
            marker in page
            and hit is not None and marker in hit["text"]
            and report["epub_sha256"] == new_sha != sha(EPUB)
            and marker not in (WEB / "index.html").read_text(encoding="utf-8")
        )
        record("a change to EPUB content appears in the next web build (page, search, build record)", ok,
               {"new_epub_sha256": new_sha, "canonical_epub_sha256": sha(EPUB)})


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    print(build_epub.build(ROOT / "epub-src", EPUB))
    build_web.build(EPUB, WEB)
    texts = epub_texts()
    check_epubcheck()
    check_reproducible()
    check_inventory(texts)
    check_propagation()
    server, url = serve(WEB)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=str(CHROMIUM))
            check_epub_render(browser)
            check_parity(browser, url, texts)
            check_web(browser, url)
            check_interaction(browser, url)
            check_performance(browser, url)
            browser.close()
    finally:
        server.shutdown()
    (OUT / "report.json").write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    failed = [r.name for r in results if not r.ok and r.name != "whole-book reconciliation complete"]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks pass. Report: {OUT / 'report.json'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
