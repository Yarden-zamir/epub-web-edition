# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Fail when a release EPUB breaks its size budget.

Usage: uv run tools/check_size.py BOOK.epub [MAX_EPUB_MB] [MAX_IMAGE_MB]

Defaults: the EPUB at most 24 MB (the web host refuses files over 25 MB) and each image at most 1 MB.
On failure it lists the largest files in the EPUB. Exits 1 when the budget is broken.
tools/check_release.py runs the same check with the defaults.
"""

import sys
import zipfile
from pathlib import Path

MB = 1_000_000
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp")


def over_budget(epub: Path, max_epub: float = 24.0, max_image: float = 1.0) -> list[str]:
    """Problems with the size budget, each with the largest files when the budget is broken. Empty when within."""
    size = epub.stat().st_size
    with zipfile.ZipFile(epub) as z:
        files = sorted(((i.file_size, i.filename) for i in z.infolist()), reverse=True)
    problems = [f"image {n} is {s / MB:.2f} MB (limit {max_image:g})"
                for s, n in files if n.lower().endswith(IMAGE_SUFFIXES) and s > max_image * MB]
    if size > max_epub * MB:
        problems.append(f"EPUB is {size / MB:.1f} MB (limit {max_epub:g})")
    if problems:
        problems += [f"largest: {n} {s / MB:.2f} MB" for s, n in files[:12]]
    return problems


def main() -> None:
    epub = Path(sys.argv[1])
    max_epub = float(sys.argv[2]) if len(sys.argv) > 2 else 24.0
    max_image = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    problems = over_budget(epub, max_epub, max_image)
    print(f"EPUB {epub.stat().st_size / MB:.1f} MB (limit {max_epub:g}) | images limit {max_image:g} MB | problems {len(problems)}")
    for line in problems:
        print(" ", line)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
