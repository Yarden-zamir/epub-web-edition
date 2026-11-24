---
name: eli-raz-coordinate
description: Coordinator work on the epub-web-edition repo and the Eli Raz edition. Brief and watch the agents, judge failures and merges, keep main and the merge queue moving. Use when you coordinate several agents in this repo.
---

# Coordinate

The whole workflow: docs/WORKFLOW.md. Each rule below has its reason after "Reason:".
Pattern: game-design-driven/cosmoteer-hot-cargo, skill hot-cargo-coordinate at aa64aea (only the parts without the
player's PC and game).

## Watch the agents

- Run `scripts/agent-watch.sh` from any worktree, by hand or from a scheduled check. It prints one line for each agent worktree: branch, minutes since the last commit, unpushed commits, dirty files, the PR and its queue position, and the newest check result.
- Signs that an agent needs a message: no commit for a long time; commits that are not pushed (ahead); a ready PR that is not queued; a red check for a long time.
- To reach a running agent thread, send with `t3_thread_send` mode `steer`. Put "do this after your current step" in the text for follow-up work. Reason: a queued message waits for the end of a long turn.

## Brief the agents

- One agent for each area, with a queue of its features. Never start two agents on features that touch the same files. Reason: parallel edits of one file end in merge conflicts in the queue.
- Point every brief that ends in a PR to the skill `eli-raz-pr-flow`.
- When the user's words have two readings, write "I read this as: ..." in the brief.

## Merges and failures

- Agents merge their own PRs through the merge queue (`eli-raz-pr-flow`). No agent pushes to `main`.
- When you add a PR to the queue, call `watch_pull_request` on it.
- A flaky or infrastructure failure in a check that the PR does not touch counts as passing, after a check of the same check on `main` (`eli-raz-pr-flow`). Reason: slow, flaky gates block merges; calling a real regression unrelated breaks main.
- Admin merge: only when the only failure is a known flake and every other check passed: `gh pr merge <n> --admin --merge`. Only the coordinator does this; never tell an agent to. Reason: agents act through the owner's account, and each admin merge needs a judgment call.
- Check that the nightly full run runs and passes on `main`: `gh run list --workflow check.yml --branch main --event schedule --limit 3`.
- After a batch of merges, remove merged worktrees: `scripts/prune-worktrees.sh` (`--dry-run` lists them). It keeps detached, dirty, busy and fresh worktrees, and worktrees with ignored files other than build output.
