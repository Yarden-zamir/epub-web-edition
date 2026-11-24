# /// script
# requires-python = ">=3.15"
# ///
"""Search Wikimedia Commons files and print size, stated licence and source per hit.

Usage: uv run -I csearch.py <n> "<query>" ["<query>" ...]
Writes all hits as JSON lines to stdout-adjacent file hits.jsonl in the current folder.
"""
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import commons  # noqa: E402


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, d):
        self.parts.append(d)


def plain(html: str) -> str:
    t = Text()
    t.feed(html)
    return " ".join("".join(t.parts).split())


def meta(ii: dict, key: str) -> str:
    return plain(ii.get("extmetadata", {}).get(key, {}).get("value", ""))


def main() -> None:
    n = int(sys.argv[1])
    seen: set[str] = set()
    with open("hits.jsonl", "a") as out:
        for q in sys.argv[2:]:
            titles = [t for t in commons.search(q, n) if t not in seen]
            seen.update(titles)
            print(f"## {q}: {len(titles)}")
            for title, ii in commons.info(titles).items():
                row = {"q": q, "title": title, "w": ii.get("width"), "h": ii.get("height"),
                       "licence": meta(ii, "LicenseShortName"), "artist": meta(ii, "Artist")[:80],
                       "date": meta(ii, "DateTimeOriginal")[:40], "credit": meta(ii, "Credit")[:120],
                       "url": ii["url"], "thumb": ii.get("thumburl"), "page": ii["descriptionurl"]}
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(f"  {row['w']}x{row['h']} | {row['licence']} | {title[5:90]} | {row['date']} | {row['credit'][:70]}")


if __name__ == "__main__":
    main()
