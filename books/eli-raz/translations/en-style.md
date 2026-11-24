# English translation style

Rules for the English units: a03 (Amir Eidelman) and a10 (Eli Raz), written again with care on 2026-11-24. Use them for the rest of the book.
Files: site/translations/en/<unit>.json, built from translations/en/<unit>.txt with `uv run books/eli-raz/translations/build.py en <unit>`.
Term choices and their reasons, for both languages: eli-terms.md.

## Voice

- Keep each author's register. Eli: dry humour, long sentences with asides, Biblical echoes, a moral at the end. Eidelman: warm, personal, short tribute.
- Use natural literary British English (metres, centre, programme, practise as a verb). Keep the first person.
- Keep Hebrew irony and understatement as they are ("to put it mildly", "in my humble opinion"). Do not explain jokes, except for a pun on Eli's name (below).
- Quote the Bible from JPS 1917: The Holy Scriptures According to the Masoretic Text, A New Translation (Jewish Publication Society, 1917), public domain. Text checked on Sefaria, version "The Holy Scriptures: A New Translation (JPS 1917)". Verses used: "Arise, walk through the land" (Genesis 13:17), "Take ye therefore good heed unto yourselves" (Deuteronomy 4:15). Echoes in Eli's Hebrew take the JPS words too: "hanging over nothing" for "על בלימה" (Job 26:7), "joyful and glad of heart" for "שמחים וטובי לב" (1 Kings 8:66), "the vineyards of Ein Gedi" for "כרמי עין גדי" (Song of Songs 1:14, with the modern spelling of the place).
- Keep quotes in double quotes. Hebrew single quotes around a term ('המחבת') become double quotes ("the Frying Pan").
- "ז"ל" after names of the dead: "of blessed memory".
- No word that the source does not have: no gloss, no explanation. The exceptions are in eli-terms.md, each with its reason.

## Puns

- "רז" means "secret". When an author plays on Eli's name ("רזי (רז)"), write "secrets (raz)". Readers can find the name pun in this file.

## Names and transliteration

- Simple, readable transliteration, no diacritics: kh for ח only when it is the usual spelling, otherwise h; tz for צ in place names (Metzoke Dragot); no doubled letters for dagesh, except in a given name with a usual English spelling (Benny, Danny, Bella).
- Use the established English spelling when one exists, and the English Wikidata label for places: Ein Gedi, Sde Boker, Judaean Desert, Tamar Regional Council, Dead Sea Works, Society for the Protection of Nature in Israel, Ministry of Environmental Protection, Ben Gurion Airport, Home Front Command, Dushanbe, Jirgatal, Alay Valley, Trans-Alay Range, Lenin Peak, Chamonix, Zurich, Saint Petersburg, Agursky, Dov Litvinoff, Amir Eidelman. Achik Tash has no Wikidata item.
- People of a10 without a known English spelling, transliterated: Benny Agur, Dov Meli, Gabi Manobla (as in errata/errata.json), Yuki Pereg, Ze'ev Manobla, Bella, Dima, Shai, Alon, Danny, Doron, Sharon Kligman, Noam Sinai, Moshe Gilad.
- Brands and titles: Marlboro, "Egozi" chocolate bars, Ultrasol, "Masa Acher" (magazine), "First Home in the Homeland" (absorption programme), glasnost.
- Chapter titles of this book in quotes, translated: "A Friend from Another World", "Return to the Place You Came From". A cross-reference keeps the title as the citing text prints it (a10-p003 prints 'חזור למקום ממנו באת', the chapter itself is "חזור למדבר ממנו באת"; errata row 29). When a unit gets an English title later, check the cross-references against it.

## Numbers, dates, units

- Dates: 13 July 1990; 15 September 2008. Times: "six in the evening" in prose.
- Units in prose: metres in full in narrative, "m" in brackets ((3,600 m)). Thousands with a comma. A Hebrew range "100-50" is "50–100".
- Keep every number as printed, even when it looks wrong. List doubts in the translation report.

## Markup

- Keep every tag of the source element in the same order (noterefs, page breaks, bold, links, edition corrections). build.py checks this and stops on a difference.
- Translate img alt text and figure captions, also the edition notes of this edition (for example the map note of fig-a10-02). Keep text in lang="en" spans as it is.
- Translate the edition correction notes (corr…) too; their printed form stays in Hebrew.
- When the source has an empty or broken bold span (for example `<b>�</b>` from the PDF), keep an empty `<b></b>` in the same place.
