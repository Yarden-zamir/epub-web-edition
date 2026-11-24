# Errata: errors in the printed text

Errata agent, 2026-11-24. This list covers errors in the printed book. It does not cover extraction or layout faults of the edition.

- **verified**: the evidence leaves no doubt, and the fix is a narrow replacement. These entries are in `proposed.toml`.
- **family**: the evidence is clear, but the text is a personal memoir. The family decides.
- **editor**: the printed text is probably wrong, but the fix is not narrow, or more than one fix is possible.
- **keep**: keep as printed. The reason is in the row.

Page = PDF page where the printed text starts. Element = release EPUB element ID (`epub-src-release/OEBPS/text/*.xhtml`).
Check `proposed.toml` against the release source: `uv run errata/check_errata.py` (run from the content repo root).
The lead agent re-checked the evidence of rows 1-31 and the print of rows 1-22. Evidence in rows 32-67 comes from the read in step 4 and was not re-checked one by one.
For entries that the text layer could garble, a render of the PDF page confirmed the print: a10-p003, a09-p023, a13-p058, a17-p009, a18-p063, a18-p041.

## How the book was checked

1. The known suspects: OPEN-POINTS.md item 22.
2. Every Bible and rabbinic reference in the book (27 references), checked against Sefaria (`https://www.sefaria.org/api/v3/texts/<ref>`) and the KJV (`https://bible-api.com`). All are correct except the two in the table: Leviticus 2:23 (a06-p022) and Deuteronomy 14 (a31-p007). Correct: Proverbs 3:33 (a15-p005), 1 Kings 10 (a16-p023), Isaiah 63:1 (a17-p004), 2 Kings 14:7, 14:8, 14:10 (a17-p015, a17-p055), Jeremiah 49:16 and Obadiah 1:3-4 (a17-p024), Jeremiah 48:28 (a17-p026), the Edom prophecies (a17-p054), Numbers 33:41-44 and 1 Chronicles 4:12 (a18-p003), Genesis 1:25 and 43:11 (a19-p005, a19-p008), Mishnah Eduyot 2:5 (a19-p006), Numbers 21:12-13, Deuteronomy 2:13, Genesis 19:30, Numbers 24:6, 2 Chronicles 25:11, Numbers 33:42 (a25), Ezekiel 47 (a36-p004), Zephaniah 2:9 and Ezekiel 47:9-11 in the KJV (a06-p022), Genesis 18-19 (a06-fn7).
3. Classical and medieval sources: Josephus, Diodorus, Hieronymus of Cardia, Dioscorides, Eusebius (a06, a16, a17) and the Röhricht Regesta (a06-fn15). Only the Regesta number is wrong.
4. A full read of the book for factual slips (dates, numbers, names), in three parts, with web checks of each candidate. About 80 more facts were checked and found correct. They are not listed here.

## Verified (in proposed.toml)

