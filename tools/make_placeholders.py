# /// script
# requires-python = ">=3.15"
# dependencies = ["pillow==13.0.0"]
# ///
"""Generate wholly synthetic placeholder images and record their checksums in inventory/assets.csv.

Limit: these images stand in for real scans. Delete this script and its
outputs when the real source bundle replaces the synthetic content.
"""

import csv
import hashlib
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ORIGINALS = ROOT / "originals"
EPUB_IMAGES = ROOT / "epub-src" / "OEBPS" / "images"
ASSETS = ROOT / "inventory" / "assets.csv"
EPUB_LONG_EDGE = 1600  # Kindle guidance: keep the long edge near 1600 px or less.

type RGB = tuple[int, int, int]

# name -> (size, background, palette). A fixed seed per name keeps the output stable.
SPECS: dict[str, tuple[tuple[int, int], RGB, list[RGB]]] = {
    "cover": ((1800, 2700), (34, 40, 44), [(176, 98, 62), (214, 170, 110), (70, 92, 96)]),
    "fig-01-01": ((3200, 2133), (198, 186, 166), [(140, 112, 84), (232, 220, 198), (96, 104, 98)]),
    "fig-02-01": ((2000, 2400), (232, 224, 208), [(168, 64, 44), (40, 70, 96), (220, 180, 90)]),
    "fig-03-01": ((3600, 1800), (52, 64, 72), [(120, 150, 160), (210, 196, 170), (34, 40, 44)]),
}


def placeholder(name: str, size: tuple[int, int], background: RGB, palette: list[RGB]) -> Image.Image:
    rng = random.Random(name)
    w, h = size
    img = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(img)
    for _ in range(9):
        r = rng.uniform(0.15, 0.45) * min(w, h)
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=rng.choice(palette))
    img = img.filter(ImageFilter.GaussianBlur(min(w, h) / 9))
    grain = Image.effect_noise(size, 18).convert("RGB")
    img = Image.blend(img, grain, 0.06)
    label = f"placeholder {name}"
    size_px = max(14, min(w, h) // 45)
    ImageDraw.Draw(img).text((size_px, h - size_px * 2), label, fill=(255, 255, 255), font_size=size_px)
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
    for name, (size, background, palette) in SPECS.items():
        original = placeholder(name, size, background, palette)
        original.save(ORIGINALS / f"{name}.jpg", quality=92)
        derived = derive(original)
        derived.save(EPUB_IMAGES / f"{name}.jpg", quality=86, optimize=True, progressive=True)
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
