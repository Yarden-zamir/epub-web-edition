"""Polite Wikimedia Commons API helper: one request at a time, pauses, backoff on 429."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "book-clearance-check/1.0 (private research script; low volume)"}


def get(url: str, raw: bool = False):
    for attempt in range(6):
        try:
            time.sleep(1.5)
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                data = r.read()
            return data if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"rate limited: {url}")


def api(params: dict):
    return get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"}))


def search(q: str, n: int = 30) -> list[str]:
    r = api({"action": "query", "list": "search", "srsearch": q, "srnamespace": 6, "srlimit": n})
    return [h["title"] for h in r["query"]["search"]]


def info(titles: list[str]) -> dict:
    """imageinfo with license metadata and a 300 px thumbnail URL, 20 titles per request."""
    out = {}
    for i in range(0, len(titles), 20):
        r = api({"action": "query", "titles": "|".join(titles[i:i + 20]), "prop": "imageinfo",
                 "iiprop": "url|size|extmetadata|sha1", "iiurlwidth": 300})
        for p in r["query"]["pages"].values():
            if "imageinfo" in p:
                out[p["title"]] = p["imageinfo"][0]
    return out
