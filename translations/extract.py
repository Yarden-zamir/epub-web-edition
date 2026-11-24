# /// script
# requires-python = ">=3.15"
# ///
"""List translatable elements of release chapters with their exact inner HTML.

Usage: uv run translations/extract.py UNIT [--lang en|he]
Prints JSON {element ID: {"tag", "lang", "inner"}} for every element with an id that is
a heading, p, figure or footnote aside (direct text holders). --lang keeps only elements
whose own lang attribute (or the unit default "he") matches.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TEXT = Path(__file__).resolve().parents[1] / "epub-src-release" / "OEBPS" / "text"
XHTML = "{http://www.w3.org/1999/xhtml}"
HOLDERS = {"h1", "h2", "h3", "h4", "p", "figure", "aside", "li", "td", "th", "blockquote"}


def inner_html(raw: str, element_id: str) -> str:
    """Return the exact source markup between the start and end tag of the element with this id."""
    marker = f' id="{element_id}"'
    pos = raw.index(marker)
    start = raw.rindex("<", 0, pos)
    tag = raw[start + 1 : raw.index(" ", start)]
    open_end = raw.index(">", pos) + 1
    if raw[open_end - 2] == "/":
        return ""
    depth, i = 1, open_end
    while depth:
        nxt_open = raw.find(f"<{tag}", i)
        nxt_close = raw.index(f"</{tag}>", i)
        # Count only real start tags of the same name, not prefixes such as <p vs <path.
        if nxt_open != -1 and nxt_open < nxt_close and raw[nxt_open + len(tag) + 1] in " >":
            depth += 1
            i = nxt_open + 1
        else:
            depth -= 1
            i = nxt_close + len(tag) + 3
    return raw[open_end : i - len(tag) - 3]


def holders(unit: str) -> dict[str, dict[str, str]]:
    path = TEXT / f"{unit}.xhtml"
    raw = path.read_text(encoding="utf-8")
    root = ET.fromstring(raw)
    out: dict[str, dict[str, str]] = {}
    for el in root.iter():
        tag = el.tag.removeprefix(XHTML)
        element_id = el.get("id")
        if element_id is None or tag not in HOLDERS:
            continue
        lang = el.get("lang") or el.get("{http://www.w3.org/XML/1998/namespace}lang") or "he"
        out[element_id] = {"tag": tag, "lang": lang, "inner": inner_html(raw, element_id)}
    return out


def main() -> None:
    unit = sys.argv[1]
    lang = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else None
    items = {k: v for k, v in holders(unit).items() if lang is None or v["lang"] == lang}
    print(json.dumps(items, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
