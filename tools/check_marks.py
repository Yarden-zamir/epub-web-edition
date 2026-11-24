# /// script
# requires-python = ">=3.15"
# dependencies = ["pymupdf==1.28.2", "python-bidi==0.6.12", "fonttools==4.68.0"]
# ///
"""Check combining marks (Hebrew points) in the EPUB text.

Usage: uv run tools/check_marks.py CONTENT_DIR [EPUB_SRC_DIR]

Fails on:
- a mark that sat over no letter in print (issues.csv rows of type "mark", written by ingest_pdf.py, which
  places each mark by the ink of its glyph);
- a mark that does not follow a Hebrew letter or another mark;
- the same mark twice on one letter;
- marks out of the standard order: shin and sin dots, dagesh, vowels, other marks.
EPUB_SRC_DIR defaults to CONTENT_DIR/epub-src; its inventory folder is the sibling inventory one.
"""

import csv
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest_pdf import is_hebrew, mark_rank  # noqa: E402


def problems(text: str) -> list[str]:
    found = []
    letter, marks = "", ""
    for i, c in enumerate(text + " "):
        if unicodedata.combining(c):
            if not letter:
                found.append(f"mark U+{ord(c):04X} after {text[i - 1:i]!r}, not after a letter")
            marks += c
            continue
        if marks:
            if len(set(marks)) != len(marks):
                found.append(f"a mark twice on {letter}{marks}")
            if list(marks) != sorted(marks, key=mark_rank):
                found.append(f"marks out of order on {letter}{marks}")
        letter, marks = (c if is_hebrew(c) and c.isalpha() else ""), ""
    return found


def main() -> None:
    content = Path(sys.argv[1])
    src = Path(sys.argv[2]) if len(sys.argv) > 2 else content / "epub-src"
    inventory = content / ("inventory-release" if src.name.endswith("release") else "inventory")
    with (inventory / "issues.csv").open(encoding="utf-8", newline="") as f:
        unplaced = [r for r in csv.DictReader(f) if r["type"] == "mark"]
    for r in unplaced:
        print(f"PDF page {r['page']}: {r['description']}")
    total = len(unplaced)
    marks = 0
    files = sorted((src / "OEBPS" / "text").glob("*.xhtml"))
    if not files:
        raise SystemExit(f"{src}: no OEBPS/text/*.xhtml")
    for f in files:
        for el in ET.parse(f).getroot().iter():
            for part in (el.text or "", el.tail or ""):
                marks += sum(unicodedata.combining(c) > 0 for c in part)
                for p in problems(part):
                    total += 1
                    print(f"{f.stem}: {p} | {part.strip()[:60]}")
    print(f"marks in EPUB text: {marks} | problems: {total}")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
