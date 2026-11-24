"""Maps inside printed figures: figure maps (figure-maps/<figure ID>.json) and the then-and-now view (then-now.json).

Both files sit next to the enhancements file; their formats are in books/eli-raz/AGENTS-BRIEF.md and the files' own notes.
The build checks every figure and element ID against the EPUB, writes the browser data to data/maps/<figure ID>.json,
writes the then-and-now images to media/then-now/ at the size the view needs, and puts a hidden box inside each figure.
site/features/75-map-figures.js fills the box and adds a toggle between the map and the printed image.
"""

import html
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from build_web import BookError, Site, missing_id

# Line colours for figure maps: the first three slots of the dataviz reference palette, the only slots that stay apart
# for colour-blind readers when all pairs can meet (site/features/75-map-figures.css). Each slot also has its own dash.
LINE_SLOTS = 3
BOXES: dict[str, ET.Element] = {}  # Printed figure ID -> map box placed inside it.
IMAGES: list[tuple[Path, str]] = []  # Then-and-now images: (source file, path in the site).
# The long side of a then-and-now image in the site: about twice the largest map box (44rem), for sharp screens.
# Known limit: a reader who zooms in far sees the image soften. Revisit if the view gets a zoom past the fitted layer.
THEN_NOW_SIDE = 1600
THEN_NOW_QUALITY = 70  # WebP quality: each layer lands between 80 and 400 KB.


def check_lat_lon(lat: float, lon: float, where: str) -> None:
    if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise BookError(f"{where}: bad coordinates {lat!r}, {lon!r}")


def check_bounds(bounds: list, where: str) -> list:
    """[[south, west], [north, east]] with south < north and west < east."""
    (s, w), (n, e) = bounds
    for lat, lon in bounds:
        check_lat_lon(lat, lon, where)
    if not (s < n and w < e):
        raise BookError(f"{where}: bounds must be [[south, west], [north, east]]: {bounds}")
    return [[s, w], [n, e]]


def book_path(site: Site, path: str, where: str) -> Path:
    """A path in then-now.json, written from the book folder ("site/media/…"), as a file in the site data folder."""
    if not path.startswith("site/"):
        raise BookError(f"{where}: {path!r} must start with site/")
    return site.data_dir / path.removeprefix("site/")


def credit_html(lines: list[str], links: dict[str, str], where: str) -> str:
    """The attribution lines as HTML, with the first use of each linked word made a link."""
    text = " · ".join(html.escape(line) for line in lines)
    for word, url in links.items():
        if not url.startswith("https://"):
            raise BookError(f"{where}: attribution link for {word!r} must be https")
        key = html.escape(word)
        if key not in text:
            raise BookError(f"{where}: attribution_links names {word!r}, which no attribution line has")
        text = text.replace(key, f'<a href="{html.escape(url)}" rel="noopener">{key}</a>', 1)
    return text


def map_box(figure: str, kind: str) -> ET.Element:
    """Hidden until 75-map-figures.js fills it, so a page without JavaScript shows only the printed figure."""
    return ET.Element("div", {"class": "map-figure", "data-map": f"data/maps/{figure}.json", "data-kind": kind, "hidden": "hidden"})


def load_figure_map(site: Site, path: Path) -> dict:
    where = f"figure-maps/{path.name}"
    spec = json.loads(path.read_text(encoding="utf-8"))
    figure = spec["figure"]
    if figure != path.stem:
        raise BookError(f"{where}: figure {figure!r} does not match the file name")
    if spec["base"] != "opentopomap":
        raise BookError(f"{where}: base {spec['base']!r}: only opentopomap is drawn")
    markers = []
    for m in spec["markers"]:
        check_lat_lon(m["lat"], m["lon"], f"{where}: marker {m['name']!r}")
        if not m.get("source"):
            raise BookError(f"{where}: marker {m['name']!r} needs a source")
        if m.get("target") and m["target"] not in site.conv.tags:
            raise missing_id(where, m["target"])
        markers.append({"name": m["name"], "lat": m["lat"], "lon": m["lon"], "target": m.get("target")})
    names: list[str] = []  # One legend entry and one colour slot per line name; a long road can come in several parts.
    lines = []
    for line in spec["lines"]:
        if not line.get("source"):
            raise BookError(f"{where}: line {line['name']!r} needs a source")
        for lat, lon in line["coords"]:
            check_lat_lon(lat, lon, f"{where}: line {line['name']!r}")
        if line["name"] not in names:
            names.append(line["name"])
        lines.append({"slot": names.index(line["name"]) + 1, "coords": line["coords"]})
    if len(names) > LINE_SLOTS:
        raise BookError(f"{where}: {len(names)} line names; colour-blind readers can tell at most {LINE_SLOTS} apart")
    areas = []
    for area in spec.get("areas", []):
        if not area.get("source"):
            raise BookError(f"{where}: area {area['name']!r} needs a source")
        for lat, lon in area["coords"]:
            check_lat_lon(lat, lon, f"{where}: area {area['name']!r}")
        areas.append({"name": area["name"], "coords": area["coords"]})
    return {
        "kind": "figure-map", "figure": figure, "title": spec["title"], "bounds": check_bounds(spec["bounds"], where),
        "markers": markers, "lines": lines, "legend": names, "areas": areas,
        "credit": credit_html(spec["attribution"], spec.get("attribution_links", {}), where),
    }


