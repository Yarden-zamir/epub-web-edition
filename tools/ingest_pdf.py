# /// script
# requires-python = ">=3.13"
# dependencies = ["pymupdf==1.28.2"]
# ///
"""Convert a print PDF into an EPUB source tree and a page inventory.

Usage: uv run tools/ingest_pdf.py CONTENT_DIR

CONTENT_DIR holds book.toml. The script writes CONTENT_DIR/epub-src/ and
CONTENT_DIR/inventory/{pages,assets,issues}.csv. All book content stays in CONTENT_DIR.

Rules:
- Text comes only from the PDF text layer. The script never invents text.
- Images are copied byte for byte from the PDF streams (extract_image).
- Every page gets a page marker and an inventory row with status "pending".
  A person sets "verified" after a visual check against the PDF.
- Each automatic text change (punctuation order, hyphen joins) is an issue row.
"""

import csv
import hashlib
import html
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pymupdf

PIPELINE = Path(__file__).resolve().parent.parent
FONT_DIR = PIPELINE / "epub-src" / "OEBPS" / "fonts"
BOOK_CSS = PIPELINE / "epub-src" / "OEBPS" / "css" / "book.css"
PUNCT = set("?!.,:;")

type Role = Literal["body", "display", "title", "byline", "subheading", "small", "caption", "footnote"]
# "small": small print. attach_captions() turns it into "caption" (next to an image) or "footnote" (low on the page).
type UnitKind = Literal["cover", "blank", "titlepage", "contents", "frontispiece", "article", "part", "end"]


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
            units.append(Unit(u["id"], u["kind"], u["start"], end))
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

    def lines(self, pno: int) -> list[Line]:
        page = self.doc[pno - 1]
        height = page.rect.height
        result: list[Line] = []
        for block in page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                y0, y1 = line["bbox"][1], line["bbox"][3]
                if y1 / height < float(self.layout["header_max_y"]):
                    continue  # Running head or folio.
                main = max(spans, key=lambda s: len(s["text"]))
                font, size = main["font"].split("+")[-1], main["size"]
                parts, plain = [], []
                for s in line["spans"]:
                    t = s["text"].replace("\t", " ")
                    plain.append(t)
                    esc = html.escape(t, quote=False)
                    if t.strip().isdigit() and s["size"] < size * 0.8 and font not in ("AlmoniDLAAA",):
                        parts.append(f'<sup class="ref">{esc.strip()}</sup>')
                    elif s["flags"] & 16 and not main["flags"] & 16:
                        parts.append(f"<b>{esc}</b>")
                    else:
                        parts.append(esc)
                text = "".join(plain).strip()
                markup = "".join(parts).strip()
                rtl = hebrew_share(text) >= 0.5
                if rtl and any(v in font for v in self.layout["visual_order_fonts"]) and text[:1] in PUNCT:
                    lead = len(text) - len(text.lstrip("".join(PUNCT)))
                    moved = text[:lead]
                    self.issue(pno, "auto-fix", f"Visual-order punctuation moved to line end ({font}): {moved!r}")
                    text = text[lead:].strip() + moved
                    markup = html.escape(text, quote=False)
                role = role_for(font, size, self.rules)  # "small" resolves to caption or footnote later.
                result.append(Line(pno, y0, y1, line["bbox"][0], line["bbox"][2], role, markup, text, rtl, size))
        result.sort(key=lambda ln: (round(ln.y0), -ln.x1 if ln.rtl else ln.x0))
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

    def render_unit(self, unit: Unit) -> tuple[str, list[str], str | None]:
        """Return XHTML body content, the IDs per page, and the unit heading text."""
        counters = {"p": 0, "fig": 0, "n": 0}
        parts: list[str] = []
        heading: str | None = None
        page_ids: dict[int, list[str]] = {}
        for pno in range(unit.start, unit.end + 1):
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
                kind = "photo"
                flow.append((fig.bbox[1], f'<figure id="{fid}" class="figure {kind}"><img src="../images/{fig.file}" width="{fig.width}" height="{fig.height}" alt=""/>{self.caption_html(fig)}</figure>'))
                ids.append(fid)
                self.issue(pno, "alt-text", f"{fid}: needs alt text written from the image (not in the PDF)")
            flow.sort(key=lambda t: t[0])
            parts.extend(h for _, h in flow)
        self.page_ids.update(page_ids)
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
        for f in FONT_DIR.iterdir():
            shutil.copyfile(f, self.out / "OEBPS" / "fonts" / f.name)
        shutil.copyfile(BOOK_CSS, self.out / "OEBPS" / "css" / "book.css")
        self.page_ids: dict[int, list[str]] = {}
        docs: list[tuple[Unit, str, str | None]] = []
        for unit in self.units:
            body, _, heading = self.render_unit(unit)
            epub_type = {"cover": "cover", "titlepage": "titlepage", "contents": "toc", "part": "part",
                         "article": "chapter", "frontispiece": "frontispiece", "blank": ""}[unit.kind]
            type_attr = f' epub:type="{epub_type}"' if epub_type else ""
            labelled = f' aria-labelledby="{unit.id}-h"' if heading else ""
            xhtml = DOC.format(lang=self.cfg["meta"]["language"], title=html.escape(heading or unit.id),
                               body=f'<section id="{unit.id}" class="{unit.kind}"{type_attr}{labelled}>\n{body}\n</section>')
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
            for u, href, _ in docs for p in range(u.start, u.end + 1))
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
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    Ingest(Path(sys.argv[1]).resolve()).run()
