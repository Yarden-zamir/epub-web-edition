"""Navigator: the EPUB toc nav as parts and chapters with authors, for the chapters panel."""

import html
import xml.etree.ElementTree as ET
import zipfile

from build_web import Book, Converter, OPS, Site, XHTML, clean_text, required


def printed_names(conv: Converter) -> dict[str, str]:
    """Chapter ID -> its name in the printed contents (ol.contents), which can differ from the chapter heading."""
    names: dict[str, str] = {}
    for _, body in conv.bodies:
        for ol in body.iter("ol"):
            if "contents" in (ol.get("class") or "").split():
                for a in ol.iter("a"):
                    if (href := a.get("href", "")).startswith("#"):
                        names.setdefault(conv.chapter_of.get(href[1:], href[1:]), clean_text(a))
    return names


def words(text: str) -> set[str]:
    return {w.strip("-–:,.'\"״׳?!()") for w in text.split()} - {""}


def toc_html(z: zipfile.ZipFile, book: Book, conv: Converter) -> str:
    """The EPUB toc nav as a list of in-page links. Articles after a part sit inside that part; the title
    comes from the chapter heading when the nav label is cut short, and the byline shows as the author."""
    nav_root = ET.fromstring(z.read(book.nav.path))
    toc = next(
        (n for n in nav_root.iter(f"{{{XHTML}}}nav") if n.attrib.get(f"{{{OPS}}}type") == "toc"),
        None,
    )
    toc = required(toc, "toc nav")
    printed = printed_names(conv)

    def item(chapter: str, label: str) -> str:
        byline = conv.byline.get(chapter)
        author = ""
        if byline:
            lang = f' lang="{html.escape(byline[1])}"' if byline[1] else ""
            author = f'<span class="toc-author"{lang}>{html.escape(byline[0])}</span>'
        # A printed contents name that shares no word with the heading (print "צרור תודות" for "להצלחה אבות רבים")
        # shows under the title, so a reader who comes from the printed contents finds the chapter.
        name = printed.get(chapter, "")
        also = (f'<span class="toc-printed">בתוכן העניינים: {html.escape(name)}</span>'
                if name and not words(name) & words(label) else "")
        return (f'<li class="toc-item" data-chapter="{html.escape(chapter)}"><a href="#{html.escape(chapter)}">'
                f'<span class="toc-name">{html.escape(label)}</span>{also}{author}</a></li>')

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


def values(site: Site) -> dict[str, str]:
    return {"toc": toc_html(site.z, site.book, site.conv)}
