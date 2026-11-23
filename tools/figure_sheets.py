# /// script
# requires-python = ">=3.13"
# dependencies = ["pymupdf==1.28.2", "pillow==13.0.0"]
# ///
"""Render review sheets for every page with figures.

Usage: uv run tools/figure_sheets.py CONTENT_DIR OUT_DIR

Red: image box and figure ID. Green: caption lines attached to that figure.
Orange: other small-print lines on the page (possible missed captions).
Reads CONTENT_DIR/inventory/figures.csv. Writes OUT_DIR/figures-NN.png.
"""

import csv
import io
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

COLS, ROWS, THUMB_W = 4, 3, 330


def main() -> None:
    content, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    cfg = tomllib.loads((content / "book.toml").read_text(encoding="utf-8"))
    doc = pymupdf.open(Path(cfg["pdf"]).expanduser())
    small_rule = next(r for r in cfg["role"] if r["role"] == "small")
    by_page: dict[int, list[dict[str, str]]] = defaultdict(list)
    with (content / "inventory" / "figures.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_page[int(row["pdf_page"])].append(row)
    pages = sorted(by_page)
    per = COLS * ROWS
    for sheet_no, start in enumerate(range(0, len(pages), per), start=1):
        chunk = pages[start:start + per]
        page = doc[0]
        scale = THUMB_W / page.rect.width
        th = round(page.rect.height * scale)
        sheet = Image.new("RGB", (COLS * (THUMB_W + 10), ROWS * (th + 26)), "white")
        draw = ImageDraw.Draw(sheet)
        for k, pno in enumerate(chunk):
            pg = doc[pno - 1]
            im = Image.open(io.BytesIO(pg.get_pixmap(matrix=pymupdf.Matrix(scale, scale)).tobytes("png"))).convert("RGB")
            d = ImageDraw.Draw(im)
            green: list[tuple[float, ...]] = []
            for row in by_page[pno]:
                x0, y0, x1, y1 = (float(v) * scale for v in row["bbox"].split())
                d.rectangle([x0, y0, x1, y1], outline=(220, 0, 0), width=2)
                d.text((x0 + 3, y0 + 2), row["figure_id"], fill=(220, 0, 0), font_size=11)
                for box in filter(None, row["caption_boxes"].split(";")):
                    b = [float(v) * scale for v in box.split()]
                    green.append(tuple(b))
                    d.rectangle(b, outline=(0, 160, 0), width=2)
            for block in pg.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    s = line["spans"][0]
                    if small_rule["font"] in s["font"] and s["size"] <= float(small_rule.get("max", 99)):
                        b = [v * scale for v in line["bbox"]]
                        if not any(abs(b[1] - g[1]) < 2 and abs(b[3] - g[3]) < 2 for g in green):
                            d.rectangle(b, outline=(255, 140, 0), width=1)
            x, y = (k % COLS) * (THUMB_W + 10), (k // COLS) * (th + 26)
            sheet.paste(im, (x, y + 22))
            draw.text((x + 2, y + 2), f"PDF {pno}", fill="black", font_size=16)
        sheet.save(out / f"figures-{sheet_no:02d}.png")
    print(f"{len(pages)} pages with figures -> {sheet_no} sheets in {out}")


if __name__ == "__main__":
    main()
