# /// script
# requires-python = ">=3.15"
# dependencies = ["matplotlib==3.11.2", "numpy==2.5.4", "Pillow==13.0.0"]
# ///
"""Build the "old map and today" explainers of chapter a07 (site/explorables/fig-a07-0{2,4,5,7}.json, kind old-map).

The printed map stays as it is. Today's map is drawn into the frame of the printed image instead:
1. Places named on the old map are read by eye on the release image (pixel of the symbol, or the middle of the name
   when the map has no symbol). Their real positions come from Wikidata (P625) or OpenStreetMap nodes.
2. A similarity transform (turn, one scale, shift; no shear, no warp) is fitted by least squares from image pixels to
   kilometres east and north of 31.5 N 35.5 E. A similarity keeps the shape of the old map, so what the reader sees is
   the map's own distortion. The residual of each place, in km, goes into the JSON.
3. Check places are not fitted: their offset shows a known error of the map (the Arnon of Fuller, the Yarmouk of the
   Peutinger map).
4. Today's geometry goes through the inverse transform into image pixels: the Dead Sea (OSM relation 9351124) and the
   salt ponds of its southern basin (OSM landuse=salt_pond), the lower Jordan (OSM), the Mediterranean coast
   (Natural Earth 10m coastline, public domain).

Sources:
- Wikidata, P625 of each item in PLACES (CC0): https://www.wikidata.org/wiki/<id>
- OpenStreetMap via Overpass (© OpenStreetMap contributors, ODbL): element IDs in QUERY and PLACES.
- Natural Earth v5.1.2 ne_10m_coastline (public domain): https://www.naturalearthdata.com/
- Release images: books/eli-raz/epub-src-release/OEBPS/images (built by tools/ingest_pdf.py --release); their rights
  are in book.toml and NOTICE.md. The web build serves them as book/OEBPS/images/<name>.

Usage: uv run scripts/old_maps.py   (needs the release EPUB tree; run scripts/check.py once first)
Known limit: kilometres come from a flat projection around 31.5 N (equirectangular). Over these frames (up to 200 km)
the error is under 1%, far below the residuals. Revisit if a fitted map covers more than about 300 km.
"""

import json
import math
import time

import numpy as np
from PIL import Image

from map_common import ROOT, download, km_per_degree_lon, natural_earth, osm_element, osm_line, osm_rings, overpass

IMAGES = ROOT / "epub-src-release" / "OEBPS" / "images"
OUT = ROOT / "site" / "explorables"
WIKIDATA = ROOT / "work" / "wikidata"
LAT0, LON0 = 31.5, 35.5
KM_PER_DEG_LAT = 110.574

DEAD_SEA = 9351124  # OSM relation, Wikidata Q23883 (also used by scripts/jordan_maps.py).
JORDAN = "Q40059"  # The Jordan river relation in OSM carries this Wikidata id.
YARMOUK_END = 969126995  # OSM way "Nahal Yarmukh": its last node (downstream) is the mouth at the Jordan.
QUERY = f"""[out:json][timeout:180];
(relation({DEAD_SEA}); wr["landuse"="salt_pond"](30.85,35.3,31.3,35.65););
out geom;
node(id:802887063,802901842);
out body;
way({YARMOUK_END});
out geom;
relation["waterway"="river"]["wikidata"="{JORDAN}"];
way(r)(31.75,35.45,32.7,35.7);
out geom;"""

