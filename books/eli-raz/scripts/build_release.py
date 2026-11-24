# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Build and check the release web edition, as GitHub Actions does before each deploy.

Usage: uv run scripts/build_release.py PIPELINE_DIR
PIPELINE_DIR is a checkout of Yarden-zamir/epub-web-edition with .tools/ (EPUBCheck 5.4.0 in
.tools/epubcheck-5.4.0/, a Java runtime in .tools/jdk-*/, axe-core 4.14.0 in .tools/axe/package/).
The smoke test needs the Chromium of Playwright 1.64.1 (see scripts/smoke_site.py).
Output: dist/release/eli-raz.epub and dist/release/web in this content folder. Exits 1 when a step fails.
.github/workflows/kitshn.yml runs this script and deploys dist/release/web.
"""

import subprocess
import sys
from pathlib import Path

CONTENT = Path(__file__).resolve().parent.parent
SMOKE = CONTENT / "scripts" / "smoke_site.py"


def run(cmd: list[str | Path], cwd: Path | None = None) -> str:
    """Run a command with its output on the console; exit when it fails."""
    print(f"$ {' '.join(map(str, cmd[:3]))} …", flush=True)
    res = subprocess.run([str(c) for c in cmd], cwd=cwd, stdout=subprocess.PIPE, text=True)
    print(res.stdout[-4000:], flush=True)
    if res.returncode != 0:
        sys.exit(f"{cmd[:3]} failed with exit code {res.returncode}")
    return res.stdout


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    pipeline = Path(sys.argv[1]).resolve()
    tools = pipeline / ".tools"
    java = next(tools.glob("jdk-*/bin/java"))  # StopIteration names a missing Java runtime.
    epub = CONTENT / "dist" / "release" / "eli-raz.epub"
    web = CONTENT / "dist" / "release" / "web"
    epub.parent.mkdir(parents=True, exist_ok=True)
    uv = ["uv", "run"]
    run([*uv, "tools/ingest_pdf.py", CONTENT], pipeline)  # Complete edition: check_release compares against it.
    run([*uv, "tools/ingest_pdf.py", CONTENT, "--release"], pipeline)
    run([*uv, "tools/build_epub.py", CONTENT / "epub-src-release", epub], pipeline)
    run([*uv, "tools/build_web.py", epub, web, CONTENT / "site" / "enhancements.json"], pipeline)
    # check_release also runs tools/check_size.py: the EPUB at most 24 MB, under the 25 MB static asset limit of kitshn.
    run([*uv, "tools/check_release.py", CONTENT, epub, web], pipeline)
    out = run([java, "-jar", tools / "epubcheck-5.4.0" / "epubcheck.jar", epub])
    if "0 fatals / 0 errors" not in out:
        sys.exit("EPUBCheck reported errors")
    run([*uv, SMOKE, web, tools / "axe" / "package" / "axe.min.js"])


if __name__ == "__main__":
    main()
