# Plan: modern topographic map for fig-a17-02 (Sela)

Figure fig-a17-02 (a17, PDF page 147): the printed topographic map of Sela, credit "באדיבות איתי חביב".
Add a second tab with a modern topographic map of the same area. The printed map stays the default tab.

## Decisions
- Candidates: OpenTopoMap (live tiles), our own render (Copernicus DEM GLO-30 and OpenStreetMap), scanned topo sheets.
- Choice: our own render. It matches the print one to one: same bounds, north up, 100 m contours, the same scale bar.
- Scanned sheets: the University of Texas map library (Perry-Castañeda) has no Jordan 1:50,000 series online; the
  nearest series (Arabian Peninsula 1:500,000) is too coarse for a 4 km map.
- Fortress position: Wikidata Q126824792 (castle) and OSM node 798883031. Village: Wikidata Q489724, OSM node 798883086.
  Q12218883 from the brief is a bacterium.

## Steps
- [ ] Align the printed map: fit control points (print pixels to coordinates), report the error
- [ ] Render the modern map (scripts/sela_topo.py): WebP under 400 KB, the same frame as the print
- [ ] Spec (site/figure-maps/fig-a17-02.json), credits, CONTENT-CHANGES.md
- [ ] After PR #12 merges: image map kind and a print-first tab in tools/web/72_map_figures.py and site/features/75-map-figures.js
- [ ] PR images: the print and the new tab side by side
