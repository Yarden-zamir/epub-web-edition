#!/usr/bin/env bash
# Removes the worktrees whose branch is merged into origin/main, and deletes their local branch. A worktree stays when it is
# the main worktree, detached, has changes or untracked files, holds ignored files other than build output (for example
# downloads in books/eli-raz/work/), is the working folder of a running process, or has no commit of its own yet (its tip
# is on main's first-parent line: a fresh agent worktree).
# Usage: scripts/prune-worktrees.sh [--dry-run]   (from any worktree). Prints each worktree it removes or would remove.
# Called by: the coordinator (skill eli-raz-coordinate), by hand or after a batch of merges.
# Pattern: game-design-driven/cosmoteer-hot-cargo scripts/prune-worktrees.sh at aa64aea, with the ignored-files guard.
set -euo pipefail
cd "$(dirname "$0")/../.."
dry="${1:-}"
git --git-dir .bare fetch -q origin main
# main's own commits (the merge commits of the queue). A merged branch's tip sits behind them, a fresh branch's tip on them.
first_parent="$(git --git-dir .bare rev-list --first-parent origin/main)"
# Working folders of running processes. Only folders are read, never command lines.
busy="$(for p in /proc/[0-9]*; do readlink "$p/cwd" || true; done 2>/dev/null | sort -u)"  # Other users' processes deny it.
# Ignored files that a build makes again; any other ignored file keeps its worktree.
build_output='^!! (\.tools|dist/|books/eli-raz/(dist|epub-src|epub-src-release)/|.*__pycache__/)'
removed=0
while IFS= read -r line; do
  case "$line" in
    "worktree "*) path="${line#worktree }" branch="" ;;
    "branch refs/heads/"*) branch="${line#branch refs/heads/}" ;;
    "") # The end of one worktree's lines.
      [[ -n "${path:-}" && -n "$branch" && "$branch" != main ]] || { path=""; continue; }
      tip="$(git --git-dir .bare rev-parse "refs/heads/$branch")"
      if git --git-dir .bare merge-base --is-ancestor "$tip" origin/main && ! grep -qx "$tip" <<<"$first_parent" \
        && [[ -z "$(git -C "$path" status --porcelain 2>/dev/null)" ]] \
        && [[ -z "$(git -C "$path" status --porcelain --ignored 2>/dev/null | grep '^!!' | grep -vE "$build_output")" ]] \
        && ! grep -qxF "$path" <<<"$busy" && ! grep -qF "$path/" <<<"$busy"; then
        echo "remove $(basename "$path") ($branch)"
        if [[ "$dry" != --dry-run ]]; then git --git-dir .bare worktree remove --force "$path" && git --git-dir .bare branch -q -d "$branch"; fi
        removed=$((removed + 1))
      fi
      path="" ;;
  esac
done < <(git --git-dir .bare worktree list --porcelain; echo)
echo "prune-worktrees: $removed worktrees $([[ "$dry" == --dry-run ]] && echo "would go" || echo removed)"
