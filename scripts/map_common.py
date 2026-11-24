"""Shared helpers for the edition maps (pamir_map.py, rd_conveyance_map.py, jordan_plateau_view.py).

Each map script is a PEP 723 script in this folder; `uv run scripts/<name>.py` puts this folder on sys.path.
Downloads are cached under work/maps/ (ignored by git). Each helper prints the SHA-256 of what it reads.
"""

import hashlib
import io
import json
import math
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from matplotlib import font_manager
from matplotlib import patheffects
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work" / "maps"
USER_AGENT = {"User-Agent": "map-figure-builder/0.1"}

NATURAL_EARTH = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
OVERPASS_SERVERS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
DEM_URL = {90: "https://copernicus-dem-90m.s3.amazonaws.com/Copernicus_DSM_COG_30_{tile}_DEM/Copernicus_DSM_COG_30_{tile}_DEM.tif",
           30: "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{tile}_DEM/Copernicus_DSM_COG_10_{tile}_DEM.tif"}
DEM_PIXELS_PER_DEGREE = {90: 1200, 30: 3600}

OSM_CREDIT = "© OpenStreetMap contributors (ODbL)"
NE_CREDIT = "Natural Earth (public domain)"
OTM_CREDIT = "Map style: © OpenTopoMap (CC BY-SA)"


def dem_credit(*resolutions: int) -> str:
    """Attribution that the Copernicus DEM licence (Article 6) asks for on modified data."""
    products = " and ".join(f"WorldDEM-{r}" for r in resolutions)
    return (f"Relief produced using Copernicus {products} © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH "
            "2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved")


def credit_text(*parts: str, width: int) -> str:
    """Credit lines for the corner of a static map, wrapped to `width` characters."""
    return "\n".join(textwrap.fill(part, width) for part in parts)


