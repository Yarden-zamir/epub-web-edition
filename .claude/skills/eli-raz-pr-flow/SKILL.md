---
name: eli-raz-pr-flow
description: Take a change of the epub-web-edition repo (the pipeline, the site, or the Eli Raz book in books/eli-raz) from its branch to a merged PR. Draft PR with PLAN.md, PR checks, gh pr ready, the merge queue, conflicts, failures that look unrelated, PR text. Use when you start, update or merge a PR in this repo, and point every agent brief that ends in a PR to it.
---

# From branch to merged PR

The workflow and its reasons: docs/WORKFLOW.md. Book rules: books/eli-raz/AGENTS-BRIEF.md. This skill gives the order.
Pattern: game-design-driven/cosmoteer-hot-cargo, skill hot-cargo-pr-flow at aa64aea.

1. Branch from `origin/main` in your own worktree: `cd ~/Github/epub-web-edition/main && $DOTFILES/bin/wt-new <type>/<name> origin/main`, then work in `~/Github/epub-web-edition/<name>`. Types: `feat`, `fix`, `docs`, `ci`, `refactor`, `perf`.
2. In the first minutes: commit a short `PLAN.md` (design decisions, steps) at the repo root, push the branch (`git push -u origin HEAD`), and open a draft PR: `gh pr create --draft --fill-first`, then edit the text from the template (`.github/pull_request_template.md`) with the steps of PLAN.md as the checklist. A restarted agent reads the branch, PLAN.md and the PR checklist first, and continues from there.
3. Commit with conventional commits, by path (`git commit -m "..." -- <paths>`). Never credit an AI, a model or a tool. Push after each step that builds, and tick the step in the PR. Each push runs the PR check (`check`: ingest, build, check_release, EPUBCheck, quick smoke) on GitHub. Do not run the heavy checks on the build machine (books/eli-raz/AGENTS-BRIEF.md, Checks).
4. Before you push, run the light local check: `uv run books/eli-raz/scripts/check.py` (add `--preview <units>` for UI work).
5. PR text: start with 🤖, keep it short, add images of each visible change (`gh-pr-images` skill). The `### Decisions` block lists each choice that the brief did not make, one line with its reason, or `none`. The `pr-text` check fails without it, and an edit of the text reruns only that check.
6. When the work is done: delete PLAN.md in the last commit (the `pr-text` check fails a ready PR that still has it), push, then mark the PR ready: `gh pr ready <n>`. A draft PR does not merge.
7. Queue it: `scripts/queue-pr.sh <n>`. It turns on auto-merge, adds the queue entry itself when the checks passed and `gh pr merge --auto` queued nothing, prints the queue position, and fails loudly on any other state. While the PR check still runs, run it again after the check passes if no entry appears. Do not use `gh pr merge --merge` or `--admin`. The merge queue tests the PR on top of the newest `main` and the PRs ahead of it with every check (axe on the whole page at every width and scheme, the explainers, the sample edition, the PR text of the group), then merges it. Watch the PR (`watch_pull_request`). Do not poll it.
8. The PR does not have to be up to date with `main`. When `main` moves, read what the new commits intend (`git log`, `gh pr view`). Only if they conflict with the change or change what it does: `git fetch origin && git merge origin/main`, resolve, check, push. No rebase and no force-push on a PR branch.
9. If a check fails, read it: `gh pr checks <n>`, `gh run view <run id> --log-failed`. A failure in the merge queue removes the PR from the queue. Then follow the next section, fix, push, and run `scripts/queue-pr.sh <n>` again.
10. After the merge, `main` deploys both sites (`.github/workflows/kitshn.yml`). Check the deploy: `gh run list --workflow kitshn.yml --branch main --limit 1`.

## A failure that looks unrelated

1. Check the same check on `main` first: the nightly full run (`gh run list --workflow check.yml --branch main --event schedule --limit 3`), and queue runs of other PRs (`--event merge_group`).
2. If it passes on `main`, the failure belongs to the PR. Fix it.
3. If it is flaky (it passes on a rerun) or an infrastructure failure (a download, a runner), it counts as passing. On the PR's own run: `gh run rerun <run id> --failed`. In the merge queue: `scripts/queue-pr.sh <n>` again. Note it in the PR in one line.
4. If it also fails on `main`, `main` is broken. Do not merge over it. Tell the coordinator.

Do not babysit a fragile check. Decide in one look: a product bug or test variance, then move on.

## Merge queue traps

- A queue entry in state UNMERGEABLE conflicts with a PR ahead of it in the queue, not with `main`. Find it with `git merge-tree` against the head of each queued PR.
- While a PR has a queue entry, a push to its branch fails ("protected branch hook declined"). Remove the entry first: `gh api graphql -f query='mutation { dequeuePullRequest(input: {id: "<PR node id>"}) { clientMutationId } }'` (node id: `gh pr view <n> --json id`). Then push, and run `scripts/queue-pr.sh <n>` again.
