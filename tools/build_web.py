# /// script
# requires-python = ">=3.15"
# dependencies = ["pillow==13.0.0"]
# ///
"""Build the static web edition from the finished EPUB file.

The EPUB is the only source of book content. The site layer (site/) adds
presentation and site-only features, attached by stable element IDs.

Usage: uv run tools/build_web.py [BOOK_EPUB] [OUT_DIR] [ENHANCEMENTS_JSON | none]

ENHANCEMENTS_JSON defaults to site/enhancements.json. Its "original" paths resolve
against the folder above the file's folder (the content root). "none" uses no enhancements.
Its optional "related" block adds plain outbound links (title, links: label, href, note) to the footer.
An optional places.json next to the enhancements file adds a map section after the printed contents
(format in places_html). The list works without JavaScript; reader.js draws the map with Leaflet.
Its optional "tables" block turns a figure that prints a table as an image into a real table:
{figure ID: {columns, rows, bar (column index drawn as bars), ltr (column indices), source}}.
The printed image stays inside the figure, in a collapsed <details>.
Its optional "charts" block adds a live measured series to a printed figure:
{figure ID: {data (JSON file under the content root with source and [date, value] points), title, unit}}.
Files charts/<figure ID>.json next to it add digitized or dataset charts (format in chart_panel).
A figure with charts gets the interactive chart and a toggle back to the printed image. All panels of one
figure share the x axis (small multiples). Each figure carries data tables and a CSV file, so it reads without JavaScript.
The site links out only: it never embeds or copies the linked media.
"""

import csv
import hashlib
import math
import html
import json
import posixpath
import shutil
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlsplit

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
OPF = "http://www.idpf.org/2007/opf"
DC = "http://purl.org/dc/elements/1.1/"
XHTML = "http://www.w3.org/1999/xhtml"
OPS = "http://www.idpf.org/2007/ops"
XML = "http://www.w3.org/XML/1998/namespace"

EPUB_ONLY = "epub-only"
INDEXED_TAGS = {"p", "h1", "h2", "h3", "figure", "table", "li"}
SEARCH_KIND = {"h1": "heading", "h2": "heading", "h3": "heading", "figure": "figure"}  # Others are "text".

type Direction = Literal["rtl", "ltr"]


class BookError(Exception):
    """The EPUB breaks a rule that the web build depends on."""


ID_MOVES: dict[str, tuple[str, Path]] = {}  # Old element ID -> (new ID, the id-moves.csv that says so). Set by build().


def load_id_moves(content_root: Path) -> None:
    """Read the id-moves.csv files that tools/ingest_pdf.py writes into the content inventory folders."""
    ID_MOVES.clear()
    for path in sorted(content_root.glob("inventory*/id-moves.csv")):
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                ID_MOVES[row["old_id"]] = (row["new_id"], path)


def missing_id(where: str, ref: str, what: str = "an ID") -> BookError:
    """Error for site data that names an element ID the EPUB does not have, with its new ID when it moved."""
    if ref in ID_MOVES:
        new, path = ID_MOVES[ref]
        return BookError(f"{where}: {ref!r} moved to {new!r} (see {path.parent.name}/{path.name}); update the data file")
    return BookError(f"{where}: {ref!r} is not {what} in the EPUB (moved IDs are listed in the content inventory's id-moves.csv)")


@dataclass(frozen=True)
class Item:
    id: str
    path: str  # Path inside the zip.
    media_type: str
    properties: frozenset[str]


@dataclass(frozen=True)
class Book:
    identifier: str
    title: str
    creator: str
    description: str
    language: str
    direction: Direction
    items: dict[str, Item]
    spine: list[Item]
    nav: Item
    cover: Item


@dataclass(frozen=True)
class SearchEntry:
    id: str
    page: str | None
    section: str | None
    text: str
    chapter: str | None = None  # ID of the top-level section that holds the entry.
    img: str | None = None  # Image path of a figure entry.


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def required(el: ET.Element | None, what: str) -> ET.Element:
    if el is None:
        raise BookError(f"missing {what}")
    return el


def read_book(z: zipfile.ZipFile) -> Book:
    container = ET.fromstring(z.read("META-INF/container.xml"))
    rootfile = required(container.find(f".//{{{CONTAINER_NS}}}rootfile"), "container rootfile")
    opf_path = rootfile.attrib["full-path"]
    opf_dir = posixpath.dirname(opf_path)
    package = ET.fromstring(z.read(opf_path))
    meta = required(package.find(f"{{{OPF}}}metadata"), "OPF metadata")

    def dc(name: str, optional: bool = False) -> str:
        el = meta.find(f"{{{DC}}}{name}")
        if el is None and optional:
            return ""
        return (required(el, f"dc:{name}").text or "").strip()

    direction = package.attrib.get("dir", "ltr")
    if direction not in ("rtl", "ltr"):
        raise BookError(f"unsupported package dir={direction!r}")

    items: dict[str, Item] = {}
    for el in required(package.find(f"{{{OPF}}}manifest"), "OPF manifest"):
        items[el.attrib["id"]] = Item(
            id=el.attrib["id"],
            path=posixpath.normpath(posixpath.join(opf_dir, unquote(el.attrib["href"]))),
            media_type=el.attrib["media-type"],
            properties=frozenset(el.attrib.get("properties", "").split()),
        )
    spine = [
        items[ref.attrib["idref"]]
        for ref in required(package.find(f"{{{OPF}}}spine"), "OPF spine")
        if ref.attrib.get("linear", "yes") != "no"
    ]
    navs = [i for i in items.values() if "nav" in i.properties]
    if len(navs) != 1:
        raise BookError(f"expected one nav document, found {len(navs)}")
    covers = [i for i in items.values() if "cover-image" in i.properties]
    if len(covers) != 1:
        raise BookError(f"expected one cover-image item, found {len(covers)}")
    return Book(
        dc("identifier"), dc("title"), dc("creator"), dc("description", optional=True),
        dc("language"), direction, items, spine, navs[0], covers[0],
    )


def is_relative(url: str) -> bool:
    parts = urlsplit(url)
    return not parts.scheme and not parts.netloc and not url.startswith("/")


