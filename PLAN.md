# Plan: careful translations in place of the quick ones

Goal: replace each quick bulk translation with a literary translation written paragraph by paragraph, with the whole book as context. No translation API or script translates text.

## Design

- Source: the release text, books/eli-raz/epub-src-release/OEBPS/text/*.xhtml (fresh release ingest of main).
- Working files stay as they are: translations/<lang>/<unit>.txt, built by translations/build.py into site/translations/<lang>/<unit>.json. build.py checks every ID and every tag.
- Each new file replaces the old file in place, in the same commit, so the site never lacks a translation.
- Each unit gets three passes: a full draft, a review against the source sentence by sentence, a read-aloud pass in the target language only. Only after the draft, compare with the old text.
- Label: translator "AI translation (Claude Opus 5.5) with the full book as context, not reviewed by a person". Site notes: he "תרגום בבינה מלאכותית, לא נבדק בידי אדם", en "AI translation, not reviewed by a person". In site/*, only these label strings change.
- Bible quotes in English: JPS 1917 (public domain). Terms: one term per concept, each choice and its reason in translations/eli-terms.md.

## Steps

1. Read the whole book and the inputs (style guides, glossary, places).
2. en/a03: Amir Eidelman's tribute, Hebrew to English.
3. en/a10: "The Pamir Disaster", Hebrew to English.
4. he/a06: "The Life Story of the Dead Sea", English to Hebrew.
5. errata-he.json: the Hebrew explanations of the 70 errata rows, from errata/errata.json.
6. Labels: build.py, errata-he.json, 85-languages.js, 35_errata.py, check_languages.py.
7. Docs: en-style.md, eli-terms.md, CONTENT-CHANGES.md, OPEN-POINTS.md, AGENTS-BRIEF.md.
8. PR text with samples and decisions; delete PLAN.md; ready; queue.
