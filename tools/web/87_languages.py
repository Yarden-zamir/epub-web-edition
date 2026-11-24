"""Translations: translations/<lang>/<unit>.json next to the enhancements file, shown per chapter or per element.

Each file holds {"unit", "lang", "translator", "items": {element ID: inner HTML in EPUB markup}}. The build checks
every ID, converts the markup like the book text (epub:type, links, image paths), and writes
translations/<lang>/<unit>.json to the site. A figure swaps only its caption and image alt texts, so the image and
the site parts in it stay. The page gets an index of the translated chapters; site/features/85-languages.js
fetches a file when the reader asks for its language.
"""

import html
import json
import posixpath
import xml.etree.ElementTree as ET
from typing import TypedDict
from urllib.parse import unquote

from build_web import OPS, XHTML, XML, BookError, Site, is_relative, local, missing_id

LANGS = {"he", "en"}  # Languages that site/features/85-languages.js can show (LANG_DIR there).


class Unit(TypedDict):
    chapter: str  # ID of the chapter section.
    original: str  # Language the chapter was printed in.
    file: str  # Site path of the converted translation.
    lang: str
    ids: list[str]  # The translated element IDs, so the page knows them before it fetches the file.


SOURCES: dict[str, dict] = {}  # Site path -> the source translation file, read at load.


def load(site: Site) -> None:
    folder = site.data_dir / "translations" if site.data_dir else None
    if folder is None or not folder.is_dir():
        return
    for path in sorted(folder.glob("*/*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        lang = path.parent.name
        if data["lang"] != lang or data["unit"] != path.stem or lang not in LANGS:
            raise BookError(f"{path}: lang {data['lang']!r} and unit {data['unit']!r} must match the path; languages: {sorted(LANGS)}")
        if not data["translator"].strip() or not data["items"]:
            raise BookError(f"{path}: translator and items are required")
        for el_id in data["items"]:
            if el_id not in site.conv.ids:
                raise missing_id(path.name, el_id)
        SOURCES[f"translations/{lang}/{path.stem}.json"] = data


def parse(fragment: str, where: str) -> ET.Element:
    """An inner HTML fragment in EPUB markup, as one element (a wrapper around it)."""
    try:
        return ET.fromstring(f'<div xmlns="{XHTML}" xmlns:epub="{OPS}">{fragment}</div>')
    except ET.ParseError as error:
        raise BookError(f"{where}: {error}") from error


def convert(site: Site, wrapper: ET.Element, doc: str) -> None:
    """The attribute rules of build_web.Converter.convert for translated markup: plain tags, epub:type and
    xml:lang as data-epub-type and lang, links into the page, image paths into book/."""
    for el in wrapper.iter():
        el.tag = local(el.tag)
        attrs = dict(el.attrib)
        el.attrib.clear()
        for name, value in attrs.items():
            if name == f"{{{OPS}}}type":
                el.set("data-epub-type", value)
            elif name == f"{{{XML}}}lang":
                el.set("lang", value)
            elif name == "href":
                if (resolved := site.conv.resolve_href(doc, value)) is not None:
                    el.set("href", resolved)
            elif name == "src" and is_relative(value):
                el.set("src", "book/" + posixpath.normpath(posixpath.join(posixpath.dirname(doc), unquote(value))))
            else:
                el.set(local(name), value)


def inner(el: ET.Element) -> str:
    return html.escape(el.text or "", quote=False) + "".join(ET.tostring(c, encoding="unicode", method="html") for c in el)


def ids_in(el: ET.Element) -> list[str]:
    return [d.get("id") for d in el.iter() if d is not el and d.get("id")]


def values(site: Site) -> dict[str, str]:
    if not SOURCES:
        return {}
    page: dict[str, ET.Element] = {el.get("id"): el for _, body in site.conv.bodies for el in body.iter() if el.get("id")}
    index: dict[str, list[Unit]] = {}
    for file, data in SOURCES.items():
        lang, items, figures = data["lang"], {}, {}
        chapters = {site.conv.chapter_of.get(el_id) for el_id in data["items"]}
        if len(chapters) != 1 or None in chapters:
            raise BookError(f"{file}: the items must belong to one chapter, found {sorted(map(str, chapters))}")
        chapter = chapters.pop()
        for el_id, fragment in data["items"].items():
            if el_id not in page:  # The title page and the copyright page move to the footer.
                raise missing_id(file, el_id, "an element of the book text")
            original = page[el_id]
            wrapper = parse(fragment, f"{file}: {el_id}")
            convert(site, wrapper, site.conv.ids[el_id])
            if original.tag == "figure":
                figures[el_id] = figure_parts(file, el_id, original, wrapper)
                continue
            # The swap must keep every ID (page markers, note references) and every image of the element.
            if ids_in(wrapper) != ids_in(original):
                raise BookError(f"{file}: {el_id}: the inner IDs {ids_in(wrapper)} differ from the book's {ids_in(original)}")
            if [i.get("src") for i in wrapper.iter("img")] != [i.get("src") for i in original.iter("img")]:
                raise BookError(f"{file}: {el_id}: the images differ from the book's")
            items[el_id] = inner(wrapper)
        heading = next((h for h in page[chapter].iter() if h.tag in ("h1", "h2", "h3")), page[chapter])
        out = site.out / file
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"lang": lang, "items": items, "figures": figures}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        index.setdefault(chapter, []).append(Unit(chapter=chapter, original=heading.get("lang") or site.book.language,
                                                  file=file, lang=lang, ids=list(data["items"])))
    site.report["translations"] = sorted(SOURCES)
    data = json.dumps(index, ensure_ascii=False).replace("</", "<\\/")
    return {"end": f'<script type="application/json" id="translations-data">{data}</script>\n'}


def figure_parts(file: str, el_id: str, original: ET.Element, wrapper: ET.Element) -> dict:
    """A translated figure: its caption's inner HTML and the alt text of each image, in order."""
    caption = wrapper.find("figcaption")
    book_caption = original.find("figcaption")
    if (caption is None) != (book_caption is None):
        raise BookError(f"{file}: {el_id}: the translation and the book differ in having a caption")
    book_imgs, imgs = list(original.iter("img")), list(wrapper.iter("img"))
    if len(imgs) != len(book_imgs):
        raise BookError(f"{file}: {el_id}: {len(imgs)} images in the translation, {len(book_imgs)} in the book")
    if caption is not None and ids_in(caption) != ids_in(book_caption):
        raise BookError(f"{file}: {el_id}: caption IDs {ids_in(caption)} differ from the book's {ids_in(book_caption)}")
    return {"caption": inner(caption) if caption is not None else None, "alts": [img.get("alt") or "" for img in imgs]}
