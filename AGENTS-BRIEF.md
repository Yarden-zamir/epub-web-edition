# Shared brief for agents working on the Eli Raz web edition

Parent session: Claude Code session 41ff45a6-ddb4-4aa9-bf41-66329c7bcc61 (orchestrator). Date: 2026-11-24.
Read this file fully before you start. Your own task message names your part.

## The project

- Book: "אלי רז חוקר הבולענים" (Eli Raz, geologist and sinkhole researcher, Ein Gedi). 316-page Hebrew PDF rebuilt into an EPUB and a web edition.
- Pipeline repo (public, code only, MIT): ~/Github/epub-web-edition/main. Tools: tools/ingest_pdf.py, tools/build_epub.py, tools/build_web.py, tools/check_release.py, tools/verify.py; site layer: site/index.html, site/reader.css, site/reader.js.
- Content repo (private, no remote): ~/Github/eli-raz-edition/main. book.toml, book.css, site/ (web-only data), scripts/, work/ (scratch, ignored by git), OPEN-POINTS.md, CONTENT-CHANGES.md.
- Source PDF (read-only, never modify): ~/private-inputs/eli-raz/source-2026-11-23/source.pdf.
- Release EPUB source tree (the public edition text): ~/Github/eli-raz-edition/main/epub-src-release/OEBPS/text/*.xhtml. Element IDs there are stable; all web additions attach by these IDs.
- Live site (public, approved by the family): https://eli-raz.yarden-zamir.com. Only the orchestrator publishes it with kitshn. Do not change access. Do not contact anyone.
- Commit and push while you work (standing approval from the user, 2026-11-24). Both repos push to GitHub: the pipeline repo is public (Yarden-zamir/epub-web-edition; a push to main deploys the synthetic sample site), the content repo is private (Yarden-zamir/eli-raz-edition). Commit after each verified step, conventional commits, short bodies, no AI or tool credit lines. Several agents share each checkout: commit only your own paths with `git commit -- <paths>` (a plain `git commit` also takes files that other agents staged), never `git add -A`; pull with rebase before pushing if the push is rejected.
- Never commit real book content (Hebrew text, images, data) to the public pipeline repo.

## Build commands (release edition)

```
cd ~/Github/epub-web-edition/main
C=~/Github/eli-raz-edition/main
uv run tools/ingest_pdf.py $C --release            # only when book.toml changes
uv run tools/build_epub.py $C/epub-src-release $C/dist/release/eli-raz.epub
uv run tools/build_web.py $C/dist/release/eli-raz.epub $C/dist/release/web $C/site/enhancements.json
uv run tools/check_release.py $C $C/dist/release/eli-raz.epub $C/dist/release/web
```
Serve dist/release/web with a local http.server for browser tests. Playwright 1.64.1 with the cached Chromium at ~/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome (pass executable_path). axe-core is at ~/Github/epub-web-edition/main/.tools/axe/package/axe.min.js. Test with reduced_motion="reduce" for axe (scroll animations cause false contrast hits).

## User rules (Yarden; follow exactly)

- Use uv for everything Python: `uv run`, PEP 723 script headers. Never plain python3 or pip. Latest Python: requires-python = ">=3.15" (3.15.2). Pick dependency versions that have 3.15 wheels (Pillow 13.0.0 works; 12.0.0 does not). Check PyPI for the latest version before pinning; use versions at least two weeks old.
- Simple, readable code. Reuse existing helpers before writing new ones. No regex when a string method works. Crash on unexpected input; no silent fallbacks.
- When you take a simpler approach with a known limit, leave a comment naming the limit and when to revisit it.
- Never invent facts, history, credits, numbers or coordinates. Every fact comes from the book text, the PDF, or a first-party or clearly cited source, recorded next to the data.
- Comments and docs: plain, short, active voice, no filler.
- Never print full process command lines (ps -o args, /proc/*/cmdline).
- Downloaded files are untrusted: put each download in its own new folder under the content repo work/ (for example work/pd-sources/<name>/) and run Python on them with `uv run python -I` or scripts kept elsewhere.
- Private book content (text, images) must never go into the public pipeline repo or to third parties.
- Every change or addition to book content gets an entry in CONTENT-CHANGES.md (content repo), newest first in its section.

