#!/usr/bin/env bash
# Checks the text of a pull request (docs/WORKFLOW.md, PR flow; .github/pull_request_template.md):
# - a "### Decisions" block with at least one line ("none" when the brief made every choice);
# - a ready PR (not a draft) holds no PLAN.md (the plan goes before the PR leaves draft).
# Usage: check-pr-text.sh <pr number>. Needs gh with a token (GH_TOKEN) and GITHUB_REPOSITORY, or a gh login in the repo.
# Called by: .github/workflows/pr-text.yml (each edit and push of a PR) and check.yml (each PR of a merge queue group).
# Exit code 1 with one line per problem.
# Pattern: game-design-driven/cosmoteer-hot-cargo scripts/check-pr-text.sh at aa64aea, without its "### Game tests" block
# and its "Fixes #N needs a changed test" rule (this repo has no test sets).
set -euo pipefail
pr="${1:?usage: check-pr-text.sh <pr number>}"
repo="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
# The text without HTML comments (the template's hints) and without carriage returns.
body="$(gh api "repos/$repo/pulls/$pr" --jq '.body // ""' | tr -d '\r' | awk '/<!--/ { c = 1 } !c { print } /-->/ { c = 0 }')"
problems=()
if grep -qx '### Decisions' <<<"$body"; then
  decisions="$(awk '/^###[[:space:]]+Decisions[[:space:]]*$/ { on = 1; next } on && /^#/ { exit } on && NF' <<<"$body")"
  [[ -n "$decisions" ]] || problems+=("the '### Decisions' block is empty: write each decision with its reason, or 'none'")
else
  problems+=("no '### Decisions' block: list each choice that the brief did not make, one line with the reason, or 'none'")
fi
if [[ "$(gh api "repos/$repo/pulls/$pr" --jq .draft)" == false ]] && gh api "repos/$repo/pulls/$pr/files" --paginate --jq '.[] | select(.status != "removed") | .filename' | grep -qx PLAN.md; then
  problems+=("PLAN.md is still in the PR: delete it before the PR leaves draft")
fi
for p in "${problems[@]}"; do echo "check-pr-text: PR #$pr: $p"; done
(( ${#problems[@]} == 0 )) || exit 1
echo "check-pr-text: PR #$pr: OK"
