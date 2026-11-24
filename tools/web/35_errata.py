"""Edition corrections and the errata page.

The EPUB marks each correction as span.edition-correction[data-printed] right before a.edition-mark, a note
reference to its edition note (tools/ingest_pdf.py). This module links each mark to its row in the errata list
(<book>/errata/errata.json), adds the printed form of each corrected block to the search index, and writes
errata/index.html: every row with its evidence, the print crop and the facsimile page. Hebrew text comes from
<data>/errata-he.json. Without errata.json (the sample edition) the feature is off.
"""

import html
import json
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from build_web import ROOT, BookError, Site, fill, missing_id

STATUSES = {  # Status -> (section title, one-line description). Order is the page order.
    "verified": ("תוקן במהדורה זו",
                 "ההוכחה חד־משמעית והתיקון צר: מילה, מספר או כמה אותיות. בספר מופיע הנוסח המתוקן, ולידו הסימן †."),
    "family": ("להחלטת המשפחה",
               "ההוכחה ברורה, אבל הטקסט הוא זיכרונות אישיים, ולכן המשפחה תחליט. עד אז הנוסח המודפס נשאר."),
    "editor": ("לבדיקת עורך",
               "הנוסח המודפס כנראה שגוי, אבל התיקון אינו צר, או שיש יותר מתיקון אפשרי אחד. הנוסח המודפס נשאר."),
    "keep": ("נשאר כפי שנדפס",
             "נבדק ונמצא סביר: מספר עגול, כתיב של שם או בחירה של הכותב."),
    "not-print": ("רשומות פגומות ברשימת המקורות",
                  "תקלות ברשימת המקורות שבסוף הספר. התג שליד כל רשומה אומר אם התקלה נמצאת בספר המודפס."),
}
PRINT_CHECK = {"in print": "בדפוס", "conversion error": "תקלת המרה"}
FACSIMILE = "book/OEBPS/facsimile/fx-{:03d}.jpg"
PAGE = ROOT / "site" / "pages" / "errata.html"


@dataclass
class Correction:
    """One corrected run in the reading text."""
    element: str
    printed: str
    corrected: str
    span: ET.Element
    mark: ET.Element
    row: int = 0  # Its errata row, set by link().


@dataclass
class State:
    rows: list[dict] = field(default_factory=list)
    he: dict[str, dict[str, str]] = field(default_factory=dict)
    translator: str = ""
    crops: Path | None = None
    elements: set[str] = field(default_factory=set)  # Every element ID that a row names.
    corrections: list[Correction] = field(default_factory=list)
    texts: dict[str, list[str | tuple[str, str]]] = field(default_factory=dict)  # Element ID -> text runs.
    page_labels: dict[int, str] = field(default_factory=dict)  # PDF page -> printed page label ("עמוד 25").
    unmarked: list[int] = field(default_factory=list)  # Rows whose quote the viewer text could not mark.


STATE: State | None = None  # None when the book has no errata list. Fresh for each build (the module loads per build).


def elements_of(row: dict) -> list[str]:
    return [e.strip() for e in row["element"].split(",")]


def load(site: Site) -> None:
    global STATE
    path = site.data_dir.parent / "errata" / "errata.json" if site.data_dir else None
    if path is None or not path.is_file():
        return
    rows = json.loads(path.read_text(encoding="utf-8"))["entries"]
    he_file = json.loads((site.data_dir / "errata-he.json").read_text(encoding="utf-8"))
    state = State(rows=rows, he=he_file["rows"], translator=he_file["translator"], crops=path.parent)
    for row in rows:
        where = f"errata.json row {row['row']}"
        if row["status"] not in STATUSES:
            raise BookError(f"{where}: unknown status {row['status']!r}")
        if row["print_check"] not in PRINT_CHECK:
            raise BookError(f"{where}: unknown print_check {row['print_check']!r}")
        if str(row["row"]) not in state.he:
            raise BookError(f"errata-he.json: row {row['row']} has no Hebrew text")
        if not (state.crops / row["crop"].removeprefix("errata/")).is_file():
            raise BookError(f"{where}: crop {row['crop']} does not exist")
        for el in elements_of(row):
            if el not in site.conv.ids:
                raise missing_id(where, el, "an element ID")
            state.elements.add(el)
    if extra := state.he.keys() - {str(r["row"]) for r in rows}:
        raise BookError(f"errata-he.json: rows {sorted(extra)} are not in errata.json")
    STATE = state


def classes(el: ET.Element) -> set[str]:
    return set((el.get("class") or "").split())


