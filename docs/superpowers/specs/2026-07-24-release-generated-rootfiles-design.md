# Release-Generated Rootfiles — Design

**Date:** 2026-07-24
**Status:** Approved
**Repo:** `MakinaHQ/config`

## Problem

`caliber.yaml` (per machine/network) is the real source of truth for a caliber's full
desired state. A rootfile is just `transpile(caliber.yaml)` frozen at a point in time.
Today rootfiles are **hand-generated on a branch and committed in the PR**, and CI
(`transpiler.yaml`) enforces that the newest added rootfile equals
`transpile(caliber.yaml @ that branch)`.

Because rootfiles are authored per-branch, concurrent work diverges:

- User A branches from caliber `{1,2,3}`, adds position 4, generates rootfile
  `A = transpile({1,2,3,4})`, merges.
- User B branched at the same time from `{1,2,3}`, adds position 5, generates
  `B = transpile({1,2,3,5})`, merges after A.
- Main's `caliber.yaml` now text-merges to `{1,2,3,4,5}`, **but the newest rootfile is
  `B = {1,2,3,5}`** — position 4 is silently dropped from the artifact spellcaster
  actually applies. Each branch's PR-time CI passed in isolation and never re-runs
  against merged `main`.

This is "the second merged PR overwrites the first merged rootfile."

## Goal

Rootfiles stop being hand-authored inputs and become **build artifacts of a release**,
produced by a single serialized producer from the authoritative merged `caliber.yaml`.

1. **No human PR may add or modify a rootfile** (CI hard-block).
2. Rootfiles are (re)generated automatically when a **GitHub Release is published**.
3. A release regenerates only the calibers whose **transpiler output** changed (vs their
   newest existing rootfile), and commits the results back to `main` via an
   **bot PR that a human must approve** (`main` requires 1 review; auto-merge lands it
   once approved and green).

## Hard constraint (drives the whole design)

Spellcaster consumes rootfiles from the git tree via
`rootfiles = "github:MakinaHQ/config/machines/<m>/<net>/rootfiles"` in every
`config.toml`. So generated rootfiles **must land in that in-tree path on `main`**.
They therefore continue to live in `main` — but authored exclusively by the release
workflow, never by a human PR.

## Decisions (locked)

| Decision                       | Choice                                                                                                                                                                                                                                                                                                                                                                      |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Where generated rootfiles live | In-tree on `main` (spellcaster path unchanged)                                                                                                                                                                                                                                                                                                                              |
| Release trigger                | GitHub Release **published** (`on: release: { types: [published] }`)                                                                                                                                                                                                                                                                                                        |
| Which calibers regenerate      | **Output-based**: transpile every caliber, diff against its newest existing rootfile; only the changed set is checked/validated/committed (see "Output-based change detection on release" — supersedes git-path scoping, which is retained only for the lighter-weight PR check)                                                                                            |
| Existing 120 rootfiles         | Keep as-is (historical migrations)                                                                                                                                                                                                                                                                                                                                          |
| How the bot writes to `main`   | Release workflow opens a **bot PR requiring 1 approving review** (auto-merge lands it once approved and green) using a **dedicated `RELEASE_BOT_TOKEN`** (GitHub App installation token or fine-grained PAT, not `GITHUB_TOKEN`) so the PR's required checks actually fire; the PR guard runs in **verify mode** on the bot branch (bytes must reproduce transpiler output) |

## Dependency graph → "affected calibers"

A caliber resolves inputs from:

- local `machines/<m>/<net>/instructions/*.yaml` (via `!include "./instructions/…"`)
- **shared top-level** `instructions/*.yaml` (via `!include "../../../instructions/…"`)
- `blueprints/**` and `blueprints-x/**` (via instruction `path:` references)
- `token-lists/*.json` (transpiler `-t` argument)
- config embedded in `caliber.yaml` itself

