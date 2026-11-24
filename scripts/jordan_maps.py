# /// script
# requires-python = ">=3.15"
# dependencies = ["matplotlib==3.11.2", "numpy==2.5.4", "Pillow==13.0.0"]
# ///
"""Draw open maps for the two withheld figures in chapter a36 (PDF pages 301 and 302).

fig-a36-09 (p301-x1169): new schematic map of the eastern Red Sea – Dead Sea conveyance (RD), drawn from the
book text, not the authors' figure (Bein et al. 2020). The text gives: water from Aqaba (a36-p045) along the
Jordanian side of the Arava (a36-p044: all of it inside Jordan), a desalination plant near the Dead Sea
(a36-p045), mixed seawater and brine to the Dead Sea, desalinated water to the Amman area (fig-a36-09 caption).
The text gives no alignment and no plant site, so the map draws schematic lines and an approximate plant zone.

fig-a36-10 (p302-x1173): new perspective relief view of the Jordanian plateau, looking north-east (caption), with
the Desert Highway (Highway 15) and the King's Highway (Highway 35) from OSM and an arrow toward Amman.
The Disi–Amman pipeline runs in the right-of-way of the Desert Highway from Al Jiza to Jurf al-Darawish:
Consolidated Consultants, Environmental and Social Assessment, Disi-Mudawarra to Amman Water Conveyance System,
Part C Final Report vol. 1 (2008), section 3.1 segment B and section 3.3.3.5,
https://www.dfc.gov/sites/default/files/esia/2008/ammanwater/Part%20C%20-Final%20Report-Vol1.pdf
The alternative routes ALT-1 to ALT-4 in the printed image have no open source, so the view leaves them out.

Data: Copernicus DEM GLO-90 (map_common.dem_credit), OpenStreetMap via Overpass (ODbL),
Natural Earth v5.1.2 borders (public domain).

Usage: uv run scripts/jordan_maps.py
Writes replacements/p301-x1169-open-map.png, replacements/p302-x1173-open-view.png and
site/figure-maps/fig-a36-09.json, site/figure-maps/fig-a36-10.json.
"""

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch  # noqa: E402
from matplotlib.path import Path as PolyPath  # noqa: E402

from map_common import (DEM_PIXELS_PER_DEGREE, NE_CREDIT, OSM_CREDIT, OTM_CREDIT, ROOT, credit_text, dem,  # noqa: E402
                        dem_credit, halo, hebrew_fonts, hillshade, km_per_degree_lon, natural_earth, osm_element,
                        osm_line, osm_point, osm_rings, overpass, relief, rings, save_png, write_spec)

MAP_OUT = ROOT / "replacements" / "p301-x1169-open-map.png"
VIEW_OUT = ROOT / "replacements" / "p302-x1173-open-view.png"
DISI_SOURCE = ("Consolidated Consultants, ESA Disi-Mudawarra to Amman Water Conveyance System, Part C Final Report "
               "vol. 1 (2008), sections 3.1 and 3.3.3.5: the pipeline runs in the Desert Highway right-of-way "
               "from Al Jiza to Jurf al-Darawish")

# key: (OSM node id, Wikidata id or None, Hebrew label)
PLACES = {
    "eilat": (27132996, "Q134762", "אילת"),
    "jerusalem": (29090735, "Q1218", "ירושלים"),
    "aqaba": (798842911, "Q180522", "עקבה"),
    "amman": (1643504896, "Q3805", "עמאן"),
    "karak": (798877241, "Q31572", "כרכ"),
    "tafila": (798885889, "Q2550996", "טפילה"),
    "safi": (425777095, None, "א־צאפי"),
    "qatrana": (798875734, None, "קטרנה"),
    "hasa": (9205489035, None, "אל־חסא"),
    "jurf": (802946184, None, "ג'ורף"),
}
DEAD_SEA = 9351124  # OSM relation, Wikidata Q23883.
PLACES_QUERY = f"node(id:{','.join(str(v[0]) for v in PLACES.values())});\nout body;"
WATER_QUERY = f"""[out:json][timeout:180];
(relation({DEAD_SEA}); way["landuse"="salt_pond"](30.85,35.3,31.3,35.65););
out geom;"""
ROADS_QUERY = """[out:json][timeout:180];
way["highway"~"^(motorway|trunk|primary)$"]["ref"~"(^|;)(15|35)(;|$)"](30.5,35.3,32.05,36.4);
out geom;"""

