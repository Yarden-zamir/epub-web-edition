"""Interactive explainers ("explorables") placed inside printed figures of the web edition.

Each file explorables/<figure ID>.json next to the enhancements file describes one explainer:
{
  "figure": the printed figure it explains (must match the file name),
  "kind": the drawing module in site/features/explorables/<kind>.js,
  "title", "instruction" (one short Hebrew line), "schematic" (what is simplified),
  "control": {"label", "min", "max", "step", "start", "unit"},
  "sources": [{"label", "element"?: book element ID, "url"?}],
  "data"?: {name: {"file": path under the folder of the enhancements file, "series"?: series name in a charts file}},
  anything else the drawing module reads (labels, values), each value with its source in "sources".
}
The build checks the figure and every source element against the EPUB, embeds the named data series,
and writes data/explorables/<figure ID>.json. site/features/72-explorables.js adds a toggle between the
explainer and the printed image; 7N-explorable-<kind>.js files draw each kind.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from build_web import BookError, Site


REQUIRED = ("figure", "kind", "title", "instruction", "schematic", "control", "sources")
CONTROL = ("label", "min", "max", "step", "start", "unit")


def load_data(data_dir: Path, name: str, ref: dict, where: str) -> dict:
    """One data series: a level file ({source, points}) or one series of a charts/<figure>.json file."""
    path = data_dir / ref["file"]
    if not path.is_file():
        raise BookError(f"{where}: data {name!r}: {path} does not exist")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "series" in ref:
        series = next((s for s in raw["series"] if s["name"] == ref["series"]), None)
        if series is None:
            raise BookError(f"{where}: data {name!r}: no series {ref['series']!r} in {ref['file']}")
        return {"source": raw["source"]["label"], "url": raw["source"].get("url", ""), "points": series["points"]}
    return {"source": raw["source"]["label"], "url": raw["source"].get("url", ""), "points": raw["points"]}


def explorable_box(spec: dict, href: str) -> ET.Element:
    """Hidden until explorables.js fills it, so a page without JavaScript shows only the printed figure."""
    box = ET.Element("div", {"class": "explorable", "data-explorable": href, "data-kind": spec["kind"], "hidden": "hidden"})
    ET.SubElement(box, "p", {"class": "xp-schematic"}).text = spec["schematic"]
    sources = ET.SubElement(box, "p", {"class": "xp-sources"})
    sources.text = "מקורות: "
    for i, source in enumerate(spec["sources"]):
        if i:
            ET.SubElement(sources, "span").text = "; "
        if source.get("element"):
            ET.SubElement(sources, "a", {"href": f"#{source['element']}"}).text = source["label"]
        elif source.get("url"):
            ET.SubElement(sources, "a", {"href": source["url"], "rel": "noopener"}).text = source["label"]
        else:
            ET.SubElement(sources, "span").text = source["label"]
    return box


BOXES: dict[str, ET.Element] = {}  # Printed figure ID -> explainer box placed inside it.


def load(site: Site) -> None:
    folder = site.data_dir / "explorables" if site.data_dir else None
    if folder is None or not folder.is_dir():
        return
    data_dir, tags, out = site.data_dir, site.conv.tags, site.out
    for path in sorted(folder.glob("*.json")):
        where = f"explorables/{path.name}"
        spec = json.loads(path.read_text(encoding="utf-8"))
        missing = [key for key in REQUIRED if key not in spec] + [f"control.{k}" for k in CONTROL if k not in spec.get("control", {})]
        if missing:
            raise BookError(f"{where}: missing {missing}")
        if spec["figure"] != path.stem:
            raise BookError(f"{where}: figure {spec['figure']!r} does not match the file name")
        if tags.get(spec["figure"]) != "figure":
            raise BookError(f"{where}: {spec['figure']!r} is not a figure in the EPUB")
        for source in spec["sources"]:
            if not source.get("label") or not (source.get("element") or source.get("url")):
                raise BookError(f"{where}: each source needs a label and an element or a url: {source}")
            if source.get("element") and source["element"] not in tags:
                raise BookError(f"{where}: source element {source['element']!r} is not in the EPUB")
        control = spec["control"]
        if not control["min"] <= control["start"] <= control["max"]:
            raise BookError(f"{where}: control start {control['start']} is outside {control['min']}..{control['max']}")
        spec["data"] = {name: load_data(data_dir, name, ref, where) for name, ref in spec.get("data", {}).items()}
        (out / "data" / "explorables").mkdir(parents=True, exist_ok=True)
        (out / "data" / "explorables" / path.name).write_text(
            json.dumps(spec, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        BOXES[spec["figure"]] = explorable_box(spec, f"data/explorables/{path.name}")


def transform(site: Site, body: ET.Element, top: ET.Element | None, kind: str) -> None:
    for fig in list(body.iter("figure")):
        if (box := BOXES.get(fig.get("id", ""))) is not None:
            if "has-chart" in fig.get("class", "").split():
                raise BookError(f"{fig.get('id')}: a figure takes a chart or an explorable, not both")
            caption = fig.find("figcaption")
            fig.insert(list(fig).index(caption) if caption is not None else len(fig), box)
            fig.set("class", (fig.get("class", "") + " has-explorable").strip())
