# /// script
# requires-python = ">=3.15"
# dependencies = ["pillow==13.0.0"]
# ///
"""Build the static web edition from the finished EPUB file.

The EPUB is the only source of book content. The site layer adds presentation and site-only features,
attached by stable element IDs. This file is the core: it reads the EPUB, converts the spine into one page,
fills site/index.html and joins site/features/*.js and *.css into reader.js and reader.css.
Each feature (search, places, charts, glossary, …) is a module in tools/web/, found by name; the hooks are
described in site/features/README.md.

Usage: uv run tools/build_web.py [BOOK_EPUB] [OUT_DIR] [ENHANCEMENTS_JSON | none]

ENHANCEMENTS_JSON defaults to site/enhancements.json. The other site data files (places.json, timeline.json,
charts/, …) sit in the same folder. "none" uses no site data.
"""

import csv
import functools
import hashlib
import importlib.util
import html
import json
import posixpath
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType
from typing import Callable, Literal
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
        self.skipped_docs: set[str] = set()  # Spine documents marked epub-only.
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

    def convert(self, item: Item, body: ET.Element, transforms: list[Callable[[ET.Element, ET.Element | None, str], None]]) -> str:
        """One spine document as HTML. Each feature transform then changes the document (body, top section, kind)."""
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
            indexed = el.tag in INDEXED_TAGS or (el.tag == "span" and "line" in (el.get("class") or "").split())  # Poem lines.
            if el_id and indexed and (text := clean_text(el)):
                self.search.append(SearchEntry(el_id, page, section, text))
        images = {fig.get("id"): img.get("src") for fig in body.iter("figure")
                  if fig.get("id") and (img := fig.find(".//img")) is not None}
        self.figure_img |= {fig.get("id"): (img.get("src"), img.get("alt") or "") for fig in body.iter("figure")
                            if fig.get("id") and (img := fig.find(".//img")) is not None}
        self.search[first_entry:] = [replace(e, chapter=chapter, img=images.get(e.id)) for e in self.search[first_entry:]]
        for transform in transforms:
            transform(body, top, kind)
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


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:  # The BOM lets spreadsheet apps read Hebrew.
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


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


@dataclass
class Site:
    """What a feature module sees: the book, the converter, the output folder and the site data folder."""

    z: zipfile.ZipFile
    book: Book
    conv: Converter
    out: Path
    epub: Path
    enhancements_file: Path | None
    data_dir: Path | None  # The folder that holds enhancements.json and the other site data files.
    thumbs: Thumbs
    report: dict[str, object]


HOOKS = ("load", "transform", "after_contents", "values", "write")
SHARED_SLOTS = ("head", "end")  # Template markers that several features may fill; their parts join in feature order.


