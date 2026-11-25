# /// script
# requires-python = ">=3.15"
# dependencies = ["matplotlib==3.11.2", "numpy==2.5.4", "Pillow==13.0.0"]
# ///
"""Elevation grids for the two shoreline explorables: the shrinking Dead Sea (fig-a14-24) and Lake Lisan (fig-a34-07).

Each map is a relief image plus a "flood level" grid. The flood level of a cell is the lowest lake level at which water
from the lake reaches that cell (a priority flood from a seed in the lake). The page fills every cell whose flood level
is at or below the chosen lake level, so closed hollows above the lake stay dry.

Data:
- Heights: Copernicus DEM GLO-30, free licence; notice in map_common.DEM_NOTICE[30]. Acquired 2011-2015.
  The DEM shows the Dead Sea as one flat surface at -427 m, so it has no shore below that level.
- Evaporation ponds (Dead Sea map only): OpenStreetMap ways and relations tagged landuse=salt_pond, via Overpass, ODbL
  (way 62324950, relation 6475754 on 2026-11-25). Inside the ponds the DEM shows dikes and pond surfaces, not the old
  lake bed, so the flood grid keeps every pond cell dry and the page draws the ponds as a hatched area.
- Kinneret (Lisan map only): the flat DEM surface around Wikidata Q126982 (32.818906, 35.590033), drawn as water.

Limits:
- Cells are block means of the 30 m DEM (about 160 m for the Dead Sea, 450 m for the rift). Narrow channels (the
  pumping canal) and single dikes vanish. Revisit if a map needs features under the cell size.
- Today's heights stand in for the past. Revisit if a source gives a past surface (for example the Lisan rift floor).

Usage: uv run scripts/shoreline_maps.py
Writes site/data/shoreline-dead-sea.json and site/data/shoreline-lisan.json ({"source", "points": {map}}).
"""

import base64
import heapq
import io
import json
import math
import zlib
from pathlib import Path

import numpy as np
from matplotlib.path import Path as PolyPath
from PIL import Image

from map_common import DEM_NOTICE, DEM_PIXELS_PER_DEGREE, ROOT, dem, hillshade, overpass, osm_rings, relief

DEM_SOURCE = {"label": "Copernicus DEM GLO-30", "url": "https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM"}
# Hypsometric tints of the other edition maps (jordan_maps.py), lighter so the water reads on top.
STOPS = [(-430, "#e4e8d2"), (-200, "#e8e8cf"), (0, "#efe7cd"), (500, "#e9d4ae"), (1000, "#d9bf98"), (1700, "#c4a680")]
LAKE = "#a9c8d6"
DEM_LAKE = -427.0  # The flat Dead Sea surface of the DEM (checked in main()).


def block_mean(z: np.ndarray, f: int) -> np.ndarray:
    rows, cols = z.shape[0] // f, z.shape[1] // f
    return z[: rows * f, : cols * f].reshape(rows, f, cols, f).mean(axis=(1, 3))


def flood_levels(z: np.ndarray, seed: tuple[int, int]) -> np.ndarray:
    """Lowest water level at which a lake that starts at `seed` reaches each cell (4-neighbour priority flood)."""
    rows, cols = z.shape
    level = np.full(z.shape, np.inf, dtype=np.float64)
    level[seed] = z[seed]
    heap = [(float(z[seed]), *seed)]
    while heap:
        h, r, c = heapq.heappop(heap)
        if h > level[r, c]:
            continue
        for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= rr < rows and 0 <= cc < cols:
                nh = max(h, float(z[rr, cc]))
                if nh < level[rr, cc]:
                    level[rr, cc] = nh
                    heapq.heappush(heap, (nh, rr, cc))
    return level


def cell(lat: float, lon: float, box: dict, f: int) -> tuple[int, int]:
    ppd = DEM_PIXELS_PER_DEGREE[30] / f
    return round((box["north"] - lat) * ppd), round((lon - box["west"]) * ppd)


def packed(level: np.ndarray, base: float, step: float) -> dict:
    """Flood levels as bytes: code = (level - base) / step, 0..255, rows north first; zlib, then base64."""
    codes = np.clip(np.rint((level - base) / step), 0, 255).astype(np.uint8)
    return {"base": base, "step": step, "data": base64.b64encode(zlib.compress(codes.tobytes(), 9)).decode()}


