# /// script
# requires-python = ">=3.15"
# dependencies = ["pillow==13.0.0"]
# ///
"""Tile screenshots into one sheet: montage.py OUT.jpg COLS TILE_WIDTH FILES..."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

out, cols, tw = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
files = [Path(f) for f in sys.argv[4:] if Path(f).exists()]
tiles = []
for f in files:
    im = Image.open(f).convert("RGB")
    im = im.resize((tw, max(1, int(im.height * tw / im.width))))
    tiles.append((f.stem, im))
rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
heights = [max(im.height for _, im in r) + 18 for r in rows]
sheet = Image.new("RGB", (cols * (tw + 8), sum(heights)), "#888")
y = 0
for r, h in zip(rows, heights):
    for i, (name, im) in enumerate(r):
        x = i * (tw + 8)
        sheet.paste(im, (x, y + 18))
        ImageDraw.Draw(sheet).text((x + 2, y + 2), name, fill="white")
    y += h
sheet.save(out, quality=80)
print(out, sheet.size)