# Place key -> (Hebrew name, reference). A reference is ("wikidata", id) or ("osm", node id).
PLACES = {
    "jericho": ("יריחו", ("wikidata", "Q5687")),
    "olives": ("הר הזיתים", ("wikidata", "Q205976")),
    "amman": ("עמאן (פילדלפיה)", ("wikidata", "Q3805")),
    "yarmouk": ("שפך הירמוך לירדן", ("osm-way-end", YARMOUK_END)),
    "jordan_mouth": ("שפך הירדן", ("wikidata", "Q40059")),
    "ein_gedi": ("עין גדי", ("wikidata", "Q1011544")),
    "masada": ("מצדה", ("wikidata", "Q186312")),
    "mar_saba": ("מנזר מר סבא", ("wikidata", "Q1059946")),
    "herodium": ("הרודיון", ("wikidata", "Q913099")),
    "nebo": ("הר נבו", ("wikidata", "Q680161")),
    "callirrhoe": ("חמי קלירוהי", ("wikidata", "Q11910919")),
    "machaerus": ("מכוור", ("wikidata", "Q1549278")),
    "arnon": ("שפך הארנון (ואדי מוג'יב)", ("wikidata", "Q2120208")),
    "jerusalem": ("ירושלים", ("wikidata", "Q1218")),
    "bethlehem": ("בית לחם", ("wikidata", "Q5776")),
    "hebron": ("חברון", ("wikidata", "Q168225")),
    "arad": ("תל ערד", ("wikidata", "Q2063578")),
    "gaza": ("עזה", ("wikidata", "Q47492")),
    "ashkelon": ("אשקלון", ("wikidata", "Q60956")),
    "ashdod": ("אשדוד העתיקה", ("wikidata", "Q122059851")),
    "sodom": ("הר סדום", ("wikidata", "Q2670801")),
    "mazraa": ("גור אל־מזרעה", ("osm", 802887063)),
    "safi": ("גור א־צאפי", ("osm", 802901842)),
}
# Wikidata items with more than one P625: the value to use, as (lat, lon) rounded to 4 places.
P625_PICK = {
    "Q60956": (31.67, 34.5456),  # Ashkelon: the ancient city on the coast (national park), not the modern centre.
    "Q205976": (31.7779, 35.2457),  # Mount of Olives: two points 0.3 km apart; the first one.
    "Q1218": (31.7767, 35.2342),  # Jerusalem: the Old City, not the second point 0.9 km west.
    "Q40059": (31.7614, 35.5583),  # Jordan: the mouth at the Dead Sea, not the source.
    "Q3805": (31.95, 35.9333),  # Amman: the old centre (Philadelphia, by the citadel), not the second point 2 km south.
}

SCHEMATIC = ("המפה הישנה לא עוותה. המפה של היום הוטלה עליה בהתאמה של סיבוב, קנה מידה אחד והזזה, בלי עיוות, לפי מקומות "
             "שזוהו בשמם. מיקום המקומות במפה הישנה נקרא בעין, בדיוק של כמה פיקסלים. קו החוף של היום מ־OpenStreetMap.")
INSTRUCTION = "גררו את הקו, או הזיזו את המחוון, כדי לחשוף את אותו שטח היום."
LEGEND = [{"swatch": "lake", "label": "ים המלח היום"},
          {"swatch": "old-map-ponds", "label": "בריכות האידוי היום"},
          {"swatch": "old-map-shore", "label": "חוף ים המלח היום, על המפה הישנה"},
          {"swatch": "old-map-place", "label": "המקום כפי שצויר"},
          {"swatch": "old-map-real", "label": "המקום באמת"}]

