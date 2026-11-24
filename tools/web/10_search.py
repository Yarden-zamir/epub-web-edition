"""Search index: search.json with every indexed text block, its printed page, chapter, kind and figure thumbnail."""

import json

from build_web import Site


SEARCH_KIND = {"h1": "heading", "h2": "heading", "h3": "heading", "figure": "figure"}  # Others are "text".


def write(site: Site) -> None:
    # Location: the running number of a text block (its index here plus one), like a Kindle location.
    conv = site.conv
    search = [
        {"id": e.id, "page": e.page, "section": e.section, "chapter": e.chapter, "text": e.text,
         "kind": SEARCH_KIND.get(conv.tags[e.id], "text")} | ({"thumb": site.thumbs(e.img)} if e.img else {})
        for e in conv.search
    ]
    index = {"pages": conv.pages, "entries": search}
    (site.out / "search.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    site.report["search_entries"] = len(search)
