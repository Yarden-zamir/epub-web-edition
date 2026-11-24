"""Read the entries of errata/ERRATA.md (all sections) into plain dicts.

The table sections give rows 1-67. The "Not print errors" bullets get rows 68-70, in list order.
Their page comes from the release EPUB (the PDF page where the element starts).
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal, TypedDict

ERRATA = Path("errata/ERRATA.md")
TEXT_DIR = Path("epub-src-release/OEBPS/text")
PAGEBREAK = "{http://www.idpf.org/2007/ops}type"

type Status = Literal["verified", "family", "editor", "keep", "not-print"]

SECTIONS: dict[str, Status] = {
    "## Verified": "verified",
    "## Family decision": "family",
    "## Editor decision": "editor",
    "## Keep as printed": "keep",
    "## Not print errors": "not-print",
}


class Entry(TypedDict):
    row: int
    status: Status
    elements: list[str]
    pages: list[int]
    printed: list[str]           # the backtick quotes of the Printed cell
    printed_cell: str            # the Printed cell as written
    correction: str | None       # Correction or Proposed cell; None for editor, keep and not-print
    note: str                    # Problem, Reason or Evidence cell (markdown)
    evidence: str                # Evidence cell (markdown), empty when the section has none
    locate: list[tuple[str, int]]  # (quote, page) pairs for crop.py


def backticks(cell: str) -> list[str]:
    parts = cell.split("`")
    if len(parts) % 2 == 0:
        raise SystemExit(f"unbalanced backticks: {cell!r}")
    return parts[1::2]


def element_text(eid: str) -> tuple[int, str]:
    """PDF page where the element starts (last page break before it) and the element text."""
    for f in sorted(TEXT_DIR.glob("*.xhtml")):
        page = None
        for el in ET.parse(f).getroot().iter():
            if el.get(PAGEBREAK) == "pagebreak":
                page = int(el.get("id").removeprefix("pg-"))
            if el.get("id") == eid:
                if page is None:
                    raise SystemExit(f"no page break before {eid}")
                return page, "".join(el.itertext())
    raise SystemExit(f"element not found: {eid}")


def table_entry(status: Status, cells: list[str]) -> Entry:
    row, element, page, printed = cells[:4]
    elements = [e.split()[0] for e in element.split(", ")]
    pages = [int(p) for p in page.split(", ")]
    quotes = backticks(printed)
    if not quotes:
        raise SystemExit(f"row {row}: no quoted printed text")
    match status:
        case "verified" | "family":
            correction, note, evidence = cells[4], cells[5], cells[5]
        case "editor":
            correction, note, evidence = None, cells[4], cells[5]
        case "keep":
            correction, note, evidence = None, cells[4], ""
        case _:
            raise SystemExit(f"unexpected table status {status}")
    if correction is not None:
        correction = "".join(backticks(correction)) if "`" in correction else correction
    # One page for all quotes, one page per quote, or one quote on each page.
    if len(pages) == 1:
        locate = [(q, pages[0]) for q in quotes]
    elif len(pages) == len(quotes):
        locate = list(zip(quotes, pages))
    elif len(quotes) == 1:
        locate = [(quotes[0], p) for p in pages]
    else:
        raise SystemExit(f"row {row}: {len(pages)} pages for {len(quotes)} quotes")
    return Entry(row=int(row), status=status, elements=elements, pages=pages, printed=quotes,
                 printed_cell=printed, correction=correction, note=note, evidence=evidence, locate=locate)


def bullet_entry(row: int, line: str) -> Entry:
    eid, _, rest = line.removeprefix("- ").partition(": ")
    page, text = element_text(eid)
    # A bullet without a quote names a fault of the whole entry: show the start of the element.
    quote = rest.split('"')[1] if '"' in rest else " ".join(text.split()[:6])
    return Entry(row=row, status="not-print", elements=[eid], pages=[page], printed=[quote],
                 printed_cell=f"`{quote}`", correction=None, note=rest, evidence="", locate=[(quote, page)])


def load_entries() -> list[Entry]:
    entries: list[Entry] = []
    status: Status | None = None
    for line in ERRATA.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            status = next((s for h, s in SECTIONS.items() if line.startswith(h)), None)
            continue
        if status is None:
            continue
        if status == "not-print" and line.startswith("- "):
            entries.append(bullet_entry(68 + sum(e["status"] == "not-print" for e in entries), line))
        elif line.startswith("| ") and line[2:3].isdigit():
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            entries.append(table_entry(status, cells))
    rows = [e["row"] for e in entries]
    if rows != list(range(1, 71)):
        raise SystemExit(f"unexpected rows: {rows}")
    return entries
