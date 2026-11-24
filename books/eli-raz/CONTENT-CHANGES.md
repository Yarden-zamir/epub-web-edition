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
| Whole book (about 260 places); PDF pages 145, 305, 311 | No space after a hyphen or dash glued to a prefix and a number ("ה-14", "ב-1993", "כ-25,000", "36%-45%"), as printed. a17-src1 "פורסם בקתדרה 101, 2002." (was "2002,101."); "1978/9" (was "9 /1978"); sources entry 54 (Ehrenberg) on its own line, new ID sources-p097 | Conversion faults, found by the print check (errata/print-check.md rows 33, 68 and the hyphen note); checked against crops and renders. No paragraph ID moved |
| PDF pages 50, 207, 213-214, 244, 290, 308 | Six verse pieces set as poems (section.poem, title and author line, stanzas, one line per printed line, staircase indents as printed on page 308): Galit Hazan-Rokach "כְּמוֹ אֵשֶׁת לוֹט" (a07), the song quoted in a24, Moshe Mazar's maqama (a26), Elisheva Rosenbaum "גזעי התמרים" (a30), "דרך חלון האוטובוס" (a35), "קו 486 - בדרך היורדת אל הבית" (a36). Each line keeps the ID of the paragraph it started | Print sets verse in lines and stanzas; the text layer gave paragraphs that merged lines. book.toml [[poem]]. The author line prints "חזן-רוקם" (a01-p011: "חזן-רוקח"); kept as printed |
| Whole book (1,125 points on 75 PDF pages: poems in a07, a30 and a35; Bible quotes in a15, a17, a19, a25; words such as הקַשָרים in a10) | Each point is on the letter it prints on, for example "גִּזְעֵי הַתְּמָרִים", "כְּמוֹ", "לֹא" (was "ּגִזְעֵי הַּתְמִָרים"). Points follow standard typing order: shin and sin dot, dagesh, vowel. A point that a letter glyph already carries is not doubled | The PDF places zero-width point glyphs at a neighbour's edge. Ingest now places each point by its outline in the embedded font. Checked: every pointed line (151) against a 300 dpi render; tools/check_marks.py |
| PDF pages 25, 181, 287 | Three tables printed as text (Dead Sea salinity by year twice, copper and slag by period) set as XHTML tables (a06-t1, a18-t1, a35-t1) | Print shows tables; the text layer gave one cell per paragraph. book.toml [[text_table]]; the rows must hold exactly the printed characters. |
| PDF page 78 | QR captions and film credits separated: "הסרט שצולם בידי צוות המחפשים, חלק 1" (fig-a10-13), "…הנספים לפני האסון" (fig-a10-14), credits as two paragraphs (a10-p051, a10-p052) | The PDF stores two stacked caption lines of neighbouring columns as one text line, so letters interleaved. |
| Whole book | 38 wrong paragraph splits joined (37 in text, 1 in the PDF page 78 credits): paragraphs that print splits at a photo edge, a hanging list label, a citation line or a tall glyph are one paragraph again; list items and paragraphs that print separates by 3-4 pt of space are separate | Ingest paragraph rules. Old IDs of joined paragraphs and where they went: id-moves.csv; IDs stay stable through ids.csv. |
| PDF pages 34, 127, 279, 280, 283, 284, 286, 291, 294, 303 | 14 bracket and run-order fixes in mixed Hebrew and Latin lines, for example "(Siwa, …", "(Bourcart, 1899)", "(RB)." | book.toml [[text_fix]]; each checked against a render of the printed line and the EPUB line in Chromium. Brackets that print leaves open are kept: book.toml [[print_quirk]] (6). |
| PDF page 22 | Omitted "The English text continues from the left page" | Print-only reading note for two-page spreads; the EPUB puts the English pages in reading order. |
| PDF page 23 | Note reference 3 restored as a superscript link | Print sets it as a full-size digit. |
| PDF pages 21-37 | English article pages in reading order 21, 23, 22, 25, 24, … | Print lays out two-page spreads. |
| PDF page 70 (a10-p021) | Patach restored in "הקַשָרים": the PDF draws it as one FrankRuhlMFBold glyph without a character code (U+FFFD), which showed as "�" | book.toml [char_map]; checked against a 300 dpi render of the line. The converter now stops on any unmapped U+FFFD. |
| Whole book | U+0007 → space; U+001A → shva (U+05B0) | Wrong code points in the PDF text layer (book.toml [char_map]). |

