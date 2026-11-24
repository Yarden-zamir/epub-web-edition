# /// script
# requires-python = ">=3.15"
# dependencies = ["matplotlib==3.11.2", "numpy==2.5.4", "Pillow==13.0.0"]
# ///
"""Draw the open replacement for the disaster-area map on PDF page 66 (image p066-x251, figure fig-a10-02).

The printed map looks like a Google Maps screenshot without attribution, so the release edition uses this map.
It shows the places that chapter a10 names: Dushanbe (a10-p007), the Jirgatal airstrip (a10-p008), the base camp
at Achik-Tash (a10-p010), the first camp at 4,400 m (a10-p016, a10-p018), the Frying Pan (a10-p002) and Lenin Peak.

Data:
- Relief: Copernicus DEM GLO-90 (overview) and GLO-30 (detail), free licence with attribution (map_common.dem_credit).
- Places, camps, glaciers, rivers in the detail: OpenStreetMap via Overpass, ODbL. Element IDs in PLACES.
- Borders, rivers and lakes in the overview: Natural Earth v5.1.2, public domain.
- Range and valley labels: placed by hand along the relief; Wikidata Q1206886 (Trans-Alay Range) and Q2282164 (Alay Valley)
  give the reference points.

Usage: uv run scripts/pamir_map.py
Writes replacements/p066-x251-open-map.png and site/figure-maps/fig-a10-02.json.
"""

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import ConnectionPatch, Rectangle  # noqa: E402

from map_common import (DEM_PIXELS_PER_DEGREE, NE_CREDIT, credit_text, OSM_CREDIT, OTM_CREDIT, ROOT, dem, dem_credit, halo, hebrew_fonts,  # noqa: E402
                        hillshade, km_per_degree_lon, natural_earth, osm_element, osm_line, osm_point, osm_rings,
                        overpass, relief, rings, save_png, write_spec)

OUT = ROOT / "replacements" / "p066-x251-open-map.png"
FIGURE = "fig-a10-02"

# Overview and detail frames: (west, east, south, north).
MAIN = (68.25, 73.75, 38.15, 40.15)
DETAIL = (72.69, 73.033, 39.325, 39.50)

# key: (OSM type, OSM id, Wikidata id or None, Hebrew label, book paragraph that names the place)
PLACES = {
    "dushanbe": ("node", 27547977, "Q9365", "דושנבה", "a10-p007"),
    "jirgatal": ("node", 1042088758, None, "ג'ירגיטל (מנחת)", "a10-p008"),
    "base_camp": ("node", 9355212381, "Q65038131", "מחנה הבסיס באצ'יקטש", "a10-p010"),
    "camp_1": ("node", 2439609423, None, "המחנה הראשון", "a10-p018"),
    "frying_pan": ("way", 368181500, None, "המחבת, אתר האסון", "a10-p002"),
    "lenin_peak": ("node", 349008747, "Q838587", "פסגת לנין", "a10-p002"),
}
OSM_NOTES = {
    "jirgatal": "OSM node 1042088758, Jirgatol Airport",
    "base_camp": "OSM node 9355212381, IMC Pamir base camp in the Achik-Tash valley (Wikidata Q65038131)",
    "camp_1": "OSM node 2439609423, Camp 1",
    "frying_pan": "Centre of OSM way 368181500, Сковородка / The Frying Pan",
}
PLACES_QUERY = """[out:json][timeout:120];
(node(id:27547977,1042088758,9355212381,2439609423,349008747); way(id:368181500););
out center tags;"""
DETAIL_QUERY = """[out:json][timeout:120];
(nwr["natural"="glacier"](39.30,72.66,39.52,73.06); way["waterway"~"river|stream"]["name"](39.30,72.66,39.52,73.06););
out geom;"""

# Hypsometric tints (metres, colour): light, so labels and e-ink greys stay readable.
STOPS = [(300, "#cfd8b4"), (1200, "#e2dcb6"), (2200, "#e6cfa6"), (3200, "#d6bf9c"), (4200, "#c9bcae"),
         (5000, "#e3e1de"), (6000, "#f7f7f7")]
INK, ACCENT, ROUTE, WATER = "#1c1a17", "#b3261e", "#0e4840", "#4f86a8"


def draw_relief(ax, frame: tuple[float, float, float, float], resolution: int, step: int) -> None:
    west, east, south, north = frame
    z = dem(west, east, south, north, resolution)[::step, ::step]
    shade = hillshade(z, south, north, step / DEM_PIXELS_PER_DEGREE[resolution])
    ax.imshow(relief(z, shade, STOPS), extent=(west, east, south, north), origin="upper", interpolation="antialiased", zorder=0)
    frame_axes(ax, frame)  # After imshow, which resets the aspect.


