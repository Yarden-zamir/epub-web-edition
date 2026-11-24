"""Places map: places.json becomes a map section right after the printed contents."""

import html
import json
from pathlib import Path

from build_web import BookError, Converter, Site, Thumbs, missing_id


def place_style(count: int) -> str:
    """--place-N for each place, used by the contents dots, the navigator and search.
    Every place takes the one pin colour (--pin, 50-maps.css): the map names each place, and 29 colours cannot stay
    apart for colour-blind readers (the validated 8-colour palette of the dataviz rules keeps at most 3 hues apart
    on a map; the Ein Gedi group alone has 7 places within 2 km). Revisit if places get a grouping with 3 or fewer kinds."""
    return ":root { " + " ".join(f"--place-{i}: var(--pin);" for i in range(1, count + 1)) + " }"


def places_html(data_dir: Path | None, conv: "Converter", thumbs: Thumbs) -> str:
    """Map section from places.json: {"places": [{id, name, lat, lon, wikidata, targets, description,
    description_source, figures}]}. Every element ID must exist in the EPUB. Empty when the file is absent."""
    path = data_dir / "places.json" if data_dir else None
    if path is None or not path.is_file():
        return ""
    places = json.loads(path.read_text(encoding="utf-8"))["places"]
    items, points, seen = [], [], set()
    for n, place in enumerate(places, start=1):
        pid, name, lat, lon = place["id"], place["name"], float(place["lat"]), float(place["lon"])
        where = f"places.json: place {pid!r}"
        if pid in seen or pid in conv.ids:
            raise BookError(f"{where}: id is not unique")
        seen.add(pid)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise BookError(f"{where}: bad coordinates")
        if not (place["wikidata"].startswith("Q") and place["wikidata"][1:].isdigit()):
            raise BookError(f"{where}: wikidata must be a Q identifier")
        for ref in [*place["targets"], place["description_source"]]:
            if ref not in conv.ids:
                raise missing_id(where, ref)
        kind = place["description_kind"]
        if kind not in ("book", "edition") or (kind == "edition" and not place.get("description_url", "").startswith("https://")):
            raise BookError(f"{where}: description_kind must be book or edition; an edition description needs an https description_url")
        if not isinstance(place.get("far", False), bool):
            raise BookError(f"{where}: far must be true or false")
        if not place["targets"]:
            raise BookError(f"{where}: needs at least one target")
        for fig in place["figures"]:
            if fig not in conv.figure_img:
                raise missing_id(where, fig, "a figure with an image")
        first_target: dict[str, str] = {}  # Chapter ID -> the place's first target in it, in file order.
        for t in place["targets"]:
            first_target.setdefault(conv.chapter_of[t], t)
        chapters = [{"href": f"#{t}", "chapter": c, "title": conv.chapter_title[c]} for c, t in first_target.items()]
        points.append({
            "id": pid, "n": n, "name": name, "lat": lat, "lon": lon, "far": place.get("far", False),
            "wikidata": f"https://www.wikidata.org/wiki/{place['wikidata']}",
            "description": place["description"], "source": f"#{place['description_source']}",
            "description_kind": kind, "description_url": place.get("description_url"),
            "chapters": chapters,
            "figures": [{"href": f"#{f}", "thumb": thumbs(conv.figure_img[f][0]), "alt": conv.figure_img[f][1]}
                        for f in place["figures"]],
        })
        links = "".join(f'<a href="{html.escape(c["href"])}">{html.escape(c["title"])}</a>' for c in chapters)
        items.append(f'<li id="place-{html.escape(pid)}">'
                     f'<i class="place-dot" aria-hidden="true"></i>'
                     f'<span class="place-name">{html.escape(name)}</span><span class="place-chapters">{links}</span></li>')
    data = json.dumps(points, ensure_ascii=False).replace("</", "<\\/")
    return ('<section class="places" id="places" aria-labelledby="places-title">'
            '<div class="places-head"><h2 id="places-title">המקומות בספר</h2>'
            '<p class="places-intro">לחיצה על מקום במפה מציגה את תיאורו מתוך הספר ואת הפרקים שבהם הוא מופיע.</p></div>'
            '<div class="places-map" id="places-map" hidden></div>'
            f'<details class="places-all"><summary>כל המקומות ({len(places)})</summary>'
            f'<ol class="places-list">{"".join(items)}</ol></details>'
            f'<style>{place_style(len(places))}</style>'
            f'<script type="application/json" id="places-data">{data}</script></section>')


def after_contents(site: Site) -> str:
    return places_html(site.data_dir, site.conv, site.thumbs)
