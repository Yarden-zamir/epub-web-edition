# /// script
# requires-python = ">=3.15"
# dependencies = ["pymupdf==1.28.2", "python-bidi==0.6.12"]
# ///
"""Check reading order line by line: the logical text, displayed with the Unicode bidi algorithm,
must show the characters in the same left-to-right order as the printed line.

Usage: uv run tools/check_bidi.py CONTENT_DIR [--show N]

Brackets compare as one symbol, because Hebrew and Latin fonts store them differently
(tools/check_text.py checks bracket pairs). Spaces are ignored.
book.toml [[bidi_reviewed]] lists lines that differ on purpose (page and a text the line contains). They are
counted, not failed. An entry that matches no differing line is an error, so the list stays true.
"""

import sys
import unicodedata
from pathlib import Path

from bidi import get_display

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest_pdf  # noqa: E402


def key(s: str) -> str:
    """Order key: brackets as one symbol; no spaces; no combining marks (the display algorithm moves them)."""
    return "".join("|" if c in "()[]" else c for c in s if not c.isspace() and not unicodedata.combining(c))


def main() -> None:
    content = Path(sys.argv[1]).resolve()
    show = int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 15
    ing = ingest_pdf.Ingest(content)
    reviewed = [(r["page"], r["contains"]) for r in ing.cfg.get("bidi_reviewed", [])]
    seen: set[tuple[int, str]] = set()
    total = bad = 0
    examples = []
    for pno in range(1, ing.doc.page_count + 1):
        for ln in ing.lines(pno):
            if not ln.clusters or ln.text.startswith(("@@",)):
                continue
            printed = key("".join(c.text for c in sorted(ln.clusters, key=lambda c: c.x0 + c.x1)))
            shown = key(get_display(ln.text, base_dir="R" if ln.rtl else "L"))
            total += 1
            if shown != printed:
                if hits := [r for r in reviewed if r[0] == pno and r[1] in ln.text]:
                    seen.update(hits)
                    continue
                bad += 1
                if len(examples) < show:
                    examples.append(f"p{pno}: printed {printed[:70]!r}\n      shown   {shown[:70]!r}")
    if stale := [r for r in reviewed if r not in seen]:
        raise SystemExit(f"book.toml [[bidi_reviewed]] entries match no differing line: {stale}")
    print(f"lines {total} | order differs from print {bad} | reviewed differences {len(seen)}")
    print("\n".join(examples))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
