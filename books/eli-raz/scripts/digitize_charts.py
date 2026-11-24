# /// script
# requires-python = ">=3.15"
# dependencies = ["pymupdf==1.28.2", "numpy==2.5.4", "pillow==13.0.0"]
# ///
"""Digitize four printed charts into site/charts/<figure-id>.json.

All four charts are raster images in the source PDF (no vector drawings), and no published data table was found.
The script reads each embedded image at its native resolution, calibrates the axes from tick marks
that it detects in the image, extracts curves and points by colour, and writes the data.
It also writes a review overlay per chart to work/charts/<figure-id>-overlay.png:
the digitized data drawn over the printed image at 3x, with the calibration ticks in cyan.

Usage: uv run scripts/digitize_charts.py
The source PDF is only read.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SOURCE_PDF = Path.home() / "private-inputs/eli-raz/source-2026-11-23/source.pdf"
OUT = ROOT / "site" / "charts"
WORK = ROOT / "work" / "charts"
ZOOM = 3  # overlay scale

type Px = tuple[float, float]  # (x, y) in image pixels
type Mask = np.ndarray  # 2-D bool


# ---------- image and calibration helpers ----------


def embedded_image(doc: pymupdf.Document, page_no: int, xref: int) -> np.ndarray:
    """Return the embedded image as an RGB uint8 array, at its native resolution."""
    if xref not in [info["xref"] for info in doc[page_no - 1].get_image_info(xrefs=True)]:
        raise SystemExit(f"image xref {xref} is not on PDF page {page_no}")
    pix = pymupdf.Pixmap(doc, xref)
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    if pix.n != 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).copy()


@dataclass(frozen=True)
class Axis:
    """Map from a pixel coordinate to a data value, fitted to labelled ticks.

    Linear by default. piecewise=True interpolates between neighbouring ticks, for a printed axis
    whose tick spacing drifts smoothly (a distorted drawing); outside the ticks it extends the end segments.
    """

    ticks: list[tuple[float, float]]  # (pixel, value), ordered by pixel
    scale: float
    offset: float
    residual_px: float  # largest distance between a tick and the linear fit
    piecewise: bool

    def value(self, px: float) -> float:
        if self.piecewise:
            return piecewise_linear(px, self.ticks)
        return self.scale * px + self.offset

    def pixel(self, value: float) -> float:
        if self.piecewise:
            return piecewise_linear(value, sorted((v, p) for p, v in self.ticks))
        return (value - self.offset) / self.scale

    @property
    def error_px(self) -> float:
        """Calibration error in pixels: the linear-fit residual, or 1 px of tick detection when piecewise."""
        return 1.0 if self.piecewise else self.residual_px


def piecewise_linear(x: float, knots: list[tuple[float, float]]) -> float:
    """Interpolate through (x, y) knots sorted by x; beyond the ends, extend the first or last segment."""
    i = 0 if x < knots[0][0] else len(knots) - 2 if x > knots[-1][0] else None
    if i is None:
        return float(np.interp(x, *zip(*knots)))
    (x0, y0), (x1, y1) = knots[i], knots[i + 1]
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


def fit_axis(pixels: list[float], values: list[float], max_residual_px: float, piecewise: bool = False) -> Axis:
    if len(pixels) != len(values):
        raise SystemExit(f"found {len(pixels)} ticks, expected {len(values)}: {pixels}")
    scale, offset = np.polyfit(pixels, values, 1)
    residual = max(abs((v - offset) / scale - p) for p, v in zip(pixels, values))
    if residual > max_residual_px:
        raise SystemExit(f"tick fit residual {residual:.1f} px exceeds {max_residual_px} px: {pixels}")
    ticks = sorted((round(p, 1), v) for p, v in zip(pixels, values))
    return Axis(ticks, float(scale), float(offset), round(float(residual), 1), piecewise)


def runs(line: np.ndarray) -> list[tuple[int, int]]:
    """Return (first, last) index of each run of True values."""
    idx = np.flatnonzero(line)
    if idx.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([idx[0]], idx[breaks + 1]))
    ends = np.concatenate((idx[breaks], [idx[-1]]))
    return [(int(s), int(e)) for s, e in zip(starts, ends)]


def peak_centres(profile: np.ndarray, threshold: float, offset: int = 0) -> list[float]:
    """Weighted centre of each run where the profile exceeds the threshold."""
    return [
        offset + float(np.average(np.arange(s, e + 1), weights=profile[s : e + 1]))
        for s, e in runs(profile > threshold)
    ]


def darkness(img: np.ndarray) -> np.ndarray:
    return 255 - img.mean(axis=2)


def erode(mask: Mask, radius: int) -> Mask:
    """Square binary erosion; keeps a pixel only when its whole (2r+1)^2 neighbourhood is set."""
    out = mask.copy()
    h, w = mask.shape
    padded = np.pad(mask, radius)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            out &= padded[radius + dy : radius + dy + h, radius + dx : radius + dx + w]
    return out


def dilate(mask: Mask, radius: int) -> Mask:
    return ~erode(~mask, radius)


def components(mask: Mask) -> list[list[tuple[int, int]]]:
    """8-connected components as lists of (y, x)."""
    seen = np.zeros_like(mask)
    found = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        stack, pixels = [(int(y), int(x))], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            pixels.append((cy, cx))
            for ny in range(cy - 1, cy + 2):
                for nx in range(cx - 1, cx + 2):
                    if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        found.append(pixels)
    return found


def find_dots(dark: Mask, radius: int, min_core: int) -> tuple[list[Px], Mask]:
    """Find filled round markers: blobs that survive an erosion that removes thin lines.

    Returns the dot centres and a mask of the dot pixels (so that curve tracing can skip them).
    Limit: two touching dots count as one dot. Revisit when a chart has dense clusters of markers.
    """
    core = erode(dark, radius)
    centres = []
    for blob in components(core):
        if len(blob) < min_core:
            continue
        ys, xs = zip(*blob)
        centres.append((float(np.mean(xs)), float(np.mean(ys))))
    return centres, dilate(core, radius + 2) & dark


def trace(mask: Mask, x_from: int, min_blob: int = 6, skip_cost: float = 3.0, max_skip: int = 15) -> list[Px]:
    """Follow a thin curve across the columns of a mask, from column x_from to the right edge.

    Each column holds runs of set pixels. The path takes at most one run per column and minimises
    the total vertical jump between consecutive runs, plus skip_cost per skipped column
    (so that the path can step over leftover marks). It considers the whole chart at once,
    so one wrong branch does not derail the rest. Blobs smaller than min_blob pixels are ignored.
    A long run is a steep part of the curve: its near end is emitted first, then its far end.
    Limit: where the curve turns back in x (a loop), only one branch is kept. Check the overlay.
    """
    clean = np.zeros_like(mask)
    for blob in components(mask[:, x_from:]):
        if len(blob) >= min_blob:
            ys, xs = zip(*blob)
            clean[ys, np.array(xs) + x_from] = True
    cols = [(x, runs(clean[:, x])) for x in range(x_from, mask.shape[1])]
    cols = [(x, rs) for x, rs in cols if rs]
    if not cols:
        raise SystemExit("trace: no curve pixels")

    def gap(r1: tuple[int, int], r2: tuple[int, int]) -> float:
        return max(r2[0] - r1[1], r1[0] - r2[1], 0)

    # cost[i][j]: cheapest path that ends on run j of column i; back[i][j]: (column, run) before it.
    first_x = cols[0][0]
    cost = [[skip_cost * (x - first_x) for _ in rs] for x, rs in cols]
    back: list[list[tuple[int, int] | None]] = [[None for _ in rs] for _, rs in cols]
    for i, (x, rs) in enumerate(cols):
        for k in range(i - 1, -1, -1):
            xk, rk = cols[k]
            if x - xk - 1 > max_skip:
                break
            for j, r in enumerate(rs):
                for jk, r_prev in enumerate(rk):
                    c = cost[k][jk] + gap(r_prev, r) + skip_cost * (x - xk - 1)
                    if c < cost[i][j]:
                        cost[i][j], back[i][j] = c, (k, jk)
    last_x = cols[-1][0]
    end = min(
        ((i, j) for i, (x, rs) in enumerate(cols) for j in range(len(rs))),
        key=lambda ij: cost[ij[0]][ij[1]] + skip_cost * (last_x - cols[ij[0]][0]),
    )
    chain = []
    node: tuple[int, int] | None = end
    while node is not None:
        chain.append(node)
        node = back[node[0]][node[1]]
    chain.reverse()

    path: list[Px] = []
    prev = None
    for i, j in chain:
        x, (s, e) = cols[i][0], cols[i][1][j]
        if e - s <= 2:
            path.append((x, (s + e) / 2))
            prev = (s + e) / 2
            continue
        near, far = (s, e) if prev is None or abs(s - prev) <= abs(e - prev) else (e, s)
        path += [(x, float(near)), (x, float(far))]
        prev = far
    return path


def simplify(points: list[Px], tolerance: float) -> list[Px]:
    """Ramer-Douglas-Peucker line simplification, in pixel units."""
    if len(points) < 3:
        return points
    (ax, ay), (bx, by) = points[0], points[-1]
    dx, dy = bx - ax, by - ay
    norm = np.hypot(dx, dy)
    # Distance of each point from the chord a-b (or from a, when the path returns to its start).
    dists = [abs(dx * (py - ay) - dy * (px - ax)) / norm if norm else np.hypot(px - ax, py - ay) for px, py in points[1:-1]]
    i = int(np.argmax(dists)) + 1
    if dists[i - 1] <= tolerance:
        return [points[0], points[-1]]
    return simplify(points[: i + 1], tolerance)[:-1] + simplify(points[i:], tolerance)


def interpolate_y(path: list[Px], x: float) -> float:
    """y of a traced path at x, from the path points around x (the path must be ordered by x)."""
    xs = np.array([p[0] for p in path])
    if not xs[0] <= x <= xs[-1]:
        raise SystemExit(f"x={x:.1f} is outside the traced range {xs[0]}..{xs[-1]}")
    return float(np.interp(x, xs, [p[1] for p in path]))


def rect_mask(shape: tuple[int, ...], rects: list[tuple[int, int, int, int]]) -> Mask:
    """True inside each (x0, y0, x1, y1) rectangle, edges included."""
    m = np.zeros(shape[:2], bool)
    for x0, y0, x1, y1 in rects:
        m[y0 : y1 + 1, x0 : x1 + 1] = True
    return m


# ---------- overlay ----------


class Overlay:
    def __init__(self, img: np.ndarray):
        self.im = Image.fromarray(img).resize((img.shape[1] * ZOOM, img.shape[0] * ZOOM), Image.LANCZOS)
        self.im = Image.blend(self.im, Image.new("RGB", self.im.size, "white"), 0.35)
        self.draw = ImageDraw.Draw(self.im)

    def line(self, pts: list[Px], colour: str, width: int = 2):
        self.draw.line([(x * ZOOM, y * ZOOM) for x, y in pts], fill=colour, width=width)

    def dots(self, pts: list[Px], colour: str, r: int = 5):
        for x, y in pts:
            self.draw.ellipse((x * ZOOM - r, y * ZOOM - r, x * ZOOM + r, y * ZOOM + r), outline=colour, width=2)

    def ticks(self, axis: Axis, vertical: bool, at: float):
        """Mark calibration ticks. vertical=True for a y axis (ticks at rows), at = column (or row)."""
        for p, v in axis.ticks:
            x, y = (at, p) if vertical else (p, at)
            self.draw.line((x * ZOOM - 8, y * ZOOM, x * ZOOM + 8, y * ZOOM), fill="#00b5d8", width=2)
            self.draw.line((x * ZOOM, y * ZOOM - 8, x * ZOOM, y * ZOOM + 8), fill="#00b5d8", width=2)
            self.draw.text((x * ZOOM + 6, y * ZOOM + 4), f"{v:g}", fill="#007a92")

    def save(self, name: str) -> str:
        path = WORK / name
        self.im.save(path)
        return str(path.relative_to(ROOT))


def chart_overlay(img: np.ndarray, chart: dict, x_axis: Axis, y_axis: Axis, frame: tuple[float, float]) -> Overlay:
    """Draw the chart's final JSON values back onto the printed image through the calibration.

    Lines are red, points blue, bands green, markers magenta; calibration ticks cyan.
    frame = (column of the y axis, row of the x axis) for the tick marks.
    """
    ov = Overlay(img)

    def px(point: list[float]) -> Px:
        return x_axis.pixel(point[0]), y_axis.pixel(point[1])

    for series in chart["series"]:
        pts = [px(p) for p in series["points"]]
        if series["kind"] == "line":
            ov.line(pts, "#e00000", 2)
        else:
            ov.dots(pts, "#0050ff", 5)
    h, w = img.shape[:2]
    for band in chart.get("bands", []):
        x0, x1 = x_axis.pixel(band["from"]), x_axis.pixel(band["to"])
        ov.draw.rectangle((x0 * ZOOM, 0, x1 * ZOOM, h * ZOOM), outline="#00a000", width=2)
    for marker in chart.get("markers", []):
        if marker["axis"] == "x":
            ov.line([(x_axis.pixel(marker["at"]), 0), (x_axis.pixel(marker["at"]), h)], "#d000d0", 1)
        else:
            ov.line([(0, y_axis.pixel(marker["at"])), (w, y_axis.pixel(marker["at"]))], "#d000d0", 1)
    ov.ticks(x_axis, False, frame[1])
    ov.ticks(y_axis, True, frame[0])
    return ov


def calibration(axis: Axis) -> dict:
    return {"ticks_px_value": axis.ticks, "linear_fit_max_residual_px": axis.residual_px, "piecewise": axis.piecewise}


# ---------- chart 1: PDF page 113, cumulative number of sinkholes ----------


def sinkholes(doc: pymupdf.Document) -> dict:
    img = embedded_image(doc, 113, 424)
    a = img.astype(int)
    dark = darkness(img)
    # Ticks point out of the frame: below the x axis (row 352), right of the right axis (column 625).
    x_axis = fit_axis(peak_centres(dark[354:357, 90:620].sum(axis=0), 300, 90), list(range(1978, 2019, 5)), 1.0)
    y_axis = fit_axis(peak_centres(dark[:, 627:633].sum(axis=1), 600), list(range(6000, -1, -1000)), 1.0)
    level_axis = fit_axis(peak_centres(dark[:, 75:80].sum(axis=1), 500), list(range(-400, -431, -5)), 1.0)

    red = (a[..., 0] > 170) & (a[..., 1] < 110) & (a[..., 2] < 110)
    first_red = int(np.flatnonzero(red.any(axis=0))[0])
    path = trace(red, first_red)
    # The path starts at 1980 and ends near the top of the frame (2016).
    years = range(1980, int(x_axis.value(path[-1][0])) + 1)
    points = [[y, int(round(y_axis.value(interpolate_y(path, x_axis.pixel(y))), -1))] for y in years]

    # Check the shared x calibration on the blue Dead Sea level line against the Water Authority series.
    blue = (a[..., 2] > 120) & (a[..., 0] < 90) & (a[..., 1] > 60) & (a[..., 1] < 170)
    first_blue = int(np.flatnonzero(blue.any(axis=0))[0])
    blue_path = trace(blue, first_blue)
    level = json.loads((ROOT / "site/data/dead-sea-level.json").read_text())["points"]
    months = np.array([int(d[:4]) + (int(d[5:7]) - 0.5) / 12 for d, _ in level])
    official = np.array([v for _, v in level])
    diffs = [level_axis.value(y) - np.interp(x_axis.value(x), months, official) for x, y in blue_path[::4]]
    check = (
        f"קו המפלס הכחול באותו איור, שעבר את אותה דיגיטציה, סוטה מנתוני רשות המים בממוצע "
        f"{np.mean(np.abs(diffs)):.2f} מ' (מרבי {np.max(np.abs(diffs)):.2f} מ'). זו בדיקה של כיול ציר השנים."
    )
    print("page 113 blue-line check:", check)

    # Error budget: tick fit residual plus half the drawn line width (red line is about 4 px tall).
    count_err = round((y_axis.error_px + 2) * abs(y_axis.scale), -1)
    chart = {
        "figure": "fig-a14-08",
        "title": "מספר הבולענים המצטבר לאורך חוף ים המלח, 1980–2016",
        "source": {
            "kind": "digitized",
            "label": "דיגיטציה של האיור בעמוד 113 (Nof, Abelson, Raz et al. 2019)",
            "url": "https://doi.org/10.3390/rs11010089",
            "method": "הקו האדום באיור המודפס חולץ לפי צבע, וערכיו נקראו לכל שנה. לא נמצאה טבלה שפורסמה עם הספירות השנתיות.",
            "pdf_page": 113,
            "image": "p113-x424",
            "calibration": {"x": calibration(x_axis), "y": calibration(y_axis)},
            "accuracy": {"x": f"±{abs(x_axis.scale) * (x_axis.error_px + 1):.2f} שנה", "y": f"±{count_err:g} בולענים"},
        },
        "x": {"label": "שנה", "unit": "", "type": "year"},
        "y": {"label": "מספר הבולענים המצטבר", "unit": "בולענים"},
        "series": [{"name": "בולענים (מצטבר)", "kind": "line", "points": points}],
        "notes": (
            "באיור המקורי מופיעים מפלס ים המלח ומספר הבולענים על שני צירים. כאן מספר הבולענים מוצג לבדו; "
            "המפלס מוצג בגרף הנפרד מנתוני רשות המים. בין 1980 ל־1997 הקו באיור כמעט ישר, ולכן הערכים השנתיים בטווח הזה "
            "הם קריאה של הקו ולא ספירות שנתיות. " + check
        ),
    }
    ov = chart_overlay(img, chart, x_axis, y_axis, (625, 352))
    ov.dots([(x_axis.pixel(y), y_axis.pixel(v)) for y, v in points], "#e00000", 4)
    ov.line(blue_path, "#ff00ff", 1)  # the traced level line used for the calibration check
    ov.ticks(level_axis, True, 81)
    chart["source"]["overlay"] = ov.save("fig-a14-08-overlay.png")
    return chart


# ---------- chart 2: PDF page 262, Lake Lisan levels ----------


def lisan(doc: pymupdf.Document) -> dict:
    img = embedded_image(doc, 262, 1019)
    dark_level = darkness(img)
    # The printed image has unlabelled ticks; the book prints the numbers as PDF text over the image.
    # Left ticks every 10 m (160 to 420 m below sea level); bottom ticks every 5 ka (5 to 65 ka).
    y_axis = fit_axis(peak_centres(dark_level[:, 55:59].sum(axis=1), 250), list(range(-160, -421, -10)), 2.5)
    bottom = dark_level[567:568, :].sum(axis=0).astype(float)
    bump = bottom - np.convolve(bottom, np.ones(15) / 15, mode="same")
    tick_x = [x for x in range(66, 598) if bump[x] == bump[x - 4 : x + 5].max() and bump[x] > 25]
    x_axis = fit_axis(tick_x, list(range(5, 66, 5)), 4.0, piecewise=True)
    check_labels_against_pdf_text(doc, 262, img, x_axis, y_axis)

    # Heinrich event bars: light grey columns that fill the plot height.
    grey = (dark_level > 35) & (dark_level < 110)
    bars = [(s, e) for s, e in runs(grey[300:540, 62:600].mean(axis=0) > 0.5) if e - s >= 4]  # skip the frame edge
    bars = [(s + 62, e + 62) for s, e in bars]
    if len(bars) != 5:
        raise SystemExit(f"expected 5 Heinrich bars, found {bars}")

    # Measured grey levels: dot cores below 60, the curve core 90-130, the bars 170 and lighter.
    plot = rect_mask(dark_level.shape, [(64, 40, 598, 561)])
    # Printed labels inside the plot: "מפלס ים המלח היום" with its arrow, and "אירועי היינריך" at the top right.
    text = rect_mask(dark_level.shape, [(98, 519, 225, 535), (62, 529, 100, 561), (440, 18, 560, 40)])
    dots, dot_pixels = find_dots((dark_level > 195) & plot & ~text, radius=1, min_core=1)
    curve = (dark_level > 105) & plot & ~text & ~dot_pixels
    path = simplify(trace(curve, 64), 1.2)

    present = y_axis.value(548.0)  # tip of the arrow from "מפלס ים המלח היום", on the left frame

    chart = {
        "figure": "fig-a34-05",
        "title": "תנודות מפלסי אגם הלשון ואירועי היינריך",
        "source": {
            "kind": "digitized",
            "label": "דיגיטציה של האיור בעמוד 262 (ברטוב 2005)",
            "method": (
                "הקו והנקודות באיור המודפס חולצו לפי צבע. הכיול נעשה לפי סימני השנתות בתמונה, "
                "ונבדק מול המספרים שהספר מדפיס מעל התמונה."
            ),
            "pdf_page": 262,
            "image": "p262-x1019",
            "calibration": {"x": calibration(x_axis), "y": calibration(y_axis)},
            "accuracy": {
                "x": f"±{abs(x_axis.scale) * (x_axis.error_px + 1.5):.1f} אלפי שנים",
                "y": f"±{abs(y_axis.scale) * (y_axis.error_px + 1.5):.0f} מ'",
            },
        },
        "x": {"label": "גיל מוחלט", "unit": "אלפי שנים", "type": "number"},
        "y": {"label": "מפלס האגם", "unit": "מטר ביחס לפני הים"},
        "series": [
            {
                "name": "עקומת המפלס",
                "kind": "line",
                "points": [[round(x_axis.value(x), 1), round(y_axis.value(y))] for x, y in path],
            },
            {
                "name": "נקודות שמסומנות באיור",
                "kind": "points",
                "points": sorted([round(x_axis.value(x), 1), round(y_axis.value(y))] for x, y in dots),
            },
        ],
        "bands": [
            {"axis": "x", "from": round(x_axis.value(s - 0.5), 1), "to": round(x_axis.value(e + 0.5), 1), "label": str(n)}
            for n, (s, e) in enumerate(bars, start=1)
        ],
        "markers": [{"axis": "y", "at": round(present), "label": "מפלס ים המלח היום, כפי שסומן באיור המקורי"}],
        "notes": (
            "הפסים הממוספרים 1 עד 5 הם אירועי היינריך, כמו באיור. "
            "ליד פס 1 (כ־14.5 עד 16.5 אלפי שנים) הקו באיור יוצר לולאה צרה בתוך הפס, והקו כאן מפשט אותה "
            "(הקצוות שלה, כ־270 וכ־340 מטר מתחת לפני הים, חסרים). "
            "השקע הקטן ליד 55 אלף שנה, שמוסתר מתחת לנקודות, והקטע המנוקד בקצה הימני (אחרי כ־69 אלף שנה) לא נקראו. "
            "נקודות שנוגעות זו בזו נספרות כנקודה אחת."
        ),
    }
    chart["source"]["overlay"] = chart_overlay(img, chart, x_axis, y_axis, (60, 566)).save("fig-a34-05-overlay.png")
    return chart


def check_labels_against_pdf_text(doc: pymupdf.Document, page_no: int, img: np.ndarray, x_axis: Axis, y_axis: Axis):
    """The book prints the tick numbers of page 262 as PDF text. Each number must sit on its detected tick."""
    page = doc[page_no - 1]
    bbox = pymupdf.Rect(page.get_image_info(xrefs=True)[0]["bbox"])
    sx, sy = img.shape[1] / bbox.width, img.shape[0] / bbox.height
    for x0, y0, x1, y1, word, *_ in page.get_text("words"):
        if not word.isdigit() or not pymupdf.Rect(x0, y0, x1, y1).intersects(bbox):
            continue
        cx, cy = ((x0 + x1) / 2 - bbox.x0) * sx, ((y0 + y1) / 2 - bbox.y0) * sy
        value = int(word)
        if cx < 40:  # numbers left of the frame label the y axis (metres below sea level)
            err = abs(y_axis.pixel(-value) - cy)
        else:  # numbers under the frame label the x axis (thousands of years)
            err = abs(x_axis.pixel(value) - cx)
        print(f"page {page_no} printed label {value}: {err:.1f} px from the fitted tick")
        if err > 8:
            raise SystemExit(f"printed label {value} is {err:.1f} px from the fitted axis")


# ---------- chart 3: PDF page 304, level change by added water (schematic) ----------


def conveyance(doc: pymupdf.Document) -> dict:
    img = embedded_image(doc, 304, 1179)
    a = img.astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    grey_level = a.mean(axis=2)
    # x: centres of the orange labels 0..1000 above the panel (digits of one number are less than 8 px apart).
    orange = (r - b > 35) & (grey_level < 200)
    cols = np.flatnonzero(orange[90:105, :].any(axis=0))
    groups = np.split(cols, np.flatnonzero(np.diff(cols) > 8) + 1)
    label_x = [float(grp.mean()) for grp in groups if grp.size > 3 and grp.mean() > 150]
    x_axis = fit_axis(label_x, list(range(0, 1001, 100)), 8.0)
    # y: the printed zero line (0) and the centre of the "-1" label.
    zero_row = 100 + int(np.argmax((grey_level[100:200, 160:640] < 170).sum(axis=1)))
    minus_one_rows = np.flatnonzero((grey_level[190:230, 136:144] < 100).any(axis=1)) + 190
    y_axis = fit_axis([float(zero_row), float(minus_one_rows.mean())], [0.0, -1.0], 0.5)

    # The level band ("wedge"): neutral or bluish grey pixels; its upper edge is RB, its lower edge SW.
    band = (grey_level > 110) & (grey_level < 228) & (abs(r - g) < 12) & (b >= r - 3)
    band[zero_row - 2 : zero_row + 3, :] = False  # the printed zero line crosses the band
    edges: dict[str, list[Px]] = {"top": [], "bottom": []}
    prev = (float(zero_row) + 18, float(zero_row) + 18)  # the band's right end, just below the zero line
    for x in range(int(x_axis.pixel(950)), int(x_axis.pixel(0)) - 1, -1):
        candidates = [(s, e) for s, e in runs(band[100:240, x])]
        if not candidates:
            continue
        s, e = min(candidates, key=lambda rr: abs(rr[0] + 100 - prev[0]) + abs(rr[1] + 100 - prev[1]))
        if abs(s + 100 - prev[0]) > 6 and abs(e + 100 - prev[1]) > 6:
            continue
        edges["top"].append((x, s + 100.0))
        edges["bottom"].append((x, e + 100.0))
        prev = (s + 100.0, e + 100.0)

    lines = {name: robust_line(pts) for name, pts in edges.items()}
    xs = list(range(0, 1001, 100))
    rb = [[v, round(y_axis.value(lines["top"](x_axis.pixel(v))), 2)] for v in xs]
    sw = [[v, round(y_axis.value(lines["bottom"](x_axis.pixel(v))), 2)] for v in xs]
    crossing = {
        name: round(x_axis.value(np.interp(zero_row, *zip(*sorted((f(x), x) for x in range(150, 700))))), -1)
        for name, f in lines.items()
    }
    print("page 304 zero crossings (MCM/yr):", crossing)

    chart = {
        "figure": "fig-a36-11",
        "title": "שינוי המפלס השנתי של ים המלח לפי כמות המים המוזרמת",
        "source": {
            "kind": "digitized",
            "label": "דיגיטציה של הפס 'Level change' באיור בעמוד 304 (GSI & Tahal Reports, 2011)",
            "url": "https://www.researchgate.net/publication/332727902_Red_Sea_-_Dead_Sea_Water_Conveyance_Study_Program_-_Dead_Sea_Study",
            "method": (
                "האיור הוא תרשים סכמטי. שני שולי הפס האפור חולצו לפי צבע והותאמו לקווים ישרים. "
                "ציר הכמות כויל לפי 11 התוויות 0–1000, שהמרווחים ביניהן לא אחידים בדפוס."
            ),
            "pdf_page": 304,
            "image": "p304-x1179",
            "calibration": {"x": calibration(x_axis), "y": calibration(y_axis)},
            "accuracy": {"x": f"±{round(abs(x_axis.scale) * x_axis.error_px, -1):g} מלמ\"ש", "y": "±0.05 מ' לשנה"},
        },
        "x": {"label": "כמות המים המוזרמת", "unit": "מלמ\"ש", "type": "number"},
        "y": {"label": "שינוי המפלס", "unit": "מטר לשנה"},
        "series": [
            {"name": "RB – רכז מי ים", "kind": "line", "points": rb},
            {"name": "SW – מי ים", "kind": "line", "points": sw},
        ],
        "markers": [
            {"axis": "y", "at": 0, "label": "מפלס יציב"},
            {"axis": "x", "at": 400, "label": "400 מלמ\"ש – מגבלת שלב א' (a36-p061)"},
            {"axis": "x", "at": 700, "label": "כ־700 מלמ\"ש – ייצוב המפלס ב־RB (a36-p060)"},
            {"axis": "x", "at": 900, "label": "כ־900 מלמ\"ש – ייצוב המפלס ב־SW (a36-p060)"},
        ],
        "notes": (
            "רק החלק הכמותי של האיור (שינוי המפלס) מוצג כאן; שאר השורות באיור (שכבתיות, פריחה ביולוגית, "
            "הלבנת גבס, בולענים, מי תהום ותעשייה) הן תיאור איכותני. "
            f"בדיגיטציה השוליים חוצים את קו האפס בכ־{crossing['top']:g} (RB) ובכ־{crossing['bottom']:g} (SW) מלמ\"ש. "
            "הקווים האדומים באיור נמצאים בכ־400, כ־710 וכ־915 מלמ\"ש; הסמנים כאן משתמשים בערכים שבטקסט הספר."
        ),
    }
    ov = chart_overlay(img, chart, x_axis, y_axis, (150, 98))
    for name in ("top", "bottom"):
        ov.dots(edges[name][::6], "#00a000", 2)  # sampled band edges behind the line fit
    chart["source"]["overlay"] = ov.save("fig-a36-11-overlay.png")
    return chart


def robust_line(points: list[Px]):
    """Least-squares line y(x), refitted once without points more than 1.5 px off (text over the band)."""
    xs, ys = np.array(points).T
    k, c = np.polyfit(xs, ys, 1)
    keep = np.abs(ys - (k * xs + c)) <= 1.5
    k, c = np.polyfit(xs[keep], ys[keep], 1)
    return lambda x: float(k * x + c)


# ---------- chart 4: PDF page 305, Dead Sea density by depth ----------


def density(doc: pymupdf.Document) -> dict:
    img = embedded_image(doc, 305, 1185)
    a = img.astype(int)
    red = (a[..., 0] - a[..., 1] > 60) & (a[..., 0] > 150)
    dark_level = darkness(img)
    dark_level[dilate(red, 1)] = 0
    # Ticks point into the frame: right of the left axis (column 73), above the bottom axis (row 411).
    y_axis = fit_axis(peak_centres(dark_level[:, 75:80].sum(axis=1), 200)[:8], list(range(0, -351, -50)), 3.0)
    inner = peak_centres(dark_level[403:409, 76:548].sum(axis=0), 200, 76)
    right_frame = 540 + int(np.argmax((dark_level[20:400, 540:560] > 110).sum(axis=0)))
    x_axis = fit_axis(inner + [float(right_frame)], [171.0, 172.0, 173.0, 174.0], 2.0)

    # Measured grey levels: dot cores below 120, the curve 140-170 and 2-3 px wide.
    plot = rect_mask(dark_level.shape, [(77, 9, 547, 406)])
    # Printed Hebrew text blocks: the left block and the red-framed block.
    text = rect_mask(dark_level.shape, [(100, 140, 216, 372), (276, 136, 426, 380)])
    dots, dot_pixels = find_dots((dark_level > 135) & plot & ~text, radius=1, min_core=1)
    curve = (dark_level > 60) & plot & ~text & ~dot_pixels
    # Trace the curve along depth: transpose, so that rows become columns.
    start_row = 9  # top of the plot frame
    path_t = trace(curve.T, start_row)
    # The printed line is a smooth fitted curve, so a running median removes snags on leftover dot pixels.
    cols = [c for _, c in path_t]
    smooth = [float(np.median(cols[max(i - 4, 0) : i + 5])) for i in range(len(cols))]
    path = simplify([(c, r) for (r, _), c in zip(path_t, smooth)], 1.0)
    boundary = y_axis.value(np.flatnonzero(red[:, 120:200].any(axis=1)).mean())

    chart = {
        "figure": "fig-a36-12",
        "title": "צפיפות מי ים המלח לפי העומק (ים המלח המשוכב)",
        "source": {
            "kind": "digitized",
            "label": "דיגיטציה של האיור בעמוד 305 (בעקבות Neev and Emery, 1967)",
            "method": "הנקודות והקו באיור המודפס חולצו לפי צבע. הכיול נעשה לפי סימני השנתות בתמונה.",
            "pdf_page": 305,
            "image": "p305-x1185",
            "calibration": {"x": calibration(x_axis), "y": calibration(y_axis)},
            "accuracy": {
                "x": f"±{abs(x_axis.scale) * (x_axis.error_px + 1.5):.2f} (יחידות הציר)",
                "y": f"±{abs(y_axis.scale) * (y_axis.error_px + 1.5):.0f} מ'",
            },
        },
        "x": {"label": "צפיפות", "unit": "כפי שמודפס בציר: גרם לסמ\"ק", "type": "number"},
        "y": {"label": "עומק", "unit": "מטר"},
        "series": [
            {
                "name": "מדידות",
                "kind": "points",
                "points": sorted([round(x_axis.value(x), 2), round(y_axis.value(y))] for x, y in dots),
            },
            {
                "name": "עקומה",
                "kind": "line",
                "points": [[round(x_axis.value(x), 2), round(y_axis.value(y))] for x, y in path],
            },
        ],
        "markers": [{"axis": "y", "at": round(boundary), "label": "הגבול בין גוף המים העליון לתחתון, כפי שסומן באיור"}],
        "notes": (
            "ערכי הצפיפות הם המספרים שעל ציר האיור (170–174). הנקודות שמתחת לקו האדום או לטקסט באיור לא נקראו. "
            "שתי נקודות שנוגעות זו בזו נספרות כנקודה אחת."
        ),
    }
    chart["source"]["overlay"] = chart_overlay(img, chart, x_axis, y_axis, (73, 411)).save("fig-a36-12-overlay.png")
    return chart


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(SOURCE_PDF)
    for build in (sinkholes, lisan, conveyance, density):
        chart = build(doc)
        path = OUT / f"{chart['figure']}.json"
        path.write_text(json.dumps(chart, ensure_ascii=False, indent=1) + "\n")
        print(f"{path.relative_to(ROOT)}: {[(s['name'], len(s['points'])) for s in chart['series']]}")


if __name__ == "__main__":
    main()
