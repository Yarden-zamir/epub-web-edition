#!/usr/bin/env bash
# Coordinator's agent watch: one compact line per agent worktree.
# Columns: worktree, branch, minutes since the last commit, ahead (commits not pushed), uncommitted files, the PR of the
# branch (number and state: draft, ready, or queued with its position), and its newest check result.
# Usage: scripts/agent-watch.sh   (from any worktree; it reads the container folder that holds .bare)
# Exit code 0. It only reads state.
# Called by: the coordinator, by hand or from a scheduled check (skill eli-raz-coordinate).
# Pattern: game-design-driven/cosmoteer-hot-cargo scripts/agent-watch.sh at aa64aea, without its PC slot columns.
set -uo pipefail
cd "$(dirname "$0")/../.."
now=$(date +%s)
R="$(git --git-dir .bare remote get-url origin | sed -E 's#(\.git)?$##; s#^.*github\.com[:/]##')"
# One query for every open PR: branch, draft, queue entry, newest check result.
prs="$(gh api graphql -f query="{ repository(owner: \"${R%/*}\", name: \"${R#*/}\") { pullRequests(states: OPEN, first: 100) { nodes {
  number headRefName isDraft mergeQueueEntry { position state }
  commits(last: 1) { nodes { commit { statusCheckRollup { state } } } } } } } }" \
  --jq '.data.repository.pullRequests.nodes[] | [.headRefName, .number,
    (if .mergeQueueEntry then "queued:\(.mergeQueueEntry.position)" elif .isDraft then "draft" else "ready" end),
    (.commits.nodes[0].commit.statusCheckRollup.state // "none" | ascii_downcase)] | @tsv' 2>/dev/null)"
echo "== $(date +%H:%M)  open PRs: $(grep -c . <<<"$prs")  queued: $(grep -c queued <<<"$prs")"
for w in $(git --git-dir .bare worktree list --porcelain | awk '/^worktree /{print $2}' | xargs -n1 basename); do
  [[ "$w" == .bare ]] && continue
  [[ -d "$w" ]] || continue
  branch=$(git -C "$w" branch --show-current 2>/dev/null); branch=${branch:-detached}
  last=$(git -C "$w" log -1 --format=%ct 2>/dev/null || echo "$now")
  ahead=$(git -C "$w" status -sb 2>/dev/null | head -1 | grep -o 'ahead [0-9]*' | tr -d 'ahead ' || true)
  dirty=$(git -C "$w" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  pr=$(awk -F'\t' -v b="$branch" '$1 == b { print "#" $2 " " $3 " check " $4 }' <<<"$prs")
  printf "  %-18s %-34s commit %4dm ago  ahead %-3s dirty %-3s %s\n" "$w" "$branch" $(( (now - last) / 60 )) "${ahead:-0}" "$dirty" "${pr:-no PR}"
done
