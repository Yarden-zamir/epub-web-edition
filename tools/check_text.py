# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Find direction defects in the EPUB text: reversed Hebrew words and reversed or unbalanced brackets.

Usage: uv run tools/check_text.py CONTENT_DIR [EPUB_SRC_DIR]
EPUB_SRC_DIR defaults to CONTENT_DIR/epub-src. Paragraphs that contain a book.toml [[print_quirk]] text
are skipped: their bracket defect is in the print. A quirk that matches no paragraph is an error.
Exits 1 when it finds a defect. Prints each one with its element ID.
"""

import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

XHTML = "{http://www.w3.org/1999/xhtml}"
FINALS = set("ךםןףץ")  # Hebrew final letters. A word never starts with one, so a word that does is reversed.
BLOCKS = {f"{XHTML}{t}" for t in ("p", "h2", "li", "figcaption", "aside")}


def is_label(text: str, i: int, depth: int) -> bool:
    """The ")" at i closes a list label such as "א)" or "1)": outside brackets, one letter or digit after a space or at the start."""
    return depth == 0 and i >= 1 and (text[i - 1].isdigit() or "א" <= text[i - 1] <= "ת") and (i == 1 or text[i - 2] == " ")


def defects(text: str) -> list[str]:
    found = []
    for word in text.split():
        letters = "".join(c for c in word if "א" <= c <= "ת")
        if len(letters) >= 2 and letters[0] in FINALS:
            found.append(f"reversed Hebrew word {word!r}")
    depth = 0
    for i, c in enumerate(text):
        if c == ")" and is_label(text, i, depth):
            continue
        depth += {"(": 1, ")": -1}.get(c, 0)
        if depth < 0:
            found.append("a ')' comes before its '('")
            break
    if depth > 0:
        found.append("unbalanced '('")
    return found


def main() -> None:
    content = Path(sys.argv[1])
    root = (Path(sys.argv[2]) if len(sys.argv) > 2 else content / "epub-src") / "OEBPS" / "text"
    quirks = [q["contains"] for q in tomllib.loads((content / "book.toml").read_text(encoding="utf-8")).get("print_quirk", [])]
    used: set[str] = set()
    total = 0
    for f in sorted(root.glob("*.xhtml")):
        for el in ET.parse(f).getroot().iter():
            if el.tag not in BLOCKS or not el.attrib.get("id"):
                continue
            text = " ".join("".join(el.itertext()).split())
            if hits := [q for q in quirks if q in text]:
                used.update(hits)
                continue
            for d in defects(text):
                total += 1
                print(f"{f.stem}#{el.attrib['id']}: {d} | {text[:90]}")
    if stale := [q for q in quirks if q not in used]:
        raise SystemExit(f"book.toml [[print_quirk]] entries match no paragraph: {stale}")
    print(f"text defects: {total} | print quirks skipped: {len(used)}")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
