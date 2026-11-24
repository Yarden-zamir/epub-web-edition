# /// script
# requires-python = ">=3.15"
# ///
"""Build site/translations/<lang>/<unit>.json from a working text file and check it against the source.

Usage: uv run translations/build.py LANG UNIT
Reads translations/<lang>/<unit>.txt: a line "## <element ID>" starts an item, the next
non-empty line is the translated inner HTML of that element.
Checks, and crashes on any failure:
- every element ID exists in epub-src-release/OEBPS/text/<unit>.xhtml;
- the translated markup has the same tags, in the same order, with the same attributes as the
  source, except that an img alt value may change (alt text is translated too).
"""

import json
import sys
from pathlib import Path

from extract import holders

ROOT = Path(__file__).resolve().parents[1]
TRANSLATOR = "machine translation (Claude), not reviewed"


def tags(html: str) -> list[str]:
    """Return every tag in the markup, with img alt values blanked."""
    out: list[str] = []
    i = 0
    while (start := html.find("<", i)) != -1:
        end = html.index(">", start)
        tag = html[start : end + 1]
        if tag.startswith("<img "):
            alt_start = tag.index(' alt="') + len(' alt="')
            alt_end = tag.index('"', alt_start)
            tag = tag[:alt_start] + tag[alt_end:]
        out.append(tag)
        i = end + 1
    return out


def parse(text: str) -> dict[str, str]:
    items: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line.removeprefix("## ").strip()
            if current in items:
                raise SystemExit(f"duplicate element ID {current}")
            items[current] = ""
        elif line.strip():
            if current is None or items[current]:
                raise SystemExit(f"text outside an item, or a second line for {current}: {line[:60]}")
            items[current] = line.strip()
    empty = [k for k, v in items.items() if not v]
    if empty:
        raise SystemExit(f"items without text: {empty}")
    return items


def main() -> None:
    lang, unit = sys.argv[1], sys.argv[2]
    src = holders(unit)
    items = parse((ROOT / "translations" / lang / f"{unit}.txt").read_text(encoding="utf-8"))
    for element_id, html in items.items():
        if element_id not in src:
            raise SystemExit(f"{element_id} is not an element of {unit}")
        want, got = tags(src[element_id]["inner"]), tags(html)
        if want != got:
            raise SystemExit(f"{element_id}: markup differs\n source: {want}\n target: {got}")
    out = ROOT / "site" / "translations" / lang / f"{unit}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = {"unit": unit, "lang": lang, "translator": TRANSLATOR, "items": items}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {len(items)} items")


if __name__ == "__main__":
    main()
