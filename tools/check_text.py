"""Find direction defects in the EPUB text: reversed Hebrew words and reversed or unbalanced brackets.

Usage: python3 tools/check_text.py CONTENT_DIR
Exits 1 when it finds a defect. Prints each one with its element ID.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

XHTML = "{http://www.w3.org/1999/xhtml}"
FINALS = set("ךםןףץ")  # Hebrew final letters. A word never starts with one, so a word that does is reversed.
BLOCKS = {f"{XHTML}{t}" for t in ("p", "h2", "li", "figcaption", "aside")}


def defects(text: str) -> list[str]:
    found = []
    for word in text.split():
        letters = "".join(c for c in word if "א" <= c <= "ת")
        if len(letters) >= 2 and letters[0] in FINALS:
            found.append(f"reversed Hebrew word {word!r}")
    depth = 0
    # A list label such as "א)" or "1)" opens an item; it is not a bracket pair.
    if len(text) > 1 and text[1] == ")" and (text[0].isdigit() or "\u05d0" <= text[0] <= "\u05ea"):
        text = text[2:]
    for c in text:
        depth += {"(": 1, ")": -1}.get(c, 0)
        if depth < 0:
            found.append("a ')' comes before its '('")
            break
    if depth > 0:
        found.append("unbalanced '('")
    return found


def main() -> None:
    root = Path(sys.argv[1]) / "epub-src" / "OEBPS" / "text"
    total = 0
    for f in sorted(root.glob("*.xhtml")):
        for el in ET.parse(f).getroot().iter():
            if el.tag not in BLOCKS or not el.attrib.get("id"):
                continue
            text = " ".join("".join(el.itertext()).split())
            for d in defects(text):
                total += 1
                print(f"{f.stem}#{el.attrib['id']}: {d} | {text[:90]}")
    print(f"text defects: {total}")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
