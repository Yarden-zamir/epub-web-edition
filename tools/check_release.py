# /// script
# requires-python = ">=3.15"
# dependencies = ["pymupdf==1.28.2"]
# ///
"""Check that a release build leaves out every withheld or replaced image and carries every edition credit.

Usage: uv run tools/check_release.py CONTENT_DIR RELEASE_EPUB WEB_DIR

Checks, from book.toml [release]:
- no file in the EPUB or the web folder has the bytes of a changed image (PDF stream, or the
  complete build's derived file in CONTENT_DIR/epub-src/OEBPS/images);
- each withheld or replaced figure, and each credited figure, carries its edition span in the EPUB text;
- the EPUB keeps its size budget (tools/check_size.py: at most 24 MB, each image at most 1 MB).
Exits 1 when a check fails.
"""

import hashlib
import html
import sys
import tomllib
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_size import over_budget  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    content, epub, web = (Path(a).resolve() for a in sys.argv[1:4])
    cfg = tomllib.loads((content / "book.toml").read_text(encoding="utf-8"))
    release = cfg["release"]
    doc = pymupdf.open(content / cfg["pdf"])
    banned: dict[str, str] = {}
    for change in release.get("change", []):
        stem = change["image"]
        xref = int(stem.split("-x")[1])
        banned[sha(doc.extract_image(xref)["image"])] = f"{stem} PDF stream"
        for derived in (content / "epub-src" / "OEBPS" / "images").glob(f"{stem}*"):
            banned[sha(derived.read_bytes())] = f"{stem} derived file {derived.name}"
    leaks = []
    with zipfile.ZipFile(epub) as z:
        for name in z.namelist():
            if (hit := banned.get(sha(z.read(name)))):
                leaks.append(f"EPUB {name}: {hit}")
        # Text content per document (notes may hold markup, such as a left-to-right span).
        docs = [z.read(n) for n in z.namelist() if n.endswith(".xhtml") and "/facsimile" not in n and "/fx-" not in n]
        text = "\n".join(" ".join("".join(ET.fromstring(d).itertext()).split()) for d in docs)
    for path in web.rglob("*"):
        if path.is_file() and (hit := banned.get(sha(path.read_bytes()))):
            leaks.append(f"web {path.relative_to(web)}: {hit}")
    missing = []
    for change in release.get("change", []):
        if " ".join(change["note"].split()) not in text:
            missing.append(f"{change['image']}: edition note missing")
    for credit in release.get("credit", []):
        if " ".join(credit["text"].split()) not in text:
            missing.append(f"{credit['image']}: edition credit missing")
    for notice in release.get("notice", []):
        if " ".join(notice["text"].split()) not in text:
            missing.append(f"release notice missing: {notice['text'][:40]}")
    missing += over_budget(epub)
    print(f"changed images {len(release.get('change', []))} | banned files {len(banned)} | leaks {len(leaks)}")
    print(f"credits {len(release.get('credit', []))} | missing notes or credits {len(missing)}")
    for line in leaks + missing:
        print(" ", line)
    sys.exit(1 if leaks or missing else 0)


if __name__ == "__main__":
    main()
