# Maps lane: screenshots and measurements

Made by `books/eli-raz/scripts/check_maps.py` on 2026-11-24, on a local release build.

## Screenshots

- File names: `<phone|desktop>-<light|dark>-<map>.jpg`. Phone is 393 px with touch, desktop is 1280 px.
- The screenshots come from the build before these changes: the shared motion and radius tokens, and label placement without layout reads.
- Nothing visible changed after these screenshots, except corner radii.

## Measurements

- `perf-under-load.json`: gestures on a phone with the CPU slowed 4 times.
- These numbers are not valid. The machine had a load average of 20 to 38 on 4 cores, and runs of the same test differed by up to 5 times.
- Control test: a 20 px square that animates on the book page gets about 50 ms frames without throttling. On a blank page it gets 17 ms, also with 4 times throttling.
- In the trace, most main-thread time is PrePaint (about 160 ms per frame) and IntersectionObserver. Map scripts are a small part.
- The page has about 18,000 elements, so the cost is page-wide.

## Still to do

- Record the videos and the throttled trace again on the CI lane checks or on an idle machine.