def download(url: str, path: Path) -> bytes:
    """Download url to path once; later runs read the cached file."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers=USER_AGENT), timeout=300) as r:
            path.write_bytes(r.read())
    data = path.read_bytes()
    print(f"{path.relative_to(ROOT)} sha256={hashlib.sha256(data).hexdigest()}")
    return data


def natural_earth(name: str) -> dict:
    return json.loads(download(NATURAL_EARTH + name, ROOT / "work" / "natural-earth" / name))


def overpass(name: str, query: str) -> list[dict]:
    """Run an Overpass query once and cache the raw answer as work/maps/osm/<name>.json."""
    path = WORK / "osm" / f"{name}.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(overpass_fetch(query))
    data = path.read_bytes()
    print(f"{path.relative_to(ROOT)} sha256={hashlib.sha256(data).hexdigest()}")
    return json.loads(data)["elements"]


def overpass_fetch(query: str) -> bytes:
    """POST a query to the public Overpass servers in turn; they often answer 502 or 504 under load."""
    body = urllib.parse.urlencode({"data": query}).encode()
    errors = []
    for attempt in range(8):
        server = OVERPASS_SERVERS[attempt % len(OVERPASS_SERVERS)]
        try:
            with urllib.request.urlopen(urllib.request.Request(server, data=body, headers=USER_AGENT), timeout=300) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError) as error:
            errors.append(f"{server}: {error}")
            time.sleep(10)
    raise SystemExit("Overpass failed:\n" + "\n".join(errors))


def osm_element(elements: list[dict], kind: str, osm_id: int) -> dict:
    found = [e for e in elements if e["type"] == kind and e["id"] == osm_id]
    if len(found) != 1:
        raise SystemExit(f"OSM {kind} {osm_id} not found in the Overpass answer")
    return found[0]


def osm_point(element: dict) -> tuple[float, float]:
    """(lat, lon) of a node, or the Overpass center of a way or relation."""
    if "lat" in element:
        return element["lat"], element["lon"]
    return element["center"]["lat"], element["center"]["lon"]


def osm_rings(element: dict) -> list[list[tuple[float, float]]]:
    """Closed (lon, lat) rings of an Overpass `out geom` way or multipolygon relation (outer members only).

    Limit: inner rings (holes) are dropped; fine for glaciers and lakes drawn as light fills. Revisit for features with large holes.
    """
    if element["type"] == "way":
        return [[(p["lon"], p["lat"]) for p in element["geometry"]]]
    pieces = [[(p["lon"], p["lat"]) for p in m["geometry"]] for m in element["members"]
              if m["type"] == "way" and m["role"] == "outer"]
    result = []
    while pieces:
        ring = pieces.pop(0)
        while ring[0] != ring[-1]:
            match = next((p for p in pieces if ring[-1] in (p[0], p[-1])), None)
            if match is None:
                raise ValueError(f"relation {element['id']}: outer ring does not close")
            pieces.remove(match)
            ring += (match if match[0] == ring[-1] else match[::-1])[1:]
        result.append(ring)
    return result


def osm_line(element: dict) -> list[tuple[float, float]]:
    """(lon, lat) points of an Overpass `out geom` way."""
    return [(p["lon"], p["lat"]) for p in element["geometry"]]


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


def dem(west: float, east: float, south: float, north: float, resolution: int = 90) -> np.ndarray:
    """Copernicus DEM heights (metres) for the box, north row first, one pixel per 3 or 1 arc seconds.

    Limit: tiles below 50° N are square (1200 or 3600 px a side); the half-pixel offset of the tile grid (under 45 m) is ignored.
    Revisit both if a map goes north of 50° N or needs sub-pixel accuracy.
    """
    if north > 50:
        raise ValueError("tiles north of 50° N are narrower; extend dem() first")
    ppd = DEM_PIXELS_PER_DEGREE[resolution]
    rows = []
    for lat in range(math.ceil(north) - 1, math.floor(south) - 1, -1):
        row = []
        for lon in range(math.floor(west), math.ceil(east)):
            tile = f"N{lat:02d}_00_E{lon:03d}_00"
            path = WORK / "dem" / f"glo{resolution}" / Path(DEM_URL[resolution].format(tile=tile)).name
            download(DEM_URL[resolution].format(tile=tile), path)
            heights = np.asarray(Image.open(path), dtype=np.float32)
            if heights.shape != (ppd, ppd):
                raise ValueError(f"{path.name}: unexpected shape {heights.shape}")
            row.append(heights)
        rows.append(np.hstack(row))
    mosaic = np.vstack(rows)
    top, left = math.ceil(north), math.floor(west)
    r0, r1 = round((top - north) * ppd), round((top - south) * ppd)
    c0, c1 = round((west - left) * ppd), round((east - left) * ppd)
    return mosaic[r0:r1, c0:c1]


def hillshade(z: np.ndarray, south: float, north: float, step: float,
              azimuth: float = 315, altitude: float = 45, exaggeration: float = 1.0) -> np.ndarray:
    """Lambert hillshade 0..1 for a lat/lon grid (north row first) with cells of `step` degrees."""
    dy = step * 110_574
    dx = step * 111_320 * math.cos(math.radians((south + north) / 2))
    # Rows run north to south, so gy is the slope toward the south, as in the ESRI hillshade formula.
    gy, gx = np.gradient(z * exaggeration, dy, dx)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(gy, -gx)
    sun = math.radians(360 - azimuth + 90)
    alt = math.radians(altitude)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(sun - aspect)
    return np.clip(shade, 0, 1)


def tint(z: np.ndarray, stops: list[tuple[float, str]]) -> np.ndarray:
    """Hypsometric colours: linear between (height, hex colour) stops."""
    heights = [h for h, _ in stops]
    rgb = np.array([[int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)] for _, c in stops])
    return np.stack([np.interp(z, heights, rgb[:, k]) for k in range(3)], axis=-1)


def relief(z: np.ndarray, shade: np.ndarray, stops: list[tuple[float, str]], strength: float = 0.55) -> np.ndarray:
    """Tinted relief: tint times a softened hillshade, so flat ground keeps its tint."""
    soft = 1 - strength + strength * shade / max(float(np.percentile(shade, 60)), 1e-6)
    return np.clip(tint(z, stops) * np.clip(soft, 0, 1.15)[..., None], 0, 1)


def hebrew_fonts() -> tuple[font_manager.FontProperties, font_manager.FontProperties]:
    """Regular and bold. Noto Sans Hebrew has no digits or Latin; DejaVu Sans (bundled with Matplotlib) draws those."""
    for name in ("NotoSansHebrew-Regular.ttf", "NotoSansHebrew-Bold.ttf"):
        font_manager.fontManager.addfont(ROOT / "fonts" / name)
    family = ["Noto Sans Hebrew", "DejaVu Sans"]
    return font_manager.FontProperties(family=family), font_manager.FontProperties(family=family, weight="bold")


def halo(width: float = 3, color: str = "white") -> list:
    """White outline under text and lines, so they read on relief and on e-ink."""
    return [patheffects.withStroke(linewidth=width, foreground=color)]


def km_per_degree_lon(lat: float) -> float:
    return 111.32 * math.cos(math.radians(lat))


def save_png(fig, path: Path, dpi: int = 200) -> None:
    """Save as a 256-colour PNG with dithering: about 60% smaller, no visible loss on these maps.

    Limit: a map with smooth wide gradients can band. Save full RGB if a new map shows bands.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    fig.savefig(buffer, dpi=dpi, format="png")
    image = Image.open(buffer).convert("RGB").quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    image.save(path, format="PNG", optimize=True)
    print(f"wrote {path.relative_to(ROOT)} sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")


def write_spec(figure: str, spec: dict) -> None:
    """Write site/figure-maps/<figure>.json (format in AGENTS-BRIEF.md)."""
    path = ROOT / "site" / "figure-maps" / f"{figure}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"figure": figure, **spec}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")
