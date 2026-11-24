# Agents in this repo

- The workflow (worktrees, branches, PRs, the merge queue, checks, deploy): `docs/WORKFLOW.md`. Its steps: skill `eli-raz-pr-flow`. The coordinator: skill `eli-raz-coordinate`.
- The Eli Raz edition (rules, file owners, build commands, checks): `books/eli-raz/AGENTS-BRIEF.md`.
- Work only in your own worktree and branch. Every change goes through a PR and the merge queue; never push to `main`.
- Save progress so a restart loses nothing: in the first minutes commit a short `PLAN.md`, push, and open a draft PR with its steps as a checklist. Push after each step that builds and tick it. A restarted agent reads the branch, `PLAN.md` and the PR checklist first. Delete `PLAN.md` before `gh pr ready`.
- Decide with a reason: each choice that the brief did not make goes in the `### Decisions` block of the PR text, one line each, and again in the final report.
- The build machine is shared and has 4 cores: run only the light check there (`uv run books/eli-raz/scripts/check.py`); GitHub runs the heavy checks.
- Start only the last message with `FINAL REPORT`.