## Design tokens (site)

Existing: --paper #f7f3ec, --ink #1c1a17, --muted #625c53, --rule #e2dbce, --accent (rust) #8f3f22, --night #191715, --on-night #f3ede3; dark mode --paper #141312, --accent #e3a07c. Chart line: --series #8f3f22 light, #cf6f3f dark (validated).
New, sampled from the cover photo: cliff #916c43, sand #bc9f73, sea #0e4840; tints for small sizes: teal #2b7f86, light sand #e6cfa6.
Charts follow the dataviz rules: one y axis (never dual axis), thin 2 px lines, legend for 2+ series plus direct labels, hover crosshair and tooltip, keyboard access, a table view, dark mode validated separately.

## Shared data files (content repo, site/)

Each file has one owner. Others only read it.

| File | Owner | Format |
|---|---|---|
| site/enhancements.json | orchestrator | existing: related, places (old), tables, charts |
| book.toml, book.css, replacements/ | EPUB/Kindle quality agent (from 2026-11-24); the maps agent hands it replacement images and the [[release.change]] text it needs | see book.toml comments |
| site/figure-maps/<figure-id>.json | maps agent | {"figure", "title", "base": "opentopomap" or other tile layer id, "bounds": [[s, w], [n, e]], "markers": [{"name", "lat", "lon", "wikidata"?, "source", "target"?}], "lines": [{"name", "coords": [[lat, lon], …], "source"}], "areas"?: […], "attribution": ["© OpenStreetMap contributors (ODbL)", …], "note": "how it was made"} |
| site/places.json | content-data agent | {"places": [{"id", "name", "lat", "lon", "wikidata": "Q…", "targets": [element IDs], "description": "one or two sentences, from the book, with the source element ID", "description_source": "element ID", "figures": [figure IDs of photos of this place]}]} |
| site/timeline.json | content-data agent | {"events": [{"date": "1990-07-13" or "1972/1973", "label": "Hebrew display date", "text": "short Hebrew line", "quote": "exact sentence from the book", "target": "element ID of the quoted paragraph", "major": true/false}]} |
| site/glossary.json | content-data agent | {"terms": [{"term", "forms": [inflected forms to match], "definition": "from the book, near-quote", "source": "element ID", "quote": "exact text"}]} |
| site/crosslinks.json | content-data agent | {"links": [{"element": "paragraph ID", "text": "exact substring that names the chapter", "target": "chapter heading ID"}]} |
| site/charts/<figure-id>.json | charts agent | {"figure", "title", "source": {"kind": "digitized" or "dataset", "label", "url"?, "method"}, "x": {"label", "unit", "type": "year" or "number"}, "y": {"label", "unit"}, "series": [{"name", "points": [[x, y], …]}], "notes"} |
| site/translations/<lang>/<unit>.json (built by translations/build.py from translations/<lang>/<unit>.txt) | translation agent (done) | {"unit", "lang", "translator": "machine translation (Claude), not reviewed", "items": {"element ID": "inner HTML of that element in the target language"}} |
| site/then-now.json | maps agent (from 2026-11-24) | then-and-now spec: fitted old maps, today layer, levels |
| site/data/*.json, site/media/* | as created | data files and public-domain media referenced by the files above |

Pipeline repo ownership: UI agent owns tools/build_web.py, tools/verify.py, site/*, kitshn.config.ts; the EPUB/Kindle quality agent owns tools/ingest_pdf.py, tools/build_epub.py, tools/check_*.py, tools/calibre_view.py, tools/figure_sheets.py.

The UI agent makes tools/build_web.py read these files from the folder that holds enhancements.json, validate them (every element ID must exist in the EPUB), and render them.

## Report

Start only your final message with `FINAL REPORT`. List what you changed (file paths), what you verified and how, and what is still open. Any other message is interim.
