# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Land a lane's commits on main after GitHub Actions checked them. Run it from your worktree, with your work committed.

Usage: uv run books/eli-raz/scripts/lane_push.py <lane-name> [--record]
--record: also record videos, traces, screenshots and load timings (a second billed job). A commit message with
"[record]" does the same.

1. git fetch origin, then git rebase origin/main (with --autostash), so the checked commit is the commit that lands.
2. git push --force-with-lease origin HEAD:lane/<lane-name>. The lane branch is yours alone; each rebase rewrites it.
3. Wait for the "checks" run of that commit (.github/workflows/checks.yml). It prints the run address, the command
   that downloads its artifacts (the build, explainer screenshots, the sample report, and videos and traces when
   recorded), and the warnings of advisory checks, which do not block.
4. When the checks pass: if main did not move, git push origin HEAD:main. If main moved and its new commits touch a
   file that your commits touch, back to step 1 (at most MAX_ROUNDS times). If they touch other files, rebase and push
   without a new check; main's kitshn.yml checks again before it deploys anything.
Exits 1 when the checks fail, the rebase stops on a conflict, or main keeps moving.
"""

import json
import subprocess
import sys
import time

MAX_ROUNDS = 3
WORKFLOW = "checks"  # The name in .github/workflows/checks.yml. Matched by name: `gh run list -w` needs the file on main.
POLL_S = 15


def sh(*cmd: str, check: bool = True) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if check and res.returncode != 0:
        sys.exit(f"{' '.join(cmd)} failed:\n{res.stdout}{res.stderr}")
    return res.stdout.strip()


def say(text: str) -> None:
    print(text, flush=True)


def files(a: str, b: str) -> set[str]:
    return set(filter(None, sh("git", "diff", "--name-only", a, b).splitlines()))


def rebase() -> str:
    """Rebase on the newest main; the main commit that HEAD now sits on."""
    sh("git", "fetch", "-q", "origin")
    res = subprocess.run(["git", "rebase", "--autostash", "origin/main"], capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"The rebase on origin/main stopped:\n{res.stdout}{res.stderr}\n"
                 "Resolve it (git status), git rebase --continue, then run lane_push.py again.")
    return sh("git", "rev-parse", "origin/main")


def wait_for_checks(repo: str, branch: str, sha: str, event: str) -> None:
    """Wait for the checks run of this commit that this event started (push, or workflow_dispatch for --record)."""
    run = None
    for _ in range(40):  # The run appears a few seconds after the push.
        runs = json.loads(sh("gh", "run", "list", "-R", repo, "-b", branch, "-c", sha,
                             "--json", "databaseId,url,workflowName,event", "-L", "10"))
        found = [r for r in runs if r["workflowName"] == WORKFLOW and r["event"] == event]
        if found:
            run = found[0]
            break
        time.sleep(3)
    if run is None:
        sys.exit(f"No {WORKFLOW} run for {sha[:12]} on {branch} after 2 minutes. See: gh run list -R {repo} -b {branch}")
    rid = run["databaseId"]
    say(f"checks: {run['url']}")
    say(f"artifacts: gh run download {rid} -R {repo} -D dist/run-{rid}  (book-check; book-record when recorded)")
    last = ""
    while True:
        view = json.loads(sh("gh", "run", "view", str(rid), "-R", repo, "--json", "status,conclusion,jobs"))
        jobs = ", ".join(f"{j['name']} {j['conclusion'] or j['status']}" for j in view["jobs"])
        if jobs != last:
            say(f"  {jobs}")
            last = jobs
        if view["status"] == "completed":
            break
        time.sleep(POLL_S)
    for job in view["jobs"]:  # Advisory checks (check.py --advisory) warn without failing the run.
        notes = json.loads(sh("gh", "api", f"repos/{repo}/check-runs/{job['databaseId']}/annotations"))
        for n in notes:
            if n["title"] == "advisory check failed":
                say(f"  advisory, does not block: {n['message']}")
    if view["conclusion"] != "success":
        sys.exit(f"checks {view['conclusion']}: {run['url']}\nlogs of the failed steps: gh run view {rid} -R {repo} --log-failed")


def main() -> None:
    args = sys.argv[1:]
    record = "--record" in args
    names = [a for a in args if a != "--record"]
    if len(names) != 1 or not names[0] or "/" in names[0] or names[0].startswith("-"):
        sys.exit(__doc__)
    branch = f"lane/{names[0]}"
    repo = sh("gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner")
    for round_no in range(1, MAX_ROUNDS + 1):
        base = rebase()
        sha = sh("git", "rev-parse", "HEAD")
        if sha == base:
            sys.exit("Nothing to land: HEAD is origin/main.")
        mine = files(base, sha)
        say(f"round {round_no}: {sh('git', 'rev-list', '--count', f'{base}..{sha}')} commits on main {base[:12]}, pushing {branch}")
        sh("git", "push", "-q", "--force-with-lease", "origin", f"HEAD:{branch}")
        if record:
            # A manual run with recording; it replaces the push run of the same lane (one run per lane at a time).
            sh("gh", "workflow", "run", "checks.yml", "-R", repo, "--ref", branch, "-f", "record=true")
        wait_for_checks(repo, branch, sha, "workflow_dispatch" if record else "push")
        for _ in range(5):
            sh("git", "fetch", "-q", "origin")
            main_now = sh("git", "rev-parse", "origin/main")
            if main_now != base:
                overlap = mine & files(base, main_now)
                if overlap:
                    say(f"main moved and touches your files {sorted(overlap)[:5]}: checking again")
                    break
                say("main moved, other files only: rebase and push; main's deploy workflow checks the result")
                base = rebase()
            if subprocess.run(["git", "push", "-q", "origin", "HEAD:main"]).returncode == 0:
                say(f"landed {sh('git', 'rev-parse', '--short', 'HEAD')} on main; the deploy: gh run list -R {repo} -w kitshn.yml -b main -L 1")
                return
            say("main moved during the push; trying again")
        else:
            sys.exit("git push origin HEAD:main failed 5 times; read the error above.")
    sys.exit(f"main kept moving over your files for {MAX_ROUNDS} rounds; run lane_push.py again.")


if __name__ == "__main__":
    main()
