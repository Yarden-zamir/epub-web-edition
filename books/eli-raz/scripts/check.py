# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Build the release edition and check it. The default is light, for this machine; the heavy checks run in GitHub Actions.

Usage, from the repo root (flags combine):
  uv run books/eli-raz/scripts/check.py                  default: ingest outputs from the shared cache, build_epub,
                                                          build_web, check_release, and preview.html (a06)
  --preview a06,a14     the units of preview.html (books/eli-raz/dist/release/web/preview.html)
  --ingest              run both ingests when their inputs are not in the cache (heavy: minutes of CPU)
  --compare-ingest      with --ingest: when the ingests run, also run the complete ingest in a copy of the whole book
                        folder and fail when it differs from the copy of INGEST_INPUTS (a missing input)
  --epubcheck           EPUBCheck (Java), skipped when these exact EPUB bytes passed before
  --smoke               quick smoke test (Playwright): errors, overflow, axe on a sample (scripts/smoke_site.py)
  --axe-full            smoke test with a fresh load at every width and scheme and axe on the whole page
  --explorables         every interactive explainer (scripts/check_explorables.py), screenshots in dist/explorables
  --record              videos, traces, screenshots and load timings (scripts/record_site.py) in dist/record
  --sample              tools/verify.py on the sample edition (widths, interaction, speed)
  --gate                --ingest --epubcheck --smoke: what main's deploy workflow runs on every push
  --full                every check above; ingests run again in a copy of INGEST_INPUTS and of the whole book folder,
                        and fail when the two differ; EPUBCheck runs again
  --no-build            use the build that is already in books/eli-raz/dist/release (CI jobs after the build job)
  --advisory sample     comma-separated groups (epubcheck, smoke, explorables, record, sample) whose failure only
                        warns (a GitHub annotation in CI) and does not fail the run

Agents do not run the heavy checks on the build machine: .github/workflows/check.yml runs them on GitHub for each PR
(--gate), the merge queue (every check) and every night (--full); docs/WORKFLOW.md, Checks.
Shared cache (all worktrees on this machine): ~/.cache/eli-raz, or $ELI_RAZ_CACHE.
The heavy flags need .tools/ in the repo root: EPUBCheck 5.4.0 in .tools/epubcheck-5.4.0/, a Java runtime in
.tools/jdk-*/, axe-core 4.14.0 in .tools/axe/package/, and the Chromium of Playwright 1.64.1 (see smoke_site.py).
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CONTENT = Path(__file__).resolve().parent.parent
PIPELINE = CONTENT.parent.parent
TOOLS = PIPELINE / ".tools"
SMOKE = CONTENT / "scripts" / "smoke_site.py"
EXPLORABLES = CONTENT / "scripts" / "check_explorables.py"
RECORD = CONTENT / "scripts" / "record_site.py"
AXE = TOOLS / "axe" / "package" / "axe.min.js"
EPUB = CONTENT / "dist" / "release" / "eli-raz.epub"
WEB = CONTENT / "dist" / "release" / "web"
CACHE = Path(os.environ.get("ELI_RAZ_CACHE", Path.home() / ".cache" / "eli-raz"))
# Newest ingest results kept in the cache; each holds both EPUB source trees (about 50 MB). CI keeps fewer.
INGEST_CACHE_KEEP = int(os.environ.get("ELI_RAZ_INGEST_KEEP", "8"))
# Every file that tools/ingest_pdf.py reads (folders count with all their files). Known limit: this list is kept by
# hand. Revisit it when ingest_pdf.py reads a new file or folder. The complete ingest runs in a copy of exactly these
# files; `--full` also runs it in a copy of the whole book folder and fails when the two differ, so a missing entry
# shows up there (ingest may skip a missing file without an error, as it did once for pages.csv).
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
    # The review status and notes of each page carry over from the last pages.csv.
    CONTENT / "inventory" / "pages.csv",
    CONTENT / "inventory-release" / "pages.csv",
]
# What each ingest writes into the book folder (tools/ingest_pdf.py: out, write_inventory, write_ids). Only these
# move between the book folder and the cache; other files in the inventory folders (coverage.csv) stay as they are.
INVENTORY_FILES = ["pages.csv", "assets.csv", "issues.csv", "figures.csv"]
COMPLETE_OUTPUTS = ["epub-src"] + [f"inventory/{n}" for n in INVENTORY_FILES]
RELEASE_OUTPUTS = ["epub-src-release", "ids.csv", "id-moves.csv"] + [f"inventory-release/{n}" for n in INVENTORY_FILES]


