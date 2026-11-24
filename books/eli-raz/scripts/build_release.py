# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Build and check the release web edition, as GitHub Actions does before each deploy.

Usage: uv run books/eli-raz/scripts/build_release.py
The pipeline is the root of this repo. It needs .tools/ there (EPUBCheck 5.4.0 in .tools/epubcheck-5.4.0/,
a Java runtime in .tools/jdk-*/, axe-core 4.14.0 in .tools/axe/package/).
The smoke test needs the Chromium of Playwright 1.64.1 (see scripts/smoke_site.py).
Output: dist/release/eli-raz.epub and dist/release/web in the book folder (books/eli-raz). Exits 1 when a step fails.
The repo workflow .github/workflows/kitshn.yml runs this script and deploys dist/release/web.

Both ingests run only when their inputs change: work/ingest-key holds the hash of INGEST_INPUTS from the last
ingest. CI keeps it with epub-src/ and epub-src-release/ in its cache between runs.
"""

import hashlib
import subprocess
import sys
import time
from pathlib import Path

CONTENT = Path(__file__).resolve().parent.parent
PIPELINE = CONTENT.parent.parent
SMOKE = CONTENT / "scripts" / "smoke_site.py"
INGEST_KEY = CONTENT / "work" / "ingest-key"  # Not in epub-src-release/: build_epub.py packs that folder.
# Every file that tools/ingest_pdf.py reads (folders count with all their files). Known limit: this list is kept by
# hand. Revisit it when ingest_pdf.py reads a new file or folder, or a skipped ingest could serve stale book content.
INGEST_INPUTS = [
    PIPELINE / "tools" / "ingest_pdf.py",
    PIPELINE / "epub-src" / "OEBPS" / "fonts",  # Defaults when book.toml names no fonts or css.
    PIPELINE / "epub-src" / "OEBPS" / "css" / "book.css",
    CONTENT / "book.toml",
    CONTENT / "book.css",
    CONTENT / "ids.csv",
    CONTENT / "id-moves.csv",
    CONTENT / "source",
    CONTENT / "replacements",
    CONTENT / "fonts",
    # book.toml [additions] data: tables, cross-references, glossary and timeline appendices.
    CONTENT / "site" / "enhancements.json",
    CONTENT / "site" / "crosslinks.json",
    CONTENT / "site" / "glossary.json",
    CONTENT / "site" / "timeline.json",
]


def ingest_key() -> str:
    """The hash of the names and bytes of every ingest input."""
    digest = hashlib.sha256()
    for root in INGEST_INPUTS:
        files = sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else [root]
        for f in files:
            digest.update(str(f.relative_to(PIPELINE)).encode() + b"\0" + f.read_bytes() + b"\0")
    return digest.hexdigest()


def command(cmd: list[str | Path]) -> list[str]:
    print(f"$ {' '.join(map(str, cmd[:3]))} …", flush=True)
    return [str(c) for c in cmd]


def finish(cmd: list[str], res: subprocess.CompletedProcess[str] | subprocess.Popen[str], out: str, start: float) -> str:
    """Print a command's output and time; exit when it failed."""
    print(out[-4000:], flush=True)
    print(f"({time.monotonic() - start:.0f} s: {' '.join(cmd[:3])[-80:]})", flush=True)
    if res.returncode != 0:
        sys.exit(f"{cmd[:3]} failed with exit code {res.returncode}")
    return out


def run(cmd: list[str | Path], cwd: Path | None = None) -> str:
    """Run a command with its output on the console; exit when it fails."""
    args, start = command(cmd), time.monotonic()
    res = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, text=True)
    return finish(args, res, res.stdout, start)


def run_parallel(cmds: list[list[str | Path]]) -> list[str]:
    """Run independent commands at the same time; exit when one fails, after all ended."""
    start = time.monotonic()
    started = [(args, subprocess.Popen(args, stdout=subprocess.PIPE, text=True)) for args in map(command, cmds)]
    outs = []
    for args, proc in started:
        out = proc.communicate()[0]
        print(f"({time.monotonic() - start:.0f} s until {' '.join(args[:3])[-60:]} ended)", flush=True)
        outs.append((args, proc, out))
    return [finish(args, proc, out, start) for args, proc, out in outs]


def main() -> None:
    if len(sys.argv) != 1:
        sys.exit(__doc__)
    tools = PIPELINE / ".tools"
    java = next(tools.glob("jdk-*/bin/java"))  # StopIteration names a missing Java runtime.
    epub = CONTENT / "dist" / "release" / "eli-raz.epub"
    web = CONTENT / "dist" / "release" / "web"
    epub.parent.mkdir(parents=True, exist_ok=True)
    uv = ["uv", "run"]
    key = ingest_key()
    built = all((CONTENT / d).is_dir() for d in ("epub-src", "epub-src-release"))
    if built and INGEST_KEY.is_file() and INGEST_KEY.read_text() == key:
        print(f"ingest inputs unchanged ({key[:12]}): both ingests skipped", flush=True)
    else:
        # Not in parallel: both modes read and rewrite ids.csv and id-moves.csv.
        run([*uv, "tools/ingest_pdf.py", CONTENT], PIPELINE)  # Complete edition: check_release compares against it.
        run([*uv, "tools/ingest_pdf.py", CONTENT, "--release"], PIPELINE)
        INGEST_KEY.parent.mkdir(exist_ok=True)
        INGEST_KEY.write_text(key)
    run([*uv, "tools/build_epub.py", CONTENT / "epub-src-release", epub], PIPELINE)
    run([*uv, "tools/build_web.py", epub, web, CONTENT / "site" / "enhancements.json"], PIPELINE)
    # check_release also runs tools/check_size.py: the EPUB at most 24 MB, under the 25 MB static asset limit of kitshn.
    run([*uv, "tools/check_release.py", CONTENT, epub, web], PIPELINE)
    epubcheck, _ = run_parallel([
        [java, "-jar", tools / "epubcheck-5.4.0" / "epubcheck.jar", epub],
        [*uv, SMOKE, web, tools / "axe" / "package" / "axe.min.js"],
    ])
    if "0 fatals / 0 errors" not in epubcheck:
        sys.exit("EPUBCheck reported errors")


if __name__ == "__main__":
    main()
