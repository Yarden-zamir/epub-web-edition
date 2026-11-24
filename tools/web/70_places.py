"""Places map: places.json becomes a map section right after the printed contents."""

import html
import json
import math
from pathlib import Path

from build_web import BookError, Converter, Site, Thumbs, missing_id


def oklch_hex(lightness: float, chroma: float, hue: float) -> str | None:
    """sRGB hex for an OKLCH colour, or None when it is outside the sRGB gamut."""
    a, b = chroma * math.cos(math.radians(hue)), chroma * math.sin(math.radians(hue))
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076926715 * s_)
    if any(not 0 <= c <= 1 for c in rgb):
        return None
    srgb = (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in rgb)
    return "#" + "".join(f"{round(255 * c):02x}" for c in srgb)


def place_colours(count: int, lightness: tuple[float, float]) -> list[str]:
    """One colour per place. Hues step by the golden angle and lightness alternates, so neighbours in the
    list differ in hue and in lightness. Limit: with many places, some pairs far apart in the list look alike,
    especially with colour blindness, so each place also shows its number and name. Revisit if places get a grouping."""
    colours = []
    for i in range(count):
        hue, l_, chroma = (25 + i * 137.508) % 360, lightness[i % 2], 0.16
        # Lower the chroma to fit sRGB, but not below 0.11 (grey territory); turn the hue a little instead.
        while (colour := oklch_hex(l_, chroma, hue)) is None:
            chroma -= 0.005
            if chroma < 0.11:
                hue, chroma = (hue + 7) % 360, 0.16
        colours.append(colour)
    return colours


def number_ink(colour: str) -> str:
    """White or near-black, whichever has more WCAG contrast on the colour, for the number on a place dot."""
    channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lum = sum(w * (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
              for w, c in zip((0.2126, 0.7152, 0.0722), channels))
    return "#ffffff" if 1.05 / (lum + 0.05) >= (lum + 0.05) / 0.0617 else "#1c1a17"  # 0.0617: luminance of #1c1a17 + 0.05.


def place_style(count: int) -> str:
    """CSS custom properties --place-N (colour) and --place-ink-N (number colour) for light and dark mode."""
    def props(colours: list[str]) -> str:
        return " ".join(f"--place-{i}: {c}; --place-ink-{i}: {number_ink(c)};" for i, c in enumerate(colours, start=1))
    light = props(place_colours(count, (0.48, 0.7)))
    dark = props(place_colours(count, (0.5, 0.665)))
    return (f":root {{ {light} }}\n@media (prefers-color-scheme: dark) {{ :root:not([data-theme=\"light\"]) {{ {dark} }} }}\n"
            f":root[data-theme=\"dark\"] {{ {dark} }}")


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
        items.append(f'<li id="place-{html.escape(pid)}" style="--place: var(--place-{n}); --ink: var(--place-ink-{n})">'
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
