"""Related links: enhancements.json "related" adds outbound links to the footer."""

import html
import json
from pathlib import Path

from build_web import BookError, Site


def related_html(path: Path | None) -> str:
    """Footer list of outbound links from the enhancements file. Empty when the file has none."""
    related = json.loads(path.read_text(encoding="utf-8")).get("related") if path else None
    if not related:
        return ""
    items = []
    for link in related["links"]:
        if not link["href"].startswith("https://"):
            raise BookError(f"enhancements.json: related link {link['href'][:60]!r} must be an https URL")
        note = f' <span class="related-note">{html.escape(link["note"])}</span>' if link.get("note") else ""
        items.append(f'<li><a href="{html.escape(link["href"])}" rel="noopener">{html.escape(link["label"])}</a>{note}</li>')
    title = html.escape(related["title"])
    return f'<nav class="related" aria-label="{title}"><h2 class="related-title">{title}</h2><ul>{"".join(items)}</ul></nav>'


def values(site: Site) -> dict[str, str]:
    return {"related": related_html(site.enhancements_file)}