class Converter:
    """Turns spine XHTML documents into one HTML document with book-wide unique IDs."""

    def __init__(self, z: zipfile.ZipFile, book: Book) -> None:
        self.z = z
        self.book = book
        self.ids: dict[str, str] = {}  # Element ID -> source document path.
        self.doc_anchor: dict[str, str] = {}  # Source document path -> first ID in that document.
        self.tags: dict[str, str] = {}  # Element ID -> tag name.
        self.tables: dict[str, dict] = {}  # Figure ID -> data table spec from the enhancements file.
        self.charts: dict[str, ET.Element] = {}  # Printed figure ID -> chart box placed inside it.
        self.skipped_docs: set[str] = set()  # Spine documents marked epub-only.
        self.crosslinks: dict[str, list[dict]] = {}  # Element ID -> crosslinks.json entries inside it.
        self.glossary: list[dict] = []  # glossary.json terms, in file order.
        self.links: list[tuple[str, str]] = []  # (source document, target ID) to check after all documents load.
        self.search: list[SearchEntry] = []
        self.bodies: list[tuple[Item, ET.Element]] = []
        self.colophon: list[str] = []  # Copyright-page and title-page sections. The site shows them in the footer.
        self.pages: dict[str, str] = {}  # Printed page label -> page marker ID, for "go to page".
        self.kinds: list[str] = []  # Kind of each converted document (class of its top section), in spine order.
        self.chapter_of: dict[str, str] = {}  # Element ID -> ID of the top-level section that holds it.
        self.chapter_title: dict[str, str] = {}  # Top-level section ID -> its heading text, without a source-note mark.
        self.byline: dict[str, tuple[str, str | None] | None] = {}  # Top-level section ID -> (byline text, lang).
        self.kind_of: dict[str, str] = {}  # Top-level section ID -> its kind (class of the section).
        self.figure_img: dict[str, tuple[str, str]] = {}  # Figure ID -> (image path in the site, alt text).

    def load(self) -> None:
        for item in self.book.spine:
            if item.media_type != "application/xhtml+xml":
                raise BookError(f"spine item {item.path} is {item.media_type}, expected XHTML")
            root = ET.fromstring(self.z.read(item.path))
            body = required(root.find(f"{{{XHTML}}}body"), f"body in {item.path}")
            # Class "epub-only" marks content that the web edition replaces with its own feature.
            top = next((el for el in body if local(el.tag) == "section"), None)
            if top is not None and EPUB_ONLY in (top.get("class") or "").split():
                self.skipped_docs.add(item.path)
                continue
            for parent in list(body.iter()):
                for child in list(parent):
                    if EPUB_ONLY in (child.get("class") or "").split():
                        if (child.tail or "").strip():
                            raise BookError(f"{item.path}: text follows epub-only element {child.get('id')!r}")
                        parent.remove(child)
            for el in body.iter():
                if (el_id := el.attrib.get("id")) is not None:
                    if el_id in self.ids:
                        raise BookError(f"duplicate id {el_id!r} in {item.path} and {self.ids[el_id]}")
                    self.ids[el_id] = item.path
                    self.tags[el_id] = local(el.tag)
                    self.doc_anchor.setdefault(item.path, el_id)
            if item.path not in self.doc_anchor:
                raise BookError(f"{item.path} has no element with an id; deep links need one")
            self.bodies.append((item, body))

    def resolve_href(self, doc: str, href: str) -> str | None:
        """In-page link for an EPUB href. None for a link into an epub-only document: the web shows its text only."""
        if not is_relative(href):
            return href
        path, _, fragment = href.partition("#")
        target_doc = posixpath.normpath(posixpath.join(posixpath.dirname(doc), unquote(path))) if path else doc
        if target_doc in self.skipped_docs:
            return None
        target = fragment or self.doc_anchor.get(target_doc, "")
        if not target:
            raise BookError(f"{doc}: link {href!r} points to a document outside the spine")
        self.links.append((doc, target))
        return f"#{target}"

    def convert(self, item: Item, body: ET.Element, enhancements: dict[str, dict[str, str]]) -> str:
        page: str | None = None
        section: str | None = None
        first_entry = len(self.search)
        top = next((el for el in body if local(el.tag) == "section"), None)
        kind = (top.get("class") or "").split(" ", 1)[0] if top is not None else ""
        chapter = top.get("id") if top is not None else None
        self.kinds.append(kind)
        if chapter and top is not None:
            self.kind_of[chapter] = kind
            self.chapter_title[chapter], self.byline[chapter] = title_and_byline(top, kind)
        for el in body.iter():
            el.tag = local(el.tag)
            attrs = dict(el.attrib)
            el.attrib.clear()
            for name, value in attrs.items():
                match name:
                    case _ if name == f"{{{OPS}}}type":
                        el.set("data-epub-type", value)
                    case _ if name == f"{{{XML}}}lang":
                        el.set("lang", value)
                    case "src" if is_relative(value):
                        el.set("src", "book/" + posixpath.normpath(posixpath.join(posixpath.dirname(item.path), unquote(value))))
                    case "href":
                        if (resolved := self.resolve_href(item.path, value)) is not None:
                            el.set("href", resolved)
                    case _:
                        el.set(local(name), value)
            if el.tag == "img" and "cover" not in body.attrib.get("data-epub-type", ""):
                el.set("loading", "lazy")
                el.set("decoding", "async")
                width, height = el.get("width"), el.get("height")
                if not (width and height and width.isdigit() and height.isdigit() and int(height) > 0):
                    raise BookError(f"{item.path}: img {el.get('src')} needs numeric width and height to prevent layout shift")
                # CSS sizes artwork from this ratio, so the box is final before the image loads.
                el.set("style", f"--ratio: {int(width) / int(height):.4f}; --w: {int(width)}px")
                # Only clearly wide photos may be cropped and panned on scroll; others always show whole.
                el.set("data-shape", "landscape" if int(width) >= 1.3 * int(height) else "upright")
            if el.get("data-epub-type") == "pagebreak":
                # Page markers carry the printed number in title. axe 4.14 rejects aria-label on doc-pagebreak.
                page = el.get("title")
                if page and el.get("id"):
                    self.pages.setdefault(page, el.get("id"))
            el_id = el.get("id")
            if el_id and chapter:
                self.chapter_of[el_id] = chapter
            if el.tag == "section" and el_id:
                heading = next((h for h in el if local(h.tag) in ("h1", "h2", "h3")), None)
                section = clean_text(heading) if heading is not None else section
            if el_id in enhancements:
                for key, value in enhancements[el_id].items():
                    el.set(f"data-{key}", value)
            indexed = el.tag in INDEXED_TAGS or (el.tag == "span" and "line" in (el.get("class") or "").split())  # Poem lines.
            if el_id and indexed and (text := clean_text(el)):
                self.search.append(SearchEntry(el_id, page, section, text))
        images = {fig.get("id"): img.get("src") for fig in body.iter("figure")
                  if fig.get("id") and (img := fig.find(".//img")) is not None}
        self.figure_img |= {fig.get("id"): (img.get("src"), img.get("alt") or "") for fig in body.iter("figure")
                            if fig.get("id") and (img := fig.find(".//img")) is not None}
        self.search[first_entry:] = [replace(e, chapter=chapter, img=images.get(e.id)) for e in self.search[first_entry:]]
        if top is not None:
            for el in list(top.iter()):
                for link in self.crosslinks.get(el.get("id", ""), []):
                    add_crosslink(el, link)
            if kind == "article":
                mark_terms(top, self.glossary)
        for fig in list(body.iter("figure")):
            if (spec := self.tables.get(fig.get("id", ""))):
                attach_table(fig, spec)
        for fig in list(body.iter("figure")):
            if (box := self.charts.get(fig.get("id", ""))) is not None:
                caption = fig.find("figcaption")
                fig.insert(list(fig).index(caption) if caption is not None else len(fig), box)
                fig.set("class", (fig.get("class", "") + " has-chart").strip())
        for parent in list(body.iter()):
            for child in list(parent):
                if "copyright-page" in child.get("data-epub-type", "").split():
                    parent.remove(child)
                    child.tail = None
                    self.colophon.append(ET.tostring(child, encoding="unicode", method="html"))
        if kind == "titlepage" and top is not None:
            # The hero shows the title; the title page credits go to the footer in small type.
            self.colophon.insert(0, ET.tostring(top, encoding="unicode", method="html"))
            body.remove(top)
        body.tag = "div"
        epub_type = body.get("data-epub-type", "")
        body.attrib.clear()
        body.set("class", "doc")
        body.set("data-src", item.path)
        if kind:
            body.set("data-kind", kind)
        if epub_type:
            body.set("data-epub-type", epub_type)
        return ET.tostring(body, encoding="unicode", method="html")

    def check_links(self) -> None:
        for doc, target in self.links:
            if target not in self.ids:
                raise BookError(f"{doc}: link target #{target} does not exist")


