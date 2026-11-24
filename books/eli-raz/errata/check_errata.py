# /// script
# requires-python = ">=3.15"
# ///
"""Check errata/proposed.toml against the release EPUB source.

For each [[correction]]: the element exists, `find` occurs exactly once in its text,
and `page` is the PDF page where `find` starts. Exit 1 on any mismatch.
A correction that the build already applied counts as its printed text: the build writes
<span class="edition-correction" data-printed="find">replace</span>, and this check reads data-printed
(and requires the span text to equal `replace`).
With --pages, print the computed page for each correction instead of failing on it.
Run from the content repo root: uv run errata/check_errata.py [--pages]
"""
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

TEXT_DIR = Path("epub-src-release/OEBPS/text")
PAGEBREAK = "{http://www.idpf.org/2007/ops}type"


def element_runs(eid: str) -> list[tuple[int, str]]:
    """Return (page, text) runs of the element, split at page breaks."""
    for f in sorted(TEXT_DIR.glob("*.xhtml")):
        root = ET.parse(f).getroot()
        page = 0
        for el in root.iter():
            if el.get(PAGEBREAK) == "pagebreak":
                page = int(el.get("id").removeprefix("pg-"))
            if el.get("id") == eid:
                runs = [(page, "")]
                walk(el, runs)
                return runs
    raise SystemExit(f"element not found: {eid}")


APPLIED: dict[str, str] = {}  # Printed text -> corrected text, for corrections the build applied.


def walk(el, runs):
    if el.get(PAGEBREAK) == "pagebreak":
        runs.append((int(el.get("id").removeprefix("pg-")), ""))
    elif "edition-correction" in (el.get("class") or "").split() and el.get("data-printed") is not None:
        printed = el.get("data-printed")
        APPLIED[printed] = "".join(el.itertext())
        runs[-1] = (runs[-1][0], runs[-1][1] + printed)
    else:
        runs[-1] = (runs[-1][0], runs[-1][1] + (el.text or ""))
        for c in el:
            walk(c, runs)
    if el.tail is not None:
        runs[-1] = (runs[-1][0], runs[-1][1] + el.tail)


def main() -> int:
    show = "--pages" in sys.argv
    data = tomllib.loads(Path("errata/proposed.toml").read_text(encoding="utf-8"))
    errors = 0
    for c in data["correction"]:
        runs = element_runs(c["element"])
        text = "".join(t for _, t in runs)
        n = text.count(c["find"])
        if c["find"] in APPLIED and APPLIED[c["find"]] != c["replace"]:
            print(f"FAIL {c['element']}: applied as {APPLIED[c['find']]!r}, toml says {c['replace']!r}")
            errors += 1
            continue
        if n != 1:
            print(f"FAIL {c['element']}: find occurs {n} times: {c['find']!r}")
            errors += 1
            continue
        start = text.find(c["find"])
        pos, page = 0, None
        for p, t in runs:
            if pos <= start < pos + len(t):
                page = p
            pos += len(t)
        if show:
            print(f"{c['element']}\tpage {page}\t{c['find']}")
        elif page != c["page"]:
            print(f"FAIL {c['element']}: page {c['page']} in toml, find starts on page {page}")
            errors += 1
    applied = sum(c["find"] in APPLIED for c in data["correction"])
    print(f"{len(data['correction'])} corrections, {applied} applied in the release text, {errors} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