# Figure -> what the explainer shows. "points": (place key, name as printed, (x, y) in the release image, fitted).
MAPS = {
    "fig-a07-02": {
        "image": "p040-x169.jpeg",
        "year": "המאה ה־4",
        "title": "מפת פויטינגר והמפה של היום",
        # Not fitted: the Peutinger map is a road map, stretched east-west and not to scale. Today's map is turned
        # as the caption says (west up, north to the right) and framed so the three towns fill the box of the drawn ones.
        "turn": 1j,
        "loose": ("המפה אינה בקנה מידה, ולכן אין כאן מדידת סטייה. המפה של היום מסובבת כמו המפה הישנה, המערב "
                  "למעלה, ומוקטנת כך ששלושת המקומות נכנסים למסגרת שלהם במפה הישנה."),
        "points": [
            ("jericho", "Herichonte", (583, 70), True),  # Two towers.
            ("olives", "Mons Olivet", (300, 62), True),  # Middle of the drawn ridge.
            ("amman", "Philadelfia", (80, 270), True),  # Two towers.
            ("yarmouk", "Fl. Heromicas", (420, 212), False),  # Where the drawn river meets the lake.
        ],
        "old": ("המפה ערוכה לכיוון מערב: המערב למעלה והצפון מימין. יריחו, הר הזיתים ופילדלפיה (עמאן) ממוקמות בה "
                "בתיאום טוב, כדברי הכיתוב. הירמוך (Heromicas) נשפך בה לים המלח, אבל במציאות הוא נשפך לירדן, "
                "\u2068{yarmouk_km:.0f}\u2069 ק\"מ צפונה לשפך הירדן בים המלח."),
        "sources": [("כיתוב האיור: כיוון המפה, הירמוך, יריחו, הר הזיתים ופילדלפיה", "fig-a07-02")],
    },
    "fig-a07-04": {
        "image": "p042-x177.png",
        "year": "1584",
        "title": "המפה הלטינית של 1584 והמפה של היום",
        "points": [
            ("jericho", "Iericho", (35, 372), True),
            ("ein_gedi", "Engadi mons", (205, 300), True),  # Middle of the name: the map has no symbol.
            ("masada", "Massada", (265, 325), True),
            ("mar_saba", "S. Saba", (233, 365), True),
            ("herodium", "Herodium", (166, 357), True),
            ("nebo", "M. Nebo", (50, 232), True),  # Middle of the name.
            ("callirrhoe", "Callirrhoe B.", (55, 220), True),
            ("machaerus", "Macherunta", (62, 266), True),
            ("arnon", "Arnon", (95, 115), False),  # Where the drawn river meets the lake.
        ],
        "old": ("צורת האגם, כמו במפות שבין ימי הביניים למאה ה־19, כמעט ללא קשר למציאות, והדגש על "
                "השמות ההיסטוריים: סדום, עמורה, אדמה וצבויים מצוירות בתוך האגם. המקומות שעל החופים קרובים יותר "
                "למקומם."),
        "sources": [("פסקת המפות המאוחרות: צורת האגם, השמות, ערי הכיכר", "a07-p005"), ("כיתוב האיור", "fig-a07-04")],
    },
    "fig-a07-05": {
        "image": "p043-x181-replacement.jpg",
        "year": "1650",
        "title": "מפת פולר (1650) והמפה של היום",
        "points": [
            ("jerusalem", "Ierusalem", (757, 30), True),  # Middle of the city drawing.
            ("bethlehem", "Bethlehem", (680, 168), True),
            ("hebron", "Kirjath-Arba Hebron", (638, 462), True),
            ("ein_gedi", "Engedi", (1058, 562), True),
            ("arad", "Arad", (847, 1165), True),
            ("gaza", "Gaza", (27, 925), True),
            ("ashkelon", "Askelon", (50, 767), True),
            ("ashdod", "Ashdod Azotus", (58, 465), True),
            ("arnon", "Arnon flu.", (1470, 105), False),  # Where the drawn river meets the lake.
        ],
        "old": ("הצפון למעלה, ויהודה מצוירת בפירוט. אבל ים המלח רחב ומאורך מדי, וסדום, עמורה, אדמה וצבויים מצוירות "
                "בתוכו כשהן בוערות. הארנון נשפך בה לצפון הימה; במציאות הוא נשפך באמצע החוף המזרחי."),
        "sources": [("כיתוב האיור: הארנון בצפון הימה", "fig-a07-05"),
                    ("פסקת המפות המאוחרות: ערי הכיכר הבוערות", "a07-p005")],
    },
    "fig-a07-07": {
        "image": "p045-x189.png",
        "year": "1806",
        "title": "מפת זאטצן (1806) והמפה של היום",
        "points": [
            ("masada", "Masada aliis", (181, 92), True),  # Start of the name, at the drawn shore.
            ("sodom", "Dschibbel Usdumm od. Sodom", (232, 540), True),  # Middle of the name of the ridge.
            ("mazraa", "Gôr el Mesraa", (570, 358), True),  # Middle of the name of the district.
            ("safi", "Gôr el Szâphia", (580, 540), True),  # Middle of the name of the district.
        ],
        "old": ("לראשונה מתוארים חצי האי הלשון והאגן הדרומי, על יסוד סיור בשטח, ושמות ערביים כפי שלמד זאטצן ממלווהו. "
                "המעברה (Die Furth), כף קוסטיגאן, כף מולינה וזיהוי מצדה הם אולי תוספות מ־1859. היום האגן הדרומי "
                "יבש, ובמקומו בריכות האידוי של מפעלי ים המלח."),
        "sources": [("כיתוב האיור: הלשון, האגן הדרומי, המעברה והתוספות של 1859", "fig-a07-07"),
                    ("זאטצן, השמות הערביים והמעברה על מיצר לינטש", "a07-p013"),
                    ("בריכות האידוי של מפעלי ים המלח באגן הדרומי", "a34-p038")],
    },
}


