# Lighthouse lane

Goal: raise the Lighthouse scores of https://eli-raz.yarden-zamir.com (Performance, Accessibility, Best Practices, SEO) on mobile and desktop with real fixes.

## Design decisions

- Measure on GitHub, not on the build machine: `.github/workflows/lighthouse.yml`, a separate workflow, so it never blocks the merge queue.
- Lighthouse 13.6.0 (npm, 2026-10-27). Local server: `serve` 14.2.7 (gzip on the fly, close to the live brotli).
- Pages: home (`/`) and a long chapter deep link (`/#a34`), mobile and desktop, 3 runs each, median by Performance.
- SEO: `noindex, nofollow` stays on purpose.
- Do not edit files of open PRs (maps lane: 50-maps, 55-places, 75-map-figures, 90-offline, sw.js; explainers lane: 72/73-explorable).

## Steps

1. CI Lighthouse workflow with reports as artifacts and a job summary; record the baseline.
2. Hero image: responsive sizes, modern format, one fetch for backdrop and cover, fetchpriority.
3. Fonts and render-blocking CSS: no `@import` chain; WOFF2 fonts.
4. Below-the-fold images and other audits that the baseline reports.
5. Accessibility and Best Practices audits that the baseline reports.
