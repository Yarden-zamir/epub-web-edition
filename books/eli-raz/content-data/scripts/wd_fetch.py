# /// script
# requires-python = ">=3.15"
# ///
"""Polite Wikidata client: one request at a time, pause between calls, back off on 429.

Usage:
  wd_fetch.py search OUT_DIR "query" LANG
  wd_fetch.py get OUT_DIR Q1 Q2 ...
Writes the raw JSON response to OUT_DIR (a new folder per download), prints nothing else.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.wikidata.org/w/api.php"
UA = "BookPlaceVerification/0.1 (one-off research script; low volume)"
PAUSE = 1.5


def call(params: dict[str, str]) -> dict:
    url = API + "?" + urllib.parse.urlencode(params | {"format": "json"})
    delay = 5.0
    for _ in range(6):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            time.sleep(PAUSE)
            return data
        except urllib.error.HTTPError as err:
            if err.code != 429 and err.code < 500:
                raise
            retry = err.headers.get("Retry-After")
            time.sleep(float(retry) if retry and retry.isdigit() else delay)
            delay *= 2
    raise RuntimeError(f"gave up after retries: {url}")


def main() -> None:
    mode, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=False)
    if mode == "search":
        query, lang = sys.argv[3], sys.argv[4]
        data = call({"action": "wbsearchentities", "search": query, "language": lang,
                     "uselang": lang, "limit": "8", "type": "item"})
    elif mode == "get":
        ids = sys.argv[3:]
        if not ids or len(ids) > 50:
            raise SystemExit("get needs 1..50 ids")
        data = call({"action": "wbgetentities", "ids": "|".join(ids),
                     "props": "labels|aliases|descriptions|claims|sitelinks", "languages": "he|en"})
    else:
        raise SystemExit(f"unknown mode {mode}")
    (out / "response.json").write_text(json.dumps(data, ensure_ascii=False))


main()
