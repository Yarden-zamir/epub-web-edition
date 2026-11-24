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

## Shared design tokens

Use the tokens of `00-base.css`, never a literal value for the same purpose.

| Token | Value | For |
|---|---|---|
| `--radius-s` | 0.5rem | Inputs, chips, thumbnails, small tooltips |
| `--radius-m` | 0.875rem | Cards, popovers, dialogs, menus, sheets, video |
| `--radius-pill` | 999px | Pill buttons, toggles, round icon buttons |

- A part inside a rounded box with padding takes the outer radius minus the padding, so the corners stay concentric. For example, a row inside a `--radius-m` panel with 0.5rem padding uses `calc(var(--radius-m) - 0.5rem)`.
- Circles (dots) use 50%. Book photos have no radius.
- Motion: `--dur-quick` (140 ms, hover and press), `--dur-base` (220 ms, menus, popovers, fades), `--dur-slow` (340 ms, entrances), with `--ease-out` (most motion), `--ease-in-out` (moves between two places) or `--ease-spring` (pills and toggles). Animate transform and opacity only. Reduced motion sets the durations to 0. Entrance styles apply only under `html.motion` (set by `00-core.js`), so without the script everything shows in its final state. For "once when on screen", use `onVisible(el, fn)` from `00-core.js`; for "once when near", use `onNear(el, fn)`. Do not add your own observers or scroll listeners. Text that is already on screen never fades. `--dur-fast`, `--dur` and `--ease` are older names for the same tokens.
- Colours: `--paper`, `--ink`, `--soft`, `--muted`, `--rule`, `--mat`, `--accent`, `--night`, `--on-night`, `--on-night-soft`. Text needs 4.5:1, and large text or a control needs 3:1, in light and dark mode. Text over a photo or a map always gets a solid backing or a scrim.
- Focus: the global `:focus-visible` ring follows the element's own corners. Leave 4px of room around a focusable part inside a scroll or `overflow: hidden` box, so the ring is never cut. On dark ground the ring uses `--on-night`.

Motion:

| Token | Value | For |
|---|---|---|
| `--ease-out` | cubic-bezier(0.22, 1, 0.36, 1) | Things that enter or settle |
| `--ease-in-out` | cubic-bezier(0.65, 0, 0.35, 1) | Things that move from one place to another |
| `--dur-quick` | 140ms | Hover, press, small fades |
| `--dur-base` | 220ms | Popovers, dialogs, toggles |
| `--dur-slow` | 340ms | Larger moves, slides between images |

- Reduced motion sets every `--dur-*` to 0ms, so a transition that uses them respects it without its own media query.
- Script animations read the same tokens, for example `parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--dur-base"))`. A 0 ms Web Animation still resolves `finished`; a 0 ms CSS transition fires no `transitionend`, so do not wait for one.

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
- Land a change through a PR and the merge queue (skill `eli-raz-pr-flow`, docs/WORKFLOW.md). GitHub Actions runs `tools/verify.py`, the smoke and axe checks, explainers and videos; this machine runs only `uv run books/eli-raz/scripts/check.py` (light).
