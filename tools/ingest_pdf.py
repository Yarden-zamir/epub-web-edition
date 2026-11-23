# /// script
# requires-python = ">=3.13"
# dependencies = ["pymupdf==1.28.2"]
# ///
"""Convert a print PDF into an EPUB source tree and a page inventory.

Usage: uv run tools/ingest_pdf.py CONTENT_DIR
       uv run tools/ingest_pdf.py CONTENT_DIR --print-units FIRST-LAST   (contents PDF pages)

CONTENT_DIR holds book.toml. The script writes CONTENT_DIR/epub-src/ and
CONTENT_DIR/inventory/{pages,assets,issues}.csv. All book content stays in CONTENT_DIR.

Rules:
- Text comes only from the PDF text layer. The script never invents text.
- Images are copied byte for byte from the PDF streams (extract_image).
- Every page gets a page marker and an inventory row with status "pending".
  A person sets "verified" after a visual check against the PDF.
- Each automatic text change (hyphen joins) is an issue row.
- Line text is ordered by printed glyph position, not by PDF stream order (see visual_to_logical).
"""

import csv
import hashlib
import html
import shutil
import sys
import tomllib
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pymupdf

PIPELINE = Path(__file__).resolve().parent.parent
FONT_DIR = PIPELINE / "epub-src" / "OEBPS" / "fonts"
BOOK_CSS = PIPELINE / "epub-src" / "OEBPS" / "css" / "book.css"

type Role = Literal["body", "display", "title", "byline", "subheading", "small", "caption", "footnote"]
# "small": small print. attach_captions() turns it into "caption" (next to an image) or "footnote" (low on the page).
type UnitKind = Literal["cover", "blank", "titlepage", "contents", "frontispiece", "article", "part",
                       "bibliography", "backcover", "end"]


@dataclass
class Cluster:
    """One base character with its combining marks (Hebrew points), at its printed position."""
    x0: float
    x1: float
    text: str
    style: Literal["", "b", "sup"]


@dataclass
class Line:
    page: int
    y0: float
    y1: float
    x0: float
    x1: float
    role: Role
    html: str  # Escaped text with inline markup.
    text: str  # Plain text.
    rtl: bool
    size: float
    clusters: list[Cluster] = field(default_factory=list)


@dataclass
class Figure:
    page: int
    bbox: tuple[float, float, float, float]
    file: str
    width: int
    height: int
    xref: int
    captions: list[Line] = field(default_factory=list)


@dataclass
class Unit:
    id: str
    kind: UnitKind
    start: int
    end: int  # Inclusive PDF page.
    pages: list[int]  # Reading order of the unit's PDF pages.


class IngestError(Exception):
    """The PDF or the config breaks an assumption of this script."""


def hebrew_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum("֐" <= c <= "׿" for c in letters) / len(letters)


def role_for(font: str, size: float, rules: list[dict[str, object]]) -> Role:
    for rule in rules:
        if str(rule["font"]) in font and float(rule.get("min", 0)) <= size <= float(rule.get("max", 999)):
            return rule["role"]  # type: ignore[return-value]
    return "body"


LTR_JOINERS = set(".,:/%+-'– ")
CLOSERS = set(".,:;!?)]”")  # No space before these. ASCII quotes are ambiguous in Hebrew (geresh, gershayim), so they stay out.
OPENERS = set("([“")  # No synthetic space after these.


def ltr_strong(c: str) -> bool:
    return c.isascii() and c.isalnum()


