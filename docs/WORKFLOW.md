# Development workflow

This page is the map of how this repo is built: who works, where, and how a change reaches the two live sites. It links to the detailed docs and skills and does not repeat them.

Each section has two parts:

- **Generic**: the pattern. It works for any project with parallel coding agents and a GitHub merge queue.
- **Here**: the parts that depend on this repo: the EPUB pipeline, the Eli Raz edition and kitshn.

## Sync with Hot Cargo

This workflow copies [game-design-driven/cosmoteer-hot-cargo](https://github.com/game-design-driven/cosmoteer-hot-cargo) `docs/WORKFLOW.md`, its scripts, skills and workflows where they translate. Matched commit: `aa64aeaf661d81f199e167cf8e324f15eba1f5f2` (2026-11-24, "feat(autonomy): the Salvager preset waits for repairs like the Looter (#293)").

To sync later: in a clone of Hot Cargo, `git diff aa64aea..origin/main -- docs/WORKFLOW.md CLAUDE.md CONTRIBUTING.md scripts/queue-pr.sh scripts/agent-watch.sh scripts/prune-worktrees.sh scripts/check-pr-text.sh .github/workflows/check.yml .github/workflows/pr-text.yml .github/pull_request_template.md .claude/skills/hot-cargo-pr-flow .claude/skills/hot-cargo-coordinate`, adopt what translates, and update the commit above. Read the repo settings too (`gh api repos/game-design-driven/cosmoteer-hot-cargo/rulesets`, `.../branches/main/protection`).

Not copied, because this repo has no counterpart: the player's PC, test slots and the player hold; game test sets and the `### Game tests` block; spec number blocks; releases and installs; `requeue-flakes.sh` and `tests/flaky.txt` (no known flakes yet).

## Overview

```
coordinator thread ── briefs ──► one agent per area (own worktree, own branch, draft PR with PLAN.md)
                                   │ light local check (books/eli-raz/scripts/check.py)
                                   ▼
                                 PR ── check on the PR: ingest, build, check_release, EPUBCheck, quick smoke; pr-text
                                   │   preview (kitshn.yml): epub-web-edition-book-pr-<n>.yarden-zamir.com
                                   │ gh pr ready <n>; scripts/queue-pr.sh <n>
                                   ▼
                                 merge queue ── every check on main plus the PRs ahead (full axe, explainers, sample, PR text)
                                   ▼
                                 main ── deploy (kitshn.yml): eli-raz.yarden-zamir.com and the sample site
                                      └─ nightly full run (check.yml schedule), the safety net
```

## Agents and areas

Generic:
- A coordinator thread briefs the agents, watches them and judges failures (skill `eli-raz-coordinate`).
- One agent owns one area and has a queue of its features. Two agents never work on features that touch the same files.
- Each agent saves its progress so that a restart loses nothing: a `PLAN.md` on its branch, a draft PR with a checklist, a push after each step that builds (skill `eli-raz-pr-flow`).
- An agent ends with one message that starts with `FINAL REPORT`.

Here:
- Areas and file owners: `books/eli-raz/AGENTS-BRIEF.md` (Shared data files, Pipeline ownership).
- The agents run as Claude threads in T3 Code on one build machine with 4 cores. Heavy checks run on GitHub, not there (`books/eli-raz/AGENTS-BRIEF.md`, Checks).

## Branches and worktrees

Generic:
- The clone is a container folder: `.bare/` (the git repository), `_shared/` (local files that every worktree links), and one folder for each branch.
- Each agent works only in its own worktree: `$DOTFILES/bin/wt-new <type>/<name> origin/main` from `~/Github/epub-web-edition/main`.
- Branch names and commits use conventional commits (`feat/`, `fix/`, `docs/`, `ci/`, `perf/`, `refactor/`). Never credit an AI, a model or a tool.

Here:
- Builds write only ignored folders: `books/eli-raz/dist/`, `books/eli-raz/epub-src*/`, `dist/`. Downloads go to `books/eli-raz/work/` (ignored).
- The shared check cache of the build machine: `~/.cache/eli-raz` (ingest outputs by input hash, EPUBs that passed EPUBCheck, sections that passed axe).

## PR flow and the merge queue

Generic:
- Every change goes through a PR. Nobody pushes to `main`; the ruleset of `main` lets only the merge queue merge.
- The agent that owns a PR merges it: mark it ready, then `scripts/queue-pr.sh <n>` (auto-merge, and the queue entry if `gh pr merge --auto` adds none). Only the coordinator uses `--admin`, and only for a known flake.
- `main` has a GitHub merge queue. It tests each PR on top of the newest `main` and the PRs ahead of it. A PR does not have to be up to date with `main`; on a conflict, its owner merges `origin/main` into the branch (no rebase, no force-push).
- `main` gets one merge commit for each PR, titled with the PR title and `(#N)`. Read the history with `git log --first-parent --oneline`. Squash and rebase merges are off.
- PR text starts with 🤖, stays short, shows images of visible changes, and has a `### Decisions` block.
- Steps, failures and queue traps: skill `eli-raz-pr-flow`.

Here:
- Required check: `check` (`.github/workflows/check.yml`). The `pr-text` check (`.github/workflows/pr-text.yml`) runs on each edit of the text; the queue checks the text of each PR of its group again.
- Settings, as at Hot Cargo: merge queue with merge commits, ALLGREEN grouping, up to 5 PRs built and merged at once, minimum 1, no wait, 90 minutes for the checks; auto-merge on; head branches deleted after merge; "update branch" allowed; approval for workflows of fork PRs from outside contributors.

## Checks

Generic:
- One job builds once and runs the checks as parallel processes, so a run uses one runner.
- A PR run is fast and runs on every push. The merge queue runs every check. A full run on `main` every night is the safety net.

Here (`books/eli-raz/scripts/check.py`, `check.yml`):

| Run | Checks |
|---|---|
| Build machine, before a push | `check.py`: the ingest of the current inputs (shared cache, or one ingest run when the inputs are new), build, check_release, preview.html (no browser, no Java) |
| PR (each push) | `--gate`: ingest, build, check_release (withheld images, credits, size budget), EPUBCheck, quick smoke (errors, overflow, axe on a sample) |
| Merge queue | also axe on the whole page at every width and scheme, the explainers, tools/verify.py on the sample edition, the INGEST_INPUTS comparison when ingest runs, the PR text of each PR |
| Nightly, by hand | `--full`, also videos and traces; by hand with `gh workflow run check.yml --ref <branch> [-f record=true]` |
| Deploy (push to main) | `kitshn.yml`: `--gate` again, then kitshn deploys both apps |
| PR preview (each push) | `kitshn.yml`: the light check, then kitshn deploys the book to epub-web-edition-book-pr-<n>.yarden-zamir.com (public). The close of the PR removes it. The label `no-preview` and a PR from a fork skip it |
| PR that changes the site, advisory | `lighthouse.yml`: Lighthouse on the PR and its base, on one runner (scores in the job summary); never blocks the queue. The live site by hand: `gh workflow run lighthouse.yml -f url=https://eli-raz.yarden-zamir.com` |

## Flakes and failures

Generic:
- Before you call a failure unrelated, check the same check on `main`. A failure that shows only with the change belongs to the PR.
- A flaky or infrastructure failure in a check that the PR does not touch counts as passing. Note it in the PR in one line.
- Do not babysit a fragile check. Decide in one look if it is a bug or test variance, then move on.
- Steps: skill `eli-raz-pr-flow`, "A failure that looks unrelated".

## Deploy

Generic:
- Every push to `main` deploys. `main` only moves through the queue, so each deploy is a tested commit.

Here:
- `.github/workflows/kitshn.yml` builds the book again (`check.py --gate`) and deploys both apps of `kitshn.config.ts` with kitshn: the sample edition and the Eli Raz edition at https://eli-raz.yarden-zamir.com. A failed check deploys nothing; both sites keep their last deploy. Each PR of this repo also gets a preview of the book at epub-web-edition-book-pr-<n>.yarden-zamir.com, built with the light check.
- `.github/workflows/kitshn-retry.yml` reruns a failed kitshn deploy job once, when its log shows a failure of kitshn or of the network, not of the build.

## Public repo hygiene

Generic:
- No secrets and no personal data in tracked files: no home paths, machine names, IDs or tokens. Machine settings go in an ignored local file.

Here:
- The book is © its authors and photographers, all rights reserved, published with the family's permission; the MIT licence covers only the code and the sample (`books/eli-raz/NOTICE.md`).

## Coordinator tools

- `scripts/agent-watch.sh`: one line for each agent worktree.
- `scripts/prune-worktrees.sh`: removes merged worktrees.
- Rules for briefs, merges and failures: skill `eli-raz-coordinate`.

## Every script

Each file in `scripts/` and `.github/workflows/` starts with a header: what it does, its inputs, its exit codes and who calls it. Read the header before you run a script.
