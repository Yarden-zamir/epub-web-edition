# /// script
# requires-python = ">=3.15"
# dependencies = ["matplotlib==3.11.2", "numpy==2.5.4", "Pillow==13.0.0", "scipy==1.18.1"]
# ///
"""Draw a modern topographic map of Sela for the web tab of the printed map fig-a17-02 (PDF page 147, image p147-x583).

The printed map (credit "באדיבות איתי חביב") stays the default view. This map covers the same ground, north up,
at the same scale, with 100 m contours like the print, so the reader can switch tabs and compare.

Alignment: a fit of the printed image to modern data. The script fits shift, scale and rotation so that
(1) the OSM King's Highway lies on the thick printed road and (2) the DEM contours 700-1,200 m lie on the thin printed
lines. It prints the fit and the residuals. The modern map uses the fitted centre and scale, north up.

Data:
- Heights, contours, relief and wadi lines: Copernicus DEM GLO-30, free licence; notice in map_common.DEM_NOTICE[30].
- Roads, streets, the village and the ruins of the old village: OpenStreetMap via Overpass, ODbL. Element IDs below.
- Fortress: OSM node 798883031 "خربة السلع" (tags wikidata=Q489724, wikipedia=en:Sela (Edom)); Wikidata Q126824792
  (castle) lies 50 m from it.
- Labels: the names of the printed map and of chapter a17 (a17-p012). Wadi labels stand at the printed label
  positions (moved through the fit), on the nearest DEM valley line.
Not shown: Mit Dlib (מית דליב), because no modern source gives its position.

Usage: uv run scripts/sela_topo.py (after a build: it reads the printed image from epub-src-release/).
Writes site/media/sela-topo/fig-a17-02-modern.webp and site/figure-maps/fig-a17-02.json.
"""

import hashlib
import heapq
import io
import itertools
import json
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.patches import FancyArrow, Polygon  # noqa: E402
from PIL import Image  # noqa: E402
from scipy import ndimage, optimize  # noqa: E402

from map_common import (DEM_NOTICE, OSM_COPYRIGHT_URL, ROOT, dem, halo, hebrew_fonts, hillshade,  # noqa: E402
                        image_credit, osm_element, osm_line, osm_point, overpass, write_spec)

FIGURE = "fig-a17-02"
PRINT = ROOT / "epub-src-release" / "OEBPS" / "images" / "p147-x583.jpeg"
OUT = ROOT / "site" / "media" / "sela-topo" / f"{FIGURE}-modern.webp"
MAX_BYTES = 400_000

FORTRESS = 798883031  # OSM node, خربة السلع.
VILLAGE = 798883086  # OSM node, السلع (Wikidata Q489724 gives the same point).
OLD_VILLAGE = 360854822  # OSM way, historic=archaeological_site at the village: the hatched area of the print.
BOX = (35.54, 35.62, 30.75, 30.81)  # (west, east, south, north): data box, larger than the map.
QUERY = f"""[out:json][timeout:120];
(way["highway"~"^(primary|secondary|tertiary|unclassified|residential|service|track)$"]({BOX[2]},{BOX[0]},{BOX[3]},{BOX[1]});
 node(id:{FORTRESS},{VILLAGE}); way(id:{OLD_VILLAGE}););
out geom tags;"""

# The printed image: its frame lines (pixels), the scale bar (500 m) and the fortress dot "879".
PRINT_SIZE = (709, 701)
PRINT_FRAME = (8, 9.5, 699, 693.5)  # left, top, right, bottom
PRINT_BAR_PX = 98  # x 580.5 to 678.5
PRINT_DOT = (189.70, 359.45)
# Label anchors on the print (pixels): the wadi names with their text angle, the road name, the arrow to Tafila.
PRINT_LABELS = {"ואדי חבס": ((395, 320), 0), "ואדי אל־הרש": ((125, 487), 12)}
PRINT_ROAD_LABEL = (668, 390)
PRINT_TAFILA = (575, 70)
VALLEY_M2 = 300_000  # Upstream area of the smallest wadi drawn.

