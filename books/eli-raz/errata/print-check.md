# Print check of the errata list

Test agent, 2026-11-24. This file checks that each entry of [ERRATA.md](ERRATA.md) quotes the printed book, not a fault of our PDF conversion.

## Method

1. `errata/print-check/entries.py` reads all 70 entries of ERRATA.md: rows 1-67 from the tables, and rows 68-70 from the "Not print errors" bullets, in list order.
2. `errata/print-check/crop.py` finds each quote on its stated PDF page with PyMuPDF 1.28.2. It groups words into printed lines by vertical position and scores each line by the quote words it holds. It renders that line with one line of context at 350 dpi to `errata/print-check/<row>.png`. A row with several quotes stacks its crops, with a gray bar between them.
3. A person (this agent) looked at every crop. Where single characters decide the verdict, a 700 dpi close-up is in `<row>-zoom.png` (rows 31, 33, 68), and the PDF glyphs were read with their positions.
4. `errata/print-check/checks.toml` holds the verdicts, the notes and the plain explanations. `errata/print-check/build.py` writes this table and `errata/errata.json`.

Rebuild from the content repo root:

```
uv run errata/print-check/crop.py
uv run errata/print-check/build.py
```

Verdicts:

- **in print**: the crop shows the quoted text. Differences of line breaks and of the dash glyph do not count (see below).
- **conversion error**: the print differs from our text. The quote is an extraction fault.
- **unclear**: the crop does not decide.

## Result

- in print: 68
- conversion error: 2 (rows 33 and 68)
- unclear: 0

### Conversion errors

- **Row 33** (a17-src1, page 145). Print: "פורסם בקתדרה 101, 2002." Our text: "פורסם בקתדרה 2002,101." The conversion reverses the two numbers and drops the space. The year 2002 is in print, so the editor question (Cathedra 101 is dated October 2001) stays open. The release text needs a fix for the number order.
- **Row 68** (sources-p060, page 311). In print, entry 54 starts its own line: "54. Ehrenberg, C.G. מובא אצל אורן, א., (2008). חיים בים־המלח – עבר, הווה ועתיד. מלח הארץ 3, הוצ' מגנס, האוניברסיטה העברית בירושלים, עמ' 72." Our sources-p060 merges entries 53 and 54 and puts "54." in the middle. The print gives no year for Ehrenberg; it cites him through Oren 2008. So "Ehrenberg 1848 lost its data" in ERRATA.md is not a print fault.

### Other findings

- **Row 31** is in print, not a conversion fault. The PDF prints "(7373 מ״ר)": the four digits sit edge to edge (each 5.28 pt wide), with no gap and no unmapped glyph between them. The "×" was lost before the PDF was made.
- **Rows 69 and 70** are print faults, not conversion faults. The print itself has the broken entry "30. C. B., Smith, N. G.,Ben-Yosef, E., Robinson", and entry 39 (Weinberger and Begin) has no year in print.
- **Row 49**: a36-p063 prints "(Steinhorn 1983)" without the comma that ERRATA.md quotes. Our text agrees with the print.
- **Row 61**: a17-p036 (page 156) prints "(539–555 לפנה״ס)", the years in the other order from a17-p010. Our text agrees with the print in both places.
- **Row 52**: the print sets the minus sign directly left of the digits ("428–", "394–"). Our text has a space between the number and the sign. The numbers agree.
- The Hebrew font draws the hyphen (U+002D, as the PDF text layer stores it) like a dash, for example "ה–3" in row 8. This is a glyph shape, not a different character.
- Our text writes a prefix, a hyphen and a number with a space after the hyphen ("במאה ה- 14", about 140 places in the release text). The print sets them without that space: on page 185 the hyphen glyph touches both "ה" and "14". Only the space differs, so these rows count as "in print". This is a systematic spacing difference for the EPUB agent to decide on.
- In right-to-left lines, a number range such as "14-13" (row 9) displays as the print shows it. The logical order of our text matches the print.

## Table

`errata/errata.json` has the same rows for the web errata page. In that file, `element` is the Element cell of ERRATA.md (comma-separated when the entry has several), `pdf_page` is always a list, and `printed` is the printed text (the ERRATA.md quotes joined with " / ", or the corrected print text for a conversion error). An `evidence` entry with `"url": null` is a citation without a link.

<!-- table -->

