# Plan: interactive explainers (feat/explorables)

Explainers inside three printed figures: sinkholes (fig-a14-07), the Dead Sea transform (fig-a18-05), Mount Sodom (fig-a34-17).
Data and sources: books/eli-raz/site/explorables/*.json. Code: site/features/72-75, tools/web/45_explorables.py.

## Decisions

- Drawings on canvas with cached bitmap layers; the transform moves pre-drawn layers by CSS transform only. Reason: SVG attribute changes cost style, pre-paint and layer work on this long page.
- Value line in fixed-width slots (tabular digits, isolated numbers); the explanation changes only when a move ends.
- Handles are 48 px HTML elements with touch-action none; the drawing keeps pan-y, so a swipe elsewhere scrolls.

## Steps

1. Canvas explainers, stable numbers, touch-safe handles, slow water motion (done, commits up to af409f0).
2. Sinkhole feedback: fresh groundwater shown as flowing streaks that wash the exposed salt and carry salt out; static arrows under reduced motion.
3. Sinkhole feedback: jagged, connected dissolution pockets from seeded noise that grow with the level drop; collapse cones above the deepest pockets.
4. Sinkhole feedback: the salt under the brine stays intact; a short label "מי תהום מתוקים ממיסים את המלח".
5. Review the explainer screenshots and videos from the checks; save the final ones under books/eli-raz/research/explorables/.
