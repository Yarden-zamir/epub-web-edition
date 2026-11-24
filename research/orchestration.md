# Orchestration: parallel site agents and a merge queue

Date: 2026-11-24. Research agent for the orchestrator (Claude Code session 41ff45a6-ddb4-4aa9-bf41-66329c7bcc61).
Status: proposal. Nothing in this file is applied yet. The orchestrator applies the steps after the user approves.

## 1. Sources

- T3 thread "Cosmotier Hot Cargo" on the Mac (environment fd5b6bfd-…, thread 555b8fde-…). Read only.
- Repo [game-design-driven/cosmoteer-hot-cargo](https://github.com/game-design-driven/cosmoteer-hot-cargo) at commit `cefc746`, read with `gh api`:
  - `docs/WORKFLOW.md`: the whole workflow, split into generic and project parts.
  - `CLAUDE.md` (Git, Agents), `CONTRIBUTING.md` (Git).
  - `.claude/skills/hot-cargo-coordinate/SKILL.md` (coordinator rules) and `.claude/skills/hot-cargo-pr-flow/SKILL.md` (agent PR steps).
  - `.github/workflows/check.yml`, `dev-release.yml`, `full-suite-trigger.yml`, `.github/pull_request_template.md`.
  - `scripts/queue-pr.sh`, `scripts/agent-watch.sh`.
  - Live settings: the ruleset "main merge queue" (id 27255240), the branch protection of `main`, the repo merge settings.
- GitHub docs source, `data/reusables/gated-features/merge-queue.md` in [github/docs](https://github.com/github/docs).
- Our side: `AGENTS-BRIEF.md`, both repos and their live GitHub settings, the orchestrator thread "Eli Raz: professional book and web edition" and the queue of the thread "Eli Raz site: UI and UX".

## 2. How Hot Cargo orchestrates

### 2.1 Split of work

- One coordinator thread. It briefs agents, watches them, judges failures and does the work on the player's PC.
- One agent per **area**, with a queue of features for that area. Two agents never work on features that touch the same files.
- An area is a folder (`src/HotCargo/<Area>/`, `mod/<area>/`) with its own entry point, tunables, rules and strings. The shared core changes only through hooks (`Run.Hooks`, `DebugKeys.Extra`, `Autotest.Commands`).
- Folders are found by name, not by a shared list. For example, `scripts/assemble-mod.sh` builds `mod.rules` from every `mod/<area>/actions.rules`, and the area of a test comes from its file name. So two areas never edit one list file.
- The coordinator gives parallel agents separate spec number blocks. CI fails on a duplicate number, which catches a clash between two queued PRs.

### 2.2 Checkout per agent

- Bare repo container: `.bare/`, `_shared/`, one folder per branch.
- Each agent: `git --git-dir ../.bare worktree add ../<name> -b <type>/<name> origin/main`. It works only in that worktree.
- Local state that is not code (logs, locks, the player hold) sits next to `.bare/`, outside git.
- A `play` worktree is a detached checkout of `origin/main`, used only for installs.

### 2.3 How changes land

- Every change is a PR. Nobody pushes to `main`. A release only pushes a tag.
- Each agent opens a draft PR in its first minutes, with a `PLAN.md` on the branch and a step checklist in the PR text. It pushes after each step that builds. A restarted agent continues from the branch, `PLAN.md` and the checklist. It deletes `PLAN.md` before the last commit.
- The agent that owns the PR merges it: `gh pr ready`, then `scripts/queue-pr.sh <n>`. That script turns on auto-merge and adds the queue entry with the GraphQL `enqueuePullRequest` mutation when `gh pr merge --auto` queues nothing (this happens).
- GitHub merge queue on `main`, live settings:

| Setting | Value |
|---|---|
| Ruleset | "main merge queue", target `~DEFAULT_BRANCH`, enforcement active |
| Merge method | `MERGE` (one merge commit per PR, subject = PR title + `(#N)`) |
| Grouping | `ALLGREEN`, build up to 5, merge 1 to 5, no wait |
| Check timeout | 90 minutes |
| Bypass | repository role admin, mode `pull_request` (the coordinator's `--admin` merge of a known flake) |
| Branch protection | required checks `build`, `game-tests`, `spec-numbers`; `strict: false` (a PR does not have to be up to date) |
| Repo merge settings | merge commits only (squash and rebase off, because squash broke stacked branches), auto-merge on, delete branch on merge, update branch on |

- Conflicts: the queue tests each PR on top of `main` plus the PRs ahead of it. A queue entry in state UNMERGEABLE conflicts with a PR ahead of it. The agent merges `origin/main` into its branch (no rebase, no force push), adapts and pushes. A push fails while the PR has a queue entry, so the agent dequeues first.
- When `main` moves, an agent reads what the new commits intend. It merges `origin/main` only when they conflict with or change its work.

### 2.4 Review and test gates

- No human review gate and no required approvals. The gates are the required checks plus the owner's own tests before the push.
- `check.yml` runs on `pull_request`, `merge_group`, `workflow_dispatch` and a schedule. It has no `push` trigger: `main` moves only through the queue.
- PR runs: cheap checks only (build, unit tests, spec numbers). The merge queue runs the expensive game tests for the set of PRs in the group. The PR text can change that set (`### Game tests` block).
- Full suite on `main`: after each merge at most every 3 hours (`full-suite-trigger.yml`), plus a schedule as a second path. A release needs it green.
- One stable check name (`game-tests`) sums up a matrix of shards, so branch protection never changes.
- Private game files reach CI from a private repo through a read-only deploy key. They never go into a cache, an artifact or a log. No `pull_request_target`; fork PRs get no secret.
- Flake rule: before an agent calls a failure unrelated, it checks the same test on `main`. Only the coordinator does admin merges.
- Visible changes: the agent takes its own screenshots and puts them in the PR.

### 2.5 State tracking

- The draft PR checklist and the branch are the state of each agent.
- `scripts/agent-watch.sh`: one line per agent worktree (minutes since the last commit, ahead or pushed, dirty files, running tests, held test slots). It reads only, never full command lines.
- The coordinator calls `watch_pull_request` on each queued PR and re-queues a PR that left the queue on a known flake.
- To reach a busy agent: `t3_thread_send` mode `steer`, with "after your current step" in the text. Queued messages wait for the end of a long turn and are often dropped.

### 2.6 Deploys after merges

- Each push to `main` (each merge) publishes an untested dev prerelease (`dev-release.yml`, newer push cancels older).
- A tested release takes the newest `main` commit with every required check and a green full suite (`scripts/release.sh`). So releases need no merge freeze.
- The coordinator installs the newest `main` into the player's game after merges.

## 3. Our setup today

- Pipeline repo [Yarden-zamir/epub-web-edition](https://github.com/Yarden-zamir/epub-web-edition): public, owned by a user account. No branch protection. Merge settings: all three methods on, auto-merge off. CI: `kitshn.yml` only (sample site deploy on push to `main`, an ephemeral `pr-{pr}` preview per PR).
- Content repo [Yarden-zamir/eli-raz-edition](https://github.com/Yarden-zamir/eli-raz-edition): private, owned by a user account on GitHub Free. Branch protection and rulesets return HTTP 403 "Upgrade to GitHub Pro or make this repository public". No workflows yet. The thread "Eli Raz: move the live build to GitHub Actions" adds the live build and deploy there now.
- All agents commit and push to `main` from one shared checkout per repo (`main/`), with `git commit -- <paths>`. The pipeline `main/` checkout now holds uncommitted edits of the UI agent (`site/index.html`, `site/reader.css`, `site/reader.js`, `tools/build_web.py`) and of the EPUB agent (`tools/ingest_pdf.py`).
- One UI agent owns every site file: `tools/build_web.py` (1,051 lines), `site/reader.js` (1,338), `site/reader.css` (565), `site/index.html` (136), `tools/verify.py`, `kitshn.config.ts`. Its queue holds 9 pending messages (T3 runs 3 to 11 are "queued").
- Every local build writes to the same `~/Github/eli-raz-edition/main/dist/release/`. Two parallel UI agents would overwrite each other's build.
- `tools/verify.py` and `scripts/smoke_site.py` have fixed paths for Chromium (`~/.cache/ms-playwright/chromium-1255/…`) and for `.tools/` (1.2 GB, in `main/` only).
- `_shared/` is empty in both containers. The global `post-checkout` hook is in the dotfiles repo (`.config/git/hooks/post-checkout`), but `~/.config/git/hooks/` does not exist on this machine. So `wt-new` links nothing from `_shared/` here.

## 4. The blocker: merge queue availability

🔴 GitHub docs: "Pull request merge queues are available in any public repository owned by an organization, or in private repositories owned by organizations using GitHub Enterprise Cloud." Both our repos are owned by a user account. So neither repo can have a merge queue as it is.

| Repo | Merge queue | Branch protection and required checks |
|---|---|---|
| Pipeline (public, user) | no | yes |
| Pipeline after a transfer to the organization `game-design-driven` (public, Free plan, Yarden is admin) | **yes** (Hot Cargo uses it there) | yes |
| Content (private, user, Free) | no | no (needs GitHub Pro) |
| Content in any organization without Enterprise Cloud | no | needs GitHub Team |

Where the conflicts come from: the parallel UI work edits the pipeline repo. The content repo has one owner per data file (AGENTS-BRIEF.md table), so parallel content agents rarely touch one file.

🟢 Recommendation: a merge queue for the pipeline repo only, after a transfer to `game-design-driven`. The content repo keeps commit-by-path to `main`, and its Actions deploy is the gate (it publishes only a build that passes every check, and the live site keeps the last good build).

⚪ Alternative without a transfer: keep the pipeline repo under the user account. Use branch protection with one required check and `strict: true`, plus auto-merge. Each PR must then be up to date with `main`: the owner runs `gh pr update-branch <n>`, CI runs again, and auto-merge merges it. This serializes merges like a queue of one, with one extra CI run each time `main` moves. It is fine for 4 or 5 agents with a CI run of a few minutes.

⚪ Content repo with required checks: GitHub Pro on the user account gives branch protection on private repos, still with no merge queue. I do not recommend it now.

🔴 Transfer risks (not checked):
- The kitshn deploy (`Yarden-zamir/kitshn/.github/workflows/kitshn2-deploy.yml@main`, OIDC `id-token: write`, `secrets: inherit`) may bind the app to the repo name `Yarden-zamir/epub-web-edition`. Check with the `kitshn` skill before the transfer, and move or re-link the app.
- The live build in the content repo checks out the pipeline repo by name. GitHub redirects the old name, but update every reference: AGENTS-BRIEF.md, the new content repo workflow, `README.md`, the `origin` URLs.
- The transfer is outward-facing and changes the repo owner. It needs the user's yes.

## 5. Proposal

### 5.1 Split the UI work into lanes

Copy the Hot Cargo rule: one agent per area, a queue per agent, no two agents on the same files. Today the site code has one file per layer (one JS, one CSS, one build file), so every feature touches the same four files. Two steps fix that.

**Step A, one refactor PR by the current UI agent, before the lanes start.** Split the four files by feature, with no change in behaviour:

```
site/index.html            core only, with generic slots ({{head}}, {{panels}}, {{end}})
site/js/00-core.js         byId, history, overlays, goTo, highlight, dialogs (reader.js lines 1-245 now)
site/js/<nn>-<feature>.js  one file per feature: navigator, search, figures, places, charts, popovers, resume
site/css/00-base.css       tokens, base, buttons, nav, hero, book, footer, panels
site/css/<nn>-<feature>.css
tools/build_web.py         core: read_book, Converter, fill, build
tools/web/<feature>.py     one module per feature: places, timeline, glossary, crosslinks, charts, tables, hero, related
```

- The build concatenates `site/js/*.js` into one `reader.js`, and `site/css/*.css` into one `reader.css`, in file name order. The site still loads one script and one stylesheet.
- `build_web.py` finds `tools/web/*.py` by name, in sorted order. Each module returns its fragments for the template slots. No shared list of features exists, so a new feature adds files and edits no shared line. This copies `assemble-mod.sh` in Hot Cargo.
- Proof of no change: build the release before and after. `index.html`, `reader.js`, `reader.css` and `search.json` must be byte-identical. A unit check in `verify.py` keeps the concatenation order stable.
- The UI agent owns the design of the module contract. The rule is fixed: a feature lives in its own files, and core changes only when a feature cannot work through the slots.

🟠 Simpler alternative: skip Step A. Git merges edits to different parts of one file without a conflict, so lanes can work in the four big files. Conflicts then come at the shared end of a file, the `fill()` values in `build()`, and `index.html`. The merge queue finds each conflict, and the owner merges `origin/main` and fixes it. This works for 2 lanes. For 4 or more lanes, Step A costs one PR and removes most conflicts, so I recommend it.

**Step B, the lanes.** Each lane is one agent with a queue. It owns the files named in its row. The orchestrator sends each new UI task to the lane that owns its files. It sends a task that crosses lanes to the UI core lane.

| Lane | Owns (pipeline repo) | Queue now (from the orchestrator and UI threads, 2026-11-24) |
|---|---|---|
| 1. UI core (the current UI agent) | `site/index.html`, `site/js/00-core.js`, `site/css/00-base.css`, `tools/build_web.py`, `tools/verify.py`, `kitshn.config.ts`, `.github/` | Step A refactor; the "back to where you were" chip (history core); motion tokens (durations, easings, reduced motion) and the motion of core parts (hero, chapter headings, buttons); nav and download menu polish; the footnote, glossary and correction popovers |
| 2. Places and maps | `site/js/*-places.js`, `site/css/*-places.css`, `tools/web/places.py`, new then-now files | Places popup as a compact card or phone sheet; selected marker in place; name labels instead of numbers; section heading size; the then-and-now view of `site/then-now.json` (maps agent data); map motion |
| 3. Figures and data | figure viewer, charts, tables, errata page files | Figure viewer upgrade (zoom, previous and next, swipe down to close); errata page with "printed line" and "page N" pills and the side-by-side viewer; the sortable route table of PDF page 297; chart and table motion |
| 4. Offline and sharing | new `site/sw.js`, manifest, link preview files, head fragments | Open Graph link preview with a 1200x630 hero crop; web app manifest; service worker (HTML network first, versioned precache, the whole book cached in the background when installed as an app) |
| 5. Navigation and reading | navigator, search, chapter rail, translations files | Chapter rail with scrubbing; navigator and search panel polish; the per-chapter language toggle for `site/translations/` with the "machine translation, not reviewed" label |

- The "subtle animations" task splits: lane 1 adds the shared motion tokens first, and each lane then animates its own parts.
- The design QA list (thread "Eli Raz: design QA review of the site") goes to the lanes item by item, by the file that each fix touches.
- Start lanes 2 to 5 after Step A merges. Lanes 1 and 4 can start at the same time as Step A only if lane 4 adds new files only.
- Keep at most 5 lanes. The free plan runs about 20 Actions jobs at once, and each lane also builds the real book locally.
- Content and EPUB agents stay as they are (content data, maps data, EPUB and Kindle quality). The EPUB agent owns `tools/ingest_pdf.py`, `tools/build_epub.py` and `tools/check_*.py` in the pipeline repo, so it also follows the PR flow there.

### 5.2 GitHub settings (pipeline repo)

Apply in this order. The orchestrator runs these commands after the user approves. Use `R=game-design-driven/epub-web-edition` after a transfer, or `R=Yarden-zamir/epub-web-edition` for the alternative without a transfer.

1. Transfer (only with the user's yes, after the kitshn check in section 4):
   ```sh
   gh api -X POST repos/Yarden-zamir/epub-web-edition/transfer -f new_owner=game-design-driven
   git -C ~/Github/epub-web-edition/.bare remote set-url origin https://github.com/game-design-driven/epub-web-edition.git
   ```
2. Merge settings, as in Hot Cargo:
   ```sh
   gh api -X PATCH repos/$R -F allow_merge_commit=true -F allow_squash_merge=false -F allow_rebase_merge=false \
     -F allow_auto_merge=true -F delete_branch_on_merge=true -F allow_update_branch=true \
     -f merge_commit_title=PR_TITLE -f merge_commit_message=PR_BODY
   ```
3. Land `.github/workflows/ci.yml` (section 5.3) on `main` first, so that the check name `check` exists before protection requires it. This is the last direct push to `main`.
4. Branch protection with the required check:
   ```sh
   gh api -X PUT repos/$R/branches/main/protection --input - <<'EOF'
   {"required_status_checks": {"strict": false, "checks": [{"context": "check", "app_id": 15368}]},
    "enforce_admins": false, "required_pull_request_reviews": null, "restrictions": null,
    "allow_force_pushes": false, "allow_deletions": false}
   EOF
   ```
   `app_id` 15368 is GitHub Actions (the same value as in Hot Cargo). For the alternative without a transfer, set `"strict": true`.
5. The merge queue ruleset (organization repo only):
   ```sh
   gh api -X POST repos/$R/rulesets --input - <<'EOF'
   {"name": "main merge queue", "target": "branch", "enforcement": "active",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}],
    "rules": [{"type": "merge_queue", "parameters": {"merge_method": "MERGE", "grouping_strategy": "ALLGREEN",
      "max_entries_to_build": 5, "min_entries_to_merge": 1, "max_entries_to_merge": 5,
      "min_entries_to_merge_wait_minutes": 0, "check_response_timeout_minutes": 30}}]}
   EOF
   ```
   The timeout is 30 minutes, not 90: our check takes minutes, not a game suite.
6. Check: `gh api repos/$R/rulesets` and `gh api repos/$R/branches/main/protection` show the values above.

### 5.3 CI for the pipeline repo

New file `.github/workflows/ci.yml` (owner: lane 1). It checks the public sample book only, because a public repo's Actions logs are public. Real book checks stay in the private content repo (section 5.6).

```yaml
# Checks pull requests and the merge queue of main on the synthetic sample book: EPUB build, web build, verify.py
# (EPUBCheck, axe, layout, IDs). No push trigger: main moves only through the merge queue.
# Real book checks run in the private content repo, never here: logs of a public repo are public.
name: ci
on:
  pull_request:
  merge_group:
    types: [checks_requested]
  workflow_dispatch:
concurrency:
  group: ci-${{ github.event_name }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v7.0.1
      - uses: astral-sh/setup-uv@v10.3.3
      # verify.py reads .tools/ (EPUBCheck, a Java runtime, axe-core). The runner image has Temurin 21.
      - name: Tools
        run: |
          mkdir -p .tools
          ln -s "$JAVA_HOME_21_X64" .tools/jdk-21-runner
          curl -fsSL -o /tmp/epubcheck.zip https://github.com/w3c/epubcheck/releases/download/v5.4.0/epubcheck-5.4.0.zip
          unzip -q /tmp/epubcheck.zip -d .tools
          npm pack --silent axe-core@4.14.0 --pack-destination /tmp
          mkdir .tools/axe && tar -xzf /tmp/axe-core-4.14.0.tgz -C .tools/axe
          uv run --with playwright==1.64.1 playwright install --with-deps chromium
      - run: uv run tools/build_epub.py
      - run: uv run tools/build_web.py
      - run: uv run tools/verify.py
```

- Required code change before this works (lane 1, in Step A or before it): `tools/verify.py` and `scripts/smoke_site.py` fix the Chromium path to `chromium-1255`. Read the path from a `CHROMIUM` environment variable and crash when it is not set and the fixed path does not exist. In CI, set `CHROMIUM` from `uv run --with playwright==1.64.1 python -c "from playwright.sync_api import sync_playwright as s; p=s().start(); print(p.chromium.executable_path)"`.
- Versions: `actions/checkout@v7.0.1` (2026-07-20, the same as Hot Cargo). `astral-sh/setup-uv@v10.3.3` (2026-10-28). The newest, v10.4.0 of 2026-11-20, is less than two weeks old. EPUBCheck 5.4.0 and axe-core 4.14.0 match `.tools/`.
- `kitshn.yml` stays. Its `pr-{pr}` preview gives each PR a live sample site for screenshots. Limit: the preview shows the sample book, not the real book.
- 🟠 No full-suite or schedule workflow now. Hot Cargo needs it because the queue runs only part of a long game suite. Our check runs everything in minutes. Revisit when the check takes more than about 15 minutes.

### 5.4 Worktree per agent

One-time setup (orchestrator):

```sh
# 1. Install the global hooks from the dotfiles, so wt-new links _shared/ into each worktree.
#    ~/.config/git/hooks does not exist on this machine. Follow the dotfiles installer; do not link files by hand.
# 2. Move the local tools and caches out of main/ into _shared/, so every worktree gets them through the hook.
mv ~/Github/epub-web-edition/main/.tools ~/Github/epub-web-edition/_shared/.tools
# 3. The shared main/ checkouts become read-only for agents. Only the orchestrator pulls there.
```

Per lane agent (in its brief):

```sh
cd ~/Github/epub-web-edition/main && git fetch -q origin
$DOTFILES/bin/wt-new feat/places-card origin/main        # creates ~/Github/epub-web-edition/places-card
W=~/Github/epub-web-edition/places-card
# A clean, detached copy of the pushed content, so other agents' unpushed edits never enter the build.
git -C ~/Github/eli-raz-edition/main fetch -q origin
git -C ~/Github/eli-raz-edition/main worktree add --detach ../content-places origin/main
C=~/Github/eli-raz-edition/content-places
# Build into the lane's own worktree, never into the shared content dist/.
cd $W
uv run tools/build_epub.py $C/epub-src-release $W/dist/release/eli-raz.epub
uv run tools/build_web.py $W/dist/release/eli-raz.epub $W/dist/release/web $C/site/enhancements.json
uv run tools/check_release.py $C $W/dist/release/eli-raz.epub $W/dist/release/web
uv run $C/scripts/smoke_site.py $W/dist/release/web
# To see newer pushed content: git -C $C checkout -q --detach origin/main after a fetch.
```

- `wt-new` names the folder after the last part of the branch. So the branch `feat/places-card` lives in the folder `places-card`.
- `dist/` is in `.gitignore`, so each worktree has its own build output.
- After the merge, remove the worktrees: `git -C $W status --ignored --short` first, move anything that is not build output to `_shared/`, then `git -C ~/Github/epub-web-edition/main worktree remove $W` and the same for `$C`.

### 5.5 PR flow for agents

New file `scripts/queue-pr.sh` in the pipeline repo: copy it unchanged from Hot Cargo (`scripts/queue-pr.sh` at commit `cefc746`). Without a merge queue (the alternative), use `gh pr update-branch <n> && gh pr merge <n> --auto --merge` instead.

New file `.github/pull_request_template.md`:

```markdown
🤖 <one or two lines: what changes for the reader>

- [ ] Real book build and checks passed locally: check_release.py, smoke_site.py (393 and 1280 px, light and dark)
- [ ] Screenshots of visible changes (phone and desktop, light and dark)
```

Steps for each lane agent (put them in every brief that ends in a PR):

1. Make the worktrees (section 5.4).
2. In the first minutes, commit `PLAN.md` (decisions, steps), push, and open a draft PR: `gh pr create --draft --title "feat(places): compact place card" --body-file <file>`. The body holds a checklist of the steps.
3. Commit and push after each step that builds. Tick the step in the PR body. Conventional commits. No AI, model or tool credit.
4. Before the last push: run the real book build and checks (section 5.4). Add screenshots with the `gh-pr-images` skill. Delete `PLAN.md`.
5. The PR title is a conventional commit: it becomes the merge commit subject. The body starts with 🤖, is short, and links its task.
6. `gh pr ready <n>`, then `scripts/queue-pr.sh <n>`. Never `gh pr merge --merge` (the queue sets the method) and never `--admin`.
7. When `main` moves, read the new commits (`git log --first-parent`). Only when they conflict or change your feature: `git merge origin/main`, adapt, push. Never rebase or force-push a branch with an open PR.
8. A queue failure removes the PR from the queue. Read it (`gh pr checks <n>`, `gh run view <id> --log-failed`). Check the same step on `main` before you call it unrelated. Fix, push, run step 6 again. A push to a queued PR fails: dequeue first with `gh api graphql -f query='mutation { dequeuePullRequest(input: {id: "<node id>"}) { clientMutationId } }'` (node id: `gh pr view <n> --json id`).
9. End with one message that starts with `FINAL REPORT`, with the PR link, the merge commit and the checks.

### 5.6 Deploy after merges

- Pipeline `main` changes only through the queue. Each merge triggers the live build in the content repo (the thread "Eli Raz: move the live build to GitHub Actions" sets up that trigger).
- The live build runs every real book check (check_release.py, smoke_site.py) and publishes only when all pass. When a check fails, the live site keeps the last good build, and the orchestrator gets a red run. This is our version of the Hot Cargo full suite on `main`: the gate after the merge.
- The orchestrator watches the live build runs: `gh run list -R Yarden-zamir/eli-raz-edition --limit 5`. A red run after a pipeline merge goes back to the lane that owns the merged PR as its next task.
- ⚪ Later, if real book breaks after merges are frequent: add a second required check `release-check` to the queue. A queue job starts a `workflow_dispatch` run in the private content repo with the group's commit, waits, and prints only the result. That needs a fine-grained token with `actions: write` on the content repo, stored as a secret in the pipeline repo. Book text stays in private logs. Not proposed now: it adds a token and a cross-repo wait for a risk that has not happened.

### 5.7 Orchestrator state

- Lane state: the draft PR of each lane, its checklist and its branch. `gh pr list -R $R --json number,title,headRefName,isDraft,mergeStateStatus,autoMergeRequest`.
- New file `scripts/agent-watch.sh` in the pipeline repo (owner: lane 1): one line per worktree, as in Hot Cargo, without the PC parts:
  ```sh
  #!/usr/bin/env bash
  # One line per agent worktree: minutes since the last commit, ahead of its upstream, uncommitted files.
  # Reads only. Run from any worktree of the container. Called by the orchestrator.
  set -uo pipefail
  cd "$(dirname "$0")/../.."
  now=$(date +%s)
  for w in $(git --git-dir .bare worktree list --porcelain | awk '/^worktree /{print $2}' | xargs -n1 basename); do
    [[ "$w" == .bare || ! -d "$w" ]] && continue
    last=$(git -C "$w" log -1 --format=%ct)
    ahead=$(git -C "$w" status -sb | head -1 | grep -o 'ahead [0-9]*' || true)
    dirty=$(git -C "$w" status --porcelain | wc -l | tr -d ' ')
    printf "  %-20s commit %4dm ago  %-9s dirty %s\n" "$w" $(( (now - last) / 60 )) "${ahead:-pushed}" "$dirty"
  done
  ```
- Call `watch_pull_request` on each queued PR. Re-queue a PR that left the queue on a known flake.
- Send follow-up tasks to a busy lane with `t3_thread_send` mode `steer` and "after your current step". The UI agent now has 9 queued messages that have not started: the Hot Cargo coordinator saw such queued messages dropped.

### 5.8 Changes to AGENTS-BRIEF.md

The orchestrator owns that file. Proposed patch:

1. Replace the bullet "Commit and push while you work …" with two bullets:
   - "Pipeline repo: every change goes through a PR and the merge queue of `main` (research/orchestration.md, section 5.5). Work only in your own worktree and branch. Never push to `main`."
   - "Content repo: commit and push your own paths to `main` with `git commit -- <paths>`, as before. It has no branch protection on the Free plan. The live build publishes only a build that passes every check."
2. Replace the line "Pipeline repo ownership: UI agent owns …" with the lane table of section 5.1.
3. In "Build commands", build into your own worktree (section 5.4), not into `$C/dist/release`.
4. Update the pipeline repo name after a transfer.

## 6. Order of work

1. The user approves: the transfer to `game-design-driven` (or the alternative), and PRs opened by agents.
2. The UI agent and the EPUB agent finish and push their current uncommitted batches in the shared `main/`.
3. Orchestrator: install the dotfiles hooks, move `.tools` to `_shared/`, run the kitshn check, transfer.
4. Lane 1 lands `ci.yml` and the `CHROMIUM` change directly on `main` (the last direct push). The orchestrator applies the settings of section 5.2, steps 2, 4, 5 and 6.
5. Lane 1 opens the Step A refactor PR through the queue. This is the first queued PR and tests the whole flow.
6. The orchestrator starts lanes 2 to 5 with the brief steps of section 5.5, and patches AGENTS-BRIEF.md (section 5.8).

## 7. Open decisions for the user

1. Transfer the pipeline repo to the organization `game-design-driven` for a real merge queue, or keep it under the user account with strict required checks.
2. Agents open their own PRs and merge them through the queue. The user's global rule says to open PRs only when asked, so this needs a standing approval for both repos' agents.
3. The content repo stays push-to-main for its data owners. A queue there needs GitHub Enterprise Cloud.