STOPS = [(-430, "#d4dfc2"), (-200, "#dfe3c4"), (0, "#ece4c8"), (500, "#e6cfa6"), (1000, "#d4b890"), (1700, "#bf9f78")]
INK, ACCENT, SEA_LINE, MIX, DESAL, KINGS = "#1c1a17", "#8f3f22", "#0e4840", "#2b7f86", "#8f3f22", "#6a3fa0"
SEA, LAKE, POND = "#bcd3df", "#8db5cc", "#a9cbdc"


def axes_frame(ax, frame) -> None:
    west, east, south, north = frame
    ax.set_xlim(west, east)
    ax.set_ylim(south, north)
    ax.set_aspect(1 / math.cos(math.radians((south + north) / 2)))
    ax.set_xticks([])
    ax.set_yticks([])


def join_ways(lines: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Join ways that share end nodes into longer chains; at a junction the first match wins."""
    pieces = [list(line) for line in lines]
    chains = []
    while pieces:
        chain = pieces.pop(0)
        grown = True
        while grown:
            grown = False
            for piece in pieces:
                if piece[0] == chain[-1] or piece[-1] == chain[-1]:
                    chain += (piece if piece[0] == chain[-1] else piece[::-1])[1:]
                elif piece[-1] == chain[0] or piece[0] == chain[0]:
                    chain[:0] = (piece if piece[-1] == chain[0] else piece[::-1])[:-1]
                else:
                    continue
                pieces.remove(piece)
                grown = True
                break
        chains.append(chain)
    return chains


def road_lines(roads: list[dict], ref: str) -> list[list[tuple[float, float]]]:
    """(lon, lat) lines of OSM ways whose ref list holds `ref`; link roads excluded by the query."""
    return [osm_line(w) for w in roads if ref in w["tags"]["ref"].split(";")]


def offset_east(line: list[tuple[float, float]], km: float) -> list[tuple[float, float]]:
    return [(lon + km / km_per_degree_lon(lat), lat) for lon, lat in line]


def arava_border(countries: dict) -> list[tuple[float, float]]:
    """Jordan's western border in the Arava, south to north, from Natural Earth 10m."""
    jordan = next(f for f in countries["features"] if f["properties"]["ADM0_A3"] == "JOR")
    points = [(lon, lat) for ring in rings(jordan["geometry"]) for lon, lat in ring
              if 29.53 <= lat <= 31.0 and lon < 35.6]
    if len(points) < 10:
        raise SystemExit("Arava border not found in Natural Earth")
    return sorted(set(points), key=lambda p: p[1])


def conveyance_map(font, bold, coords, water, countries) -> dict:
    frame = (34.35, 36.55, 29.3, 32.05)
    west, east, south, north = frame
    ratio = (north - south) / ((east - west) * math.cos(math.radians((south + north) / 2)))
    fig = plt.figure(figsize=(8, 8 * ratio), dpi=200)
    ax = fig.add_axes((0, 0, 1, 1))
    z = dem(west, east, south, north)[::2, ::2]
    shade = hillshade(z, south, north, 2 / DEM_PIXELS_PER_DEGREE[90])
    rgb = relief(z, shade, STOPS)
    rgb[z == 0] = [int(SEA[i:i + 2], 16) / 255 for i in (1, 3, 5)]  # Copernicus DEM sets open sea to exactly 0 m.
    ax.imshow(rgb, extent=frame, origin="upper", interpolation="antialiased", zorder=0)
    axes_frame(ax, frame)
    for element in water:
        color = LAKE if element["type"] == "relation" else POND
        for ring in osm_rings(element):
            ax.fill(*zip(*ring), color=color, linewidth=0, zorder=1)
    for feat in countries["features"]:
        if feat["properties"]["ADM0_A3"] in ("ISR", "JOR", "EGY", "PSX", "SAU"):
            for ring in rings(feat["geometry"]):
                ax.plot(*zip(*ring), color="white", linewidth=2.6, alpha=0.8, zorder=2)
                ax.plot(*zip(*ring), color="#5c5047", linewidth=1, dashes=(5, 2), zorder=2)

    # Schematic conveyance: seawater 6 km east of the border, plant zone near the Dead Sea, mix and desalinated lines.
    a_lat, a_lon = coords["aqaba"]
    route = [(a_lon, a_lat)] + offset_east(arava_border(countries), 6)
    p_lon, p_lat = route[-1]
    dead_sea = osm_rings(osm_element(water, "relation", DEAD_SEA))
    shore = min((pt for ring in dead_sea for pt in ring), key=lambda pt: math.hypot(
        (pt[0] - p_lon) * math.cos(math.radians(p_lat)), pt[1] - p_lat))
    m_lat, m_lon = coords["amman"]
    ax.plot(*zip(*route), color="white", linewidth=7, solid_capstyle="round", zorder=4)
    ax.plot(*zip(*route), color=SEA_LINE, linewidth=4, solid_capstyle="round", zorder=4)
    ax.plot([p_lon, shore[0]], [p_lat, shore[1]], color=MIX, linewidth=7, solid_capstyle="round", zorder=4,
            path_effects=halo(10))
    ax.plot([p_lon, shore[0]], [p_lat, shore[1]], color="white", linewidth=2, zorder=4)
    ax.plot([p_lon, m_lon], [p_lat, m_lat], color=DESAL, linewidth=3.5, dashes=(4, 2.5), zorder=4, path_effects=halo(6))
    zone_km = 8
    ax.add_patch(Circle((p_lon, p_lat), zone_km / 110.57, transform=ax.transData, facecolor="#ffffff99", edgecolor=ACCENT,
                        linewidth=2, linestyle=(0, (3, 2)), zorder=5))
    ax.plot(p_lon, p_lat, "o", markersize=9, color=ACCENT, markeredgecolor="white", markeredgewidth=1.5, zorder=6)
    ax.text(p_lon + 0.1, p_lat - 0.02, "מתקן התפלה\n(מיקום משוער)", fontproperties=bold, fontsize=10.5, color=ACCENT,
            ha="left", va="center", path_effects=halo(3.5), zorder=7, linespacing=1.2)

    for key in ("jerusalem", "amman", "eilat", "aqaba"):
        lat, lon = coords[key]
        ax.plot(lon, lat, "o", markersize=7, color=INK, markeredgecolor="white", markeredgewidth=1.5, zorder=6)
        right = key in ("amman", "aqaba")
        ax.text(lon + (0.05 if right else -0.05), lat, PLACES[key][2], fontproperties=bold, fontsize=12, color=INK,
                ha="left" if right else "right", va="center", path_effects=halo(3.5), zorder=7)
    for text, x, y, size, rot, color in (("ירדן", 36.05, 30.45, 22, 0, "#5c4a3a"), ("ישראל", 34.72, 30.75, 16, 0, "#5c4a3a"),
                                         ("מצרים", 34.55, 29.62, 16, 0, "#5c4a3a"), ("ים המלח", 35.33, 31.55, 11, 0, "#24506b"),
                                         ("מפרץ\nאילת", 34.8, 29.36, 10, 0, "#24506b"), ("הערבה", 35.08, 30.4, 12, 64, "#5c4a3a"),
                                         ("הים התיכון", 34.5, 31.85, 10, 0, "#24506b")):
        ax.text(x, y, text, fontproperties=bold, fontsize=size, color=color, rotation=rot, ha="center", va="center",
                path_effects=halo(3.5), zorder=3, linespacing=1.1)
    ax.add_patch(FancyArrowPatch((36.4, 31.75), (36.4, 31.95), arrowstyle="-|>", mutation_scale=18, color=INK, zorder=7))
    ax.text(36.4, 31.73, "צפון", fontproperties=font, fontsize=9, color=INK, ha="center", va="top", path_effects=halo(), zorder=7)
    lat = 29.95
    deg = 50 / km_per_degree_lon(lat)
    ax.plot([34.45, 34.45 + deg], [lat, lat], color=INK, linewidth=3, solid_capstyle="butt", path_effects=halo(5), zorder=7)
    ax.text(34.45 + deg / 2, lat + 0.03, "50 ק\"מ", fontproperties=font, fontsize=10, color=INK, ha="center", va="bottom",
            path_effects=halo(), zorder=7)

    # Legend in the Sinai corner; quantities from the caption of fig-a36-09 (phase A).
    lg = fig.add_axes((0.5, 0.05, 0.48, 0.27))
    lg.set_xlim(0, 1)
    lg.set_ylim(0, 1)
    lg.set_xticks([])
    lg.set_yticks([])
    lg.set_facecolor("#ffffffe6")
    for spine in lg.spines.values():
        spine.set_edgecolor("#8b8478")
    lg.text(0.96, 0.93, "המוביל המזרחי, שלב א' (מתווה סכמטי)", fontproperties=bold, fontsize=11, color=INK, ha="right", va="center")
    rows = [("sea", "מי ים סוף מעקבה: 500 מלמ\"ש"), ("mix", "מי ים ורכז אל ים המלח: 400 מלמ\"ש"),
            ("desal", "מים מותפלים לאזור עמאן: 100 מלמ\"ש"), ("plant", "מתקן התפלה, מיקום משוער")]
    for i, (kind, label) in enumerate(rows):
        y = 0.78 - i * 0.12
        xs = [0.8, 0.95]
        match kind:
            case "sea":
                lg.plot(xs, [y, y], color=SEA_LINE, linewidth=4)
            case "mix":
                lg.plot(xs, [y, y], color=MIX, linewidth=7)
                lg.plot(xs, [y, y], color="white", linewidth=2)
            case "desal":
                lg.plot(xs, [y, y], color=DESAL, linewidth=3.5, dashes=(4, 2.5))
            case "plant":
                lg.plot(0.875, y, "o", markersize=9, color=ACCENT, markeredgecolor="white", markeredgewidth=1.5)
        lg.text(0.76, y, label, fontproperties=font, fontsize=10, color=INK, ha="right", va="center")
    lg.text(0.96, 0.25, "מפה חדשה שצוירה למהדורה זו לפי הטקסט בפרק.\nאינה האיור של ביין וחובריו (2020).\n"
            "התוואי ומיקום המתקן אינם מדויקים.", fontproperties=font, fontsize=8.5, color=INK, ha="right", va="center",
            linespacing=1.35)
    fig.text(0.98, 0.006, credit_text(f"{OSM_CREDIT} · Borders: {NE_CREDIT}", dem_credit(90) + ".", width=88),
             fontsize=5.4, color="#4d463e", ha="right", va="bottom", linespacing=1.3, path_effects=halo(2))
    save_png(fig, MAP_OUT)
    plt.close(fig)

    circle = [[round(p_lat + zone_km / 110.57 * math.sin(t), 5),
               round(p_lon + zone_km / km_per_degree_lon(p_lat) * math.cos(t), 5)]
              for t in np.linspace(0, 2 * math.pi, 25)]
    schematic = "Schematic line drawn for this edition from the book text ({}); not the planned alignment"
    return {
        "title": "המוביל המזרחי מים סוף לים המלח: מתווה סכמטי",
        "base": "opentopomap",
        "bounds": [[south, west], [north, east]],
        "markers": [{"name": PLACES[k][2], "lat": round(coords[k][0], 6), "lon": round(coords[k][1], 6),
                     "wikidata": PLACES[k][1], "source": f"OSM node {PLACES[k][0]} ({OSM_CREDIT})",
                     **({"target": "a36-p045"} if k in ("aqaba", "amman") else {})}
                    for k in ("aqaba", "amman", "eilat", "jerusalem")],
        "lines": [{"name": "מי ים סוף מעקבה: 500 מלמ\"ש (סכמטי)", "coords": [[round(la, 5), round(lo, 5)] for lo, la in route],
                   "source": schematic.format("a36-p044, a36-p045") + "; drawn 6 km east of the Natural Earth border"},
                  {"name": "מי ים ורכז אל ים המלח: 400 מלמ\"ש (סכמטי)",
                   "coords": [[round(p_lat, 5), round(p_lon, 5)], [round(shore[1], 5), round(shore[0], 5)]],
                   "source": schematic.format("a36-p045, fig-a36-09 caption") + "; ends at the nearest OSM shore point"},
                  {"name": "מים מותפלים לאזור עמאן: 100 מלמ\"ש (סכמטי)",
                   "coords": [[round(p_lat, 5), round(p_lon, 5)], [round(m_lat, 6), round(m_lon, 6)]],
                   "source": schematic.format("a36-p045, a36-p048, fig-a36-09 caption")}],
        "areas": [{"name": "מתקן התפלה, מיקום משוער", "coords": circle,
                   "source": "The book says only 'near the Dead Sea' (a36-p045); zone drawn for this edition"}],
        "attribution": [OSM_CREDIT, OTM_CREDIT],
        "note": ("New schematic map drawn for this edition from the text of chapter a36. It is not the figure of Bein et al. "
                 "(2020), which stays withheld. Quantities are phase A from the printed caption. The static EPUB image "
                 "(replacements/p301-x1169-open-map.png, scripts/jordan_maps.py) adds Copernicus DEM relief and "
                 "Natural Earth borders. " + dem_credit(90) + "."),
    }


# View grid: rows run from the near (south-west) edge to the far (north-east) edge, so the camera looks north-east.
VIEW_CENTER = (31.0, 35.72)  # (lat, lon)
VIEW_U = (-48.0, 44.0)  # km toward the south-east, the right side of the view
VIEW_V = (-30.0, 56.0)  # km toward the north-east, into the view
CELL_KM = 0.18
EXAGGERATION = 2.0


class ViewGrid:
    """Maps lon/lat to view coordinates (u right, v into the view, km) and samples the DEM there."""

    def __init__(self) -> None:
        self.lat0, self.lon0 = VIEW_CENTER
        self.kx, self.ky = km_per_degree_lon(self.lat0), 110.57
        corners = [self.lonlat(u, v) for u in VIEW_U for v in VIEW_V]
        margin = 0.02
        self.west = min(c[0] for c in corners) - margin
        self.east = max(c[0] for c in corners) + margin
        self.south = min(c[1] for c in corners) - margin
        self.north = max(c[1] for c in corners) + margin
        self.z = dem(self.west, self.east, self.south, self.north)
        self.shade = hillshade(self.z, self.south, self.north, 1 / DEM_PIXELS_PER_DEGREE[90], azimuth=290, altitude=40)

    def uv(self, lon: float, lat: float) -> tuple[float, float]:
        e, n = (lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky
        return (e - n) / math.sqrt(2), (e + n) / math.sqrt(2)

    def lonlat(self, u, v):
        e, n = (u + v) / math.sqrt(2), (v - u) / math.sqrt(2)
        return self.lon0 + e / self.kx, self.lat0 + n / self.ky

    def index(self, lon, lat):
        rows, cols = self.z.shape
        r = np.clip(np.rint((self.north - lat) * DEM_PIXELS_PER_DEGREE[90]).astype(int), 0, rows - 1)
        c = np.clip(np.rint((lon - self.west) * DEM_PIXELS_PER_DEGREE[90]).astype(int), 0, cols - 1)
        return r, c

    def height(self, lon: float, lat: float) -> float:
        r, c = self.index(np.array(lon), np.array(lat))
        return float(self.z[r, c])

    def inside(self, lon: float, lat: float) -> bool:
        u, v = self.uv(lon, lat)
        return VIEW_U[0] <= u <= VIEW_U[1] and VIEW_V[0] <= v <= VIEW_V[1]

    def xyz(self, lon: float, lat: float, lift: float = 0) -> tuple[float, float, float]:
        u, v = self.uv(lon, lat)
        return u, v, (self.height(lon, lat) + lift) / 1000 * EXAGGERATION


def land_crop(image: np.ndarray, background: tuple[int, int, int]) -> tuple[slice, slice]:
    """Largest axis-aligned crop of a parallel-projection render that holds only land (no background)."""
    land = np.any(image[..., :3] != np.array(background, dtype=image.dtype), axis=-1)
    cols = np.flatnonzero(land.any(axis=0))
    x0, x1 = cols[0] + 3, cols[-1] - 3
    top = np.array([np.flatnonzero(land[:, c])[0] for c in range(x0, x1)])
    bottom = np.array([np.flatnonzero(land[:, c])[-1] for c in range(x0, x1)])
    y0, y1 = top.max() + 2, bottom.min() - 2
    if y1 - y0 < 200 or x1 - x0 < 400:
        raise SystemExit("view crop too small; check the view settings")
    return slice(y0, y1), slice(x0, x1)


def plateau_view(font, bold, coords, water, roads) -> dict:
    grid = ViewGrid()
    us = np.arange(VIEW_U[0], VIEW_U[1] + CELL_KM / 2, CELL_KM)
    vs = np.arange(VIEW_V[0], VIEW_V[1] + CELL_KM / 2, CELL_KM)
    U, V = np.meshgrid(us, vs)
    lon, lat = grid.lonlat(U, V)
    r, c = grid.index(lon, lat)
    z, shade = grid.z[r, c], grid.shade[r, c]
    rgb = relief(z, shade, STOPS, strength=0.7)
    points = np.column_stack([lon.ravel(), lat.ravel()])
    for element in water:  # OSM Dead Sea and evaporation ponds, by point-in-polygon on the grid.
        color = LAKE if element["type"] == "relation" else POND
        for ring in osm_rings(element):
            rgb[PolyPath(ring).contains_points(points).reshape(z.shape)] = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]

    background = (255, 0, 255)
    fig = plt.figure(figsize=(10, 7), dpi=200, facecolor="#ff00ff")
    ax = fig.add_axes((0, 0, 1, 1), projection="3d", computed_zorder=False)
    ax.set_facecolor("#ff00ff")
    ax.plot_surface(U, V, z / 1000 * EXAGGERATION, facecolors=rgb, rstride=1, cstride=1, linewidth=0,
                    antialiased=False, shade=False, zorder=1)
    ax.set_proj_type("ortho")
    ax.view_init(elev=30, azim=-90)
    ax.set_box_aspect((VIEW_U[1] - VIEW_U[0], VIEW_V[1] - VIEW_V[0], float(z.max() - z.min()) / 1000 * EXAGGERATION), zoom=1.8)
    ax.set_axis_off()
    fig.canvas.draw()  # Crop from the bare surface, before labels can stick out of it.
    crop = land_crop(np.asarray(fig.canvas.buffer_rgba()), background)

    def drape(line, color, width, zorder):
        pts = [grid.xyz(lon, lat, 40) for lon, lat in line if grid.inside(lon, lat)]
        if len(pts) >= 2:
            ax.plot(*zip(*pts), color="white", linewidth=width + 2.5, zorder=zorder, solid_capstyle="round")
            ax.plot(*zip(*pts), color=color, linewidth=width, zorder=zorder + 0.1, solid_capstyle="round")

    for line in road_lines(roads, "35"):
        drape(line, KINGS, 2.4, 5)
    for line in road_lines(roads, "15"):
        drape(line, INK, 3, 6)

    def label(lon, lat, text, prop, size, color, lift=250):
        ax.text(*grid.xyz(lon, lat, lift), text, fontproperties=prop, fontsize=size, color=color, ha="center",
                va="bottom", path_effects=halo(3.5), zorder=10)

    for key in ("karak", "tafila", "safi", "qatrana", "hasa"):
        lat, lon = coords[key]
        ax.plot(*[[v] for v in grid.xyz(lon, lat, 40)], "o", markersize=6, color=INK, markeredgecolor="white",
                markeredgewidth=1.3, zorder=9)
        label(lon, lat, PLACES[key][2], bold, 11, INK, lift=200)
    label(36.16, 31.08, "הכביש המדברי (כביש 15)\nולאורכו מוביל דיסי–עמאן", bold, 11, INK, lift=300)
    label(35.67, 31.0, "דרך המלך (כביש 35)", bold, 11, "#4b2a75", lift=300)
    label(35.47, 31.1, "בריכות האידוי\nבדרום ים המלח", bold, 11, "#24506b", lift=60)
    label(35.38, 30.9, "הערבה", bold, 11, "#5c4a3a", lift=60)
    # Arrow toward Amman: north along the Desert Highway from Qatrana, which is near the far edge.
    q_lat, q_lon = coords["qatrana"]
    start = grid.xyz(q_lon - 0.03, q_lat + 0.04, 900)
    end = grid.xyz(q_lon - 0.16, q_lat + 0.15, 900)
    end = (end[0], end[1], start[2])
    ax.quiver(*start, *(e - s for e, s in zip(end, start)), color="#b3261e", linewidth=3, arrow_length_ratio=0.3, zorder=11)
    ax.text(*end, "לעמאן ", fontproperties=bold, fontsize=12, color="#b3261e", ha="right", va="center",
            path_effects=halo(3.5), zorder=11)
    fig.canvas.draw()
    view = np.asarray(fig.canvas.buffer_rgba())[crop].copy()
    plt.close(fig)

    height, width = view.shape[:2]
    out = plt.figure(figsize=(8, 8 * height / width), dpi=200)
    oax = out.add_axes((0, 0, 1, 1))
    oax.imshow(view, interpolation="antialiased")
    oax.set_axis_off()
    box = {"facecolor": "white", "alpha": 0.85, "edgecolor": "none", "boxstyle": "round,pad=0.35"}
    out.text(0.985, 0.97, "מבט חדש שצויר למהדורה זו, לכיוון צפון־מזרח. הגבהים מוגדלים פי 2.", fontproperties=font,
             fontsize=9, color=INK, ha="right", va="top", bbox=box)
    out.text(0.014, 0.014, credit_text(f"Roads: {OSM_CREDIT}", dem_credit(90) + ".", width=110), fontsize=5.2,
             color="#3d3730", ha="left", va="bottom", linespacing=1.3, bbox=box)
    save_png(out, VIEW_OUT)
    plt.close(out)

    frame = (35.35, 36.25, 30.62, 31.42)
    west, east, south, north = frame
    kx, ky = grid.kx, grid.ky

    def web_line(lines, max_lat):
        """Road ways joined into chains, one carriageway kept, points thinned to about 100 m apart."""
        chains = [[[round(lat, 5), round(lon, 5)] for lon, lat in line] for line in join_ways(lines)]
        kept, kept_points = [], np.empty((0, 2))
        for chain in sorted(chains, key=len, reverse=True):
            pts = np.array(chain)
            if len(kept_points):
                near = np.hypot((pts[:, None, 1] - kept_points[None, :, 1]) * kx,
                                (pts[:, None, 0] - kept_points[None, :, 0]) * ky).min(axis=1) < 0.15
                if near.mean() > 0.5:
                    continue  # The other carriageway of a divided road.
            kept.append(chain)
            kept_points = np.vstack([kept_points, pts])
        out = []
        for chain in kept:
            thin = []
            for lat, lon in chain:
                if lat <= max_lat and (not thin or math.hypot((lon - thin[-1][1]) * kx, (lat - thin[-1][0]) * ky) > 0.1):
                    thin.append([lat, lon])
            if len(thin) >= 2:
                out.append(thin)
        return out

    web_south, web_north = 30.62, 32.0
    m_lat, m_lon = coords["amman"]
    return {
        "title": "רמת המדבר הירדני: הכביש המדברי ודרך המלך",
        "base": "opentopomap",
        "bounds": [[web_south, west], [web_north, east]],
        "markers": [{"name": PLACES[k][2], "lat": round(coords[k][0], 6), "lon": round(coords[k][1], 6),
                     **({"wikidata": PLACES[k][1]} if PLACES[k][1] else {}),
                     "source": f"OSM node {PLACES[k][0]} ({OSM_CREDIT})",
                     **({"target": "fig-a36-10"} if k == "amman" else {})}
                    for k in ("amman", "karak", "tafila", "safi", "qatrana", "hasa", "jurf")],
        "lines": ([{"name": "הכביש המדברי (כביש 15); לאורכו מוביל דיסי–עמאן", "coords": c,
                    "source": f"OSM ways tagged ref=15 ({OSM_CREDIT}); pipeline: {DISI_SOURCE}"}
                   for c in web_line(road_lines(roads, "15"), web_north)]
                  + [{"name": "דרך המלך (כביש 35)", "coords": c, "source": f"OSM ways tagged ref=35 ({OSM_CREDIT})"}
                     for c in web_line(road_lines(roads, "35"), north)]),
        "attribution": [OSM_CREDIT, OTM_CREDIT],
        "note": ("New view drawn for this edition; the printed Google Earth image stays withheld. Highways from OSM; "
                 "the King's Highway is shown only in the area of the printed view. The printed alternative routes "
                 "ALT-1 to ALT-4 have no open source and are not shown. Amman is the end of the Desert Highway line "
                 f"(OSM node {PLACES['amman'][0]}). The static EPUB image (replacements/p302-x1173-open-view.png, "
                 "scripts/jordan_maps.py) is a perspective relief view. " + dem_credit(90) + "."),
    }


def main() -> None:
    font, bold = hebrew_fonts()
    places = overpass("jordan-places", "[out:json][timeout:120];\n" + PLACES_QUERY)
    coords = {key: osm_point(osm_element(places, "node", node)) for key, (node, *_rest) in PLACES.items()}
    water = overpass("jordan-water", WATER_QUERY)
    roads = overpass("jordan-roads", ROADS_QUERY)
    countries = natural_earth("ne_10m_admin_0_countries.geojson")
    write_spec("fig-a36-09", conveyance_map(font, bold, coords, water, countries))
    write_spec("fig-a36-10", plateau_view(font, bold, coords, water, roads))


if __name__ == "__main__":
    main()
