"""Feature photo: enhancements.json "hero" is a credited photograph that closes the book and is the link preview image."""

import html
import json
from pathlib import Path

from PIL import Image, ImageOps

from build_web import BookError, Site


PHOTO_WIDTHS = (960, 1920)


PREVIEW_SIZE = (1200, 630)  # Open Graph and Twitter large image.


def feature_photo(enhancements_file: Path | None, out: Path) -> tuple[str, str]:
    """The enhancements "hero" block {image, alt, credit, caption, source}: a credited photograph that closes the
    book above the footer, and the link preview image. Returns (closing figure HTML, preview image path);
    empty strings when the block is absent."""
    photo = json.loads(enhancements_file.read_text(encoding="utf-8")).get("hero") if enhancements_file else None
    if not photo:
        return "", ""
    if not (photo["alt"] and photo["credit"] and photo["caption"] and photo["source"]):
        raise BookError("enhancements.json: hero needs alt, caption, credit and source")
    (out / "media").mkdir(exist_ok=True)
    with Image.open(enhancements_file.resolve().parent.parent / photo["image"]) as im:
        rgb = im.convert("RGB")
        for width in PHOTO_WIDTHS:
            copy = rgb.copy()
            copy.thumbnail((width, width * 4))
            copy.save(out / "media" / f"feature-{width}.webp", "WEBP", quality=80, method=6)
        ImageOps.fit(rgb, PREVIEW_SIZE).save(out / "media" / "preview.jpg", "JPEG", quality=82, optimize=True)
    srcset = ", ".join(f"media/feature-{w}.webp {w}w" for w in PHOTO_WIDTHS)
    figure = (f'<aside aria-label="תמונת הכריכה במסגרתה המלאה"><figure class="closing-photo"><img src="media/feature-{PHOTO_WIDTHS[-1]}.webp" srcset="{srcset}" sizes="100vw" '
              f'alt="{html.escape(photo["alt"])}" loading="lazy" decoding="async">'
              f'<figcaption><span class="caption">{html.escape(photo["caption"])}</span>'
              f'<span class="credit">{html.escape(photo["credit"])}</span>'
              f'<span class="closing-note">תמונת הכריכה, במסגרתה המלאה.</span></figcaption></figure></aside>')
    return figure, "media/preview.jpg"


def preview_meta(title: str, description: str, image: str) -> str:
    """Link preview tags. Limit: image URLs are relative, which some preview services do not follow;
    revisit when the build learns the site's public URL."""
    tags = [("og:type", "book"), ("og:title", title), ("og:description", description)]
    if image:
        tags += [("og:image", image), ("og:image:width", str(PREVIEW_SIZE[0])), ("og:image:height", str(PREVIEW_SIZE[1]))]
    lines = [f'<meta property="{k}" content="{html.escape(v)}">' for k, v in tags]
    lines.append(f'<meta name="twitter:card" content="{"summary_large_image" if image else "summary"}">')
    return "\n".join(lines)


def values(site: Site) -> dict[str, str]:
    closing, preview = feature_photo(site.enhancements_file, site.out)
    return {"closing_photo": closing, "preview_meta": preview_meta(site.book.title, site.book.description, preview)}