def runs(el: ET.Element, state: State) -> list[str | tuple[str, str]]:
    """The text of an element as plain strings and (printed, corrected) pairs, without note references.
    Collects each correction once, with the mark that follows it."""
    out: list[str | tuple[str, str]] = [el.text or ""]
    children = list(el)
    for i, child in enumerate(children):
        if child.tag == "span" and "edition-correction" in classes(child):
            if len(child) or i + 1 == len(children) or "edition-mark" not in classes(children[i + 1]):
                raise BookError(f"{el.get('id')}: an edition correction must hold only text and come right before its mark")
            corrected = child.text or ""
            out.append((child.get("data-printed") or "", corrected))
            state.corrections.append(Correction("", child.get("data-printed") or "", corrected, child, children[i + 1]))
        elif child.get("role") != "doc-noteref":
            out += runs(child, state)
        out.append(child.tail or "")
    return out


def transform(site: Site, body: ET.Element, top: ET.Element | None, kind: str) -> None:
    if STATE is None:
        return
    for el in body.iter():
        if (el_id := el.get("id")) is None:
            continue
        if el.tag == "section" and "facsimile-page" in classes(el):
            STATE.page_labels[int(el_id.removeprefix("fx-"))] = el.get("aria-label") or ""
        before = len(STATE.corrections)
        if el_id in STATE.elements:
            STATE.texts[el_id] = runs(el, STATE)
        elif el.tag in ("p", "li", "aside", "td", "figcaption") and any(
                "edition-correction" in classes(s) for s in el.iter("span")):
            runs(el, STATE)  # A correction outside every row: the check in values() names it.
        for c in STATE.corrections[before:]:
            c.element = el_id
            link(c, STATE)  # Now: the converter writes this document's HTML right after the transforms.


def squeeze(text: str) -> str:
    return "".join(text.split())


def link(c: Correction, state: State) -> None:
    """Give a correction and its mark the number of their verified errata row."""
    # The errata list sometimes spaces a quote unlike the print ("ה- 14" for "ה-14"), so spaces do not count.
    rows = [r for r in state.rows if r["status"] == "verified" and r["element"] == c.element
            and squeeze(r["printed"]) == squeeze(c.printed) and squeeze(r["correction"]) == squeeze(c.corrected)]
    if len(rows) != 1:
        raise BookError(f"{c.element}: correction {c.printed!r} -> {c.corrected!r} matches {len(rows)} verified errata rows")
    c.row = rows[0]["row"]
    c.span.set("data-row", str(c.row))
    c.mark.set("data-row", str(c.row))


def link_rows(state: State) -> dict[int, Correction]:
    """Each verified row -> its correction in the text. Every verified row needs one."""
    linked = {c.row: c for c in state.corrections}
    if missing := [r["row"] for r in state.rows if r["status"] == "verified" and r["row"] not in linked]:
        raise BookError(f"errata rows {missing} are verified but have no correction in the text")
    return linked


def values(site: Site) -> dict[str, str]:
    if STATE is None:
        return {"errata_link": "", "errata_nav": ""}
    link_rows(STATE)
    why = {str(r["row"]): STATE.he[str(r["row"])]["explanation"] for r in STATE.rows if r["status"] == "verified"}
    data = json.dumps(why, ensure_ascii=False).replace("</", "<\\/")
    count = sum(r["status"] == "verified" for r in STATE.rows)
    return {
        "end": f'<script type="application/json" id="errata-data">{data}</script>\n',
        "errata_link": '<a class="footer-errata" href="errata/">תיקוני המהדורה</a>',
        "errata_nav": (f'<a class="toc-errata" href="errata/"><span>תיקוני המהדורה</span>'
                       f'<span class="toc-errata-meta">{count} תיקונים · {len(STATE.rows)} ממצאים</span></a>'),
    }


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def marked(text_runs: list[str | tuple[str, str]], printed: bool, own: Correction | None, quotes: list[str],
           row: int, state: State) -> str:
    """HTML of an element's text in one version. Marks its own correction, or else the quoted printed text."""
    parts = []
    for r in text_runs:
        if isinstance(r, str):
            parts.append(esc(r))
            continue
        text = esc(r[0] if printed else r[1])
        is_own = own is not None and r == (own.printed, own.corrected)
        parts.append(f'<mark class="{"was" if printed else "now"}">{text}</mark>' if is_own else text)
    if own is not None or not quotes:
        return " ".join("".join(parts).split())
    plain = " ".join("".join(r if isinstance(r, str) else r[0] for r in text_runs).split())
    spans = [found for q in quotes if (found := find_loose(plain, q))]
    if not spans and row not in state.unmarked:
        state.unmarked.append(row)  # Listed in build.json; the viewer then shows the text without a mark.
    out, at = [], 0
    for start, end in sorted(spans):
        out += [esc(plain[at:start]), f"<mark>{esc(plain[start:end])}</mark>"]
        at = end
    return "".join(out) + esc(plain[at:])


