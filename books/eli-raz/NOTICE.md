# Notice: rights in books/eli-raz

The MIT licence in the root `LICENSE` file covers only the pipeline code (`tools/`, `site/`) and the synthetic sample edition. It does not cover this folder's book content.

## The book

- The book "אלי רז חוקר הבולענים" is © its authors, its editor and its photographers. All rights reserved. The title page names them (source PDF pages 5-7).
- This covers the book text, the images, the source PDF (`source/source.pdf`) and every file derived from them: the EPUB, the web edition, `inventory*/`, `ids.csv`, `errata/print-check/*.png`, `translations/` and `site/translations/`.
- The edition is published with the permission of the Raz family. `PERMISSIONS.md` records the grant and its scope (a public web edition and a free EPUB download).
- No other use is granted. Do not copy or reuse this content outside this edition.

## Third-party images and data

- Images and data from other sources keep their own licences. Each one carries its credit and licence next to the image in both editions.
- The list of these changes and credits is in `CONTENT-CHANGES.md`: section 2 (image changes and credits, from `book.toml` `[release]`) and section 4 (web additions). The licence links are in `book.toml` `[[release.credit]]`, `content-data/attribution.md` and the `attribution` and `source` fields of `site/figure-maps/*.json`, `site/charts/*.json` and `site/then-now.json`.
- Maps drawn for this edition (`replacements/`, `scripts/*map*.py`) use OpenStreetMap data (© OpenStreetMap contributors, ODbL), Natural Earth (public domain) and Copernicus DEM. Each map carries a short credit, and the edition note under it holds the full wording (`content-data/attribution.md`).

## The source PDF and the release edition

The repo holds the printed book as `source/source.pdf`, in its files and its history, by the decision of the family's representative (2026-11-24). It includes the print images that the release edition withholds or replaces (`book.toml` `[release]`: p066-x251, p183-x717, p301-x1169, p302-x1173); the rights of those images stay with their holders. The public web edition and EPUB are the release edition.
