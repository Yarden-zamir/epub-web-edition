# /// script
# requires-python = ">=3.15"
# ///
"""Write errata/print-check.md and errata/errata.json from errata/ERRATA.md and errata/print-check/checks.toml.

Run from the content repo root, after crop.py: uv run errata/print-check/build.py
"""
import json
import sys
import tomllib
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from entries import Entry, load_entries  # noqa: E402

VERDICTS = ("in print", "conversion error", "unclear")
CHECKS = Path("errata/print-check/checks.toml")
CROPS = Path("errata/print-check")
REPORT = Path("errata/print-check.md")
JSON_OUT = Path("errata/errata.json")


def links(cell: str) -> list[dict]:
    """Markdown links [label](url) in a cell, in order."""
    out = []
    rest = cell
    while "](" in rest:
        head, _, tail = rest.partition("](")
        label = head.rpartition("[")[2]
        url, _, rest = tail.partition(")")
        # A URL with ")" in it (Wikipedia disambiguation) continues to the next ")".
        if url.count("(") > url.count(")"):
            more, _, rest = rest.partition(")")
            url = f"{url}){more}"
        out.append({"label": label, "url": url})
    return out


def plain(cell: str) -> str:
    return cell.replace("`", "").strip()


def evidence(e: Entry, previous: list[dict]) -> list[dict]:
    """Sources of the entry. A cell that says "Same …" reuses the sources of the row before."""
    cell = e["evidence"]
    found = links(cell)
    if found:
        return found
    if cell.startswith("Same") or "Same source" in cell:
        return previous
    for word in cell.replace(":", " ").split():
        if word.startswith("10.") and "doi" in cell:
            return [{"label": plain(cell), "url": f"https://doi.org/{word.rstrip('.,')}"}]
    # Editor rows cite books and papers without a link; keep the citation as a label.
    if e["status"] == "editor" and cell:
        return [{"label": plain(cell), "url": None}]
    return []


def main() -> int:
    entries = load_entries()
    checks = tomllib.loads(CHECKS.read_text(encoding="utf-8"))["rows"]
    if sorted(int(k) for k in checks) != [e["row"] for e in entries]:
        raise SystemExit("checks.toml rows do not match ERRATA.md rows")
    out, lines, previous = [], [], []
    counts = {v: 0 for v in VERDICTS}
    for e in entries:
        c = checks[str(e["row"])]
        verdict = c["verdict"]
        if verdict not in VERDICTS:
            raise SystemExit(f"row {e['row']}: unknown verdict {verdict!r}")
        if verdict == "conversion error" and "printed" not in c:
            raise SystemExit(f"row {e['row']}: a conversion error needs the printed text")
        counts[verdict] += 1
        crop = CROPS / f"{e['row']}.png"
        if not crop.is_file():
            raise SystemExit(f"missing crop {crop}; run crop.py first")
        ev = evidence(e, previous)
        previous = ev
        out.append({
            "row": e["row"],
            "status": e["status"],
            "element": ", ".join(e["elements"]),
            "pdf_page": e["pages"],
            "printed": c.get("printed", " / ".join(e["printed"])),
            "correction": e["correction"],
            "explanation": c["explanation"],
            "evidence": ev,
            "print_check": verdict,
            "crop": str(crop),
        })
        quote = " / ".join(f"`{q}`" for q in e["printed"])
        shows = c.get("shows", "The quoted text, unchanged.")
        zoom = CROPS / f"{e['row']}-zoom.png"
        crop_md = f"[{crop.name}](print-check/{crop.name})"
        if zoom.is_file():
            crop_md += f", [{zoom.name}](print-check/{zoom.name})"
        pages = ", ".join(str(p) for p in e["pages"])
        lines.append(f"| {e['row']} | {', '.join(e['elements'])} | {pages} | {quote} | {shows} | {verdict} | {crop_md} |")
    JSON_OUT.write_text(json.dumps({"generated": date.today().isoformat(), "entries": out},
                                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    head = REPORT.read_text(encoding="utf-8").split("<!-- table -->")[0]
    table = ["<!-- table -->", "",
             "| Row | Element | Page | Quoted printed text (ERRATA.md) | What the image shows | Verdict | Crop |",
             "|---|---|---|---|---|---|---|", *lines, ""]
    REPORT.write_text(head + "\n".join(table), encoding="utf-8")
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