**Affected-set rule** from a `git diff` (`<base>..HEAD`):

- A change under `machines/<m>/<net>/**` (excluding `rootfiles/`) ⇒ caliber `<m>/<net>`
  is a candidate.
- A change under a **global** source dir — `instructions/**`, `blueprints/**`,
  `blueprints-x/**`, `token-lists/**` ⇒ **all** calibers are candidates (any may depend
  on them).
- Changes elsewhere (`.github/**`, `scripts/**`, `docs/**`, `*.md`, …) ⇒ no calibers.

This git-path affected-set rule is used by the **PR gate** (`transpiler.yaml`) to decide
which calibers to transpile/check/validate for a PR. The **release** does not rely on it:
it uses output-based detection over all calibers (see "Recommended amendment"), which
cannot miss a caliber.

**Output-diff comparison (essential everywhere).** For each caliber under consideration,
transpile and compare the fresh output against that dir's **newest existing rootfile**;
only treat it as changed where the output _actually_ differs. Consequences:

- A global change sweeps all 26 calibers but yields new rootfiles only where output
  changed (e.g. a typo-only edit yields none).
- On release, comparing output over _all_ calibers means even an unforeseen transitive
  dependency cannot cause a stale rootfile to ship — output is source-of-truth.

## Components

All CI changes are in `.github/workflows/` plus one shared reusable workflow. The three
Python validators (`scripts/validate_*.py`) and their tests are reused unchanged; only
_what path they are pointed at_ changes (generated rootfiles instead of PR-added ones).

### A. `rootfiles-guard.yaml` — PR hard-block + bot-verify (new)

The security boundary. Trigger: `pull_request` (NOT `pull_request_target`). The job
_always runs_ and always reports (never skipped at job level, so the required check never
deadlocks the merge). Explicit `permissions: contents: read`.

Logic:

1. Compute added+modified rootfiles: `git diff --diff-filter=AM origin/<base_ref> --
   'machines/*/*/rootfiles/*.toml'`. Deletions (`--diff-filter=D`) are allowed (pruning
   stale migrations).
2. If none ⇒ **pass** (fast path; no toolchain built).
3. If some AND the PR is **not** a genuine release-bot PR ⇒ **fail** with a message
   pointing to the release flow. This is the human "no hand-authored rootfiles" rule.
4. If some AND the PR **is** a genuine release-bot PR ⇒ **verify mode**: build the pinned
   transpiler and, for every added/modified rootfile, re-transpile its caliber to a temp
   file and require **byte-identical** output (raw `diff`, the proven comparison from the
   old workflow). Pass only if all match; else fail.

"Genuine release-bot PR" requires **both**:

- `github.head_ref` matches `release/rootfiles/*`, **and**
- `github.event.pull_request.user.login` == the release bot/app login (a human cannot
  spoof the bot actor).

**Why verify mode instead of a blanket exemption:** a blanket "trust the bot branch"
exemption is exploitable — a human with write access could push a hand-crafted rootfile
onto an open bot PR's branch (the PR author stays the bot, so branch+actor checks still
pass). Verify mode closes this in code: any rootfile on the bot branch that is not
reproducible transpiler output fails the byte-diff, regardless of who pushed it. The
transpiler is only built in verify mode (rare) or never (human PRs fail before building).

Defense in depth (config, documented): restrict push access to `release/rootfiles/*` to
the bot/app via a branch/ruleset so humans cannot push there at all.

This is the single **required status check** that enforces "no rootfile reaches `main`
unless it is reproducible transpiler output."

### B. `_transpile-validate.yaml` — shared logic (new, `on: workflow_call`)

The one place that knows how to transpile + validate, called by both PR CI and the
release workflow. Inputs: `selection` = `diff` (PR) or `all` (release), and `base_ref`
(git ref to diff against, used only when `selection: diff`). Behavior:

1. Checkout config repo (full history) + pinned `MakinaHQ/transpiler`; build it
   (`cargo build --release`, cached).