def clean_text(el: ET.Element) -> str:
    return " ".join("".join(el.itertext()).split())


def text_slots(el: ET.Element) -> list[tuple[ET.Element, str]]:
    """(owner, "text" or "tail") for every run of text inside el, in reading order, outside links and buttons."""
    slots = [(el, "text")]
    for child in el:
        if child.tag not in ("a", "button"):
            slots += text_slots(child)
        slots.append((child, "tail"))
    return slots


def wrap_text(root: ET.Element, owner: ET.Element, slot: str, start: int, end: int, new: ET.Element) -> ET.Element:
    """Move text[start:end] of one text slot into the new inline element, in place."""
    text = getattr(owner, slot) or ""
    new.text, new.tail = text[start:end], text[end:]
    setattr(owner, slot, text[:start])
    if slot == "text":
        owner.insert(0, new)
    else:
        parent = next(p for p in root.iter() if any(c is owner for c in p))
        parent.insert(list(parent).index(owner) + 1, new)
    return new


def add_crosslink(el: ET.Element, link: dict) -> None:
    """Link the exact text that names a chapter. A match that is already inside a link (the EPUB has it) stays as is."""
    for owner, slot in text_slots(el):
        if (at := (getattr(owner, slot) or "").find(link["text"])) >= 0:
            wrap_text(el, owner, slot, at, at + len(link["text"]),
                      ET.Element("a", {"class": "crosslink", "href": f"#{link['target']}"}))
            return
    if link["text"] not in "".join(el.itertext()):  # Present but not found above: it sits inside a link already.
        raise BookError(f"crosslinks.json: {link['text'][:40]!r} is not in {el.get('id')}")


HEBREW_PREFIXES = "ובלמשכה"
SAFE_PREFIXES = "ובלה"  # A short form takes only these, so "בצר" never matches inside "מבצר".


def is_word_char(c: str) -> bool:
    return c.isalnum() or unicodedata.category(c).startswith("M")


def find_form(text: str, form: str) -> tuple[int, int] | None:
    """First whole-word match of a glossary form, allowing up to two one-letter prefixes before it."""
    allowed = SAFE_PREFIXES if len(form) <= 3 else HEBREW_PREFIXES
    at = text.find(form)
    while at >= 0:
        end = at + len(form)
        if end == len(text) or not is_word_char(text[end]):
            for begin in range(at, max(at - 2, 0) - 1, -1):
                if all(c in allowed for c in text[begin:at]) and (begin == 0 or not is_word_char(text[begin - 1])):
                    return begin, end
        at = text.find(form, at + 1)
    return None


def mark_terms(top: ET.Element, glossary: list[dict]) -> None:
    """Mark the first use of each glossary term in a chapter, in body paragraphs and list items."""
    left = set(range(len(glossary)))
    skip_classes = {"byline", "display-title", "small", "caption", "credit"}
    for el in list(top.iter()):
        if not left:
            return
        if el.tag not in ("p", "li") or skip_classes & set((el.get("class") or "").split()):
            continue
        for owner, slot in text_slots(el):
            while left:
                text = getattr(owner, slot) or ""
                found = [(m, i) for i in left for f in glossary[i]["forms"] if (m := find_form(text, f))]
                if not found:
                    break
                (start, end), i = min(found, key=lambda x: (x[0][0], -x[0][1]))
                term = ET.Element("button", {"type": "button", "class": "term", "data-term": str(i),
                                             "popovertarget": "term-popover"})
                owner, slot = wrap_text(top, owner, slot, start, end, term), "tail"
                left.discard(i)


