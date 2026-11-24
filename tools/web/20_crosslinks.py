"""Cross-links: crosslinks.json turns the exact text that names a chapter into a link to it."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from build_web import BookError, Converter, Site, missing_id, text_slots, wrap_text


def add_crosslink(el: ET.Element, link: dict) -> None:
    """Link the exact text that names a chapter. A match that is already inside a link (the EPUB has it) stays as is."""
    for owner, slot in text_slots(el):
        if (at := (getattr(owner, slot) or "").find(link["text"])) >= 0:
            wrap_text(el, owner, slot, at, at + len(link["text"]),
                      ET.Element("a", {"class": "crosslink", "href": f"#{link['target']}"}))
            return
    if link["text"] not in "".join(el.itertext()):  # Present but not found above: it sits inside a link already.
        raise BookError(f"crosslinks.json: {link['text'][:40]!r} is not in {el.get('id')}")


def load_crosslinks(data_dir: Path | None, conv: "Converter") -> dict[str, list[dict]]:
    path = data_dir / "crosslinks.json" if data_dir else None
    if path is None or not path.is_file():
        return {}
    result: dict[str, list[dict]] = {}
    for link in json.loads(path.read_text(encoding="utf-8"))["links"]:
        for ref in (link["element"], link["target"]):
            if ref not in conv.ids:
                raise missing_id(f"crosslinks.json: {link['element']} -> {link['target']}", ref)
        result.setdefault(link["element"], []).append(link)
    return result


CROSSLINKS: dict[str, list[dict]] = {}


def load(site: Site) -> None:
    CROSSLINKS.update(load_crosslinks(site.data_dir, site.conv))


def transform(site: Site, body: ET.Element, top: ET.Element | None, kind: str) -> None:
    if top is not None:
        for el in list(top.iter()):
            for link in CROSSLINKS.get(el.get("id", ""), []):
                add_crosslink(el, link)
