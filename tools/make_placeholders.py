# /// script
# requires-python = ">=3.13"
# dependencies = ["pillow==13.0.0"]
# ///
"""Generate wholly synthetic placeholder images and record their checksums in inventory/assets.csv.

Limit: these images stand in for real scans. Delete this script and its
outputs when the real source bundle replaces the synthetic content.
"""

import csv
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ORIGINALS = ROOT / "originals"
EPUB_IMAGES = ROOT / "epub-src" / "OEBPS" / "images"
ASSETS = ROOT / "inventory" / "assets.csv"
EPUB_LONG_EDGE = 1600  # Kindle guidance: keep the long edge near 1600 px or less.

SPECS: dict[str, tuple[tuple[int, int], tuple[int, int, int]]] = {
    "cover": ((1800, 2700), (88, 96, 92)),
    "fig-01-01": ((3200, 2133), (196, 188, 174)),
    "fig-02-01": ((2000, 2000), (168, 178, 176)),
}


def placeholder(size: tuple[int, int], tone: tuple[int, int, int], label: str) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, tone)
    draw = ImageDraw.Draw(img)
    line = tuple(min(255, c + 28) for c in tone)
    m = min(w, h) // 14
    draw.rectangle([m, m, w - m, h - m], outline=line, width=max(2, w // 600))
    font_size = max(14, min(w, h) // 28)
    text_width = draw.textlength(label, font_size=font_size)
    draw.text(((w - text_width) / 2, h / 2 - font_size / 2), label, fill=line, font_size=font_size)
    return img


def derive(src: Image.Image) -> Image.Image:
    scale = EPUB_LONG_EDGE / max(src.size)
    if scale >= 1:
        return src.copy()
    return src.resize((round(src.width * scale), round(src.height * scale)), Image.Resampling.LANCZOS)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ORIGINALS.mkdir(exist_ok=True)
    EPUB_IMAGES.mkdir(parents=True, exist_ok=True)
    for name, (size, tone) in SPECS.items():
        original = placeholder(size, tone, f"placeholder  {name}")
        original.save(ORIGINALS / f"{name}.png", optimize=True)
        derived = derive(original)
        derived.save(EPUB_IMAGES / f"{name}.jpg", quality=88, optimize=True)
        print(name, original.size, "->", derived.size)

    with ASSETS.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
    if fields is None:
        raise SystemExit(f"{ASSETS} has no header")
    for row in rows:
        row["epub_sha256"] = sha(ROOT / "epub-src" / row["epub_path"])
        row["original_sha256"] = sha(ROOT / row["original_path"])
    with ASSETS.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