def say(text: str) -> None:
    print(text, flush=True)


def files_of(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else [root]


def ingest_key() -> str:
    """The hash of the names and bytes of every ingest input."""
    digest = hashlib.sha256()
    for root in INGEST_INPUTS:
        for f in files_of(root):
            digest.update(str(f.relative_to(PIPELINE)).encode() + b"\0" + f.read_bytes() + b"\0")
    return digest.hexdigest()


def command(cmd: list[str | Path]) -> list[str]:
    say(f"$ {' '.join(str(c).removeprefix(str(PIPELINE) + '/') for c in cmd[:4])} …")
    return [str(c) for c in cmd]


def finish(args: list[str], code: int, out: str, start: float, advisory: str | None = None) -> str:
    """Print a command's output and time; exit when it failed, unless it is advisory (then warn)."""
    say(out[-4000:].rstrip())
    say(f"({time.monotonic() - start:.0f} s: {' '.join(args[:3])[-70:]})")
    if code != 0 and advisory:
        # GitHub Actions shows this line as a warning annotation; gh run view lists it.
        say(f"::warning title=advisory check failed::{advisory}: {' '.join(args[:3])[-70:]} exited {code}; it does not block")
    elif code != 0:
        sys.exit(f"{args[:3]} failed with exit code {code}")
    return out


def run(cmd: list[str | Path], cwd: Path | None = None) -> str:
    """Run a command; exit when it fails."""
    args, start = command(cmd), time.monotonic()
    res = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return finish(args, res.returncode, res.stdout, start)


def run_parallel(cmds: list[tuple[list[str | Path], Path | None]], advisory: dict[int, str] | None = None) -> list[str]:
    """Run independent commands at the same time; exit when one fails, after all ended.
    advisory: index of a command -> its group name; its failure only warns."""
    start = time.monotonic()
    procs = [(args, subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
             for args, cwd in ((command(c), cwd) for c, cwd in cmds)]
    outs = [(args, proc, proc.communicate()[0]) for args, proc in procs]
    return [finish(args, proc.returncode, out, start, (advisory or {}).get(i)) for i, (args, proc, out) in enumerate(outs)]


def copy_into(src: Path, dest: Path) -> None:
    """Replace dest (a file or a folder) with a copy of src."""
    if dest.is_dir():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)


def run_ingests(compare: bool) -> None:
    """Both ingests at the same time. The complete one runs in a copy of the inputs, because both modes rewrite
    ids.csv and id-moves.csv; the book folder keeps the release ingest's lists, as with the two run in turn.
    compare: also run the complete ingest in a copy of the whole book folder, and fail when its outputs differ."""
    uv = ["uv", "run"]
    with tempfile.TemporaryDirectory(prefix="eli-raz-complete-") as tmp:
        copy = Path(tmp) / "content"
        for root in INGEST_INPUTS:
            if root.is_relative_to(CONTENT):
                copy_into(root, copy / root.relative_to(CONTENT))
        jobs: list[tuple[list[str | Path], Path | None]] = [
            ([*uv, "tools/ingest_pdf.py", copy], PIPELINE),
            ([*uv, "tools/ingest_pdf.py", CONTENT, "--release"], PIPELINE),
        ]
        whole = Path(tmp) / "whole"
        if compare:
            skip = shutil.ignore_patterns("dist", "work", "epub-src", "epub-src-release")
            shutil.copytree(CONTENT, whole, ignore=skip)
            jobs.append(([*uv, "tools/ingest_pdf.py", whole], PIPELINE))
        run_parallel(jobs)
        if compare:
            differ = [n for n in COMPLETE_OUTPUTS if not same_tree(copy / n, whole / n)]
            if differ:
                sys.exit(f"ingest reads a file that INGEST_INPUTS misses: {differ} differ between a copy of "
                         "INGEST_INPUTS and a copy of the whole book folder")
            say("complete ingest: a copy of INGEST_INPUTS gives the same outputs as the whole book folder")
        for name in COMPLETE_OUTPUTS:
            copy_into(copy / name, CONTENT / name)


def same_tree(a: Path, b: Path) -> bool:
    """Same file names and bytes."""
    names = [p.relative_to(a) for p in files_of(a)]
    return names == [p.relative_to(b) for p in files_of(b)] and all(
        (a / n).read_bytes() == (b / n).read_bytes() for n in names)


def ingest(allowed: bool, fresh: bool, compare: bool) -> None:
    """Fill the book folder with the ingest outputs: from the shared cache, or by running both ingests (allowed)."""
    key = ingest_key()
    cached = CACHE / "ingest" / key
    if cached.is_dir() and not fresh:
        restore(cached)
        say(f"ingest inputs unchanged ({key[:12]}): outputs from {cached}")
        return
    if not allowed:
        # Light default: no ingest on this machine. The preview then shows the last ingest; CI ingests the change.
        note = "ingest inputs changed; this build uses the last ingest. CI ingests the change; --ingest ingests here"
        if (CONTENT / "epub-src-release").is_dir():
            say(f"{note} (heavy). Using the ingest in {CONTENT}.")
            return
        entries = sorted((CACHE / "ingest").glob("[0-9a-f]*"), key=lambda e: e.stat().st_mtime) if (CACHE / "ingest").is_dir() else []
        if not entries:
            sys.exit("No ingest on this machine yet. Run once with --ingest (heavy), or let CI check the change.")
        restore(entries[-1])
        say(f"{note} (heavy). Using the newest cached ingest, {entries[-1].name[:12]}, of any worktree.")
        return
    run_ingests(compare=compare)
    # Also store under the key after the ingest: a run that adds IDs changes ids.csv, and the next run starts from it.
    for k in {key, ingest_key()}:
        save_ingest(k)
    prune(CACHE / "ingest", INGEST_CACHE_KEEP)


def restore(cached: Path) -> None:
    for name in COMPLETE_OUTPUTS + RELEASE_OUTPUTS:
        copy_into(cached / name, CONTENT / name)
    os.utime(cached)  # Newest use first when the cache is pruned.


def save_ingest(key: str) -> None:
    target = CACHE / "ingest" / key
    if target.is_dir():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".tmp-", dir=target.parent))
    for name in COMPLETE_OUTPUTS + RELEASE_OUTPUTS:
        copy_into(CONTENT / name, tmp / name)
    try:
        tmp.rename(target)  # Atomic: another worktree may save the same key at the same time.
    except OSError:
        shutil.rmtree(tmp)


