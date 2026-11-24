# /// script
# requires-python = ">=3.15"
# ///
"""Summarise saved Wikidata responses: search hits, or label/description/P625/P31 per item."""
import json
import sys
from pathlib import Path

for d in sys.argv[1:]:
    data = json.loads((Path(d) / "response.json").read_text())
    print("==", Path(d).name)
    if "search" in data:
        for hit in data["search"]:
            print(f"  {hit['id']}\t{hit.get('label','')}\t{hit.get('description','')}")
        continue
    for qid, ent in data["entities"].items():
        if "missing" in ent:
            print(f"  {qid} MISSING")
            continue
        lab = {k: v["value"] for k, v in ent.get("labels", {}).items()}
        desc = {k: v["value"] for k, v in ent.get("descriptions", {}).items()}
        claims = ent.get("claims", {})
        coords = [c["mainsnak"]["datavalue"]["value"] for c in claims.get("P625", []) if "datavalue" in c["mainsnak"]]
        p31 = [c["mainsnak"]["datavalue"]["value"]["id"] for c in claims.get("P31", []) if "datavalue" in c["mainsnak"]]
        cc = [(round(c["latitude"], 4), round(c["longitude"], 4)) for c in coords]
        enwiki = ent.get("sitelinks", {}).get("enwiki", {}).get("title", "")
        hewiki = ent.get("sitelinks", {}).get("hewiki", {}).get("title", "")
        print(f"  {qid}\the={lab.get('he','')}\ten={lab.get('en','')}\n     desc he={desc.get('he','')} | en={desc.get('en','')}\n     P625={cc} P31={p31} enwiki={enwiki} hewiki={hewiki}")