def find_loose(text: str, needle: str) -> tuple[int, int] | None:
    """Where needle occurs in text when spaces do not count, as (start, end) in text."""
    where = [i for i, c in enumerate(text) if not c.isspace()]  # Index in the squeezed text -> index in text.
    at = "".join(text.split()).find(squeeze(needle))
    if at < 0 or not squeeze(needle):
        return None
    return where[at], where[at + len(squeeze(needle)) - 1] + 1


def quotes_for(row: dict, elements: list[str]) -> dict[str, list[str]]:
    """Element ID -> the printed quotes to mark in it. A row separates several quotes with " / ", one per element
    when the counts agree, and marks a cut in a long quote with "…"."""
    parts = [p.strip() for p in row["printed"].split(" / ")]
    per_element = [[p] for p in parts] if len(parts) == len(elements) else [parts] * len(elements)
    return {el: [piece.strip() for q in quotes for piece in q.split("…") if piece.strip()]
            for el, quotes in zip(elements, per_element)}


def compare_html(row: dict, own: Correction | None, state: State) -> str:
    """The viewer's text side: our reading of each element, with the changed or quoted words marked."""
    blocks = []
    elements = elements_of(row)
    n = row["row"]
    for i, el in enumerate(elements, start=1):
        text_runs = state.texts[el]
        quotes = quotes_for(row, elements)[el]
        place = f"מקום {i} · " if len(elements) > 1 else ""
        if own is not None:
            blocks.append(f'<p class="cmp-label">בספר המודפס</p><p class="cmp-text" dir="auto">{marked(text_runs, True, own, [], n, state)}</p>'
                          f'<p class="cmp-label">במהדורה זו</p><p class="cmp-text" dir="auto">{marked(text_runs, False, own, [], n, state)}</p>')
        else:
            blocks.append(f'<p class="cmp-label">{place}בספר המודפס ובמהדורה זו</p>'
                          f'<p class="cmp-text" dir="auto">{marked(text_runs, True, None, quotes, n, state)}</p>')
    return "".join(blocks)


def evidence_html(row: dict, site: Site) -> str:
    items = []
    for ev in row["evidence"]:
        label = ev["label"].strip()
        ref = label.removesuffix(".")
        if ev["url"]:
            items.append(f'<li><a href="{esc(ev["url"])}" target="_blank" rel="noopener" dir="auto">{esc(label)}</a></li>')
        elif ref in site.conv.ids:  # A label that names an element of the book links to it.
            items.append(f'<li><a href="../#{esc(ref)}">{esc(site.conv.chapter_title.get(site.conv.chapter_of.get(ref, ""), ref))}</a></li>')
        else:
            items.append(f'<li dir="auto">{esc(label)}</li>')
    return f'<ul class="er-evidence">{"".join(items)}</ul>' if items else ""


def row_html(row: dict, own: Correction | None, site: Site, state: State) -> str:
    n = row["row"]
    he = state.he[str(n)]
    elements = elements_of(row)
    chapters = []
    for el in elements:
        title = site.conv.chapter_title.get(site.conv.chapter_of.get(el, ""), "")
        if title and title not in chapters:
            chapters.append(title)
    labels = []
    for p in row["pdf_page"]:
        if not state.page_labels.get(p):
            raise BookError(f"errata row {n}: PDF page {p} has no facsimile page with a label")
        labels.append(state.page_labels[p])
    where = " · ".join(f"<bdi>{esc(part)}</bdi>" for part in [*labels, *chapters])
    crop = f"crops/{n}.png"
    pills = [f'<button type="button" class="er-pill" data-view="{crop}" data-kind="line">שורה בדפוס</button>']
    pills += [f'<button type="button" class="er-pill" data-view="../{FACSIMILE.format(p)}" data-kind="page">{esc(label)}</button>'
              for p, label in zip(row["pdf_page"], labels)]
    correction = he.get("correction") or row["correction"]
    lines = [f'<div class="er-line er-printed"><span class="er-label">בדפוס</span>'
             f'<bdi class="er-quote">{esc(row["printed"])}</bdi></div>']
    if correction:
        label = "במהדורה" if row["status"] == "verified" else "הצעה"
        lines.append(f'<div class="er-line er-fixed"><span class="er-label">{label}</span><bdi class="er-quote">{esc(correction)}</bdi></div>')
    tag = (f'<span class="er-tag" title="הנוסח שלנו שונה מהספר המודפס בגלל תקלה בהמרה">{PRINT_CHECK["conversion error"]}</span>'
           if row["print_check"] == "conversion error" else "")
    goes = []
    for i, el in enumerate(elements, start=1):
        # The book page highlights the first of these that it finds: the corrected or the printed form.
        marks = [own.corrected, own.printed] if own else quotes_for(row, elements)[el]
        href = "../?" + "&".join(f"hl={quote(m)}" for m in marks if m) + f"#{quote(el)}"
        label = "מעבר למקום בספר" if len(elements) == 1 else f"מעבר למקום {i}"
        goes.append(f'<a class="er-go" href="{esc(href)}">{label}</a>')
    search_text = " ".join([row["printed"], correction or "", he["explanation"], row["explanation"], *labels, *chapters,
                            *(e["label"] for e in row["evidence"])])
    first = next((c for r in state.texts[elements[0]] for c in (r if isinstance(r, str) else r[0]) if c.isalpha()), "א")
    direction = "rtl" if "\u0590" <= first <= "\u05ff" else "ltr"  # Of the printed line, for the viewer's start edge.
    return (f'<article class="er-row" id="row-{n}" data-status="{row["status"]}" data-dir="{direction}" data-search="{esc(search_text)}">'
            f'<header class="er-head"><span class="er-num">{n}</span><span class="er-where">{where}</span>{tag}'
            f'<span class="er-pills">{"".join(pills)}</span></header>'
            f'{"".join(lines)}'
            f'<p class="er-why">{esc(he["explanation"])}</p>'
            f'{evidence_html(row, site)}'
            f'<footer class="er-foot">{"".join(goes)}</footer>'
            f'<template class="er-compare">{compare_html(row, own, state)}</template>'
            f'</article>')