## 1a. Corrections of errors in the print (both editions, book.toml [[correction]])

Approved by Yarden on 2026-11-24. Research and verification: errata/ERRATA.md (errata agent, commit ab1c111).
The reader sees the corrected text with a dagger (†) that opens an edition note with the printed form; the web edition can show the printed form (data-printed).

| Where | Printed → corrected | Why and evidence |
|---|---|---|
| PDF page 29 (a06-p022) | "(2:23, KJV)" → "(2:13, KJV)" | The salt-of-the-covenant verse is Leviticus 2:13. Leviticus 2 has 16 verses. Evidence: https://bible-api.com/leviticus+2:13?translation=kjv |
| PDF page 29 (a06-p022) | "shalt though season" → "shalt thou season" | Misquote of the KJV: 'shalt thou season with salt'. Evidence: https://bible-api.com/leviticus+2:13?translation=kjv |
| PDF page 26 (a06-p021) | "salts form any other source" → "salts from any other source" | Typo: 'form' for 'from'. Evidence: Reading of the sentence; no outside source needed. |
| PDF page 29 (a06-p023) | "south of Hebron" → "south of Bethlehem" | Tekoa lies about 8 km south of Bethlehem, between Bethlehem and Hebron, not south of Hebron. Evidence: https://en.wikipedia.org/wiki/Tekoa_(ancient_town) |
| PDF page 33 (a06-p030) | "For 3,300 years" → "For 2,300 years" | Aristotle lived 384-322 BC; from his time to the 1930s is about 2,260 years. The book itself dates him to the 4th century BC (a35-p016). Evidence: https://en.wikipedia.org/wiki/Aristotle |
| PDF page 29 (a06-fn15) | "n. 173." → "n. 174." | In Röhricht's Regesta (1893), pp. 43-44, the 1138 charter of Fulk on Tekoa, bitumen and salt is no. 174. No. 173 is a Templar charter on churches. Evidence: https://archive.org/download/regestaregnihie00rhgoog/regestaregnihie00rhgoog_djvu.txt |
| PDF page 245 (a31-p002) | "מבול בשלושה במאי" → "מבול בשני במאי" | The Arugot flood was on 2 May 2001. The same article says 2 May twice (a31-p006, a31-p007). Israel Meteorological Service: storm in the night of 1-2 May 2001, the Arugot bridge collapsed. Evidence: https://ims.gov.il/sites/default/files/inline-files/%D7%A1%D7%A7%D7%99%D7%A8%D7%AA%20%D7%90%D7%99%D7%A8%D7%95%D7%A2%D7%99%D7%9D%20%D7%A7%D7%99%D7%A6%D7%95%D7%A0%D7%99%D7%99%D7%9D%20-%20%D7%A2%D7%93%D7%9B%D7%95%D7%95%D7%9F%20%D7%9E%D7%A8%D7%A5%202023_0.pdf |
| PDF page 247 (a31-p007) | "של ה-3 במאי" → "של ה-2 במאי" | Same event as 'ביום השיטפון ב-2 במאי' earlier in this paragraph. IMS dates the storm and the Arugot bridge collapse to 1-2 May 2001. Evidence: https://ims.gov.il/sites/default/files/inline-files/%D7%A1%D7%A7%D7%99%D7%A8%D7%AA%20%D7%90%D7%99%D7%A8%D7%95%D7%A2%D7%99%D7%9D%20%D7%A7%D7%99%D7%A6%D7%95%D7%A0%D7%99%D7%99%D7%9D%20-%20%D7%A2%D7%93%D7%9B%D7%95%D7%95%D7%9F%20%D7%9E%D7%A8%D7%A5%202023_0.pdf |
| PDF page 247 (a31-p007) | "דברים יד, 14-13" → "דברים יא, 14-13" | The quoted verses ('והיה אם שמע תשמעו ... ונתתי מטר ארצכם בעתו יורה ומלקוש') are Deuteronomy 11:13-14. Deuteronomy 14:13-14 is about unclean birds. Evidence: https://www.sefaria.org/api/v3/texts/Deuteronomy.11.13-14 |
| PDF page 66 (a10-p003) | "'מועדון האלפיני הישראל'" → "'מועדון האלפיני הישראלי'" | Missing final yod in the club name. a10-p002 prints 'המועדון האלפיני הישראלי'. Checked in the PDF render: the slip is in the print. Evidence: https://wiki.imga.org.il/index.php?title=%D7%94%D7%9E%D7%95%D7%A2%D7%93%D7%95%D7%9F_%D7%94%D7%90%D7%9C%D7%A4%D7%99%D7%A0%D7%99 |
| PDF page 61 (a09-p023) | "בן אוויס" → "בן נוויס" | Ben Nevis, 1,345 m, highest peak of the British Isles, in Scotland. The text gives the same height and place; one letter is missing in the name. Evidence: https://en.wikipedia.org/wiki/Ben_Nevis |
| PDF page 103 (a13-p058) | "שבאינדוזיה" → "שבאינדונזיה" | Typo: Komodo island is in Indonesia (אינדונזיה). Evidence: https://en.wikipedia.org/wiki/Komodo_(island) |
| PDF page 185 (a19-p009) | "במאה ה- 14" → "במאה ה- 15" | Arnold von Harff travelled to the Holy Land in 1496-1499 (still the Mamluk period, so the bracket stays true). Evidence: https://en.wikipedia.org/wiki/Arnold_von_Harff |
| PDF page 146 (a17-p009) | "אברהם מוסיל" → "אלואיס מוסיל" | The Czech explorer of Edom at the start of the 20th century is Alois Musil (1868-1944). Evidence: https://en.wikipedia.org/wiki/Alois_Musil |
| PDF page 181 (a18-p063) | "בחפירות רבת א-נחאס" → "בחפירות ח'רבת א-נחאס" | Two letters dropped: the site is ח'רבת א-נחאס (Khirbat en-Nahas) in all 8 other places in the book. Checked in the PDF render: the slip is in the print. Evidence: https://en.wikipedia.org/wiki/Khirbat_en-Nahas |
| PDF page 286 (a35-p058) | "(Bodaker et al., 2000)" → "(Bodaker et al., 2010)" | The book cites this paper as 2010 in a35-p005 and in the bibliography (sources-p053, The ISME Journal 4: 399-407). No Bodaker 2000 paper exists. Evidence: https://doi.org/10.1038/ismej.2009.141 |
| PDF page 311 (sources-p069) | "pp. 31–41" → "pp. 33–41" | Oren 1983, Limnology and Oceanography 28(1): pages 33-41 (Crossref). Evidence: https://api.crossref.org/works/10.4319/lo.1983.28.1.0033 |
| PDF page 309 (sources-p024) | "תרח"ץ" → "תרצ"ח" | Letters swapped in the Hebrew year. The entry is dated 1938, which is תרצ"ח (5698). Evidence: https://www.hebcal.com/converter?cfg=json&gy=1938&gm=6&gd=1&g2h=1 |
| PDF page 310 (sources-p047) | "Geological Society of America Bulletin, v.116,pp. 555–571" → "Geological Survey of Israel Bulletin 63" | Begin, Ehrlich and Nathan 1974 is Geological Survey of Israel Bulletin 63. GSA Bulletin 116: 555-571 is a different paper (Bookman/Ken-Tor et al. 2004, doi:10.1130/B25286.1). Evidence: https://www.cambridge.org/core/books/abs/quaternary-of-the-levant/lake-lisan/CF25D6DE02054F2F38A24D91617CBC85 |
| PDF page 303 (a36-p053) | "לכמיליון עד סוף העשור" → "לכמיליארד עד סוף העשור" | From about 600 million m³ a year to 'about a million' is impossible. Government Decision 3533 (June 2018) sets the 2030 desalination target at 1,100 million m³ a year. Evidence: https://www.ceci.org.il/wp-content/uploads/2023/10/%D7%AA%D7%9B%D7%A0%D7%99%D7%AA-%D7%90%D7%A1%D7%98%D7%A8%D7%98%D7%92%D7%99%D7%AA-%D7%9C%D7%94%D7%AA%D7%9E%D7%95%D7%93%D7%93%D7%95%D7%AA-%D7%A2%D7%9D-%D7%AA%D7%A7%D7%95%D7%A4%D7%AA-%D7%91%D7%A6%D7%95%D7%A8%D7%AA-%D7%91%D7%9E%D7%A9%D7%A7-%D7%94%D7%9E%D7%99%D7%9D-%D7%9C%D7%A9%D7%A0%D7%99%D7%9D-2018-2030.pdf |
| PDF page 288 (a35-p070) | "(Coyn & Bellier" → "(Coyne & Bellier" | The French engineering firm that wrote the Red Sea - Dead Sea feasibility study is Coyne et Bellier. Evidence: https://www.eib.org/attachments/registers/82425040.pdf |
| PDF page 311 (sources-p060) | "Coyn and Bellier" → "Coyne and Bellier" | The firm name is Coyne et Bellier (same entry as a35-p070). Evidence: https://www.eib.org/attachments/registers/82425040.pdf |

