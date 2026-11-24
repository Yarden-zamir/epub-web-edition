"""Site-only originals: enhancements.json "figures" maps a figure ID to a larger original that the figure viewer opens."""

import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from build_web import BookError, Converter, Site, missing_id


def load_enhancements(out: Path, conv: Converter, path: Path | None) -> dict[str, dict[str, str]]:
    """Validate the enhancements file against the EPUB and copy referenced site-only assets."""
    if path is None:
        return {}
    content_root = path.resolve().parent.parent
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, str]] = {}
    for fig_id, fig in data["figures"].items():
        if conv.tags.get(fig_id) != "figure":
            raise missing_id("enhancements.json: figures", fig_id, "a figure")
        original = content_root / fig["original"]
        if not original.is_file():
            raise BookError(f"enhancements.json: {fig_id}: {original} does not exist")
        dest = out / "originals" / original.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, dest)
        result[fig_id] = {"original": f"originals/{original.name}"}
    return result


ORIGINALS: dict[str, dict[str, str]] = {}  # Figure ID -> data attributes. Fresh for each build (the module loads per build).


def load(site: Site) -> None:
    ORIGINALS.update(load_enhancements(site.out, site.conv, site.enhancements_file))


def transform(site: Site, body: ET.Element, top: ET.Element | None, kind: str) -> None:
    for el in body.iter():
        for key, value in ORIGINALS.get(el.get("id", ""), {}).items():
            el.set(f"data-{key}", value)


def write(site: Site) -> None:
    site.report["enhanced_ids"] = sorted(ORIGINALS)