def visual_to_logical(clusters: list[Cluster], rtl: bool) -> list[Cluster]:
    """Order clusters by printed position, then restore left-to-right runs inside Hebrew lines.

    The PDF content-stream order is not reliable: MuPDF can return a Hebrew line starting mid-line.
    Printed positions are reliable. Right to left by position is the logical order of Hebrew text.
    Runs of digits and Latin letters print left to right, so they come out reversed and flip back.
    Limit: brackets keep the character the PDF stores. Revisit if a mirrored bracket shows up in review.
    """
    ordered = sorted(clusters, key=lambda c: -(c.x0 + c.x1) if rtl else (c.x0 + c.x1))
    if not rtl:
        return ordered
    out: list[Cluster] = []
    i = 0
    while i < len(ordered):
        if not ltr_strong(ordered[i].text[:1]):
            out.append(ordered[i])
            i += 1
            continue
        j = i
        while j + 1 < len(ordered):
            nxt = ordered[j + 1].text[:1]
            if ltr_strong(nxt) or (nxt in LTR_JOINERS and j + 2 < len(ordered) and ltr_strong(ordered[j + 2].text[:1])):
                j += 1
            else:
                break
        out.extend(reversed(ordered[i:j + 1]))
        i = j + 1
    return out


def render(clusters: list[Cluster], size: float, rtl: bool) -> tuple[str, str]:
    """Plain text and escaped markup. Adds a space where printed glyphs have a word-sized gap."""
    text, parts, style, buf = [], [], "", []
    prev: Cluster | None = None

    def flush() -> None:
        if not buf:
            return
        chunk = html.escape("".join(buf), quote=False)
        parts.append({"b": f"<b>{chunk}</b>", "sup": f'<sup class="ref">{chunk}</sup>'}.get(style, chunk))
        buf.clear()

    for c in clusters:
        if prev is not None:
            gap = (prev.x0 - c.x1) if rtl else (c.x0 - prev.x1)
            if (gap > 0.25 * size and not prev.text.isspace() and not c.text.isspace()
                    and c.text not in CLOSERS and prev.text not in OPENERS):
                text.append(" ")
                buf.append(" ")
        if c.style != style:
            flush()
            style = c.style
        text.append(c.text)
        buf.append(c.text)
        prev = c
    flush()
    return tidy_spaces("".join(text)), tidy_spaces("".join(parts))


def tidy_spaces(s: str) -> str:
    """Collapse whitespace; drop spaces before closing punctuation and after opening brackets."""
    words = " ".join(s.split())
    out: list[str] = []
    for i, ch in enumerate(words):
        if ch == " " and ((i + 1 < len(words) and words[i + 1] in CLOSERS) or (out and out[-1] in OPENERS)):
            continue
        out.append(ch)
    return "".join(out)


def merge_fragments(frags: list[Line]) -> list[Line]:
    """Join the PDF text fragments of one printed line and order its characters by position.

    MuPDF splits a printed line where the direction changes. Fragments that overlap vertically
    belong to one line, including raised footnote digits.
    """
    frags = sorted(frags, key=lambda f: f.y0)
    groups: list[list[Line]] = []
    for f in frags:
        mid = (f.y0 + f.y1) / 2
        for g in groups:
            if min(x.y0 for x in g) <= mid <= max(x.y1 for x in g):
                g.append(f)
                break
        else:
            groups.append([f])
    merged: list[Line] = []
    for g in groups:
        main = max(g, key=lambda f: len(f.clusters))
        clusters = [c for f in g for c in f.clusters]
        rtl = hebrew_share("".join(c.text for c in clusters)) >= 0.5
        text, markup = render(visual_to_logical(clusters, rtl), main.size, rtl)
        merged.append(Line(main.page, min(f.y0 for f in g), max(f.y1 for f in g), min(f.x0 for f in g),
                           max(f.x1 for f in g), main.role, markup, text, rtl, main.size, clusters))
    merged.sort(key=lambda ln: ln.y0)
    return merged


