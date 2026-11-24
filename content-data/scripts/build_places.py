# /// script
# requires-python = ">=3.15"
# ///
"""Build site/places.json from the place list below and the saved Wikidata responses.

Coordinates come only from wikidata-raw/*/response.json (P625). Descriptions are near-quotes
of the element named in description_source. Run from content-data:
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
     "description": "ההיסטוריה המוכחת של עין גדי כיישוב קבע חקלאי ויהודי משתרעת על פני כ-1200 שנה רצופות כמעט, מהמאה ה-7 לפנה\"ס ועד המאה השישית לספירה.",
     "description_source": "a30-p020", "figures": []},
    {"id": "kibbutz-ein-gedi", "name": "קיבוץ עין גדי", "wikidata": "Q2469471",
     "targets": ["a21-h", "a22-h", "a15-p024", "a20-p006"],
     "description": "עין גדי יושבה מחדש בעת החדשה, כדי להבטיח את ים המלח בגבולות המדינה.",
     "description_source": "a15-p024", "figures": []},
    {"id": "ein-gedi-reserve", "name": "שמורת הטבע עין גדי", "wikidata": "Q1011544",
     "targets": ["a15-p025", "a15-p029", "a15-p030"],
     "description": "בעין גדי הוכרזה שמורת טבע שבה נכללו כל מקורות המים ושטחי החקלאות העתיקה שביניהם.",
     "description_source": "a15-p025", "figures": []},
    {"id": "ein-gedi-field-school", "name": "בית ספר שדה עין גדי", "wikidata": "Q6711961",
     "targets": ["a22-p002", "a23-p002", "a12-p002", "a24-p003", "a09-p005", "a33-p002"],
     "description": "אלי רז הגיע לעין גדי אחרי מלחמת יום הכיפורים, כשנקרא על ידי החברה להגנת הטבע לנהל את בית ספר השדה במקום.",
     "description_source": "a22-p002", "figures": []},
    {"id": "ein-gedi-temple", "name": "המקדש הכלקוליתי בעין גדי", "wikidata": "Q2900794", "coord": 0,
     "targets": ["a30-p019", "a23-p008"],
     "description": "האתר הארכיאולוגי הקדום ביותר בתחום עין גדי נמצא על במת סלע מעל מעיין עין גדי, ומזוהה כמקדש מהתקופה הכלקוליתית, כ-5000 שנה לפני זמננו.",
     "description_source": "a30-p019", "figures": []},
    {"id": "nahal-arugot", "name": "נחל ערוגות", "wikidata": "Q1138503",
     "targets": ["a30-h", "a30-p003", "a31-h", "a31-p008", "a14-p024", "a12-p011"],
     "description": "נחל ערוגות הוא מהגדולים, היפים והחשובים שבנחלי מדבר יהודה, וחוליה מקשרת בין הפסגות הגבוהות של יהודה לבין נווה עין גדי.",
     "description_source": "a30-p002", "figures": ["fig-a30-01", "fig-a31-04", "fig-a14-12"]},
    {"id": "nahal-david", "name": "נחל דוד", "wikidata": "Q2538747", "coord": 0,
     "targets": ["a12-p003", "a30-p010", "a23-p008", "a15-p030"],
     "description": "בחנוכה תשל\"ה (דצמבר 1974) נפרד גרשון נדיבי מקבוצת בני עקיבא והמשיך לטייל לבדו בנחל דוד. בכניסה לנחל הוא נראה לאחרונה.",
     "description_source": "a12-p003", "figures": ["fig-a31-01"]},
    {"id": "metzoke-dragot", "name": "מצוקי דרגות", "wikidata": "Q6590839",
     "targets": ["a20-h", "a20-p008", "a09-p011", "a21-p003"],
     "description": "פעילות הדגל של מצוקי דרגות במשך שנים רבות הייתה קורס גלישת מצוקים שתכנן והדריך אלי רז, עם תרגול בנחל דרגות וגלישה מגבהים של עד כ-30 מטר בקניון נחל חצצון.",
     "description_source": "a20-p013", "figures": []},
    {"id": "mitzpe-shalem", "name": "מצפה שלם", "wikidata": "Q2890805",
     "targets": ["a20-p002", "a16-p032"],
     "description": "קיבוץ מצפה שלם אוזרח ב-1977 באתר היאחזות הנח\"ל על רמת המדבר (היום מצוקי דרגות). בתחילת 1980 עבר הקיבוץ לנקודת הקבע שלו לרגלי מצוק ההעתקים.",
     "description_source": "a20-p002", "figures": []},
    {"id": "nahal-darga", "name": "נחל דרגה", "wikidata": "Q2906907",
     "targets": ["a08-p009", "a08-p010", "a11-p012", "a20-p013", "a34-p044"],
     "description": "בחיפוש אחר שני אחים שנעלמו בנחל דרגות, ראו אלי רז ונרי אראלי במשקפת ממצא חשוד בגדה הדרומית של הנחל, שהתברר למחרת כאחד הנעדרים.",
     "description_source": "a08-p010", "figures": ["fig-a34-03"]},
    {"id": "nahal-kedem", "name": "נחל קדם", "wikidata": "Q7218512",
     "targets": ["a11-p027", "a11-p028"],
     "description": "בערוץ נחל קדם שרדה אלה אטלנטית זקנה ויחידה בכל צפון מדבר יהודה, זכר לעידן גשום יותר בעבר.",
     "description_source": "a11-p027", "figures": ["fig-a06-01"]},
    {"id": "nahal-salvadora", "name": "נחל סלוודורה", "wikidata": "Q6758903",
     "targets": ["a11-p003", "a11-p049", "a11-p050"],
     "description": "נקיק קטן אך מרשים מצפון לעין גדי. במעלה הנקיק, מתחת לעץ סלוודורה, פיכה מעיין קטן.",
     "description_source": "a11-p049", "figures": []},
    {"id": "einot-tsukim", "name": "עינות צוקים (עין פשחה)", "wikidata": "Q405816",
     "targets": ["a07-p022", "a08-p007", "a34-p018"],
     "description": "באוקטובר 1900 נחקק קו ייחוס על סלע בקרבת עין פשחה, כדי למדוד את השינויים במפלס ים המלח עם הזמן. זו הייתה תחילת התיעוד המסודר של מפלסי ים המלח.",
     "description_source": "a07-p022", "figures": []},
    {"id": "khirbet-mazin", "name": "חורבת מזין", "wikidata": "Q6632565",
     "targets": ["a16-p009", "a16-p010"],
     "description": "המספנה החשמונאית בחורבת מזין, שבה ובסביבתה נמצאו מאות מטבעות מתקופת ינאי.",
     "description_source": "a16-p009", "figures": ["fig-a16-05"]},
    {"id": "nahal-hever", "name": "נחל חבר", "wikidata": "Q2915124",
     "targets": ["a13-p006", "a13-p031", "a16-p013"],
     "description": "בערב סוכות 2003 נסע אלי רז לנחל חבר לתעד בורות חדשים. בעת מדידות סמוך לבור קרסה האדמה תחתיו והוא נפל פנימה.",
     "description_source": "a13-p006", "figures": ["fig-a13-06"]},
    {"id": "masada", "name": "מצדה", "wikidata": "Q186312",
     "targets": ["a16-p010", "a15-p015", "a34-p023"],
     "description": "על גבי שכבה מוקדמת של טיח בחומה הדרומית של הארמון הצפוני במצדה נחרתה דמות של ספינה.",
     "description_source": "a16-p010", "figures": ["fig-a34-08"]},
    {"id": "nahal-zeelim", "name": "נחל צאלים", "wikidata": "Q1138730", "coord": 1,
     "targets": ["a14-p013", "a24-p026", "a13-p029"],
     "description": "נחל צאלים הוא לב המדבר; אם תקשיבו היטב תוכלו לשמוע אותו פועם.",
     "description_source": "a24-p026", "figures": ["fig-a31-02"]},
    {"id": "neve-zohar", "name": "נווה זוהר", "wikidata": "Q2975481",
     "targets": ["a14-p005", "a14-p023", "a14-p063", "a31-p002"],
     "description": "את תשומת הלב הציבורית לקריסות פני השטח בחוף המערבי של ים המלח הפנה בור שנפער בכביש 90 בנווה זוהר, עוד לפני שהמונח בולען נכנס לשימוש.",
     "description_source": "a14-p023", "figures": []},
    {"id": "mount-sodom", "name": "הר סדום", "wikidata": "Q2670801",
     "targets": ["a34-h", "a34-p037", "a34-p038", "a34-p039", "a22-p012"],
     "description": "הר סדום הוא 'מחדר' מלח גדול (דיאפיר) שמתרומם בצידו המערבי של האגן הדרומי של בקעת ים המלח, בין מישור עמיעז לבריכות האידוי של מפעלי ים המלח.",
     "description_source": "a34-p038", "figures": []},
    {"id": "lisan-peninsula", "name": "חצי האי הלשון", "wikidata": "Q2921024",
     "targets": ["a34-p007", "a16-p013"],
     "description": "הסלע השולט בחצי האי הלשון פריך וממוצא אגמי. הגיאולוג הצרפתי לרטה קרא לו 'חוואר הלשון', ולאגם שבו נוצר 'אגם הלשון'.",
     "description_source": "a34-p007", "figures": []},
    {"id": "dead-sea", "name": "ים המלח", "wikidata": "Q23883",
     "targets": ["a06-h", "a07-h", "a35-h", "a36-h", "a16-h", "a32-h"],
     "description": "ים המלח נמצא בחלקה היבשתי העמוק ביותר של מערכת הבקעים הסורית–אפריקנית. פני מימיו הם פני השטח הנמוכים בתבל, והאגם חסר ניקוז חיצוני.",
     "description_source": "a35-p003", "figures": ["fig-a06-03", "fig-a06-07", "fig-a16-01", "fig-a16-06"]},
    {"id": "callirrhoe", "name": "חמי קלירוהי (צרת השחר)", "wikidata": "Q11910919",
     "targets": ["a19-p014", "a07-p004"],
     "description": "בחוף המזרחי של ים המלח, אתר מעיינות חמים בעלי מוניטין של מרפא, מהמפורסמים בעולם העתיק, הנקרא ביוונית 'קלירוהי' ובמקורותינו 'צרת השחר'.",
     "description_source": "a19-p014", "figures": []},
    {"id": "arnon", "name": "נחל ארנון (ואדי מוג'יב)", "wikidata": "Q2120208",
     "targets": ["a25-p005", "a27-p016", "a27-p017", "a16-p029", "a31-p020"],
     "description": "המעבר בקניון הארנון לכל אורכו נחשב לבלתי אפשרי עד שהגיעו אלי רז וקבוצותיו. הוא בנה מסלול מעגלי שיורד בקניון לכל אורכו, כולל גלישת צוקים לאורך מפל גבוה.",
     "description_source": "a27-p017", "figures": ["fig-a27-02"]},
    {"id": "sela", "name": "סלע (קלעת סלע)", "wikidata": "Q489724",
     "targets": ["a17-h", "a17-p033", "a25-p013", "a27-p039"],
     "description": "גוש הררי שיובליו העליונים של ואדי חנזירה חובקים. הביצור הטבעי וחציבה ובנייה בידי אדם הפכו אותו למצודה נשגבת, הנקראת קלעת (מצודת) סלע.",
     "description_source": "a17-p004", "figures": ["fig-a17-05", "fig-a17-10", "fig-a17-14", "fig-a17-17"]},
    {"id": "faynan", "name": "פונון (ואדי פינאן)", "wikidata": "Q12250629",
     "targets": ["a18-h", "a18-p003", "a18-p005", "a27-p008", "a27-p009", "a25-p015"],
     "description": "תל ח'רבת פינאן שוכן במזלג הנחלים ואדי פינאן וואדי דנא. פינאן ידועה מימי קדם כמרכז הפקת הנחושת החשוב ביותר של דרום הלבנט.",
     "description_source": "a18-p003", "figures": ["fig-a18-02", "fig-a18-04", "fig-a18-08"]},
    {"id": "khirbat-en-nahas", "name": "ח'רבת א-נחאס", "wikidata": "Q6401745",
     "targets": ["a18-p040", "a18-p044", "a27-p008"],
     "description": "מרכז הפקת הנחושת הגדול ביותר בדרום הלבנט, על גדתו הדרומית של ואדי אל-ע'וויבה. החורבה משתרעת על כ-100 דונם, ובה עשרות ערמות של סיגי נחושת שחורים, מבנים מסיביים ומצודה.",
     "description_source": "a18-p040", "figures": ["fig-a18-07"]},
    {"id": "timna", "name": "בקעת תמנע", "wikidata": "Q1973199", "coord": 0,
     "targets": ["a18-p017", "a18-p018", "a18-p019", "a18-p042", "a27-p008"],
     "description": "בבקעת תמנע שבהרי אילת, כ-25 ק\"מ מצפון לאילת, יש מרבצי נחושת דומים לאלה שבפונון, בכמויות קטנות בהרבה.",
     "description_source": "a18-p018", "figures": []},
    {"id": "wadi-rushmiya", "name": "ואדי רושמיה (נחל גיבורים)", "wikidata": "Q4024328", "coord": 0,
     "targets": ["a09-h", "a09-p003", "a09-p004"],
     "description": "צוקים זקופים במורד ואדי רושמיה, סמוך לגשר המפורסם בחיפה, היו המקום של טיפוס הצוקים הראשון של אלי רז.",
     "description_source": "a09-p003", "figures": []},
    {"id": "lenin-peak", "name": "פסגת לנין", "wikidata": "Q838587", "far": True,
     "targets": ["a10-h", "a10-p002", "a22-p013"],
     "description": "פסגה (7,200 מטר) ברכס פאמיר, בגבול טג'יקיסטאן וקירגיזסטאן. בדרך אליה, בעמק 'המחבת', התרחש ב-13 ביולי 1990 האסון הגדול ביותר בתולדות האלפיניזם.",
     "description_source": "a10-p002", "figures": ["fig-a10-04", "fig-a10-05", "fig-a10-08", "fig-a10-09"]},
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
                 "description_source": p["description_source"], "figures": p["figures"]}
        if p.get("far"):
            entry["far"] = True
        out.append(entry)
    Path(sys.argv[1]).write_text(json.dumps({"places": out}, ensure_ascii=False, indent=1) + "\n")
    print(len(out), "places")


main()
