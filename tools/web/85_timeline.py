"""Timeline: timeline.json becomes the "ציר זמן" tab of the chapters panel."""

import html
import json
from pathlib import Path

from build_web import BookError, Converter, Site, missing_id


def timeline_html(data_dir: Path | None, conv: Converter) -> tuple[str, str]:
    """Tab button and panel for timeline.json: {"events": [{date, label, text, quote, target, major,
    date_source?}]}. Each event links to its quoted paragraph. Empty strings when the file is absent."""
    path = data_dir / "timeline.json" if data_dir else None
    if path is None or not path.is_file():
        return "", ""
    events = json.loads(path.read_text(encoding="utf-8"))["events"]
    items = []
    for i, ev in enumerate(events):
        for ref in (ev["target"], ev.get("date_source", ev["target"])):
            if ref not in conv.ids:
                raise missing_id(f"timeline.json: event {i} ({ev['label']})", ref)
        if not isinstance(ev["major"], bool):
            raise BookError(f"timeline.json: event {i}: major must be true or false")
        cls = "tl-event tl-major" if ev["major"] else "tl-event"
        items.append(f'<li class="{cls}"><a href="#{html.escape(ev["target"])}" data-quote="{html.escape(ev["quote"])}">'
                     f'<span class="tl-date">{html.escape(ev["label"])}</span>'
                     f'<span class="tl-text">{html.escape(ev["text"])}</span></a></li>')
    tab = '<button type="button" role="tab" id="tab-timeline" aria-selected="false" aria-controls="toc-timeline" tabindex="-1">ציר זמן</button>'
    panel = (f'<div id="toc-timeline" class="panel-body" role="tabpanel" aria-labelledby="tab-timeline" hidden>'
             f'<ol class="timeline">{"".join(items)}</ol></div>')
    return tab, panel


def values(site: Site) -> dict[str, str]:
    tab, panel = timeline_html(site.data_dir, site.conv)
    return {"timeline_tab": tab, "timeline": panel}
