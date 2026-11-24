"""Brand icons: the brand/ folder next to the enhancements file gives the favicon and app icons."""

import shutil
from pathlib import Path

from build_web import BookError, Site


BRAND_FILES = ("favicon.ico", "icon.svg", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-mask.png")


ICON_LINKS = """<link rel="icon" href="favicon.ico" sizes="32x32">
<link rel="icon" href="icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="apple-touch-icon.png">"""


def brand_files(enhancements_file: Path | None) -> list[Path]:
    """Icon files from the brand/ folder next to the enhancements file. A book without that folder has no icons."""
    folder = enhancements_file.parent / "brand" if enhancements_file else None
    if folder is None or not folder.is_dir():
        return []
    files = [folder / name for name in BRAND_FILES]
    if missing := [f.name for f in files if not f.is_file()]:
        raise BookError(f"{folder}: missing icon files {missing}")
    return files


def values(site: Site) -> dict[str, str]:
    return {"icons": ICON_LINKS if brand_files(site.enhancements_file) else ""}


def write(site: Site) -> None:
    for path in brand_files(site.enhancements_file):
        shutil.copyfile(path, site.out / path.name)
