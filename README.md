# Book rebuild: EPUB and web edition

Pipeline that turns a book into a reflowable EPUB 3 and a continuous web edition built from that EPUB.

This repository is private. It holds two editions:

- The synthetic sample edition at the root (`epub-src/`, `inventory/`, `originals/`). Its content is placeholder.
- The Eli Raz edition in `books/eli-raz/`, the real book "אלי רז חוקר הבולענים", live at https://eli-raz.yarden-zamir.com.
  See `books/eli-raz/AGENTS-BRIEF.md` for its build and rules.

Licences: the MIT licence in `LICENSE` covers the pipeline code and the sample edition only.
The Eli Raz book content is © its authors and photographers, all rights reserved; see `books/eli-raz/NOTICE.md`.
Before this repository goes public, its history needs a rewrite (`books/eli-raz/NOTICE.md` says why).

## Deploy

A push to `main` runs `.github/workflows/kitshn.yml`, which deploys both apps of `kitshn.config.ts` with kitshn:
the sample edition (`app`) and the Eli Raz edition (`book`, built by `books/eli-raz/scripts/build_release.py`).
The book deploys first. Three things keep a deploy short:
- kitshn uploads only files whose hash Cloudflare does not have yet, and both builds are byte-reproducible.
- The workflow keeps the last checked book build under the hash of everything the build reads. A push that changes none of it (for example only the sample) restores that build and skips the build and checks.
- `build_release.py` skips both PDF ingests when the hash of their inputs is unchanged (`INGEST_INPUTS`).

## Pipeline

```
source.pdf ──(recovery, not built yet)──▶ epub-src/ ──tools/build_epub.py──▶ dist/book.epub ──tools/build_web.py──▶ dist/web/
                                              ▲                                     │                        ▲
                                  inventory/ (page-by-page reconciliation)          └── canonical input ─────┘
                                                                         site/ (template, features/*.js and *.css, enhancements.json)
```

1. `epub-src/` holds the EPUB 3 source tree. It is the only editable book content.
2. `tools/build_epub.py` packs it into `dist/book.epub`. The output is byte-reproducible.
3. `tools/build_web.py` reads **only** `dist/book.epub`: container, OPF manifest and spine, nav, XHTML and assets. It writes one continuous static page to `dist/web/`.
4. `site/` adds web-only presentation and features. `site/enhancements.json` attaches features by stable element ID. The build fails if an ID does not exist in the EPUB.
5. `tools/verify.py` runs all checks and writes `dist/verify/report.json` and screenshots.

## Commands

```sh
uv run tools/build_epub.py   # epub-src/ -> dist/book.epub
uv run tools/build_web.py    # dist/book.epub -> dist/web/
uv run tools/verify.py       # build both, then run all checks
```

`verify.py` needs `.tools/` (local, not tracked): EPUBCheck 5.4.0, Temurin JRE 21, and axe-core 4.14.0.
It uses the cached Playwright Chromium build 1255.

## Stable IDs

IDs never change after first assignment. A new element gets a new ID. Do not renumber.

| Pattern | Element |
|---|---|
| `ch-NN`, `ch-NN-h` | Chapter section and its heading |
| `p-NN-NNN` | Paragraph in chapter NN |
| `fig-NN-NN` | Figure (image, caption, credit) |
| `tbl-NN-NN` | Table |
| `note-NN-NN`, `nref-NN-NN` | Footnote and its reference |
| `pg-N` | Print page marker. N is the source PDF page number |

## Inventory

- `inventory/source.json`: source PDF page count and checksum.
- `inventory/pages.csv`: one row per source page, with the EPUB IDs that hold its content, and a status (`verified`, `pending` or `ambiguous`).
- `inventory/assets.csv`: one row per image. It records the EPUB file, the unmodified original, both checksums, the source page, the derivation, and the credit line as printed.
- `inventory/issues.csv`: OCR doubts, reading-order questions and intentional changes.

The whole-book reconciliation is complete only when `source.json` is not synthetic, all pages are `verified`, and no issue is open. `verify.py` reports this as `OPEN` or `DONE`.

## Decisions

- Page markers use `title`, not `aria-label`. axe-core 4.14.0 rejects `aria-label` on `doc-pagebreak`.
- EPUB CSS sets no `direction`. EPUB forbids it. Direction comes from `dir` attributes only.
- Book font: Noto Serif Hebrew 2.004, static TTF, SIL OFL. Kindle handles variable fonts poorly. Replace with the fonts from the recovered bundle if their licence allows embedding.
- Site-only originals (`originals/`) are full-resolution files. The EPUB carries 1600 px derivatives.
- The web page has `noindex`, because the content is placeholder.
- The site is an editorial page, not an e-reader. Its hero uses the EPUB title, author, description and cover image.
- The Kindle download is the canonical `dist/book.epub`, copied byte for byte. Send to Kindle accepts EPUB.
- The site hides the EPUB cover page, title page and in-book contents list, because the hero and the "פרקים" panel show the same content.
- The build moves the EPUB copyright-page section into the site footer.
- Photos run full width and pan with scroll. Artwork is never cropped; it shows whole on a mat.
- Motion uses CSS scroll-driven animations. Browsers without support, and readers who ask for reduced motion, get a static page.

## Deploy

`kitshn.config.ts` deploys `dist/web/` as a static site with kitshn 2 on each push to `main`.
Each pull request gets a preview.