| Row | Element | Page | Quoted printed text (ERRATA.md) | What the image shows | Verdict | Crop |
|---|---|---|---|---|---|---|
| 1 | a06-p022 | 29 | `(2:23, KJV)` | The quoted text, unchanged. | in print | [1.png](print-check/1.png) |
| 2 | a06-p022 | 29 | `shalt though season` | The quoted text, unchanged. | in print | [2.png](print-check/2.png) |
| 3 | a06-p021 | 26 | `salts form any other source` | The quoted text, unchanged. | in print | [3.png](print-check/3.png) |
| 4 | a06-p023 | 29 | `south of Hebron` | The quoted text, unchanged. | in print | [4.png](print-check/4.png) |
| 5 | a06-p030 | 33 | `For 3,300 years` | The quoted text, unchanged. | in print | [5.png](print-check/5.png) |
| 6 | a06-fn15 | 29 | `n. 173.` | The quoted text, unchanged. | in print | [6.png](print-check/6.png) |
| 7 | a31-p002 | 245 | `מבול בשלושה במאי` | "מבול בשלושה" at the end of one line and "במאי" at the start of the next. | in print | [7.png](print-check/7.png) |
| 8 | a31-p007 | 247 | `של ה-3 במאי` | "של ה–3 במאי". The dash is the Hebrew font's hyphen; the PDF text layer stores U+002D. | in print | [8.png](print-check/8.png) |
| 9 | a31-p007 | 247 | `דברים יד, 14-13` | "דברים יד, 13–14:" (read right to left). The text layer stores "14-13", which displays the same way in a right-to-left line. | in print | [9.png](print-check/9.png) |
| 10 | a10-p003 | 66 | `'מועדון האלפיני הישראל'` | The quoted text, unchanged. | in print | [10.png](print-check/10.png) |
| 11 | a09-p023 | 61 | `בן אוויס` | "בן אוויס 1345 מ׳". | in print | [11.png](print-check/11.png) |
| 12 | a13-p058 | 103 | `שבאינדוזיה` | The quoted text, unchanged. | in print | [12.png](print-check/12.png) |
| 13 | a19-p009 | 185 | `במאה ה- 14` | The quoted text, unchanged. | in print | [13.png](print-check/13.png) |
| 14 | a17-p009 | 146 | `אברהם מוסיל` | The quoted text, unchanged. | in print | [14.png](print-check/14.png) |
| 15 | a18-p063 | 181 | `בחפירות רבת א-נחאס` | The quoted text, unchanged. | in print | [15.png](print-check/15.png) |
| 16 | a35-p058 | 286 | `(Bodaker et al., 2000)` | The quoted text, unchanged. | in print | [16.png](print-check/16.png) |
| 17 | sources-p069 | 311 | `pp. 31–41` | The quoted text, unchanged. | in print | [17.png](print-check/17.png) |
| 18 | sources-p024 | 309 | `תרח"ץ` | The quoted text, unchanged. | in print | [18.png](print-check/18.png) |
| 19 | sources-p047 | 310 | `Geological Society of America Bulletin, v.116,pp. 555–571` | The quoted text, unchanged. | in print | [19.png](print-check/19.png) |
| 20 | a36-p053 | 303 | `לכמיליון עד סוף העשור` | The quoted text, unchanged. | in print | [20.png](print-check/20.png) |
| 21 | a35-p070 | 288 | `(Coyn & Bellier` | The quoted text, unchanged. | in print | [21.png](print-check/21.png) |
| 22 | sources-p060 | 311 | `Coyn and Bellier` | The quoted text, unchanged. | in print | [22.png](print-check/22.png) |
| 23 | a10-p012 | 68 | `בני, דב, גדי ויוקי` | "בני, דב," at the end of one line and "גדי ויוקי" at the start of the next. | in print | [23.png](print-check/23.png) |
| 24 | a10-p020 | 69 | `באסון רעידת אדמה שהתרחש בתורכיה זמן מה קודם לכן` | The quote wraps over two lines. | in print | [24.png](print-check/24.png) |
| 25 | a09-p014, a10-p037 | 59, 76 | `באוגוסט 1981` / `ב- 1982, אי שם באלפים הצרפתיים` | The quoted text, unchanged. | in print | [25.png](print-check/25.png) |
| 26 | a10-p002 | 65 | `בגובה 3,005 מטר` | The quoted text, unchanged. | in print | [26.png](print-check/26.png) |
| 27 | a06-p027 | 30 | `the Jewish World Zionist Organization appointed a scientific delegation, headed by … Blanckenhorn` | The quote wraps over two lines; the "…" stands for "German geologist Max". | in print | [27.png](print-check/27.png) |
| 28 | a34-p007 | 261 | `עבד בחצי אי הלשון בשנת 1869` | The quoted text, unchanged. | in print | [28.png](print-check/28.png) |
| 29 | a10-p003 | 66 | `'חזור למקום ממנו באת'` | The quoted text, unchanged. | in print | [29.png](print-check/29.png) |
| 30 | a36-p063 | 305 | `'האקולוגיה של ים המלח'` | The quoted text, unchanged. | in print | [30.png](print-check/30.png) |
| 31 | a18-p041 | 177 | `(7373 מ"ר)` | "(7373 מ״ר)". The four digits sit edge to edge (each 5.28 pt wide, no gap), and the text layer holds no unmapped glyph between them. The "×" is missing in the print itself, not in our conversion. | in print | [31.png](print-check/31.png), [31-zoom.png](print-check/31-zoom.png) |
| 32 | a17-p015 | 150 | `מקדים בכמאה שנה את אמציהו` | The quoted text, unchanged. | in print | [32.png](print-check/32.png) |
| 33 | a17-src1 | 145 | `פורסם בקתדרה 2002,101` | "פורסם בקתדרה 101, 2002." The text layer stores ",101" to the right of ".2002"; our text reverses the two numbers and drops the space ("2002,101"). The year 2002 is printed, so the question about the year stays open. | conversion error | [33.png](print-check/33.png), [33-zoom.png](print-check/33-zoom.png) |
| 34 | a17-p004, a18-p002 | 145, 167 | `19 ק"מ מזרחית לחצבה` / `כ- 28 ק"מ ממזרח לחצבה` | The quoted text, unchanged. | in print | [34.png](print-check/34.png) |
| 35 | a17-p004 | 145 | `5 ק"מ מצפון-מזרח לכפר בוצירה` | The quoted text, unchanged. | in print | [35.png](print-check/35.png) |
| 36 | a15-p029 | 132 | `הקמת הקיבוץ בשנות ה- 60` | The quoted text, unchanged. | in print | [36.png](print-check/36.png) |
| 37 | a08-p003 | 53 | `עמרם מצנע, אלוף פיקוד מרכז דאז` | The quoted text, unchanged. | in print | [37.png](print-check/37.png) |
| 38 | a04-p004 | 15 | `1958: מצעד יום העצמאות בחיפה` | The quoted text, unchanged. | in print | [38.png](print-check/38.png) |
| 39 | a06-p025 | 31 | `For the first and last time, the Degania Dam gates were opened` | The quoted text, unchanged. | in print | [39.png](print-check/39.png) |
| 40 | a35-p052 | 285 | `400 אלף תאי דונליאלה` | The quoted text, unchanged. | in print | [40.png](print-check/40.png) |
| 41 | sources-p055, sources-p091 | 310, 312 | `Letters to T. Herzl, 1809-1901` | The quoted text, unchanged. | in print | [41.png](print-check/41.png) |
| 42 | a35-p073 | 289 | `בשנת 1994 פסק בית המשפט בקליפורניה` | The quoted text, unchanged. | in print | [42.png](print-check/42.png) |
| 43 | a34-p046 | 272 | `(259 מ' במרץ 2026)` | The quoted text, unchanged. | in print | [43.png](print-check/43.png) |
| 44 | a36-p073 | 307 | `הוגש לשותפות ב- 2021` | The quoted text, unchanged. | in print | [44.png](print-check/44.png) |
| 45 | a36-p045, a36-p046 | 300, 301 | `נחתם בנובמבר 2021` / `ב- 2019, בטרם יבש הדיו` | The quoted text, unchanged. | in print | [45.png](print-check/45.png) |
| 46 | a36-p033 | 297 | `ב- 2015, בעקבות מזכר הבנות` | The quoted text, unchanged. | in print | [46.png](print-check/46.png) |
| 47 | a36-p068, a36-p075 | 306, 307 | `2020` | Page 306: "מסמך מדיניות ארוכת טווח (2020)". Page 307: "ארוכת טווח' מינואר 2020". | in print | [47.png](print-check/47.png) |
| 48 | sources-p063 | 311 | `Harza JRV Group (1997)` | The quoted text, unchanged. | in print | [48.png](print-check/48.png) |
| 49 | a35-p006, a36-p063 | 276, 305 | `Steinhorn, 1983` | Page 276 (a35-p006): "(Steinhorn, 1983)". Page 305 (a36-p063): "(Steinhorn 1983)", without the comma; our text agrees with the print there. | in print | [49.png](print-check/49.png) |
| 50 | a36-p006 | 292 | `כיהן בשנים 1950 עד 1955 כמרצה בטכניון` | "כיהן בשנים 1950" at the end of one line and "עד 1955 כמרצה בטכניון" at the start of the next. | in print | [50.png](print-check/50.png) |
| 51 | a06-fn24 | 35 | `6 (October 2009), pp. 1–11` | The quoted text, unchanged. | in print | [51.png](print-check/51.png) |
| 52 | a07-p018 | 46 | `428 −` / `394 −` | "הגובה הוא 428–." and "לינטש: 394– מטרים": the minus sign (U+2212) prints directly left of the digits. Our text has a space between the number and the minus sign; the numbers and signs agree. | in print | [52.png](print-check/52.png) |
| 53 | a18-p003 | 167 | `מחדש ב- 1907` | The quoted text, unchanged. | in print | [53.png](print-check/53.png) |
| 54 | a34-p039 | 270 | `הגדולה שבהן הוא 5.7 ק"מ` | "הגדולה" at the end of one line and "שבהן הוא 5.7 ק״מ" at the start of the next. | in print | [54.png](print-check/54.png) |
| 55 | a35-p034 | 281 | `(Buchalo et al., 2000)` | The quoted text, unchanged. | in print | [55.png](print-check/55.png) |
| 56 | a20-p002 | 189 | `אוזרח בשנת 1977` | The quoted text, unchanged. | in print | [56.png](print-check/56.png) |
| 57 | a10-p002 | 65 | `(7,200 מטר)` | The quoted text, unchanged. | in print | [57.png](print-check/57.png) |
| 58 | a10-p002 | 65 | `כחמישים מטפסים` | The quoted text, unchanged. | in print | [58.png](print-check/58.png) |
| 59 | a14-p008 | 110 | `'מורל ועט ונייר טואלט'` | The quoted text, unchanged. | in print | [59.png](print-check/59.png) |
| 60 | a09-p023 | 61 | `האיים ההיברידיים` | The quoted text, unchanged. | in print | [60.png](print-check/60.png) |
| 61 | a17-p010, a17-p036 | 146, 156 | `555-539` | Page 146 (a17-p010): "(555–539 לפנה״ס)". Page 156 (a17-p036): "(539–555 לפנה״ס)", the two years in the other order; our text agrees with the print in both places. | in print | [61.png](print-check/61.png) |
| 62 | a17-p054 | 163 | `ישעיה לד, ז-יז` / `עובדיה א, א-יט` | The quoted text, unchanged. | in print | [62.png](print-check/62.png) |
| 63 | a07-p011 | 43 | `ב- 1818` | The quoted text, unchanged. | in print | [63.png](print-check/63.png) |
| 64 | a18-p025 | 173 | `לפני כ- 550 מיליון שנה` | The quoted text, unchanged. | in print | [64.png](print-check/64.png) |
| 65 | a18-p026 | 173 | `הנקראת דיאופטז` | The quoted text, unchanged. | in print | [65.png](print-check/65.png) |
| 66 | a17-p004 | 145 | `17 ק"מ מדרום מזרח לעיירה טפילה` | The quoted text, unchanged. | in print | [66.png](print-check/66.png) |
| 67 | a13-p057 | 103 | `לכל היותר עוד שלוש וחצי שעות` | The quoted text, unchanged. | in print | [67.png](print-check/67.png) |
| 68 | sources-p060 | 311 | `Ehrenberg, C.G. 54.מובא אצל אורן…` | Entry 53 (Coyn and Bellier) ends with "p. 3." Entry 54 starts a new line: "Ehrenberg, C.G.", cited through Oren 2008. Our sources-p060 merges the two entries and moves "54." into the middle. The print gives no year for Ehrenberg, so "lost its data" is not a print fault. | conversion error | [68.png](print-check/68.png), [68-zoom.png](print-check/68-zoom.png) |
| 69 | sources-p035 | 310 | `30. C. B., Smith, N. G.,Ben-Yosef, E., Robinson` | "30. C. B., Smith, N. G.,Ben-Yosef, E., Robinson" and nothing more, before the next heading. The print itself has the broken entry. | in print | [69.png](print-check/69.png) |
| 70 | sources-p045 | 310 | `39. וינברג, ר. ובגין, ב"ז, 'מה` | "39. וינברג, ר. ובגין, ב"ז, 'מה ראתה אשת לוט? …'. מלח הארץ 1, עמ' 1–18." with no year. The print itself has no year. | in print | [70.png](print-check/70.png) |
