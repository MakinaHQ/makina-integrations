---
description: Import sUSN-style feature PRs from MakinaHQ/config into this repo, regenerate rootfiles, verify, and clean up.
argument-hint: <config PR numbers or URLs, space/comma separated> [target-branch-name]
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

# Import feature PR(s) from MakinaHQ/config

You are importing one or more feature PRs that live in the **`MakinaHQ/config`** repo
into **this** repo (`MakinaHQ/makina-integrations`), regenerating the affected rootfiles,
verifying, and cleaning up after yourself.

**PRs to import:** $ARGUMENTS

> `config` and `makina-integrations` are **two separate repos with the same layout**
> (`blueprints/`, `instructions/`, `machines/<machine>/<chain>/{caliber.yaml,rootfiles}`,
> `token-lists/`). Their shared files have **diverged** — never wholesale-copy a shared
> file; apply only the feature-specific additions. A local clone of config usually exists
> at `/Users/augustin/Desktop/makina/config`.

Work through the steps below in order. Track them with a todo list. The workflow
culminates in **opening a PR against `main`** (see step 10). Along the way, if anything
is **fundamentally different** between the config repo and this repo — such that the
imported feature would not cleanly fit here (see "When to stop and ask" below) — **stop
and ask the user for clarification** before proceeding. Do not paper over a mismatch by
guessing.

### When to stop and ask

Pause and ask the user rather than improvising when you hit any of these:

- The target `caliber.yaml`, blueprint, or instruction has **structurally diverged** from
  config in a way that means the feature's block can't be dropped in as an additive change
  (renamed/removed fields, a different position schema, a moved include path).
- A **base ref / stacked dependency** the PR relies on is **not present** here and isn't
  obviously already covered.
- A `${token_list.<chain>.<SYM>}` reference, chain, machine, or address in the source PR
  **doesn't resolve** to anything in this repo, or resolves to something different.
- The transpiler output or a validator fails in a way that points at a real config
  mismatch (not just a placeholder you were told to keep).

In these cases, describe precisely what differs (config vs. here) and ask how the user
wants it reconciled. It is always better to ask than to force a PR that doesn't fit.

## 1. Understand the PRs

For each PR: `gh pr view <n> --repo MakinaHQ/config --json number,title,state,baseRefName,headRefName,body`
and `gh pr diff <n> --repo MakinaHQ/config` (save each diff to the scratchpad and read it).

Determine, per PR:

- Which **new files** it adds (blueprints, instructions).
- Which **shared files** it modifies (`machines/<machine>/<chain>/caliber.yaml`,
  `token-lists/prod-token-list.json`, `config.toml`).
- Its **base ref** — if a PR is stacked on another branch (e.g. a `*-import-*` base-caliber
  import), check whether that base is **already present** in this repo before assuming you
  need it. Often it already is.

## 1b. Prod addresses only — verify every infra address

This is the **prod** repo (`makina-integrations`). Rootfiles here go on-chain against
**production** deployments, so every Makina infra address a blueprint/instruction hardcodes
(OracleRegistry, MathHelper, SwapModule, registries, beacons, bridge adapters, WeirollVM,
helpers, …) **MUST be the prod address** — never a test-infra or ad-hoc deployment. The
config repo's source PRs are frequently authored against **test infra**, so treat every
hardcoded infra address in an imported file as suspect until checked.

Makina deploys its core/periphery infra at the **same deterministic address on every chain**,
so a prod address is chain-independent — the same `0x…` is valid on Ethereum, Base, Arbitrum,
Ink, Monad, Optimism. Canonical **prod** addresses:

| Contract | Prod address (all chains) |
|---|---|
| OracleRegistry | `0xC388B72AB90Be82B230D919F9C05c87F9397f485` |
| TokenRegistry | `0xd9310A41d085c0DC1E40F691e8647080862A5fd4` |
| SwapModule | `0x923c98b22F9c367A109E93f7dfBaCa28b20C17C3` |
| MathHelper (unsigned) | `0x3D623B199E290358416415eA7e05B635E442e3c0` |
| SignedMathHelper | `0xe11b4879a771222CdAe84E4392B03AdAA151bC4D` |
| BooleanHelper | `0x8dc60173F37B34998FD5B2aeF47Dd68C68CC22C4` |
| Bytes32Helper | `0x74DC739B8F98ad0F76Cd8900695DD8D5083E45D3` |
| CastHelper | `0x54423e194CB882608ecd39B94687ed67D89198B5` |
| ContextHelper | `0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE` |
| WeirollVM | `0xFD162A672928bf40E5A81F0D11501D2849841FA6` |
| Caliber Beacon | `0x3f5A881DB86D6f495823028A1e892E7b2CD7e162` |
| AccessManagerUpgradeable | `0x0fCEfa3f1047F35521A49cD8B06faBd588665d7F` |
| SpokeCoreRegistry / SpokeCoreFactory | `0x0FAEeCEab0BCb63bE2Fe984Ea8c77778989d53eA` / `0x8d28A69328561eF9F171c58996fEcB9F494e070c` |