def km(lat: float, lon: float) -> tuple[float, float]:
    """Kilometres east and north of (LAT0, LON0)."""
    return (lon - LON0) * km_per_degree_lon(LAT0), (lat - LAT0) * KM_PER_DEG_LAT


def wikidata_point(item: str) -> tuple[float, float]:
    path = WIKIDATA / f"{item}.json"
    if not path.exists():
        time.sleep(1)  # Wikidata limits bursts from one address.
    data = json.loads(download(f"https://www.wikidata.org/wiki/Special:EntityData/{item}.json", path))
    values = [c["mainsnak"]["datavalue"]["value"] for c in data["entities"][item]["claims"]["P625"]]
    points = [(v["latitude"], v["longitude"]) for v in values]
    if len(points) == 1:
        return points[0]
    pick = [p for p in points if (round(p[0], 4), round(p[1], 4)) == P625_PICK.get(item)]
    if len(pick) != 1:
        raise SystemExit(f"{item}: {len(points)} P625 values {points}; name one in P625_PICK")
    return pick[0]


def place_point(ref: tuple, osm: list[dict]) -> tuple[tuple[float, float], str]:
    """(lat, lon) and a source URL."""
    match ref:
        case ("wikidata", item):
            return wikidata_point(item), f"https://www.wikidata.org/wiki/{item}"
        case ("osm", node):
            e = osm_element(osm, "node", node)
            return (e["lat"], e["lon"]), f"https://www.openstreetmap.org/node/{node}"
        case ("osm-way-end", way):
            lon, lat = osm_line(osm_element(osm, "way", way))[-1]
            return (lat, lon), f"https://www.openstreetmap.org/way/{way}"
    raise SystemExit(f"unknown place reference {ref}")


class Similarity:
    """Pixel (x, y down) -> km (east, north) as one complex number: z_km = s * (x - iy) + t."""

    def __init__(self, pixels: list[tuple[float, float]], kms: list[tuple[float, float]], turn: complex | None = None):
        """Least squares on the places. With `turn` (a unit complex number, for a map that is not to scale) nothing is
        fitted: today's map is turned by it and framed so that the real places fill the box of the drawn ones."""
        if len(pixels) < 3:
            raise SystemExit("a similarity fit with residuals needs at least 3 places")
        drawn = [complex(x, -y) for x, y in pixels]
        if turn:
            real = [complex(e, n) / turn for e, n in kms]
            span = lambda zs: (max(z.real for z in zs) - min(z.real for z in zs), max(z.imag for z in zs) - min(z.imag for z in zs))
            middle = lambda zs: complex((max(z.real for z in zs) + min(z.real for z in zs)) / 2,
                                        (max(z.imag for z in zs) + min(z.imag for z in zs)) / 2)
            (rw, rh), (dw, dh) = span(real), span(drawn)
            self.s = max(rw / dw, rh / dh) * turn  # km per pixel: the larger ratio keeps every real place in the box.
            self.t = turn * middle(real) - self.s * middle(drawn)
            return
        rows, rhs = [], []
        for w, (e, n) in zip(drawn, kms):
            rows += [[w.real, -w.imag, 1, 0], [w.imag, w.real, 0, 1]]
            rhs += [e, n]
        a, b, c, d = np.linalg.lstsq(np.array(rows, float), np.array(rhs, float), rcond=None)[0]
        self.s, self.t = complex(a, b), complex(c, d)

    def to_km(self, x: float, y: float) -> tuple[float, float]:
        z = self.s * complex(x, -y) + self.t
        return z.real, z.imag

    def to_pixel(self, e: float, n: float) -> tuple[float, float]:
        z = (complex(e, n) - self.t) / self.s
        return z.real, -z.imag

    def north_deg(self) -> float:
        """Direction of north on the image, clockwise from up."""
        z = 1j / self.s
        return math.degrees(math.atan2(z.real, z.imag)) % 360