class Ingest:
    def __init__(self, content: Path) -> None:
        self.content = content
        self.cfg = tomllib.loads((content / "book.toml").read_text(encoding="utf-8"))
        pdf = Path(str(self.cfg["pdf"])).expanduser()
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if digest != self.cfg["pdf_sha256"]:
            raise IngestError(f"{pdf}: sha256 {digest} does not match book.toml")
        self.doc = pymupdf.open(pdf)
        self.layout = self.cfg["layout"]
        self.rules = self.cfg["role"]
        self.char_map: dict[str, str] = self.cfg.get("char_map", {})
        self.out = content / "epub-src"
        self.issues: list[dict[str, str]] = []
        self.assets: list[dict[str, str]] = []
        self.seen_xrefs: dict[int, str] = {}
        self.units = self.load_units()

    # ---------- structure ----------

    def load_units(self) -> list[Unit]:
        raw = self.cfg["unit"]
        units = []
        for i, u in enumerate(raw):
            end = raw[i + 1]["start"] - 1 if i + 1 < len(raw) else self.doc.page_count
            order = u.get("page_order", list(range(u["start"], end + 1)))
            if sorted(order) != list(range(u["start"], end + 1)):
                raise IngestError(f"unit {u['id']}: page_order must list PDF pages {u['start']}-{end} once each")
            units.append(Unit(u["id"], u["kind"], u["start"], end, order))
        if units[0].start != 1:
            raise IngestError("the first unit must start at PDF page 1")
        return [u for u in units if u.kind != "end"]

    def label(self, page: int) -> str:
        printed = page - int(self.layout["folio_offset"])
        return str(printed) if printed >= 1 else ["i", "ii", "iii", "iv", "v", "vi"][page - 1]

    def issue(self, page: int, kind: str, text: str) -> None:
        self.issues.append({"id": f"A-{len(self.issues) + 1:04d}", "page": str(page), "type": kind,
                            "description": text, "status": "open"})

    # ---------- page reading ----------

    def is_running_head(self, font: str, size: float) -> bool:
        return any(name in font and abs(size - float(sz)) < 0.3 for name, sz in self.layout["running_head_fonts"])

    def lines(self, pno: int) -> list[Line]:
        kept = []
        for ln in merge_fragments(self.fragments(pno)):
            rule = next((o for o in self.cfg.get("omit", []) if o["page"] == pno and o["contains"] in ln.text), None)
            if rule:
                self.issue(pno, "intentional-change", f"Omitted {ln.text[:60]!r}: {rule['reason']}")
                continue
            kept.append(ln)
        return kept

    def fragments(self, pno: int) -> list[Line]:
        """PDF text fragments of a page with letter clusters, without running heads and folios."""
        page = self.doc[pno - 1]
        height = page.rect.height
        result: list[Line] = []
        for block in page.get_text("rawdict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                spans = [s for s in line["spans"] if "".join(c["c"] for c in s["chars"]).strip()]
                if not spans:
                    continue
                y0, y1 = line["bbox"][1], line["bbox"][3]
                main = max(spans, key=lambda s: len(s["chars"]))
                font, size = main["font"].split("+")[-1], main["size"]
                if y1 / height < float(self.layout["header_max_y"]) and self.is_running_head(font, size):
                    continue
                clusters: list[Cluster] = []
                for s in line["spans"]:
                    digits = "".join(c["c"] for c in s["chars"]).strip()
                    style: Literal["", "b", "sup"] = ""
                    if digits.isdigit() and s["size"] < size * 0.8:
                        style = "sup"
                    elif s["flags"] & 16 and not main["flags"] & 16:
                        style = "b"
                    for ch in s["chars"]:
                        c = ch["c"].replace("\t", " ")
                        if c in self.char_map:
                            if not self.char_map[c].isspace():
                                self.issue(pno, "char-map", f"U+{ord(c):04X} mapped to U+{ord(self.char_map[c]):04X}; check against print")
                            c = self.char_map[c]
                        if ord(c) < 32:
                            raise IngestError(f"PDF page {pno}: control character U+{ord(c):04X}; add it to [char_map] in book.toml")
                        if unicodedata.combining(c) and clusters:
                            clusters[-1].text += c  # Points stay with their letter.
                            continue
                        clusters.append(Cluster(ch["bbox"][0], ch["bbox"][2], c, style))
                plain = "".join(c.text for c in clusters)
                role = role_for(font, size, self.rules)  # "small" resolves to caption or footnote later.
                result.append(Line(pno, y0, y1, line["bbox"][0], line["bbox"][2], role, "", plain,
                                   hebrew_share(plain) >= 0.5, size, clusters))
        return result

    def figures(self, pno: int) -> list[Figure]:
        page = self.doc[pno - 1]
        figs = []
        placed: set[int] = set()
        for info in page.get_image_info(xrefs=True):
            xref = info["xref"]
            if not xref or xref in placed:
                continue  # Inline image, or a second placement of the same image on this page.
            placed.add(xref)
            bbox = tuple(info["bbox"])
            if (bbox[2] - bbox[0]) < 30 or (bbox[3] - bbox[1]) < 30:
                continue  # Rules, bullets and other ornaments.
            if f"p{pno:03d}-x{xref}" in self.cfg.get("decorative", []):
                self.issue(pno, "info", f"p{pno:03d}-x{xref}: decorative per book.toml; not in the EPUB")
                continue
            if xref in self.seen_xrefs:
                self.issue(pno, "reuse", f"Image xref {xref} repeats; first file {self.seen_xrefs[xref]}")
            image = self.doc.extract_image(xref)
            name = f"p{pno:03d}-x{xref}.{image['ext']}"
            dest = self.out / "OEBPS" / "images" / name
            dest.write_bytes(image["image"])
            self.seen_xrefs.setdefault(xref, name)
            if image.get("smask"):
                self.issue(pno, "image", f"{name}: the PDF masks this image; the mask is not applied")
            figs.append(Figure(pno, bbox, name, image["width"], image["height"], xref))
            self.assets.append({"file": f"OEBPS/images/{name}", "sha256": hashlib.sha256(image["image"]).hexdigest(),
                                "pdf_page": str(pno), "pdf_xref": str(xref), "pixels": f"{image['width']}x{image['height']}",
                                "derivation": "unmodified PDF image stream", "status": "pending"})
        return figs

    # ---------- assembly ----------

    def paragraphs(self, lines: list[Line]) -> list[list[Line]]:
        if not lines:
            return []
        body = [ln for ln in lines if ln.role == "body"] or lines
        left, right = min(ln.x0 for ln in body), max(ln.x1 for ln in body)
        indent, short = float(self.layout["indent_tolerance"]), float(self.layout["short_tolerance"])
        paras: list[list[Line]] = [[lines[0]]]
        for prev, cur in zip(lines, lines[1:]):
            gap = cur.y0 - prev.y1
            if cur.role != prev.role or gap > max(cur.y1 - cur.y0, 6) * 0.9 or gap < -2:
                paras.append([cur])
                continue
            if cur.rtl:
                starts = cur.x1 < right - indent
                prev_short = prev.x0 > left + short
            else:
                starts = cur.x0 > left + indent
                prev_short = prev.x1 < right - short
            if cur.role in ("footnote", "caption", "small"):
                # Notes and sources use hanging indents: only a leading number starts a new entry.
                starts = cur.text.split(" ", 1)[0].rstrip(".").isdigit()
            if starts or (prev_short and cur.role == "body"):
                paras.append([cur])
            else:
                paras[-1].append(cur)
        return paras

    def join(self, para: list[Line]) -> str:
        out = para[0].html
        for prev, cur in zip(para, para[1:]):
            if not prev.rtl and prev.text.endswith("-") and cur.text[:1].islower():
                out = out[:-1] + cur.html
                self.issue(prev.page, "hyphen", f"Joined a line-end hyphen: {prev.text.split()[-1]!r}")
            else:
                out += " " + cur.html
        return out

    def attach_captions(self, figs: list[Figure], lines: list[Line]) -> list[Line]:
        gap = float(self.layout["caption_gap"])
        height = self.doc[0].rect.height
        rest = []
        for ln in lines:
            target = None
            if ln.role == "small":
                for f in figs:
                    overlap = min(f.bbox[2], ln.x1) - max(f.bbox[0], ln.x0) > 0
                    near = -2 <= ln.y0 - f.bbox[3] <= gap or -2 <= f.bbox[1] - ln.y1 <= gap
                    if overlap and near:
                        target = f
                        break
            if target:
                ln.role = "caption"
                target.captions.append(ln)
            else:
                if ln.role == "small":
                    ln.role = "footnote" if ln.y0 / height >= float(self.layout["footnote_min_y"]) else "caption"
                rest.append(ln)
        return rest

    def caption_html(self, fig: Figure) -> str:
        if not fig.captions:
            self.issue(fig.page, "info", f"{fig.file}: no caption next to this image in print")
            return ""
        prefixes = tuple(self.layout["credit_prefixes"])
        spans = []
        for para in self.paragraphs(fig.captions):
            text = self.join(para)
            cls = "credit" if para[0].text.startswith(prefixes) else "caption"
            spans.append(f'<span class="{cls}">{text}</span>')
        return "<figcaption>" + "".join(spans) + "</figcaption>"

    def contents_rows(self, pno: int) -> list[tuple[str, list[str]]]:
        """Rows of a printed contents page: ("heading" | "part" | "entry", [title, author?, page?]).

        Entries print in columns: title (right), author (right-aligned on one edge), page number (left).
        The author edge is the largest right edge among the smaller author-size fragments of the page.
        """
        frags = self.fragments(pno)
        entry_size = max((f.size for f in frags if f.size < 12.5), default=0)
        author_edge = max((f.x1 for f in frags if f.size < entry_size - 0.5), default=0)
        rows = []
        for line in merge_fragments(frags):
            kind = "heading" if line.size >= 20 else "part" if line.size >= 12.5 else "entry"
            if kind != "entry":
                rtl = hebrew_share(line.text) >= 0.5
                rows.append((kind, [render(visual_to_logical(line.clusters, rtl), line.size, rtl)[0]]))
                continue
            title = [c for c in line.clusters if (c.x0 + c.x1) / 2 > author_edge + 3]
            rest = [c for c in line.clusters if (c.x0 + c.x1) / 2 <= author_edge + 3]
            cells = []
            for group in (title, rest):
                if group:
                    rtl = hebrew_share("".join(c.text for c in group)) >= 0.5
                    cells.append(render(visual_to_logical(group, rtl), line.size, rtl)[0])
            if cells and len(cells[-1].split()) > 0 and cells[-1].split()[-1].isdigit():
                *words, page = cells[-1].split()
                cells = cells[:-1] + ([" ".join(words)] if words else []) + [page]
            rows.append((kind, cells))
        return rows

    def contents_html(self, unit: Unit) -> tuple[str, str | None]:
        """The printed contents as one nested list. Page markers sit inside the first item of each page."""
        start_of = {u.start: u for u in self.units}
        head: list[str] = []
        items: list[str] = []
        heading: str | None = None
        open_part = False
        for pno in range(unit.start, unit.end + 1):
            marker = f'<span epub:type="pagebreak" role="doc-pagebreak" id="pg-{pno}" title="{self.label(pno)}"/>'
            if pno == unit.start:
                head.append(marker)
                marker = ""
            for kind, cells in self.contents_rows(pno):
                esc = [html.escape(c, quote=False) for c in cells]
                if kind == "heading":
                    heading = cells[0]
                    head.append(f'<h2 id="{unit.id}-h">{esc[0]}</h2>')
                    continue
                if kind == "part":
                    if open_part:
                        items.append("</ol></li>")
                    items.append(f'<li class="part">{marker}<span class="part-title">{esc[0]}</span><ol>')
                    marker, open_part = "", True
                    continue
                if not open_part:
                    items.append('<li class="part front"><ol>')
                    open_part = True
                page = cells[-1] if cells and cells[-1].isdigit() else None
                title = esc[0]
                author = esc[1] if (len(esc) > 2 or (len(esc) == 2 and page is None)) else ""
                target = start_of.get(int(page) + int(self.layout["folio_offset"])) if page else None
                if target is None:
                    self.issue(pno, "contents", f"Contents entry {cells!r}: no unit starts at its page")
                lang = ' lang="en" dir="ltr"' if hebrew_share(cells[0]) < 0.5 else ""
                link = f'<a href="{target.id}.xhtml#{target.id}"{lang}>{title}</a>' if target else f"<span{lang}>{title}</span>"
                author_html = f' <span class="author">{author}</span>' if author else ""
                page_html = f' <span class="page">{html.escape(page)}</span>' if page else ""
                items.append(f"<li>{marker}{link}{author_html}{page_html}</li>")
                marker = ""
        if open_part:
            items.append("</ol></li>")
        return "\n".join(head + ['<ol class="contents">'] + items + ["</ol>"]), heading

    def print_units(self, pages: list[int]) -> None:
        """Propose [[unit]] entries from the printed contents. Review them against the PDF."""
        offset = int(self.layout["folio_offset"])
        n, s = 0, 0
        for pno in pages:
            pending_part = False
            for kind, cells in self.contents_rows(pno):
                if kind == "part":
                    pending_part = True
                    continue
                if kind != "entry" or not cells[-1].isdigit():
                    continue
                start = int(cells[-1]) + offset
                if pending_part:
                    s += 1
                    print(f'[[unit]]\nstart = {start - 2}\nid = "s{s:02d}"\nkind = "part"  # {cells[0] if False else ""}')
                    pending_part = False
                n += 1
                print(f'[[unit]]\nstart = {start}\nid = "a{n:02d}"\nkind = "article"  # {cells[0]}')

    def render_unit(self, unit: Unit) -> tuple[str, list[str], str | None]:
        """Return XHTML body content, the IDs per page, and the unit heading text."""
        if unit.kind == "contents":
            body, heading = self.contents_html(unit)
            self.page_ids.update({p: [unit.id] for p in range(unit.start, unit.end + 1)})
            return body, [], heading
        counters = {"p": 0, "fig": 0, "n": 0}
        parts: list[str] = []
        heading: str | None = None
        page_ids: dict[int, list[str]] = {}
        for pno in unit.pages:
            ids = page_ids.setdefault(pno, [])
            parts.append(f'<span epub:type="pagebreak" role="doc-pagebreak" id="pg-{pno}" title="{self.label(pno)}"/>')
            figs = self.figures(pno)
            lines = self.attach_captions(figs, self.lines(pno))
            flow: list[tuple[float, str]] = []
            for para in self.paragraphs(lines):
                role, first = para[0].role, para[0]
                text = self.join(para)
                attrs = "" if first.rtl else ' lang="en" dir="ltr"'
                if role in ("title", "display") and heading is None and unit.kind in ("article", "part"):
                    heading = " ".join(ln.text for ln in para)
                    flow.append((first.y0, f'<h2 id="{unit.id}-h"{attrs}>{text}</h2>'))
                    ids.append(f"{unit.id}-h")
                    continue
                if role == "footnote":
                    counters["n"] += 1
                    nid = f"{unit.id}-n{counters['n']:02d}"
                    flow.append((10_000 + first.y0, f'<aside epub:type="footnote" role="doc-footnote" id="{nid}" class="footnote"{attrs}><p>{text}</p></aside>'))
                    ids.append(nid)
                    continue
                counters["p"] += 1
                pid = f"{unit.id}-p{counters['p']:03d}"
                tag = {"title": "p", "display": "p"}.get(role, "p")
                cls = {"title": "display-title", "display": "display-title", "byline": "byline",
                       "subheading": "subheading", "caption": "small"}.get(role)
                cls_attr = f' class="{cls}"' if cls else ""
                flow.append((first.y0, f'<{tag} id="{pid}"{cls_attr}{attrs}>{text}</{tag}>'))
                ids.append(pid)
            for fig in figs:
                counters["fig"] += 1
                fid = f"fig-{unit.id}-{counters['fig']:02d}"
                page_w = self.doc[0].rect.width
                # "photo": prints edge to edge (bleed). "inline": sits in the text column.
                kind = "photo" if (fig.bbox[2] - fig.bbox[0]) >= 0.9 * page_w else "inline"
                flow.append((fig.bbox[1], f'<figure id="{fid}" class="figure {kind}"><img src="../images/{fig.file}" width="{fig.width}" height="{fig.height}" alt=""/>{self.caption_html(fig)}</figure>'))
                ids.append(fid)
                self.issue(pno, "alt-text", f"{fid}: needs alt text written from the image (not in the PDF)")
            flow.sort(key=lambda t: t[0])
            parts.extend(h for _, h in flow)
        self.page_ids.update(page_ids)
        first_content = next((x for x in parts if not x.startswith("<span epub:type")), "")
        self.opens_with_photo[unit.id] = 'class="figure photo"' in first_content
        return "\n".join(parts), [], heading

    # ---------- output ----------

    def run(self) -> None:
        if self.out.exists():
            shutil.rmtree(self.out)
        (self.out / "META-INF").mkdir(parents=True)
        for sub in ("text", "images", "css", "fonts"):
            (self.out / "OEBPS" / sub).mkdir(parents=True)
        (self.out / "mimetype").write_text("application/epub+zip", encoding="ascii")
        (self.out / "META-INF" / "container.xml").write_text(CONTAINER, encoding="utf-8")
        assets = self.cfg.get("assets", {})
        font_dir = self.content / assets["fonts"] if "fonts" in assets else FONT_DIR
        css = self.content / assets["css"] if "css" in assets else BOOK_CSS
        for f in sorted(font_dir.iterdir()):
            shutil.copyfile(f, self.out / "OEBPS" / "fonts" / f.name)
        shutil.copyfile(css, self.out / "OEBPS" / "css" / "book.css")
        self.page_ids: dict[int, list[str]] = {}
        self.opens_with_photo: dict[str, bool] = {}
        docs: list[tuple[Unit, str, str | None]] = []
        for unit in self.units:
            body, _, heading = self.render_unit(unit)
            epub_type = {"cover": "cover", "titlepage": "titlepage", "contents": "toc", "part": "part",
                         "article": "chapter", "frontispiece": "frontispiece", "blank": "",
                         "bibliography": "bibliography", "backcover": ""}[unit.kind]
            type_attr = f' epub:type="{epub_type}"' if epub_type else ""
            labelled = f' aria-labelledby="{unit.id}-h"' if heading else ""
            xhtml = DOC.format(lang=self.cfg["meta"]["language"], title=html.escape(heading or unit.id),
                               body=f'<section id="{unit.id}" class="{unit.kind}{" chapter" if unit.kind == "article" else ""}{" opens-with-photo" if self.opens_with_photo.get(unit.id) else ""}"{type_attr}{labelled}>\n{body}\n</section>')
            (self.out / "OEBPS" / "text" / f"{unit.id}.xhtml").write_text(xhtml, encoding="utf-8")
            docs.append((unit, f"text/{unit.id}.xhtml", heading))
        self.write_package(docs)
        self.write_inventory()

    def write_package(self, docs: list[tuple[Unit, str, str | None]]) -> None:
        m = self.cfg["meta"]
        images = sorted((self.out / "OEBPS" / "images").iterdir())
        media = {"jpeg": "image/jpeg", "jpg": "image/jpeg", "png": "image/png", "jpx": "image/jp2"}
        manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                    '<item id="css" href="css/book.css" media-type="text/css"/>']
        for f in sorted((self.out / "OEBPS" / "fonts").iterdir()):
            if f.suffix == ".ttf":
                manifest.append(f'<item id="font-{f.stem}" href="fonts/{f.name}" media-type="font/ttf"/>')
        cover_file = next((d for d in images if d.name.startswith("p001-")), None)
        for img in images:
            ext = img.suffix.lstrip(".")
            if ext not in media:
                raise IngestError(f"{img.name}: unsupported image type for EPUB")
            props = ' properties="cover-image"' if img == cover_file else ""
            manifest.append(f'<item id="img-{img.stem}" href="images/{img.name}" media-type="{media[ext]}"{props}/>')
        spine = []
        for unit, href, _ in docs:
            manifest.append(f'<item id="x-{unit.id}" href="{href}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="x-{unit.id}"/>')
        creators = "\n    ".join(f"<dc:creator>{html.escape(c)}</dc:creator>" for c in m["creators"])
        opf = OPF.format(identifier=m["identifier"], title=html.escape(m["title"]), creators=creators,
                         editor=html.escape(m["editor"]), language=m["language"], source=m["source"],
                         rights=html.escape(m["rights"]), description=html.escape(m.get("description", "")),
                         manifest="\n    ".join(manifest), spine="\n    ".join(spine))
        (self.out / "OEBPS" / "package.opf").write_text(opf, encoding="utf-8")
        toc = "\n      ".join(f'<li><a href="{href}#{u.id}">{html.escape(h)}</a></li>' for u, href, h in docs if h)
        pages = "\n      ".join(
            f'<li><a href="{href}#pg-{p}">{self.label(p)}</a></li>'
            for u, href, _ in docs for p in u.pages)
        nav = NAV.format(lang=m["language"], toc=toc, pages=pages)
        (self.out / "OEBPS" / "nav.xhtml").write_text(nav, encoding="utf-8")

    def write_inventory(self) -> None:
        inv = self.content / "inventory"
        inv.mkdir(exist_ok=True)
        unit_of = {p: u for u in self.units for p in range(u.start, u.end + 1)}
        with (inv / "pages.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["page", "printed", "unit", "kind", "target_ids", "status", "notes"])
            for p in sorted(unit_of):
                u = unit_of[p]
                w.writerow([p, self.label(p), u.id, u.kind, " ".join(self.page_ids.get(p, [])), "pending", ""])
        for name, rows in (("assets.csv", self.assets), ("issues.csv", self.issues)):
            with (inv / name).open("w", encoding="utf-8", newline="") as f:
                if rows:
                    w2 = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
                    w2.writeheader()
                    w2.writerows(rows)
        print(f"units {len(self.units)} | pages {len(unit_of)} | images {len(self.assets)} | issues {len(self.issues)}")


CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/package.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""

DOC = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}" dir="rtl">
<head><meta charset="utf-8"/><title>{title}</title><link rel="stylesheet" href="../css/book.css"/></head>
<body>
{body}
</body>
</html>
"""

OPF = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id" xml:lang="{language}" dir="rtl">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">{identifier}</dc:identifier>
    <dc:title>{title}</dc:title>
    {creators}
    <dc:contributor id="editor">{editor}</dc:contributor>
    <meta refines="#editor" property="role" scheme="marc:relators">edt</meta>
    <dc:language>{language}</dc:language>
    <dc:source>{source}</dc:source>
    <dc:rights>{rights}</dc:rights>
    <dc:description>{description}</dc:description>
    <meta property="dcterms:modified">2026-11-23T00:00:00Z</meta>
    <meta property="schema:accessMode">textual</meta>
    <meta property="schema:accessMode">visual</meta>
    <meta property="schema:accessModeSufficient">textual,visual</meta>
    <meta property="schema:accessibilityFeature">printPageNumbers</meta>
    <meta property="schema:accessibilityFeature">pageNavigation</meta>
    <meta property="schema:accessibilityFeature">tableOfContents</meta>
    <meta property="schema:accessibilityFeature">readingOrder</meta>
    <meta property="schema:accessibilityHazard">none</meta>
    <meta property="schema:accessibilitySummary">Reflowable text with print page numbers from the source book.</meta>
    <meta property="pageBreakSource">{source}</meta>
  </metadata>
  <manifest>
    {manifest}
  </manifest>
  <spine page-progression-direction="rtl">
    {spine}
  </spine>
</package>
"""

NAV = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}" dir="rtl">
<head><meta charset="utf-8"/><title>תוכן העניינים</title><link rel="stylesheet" href="css/book.css"/></head>
<body>
  <nav epub:type="toc" id="toc" role="doc-toc">
    <h2 id="toc-h">תוכן העניינים</h2>
    <ol>
      {toc}
    </ol>
  </nav>
  <nav epub:type="page-list" id="page-list" role="doc-pagelist" hidden="hidden">
    <ol>
      {pages}
    </ol>
  </nav>
</body>
</html>
"""


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[2] == "--print-units":
        first, last = (int(x) for x in sys.argv[3].split("-"))
        ing = Ingest(Path(sys.argv[1]).resolve())
        ing.print_units(list(range(first, last + 1)))
    elif len(sys.argv) == 2:
        Ingest(Path(sys.argv[1]).resolve()).run()
    else:
        raise SystemExit(__doc__)