def load_features() -> list[ModuleType]:
    """Every tools/web/*.py feature module, in file name order. Each build loads them fresh, so module state never
    carries over from an earlier build. A module defines any of HOOKS (see site/features/README.md)."""
    features = []
    for path in sorted((ROOT / "tools" / "web").glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"web_feature_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not any(hasattr(module, hook) for hook in HOOKS):
            raise BookError(f"{path.name}: a feature module needs at least one of {HOOKS}")
        features.append(module)
    return features


def bundle(suffix: str) -> str:
    """site/features/*.js or *.css joined in file name order: one script and one stylesheet for the page."""
    return "".join(p.read_text(encoding="utf-8") for p in sorted((SITE / "features").glob(f"*{suffix}")))


def build(epub: Path, out: Path, enhancements_file: Path | None = SITE / "enhancements.json") -> dict[str, object]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    epub_bytes = epub.read_bytes()
    if enhancements_file:
        # Site data must not use a paragraph ID that ingestion moved (tools/check_ids.py reads the content's id-moves.csv).
        content = enhancements_file.resolve().parent.parent
        if (content / "id-moves.csv").is_file():
            check = subprocess.run([sys.executable, str(ROOT / "tools" / "check_ids.py"), str(content)], capture_output=True, text=True)
            if check.returncode != 0:
                raise BookError(f"tools/check_ids.py: site data uses moved IDs\n{check.stdout}{check.stderr}")
    features = load_features()
    hooked = lambda hook: [getattr(f, hook) for f in features if hasattr(f, hook)]  # noqa: E731
    with zipfile.ZipFile(epub) as z:
        book = read_book(z)
        conv = Converter(z, book)
        conv.load()
        assets = sorted(i.path for i in book.items.values() if i.media_type != "application/xhtml+xml")
        for path in assets:
            dest = out / "book" / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(path))
        data_dir = enhancements_file.parent if enhancements_file else None
        site = Site(z, book, conv, out, epub, enhancements_file, data_dir, Thumbs(out), {})
        load_id_moves(enhancements_file.resolve().parent.parent if enhancements_file else ROOT)
        for load in hooked("load"):
            load(site)
        transforms = [functools.partial(t, site) for t in hooked("transform")]
        docs = [conv.convert(item, body, transforms) for item, body in conv.bodies]
        # Consecutive facsimile pages share one container, so the browser tracks one off-screen box instead of
        # hundreds (content-visibility in 02-book.css). Feature sections then go right after the printed contents.
        grouped: list[str] = []
        kinds: list[str] = []
        for doc, kind in zip(docs, conv.kinds):
            if kind == "facsimile-page" and kinds and kinds[-1] == "facsimile-page":
                grouped[-1] = grouped[-1].removesuffix("</div>") + "\n" + doc + "</div>"
            else:
                grouped.append(f'<div class="fx-set">{doc}</div>' if kind == "facsimile-page" else doc)
                kinds.append(kind)
        docs = grouped
        at = kinds.index("contents") + 1 if "contents" in kinds else 0
        docs.insert(at, "".join(part(site) for part in hooked("after_contents")))
        values: dict[str, str] = dict.fromkeys(SHARED_SLOTS, "")
        for feature_values in hooked("values"):
            for key, value in feature_values(site).items():
                if key in SHARED_SLOTS:
                    values[key] += value
                elif key in values:
                    raise BookError(f"template marker {key!r} has two features")
                else:
                    values[key] = value
        conv.check_links()
    css = next(p for p in assets if p.endswith(".css"))
    # The Kindle download is the canonical EPUB itself. Send to Kindle accepts EPUB.
    download = out / "download" / epub.name
    download.parent.mkdir()
    download.write_bytes(epub_bytes)
    core = {
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
        "font_preload": "\n".join(
            f'<link rel="preload" href="{html.escape("book/" + i.path)}" as="font" type="{i.media_type}" crossorigin>'
            for i in sorted(book.items.values(), key=lambda i: i.path)
            if i.media_type.startswith("font/")
        ),
        "colophon": "\n".join(conv.colophon),
        "short_title": html.escape(book.creator),  # The bar shows the author's name when the title does not fit.
        "book": "\n".join(docs),
    }
    if clash := core.keys() & values.keys():
        raise BookError(f"features fill core template markers {sorted(clash)}")
    page = fill((SITE / "index.html").read_text(encoding="utf-8"), core | values)
    (out / "index.html").write_text(page, encoding="utf-8")
    (out / "reader.css").write_text(bundle(".css"), encoding="utf-8")
    (out / "reader.js").write_text(bundle(".js"), encoding="utf-8")
    site.report.update({
        "epub": epub.name,
        "epub_sha256": hashlib.sha256(epub_bytes).hexdigest(),
        "spine": [i.path for i in book.spine],
        "ids": len(conv.ids),
    })
    for write in hooked("write"):
        write(site)
    (out / "build.json").write_text(json.dumps(site.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return site.report


if __name__ == "__main__":
    # Feature modules import this file as "build_web"; make that name this running module, not a second copy.
    sys.modules.setdefault("build_web", sys.modules["__main__"])
    epub = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "book.epub"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "dist" / "web"
    enh: Path | None = SITE / "enhancements.json"
    if len(sys.argv) > 3:
        enh = None if sys.argv[3] == "none" else Path(sys.argv[3])
    print(json.dumps(build(epub, out, enh), ensure_ascii=False, indent=2))