def load_glossary(data_dir: Path | None, conv: "Converter") -> list[dict]:
    path = data_dir / "glossary.json" if data_dir else None
    if path is None or not path.is_file():
        return []
    terms = json.loads(path.read_text(encoding="utf-8"))["terms"]
    for t in terms:
        if t["source"] not in conv.ids:
            raise missing_id(f"glossary.json: term {t['term']!r}", t["source"])
        if not t["forms"] or not t["definition"]:
            raise BookError(f"glossary.json: term {t['term']!r}: needs forms and a definition")
    return terms


def load_crosslinks(data_dir: Path | None, conv: "Converter") -> dict[str, list[dict]]:
    path = data_dir / "crosslinks.json" if data_dir else None
    if path is None or not path.is_file():
        return {}
    result: dict[str, list[dict]] = {}
    for link in json.loads(path.read_text(encoding="utf-8"))["links"]:
        for ref in (link["element"], link["target"]):
            if ref not in conv.ids:
                raise missing_id(f"crosslinks.json: {link['element']} -> {link['target']}", ref)
        result.setdefault(link["element"], []).append(link)
    return result


def glossary_data(glossary: list[dict]) -> str:
    """Term definitions for the popover. reader.js reads them by the data-term index."""
    data = [{"term": t["term"], "definition": t["definition"], "source": f"#{t['source']}"} for t in glossary]
    return f'<script type="application/json" id="glossary-data">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script>'


def title_and_byline(top: ET.Element, kind: str) -> tuple[str, tuple[str, str | None] | None]:
    """Heading text of a top-level section, and its first byline paragraph (text, lang) if it has one.
    A part title continues in the display-title paragraphs right after its heading (print splits it in two)."""
    children = list(top)
    heading = next((c for c in children if local(c.tag) in ("h1", "h2", "h3")), None)
    if heading is None:
        return "", None
    # A heading can end with a source-note asterisk and run on into a subtitle; keep the title part.
    title = clean_text(heading).split("*", 1)[0].strip()
    if kind == "part":
        for el in children[children.index(heading) + 1:]:
            if local(el.tag) == "p" and "display-title" in (el.get("class") or "").split():
                title += " " + clean_text(el)
            elif local(el.tag) != "span":  # Page markers sit between the lines.
                break
    byline = next((c for c in children if local(c.tag) == "p" and "byline" in (c.get("class") or "").split()), None)
    lang = byline.get(f"{{{XML}}}lang", byline.get("lang")) if byline is not None else None
    return title, ((clean_text(byline), lang) if byline is not None else None)


def toc_html(z: zipfile.ZipFile, book: Book, conv: Converter) -> str:
    """The EPUB toc nav as a list of in-page links. Articles after a part sit inside that part; the title
    comes from the chapter heading when the nav label is cut short, and the byline shows as the author."""
    nav_root = ET.fromstring(z.read(book.nav.path))
    toc = next(
        (n for n in nav_root.iter(f"{{{XHTML}}}nav") if n.attrib.get(f"{{{OPS}}}type") == "toc"),
        None,
    )
    toc = required(toc, "toc nav")

    def item(chapter: str, label: str) -> str:
        byline = conv.byline.get(chapter)
        author = ""
        if byline:
            lang = f' lang="{html.escape(byline[1])}"' if byline[1] else ""
            author = f'<span class="toc-author"{lang}>{html.escape(byline[0])}</span>'
        return (f'<li class="toc-item" data-chapter="{html.escape(chapter)}"><a href="#{html.escape(chapter)}">'
                f'<span class="toc-name">{html.escape(label)}</span>{author}</a></li>')

    lines, in_part = ['<ol class="toc">'], False
    for a in toc.iter(f"{{{XHTML}}}a"):
        if (href := conv.resolve_href(book.nav.path, a.attrib["href"])) is None:
            continue  # An epub-only document.
        target = href[1:]
        chapter = conv.chapter_of.get(target, target)
        kind = conv.kind_of.get(chapter, "")
        label = conv.chapter_title.get(chapter) or clean_text(a)
        if kind == "part":
            lines.append("</ol></li>" if in_part else "")
            lines.append(f'<li class="toc-part" data-chapter="{html.escape(chapter)}">'
                         f'<a class="toc-part-title" href="#{html.escape(chapter)}">{html.escape(label)}</a><ol>')
            in_part = True
            continue
        if in_part and kind != "article":
            lines.append("</ol></li>")
            in_part = False
        lines.append(item(chapter, label))
    lines.append("</ol></li></ol>" if in_part else "</ol>")
    return "\n".join(line for line in lines if line)


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


def leading_number(cell: str) -> float | None:
    """First number in a printed cell, for example 3630 in "3630 (700%)" or 9010 in "9,010"."""
    token = cell.strip().split(" ", 1)[0].replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


def table_element(fig_id: str, spec: dict) -> ET.Element:
    columns, rows, bar = spec["columns"], spec["rows"], spec.get("bar")
    ltr = set(spec.get("ltr", []))
    if any(len(r) != len(columns) for r in rows):
        raise BookError(f"enhancements.json: table {fig_id}: every row needs {len(columns)} cells")
    peak = max((leading_number(r[bar]) or 0) for r in rows) if bar is not None else 0
    table = ET.Element("table", {"class": "data-table"})
    head = ET.SubElement(ET.SubElement(table, "thead"), "tr")
    for i, name in enumerate(columns):
        th = ET.SubElement(head, "th", {"scope": "col"})
        ET.SubElement(th, "button", {"type": "button", "data-sort": str(i)}).text = name
    tbody = ET.SubElement(table, "tbody")
    for row in rows:
        tr = ET.SubElement(tbody, "tr")
        for i, cell in enumerate(row):
            attrs = {"dir": "ltr"} if i in ltr else {}
            value = leading_number(cell)
            if value is not None:
                attrs["data-value"] = f"{value:g}"
            if i == bar and value is not None and peak:
                attrs["class"] = "bar"
                attrs["style"] = f"--v: {value / peak:.3f}"
            td = ET.SubElement(tr, "th" if i == 0 else "td", attrs | ({"scope": "row"} if i == 0 else {}))
            ET.SubElement(td, "span").text = cell
    return table


