---
description: E2E-simulate a makina-x (Safe-module) blueprint — drive the deployed MakinaXModule on a fork, run deposit -> withdraw, report pass/fail (no accounting)
argument-hint: <pr-url | instruction-path | machine caliber> [--amount n] [--position-id id] [--feeds "0xTok=0xFeed1[:0xFeed2],..."] [--post-to-pr]
---

# Test E2E (makina-x)

Validate a **makina-x** blueprint by executing its exact compiled weiroll instructions against
the **real deployed `MakinaXModule`** on a fork, as the Safe, then reporting the **deposit ->
withdraw** lifecycle. makina-x positions are **not NAV-accounted on-chain**, so — unlike
`/test_e2e` — there is **no ACCOUNTING action**: this command tests management flows only.

**Why this is a separate command.** `/test_e2e` drives `spellcaster manage-position` through a
**caliber** (`caliber_address`). makina-x has no caliber: positions are held by a **Safe** and
executed by a **`MakinaXModule`** Safe module (`makina_lite_module`), which the local `makina-rs`
spellcaster does not support. So this command uses a **forge fork-test harness** instead of
spellcaster.

This is a **resolver + dispatcher**: it figures out *what* makina-x caliber to test from
`$ARGUMENTS`, then runs the deterministic harness (`scripts/makinax_e2e_harness.py`) per target
and relays the result. The harness owns the playbook (parse rootfile → generate & run the forge
test → report); this command does not re-implement it.

---

## Environment prerequisites (verify BEFORE running)

- **foundry** — `forge` must be installed (`which forge`). The harness forks via forge's
  `createSelectFork`; no separate anvil process is needed.
- **RPC** — `MAINNET_RPC_URL` (and any L2 `*_RPC_URL`) in `.claude/settings.local.json` `env`.
  A missing L2 RPC is not a blocker: the harness derives a gateway URL from the tenderly mainnet
  key (e.g. `https://base.gateway.tenderly.co/<key>`). Override with `--rpc-url`.
- **forge-std** — the harness builds a standalone forge project remapped to the makina-x checkout's
  `lib/forge-std`; it will `git submodule update --init lib/forge-std` there if missing. Point at a
  non-default checkout with `--makina-x-path` or `$MAKINA_X_PATH` (default
  `/Users/augustin/Desktop/git/makina-x`).
- **No transpiler needed for calibers already on `main`** — their historical rootfiles remain
  committed, and the harness parses the compiled rootfile rather than recompiling (the fallback
  transpiler lacks `--lite`). For a caliber under active integration (a new position not yet in
  any committed rootfile), compile to a scratch path yourself (see `/integrate-x` Stage 3) and
  pass `--rootfile <scratch-path>` explicitly — do **not** rely on "newest in the sibling
  `rootfiles/`" below, since production rootfiles are release-only now and may be stale relative
  to your branch's `caliber.yaml`.

---

## Step 1 — Parse `$ARGUMENTS` and detect the input form

Flags (strip before detection, forward the rest to the harness):
- `--amount <n>` — base-token deposit amount in human units (default `10000`).
- `--position-id <id>` — restrict to one position (default: the first deposit+withdraw pair).
- `--feeds "0xTok=0xFeed1[:0xFeed2],..."` — WALLED modules only (see below).
- `--post-to-pr` — after reporting, post the report as a PR comment (PR-URL form only).

Detect the remaining argument (in order):

| If the argument… | Form | Action |
|---|---|---|
| matches `github.com/.../pull/<n>` | **PR URL** | Step 2a |
| ends in `.yaml` / is an existing path | **instruction or caliber path** | Step 2b |
| is two bare tokens | **`machine caliber`** | Step 2c |

If none match, print the `argument-hint` and stop.

## Step 2a — PR URL → target caliber(s)

```bash
gh pr view <n> --repo MakinaHQ/config --json headRefName,files
gh pr checkout <n>   # same-repo; remember the current branch and restore it when done
```
From `files`, keep every changed **`machines/<machine>/<net>/caliber.yaml`** and any changed
**`blueprints-x/**`** / **`machines/<m>/<net>/instructions/*.yaml`**. Derive one target per changed
makina-x caliber (a caliber whose config has `makina_lite_module`). Skip non-makina-x calibers —
those are `/test_e2e`'s job.

## Step 2b — instruction/caliber path → target

If given a `caliber.yaml`, that is the target. If given an instruction file, find the
`machines/<m>/<net>/caliber.yaml` that `!include`s it. Confirm it's makina-x
(`grep -q makina_lite_module`); if not, tell the user to use `/test_e2e`.

## Step 2c — `machine caliber` → target

Target is `machines/<machine>/<caliber-network>/caliber.yaml`.

---

## Step 3 — Run the harness per target (sequential)

```bash
uv run scripts/makinax_e2e_harness.py <caliber.yaml> \
    [--amount <n>] [--position-id <id>] [--feeds "..."] \
    --out <report.md> --json
```
The harness:
1. Reads the caliber (`makina_lite_module`, `safe_address`, positions) and the compiled rootfile
   (newest in the sibling `rootfiles/`, or `--rootfile`).
2. Picks the deposit + withdraw MANAGEMENT instructions for the position and reconstructs each
   `Instruction` struct from the compiled `commands`/`state`/`bitmap`.
3. Generates a forge test from `scripts/templates/MakinaXE2E.t.sol.tmpl` and runs it on the fork:
   - **compile check** — recomputed composite merkle root == the rootfile's transpiler root
     (validates the compile against the module's on-chain leaf encoding; skipped when a position
     has ≠2 leaves).
   - **lifecycle** — prank Safe (`addOperator` + `setAllowedInstrRoot`), `deal` the base token,
     prank operator `managePosition(mgmt, emptyAcct)` for **deposit** then **withdraw**; assert
     the base token is pulled then returned and the position token rises then falls.
4. Exits non-zero on failure and writes a markdown report.

**Operating mode.** OPEN/FENCED modules are unguarded → the empty accounting instruction used above
is valid (chronograph-x is FENCED). If the module is **WALLED**, `managePosition` requires an
ACCOUNTING instruction *and* oracle feed routes: the harness will use a compiled ACCOUNTING
instruction if the rootfile has one and wire feeds from `--feeds`; without both it reports the
WALLED target as unsupported. No makina-x caliber is WALLED today, so this path ships **built but
unvalidated** — treat a WALLED PASS with skepticism until a real WALLED caliber exists.

---

## Step 4 — Relay results

The harness report is not shown to the user automatically — **relay it**. For each target surface
the pass/fail table (compile-root check / deposit / withdraw — **no accounting row**, by design),
any revert reasons, and the report path. End with an overall PASS / FAIL across targets. With
`--post-to-pr`, post the combined report via `gh pr comment <n> --repo MakinaHQ/config --body-file`.

If you checked out a PR branch in Step 2a, **restore the original branch** before finishing.
