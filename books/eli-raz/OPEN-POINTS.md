# Open points

Record of open items for the Eli Raz edition. Update an item in place when it changes. Delete it when it is resolved.
Site: https://eli-raz.yarden-zamir.com (public since 2026-11-24, Yarden approved the Everyone placement).
Clearance evidence: scratchpad clearance record of 2026-11-24, summarized in book.toml [release].

## Rights and credits

1. PDF page 302 Google Earth view (p302-x1173): withheld. Maps agent (2026-11-24) checks Google's guidelines and otherwise draws an open map.
2. PDF page 183 Theriaca Reformata jar (p183-x717): withheld. No source found among 411 Commons candidates.
3. PDF page 301 route map, Bein et al. 2020 (p301-x1169): withheld until the authors give permission. Maps agent draws an open map of the route the chapter describes, labelled as new.
4. PDF page 66 disaster-area map (p066-x251): replaced by an open map. Maps agent (2026-11-24) improves it or brings a better open source.
5. Credits that rest on one non-original record:
   - PDF page 35 Kochva photo (p035-x151): Commons record only; the PikiWiki page is not reachable.
   - PDF page 183 Wellcome jar (p183-x713): Commons record only; no live Wellcome catalogue record found.
   - PDF page 275 CSIRO image (p275-x1087): licence from an archived CSIRO page (Wayback 2023-04-16).
6. Cover photo (Moshe Bernstein, Nahal Kedem): compare with the Drive originals "Kedem 1" and "Kedem 2". Blocked: no signed-in Google Drive tool on the build machine. Fix: download both into the private input folder on the build machine (outside the repo).
7. The complete edition (with all print images) was public for a short time before the release replaced it on 2026-11-24. Accepted by Yarden; no action.

## Quality

8. Visual check of all 316 pages against the PDF (inventory/pages.csv status "pending").
9. 23 bracket items from tools/check_text.py.
10. 4 known reading-order differences from tools/check_bidi.py (PDF pages 279, 280, 283, 291).
11. Kindle Previewer test: not available on Linux. Test on a Kindle device or on a Mac or Windows machine.
12. Calibre Flow view: not tested.

17. PDF page 78 caption of the part 1 video (fig-a10-13) is garbled: two overlapping caption lines merged ("הנספים לפני האסון הצסורותט…"). Fix in ingest or with a text fix.

22. Errors in the printed text: errata/ERRATA.md (67 entries, 2026-11-24). 22 verified corrections go into both editions with a visible edition note (EPUB/Kindle agent). Family decisions: a10-p012 victim's name "גדי" vs "גבי" (a10-p002 and the Israeli Mountain Guides wiki say גבי); a10-p020 the earlier rescue mission named as Turkey (in 1990 the recent one was Armenia, December 1988); the Alps trip year, 1981 (a09-p014) vs 1982 (a10-p037). 31 more for an editor, listed with evidence.
23. Translations are machine translations, not reviewed by a person: he/a06, he/a36, en/a03, en/a10 (site/translations/). Translator notes and open questions: translations/eli-terms.md, translations/en-style.md, and the translation agent's report.

24. Digitized charts (site/charts/, scripts/digitize_charts.py): values traced from the print, with stated accuracy. Checked 2026-11-24 in a browser: Nof, Abelson, Raz et al. 2019 has no data availability or supplementary section; its text (~6,000 total, ~700 new in 2015) matches the digitized series (5,940; 690). Exact yearly counts would need the Geological Survey of Israel sinkhole inventory. The density axis on PDF page 305 prints 170-174 "g/cm³". Published values from the same 1959-60 survey are about 1.19-1.205 (upper water) and 1.23 g/cm³ (lower water), a 40-unit step at x1000, but the chart steps about 3 units, so the printed quantity is not density x1000. Unit unresolved without Neev and Emery 1967 (GSI Bulletin 41); the chart keeps the printed numbers.
25. Places without a Wikidata item, not on the map: ואדי אל-הידאן, ואדי זרקא מעין (content-data/places.md).
26. PDF page 297 (fig-a36-06): Eli's 2011 schematic has a three-row table of route lengths; it could become a sortable table.

27. Pointed Hebrew (niqqud) attached to the wrong letters in every pointed passage (poems at chapter ends, Bible quotes); and poems shown as one paragraph per line. Assigned 2026-11-24: EPUB/Kindle agent (mark attachment by glyph position, poem markup), UI agent (poem styling).

## Design and assets

13. Print fonts: bundle licensed font files, or keep Noto Sans Hebrew as the fallback.
14. EPUB cover page design.

## Repos

15. Commit and push continuously (user rule, 2026-11-24). Since 2026-11-24 the book lives in books/eli-raz/ of the public repo game-design-driven/epub-web-edition (workflow: docs/WORKFLOW.md).

## Web enrichment (site/enhancements.json)

18. Done 2026-11-24: places map (7 places, Wikidata coordinates), 5 YouTube players from QR links, 3 printed tables as sortable tables (PDF pages 281, 282, 285), live Dead Sea level chart from Water Authority data (scripts/dead_sea_level.py; run again to refresh).
19. Candidates without exact numbers, left as print images: sinkhole count (PDF page 113, second series), Lisan lake levels (page 262), water density by depth (page 305), Red Sea - Dead Sea flows (page 304). Each needs a first-party dataset or the authors' data.
20. Places not on the map: chapters about routes or regions (a25-a28, a30) and the Tropic of Cancer tour (a28). Add a place only with a verified Wikidata record and a clear link to the text.
21. Historic maps (a07, PDF pages 40-49): possible side-by-side view with a modern map. Not started.
