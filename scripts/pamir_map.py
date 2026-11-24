# /// script
# requires-python = ">=3.15"
# dependencies = ["matplotlib==3.11.2"]
# ///
"""Draw the open replacement for the disaster-area map on PDF page 66 (image p066-x251).

The printed map looks like a Google Maps screenshot without attribution, so the release edition uses this map.
Data: Natural Earth v5.1.2, public domain (https://www.naturalearthdata.com/about/terms-of-use/).
Lenin Peak: Wikidata Q838587, 39.343677 N, 72.877897 E. The article names the peak and the Pamir range.

Usage: uv run scripts/pamir_map.py
Writes replacements/p066-x251-open-map.png and prints the SHA-256 of each data file.
"""

import hashlib
import json
import math
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "work" / "natural-earth"
OUT = ROOT / "replacements" / "p066-x251-open-map.png"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
FILES = ("ne_50m_admin_0_countries.geojson", "ne_50m_lakes.geojson", "ne_50m_rivers_lake_centerlines.geojson",
         "ne_50m_populated_places_simple.geojson")

WEST, EAST, SOUTH, NORTH = 63.0, 78.5, 33.0, 43.2
LENIN_PEAK = (72.877897, 39.343677)
# Hebrew country names, placed by hand inside each country within the map frame.
COUNTRIES = {"TJK": ("טג'יקיסטן", 70.6, 38.25), "KGZ": ("קירגיזסטן", 74.6, 41.5), "UZB": ("אוזבקיסטן", 65.4, 41.4),
             "AFG": ("אפגניסטן", 66.2, 34.3), "CHN": ("סין", 77.3, 38.6), "PAK": ("פקיסטן", 71.0, 33.5),
             "KAZ": ("קזחסטן", 69.0, 42.85), "TKM": ("טורקמניסטן", 64.4, 38.0)}
CITIES = {"Dushanbe": "דושנבה", "Tashkent": "טשקנט", "Kabul": "קאבול"}


def fetch(name: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if not path.exists():
        with urllib.request.urlopen(NE + name, timeout=120) as r:
            path.write_bytes(r.read())
    data = path.read_bytes()
    print(f"{name} sha256={hashlib.sha256(data).hexdigest()}")
    return json.loads(data)


def rings(geom: dict) -> list[list[list[float]]]:
    match geom["type"]:
        case "Polygon":
            return geom["coordinates"]
        case "MultiPolygon":
            return [ring for poly in geom["coordinates"] for ring in poly]
        case "LineString":
            return [geom["coordinates"]]
        case "MultiLineString":
            return geom["coordinates"]
    raise ValueError(f"unexpected geometry {geom['type']}")


def main() -> None:
    countries, lakes, rivers, places = (fetch(n) for n in FILES)
    for name in ("NotoSansHebrew-Regular.ttf", "NotoSansHebrew-Bold.ttf"):
        font_manager.fontManager.addfont(ROOT / "fonts" / name)
    # Noto Sans Hebrew has no digits or punctuation; DejaVu Sans (bundled with Matplotlib) draws those.
    font = font_manager.FontProperties(family=["Noto Sans Hebrew", "DejaVu Sans"])
    bold = font_manager.FontProperties(family=["Noto Sans Hebrew", "DejaVu Sans"], weight="bold")
    aspect = 1 / math.cos(math.radians((SOUTH + NORTH) / 2))  # Plate carrée stretched to true shape at mid-latitude.
    fig, ax = plt.subplots(figsize=(8, 8 * (NORTH - SOUTH) * aspect / (EAST - WEST)), dpi=200)
    ax.set_xlim(WEST, EAST)
    ax.set_ylim(SOUTH, NORTH)
    ax.set_aspect(aspect)
    ax.set_axis_off()
    fig.subplots_adjust(0, 0, 1, 1)
    ax.add_patch(plt.Rectangle((WEST, SOUTH), EAST - WEST, NORTH - SOUTH, color="#dfe7ec", zorder=0))
    for feat in countries["features"]:
        code = feat["properties"]["ADM0_A3"]
        fill = "#f4e7cf" if code == "TJK" else "#f3f1ec"
        for ring in rings(feat["geometry"]):
            xs, ys = zip(*ring)
            ax.fill(xs, ys, color=fill, zorder=1)
            ax.plot(xs, ys, color="#8b8478", linewidth=0.7, zorder=3)
    for feat in rivers["features"]:
        for line in rings(feat["geometry"]):
            xs, ys = zip(*line)
            ax.plot(xs, ys, color="#9ab6c6", linewidth=0.6, zorder=2)
    for feat in lakes["features"]:
        for ring in rings(feat["geometry"]):
            xs, ys = zip(*ring)
            ax.fill(xs, ys, color="#bcd2df", zorder=2)
    for name, x, y in COUNTRIES.values():
        ax.text(x, y, name, fontproperties=bold, fontsize=11, color="#6b6357", ha="center", va="center", zorder=4)
    found = set()
    for feat in places["features"]:
        name = feat["properties"]["name"]
        if name in CITIES and feat["properties"]["adm0_a3"] in COUNTRIES:
            x, y = feat["geometry"]["coordinates"]
            found.add(name)
            ax.plot(x, y, "o", markersize=4, color="#2b2722", zorder=5)
            ax.text(x, y - 0.32, CITIES[name], fontproperties=font, fontsize=10, color="#2b2722", ha="center", va="top", zorder=5)
    if found != set(CITIES):
        raise SystemExit(f"cities not found in Natural Earth: {sorted(set(CITIES) - found)}")
    x, y = LENIN_PEAK
    ax.plot(x, y, "^", markersize=11, color="#b3261e", markeredgecolor="white", markeredgewidth=1.2, zorder=6)
    ax.text(x, y + 0.33, "פסגת לנין, רכס פאמיר", fontproperties=bold, fontsize=11, color="#b3261e", ha="center", va="bottom", zorder=6)
    # Scale bar: 200 km at the bar's latitude.
    lat = SOUTH + 0.55
    km = 200
    deg = km / (111.32 * math.cos(math.radians(lat)))
    x0 = EAST - 0.6 - deg
    ax.plot([x0, x0 + deg], [lat, lat], color="#2b2722", linewidth=2, zorder=6)
    ax.text(x0 + deg / 2, lat + 0.15, f"{km} ק\"מ", fontproperties=font, fontsize=9, color="#2b2722", ha="center", va="bottom", zorder=6)
    ax.text(WEST + 0.15, SOUTH + 0.12, "Data: Natural Earth (public domain)", fontsize=7, color="#6b6357", ha="left", va="bottom", zorder=6)
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=200, metadata={"Software": None})
    print(f"wrote {OUT.relative_to(ROOT)} sha256={hashlib.sha256(OUT.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
