# Plan: source citations as links (feat/source-refs)

Goal: the book's citations of its source list (sources.xhtml, entries 1-88, one global numbering) are links, in the EPUB and on the web, made in the ingest.

Found (cached release ingest of main):
- Only a16 has the note "המספרים בסוגריים מפנים אל המקורות בסוף הספר" and number citations "(17)". The other 9 starred notes (a10, a11, a17, a18, a28, a30, a31, a32, a35) are provenance notes ("פורסם ב…"). They stay.
- a17 numbers (1)-(68) cite the bibliography of the original Cathedra 101 article. That list is not in this book: no links.
- a07, a14, a15, a16 (captions), a18, a34, a35, a36 cite the same list by author and year ("(Masterman, 1913)"). Each chapter has its own section of the list.

Steps:
1. book.toml [[source_ref]] (element, text, source) and [[page_ref]] (element, text, target); ingest links each one, adds src-N IDs and back links on the source entries, crashes on an unknown entry or a text that does not occur once.
2. Remove the a16 note and its star; edition note in the list of edition changes.
3. Bibliography: one role for all small print, so entry 86 is one paragraph (sources-p094 joins sources-p093).
4. Web: citation popover with the full source (site/features/70-popovers.js, minimal).
5. CONTENT-CHANGES.md; count check; PR text with before and after of a16 and a35.
