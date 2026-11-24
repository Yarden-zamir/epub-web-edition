"""Offline reading: writes sw.js (from site/sw.js) with the content hash and kind of every site file.

Runs last (99), so every other feature has written its files. site/features/90-offline.js registers the worker.
"""

import hashlib
import json
from pathlib import Path
from typing import Literal

from build_web import SITE, BookError, Site

type Kind = Literal["shell", "media"]

SKIP = {"build.json", "sw.js"}  # Build report and the worker itself.
SKIP_FOLDERS = {"download"}  # The EPUB download is never cached.
SHELL_SUFFIXES = {".html", ".css", ".js", ".json", ".webmanifest", ".csv", ".ttf", ".otf", ".woff", ".woff2"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg", ".ico"}


def kind(path: str) -> Kind:
    """Shell files are saved at install; media are saved once read. Images at the root are the app icons (shell)."""
    suffix = Path(path).suffix.lower()
    if suffix in SHELL_SUFFIXES or (suffix in IMAGE_SUFFIXES and "/" not in path):
        return "shell"
    if suffix in IMAGE_SUFFIXES:
        return "media"
    raise BookError(f"99_offline.py: no cache rule for {path}; add its suffix to SHELL_SUFFIXES or IMAGE_SUFFIXES")


def write(site: Site) -> None:
    files: dict[str, tuple[str, Kind]] = {}
    for file in sorted(p for p in site.out.rglob("*") if p.is_file()):
        path = file.relative_to(site.out).as_posix()
        if path in SKIP or path.split("/", 1)[0] in SKIP_FOLDERS:
            continue
        files[path] = (hashlib.sha256(file.read_bytes()).hexdigest()[:12], kind(path))
    listing = json.dumps(files, ensure_ascii=False, separators=(",", ":"))
    version = hashlib.sha256(listing.encode()).hexdigest()[:12]
    template = (SITE / "sw.js").read_text(encoding="utf-8")
    for marker in ('"__VERSION__"', "__FILES__"):
        if template.count(marker) != 1:
            raise BookError(f"site/sw.js: expected one {marker}")
    worker = template.replace('"__VERSION__"', json.dumps(version)).replace("__FILES__", listing)
    (site.out / "sw.js").write_text(worker, encoding="utf-8")
    shell = [p for p, (_, k) in files.items() if k == "shell"]
    site.report["offline"] = {
        "version": version,
        "shell_files": len(shell),
        "shell_bytes": sum((site.out / p).stat().st_size for p in shell),
        "media_files": len(files) - len(shell),
        "media_bytes": sum((site.out / p).stat().st_size for p, (_, k) in files.items() if k == "media"),
    }