def project(points_lonlat, fit: Similarity, size: tuple[int, int], keep_whole: bool) -> list[list[list[float]]]:
    """Lon/lat points as image pixels, thinned to 1 px steps. Rings (keep_whole) stay whole when any point is near the
    frame; lines keep only their runs inside a frame padded by 10%."""
    w, h = size
    pad = 0.1 * max(w, h)
    inside = lambda p: -pad <= p[0] <= w + pad and -pad <= p[1] <= h + pad
    pixels = [fit.to_pixel(*km(lat, lon)) for lon, lat in points_lonlat]
    runs = [pixels] if keep_whole and any(map(inside, pixels)) else []
    if not keep_whole:
        run: list = []
        for p in pixels:
            if inside(p):
                run.append(p)
            elif run:
                runs.append(run)
                run = []
        runs.append(run)
    out = []
    for run in runs:
        thin = [run[0]] if run else []
        for p in run[1:]:
            if math.dist(p, thin[-1]) >= 1:
                thin.append(p)
        if len(thin) >= 2:
            out.append([[round(x, 1), round(y, 1)] for x, y in thin])
    return out


def north_words(north: float) -> str:
    """Direction of north on the image (degrees clockwise from up) in words."""
    turn = (north + 180) % 360 - 180
    if abs(turn) < 5:
        return "למעלה"
    return f"\u2068{abs(turn):.0f}\u2069 מעלות {'ימינה' if turn > 0 else 'שמאלה'} מהכיוון למעלה"


def fit_text(places: list[dict], loose: str | None, north: float) -> str:
    if loose:  # No error numbers for a map that is not to scale.
        return loose
    fitted = [p for p in places if p["fitted"]]
    rms = math.sqrt(sum(p["km"] ** 2 for p in fitted) / len(fitted))
    worst = max(fitted, key=lambda p: p["km"])
    text = (f"לפי ההתאמה, הצפון פונה במפה {north_words(north)} (החץ במפה של היום). "
            f"ההתאמה לפי {len(fitted)} מקומות: סטייה ממוצעת (RMS) ⁨{rms:.1f}⁩ ק\"מ, הגדולה ביותר "
            f"⁨{worst['km']:.1f}⁩ ק\"מ ({worst['name']}).")
    for p in places:
        if not p["fitted"]:
            text += f" {p['name']}, שלא נכלל בהתאמה, רחוק ⁨{p['km']:.0f}⁩ ק\"מ ממקומו במפה."
    return text


