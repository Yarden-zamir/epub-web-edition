"""Site identity: link previews (Open Graph and Twitter tags with a 1200x630 crop of the enhancements.json "hero"
photo) and the web app manifest.

app.json next to the enhancements file gives the public address and the short app name. Preview services need
absolute image addresses, so a book without app.json gets title and description tags only, and no manifest.
"""

import html
import json
from pathlib import Path
from typing import TypedDict

from PIL import Image, ImageOps

from build_web import BookError, Site


# The manifest icons come from the brand/ folder that 95_brand.py copies to the site root.
MANIFEST_ICONS = [
    {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
    {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    {"src": "icon-mask.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
]
# The same colours as --paper in site/features/00-base.css and the theme-color meta in site/index.html.
BACKGROUND, THEME = "#f7f3ec", "#191715"
PREVIEW_SIZE = (1200, 630)  # Open Graph and Twitter large image.
PREVIEW_PATH = "media/preview.jpg"


class App(TypedDict):
    url: str  # Public address of the site, with a final "/".
    short_name: str  # Name under the home screen icon.


def read_app(data_dir: Path | None) -> App | None:
    """app.json next to the enhancements file, checked. None when the book has none."""
    path = data_dir / "app.json" if data_dir else None
    if path is None or not path.is_file():
        return None
    app = json.loads(path.read_text(encoding="utf-8"))
    if set(app) != set(App.__annotations__):
        raise BookError(f"{path}: expected the keys {sorted(App.__annotations__)}, found {sorted(app)}")
    if not (app["url"].startswith("https://") and app["url"].endswith("/")):
        raise BookError(f"{path}: url must start with https:// and end with /")
    if not app["short_name"].strip():
        raise BookError(f"{path}: short_name is empty")
    return app


def preview_image(site: Site) -> str | None:
    """The 1200x630 crop of the hero photo, as alt text. None when the book has no hero photo."""
    photo = json.loads(site.enhancements_file.read_text(encoding="utf-8")).get("hero") if site.enhancements_file else None
    if not photo:
        return None
    (site.out / "media").mkdir(exist_ok=True)
    with Image.open(site.enhancements_file.resolve().parent.parent / photo["image"]) as im:
        ImageOps.fit(im.convert("RGB"), PREVIEW_SIZE).save(site.out / PREVIEW_PATH, "JPEG", quality=82, optimize=True)
    return photo["alt"]


def values(site: Site) -> dict[str, str]:
    title, description = site.book.title, site.book.description
    app = read_app(site.data_dir)
    tags = [("og:type", "book"), ("og:site_name", title), ("og:title", title), ("og:description", description)]
    twitter = [("twitter:title", title), ("twitter:description", description)]
    image_alt = preview_image(site)
    if app:
        tags.append(("og:url", app["url"]))
    if app and image_alt is not None:
        image = app["url"] + PREVIEW_PATH
        tags += [("og:image", image), ("og:image:type", "image/jpeg"), ("og:image:width", str(PREVIEW_SIZE[0])),
                 ("og:image:height", str(PREVIEW_SIZE[1])), ("og:image:alt", image_alt)]
        twitter += [("twitter:image", image), ("twitter:image:alt", image_alt)]
    twitter.append(("twitter:card", "summary_large_image" if app and image_alt is not None else "summary"))
    tags += twitter
    # Open Graph uses the property attribute, Twitter the name attribute.
    lines = [f'<meta {"name" if key.startswith("twitter:") else "property"}="{key}" content="{html.escape(value)}">'
             for key, value in tags]
    head = ""
    if app:
        if missing := [i["src"] for i in MANIFEST_ICONS if not (site.data_dir / "brand" / i["src"]).is_file()]:
            raise BookError(f"app.json needs the manifest icons {missing} in {site.data_dir / 'brand'}")
        head = (f'<link rel="manifest" href="manifest.webmanifest">\n'
                f'<meta name="apple-mobile-web-app-title" content="{html.escape(app["short_name"])}">\n')
    return {"preview_meta": "\n".join(lines), "head": head}


def write(site: Site) -> None:
    app = read_app(site.data_dir)
    if not app:
        return
    book = site.book
    manifest = {
        "id": "./", "name": book.title, "short_name": app["short_name"], "description": book.description,
        "lang": book.language, "dir": book.direction, "start_url": "./", "scope": "./", "display": "standalone",
        "background_color": BACKGROUND, "theme_color": THEME, "icons": MANIFEST_ICONS,
    }
    (site.out / "manifest.webmanifest").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
