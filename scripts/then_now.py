# /// script
# requires-python = ">=3.15"
# dependencies = ["matplotlib==3.11.2", "numpy==2.5.4", "Pillow==13.0.0", "pyproj==3.8.0", "rasterio==1.5.2"]
# ///
"""Build the then-and-now layers for the Dead Sea view (site/then-now.json, figure fig-a07-09).

Three layers, each a north-up image in Web Mercator (EPSG:3857), so Leaflet places it exactly with L.imageOverlay(bounds):
- lynch-1849: W. F. Lynch, "Sketch map of the Dead Sea", 1848 survey, NLI FL25570575 (via Commons). Affine least-squares
  fit on land landmarks with Wikidata coordinates (LYNCH_CONTROL). Residuals in km go into the JSON.
- survey-1945: Survey of Palestine 1:100,000 sheet 13 "Dead Sea", revised June 1945, NLI FL60505868 (via Commons).
  Fitted by its printed 1 km Palestine Grid (EPSG:28191): grid crossings are found in the scan and fitted with an affine
  pixel -> grid transform. The grid was checked first against the printed corner table and against landmarks (SURVEY_CHECKS).
- sentinel-2026-11-20: Copernicus Sentinel-2 L2A true colour (TCI), scenes S2C_36RYV_20261120_0_L2A and
  S2C_36SYA_20261120_0_L2A (Earth Search STAC), read at 20 m from the cloud-optimised GeoTIFFs, over the union of
  the two old-map frames.

The Spencer sheet stays as the top-level fallback entry in then-now.json.

Usage: uv run scripts/then_now.py
Writes site/media/then-now/*.webp|jpg and updates site/then-now.json (keeps its fields, adds "layers" and levels.middle).
"""

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.transform import Affine, from_origin
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds

from map_common import ROOT, WORK, download, km_per_degree_lon

Image.MAX_IMAGE_PIXELS = None  # The scans are 57 and 197 megapixels; both are checked by SHA-1 below.

SPEC = ROOT / "site" / "then-now.json"
MEDIA = ROOT / "site" / "media" / "then-now"
SOURCES = WORK / "sources"

LYNCH = {
    "url": "https://upload.wikimedia.org/wikipedia/commons/d/d9/William_Francis_Lynch%2C_Sketch_map_of_the_Dead_Sea_%28FL25570575_3468188%29.jpg",
    "page": "https://commons.wikimedia.org/wiki/File:William_Francis_Lynch,_Sketch_map_of_the_Dead_Sea_(FL25570575_3468188).jpg",
    "sha1": "610f21413ddda3ccf1d37ecb4915ba1fb0b64908",
    "path": SOURCES / "lynch-1849-nli" / "image.jpg",
}
SURVEY = {
    "url": "https://upload.wikimedia.org/wikipedia/commons/7/7a/Survey_of_Palestine%2C_Dead_Sea_%28FL60505868_3809558%29.jpg",
    "page": "https://commons.wikimedia.org/wiki/File:Survey_of_Palestine,_Dead_Sea_(FL60505868_3809558).jpg",
    "sha1": "54053646381fb1ac2e60348f867f585c7e240601",
    "path": SOURCES / "survey-1945-sheet13" / "image.jpg",
}
S2_SCENES = {
    "S2C_36RYV_20261120_0_L2A": "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/36/R/YV/2026/11/S2C_36RYV_20261120_0_L2A/TCI.tif",
    "S2C_36SYA_20261120_0_L2A": "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/36/S/YA/2026/11/S2C_36SYA_20261120_0_L2A/TCI.tif",
}
S2_STAC = "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/"
S2_READ_BOX = (35.10, 30.95, 35.85, 31.90)  # (west, south, east, north): read and cached once; holds every layer frame.

