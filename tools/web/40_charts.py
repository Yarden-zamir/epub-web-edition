"""Charts: charts/<figure>.json and enhancements.json "charts" draw interactive charts inside their printed figures."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from build_web import BookError, Converter, Site, missing_id, write_csv


def chart_panel(spec: dict, where: str) -> dict:
    """Check one charts/<figure>.json file and return the panel that reader.js draws. Format:
    {figure, title, source: {kind, label, url?, method, accuracy?: {x, y}, ...}, x: {label, unit, type: year|number},
    y: {label, unit}, series: [{name, kind: line|points, points: [[x, y], ...]}], bands?: [{axis, from, to, label}],
    markers?: [{axis, at, label}], notes?}. Line points keep their drawing order: x may repeat or step back."""
    if spec["x"]["type"] not in ("year", "number") or not spec["series"]:
        raise BookError(f"{where}: x.type must be year or number, and there must be series")
    for series in spec["series"]:
        if series["kind"] not in ("line", "points") or len(series["points"]) < 2:
            raise BookError(f"{where}: series {series['name']!r} needs kind line or points and two or more points")
        if any(len(pt) != 2 or not all(isinstance(v, (int, float)) for v in pt) for pt in series["points"]):
            raise BookError(f"{where}: series {series['name']!r} has a point that is not [x, y]")
    for item in [*spec.get("bands", []), *spec.get("markers", [])]:
        if item["axis"] not in ("x", "y"):
            raise BookError(f"{where}: band or marker axis must be x or y")
    source = spec["source"]
    if source.get("url") and not source["url"].startswith("https://"):
        raise BookError(f"{where}: source URL must be https")
    accuracy = source.get("accuracy")
    line = source["label"]
    if source["kind"] == "digitized":
        line += ". דיגיטציה של האיור המודפס"
        if accuracy:
            line += f"; דיוק: {accuracy['x']} בציר האופקי, {accuracy['y']} בציר האנכי"
    # Only public fields go to the site; source.overlay is a private review image.
    return {"title": spec["title"], "x": spec["x"], "y": spec["y"], "series": spec["series"],
            "bands": spec.get("bands", []), "markers": spec.get("markers", []), "notes": spec.get("notes", ""),
            "source": {"line": line + ".", "url": source.get("url"), "method": source.get("method", "")}}


def measured_panel(spec: dict, data: dict, where: str) -> dict:
    """Panel for a live measured series from the enhancements file: [ISO date, value] points."""
    points = data["points"]
    if len(points) < 2 or any(len(pt) != 2 for pt in points):
        raise BookError(f"{where}: needs at least two [date, value] points")
    if not data["source"]["url"].startswith("https://"):
        raise BookError(f"{where}: source URL must be https")
    years = f"{points[0][0][:4]}–{points[-1][0][:4]}"
    return {"title": spec["title"], "x": {"label": "תאריך", "unit": "", "type": "date"},
            "y": {"label": spec["unit"], "unit": ""}, "series": [{"name": spec["title"], "kind": "line", "points": points}],
            "bands": [], "markers": [], "notes": "",
            "source": {"line": f"נתונים עדכניים שנוספו לאתר, {years}: {data['source']['label']}.", "url": data["source"]["url"], "method": ""}}


def panel_table(panel: dict) -> ET.Element:
    """Data table of one panel. A dated series shows its first reading of each year."""
    table = ET.Element("table", {"class": "data-table"})
    ET.SubElement(table, "caption").text = panel["title"]
    head = ET.SubElement(ET.SubElement(table, "thead"), "tr")
    x_name = " ".join(filter(None, [panel["x"]["label"], panel["x"]["unit"] and f"({panel['x']['unit']})"]))
    y_name = " ".join(filter(None, [panel["y"]["label"], panel["y"]["unit"] and f"({panel['y']['unit']})"]))
    names = ["סדרה", x_name, y_name] if len(panel["series"]) > 1 else [x_name, y_name]
    for name in names:
        ET.SubElement(head, "th", {"scope": "col"}).text = name
    body = ET.SubElement(table, "tbody")
    for series in panel["series"]:
        points = series["points"]
        if panel["x"]["type"] == "date":
            first: dict[str, list] = {}
            for pt in points:
                first.setdefault(pt[0][:4], pt)
            points = list(first.values())
        for x, y in points:
            tr = ET.SubElement(body, "tr")
            if len(panel["series"]) > 1:
                ET.SubElement(tr, "td").text = series["name"]
            ET.SubElement(tr, "th", {"scope": "row", "dir": "ltr"}).text = f"{x:g}" if isinstance(x, float) else str(x)
            ET.SubElement(tr, "td", {"dir": "ltr"}).text = f"{y:g}"
    return table


def chart_box(fig_id: str, panels: list[dict], href: str, csv_href: str) -> ET.Element:
    """Drawing area for reader.js, the source line of each panel, data tables and a CSV link."""
    box = ET.Element("div", {"class": "chart-box", "data-chart": href})
    ET.SubElement(box, "div", {"class": "chart-area", "hidden": "hidden"})
    for panel in panels:
        line = ET.SubElement(box, "p", {"class": "chart-source"})
        if panel["source"]["url"]:
            ET.SubElement(line, "a", {"href": panel["source"]["url"], "rel": "noopener"}).text = panel["source"]["line"]
        else:
            line.text = panel["source"]["line"]
        if panel["notes"]:
            ET.SubElement(box, "p", {"class": "chart-notes"}).text = panel["notes"]
    details = ET.SubElement(box, "details", {"class": "print-version"})
    ET.SubElement(details, "summary").text = "הנתונים בטבלה"
    for panel in panels:
        details.append(panel_table(panel))
    ET.SubElement(box, "a", {"class": "csv-link", "href": csv_href, "download": ""}).text = "הורדת הנתונים (CSV)"
    return box


def load_charts(out: Path, enhancements_file: Path | None, data_dir: Path | None, conv: "Converter") -> dict[str, ET.Element]:
    panels: dict[str, list[dict]] = {}
    measured = json.loads(enhancements_file.read_text(encoding="utf-8")).get("charts", {}) if enhancements_file else {}
    for fig_id, spec in measured.items():
        data = json.loads((enhancements_file.resolve().parent.parent / spec["data"]).read_text(encoding="utf-8"))
        panels.setdefault(fig_id, []).append(measured_panel(spec, data, f"enhancements.json: chart for {fig_id}"))
    for path in sorted((data_dir / "charts").glob("*.json")) if data_dir else []:
        spec = json.loads(path.read_text(encoding="utf-8"))
        if spec["figure"] != path.stem:
            raise BookError(f"{path.name}: figure {spec['figure']!r} does not match the file name")
        panels.setdefault(path.stem, []).append(chart_panel(spec, f"charts/{path.name}"))
    result = {}
    for fig_id, figure_panels in panels.items():
        if conv.tags.get(fig_id) != "figure":
            raise missing_id("chart", fig_id, "a figure")
        (out / "data" / "charts").mkdir(parents=True, exist_ok=True)
        (out / "data" / "charts" / f"{fig_id}.json").write_text(
            json.dumps({"figure": fig_id, "panels": figure_panels}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        rows = [[panel["title"], series["name"], x, y] for panel in figure_panels for series in panel["series"] for x, y in series["points"]]
        write_csv(out / "data" / "charts" / f"{fig_id}.csv", ["גרף", "סדרה", "x", "y"], rows)
        result[fig_id] = chart_box(fig_id, figure_panels, f"data/charts/{fig_id}.json", f"data/charts/{fig_id}.csv")
    return result


CHARTS: dict[str, ET.Element] = {}  # Printed figure ID -> chart box placed inside it.


def load(site: Site) -> None:
    CHARTS.update(load_charts(site.out, site.enhancements_file, site.data_dir, site.conv))


def transform(site: Site, body: ET.Element, top: ET.Element | None, kind: str) -> None:
    for fig in list(body.iter("figure")):
        if (box := CHARTS.get(fig.get("id", ""))) is not None:
            caption = fig.find("figcaption")
            fig.insert(list(fig).index(caption) if caption is not None else len(fig), box)
            fig.set("class", (fig.get("class", "") + " has-chart").strip())
