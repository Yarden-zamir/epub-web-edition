# /// script
# requires-python = ">=3.15"
# ///
"""Fetch the official Dead Sea level series for the web chart next to the printed chart on PDF page 113.

Source: Israel Water Authority, dataset "מפלס ים המלח" on data.gov.il (licence: open, "אחר (פתוח)").
Usage: uv run scripts/dead_sea_level.py
Writes site/data/dead-sea-level.json: {source, fetched, points: [[YYYY-MM-DD, level in metres], ...]}.
"""

import datetime
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data" / "dead-sea-level.json"
RESOURCE = "823479b4-4771-43d8-9189-6a2a1dcaaf10"
API = f"https://data.gov.il/api/3/action/datastore_search?resource_id={RESOURCE}&limit=10000"
DATASET = "https://data.gov.il/dataset/https-www-data-gov-il-dataset-683"


def main() -> None:
    # data.gov.il refuses requests without a browser-like User-Agent.
    req = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0 (book site data fetch)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        result = json.load(r)["result"]
    records = result["records"]
    if result.get("total") != len(records):
        raise SystemExit(f"got {len(records)} of {result.get('total')} records; raise the limit")
    points = sorted(
        (datetime.datetime.strptime(rec["תאריך מדידה"], "%d/%m/%Y").date().isoformat(), float(rec["מפלס"]))
        for rec in records
    )
    if len({d for d, _ in points}) != len(points):
        raise SystemExit("duplicate measurement dates in the source")
    if not all(-460 < level < -380 for _, level in points):
        raise SystemExit("a level is outside the plausible range; check the source")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "source": {"label": "רשות המים, data.gov.il", "url": DATASET},
        "fetched": datetime.date.today().isoformat(),
        "points": points,
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(points)} points, {points[0]} to {points[-1]} -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
