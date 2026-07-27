# Release-Generated Rootfiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop humans from hand-authoring rootfiles in PRs; make rootfiles a build artifact produced by publishing a GitHub Release.

**Architecture:** A new composite action (`transpile-validate`) is the single place that transpiles a caliber, diffs the output against its newest existing rootfile, and — for whatever changed — runs `check` plus the three on-chain validators. Two workflows call it: `transpiler.yaml` (PR gate, git-diff-scoped, commits nothing) and `release.yaml` (on `release: published`, sweeps every caliber, renames changed output to a dated rootfile, and lands it on `main` via an auto-merging bot PR). A third workflow, `rootfiles-guard.yaml`, is the enforcement boundary: it fails any human PR that adds/modifies a rootfile, and re-verifies (byte-for-byte) any rootfile the release bot's own PR adds.

**Tech Stack:** GitHub Actions (composite action + reusable-by-call workflows), Rust transpiler CLI (`MakinaHQ/transpiler`, invoked via `cargo run`), Python 3 (`uv run`) for the affected-calibers rule and the existing on-chain validators, bash for CI orchestration (existing repo convention).

## Global Constraints

- Spec of record: `docs/superpowers/specs/2026-07-24-release-generated-rootfiles-design.md`. This plan implements it; where an implementation detail below refines the spec's mechanism (not its decisions), that's called out inline rather than re-litigated.
- Rootfile path regex (matches the three existing validators): `^machines/([^/]+)/([^/]+)/rootfiles/([^/]+\.toml)$`.
- Global source dirs whose change affects every caliber: `instructions/`, `blueprints/`, `blueprints-x/`, `token-lists/`.
- Transpiler CLI, exactly as proven in the current `transpiler.yaml`: `cargo run -r -- -i <input> -o <output> -t <token-list> [--lite] [transpile|check --github-errors]`. `--lite` detection: `grep -q 'makina_lite_module' "$caliber"`.
- Token list path (single file, no ambiguity): `token-lists/prod-token-list.json`.
- Temp/generated rootfile name (never committed as-is): `__ci_generated__.toml`.
- Final committed rootfile name: `<YYYYMMDDHHMMSS>-<release-tag-slug>.toml`, timestamp from `github.event.release.published_at`, slug = tag lowercased with every run of non-`[a-z0-9]` collapsed to a single `-` and leading/trailing `-` stripped.
- Bot branch naming: `release/rootfiles/<release-tag-slug>`.
- New secret: `secrets.RELEASE_BOT_TOKEN` (GitHub App installation token or fine-grained PAT; `contents:write` + `pull-requests:write` on this repo). New repo variable: `vars.RELEASE_BOT_LOGIN` (the login `RELEASE_BOT_TOKEN` authenticates as).
- Existing secrets, unchanged: `secrets.ETHERSCAN_API_KEY`, `secrets.ALCHEMY_API_KEY`.
- Action pins: `actions/checkout@v6`, `dtolnay/rust-toolchain@stable`, `Swatinem/rust-cache@v2`, `astral-sh/setup-uv@v7` (matches the most recent workflows in this repo). No `pull_request_target` anywhere.
- `scripts/validate_open_positions.py`, `scripts/validate_base_tokens.py`, `scripts/validate_token_chains.py` and their tests are reused **unchanged** — they already operate purely on a rootfile's path + content (proven by their `ROOTFILE_PATH_RE`), so pointing them at a generated temp file works with zero code changes.
- Never commit with `git add -A`; every `git add` in generated workflows uses an explicit file list.

---

### Task 1: Affected-calibers rule (`scripts/compute_affected_calibers.py`)

**Files:**

- Create: `scripts/compute_affected_calibers.py`
- Test: `tests/test_compute_affected_calibers.py`

**Interfaces:**

