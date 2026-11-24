# /// script
# requires-python = ">=3.15"
# dependencies = ["playwright==1.64.1", "pillow==13.0.0"]
# ///
"""Render the site icon set from site/brand/icon.svg (Escarpment, option A).

Writes site/brand/: favicon.ico (32 px), apple-touch-icon.png (180 px, mark at 140 px on the background colour),
icon-192.png, icon-512.png, icon-mask.png (512 px, mark inside the 409 px safe circle).
File set from Evil Martians, "How to Favicon in 2026".
Usage: uv run scripts/brand_icons.py
"""
import base64
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

BRAND = Path(__file__).resolve().parent.parent / "site" / "brand"
CHROME = Path.home() / ".cache/ms-playwright/chromium-1255/chrome-linux64/chrome"
PAPER = "#f7f3ec"


def render(page, svg: str, size: int, mark: int, background: str) -> Image.Image:
    """Screenshot the SVG at `mark` px centred on a `size` px square of `background` (transparent when empty)."""
    bg = f"background:{background};" if background else "background:transparent;"
    page.set_viewport_size({"width": size, "height": size})
    page.set_content(f'<html><body style="margin:0;{bg}width:{size}px;height:{size}px;display:grid;place-items:center">'
                     f'<img src="data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}" width="{mark}" height="{mark}"></body></html>')
    out = BRAND / f"_tmp_{size}.png"
    page.screenshot(path=str(out), omit_background=not background)
    img = Image.open(out).convert("RGBA")
    out.unlink()
    return img


def main() -> None:
    # The light variant: browsers apply the SVG's own dark-mode style only to the SVG favicon itself.
    svg = (BRAND / "icon.svg").read_text().replace("@media (prefers-color-scheme:dark){.bg{fill:#191715}}", "")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROME))
        page = b.new_page(color_scheme="light")
        render(page, svg, 32, 32, "").save(BRAND / "favicon.ico", sizes=[(32, 32)])
        render(page, svg, 180, 140, PAPER).convert("RGB").save(BRAND / "apple-touch-icon.png")
        render(page, svg, 192, 192, "").save(BRAND / "icon-192.png")
        render(page, svg, 512, 512, "").save(BRAND / "icon-512.png")
        # Maskable: the launcher may crop to a circle of 409 px; keep the whole mark inside it on a full background.
        render(page, svg, 512, 300, PAPER).convert("RGB").save(BRAND / "icon-mask.png")
        b.close()
    for f in sorted(BRAND.iterdir()):
        if f.is_file():
            print(f.name, f.stat().st_size)


if __name__ == "__main__":
    main()
