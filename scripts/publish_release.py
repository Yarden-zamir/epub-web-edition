# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Publish the live book site when either repo's origin/main changes.

Builds from clean worktrees of origin/main of both repos (never from a working copy that agents edit),
runs the release checks, and publishes with kitshn only when every check passes.
The build needs the private source PDF on this machine, so this runs here, not in GitHub Actions.

Usage: uv run scripts/publish_release.py [--force]
Runs from a systemd user timer (scripts/systemd/eli-raz-publish.timer). State and logs: ~/.local/state/eli-raz-publish/.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = Path.home()
PIPELINE = HOME / "Github" / "epub-web-edition"
CONTENT = HOME / "Github" / "eli-raz-edition"
STATE = HOME / ".local" / "state" / "eli-raz-publish"
EPUB_LIMIT = 25_000_000  # kitshn static asset limit; the EPUB is served as a download.
SMOKE = Path(__file__).resolve().parent / "smoke_site.py"


def run(cmd: list[str], cwd: Path | None = None, log: Path | None = None) -> str:
    """Run a command; raise with its output when it fails."""
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if log:
        with log.open("a") as f:
            f.write(f"$ {' '.join(map(str, cmd[:3]))} …\n{res.stdout[-4000:]}{res.stderr[-4000:]}\n")
    if res.returncode != 0:
        raise RuntimeError(f"{cmd[:3]} failed ({res.returncode}): {(res.stdout + res.stderr)[-1500:]}")
    return res.stdout


def head(repo: Path) -> str:
    run(["git", "-C", str(repo / ".bare"), "fetch", "-q", "origin", "main:refs/remotes/origin/main"])
    return run(["git", "-C", str(repo / ".bare"), "rev-parse", "refs/remotes/origin/main"]).strip()


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    state_file = STATE / "last.json"
    last = json.loads(state_file.read_text()) if state_file.exists() else {}
    now = {"pipeline": head(PIPELINE), "content": head(CONTENT)}
    failed_file = STATE / "last-failed.json"
    failed = json.loads(failed_file.read_text()) if failed_file.exists() else {}
    # Build only new commits: skip what is live, and skip a pair that already failed until something new is pushed.
    if now in ({k: last.get(k) for k in now}, {k: failed.get(k) for k in now}) and "--force" not in sys.argv:
        return
    log = STATE / f"build-{time.strftime('%Y%m%d-%H%M%S')}.log"
    tmp = Path(tempfile.mkdtemp(prefix="eli-raz-publish-"))
    p, c = tmp / "pipeline", tmp / "content"
    try:
        run(["git", "-C", str(PIPELINE / ".bare"), "worktree", "add", "--detach", str(p), now["pipeline"]])
        run(["git", "-C", str(CONTENT / ".bare"), "worktree", "add", "--detach", str(c), now["content"]])
        (p / ".tools").symlink_to(PIPELINE / "main" / ".tools")
        uv = shutil.which("uv") or str(HOME / ".local" / "bin" / "uv")
        run([uv, "run", "tools/ingest_pdf.py", str(c)], p, log)  # Complete edition: check_release compares against it.
        run([uv, "run", "tools/ingest_pdf.py", str(c), "--release"], p, log)
        epub = c / "dist" / "release" / "eli-raz.epub"
        web = c / "dist" / "release" / "web"
        epub.parent.mkdir(parents=True)
        run([uv, "run", "tools/build_epub.py", str(c / "epub-src-release"), str(epub)], p, log)
        if epub.stat().st_size > EPUB_LIMIT:
            raise RuntimeError(f"release EPUB is {epub.stat().st_size / 1e6:.1f} MB, over the 25 MB download limit")
        run([uv, "run", "tools/build_web.py", str(epub), str(web), str(c / "site" / "enhancements.json")], p, log)
        run([uv, "run", "tools/check_release.py", str(c), str(epub), str(web)], p, log)
        java = next((PIPELINE / "main" / ".tools").glob("jdk-*/bin/java"))
        out = run([str(java), "-jar", str(PIPELINE / "main" / ".tools" / "epubcheck-5.4.0" / "epubcheck.jar"), str(epub)], log=log)
        if "0 fatals / 0 errors" not in out:
            raise RuntimeError("EPUBCheck reported errors")
        run([uv, "run", str(SMOKE), str(web)], log=log)
        run(["kitshn", "publish", str(web), "--name", "eli-raz"], c, log)
        state_file.write_text(json.dumps(now) + "\n")
        print(f"published pipeline {now['pipeline'][:8]} content {now['content'][:8]}")
    except Exception as e:
        # Keep the failure visible; the next pushed fix retries on the next timer run.
        failed_file.write_text(json.dumps(now) + "\n")
        (STATE / "last-error.txt").write_text(f"{time.ctime()} pipeline {now['pipeline'][:8]} content {now['content'][:8]}\n{e}\nlog: {log}\n")
        raise
    finally:
        run(["git", "-C", str(PIPELINE / ".bare"), "worktree", "remove", "--force", str(p)]) if p.exists() else None
        run(["git", "-C", str(CONTENT / ".bare"), "worktree", "remove", "--force", str(c)]) if c.exists() else None
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
