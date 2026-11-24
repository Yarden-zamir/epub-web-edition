# /// script
# requires-python = ">=3.15"
# ///
"""List files and subcategories of a Commons category.

Usage: uv run --script ccat.py "Category:Name" [max files]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import commons  # noqa: E402


def main(cat: str, limit: str = "500") -> None:
    params = {"action": "query", "list": "categorymembers", "cmtitle": cat, "cmlimit": "500",
              "cmtype": "file|subcat"}
    count = 0
    while count < int(limit):
        r = commons.api(params)
        for m in r["query"]["categorymembers"]:
            print(m["title"])
            count += 1
        if "continue" not in r:
            break
        params.update(r["continue"])


if __name__ == "__main__":
    main(*sys.argv[1:])