def attach_table(fig: ET.Element, spec: dict) -> None:
    """Put the data table first in the figure and fold the printed image into a details element."""
    img = fig.find("img")
    if img is None:
        raise BookError(f"enhancements.json: table {fig.get('id')}: the figure has no direct img")
    details = ET.Element("details", {"class": "print-version"})
    ET.SubElement(details, "summary").text = "הטבלה כפי שהודפסה"
    index = list(fig).index(img)
    fig.remove(img)
    details.append(img)
    fig.insert(index, details)
    fig.insert(0, table_element(fig.get("id", ""), spec))
    link = ET.Element("a", {"class": "csv-link", "href": f"data/tables/{fig.get('id')}.csv", "download": ""})
    link.text = "הורדת הטבלה (CSV)"
    fig.insert(1, link)
    fig.set("class", (fig.get("class", "") + " has-table").strip())


def chart_panel(spec: dict, where: str) -> dict:
    """Check one charts/<figure>.json file and return the panel that reader.js draws. Format:
    {figure, title, source: {kind, label, url?, method, accuracy?: {x, y}, ...}, x: {label, unit, type: year|number},
    y: {label, unit}, series: [{name, kind: line|points, points: [[x, y], ...]}], bands?: [{axis, from, to, label}],
    markers?: [{axis, at, label}], notes?}. Line points keep their drawing order: x may repeat or step back."""
    if spec["x"]["type"] not in ("year", "number") or not spec["series"]:
        raise BookError(f"{where}: x.type must be year or number, and there must be series")
    for series in spec["series"]:
        if series["kind"] not in ("line", "points") or len(series["points"]) < 2:
            raise BookError(f"{where}: series {series['name']!r} needs kind line or points and two or more points")
        if any(len(pt) != 2 or not all(isinstance(v, (int, float)) for v in pt) for pt in series["points"]):
            raise BookError(f"{where}: series {series['name']!r} has a point that is not [x, y]")
    for item in [*spec.get("bands", []), *spec.get("markers", [])]:
        if item["axis"] not in ("x", "y"):
            raise BookError(f"{where}: band or marker axis must be x or y")
    source = spec["source"]
    if source.get("url") and not source["url"].startswith("https://"):
        raise BookError(f"{where}: source URL must be https")
    accuracy = source.get("accuracy")
    line = source["label"]
    if source["kind"] == "digitized":
        line += ". דיגיטציה של האיור המודפס"
        if accuracy:
            line += f"; דיוק: {accuracy['x']} בציר האופקי, {accuracy['y']} בציר האנכי"
    # Only public fields go to the site; source.overlay is a private review image.
    return {"title": spec["title"], "x": spec["x"], "y": spec["y"], "series": spec["series"],
            "bands": spec.get("bands", []), "markers": spec.get("markers", []), "notes": spec.get("notes", ""),
            "source": {"line": line + ".", "url": source.get("url"), "method": source.get("method", "")}}


def measured_panel(spec: dict, data: dict, where: str) -> dict:
    """Panel for a live measured series from the enhancements file: [ISO date, value] points."""
    points = data["points"]
    if len(points) < 2 or any(len(pt) != 2 for pt in points):
        raise BookError(f"{where}: needs at least two [date, value] points")
    if not data["source"]["url"].startswith("https://"):
        raise BookError(f"{where}: source URL must be https")
    years = f"{points[0][0][:4]}–{points[-1][0][:4]}"
    return {"title": spec["title"], "x": {"label": "תאריך", "unit": "", "type": "date"},
            "y": {"label": spec["unit"], "unit": ""}, "series": [{"name": spec["title"], "kind": "line", "points": points}],
            "bands": [], "markers": [], "notes": "",
            "source": {"line": f"נתונים עדכניים שנוספו לאתר, {years}: {data['source']['label']}.", "url": data["source"]["url"], "method": ""}}


def panel_table(panel: dict) -> ET.Element:
    """Data table of one panel. A dated series shows its first reading of each year."""
    table = ET.Element("table", {"class": "data-table"})
    ET.SubElement(table, "caption").text = panel["title"]
    head = ET.SubElement(ET.SubElement(table, "thead"), "tr")
    x_name = " ".join(filter(None, [panel["x"]["label"], panel["x"]["unit"] and f"({panel['x']['unit']})"]))
    y_name = " ".join(filter(None, [panel["y"]["label"], panel["y"]["unit"] and f"({panel['y']['unit']})"]))
    names = ["סדרה", x_name, y_name] if len(panel["series"]) > 1 else [x_name, y_name]
    for name in names:
        ET.SubElement(head, "th", {"scope": "col"}).text = name
    body = ET.SubElement(table, "tbody")
    for series in panel["series"]:
        points = series["points"]
        if panel["x"]["type"] == "date":
            first: dict[str, list] = {}
            for pt in points:
                first.setdefault(pt[0][:4], pt)
            points = list(first.values())
        for x, y in points:
            tr = ET.SubElement(body, "tr")
            if len(panel["series"]) > 1:
                ET.SubElement(tr, "td").text = series["name"]
            ET.SubElement(tr, "th", {"scope": "row", "dir": "ltr"}).text = f"{x:g}" if isinstance(x, float) else str(x)
            ET.SubElement(tr, "td", {"dir": "ltr"}).text = f"{y:g}"
    return table


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:  # The BOM lets spreadsheet apps read Hebrew.
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def chart_box(fig_id: str, panels: list[dict], href: str, csv_href: str) -> ET.Element:
    """Drawing area for reader.js, the source line of each panel, data tables and a CSV link."""
    box = ET.Element("div", {"class": "chart-box", "data-chart": href})
    ET.SubElement(box, "div", {"class": "chart-area", "hidden": "hidden"})
    for panel in panels:
        line = ET.SubElement(box, "p", {"class": "chart-source"})
        if panel["source"]["url"]:
            ET.SubElement(line, "a", {"href": panel["source"]["url"], "rel": "noopener"}).text = panel["source"]["line"]
        else:
            line.text = panel["source"]["line"]
        if panel["notes"]:
            ET.SubElement(box, "p", {"class": "chart-notes"}).text = panel["notes"]
    details = ET.SubElement(box, "details", {"class": "print-version"})
    ET.SubElement(details, "summary").text = "הנתונים בטבלה"
    for panel in panels:
        details.append(panel_table(panel))
    ET.SubElement(box, "a", {"class": "csv-link", "href": csv_href, "download": ""}).text = "הורדת הנתונים (CSV)"
    return box