def frame_axes(ax, frame: tuple[float, float, float, float]) -> None:
    west, east, south, north = frame
    ax.set_xlim(west, east)
    ax.set_ylim(south, north)
    ax.set_aspect(1 / math.cos(math.radians((south + north) / 2)))
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor(INK)
        spine.set_linewidth(1)


def true_ratio(frame: tuple[float, float, float, float]) -> float:
    """Height over width of a frame drawn at true shape for its middle latitude."""
    west, east, south, north = frame
    return (north - south) / ((east - west) * math.cos(math.radians((south + north) / 2)))


def scale_bar(ax, frame, km: int, label: str, font) -> None:
    west, east, south, north = frame
    lat = south + (north - south) * 0.06
    deg = km / km_per_degree_lon(lat)
    x1 = east - (east - west) * 0.04
    ax.plot([x1 - deg, x1], [lat, lat], color=INK, linewidth=2.5, solid_capstyle="butt", path_effects=halo(5), zorder=8)
    ax.text(x1 - deg / 2, lat + (north - south) * 0.025, label, fontproperties=font, fontsize=8.5, color=INK,
            ha="center", va="bottom", path_effects=halo(), zorder=8)


def main() -> None:
    font, bold = hebrew_fonts()
    places_raw = overpass("pamir-places", PLACES_QUERY)
    detail_raw = overpass("pamir-detail", DETAIL_QUERY)
    coords = {key: osm_point(osm_element(places_raw, kind, osm_id)) for key, (kind, osm_id, *_rest) in PLACES.items()}
    countries = natural_earth("ne_10m_admin_0_countries.geojson")
    rivers = natural_earth("ne_10m_rivers_lake_centerlines.geojson")
    lakes = natural_earth("ne_10m_lakes.geojson")
    locator_countries = natural_earth("ne_50m_admin_0_countries.geojson")

    width_px, detail_w, gap_px = 1600, 1000, 14
    main_px = round(width_px * true_ratio(MAIN))
    bottom_px = round(detail_w * true_ratio(DETAIL))
    height_px = main_px + gap_px + bottom_px
    fig = plt.figure(figsize=(width_px / 200, height_px / 200), dpi=200)
    fig.patch.set_facecolor("white")
    ax = fig.add_axes((0, 1 - main_px / height_px, 1, main_px / height_px))
    axd = fig.add_axes((1 - detail_w / width_px, 0, detail_w / width_px, bottom_px / height_px))

    # Overview.
    draw_relief(ax, MAIN, 90, 2)
    for feat in lakes["features"]:
        for ring in rings(feat["geometry"]):
            ax.fill(*zip(*ring), color="#a9c8dc", zorder=2)
    for feat in rivers["features"]:
        for line in rings(feat["geometry"]):
            ax.plot(*zip(*line), color=WATER, linewidth=0.8, alpha=0.8, zorder=2)
    for feat in countries["features"]:
        if feat["properties"]["ADM0_A3"] not in ("TJK", "KGZ", "UZB", "AFG", "CHN"):
            continue
        for ring in rings(feat["geometry"]):
            ax.plot(*zip(*ring), color="white", linewidth=3, alpha=0.8, zorder=3)
            ax.plot(*zip(*ring), color="#5c5047", linewidth=1.1, dashes=(5, 2), zorder=3)
    for text, x, y, size, rot in (("טג'יקיסטן", 70.35, 38.6, 15, 0), ("קירגיזסטן", 72.4, 40.0, 15, 0),
                                  ("רכס טרנס־אלאי", 72.15, 39.15, 10.5, 0), ("עמק אלאי", 72.5, 39.7, 10.5, 3),
                                  ("הרי פאמיר", 72.6, 38.45, 12, 0)):
        ax.text(x, y, text, fontproperties=bold if size > 11 else font, fontsize=size, color="#5c4a3a", rotation=rot,
                ha="center", va="center", path_effects=halo(3.5), zorder=4, alpha=0.95)
    (d_lat, d_lon), (j_lat, j_lon), (b_lat, b_lon) = coords["dushanbe"], coords["jirgatal"], coords["base_camp"]
    ax.plot([d_lon, j_lon], [d_lat, j_lat], color=ROUTE, linewidth=2, dashes=(6, 3), path_effects=halo(4.5), zorder=5)
    ax.plot([j_lon, b_lon], [j_lat, b_lat], color=ROUTE, linewidth=2, dashes=(1.5, 2.5), path_effects=halo(4.5), zorder=5)
    ax.text((d_lon + j_lon) / 2, (d_lat + j_lat) / 2 + 0.07, "טיסה", fontproperties=font, fontsize=9.5, color=ROUTE,
            rotation=math.degrees(math.atan2((j_lat - d_lat) / math.cos(math.radians(39)), j_lon - d_lon)) * 0.9,
            ha="center", va="bottom", path_effects=halo(), zorder=6)
    ax.text((j_lon + b_lon) / 2, (j_lat + b_lat) / 2 - 0.05, "מסוק", fontproperties=font, fontsize=9.5, color=ROUTE,
            rotation=math.degrees(math.atan2((b_lat - j_lat) / math.cos(math.radians(39)), b_lon - j_lon)),
            ha="center", va="top", path_effects=halo(), zorder=6)
    ax.plot(d_lon, d_lat, "o", markersize=8, color=INK, markeredgecolor="white", markeredgewidth=1.5, zorder=7)
    ax.text(d_lon, d_lat - 0.07, "דושנבה", fontproperties=bold, fontsize=11.5, color=INK, ha="center", va="top",
            path_effects=halo(), zorder=7)
    ax.plot(j_lon, j_lat, "s", markersize=7, color=ROUTE, markeredgecolor="white", markeredgewidth=1.3, zorder=7)
    ax.text(j_lon, j_lat - 0.07, "ג'ירגיטל (מנחת)", fontproperties=font, fontsize=10, color=INK, ha="center", va="top",
            path_effects=halo(), zorder=7)
    p_lat, p_lon = coords["lenin_peak"]
    ax.plot(p_lon, p_lat, "^", markersize=12, color=ACCENT, markeredgecolor="white", markeredgewidth=1.4, zorder=7)
    ax.text(p_lon + 0.02, p_lat - 0.1, "פסגת לנין", fontproperties=bold, fontsize=11.5, color=ACCENT, ha="center", va="top",
            path_effects=halo(), zorder=7)
    ax.plot(b_lon, b_lat, "D", markersize=6, color=ROUTE, markeredgecolor="white", markeredgewidth=1.2, zorder=7)
    ax.text(b_lon + 0.06, b_lat + 0.06, "מחנה הבסיס", fontproperties=font, fontsize=10, color=INK, ha="left", va="bottom",
            path_effects=halo(), zorder=7)
    west, east, south, north = DETAIL
    ax.add_patch(Rectangle((west, south), east - west, north - south, fill=False, edgecolor=INK, linewidth=1.3, zorder=8))
    scale_bar(ax, MAIN, 50, "50 ק\"מ", font)

    # Detail.
    draw_relief(axd, DETAIL, 30, 1)
    for element in detail_raw:
        tags = element["tags"]
        if element["type"] == "node":
            continue  # Glacier points carry no outline.
        if tags.get("natural") == "glacier":
            for ring in osm_rings(element):
                axd.fill(*zip(*ring), facecolor="#eef5fa", edgecolor="#7fa7c2", linewidth=0.7, alpha=0.75, zorder=2)
        elif "waterway" in tags:
            axd.plot(*zip(*osm_line(element)), color=WATER, linewidth=1.2, zorder=3)
    axd.text(72.915, 39.388, "קרחון לנין", fontproperties=font, fontsize=10, color="#2f5d7c", rotation=0,
             ha="center", va="center", path_effects=halo(3), zorder=4)
    marks = {"base_camp": ("D", ROUTE, 9, (0.008, 0.004), "left"), "camp_1": ("D", ROUTE, 9, (0.01, 0.0), "left"),
             "frying_pan": ("X", ACCENT, 12, (-0.012, 0.0), "right"), "lenin_peak": ("^", ACCENT, 13, (0.012, -0.004), "left")}
    for key, (marker, color, size, (dx, dy), ha) in marks.items():
        lat, lon = coords[key]
        axd.plot(lon, lat, marker, markersize=size, color=color, markeredgecolor="white", markeredgewidth=1.5, zorder=7)
        axd.text(lon + dx, lat + dy, PLACES[key][3], fontproperties=bold, fontsize=11, color=INK if color == ROUTE else ACCENT,
                 ha=ha, va="center", path_effects=halo(3.5), zorder=7)
    scale_bar(axd, DETAIL, 2, "2 ק\"מ", font)
    for corner_main, corner_detail in (((west, south), (west, north)), ((east, south), (east, north))):
        fig.add_artist(ConnectionPatch(corner_main, corner_detail, "data", "data", axesA=ax, axesB=axd,
                                       color=INK, linewidth=0.8, alpha=0.45))

    # Left column: legend, locator, credits.
    legend = fig.add_axes((0, 0, 1 - detail_w / width_px - 0.01, bottom_px / height_px))
    legend.set_axis_off()
    legend.set_xlim(0, 1)
    legend.set_ylim(0, 1)
    rows = [("^", ACCENT, "פסגה"), ("o", INK, "עיר"), ("s", ROUTE, "מנחת"), ("D", ROUTE, "מחנה"), ("X", ACCENT, "אתר האסון")]
    for i, (marker, color, label) in enumerate(rows):
        y = 0.96 - i * 0.055
        legend.plot(0.93, y, marker, markersize=9, color=color, markeredgecolor="white", markeredgewidth=1.2)
        legend.text(0.88, y, label, fontproperties=font, fontsize=10, color=INK, ha="right", va="center")
    for i, (dashes, label) in enumerate((((6, 3), "טיסה"), ((1.5, 2.5), "מסוק"))):
        y = 0.96 - (len(rows) + i) * 0.055
        legend.plot([0.86, 0.97], [y, y], color=ROUTE, linewidth=2, dashes=dashes)
        legend.text(0.83, y, f"{label} (קו ישר, סכמטי)", fontproperties=font, fontsize=10, color=INK, ha="right", va="center")
    y = 0.96 - (len(rows) + 2) * 0.055
    legend.plot([0.86, 0.97], [y, y], color="#5c5047", linewidth=1.1, dashes=(5, 2))
    legend.text(0.83, y, "גבול מדינה", fontproperties=font, fontsize=10, color=INK, ha="right", va="center")

    loc = fig.add_axes((0.03, 158 / height_px, 0.3, 200 / height_px))
    lw, le, ls, ln = 58.0, 81.0, 34.5, 45.0
    loc.set_xlim(lw, le)
    loc.set_ylim(ls, ln)
    loc.set_aspect(1 / math.cos(math.radians((ls + ln) / 2)))
    loc.set_xticks([])
    loc.set_yticks([])
    loc.set_facecolor("#dfe7ec")
    for feat in locator_countries["features"]:
        code = feat["properties"]["ADM0_A3"]
        fill = {"TJK": "#e6cfa6", "KGZ": "#efe2c8"}.get(code, "#f3f1ec")
        for ring in rings(feat["geometry"]):
            loc.fill(*zip(*ring), facecolor=fill, edgecolor="#8b8478", linewidth=0.4)
    loc.add_patch(Rectangle((MAIN[0], MAIN[2]), MAIN[1] - MAIN[0], MAIN[3] - MAIN[2], fill=False, edgecolor=ACCENT, linewidth=1.5))
    loc.text(0.98, 0.04, "מרכז אסיה", transform=loc.transAxes, fontproperties=font, fontsize=8, color=INK, ha="right", va="bottom")

    credits = credit_text("New map drawn for this edition.", f"Places, camps, glaciers: {OSM_CREDIT}.",
                          f"Borders, rivers: {NE_CREDIT}.", dem_credit(90, 30) + ".", width=62)
    fig.text(0.012, 0.008, credits, fontsize=5.6, color="#4d463e", ha="left", va="bottom", linespacing=1.35)
    save_png(fig, OUT)

    markers = []
    for key, (kind, osm_id, qid, label, target) in PLACES.items():
        lat, lon = coords[key]
        marker = {"name": label, "lat": round(lat, 6), "lon": round(lon, 6),
                  "source": OSM_NOTES.get(key, f"OSM {kind} {osm_id}") + " (© OpenStreetMap contributors, ODbL)", "target": target}
        if qid:
            marker["wikidata"] = qid
        markers.append(marker)
    write_spec(FIGURE, {
        "title": "מפת אזור האסון: מדושנבה אל פסגת לנין",
        "base": "opentopomap",
        "bounds": [[MAIN[2], MAIN[0]], [MAIN[3], MAIN[1]]],
        "markers": markers,
        "lines": [{"name": "טיסה מדושנבה לג'ירגיטל (קו ישר, סכמטי)", "coords": [[round(d_lat, 6), round(d_lon, 6)], [round(j_lat, 6), round(j_lon, 6)]],
                   "source": "Route as told in a10-p008; straight line between the OSM points, not the flight path"},
                  {"name": "מסוק מג'ירגיטל למחנה הבסיס (קו ישר, סכמטי)", "coords": [[round(j_lat, 6), round(j_lon, 6)], [round(b_lat, 6), round(b_lon, 6)]],
                   "source": "Route as told in a10-p008 and a10-p010; straight line between the OSM points"}],
        "attribution": [OSM_CREDIT, OTM_CREDIT],
        "note": ("Places from OpenStreetMap (element IDs in each marker source). The book gives heights that differ from "
                 "OSM; the map shows no heights. The static EPUB image (replacements/p066-x251-open-map.png, "
                 "scripts/pamir_map.py) adds Copernicus DEM relief and Natural Earth borders. " + dem_credit(90, 30) + "."),
    })


if __name__ == "__main__":
    main()