| # | Element | Page | Printed | Correction | Evidence |
|---|---|---|---|---|---|
| 1 | a06-p022 | 29 | `(2:23, KJV)` | `(2:13, KJV)` | The salt-of-the-covenant verse is Leviticus 2:13. Leviticus 2 has 16 verses. [KJV Lev 2:13](https://bible-api.com/leviticus+2:13?translation=kjv) |
| 2 | a06-p022 | 29 | `shalt though season` | `shalt thou season` | KJV: "And every oblation of thy meat offering shalt thou season with salt". Same source. |
| 3 | a06-p021 | 26 | `salts form any other source` | `salts from any other source` | Typo. |
| 4 | a06-p023 | 29 | `south of Hebron` | `south of Bethlehem` | Tekoa is "c. 5 miles (8 km) south of Bethlehem", on the road to Hebron. [Wikipedia: Tekoa](https://en.wikipedia.org/wiki/Tekoa_(ancient_town)) |
| 5 | a06-p030 | 33 | `For 3,300 years` | `For 2,300 years` | Aristotle lived 384-322 BC. The book dates him to the 4th century BC (a35-p016). [Wikipedia: Aristotle](https://en.wikipedia.org/wiki/Aristotle) |
| 6 | a06-fn15 | 29 | `n. 173.` | `n. 174.` | Röhricht, Regesta (1893), pp. 43-44: the charter "1138 Febr. 5 … Fuko … donat casale Thecuae … bitumen … et sal" is no. 174. No. 173 is a Templar charter. [archive.org OCR](https://archive.org/download/regestaregnihie00rhgoog/regestaregnihie00rhgoog_djvu.txt) |
| 7 | a31-p002 | 245 | `מבול בשלושה במאי` | `מבול בשני במאי` | Same article: "ממש ביום האירוע (2 במאי 2001)" (a31-p006), "ביום השיטפון ב-2 במאי" (a31-p007). Israel Meteorological Service: "01-02.05.2001 … בליל ה-1-2 במאי … שיטפונות אלה הביאו לקריסתו של גשר נחל ערוגות". [IMS extreme events review, 2023, p. 56](https://ims.gov.il/sites/default/files/inline-files/%D7%A1%D7%A7%D7%99%D7%A8%D7%AA%20%D7%90%D7%99%D7%A8%D7%95%D7%A2%D7%99%D7%9D%20%D7%A7%D7%99%D7%A6%D7%95%D7%A0%D7%99%D7%99%D7%9D%20-%20%D7%A2%D7%93%D7%9B%D7%95%D7%95%D7%9F%20%D7%9E%D7%A8%D7%A5%202023_0.pdf) |
| 8 | a31-p007 | 247 | `של ה-3 במאי` | `של ה-2 במאי` | Same paragraph says "ביום השיטפון ב-2 במאי". Same IMS source. |
| 9 | a31-p007 | 247 | `דברים יד, 14-13` | `דברים יא, 14-13` | The quote "והיה אם שמע תשמעו … ונתתי מטר ארצכם בעתו יורה ומלקוש" is Deuteronomy 11:13-14. Deuteronomy 14:13-14 lists unclean birds. [Sefaria Deut 11:13-14](https://www.sefaria.org/api/v3/texts/Deuteronomy.11.13-14) |
| 10 | a10-p003 | 66 | `'מועדון האלפיני הישראל'` | `'מועדון האלפיני הישראלי'` | Missing final yod. a10-p002 prints "המועדון האלפיני הישראלי". |
| 11 | a09-p023 | 61 | `בן אוויס` | `בן נוויס` | Ben Nevis, "1,345 m", the highest peak of the British Isles, in Scotland. The text gives the same height and place. [Wikipedia: Ben Nevis](https://en.wikipedia.org/wiki/Ben_Nevis) |
| 12 | a13-p058 | 103 | `שבאינדוזיה` | `שבאינדונזיה` | Komodo is in Indonesia. [Wikipedia: Komodo](https://en.wikipedia.org/wiki/Komodo_(island)) |
| 13 | a19-p009 | 185 | `במאה ה- 14` | `במאה ה- 15` | Arnold von Harff travelled in 1496-1499 (Mamluk period, so the bracket stays true). [Wikipedia: Arnold von Harff](https://en.wikipedia.org/wiki/Arnold_von_Harff) |
| 14 | a17-p009 | 146 | `אברהם מוסיל` | `אלואיס מוסיל` | The Czech explorer of Edom is Alois Musil (1868-1944). [Wikipedia: Alois Musil](https://en.wikipedia.org/wiki/Alois_Musil) |
| 15 | a18-p063 | 181 | `בחפירות רבת א-נחאס` | `בחפירות ח'רבת א-נחאס` | The book prints "ח'רבת א-נחאס" in all 8 other places. [Wikipedia: Khirbat en-Nahas](https://en.wikipedia.org/wiki/Khirbat_en-Nahas) |
| 16 | a35-p058 | 286 | `(Bodaker et al., 2000)` | `(Bodaker et al., 2010)` | The book cites the paper as 2010 in a35-p005 and in sources-p053 (ISME Journal 4: 399-407). [doi:10.1038/ismej.2009.141](https://doi.org/10.1038/ismej.2009.141) |
| 17 | sources-p069 | 311 | `pp. 31–41` | `pp. 33–41` | Oren 1983, Limnology and Oceanography 28(1): "page 33-41". [Crossref](https://api.crossref.org/works/10.4319/lo.1983.28.1.0033) |
| 18 | sources-p024 | 309 | `תרח"ץ` | `תרצ"ח` | Letters swapped. The entry is dated 1938 = 5698 = תרצ"ח. [Hebcal](https://www.hebcal.com/converter?cfg=json&gy=1938&gm=6&gd=1&g2h=1) |
| 19 | sources-p047 | 310 | `Geological Society of America Bulletin, v.116,pp. 555–571` | `Geological Survey of Israel Bulletin 63` | Begin, Ehrlich and Nathan 1974 is GSI Bulletin 63. GSA Bulletin 116: 555-571 is Ken-Tor (Bookman) et al. 2004. [Cambridge, Quaternary of the Levant, ch. 12](https://www.cambridge.org/core/books/abs/quaternary-of-the-levant/lake-lisan/CF25D6DE02054F2F38A24D91617CBC85) |
| 20 | a36-p053 | 303 | `לכמיליון עד סוף העשור` | `לכמיליארד עד סוף העשור` | "From about 600 million m³ to about a million" is impossible. Government Decision 3533 (June 2018) sets 1,100 million m³ a year for 2030. [Follow-up report on the drought plan](https://www.ceci.org.il/wp-content/uploads/2023/10/%D7%AA%D7%9B%D7%A0%D7%99%D7%AA-%D7%90%D7%A1%D7%98%D7%A8%D7%98%D7%92%D7%99%D7%AA-%D7%9C%D7%94%D7%AA%D7%9E%D7%95%D7%93%D7%93%D7%95%D7%AA-%D7%A2%D7%9D-%D7%AA%D7%A7%D7%95%D7%A4%D7%AA-%D7%91%D7%A6%D7%95%D7%A8%D7%AA-%D7%91%D7%9E%D7%A9%D7%A7-%D7%94%D7%9E%D7%99%D7%9D-%D7%9C%D7%A9%D7%A0%D7%99%D7%9D-2018-2030.pdf) |
| 21 | a35-p070 | 288 | `(Coyn & Bellier` | `(Coyne & Bellier` | The firm is Coyne et Bellier. [EIB register](https://www.eib.org/attachments/registers/82425040.pdf) |
| 22 | sources-p060 | 311 | `Coyn and Bellier` | `Coyne and Bellier` | Same firm. |

## Family decision

| # | Element | Page | Printed | Proposed | Evidence and reason |
|---|---|---|---|---|---|
| 23 | a10-p012 | 68 | `בני, דב, גדי ויוקי` | `בני, דב, גבי ויוקי` | The victim is Gabi Manobla. a10-p002 prints "גבי מנובלא". IMGA wiki: "בני אגור, יוקי פרג, גבי מנובלה ודב מלי". [IMGA: אסון פאמיר](https://wiki.imga.org.il/index.php?title=%D7%90%D7%A1%D7%95%D7%9F_%D7%A4%D7%90%D7%9E%D7%99%D7%A8). The evidence is clear. It is a name in Eli's memoir, so the family confirms. |
| 24 | a10-p020 | 69 | `באסון רעידת אדמה שהתרחש בתורכיה זמן מה קודם לכן` | ארמניה? | The story is in 1990. The Israeli rescue team went to Armenia (Spitak, December 1988). The Israeli rescue mission to Turkey was in 1999. [he.wikipedia: חטיבת החילוץ וההדרכה](https://he.wikipedia.org/wiki/%D7%97%D7%98%D7%99%D7%91%D7%AA_%D7%94%D7%97%D7%99%D7%9C%D7%95%D7%A5_%D7%95%D7%94%D7%93%D7%A8%D7%9B%D7%94). "פיקוד העורף" was founded in 1992, so the name is also anachronistic. Memoir: family decides. |
| 25 | a09-p014, a10-p037 | 59, 76 | `באוגוסט 1981` / `ב- 1982, אי שם באלפים הצרפתיים` | one of the two | The same Alps trip is dated 1981 in a09 and 1982 in a10 (a10-p004, "eight years" before 1990, also points to 1982). No outside source. |

## Editor decision

| # | Element | Page | Printed | Problem | Evidence |
|---|---|---|---|---|---|
| 26 | a10-p002 | 65 | `בגובה 3,005 מטר` | The Frying Pan camp is at about 5,200-5,300 m. Base camp is 3,600 m (a10). The correct figure differs between sources. | [Wikipedia: Lenin Peak disaster](https://en.wikipedia.org/wiki/Lenin_Peak_disaster): "Camp II, at an elevation of 5,300 meters". [IMGA](https://wiki.imga.org.il/index.php?title=%D7%90%D7%A1%D7%95%D7%9F_%D7%A4%D7%90%D7%9E%D7%99%D7%A8): "בגובה 5200מ׳ שכונה ״המחבת״". |
| 27 | a06-p027 | 30 | `the Jewish World Zionist Organization appointed a scientific delegation, headed by … Blanckenhorn` | a07-p023 says the Sultan invited and funded it, which is correct. A fix rewrites the clause. | Blanckenhorn's report (1912): "im Auftrage S. M. des Sultans Abdul Hamid II." [Persée, Annales de Géographie 1913](https://www.persee.fr/doc/geo_0003-4010_1913_bib_22_125_19303) |
| 28 | a34-p007 | 261 | `עבד בחצי אי הלשון בשנת 1869` | Lartet worked there in 1864 (de Luynes expedition, a07-p021). 1869 is the year of his publication (sources-p042). Possible fix: 1864, or keep 1869 as the publication. | [Wikipedia: Lake Lisan](https://en.wikipedia.org/wiki/Lake_Lisan): "first described by Lartet in 1869 after visiting the Dead Sea in the Spring of 1864". |
| 29 | a10-p003 | 66 | `'חזור למקום ממנו באת'` | The heading of a09 is "חזור למדבר ממנו באת". | a09-h. |
| 30 | a36-p063 | 305 | `'האקולוגיה של ים המלח'` | The heading of a35 is "המערכת האקולוגית של ים המלח". | a35-h. |
| 31 | a18-p041 | 177 | `(7373 מ"ר)` | The print lost the "X": the fortress is 73 × 73 m (about 5,300 m²). The unit also needs a change. | Finkelstein, Semitica 56: "(73 × 73 m)". [PDF](https://www.ancientportsantiques.com/wp-content/uploads/Documents/PLACES/RedSea/Elath-Finkelstein2014.pdf) |
| 32 | a17-p015 | 150 | `מקדים בכמאה שנה את אמציהו` | Bennett's earliest Edomite finds are about a century later than Amaziah, not earlier. That is why they undermined Glueck's view. a17-p018 agrees. | Bienkowski (ed.), Umm al-Biyara (2011): "No occupation at Umm al-Biyara could be dated as early as Amaziah's reign". |
| 33 | a17-src1 | 145 | `פורסם בקתדרה 2002,101` | Cathedra 101 is dated October 2001. | [he.wikipedia: פטרה](https://he.wikipedia.org/wiki/%D7%A4%D7%98%D7%A8%D7%94) cites "קתדרה 101, אוקטובר 2001". |
| 34 | a17-p004, a18-p002 | 145, 167 | `19 ק"מ מזרחית לחצבה` / `כ- 28 ק"מ ממזרח לחצבה` | The same distance differs. By coordinates it is about 31 km, so 19 is wrong. | Coordinates on Wikipedia (Sela, Hatzeva). |
| 35 | a17-p004 | 145 | `5 ק"מ מצפון-מזרח לכפר בוצירה` | Sela is about 3 km north-west of Busayra. | Virtual Archaeology Review 2024, doi:10.4995/var.2024.19977: "approximately 3 km northwest of Bozrah". |
| 36 | a15-p029 | 132 | `הקמת הקיבוץ בשנות ה- 60` | Kibbutz Ein Gedi was founded in 1953-1956. The sentence may mean the dispute began in the 1960s. | [Wikipedia: Ein Gedi (kibbutz)](https://en.wikipedia.org/wiki/Ein_Gedi_(kibbutz)) |
| 37 | a08-p003 | 53 | `עמרם מצנע, אלוף פיקוד מרכז דאז` | The text sets this in the 1970s. Mitzna was head of Central Command in 1987-1989. | [he.wikipedia: עמרם מצנע](https://he.wikipedia.org/wiki/%D7%A2%D7%9E%D7%A8%D7%9D_%D7%9E%D7%A6%D7%A0%D7%A2) |
| 38 | a04-p004 | 15 | `1958: מצעד יום העצמאות בחיפה` | The 1958 parade was in Jerusalem. Haifa held it in 1953, 1956, 1960, 1963. Photo caption; the right year is not known. | [he.wikipedia: מצעד צה"ל](https://he.wikipedia.org/wiki/%D7%9E%D7%A6%D7%A2%D7%93_%D7%A6%D7%94%22%D7%9C) |
| 39 | a06-p025 | 31 | `For the first and last time, the Degania Dam gates were opened` | The gates also opened in 1969, and later in 1993 and 1995. Not a narrow fix. | [he.wikipedia: סכר דגניה](https://he.wikipedia.org/wiki/%D7%A1%D7%9B%D7%A8_%D7%93%D7%92%D7%A0%D7%99%D7%94) |
| 40 | a35-p052 | 285 | `400 אלף תאי דונליאלה` | Published peak for 1964: up to 4 × 10⁴ cells/ml (40 thousand). The book cites Oren 2008, not checked. | Oren and Ventosa 1999, International Microbiology. |
| 41 | sources-p055, sources-p091 | 310, 312 | `Letters to T. Herzl, 1809-1901` | Herzl was born in 1860. Probably 1899-1901, not confirmed. | Bourcart's proposal to Herzl, about 1899. |
| 42 | a35-p073 | 289 | `בשנת 1994 פסק בית המשפט בקליפורניה` | 1994 is Decision 1631 of the State Water Resources Control Board. The court ruling was in 1983. | [Mono Basin timeline](https://www.monobasinresearch.org/timelines/d1631.php) |
| 43 | a34-p046 | 272 | `(259 מ' במרץ 2026)` | Bottom about −728 m, surface about −441 m: water depth about 287 m. The sentence around it is also garbled. | [Wikipedia: Dead Sea](https://en.wikipedia.org/wiki/Dead_Sea) |
| 44 | a36-p073 | 307 | `הוגש לשותפות ב- 2021` | The book dates the same report 2011 (a36-p057, sources). World Bank reports: 2013-2014. | [EIB register](https://www.eib.org/attachments/registers/82425040.pdf) |
| 45 | a36-p045, a36-p046 | 300, 301 | `נחתם בנובמבר 2021` / `ב- 2019, בטרם יבש הדיו` | 2019 cannot follow a 2021 signing. The 300 and 65 million m³ figures belong to the Israel-Jordan agreement of February 2015. | [Times of Israel, 2015](https://www.timesofisrael.com/israel-and-jordan-sign-historic-water-deal-to-save-dead-sea/) |
| 46 | a36-p033 | 297 | `ב- 2015, בעקבות מזכר הבנות` | Contradicts a36-p015 (World Bank study from 2005) and a36-p057 (final report 2011). | World Bank study 2008-2013. |
| 47 | a36-p068, a36-p075 | 306, 307 | `2020` (long-term policy document) | The same document is "2022" in a36-p013, a36-p039, a36-p041 and sources-p089. | [Times of Israel, 2022](https://www.timesofisrael.com/authorities-urged-to-immediately-stabilize-dead-sea-levels/) |
| 48 | sources-p063 | 311 | `Harza JRV Group (1997)` | sources-p092 and a36-p034 cite Harza 1998. | Known reports: 1996 draft, February 1998 final. |
| 49 | a35-p006, a36-p063 | 276, 305 | `Steinhorn, 1983` | The bibliography has only Steinhorn 1981. A 1983 paper exists, so the bibliography may lack it. | Limnology and Oceanography 1983. |
| 50 | a36-p006 | 292 | `כיהן בשנים 1950 עד 1955 כמרצה בטכניון` | Lowdermilk was in Israel 1951-1957, at the Technion from about 1953-1955 to 1957. | [NCpedia: Lowdermilk](https://www.ncpedia.org/biography/lowdermilk-walter-clay) |
| 51 | a06-fn24 | 35 | `6 (October 2009), pp. 1–11` | Final pagination: 6 Suppl 5: S575-S585. "pp. 1–11" may be the online-first version. | [PubMed 19656820](https://pubmed.ncbi.nlm.nih.gov/19656820/) |
| 52 | a07-p018 | 46 | `428 −` (Symonds 1841), `394 −` (Lynch 1848) | Symonds: 1,312 ft (about 400 m); Lynch/Dale: 1,316 ft (about 401 m). The author may use another source. | [McClintock and Strong: Salt Sea](https://www.biblicalcyclopedia.com/S/salt-sea.html) |
| 53 | a18-p003 | 167 | `מחדש ב- 1907` | Musil did field work in 1896-1902. 1907 is the year of Arabia Petraea. | Wikipedia: Alois Musil. |
| 54 | a34-p039 | 270 | `הגדולה שבהן הוא 5.7 ק"מ` | True for the old survey. Malham Cave measured about 10 km in 2019. An update note in square brackets is possible. | [phys.org, 2019](https://phys.org/news/2019-03-israelis-unveil-world-longest-salt.html) |
| 55 | a35-p034 | 281 | `(Buchalo et al., 2000)` | The first record of fungi is Buchalo et al. 1998 (a35-p015 says 1998). The bibliography has only the 2000 work, twice (sources-p054, sources-p058). | doi:10.1098/rspb.1998.0458 |
| 56 | a20-p002 | 189 | `אוזרח בשנת 1977` | Mitzpe Shalem: 1976 in a weak source. Eyewitness memoir. | [Wikipedia: Mitzpe Shalem](https://en.wikipedia.org/wiki/Mitzpe_Shalem) |

## Keep as printed

| # | Element | Page | Printed | Reason |
|---|---|---|---|---|
| 57 | a10-p002 | 65 | `(7,200 מטר)` | Lenin Peak is 7,134 m. A round figure in a memoir. |
| 58 | a10-p002 | 65 | `כחמישים מטפסים` | 43 died. "About fifty" is a round figure. |
| 59 | a14-p008 (crosslink) | 110 | `'מורל ועט ונייר טואלט'` | The heading is "מורל, עט ונייר טואלט". Only punctuation differs. |
| 60 | a09-p023 | 61 | `האיים ההיברידיים` | Hebrides. A spelling of the name, not a fact. |
| 61 | a17-p010, a17-p036 | 146, 156 | `555-539` | Nabonidus is usually 556-539 BC. 555 also appears in the literature. |
| 62 | a17-p054 | 163 | `ישעיה לד, ז-יז`, `עובדיה א, א-יט` | The author chose the verse ranges. |
| 63 | a07-p011 | 43 | `ב- 1818` (Gay-Lussac) | The literature gives 1817 or 1819. Not settled. |
| 64 | a18-p025 | 173 | `לפני כ- 550 מיליון שנה` | The Burj Formation is Middle Cambrian (about 510 million years). Not checked further; author's round figure. |
| 65 | a18-p026 | 173 | `הנקראת דיאופטז` | Dioptase is a separate mineral from chrysocolla. A simplification. |
| 66 | a17-p004 | 145 | `17 ק"מ מדרום מזרח לעיירה טפילה` | May be a road distance. |
| 67 | a13-p057 | 103 | `לכל היותר עוד שלוש וחצי שעות` | Arithmetic differs from his own scenario. A diary written in the pit. |

## Not print errors (for the EPUB/Kindle agent)

These look like faults in the bibliography block. They were not checked against a render.

- sources-p060: "Ehrenberg, C.G. 54.מובא אצל אורן…": two entries merged, Ehrenberg 1848 lost its data.
- sources-p035: broken fragment "30. C. B., Smith, N. G.,Ben-Yosef, E., Robinson".
- sources-p045: Weinberger and Begin has no year (the text cites 2005).
