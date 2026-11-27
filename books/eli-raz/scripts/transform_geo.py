# /// script
# requires-python = ">=3.15"
# dependencies = ["matplotlib==3.11.2", "numpy==2.5.4", "Pillow==13.0.0", "shapely==2.2.0"]
# ///
"""Real geography for the Dead Sea transform explainer (figure fig-a18-05, site/features/74-explorable-transform.js).

The "today" state of the explainer is drawn from this data, to scale; the motion back is derived from it in the browser.

Data:
- Land, lakes and the Gulf of Aqaba: Natural Earth v5.1.2 (1:10m), public domain.
- Places: Wikidata coordinates (P625), item IDs in PLACES.
- Fault trace: a line through the axes of the Gulf of Aqaba, the Arava, the Dead Sea, the Jordan valley and the Kinneret
  (the Natural Earth shapes give the axes), then the Yammouneh fault in Lebanon. Schematic; the trace follows
  Garfunkel 1981 (Tectonophysics 80:81-108) in outline.
- Plate velocities relative to Eurasia: GSRM v2.1 (Kreemer, Blewitt and Klein 2014, Geochem. Geophys. Geosyst. 15,
  doi:10.1002/2014GC005407), computed with the EarthScope (UNAVCO) Plate Motion Calculator at the midpoint of Timna and
  Feinan, 30.2077 N 35.2413 E: Arabia (AR) -0.41 mm/yr east, 14.75 north; Sinai (SI) -1.94 east, 8.38 north.

Projection: sinusoidal, central meridian 35 E, in km (equal-area; true scale along 35 E and on every parallel).

Usage: uv run scripts/transform_geo.py
Writes the "geo" block of site/explorables/fig-a18-05.json; every other key of that file stays as it is.
"""

import json
import math

import numpy as np
import shapely
from shapely.geometry import box, shape
from shapely.ops import unary_union

from map_common import ROOT, natural_earth

R = 6371.0088  # Mean Earth radius, km.
LON0 = 35.0
BBOX = (31.0, 25.5, 38.5, 36.5)  # lon/lat of the data kept: room for both blocks to move 240 km south.
FRAME_LAT = (27.4, 33.7)  # The drawing: 700 km tall.
FRAME_X = (-250.0, 170.0)  # km east of 35 E: 420 km wide.
SIMPLIFY_KM = 0.6
PLACES = {  # Wikidata item, latitude, longitude, as read on 2026-11-24.
    "eilat": ("Q134762", 29.55, 34.95),
    "timna": ("Q1973199", 29.78777778, 34.98888889),
    "feinan": ("Q28408071", 30.62775, 35.493647),
    "dead_sea": ("Q23883", 31.5207, 35.4845),
    "kinneret": ("Q126982", 32.818906, 35.590033),
    "tiran": ("Q208157", 28.003888888889, 34.465277777778),
}
# The triple junction of the three plates at the south tip of Sinai, in the sea (schematic).
JUNCTION = (34.40, 27.62)
# Fault trace, south to north (lon, lat). South of the junction the line follows the Red Sea axis.
FAULT = [(35.70, 25.50), (35.05, 26.90), JUNCTION, (34.47, 27.98), (34.62, 28.45), (34.74, 28.95), (34.88, 29.30), (34.97, 29.53),
         (35.07, 29.85), (35.17, 30.25), (35.29, 30.62), (35.38, 30.95), (35.44, 31.25), (35.50, 31.55), (35.54, 31.80),
         (35.56, 32.10), (35.57, 32.45), (35.58, 32.70), (35.60, 32.90), (35.62, 33.15), (35.76, 33.45), (36.00, 33.90),
         (36.24, 34.35), (36.35, 34.70), (36.38, 35.30), (36.40, 36.50)]
# The Gulf of Suez and the Suez Canal: Africa to the west, the Sinai subplate to the east (one block in the explainer).
SUEZ = [JUNCTION, (33.55, 28.00), (33.00, 28.75), (32.57, 29.70), (32.55, 29.97), (32.35, 30.55), (32.31, 31.26), (32.25, 32.40)]
# Plate velocities relative to Eurasia, mm/yr (east, north): GSRM v2.1 at 30.2077 N 35.2413 E (see above).
VELOCITY = {"arabia": (-0.41, 14.75), "sinai": (-1.94, 8.38)}
SLIP_KM = 105  # The book (a18-p021): the relative left-lateral motion.


def project(lon: float, lat: float) -> tuple[float, float]:
    phi = math.radians(lat)
    return (R * math.radians(lon - LON0) * math.cos(phi), R * phi)


def projected(geom):
    return shapely.transform(geom, lambda coords: np.array([project(x, y) for x, y in coords]))