## 2. Image changes (release edition only, book.toml [release])

| Where | Change | Why |
|---|---|---|
| PDF page 66 (p066-x251) | Replaced by a new relief map (scripts/pamir_map.py), with an edition note: Dushanbe to Lenin Peak with the flight and helicopter legs that a10 tells, and a detail of the base camp, the first camp, the Frying Pan and the peak. Places from OSM, borders from Natural Earth, relief from Copernicus DEM. Alt text and note in book.toml (JPEG, 474 KB) | Printed map looks like an unattributed Google Maps screenshot. |
| PDF page 183 (p183-x717) | Withheld, labelled placeholder, masked on the facsimile page | No source found. |
| PDF page 301 (p301-x1169) | Replaced (was withheld) by a new schematic map of the eastern RD conveyance drawn from the book text (replacements/p301-x1169-open-map.jpg, scripts/jordan_maps.py), with an edition note that it is not the figure of Bein et al. (2020). Facsimile page stays masked | Publication figure on a satellite base map; not cleared. |
| PDF page 302 (p302-x1173) | Replaced (was withheld) by a new perspective relief view looking north-east with the Desert Highway and the King's Highway from OSM (replacements/p302-x1173-open-view.jpg, scripts/jordan_maps.py), with an edition note on its sources. Facsimile page stays masked | Google Earth view without the imagery providers; Google requires the providers next to the image. |
| PDF pages 34, 35, 49, 183, 183, 270, 275 | Edition credit with source record and licence added after the printed caption | Licence terms ask for attribution and a licence link. |

