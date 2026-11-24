# Shared brief for agents working on the Eli Raz web edition

Parent session: Claude Code session 41ff45a6-ddb4-4aa9-bf41-66329c7bcc61 (orchestrator). Date: 2026-11-24.
Read this file fully before you start. Your own task message names your part.

## The project

- Book: "אלי רז חוקר הבולענים" (Eli Raz, geologist and sinkhole researcher, Ein Gedi). 316-page Hebrew PDF rebuilt into an EPUB and a web edition.
- Repo (private, GitHub Yarden-zamir/epub-web-edition, container ~/Github/epub-web-edition with .bare/ and one folder per worktree). It holds the pipeline at the root (tools/ingest_pdf.py, tools/build_epub.py, tools/build_web.py, tools/check_release.py, tools/verify.py; site layer: site/index.html and site/features/ with one .js and .css per feature, plus build modules in tools/web/; see site/features/README.md) and this book in books/eli-raz/ (book.toml, book.css, site/ for web-only data, scripts/, work/ for scratch, OPEN-POINTS.md, CONTENT-CHANGES.md). The root sample edition (epub-src/, inventory/, originals/) stays synthetic.
- The old private repo Yarden-zamir/eli-raz-edition is archived. Its full history is in books/eli-raz/ (git subtree, 2026-11-24).
- Source PDF (never modify): books/eli-raz/source/source.pdf, with source/SHA256SUMS and source/PROVENANCE.txt. book.toml names it relative to the book folder. The original stays read-only in ~/private-inputs/eli-raz/source-2026-11-23/.
- Rights: books/eli-raz/NOTICE.md. The MIT licence covers only the pipeline code and the sample. The repo history holds the source PDF and the withheld print images, so the repo must not go public without a history rewrite.
- Release EPUB source tree (the public edition text): books/eli-raz/epub-src-release/OEBPS/text/*.xhtml (built, ignored by git). Element IDs there are stable; all web additions attach by these IDs.
- Live site (public, approved by the family): https://eli-raz.yarden-zamir.com. GitHub Actions builds and deploys it on each push to main (see "Deploy" below). Do not change access. Do not contact anyone.

## Git flow

- Commit and push while you work (standing approval from the user, 2026-11-24). Conventional commits, short bodies, no AI or tool credit lines. Commit after each verified step.
- Each agent works in its own worktree, never in another agent's folder. Make one once: `cd ~/Github/epub-web-edition/main && $DOTFILES/bin/wt-new <your-name> origin/main`. It is the folder ~/Github/epub-web-edition/<your-name>.
- Commit only your own paths: `git commit -m "..." -- <paths>`. Never `git add -A`.
- To push: `git pull --rebase origin main`, then `git push origin HEAD:main`. No pull requests, no merge queue.
- A push to main deploys both sites. A failed build or check deploys nothing, and both sites stay as they were.

## Build commands (release edition)

Run from the repo root of your worktree:

```
B=books/eli-raz
uv run tools/ingest_pdf.py $B --release            # only when book.toml changes
uv run tools/build_epub.py $B/epub-src-release $B/dist/release/eli-raz.epub
uv run tools/build_web.py $B/dist/release/eli-raz.epub $B/dist/release/web $B/site/enhancements.json
uv run tools/check_release.py $B $B/dist/release/eli-raz.epub $B/dist/release/web
```
Serve dist/release/web with a local http.server for browser tests. Playwright 1.64.1 with its own Chromium: `uv run --with playwright==1.64.1 playwright install --only-shell chromium`. axe-core is at .tools/axe/package/axe.min.js (.tools/ is not tracked; copy or link ~/Github/epub-web-edition/main/.tools into your worktree). Test with reduced_motion="reduce" for axe (scroll animations cause false contrast hits).

Full release build with every check (the same steps as CI): `uv run books/eli-raz/scripts/build_release.py`. It runs both ingests, build_epub, build_web, check_release (with check_size), EPUBCheck 5.4.0 and scripts/smoke_site.py.

## Deploy

- .github/workflows/kitshn.yml: the job "book" runs books/eli-raz/scripts/build_release.py and passes books/eli-raz/dist/release/web as an artifact. The kitshn job then deploys both apps of kitshn.config.ts: the sample ("app") and this book ("book", https://eli-raz.yarden-zamir.com).
- Read the run log: `gh run list -R Yarden-zamir/epub-web-edition -w kitshn.yml`. Build and deploy by hand: `gh workflow run kitshn.yml -R Yarden-zamir/epub-web-edition`.
- The repo is private, so Actions minutes count against the account quota.
- Speed: a push that changes nothing the book build reads restores the last checked build (about 1 min from push to live). build_release.py skips both ingests when the hash of INGEST_INPUTS is unchanged. Whoever makes tools/ingest_pdf.py read a new file or folder adds it to INGEST_INPUTS in books/eli-raz/scripts/build_release.py, in the same commit.

## User rules (Yarden; follow exactly)

- Use uv for everything Python: `uv run`, PEP 723 script headers. Never plain python3 or pip. Latest Python: requires-python = ">=3.15" (3.15.2). Pick dependency versions that have 3.15 wheels (Pillow 13.0.0 works; 12.0.0 does not). Check PyPI for the latest version before pinning; use versions at least two weeks old.
- Simple, readable code. Reuse existing helpers before writing new ones. No regex when a string method works. Crash on unexpected input; no silent fallbacks.
- When you take a simpler approach with a known limit, leave a comment naming the limit and when to revisit it.
- Never invent facts, history, credits, numbers or coordinates. Every fact comes from the book text, the PDF, or a first-party or clearly cited source, recorded next to the data.
- Comments and docs: plain, short, active voice, no filler.
- Never print full process command lines (ps -o args, /proc/*/cmdline).
- Downloaded files are untrusted: put each download in its own new folder under books/eli-raz/work/ (for example work/pd-sources/<name>/) and run Python on them with `uv run python -I` or scripts kept elsewhere.
- Private book content (text, images) must never go to third parties, and the repo must not go public (see NOTICE.md).
- Every change or addition to book content gets an entry in books/eli-raz/CONTENT-CHANGES.md, newest first in its section.

## Design tokens (site)

Existing: --paper #f7f3ec, --ink #1c1a17, --muted #625c53, --rule #e2dbce, --accent (rust) #8f3f22, --night #191715, --on-night #f3ede3; dark mode --paper #141312, --accent #e3a07c. Chart line: --series #8f3f22 light, #cf6f3f dark (validated).
New, sampled from the cover photo: cliff #916c43, sand #bc9f73, sea #0e4840; tints for small sizes: teal #2b7f86, light sand #e6cfa6.
Charts follow the dataviz rules: one y axis (never dual axis), thin 2 px lines, legend for 2+ series plus direct labels, hover crosshair and tooltip, keyboard access, a table view, dark mode validated separately.

## Shared data files (books/eli-raz/site/)

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

Pipeline ownership (repo root): UI agent owns tools/build_web.py, tools/verify.py, site/*; the orchestrator owns kitshn.config.ts, .github/workflows/kitshn.yml, books/eli-raz/scripts/build_release.py and books/eli-raz/scripts/smoke_site.py; the EPUB/Kindle quality agent owns tools/ingest_pdf.py, tools/build_epub.py, tools/check_*.py, tools/calibre_view.py, tools/figure_sheets.py.

The UI agent makes tools/build_web.py read these files from the folder that holds enhancements.json, validate them (every element ID must exist in the EPUB), and render them.

## Report

Start only your final message with `FINAL REPORT`. List what you changed (file paths), what you verified and how, and what is still open. Any other message is interim.