2. Determine the caliber set: for `selection: diff`, the git-path affected-set from
   `git diff <base_ref>..HEAD`; for `selection: all`, every caliber.
3. **Transpile pass (cheap, no network)** — for each caliber `<m>/<net>` in the set:
   - Detect `--lite` by grepping `makina_lite_module` in `caliber.yaml`.
   - Transpile to a **conforming temp path** `machines/<m>/<net>/rootfiles/__ci_generated__.toml`
     (matches the validators' `^machines/([^/]+)/([^/]+)/rootfiles/([^/]+\.toml)$` regex).
     A transpile failure fails the workflow.
   - Byte-compare the temp output to the dir's newest existing rootfile; record `changed:
     true|false` and the temp file path.
4. **Validate pass (network) — only for `changed: true` calibers:**
   - Run transpiler `check --github-errors` (needs `ETHERSCAN_API_KEY`).
   - Run the three validators against the temp file: `validate_open_positions.py`,
     `validate_base_tokens.py`, `validate_token_chains.py` (need `ALCHEMY_API_KEY`).
     Their unit tests run too (as today).
     Skipping unchanged calibers keeps network cost proportional to real change and makes a
     comment/whitespace-only PR fast.
5. Output the list of `(machine, chain, changed, tmp_path)` records for the caller.

Secrets (`ETHERSCAN_API_KEY`, `ALCHEMY_API_KEY`) are passed explicitly to the called
workflow (scoped, not blanket `secrets: inherit`).

### C. `transpiler.yaml` — PR gate (repurposed)

- Trigger: `pull_request`.
- Calls `_transpile-validate.yaml` with `base_ref = origin/<base_ref>`.
- After it returns, **deletes** all `__ci_generated__.toml` temp files. Commits nothing.
- Net effect: a PR cannot merge source that fails to transpile, fails `check`, or fails
  any validator — validated against exactly what a release would emit. The old
  "added rootfile must equal transpiler output" diffing is removed (obsolete; no rootfiles
  in PRs).

### D. `release.yaml` — release producer (new)

- Trigger: `release: { types: [published] }`. Permissions: `contents: write`,
  `pull-requests: write` (least privilege; nothing else).
- **Change detection is output-based, not git-diff-based** (see "Recommended amendment"
  below — this supersedes git-path scoping for the release). Steps:
  1. Call `_transpile-validate.yaml` with `selection: all`. It transpiles every caliber,
     records the **changed** set by byte-diff, and runs `check` + validators on the
     changed set only. A caliber with no existing rootfile counts as changed (first
     rootfile). A comment/whitespace-only edit is unchanged ⇒ skipped.
  2. Rename each changed temp file to the final name
     `machines/<m>/<net>/rootfiles/<YYYYMMDD>-<release-tag-slug>.toml` (date from the
     release's `published_at`; `<release-tag-slug>` = tag lowercased and reduced to
     `[a-z0-9-]`). Delete all temp files for unchanged calibers. The date format is
     coupled to `rootfiles-guard`'s filename regex — changing one without the other
     makes the guard reject the release bot's own output.
  3. If nothing changed ⇒ log "no rootfiles to regenerate", open **no** PR, exit 0.
  4. Else create branch `release/rootfiles/<release-tag-slug>`, commit
     `chore(release): rootfiles for <tag>`, push, open a PR with `gh pr create`, enable
     `gh pr merge --auto`. PR body lists the regenerated calibers.

- **Bot identity:** the push, PR creation, and merge use `secrets.RELEASE_BOT_TOKEN` (a
  GitHub App installation token or fine-grained PAT with `contents:write` +
  `pull-requests:write` on this repo) — **not** the default `GITHUB_TOKEN`. GitHub does
  not fire further workflow runs on PRs opened by `GITHUB_TOKEN`, so `rootfiles-guard`
  (verify mode) and other required checks would never start, leaving the PR permanently
  unmergeable. Using a dedicated bot token makes the bot PR behave like a normal
  contributor PR: its checks run, and a reviewer can merge it once they're green.

- **Injection hardening:** `github.event.release.tag_name`, `published_at`, and any
  attacker-influenceable field are passed via `env:` and referenced quoted (`"$VAR"`) —
  never interpolated directly into a `run:` script — and the slug is reduced to
  `[a-z0-9-]` before use in branch names, file paths, and commit messages.

### Data flow

```
Human PR (source only) ──▶ rootfiles-guard.yaml   (fails if a human adds/modifies a rootfile)
                        └▶ transpiler.yaml ──▶ _transpile-validate.yaml (selection: diff)
                                                 (transpile→diff→[check+validate changed], temp, no commit)

GitHub Release published ──▶ release.yaml
      ├─ _transpile-validate.yaml (selection: all)  ← transpile ALL, detect changed by output, validate changed
      ├─ rename changed temps → <ts>-<tag>.toml
      └─ bot branch → commit → PR (needs 1 approval) ← rootfiles-guard runs in VERIFY mode on this PR
                                   │
                                   ▼
                             main (rootfiles updated) ──▶ spellcaster github:.../rootfiles
```

## Fate of the standalone validator workflows

`open-positions.yaml`, `base-tokens.yaml`, and `token-chains.yaml` currently trigger on
`pull_request` and validate the PR-added rootfile. Since PRs no longer add rootfiles,
these standalone triggers are dead. Their **validation is folded into
`_transpile-validate.yaml`** (run against generated rootfiles from both the PR and
release paths), so coverage is preserved and on-chain calls aren't duplicated. The three
standalone workflow files are **deleted**; the `scripts/validate_*.py` and
`tests/test_validate_*.py` are kept and reused.

## Docs

- `README.md` → rewrite the "Updating the rootfiles" section: humans edit source files
  only (`caliber.yaml`, instructions, blueprints, token-lists); rootfiles are produced by
  publishing a GitHub Release; describe how to cut a release and what gets regenerated.
- `AGENTS.md` / `CLAUDE.md` → update any guidance that tells agents to generate/commit
  rootfiles by hand (e.g. `/compile` guidance, plan templates) to reflect that rootfiles
  are release artifacts.

## Operational prerequisites (outside this repo's code)

1. Branch protection on `main`: mark the required status check with context string **`rootfiles-guard`** (the job id from `rootfiles-guard.yaml`, the enforcement boundary).
   Set `required_approving_review_count: 1` so nothing lands unreviewed; admins get a
   ruleset bypass checkbox on a PR for the cases that need it.
2. Auto-merge enabled on the repo.
3. Provision **`RELEASE_BOT_TOKEN`**: a GitHub App installation token (recommended) or
   fine-grained PAT scoped to this repo with `contents:write` + `pull-requests:write`,
   stored as a repo secret. Used by `release.yaml` to push the bot branch and open/merge
   the PR, so its checks actually run (see "Operational caveat" above). If using a
   ruleset/branch-protection rule restricting who may push to `release/rootfiles/*`
   (defense in depth, recommended), allow this bot identity.
4. Secrets already present: `ETHERSCAN_API_KEY`, `ALCHEMY_API_KEY`.

## Non-goals

- No change to spellcaster or the `github:` resolution scheme.
- No change to the transpiler.
- Existing rootfiles are not purged or rewritten.
- No dependency-graph parser for instruction→blueprint edges; path-based candidate
  scoping plus the output-diff guard is sufficient and robust.

## Output-based change detection on release (locked)

The original framing was "regenerate only calibers whose source changed since the
previous release," scoped by a `git diff` of source paths. The edge-case study found two
problems with git-path scoping **on the release**:

1. **Miss risk.** Path scoping relies on the assumption that a caliber's includes never
   reach outside its own `machines/<m>/<net>/` dir or the known global dirs. That holds
   today, but a future cross-dir include would silently make a release skip an affected
   caliber and ship a stale rootfile — the exact class of bug we are eliminating.
2. **Redundant work / imprecision.** A source edit that does not change transpiler output
   (comments, whitespace, reordering) would still mark the caliber "changed" by path and
   run needless on-chain validation, while adding no rootfile.

**Resolution (confirmed):** on the release, detect change by **transpiler output**, not by
git path. Transpile all calibers (cheap, no network), byte-diff each against its newest
existing rootfile, and treat the set that differs as "changed." Then run the expensive
`check` + validators, and commit rootfiles, only for that changed set. This is strictly
more correct (cannot miss a caliber), yields exactly the "only relevant rootfiles" result
the original decision wanted, and keeps network cost proportional to real change.
Component D is written to this. **Git-path scoping is retained only for the PR gate**
(`transpiler.yaml`), where a full output sweep on every PR is not warranted and a miss
there cannot corrupt `main` (the release's full sweep is the backstop).

## Security analysis

Threat model: **can anything other than reproducible transpiler output reach a rootfile on
`main`?**

| Vector                                                                              | Outcome                                                                                                                                                                                                                                                                                                            |
| ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Human opens a PR adding/modifying a rootfile                                        | `rootfiles-guard` fails (human path). Blocked.                                                                                                                                                                                                                                                                     |
| Human names branch `release/rootfiles/x` to hit the exemption                       | Exemption also requires PR author == bot login; a human author fails the check. Blocked.                                                                                                                                                                                                                           |
| Human with write access pushes a hand-crafted rootfile onto an open bot PR's branch | Guard is in **verify mode** for bot PRs: every added/modified rootfile must byte-match fresh transpiler output. Tampered content fails the diff. Blocked. (Defense in depth: restrict push to `release/rootfiles/*` to the bot.)                                                                                   |
| Human edits `caliber.yaml`/instructions maliciously                                 | Not a rootfile, so allowed to open — but this is the intended review surface. Caught by human PR review + transpiler `check` + the three validators (open-positions, base-tokens, token-chains) run against generated output. Same trust model as today; source review is now the single security-relevant review. |
| Malicious change to a global blueprint/instruction/token-list                       | On PR: affected-set = all calibers ⇒ all are transpiled/checked/validated (heavier, but correct). On release: full output sweep regenerates every caliber whose output changed. No silent skip.                                                                                                                    |
| Direct push to `main`                                                               | Blocked by branch protection (operational prerequisite).                                                                                                                                                                                                                                                           |
| Secret exfiltration                                                                 | Triggers are `pull_request` (never `pull_request_target`), so fork PRs receive **no** secrets and cannot exfiltrate; same-repo branch PRs are trusted collaborators. Secrets (`ETHERSCAN_API_KEY`, `ALCHEMY_API_KEY`) are passed via `env:` only, never echoed.                                                    |
| Command injection via release tag / branch name                                     | All GitHub-context strings are passed through `env:` and referenced quoted; slugs reduced to `[a-z0-9-]` before use in paths/branches/messages. No direct `${{ }}` interpolation into `run:`.                                                                                                                      |
| Over-privileged token                                                               | Explicit least-privilege `permissions:` per workflow — PR checks `contents: read`; release `contents: write` + `pull-requests: write`.                                                                                                                                                                             |

**What is intentionally NOT protected:** the correctness of the _source_ a human merges.
Bad-but-valid source (e.g. a wrong-but-real token address) transpiles fine and only fails
if a validator or reviewer catches it — identical to today. Rootfiles being reproducible
does not make the underlying source correct.

### Operational caveat (resolved)

PRs opened by the built-in `GITHUB_TOKEN` do **not** trigger further workflow runs
(GitHub's recursion guard). Resolved by having `release.yaml` open/merge the bot PR with
`secrets.RELEASE_BOT_TOKEN` (App installation token or fine-grained PAT) instead of
`GITHUB_TOKEN` — see Component D. Its checks fire normally, giving an independent
re-verification (`rootfiles-guard` verify mode) at review time rather than trusting
release.yaml's own run alone.

## Edge cases

- **Typo / comment / whitespace-only caliber edit** (the asked-about case): output is
  byte-identical to the newest existing rootfile ⇒ release commits **no** rootfile, opens
  **no** PR. On PR, `transpiler.yaml` still transpiles/checks/validates it and passes. No
  churn. ✅
- **New machine/network with no existing rootfile**: newest-existing is empty ⇒ any output
  "differs" ⇒ first rootfile is committed. ✅
- **Release with zero effective change**: full output sweep finds no diffs ⇒ no PR opened,
  exit 0. No empty PRs. ✅
- **First release after adopting this system**: existing rootfiles were hand-authored and
  may reflect divergent branch states (the bug being fixed). The first release regenerates
  every caliber whose authoritative output differs from its last hand-authored rootfile —
  i.e. it _heals_ prior drift. Expect a larger-than-usual first regeneration; this is
  correct and desirable.
- **Transpiler version bump** (pinned `MakinaHQ/transpiler` advances): may change output
  for many calibers ⇒ a release legitimately regenerates them. A real migration; expected.
- **Two releases the same day / concurrent releases**: filenames disambiguate via the
  tag slug (the date alone is shared), and sort monotonically after existing files.
  Concurrent runs open separate bot PRs from their respective HEADs; the reviewer merges
  them in turn (the second may need updating). Low risk; re-runnable.
- **Position deleted from `caliber.yaml`**: output changes ⇒ new rootfile. The
  open-positions validator still guards that on-chain-open positions retain accounting, so
  removing a position that is still open on-chain fails CI. ✅
- **`--lite` (makina-x) calibers**: detected by grepping `makina_lite_module` in
  `caliber.yaml` (parity with the existing workflow). If a lite caliber lacks the marker,
  transpile fails loudly on the missing accounting instruction.
- **`config.toml` change** (machine-level, e.g. new caliber address, swapper): not a
  transpiler input (the transpiler reads `caliber.yaml`, not `config.toml`) and lives at
  `machines/<m>/config.toml`, outside the `machines/<m>/<net>/**` affected path ⇒ no
  rootfile regeneration, correctly. Caliber-address changes that must affect output live in
  `caliber.yaml`'s `config:` block, which is inside the network dir and is transpiled.
- **dprint formatting**: transpiler output is already dprint-clean (proven by the old raw
  `diff` gate and by `dprint check` passing on committed rootfiles), so byte-diff needs no
  normalization; the bot PR's own `dprint check` is an independent backstop against drift.
- **Pre-release vs full release**: `on: release: published` fires for pre-releases too.
  Output-based detection needs no baseline, so a pre-release simply triggers a full output
  sweep like any published release. Decide during implementation whether to filter
  pre-releases out (default: no — treat every published release the same).
- **`main` moves during a release**: the bot PR is created from `main`'s HEAD at run time;
  the reviewer updates the branch if needed. If blocked, the release is re-runnable idempotently
  (same tag ⇒ same slug ⇒ same target files; timestamps differ only if `published_at`
  differs, which it will not for the same release).
- **Bot PR re-triggering PR CI**: `rootfiles-guard` runs in verify mode (passes iff bytes
  reproduce); `transpiler.yaml` sees no source changes ⇒ no affected calibers ⇒ trivially
  passes; `linting` (`dprint check`) validates format.
- **Validator flakiness / RPC rate limits on release**: a transient on-chain failure fails
  the release before any commit ⇒ no partial/half-written rootfiles reach `main`. Re-run
  the release. (Consider a small retry/timeout in the validators; out of scope here.)
