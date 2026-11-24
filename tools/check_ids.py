# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Fail early when site data still uses a paragraph ID that ingestion moved.

Usage: uv run tools/check_ids.py CONTENT_DIR

Reads CONTENT_DIR/id-moves.csv (written by tools/ingest_pdf.py: old_id, new_id) and every JSON file under
CONTENT_DIR/site. Any JSON key or string value equal to an old ID is an error, printed with its new ID.
Exits 1 when it finds one.
"""

import csv
import json
import sys
from pathlib import Path


def strings(value: object) -> list[str]:
    """Every key and string value in a JSON document."""
    match value:
        case str():
            return [value]
        case dict():
            return [s for k, v in value.items() for s in [k, *strings(v)]]
        case list():
            return [s for v in value for s in strings(v)]
        case _:
            return []


def main() -> None:
    content = Path(sys.argv[1])
    with (content / "id-moves.csv").open(encoding="utf-8", newline="") as f:
        moves = {row["old_id"]: row["new_id"] for row in csv.DictReader(f)}
    found = 0
    for path in sorted((content / "site").rglob("*.json")):
        for s in strings(json.loads(path.read_text(encoding="utf-8"))):
            if s in moves:
                found += 1
                print(f"{path.relative_to(content)}: {s} moved to {moves[s]} (id-moves.csv); update the reference")
    print(f"moved IDs in site data: {found} | known moves {len(moves)}")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