## 3. Additions (EPUB)

| What | Where |
|---|---|
| Cover page: the render of the printed cover opens the book; hidden landmarks nav (cover, printed contents, start of text) for Kindle | Start of the book, nav.xhtml |
| Tables of PDF pages 281, 282, 285 as text tables after their printed images, with an edition caption (from site/enhancements.json "tables", transcribed from print) | a35, after fig-a35-02, fig-a35-03, fig-a35-04 |
| 17 cross-references: the printed words that name another chapter link to that chapter (site/crosslinks.json) | a09, a10, a14, a22, a27, a29, a34, a35, a36 |
| Glossary appendix: 51 terms the book explains, short wording after the book, each linked to its place in the book (site/glossary.json). No links on words in the text: the text stays as printed, and Kindle has its own dictionary | Before the facsimile appendix |
| Timeline appendix: 62 dates from the book, each linked to its sentence (site/timeline.json) | Before the facsimile appendix |
| Facsimile appendix: one 56 dpi image (JPEG quality 55) of every printed page, with a Return link. Lowered from 64 dpi on 2026-11-24 to keep the release EPUB at most 24 MB | End of the book |
| Alt text for all 217 images | book.toml [alt]; written from the images, not printed |
| QR codes link to their decoded targets | book.toml [qr_links] |

