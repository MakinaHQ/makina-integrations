---
description: End-to-end makina-x (Safe-module) pool integration — specs, execution testing, and blueprints-x writing (no accounting)
argument-hint: [--resume] [--context "..."] <pool-identifier>
---

# Pool Integration (makina-x)

The makina-x parallel to `/integrate`. Same specs → execution → blueprint pipeline, but for
**makina-x** funds: positions are held by a **Safe** and executed by a **`MakinaXModule`** Safe
module (config has `safe_address` + `makina_lite_module`, **not** `caliber_address`). makina-x
positions are **not NAV-accounted on-chain**, so this pipeline has **NO accounting stage**:
instructions are **MANAGEMENT-only**, blueprints live in **`blueprints-x/`** (no `account.yaml`),
calibers compile with **`--lite`**, and Stage 4 validates with **`/test_e2e_x`** (not spellcaster).

Parse `$ARGUMENTS`:
- `--resume`: Resume from existing progress.yaml (skip Stage 0)
- `--context "..."`: Plain-English hints, stored in progress.yaml and passed to all agents as advisory context.
- Remaining: **pool identifier** (dialectic ID, address, or pool name)

If the target machine turns out NOT to be makina-x (its caliber has `caliber_address`, not
`makina_lite_module`), stop and tell the user to use `/integrate` instead.

---

## Environment Prerequisites (verify BEFORE Stage 0)

### Transpiler with `--lite` (mandatory for makina-x)
makina-x calibers have no accounting instruction, so the transpiler rejects them unless run with
`--lite` ("Allow positions without accounting instructions for Makina Lite"). **The rev-`9471437`
fallback transpiler does NOT support `--lite`.** Use a `--lite`-capable build — the same one CI uses
(`MakinaHQ/transpiler`, v0.2.4+):

    git clone https://github.com/MakinaHQ/transpiler && (cd transpiler && cargo build --release)
    TP=transpiler/target/release/transpiler

Set `TRANSPILER_PATH` to a `--lite`-capable binary in `.claude/settings.local.json`. Canonical
invocation (note the trailing `--lite`; token list is mandatory because instructions reference
`${token_list.*}`):

    "$TP" -i machines/<machine-x>/<network>/caliber.yaml \
      -t token-lists/prod-token-list.json [-o out.toml] --lite [check | transpile]

