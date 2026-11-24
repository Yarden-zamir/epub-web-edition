# /// script
# requires-python = ">=3.15"
# dependencies = ["pymupdf==1.28.2", "pillow==13.0.0"]
# ///
"""Render the printed line of each errata entry to errata/print-check/<row>.png.

For each quote of an entry, the script scores every text line of the stated PDF page
by how many quote words it holds, and renders the best line with one line of context above and below.
A row with several quotes stacks its crops in one image, in quote order, with a gray bar between them.
ZOOMS adds <row>-zoom.png close-ups for rows where single characters decide the verdict.
It also writes errata/print-check/locate.json (row, quote, page, line bbox, score, PDF line text)
for a person who checks the crops.
Run from the content repo root: uv run errata/print-check/crop.py
"""
import json
import sys
from pathlib import Path

import pymupdf
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from entries import load_entries  # noqa: E402

PDF = Path(__file__).resolve().parents[2] / "source" / "source.pdf"
OUT = Path("errata/print-check")
DPI = 350
ZOOM_DPI = 700
# Close-ups of the characters that decide a verdict: row -> (PDF page, clip rectangle in points).
ZOOMS = {
    31: (177, (200, 157, 345, 174)),   # "7373": the digits sit edge to edge, no "×"
    33: (145, (140, 599, 420, 614)),   # "101, 2002" in print, "2002,101" in our text
    68: (311, (60, 219, 420, 248)),    # entry 54 "Ehrenberg" starts its own line
}


def norm(word: str) -> str:
    """Keep letters and digits only; quotes, brackets and punctuation differ between print and text."""
    return "".join(ch for ch in word if ch.isalnum())


def page_lines(page: pymupdf.Page) -> list[tuple[pymupdf.Rect, list[str], str]]:
    """Return (bbox, normalized words, raw text) per printed line, top to bottom.

    MuPDF can split one printed right-to-left line into several of its lines,
    so words join a printed line by their vertical center.
    Limit: two text columns at the same height merge into one line. Revisit if a quote sits in a two-column layout.
    """
    words = sorted(page.get_text("words"), key=lambda w: (w[1] + w[3]) / 2)
    groups: list[list] = []
    for w in words:
        yc, h = (w[1] + w[3]) / 2, w[3] - w[1]
        if groups and abs(yc - groups[-1][0]) < 0.4 * h:
            groups[-1][1].append(w)
        else:
            groups.append([yc, [w]])
    out = []
    for _, ws in groups:
        rect = pymupdf.Rect(ws[0][:4])
        for w in ws:
            rect |= pymupdf.Rect(w[:4])
        out.append((rect, [norm(w[4]) for w in ws], " ".join(w[4] for w in ws)))
    return out


def variants(word: str) -> set[str]:
    """Forms of a quote word as the PDF can store it: digits in reverse order, a range in visual order."""
    forms = {norm(word), norm(word)[::-1]}
    if word.count("-") == 1:
        forms.add(norm("-".join(reversed(word.split("-")))))
    return {f for f in forms if f}


def found(forms: set[str], line_words: list[str]) -> bool:
    joined = "".join(line_words)
    return any(f in line_words or (len(f) >= 3 and f in joined) for f in forms)


def locate(doc: pymupdf.Document, page_no: int, quote: str) -> dict:
    """Find the printed line of `quote` on PDF page `page_no` (1-based) or on the next page.

    Each quote word found in a line adds 1 / (number of page lines that hold it), so rare words decide.
    A long quote can wrap: the window grows to the next line when that line holds more quote words.
    """
    quote_words = [variants(w) for w in quote.split() if norm(w)]
    if not quote_words:
        raise SystemExit(f"quote has no words: {quote!r}")
    best = None
    for pno in (page_no, page_no + 1):
        lines = page_lines(doc[pno - 1])
        df = [max(1, sum(found(q, lw) for _, lw, _ in lines)) for q in quote_words]
        for i in range(len(lines)):
            hits = {k for k, q in enumerate(quote_words) if found(q, lines[i][1])}
            end = i
            if i + 1 < len(lines):
                more = {k for k, q in enumerate(quote_words) if found(q, lines[i + 1][1])} - hits
                if len(hits) + len(more) > len(hits) and len(hits) < len(quote_words) and more:
                    hits |= more
                    end = i + 1
            weight = sum(1 / df[k] for k in hits)
            if best is None or weight > best["weight"]:
                rect = lines[i][0] | lines[end][0]
                best = {"page": pno, "weight": weight, "score": len(hits), "rect": rect,
                        "line": " / ".join(lines[j][2] for j in range(i, end + 1)),
                        "above": lines[i - 1][0] if i > 0 else None,
                        "below": lines[end + 1][0] if end + 1 < len(lines) else None}
        if best and best["score"] == len(quote_words):
            break
    if best is None or best["score"] == 0:
        raise SystemExit(f"no line found on page {page_no}: {quote!r}")
    best["words"] = len(quote_words)
    return best


def render(doc: pymupdf.Document, hit: dict) -> Image.Image:
    page = doc[hit["page"] - 1]
    clip = pymupdf.Rect(hit["rect"])
    for ctx in (hit["above"], hit["below"]):
        if ctx is not None:
            clip |= ctx
    clip = pymupdf.Rect(page.rect.x0 + 20, clip.y0 - 4, page.rect.x1 - 20, clip.y1 + 4) & page.rect
    pix = page.get_pixmap(dpi=DPI, clip=clip)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def stack(images: list[Image.Image]) -> Image.Image:
    gap = 24
    w = max(i.width for i in images)
    h = sum(i.height for i in images) + gap * (len(images) - 1)
    out = Image.new("RGB", (w, h), (200, 60, 40))
    y = 0
    for im in images:
        out.paste(im, (0, y))
        y += im.height + gap
    return out


def main() -> int:
    doc = pymupdf.open(PDF)
    report = []
    for e in load_entries():
        images = []
        for quote, page_no in e["locate"]:
            hit = locate(doc, page_no, quote)
            images.append(render(doc, hit))
            report.append({"row": e["row"], "quote": quote, "page": hit["page"], "score": hit["score"],
                           "words": hit["words"], "bbox": [round(v, 1) for v in hit["rect"]], "line": hit["line"]})
        stack(images).convert("L").save(OUT / f"{e['row']}.png", optimize=True)
    for row, (page_no, rect) in ZOOMS.items():
        pix = doc[page_no - 1].get_pixmap(dpi=ZOOM_DPI, clip=pymupdf.Rect(rect), colorspace=pymupdf.csGRAY)
        pix.save(OUT / f"{row}-zoom.png")
    (OUT / "locate.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    weak = [r for r in report if r["score"] < r["words"]]
    for r in weak:
        print(f"row {r['row']} p{r['page']}: {r['score']}/{r['words']} words: {r['quote']!r} -> {r['line']!r}")
    print(f"{len(report)} crops, {len(weak)} partial matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