def relief_image(z: np.ndarray, box: dict, f: int, water: np.ndarray | None, quality: int) -> str:
    shade = hillshade(z, box["south"], box["north"], f / DEM_PIXELS_PER_DEGREE[30], exaggeration=2.0)
    rgb = relief(z, shade, STOPS, strength=0.6)
    if water is not None:
        rgb[water] = [int(LAKE[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    image = Image.fromarray(np.rint(rgb * 255).astype(np.uint8), "RGB")
    out = io.BytesIO()
    image.save(out, "WEBP", quality=quality, method=6)
    print(f"  relief {image.size[0]}x{image.size[1]} {out.tell()} bytes")
    return "data:image/webp;base64," + base64.b64encode(out.getvalue()).decode()


def ponds() -> list[list[list[float]]]:
    """Outer rings of the evaporation ponds of the southern basin as [lon, lat] lists, rounded to about 10 m."""
    box = "30.95,35.33,31.25,35.62"  # South, west, north, east: the southern basin only.
    query = f'[out:json][timeout:120];(way["landuse"="salt_pond"]({box});relation["landuse"="salt_pond"]({box}););out geom;'
    rings = []
    for element in overpass("dead-sea-salt-ponds", query):
        for ring in osm_rings(element):
            rings.append([[round(lon, 4), round(lat, 4)] for lon, lat in ring])
    if not rings:
        raise SystemExit("no salt ponds in the Overpass answer")
    return rings


def pond_cells(rings: list[list[list[float]]], box: dict, shape: tuple[int, int]) -> np.ndarray:
    """True for the cells whose centre lies inside a pond ring."""
    rows, cols = shape
    lon = box["west"] + (np.arange(cols) + 0.5) * (box["east"] - box["west"]) / cols
    lat = box["north"] - (np.arange(rows) + 0.5) * (box["north"] - box["south"]) / rows
    centres = np.column_stack([g.ravel() for g in np.meshgrid(lon, lat)])
    inside = np.zeros(rows * cols, dtype=bool)
    for ring in rings:
        inside |= PolyPath(ring).contains_points(centres)
    return inside.reshape(shape)


def build(name: str, box: dict, f: int, seed: tuple[float, float], base: float, step: float, quality: int,
          extra: dict) -> None:
    print(name)
    full = dem(box["west"], box["east"], box["south"], box["north"], 30)
    z = block_mean(full, f)
    if "ponds" in extra:
        # The DEM shows dikes and pond surfaces inside the ponds, not a lake bed: no water enters them on the map.
        inside = pond_cells(extra["ponds"], box, z.shape)
        z = np.where(inside, np.inf, z)
        print(f"  {int(inside.sum())} cells inside the evaporation ponds")
    level = flood_levels(z, cell(*seed, box, f))
    lake = float(level[cell(*seed, box, f)])
    if abs(lake - DEM_LAKE) > 0.5:
        raise SystemExit(f"{name}: the DEM lake surface is {lake}, expected {DEM_LAKE}; check the seed and DEM_LAKE")
    water = None
    if "kinneret" in extra:
        k = cell(*extra.pop("kinneret"), box, f)
        water = flood_levels(z, k) <= z[k] + 0.5
        print(f"  Kinneret surface {z[k]:.1f} m, {int(water.sum())} cells")
    # The relief image has twice the cells of the flood grid in each direction.
    fine = block_mean(full, f // 2)[: 2 * z.shape[0], : 2 * z.shape[1]]
    fine_water = None if water is None else np.repeat(np.repeat(water, 2, axis=0), 2, axis=1)
    map_ = {
        "bounds": [box["south"], box["west"], box["north"], box["east"]],
        "cols": z.shape[1], "rows": z.shape[0],
        "km_per_degree": [110.57, 111.32 * math.cos(math.radians((box["south"] + box["north"]) / 2))],
        "dem_lake": DEM_LAKE,
        "flood": packed(level, base, step),
        "relief": relief_image(fine, box, f // 2, fine_water, quality),
        **extra,
    }
    path = ROOT / "site" / "data" / f"shoreline-{name}.json"
    path.write_text(json.dumps({
        "source": {**DEM_SOURCE, "notice": DEM_NOTICE[30]},
        "method": __doc__.split("\n\n")[1].replace("\n", " "),
        "points": map_,
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"  {z.shape[1]}x{z.shape[0]} cells, wrote {path.relative_to(ROOT)} {path.stat().st_size} bytes")


def main() -> None:
    dead_sea = {"south": 30.96, "north": 31.80, "west": 35.33, "east": 35.62}
    build("dead-sea", dead_sea, 6, (31.55, 35.47), base=-428.0, step=0.2, quality=72,
          extra={"ponds": ponds()})
    rift = {"south": 30.60, "north": 33.00, "west": 35.15, "east": 35.75}
    build("lisan", rift, 16, (31.55, 35.47), base=-430.0, step=1.2, quality=70,
          extra={"kinneret": (32.818906, 35.590033)})


if __name__ == "__main__":
    main()
