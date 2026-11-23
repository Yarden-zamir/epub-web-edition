# /// script
# requires-python = ">=3.13"
# dependencies = ["pymupdf==1.28.2"]
# ///
"""Check that the EPUB source keeps every word of the PDF, page by page.

Usage: uv run tools/check_coverage.py CONTENT_DIR [MIN_SHARE]

Compares letters and digits as multisets (order-free), outside the running-head zone.
Punctuation and whitespace are ignored, so word splitting (maqaf, gershayim) does not count.
The check finds dropped or extra text, not ordering. Writes CONTENT_DIR/inventory/coverage.csv and prints pages below MIN_SHARE.
"""

import collections
import csv
import sys
import tomllib
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import pymupdf

XHTML = "{http://www.w3.org/1999/xhtml}"
OPS = "{http://www.idpf.org/2007/ops}"


def norm_words(text: str) -> list[str]:
    """Letters and digits of the text, one item per character."""
    return [c for c in unicodedata.normalize("NFC", text) if c.isalnum()]


def epub_words_by_page(text_dir: Path) -> dict[int, list[str]]:
    """Words per PDF page, split at the page markers (id="pg-N") in document order."""
    pages: dict[int, list[str]] = collections.defaultdict(list)
    for f in sorted(text_dir.glob("*.xhtml")):
        body = ET.parse(f).getroot().find(f"{XHTML}body")
        assert body is not None, f
        current = 0
        for event_el in body.iter():
            el_id = event_el.attrib.get("id", "")
            if event_el.attrib.get(f"{OPS}type") == "pagebreak" and el_id.startswith("pg-"):
                current = int(el_id[3:])
            if event_el.text:
                pages[current].extend(norm_words(event_el.text))
            if event_el.tail:
                pages[current].extend(norm_words(event_el.tail))
    return pages


def main() -> None:
    content = Path(sys.argv[1]).resolve()
    min_share = float(sys.argv[2]) if len(sys.argv) > 2 else 0.98
    cfg = tomllib.loads((content / "book.toml").read_text(encoding="utf-8"))
    doc = pymupdf.open(Path(cfg["pdf"]).expanduser())
    header = float(cfg["layout"]["header_max_y"])
    char_map = cfg.get("char_map", {})
    epub = epub_words_by_page(content / "epub-src" / "OEBPS" / "text")
    rows, low = [], []
    for page in doc:
        h = page.rect.height
        heads = cfg["layout"]["running_head_fonts"]
        omits = [o["contains"] for o in cfg.get("omit", []) if o["page"] == page.number + 1]
        parts = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line["spans"])
                main = max(line["spans"], key=lambda s: len(s["text"]))
                font, size = main["font"].split("+")[-1], main["size"]
                is_head = line["bbox"][3] / h < header and any(n in font and abs(size - float(z)) < 0.3 for n, z in heads)
                if not is_head and not any(o in text for o in omits):
                    parts.append(text)
        raw = " ".join(parts)
        for src, dst in char_map.items():
            raw = raw.replace(src, dst)
        want = collections.Counter(norm_words(raw))
        got = collections.Counter(epub.get(page.number + 1, []))
        missing = want - got
        share = 1.0 if not want else 1 - sum(missing.values()) / sum(want.values())
        extra = sum((got - want).values())
        rows.append([page.number + 1, sum(want.values()), sum(got.values()), sum(missing.values()), extra, f"{share:.3f}"])
        if share < min_share:
            low.append((page.number + 1, round(share, 3), sum(missing.values()), sum(want.values())))
    with (content / "inventory" / "coverage.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["page", "pdf_letters", "epub_letters", "missing", "extra", "share"])
        w.writerows(rows)
    total = sum(r[1] for r in rows)
    missing_total = sum(r[3] for r in rows)
    extra_total = sum(r[4] for r in rows)
    print(f"pages {len(rows)} | PDF letters {total} | missing {missing_total} ({missing_total / max(total, 1):.2%})"
          f" | extra in EPUB {extra_total} | pages below {min_share}: {len(low)}")
    for r in rows:
        if r[4] > 0:
            print("  extra letters on page", r[0], ":", r[4])
    for row in low[:40]:
        print("  page, share, missing, pdf letters:", row)


if __name__ == "__main__":
    main()