def load_charts(out: Path, enhancements_file: Path | None, data_dir: Path | None, conv: "Converter") -> dict[str, ET.Element]:
    panels: dict[str, list[dict]] = {}
    measured = json.loads(enhancements_file.read_text(encoding="utf-8")).get("charts", {}) if enhancements_file else {}
    for fig_id, spec in measured.items():
        data = json.loads((enhancements_file.resolve().parent.parent / spec["data"]).read_text(encoding="utf-8"))
        panels.setdefault(fig_id, []).append(measured_panel(spec, data, f"enhancements.json: chart for {fig_id}"))
    for path in sorted((data_dir / "charts").glob("*.json")) if data_dir else []:
        spec = json.loads(path.read_text(encoding="utf-8"))
        if spec["figure"] != path.stem:
            raise BookError(f"{path.name}: figure {spec['figure']!r} does not match the file name")
        panels.setdefault(path.stem, []).append(chart_panel(spec, f"charts/{path.name}"))
    result = {}
    for fig_id, figure_panels in panels.items():
        if conv.tags.get(fig_id) != "figure":
            raise missing_id("chart", fig_id, "a figure")
        (out / "data" / "charts").mkdir(parents=True, exist_ok=True)
        (out / "data" / "charts" / f"{fig_id}.json").write_text(
            json.dumps({"figure": fig_id, "panels": figure_panels}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        rows = [[panel["title"], series["name"], x, y] for panel in figure_panels for series in panel["series"] for x, y in series["points"]]
        write_csv(out / "data" / "charts" / f"{fig_id}.csv", ["גרף", "סדרה", "x", "y"], rows)
        result[fig_id] = chart_box(fig_id, figure_panels, f"data/charts/{fig_id}.json", f"data/charts/{fig_id}.csv")
    return result


def load_tables(path: Path | None, conv: "Converter") -> dict[str, dict]:
    tables = json.loads(path.read_text(encoding="utf-8")).get("tables", {}) if path else {}
    for fig_id in tables:
        if conv.tags.get(fig_id) != "figure":
            raise missing_id("enhancements.json: table", fig_id, "a figure")
    return tables


def load_enhancements(out: Path, conv: Converter, path: Path | None) -> dict[str, dict[str, str]]:
    """Validate the enhancements file against the EPUB and copy referenced site-only assets."""
    if path is None:
        return {}
    content_root = path.resolve().parent.parent
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, str]] = {}
    for fig_id, fig in data["figures"].items():
        if conv.tags.get(fig_id) != "figure":
            raise missing_id("enhancements.json: figures", fig_id, "a figure")
        original = content_root / fig["original"]
        if not original.is_file():
            raise BookError(f"enhancements.json: {fig_id}: {original} does not exist")
        dest = out / "originals" / original.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, dest)
        result[fig_id] = {"original": f"originals/{original.name}"}
    return result


HERO_WIDTHS = (960, 1920)


def hero_html(enhancements_file: Path | None, out: Path, cover: str) -> tuple[str, str]:
    """Hero backdrop and its preload. With an enhancements "hero" block {image, alt, credit, caption, source}
    the photograph shows sharp and credited, as WebP at two widths; without one, a blurred copy of the cover."""
    hero = json.loads(enhancements_file.read_text(encoding="utf-8")).get("hero") if enhancements_file else None
    if not hero:
        return (f'<div class="hero-backdrop" aria-hidden="true"><img src="{html.escape(cover)}" alt=""></div>',
                f'<link rel="preload" href="{html.escape(cover)}" as="image">')
    if not (hero["alt"] and hero["credit"] and hero["source"]):
        raise BookError("enhancements.json: hero needs alt, credit and source")
    src = enhancements_file.resolve().parent.parent / hero["image"]
    (out / "media").mkdir(exist_ok=True)
    with Image.open(src) as im:
        for width in HERO_WIDTHS:
            copy = im.convert("RGB")
            copy.thumbnail((width, width * 4))
            copy.save(out / "media" / f"hero-{width}.webp", "WEBP", quality=80, method=6)
    srcset = ", ".join(f"media/hero-{w}.webp {w}w" for w in HERO_WIDTHS)
    caption = " · ".join(html.escape(x) for x in (hero.get("caption"), hero["credit"]) if x)
    backdrop = (f'<figure class="hero-backdrop hero-photo"><img src="media/hero-{HERO_WIDTHS[-1]}.webp" srcset="{srcset}" '
                f'sizes="100vw" alt="{html.escape(hero["alt"])}" fetchpriority="high">'
                f'<figcaption class="hero-credit">{caption}</figcaption></figure>')
    preload = f'<link rel="preload" as="image" imagesrcset="{srcset}" imagesizes="100vw">'
    return backdrop, preload


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


