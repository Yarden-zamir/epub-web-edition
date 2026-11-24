# /// script
# requires-python = ">=3.15"
# dependencies = ["pymupdf==1.28.2", "python-bidi==0.6.12"]
# ///
"""Convert a print PDF into an EPUB source tree and a page inventory.

Usage: uv run tools/ingest_pdf.py CONTENT_DIR
       uv run tools/ingest_pdf.py CONTENT_DIR --release
       uv run tools/ingest_pdf.py CONTENT_DIR --print-units FIRST-LAST   (contents PDF pages)

CONTENT_DIR holds book.toml. The script writes CONTENT_DIR/epub-src/ and
CONTENT_DIR/inventory/{pages,assets,issues}.csv. All book content stays in CONTENT_DIR.

--release builds the public edition into CONTENT_DIR/epub-src-release/ and CONTENT_DIR/inventory-release/.
It applies book.toml [release]: images withheld or replaced until their rights are clear, and edition credits.
The complete edition (without --release) never changes for [release] entries.

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
from bidi import get_display

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
    bracket_font: Literal["", "hebrew", "latin"] = ""  # Hebrew fonts store a bracket's logical code, Latin fonts its shape.


MIRROR = {"(": ")", ")": "("}


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


@dataclass(frozen=True)
class ReleaseChange:
    """book.toml [[release.change]]: an image that the public edition withholds or replaces."""
    image: str  # Image stem as printed in figures.csv, for example "p066-x251".
    action: Literal["withhold", "replace"]
    note: str  # Edition note in the reading text and under the facsimile page.
    reason: str  # For the issue log only.
    file: str = ""  # replace: replacement image, relative to CONTENT_DIR.
    alt: str = ""  # replace: alt text of the replacement image.


@dataclass(frozen=True)
class ReleaseCredit:
    """book.toml [[release.credit]]: an edition credit added after the printed caption."""
    image: str
    text: str
    links: tuple[tuple[str, str], ...]  # (label, https URL) pairs, for example the source record and the licence.


@dataclass
class Figure:
    page: int
    bbox: tuple[float, float, float, float]
    file: str
    width: int
    height: int
    xref: int
    captions: list[Line] = field(default_factory=list)
    change: ReleaseChange | None = None  # Set only in a release build.


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


LTR_JOINERS = set("().,:/%+-@_&'– ")  # Brackets join only when a left-to-right run goes on after them.
CLOSERS = set(".,:;!?)]”")  # No space before these. ASCII quotes are ambiguous in Hebrew (geresh, gershayim), so they stay out.
OPENERS = set("([“")  # No synthetic space after these.


def ltr_strong(c: str) -> bool:
    return c.isascii() and c.isalnum()


def is_hebrew(c: str) -> bool:
    return "\u0590" <= c <= "\u05ff"


NUMBER_SEPARATORS = set(".,:/+-")  # Unicode bidi ES and CS: join two numbers only when alone between them.
NUMBER_SIGNS = set("%$€₪")  # Unicode bidi ET: belong to the number next to them.


def ltr_run_end(ordered: list[Cluster], i: int) -> int:
    """Last index of the left-to-right run that starts at i, in a right-to-left line (Unicode bidi W4–W7, N1)."""
    j = i
    has_letter = ordered[i].text[:1].isascii() and ordered[i].text[:1].isalpha()
    while True:
        k = j + 1
        while k < len(ordered) and not ltr_strong(ordered[k].text[:1]) and not is_hebrew(ordered[k].text[:1]):
            k += 1
        if k >= len(ordered) or not ltr_strong(ordered[k].text[:1]):
            return j
        between = "".join(c.text for c in ordered[j + 1:k])
        # The PDF often has no space glyph: a visible gap between glyphs is a space.
        chain = ordered[j:k + 1]
        if any(max(a.x0 - b.x1, b.x0 - a.x1) > 2.0 for a, b in zip(chain, chain[1:])):
            between += " "
        nxt = ordered[k].text[:1]
        if has_letter:
            ok = True  # After a Latin letter, digits turn left to right and neutrals between two L join (W7, N1).
        elif nxt.isdigit():
            ok = between == "" or (len(between) == 1 and between in NUMBER_SEPARATORS) or set(between) <= NUMBER_SIGNS
        else:
            ok = between == ""  # A Latin letter after a number in Hebrew text starts a new run.
        if not ok:
            return j
        has_letter = has_letter or (nxt.isascii() and nxt.isalpha())
        j = k


def loose_run_end(ordered: list[Cluster], i: int) -> int:
    """Last index of a left-to-right run that joins through spaces, brackets and punctuation."""
    j = i
    while j + 1 < len(ordered):
        k = j + 1
        while k < len(ordered) and ordered[k].text[:1] in LTR_JOINERS and not ltr_strong(ordered[k].text[:1]):
            k += 1
        if k < len(ordered) and ltr_strong(ordered[k].text[:1]):
            j = k
        else:
            break
    return j


def order_key(s: str) -> str:
    """Compare display order: brackets as one symbol, no spaces, no combining marks."""
    return "".join("|" if c in "()[]" else c for c in s if not c.isspace() and not unicodedata.combining(c))


def visual_to_logical(clusters: list[Cluster], rtl: bool, loose: bool = False) -> list[Cluster]:
    """Order clusters by printed position, then restore embedded runs of the other direction.

    The PDF content-stream order is not reliable: MuPDF can return a Hebrew line starting mid-line.
    Printed positions are reliable. In a right-to-left line, left-to-right runs (Latin words, numbers)
    come out reversed and flip back; the run rules follow the Unicode bidi algorithm, so the logical
    text displays like the print (tools/check_bidi.py checks this line by line).
    In a left-to-right line, Hebrew runs flip back.
    Limit: brackets keep the character the PDF stores, which differs between Hebrew and Latin fonts.
    book.toml [[text_fix]] corrects the remaining cases one by one. Revisit with a full bidi inverse.
    """
    ordered = sorted(clusters, key=lambda c: -(c.x0 + c.x1) if rtl else (c.x0 + c.x1))
    out: list[Cluster] = []
    i = 0
    while i < len(ordered):
        ch = ordered[i].text[:1]
        if rtl and ltr_strong(ch):
            j = loose_run_end(ordered, i) if loose else ltr_run_end(ordered, i)
        elif not rtl and is_hebrew(ch):
            j = i
            while j + 1 < len(ordered):
                k = j + 1
                while k < len(ordered) and ordered[k].text[:1] in " '\"\u05be-" and not is_hebrew(ordered[k].text[:1]):
                    k += 1
                if k < len(ordered) and is_hebrew(ordered[k].text[:1]):
                    j = k
                else:
                    break
        else:
            out.append(ordered[i])
            i += 1
            continue
        run = ordered[i:j + 1]
        text = "".join(c.text for c in run)
        # A number sign printed next to the number belongs to it (W5).
        while rtl and out and out[-1].text in NUMBER_SIGNS and run[0].text[:1].isdigit():
            run.insert(0, out.pop())
        # A bracket at either edge belongs to the run when its partner is inside the run.
        if text.count("(") > text.count(")") and out and out[-1].text == ")":
            run.insert(0, out.pop())
        if text.count(")") > text.count("(") and j + 1 < len(ordered) and ordered[j + 1].text == "(":
            run.append(ordered[j + 1])
            j += 1
        out.extend(reversed(run))
        i = j + 1
    return out


def displayed_brackets(text: str, rtl: bool) -> list[tuple[str, str]]:
    """Brackets left to right as displayed: (logical code, shape a reader sees). A bracket keeps its code
    inside a run of the other direction only with letters of that script on both sides (Unicode bidi N0)."""
    shown = get_display(text, base_dir="R" if rtl else "L")
    out = []
    for i, c in enumerate(shown):
        if c not in MIRROR:
            continue
        left = next((x for x in reversed(shown[:i]) if x.isalpha()), "")
        right = next((x for x in shown[i + 1:] if x.isalpha()), "")
        if rtl:
            keeps = left != "" and right != "" and left.isascii() and right.isascii()
        else:
            keeps = not (is_hebrew(left) and is_hebrew(right))
        out.append((c, c if keeps else MIRROR[c]))
    return out


def fix_brackets(text: str, markup: str, clusters: list[Cluster], rtl: bool) -> tuple[str, str]:
    """Choose "(" or ")" for each bracket: a Hebrew-font bracket keeps its stored logical code; a Latin-font
    bracket must display with its stored shape."""
    printed = [c for c in sorted(clusters, key=lambda c: c.x0 + c.x1) if c.bracket_font]
    spots = [i for i, c in enumerate(text) if c in MIRROR]

    def fits(candidate: str) -> bool:
        shown = displayed_brackets(candidate, rtl)
        return len(shown) == len(printed) and all(
            (code if p.bracket_font == "hebrew" else shape) == p.text for (code, shape), p in zip(shown, printed))

    # Disabled: guessing each bracket's display level (N0) without a full bidi engine made results worse
    # (26 bracket defects against 22). Revisit with a bidi library that reports embedding levels.
    return text, markup
    if not spots or len(spots) != len(printed) or len(spots) > 8 or fits(text):
        return text, markup
    for mask in range(1 << len(spots)):
        chars = list(text)
        for b, i in enumerate(spots):
            chars[i] = "(" if mask >> b & 1 else ")"
        candidate = "".join(chars)
        if fits(candidate):
            it = iter(candidate[i] for i in spots)
            return candidate, "".join(next(it) if c in MIRROR else c for c in markup)
    return text, markup


def render_best(clusters: list[Cluster], size: float, rtl: bool) -> tuple[str, str]:
    """Logical text for a printed line. Prefer runs joined through spaces and brackets (a citation stays one
    run for search and screen readers) when that text displays like the print; else the strict Unicode runs."""
    if not rtl:
        return fix_brackets(*render(visual_to_logical(clusters, rtl), size, rtl), clusters, rtl)
    printed = order_key("".join(c.text for c in sorted(clusters, key=lambda c: c.x0 + c.x1)))
    strict = render(visual_to_logical(clusters, rtl), size, rtl)
    loose = render(visual_to_logical(clusters, rtl, loose=True), size, rtl)
    for text, markup in (loose, strict):
        if order_key(get_display(text, base_dir="R")) == printed:
            return fix_brackets(text, markup, clusters, rtl)
    return fix_brackets(*loose, clusters, rtl)


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
            # Distance between the two glyph boxes in either direction (digit runs inside Hebrew read left to right).
            gap = max(prev.x0 - c.x1, c.x0 - prev.x1)
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


def swap_reversed_pairs(markup: str) -> tuple[str, list[str]]:
    """Turn ") X (" into "(X)" when X holds Latin letters or digits and no Hebrew and no markup.

    Mixed-font lines store brackets around an embedded left-to-right run in the wrong order.
    """
    out, fixed, i = [], [], 0
    while i < len(markup):
        if markup[i] == ")":
            j = markup.find("(", i + 1)
            inner = markup[i + 1:j] if j > 0 else ""
            if (j > 0 and j - i < 80 and "<" not in inner and ")" not in inner and not any(is_hebrew(c) for c in inner)
                    and any(c.isascii() and c.isalnum() for c in inner)):
                out.append("(" + inner.strip() + ")")
                fixed.append(markup[i:j + 1])
                i = j + 1
                continue
        out.append(markup[i])
        i += 1
    return "".join(out), fixed


def figs_above(figs: list["Figure"], line: Line) -> bool:
    return any(f.bbox[3] <= line.y0 + 2 for f in figs)


def first_rtl(markup: str) -> bool:
    return 'dir="ltr"' not in markup.split(">", 1)[0]


def merge_fragments(frags: list[Line], max_gap: float | None = 15.0) -> list[Line]:  # 15 pt: a stretched word space; side-by-side captions sit further apart.
    """Join the PDF text fragments of one printed line and order its characters by position.

    MuPDF splits a printed line where the direction changes. Fragments that overlap vertically
    belong to one line, including raised footnote digits.
    """
    frags = sorted(frags, key=lambda f: f.y0)
    groups: list[list[Line]] = []
    for f in frags:
        mid = (f.y0 + f.y1) / 2
        # Raised reference digits join their line. Otherwise only similar sizes join: text at the same
        # height in another column (a caption beside body text) is a separate line.
        is_ref = all(c.style == "sup" or c.text.isspace() for c in f.clusters)
        for g in groups:
            same_height = min(x.y0 for x in g) <= mid <= max(x.y1 for x in g)
            similar = is_ref or any(abs(x.size - f.size) <= 1.2 for x in g)  # Contents: 10 vs 9 pt joins; captions 10.9 vs body 12.5 do not.
            # Fragments of one printed line touch. Side-by-side captions at the same height stay separate.
            gap = max(min(x.x0 for x in g) - f.x1, f.x0 - max(x.x1 for x in g), 0.0)
            # A gap wider than about one character height separates text units (side-by-side captions).
            near = max_gap is None or gap <= min(max_gap, 1.1 * f.size)
            if same_height and similar and near:
                g.append(f)
                break
        else:
            groups.append([f])
    merged: list[Line] = []
    for g in groups:
        main = max(g, key=lambda f: len(f.clusters))
        clusters = [c for f in g for c in f.clusters]
        rtl = hebrew_share("".join(c.text for c in clusters)) >= 0.5
        text, markup = render_best(clusters, main.size, rtl)
        merged.append(Line(main.page, min(f.y0 for f in g), max(f.y1 for f in g), min(f.x0 for f in g),
                           max(f.x1 for f in g), main.role, markup, text, rtl, main.size, clusters))
    merged.sort(key=lambda ln: ln.y0)
    return merged


def with_edition_span(caption: str, cls: str, inner: str) -> str:
    """Add an edition span after the printed caption, or make a caption when print has none."""
    span = f'<span class="{cls}">{inner}</span>'
    return caption.replace("</figcaption>", span + "</figcaption>") if caption else f"<figcaption>{span}</figcaption>"


def credit_html(credit: ReleaseCredit) -> str:
    links = " · ".join(f'<a href="{html.escape(url)}">{html.escape(label)}</a>' for label, url in credit.links)
    return html.escape(credit.text) + (f" {links}" if links else "")


def load_release(cfg: dict) -> tuple[dict[str, ReleaseChange], dict[str, ReleaseCredit]]:
    rel = cfg.get("release", {})
    changes: dict[str, ReleaseChange] = {}
    for c in rel.get("change", []):
        change = ReleaseChange(**c)
        if change.action not in ("withhold", "replace"):
            raise IngestError(f"[[release.change]] {change.image}: unknown action {change.action!r}")
        if (change.action == "replace") != bool(change.file and change.alt):
            raise IngestError(f"[[release.change]] {change.image}: 'replace' needs file and alt; 'withhold' takes neither")
        if change.image in changes:
            raise IngestError(f"[[release.change]] {change.image}: listed twice")
        changes[change.image] = change
    credits: dict[str, ReleaseCredit] = {}
    for c in rel.get("credit", []):
        links = tuple((link["label"], link["url"]) for link in c.get("links", []))
        if not all(url.startswith("https://") for _, url in links):
            raise IngestError(f"[[release.credit]] {c['image']}: links must be https URLs")
        if c["image"] in credits or c["image"] in changes:
            raise IngestError(f"[[release.credit]] {c['image']}: listed twice, or also withheld or replaced")
        credits[c["image"]] = ReleaseCredit(c["image"], c["text"], links)
    return changes, credits


class Ingest:
    def __init__(self, content: Path, release: bool = False) -> None:
        self.content = content
        self.release = release
        self.cfg = tomllib.loads((content / "book.toml").read_text(encoding="utf-8"))
        changes, credits = load_release(self.cfg)
        self.changes = changes if release else {}
        self.credits = credits if release else {}
        self.release_used: set[str] = set()
        # PDF page -> (image box in points, edition note): regions that the facsimile page masks.
        self.facsimile_masks: dict[int, list[tuple[tuple[float, float, float, float], str]]] = {}
        pdf = Path(str(self.cfg["pdf"])).expanduser()
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if digest != self.cfg["pdf_sha256"]:
            raise IngestError(f"{pdf}: sha256 {digest} does not match book.toml")
        self.doc = pymupdf.open(pdf)
        self.layout = self.cfg["layout"]
        self.rules = self.cfg["role"]
        self.char_map: dict[str, str] = self.cfg.get("char_map", {})
        self.text_fixes_used: set[tuple[int, str]] = set()
        for key, url in self.cfg.get("qr_links", {}).items():
            if not url.startswith(("https://", "http://")):
                raise IngestError(f"book.toml [qr_links] {key}: {url[:40]!r} is not a URL (a misplaced entry?)")
        self.out = content / ("epub-src-release" if release else "epub-src")
        self.inventory = content / ("inventory-release" if release else "inventory")
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
        merged = merge_fragments(self.fragments(pno))
        page_rtl = hebrew_share(" ".join(ln.text for ln in merged)) >= 0.5
        for ln in merged:
            # Line direction: without letters, the page direction; on a Hebrew page, any Hebrew letter makes
            # the line right to left (a mostly Latin reference line inside a Hebrew paragraph).
            has_hebrew = any(is_hebrew(c) for c in ln.text)
            wanted = page_rtl if not any(c.isalpha() for c in ln.text) else (
                has_hebrew if page_rtl else hebrew_share(ln.text) >= 0.5)
            if wanted != ln.rtl:
                ln.rtl = wanted
                ln.text, ln.html = render_best(ln.clusters, ln.size, wanted)
        kept = []
        for ln in merged:
            rule = next((o for o in self.cfg.get("omit", []) if o["page"] == pno and o["contains"] in ln.text), None)
            if rule:
                self.issue(pno, "intentional-change", f"Omitted {ln.text[:60]!r}: {rule['reason']}")
                continue
            for tf in self.cfg.get("text_fix", []):
                if tf["page"] == pno and tf["find"] in ln.text:
                    if sorted(c for c in tf["find"] if c.isalnum()) != sorted(c for c in tf["replace"] if c.isalnum()):
                        raise IngestError(f"text_fix on page {pno}: find and replace must hold the same letters")
                    ln.text = ln.text.replace(tf["find"], tf["replace"])
                    ln.html = ln.html.replace(html.escape(tf["find"], quote=False), html.escape(tf["replace"], quote=False))
                    self.text_fixes_used.add((pno, tf["find"]))
                    self.issue(pno, "intentional-change", f"Text fix {tf['find']!r} -> {tf['replace']!r}: {tf['reason']}")
            fix = next((f for f in self.cfg.get("note_ref_fix", []) if f["page"] == pno and f["contains"] in ln.text), None)
            if fix:
                num = str(fix["number"])
                before = html.escape(fix["contains"], quote=False)
                if not before.endswith(num) or ln.html.count(before) != 1:
                    raise IngestError(f"note_ref_fix on page {pno}: {fix['contains']!r} must end with {num} and occur once")
                ln.html = ln.html.replace(before, before[: -len(num)] + f'<sup class="ref">{num}</sup>')
                self.issue(pno, "intentional-change", f"Note reference {num} restored: {fix['reason']}")
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
                    font = s["font"].split("+")[-1]
                    digits = "".join(c["c"] for c in s["chars"]).strip()
                    style: Literal["", "b", "sup"] = ""
                    if digits.isdigit() and len(digits) <= 3 and s["size"] < size * 0.8:  # A 4-digit run is a year.
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
                        if c == "\ufffd":
                            raise IngestError(f"PDF page {pno}: a glyph without a character code (U+FFFD); check the print and add it to [char_map] in book.toml")
                        if unicodedata.combining(c) and clusters:
                            clusters[-1].text += c  # Points stay with their letter.
                            continue
                        kind: Literal["", "hebrew", "latin"] = ""
                        if c in MIRROR:
                            kind = "hebrew" if any(h in font for h in self.layout["hebrew_fonts"]) else "latin"
                        clusters.append(Cluster(ch["bbox"][0], ch["bbox"][2], c, style, kind))
                plain = "".join(c.text for c in clusters)
                role = role_for(font, size, self.rules)  # "small" resolves to caption or footnote later.
                result.append(Line(pno, y0, y1, line["bbox"][0], line["bbox"][2], role, "", plain,
                                   hebrew_share(plain) >= 0.5, size, clusters))
        return result

    def figures(self, pno: int) -> list[Figure]:
        """Figures of a page. Unmodified image streams where possible; derived images where print needs more.

        Derived cases, each recorded in assets.csv:
        - soft mask: the stream with its own transparency mask applied (lossless PNG);
        - overlay: an inline image printed on top of the figure (a label), so the page region is rendered;
        - vector QR code: a dense cluster of tiny vector squares, rendered as an image.
        """
        page = self.doc[pno - 1]
        figs: list[Figure] = []
        placed: set[int] = set()
        infos = page.get_image_info(xrefs=True)
        inline = [pymupdf.Rect(i["bbox"]) for i in infos if not i["xref"]]
        for info in infos:
            xref = info["xref"]
            if not xref or xref in placed:
                continue  # Inline image (handled as overlay below), or a second placement of the same image.
            placed.add(xref)
            bbox = tuple(info["bbox"])
            rect = pymupdf.Rect(bbox)
            if rect.width < 30 or rect.height < 30:
                continue  # Rules, bullets and other ornaments.
            stem = f"p{pno:03d}-x{xref}"
            if stem in self.cfg.get("decorative", []):
                self.issue(pno, "info", f"{stem}: decorative per book.toml; not in the EPUB")
                continue
            if change := self.changes.get(stem):
                figs.append(self.release_figure(pno, bbox, xref, change))
                continue
            if xref in self.seen_xrefs:
                self.issue(pno, "reuse", f"Image xref {xref} repeats; first file {self.seen_xrefs[xref]}")
            image = self.doc.extract_image(xref)
            overlay = any((o & rect).get_area() > 0.8 * o.get_area() and o.get_area() < rect.get_area() for o in inline)
            a, b, c, d = info["transform"][:4]
            # Placed rotated by 90° or mirrored: the stream alone shows sideways or reversed.
            # Limit: small skews (1–2°) keep the raw stream. Revisit if one looks tilted in review.
            turned = abs(b) > abs(a) or (abs(b) < 1e-3 and (a < 0 or d < 0))
            if overlay or turned:
                dpi = max(72, min(300, round(image["width"] / (rect.width / 72))))
                pix = page.get_pixmap(dpi=dpi, clip=rect)
                name, data = f"{stem}-render.jpg", pix.tobytes("jpg", jpg_quality=90)
                why = "an inline image prints on top (label)" if overlay else "placed rotated or mirrored in print"
                derivation = f"page region rendered at {dpi} dpi: {why}; original stream kept in work/originals"
                orig_dir = self.content / "work" / "originals"
                orig_dir.mkdir(parents=True, exist_ok=True)
                (orig_dir / f"{stem}.{image['ext']}").write_bytes(image["image"])
                width, height = pix.width, pix.height
            elif image.get("smask"):
                base = pymupdf.Pixmap(self.doc, xref)
                if base.n - base.alpha >= 4:
                    base = pymupdf.Pixmap(pymupdf.csRGB, base)
                pix = pymupdf.Pixmap(base, pymupdf.Pixmap(self.doc, image["smask"]))
                name, data = f"{stem}-masked.png", pix.tobytes("png")
                derivation = "PDF image stream with its soft mask applied (lossless PNG)"
                width, height = pix.width, pix.height
            else:
                name, data = f"{stem}.{image['ext']}", image["image"]
                derivation = "unmodified PDF image stream"
                width, height = image["width"], image["height"]
            (self.out / "OEBPS" / "images" / name).write_bytes(data)
            self.seen_xrefs.setdefault(xref, name)
            figs.append(Figure(pno, bbox, name, width, height, xref))
            self.asset_row(name, data, pno, str(xref), width, height, derivation)
        figs.extend(self.vector_codes(pno, page))
        return figs

    def vector_codes(self, pno: int, page: "pymupdf.Page") -> list[Figure]:
        """QR codes drawn as vectors: compact square clusters of at least 100 small filled shapes."""
        cells = [d["rect"] for d in page.get_drawings() if d.get("fill") is not None
                 and 0 < d["rect"].width < 6 and 0 < d["rect"].height < 6]
        if len(cells) < 100:
            return []
        clusters: list[pymupdf.Rect] = []  # Union boxes; cells within 4 pt of a box join it.
        counts: list[int] = []
        for c in sorted(cells, key=lambda r: (r.x0, r.y0)):
            for i, box in enumerate(clusters):
                if (box + (-4, -4, 4, 4)).intersects(c):
                    clusters[i] = box | c
                    counts[i] += 1
                    break
            else:
                clusters.append(pymupdf.Rect(c))
                counts.append(1)
        figs = []
        for box, n in zip(clusters, counts):
            if n < 100:
                continue
            if box.width > 150 or abs(box.width - box.height) > 0.2 * box.width:
                self.issue(pno, "vector", f"{n} small vector shapes in {[round(v) for v in box]}; not a QR shape; check by eye")
                continue
            pix = page.get_pixmap(dpi=300, clip=box + (-2, -2, 2, 2))
            name = f"p{pno:03d}-qr{len(figs) + 1}.png"
            data = pix.tobytes("png")
            (self.out / "OEBPS" / "images" / name).write_bytes(data)
            self.asset_row(name, data, pno, "vector", pix.width, pix.height, "vector QR code rendered at 300 dpi")
            figs.append(Figure(pno, tuple(box), name, pix.width, pix.height, 0))
        return figs

    def release_figure(self, pno: int, bbox: tuple[float, float, float, float], xref: int, change: ReleaseChange) -> Figure:
        """A withheld image writes no file. A replaced image writes the replacement file instead of the PDF image."""
        self.release_used.add(change.image)
        self.facsimile_masks.setdefault(pno, []).append((bbox, change.note))
        self.issue(pno, "intentional-change", f"Release: {change.image} {change.action}: {change.reason}")
        if change.action == "withhold":
            return Figure(pno, bbox, "", 0, 0, xref, change=change)
        src = self.content / change.file
        data = src.read_bytes()
        pix = pymupdf.Pixmap(str(src))
        name = f"{change.image}-replacement{src.suffix}"
        (self.out / "OEBPS" / "images" / name).write_bytes(data)
        self.asset_row(name, data, pno, str(xref), pix.width, pix.height, f"release replacement from {change.file}")
        return Figure(pno, bbox, name, pix.width, pix.height, xref, change=change)

    def asset_row(self, name: str, data: bytes, pno: int, xref: str, w: int, h: int, derivation: str) -> None:
        self.assets.append({"file": f"OEBPS/images/{name}", "sha256": hashlib.sha256(data).hexdigest(),
                            "pdf_page": str(pno), "pdf_xref": xref, "pixels": f"{w}x{h}",
                            "derivation": derivation, "status": "pending"})

    # ---------- assembly ----------

    def paragraphs(self, lines: list[Line]) -> list[list[Line]]:
        if not lines:
            return []
        body = [ln for ln in lines if ln.role == "body"] or lines
        left, right = min(ln.x0 for ln in body), max(ln.x1 for ln in body)
        indent, short = float(self.layout["indent_tolerance"]), float(self.layout["short_tolerance"])
        paras: list[list[Line]] = [[lines[0]]]
        for n, (prev, cur) in enumerate(zip(lines, lines[1:])):
            gap = cur.y0 - prev.y1
            if cur.role != prev.role or gap > max(cur.y1 - cur.y0, 6) * 0.9 or gap < -2:
                paras.append([cur])
                continue
            # The column edge near these lines: a figure beside the text narrows the column locally.
            near = [ln for ln in lines[max(0, n - 1):n + 3] if ln.role == cur.role]
            col_left, col_right = min(ln.x0 for ln in near), max(ln.x1 for ln in near)
            if cur.rtl:
                starts = cur.x1 < min(right, col_right) - indent
                prev_short = prev.x0 > max(left, col_left) + short
            else:
                starts = cur.x0 > max(left, col_left) + indent
                prev_short = prev.x1 < min(right, col_right) - short
            if cur.role in ("footnote", "caption", "small"):
                # Notes and sources use hanging indents: only a leading number starts a new entry.
                starts = cur.text.split(" ", 1)[0].rstrip(".").isdigit()
            if starts or (prev_short and cur.role == "body"):
                paras.append([cur])
            else:
                paras[-1].append(cur)
        return paras

    def join(self, para: list[Line]) -> str:
        joined = self.join_lines(para)
        if not para[0].rtl:
            return joined
        fixed_markup, fixed = swap_reversed_pairs(joined)
        for f in fixed:
            self.issue(para[0].page, "auto-fix", f"Bracket pair {f!r} reordered around a left-to-right run; check against print")
        return fixed_markup

    def join_lines(self, para: list[Line]) -> str:
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
            target, best = None, -1.0
            first_word = ln.text.split(" ", 1)[0]
            is_note_start = first_word.isdigit() and len(first_word) <= 3 and ln.y0 / height >= float(self.layout["footnote_min_y"])
            if ln.role == "small" and not is_note_start:
                # First: the next line of a caption already attached (lines arrive top to bottom).
                for f in figs:
                    if any(0 <= ln.y0 - c.y1 < 8 and min(c.x1, ln.x1) - max(c.x0, ln.x0) > 0 for c in f.captions):
                        target, best = f, float("inf")
                        break
            if ln.role == "small" and not is_note_start and target is None:
                for f in figs:
                    overlap = min(f.bbox[2], ln.x1) - max(f.bbox[0], ln.x0) > 0
                    near = -8 <= ln.y0 - f.bbox[3] <= gap or -2 <= f.bbox[1] - ln.y1 <= gap  # Captions may tuck 8 pt into the image bottom.
                    inside = f.bbox[0] - 1 <= ln.x0 and ln.x1 <= f.bbox[2] + 1 and f.bbox[1] - 1 <= ln.y0 and ln.y1 <= f.bbox[3] + 1
                    beside = (f.bbox[1] - 2 <= ln.y0 <= f.bbox[3] + 2
                              and (0 <= f.bbox[0] - ln.x1 <= 20 or 0 <= ln.x0 - f.bbox[2] <= 20))
                    if (overlap and near) or inside or beside:  # Below/above, printed on the image, or beside it.
                        share = max(min(f.bbox[2], ln.x1) - max(f.bbox[0], ln.x0), 0.0)
                        if -8 <= ln.y0 - f.bbox[3] <= gap:
                            share += 10_000  # A caption under an image wins over one above the next image.
                        if target is None or share > best:  # The image the caption overlaps most.
                            target, best = f, share
            if target:
                ln.role = "caption"
                target.captions.append(ln)
            else:
                rest.append(ln)
        # Chain: a small line right under (or over) an attached caption line belongs to the same caption.
        changed = True
        while changed:
            changed = False
            for ln in list(rest):
                if ln.role != "small":
                    continue
                for f in figs:
                    if any((abs(ln.y0 - c.y1) < 8 or abs(c.y0 - ln.y1) < 8) and min(c.x1, ln.x1) - max(c.x0, ln.x0) > 0
                           for c in f.captions):  # Same caption line: right above or below, and overlapping.
                        ln.role = "caption"
                        f.captions.append(ln)
                        f.captions.sort(key=lambda c: c.y0)
                        rest.remove(ln)
                        changed = True
                        break
        for ln in rest:
            if ln.role == "small":
                ln.role = "footnote" if ln.y0 / height >= float(self.layout["footnote_min_y"]) else "caption"
        return rest

    def caption_html(self, fig: Figure) -> str:
        if not fig.captions:
            self.issue(fig.page, "info", f"{fig.file}: no caption next to this image in print")
            return ""
        prefixes = tuple(self.layout["credit_prefixes"])
        spans = []
        for para in self.paragraphs(fig.captions):
            text = self.join(para)
            # A credit can start the line or follow the caption in the same line ("… צילום: name").
            cut = min((i for pre in prefixes for i in [text.find(pre + ":"), text.find(pre + " ")] if i > 0), default=-1)
            if text.startswith(prefixes):
                spans.append(f'<span class="credit">{text}</span>')
            elif cut > 0:
                spans.append(f'<span class="caption">{text[:cut].rstrip()}</span> <span class="credit">{text[cut:]}</span>')
            else:
                spans.append(f'<span class="caption">{text}</span>')
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
        for line in merge_fragments(frags, max_gap=None):  # Contents columns sit far apart.
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

    def continues(self, para: list[Line], body: list[list[Line]]) -> bool:
        """The page's first body paragraph starts without an indent, so it continues the previous page."""
        first = para[0]
        edge_lines = [ln for pa in body for ln in pa[1:]] or [ln for pa in body for ln in pa]
        indent = float(self.layout["indent_tolerance"])
        if first.rtl:
            return first.x1 >= max(ln.x1 for ln in edge_lines) - indent
        return first.x0 <= min(ln.x0 for ln in edge_lines) + indent

    def ends_full(self, para: list[Line], body: list[list[Line]]) -> bool:
        """The paragraph's last line reaches the far column edge, so the sentence may go on."""
        last = para[-1]
        edge_lines = [ln for pa in body for ln in pa[:-1]] or [ln for pa in body for ln in pa]
        short = float(self.layout["short_tolerance"])
        if last.text.rstrip().endswith((".", "?", "!", ":")):
            return False
        if last.rtl:
            return last.x0 <= min(ln.x0 for ln in edge_lines) + short
        return last.x1 >= max(ln.x1 for ln in edge_lines) - short

    def link_notes(self, unit: Unit, parts: list[str], notes: dict[int, dict[str, object]]) -> list[str]:
        """Link reference numbers and notes both ways. IDs use the printed note number: {unit}-fn{n}, {unit}-fnref{n}."""
        referenced: set[int] = set()
        out = []
        for part in parts:
            pieces = part.split('<sup class="ref">')
            rebuilt = pieces[0]
            for piece in pieces[1:]:
                num, _, tail = piece.partition("</sup>")
                n = int(num) if num.isdigit() else None
                if n is not None and n in notes and n not in referenced:
                    referenced.add(n)
                    rebuilt += (f'<a epub:type="noteref" role="doc-noteref" id="{unit.id}-fnref{n}" '
                                f'href="#{unit.id}-fn{n}">{n}</a>' + tail)
                else:
                    self.issue(unit.start, "note", f"{unit.id}: reference {num!r} has no single matching note; kept as superscript")
                    rebuilt += f'<sup class="ref">{num}</sup>' + tail
            out.append(rebuilt)
        # Starred provenance notes: the title (h2 or display title) ends with "*" in print.
        src_ids = [x[6:].split("|", 1)[0] for x in out if x.startswith("@@SRC ")]
        star_linked: str | None = None
        if src_ids:
            sid = src_ids[0]
            for i, part in enumerate(out):
                if (part.startswith("<h2") or 'class="display-title"' in part.split(">", 1)[0]) and "*" in part:
                    tag_end = part.index(">") + 1
                    body = part[tag_end:]
                    out[i] = part[:tag_end] + body.replace(
                        "*", f'<a epub:type="noteref" role="doc-noteref" id="{sid}-ref" href="#{sid}">*</a>', 1)
                    star_linked = sid
                    break
        rendered = []
        for part in out:
            if part.startswith("@@SRC "):
                sid, attrs, text = part[6:-2].split("|", 2)
                if sid == star_linked:
                    body = text[1:] if text.startswith("*") else text
                    rendered.append(f'<aside epub:type="footnote" role="doc-footnote" id="{sid}" class="footnote source-note"{attrs}>'
                                    f'<p><a href="#{sid}-ref" role="doc-backlink">*</a>{body}</p></aside>')
                else:
                    self.issue(unit.start, "note", f"{unit.id}: provenance note {sid} has no asterisk in the title; kept as text")
                    rendered.append(f'<p id="{sid}" class="source-note"{attrs}>{text}</p>')
                continue
            if part.startswith("@@NOTE") and part.endswith("@@"):
                n = int(part[6:-2])
                note = notes[n]
                back = (f'<a href="#{unit.id}-fnref{n}" role="doc-backlink">{n}</a>' if n in referenced else str(n))
                if n not in referenced:
                    self.issue(int(note["page"]), "note", f"{unit.id}: note {n} has no reference in the text")
                body = " ".join(str(x) for x in note["parts"] if x)
                rendered.append(f'<aside epub:type="footnote" role="doc-footnote" id="{unit.id}-fn{n}" class="footnote"{note["attrs"]}><p>{back} {body}</p></aside>')
            else:
                rendered.append(part)
        return rendered

    def render_unit(self, unit: Unit) -> tuple[str, list[str], str | None]:
        """Return XHTML body content, the IDs per page, and the unit heading text."""
        if unit.kind == "contents":
            body, heading = self.contents_html(unit)
            self.page_ids.update({p: [unit.id] for p in range(unit.start, unit.end + 1)})
            return body, [], heading
        counters = {"p": 0, "fig": 0, "n": 0}
        notes: dict[int, dict[str, object]] = {}
        last_note: int | None = None
        prev_note_y = -1e9
        parts: list[str] = []
        heading: str | None = None
        page_ids: dict[int, list[str]] = {}
        open_para: str | None = None  # ID of the previous page's last body paragraph when its last line is full.
        for pno in unit.pages:
            ids = page_ids.setdefault(pno, [])
            parts.append(f'<span epub:type="pagebreak" role="doc-pagebreak" id="pg-{pno}" title="{self.label(pno)}"/>')
            figs = self.figures(pno)
            lines = self.attach_captions(figs, self.lines(pno))
            flow: list[tuple[float, str]] = []
            paras = self.paragraphs(lines)
            body_paras = [pa for pa in paras if pa[0].role == "body"]
            top_body = body_paras[0] if body_paras else None
            next_open: str | None = None
            for para in paras:
                role, first = para[0].role, para[0]
                text = self.join(para)
                if para is top_body and open_para and self.continues(para, body_paras) and not figs_above(figs, first):
                    flow.append((first.y0, f"@@CONT {open_para}|{text}"))
                    if para is body_paras[-1]:
                        next_open = open_para if self.ends_full(para, body_paras) else None
                    continue
                attrs = "" if first.rtl else ' lang="en" dir="ltr"'
                if role in ("title", "display") and heading is None and unit.kind in ("article", "part"):
                    heading = " ".join(ln.text for ln in para)
                    flow.append((first.y0, f'<h2 id="{unit.id}-h"{attrs}>{text}</h2>'))
                    ids.append(f"{unit.id}-h")
                    continue
                if role == "footnote" and unit.kind != "bibliography":
                    plain = " ".join(ln.text for ln in para)
                    head = plain.split(" ", 1)[0]
                    if plain.startswith("*"):
                        counters["src"] = counters.get("src", 0) + 1
                        sid = f"{unit.id}-src{counters['src']}"
                        flow.append((10_000 + first.y0, f'@@SRC {sid}|{attrs} data-pdf-page="{pno}"|{text}@@'))
                        ids.append(sid)
                        continue
                    expected = 1 if last_note is None else last_note + 1
                    if head.rstrip(".").isdigit() and int(head.rstrip(".")) == expected:
                        n = expected
                        if n in notes:
                            raise IngestError(f"unit {unit.id}: note {n} appears twice (PDF page {pno})")
                        rest = text.split(" ", 1)[1] if " " in text else ""
                        notes[n] = {"attrs": f'{attrs} data-pdf-page="{pno}"', "parts": [rest], "page": pno}
                        last_note = n
                        prev_note_y = para[-1].y1
                        flow.append((10_000 + first.y0, f"@@NOTE{n}@@"))
                        ids.append(f"{unit.id}-fn{n}")
                        continue
                    if last_note is not None and (not head.rstrip(".").isdigit() or first.y0 - prev_note_y < 14):
                        notes[last_note]["parts"].append(text)
                        self.issue(pno, "note-join", f"{unit.id}: unnumbered note text joined to note {last_note} (continued from the previous page)")
                        continue
                    self.issue(pno, "note", f"{unit.id}: small print at the page foot without a number; kept as a paragraph")
                    role = "caption"
                counters["p"] += 1
                pid = f"{unit.id}-p{counters['p']:03d}"
                tag = {"title": "p", "display": "p"}.get(role, "p")
                cls = {"title": "display-title", "display": "display-title", "byline": "byline",
                       "subheading": "subheading", "caption": "small"}.get(role)
                cls_attr = f' class="{cls}"' if cls else ""
                flow.append((first.y0, f'<{tag} id="{pid}"{cls_attr}{attrs}>{text}</{tag}>'))
                ids.append(pid)
                if role == "body" and para is body_paras[-1]:
                    next_open = pid if self.ends_full(para, body_paras) else None
            for fig in figs:
                counters["fig"] += 1
                fid = f"fig-{unit.id}-{counters['fig']:02d}"
                page_w = self.doc[0].rect.width
                # "photo": prints edge to edge (bleed). "inline": sits in the text column.
                kind = "photo" if (fig.bbox[2] - fig.bbox[0]) >= 0.9 * page_w else "inline"
                base = f"p{pno:03d}-x{fig.xref}"
                stem = fig.file.rsplit(".", 1)[0] if fig.file and not fig.change else base
                alts = self.cfg.get("alt", {})
                alt = alts.get(stem, alts.get(base))
                self.used_alt.update({stem, base})
                caption = self.caption_html(fig)
                if fig.change:
                    self.used_alt.update(k for k in alts if k.startswith(base + "-"))
                    alt = fig.change.alt or ""
                    caption = with_edition_span(caption, "edition-note", html.escape(fig.change.note))
                elif credit := self.credits.get(base):
                    self.release_used.add(base)
                    caption = with_edition_span(caption, "edition-credit", credit_html(credit))
                img = f'<img src="../images/{fig.file}" width="{fig.width}" height="{fig.height}" alt="{html.escape(alt or "")}"/>'
                if fig.change and fig.change.action == "withhold":
                    img = '<div class="withheld" role="img" aria-label="' + html.escape(fig.change.note) + '"></div>'
                link = self.cfg.get("qr_links", {}).get(stem)
                if link:
                    img = f'<a href="{html.escape(link)}" class="qr-link">{img}</a>'
                    self.issue(pno, "intentional-change", f"{fid}: QR code image links to its decoded target")
                flow.append((fig.bbox[1], f'<figure id="{fid}" class="figure {kind}" data-pdf-page="{pno}">{img}{caption}</figure>'))
                ids.append(fid)
                if alt is None and not fig.change:
                    self.issue(pno, "alt-text", f"{fid} ({stem}): needs alt text written from the image (not in the PDF)")
                self.figure_log.append({
                    "figure_id": fid, "image": stem, "pdf_page": str(pno), "printed_page": self.label(pno), "kind": kind,
                    "bbox": " ".join(f"{v:.0f}" for v in fig.bbox), "pixels": f"{fig.width}x{fig.height}",
                    "caption_lines": str(len(fig.captions)),
                    "caption_boxes": ";".join(f"{c.x0:.0f} {c.y0:.0f} {c.x1:.0f} {c.y1:.0f}" for c in fig.captions),
                    "has_credit": "yes" if 'class="credit"' in caption else "no",
                    "alt": "decorative" if alt == "" else ("yes" if alt else "missing"),
                    "release": fig.change.action if fig.change else ("credit" if base in self.credits else ""),
                    "status": "pending"})
            flow.sort(key=lambda t: t[0])
            for _, h in flow:
                if h.startswith("@@CONT "):
                    pid, text = h[7:].split("|", 1)
                    marker = parts.pop(parts.index(next(x for x in reversed(parts) if x.startswith('<span epub:type="pagebreak"'))))
                    k = max(i for i, x in enumerate(parts) if x.startswith(f'<p id="{pid}"'))
                    sep = "" if parts[k].endswith("-</p>") and not first_rtl(parts[k]) else " "
                    parts[k] = parts[k][:-4] + sep + marker + text + "</p>"
                    ids.append(pid)
                    self.issue(pno, "info", f"{pid}: paragraph continues across the page break (marker kept inside)")
                else:
                    parts.append(h)
            open_para = next_open
        self.page_ids.update(page_ids)
        parts = self.link_notes(unit, parts, notes)
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
        self.figure_log: list[dict[str, str]] = []
        self.used_alt: set[str] = set()
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
        self.write_package(docs, self.write_cover(), self.write_facsimile())
        stale = [(f["page"], f["find"]) for f in self.cfg.get("text_fix", []) if (f["page"], f["find"]) not in self.text_fixes_used]
        if stale:
            raise IngestError(f"book.toml [[text_fix]] entries match no text: {stale}")
        if stale_release := sorted((self.changes.keys() | self.credits.keys()) - self.release_used):
            raise IngestError(f"book.toml [release] entries match no image: {stale_release}")
        unused = sorted(set(self.cfg.get("alt", {})) - self.used_alt)
        if unused:
            raise IngestError(f"book.toml [alt] keys match no image: {unused}")
        self.write_inventory()

    def write_cover(self) -> str | None:
        """Render the printed cover as the EPUB cover-image. Returns its file name under OEBPS/images."""
        cfg = self.cfg.get("cover")
        if not cfg:
            return None
        page = self.doc[int(cfg["render_page"]) - 1]
        dpi = round(int(cfg["height_px"]) / page.rect.height * 72)  # MuPDF takes an integer DPI.
        (self.out / "OEBPS" / "images" / "cover.jpg").write_bytes(page.get_pixmap(dpi=dpi).tobytes("jpg", jpg_quality=88))
        return "cover.jpg"

    def write_facsimile(self) -> list[tuple[str, str]]:
        """One appendix document per PDF page with a page image and a Return link. Returns (id, href) pairs."""
        cfg = self.cfg.get("facsimile")
        if not cfg:
            return []
        lang = self.cfg["meta"]["language"]
        (self.out / "OEBPS" / "facsimile").mkdir()
        unit_of = {p: u for u in self.units for p in range(u.start, u.end + 1)}
        docs = [("facsimile", "text/facsimile.xhtml")]
        intro = (f'<section id="facsimile" class="facsimile-intro" epub:type="appendix" aria-labelledby="facsimile-h">\n'
                 f'<h2 id="facsimile-h">{html.escape(cfg["title"])}</h2>\n'
                 f'<p id="facsimile-note" class="edition-note">{html.escape(cfg["note"])}</p>\n</section>')
        (self.out / "OEBPS" / "text" / "facsimile.xhtml").write_text(
            DOC.format(lang=lang, title=html.escape(cfg["title"]), body=intro), encoding="utf-8")
        for page in self.doc:
            pno = page.number + 1
            pix = page.get_pixmap(dpi=int(cfg["dpi"]))
            scale = int(cfg["dpi"]) / 72
            masks = self.facsimile_masks.get(pno, [])
            for (x0, y0, x1, y1), _ in masks:
                pix.set_rect(pymupdf.IRect(int(x0 * scale), int(y0 * scale), int(x1 * scale) + 1, int(y1 * scale) + 1),
                             (226, 222, 214))
            name = f"fx-{pno:03d}"
            (self.out / "OEBPS" / "facsimile" / f"{name}.jpg").write_bytes(pix.tobytes("jpg", jpg_quality=int(cfg["quality"])))
            label = html.escape(f'{cfg["page_label"]} {self.label(pno)}')
            back = f"{unit_of[pno].id}.xhtml#pg-{pno}"
            body = (f'<section id="{name}" class="facsimile-page" epub:type="appendix" aria-label="{label}">\n'
                    f'<p class="fx-nav"><a href="{back}">{html.escape(cfg["return_label"])}</a> <span class="fx-label">{label}</span></p>\n'
                    f'<figure id="{name}-img" class="facsimile"><img src="../facsimile/{name}.jpg" width="{pix.width}" height="{pix.height}" '
                    f'alt="{label}: תמונת העמוד המודפס"/></figure>\n'
                    + "".join(f'<p class="edition-note fx-mask-note">{html.escape(note)}</p>\n' for _, note in masks)
                    + '</section>')
            page_doc = DOC.format(lang=lang, title=label, body=body).replace("<body>", '<body epub:type="appendix">', 1)
            (self.out / "OEBPS" / "text" / f"{name}.xhtml").write_text(page_doc, encoding="utf-8")
            docs.append((name, f"text/{name}.xhtml"))
        return docs

    def write_package(self, docs: list[tuple[Unit, str, str | None]], cover: str | None,
                      facsimile: list[tuple[str, str]]) -> None:
        m = self.cfg["meta"]
        images = sorted((self.out / "OEBPS" / "images").iterdir())
        media = {"jpeg": "image/jpeg", "jpg": "image/jpeg", "png": "image/png", "jpx": "image/jp2"}
        manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                    '<item id="css" href="css/book.css" media-type="text/css"/>']
        for f in sorted((self.out / "OEBPS" / "fonts").iterdir()):
            if f.suffix == ".ttf":
                manifest.append(f'<item id="font-{f.stem}" href="fonts/{f.name}" media-type="font/ttf"/>')
        cover_file = next((d for d in images if d.name == cover), None) if cover else None
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
        for fid, href in facsimile:
            manifest.append(f'<item id="x-{fid}" href="{href}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="x-{fid}"/>')
            if fid != "facsimile":
                manifest.append(f'<item id="img-{fid}" href="facsimile/{fid}.jpg" media-type="image/jpeg"/>')
        creators = "\n    ".join(f"<dc:creator>{html.escape(c)}</dc:creator>" for c in m["creators"])
        opf = OPF.format(identifier=m["identifier"], title=html.escape(m["title"]), creators=creators,
                         editor=html.escape(m["editor"]), language=m["language"], source=m["source"],
                         rights=html.escape(m["rights"]), description=html.escape(m.get("description", "")),
                         manifest="\n    ".join(manifest), spine="\n    ".join(spine))
        (self.out / "OEBPS" / "package.opf").write_text(opf, encoding="utf-8")
        toc = "\n      ".join(f'<li><a href="{href}#{u.id}">{html.escape(h)}</a></li>' for u, href, h in docs if h)
        if facsimile:
            toc += f'\n      <li><a href="text/facsimile.xhtml#facsimile">{html.escape(self.cfg["facsimile"]["title"])}</a></li>'
        pages = "\n      ".join(
            f'<li><a href="{href}#pg-{p}">{self.label(p)}</a></li>'
            for u, href, _ in docs for p in u.pages)
        nav = NAV.format(lang=m["language"], toc=toc, pages=pages)
        (self.out / "OEBPS" / "nav.xhtml").write_text(nav, encoding="utf-8")

    def write_inventory(self) -> None:
        inv = self.inventory
        inv.mkdir(exist_ok=True)
        unit_of = {p: u for u in self.units for p in range(u.start, u.end + 1)}
        with (inv / "pages.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["page", "printed", "unit", "kind", "target_ids", "status", "notes"])
            for p in sorted(unit_of):
                u = unit_of[p]
                w.writerow([p, self.label(p), u.id, u.kind, " ".join(self.page_ids.get(p, [])), "pending", ""])
        for name, rows in (("assets.csv", self.assets), ("issues.csv", self.issues), ("figures.csv", self.figure_log)):
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
    elif len(sys.argv) == 3 and sys.argv[2] == "--release":
        Ingest(Path(sys.argv[1]).resolve(), release=True).run()
    else:
        raise SystemExit(__doc__)
