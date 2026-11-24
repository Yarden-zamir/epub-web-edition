# Trek site features for the Eli Raz web edition

Research only. No code changed. Date: 2026-11-24.

## Sources

- Trek sites: [Yarden-zamir/gr52](https://github.com/Yarden-zamir/gr52) (GR52 trail story, live at https://gr52.yarden-zamir.com), [Yarden-zamir/yam2yam](https://github.com/Yarden-zamir/yam2yam) (Sea to Sea plan, live at https://yam2yam.yarden-zamir.com), [Yarden-zamir/trek-site-template](https://github.com/Yarden-zamir/trek-site-template) (the shared code).
- The three repos run the same page code: `site/map.js`, `site/log.js` and `src/sw.js` have identical checksums. References below use the gr52 copy at commit 073739f. `src/build.py` in the template differs a little from gr52 and yam2yam.
- Book site: [Yarden-zamir/epub-web-edition](https://github.com/Yarden-zamir/epub-web-edition) at commit 4028809 "fix: place Hebrew points by their printed ink". The UI agent has uncommitted changes (hero photo in `tools/build_web.py`), so line numbers come from the committed files. Content data: `~/Github/eli-raz-edition/main/site/`.
- Live check: Playwright 1.64.1 with Chromium 1255, desktop 1440x900 and phone 390x844, on all three sites. Results:

| Check | gr52 | yam2yam | Book |
|---|---|---|---|
| Web app manifest linked | yes | yes | no (icons exist: `icon-192.png`, `icon-512.png`, `icon-mask.png`) |
| Service worker | yes | yes | no |
| `robots` meta | none on the front page | none | `noindex, nofollow` |
| canonical, Open Graph tags | yes, with a 1200x630 image | yes, no image | none |
| `/robots.txt`, `/sitemap.xml` | built by the site | built by the site | robots.txt is the Cloudflare managed file; sitemap 404 |
| Analytics | GA4 | GA4 | none |
| Page size | 37,000 px tall, 683 images | 8,300 px | 546,000 px tall, 1.08 MB HTML, 534 figures; whole site 59 MB (27 MB EPUB download, 29 MB book images) |

Screenshots are in the session scratchpad (not kept): the GR52 story with the map beside it, and the phone lightbox.

## Legend

- **Book status**: Has = the book site does this now. Queued = the data or a task exists (AGENTS-BRIEF.md, OPEN-POINTS.md), not yet rendered. No = not present.
- **Fit**: High, Medium, Low, None, with the reason.
- **Effort**: S = one function or a small file, no new data. M = a new module in `reader.js` or `build_web.py`, or new build output. L = new data, a server, or a design change across the page.

## 1. Map behaviour and controls

| Feature | What it does | Trek code | Book status | Fit | Effort |
|---|---|---|---|---|---|
| Gesture rules | Ctrl or pinch zooms, wheel scrolls the page, two fingers on a phone | `gr52/site/map.js:182` | Has, with a fuller rule set and hints (`reader.js:609-708`) | — | — |
| Collapsible map credit | A "©" button that opens the attribution | `map.js:196` | Has (credit toggle in `makeMap`, `reader.js:643`) | — | — |
| Layer control per kind and per day | Leaflet layers control: nights, water, passes, each day's stretch | `map.js:206-240` | No. Book maps have one layer each | Medium. Useful only for a map with many kinds (places map: places with photos against places without; figure maps: route against areas). 29 places do not need layers | S |
| Rotate with two fingers | leaflet-rotate plugin | `map.js:1`, `site/vendor/leaflet-rotate.*` | No | Low. A reader does not navigate with the map; rotation adds a vendored plugin for little gain | S |
| Scope a map to a part ("day"), fly between parts | `setScope` fits the map to one day and highlights it | `map.js:246-272` | Partial. Place chips fly to one place (`reader.js:840`) | Medium. A chapter scope on the places map ("places in this chapter") reuses `targets` in `places.json` | S |
| Focus a named place from the text | Place names in the text become chips that open the map at the place | `src/build.py:69` `link_places`, `map.js:417-449` `focus` | Has: place dots after chapters in the printed contents and pills (`reader.js:860`); `places.json` holds 110 text targets | Medium. The trek links the name inside the paragraph. The book could mark place names in the text the way it marks glossary terms (`build_web.py:405` `mark_terms`) | M |
| Elevation profile linked to the map | Canvas profile, hover moves a marker on the map, picture marks on the profile | `map.js:274-340` | No | Low. Only route figure maps (Pamir expedition fig-a10-02, route figures in a36) have a line. Heights need a cited elevation source | M |
| Offline "save whole route" tiles | Downloads a corridor of tiles at zoom 12-16 into Cache Storage | `map.js:362-415` | No | Low. Book maps are small and few. The service worker can cache tiles as they are used (see 4) | S |
| Picture clusters on the map | One preview per group of pictures that overlap at the zoom | `site/log.js:111-168` | Partial. Place popups show thumbnails of that place's figures (`build_web.py:873`) | Low. 29 places, each with a few figures: popups are enough | M |
| Retry the data load on a bad signal | The GPX fetch retries with a growing pause | `map.js:561-578` | No. Leaflet and tiles load once from cdnjs | Medium. Cheap and matches the Ein Gedi audience with weak signal | S |

## 2. Story on the map ("spine")

| Feature | What it does | Trek code | Book status | Fit | Effort |
|---|---|---|---|---|---|
| Map beside the text | On a wide screen or a phone on its side the map sits sticky beside the story at full height | `src/head.html:244-305`, `map.js:503-521`, `map.js:581-591` | No. The places map is one block after the contents | Medium-High on desktop. The book has 29 places with 110 text targets, 3 figure maps and a then-and-now map queued. A side map that shows the places of the chapter in view turns the map into a reading aid. Risk: the book column is the product; the map must stay optional (a toggle, closed by default on narrow screens) | L |
| Map follows the reader | The rail reports the day under the eye; the map flies to it | `map.js:626-638` (`trek:reading`) | No | Same as above; it is the behaviour that makes the side map useful | M (with the spine) |
| "Track the log" | The map glides to each picture as it passes the reading line | `log.js:947-988`, button `map.js:454-478` | No | Medium. Book equivalent: fly to each place paragraph (`targets`) as it passes | M (with the spine) |
| Drag to resize the map column | A grip on the map edge; the share is kept in localStorage | `map.js:592-624` | No | Low. Polish for the spine only | S |

## 3. Pictures and lightbox

| Feature | What it does | Trek code | Book status | Fit | Effort |
|---|---|---|---|---|---|
| Full-screen viewer | Picture, caption, counter, download | `log.js:171-192`, `#lightbox` | Has: `<dialog id="figure-dialog">` with caption and "open original" (`reader.js:303-318`, `reader.css:331`) | — | — |
| Zoom and pan | Pinch, double tap, double click, wheel; drag once zoomed; clamped to the screen; 1x-6x | `log.js:238-284` | No | High. The book has historic maps (a07, PDF pages 40-49), diagrams, printed tables and charts as images. On a phone they are unreadable without zoom. The originals are full resolution | M |
| Previous and next | Arrow buttons, arrow keys, swipe sideways; preloads the next picture | `log.js:186-190`, `log.js:286-294` | No. The viewer shows one figure | High. 534 figures; a "figure set" (photos in one chapter, or a multi-image figure) is the natural list. Arrow direction must follow RTL | S-M |
| Swipe down to close | A short downward swipe closes the viewer | `log.js:288-294` | No (Back, Escape and × close it) | High on phones; tiny | S |
| `?photo=ID` in the address | The open picture is shareable; the viewer is a history entry | `log.js:184`, `log.js:193-214` | Partial. History entry yes (`openOverlay`, `reader.js:110`); deep link buttons on figures copy `#fig-…` but the link scrolls to the figure, it does not open the viewer | Medium. A shared link to a figure could open it in the viewer | S |
| Rows that fill at one height | Pictures on one line share the width by aspect ratio | `log.js:72-110` | Different design: photos run full width and pan with scroll; artwork never cropped (pipeline README "Decisions") | None. The book layout follows the print and its own rules | — |
| Videos in the lightbox | Clips play in the viewer | `log.js:177-180` | Has: YouTube players from printed QR codes, load on press (`reader.js:565`) | — | — |
| Picture place by time | Pictures without GPS go on the route by their time | `log.js:45-71` | No | None. Book figures have no capture data; a place must come from the text | — |

## 4. Offline, PWA and service worker

| Feature | What it does | Trek code | Book status | Fit | Effort |
|---|---|---|---|---|---|
| Web app manifest | Name, start URL, standalone display, colours, icon | built at `src/build.py:351-360`; `gr52/site/manifest.webmanifest` | No, but the icon set is already built (`build_web.py:892-905` `ICON_LINKS`, `brand_files`) | High. "Add to home screen" gives the family a book icon on the phone. The icons exist; only the JSON file and one `<link>` are missing | S |
| Service worker, versioned precache | Precache list with content hashes; old caches dropped on activate; `cache: 'reload'` on install so no stale file enters | `src/sw.js:1-14`, list built at `src/build.py:390-399` | No | High. A reader at the Dead Sea or on a plane reads without signal. Precache: `index.html`, `reader.css`, `reader.js`, the book CSS and fonts, `search.json` (808 KB), thumbs. Images by use (below) | M |
| Runtime strategies per host | Tiles cache-first; weather network-first with cache fallback; fonts cache-first; same-origin stale-while-revalidate; sign-in and per-user paths bypass | `src/sw.js:15-47` | No | High for the pattern. Book map: OpenTopoMap tiles cache-first; cdnjs Leaflet cache-first; book images cache-first (immutable names); `index.html` network-first so corrections show at once; the 27 MB EPUB download bypasses the worker | S (part of the worker) |
| "Save the whole book" | The trek saves a tile corridor on request | `map.js:369-415` | No | Medium-High. One button that caches the 29 MB of images for full offline reading, with progress. Default stays "cache as read" | S (after the worker) |
| Reload on a new version | When a new worker takes control, the page reloads once | `src/scripts.html:24-28` | No | Medium, with a change. A silent reload in the middle of a 546,000 px page is rude. The book restores scroll on reload (`reader.js:146`), so it would land in place, but a small "new version — reload" note is safer | S |
| Short cache headers for data | `_headers` file sets max-age per path for kitshn 2 | `gr52/site/_headers` | No. Live `index.html` is `max-age=0, must-revalidate` | Medium. Long `immutable` cache for `book/` images, `thumbs/`, `media/` cuts repeat loads; keep HTML at 0 | S (needs a check that names change when content changes) |

## 5. Languages

| Feature | What it does | Trek code | Book status | Fit | Effort |
|---|---|---|---|---|---|
| Two full copies, one hidden | The build writes `#en` and `#he` wraps; the second language's IDs get a `he-` prefix | `src/render_log.py:104-112`, `src/render_log.py:174-182` | No | Low as is. The book page is 1.08 MB; a second full copy doubles it. Only 4 chapters have translations | — |
| Language button, `?lang=`, remembered choice | A shared link carries its language; otherwise the reader's saved choice; `dir` flips on `<html>` | `src/scripts.html:3-23` | Queued: `site/translations/<lang>/<unit>.json` (he/a06, he/a36, en/a03, en/a10), not rendered yet | High for the pattern, applied per chapter: a toggle on a translated chapter swaps its elements by ID from the JSON, sets `lang` and `dir` on that section only, and keeps the choice in `?lang=` and localStorage. The "machine translation, not reviewed" label (OPEN-POINTS 23) must show next to the toggle | M |
| Strings table per language | One `T = {en, he}` object for all UI text | `log.js:8-16` | The book UI is Hebrew only, strings inline | Low. Only needed if the whole interface gets a second language | — |
| `og:locale` and per-language preview text | Link previews in the visit's language | `src/build.py:183-195`, `src/build.py:260-278` | No Open Graph at all | See 6 | — |

## 6. Sharing, search engines, analytics

| Feature | What it does | Trek code | Book status | Fit | Effort |
|---|---|---|---|---|---|
| Open Graph and Twitter card | Title, description, canonical, a 1200x630 JPEG crop of the cover photo | `src/build.py:260-278`; crop made by `uploader/app.py:314` `og_preview` | No | High. The family shares the link on WhatsApp; today it shows a bare URL. Build a 1200x630 crop of the hero photo or cover at build time with Pillow (already a build dependency, `build_web.py` hero code). Independent of indexing: OG works with `noindex` | S |
| `robots.txt`, `sitemap.xml`, canonical | Only the front page is indexed; copies are `noindex` | `src/build.py:384-388`, `src/build.py:306`, `src/build.py:325` | `noindex, nofollow` is hard-coded in the template (`site/index.html:6`) because the public pipeline repo serves placeholder content. The real site inherits it | Decision for the user, not a feature gap. If the family wants the book findable, the build needs a per-edition switch (content repo `book.toml` or enhancements) so the synthetic sample stays `noindex` | S |
| GA4 page events | Scroll depth, sections reached, pictures opened, map use, tabs, language, downloads; only on the production host; `tools/analytics.py` reads reports | `site/analytics.js:1-58`, tag at `src/build.py:240-258` | No | Low-Medium. The event design fits well (chapters reached, figures opened, EPUB downloads, search use). The vendor does not: the book avoids third-party loads (YouTube loads only on press). A cookie-less option (Cloudflare Web Analytics, if the zone allows it, or a self-hosted counter) fits better. Needs the user's and family's consent | S-M |

## 7. Gestures and scrolling

| Feature | What it does | Trek code | Book status | Fit | Effort |
|---|---|---|---|---|---|
| Dot rail with scrubbing | A rail of dots (days) and dashes (sections), the current one lit; drag along it to scrub the page; hidden in print | `map.js:747-805`, CSS `src/head.html:413` | No. The book has a top progress bar (`reader.css:113`) and the chapter navigator dialog | High. The page is 546,000 px tall with 36+ chapters. A thin rail with one mark per chapter (and part), scrub with the finger, label of the chapter under the finger, is the fastest way to move through it on a phone. Needs RTL placement and a design pass | M |
| Glide onto the next part after a touch | After a finger lifts near the start of a day, the page glides so the day starts at the top (not CSS scroll snap) | `map.js:806-822` (`settle`, `scrollend`) | No | Low. In a book a reader stops anywhere; a forced glide fights reading. CSS `scroll-snap` is worse for long text | — |
| Swipe sideways between tabs | On a day card, swipe changes the tab, RTL aware | `map.js:825-842` | No tabs in the reading flow. The navigator dialog has tabs (chapters, timeline; `reader.js:225`) | Low. Two tabs in a dialog do not need a swipe | S |
| Buzz on each day and picture | `navigator.vibrate` on Android | `map.js:752`, `log.js:976-988` | No | None. Distracting while reading | — |
| Address follows the reader | `?at=d3:log` updated as the scroll settles, so a reload or shared link returns there | `map.js:685-704` | Has a stronger form: scroll position in history state (`reader.js:140-157`) and "continue reading" in localStorage (`reader.js:1279`) | — | — |
| Way-back bubble after a map jump | A bubble "Back to …" for a few seconds; browser Back still works | `map.js:705-722` | Partial: Back and Forward return and highlight (`reader.js:12-157`); no visible button | Medium. Desktop readers rarely press Back. A small "חזרה ל…" chip after a footnote, cross-link or map jump names where Back goes. The history logic exists; this is UI only | S |
| Cover parallax and fade | Scroll-driven CSS with a JS fallback; reduced motion respected | `src/head.html:157-163`, `src/scripts.html:30-39` | Has (hero drift and lift, photo pan, `reader.css:254-267`) | — | — |

## 8. Editing on the page and comments

| Feature | What it does | Trek code | Book status | Fit | Effort |
|---|---|---|---|---|---|
| Edit text on the page | Editors sign in with GitHub (oauth2-proxy); pencil or long press opens the editor; edits go to `edits.json`; `tools/log_pull.py` folds them back | `log.js:308-770`, `uploader/app.py:248-312`, `container/Caddyfile` | No | None for the text. The book text is the printed text; every change needs an entry in CONTENT-CHANGES.md. kitshn 2 does not run the uploader either (template README "Deploy") | L |
| Upload pictures, Google Takeout zip | Editors add pictures and videos; time and place from EXIF or sidecar | `log.js:827-933`, `uploader/app.py:85-246` | No | None. Book images come only from the print or cleared public-domain sources | — |
| Comments (giscus) | One GitHub Discussion under the story | `log.js:997-1018` | No | Low. Needs a public repo with Discussions; the content repo is private. A "report an error" route for the family is a separate, simpler need (OPEN-POINTS 22 lists printed errors) | M |

## 9. Other trek features

| Feature | What it does | Trek code | Fit for the book |
|---|---|---|---|
| Weather history per day (ERA5) | Weather on the walked dates at the night spot and high point | `log.js:771-826` | None. It adds data the book does not state, against the "never invent facts" rule |
| Plan weather, day simulator, warnings | Forecast per day, ensemble strip, start-time slider | `site/trip.js:121-286` | None |
| Position snapshot ("where am I") | One GPS fix; draws you on the map, marks progress | `trip.js:338-435` | Low-Medium. A "places near me" button on the places map, for readers who visit Ein Gedi and the sinkhole fields. 29 places have coordinates. Uses only the browser; no data leaves the phone | 
| GPX download | The route for any map app | `src/build.py` (GPX path), `site/_headers` `Content-Disposition` | Low-Medium. Route lines in `site/figure-maps/*.json` could download as GPX, so a reader can walk a route the book describes. Only for lines traced from a cited source |
| Annotated section maps for print | WebP maps per section | `tools/maps.py` | None. The book has its own print figures |
| Cast to TV and remote control | Google Cast, `?cast=1`, arrow keys walk the story | `log.js:1019-1167` | Low. A family reading together on a TV is possible, but the book text is not a slideshow. The keyboard part (arrow keys move between chapters) costs little |
| Facts chips layout | Fact chips laid out with no holes in the last row | `map.js:844-860` | None. The book has no fact chips |
| Dark mode tokens and `data-theme` | `prefers-color-scheme` plus a manual override | `src/head.html:16-30` | Has (`reader.css:22-33`) |
| Link checker | Checks every link and reference, and external pages | `tools/links.py` | Medium. The book has many external links (credits, related, sources). The pipeline has `check_release.py`; an external-link pass with `--no-net` for CI is cheap |
| Headless page checks | `tools/check.py` drives Chrome against the page or a URL | `tools/check.py` | Has: `tools/verify.py` with axe-core |

## 10. Ranked shortlist

1. **Link preview (Open Graph)**: title, description, canonical and a 1200x630 hero crop made at build time. Family members share the link; today WhatsApp shows a bare URL. Trek: `src/build.py:260-278`. Effort S. No content risk.
2. **Web app manifest**: the icons already exist; add `manifest.webmanifest` and one `<link>`. "Add to home screen" gives the book its own icon. Trek: `src/build.py:351-360`. Effort S.
3. **Lightbox zoom, previous and next, swipe down to close**: upgrade the existing `figure-dialog`. Historic maps, diagrams and tables become readable on a phone. Arrow direction follows RTL. Trek: `log.js:171-294`. Effort M.
4. **Service worker for offline reading**: versioned precache of the page, CSS, JS, fonts and search index; images and map tiles cache-first as read; HTML network-first so corrections show at once; the EPUB bypasses the worker. Trek: `src/sw.js`, `src/build.py:390-399`. Effort M.
5. **"Save the whole book offline" button**: after item 4, one button caches the 29 MB of images, with progress. Trek: `map.js:369-415`. Effort S.
6. **Chapter rail with scrubbing**: one mark per chapter on the inline-start edge, current chapter lit, drag to scrub with the chapter name shown. Fast travel on a 546,000 px page. Trek: `map.js:747-805`. Effort M, needs a design pass.
7. **Per-chapter language toggle**: render the queued translations with the trek's `?lang=` plus localStorage pattern, per chapter, with the "machine translation, not reviewed" label. Trek: `src/scripts.html:3-23`. Effort M. Depends on the UI agent's queue.
8. **Visible "back to where you were" chip**: show the destination of Back for a few seconds after a footnote, cross-link or map jump. The history logic exists. Trek: `map.js:705-722`. Effort S.
9. **Places map beside the text (desktop)**: a sticky side map that follows the chapter in view and flies to place paragraphs, off by default on narrow screens. Biggest reading aid, biggest design change. Trek: `src/head.html:244-305`, `map.js:626-638`, `log.js:947-988`. Effort L.
10. **Places near me**: one button on the places map that shows the reader's position and the nearest book places. For visitors at the Dead Sea. Trek: `trip.js:338-435`. Effort S-M.

Not recommended: editing on the page, uploads, giscus comments, weather history, the glide after touch, vibration, scroll snapping, two full language copies, GA4 as the analytics vendor.

## Decisions for the user

- Indexing: the live book keeps `noindex, nofollow` from the public template. Keep it, or let the family's book be found by search engines (needs a per-edition switch).
- Analytics: none today. If wanted, pick a cookie-less option and tell the family.
