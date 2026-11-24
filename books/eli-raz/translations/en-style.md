# English translation style

Choices from the pilot (a03 by Amir Eidelman, a10 by Eli Raz). Use them for the rest of the book.
Files: site/translations/en/<unit>.json, built from work/translations/en/<unit>.txt with `uv run work/translations/build.py en <unit>`.

## Voice

- Keep each author's register. Eli: dry humour, long sentences with asides, Biblical echoes, a moral at the end. Eidelman: warm, personal, short tribute.
- Use natural literary British English (metres, centre, programme, practise as a verb). Keep the first person.
- Keep Hebrew irony and understatement as they are ("to put it mildly", "in my humble opinion"). Do not explain jokes, except for a pun on Eli's name (below).
- Render Biblical phrases with the King James Version: "hanging upon nothing" (Job 26:7, for "על בלימה"), "Arise, walk through the land" (Genesis 13:17), "Take ye therefore good heed unto yourselves" (Deuteronomy 4:15).
- Keep quotes in double quotes. Hebrew single quotes around a term ('המחבת') become double quotes ("the Frying Pan").
- "ז"ל" after names of the dead: "of blessed memory".

## Puns

- "רז" means "secret". When an author plays on Eli's name ("רזי (רז)"), write "secrets (raz)". Readers can find the name pun in this file.

## Names and transliteration

- Simple, readable transliteration, no diacritics: kh for ח only when it is the usual spelling, otherwise h; tz for צ in place names (Metzoke Dragot); no doubled letters for dagesh.
- Use the established English spelling when one exists: Ein Gedi, Sde Boker, Dead Sea Works, Society for the Protection of Nature in Israel, Ministry of Environmental Protection, Ben Gurion Airport, Home Front Command, Dushanbe, Jirgatal, Chamonix, Saint Petersburg, Agursky, Dov Litvinoff, Amir Eidelman.
- Brands and titles: Marlboro, "Egozi" chocolate bars, Ultrasol, "Masa Acher" (magazine), "First Home in the Homeland" (absorption programme), glasnost.
- Chapter titles of this book in quotes, translated: "A Friend from Another World", "Return to the Place You Came From". When a unit gets an English title later, check the cross-references against it.

## Mountaineering terms (a10)

| Hebrew | English |
|---|---|
| אלפיניזם | mountaineering |
| אלפיניסט | alpinist (Eli's word; keep it for the club members and Russian climbers) |
| מטפס | climber |
| סיראקים | seracs |
| קראוואס, בקיע | crevasse |
| המחבת | the Frying Pan |
| מחנה הבסיס באצ'יקטש | the base camp at Achik Tash |
| פיסגת לנין | Lenin Peak |
| רכס פאמיר | the Pamir range; "בפאמיר" = in the Pamirs |
| הסתגלות לגובה | acclimatization |
| מחלת הגובה | altitude sickness |
| גלישה בחבלים | abseiling |
| טיפוס צוקים | rock climbing |
| קשר (person) | radio operator |
| איתור נעדרים | search for missing persons; "the missing" |
| יצר הקיום | survival instinct |
| איתני הטבע | the forces of nature |

## Numbers, dates, units

- Dates: 13 July 1990; 15 September 2008. Times: "six in the evening" in prose.
- Units in prose: metres in full in narrative, "m" in brackets ((3,600 m)). Thousands with a comma.
- Keep every number as printed, even when it looks wrong. List doubts in the translation report.

## Markup

- Keep every tag of the source element in the same order (noterefs, page breaks, bold, links). build.py checks this and stops on a difference.
- Translate img alt text too.
- When the source has an empty or broken bold span (for example `<b>�</b>` from the PDF), keep an empty `<b></b>` in the same place.