# (name, pixel in the full Lynch scan, Wikidata id, (lat, lon) from Wikidata P625). Pixels read by eye on the scan:
# springs and towns at their symbol, wadis where the channel meets the 1848 shore.
LYNCH_CONTROL = [
    ("Ain el Feshkhah / Ein Feshkha", (2395, 1595), "Q405816", (31.714444, 35.453333)),
    ("W. Zerka Main, Callirrhoe / Ayn al-Zara", (3650, 2545), "Q11910919", (31.597, 35.559306)),
    ("Ain Jidy / Ein Gedi", (1930, 4625), "Q1011544", (31.466667, 35.394444)),
    ("W. el Mojeb, Arnon / Wadi Mujib", (3745, 4445), "Q2120208", (31.465833, 35.573333)),
    ("Sebbeh, Masada", (1528, 6266), "Q186312", (31.315556, 35.353889)),
    ("Kerak / Kerak Castle", (5180, 7634), "Q844694", (31.180556, 35.701389)),
]
# Check points, not fitted. Safieh is 5.7-7.3 km off in every fit that leaves it out, so the sketch is distorted south
# of the Lisan (or the modern Al Safi point is not the 1848 hamlet); fitting it would pull the whole sheet.
LYNCH_CHECKS = [
    ("Safieh / Al Safi", (3272, 8893), "Q27125336", (31.036904, 35.487657)),
]
LYNCH_CROP = (175, 270, 5360, 9920)  # Inside the printed frame of the scan: (left, top, right, bottom).

# Sheet 13 grid: eastings 165-210 km, northings 080-120 km. Coarse pixel of (165, 080) and pixels per km seed the search.
SURVEY_SEED = ((1225, 10850), 236.5)
# Printed table "Palestine grid values at sheet corners" (Palestine 1923 datum): grid km -> (lat, lon) in degrees.
SURVEY_CORNER_TABLE = {(165, 120): ((31, 40, 19.7), (35, 9, 24.1)), (165, 80): ((31, 18, 40.9), (35, 9, 24.9)),
                       (210, 120): ((31, 40, 17.3), (35, 37, 52.4)), (210, 80): ((31, 18, 38.5), (35, 37, 46.6))}
# Landmark check: printed symbol pixel (read by eye) against the Wikidata point.
SURVEY_CHECKS = [
    ("Masada, summit", (5626, 10780), "Q186312", (31.315556, 35.353889)),
    ("Engeddi, spring symbol", (6411, 6789), "Q1011544", (31.466667, 35.394444)),
    ("Hot Springs (Callirrhoe), spring symbol", (10248, 3424), "Q11910919", (31.597, 35.559306)),
    ("Wadi Mujib, channel at the mouth", (10553, 6847), "Q2120208", (31.465833, 35.573333)),
]

TO_MERC = Transformer.from_crs(4326, 3857, always_xy=True)
TO_WGS = Transformer.from_crs(3857, 4326, always_xy=True)


def source_image(src: dict) -> Image.Image:
    data = download(src["url"], src["path"])
    if hashlib.sha1(data).hexdigest() != src["sha1"]:
        raise SystemExit(f"{src['path']}: SHA-1 differs from the Commons record")
    return Image.open(src["path"]).convert("RGB")


def warp_to_mercator(rgb: np.ndarray, src_transform: Affine, src_crs: str, dst_transform: Affine,
                     shape: tuple[int, int]) -> np.ndarray:
    """RGBA image in EPSG:3857; alpha 0 where the source does not reach."""
    out = np.zeros((4, *shape), dtype=np.uint8)
    source = np.concatenate([np.moveaxis(rgb, -1, 0), np.full((1, *rgb.shape[:2]), 255, np.uint8)])
    for band in range(4):
        reproject(source[band], out[band], src_transform=src_transform, src_crs=src_crs, dst_transform=dst_transform,
                  dst_crs="EPSG:3857", resampling=Resampling.lanczos if band < 3 else Resampling.nearest)
    return np.moveaxis(out, 0, -1)


def mercator_grid(west: float, south: float, east: float, north: float, metres: float) -> tuple[Affine, tuple[int, int]]:
    x0, y0 = TO_MERC.transform(west, north)
    x1, y1 = TO_MERC.transform(east, south)
    width, height = math.ceil((x1 - x0) / metres), math.ceil((y0 - y1) / metres)
    return from_origin(x0, y0, metres, metres), (height, width)


def bounds_of(transform: Affine, shape: tuple[int, int]) -> list[list[float]]:
    """[[south, west], [north, east]] in degrees, as Leaflet takes them."""
    west, north = TO_WGS.transform(transform.c, transform.f)
    east, south = TO_WGS.transform(transform.c + transform.a * shape[1], transform.f + transform.e * shape[0])
    return [[round(south, 6), round(west, 6)], [round(north, 6), round(east, 6)]]