class Thumbs:
    """Square WebP thumbnails of site images, made once per image under OUT/thumbs/."""

    SIZE = 160

    def __init__(self, out: Path) -> None:
        self.out = out
        self.made: dict[str, str] = {}  # Image path in the site -> thumbnail path in the site.

    def __call__(self, src: str) -> str:
        if src in self.made:
            return self.made[src]
        name = posixpath.splitext(posixpath.basename(src))[0] + ".webp"
        if f"thumbs/{name}" in self.made.values():
            raise BookError(f"thumbnail name {name} is used by two images")
        dest = self.out / "thumbs" / name
        dest.parent.mkdir(exist_ok=True)
        with Image.open(self.out / src) as im:
            ImageOps.fit(im.convert("RGB"), (self.SIZE, self.SIZE)).save(dest, "WEBP", quality=72, method=6)
        self.made[src] = f"thumbs/{name}"
        return self.made[src]


def oklch_hex(lightness: float, chroma: float, hue: float) -> str | None:
    """sRGB hex for an OKLCH colour, or None when it is outside the sRGB gamut."""
    a, b = chroma * math.cos(math.radians(hue)), chroma * math.sin(math.radians(hue))
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076926715 * s_)
    if any(not 0 <= c <= 1 for c in rgb):
        return None
    srgb = (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in rgb)
    return "#" + "".join(f"{round(255 * c):02x}" for c in srgb)


def place_colours(count: int, lightness: tuple[float, float]) -> list[str]:
    """One colour per place. Hues step by the golden angle and lightness alternates, so neighbours in the
    list differ in hue and in lightness. Limit: with many places, some pairs far apart in the list look alike,
    especially with colour blindness, so each place also shows its number and name. Revisit if places get a grouping."""
    colours = []
    for i in range(count):
        hue, l_, chroma = (25 + i * 137.508) % 360, lightness[i % 2], 0.16
        # Lower the chroma to fit sRGB, but not below 0.11 (grey territory); turn the hue a little instead.
        while (colour := oklch_hex(l_, chroma, hue)) is None:
            chroma -= 0.005
            if chroma < 0.11:
                hue, chroma = (hue + 7) % 360, 0.16
        colours.append(colour)
    return colours