Known **test-infra / non-prod** addresses seen in config PRs (must be replaced if imported):
`0x4B3336630e591D36ca81f0c25b798895289dDD30` (test OracleRegistry),
`0xe75e81E0995816eBcd510Ed9CDD84ED05aC60442` (test OracleRegistry v1.3.0),
`0x16D120a18334e273FA3C029Ece56bfA5A2ABFCFd` (non-prod, unverified MathHelper).

**Checklist for every imported file:**
- Grep the imported blueprints/instructions for hardcoded `0x…` infra addresses (registries,
  helpers, modules, beacons). Protocol-specific addresses (pools, vaults, tokens, EOAs) are
  out of scope here — this is about **Makina infra** only.
- Cross-check each against the prod table above. If an address isn't the prod one — or isn't
  in the table and you can't confirm it's prod — **replace it with the prod address** (comment
  the old value as non-prod), or **stop and ask** if you can't identify the prod equivalent.
- Sanity-check against an existing prod blueprint that uses the same contract (e.g.
  `blueprints/securitize/account.yaml` uses prod OracleRegistry + MathHelper).
- The authoritative source is the **Production Infra Contracts** sheet
  (`~/Downloads/**/Protocol/Production Infra Contracts *.csv`); when in doubt, read it and/or
  verify the contract on-chain (a prod contract is verified with source; test/ad-hoc ones
  often are not).

**Independent on-chain verification (spawn a subagent).** The static table above can go stale,
so do not rely on it alone. After collecting the hardcoded infra addresses, **spawn a
general-purpose subagent** (Agent tool) to independently verify them on-chain, in parallel with
the rest of the import. Give it the list of `(address, expected contract, chain)` tuples and
have it report, per address:
  1. **Verified source** — the contract is verified (has published source) on the relevant
     explorer for that chain. Unverified ⇒ almost certainly not a prod deployment ⇒ flag.
  2. **Prod match** — the address equals the canonical prod address for that contract (same on
     every chain), and the deployed code actually behaves as that contract (e.g. `getPrice`
     returns for OracleRegistry, `mulDiv` for MathHelper).
  3. **Registry registration (if applicable)** — where a registry should know the address,
     confirm it is registered: e.g. the token/position is routed in the **OracleRegistry**
     (`getPrice(token, quote)` does not revert) and listed in the **TokenRegistry**
     (`0xd9310A41d085c0DC1E40F691e8647080862A5fd4`). If a lookup isn't possible, say so rather
     than assuming.
  Prefer the etherscan/tenderly MCP read tools (`read_contract_state`, `get_address_info`) for
  this. **Block the import on any address that fails (1) or (2)** — replace with the prod
  address and regenerate; surface (3) failures to the user as go-live gates (a feed/route may
  simply not be registered on-chain yet).

## 2. NEVER import these (specs / factory notes / docs)