def build(figure: str, spec: dict, osm: list[dict], water: dict, coast: dict, osm_date: str) -> dict:
    image = IMAGES / spec["image"]
    with Image.open(image) as im:
        size = im.size
    real = {key: place_point(PLACES[key][1], osm) for key, *_ in spec["points"]}
    fitted = [p for p in spec["points"] if p[3]]
    fit = Similarity([p[2] for p in fitted], [km(*real[p[0]][0]) for p in fitted], spec.get("turn"))
    places = []
    for key, printed, (x, y), is_fitted in spec["points"]:
        (lat, lon), url = real[key]
        e, n = km(lat, lon)
        fe, fn = fit.to_km(x, y)
        tx, ty = fit.to_pixel(e, n)
        places.append({"name": PLACES[key][0], "printed": printed, "map": [x, y], "true": [round(tx, 1), round(ty, 1)],
                       "km": round(math.hypot(fe - e, fn - n), 2), "fitted": is_fitted, "source": url})
    for p in places:
        print(f"{figure} {p['printed']:<28} {'fit' if p['fitted'] else 'check'} {p['km']:6.2f} km")
    rms = math.sqrt(sum(p["km"] ** 2 for p in places if p["fitted"]) / len(fitted))
    north = fit.north_deg()
    print(f"{figure}: RMS {rms:.2f} km, north {north:.0f} deg, {abs(fit.s):.4f} km/px")
    loose = "loose" in spec
    if loose:
        for p in places:
            p["km"] = None
    yarmouk, mouth = (km(*place_point(PLACES[k][1], osm)[0]) for k in ("yarmouk", "jordan_mouth"))
    old_text = spec["old"].format(yarmouk_km=math.dist(yarmouk, mouth))
    year = spec["year"]
    sources = [{"label": label, "element": element} for label, element in spec["sources"]]
    sources += [
        {"label": "קו החוף ובריכות האידוי של היום: © OpenStreetMap contributors (ODbL)", "url": "https://www.openstreetmap.org/copyright"},
        {"label": "חוף הים התיכון: Natural Earth", "url": "https://www.naturalearthdata.com/about/terms-of-use/"},
        {"label": "מיקום המקומות: Wikidata ו־OpenStreetMap", "url": "https://www.wikidata.org/wiki/Wikidata:Licensing"},
    ]
    return {
        "figure": figure,
        "kind": "old-map",
        "title": spec["title"],
        "instruction": INSTRUCTION,
        "schematic": SCHEMATIC,
        # Start at 30: the handle sits fully inside the drawing (at 0 half of it is cut off and hard to grab).
        "control": {"label": "המפה של היום", "min": 0, "max": 100, "step": 1, "start": 30, "unit": "%", "hint": 30},
        "marks": [{"value": 0, "label": year}, {"value": 100, "label": "היום"}],
        "legend": LEGEND,
        "view": [0, 0, *size],
        "image": f"book/OEBPS/images/{spec['image']}",
        "fit": {"kind": "turned as the caption says, framed on the places" if loose else "similarity",
                "rms_km": None if loose else round(rms, 2), "north_deg": round(north, 1),
                "km_per_px": round(abs(fit.s), 5), "osm_date": osm_date},
        "places": places,
        "sea": [r for ring in osm_rings(osm_element(osm, "relation", DEAD_SEA)) for r in project(ring, fit, size, True)],
        "ponds": [r for e in water["ponds"] for ring in osm_rings(e) for r in project(ring, fit, size, True)],
        "rivers": [r for e in water["jordan"] for r in project(osm_line(e), fit, size, False)],
        "coast": [r for line in coast for r in project(line, fit, size, False)],
        "labels": {"old": f"המפה של {year}", "now": "היום", "north": "צפון", "osm": "© OpenStreetMap"},
        "texts": {"old": old_text, "fit": fit_text(places, spec.get("loose"), north)},
        "sources": sources,
    }


def main() -> None:
    if not IMAGES.is_dir():
        raise SystemExit(f"{IMAGES} is missing: build the release tree first (uv run scripts/check.py)")
    raw = overpass("old-maps", QUERY)
    osm_date = json.loads((ROOT / "work" / "maps" / "osm" / "old-maps.json").read_text())["osm3s"]["timestamp_osm_base"]
    water = {"ponds": [e for e in raw if e.get("tags", {}).get("landuse") == "salt_pond"],
             "jordan": [e for e in raw if e["type"] == "way" and e["id"] != YARMOUK_END
                        and e.get("tags", {}).get("waterway") == "river"]}
    if not water["ponds"] or not water["jordan"]:
        raise SystemExit("Overpass answer has no salt ponds or no Jordan River")
    # The Mediterranean coast of the area (lon 34-35, lat 30.9-32.3); one feature can run far beyond it.
    coast = [line for f in natural_earth("ne_10m_coastline.geojson")["features"]
             for line in ([f["geometry"]["coordinates"]] if f["geometry"]["type"] == "LineString" else f["geometry"]["coordinates"])
             if any(34 <= lon <= 35 and 30.9 <= lat <= 32.3 for lon, lat in line)]
    if not coast:
        raise SystemExit("no Natural Earth coastline near Gaza")
    OUT.mkdir(parents=True, exist_ok=True)
    for figure, spec in MAPS.items():
        data = build(figure, spec, raw, water, coast, osm_date)
        path = OUT / f"{figure}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
