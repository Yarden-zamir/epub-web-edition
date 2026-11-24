"""Glossary: the first use of each glossary.json term in a chapter opens its definition in a popover."""

import json
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

from build_web import BookError, Converter, Site, missing_id, text_slots, wrap_text


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


def glossary_data(glossary: list[dict]) -> str:
    """Term definitions for the popover. reader.js reads them by the data-term index."""
    data = [{"term": t["term"], "definition": t["definition"], "source": f"#{t['source']}"} for t in glossary]
    return f'<script type="application/json" id="glossary-data">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script>'


GLOSSARY: list[dict] = []


def load(site: Site) -> None:
    GLOSSARY.extend(load_glossary(site.data_dir, site.conv))


def transform(site: Site, body: ET.Element, top: ET.Element | None, kind: str) -> None:
    if top is not None and kind == "article":
        mark_terms(top, GLOSSARY)


def values(site: Site) -> dict[str, str]:
    return {"glossary": glossary_data(GLOSSARY) if GLOSSARY else ""}
