# Test speed (2026-11-24)

Live-build agent. Local numbers come from the build machine: 4 cores, load average 20 to 35 while six lanes ran Playwright, EPUBCheck and ffmpeg. They vary by a factor of two from run to run. CI numbers come from `ubuntu-latest` (2 vCPU, private repo).

## Before

Each lane ran `build_release.py` (the full chain) before every push. UI lanes also ran `tools/verify.py`.

Local, cold, one run (load 16 to 26):

| Step | Time |
|---|---|
| Complete ingest | 111 s |
| Release ingest (after the complete one) | 156 s |
| build_epub | 13 s |
| build_web | 30 s |
| check_release | 6 s |
| EPUBCheck and smoke test, in parallel | up to 232 s |
| Total | 551 s |

The old smoke test (six fresh loads, axe on the whole 546,000 px page) alone: 171 s with the six pages in parallel, 311 s one after another (load about 14). Each axe run costs 11 to 25 s even on CI: axe hit-tests every text node against the whole page.

CI, main, per push (book job, then deploy): 117 to 185 s in total. Ingests 12 to 13 s each when their inputs changed, EPUBCheck and smoke 21 to 37 s, job overhead about 30 s, deploy job 41 to 53 s.

Before, by kind of change (local):

| Change | What ran | Local |
|---|---|---|
| Site feature CSS or JS | build, check_release, EPUBCheck, full smoke (+ verify.py) | about 220 to 360 s |
| A build_web module | same | about 220 to 360 s |
| Book data JSON not read by ingest (places, charts, maps) | same | about 220 to 360 s |
| book.toml, ingest code, book.css, replacements, ingest-read JSON | both ingests in every worktree, then the rest | about 550 s |

## After

Heavy checks run in GitHub Actions only (`.github/workflows/checks.yml` on `lane/<name>`, the deploy gate on main, a nightly run). This machine runs the light default.

Local, `uv run books/eli-raz/scripts/check.py` (load 24 to 31):

| Step | Time |
|---|---|
| Ingest outputs from the shared cache ~/.cache/eli-raz/ingest | about 1 s |
| build_epub | 5 to 8 s |
| build_web | 16 to 31 s |
| check_release | 3 to 6 s |
| preview.html | under 1 s |
| Total | 36 to 41 s |

The same for every kind of change in the table above: the default runs no ingest, no EPUBCheck and no browser. When ingest inputs changed, the local build uses the last ingest, and CI ingests the change. `--ingest` runs both ingests in parallel (176 s at load 31 instead of 267 s in turn), once per input hash on the machine; every other worktree then reuses it.

Measured while building the change (local, load 21 to 35):

- Quick smoke (`--smoke`: one load per device class, axe on a sample): 38 to 108 s; first run 241 s, because it checks every section once to fill the cache of passed sections.
- axe on a sample part costs 4 to 10 times less after the other book parts leave the page (colour contrast on chapter a06: 14 s on the whole page, 2.3 s on a 31,882 px page).
- Two builds from the same inputs are byte-identical, so the ingest cache and the EPUBCheck pass cache (by EPUB bytes) skip work without changing results. The parallel ingest gives the same EPUB bytes as the two ingests in turn (sha256 cb394020…).

CI after the change: see "CI after" below, filled from the first lane and main runs.

## Decisions

- Hash keys, not path rules: ingest reads four site JSON files and pages.csv, so "data JSON skips ingest" holds only for the other data files. The INGEST_INPUTS hash decides.
- The complete ingest runs in a copy of INGEST_INPUTS, so the two ingests run in parallel without racing on ids.csv. `--compare-ingest` also runs it in a copy of the whole book folder and fails when the outputs differ. That found one missing input (inventory/pages.csv) while this change was built.
- Known limit: the quick smoke test checks a CSS or JS change on the sample parts only. The lane run (`--axe-full`) and the nightly run check the whole page.

## CI after

| Run | Change | Push to done | Notes |
|---|---|---|---|
