# /// script
# requires-python = ">=3.15"
# ///
"""Build site/places.json from the place list below and the saved Wikidata responses.

Coordinates come only from wikidata-raw/*/response.json (P625). A "book" description is an exact
quote of the element named in description_source; a quote cut before its sentence ends ends in "…".
An "edition" description is written for this edition from description_url, for places that the book
names but never describes; its description_source is still the passage that names the place.
Run from content-data:
  uv run python -I scripts/build_places.py ../../site/places.json
"""
import json
import sys
from pathlib import Path

RAW = Path("wikidata-raw")

# coord: index into the item's P625 list, for items with more than one coordinate.
PLACES = [
    {"id": "ein-gedi-oasis", "name": "נווה עין גדי", "wikidata": "Q25489001",
     "targets": ["a15-h", "a30-p014", "a30-p020", "a16-p014", "a14-p015", "a14-p017", "a14-p051"],
     "description": "נווה עין גדי הזעיר ניזון מכשלושה מיליון קוב מים בשנה, ובו כשש מאות תושבים וכאלף תמרים - לאחר שנאלצו להיפרד מכאלפיים בגלל מכת הבולענים, והוא היחיד במרחב ההיסטורי והגיאוגרפי שלנו המכיל את הצירוף המסורתי: מעינות מפכים וישוב חי בצל מורשת עתיקה ונוף התמר…",
     "description_source": "a15-p020", "description_kind": "book", "figures": []},
    {"id": "kibbutz-ein-gedi", "name": "קיבוץ עין גדי", "wikidata": "Q2469471",
     "targets": ["a21-h", "a22-h", "a15-p024", "a20-p006"],
     "description": "עין גדי יושבה מחדש בעת החדשה, כדי להבטיח את ים המלח בגבולות המדינה.",
     "description_source": "a15-p024", "description_kind": "book", "figures": []},
    {"id": "ein-gedi-reserve", "name": "שמורת הטבע עין גדי", "wikidata": "Q1011544",
     "targets": ["a15-p025", "a15-p029", "a15-p030"],
     "description": "בהמשך הוכרזה בעין גדי גם שמורת טבע שבה נכללו כל מקורות המים ושטחי החקלאות העתיקה שביניהם…",
     "description_source": "a15-p025", "description_kind": "book", "figures": []},
    {"id": "ein-gedi-field-school", "name": "בית ספר שדה עין גדי", "wikidata": "Q6711961",
     "targets": ["a22-p002", "a23-p002", "a12-p002", "a24-p003", "a09-p005", "a33-p002"],
     "description": "אלי רז הגיע לעין גדי אחרי מלחמת יום הכיפורים, כשנקרא על ידי החברה להגנת הטבע לנהל את בית ספר שדה במקום. במשך ארבע שנות עבודתו בבית ספר שדה הגיעו מהשטח ידיעות רבות על מטיילים שאיבדו את דרכם או שנתקעו ולא יכלו להמשיך.",
     "description_source": "a22-p002", "description_kind": "book", "figures": []},
    {"id": "ein-gedi-temple", "name": "המקדש הכלקוליתי בעין גדי", "wikidata": "Q2900794", "coord": 0,
     "targets": ["a30-p019", "a23-p008"],
     "description": "האתר הארכיאולוגי הקדום ביותר בתחום עין גדי נמצא על במת סלע, הצופה אל הנוף, מעל מעיין עין גדי. הוא מזוהה - מיקומו, תכניתו וממצאיו - כמקדש מהתקופה הכלכוליתית - כ- 5000 שנה לפני זמננו.",
     "description_source": "a30-p019", "description_kind": "book", "figures": []},
    {"id": "nahal-arugot", "name": "נחל ערוגות", "wikidata": "Q1138503",
     "targets": ["a30-h", "a30-p003", "a31-h", "a31-p008", "a14-p024", "a12-p011"],
     "description": "נחל ערוגות, שבצוקיו הנישאים מצא גרשון את מותו הוא מהגדולים, היפים והחשובים שבנחלי מדבר יהודה.",
     "description_source": "a30-p002", "description_kind": "book", "figures": ["fig-a30-01", "fig-a31-04", "fig-a14-12"]},
    {"id": "nahal-david", "name": "נחל דוד", "wikidata": "Q2538747", "coord": 0,
     "targets": ["a12-p003", "a30-p010", "a23-p008", "a15-p030"],
     "description": "לבד מהמעיינות הנובעים בנחל ערוגות, נובעים מעיינות גם בנחל דוד, ושני מקורות נוספים נמצאים על קו שבר העובר בין שני הנחלים, בשיפולי הר מצפה עין גדי, והם מוכרים לציבור המטיילים כמעיין שולמית ומעיין עין גדי.",
     "description_source": "a30-p010", "description_kind": "book", "figures": ["fig-a31-01"]},
    {"id": "metzoke-dragot", "name": "מצוקי דרגות", "wikidata": "Q6590839",
     "targets": ["a20-h", "a20-p008", "a09-p011", "a21-p003"],
     "description": "שיתוף הפעולה עם אלי נתן דחיפה להקמת המרכז לפעילות ולסיורי מדבר, ובהמשך הוחלט לקרוא לו 'מצוקי דרגות'.",
     "description_source": "a20-p008", "description_kind": "book", "figures": []},
    {"id": "mitzpe-shalem", "name": "מצפה שלם", "wikidata": "Q2890805",
     "targets": ["a20-p002", "a16-p032"],
     "description": "קיבוץ מצפה שלם אוזרח בשנת 1977 באתר היאחזות הנח\"ל, גבוה על רמת המדבר (היום מצוקי דרגות). בתחילת 1980 הקיבוץ עבר לנקודת הקבע שלו לרגלי מצוק ההעתקים, והמוסדות המיישבים הותירו בידיו את אתר ההיאחזות.",
     "description_source": "a20-p002", "description_kind": "book", "figures": []},
    {"id": "nahal-darga", "name": "נחל דרגה", "wikidata": "Q2906907",
     "targets": ["a08-p009", "a08-p010", "a11-p012", "a20-p013", "a34-p044"],
     "description": "נחל אכזב בצפון מדבר יהודה, הנשפך לים המלח.",
     "description_source": "a08-p010", "description_kind": "edition",
     "description_url": "https://he.wikipedia.org/wiki/%D7%A0%D7%97%D7%9C_%D7%93%D7%A8%D7%92%D7%94", "figures": ["fig-a34-03"]},
    {"id": "nahal-kedem", "name": "נחל קדם", "wikidata": "Q7218512",
     "targets": ["a11-p027", "a11-p028"],
     "description": "אלה אטלנטית זקנה ויחידה בכל צפון מדבר יהודה שרדה בערוץ נחל קדם, זכר לעידן גשום יותר בעבר…",
     "description_source": "a11-p027", "description_kind": "book", "figures": ["fig-a06-01"]},
    {"id": "nahal-salvadora", "name": "נחל סלוודורה", "wikidata": "Q6758903",
     "targets": ["a11-p003", "a11-p049", "a11-p050"],
     "description": "ב- 1/12/1993 התפרסמו בעיתוני הצהריים בארצנו ידיעות מרעישות, על מציאת גופה ערופה במעלה נחל סלוודורה - ערוץ נחל במדבר יהודה, מצפון לעין גדי.",
     "description_source": "a11-p003", "description_kind": "book", "figures": []},
    {"id": "einot-tsukim", "name": "עינות צוקים (עין פשחה)", "wikidata": "Q405816",
     "targets": ["a07-p022", "a08-p007", "a34-p018"],
     "description": "באוקטובר 1900 הטילה הקרן הבריטית לחקירת ארץ ישראל (P.E.F) על מקאליסטר, ראש המשלחת הארכיאולוגית בגזר, לחקוק קו ייחוס על סלע בקירבת עין פשחה. זאת, כדי שאפשר יהיה למדוד את השינויים במיפלס ים המלח עם הזמן.",
     "description_source": "a07-p022", "description_kind": "book", "figures": []},
    {"id": "khirbet-mazin", "name": "חורבת מזין", "wikidata": "Q6632565",
     "targets": ["a16-p009", "a16-p010"],
     "description": "ממצא רלוונטי לספנות המפותחת בתקופה זו, היא המספנה החשמונאית בחורבת מזין שבה ובסביבתה נמצאו מאות מטבעות מתקופת ינאי.",
     "description_source": "a16-p009", "description_kind": "book", "figures": ["fig-a16-05"]},
    {"id": "nahal-hever", "name": "נחל חבר", "wikidata": "Q2915124",
     "targets": ["a13-p006", "a13-p031", "a16-p013"],
     "description": "על טיב הקשרים ביניהם אפשר ללמוד מתעודות שנמצאו במערת האיגרות בנחל חבר (כ-5 ק\"מ דרומית-מערבית לעין גדי), שבה הסתתרו אנשים מעין גדי בזמן דיכוי מרד בר-כוכבא.",
     "description_source": "a16-p013", "description_kind": "book", "figures": ["fig-a13-06"]},
    {"id": "masada", "name": "מצדה", "wikidata": "Q186312",
     "targets": ["a16-p010", "a15-p015", "a34-p023"],
     "description": "מבצר עתיק על פסגתו של הר שולחן מבודד בשולי מדבר יהודה, מעל החוף המערבי של ים המלח.",
     "description_source": "a16-p010", "description_kind": "edition",
     "description_url": "https://he.wikipedia.org/wiki/%D7%9E%D7%A6%D7%93%D7%94", "figures": ["fig-a34-08"]},
    {"id": "nahal-zeelim", "name": "נחל צאלים", "wikidata": "Q1138730", "coord": 1,
     "targets": ["a14-p013", "a24-p026", "a13-p029"],
     "description": "מהגדולים שבנחלי האכזב של מדבר יהודה, הנשפך לים המלח מצפון למצדה.",
     "description_source": "a24-p026", "description_kind": "edition",
     "description_url": "https://he.wikipedia.org/wiki/%D7%A0%D7%97%D7%9C_%D7%A6%D7%90%D7%9C%D7%99%D7%9D", "figures": ["fig-a31-02"]},
    {"id": "neve-zohar", "name": "נווה זוהר", "wikidata": "Q2975481",
     "targets": ["a14-p005", "a14-p023", "a14-p063", "a31-p002"],
     "description": "תופעות של קריסת פני שטח בחוף המערבי של ים המלח מוכרות החל מ- 1989, כמטרד בטיחותי הטעון טיפול. ההתרחשות שהפנתה את תשומת הלב הציבורית לכך, היתה בור - המונח בולען טרם נכנס לשימוש - שנפער בכביש 90 בנווה זוהר.",
     "description_source": "a14-p023", "description_kind": "book", "figures": []},
    {"id": "mount-sodom", "name": "הר סדום", "wikidata": "Q2670801",
     "targets": ["a34-h", "a34-p037", "a34-p038", "a34-p039", "a22-p012"],
     "description": "הר סדום הוא 'מֶחדר' מלח גדול (דיאפיר) שמתרומם בצידו המערבי של האגן הדרומי של בקעת ים המלח, בין מישור עמיעז במערב לבריכות האידוי של מפעלי ים המלח במזרח.",
     "description_source": "a34-p038", "description_kind": "book", "figures": []},
    {"id": "lisan-peninsula", "name": "חצי האי הלשון", "wikidata": "Q2921024",
     "targets": ["a34-p007", "a16-p013"],
     "description": "הגיאולוג הצרפתי Lartet עבד בחצי אי הלשון בשנת 1869. הסלע השולט שם הוא פריך וממוצא אגמי, ובנוי מרבדים (למינות) דקים ולבנים של המינרל ארגוניט, לסירוגין עם למינות של חרסיות כהות.",
     "description_source": "a34-p007", "description_kind": "book", "figures": []},
    {"id": "dead-sea", "name": "ים המלח", "wikidata": "Q23883",
     "targets": ["a06-h", "a07-h", "a35-h", "a36-h", "a16-h", "a32-h"],
     "description": "אגם ים המלח נמצא בחלקה היבשתי העמוק ביותר של מערכת הבקעים הסורית–אפריקנית ומהווה בסיס ניקוז לאגן של כ- 43,000 קמ\"ר, הכולל שטחים בישראל, ירדן, סוריה, לבנון וסיני. שטח גוף המים הטבעי כ- 600 קמ״ר, עומקו המרבי כ- 300 מ׳ ורום מפלסו 430 מ׳ מתחת לפני הים (במאי 2016), והוא מהווה את פני השטח הנמוכים בתבל.",
     "description_source": "a35-p003", "description_kind": "book", "figures": ["fig-a06-03", "fig-a06-07", "fig-a16-01", "fig-a16-06"]},
    {"id": "callirrhoe", "name": "חמי קלירוהי (צרת השחר)", "wikidata": "Q11910919",
     "targets": ["a19-p014", "a07-p004"],
     "description": "בחוף המזרחי של ים המלח, מצוי אתר מעיינות חמים בעלי מוניטין של מרפא, מהמפורסמים בעולם העתיק, הנקרא ביוונית 'קלירוהי' ובמקורותינו - 'צֶרֶת השחר'…",
     "description_source": "a19-p014", "description_kind": "book", "figures": []},
    {"id": "arnon", "name": "נחל ארנון (ואדי מוג'יב)", "wikidata": "Q2120208",
     "targets": ["a25-p005", "a27-p016", "a27-p017", "a16-p029", "a31-p020"],
     "description": "נחל איתן בעבר הירדן המזרחי הנשפך לים המלח, ומזוהה עם ואדי אל-מוג'יב שבירדן.",
     "description_source": "a27-p017", "description_kind": "edition",
     "description_url": "https://he.wikipedia.org/wiki/%D7%A0%D7%97%D7%9C_%D7%90%D7%A8%D7%A0%D7%95%D7%9F", "figures": ["fig-a27-02"]},
    {"id": "sela", "name": "סלע (קלעת סלע)", "wikidata": "Q489724",
     "targets": ["a17-h", "a17-p033", "a25-p013", "a27-p039"],
     "description": "יובליו העליונים של ואדי חנזירה, היורד לצפון הערבה הירדנית מול נאות הכיכר, חובקים גוש הררי יפיפה ומבודדים אותו מסביבתו. הביצור הטבעי וחציבה ובנייה בידי אדם הפכו אותו למצודה נשגבת ומרשימה מאוד, הנקראת קלעת (מצודת) סלע.",
     "description_source": "a17-p004", "description_kind": "book", "figures": ["fig-a17-05", "fig-a17-10", "fig-a17-14", "fig-a17-17"]},
    {"id": "faynan", "name": "פונון (ואדי פינאן)", "wikidata": "Q12250629",
     "targets": ["a18-h", "a18-p003", "a18-p005", "a27-p008", "a27-p009", "a25-p015"],
     "description": "תל ח'רבת פינאן שוכן במזלג הנחלים ואדי פינאן וואדי דנא, בחלק המזרחי של בקעת פינאן, שהיא התרחבות של הערבה מזרחה. פינאן ידועה מימי קדם כמרכז הפקת הנחושת החשוב ביותר של דרום הלבנט.",
     "description_source": "a18-p003", "description_kind": "book", "figures": ["fig-a18-02", "fig-a18-04", "fig-a18-08"]},
    {"id": "khirbat-en-nahas", "name": "ח'רבת א-נחאס", "wikidata": "Q6401745",
     "targets": ["a18-p040", "a18-p044", "a27-p008"],
     "description": "האתר המרכזי מתקופה זו הוא ח'רבת א-נחאס, מרכז הפקת הנחושת הגדול ביותר בדרום הלבנט. ח'רבת א-נחאס (בעברית: 'חורבת הנחושת' שוכנת על גדתו הדרומית של ואדי אל-ע'וויבה, בצפון מערב אזור מכרות הנחושת של פינאן.",
     "description_source": "a18-p040", "description_kind": "book", "figures": ["fig-a18-07"]},
    {"id": "timna", "name": "בקעת תמנע", "wikidata": "Q1973199", "coord": 0,
     "targets": ["a18-p017", "a18-p018", "a18-p019", "a18-p042", "a27-p008"],
     "description": "בבקעת תמנע שבהרי אילת, כ- 25 ק\"מ מצפון לאילת, יש מרבצי נחושת דומים לאלה שבפונון, בכמויות קטנות בהרבה. גם בתמנע נוצלו מרבצי הנחושת על ידי הקדמונים ובאתר נתגלו מכרות נחושת מעניינים שגילם החל מסוף האלף הרביעי לפנה\"ס ואולי אף קודם לכן.",
     "description_source": "a18-p018", "description_kind": "book", "figures": []},
    {"id": "wadi-rushmiya", "name": "ואדי רושמיה (נחל גיבורים)", "wikidata": "Q4024328", "coord": 0,
     "targets": ["a09-h", "a09-p003", "a09-p004"],
     "description": "אחת מתגליותיי החשובות בנעורי היו צוקים זקופים ומרשימים במורד ואדי רושמיה, סמוך לגשר המפורסם, כמהלך שעה מזרחה מביתי ברחוב לונץ. מגנט סמוי משך אותי אליהם, וגרם לטיפוס הצוקים הראשון שלי.",
     "description_source": "a09-p003", "description_kind": "book", "figures": []},
    {"id": "lenin-peak", "name": "פסגת לנין", "wikidata": "Q838587", "far": True,
     "targets": ["a10-h", "a10-p002", "a22-p013"],
     "description": "האסון אירע בלילה, כתוצאה מרעידת אדמה שגרמה להתמוטטות גושי קרח גדולים 'סיראקים' ולמפולות שלגים על האוהלים שהוקמו בעמק קטן, המכונה 'המחבת', בגובה 3,005 מטר, אשר בו חנו המטפסים בדרכם לפיסגת לנין (7,200 מטר) שברכס פאמיר. רכס זה הוא הגבוה ברכסי ברית המועצות לשעבר ומהווה גבול בין הרפובליקות האיסלמיות טג'יקיסטאן מדרום וקירגיזסטאן מצפון.",
     "description_source": "a10-p002", "description_kind": "book", "figures": ["fig-a10-04", "fig-a10-05", "fig-a10-08", "fig-a10-09"]},
]


