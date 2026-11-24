# /// script
# requires-python = ">=3.15"
# ///
"""Download one URL into a new folder work/pd-sources/<name>/ and record where it came from.

Usage: uv run -I fetch.py <name> <url> [filename]
Polite: generic User-Agent, a pause before each request, backoff on HTTP 429.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, UTC
from pathlib import Path

UA = {"User-Agent": "public-domain-source-check/1.0 (research script; low volume)"}
ROOT = Path.home() / "Github/eli-raz-edition/main/work/pd-sources"


def get(url: str) -> tuple[bytes, str]:
    for attempt in range(3):
        time.sleep(6)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            wait = int(e.headers.get("Retry-After") or 60)
            print(f"429, waiting {wait} s", file=sys.stderr)
            time.sleep(min(wait, 700))
    raise RuntimeError(f"rate limited: {url}")


def main(name: str, url: str, filename: str | None = None) -> None:
    folder = ROOT / name
    if folder.exists():  # each download gets a new folder
        raise SystemExit(f"folder exists: {folder}")
    data, ctype = get(url)
    folder.mkdir(parents=False)
    filename = filename or url.rstrip("/").split("/")[-1].split("?")[0] or "download"
    (folder / filename).write_bytes(data)
    (folder / "source.json").write_text(json.dumps(
        {"url": url, "file": filename, "bytes": len(data), "content_type": ctype,
         "fetched": datetime.now(UTC).isoformat(timespec="seconds")}, indent=1))
    print(folder / filename, len(data), ctype)


if __name__ == "__main__":
    main(*sys.argv[1:])
