"""Feature photo: enhancements.json "feature_photo" is a credited photograph that closes the book. 96_app.py makes the link preview from it."""

import html
import json
from pathlib import Path

from PIL import Image

from build_web import BookError, Site


PHOTO_WIDTHS = (960, 1920)


def feature_photo(enhancements_file: Path | None, out: Path) -> str:
    """The enhancements "feature_photo" block {image, alt, credit, caption, source}: a credited photograph that closes the
    book above the footer. Returns the closing figure HTML; an empty string when the block is absent."""
    photo = json.loads(enhancements_file.read_text(encoding="utf-8")).get("feature_photo") if enhancements_file else None
    if not photo:
        return ""
    if not (photo["alt"] and photo["credit"] and photo["caption"] and photo["source"]):
        raise BookError("enhancements.json: feature_photo needs alt, caption, credit and source")
    (out / "media").mkdir(exist_ok=True)
    with Image.open(enhancements_file.resolve().parent.parent / photo["image"]) as im:
        rgb = im.convert("RGB")
        for width in PHOTO_WIDTHS:
            copy = rgb.copy()
            copy.thumbnail((width, width * 4))
            copy.save(out / "media" / f"feature-{width}.webp", "WEBP", quality=80, method=6)
    srcset = ", ".join(f"media/feature-{w}.webp {w}w" for w in PHOTO_WIDTHS)
    figure = (f'<aside aria-label="תמונת הכריכה במסגרתה המלאה"><figure class="closing-photo"><img src="media/feature-{PHOTO_WIDTHS[-1]}.webp" srcset="{srcset}" sizes="100vw" '
              f'alt="{html.escape(photo["alt"])}" loading="lazy" decoding="async">'
              f'<figcaption><span class="caption">{html.escape(photo["caption"])}</span>'
              f'<span class="credit">{html.escape(photo["credit"])}</span>'
              f'<span class="closing-note">תמונת הכריכה, במסגרתה המלאה.</span></figcaption></figure></aside>')
    return figure


def values(site: Site) -> dict[str, str]:
    return {"closing_photo": feature_photo(site.enhancements_file, site.out)}
