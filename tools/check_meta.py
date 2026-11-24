# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Check the link preview addresses of a built web edition.

Usage: uv run tools/check_meta.py WEB_DIR [APP_JSON]

- In every HTML page of WEB_DIR, og:url, og:image, og:image:secure_url, twitter:image and link rel=canonical are
  absolute https addresses. Preview services (WhatsApp, Telegram, X) ignore a relative address.
- With APP_JSON (the site's one URL setting, read by tools/web/96_app.py): the home page has og:url, og:image and
  twitter:image, each starting with its "url", and the host of that url is a deploy address in kitshn.config.ts.
Called by: books/eli-raz/scripts/check.py (the book, with its app.json) and tools/verify.py (the sample edition,
which has no app.json and so no preview addresses).
"""

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADDRESS_TAGS = {"og:url", "og:image", "og:image:secure_url", "twitter:image"}
REQUIRED_TAGS = {"og:url", "og:image", "twitter:image"}


class Addresses(HTMLParser):
    """The address of each preview tag and canonical link of one page: (tag, value) in page order."""

    def __init__(self) -> None:
        super().__init__()
        self.found: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        key = a.get("property") or a.get("name") or ""
        if tag == "meta" and key in ADDRESS_TAGS:
            self.found.append((key, a.get("content", "")))
        if tag == "link" and a.get("rel") == "canonical":
            self.found.append(("canonical", a.get("href", "")))


def addresses(page: Path) -> list[tuple[str, str]]:
    parser = Addresses()
    parser.feed(page.read_text(encoding="utf-8"))
    return parser.found


def problems(web: Path, app_json: Path | None = None) -> list[str]:
    out = []
    for page in sorted(web.rglob("*.html")):
        name = page.relative_to(web).as_posix()
        out += [f"{name}: {tag} is not an absolute https address: {value!r}"
                for tag, value in addresses(page) if not value.startswith("https://")]
    if app_json is None:
        return out
    url = json.loads(app_json.read_text(encoding="utf-8"))["url"]
    home = dict(addresses(web / "index.html"))
    out += [f"index.html: {tag} is missing" for tag in sorted(REQUIRED_TAGS - home.keys())]
    out += [f"index.html: {tag} {home[tag]!r} does not start with {url!r} ({app_json.name})"
            for tag in sorted(REQUIRED_TAGS & home.keys()) if not home[tag].startswith(url)]
    host = url.removeprefix("https://").split("/", 1)[0]
    if f'"{host}"' not in (ROOT / "kitshn.config.ts").read_text(encoding="utf-8"):
        out.append(f"{app_json}: the host {host} is not a deploy address in kitshn.config.ts")
    return out


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3) or not (Path(sys.argv[1]) / "index.html").is_file():
        sys.exit(__doc__)
    found = problems(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) == 3 else None)
    print("\n".join(found) or "link preview addresses ok")
    sys.exit(1 if found else 0)