def prune(folder: Path, keep: int) -> None:
    entries = sorted((p for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".")),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    for old in entries[keep:]:
        shutil.rmtree(old, ignore_errors=True)


def preview(units: list[str]) -> None:
    """Write WEB/preview.html: the built page with only these units in its main part. Links to other units break."""
    page = (WEB / "index.html").read_text(encoding="utf-8")
    main_open = page.index('<main id="read"')
    body_start = page.index(">", main_open) + 1
    body_end = page.index("</main>", body_start)
    # Each unit is one <div class="doc" data-src=…> child of <main> (tools/build_web.py); split on that opening tag.
    # A part between two units (the places section) stays with the unit before it.
    marker = '<div class="doc" '
    head, *docs = page[body_start:body_end].split(marker)
    kept = [d for d in docs if any(f'<section id="{u}"' in d for u in units)]
    missing = [u for u in units if not any(f'<section id="{u}"' in d for d in kept)]
    if missing:
        sys.exit(f"--preview: no unit {missing} in {WEB / 'index.html'}")
    out = page[:body_start] + head + "".join(marker + d for d in kept) + page[body_end:]
    (WEB / "preview.html").write_text(out, encoding="utf-8")
    say(f"preview: {WEB / 'preview.html'} ({len(out) // 1000} KB, units {', '.join(units)})")
    say(f"serve it: uv run python -m http.server -d {WEB} 8000, then open http://127.0.0.1:8000/preview.html")


