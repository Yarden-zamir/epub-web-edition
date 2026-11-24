"""Offline reading: writes sw.js (from site/sw.js) with the content hash and kind of every site file, after it
gives each page's script and style links a ?v=<content hash> (version_links).

Runs last (99), so every other feature has written its files. site/features/90-offline.js registers the worker.
"""

import hashlib
import json
from html.parser import HTMLParser
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


def content_hash(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()[:12]


class AssetLinks(HTMLParser):
    """The src of each script and the href of each link tag of one page."""

    def __init__(self) -> None:
        super().__init__()
        self.refs: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if (ref := a.get("src") if tag == "script" else a.get("href") if tag == "link" else None):
            self.refs.add(ref)


def version_links(out: Path) -> None:
    """Each page asks for this build's copy of its own scripts and styles: "reader.js" becomes "reader.js?v=<content
    hash>". A new build then has new addresses, so no cache layer (browser, CDN, an older service worker) can serve an
    old copy with new HTML. sw.js accepts exactly this query (fetch handler)."""
    for page in sorted(out.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        parser = AssetLinks()
        parser.feed(text)
        for ref in sorted(parser.refs):
            if "?" in ref or ":" in ref or ref.startswith("/") or Path(ref).suffix not in (".js", ".css"):
                continue  # Other sites, data: addresses, and files that are not scripts or styles.
            target = (page.parent / ref).resolve()
            if not target.is_file() or not target.is_relative_to(out.resolve()):
                raise BookError(f"{page.relative_to(out)}: links {ref}, which is not a file of the site")
            text = text.replace(f'="{ref}"', f'="{ref}?v={content_hash(target)}"')
        page.write_text(text, encoding="utf-8")


def write(site: Site) -> None:
    version_links(site.out)
    files: dict[str, tuple[str, Kind]] = {}
    for file in sorted(p for p in site.out.rglob("*") if p.is_file()):
        path = file.relative_to(site.out).as_posix()
        if path in SKIP or path.split("/", 1)[0] in SKIP_FOLDERS:
            continue
        files[path] = (content_hash(file), kind(path))
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
