"""Credits and licences: the footer block that holds the edition credits (the colophon) and the credits of the web edition.

The web part, in this order:
- the base map of every web map (makeMap in site/features/50-maps.js), and each other line of figure-maps/*.json
  "attribution" (with "attribution_links");
- the source of each then-and-now layer (then-now.json "credit");
- the groups of credits.json, next to the enhancements file, for data that no map spec names (for example the relief
  of the maps drawn for the edition). Format in books/eli-raz/AGENTS-BRIEF.md;
- the map library.
Map parts show only when the book has a map.
"""

import html
import json
from pathlib import Path

from build_web import BookError, Site, credit_html

# The credit of the base map tiles. 50-maps.js shows the same credit (MAP_CREDIT) in the corner of each map.
BASE_MAP = ["Map data: © OpenStreetMap contributors, SRTM", "Map display: © OpenTopoMap (CC-BY-SA)"]
BASE_MAP_LINKS = {"OpenStreetMap": "https://www.openstreetmap.org/copyright", "OpenTopoMap": "https://opentopomap.org",
                  "CC-BY-SA": "https://creativecommons.org/licenses/by-sa/3.0/"}
LIBRARY = ("Leaflet 1.9.4 © 2010-2023 Volodymyr Agafonkin, © 2010-2011 CloudMade, BSD 2-Clause License",
           {"Leaflet": "https://leafletjs.com", "BSD 2-Clause License": "https://github.com/Leaflet/Leaflet/blob/v1.9.4/LICENSE"})


def item(text_html: str, lang: str | None) -> str:
    """One credit line. A line in another language keeps its own direction inside the right-to-left list."""
    if lang:
        return f'<li><bdi lang="{html.escape(lang)}" dir="{"rtl" if lang == "he" else "ltr"}">{text_html}</bdi></li>'
    return f"<li>{text_html}</li>"


def group(title: str, items: list[str]) -> str:
    return f'<h3 class="credits-group">{html.escape(title)}</h3><ul>{"".join(items)}</ul>' if items else ""


def map_groups(data_dir: Path) -> list[str]:
    figure_maps = sorted((data_dir / "figure-maps").glob("*.json")) if (data_dir / "figure-maps").is_dir() else []
    then_now = data_dir / "then-now.json"
    if not (figure_maps or then_now.is_file() or (data_dir / "places.json").is_file()):
        return []
    lines = [item(credit_html([line], {w: u for w, u in BASE_MAP_LINKS.items() if w in line}, "base map"), "en") for line in BASE_MAP]
    seen = set(BASE_MAP)
    for path in figure_maps:
        spec = json.loads(path.read_text(encoding="utf-8"))
        links = spec.get("attribution_links", {})
        for line in spec["attribution"]:
            if line not in seen:
                seen.add(line)
                lines.append(item(credit_html([line], {w: u for w, u in links.items() if w in line}, f"figure-maps/{path.name}"), "en"))
    groups = [group("מפות באתר", lines)]
    if then_now.is_file():
        spec = json.loads(then_now.read_text(encoding="utf-8"))
        layers = []
        for layer in spec["layers"]:
            credit = layer["credit"]
            if not credit["url"].startswith("https://"):
                raise BookError(f"then-now.json: layer {layer['id']!r}: credit url must be https")
            layers.append(item(f'<a href="{html.escape(credit["url"])}" rel="noopener">{html.escape(credit["text"])}</a>', "en"))
        groups.append(group(f"שכבות המפה „{spec['title']}”", layers))
    return groups


def data_groups(path: Path) -> list[str]:
    """credits.json: {"groups": [{"title", "items": [{"text", "lang"?, "links"?: {word: https URL}}]}]}."""
    if not path.is_file():
        return []
    groups = []
    for n, g in enumerate(json.loads(path.read_text(encoding="utf-8"))["groups"]):
        if not g.get("title") or not g.get("items"):
            raise BookError(f"credits.json: group {n} needs a title and items")
        items = [item(credit_html([i["text"]], i.get("links", {}), f"credits.json: {g['title']}"), i.get("lang")) for i in g["items"]]
        groups.append(group(g["title"], items))
    return groups


def values(site: Site) -> dict[str, str]:
    if site.data_dir is None:
        return {"credits": ""}
    maps = map_groups(site.data_dir)
    parts = maps + data_groups(site.data_dir / "credits.json")
    if maps:
        text, links = LIBRARY
        parts.append(group("תוכנה", [item(credit_html([text], links, "map library"), "en")]))
    return {"credits": f'<section class="credits-web">{"".join(parts)}</section>' if parts else ""}