def coords(qid: str) -> list[tuple[float, float]]:
    for resp in RAW.glob("get-*/response.json"):
        ent = json.loads(resp.read_text())["entities"].get(qid)
        if ent and "missing" not in ent:
            vals = [c["mainsnak"]["datavalue"]["value"] for c in ent["claims"]["P625"]]
            return [(v["latitude"], v["longitude"]) for v in vals]
    raise SystemExit(f"{qid}: no saved Wikidata response")


def main() -> None:
    out = []
    ids = set()
    for p in PLACES:
        if p["id"] in ids:
            raise SystemExit(f"duplicate id {p['id']}")
        ids.add(p["id"])
        cs = coords(p["wikidata"])
        if len(cs) > 1 and "coord" not in p:
            raise SystemExit(f"{p['id']}: {len(cs)} coordinates, pick one with 'coord'")
        lat, lon = cs[p.get("coord", 0)]
        entry = {"id": p["id"], "name": p["name"], "lat": round(lat, 4), "lon": round(lon, 4),
                 "wikidata": p["wikidata"], "targets": p["targets"], "description": p["description"],
                 "description_source": p["description_source"], "description_kind": p["description_kind"],
                 "figures": p["figures"]}
        if p["description_kind"] == "edition":
            entry["description_url"] = p["description_url"]
        elif p["description_kind"] != "book":
            raise SystemExit(f"{p['id']}: unknown description_kind {p['description_kind']}")
        if p.get("far"):
            entry["far"] = True
        out.append(entry)
    Path(sys.argv[1]).write_text(json.dumps({"places": out}, ensure_ascii=False, indent=1) + "\n")
    print(len(out), "places")


main()
