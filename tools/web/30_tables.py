"""Data tables: enhancements.json "tables" turns a figure that prints a table as an image into a sortable table with a CSV file."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from build_web import BookError, Converter, Site, missing_id, write_csv


def leading_number(cell: str) -> float | None:
    """First number in a printed cell, for example 3630 in "3630 (700%)" or 9010 in "9,010"."""
    token = cell.strip().split(" ", 1)[0].replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


def table_element(fig_id: str, spec: dict) -> ET.Element:
    columns, rows, bar = spec["columns"], spec["rows"], spec.get("bar")
    ltr = set(spec.get("ltr", []))
    if any(len(r) != len(columns) for r in rows):
        raise BookError(f"enhancements.json: table {fig_id}: every row needs {len(columns)} cells")
    peak = max((leading_number(r[bar]) or 0) for r in rows) if bar is not None else 0
    table = ET.Element("table", {"class": "data-table"})
    head = ET.SubElement(ET.SubElement(table, "thead"), "tr")
    for i, name in enumerate(columns):
        th = ET.SubElement(head, "th", {"scope": "col"})
        ET.SubElement(th, "button", {"type": "button", "data-sort": str(i)}).text = name
    tbody = ET.SubElement(table, "tbody")
    for row in rows:
        tr = ET.SubElement(tbody, "tr")
        for i, cell in enumerate(row):
            attrs = {"dir": "ltr"} if i in ltr else {}
            value = leading_number(cell)
            if value is not None:
                attrs["data-value"] = f"{value:g}"
            if i == bar and value is not None and peak:
                attrs["class"] = "bar"
                attrs["style"] = f"--v: {value / peak:.3f}"
            td = ET.SubElement(tr, "th" if i == 0 else "td", attrs | ({"scope": "row"} if i == 0 else {}))
            ET.SubElement(td, "span").text = cell
    return table


def attach_table(fig: ET.Element, spec: dict) -> None:
    """Put the data table first in the figure and fold the printed image into a details element."""
    img = fig.find("img")
    if img is None:
        raise BookError(f"enhancements.json: table {fig.get('id')}: the figure has no direct img")
    details = ET.Element("details", {"class": "print-version"})
    ET.SubElement(details, "summary").text = "הטבלה כפי שהודפסה"
    index = list(fig).index(img)
    fig.remove(img)
    details.append(img)
    fig.insert(index, details)
    fig.insert(0, table_element(fig.get("id", ""), spec))
    link = ET.Element("a", {"class": "csv-link", "href": f"data/tables/{fig.get('id')}.csv", "download": ""})
    link.text = "הורדת הטבלה (CSV)"
    fig.insert(1, link)
    fig.set("class", (fig.get("class", "") + " has-table").strip())


def load_tables(path: Path | None, conv: "Converter") -> dict[str, dict]:
    tables = json.loads(path.read_text(encoding="utf-8")).get("tables", {}) if path else {}
    for fig_id in tables:
        if conv.tags.get(fig_id) != "figure":
            raise missing_id("enhancements.json: table", fig_id, "a figure")
    return tables


TABLES: dict[str, dict] = {}


def load(site: Site) -> None:
    TABLES.update(load_tables(site.enhancements_file, site.conv))
    for fig_id, spec in TABLES.items():
        write_csv(site.out / "data" / "tables" / f"{fig_id}.csv", spec["columns"], spec["rows"])


def transform(site: Site, body: ET.Element, top: ET.Element | None, kind: str) -> None:
    for fig in list(body.iter("figure")):
        if (spec := TABLES.get(fig.get("id", ""))):
            attach_table(fig, spec)
