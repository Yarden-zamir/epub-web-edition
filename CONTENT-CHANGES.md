# Content changes and additions

Log of every change to the book's content, and of every addition that the editions show next to it.
Add an entry in the same change that makes it. Newest first within each section.

- Print source: ~/private-inputs/eli-raz/source-2026-11-23/source.pdf (sha256 c7efc94e…), never modified.
- Complete edition: `ingest_pdf.py CONTENT` → dist/eli-raz.epub. Every printed image and the printed text.
- Release edition (public site and download): `ingest_pdf.py CONTENT --release` → dist/release/.
- Machine log of automatic text handling: inventory/issues.csv and inventory-release/issues.csv.

## 1. Text changes (both editions, from book.toml)

| Where | Change | Why |
|---|---|---|
| PDF pages 25, 181, 287 | Three tables printed as text (Dead Sea salinity by year twice, copper and slag by period) set as XHTML tables (a06-t1, a18-t1, a35-t1) | Print shows tables; the text layer gave one cell per paragraph. book.toml [[text_table]]; the rows must hold exactly the printed characters. |
| PDF page 78 | QR captions and film credits separated: "הסרט שצולם בידי צוות המחפשים, חלק 1" (fig-a10-13), "…הנספים לפני האסון" (fig-a10-14), credits as two paragraphs (a10-p051, a10-p052) | The PDF stores two stacked caption lines of neighbouring columns as one text line, so letters interleaved. |
| Whole book | 38 wrong paragraph splits joined (37 in text, 1 in the PDF page 78 credits): paragraphs that print splits at a photo edge, a hanging list label, a citation line or a tall glyph are one paragraph again; list items and paragraphs that print separates by 3-4 pt of space are separate | Ingest paragraph rules. Old IDs of joined paragraphs and where they went: id-moves.csv; IDs stay stable through ids.csv. |
| PDF pages 34, 127, 279, 280, 283, 284, 286, 291, 294, 303 | 14 bracket and run-order fixes in mixed Hebrew and Latin lines, for example "(Siwa, …", "(Bourcart, 1899)", "(RB)." | book.toml [[text_fix]]; each checked against a render of the printed line and the EPUB line in Chromium. Brackets that print leaves open are kept: book.toml [[print_quirk]] (6). |
| PDF page 22 | Omitted "The English text continues from the left page" | Print-only reading note for two-page spreads; the EPUB puts the English pages in reading order. |
| PDF page 23 | Note reference 3 restored as a superscript link | Print sets it as a full-size digit. |
| PDF pages 21-37 | English article pages in reading order 21, 23, 22, 25, 24, … | Print lays out two-page spreads. |
| PDF page 70 (a10-p021) | Patach restored in "הקַשָרים": the PDF draws it as one FrankRuhlMFBold glyph without a character code (U+FFFD), which showed as "�" | book.toml [char_map]; checked against a 300 dpi render of the line. The converter now stops on any unmapped U+FFFD. |
| Whole book | U+0007 → space; U+001A → shva (U+05B0) | Wrong code points in the PDF text layer (book.toml [char_map]). |

## 2. Image changes (release edition only, book.toml [release])

| Where | Change | Why |
|---|---|---|
| PDF page 66 (p066-x251) | Replaced by a map drawn from Natural Earth data (scripts/pamir_map.py), with an edition note | Printed map looks like an unattributed Google Maps screenshot. |
| PDF page 183 (p183-x717) | Withheld, labelled placeholder, masked on the facsimile page | No source found. |
| PDF page 301 (p301-x1169) | Withheld, as above | Publication figure on a satellite base map; not cleared. |
| PDF page 302 (p302-x1173) | Withheld, as above | Google Earth view without the imagery providers. |
| PDF pages 34, 35, 49, 183, 183, 270, 275 | Edition credit with source record and licence added after the printed caption | Licence terms ask for attribution and a licence link. |

## 3. Additions (EPUB)

| What | Where |
|---|---|
| Facsimile appendix: one 64 dpi image of every printed page, with a Return link | End of the book |
| Alt text for all 217 images | book.toml [alt]; written from the images, not printed |
| QR codes link to their decoded targets | book.toml [qr_links] |

## 4. Additions (web edition only, site/enhancements.json)

| Date | What | Source |
|---|---|---|
| 2026-11-24 | site/crosslinks.json: 17 links where the text names another chapter of the book, each from the printed phrase to that chapter's heading | Book text; checked by content-data/scripts/check_content_data.py |
| 2026-11-24 | site/glossary.json: 51 geological and local terms that the book explains, each with a near-quote definition and the exact source text | Book text at each term's source element |
| 2026-11-24 | site/timeline.json: 62 dated events (12 major) from Eli Raz's life and the book, each with the exact sentence and its paragraph | Book text; only dates that the text gives (notes in content-data/places.md) |
| 2026-11-24 | site/places.json: 29 places (the 7 earlier places in the new format plus 22 more), each with chapter targets, a description from the book and photos named in captions | Coordinates from Wikidata P625 (raw responses in content-data/wikidata-raw); descriptions from the book text at description_source |
| 2026-11-24 | Chart data for PDF page 113: cumulative number of sinkholes 1980–2016, its own chart (site/charts/fig-a14-08.json) | Digitized from the printed chart (scripts/digitize_charts.py); no published yearly table found |
| 2026-11-24 | Chart data for PDF page 262: Lake Lisan level curve, marked points, Heinrich bands 1–5 (site/charts/fig-a34-05.json) | Digitized from the printed chart (ברטוב 2005) |
| 2026-11-24 | Chart data for PDF page 304: level change by added water, RB and SW edges only (site/charts/fig-a36-11.json) | Digitized from the printed schematic (GSI & Tahal Reports, 2011); markers 400/700/900 from the book text a36-p060, a36-p061 |
| 2026-11-24 | Chart data for PDF page 305: Dead Sea density by depth, points and curve (site/charts/fig-a36-12.json) | Digitized from the printed chart (after Neev and Emery, 1967) |
| 2026-11-24 | English translation, pilot: "Eli Raz, Man of the Desert and the Dead Sea" by Amir Eidelman (site/translations/en/a03.json, 10 elements) and "The Pamir Disaster" by Eli Raz (site/translations/en/a10.json, 69 elements), alt text included. Machine translation (Claude), not reviewed. In a10 the garbled QR captions fig-a10-13 and fig-a10-14 are translated as their decoded targets and alt text say | Book text; choices in work/translations/en-style.md |
| 2026-11-24 | Hebrew translation of the English elements: the chapter "The Life Story of the Dead Sea" (site/translations/he/a06.json, 50 elements: text, translated footnotes, English chart caption and alt text) and the English line a36-p050 (site/translations/he/a36.json). Machine translation (Claude), not reviewed. Citations of English publications stay as printed | Book text; Eli's Hebrew terms from his own chapters, in work/translations/eli-terms.md |
| 2026-11-24 | Places map with 7 places, each linked to its chapter | Coordinates from Wikidata (IDs in enhancements.json) |
| 2026-11-24 | Players for the 5 YouTube videos behind printed QR codes | The printed QR links |
| 2026-11-24 | Tables on PDF pages 281, 282, 285 as sortable tables; printed image kept under each | Transcribed from the printed images |
| 2026-11-24 | Live Dead Sea level chart after the chart on PDF page 113 | Water Authority, data.gov.il (scripts/dead_sea_level.py) |
| 2026-11-24 | Footer link to the National Library record of Eli's filmed interview | NLI catalogue |