M_LAT = 110_860.0  # Metres per degree at 30.78° N. Limit: a flat local frame; fine for a 4 km map.
M_LON = 111_320 * math.cos(math.radians(30.78))
SCALE_OUT = 2  # Output pixels per print pixel, for sharp screens.

PAPER, INK, MUTED = "#fbf8f2", "#1c1a17", "#625c53"
CONTOUR, CONTOUR_MINOR, WATER, SITE = "#7a5a3a", "#cdb89c", "#2b7f86", "#8f3f22"


def frame_points(element: dict, lat0: float, lon0: float) -> np.ndarray:
    """Metres east and north of (lat0, lon0) for the points of an Overpass `out geom` way."""
    return np.array([((lon - lon0) * M_LON, (lat - lat0) * M_LAT) for lon, lat in osm_line(element)])


def to_print(east: np.ndarray, north: np.ndarray, fit: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Metres east and north of the fortress node -> print pixels, for a fit (dx, dy, metres per pixel, rotation°)."""
    dx, dy, scale, rot = fit
    r = math.radians(rot)
    x = (east * math.cos(r) - north * math.sin(r)) / scale
    y = -(east * math.sin(r) + north * math.cos(r)) / scale
    return x + PRINT_DOT[0] + dx, y + PRINT_DOT[1] + dy


def from_print(x: float, y: float, fit: np.ndarray) -> tuple[float, float]:
    """Print pixel -> metres east and north of the fortress node (inverse of to_print)."""
    dx, dy, scale, rot = fit
    u, v = (x - PRINT_DOT[0] - dx) * scale, -(y - PRINT_DOT[1] - dy) * scale
    r = math.radians(rot)
    return u * math.cos(r) + v * math.sin(r), -u * math.sin(r) + v * math.cos(r)


def densify(line: np.ndarray, step: float = 10) -> np.ndarray:
    out = [line[0]]
    for p, q in zip(line, line[1:]):
        n = max(1, int(np.hypot(*(q - p)) / step))
        out += [p + (q - p) * k / n for k in range(1, n + 1)]
    return np.array(out)


def fit_print(road: np.ndarray, contours: np.ndarray) -> tuple[np.ndarray, dict]:
    """Fit the print to the King's Highway (thick lines) and the DEM contours (thin lines); return the fit and residuals."""
    a = np.asarray(Image.open(PRINT).convert("L")).astype(int)
    if a.shape[::-1] != PRINT_SIZE:
        raise SystemExit(f"{PRINT.name}: size {a.shape[::-1]}, expected {PRINT_SIZE}")
    dark = a < 110
    thick = ndimage.binary_opening(dark, structure=np.ones((4, 4)))  # Lines at least 4 px wide: the roads.
    thin = dark & ~ndimage.binary_dilation(thick, iterations=2)
    left, top, right, bottom = PRINT_FRAME
    for mask in (thick, thin):  # Keep the inside of the frame, without the scale bar and the north arrow.
        mask[:, : int(left) + 4] = mask[:, int(right) - 4:] = False
        mask[: int(top) + 4, :] = mask[int(bottom) - 4:, :] = False
        mask[:60, 560:] = False
    road_dist = ndimage.distance_transform_edt(~thick)
    line_dist = ndimage.distance_transform_edt(~thin)

    def distances(points, dist, fit):
        x, y = to_print(points[:, 0], points[:, 1], fit)
        inside = (x > left + 6) & (x < right - 6) & (y > top + 6) & (y < bottom - 6) & ~((y < 60) & (x > 560))
        return ndimage.map_coordinates(dist, [y[inside], x[inside]], order=1)

    def cost(fit):
        d_road, d_line = distances(road, road_dist, fit), distances(contours, line_dist, fit)
        if len(d_road) < 50 or len(d_line) < 200:
            return 1e9
        # Capped: a point far from any printed line (a modern road change, a label gap) counts no more than the cap.
        return np.mean(np.minimum(d_road, 25) ** 2) + np.mean(np.minimum(d_line, 15) ** 2)

    starts = sorted(itertools.product(range(-40, 41, 4), range(-40, 41, 4), (4.9, 5.1, 5.3), (-3, 0, 3)),
                    key=lambda v: cost(np.array(v, dtype=float)))[:6]
    best = None
    for v0 in starts:
        simplex = [v0, *[np.add(v0, d) for d in ([3, 0, 0, 0], [0, 3, 0, 0], [0, 0, 0.15, 0], [0, 0, 0, 1.5])]]
        r = optimize.minimize(cost, v0, method="Nelder-Mead",
                              options={"initial_simplex": np.array(simplex, dtype=float), "xatol": 0.02, "fatol": 0.005, "maxiter": 4000})
        if best is None or r.fun < best.fun:
            best = r
    fit = best.x
    d_road, d_line = distances(road, road_dist, fit), distances(contours, line_dist, fit)
    m = fit[2]
    residuals = {
        "road_m": {"median": round(float(np.median(d_road)) * m), "p90": round(float(np.percentile(d_road, 90)) * m)},
        "contours_m": {"median": round(float(np.median(d_line)) * m), "p90": round(float(np.percentile(d_line, 90)) * m)},
    }
    print(f"fit: shift {fit[0]:.1f}, {fit[1]:.1f} px; {m:.3f} m/px (scale bar {500 / PRINT_BAR_PX:.3f}); rotation {fit[3]:.2f}°; {residuals}")
    return fit, residuals


def filled(z: np.ndarray) -> np.ndarray:
    """Priority-flood: raise each pit to its spill height, so that every cell drains to the edge."""
    rows, cols = z.shape
    out = z.copy()
    done = np.zeros(z.shape, bool)
    heap = []
    for r in range(rows):
        for c in range(cols):
            if r in (0, rows - 1) or c in (0, cols - 1):
                heapq.heappush(heap, (out[r, c], r, c))
                done[r, c] = True
    while heap:
        h, r, c = heapq.heappop(heap)
        for dr, dc in itertools.product((-1, 0, 1), repeat=2):
            rr, cc = r + dr, c + dc
            if 0 <= rr < rows and 0 <= cc < cols and not done[rr, cc]:
                done[rr, cc] = True
                out[rr, cc] = max(out[rr, cc], h + 1e-3)
                heapq.heappush(heap, (out[rr, cc], rr, cc))
    return out


def drainage(z: np.ndarray, cell: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    """D8 flow: for each cell the index of its steepest downhill neighbour (-1 at the edge), and the upstream area in m²."""
    rows, cols = z.shape
    zf = filled(z)
    down = np.full(z.size, -1)
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            best, target = 0.0, -1
            for dr, dc in itertools.product((-1, 0, 1), repeat=2):
                if dr or dc:
                    drop = (zf[r, c] - zf[r + dr, c + dc]) / math.hypot(dr * cell[1], dc * cell[0])
                    if drop > best:
                        best, target = drop, (r + dr) * cols + c + dc
            down[r * cols + c] = target
    area = np.full(z.size, cell[0] * cell[1])
    for i in np.argsort(-zf, axis=None):
        if down[i] >= 0:
            area[down[i]] += area[i]
    return down, area


def flow_paths(down: np.ndarray, area: np.ndarray) -> list[list[int]]:
    """Wadi lines as cell index paths: from each valley head down to the edge or to a line drawn before."""
    valley = area >= VALLEY_M2
    fed = np.zeros(area.size, bool)
    for i in np.flatnonzero(valley):
        if down[i] >= 0:
            fed[down[i]] = True
    drawn: set[int] = set()
    paths = []
    for head in sorted(np.flatnonzero(valley & ~fed), key=lambda i: -area[i]):
        path, i = [head], head
        while down[i] >= 0 and i not in drawn:
            drawn.add(i)
            i = down[i]
            path.append(i)
        paths.append(path)
    return paths


def smooth(xy: np.ndarray, window: int = 5) -> np.ndarray:
    """Moving average that keeps both end points, so lines still meet at junctions. Removes the 45° steps of D8."""
    if len(xy) <= window:
        return xy
    kernel = np.ones(window) / window
    out = xy.copy()
    for k in range(2):
        out[window // 2: -(window // 2), k] = np.convolve(xy[:, k], kernel, mode="valid")
    return out


def main() -> None:
    elements = overpass("sela-topo", QUERY)
    fortress = osm_element(elements, "node", FORTRESS)
    lat0, lon0 = osm_point(fortress)
    roads = [e for e in elements if e["type"] == "way" and "highway" in e.get("tags", {})]
    kings = [frame_points(w, lat0, lon0) for w in roads if w["tags"].get("ref") == "35"]
    if not kings:
        raise SystemExit("no King's Highway (ref 35) in the Overpass answer")

    west, east, south, north = BOX
    z = dem(west, east, south, north, 30)
    lats = north - (np.arange(z.shape[0]) + 0.5) / 3600
    lons = west + (np.arange(z.shape[1]) + 0.5) / 3600
    gx, gy = np.meshgrid((lons - lon0) * M_LON, (lats - lat0) * M_LAT)  # Metres east and north of the fortress.

    probe = plt.figure()
    cs = probe.add_subplot().contour(gx, gy, z, levels=range(700, 1300, 100))
    contour_points = np.vstack([densify(line) for level in cs.allsegs for line in level if len(line) > 1])
    plt.close(probe)
    fit, residuals = fit_print(np.vstack([densify(line) for line in kings]), contour_points)
    m_per_px = fit[2]

    # The modern map: the ground of the whole printed image, north up, around the fitted centre of the print.
    cx, cy = from_print(PRINT_SIZE[0] / 2, PRINT_SIZE[1] / 2, fit)
    half_w, half_h = PRINT_SIZE[0] * m_per_px / 2, PRINT_SIZE[1] * m_per_px / 2
    extent = (cx - half_w, cx + half_w, cy - half_h, cy + half_h)  # The whole printed image.
    left, top, right, bottom = PRINT_FRAME
    frame = (extent[0] + left * m_per_px, extent[0] + right * m_per_px, extent[3] - bottom * m_per_px, extent[3] - top * m_per_px)

    font, bold = hebrew_fonts()
    w_px, h_px = PRINT_SIZE[0] * SCALE_OUT, PRINT_SIZE[1] * SCALE_OUT
    fig = plt.figure(figsize=(w_px / 200, h_px / 200), dpi=200, facecolor=PAPER)
    # The axes cover the printed frame exactly, so they clip every line at the frame, as the print does.
    ax = fig.add_axes((left / PRINT_SIZE[0], 1 - bottom / PRINT_SIZE[1], (right - left) / PRINT_SIZE[0], (bottom - top) / PRINT_SIZE[1]))
    ax.set_xlim(frame[0], frame[1])
    ax.set_ylim(frame[2], frame[3])
    ax.set_axis_off()
    ax.add_patch(plt.Rectangle((frame[0], frame[2]), frame[1] - frame[0], frame[3] - frame[2], facecolor=PAPER, edgecolor="none", zorder=0))

    # Relief: a soft grey hillshade under everything.
    shade = hillshade(z, south, north, 1 / 3600, exaggeration=1.5)
    rgba = np.zeros((*z.shape, 4))
    rgba[..., 3] = np.clip((0.78 - shade) * 0.4, 0, 0.22)
    half = (M_LON / 7200, M_LAT / 7200)  # Half a cell: imshow extents are cell edges.
    ax.imshow(rgba, extent=(gx[0, 0] - half[0], gx[0, -1] + half[0], gy[-1, 0] - half[1], gy[0, 0] + half[1]),
              interpolation="bilinear", zorder=1)

    # Contours: 20 m thin, 100 m strong with labels; the print draws only the 100 m lines.
    ax.contour(gx, gy, z, levels=[h for h in range(300, 1500, 20) if h % 100], colors=CONTOUR_MINOR, linewidths=0.35, zorder=2)
    major = ax.contour(gx, gy, z, levels=range(300, 1500, 100), colors=CONTOUR, linewidths=0.9, zorder=3)
    for text in ax.clabel(major, levels=range(700, 1300, 100), fmt="%d", fontsize=6.5, inline_spacing=2):
        text.set_color(CONTOUR)

    # Wadis: DEM flow lines that drain at least VALLEY_M2, smoothed, wider downstream.
    down, area = drainage(z, (M_LON / 3600, M_LAT / 3600))
    flat_x, flat_y = gx.ravel(), gy.ravel()
    valley = np.flatnonzero(area >= VALLEY_M2)
    for path in flow_paths(down, area):
        xy = smooth(np.column_stack([flat_x[path], flat_y[path]]))
        widths = [0.6 + 0.4 * min(math.log10(area[i] / VALLEY_M2), 2) for i in path[:-1]]
        ax.add_collection(LineCollection(list(zip(xy[:-1], xy[1:])), colors=WATER, linewidths=widths, capstyle="round", zorder=4))

    # Roads and streets from OSM.
    styles = {"primary": (INK, 2.6), "secondary": (INK, 1.8), "tertiary": (INK, 1.3), "unclassified": (MUTED, 0.8),
              "residential": ("#8a8279", 0.55), "service": ("#8a8279", 0.45), "track": (MUTED, 0.5)}
    for w in roads:
        color, width = styles[w["tags"]["highway"]]
        pts = frame_points(w, lat0, lon0)
        if w["tags"]["highway"] == "primary":
            ax.plot(pts[:, 0], pts[:, 1], color="white", linewidth=width + 1.6, solid_capstyle="round", zorder=5)
        ax.plot(pts[:, 0], pts[:, 1], color=color, linewidth=width, solid_capstyle="round", zorder=6,
                linestyle=(0, (2, 1.5)) if w["tags"]["highway"] == "track" else "-")

    # The old village (hatched, as in the print), the village and the fortress.
    old = frame_points(osm_element(elements, "way", OLD_VILLAGE), lat0, lon0)
    ax.add_patch(Polygon(old, closed=True, facecolor="none", edgecolor=SITE, hatch="/////", linewidth=1, zorder=7))
    v_lat, v_lon = osm_point(osm_element(elements, "node", VILLAGE))
    vx, vy = (v_lon - lon0) * M_LON, (v_lat - lat0) * M_LAT
    summit = np.unravel_index(np.argmax(np.where(np.hypot(gx, gy) < 250, z, -1)), z.shape)
    summit_m = round(float(z[summit]))
    ax.plot([0], [0], "o", markersize=5, color=INK, markeredgecolor="white", markeredgewidth=1, zorder=8)

    def label(x, y, text, prop, size, color=INK, angle=0, ha="center", va="center"):
        ax.text(x, y, text, fontproperties=prop, fontsize=size, color=color, rotation=angle, ha=ha, va=va,
                rotation_mode="anchor", path_effects=halo(2.5, PAPER), zorder=9)

    label(0, -55, "קלעת סלע", bold, 10, va="top")
    label(55, 0, f"{summit_m}", font, 8, ha="left")
    label(vx + 25, vy - 120, "א־סלע", bold, 9.5)
    for text, ((px, py), angle) in PRINT_LABELS.items():
        ex, ny = from_print(px, py, fit)
        near = valley[np.argmin(np.hypot(flat_x[valley] - ex, flat_y[valley] - ny))]
        label(flat_x[near], flat_y[near] + 45, text, font, 8.5, WATER, angle)
    label(*from_print(*PRINT_ROAD_LABEL, fit), "דרך המלך", font, 8.5, angle=-90)

    # Map furniture where the print has it: scale bar of 500 m and north arrow at the top right, Tafila at the top.
    bar_right = extent[0] + 678.5 * m_per_px
    bar_y = extent[3] - 24 * m_per_px
    ax.plot([bar_right - 500, bar_right], [bar_y, bar_y], color=INK, linewidth=1.2, zorder=10)
    for x in (bar_right - 500, bar_right):
        ax.plot([x, x], [bar_y, bar_y + 25], color=INK, linewidth=1.2, zorder=10)
    label(bar_right - 250, bar_y - 30, "500 מ'", font, 7.5, va="top")
    arrow_x = extent[0] + 688 * m_per_px
    ax.add_patch(FancyArrow(arrow_x, bar_y - 330, 0, 240, width=5, head_width=40, head_length=60, color=INK, zorder=10))
    label(arrow_x - 45, bar_y - 230, "צ", bold, 8)
    tx, ty = from_print(*PRINT_TAFILA, fit)
    ax.annotate("", xy=(tx - 90, ty + 120), xytext=(tx, ty), zorder=10,
                arrowprops={"arrowstyle": "-|>", "color": INK, "linewidth": 1.1, "mutation_scale": 10})
    label(tx + 20, ty - 20, "לטפילה", font, 8, ha="left", va="top")
    ax.add_patch(plt.Rectangle((frame[0], frame[2]), frame[1] - frame[0], frame[3] - frame[2], facecolor="none",
                               edgecolor=INK, linewidth=2.2, zorder=11))  # Half of the line falls outside the axes.

    image_credit(fig, x=(left + 4) / PRINT_SIZE[0], y=(PRINT_SIZE[1] - bottom + 3) / PRINT_SIZE[1])
    buffer = io.BytesIO()
    fig.savefig(buffer, dpi=200, format="png", facecolor=PAPER)
    plt.close(fig)
    image = Image.open(buffer).convert("RGB")
    if image.size != (w_px, h_px):
        raise SystemExit(f"rendered {image.size}, expected {(w_px, h_px)}")
    for quality in range(80, 49, -5):
        out = io.BytesIO()
        image.save(out, "WEBP", quality=quality, method=6)
        if out.tell() <= MAX_BYTES:
            break
    else:
        raise SystemExit(f"{OUT.name}: over {MAX_BYTES} bytes even at quality 50")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(out.getvalue())
    print(f"wrote {OUT.relative_to(ROOT)} {w_px}x{h_px} quality={quality} bytes={out.tell()} "
          f"sha256={hashlib.sha256(out.getvalue()).hexdigest()}")

    def lat_lon(x, y):
        return [round(lat0 + y / M_LAT, 6), round(lon0 + x / M_LON, 6)]

    write_spec(FIGURE, {
        "title": "מפה טופוגרפית עדכנית של סלע",
        "tab": "מפה עדכנית",
        "image": f"site/{OUT.relative_to(ROOT / 'site')}",
        "width": w_px, "height": h_px, "bytes": out.tell(),
        "alt": (f"מפה טופוגרפית עדכנית, צפון למעלה, באותו שטח ובאותו קנה מידה של המפה המודפסת: קווי גובה כל 100 מטר, "
                f"קלעת סלע ({summit_m} מ'), הכפר א־סלע ושרידי הכפר הישן, ואדי חבס וואדי אל־הרש, דרך המלך ורחובות "
                f"הכפרים שמצפון־מזרח, וקנה מידה של 500 מטר."),
        "bounds": [lat_lon(extent[0], extent[2]), lat_lon(extent[1], extent[3])],
        "attribution": ["Modern map drawn for this edition. Roads and places: © OpenStreetMap contributors (ODbL)",
                        f"Contours, relief and wadis: {DEM_NOTICE[30]}"],
        "attribution_links": {"OpenStreetMap": OSM_COPYRIGHT_URL},
        "sources": {
            "fortress": f"OSM node {FORTRESS} (wikidata=Q489724); Wikidata Q126824792 (castle) lies 50 m away",
            "village": f"OSM node {VILLAGE}; Wikidata Q489724",
            "old_village": f"OSM way {OLD_VILLAGE}, historic=archaeological_site",
            "summit_height": f"{summit_m} m: highest GLO-30 cell within 250 m of the fortress node (the print gives 879 m)",
            "labels": "Names from the printed map and a17-p012; wadi labels at the printed label positions, on the nearest DEM valley line",
        },
        "note": (f"scripts/sela_topo.py. North up. Fit of the printed image to the OSM King's Highway and the DEM contours "
                 f"700-1,200 m: {m_per_px:.3f} m per printed pixel (the printed scale bar gives {500 / PRINT_BAR_PX:.3f}), "
                 f"rotation {fit[3]:.2f}°, residuals {residuals}. Not shown: Mit Dlib, which has no modern source."),
    })


if __name__ == "__main__":
    main()