def write(site: Site) -> None:
    if STATE is None:
        return
    linked = link_rows(STATE)
    out = site.out / "errata"
    (out / "crops").mkdir(parents=True)
    for row in STATE.rows:
        shutil.copyfile(STATE.crops / row["crop"].removeprefix("errata/"), out / "crops" / f"{row['row']}.png")
        for p in row["pdf_page"]:
            if not (site.out / FACSIMILE.format(p)).is_file():
                raise BookError(f"errata row {row['row']}: facsimile page {FACSIMILE.format(p)} is not in the site")
    filters, sections = ['<button type="button" class="er-filter" data-filter="" aria-pressed="true">'
                         f'הכול <span>{len(STATE.rows)}</span></button>'], []
    for status, (title, about) in STATUSES.items():
        rows = [r for r in STATE.rows if r["status"] == status]
        if not rows:
            continue
        filters.append(f'<button type="button" class="er-filter" data-filter="{status}" aria-pressed="false">'
                       f'{esc(title)} <span>{len(rows)}</span></button>')
        sections.append(f'<section class="er-section" data-status="{status}" aria-labelledby="h-{status}">'
                        f'<h2 id="h-{status}">{esc(title)} <span class="er-count">{len(rows)}</span></h2>'
                        f'<p class="er-about">{esc(about)}</p>'
                        + "".join(row_html(r, linked.get(r["row"]), site, STATE) for r in rows) + "</section>")
    css = next(i.path for i in site.book.items.values() if i.media_type == "text/css")
    page = fill(PAGE.read_text(encoding="utf-8"), {
        "lang": esc(site.book.language),
        "dir": site.book.direction,
        "title": esc(site.book.title),
        "book_css": esc(f"../book/{css}"),
        "verified": str(len(linked)),
        "total": str(len(STATE.rows)),
        "translator": "ההסברים תורגמו לעברית בתרגום מכונה מתוך רשימת המחקר באנגלית, ועדיין לא נבדקו." if "machine" in STATE.translator else "",
        "filters": "".join(filters),
        "sections": "".join(sections),
    })
    (out / "index.html").write_text(page, encoding="utf-8")
    shutil.copyfile(ROOT / "site" / "pages" / "errata.js", out / "errata.js")
    add_printed_search(site, linked)
    site.report["errata_rows"] = len(STATE.rows)
    site.report["errata_corrections"] = len(linked)
    site.report["errata_unmarked"] = STATE.unmarked


def add_printed_search(site: Site, linked: dict[int, Correction]) -> None:
    """search.json "variants": the printed text of each corrected block, so search finds both forms."""
    path = site.out / "search.json"
    index = json.loads(path.read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in index["entries"]}
    variants = []
    for el in sorted({c.element for c in linked.values()}):
        if el not in entries:
            continue  # Notes are not in the search index, in either form.
        text = entries[el]["text"]
        for c in linked.values():
            if c.element == el:
                if f"{c.corrected}†" not in text:
                    raise BookError(f"{el}: search text lacks {c.corrected!r} before its mark")
                text = text.replace(f"{c.corrected}†", c.printed, 1)
        variants.append({"id": el, "text": text})
    index["variants"] = variants
    path.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
