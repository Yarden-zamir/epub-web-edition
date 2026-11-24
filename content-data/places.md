# Content data notes (places, timeline, glossary, crosslinks)

Owner: content-data agent, 2026-11-24. Files: site/places.json, site/timeline.json, site/glossary.json, site/crosslinks.json.

## How the data was made

- Text: work/content-data/text/*.txt, a dump of every element ID and its text from epub-src-release/OEBPS/text (scratchpad script, same logic as the checker).
- Wikidata: scripts/wd_fetch.py, one request at a time, 1.5 s pause, back-off on HTTP 429 and 5xx. Raw responses are in wikidata-raw/<query>/response.json.
- scripts/build_places.py builds site/places.json. Coordinates come only from the saved P625 values.
- scripts/check_content_data.py checks all four files against the EPUB source. Run it from the content repo root. Last run: 0 errors.

## Places: verification

Each place has a Wikidata item. For each one I read the label, description and coordinates, and checked them against the book text.

| Place | Item | Note |
|---|---|---|
| חורבת מזין | Q6632565 | Hebrew label is "מצד קדרון", English label "Khirbet Mazin". Same site; the book uses "חורבת מזין". |
| נחל דרגה | Q2906907 | English label "Wadi Murabba'at". Hebrew aliases include "דרג'ה", the name in a11-p012. |
| ואדי רושמיה | Q4024328 | Label "נחל גיבורים". Hebrew alias "ואדי רושמיה". |
| נווה עין גדי | Q25489001 | The item is the archaeological site and oasis. The targets also include the sinkhole paragraphs about the Ein Gedi tourist complex (a14-p015, a14-p017, a14-p051), because no item for that complex exists. |
| פסגת לנין | Q838587 | Far from the Dead Sea. The entry has an extra key `"far": true` so that the map can show it apart from the others. |

Items with more than one P625 value. I chose the value that is nearest to the part of the place that the book describes:

- נחל דוד Q2538747: first value (31.4724, 35.3815), the oasis section. The second value is the mouth.
- נחל צאלים Q1138730: second value (31.3472, 35.3986), near the shore and the borehole in a14-p013.
- המקדש הכלקוליתי Q2900794: first value (31.468, 35.3892).
- בקעת תמנע Q1973199: first value (29.7878, 34.9889).
- ואדי רושמיה Q4024328: first value (32.7997, 35.005).

## Places I could not verify (not in places.json)

- ואדי אל-הידאן (a27-p020 to a27-p034, fig-a27-03, fig-a27-04). The only item is Q16126371: Arabic Wikipedia only, no label, no coordinates.
- ואדי זרקא מעין (a25-p016, a27-p041 to a27-p051, fig-a27-05). No item for the wadi. Q33776065 is a residential area (rejected). Q6720622 "Ma'in Hot Springs" is the hot springs at the head of the wadi, not the wadi itself. Add it only if a springs entry is wanted.
- The Ein Gedi tourist complex, the site of the first sinkhole in 1990 and of the 1997 accident (a14-p015, a14-p019). The book does not name it. Q5349577 "Ein Gedi Spa" is a different place. The book mentions "מרחצאות עין גדי" only in the caption of fig-a32-02.
- Ailefroide, Holyhead, Skye (a09). The chapters only pass through these places, so I did not add them.

## Text discrepancies found (book text not changed)

- Lartet on the Lisan peninsula: 1869 in a34-p007, but 1864 (with the de Luynes expedition) in a07-p021.
- Arugot flood: "2 במאי 2001" in a31-p006 and a31-p007, but "בשלושה במאי" in a31-p002 and "ה-3 במאי" in a31-p007. The timeline uses "מאי 2001" (a14-p024) for this reason.
- The chapter names quoted in cross-references are not always exact: a10-p003 "חזור למקום ממנו באת" (heading: "חזור למדבר ממנו באת"), a14-p008 "מורל ועט ונייר טואלט", a27-p039 "סלע אדום" (heading: "סלע אֱדום"), a36-p063 "האקולוגיה של ים המלח" (heading: "המערכת האקולוגית של ים המלח"). The links use the printed text as it is.
- a10-p002 gives the height of the "המחבת" camp as 3,005 m. I kept this out of the places description.

## Timeline: choices

- The task brief mentions "Ein Gedi field school 1966". The text (a08-p006) says that Neri Arieli and Amatzia Shochat graduated from the field school in 1966, not Eli. The event says so.
- "Etan unit 1982" (a08-p007): the 1982 acceptance committee was for the Ein Gedi members. a08-p002 says that Eli joined the unit earlier, after the Yom Kippur War, but gives no year.
- The sinkhole night: the quote is from a13-p006 ("בערב סוכות שנת 2003"). The exact date 10.10.2003 comes from a22-p017, recorded in the extra key `date_source`.
- Events with no date in the text, left out: Eli's arrival as manager of the field school ("אחרי מלחמת יום הכיפורים", a22-p002), the civilian rescue unit ("במחצית שנות השבעים", a08-p006), the skeleton fragment found "שנה אחר כך" (a12-p011).
- I converted the Hebrew dates in a12-p014 (אדר תשמ"ד) to the year 1984. a12-p010 already gives 1982 next to כסלו תשמ"ג.

## Glossary: choices

- "forms" holds only forms that occur in the book; the checker enforces this. A renderer that matches whole words will not link "מבצר" to "בצר".
- Terms that the book uses but does not explain are left out: ארגוניט, מצוק ההעתקים, כוח קוריוליס, מערכת חורפית, המוביל ההפוך.