## 4. Additions (web edition only, site/enhancements.json)

| Date | What | Source |
|---|---|---|
| 2026-11-24 | site/places.json: new descriptions for all 29 places. 25 are exact quotes of one or two sentences from the book (description_kind "book"; a quote cut before its sentence ends ends in "…"), chosen to say what and where the place is and why the book cares. 4 places that the book names but never describes (Masada, Nahal Darga, Nahal Ze'elim, Arnon) have a one-line description written for this edition (description_kind "edition", with description_url). The checker now fails on any book description that is not an exact quote | Book text at description_source; Hebrew Wikipedia for the 4 edition lines (content-data/scripts/build_places.py) |
| 2026-11-24 | site/then-now.json: three dated layers for the then-and-now view of the Dead Sea, each a north-up Web Mercator image (site/media/then-now/): Lynch's own 1848 survey map (affine fit on 6 land landmarks, residuals 0.25-2.12 km; Safieh check point 6.6 km off); Survey of Palestine sheet 13, revised June 1945 (fitted by its Palestine Grid, 441 crossings, median 17 m; grid checked against the printed corner table and 4 landmarks); Copernicus Sentinel-2 of 2026-11-20. The 1938 level printed on the 1945 sheet (−392 m) added as levels.middle. The Spencer sheet stays as the fallback (scripts/then_now.py) | NLI Eran Laor scans via Commons (FL25570575, FL60505868; public domain per Commons); Copernicus Sentinel-2 L2A ("Contains modified Copernicus Sentinel data 2026"); landmark coordinates from Wikidata |
| 2026-11-24 | site/figure-maps/: interactive map specs for the three new maps (fig-a10-02 Pamir, fig-a36-09 RD conveyance, fig-a36-10 Jordanian plateau), each marker and line with its source and the book paragraph it belongs to | OSM element IDs and Wikidata IDs in each marker; schematic lines from the book text; Disi pipeline along the Desert Highway from the 2008 environmental assessment (Consolidated Consultants) |
| 2026-11-24 | Cover photograph (Moshe Berenstein, flood plume at Nahal Kedem) in its wider original frame for the web hero, credited "צילום: משה ברנשטיין"; the photographer's signature strip (bottom 58 px) cropped off | Photographer's file from Eli Raz's Drive share; same photograph as the cover (provenance/cover-photo.md) |
| 2026-11-24 | site/crosslinks.json: 17 links where the text names another chapter of the book, each from the printed phrase to that chapter's heading | Book text; checked by content-data/scripts/check_content_data.py |
| 2026-11-24 | site/glossary.json: 51 geological and local terms that the book explains, each with a near-quote definition and the exact source text | Book text at each term's source element |
| 2026-11-24 | site/timeline.json: 62 dated events (12 major) from Eli Raz's life and the book, each with the exact sentence and its paragraph | Book text; only dates that the text gives (notes in content-data/places.md) |
| 2026-11-24 | site/places.json: 29 places (the 7 earlier places in the new format plus 22 more), each with chapter targets, a description and photos named in captions | Coordinates from Wikidata P625 (raw responses in content-data/wikidata-raw); descriptions were near-quotes, replaced by exact quotes (see the newer places row) |
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
