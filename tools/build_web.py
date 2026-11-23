"""Build the static web edition from the finished EPUB file.

The EPUB is the only source of book content. The site layer (site/) adds
presentation and site-only features, attached by stable element IDs.

Usage: uv run tools/build_web.py [BOOK_EPUB] [OUT_DIR]
"""

import hashlib
import html
import json
import posixpath
import shutil
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
OPF = "http://www.idpf.org/2007/opf"
DC = "http://purl.org/dc/elements/1.1/"
XHTML = "http://www.w3.org/1999/xhtml"
OPS = "http://www.idpf.org/2007/ops"
XML = "http://www.w3.org/XML/1998/namespace"

INDEXED_TAGS = {"p", "h1", "h2", "h3", "figure", "table", "li"}
NIQQUD = range(0x0591, 0x05C8)  # Hebrew cantillation and vowel points. Search ignores them.

type Direction = Literal["rtl", "ltr"]


class BookError(Exception):
    """The EPUB breaks a rule that the web build depends on."""


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
    language: str
    direction: Direction
    items: dict[str, Item]
    spine: list[Item]
    nav: Item


@dataclass(frozen=True)
class SearchEntry:
    id: str
    page: str | None
    section: str | None
    text: str


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

    def dc(name: str) -> str:
        return (required(meta.find(f"{{{DC}}}{name}"), f"dc:{name}").text or "").strip()

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
    return Book(dc("identifier"), dc("title"), dc("language"), direction, items, spine, navs[0])


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
        self.links: list[tuple[str, str]] = []  # (source document, target ID) to check after all documents load.
        self.search: list[SearchEntry] = []
        self.bodies: list[tuple[Item, ET.Element]] = []

    def load(self) -> None:
        for item in self.book.spine:
            if item.media_type != "application/xhtml+xml":
                raise BookError(f"spine item {item.path} is {item.media_type}, expected XHTML")
            root = ET.fromstring(self.z.read(item.path))
            body = required(root.find(f"{{{XHTML}}}body"), f"body in {item.path}")
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

    def resolve_href(self, doc: str, href: str) -> str:
        if not is_relative(href):
            return href
        path, _, fragment = href.partition("#")
        target_doc = posixpath.normpath(posixpath.join(posixpath.dirname(doc), unquote(path))) if path else doc
        target = fragment or self.doc_anchor.get(target_doc, "")
        if not target:
            raise BookError(f"{doc}: link {href!r} points to a document outside the spine")
        self.links.append((doc, target))
        return f"#{target}"

    def convert(self, item: Item, body: ET.Element, enhancements: dict[str, dict[str, str]]) -> str:
        page: str | None = None
        section: str | None = None
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
                        el.set("href", self.resolve_href(item.path, value))
                    case _:
                        el.set(local(name), value)
            if el.tag == "img" and "cover" not in body.attrib.get("data-epub-type", ""):
                el.set("loading", "lazy")
                el.set("decoding", "async")
                if not (el.get("width") and el.get("height")):
                    raise BookError(f"{item.path}: img {el.get('src')} needs width and height to prevent layout shift")
            if el.get("data-epub-type") == "pagebreak":
                # Page markers carry the printed number in title. axe 4.14 rejects aria-label on doc-pagebreak.
                page = el.get("title")
            el_id = el.get("id")
            if el.tag == "section" and el_id:
                heading = next((h for h in el if local(h.tag) in ("h1", "h2", "h3")), None)
                section = clean_text(heading) if heading is not None else section
            if el_id in enhancements:
                for key, value in enhancements[el_id].items():
                    el.set(f"data-{key}", value)
            if el_id and el.tag in INDEXED_TAGS and (text := clean_text(el)):
                self.search.append(SearchEntry(el_id, page, section, text))
        body.tag = "div"
        epub_type = body.get("data-epub-type", "")
        body.attrib.clear()
        body.set("class", "doc")
        body.set("data-src", item.path)
        if epub_type:
            body.set("data-epub-type", epub_type)
        return ET.tostring(body, encoding="unicode", method="html")

    def check_links(self) -> None:
        for doc, target in self.links:
            if target not in self.ids:
                raise BookError(f"{doc}: link target #{target} does not exist")


def clean_text(el: ET.Element) -> str:
    return " ".join("".join(el.itertext()).split())


def normalize(text: str) -> str:
    """Make text match the client search normalization in site/reader.js."""
    return "".join(c for c in unicodedata.normalize("NFC", text) if ord(c) not in NIQQUD).lower()


def toc_html(z: zipfile.ZipFile, book: Book, conv: Converter) -> str:
    nav_root = ET.fromstring(z.read(book.nav.path))
    toc = next(
        (n for n in nav_root.iter(f"{{{XHTML}}}nav") if n.attrib.get(f"{{{OPS}}}type") == "toc"),
        None,
    )
    toc = required(toc, "toc nav")
    lines = ["<ol>"]
    for a in toc.iter(f"{{{XHTML}}}a"):
        href = conv.resolve_href(book.nav.path, a.attrib["href"])
        lines.append(f'<li><a href="{html.escape(href)}">{html.escape(clean_text(a))}</a></li>')
    lines.append("</ol>")
    return "\n".join(lines)


def load_enhancements(out: Path, conv: Converter) -> dict[str, dict[str, str]]:
    """Validate site/enhancements.json against the EPUB and copy referenced site-only assets."""
    data = json.loads((SITE / "enhancements.json").read_text(encoding="utf-8"))
    result: dict[str, dict[str, str]] = {}
    for fig_id, fig in data["figures"].items():
        if conv.tags.get(fig_id) != "figure":
            raise BookError(f"enhancements.json: {fig_id!r} is not a figure in the EPUB")
        original = ROOT / fig["original"]
        if not original.is_file():
            raise BookError(f"enhancements.json: {fig_id}: {original} does not exist")
        dest = out / "originals" / original.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, dest)
        result[fig_id] = {"original": f"originals/{original.name}"}
    return result


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


def build(epub: Path, out: Path) -> dict[str, object]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    epub_bytes = epub.read_bytes()
    with zipfile.ZipFile(epub) as z:
        book = read_book(z)
        conv = Converter(z, book)
        conv.load()
        enhancements = load_enhancements(out, conv)
        docs = [conv.convert(item, body, enhancements) for item, body in conv.bodies]
        toc = toc_html(z, book, conv)
        conv.check_links()
        assets = sorted(i.path for i in book.items.values() if i.media_type != "application/xhtml+xml")
        for path in assets:
            dest = out / "book" / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(path))
    css = next(p for p in assets if p.endswith(".css"))
    page = fill(
        (SITE / "index.html").read_text(encoding="utf-8"),
        {
            "lang": html.escape(book.language),
            "dir": book.direction,
            "title": html.escape(book.title),
            "book_id": html.escape(book.identifier),
            "book_css": html.escape(f"book/{css}"),
            "toc": toc,
            "book": "\n".join(docs),
        },
    )
    (out / "index.html").write_text(page, encoding="utf-8")
    for name in ("reader.css", "reader.js"):
        shutil.copyfile(SITE / name, out / name)
    search = [
        {"id": e.id, "page": e.page, "section": e.section, "text": e.text, "norm": normalize(e.text)}
        for e in conv.search
    ]
    (out / "search.json").write_text(json.dumps(search, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
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
    print(json.dumps(build(epub, out), ensure_ascii=False, indent=2))
