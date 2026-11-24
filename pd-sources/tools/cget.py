# /// script
# requires-python = ">=3.15"
# ///
"""Download a Commons file thumbnail (default 1920 px wide) into work/pd-sources/<name>/.

Usage: uv run --script cget.py <name> "<File:title>" [width]
Records the Commons metadata (licence, credit, artist, full size) in commons.json next to the file.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import commons  # noqa: E402
import fetch  # noqa: E402


def main(name: str, title: str, width: str = "1920") -> None:
    r = commons.api({"action": "query", "titles": title, "prop": "imageinfo",
                     "iiprop": "url|size|extmetadata|sha1", "iiurlwidth": width})
    page = next(iter(r["query"]["pages"].values()))
    if "imageinfo" not in page:
        raise SystemExit(f"not found: {title}")
    ii = page["imageinfo"][0]
    url = ii["thumburl"] if ii["width"] > int(width) else ii["url"]
    fetch.main(name, url, "image" + Path(url.split("?")[0]).suffix.lower())
    keep = {k: ii["extmetadata"].get(k, {}).get("value") for k in
            ("LicenseShortName", "License", "UsageTerms", "Artist", "Credit", "DateTimeOriginal", "ImageDescription")}
    (fetch.ROOT / name / "commons.json").write_text(json.dumps(
        {"title": title, "page": ii["descriptionurl"], "original": ii["url"], "width": ii["width"],
         "height": ii["height"], "sha1": ii["sha1"], "meta": keep}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