Exclude every one of these — they are notes, not config:
`scripts-factory/`, `docs/superpowers/`, `docs/**/specs/`, `*specs*.yaml`, `SUMMARY.md`,
`FINDINGS.md`, `oracle-setup.md`, `test-report*.md`, `progress.yaml`, `execution-*.md`.
Also strip any dangling `scripts-factory/…` doc-pointer lines from comments you carry over
into caliber files (they reference paths that won't exist here). Comments don't affect
transpiler output.

## 3. Fetch the config branches

```
git remote add config git@github.com:MakinaHQ/config.git 2>/dev/null || true
git fetch config <headRef1> <headRef2> ...
```

## 4. Create the target branch

Off `main` (or the branch the user named): `git checkout main && git checkout -b <branch>`.
Default branch name: a short slug of the feature (the user may pass one as the 2nd arg).

## 5. Copy NEW files verbatim

Use `git show config/<headRef>:<path> > <path>` (byte-exact) for each new blueprint /
instruction file. `mkdir -p` the parent dirs first. Note instruction-file include paths:
top-level instructions live in `instructions/`; a chain-local instruction may live in
`machines/<machine>/<chain>/instructions/` and is included from `caliber.yaml` with
`!include "./instructions/<file>.yaml"`. Blueprint `path:` refs in instruction files are
resolved **relative to the caliber.yaml** (i.e. `../../../blueprints/...` from
`machines/<machine>/<chain>/`), so they work for both top-level and chain-local instructions.

## 6. Merge SHARED files (additions only)

- **caliber.yaml**: `git diff HEAD:<path> config/<base>:<path>` first to see how the repos
  diverge, then apply ONLY the feature's new `positions:` block(s). If several PRs touch the
  same chain's caliber (e.g. two Base positions), merge **all** their positions into the one
  file. Keep placeholder ids/addresses the PR flagged (note them as go-live TODOs); don't
  invent real ones.
- **token-lists/prod-token-list.json**: add only the genuinely new token entries (dedupe;
  ignore cosmetic reorder churn from the source diff). Verify any `${token_list.<chain>.<SYM>}`
  referenced by the imported instructions actually resolves (right `chainId` + `symbol`).
  Validate JSON parses.

## 7. Regenerate the rootfiles

The transpiler is a separate Rust repo, usually not installed. Build it once:

```
git clone --depth 1 git@github.com:MakinaHQ/transpiler.git <scratch>/transpiler
(cd <scratch>/transpiler && cargo build --release)
BIN=<scratch>/transpiler/target/release/transpiler
```

For each affected `(machine, chain)`:

```
"$BIN" -i machines/<machine>/<chain>/caliber.yaml -o /tmp/out.toml -t token-lists/prod-token-list.json
```

Place the output as a new rootfile named `YYYYMMDD-<slug>.toml` (use today's date). Per the
`Transpiler` CI rules: history is **append-only** (never modify existing rootfiles), and the
new filename must be **lexicographically newer** than every existing file in that
`rootfiles/` dir.

## 8. Verify (evidence before claiming done)

- **Clean diff sanity**: diff the new mainnet-style rootfile against the previous latest —
  expect only the root-hash line to change plus pure additions (no deletions/other changes).
- **Transpiler re-verify (this is the CI check)**: re-run the transpiler and `diff` its
  output against the committed rootfile — must match byte-for-byte, for every affected chain.
- **`dprint check`** on every changed file — must exit 0. Raw transpiler output is already
  dprint-clean; do NOT hand-format rootfiles.
- **Prod-address audit (see §1b)**: grep the changed blueprints/instructions AND the generated
  rootfiles for any known non-prod infra address; there must be **zero** matches. Confirm the
  infra addresses that made it into the rootfile leaves are the prod ones.
- **token-chains** validator: `uv run python scripts/validate_token_chains.py <new rootfiles>`.
- **token-lists** validator (`uv run python scripts/validate_token_lists.py token-lists/prod-token-list.json`)
  needs `ALCHEMY_API_KEY` (on-chain metadata check). If it's absent, note it as not-run
  rather than failing.

## 9. Clean up

```
git remote remove config
```

Leave the scratchpad transpiler clone in place for reuse (it's outside the repo), or remove it.

## 10. Commit and open the PR (base `main`)

Once the import is verified and clean, **open a PR against `main`** (`gh pr create --base main`).

- **Absolutely no signs of AI — this is non-negotiable.** No `Co-Authored-By: Claude…`,
  no "Generated with Claude Code", no 🤖, no "as an AI", no Claude/Anthropic mentions —
  anywhere in the branch name, commit message(s), or PR title/body. Write the commit and PR
  as a human engineer would. If you catch any such marker before pushing, strip it.
- Stage only the imported config + regenerated rootfiles. Confirm **nothing** from step 2 is
  staged (`git status --short | grep -iE 'scripts-factory|docs/|spec|test-report|SUMMARY|FINDINGS|oracle-setup|progress.yaml|execution-'` → must be empty).
- PR base is `main`. Summarize what landed and list the remaining on-chain go-live
  prerequisites (oracle feed routes, `addBaseToken`, role grants, real EOAs, canonical
  position ids) that the source PRs flagged.

## Report

State the regenerated root hashes, the verification results (pass/fail with output), and any
placeholders / go-live gates carried over.