def load_then_now(site: Site, path: Path) -> dict:
    where = path.name
    spec = json.loads(path.read_text(encoding="utf-8"))
    levels = spec["levels"]
    layers = []
    for layer in spec["layers"]:
        lw = f"{where}: layer {layer['id']!r}"
        image = book_path(site, layer["image"], lw)
        if not image.is_file():
            raise BookError(f"{lw}: {image} does not exist")
        if image.stat().st_size != layer["bytes"]:
            raise BookError(f"{lw}: {image.name} has {image.stat().st_size} bytes, the spec says {layer['bytes']}")
        if not layer["credit"]["url"].startswith("https://"):
            raise BookError(f"{lw}: credit url must be https")
        level = dict(levels[layer["level"]])
        if level["source"].startswith("site/data/"):  # A local data file: its last point is the level.
            data = json.loads(book_path(site, level["source"], lw).read_text(encoding="utf-8"))
            date, value = data["points"][-1]
            if date != level["date"] or value != level["value"]:
                raise BookError(f"{lw}: level {level['value']} on {level['date']} is not the last point of {level['source']}")
            level |= {"source": data["source"]["label"], "url": data["source"]["url"]}
        if not level.get("url", "").startswith("https://"):
            raise BookError(f"{lw}: the level needs an https source url")
        url = f"media/then-now/{image.stem}.webp"
        if any(url == used for _, used in IMAGES):
            raise BookError(f"{lw}: two layer images give the same site file {url}")
        IMAGES.append((image, url))
        layers.append({
            "id": layer["id"], "label": layer["label"], "year": layer["date"][:4], "image": url,
            "bounds": check_bounds(layer["bounds"], lw), "credit": layer["credit"],
            "level": {k: level[k] for k in ("value", "date", "source", "url")},
        })
    years = [int(layer["year"]) for layer in layers]
    if years != sorted(years):
        raise BookError(f"{where}: layers must run from old to new")
    return {"kind": "then-now", "figure": spec["figure"], "title": spec["title"], "layers": layers}


DATA: dict[str, dict] = {}  # Figure ID -> browser data.
PLACED: set[str] = set()  # Figure IDs that got their map box.


def load(site: Site) -> None:
    if site.data_dir is None:
        return
    specs = []
    if (folder := site.data_dir / "figure-maps").is_dir():
        specs += [load_figure_map(site, path) for path in sorted(folder.glob("*.json"))]
    if (path := site.data_dir / "then-now.json").is_file():
        specs.append(load_then_now(site, path))
    for spec in specs:
        figure = spec["figure"]
        if site.conv.tags.get(figure) != "figure":
            raise BookError(f"{figure}: a map needs a figure in the EPUB")
        if figure in DATA:
            raise BookError(f"{figure}: two maps for one figure")
        DATA[figure] = spec
        BOXES[figure] = map_box(figure, spec["kind"])


def transform(site: Site, body: ET.Element, top: ET.Element | None, kind: str) -> None:
    for fig in body.iter("figure"):
        if (box := BOXES.get(fig.get("id", ""))) is None:
            continue
        if fig.find("img") is None:
            raise BookError(f"{fig.get('id')}: a map needs a figure with an image (the printed map)")
        classes = fig.get("class", "").split()
        if {"has-chart", "has-explorable"} & set(classes):
            raise BookError(f"{fig.get('id')}: a figure takes one of a chart, an explorable or a map")
        caption = fig.find("figcaption")
        fig.insert(list(fig).index(caption) if caption is not None else len(fig), box)
        fig.set("class", " ".join([*classes, "has-map"]))
        PLACED.add(fig.get("id"))


def write(site: Site) -> None:
    if missing := DATA.keys() - PLACED:
        raise BookError(f"maps for figures that the book does not show: {sorted(missing)}")
    if not DATA:
        return
    (site.out / "data" / "maps").mkdir(parents=True, exist_ok=True)
    for figure, spec in DATA.items():
        (site.out / "data" / "maps" / f"{figure}.json").write_text(json.dumps(spec, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sizes = {}
    for source, url in IMAGES:
        dest = site.out / url
        dest.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as im:
            im.thumbnail((THEN_NOW_SIDE, THEN_NOW_SIDE), Image.Resampling.LANCZOS)  # Never enlarges; keeps transparency.
            im.save(dest, "WEBP", quality=THEN_NOW_QUALITY, method=6)
        sizes[url] = {"source_bytes": source.stat().st_size, "bytes": dest.stat().st_size}
    site.report["map_figures"] = sorted(DATA)
    if sizes:
        site.report["then_now_images"] = sizes