def corners_of(bounds: list[list[float]]) -> dict:
    (south, west), (north, east) = bounds
    return {"nw": [north, west], "ne": [north, east], "sw": [south, west]}


def km_offset(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot((a[0] - b[0]) * 110.574, (a[1] - b[1]) * km_per_degree_lon((a[0] + b[0]) / 2))


def save_web(rgba: np.ndarray, name: str, alpha: bool, quality: int = 80) -> dict:
    """WebP with alpha for the warped old maps; JPEG for the fully covered satellite layer."""
    MEDIA.mkdir(parents=True, exist_ok=True)
    path = MEDIA / name
    image = Image.fromarray(rgba if alpha else rgba[..., :3], "RGBA" if alpha else "RGB")
    if alpha:
        image.save(path, format="WEBP", quality=quality, method=6)
    else:
        image.save(path, format="JPEG", quality=quality, optimize=True, progressive=True)
    data = path.read_bytes()
    print(f"wrote {path.relative_to(ROOT)} {image.width}x{image.height} bytes={len(data)} "
          f"sha256={hashlib.sha256(data).hexdigest()}")
    return {"image": str(path.relative_to(ROOT)), "size": [image.width, image.height], "bytes": len(data)}


def lynch_layer() -> dict:
    scan = source_image(LYNCH)
    left, top, right, bottom = LYNCH_CROP
    reduce = 2
    rgb = np.asarray(scan.crop(LYNCH_CROP).reduce(reduce))
    pixels = np.array([p for _, p, _, _ in LYNCH_CONTROL], dtype=float)
    lonlat = np.array([(lon, lat) for *_, (lat, lon) in LYNCH_CONTROL])
    design = np.column_stack([pixels, np.ones(len(pixels))])
    coef, *_ = np.linalg.lstsq(design, lonlat, rcond=None)  # lon/lat = [x y 1] @ coef, x y in full-scan pixels
    fitted = design @ coef
    residuals = [km_offset((la, lo), (fla, flo)) for (lo, la), (flo, fla) in zip(lonlat, fitted)]
    # Pixel (col, row) of the cropped, reduced image -> full-scan pixel -> lon/lat.
    (a, d), (b, e), (c, f) = coef
    full = Affine(reduce, 0, left, 0, reduce, top)
    src_transform = Affine(a, b, c, d, e, f) * full
    corners = [src_transform * xy for xy in ((0, 0), (rgb.shape[1], 0), (0, rgb.shape[0]), (rgb.shape[1], rgb.shape[0]))]
    west, east = min(c[0] for c in corners), max(c[0] for c in corners)
    south, north = min(c[1] for c in corners), max(c[1] for c in corners)
    dst_transform, shape = mercator_grid(west, south, east, north, 23.0)
    rgba = warp_to_mercator(rgb, src_transform, "EPSG:4326", dst_transform, shape)
    image = save_web(rgba, "lynch-1849.webp", alpha=True)
    checks = ", ".join(f"{km_offset((lat, lon), tuple(reversed(np.array([*px, 1]) @ coef))):.1f}"
                       for _, px, _, (lat, lon) in LYNCH_CHECKS)
    layer = {
        "id": "lynch-1849",
        "role": "then",
        "label": "1848: מפת הסקר של לינץ'",
        "date": "1848",
        **image,
        "bounds": bounds_of(dst_transform, shape),
        "projection": "EPSG:3857, north up; place with bounds (L.imageOverlay)",
        "load": "on-open",
        "method": (f"Affine least-squares fit, full-scan pixel to longitude and latitude, on {len(LYNCH_CONTROL)} land "
                   f"landmarks with Wikidata coordinates; residuals {min(residuals):.2f}-{max(residuals):.2f} km "
                   f"(RMS {math.sqrt(np.mean(np.square(residuals))):.2f} km). The 1848 sketch is less accurate south of "
                   f"the Lisan: the unfitted check point Safieh is {checks} km off. Scan cropped to the printed frame, "
                   "halved, warped to Web Mercator at 23 m."),
        "control_points": [
            {"name": name, "pixel_full_scan": list(px), "latlon": [lat, lon],
             "source": f"https://www.wikidata.org/wiki/{qid}", "residual_km": round(r, 2)}
            for (name, px, qid, (lat, lon)), r in zip(LYNCH_CONTROL, residuals)],
        "check_points": [
            {"name": name, "pixel_full_scan": list(px), "latlon": [lat, lon], "source": f"https://www.wikidata.org/wiki/{qid}",
             "offset_km": round(km_offset((lat, lon), tuple(reversed(np.array([*px, 1]) @ coef))), 2)}
            for name, px, qid, (lat, lon) in LYNCH_CHECKS],
        "crop_in_full_scan": list(LYNCH_CROP),
        "credit": {
            "text": ("W. F. Lynch, Sketch Map of the Dead Sea from the observations of the U.S. Expedition, 1848. "
                     "National Library of Israel, Eran Laor Cartographic Collection (FL25570575), via Wikimedia Commons. "
                     "Public domain."),
            "url": LYNCH["page"],
        },
        "level": "then",
    }
    for name, r in zip((c[0] for c in LYNCH_CONTROL), residuals):
        print(f"  lynch residual {name}: {r:.2f} km")
    for check in layer["check_points"]:
        print(f"  lynch check {check['name']}: {check['offset_km']} km")
    return layer


def grid_crossings(ink: np.ndarray, to_pixel, radius: int, band: int, share: float) -> np.ndarray:
    """(E km, N km, x, y) of each 1 km grid crossing where both lines are clearly inked near the predicted pixel."""
    found = []
    for n in range(80, 121):
        for e in range(165, 211):
            gx, gy = to_pixel(e, n)
            gx, gy = round(gx), round(gy)
            if not (band <= gy < ink.shape[0] - band and band <= gx < ink.shape[1] - band):
                continue
            columns = ink[gy - band:gy + band, gx - radius:gx + radius + 1].sum(axis=0)
            rows = ink[gy - radius:gy + radius + 1, gx - band:gx + band].sum(axis=1)
            if columns.max() < share * 2 * band or rows.max() < share * 2 * band:
                continue
            found.append((e, n, gx - radius + columns.argmax(), gy - radius + rows.argmax()))
    return np.array(found, dtype=float)


def fit_affine(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    coef, *_ = np.linalg.lstsq(np.column_stack([src, np.ones(len(src))]), dst, rcond=None)
    return coef


def survey_layer() -> dict:
    scan = source_image(SURVEY)
    reduce = 2
    small = np.asarray(scan.reduce(reduce))
    ink = small.max(axis=2) < 120  # Black ink only: grid lines and text; orange contours and blue water stay out.
    (x0, y0), ppk = SURVEY_SEED

    def seed(e, n):
        return (x0 + ppk * (e - 165)) / reduce, (y0 - ppk * (n - 80)) / reduce

    first = grid_crossings(ink, seed, radius=20, band=160, share=0.6)
    to_px = fit_affine(first[:, :2] * 1000, first[:, 2:])
    second = grid_crossings(ink, lambda e, n: np.array([e * 1000, n * 1000, 1]) @ to_px, radius=6, band=120, share=0.45)
    grid_m = second[:, :2] * 1000
    pixels = second[:, 2:] * reduce + (reduce - 1) / 2  # Full-scan pixel centres.
    coef = fit_affine(pixels, grid_m)
    residual = np.hypot(*(np.column_stack([pixels, np.ones(len(pixels))]) @ coef - grid_m).T)
    keep = residual < 3 * np.median(residual) + 10
    coef = fit_affine(pixels[keep], grid_m[keep])
    residual = np.hypot(*(np.column_stack([pixels[keep], np.ones(keep.sum())]) @ coef - grid_m[keep]).T)
    print(f"  survey grid: {keep.sum()} crossings, residual median {np.median(residual):.1f} m, max {residual.max():.1f} m")

    # Check 1: the printed corner table, on the Palestine 1923 datum (EPSG:4281) that the table uses.
    to_local = Transformer.from_crs(28191, 4281, always_xy=True)
    table_m = []
    for (e, n), (lat, lon) in SURVEY_CORNER_TABLE.items():
        tlon, tlat = to_local.transform(e * 1000, n * 1000)
        dms = [d + m / 60 + s / 3600 for d, m, s in (lat, lon)]
        table_m.append(km_offset((tlat, tlon), tuple(dms)) * 1000)
    # Check 2: printed landmarks against Wikidata, through the fitted grid and the datum shift to WGS 84.
    to_wgs = Transformer.from_crs(28191, 4326, always_xy=True)
    checks = []
    for name, (px, py), qid, latlon in SURVEY_CHECKS:
        e, n = np.array([px, py, 1]) @ coef
        lon, lat = to_wgs.transform(e, n)
        checks.append({"name": name, "pixel_full_scan": [px, py], "wikidata": qid,
                       "offset_km": round(km_offset((lat, lon), latlon), 2)})
        print(f"  survey landmark {name}: {checks[-1]['offset_km']} km")

    # Warp the grid area (E 165-210, N 080-120) from the half-size scan to Web Mercator at 16 m.
    (a, d), (b, e_), (c, f) = coef
    src_transform = Affine(a, b, c, d, e_, f) * Affine(reduce, 0, (reduce - 1) / 2, 0, reduce, (reduce - 1) / 2)
    to_merc = Transformer.from_crs(28191, 3857, always_xy=True)
    xs, ys = to_merc.transform([165000, 210000, 165000, 210000], [80000, 80000, 120000, 120000])
    west, south = TO_WGS.transform(min(xs), min(ys))
    east, north = TO_WGS.transform(max(xs), max(ys))
    dst_transform, shape = mercator_grid(west, south, east, north, 16.0)
    rgba = warp_to_mercator(small, src_transform, "EPSG:28191", dst_transform, shape)
    # Keep only the map face: clear everything outside the grid rectangle (margins, legend).
    to_grid = Transformer.from_crs(3857, 28191, always_xy=True)
    cols, rows = np.meshgrid(np.arange(shape[1]) + 0.5, np.arange(shape[0]) + 0.5)
    mx, my = dst_transform * (cols, rows)
    ge, gn = to_grid.transform(mx, my)
    rgba[~((165000 <= ge) & (ge <= 210000) & (80000 <= gn) & (gn <= 120000)), 3] = 0
    image = save_web(rgba, "survey-1945.webp", alpha=True)
    return {
        "id": "survey-1945",
        "role": "middle",
        "label": "1945: מפת מחלקת המדידות של ממשלת המנדט",
        "date": "1945-06",
        **image,
        "bounds": bounds_of(dst_transform, shape),
        "projection": "EPSG:3857, north up; place with bounds (L.imageOverlay)",
        "load": "on-open",
        "method": (f"Fitted by the printed 1 km Palestine Grid (EPSG:28191): {int(keep.sum())} grid crossings found in "
                   f"the scan, affine pixel-to-grid fit, residual median {np.median(residual):.0f} m, max "
                   f"{residual.max():.0f} m. Grid checked first: the printed corner table agrees within "
                   f"{max(table_m):.1f} m (Palestine 1923 datum), and printed landmarks lie "
                   f"{min(c['offset_km'] for c in checks):.2f}-{max(c['offset_km'] for c in checks):.2f} km from their "
                   "Wikidata points. Datum shift to WGS 84 by PROJ. Map face only (grid E 165-210, N 080-120), warped "
                   "to Web Mercator at 16 m."),
        "grid_checks": {"corner_table_max_m": round(max(table_m), 1), "landmarks": checks},
        "credit": {
            "text": ("Survey of Palestine, 1:100,000 Palestine, sheet 13 Dead Sea, second edition. Printed by 514 C. Fd. "
                     "Survey Coy. Sept. 1942, revised and reprinted by the Survey of Palestine June 1945. National Library "
                     "of Israel, Eran Laor Cartographic Collection (FL60505868), via Wikimedia Commons. Public domain."),
            "url": SURVEY["page"],
        },
        "level": "middle",
    }


def sentinel_layer(frames: list[list[list[float]]]) -> dict:
    """Mosaic of the two TCI scenes, read at 20 m through their overviews, over the union of the old-map frames."""
    south = min(f[0][0] for f in frames)
    west = min(f[0][1] for f in frames)
    north = max(f[1][0] for f in frames)
    east = max(f[1][1] for f in frames)
    dst_transform, shape = mercator_grid(west, south, east, north, 23.0)
    rgb = np.zeros((3, *shape), dtype=np.uint8)
    cache = SOURCES / "s2-20261120"
    to_utm = Transformer.from_crs(4326, 32636, always_xy=True)
    west, south, east, north = S2_READ_BOX
    xs, ys = to_utm.transform([west, east, west, east], [south, south, north, north])
    for scene, url in S2_SCENES.items():
        download(S2_STAC + scene, cache / f"{scene}.json")
        stac = json.loads((cache / f"{scene}.json").read_text())
        if not stac["properties"]["datetime"].startswith("2026-11-20") or stac["properties"]["eo:cloud_cover"] > 0.3:
            raise SystemExit(f"{scene}: not the expected clear scene of 2026-11-20")
        part_path = cache / f"{scene}-tci-20m.tif"
        if not part_path.exists():
            with rasterio.open(url) as src:
                if src.crs.to_epsg() != 32636:
                    raise SystemExit(f"{scene}: unexpected CRS {src.crs}")
                window = from_bounds(min(xs), min(ys), max(xs), max(ys), src.transform).intersection(
                    rasterio.windows.Window(0, 0, src.width, src.height))
                out_shape = (3, int(window.height) // 2, int(window.width) // 2)
                data = src.read((1, 2, 3), window=window, out_shape=out_shape, resampling=Resampling.average)
                transform = src.window_transform(window) * Affine.scale(window.width / out_shape[2], window.height / out_shape[1])
                profile = {"driver": "GTiff", "width": out_shape[2], "height": out_shape[1], "count": 3, "dtype": "uint8",
                           "crs": src.crs, "transform": transform, "compress": "deflate", "nodata": 0}
                with rasterio.open(part_path, "w", **profile) as dst:
                    dst.write(data)
        print(f"{part_path.relative_to(ROOT)} sha256={hashlib.sha256(part_path.read_bytes()).hexdigest()}")
        with rasterio.open(part_path) as part:
            for band in range(3):
                layer = np.zeros(shape, dtype=np.uint8)
                reproject(part.read(band + 1), layer, src_transform=part.transform, src_crs=part.crs, src_nodata=0,
                          dst_transform=dst_transform, dst_crs="EPSG:3857", dst_nodata=0, resampling=Resampling.lanczos)
                empty = rgb[band] == 0
                rgb[band][empty] = layer[empty]
    if (rgb.max(axis=0) == 0).mean() > 0.001:
        raise SystemExit("Sentinel mosaic leaves gaps in the frame")
    image = save_web(np.moveaxis(np.concatenate([rgb, np.full((1, *shape), 255, np.uint8)]), 0, -1),
                     "sentinel-2026-11-20.jpg", alpha=False, quality=82)
    return {
        "id": "sentinel-2026-11-20",
        "role": "now",
        "label": "2026: תצלום לוויין, 20 בנובמבר 2026",
        "date": "2026-11-20",
        **image,
        "bounds": bounds_of(dst_transform, shape),
        "projection": "EPSG:3857, north up; place with bounds (L.imageOverlay). Covers both old maps.",
        "load": "on-open",
        "method": ("Copernicus Sentinel-2 L2A true-colour image (TCI) of 2026-11-20, scenes " + " and ".join(S2_SCENES)
                   + " (cloud 0.27% and 0.007%), read at 20 m from the cloud-optimised GeoTIFFs, reprojected from "
                   "UTM 36N to Web Mercator at 23 m."),
        "credit": {"text": "Contains modified Copernicus Sentinel data 2026", "url": "https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice"},
        "level": "today",
    }


def main() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    lynch = lynch_layer()
    survey = survey_layer()
    sentinel = sentinel_layer([lynch["bounds"], survey["bounds"]])
    spec["fallback"] = ("The top-level image, corners, control points and credit describe the Spencer sheet (1370 px). "
                        "Show it when the layers cannot load.")
    spec["layers"] = [lynch, survey, sentinel]
    spec["levels"]["middle"] = {
        "value": -392,
        "date": "1938-04",
        "label": "M.W.L. (−) 392 Metres, April 1938, printed in the sea on the 1945 sheet",
        "source": "Survey of Palestine, 1:100,000 Palestine, sheet 13 Dead Sea, revised June 1945",
        "url": SURVEY["page"],
    }
    SPEC.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {SPEC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