def rings(geom) -> list[list[list[float]]]:
    """Exterior and interior rings of a (multi)polygon, simplified, as [[x, y], ...] in km, rounded to 0.1 km."""
    geom = geom.simplify(SIMPLIFY_KM, preserve_topology=True)
    out = []
    for poly in getattr(geom, "geoms", [geom]):
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        for ring in [poly.exterior, *poly.interiors]:
            pts = [[round(x, 1), round(y, 1)] for x, y in ring.coords]
            if len(pts) >= 4:
                out.append(pts)
    return out


def line(points: list[tuple[float, float]]) -> list[list[float]]:
    return [[round(x, 1), round(y, 1)] for x, y in (project(lon, lat) for lon, lat in points)]


def named(features: dict, name: str):
    for f in features["features"]:
        props = f["properties"]
        if name in (props.get("name"), props.get("name_en"), props.get("NAME"), props.get("label")):
            return shape(f["geometry"])
    raise SystemExit(f"Natural Earth: no feature named {name}")


def main() -> None:
    area = box(*BBOX)
    land = unary_union([shape(f["geometry"]).intersection(area) for f in natural_earth("ne_10m_land.geojson")["features"]
                        if shape(f["geometry"]).intersects(area)])
    lakes = natural_earth("ne_10m_lakes.geojson")
    marine = natural_earth("ne_10m_geography_marine_polys.geojson")
    dead_sea, kinneret = named(lakes, "Dead Sea"), named(lakes, "Sea of Galilee")
    # The Gulf of Aqaba: the sea north of the Straits of Tiran.
    gulf = named(marine, "Gulf of Aqaba").intersection(box(34.3, 27.98, 35.2, 29.7))
    km = {name: projected(geom) for name, geom in {"land": land, "dead_sea": dead_sea, "kinneret": kinneret, "gulf": gulf}.items()}
    y0, y1 = (R * math.radians(lat) for lat in FRAME_LAT)
    places = {key: [round(v, 1) for v in project(lon, lat)] for key, (_, lat, lon) in PLACES.items()}

    timna, feinan = places["timna"], places["feinan"]
    print(f"Timna to Feinan: {math.dist(timna, feinan):.1f} km, {feinan[1] - timna[1]:.1f} km north")
    print(f"Dead Sea north end to Kinneret south end: {km['kinneret'].bounds[1] - km['dead_sea'].bounds[3]:.1f} km")
    (ae, an), (se, sn) = VELOCITY["arabia"], VELOCITY["sinai"]
    scale = SLIP_KM / math.hypot(ae - se, an - sn)  # km per (mm/yr): the time at present-day rates, in Myr.
    print(f"Displacements: Arabia {ae * scale:.1f} E {an * scale:.1f} N, Sinai {se * scale:.1f} E {sn * scale:.1f} N")

    spec_path = ROOT / "site" / "explorables" / "fig-a18-05.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["geo"] = {
        "note": "Written by scripts/transform_geo.py; sources there. Sinusoidal projection, central meridian 35 E, km.",
        "frame": [FRAME_X[0], round(y0, 1), FRAME_X[1], round(y1, 1)],
        "land": rings(km["land"]),
        "lakes": {"dead_sea": rings(km["dead_sea"]), "kinneret": rings(km["kinneret"])},
        "gulf": rings(km["gulf"]),
        "fault": line(FAULT),
        "suez": line(SUEZ),
        "junction": line([JUNCTION])[0],
        "places": places,
        "place_sources": {key: f"Wikidata {qid}" for key, (qid, _, _) in PLACES.items()},
        "velocity_mm_yr": {k: list(v) for k, v in VELOCITY.items()},
        "velocity_source": "GSRM v2.1 (Kreemer, Blewitt and Klein 2014, doi:10.1002/2014GC005407), relative to Eurasia, "
                           "at 30.2077 N 35.2413 E, via the EarthScope Plate Motion Calculator",
        "displacement_km": {"arabia": [round(ae * scale, 1), round(an * scale, 1)], "sinai": [round(se * scale, 1), round(sn * scale, 1)]},
        "graticule": {"lon": [32, 33, 34, 35, 36, 37], "lat": [28, 29, 30, 31, 32, 33]},
    }
    # The rest of the file stays readable; the generated geometry is one compact line at the end.
    geo = spec.pop("geo")
    text = json.dumps(spec, ensure_ascii=False, indent=2)
    text = text[:-2] + ',\n  "geo": ' + json.dumps(geo, ensure_ascii=False, separators=(",", ":")) + "\n}\n"
    spec_path.write_text(text, encoding="utf-8")
    spec["geo"] = geo
    size = len(json.dumps(spec["geo"]))
    print(f"wrote {spec_path.relative_to(ROOT)}: geo {size / 1000:.0f} kB, {sum(len(r) for r in spec['geo']['land'])} land points")


if __name__ == "__main__":
    main()