def number_ink(colour: str) -> str:
    """White or near-black, whichever has more WCAG contrast on the colour, for the number on a place dot."""
    channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lum = sum(w * (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
              for w, c in zip((0.2126, 0.7152, 0.0722), channels))
    return "#ffffff" if 1.05 / (lum + 0.05) >= (lum + 0.05) / 0.0617 else "#1c1a17"  # 0.0617: luminance of #1c1a17 + 0.05.


def place_style(count: int) -> str:
    """CSS custom properties --place-N (colour) and --place-ink-N (number colour) for light and dark mode."""
    def props(colours: list[str]) -> str:
        return " ".join(f"--place-{i}: {c}; --place-ink-{i}: {number_ink(c)};" for i, c in enumerate(colours, start=1))
    light = props(place_colours(count, (0.48, 0.7)))
    dark = props(place_colours(count, (0.5, 0.665)))
    return (f":root {{ {light} }}\n@media (prefers-color-scheme: dark) {{ :root:not([data-theme=\"light\"]) {{ {dark} }} }}\n"
            f":root[data-theme=\"dark\"] {{ {dark} }}")


def places_html(data_dir: Path | None, conv: "Converter", thumbs: Thumbs) -> str:
    """Map section from places.json: {"places": [{id, name, lat, lon, wikidata, targets, description,
    description_source, figures}]}. Every element ID must exist in the EPUB. Empty when the file is absent."""
    path = data_dir / "places.json" if data_dir else None
    if path is None or not path.is_file():
        return ""
    places = json.loads(path.read_text(encoding="utf-8"))["places"]
    items, points, seen = [], [], set()
    for n, place in enumerate(places, start=1):
        pid, name, lat, lon = place["id"], place["name"], float(place["lat"]), float(place["lon"])
        where = f"places.json: place {pid!r}"
        if pid in seen or pid in conv.ids:
            raise BookError(f"{where}: id is not unique")
        seen.add(pid)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise BookError(f"{where}: bad coordinates")
        if not (place["wikidata"].startswith("Q") and place["wikidata"][1:].isdigit()):
            raise BookError(f"{where}: wikidata must be a Q identifier")
        for ref in [*place["targets"], place["description_source"]]:
            if ref not in conv.ids:
                raise missing_id(where, ref)
        if not isinstance(place.get("far", False), bool):
            raise BookError(f"{where}: far must be true or false")
        if not place["targets"]:
            raise BookError(f"{where}: needs at least one target")
        for fig in place["figures"]:
            if fig not in conv.figure_img:
                raise missing_id(where, fig, "a figure with an image")
        first_target: dict[str, str] = {}  # Chapter ID -> the place's first target in it, in file order.
        for t in place["targets"]:
            first_target.setdefault(conv.chapter_of[t], t)
        chapters = [{"href": f"#{t}", "chapter": c, "title": conv.chapter_title[c]} for c, t in first_target.items()]
        points.append({
            "id": pid, "n": n, "name": name, "lat": lat, "lon": lon, "far": place.get("far", False),
            "wikidata": f"https://www.wikidata.org/wiki/{place['wikidata']}",
            "description": place["description"], "source": f"#{place['description_source']}",
            "chapters": chapters,
            "figures": [{"href": f"#{f}", "thumb": thumbs(conv.figure_img[f][0]), "alt": conv.figure_img[f][1]}
                        for f in place["figures"]],
        })
        links = "".join(f'<a href="{html.escape(c["href"])}">{html.escape(c["title"])}</a>' for c in chapters)
        items.append(f'<li id="place-{html.escape(pid)}" style="--place: var(--place-{n}); --ink: var(--place-ink-{n})">'
                     f'<span class="place-n" aria-hidden="true">{n}</span>'
                     f'<span class="place-name">{html.escape(name)}</span><span class="place-chapters">{links}</span></li>')
    data = json.dumps(points, ensure_ascii=False).replace("</", "<\\/")
    return ('<section class="places" id="places" aria-labelledby="places-title">'
            '<div class="places-head"><h2 id="places-title">המקומות בספר</h2>'
            '<p class="places-intro">לחיצה על מקום במפה מציגה את תיאורו מתוך הספר ואת הפרקים שבהם הוא מופיע.</p></div>'
            '<div class="places-map" id="places-map" hidden></div>'
            f'<details class="places-all"><summary>כל המקומות ({len(places)})</summary>'
            f'<ol class="places-list">{"".join(items)}</ol></details>'
            f'<style>{place_style(len(places))}</style>'
            f'<script type="application/json" id="places-data">{data}</script></section>')


BRAND_FILES = ("favicon.ico", "icon.svg", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-mask.png")
ICON_LINKS = """<link rel="icon" href="favicon.ico" sizes="32x32">
<link rel="icon" href="icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="apple-touch-icon.png">"""


def brand_files(enhancements_file: Path | None) -> list[Path]:
    """Icon files from the brand/ folder next to the enhancements file. A book without that folder has no icons."""
    folder = enhancements_file.parent / "brand" if enhancements_file else None
    if folder is None or not folder.is_dir():
        return []
    files = [folder / name for name in BRAND_FILES]
    if missing := [f.name for f in files if not f.is_file()]:
        raise BookError(f"{folder}: missing icon files {missing}")
    return files


def fill(template: str, values: dict[str, str]) -> str:
    """Replace {{key}} markers in one pass, so marker text inside book content stays literal."""
    head, *parts = template.split("{{")
    out, used = [head], set()
    for part in parts:
        key, sep, rest = part.partition("}}")
        if not sep or key not in values:
            raise BookError(f"site/index.html: unknown marker {{{{{key[:40]}")
        used.add(key)
        out.append(values[key] + rest)
    if missing := values.keys() - used:
        raise BookError(f"site/index.html: missing markers {sorted(missing)}")
    return "".join(out)


def build(epub: Path, out: Path, enhancements_file: Path | None = SITE / "enhancements.json") -> dict[str, object]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    epub_bytes = epub.read_bytes()
    with zipfile.ZipFile(epub) as z:
        book = read_book(z)
        conv = Converter(z, book)
        conv.load()
        assets = sorted(i.path for i in book.items.values() if i.media_type != "application/xhtml+xml")
        for path in assets:
            dest = out / "book" / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(path))
        thumbs = Thumbs(out)
        data_dir = enhancements_file.parent if enhancements_file else None
        load_id_moves(enhancements_file.resolve().parent.parent if enhancements_file else ROOT)
        enhancements = load_enhancements(out, conv, enhancements_file)
        conv.tables = load_tables(enhancements_file, conv)
        for fig_id, spec in conv.tables.items():
            write_csv(out / "data" / "tables" / f"{fig_id}.csv", spec["columns"], spec["rows"])
        conv.charts = load_charts(out, enhancements_file, data_dir, conv)
        conv.crosslinks = load_crosslinks(data_dir, conv)
        conv.glossary = load_glossary(data_dir, conv)
        docs = [conv.convert(item, body, enhancements) for item, body in conv.bodies]
        # The places map sits right after the printed contents, or before the book when it has none.
        at = conv.kinds.index("contents") + 1 if "contents" in conv.kinds else 0
        docs.insert(at, places_html(data_dir, conv, thumbs))
        toc = toc_html(z, book, conv)
        timeline = timeline_html(data_dir, conv)
        conv.check_links()
    css = next(p for p in assets if p.endswith(".css"))
    hero = hero_html(enhancements_file, out, f"book/{book.cover.path}")
    # The Kindle download is the canonical EPUB itself. Send to Kindle accepts EPUB.
    download = out / "download" / epub.name
    download.parent.mkdir()
    download.write_bytes(epub_bytes)
    page = fill(
        (SITE / "index.html").read_text(encoding="utf-8"),
        {
            "lang": html.escape(book.language),
            "dir": book.direction,
            "title": html.escape(book.title),
            "creator": html.escape(book.creator),
            "description": html.escape(book.description),
            "cover": html.escape(f"book/{book.cover.path}"),
            "epub_href": html.escape(f"download/{epub.name}"),
            "epub_size": f"{len(epub_bytes) / 1_000_000:.1f} MB",
            "book_id": html.escape(book.identifier),
            "book_css": html.escape(f"book/{css}"),
            "toc": toc,
            "timeline_tab": timeline[0],
            "timeline": timeline[1],
            "glossary": glossary_data(conv.glossary) if conv.glossary else "",
            "font_preload": "\n".join(
                f'<link rel="preload" href="{html.escape("book/" + i.path)}" as="font" type="{i.media_type}" crossorigin>'
                for i in sorted(book.items.values(), key=lambda i: i.path)
                if i.media_type.startswith("font/")
            ),
            "colophon": "\n".join(conv.colophon),
            "related": related_html(enhancements_file),
            "hero_backdrop": hero[0],
            "hero_preload": hero[1],
            "icons": ICON_LINKS if brand_files(enhancements_file) else "",
            "short_title": html.escape(book.creator),  # The bar shows the author's name when the title does not fit.
            "book": "\n".join(docs),
        },
    )
    (out / "index.html").write_text(page, encoding="utf-8")
    for name in ("reader.css", "reader.js"):
        shutil.copyfile(SITE / name, out / name)
    for path in brand_files(enhancements_file):
        shutil.copyfile(path, out / path.name)
    # Location: the running number of a text block (its index here plus one), like a Kindle location.
    search = [
        {"id": e.id, "page": e.page, "section": e.section, "chapter": e.chapter, "text": e.text,
         "kind": SEARCH_KIND.get(conv.tags[e.id], "text")} | ({"thumb": thumbs(e.img)} if e.img else {})
        for e in conv.search
    ]
    index = {"pages": conv.pages, "entries": search}
    (out / "search.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    report: dict[str, object] = {
        "epub": epub.name,
        "epub_sha256": hashlib.sha256(epub_bytes).hexdigest(),
        "spine": [i.path for i in book.spine],
        "ids": len(conv.ids),
        "search_entries": len(search),
        "enhanced_ids": sorted(enhancements),
    }
    (out / "build.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    epub = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "book.epub"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "dist" / "web"
    enh: Path | None = SITE / "enhancements.json"
    if len(sys.argv) > 3:
        enh = None if sys.argv[3] == "none" else Path(sys.argv[3])
    print(json.dumps(build(epub, out, enh), ensure_ascii=False, indent=2))
