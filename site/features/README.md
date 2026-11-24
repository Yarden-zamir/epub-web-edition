# Site features

Each web feature lives in its own files. The build finds them by name. No shared list names the features, so a new feature adds files and edits no shared line.

## Files of one feature

| Part | Path | Build step |
|---|---|---|
| Script | `site/features/NN-name.js` | Joined in file name order into `reader.js` (one classic script). |
| Styles | `site/features/NN-name.css` | Joined in file name order into `reader.css`. |
| Build module | `tools/web/NN_name.py` | Loaded in file name order by `tools/build_web.py`, fresh for each build. |

- `NN` sets the order. Scripts run top to bottom, and later styles win ties in the cascade. The JS and CSS numbers of one feature can differ: each file type keeps its own order.
- `00-core.js` holds the shared parts: `byId`, history, `goTo`, `highlight`, overlays (`openOverlay`, `overlayClosed`). `00-base.css`, `01-nav.css`, `02-book.css` and `03-panels.css` hold tokens, base, bar, hero, book and panel styles.
- All scripts share one top-level scope. Do not reuse a top-level name of another feature.

## Build module hooks

A module defines any of these functions. Each one receives `site` (`build_web.Site`: `book`, `conv`, `out`, `data_dir`, `enhancements_file`, `thumbs`, `report`).

| Hook | When | Use |
|---|---|---|
| `load(site)` | After the EPUB loads, before conversion | Read and check site data. Raise `BookError` (or `missing_id` for an unknown element ID). |
| `transform(site, body, top, kind)` | For each spine document, after core conversion | Change the document tree: wrap text, add attributes, insert elements. |
| `after_contents(site)` | After all documents convert | Return HTML that sits right after the printed contents. |
| `values(site)` | Before the page is filled | Return `{marker: html}` for `{{marker}}` in `site/index.html`. `head` and `end` take parts from several features. Other markers belong to one feature. |
| `write(site)` | After `index.html` is written | Write extra files. Add keys to `site.report` (`build.json`). |

- Keep module state in module globals. The build loads each module again for each build.
- Shared helpers stay in `tools/build_web.py`: `BookError`, `missing_id`, `clean_text`, `text_slots`, `wrap_text`, `write_csv`, `Thumbs`, `title_and_byline`.
- A change to core is needed only when a feature cannot work through these hooks and the `head` and `end` slots.

## Check a change

- A refactor must keep the built site byte-identical. Hash every file of a sample and a release build before and after the change, and compare.
- Before each push, run `uv run tools/verify.py` and `uv run books/eli-raz/scripts/build_release.py`. The second one includes the smoke test.