- Produces: `discover_calibers(repo_root: Path) -> list[tuple[str, str]]` — sorted `(machine, chain)` pairs from `machines/*/*/caliber.yaml`. `affected_calibers(changed_paths: list[str], all_calibers: list[tuple[str, str]]) -> list[tuple[str, str]]` — pure function implementing the affected-set rule. CLI: `uv run python scripts/compute_affected_calibers.py <path> [<path> ...]` prints one `machine/chain` per line (sorted, deduped) to stdout, using `Path.cwd()` as the repo root.
- Consumed by: Task 4 (`transpiler.yaml`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_compute_affected_calibers.py`:

```python
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import compute_affected_calibers as cac


ALL_CALIBERS = [
    ("dbit", "mainnet"),
    ("dusd", "mainnet"),
    ("dusd", "base"),
]


class TestAffectedCalibers(unittest.TestCase):
    def test_local_caliber_file_change_affects_only_that_caliber(self):
        changed = ["machines/dusd/mainnet/caliber.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [("dusd", "mainnet")])

    def test_local_instruction_change_affects_only_that_caliber(self):
        changed = ["machines/dusd/mainnet/instructions/merkl.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [("dusd", "mainnet")])

    def test_global_instructions_change_affects_all_calibers(self):
        changed = ["instructions/makina.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), sorted(ALL_CALIBERS))

    def test_global_blueprints_change_affects_all_calibers(self):
        changed = ["blueprints/aave/deposit.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), sorted(ALL_CALIBERS))

    def test_blueprints_x_change_affects_all_calibers(self):
        changed = ["blueprints-x/aave-horizon/deposit.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), sorted(ALL_CALIBERS))

    def test_token_list_change_affects_all_calibers(self):
        changed = ["token-lists/prod-token-list.json"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), sorted(ALL_CALIBERS))

    def test_rootfile_change_is_excluded(self):
        changed = ["machines/dusd/mainnet/rootfiles/20260722-x.toml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [])

    def test_machine_level_config_change_is_excluded(self):
        changed = ["machines/dusd/config.toml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [])

    def test_unrelated_path_is_excluded(self):
        changed = [".github/workflows/linting.yaml", "README.md", "scripts/foo.py"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [])

    def test_unknown_machine_chain_pair_is_ignored(self):
        changed = ["machines/doesnotexist/mainnet/caliber.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [])

    def test_mixed_local_and_global_returns_all(self):
        changed = ["machines/dusd/mainnet/caliber.yaml", "blueprints/aave/deposit.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), sorted(ALL_CALIBERS))

    def test_empty_input_returns_empty(self):
        self.assertEqual(cac.affected_calibers([], ALL_CALIBERS), [])

    def test_blank_lines_are_ignored(self):
        changed = ["", "  ", "machines/dusd/mainnet/caliber.yaml"]
        self.assertEqual(cac.affected_calibers(changed, ALL_CALIBERS), [("dusd", "mainnet")])


class TestDiscoverCalibers(unittest.TestCase):
    def test_discovers_all_caliber_yaml_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "machines" / "dusd" / "mainnet").mkdir(parents=True)
            (root / "machines" / "dusd" / "mainnet" / "caliber.yaml").write_text("config: {}\n")
            (root / "machines" / "dbit" / "base").mkdir(parents=True)
            (root / "machines" / "dbit" / "base" / "caliber.yaml").write_text("config: {}\n")
            (root / "machines" / "dbit" / "base" / "instructions").mkdir()

            result = cac.discover_calibers(root)
            self.assertEqual(result, [("dbit", "base"), ("dusd", "mainnet")])

    def test_ignores_directories_without_caliber_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "machines" / "dusd" / "mainnet" / "rootfiles").mkdir(parents=True)
            result = cac.discover_calibers(root)
            self.assertEqual(result, [])


class TestMainCli(unittest.TestCase):
    def test_main_prints_affected_pairs_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "machines" / "dusd" / "mainnet").mkdir(parents=True)
            (root / "machines" / "dusd" / "mainnet" / "caliber.yaml").write_text("config: {}\n")
            (root / "machines" / "dbit" / "base").mkdir(parents=True)
            (root / "machines" / "dbit" / "base" / "caliber.yaml").write_text("config: {}\n")

            script = Path(__file__).resolve().parents[1] / "scripts" / "compute_affected_calibers.py"
            proc = subprocess.run(
                [sys.executable, str(script), "instructions/makina.yaml"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(proc.stdout.splitlines(), ["dbit/base", "dusd/mainnet"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run python -m unittest tests.test_compute_affected_calibers -v`
Expected: `ModuleNotFoundError: No module named 'compute_affected_calibers'`

- [ ] **Step 3: Write the implementation**

Create `scripts/compute_affected_calibers.py`:

```python
#!/usr/bin/env python3
"""Resolve which calibers are affected by a set of changed file paths.

Used by the PR gate (transpiler.yaml) to scope which calibers get
transpiled/checked/validated for a given PR: a caliber is affected when its
own files changed, or a shared/global source it could depend on changed.
Prints one "machine/chain" pair per line, sorted.

Release scoping does NOT use this: releases sweep every caliber and detect
change by transpiler output, which can't miss a dependency this path-based
rule doesn't know about. See
docs/superpowers/specs/2026-07-24-release-generated-rootfiles-design.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Any change under these prefixes could affect every caliber, since
# instructions/blueprints/blueprints-x are shared across machines and the
# token list is a transpiler input for all of them.
GLOBAL_PREFIXES = ("instructions/", "blueprints/", "blueprints-x/", "token-lists/")


def discover_calibers(repo_root: Path) -> list[tuple[str, str]]:
    """Return sorted (machine, chain) pairs for every machines/*/*/caliber.yaml."""
    pairs = {
        (caliber_path.parent.parent.name, caliber_path.parent.name)
        for caliber_path in repo_root.glob("machines/*/*/caliber.yaml")
    }
    return sorted(pairs)


def affected_calibers(
    changed_paths: list[str], all_calibers: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Apply the affected-set rule to a list of changed file paths."""
    all_set = set(all_calibers)
    affected: set[tuple[str, str]] = set()

    for raw_path in changed_paths:
        path = raw_path.strip()
        if not path:
            continue

        if path.startswith(GLOBAL_PREFIXES):
            return sorted(all_set)

        parts = path.split("/")
        # machines/<machine>/<chain>/<rest...>, excluding machines/<m>/<c>/rootfiles/*
        if len(parts) >= 4 and parts[0] == "machines" and parts[3] != "rootfiles":
            pair = (parts[1], parts[2])
            if pair in all_set:
                affected.add(pair)

    return sorted(affected)


def main(argv: list[str]) -> int:
    all_calibers = discover_calibers(Path.cwd())
    for machine, chain in affected_calibers(argv, all_calibers):
        print(f"{machine}/{chain}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run python -m unittest tests.test_compute_affected_calibers -v`
Expected: all tests `ok`, `OK` summary line.

- [ ] **Step 5: Commit**

```bash
git add scripts/compute_affected_calibers.py tests/test_compute_affected_calibers.py
git commit -m "feat(ci): add affected-calibers rule for the PR transpile gate"
```

---

### Task 2: Shared composite action (`transpile-validate`) and retiring the superseded validator workflows

**Why a composite action and not a `workflow_call` reusable workflow (spec Component B says "reusable workflow"):** a `workflow_call` job runs on its own runner; the caller job cannot see the temp rootfiles it produced without an artifact upload/download round-trip. A composite action's steps run inside the _calling job_, on the same runner/workspace, so the `__ci_generated__.toml` files it writes are still on disk for the caller's next steps (renaming them in `release.yaml`, deleting them in `transpiler.yaml`). This is a mechanical refinement of the spec's Component B, not a re-litigation of any locked decision — same contract (one shared "transpile + diff + validate changed" implementation), different GitHub Actions primitive.

**Files:**

- Create: `.github/actions/transpile-validate/action.yml`
- Delete: `.github/workflows/open-positions.yaml`
- Delete: `.github/workflows/base-tokens.yaml`
- Delete: `.github/workflows/token-chains.yaml`

**Interfaces:**

- Produces: composite action at `./.github/actions/transpile-validate`. Inputs: `calibers` (newline-separated `machine/chain` pairs, required), `etherscan-api-key` (required), `alchemy-api-key` (required). Output: `changed-calibers` (newline-separated `machine/chain` pairs whose transpiled output differs from that dir's newest existing rootfile — reference as `steps.<id>.outputs['changed-calibers']`, bracket notation, since the key has a hyphen). Side effect: leaves `machines/<machine>/<chain>/rootfiles/__ci_generated__.toml` for every caliber passed in, whether or not it changed — callers own cleanup/renaming.
- Consumed by: Task 3 (`rootfiles-guard.yaml`, verify mode), Task 4 (`transpiler.yaml`), Task 5 (`release.yaml`).

- [ ] **Step 1: Create the composite action**

Create `.github/actions/transpile-validate/action.yml`:

```yaml
name: Transpile and Validate Calibers
description: >-
  Transpiles each given caliber, diffs the output against its newest existing
  rootfile, and runs `check` plus the on-chain validators for whichever
  calibers actually changed. Leaves a __ci_generated__.toml temp file in each
  processed caliber's rootfiles/ directory — callers own renaming/deleting it.

inputs:
  calibers:
    description: Newline-separated "machine/chain" pairs to process.
    required: true
  etherscan-api-key:
    required: true
  alchemy-api-key:
    required: true

outputs:
  changed-calibers:
    description: >-
      Newline-separated "machine/chain" pairs whose transpiled output differs
      from their newest existing rootfile.
    value: ${{ steps.diff.outputs.changed }}

runs:
  using: composite
  steps:
    - name: Checkout transpiler repository
      uses: actions/checkout@v6
      with:
        repository: MakinaHQ/transpiler
        path: transpiler

    - name: Install Rust toolchain
      uses: dtolnay/rust-toolchain@stable

    - name: Cache Cargo
      uses: Swatinem/rust-cache@v2
      with:
        workspaces: transpiler

    - name: Build transpiler
      shell: bash
      working-directory: transpiler
      run: cargo build --release

    - name: Install uv
      uses: astral-sh/setup-uv@v7

    - name: Transpile each caliber and diff against its newest existing rootfile
      id: diff
      shell: bash
      env:
        CALIBERS: ${{ inputs.calibers }}
      run: |
        set -euo pipefail
        changed=()
        while IFS= read -r pair; do
          [ -z "$pair" ] && continue
          machine="${pair%%/*}"
          chain="${pair#*/}"
          dir="machines/$machine/$chain"
          caliber="$dir/caliber.yaml"
          mkdir -p "$dir/rootfiles"
          tmp="$dir/rootfiles/__ci_generated__.toml"

          lite=""
          if grep -q 'makina_lite_module' "$caliber"; then lite="--lite"; fi
          echo "Transpiling $caliber $lite"
          (cd transpiler && cargo run -r -- -i "../$caliber" -o "../$tmp" -t "../token-lists/prod-token-list.json" $lite)

          newest=$(cd "$dir/rootfiles" && ls -1 | grep -E '^[0-9]{8}' | LC_ALL=C sort | tail -n 1 || true)
          if [ -z "$newest" ] || ! diff -q "$dir/rootfiles/$newest" "$tmp" > /dev/null 2>&1; then
            echo "  -> changed (vs '${newest:-<none>}')"
            changed+=("$pair")
          else
            echo "  -> unchanged (matches $newest)"
          fi
        done <<< "$CALIBERS"

        {
          echo "changed<<TRANSPILE_VALIDATE_EOF"
          if [ "${#changed[@]}" -gt 0 ]; then
            printf '%s\n' "${changed[@]}"
          fi
          echo "TRANSPILE_VALIDATE_EOF"
        } >> "$GITHUB_OUTPUT"

    - name: Run transpiler checks and on-chain validators for changed calibers
      shell: bash
      env:
        CHANGED: ${{ steps.diff.outputs.changed }}
        ETHERSCAN_API_KEY: ${{ inputs.etherscan-api-key }}
        ALCHEMY_API_KEY: ${{ inputs.alchemy-api-key }}
      run: |
        set -euo pipefail
        rootfiles=()
        while IFS= read -r pair; do
          [ -z "$pair" ] && continue
          machine="${pair%%/*}"
          chain="${pair#*/}"
          dir="machines/$machine/$chain"
          caliber="$dir/caliber.yaml"
          tmp="$dir/rootfiles/__ci_generated__.toml"

          lite=""
          if grep -q 'makina_lite_module' "$caliber"; then lite="--lite"; fi
          echo "Running transpiler check for $caliber $lite"
          (cd transpiler && cargo run -r -- -i "../$caliber" -t "../token-lists/prod-token-list.json" $lite check --github-errors)
          rootfiles+=("$tmp")
        done <<< "$CHANGED"

        if [ "${#rootfiles[@]}" -gt 0 ]; then
          uv run --with 'web3==7.14.1' --with pyyaml python -m unittest tests.test_validate_open_positions
          uv run --with 'web3==7.14.1' --with pyyaml python -m unittest tests.test_validate_base_tokens
          uv run python -m unittest tests.test_validate_token_chains

          uv run --with 'web3==7.14.1' --with pyyaml python scripts/validate_open_positions.py "${rootfiles[@]}"
          uv run --with 'web3==7.14.1' --with pyyaml python scripts/validate_base_tokens.py "${rootfiles[@]}"
          uv run python scripts/validate_token_chains.py "${rootfiles[@]}"
        else
          echo "No changed calibers — skipping check and on-chain validators."
        fi
```

- [ ] **Step 2: Validate the action's YAML syntax**

Run:

```bash
uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/actions/transpile-validate/action.yml'))" && echo "VALID YAML"
```

Expected: `VALID YAML`, no traceback.

- [ ] **Step 3: Delete the three superseded standalone validator workflows**

Their `pull_request` triggers validated a PR-added rootfile — under this design PRs never add rootfiles, so the triggers are dead. Their validation logic (`scripts/validate_*.py`, kept unchanged) is now invoked by this composite action from both `transpiler.yaml` and `release.yaml`.

```bash
git rm .github/workflows/open-positions.yaml .github/workflows/base-tokens.yaml .github/workflows/token-chains.yaml
```

- [ ] **Step 4: Commit**

```bash
git add .github/actions/transpile-validate/action.yml
git commit -m "feat(ci): add shared transpile-validate composite action

Retires the three standalone pull_request validator workflows
(open-positions, base-tokens, token-chains) — their PR-added-rootfile
trigger is obsolete under the release-generated-rootfiles model. Their
scripts/validate_*.py logic is unchanged and now runs from this action."
```

---

### Task 3: `rootfiles-guard.yaml` — the enforcement boundary

**Files:**

- Create: `.github/workflows/rootfiles-guard.yaml`

**Interfaces:**

- Consumes: Task 2's composite action (`./.github/actions/transpile-validate`), `vars.RELEASE_BOT_LOGIN` (provisioned in Task 7).
- Produces: the required status check with context string `rootfiles-guard` (the job id, since the job has no display name) — this exact string is what Task 7's branch-protection step marks required in the ruleset.

- [ ] **Step 1: Create the workflow**

Create `.github/workflows/rootfiles-guard.yaml`:

```yaml
name: Rootfiles Guard

# Enforces the release-generated-rootfiles model: no human PR may add or
# modify a rootfile. Rootfiles are produced by publishing a GitHub Release
# (see release.yaml) and land on main via the release bot's own PR. That
# PR's added/modified rootfiles are re-verified here in "verify mode": they
# must be byte-identical to fresh transpiler output, or this check fails
# even for the bot's own branch.
#
# See docs/superpowers/specs/2026-07-24-release-generated-rootfiles-design.md

on:
  pull_request:

permissions:
  contents: read

jobs:
  guard:
    name: Block hand-authored rootfiles
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - name: Checkout
        uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - name: Detect added/modified rootfiles and PR identity
        id: detect
        env:
          BASE_REF: ${{ github.base_ref }}
          HEAD_REF: ${{ github.head_ref }}
          PR_AUTHOR: ${{ github.event.pull_request.user.login }}
          RELEASE_BOT_LOGIN: ${{ vars.RELEASE_BOT_LOGIN }}
        run: |
          set -euo pipefail
          FILES=$(git diff --name-only --diff-filter=AM "origin/$BASE_REF" -- 'machines/*/*/rootfiles/*.toml')

          if [ -z "$FILES" ]; then
            echo "files=" >> "$GITHUB_OUTPUT"
            echo "count=0" >> "$GITHUB_OUTPUT"
            echo "calibers=" >> "$GITHUB_OUTPUT"
          else
            {
              echo "files<<ROOTFILES_GUARD_FILES_EOF"
              echo "$FILES"
              echo "ROOTFILES_GUARD_FILES_EOF"
            } >> "$GITHUB_OUTPUT"
            echo "count=$(echo "$FILES" | wc -l | tr -d ' ')" >> "$GITHUB_OUTPUT"

            CALIBERS=$(echo "$FILES" | awk -F/ '{print $2"/"$3}' | sort -u)
            {
              echo "calibers<<ROOTFILES_GUARD_CALIBERS_EOF"
              echo "$CALIBERS"
              echo "ROOTFILES_GUARD_CALIBERS_EOF"
            } >> "$GITHUB_OUTPUT"
          fi

          if [[ "$HEAD_REF" == release/rootfiles/* && -n "$RELEASE_BOT_LOGIN" && "$PR_AUTHOR" == "$RELEASE_BOT_LOGIN" ]]; then
            echo "is_bot_pr=true" >> "$GITHUB_OUTPUT"
          else
            echo "is_bot_pr=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Pass — no rootfiles touched
        if: steps.detect.outputs.count == 0
        run: echo "No rootfiles added or modified. Pass."

      - name: Reject — human PRs must not add or modify rootfiles
        if: steps.detect.outputs.count > 0 && steps.detect.outputs.is_bot_pr == 'false'
        env:
          FILES: ${{ steps.detect.outputs.files }}
        run: |
          echo "The following rootfiles were added or modified by this PR:"
          echo "$FILES"
          echo ""
          echo "Rootfiles are generated by publishing a GitHub Release, not authored by hand."
          echo "See README.md and docs/superpowers/specs/2026-07-24-release-generated-rootfiles-design.md."
          exit 1

      - name: Verify mode — re-transpile the release bot PR's calibers
        if: steps.detect.outputs.count > 0 && steps.detect.outputs.is_bot_pr == 'true'
        id: verify
        uses: ./.github/actions/transpile-validate
        with:
          calibers: ${{ steps.detect.outputs.calibers }}
          etherscan-api-key: ${{ secrets.ETHERSCAN_API_KEY }}
          alchemy-api-key: ${{ secrets.ALCHEMY_API_KEY }}

      - name: Reject — bot PR rootfiles do not reproduce transpiler output
        if: >-
          steps.detect.outputs.is_bot_pr == 'true' &&
          steps.verify.outputs['changed-calibers'] != ''
        env:
          CHANGED: ${{ steps.verify.outputs['changed-calibers'] }}
        run: |
          echo "The following calibers' committed rootfiles do NOT match fresh transpiler output:"
          echo "$CHANGED"
          echo "This should never happen for a genuine release PR — treating the rootfile(s) as tampered."
          exit 1
```

- [ ] **Step 2: Validate the workflow's YAML syntax**

Run:

```bash
uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/rootfiles-guard.yaml'))" && echo "VALID YAML"
```

Expected: `VALID YAML`, no traceback.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/rootfiles-guard.yaml
git commit -m "feat(ci): add rootfiles-guard — block hand-authored rootfiles in PRs"
```

---

### Task 4: Repurpose `transpiler.yaml` as the PR validation gate

**Files:**

- Modify: `.github/workflows/transpiler.yaml` (full rewrite — the old file diffs an _added_ rootfile against transpiler output, which no longer exists as a concept)

**Interfaces:**

- Consumes: Task 1's `scripts/compute_affected_calibers.py`, Task 2's composite action.
- Produces: nothing consumed downstream — this is a terminal PR check.

- [ ] **Step 1: Read the current file so the rewrite is a deliberate replacement**

Run: `cat .github/workflows/transpiler.yaml`

(Confirms the old added-rootfile-diffing logic being removed — it validated a workflow this plan eliminates.)

- [ ] **Step 2: Rewrite the workflow**

Replace the full contents of `.github/workflows/transpiler.yaml` with:

```yaml
name: Transpiler

# Validates that a PR's source (caliber.yaml, instructions, blueprints,
# blueprints-x, token-lists) transpiles cleanly and passes `check` plus the
# on-chain validators. Nothing is committed here — rootfiles are only ever
# produced by a release (release.yaml). Rootfiles must never be added or
# modified in a PR; rootfiles-guard.yaml enforces that separately.
#
# See docs/superpowers/specs/2026-07-24-release-generated-rootfiles-design.md

on:
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  transpile-and-validate:
    name: Transpile and validate affected calibers
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - name: Checkout config repo
        uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - name: Install uv
        uses: astral-sh/setup-uv@v7

      - name: Compute affected calibers
        id: affected
        env:
          EVENT_NAME: ${{ github.event_name }}
          BASE_REF: ${{ github.base_ref }}
        run: |
          set -euo pipefail
          if [ "$EVENT_NAME" = "pull_request" ]; then
            # Scope to the calibers this PR's diff could affect.
            CHANGED_FILES=()
            while IFS= read -r changed; do
              [ -n "$changed" ] && CHANGED_FILES+=("$changed")
            done < <(git diff --name-only "origin/$BASE_REF")

            if [ "${#CHANGED_FILES[@]}" -eq 0 ]; then
              CALIBERS=""
            else
              CALIBERS=$(uv run python scripts/compute_affected_calibers.py "${CHANGED_FILES[@]}")
            fi
          else
            # workflow_dispatch has no base ref to diff against, so validate every
            # caliber — the same sweep a release performs, but committing nothing.
            CALIBERS=$(find machines -mindepth 3 -maxdepth 3 -name caliber.yaml \
              | sed -E 's#^machines/([^/]+)/([^/]+)/caliber\.yaml$#\1/\2#' \
              | LC_ALL=C sort)
          fi

          if [ -z "$CALIBERS" ]; then
            echo "calibers=" >> "$GITHUB_OUTPUT"
          else
            {
              echo "calibers<<TRANSPILER_CALIBERS_EOF"
              echo "$CALIBERS"
              echo "TRANSPILER_CALIBERS_EOF"
            } >> "$GITHUB_OUTPUT"
          fi

      - name: Transpile and validate
        if: steps.affected.outputs.calibers != ''
        uses: ./.github/actions/transpile-validate
        with:
          calibers: ${{ steps.affected.outputs.calibers }}
          etherscan-api-key: ${{ secrets.ETHERSCAN_API_KEY }}
          alchemy-api-key: ${{ secrets.ALCHEMY_API_KEY }}

      - name: Skip — no calibers to validate
        if: steps.affected.outputs.calibers == ''
        run: echo "No calibers to validate."

      - name: Clean up generated temp rootfiles
        if: always()
        run: find machines -name '__ci_generated__.toml' -delete
```

- [ ] **Step 3: Validate the workflow's YAML syntax**

Run:

```bash
uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/transpiler.yaml'))" && echo "VALID YAML"
```

Expected: `VALID YAML`, no traceback.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/transpiler.yaml
git commit -m "refactor(ci): repurpose transpiler.yaml as a no-commit PR validation gate

Rootfiles are no longer added in PRs, so the old added-rootfile diffing
is gone. This now transpiles+checks+validates whichever calibers the PR's
diff could affect, using the shared transpile-validate action, and commits
nothing."
```

---

### Task 5: `release.yaml` — the release producer

**Files:**

- Create: `.github/workflows/release.yaml`

**Interfaces:**

- Consumes: Task 2's composite action; `secrets.RELEASE_BOT_TOKEN` (provisioned in Task 7).
- Produces: a bot PR against `main` on branch `release/rootfiles/<slug>` containing the regenerated rootfiles, auto-merging once required checks (including `rootfiles-guard` in verify mode) pass.

- [ ] **Step 1: Create the workflow**

Create `.github/workflows/release.yaml`:

```yaml
name: Release Rootfiles

# Fires when a GitHub Release is published. Transpiles every caliber,
# detects which ones' output actually changed vs their newest existing
# rootfile, runs `check` plus the on-chain validators for the changed set,
# and opens an auto-merging PR (as the release bot) with the regenerated
# rootfiles. If nothing changed, no PR is opened.
#
# See docs/superpowers/specs/2026-07-24-release-generated-rootfiles-design.md
#
# Required repo config (see the operational setup checklist):
#   - secrets.RELEASE_BOT_TOKEN  (GitHub App installation token or fine-grained PAT;
#     contents:write + pull-requests:write on this repo)
#   - vars.RELEASE_BOT_LOGIN     (the login RELEASE_BOT_TOKEN authenticates as)
#   - secrets.ETHERSCAN_API_KEY, secrets.ALCHEMY_API_KEY (already present)
#   - "Allow auto-merge" enabled on the repo

on:
  release:
    types: [published]

permissions:
  contents: write
  pull-requests: write

jobs:
  release-rootfiles:
    name: Transpile and commit release rootfiles
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - name: Checkout config repo
        uses: actions/checkout@v6
        with:
          ref: main
          fetch-depth: 0
          token: ${{ secrets.RELEASE_BOT_TOKEN }}

      - name: Install uv
        uses: astral-sh/setup-uv@v7

      - name: Compute release identifiers
        id: release
        env:
          TAG_NAME: ${{ github.event.release.tag_name }}
          PUBLISHED_AT: ${{ github.event.release.published_at }}
        run: |
          set -euo pipefail
          SLUG=$(echo "$TAG_NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g' | sed -E 's/^-+|-+$//g')
          if [ -z "$SLUG" ]; then
            echo "::error::Release tag '$TAG_NAME' contains no alphanumeric characters, so it cannot be turned into a rootfile name or branch name. Re-tag the release using a name containing letters or digits." >&2
            exit 1
          fi
          TIMESTAMP=$(date -u -d "$PUBLISHED_AT" +%Y%m%d%H%M%S)
          echo "slug=$SLUG" >> "$GITHUB_OUTPUT"
          echo "timestamp=$TIMESTAMP" >> "$GITHUB_OUTPUT"
          echo "branch=release/rootfiles/$SLUG" >> "$GITHUB_OUTPUT"

      - name: List all calibers
        id: all
        run: |
          set -euo pipefail
          CALIBERS=$(find machines -mindepth 3 -maxdepth 3 -name caliber.yaml \
            | sed -E 's#^machines/([^/]+)/([^/]+)/caliber\.yaml$#\1/\2#' \
            | LC_ALL=C sort)
          {
            echo "calibers<<RELEASE_ALL_CALIBERS_EOF"
            echo "$CALIBERS"
            echo "RELEASE_ALL_CALIBERS_EOF"
          } >> "$GITHUB_OUTPUT"

      - name: Transpile all calibers and detect changed output
        id: transpile
        uses: ./.github/actions/transpile-validate
        with:
          calibers: ${{ steps.all.outputs.calibers }}
          etherscan-api-key: ${{ secrets.ETHERSCAN_API_KEY }}
          alchemy-api-key: ${{ secrets.ALCHEMY_API_KEY }}

      - name: Rename changed rootfiles and clean up unchanged temp files
        id: rename
        env:
          CHANGED: ${{ steps.transpile.outputs['changed-calibers'] }}
          TIMESTAMP: ${{ steps.release.outputs.timestamp }}
          SLUG: ${{ steps.release.outputs.slug }}
        run: |
          set -euo pipefail
          renamed=()
          while IFS= read -r pair; do
            [ -z "$pair" ] && continue
            machine="${pair%%/*}"
            chain="${pair#*/}"
            dir="machines/$machine/$chain/rootfiles"
            final="$dir/${TIMESTAMP}-${SLUG}.toml"
            mv "$dir/__ci_generated__.toml" "$final"
            renamed+=("$final")
            echo "Regenerated $final"
          done <<< "$CHANGED"

          find machines -name '__ci_generated__.toml' -delete

          if [ "${#renamed[@]}" -eq 0 ]; then
            echo "has_changes=false" >> "$GITHUB_OUTPUT"
          else
            echo "has_changes=true" >> "$GITHUB_OUTPUT"
            {
              echo "files<<RELEASE_RENAMED_FILES_EOF"
              printf '%s\n' "${renamed[@]}"
              echo "RELEASE_RENAMED_FILES_EOF"
            } >> "$GITHUB_OUTPUT"
          fi

      - name: No changes — nothing to release
        if: steps.rename.outputs.has_changes == 'false'
        run: echo "No caliber's transpiled output changed since the last release. Nothing to commit."

      - name: Commit, push, and open the auto-merge PR
        if: steps.rename.outputs.has_changes == 'true'
        env:
          GH_TOKEN: ${{ secrets.RELEASE_BOT_TOKEN }}
          TAG_NAME: ${{ github.event.release.tag_name }}
          BRANCH: ${{ steps.release.outputs.branch }}
          FILES: ${{ steps.rename.outputs.files }}
        run: |
          set -euo pipefail
          git config user.name "release-rootfiles-bot"
          git config user.email "release-rootfiles-bot@users.noreply.github.com"

          RENAMED=()
          while IFS= read -r file; do
            [ -n "$file" ] && RENAMED+=("$file")
          done <<< "$FILES"

          git checkout -b "$BRANCH"
          git add -- "${RENAMED[@]}"
          git commit -m "chore(release): rootfiles for ${TAG_NAME}"
          git push origin "$BRANCH"

          BULLETS=$(printf -- '- `%s`\n' "${RENAMED[@]}")
          BODY=$(printf 'Rootfiles regenerated for release `%s`.\n\nRegenerated calibers:\n\n%s\n' "$TAG_NAME" "$BULLETS")
          gh pr create --title "chore(release): rootfiles for ${TAG_NAME}" --body "$BODY" --base main --head "$BRANCH"
          gh pr merge "$BRANCH" --auto --squash
```

- [ ] **Step 2: Validate the workflow's YAML syntax**

Run:

```bash
uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yaml'))" && echo "VALID YAML"
```

Expected: `VALID YAML`, no traceback.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yaml
git commit -m "feat(ci): add release.yaml — transpile and commit rootfiles on release publish"
```

---

### Task 6: Update docs and agent-facing guidance

Scope check performed against the whole repo (not just README.md): grepped every `.claude/commands/*.md` and `.claude/skills/**` file for rootfile-commit guidance. `/compile`, `/test-compile`, `root-updates.md`, `blueprints.md`, and `testing.md` only ever write to scratch/temp paths (`caliber-test.yaml`, `test-output.toml`, `compile-output.toml`) for local iteration — none of them tell anyone to commit a production rootfile, so none of them need to change. Two real hits: `integrate-x.md` Stage 3 currently instructs producing "the rootfile" as a integration deliverable, and `test_e2e_x.md` documents defaulting to "newest in the sibling `rootfiles/`" — both assume a human-committed rootfile that no longer exists pre-merge.

**Files:**

- Modify: `README.md:49-51`
- Modify: `.claude/commands/integrate-x.md:208`
- Modify: `.claude/commands/test_e2e_x.md:37-39`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Rewrite README.md's "Updating the rootfiles" section**

Replace (README.md lines 49-51):

```markdown
#### Updating the rootfiles

When instructions, blueprints, or calibers are updated, the rootfiles must be regenerated. Add the new rootfiles to the corresponding `rootfiles` directory. Previous rootfiles are kept as references and remain necessary until the upgrade is applied on-chain. You can think of the rootfiles directory as a collection of “migration files.” The name of the rootfile should be: `[timestamp]-[name-of-the-migration].toml`. Where timestamps are in the format `YYYYMMDDHHMMSS` or `YYYYMMDD`.
```

with:

```markdown
#### Updating the rootfiles

Rootfiles are **generated, not hand-authored**. Contributors only ever edit source files —
`caliber.yaml`, `instructions/`, `blueprints/`, `blueprints-x/`, and the token lists. A CI
check (`rootfiles-guard`) rejects any PR that adds or modifies a file under a `rootfiles/`
directory.

New rootfiles are produced by publishing a GitHub Release. Publishing a release runs the
`release.yaml` workflow, which:

1. Transpiles every `caliber.yaml` in the repo.
2. Compares each caliber's fresh output against its newest existing rootfile — only
   calibers whose output actually changed are touched.
3. Runs the transpiler's `check` plus the on-chain validators (open positions, base
   tokens, token chains) against the changed set.
4. Commits the regenerated rootfiles (named `[timestamp]-[release-tag].toml`) to a bot
   branch and opens a PR that merges automatically once required checks pass.

Previous rootfiles are kept as references and remain necessary until the corresponding
upgrade is applied on-chain — nothing is deleted automatically. See
`docs/superpowers/specs/2026-07-24-release-generated-rootfiles-design.md` for the full
design (this replaces the old model, where contributors hand-generated and committed
rootfiles directly in their PRs — which let a later-merged PR silently overwrite an
earlier one's rootfile).
```

- [ ] **Step 2: Fix `integrate-x.md` Stage 3 to use a scratch path, not the production directory**

Replace (`.claude/commands/integrate-x.md:208`):

```markdown
Then compile the caliber with the `--lite` transpiler to produce the rootfile (see prerequisites).
```

with:

```markdown
Then compile the caliber with the `--lite` transpiler to a **scratch path** —
`scripts-factory/{protocol}/{chain}/{pool_id}/test-rootfile.toml`, NOT
`machines/{machine}/{network}/rootfiles/`. Production rootfiles are release-only now (see
README.md); this pipeline must not add or commit a rootfile. Pass the scratch path to
`/test_e2e_x` explicitly via `--rootfile`.
```

- [ ] **Step 3: Fix `test_e2e_x.md`'s stale "rootfiles are committed" assumption**

Replace (`.claude/commands/test_e2e_x.md:37-39`):

```markdown
- **No transpiler needed** — makina-x rootfiles are committed; the harness parses the compiled
  rootfile rather than recompiling (the fallback transpiler lacks `--lite`). Recompile separately
  if you changed the caliber source, then re-run.
```

with:

```markdown
- **No transpiler needed for calibers already on `main`** — their historical rootfiles remain
  committed, and the harness parses the compiled rootfile rather than recompiling (the fallback
  transpiler lacks `--lite`). For a caliber under active integration (a new position not yet in
  any committed rootfile), compile to a scratch path yourself (see `/integrate-x` Stage 3) and
  pass `--rootfile <scratch-path>` explicitly — do **not** rely on "newest in the sibling
  `rootfiles/`" below, since production rootfiles are release-only now and may be stale relative
  to your branch's `caliber.yaml`.
```

- [ ] **Step 4: Commit**

```bash
git add README.md .claude/commands/integrate-x.md .claude/commands/test_e2e_x.md
git commit -m "docs: update rootfile guidance for the release-generated model"
```

---

### Task 7: Operational GitHub repo setup

Not a code task — this is the checklist for wiring the actual `MakinaHQ/config` repo so Tasks 1-6 take effect. Do this **after** Tasks 1-6 are merged to `main`: `rootfiles-guard` can't be marked "required" in branch protection until GitHub has seen it run at least once (i.e., after the workflow file exists on `main` and has run on at least one PR).

- [ ] **Step 1: Provision the release bot's token**

Create a GitHub App (recommended — scoped, revocable, shows as its own bot identity in PR history) or a fine-grained PAT owned by a dedicated machine account, granted **Contents: Read & write** + **Pull requests: Read & write** on `MakinaHQ/config` only. Note the exact login this identity authenticates as (an App shows up as `<app-slug>[bot]`; a PAT shows up as the owning user's login) — this is `RELEASE_BOT_LOGIN`.

Store the token as a repo secret (never paste the raw token into a chat or commit):

```bash
gh secret set RELEASE_BOT_TOKEN --repo MakinaHQ/config
```

(Run this yourself — `gh` will prompt for the value, or pipe it from your own secret manager. I will not request or handle the raw token.)

- [ ] **Step 2: Set the bot's login as a repo variable**

```bash
gh variable set RELEASE_BOT_LOGIN --repo MakinaHQ/config --body "<the-bot-login-from-step-1>"
```

- [ ] **Step 3: Enable auto-merge on the repo**

```bash
gh repo edit MakinaHQ/config --enable-auto-merge
```

- [ ] **Step 4: Require `rootfiles-guard` in branch protection on `main`**

Via `gh api` (adjust any existing required checks/settings rather than replacing them wholesale — inspect current protection first):

```bash
gh api repos/MakinaHQ/config/branches/main/protection --jq .required_status_checks
```

Then add `rootfiles-guard` (the `rootfiles-guard.yaml` job id / context string) to the required-checks contexts, alongside whatever is already required.

- [ ] **Step 5 (defense in depth, optional): restrict pushes to `release/rootfiles/*` to the bot**

A branch protection rule or repository ruleset scoped to `release/rootfiles/**` that only allows the bot identity (App or PAT owner) to push. This closes the "human pushes onto an open bot PR branch" vector at the permissions layer, in addition to `rootfiles-guard`'s verify-mode check already closing it in code.

- [ ] **Step 6: Cut a real end-to-end test**

Open a throwaway PR that only touches a comment in a `caliber.yaml` (no output change) and confirm: `rootfiles-guard` passes trivially (no rootfile touched), `transpiler.yaml` runs and passes. Then publish a small test GitHub Release and confirm `release.yaml` runs, finds no changed output (since nothing real changed), and opens **no** PR. Then make a real caliber change, merge it, and publish a release — confirm a bot PR appears with the correct rootfile, `rootfiles-guard` passes it in verify mode, and it auto-merges.