### Fork tooling (Stage 2 and Stage 4)
- foundry: `forge --version` (Stage 4's harness forks via `createSelectFork`; no anvil process needed).
- RPC: `echo "$MAINNET_RPC_URL"` (and any L2 `*_RPC_URL`) in `.claude/settings.local.json`.

### `blueprints-x/` reference integrations
Copy the shape from existing makina-x work: `blueprints-x/aave-horizon/` (Aave supply, on
`machines/chronograph-x/`), `machines/uniswap-x-filler/`, `machines/morpho-curator/`.

---

## Required Artifacts Checklist

| Stage | Required Files | Description |
|-------|---------------|-------------|
| 1_specs | `specs.yaml`, `SUMMARY.md` | Pool specifications and summary |
| 1b_enrich | `functions.md` | Solidity code for key functions |
| 1c_offchain | `API.md`, `METATYPES.md` | Offchain fetchers/metatypes (if needed) |
| 2_{action} | `execution-{action}.md` | Execution report per action (deposit/withdraw[/harvest]) |
| 3_blueprint | `blueprints-x/` + instruction files | Blueprint + MANAGEMENT instruction YAML |
| 4_test | `test-report.md` | `/test_e2e_x` e2e result |

### File Structure

```
scripts-factory/{protocol}/{chain}/{pool_id}/
├── progress.yaml          # checkpoint state
├── specs.yaml             # Stage 1
├── SUMMARY.md             # Stage 1
├── functions.md           # Stage 1b
├── API.md / METATYPES.md  # Stage 1c (if offchain)
├── execution-deposit.md   # Stage 2
├── execution-withdraw.md  # Stage 2
├── execution-harvest.md   # Stage 2 (if applicable)
└── test-report.md         # Stage 4

blueprints-x/{protocol}/
├── deposit.yaml           # NO account.yaml (makina-x is management-only)
└── withdraw.yaml
```

Before marking a stage complete: verify its files exist, update `progress.yaml` artifacts, do not proceed until confirmed.

---

## Stage 0: Intent Specification (MANDATORY)

### 0a. Fetch Pool Context
Silently fetch with `mcp__pools_db__get_pool_context`: protocol, chain, available actions, display
name, and **pool tokens** (addresses/symbols/decimals).

### 0b. Ask User for All Parameters
A SINGLE `AskUserQuestion` with:

```
Q1 "Which makina-x machine should this pool be integrated for?"  Header "Machine"
   Options (dynamic — any machine whose caliber has makina_lite_module):
     - chronograph-x, uniswap-x-filler, morpho-curator, ...
   multiSelect: false

Q2 "Which actions should be tested?"  Header "Actions"
   Options:
     - deposit  (Recommended)
     - withdraw (Recommended)
     - harvest  (if the pool has claimable rewards)
   multiSelect: true
   # NOTE: there is deliberately NO "account" action — makina-x is not NAV-accounted.

Q3 "Which base tokens should be supported?"  Header "Tokens"
   Options: dynamic from pool tokens (0a)
   multiSelect: true
```

### 0c. Create Progress File
`scripts-factory/{protocol}/{chain}/{pool_id}/progress.yaml`:

```yaml
intent:
  pool_id: "{dialectic_id}"
  pool_name: "{pool_display_name}"
  protocol: "{protocol}"
  chain: "{chain}"
  machine: "{makina-x machine}"
  makina_x: true
  actions: [deposit, withdraw]        # from user selection; never includes account
  base_tokens:
    - {address, symbol, decimals, index}
  context: "{context or null}"

current_stage: 1
stages:
  0_intent:   {status: completed, timestamp: "..."}
  1_specs:    {status: pending}
  1b_enrich:  {status: pending}
  1c_offchain:{status: pending}   # conditional
  2_deposit:  {status: pending}   # only if in actions
  2_withdraw: {status: pending}   # only if in actions
  2_harvest:  {status: pending}   # only if in actions
  3_blueprint:{status: pending}
  4_test:     {status: pending}
testnets: {}
```

**There is no accounting-model decision (Stage 0e in `/integrate`).** makina-x positions are not
NAV-accounted, so the POSITION vs BASE-TOKEN archetype and `addBaseToken` do not apply. `affected_tokens`
are simply the tokens moved by the instruction (as in `blueprints-x/aave-horizon`). Value-preservation
checks apply only if the module is WALLED — a rare, governance-gated mode with its own accounting
setup; flag it in `intent.context` if the target Safe is WALLED and expect Stage 4 to need feeds.

### 0d. Confirm summary with the user, then proceed to Stage 1.

Status values: `pending | in_progress | completed | failed`. Failed stages carry `error`, `comment`,
`attempts`, `last_attempt` (same schema as `/integrate`).

---

## Resume Mode (`--resume`)
Find the pool's progress.yaml, read `intent:`, display any failed stage's error/comment, skip to the
first non-completed/failed stage, do not re-ask parameters.

## Using Context
When `intent.context` is set, pass it to each agent prompt as advisory guidance ("verify against
on-chain behavior") — it directs attention but never overrides discovered behavior.

---

## Stage 1: Generate Specs — agent `pool-specs-generator`
```
Generate specs for pool: {pool_identifier}
Output: scripts-factory/{protocol}/{chain}/{pool_id}/
Note: makina-x integration — management-only, NO accounting flow needed.
```
Artifacts: `specs.yaml`, `SUMMARY.md`.

## Stage 1b: Enrich — agent `specs-enricher`
Fetch Solidity for non-standard functions → `functions.md`.

## Stage 1c: Offchain (conditional) — agent `offchain-analyzer`
Run if context/specs indicate merkle proofs, signatures, APIs, or the action is `harvest`; else skip.
Artifacts: `API.md`, `METATYPES.md`.

## Stage 2: Test Execution (sequential) — agent `execution-explorer`
Run actions in order on a shared fork: **deposit → withdraw → harvest (if applicable)**. **No
`account` step.** Artifacts: `execution-deposit.md`, `execution-withdraw.md`, `execution-harvest.md`.

Tell the agent: this is makina-x — the position is executed **as the Safe** (holder/`on_behalf_of`/`to`
= the Safe); there is no caliber and no accounting to test; only the management (supply/withdraw/claim)
flows and their exact call args matter. Fork backend: local anvil (`anvil --fork-url $MAINNET_RPC_URL`)
or Tenderly, same as `/integrate`.

## Stage 3: Write Blueprint — agent `blueprint-writer`
```
Convert execution flows to makina-x blueprint + instruction files.
Machine: {intent.machine}   Source: scripts-factory/{protocol}/{chain}/{pool_id}/
Blueprint out: blueprints-x/{protocol}/{deposit,withdraw}.yaml   (NO account.yaml)
Instruction out: machines/{machine}/{network}/instructions/{protocol}-{pool}.yaml
```
Requirements for the agent:
- Blueprints go under **`blueprints-x/`**, mirror `blueprints-x/aave-horizon/` (management-only, no
  ACCOUNTING/balanceOf accounting step). Instance-specific addresses (pool/router) are blueprint
  inputs, not config.
- Each instruction: `instruction_type: "MANAGEMENT"`, holder / `on_behalf_of` / `to` = `${config.safe_address}`,
  `affected_tokens` = the moved base token(s). **Do not** emit an `account` instruction or an
  ACCOUNTING action.
- Protocol/instance-specific addresses (e.g. the pool) are hardcoded in the instruction file, not
  added to caliber config (only Safe-wide values live in config).
Then compile the caliber with the `--lite` transpiler to produce the rootfile (see prerequisites).

## Stage 4: Test Blueprint — `/test_e2e_x`
Do NOT use `blueprint-tester`/spellcaster (no lite-module support). Run the makina-x harness:
```
uv run scripts/makinax_e2e_harness.py \
  machines/{machine}/{network}/caliber.yaml [--amount N] [--position-id ID] \
  --out scripts-factory/{protocol}/{chain}/{pool_id}/test-report.md --json
```
It drives the real deployed `MakinaXModule` on a fork, runs **deposit → withdraw**, validates the
compiled merkle root against the on-chain leaf encoding, and writes `test-report.md`. Relay the
pass/fail table (compile-root / deposit / withdraw — **no accounting row**). Integration is complete
when Stage 4 passes.

**Governance follow-up (out of pipeline):** any new base-token pricing the Safe needs is set with
`/craft_txs_for_X` (`setFeedRoute`), and operators/roots are managed on the module — makina-x has no
schedule/execute timelock.

---

## Error Handling
Same as `/integrate`: on failure set `status: failed`, record `error`, and leave a `comment` with
what was attempted, partial progress, suspected fix, and any tx hashes / fork id.

| Stage | Common Issues | Debug |
|-------|---------------|-------|
| 1/1b | Unverified contract, missing ABI | pools_db, Etherscan/Sourcify, Tenderly decompiler |
| 2 | Reverts, wrong args | debug the tx, check allowances/signatures, confirm calls run as the Safe |
| 3 | Invalid YAML, transpiler rejects | run the `--lite` transpiler `check`; compare to `blueprints-x/aave-horizon` |
| 4 | Root mismatch, revert | `InvalidInstructionProof` → recompile; `UnauthorizedCaller` → operator; WALLED → needs `--feeds` |

## Committing & PR Hygiene
Only when the user asks to commit / open a PR:
1. **Run `dprint fmt` BEFORE committing** (CI `formatting` gate reflows markdown tables + YAML; `.claude`, `CLAUDE.md`, `protocol_specs` are excluded).
2. Never `git add -A`; stage explicitly (`git add scripts-factory/... machines/... blueprints-x/...`). Never commit `.mcp.json` or `.claude/worktrees/`.
3. Use the repo's commit/PR trailer convention.

## Final Output
Report: specs location, execution reports, blueprints-x + instruction paths, and the `/test_e2e_x`
result (deposit/withdraw, no accounting).
