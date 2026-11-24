# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Pack an EPUB source tree into a byte-reproducible .epub file.

Usage: uv run tools/build_epub.py [SRC_DIR] [OUT_EPUB]
"""

import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXED_TIME = (1980, 1, 1, 0, 0, 0)  # The zip format cannot store an earlier date.
SKIP_NAMES = {".DS_Store", "Thumbs.db"}


def entry(name: str, compress: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
    info.compress_type = compress
    info.external_attr = 0o644 << 16
    info.create_system = 3  # Unix. Fixes the value that the host OS would otherwise vary.
    return info


def build(src: Path, out: Path) -> str:
    mimetype = src / "mimetype"
    if mimetype.read_bytes() != b"application/epub+zip":
        raise SystemExit(f"{mimetype}: content must be exactly 'application/epub+zip'")
    files = sorted(
        p for p in src.rglob("*") if p.is_file() and p.name not in SKIP_NAMES and p != mimetype
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(entry("mimetype", zipfile.ZIP_STORED), mimetype.read_bytes())
        for p in files:
            z.writestr(entry(p.relative_to(src).as_posix(), zipfile.ZIP_DEFLATED), p.read_bytes(), compresslevel=9)
    return hashlib.sha256(out.read_bytes()).hexdigest()


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "epub-src"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "dist" / "book.epub"
    print(f"{out} sha256={build(src, out)}")
