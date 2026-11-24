# /// script
# requires-python = ">=3.15"
# ///
"""Check site/places.json, timeline.json, glossary.json, crosslinks.json against the release EPUB source.

Checks: every element ID exists; quotes are exact substrings of their element's text; figure IDs are
<figure> elements; crosslink text occurs once and inside one text node; crosslink targets are chapter
headings; place coordinates equal the saved Wikidata P625 values. Exits non-zero on any error.
Usage (from the content repo root): uv run python -I content-data/scripts/check_content_data.py
"""
import json

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

X = "{http://www.w3.org/1999/xhtml}"
TEXT_DIR = Path("epub-src-release/OEBPS/text")
SITE = Path("site")
RAW = Path("content-data/wikidata-raw")


def valid_date(d: str) -> bool:
    """Date forms used in timeline.json: 1990, 1990-07, 1990-07-13, 1972/1973."""
    first, _, end = d.partition("/")
    parts = first.split("-")
    if not 1 <= len(parts) <= 3 or len(parts[0]) != 4 or any(len(p) != 2 for p in parts[1:]):
        return False
    if not all(p.isdigit() for p in parts) or (end and not (len(end) == 4 and end.isdigit())):
        return False
    return True


errors: list[str] = []
text: dict[str, str] = {}
tag: dict[str, str] = {}
nodes: dict[str, list[str]] = {}
for f in sorted(TEXT_DIR.glob("*.xhtml")):
    for el in ET.parse(f).getroot().iter():
        eid = el.get("id")
        if not eid:
            continue
        text[eid] = "".join(el.itertext())
        tag[eid] = el.tag.removeprefix(X)
        nodes[eid] = [t for t in el.itertext()]


def need(eid: str, where: str) -> bool:
    if eid not in text:
        errors.append(f"{where}: unknown element {eid}")
        return False
    return True


def need_quote(eid: str, quote: str, where: str) -> None:
    if need(eid, where) and quote not in text[eid]:
        errors.append(f"{where}: quote not found in {eid}: {quote[:60]}")


def wikidata_coords(qid: str) -> list[tuple[float, float]]:
    for resp in RAW.glob("get-*/response.json"):
        ent = json.loads(resp.read_text())["entities"].get(qid)
        if ent and "missing" not in ent:
            return [(round(c["mainsnak"]["datavalue"]["value"]["latitude"], 4),
                     round(c["mainsnak"]["datavalue"]["value"]["longitude"], 4))
                    for c in ent["claims"]["P625"]]
    return []


places = json.loads((SITE / "places.json").read_text())["places"]
for p in places:
    w = f"places/{p['id']}"
    for t in p["targets"]:
        need(t, w)
    need(p["description_source"], w)
    for fig in p["figures"]:
        if need(fig, w) and tag[fig] != "figure":
            errors.append(f"{w}: {fig} is not a figure")
    if (p["lat"], p["lon"]) not in wikidata_coords(p["wikidata"]):
        errors.append(f"{w}: coordinates do not match saved Wikidata {p['wikidata']}")

events = json.loads((SITE / "timeline.json").read_text())["events"]
for i, e in enumerate(events):
    w = f"timeline[{i}] {e['date']}"
    if not valid_date(e["date"]):
        errors.append(f"{w}: bad date")
    if not isinstance(e["major"], bool):
        errors.append(f"{w}: major is not a boolean")
    need_quote(e["target"], e["quote"], w)
    if "date_source" in e:
        need(e["date_source"], w)
dates = [e["date"] for e in events]
# Order is checked by year only; within a year, events keep the order of the text.
years = [d[:4] for d in dates]
if years != sorted(years):
    errors.append("timeline: events are not in date order")

all_text = "\n".join(text.values())
terms = json.loads((SITE / "glossary.json").read_text())["terms"]
for t in terms:
    w = f"glossary/{t['term']}"
    need_quote(t["source"], t["quote"], w)
    missing = [f for f in t["forms"] if f not in all_text]
    if missing:
        errors.append(f"{w}: forms not in the book: {missing}")

for i, link in enumerate(json.loads((SITE / "crosslinks.json").read_text())["links"]):
    w = f"crosslinks[{i}] {link['element']}"
    if not need(link["element"], w) or not need(link["target"], w):
        continue
    n = text[link["element"]].count(link["text"])
    if n != 1:
        errors.append(f"{w}: text occurs {n} times")
    if not any(link["text"] in node for node in nodes[link["element"]]):
        errors.append(f"{w}: text spans inline markup")
    if tag[link["target"]] != "h2":
        errors.append(f"{w}: target {link['target']} is not a chapter heading")

print(f"places {len(places)}, events {len(events)}, terms {len(terms)}, errors {len(errors)}")
for e in errors:
    print("ERROR", e)
sys.exit(1 if errors else 0)