def epubcheck(force: bool) -> tuple[list[str | Path], Path | None] | None:
    """The EPUBCheck command, or None when these exact EPUB bytes passed before."""
    sha = hashlib.sha256(EPUB.read_bytes()).hexdigest()
    if (CACHE / "epubcheck-ok" / sha).exists() and not force:
        say(f"EPUBCheck: these EPUB bytes passed before ({sha[:12]}), skipped")
        return None
    java = next(TOOLS.glob("jdk-*/bin/java"))  # StopIteration names a missing Java runtime.
    return [java, "-jar", TOOLS / "epubcheck-5.4.0" / "epubcheck.jar", EPUB], None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for flag in ("ingest", "compare-ingest", "epubcheck", "smoke", "axe-full", "explorables", "record", "sample", "gate", "full", "no-build"):
        ap.add_argument(f"--{flag}", action="store_true")
    ap.add_argument("--preview", metavar="UNITS", default="a06", help="comma-separated unit IDs of preview.html")
    ap.add_argument("--advisory", metavar="GROUPS", default="", help="groups whose failure only warns")
    a = ap.parse_args()
    started = time.monotonic()
    uv: list[str | Path] = ["uv", "run"]
    if not a.no_build:
        EPUB.parent.mkdir(parents=True, exist_ok=True)
        ingest(allowed=a.ingest or a.gate or a.full, fresh=a.full, compare=a.compare_ingest or a.full)
        run([*uv, "tools/build_epub.py", CONTENT / "epub-src-release", EPUB], PIPELINE)
        run([*uv, "tools/build_web.py", EPUB, WEB, CONTENT / "site" / "enhancements.json"], PIPELINE)
        # check_release also runs tools/check_size.py: the EPUB at most 24 MB, under the 25 MB file limit of kitshn.
        run([*uv, "tools/check_release.py", CONTENT, EPUB, WEB], PIPELINE)
        preview(a.preview.split(","))
    groups = set(filter(None, a.advisory.split(",")))
    unknown = groups - {"epubcheck", "smoke", "explorables", "record", "sample"}
    if unknown:
        sys.exit(f"--advisory: unknown groups {sorted(unknown)}")
    heavy: list[tuple[list[str | Path], Path | None]] = []
    names: list[str] = []  # The group of each heavy command, in order.
    check = epubcheck(force=a.full) if a.epubcheck or a.gate or a.full else None
    if check:
        heavy.append(check)
        names.append("epubcheck")
    if a.smoke or a.gate or a.axe_full or a.full:
        heavy.append(([*uv, SMOKE, WEB, AXE] + (["--axe-full"] if a.axe_full or a.full else []), None))
        names.append("smoke")
    if a.explorables or a.full:
        heavy.append(([*uv, EXPLORABLES, WEB, AXE, CONTENT / "dist" / "explorables"], None))
        names.append("explorables")
    if a.record or a.full:
        heavy.append(([*uv, RECORD, WEB, CONTENT / "dist" / "record"], None))
        names.append("record")
    if a.sample or a.full:
        heavy.append(([*uv, "tools/verify.py"], PIPELINE))
        names.append("sample")
    outs = run_parallel(heavy, {i: n for i, n in enumerate(names) if n in groups}) if heavy else []
    if check and "0 fatals / 0 errors" not in outs[0]:
        if "epubcheck" not in groups:
            sys.exit("EPUBCheck reported errors")
        say("::warning title=advisory check failed::epubcheck: EPUBCheck reported errors; it does not block")
    elif check:  # Only bytes that passed skip EPUBCheck next time.
        ok = CACHE / "epubcheck-ok"
        ok.mkdir(parents=True, exist_ok=True)
        (ok / hashlib.sha256(EPUB.read_bytes()).hexdigest()).touch()
    say(f"check ok in {time.monotonic() - started:.0f} s")


if __name__ == "__main__":
    main()
