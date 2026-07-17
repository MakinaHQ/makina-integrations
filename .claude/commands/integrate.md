---
description: End-to-end DeFi pool integration - specs, execution testing, and blueprint writing
argument-hint: [--resume] [--context "..."] <pool-identifier>
---

# Pool Integration

Parse `$ARGUMENTS`:
- `--resume`: Resume from existing progress.yaml (skip Stage 0)
- `--context "..."`: Optional plain English hints about the pool (e.g., "uses non-standard reward claiming via external contract", "similar to Compound v2 architecture"). Stored in progress.yaml and passed to all agents as advisory context.
- Remaining: **pool identifier** (dialectic ID, address, or pool name)

---

## Environment Prerequisites (verify BEFORE Stage 0)

The orchestrator MUST confirm these once at the start of every run. Missing tooling here is the single largest time-sink; do not leave discovery to sub-agents.

### Transpiler binary
- The transpiler is a **separately-installed cargo binary, NOT on `$PATH`** and NOT part of the local `makina-rs` checkout. On this machine it lives at:
  `/Users/augustin/.cargo/git/checkouts/transpiler-11f55d1751042103/9471437/target/debug/transpiler` (rev `9471437`).
- The `makina-rs` checkout's `calldata` crate is an HTTP API server, NOT the transpiler — do not use it. (Its `abu` branch lacks the transpiler crate entirely.)
- `TRANSPILER_PATH` must be set in **this (config) repo's** `.claude/settings.local.json`, not only in the rootfiles repo. Verify: `test -x "$TRANSPILER_PATH" && echo OK || echo "SET TRANSPILER_PATH"`
- CLI: `transpiler --help` -> subcommands `transpile | check | root`; flags `-i/--input-file`, `-o/--output-file`, `-t/--token-list`, `--helpers`.

### Token list is mandatory for check/transpile
Instructions reference `${token_list.*}`, so `check` and `transpile` **fail without `--token-list`**. Canonical invocation:

    "$TRANSPILER_PATH" --input-file machines/<machine>/<network>/caliber.yaml \
      --token-list token-lists/prod-token-list.json [-o out.toml] check   # or: transpile

### Fork tooling (for Stage 2 and Stage 4)
- Confirm foundry: `anvil --version && forge --version`.
- Confirm an RPC: `echo "$MAINNET_RPC_URL"` (set in `.claude/settings.local.json`).
- Both a Tenderly testnet and a local anvil fork are valid backends — see "Fork backend & fallback" in Stage 2.

---

## Required Artifacts Checklist

**CRITICAL**: Each stage MUST generate specific files. Do NOT mark a stage complete until all required artifacts exist.

| Stage | Required Files | Description |
|-------|---------------|-------------|
| 1_specs | `specs.yaml`, `SUMMARY.md` | Pool specifications and human-readable summary |
| 1b_enrich | `functions.md` | Solidity code for key functions |
| 1c_offchain | `API.md`, `METATYPES.md` | API documentation and metatype definitions (if offchain data needed) |
| 2_{action} | `execution-{action}.md` | Execution test report for each action |
| 3_blueprint | Blueprint + instruction files | YAML files in blueprints/ and machines/ |
| 4_test | `test-report.md` | E2E test results |

### File Structure

A complete integration should produce:

```
scripts-factory/{protocol}/{chain}/{pool_id}/
├── progress.yaml          # Pipeline checkpoint state
├── specs.yaml             # Pool specifications (Stage 1)
├── SUMMARY.md             # Human-readable summary (Stage 1)
├── functions.md           # Solidity function code (Stage 1b)
├── API.md                 # API documentation (Stage 1c, if offchain)
├── METATYPES.md           # Metatype definitions (Stage 1c, if offchain)
├── execution-deposit.md   # Deposit test report (Stage 2)
├── execution-withdraw.md  # Withdraw test report (Stage 2)
├── execution-account.md   # Account test report (Stage 2)
├── execution-harvest.md   # Harvest test report (Stage 2, if applicable)
└── test-report.md         # E2E test results (Stage 4)
```

### Artifact Validation

Before marking ANY stage complete:
1. **Verify all required files exist** in the working directory
2. **Update progress.yaml** with artifact list under the stage
3. **Do NOT proceed** to next stage until artifacts are confirmed

Example progress.yaml entry with artifacts:
```yaml
stages:
  1_specs:
    status: completed
    timestamp: "2026-01-12T00:00:00Z"
    artifacts:
      - specs.yaml
      - SUMMARY.md
```

---

## Stage 0: Intent Specification (MANDATORY)

**CRITICAL**: This stage MUST be completed first. Do NOT proceed to any other stage until all parameters are collected and confirmed.

### 0a. Fetch Pool Context

First, silently fetch pool information using `mcp__pools_db__get_pool_context` to understand:
- Protocol name
- Chain
- Available actions
- Pool display name
- **Pool tokens** (addresses, symbols, decimals) - needed for base token selection in 0b

### 0b. Ask User for All Parameters

Use a SINGLE `AskUserQuestion` call with multiple questions to collect:

```
Question 1: "Which machine should this pool be integrated for?"
Header: "Machine"
Options:
  - mteth: Multi-token ETH fund
  - dusd: USD stablecoin fund
  - deth: ETH fund
  - dbit: BIT fund
multiSelect: false

Question 2: "Which actions should be tested? (select all that apply)"
Header: "Actions"
Options:
  - deposit: Add liquidity to the pool (Recommended)
  - withdraw: Remove liquidity from the pool (Recommended)
  - account: Query position value/balance (Recommended)
  - harvest: Claim rewards (if applicable)
multiSelect: true

Question 3: "Which base tokens should be supported? (select all that apply)"
Header: "Tokens"
Options:
  - <token_symbol_a>: <token_name_a> (dynamically from pool context)
  - <token_symbol_b>: <token_name_b> (dynamically from pool context)
  - ... (for pools with more tokens)
multiSelect: true
Note: Options are generated dynamically from pool tokens fetched in 0a.
      Base tokens define what the user starts with, determining the flow type
      (all tokens = balanced, single token = single-sided).
```

### 0c. Create Progress File

After user responds, create `scripts-factory/{protocol}/{chain}/{pool_id}/progress.yaml`:

```yaml
# Intent - set at Stage 0, immutable
intent:
  pool_id: "{dialectic_id}"
  pool_name: "{pool_display_name}"
  protocol: "{protocol}"
  chain: "{chain}"
  machine: "{machine}"           # from user selection
  actions: [deposit, withdraw, account]  # from user selection
  base_tokens:                   # from user selection (variable length)
    - address: "0x..."
      symbol: "..."
      decimals: N
      index: N
    # ... one entry per selected token
  context: "{context}"           # from --context flag (optional, null if not provided)
  accounting_model: base_token   # or: position (decided in 0e)

# Progress tracking
current_stage: 1
stages:
  0_intent: {status: completed, timestamp: "..."}
  1_specs: {status: pending}
  1b_enrich: {status: pending}
  1c_offchain: {status: pending}  # conditional - skip if no offchain patterns
  2_deposit: {status: pending}   # only if in actions
  2_withdraw: {status: pending}  # only if in actions
  2_account: {status: pending}   # only if in actions
  3_blueprint: {status: pending}
  4_test: {status: pending}

# Shared resources (optional, populated as stages run)
testnets: {}
```

### Stage Status Values

| Status | Description |
|--------|-------------|
| `pending` | Not started |
| `in_progress` | Currently running |
| `completed` | Finished successfully |
| `failed` | Failed with error |

### Stage Schema (when failed)

```yaml
stages:
  2_deposit:
    status: failed
    error: "Transaction reverted: ERC20 insufficient allowance"
    comment: |
      The pool requires approval to a different spender than expected.
      Found router contract at 0x1234... that should be used instead.
      See execution-deposit.md for partial progress.
    testnet_id: "abc123-def456"
    attempts: 2
    last_attempt: "2026-01-06T15:30:00Z"
```

The `comment` field allows agents to leave context for:
- Partial progress made before failure
- Suggestions for fixing the issue
- Alternative approaches discovered
- References to relevant files or transactions

### 0d. Confirm Before Proceeding

Display summary to user:
```
Integration Setup:
  Pool: {pool_name} ({protocol})
  Chain: {chain}
  Machine: {machine}
  Actions: {actions}
  Base tokens: {base_token_symbols}
  Context: {context or "none"}

Progress file: scripts-factory/{protocol}/{chain}/{pool_id}/progress.yaml
```

### 0e. Accounting Model Decision (go/no-go — decide NOW, not at Stage 3)

The most expensive rework is choosing the wrong accounting archetype late. Decide it up front from the pool tokens fetched in 0a and record it in `intent.accounting_model`.

Two archetypes:
- **POSITION model** — the held receipt token is NOT a base token. `position_tokens + accounting = active (convertToAssets/previewRedeem) + pending`. Only the underlying/denomination needs an oracle feed; `affected_tokens` on deposit/withdraw are the base tokens moved.
- **BASE-TOKEN model** (use when the held token itself is/should be a registered base token — e.g. sUSN, VBILL, reUSD, mGLOBAL, EtherFi) — the held token gets its OWN oracle feed via `addBaseToken`, and accounting is **PENDING-ONLY** (0 when idle) so the held value is not double-counted. `affected_tokens`: deposit `[]` (synthetic swap between base tokens), async request `[base token burned/leaving]`, claim `[base token arriving]`, account `[denomination]`. For an async cooldown, still KV-track a pending term so NAV stays continuous across request->claim.

Hard rule: **every `affected_tokens` entry of a management instruction MUST be a registered base token** or the caliber reverts `InvalidAffectedToken`; `_checkPositionMinDelta` bounds the signed per-leg value change.

Precedents to copy: `blueprints/re` (reUSD), `blueprints/midas` (mGLOBAL), `blueprints/securitize` (VBILL), `blueprints/etherfi` (async redemption).

If BASE-TOKEN model: base-token + oracle registration (feed route registered BEFORE `addBaseToken`) is a prerequisite of Stage 4 — flag it in `intent.context` and follow the caliber-token-setup skill, verifying every signature against DEPLOYED bytecode (see Stage 4).

Add to the `intent:` block in 0c:

    accounting_model: base_token   # or: position

Then proceed to Stage 1.

---

## Resume Mode (`--resume`)

If `--resume` flag is present:
1. Find the progress.yaml file for the given pool
2. Read intent from `intent:` section
3. Check for failed stages - display error and comment to user
4. Skip to first non-completed or failed stage
5. Do NOT ask for parameters again

### Resuming Failed Stages

When resuming a failed stage:
1. Display the previous error and comment to the user
2. Ask if they want to retry or skip
3. If retrying, increment `attempts` counter
4. Clear error/comment fields on success

---

## Using Context

When `intent.context` is set (not null), include it in agent prompts as:

```
User-provided hints (advisory, verify against on-chain behavior):
{context}
```

Agents should treat this as supplementary guidance - useful for directing attention to specific patterns or mechanisms, but always verify against actual on-chain data. Context hints don't override discovered behavior.

---

## Stage 1: Generate Specs

**Agent**: `pool-specs-generator`

**Required Artifacts:**
- `specs.yaml` - Pool specifications with contracts, flows, and parameters
- `SUMMARY.md` - Human-readable summary of the pool

```
Generate specs for pool: {pool_identifier}
Output directory: scripts-factory/{protocol}/{chain}/{pool_id}/
```

If `intent.context` is set, include it in the agent prompt.

**On completion**:
1. Verify `specs.yaml` and `SUMMARY.md` exist
2. Update progress.yaml with artifacts list
3. Set `stages.1_specs.status: completed`

---

## Stage 1b: Enrich Specs with Function Code

**Agent**: `specs-enricher`

**Required Artifacts:**
- `functions.md` - Solidity code for key contract functions

```
Fetch Solidity code for non-standard functions in specs.
Input: scripts-factory/{protocol}/{chain}/{pool_id}/specs.yaml
Output: scripts-factory/{protocol}/{chain}/{pool_id}/functions.md
```

This creates a reference file with actual function implementations, helping execution-explorer understand:
- Library delegation patterns (e.g., `swapStorage.addLiquidity()`)
- Key modifiers (`nonReentrant`, `deadlineCheck`, etc.)
- Internal validation logic

**On completion**:
1. Verify `functions.md` exists
2. Update progress.yaml with artifacts list
3. Set `stages.1b_enrich.status: completed`

---

## Stage 1c: Analyze Offchain Requirements (conditional but CRITICAL)

**Agent**: `offchain-analyzer`

### When to Run This Stage

**MUST RUN if ANY of these conditions are true:**
1. `--context` mentions: API, merkle proof, signature, offchain, external data, claim endpoint
2. The action is `harvest` (reward claiming almost always requires offchain merkle proofs)
3. specs.yaml contains `offchain_indicators` in any flow
4. The blueprint will need a custom `input_slots` type (e.g., `FluidClaimData`, `KingClaimData`)

**Skip ONLY if**: None of the above conditions apply AND the integration uses only standard on-chain data

### Why This Stage is Critical

**DO NOT SKIP this stage just because you can manually fetch data during testing.** The purpose is NOT just to test - it's to document:
- How production systems (makina-rs) should fetch the data
- The exact API endpoints, response parsing, and data transformations
- The Rust type specifications for the custom `input_slots` metatype

**If you create a blueprint with `input_slots` referencing a custom type (e.g., `type: "FluidClaimData"`), this stage MUST be completed** to document how that type gets populated at runtime.

### Stage Execution

**Required Artifacts:**
- `API.md` - API endpoint documentation with Python and Rust implementation examples
- `METATYPES.md` - Metatype definitions for the transpiler with field mappings

```
Analyze offchain data requirements.
Input: scripts-factory/{protocol}/{chain}/{pool_id}/specs.yaml
Input: scripts-factory/{protocol}/{chain}/{pool_id}/functions.md
Input: intent.context (if set - may contain API hints)
Output directory: scripts-factory/{protocol}/{chain}/{pool_id}/
```

This stage:
1. Detects offchain patterns from specs AND context hints (merkle proofs, signatures, API endpoints, etc.)
2. Researches protocol documentation for API endpoints
3. Validates findings with user
4. Generates Python fetcher code (for execution-explorer testing) → `API.md`
5. **Documents Rust specs and metatype definitions (REQUIRED for makina-rs)** → `METATYPES.md`

**On completion**:
1. Verify `API.md` and `METATYPES.md` exist
2. Update progress.yaml with artifacts list
3. Set `stages.1c_offchain.status: completed`

---

## Stage 2: Test Execution (sequential)

**Agent**: `execution-explorer`

**Required Artifacts (one per action):**
- `execution-deposit.md` - Deposit test report with transaction details
- `execution-account.md` - Account query test report
- `execution-withdraw.md` - Withdraw test report with transaction details
- `execution-harvest.md` - Harvest test report (if applicable)

If `intent.context` is set, include it in each action's agent prompt. Context hints are especially valuable here for understanding non-standard patterns.

Run actions **sequentially** in logical order on a **shared testnet**:

```
deposit → account → withdraw → harvest (if applicable)
```

| Order | Action | Description | Required Output |
|-------|--------|-------------|-----------------|
| 1 | deposit | Add liquidity to create position | `execution-deposit.md` |
| 2 | account | Query position value/balance | `execution-account.md` |
| 3 | withdraw | Remove liquidity from position | `execution-withdraw.md` |
| 4 | harvest | Claim rewards (if applicable) | `execution-harvest.md` |

**Why sequential?** Each action depends on previous state:
- Cannot withdraw without first depositing
- Cannot account for a position that doesn't exist
- Cannot harvest rewards without an active position

**Testnet sharing**: Create one testnet at stage start, pass `testnet_id` and `rpc_url` to each agent.

**Fork backend & fallback**: The Tenderly MCP connector is the default fork, but its access token can EXPIRE mid-session and block every fork tool call. When Tenderly is unavailable, fall back to a **local anvil fork** (foundry is installed, no connector required):

    anvil --fork-url "$MAINNET_RPC_URL"        # serves http://127.0.0.1:8545

anvil supports the cheatcodes these flows need: `anvil_impersonateAccount`, `anvil_setBalance`, `evm_increaseTime`, and contract deploys via `forge create`. Treat anvil as a first-class fork option, not a last resort — if Tenderly errors on auth, switch immediately rather than retrying the connector.

**Base token handling**: The `intent.base_tokens` define what tokens the user starts with. This determines the flow type:
- **All pool tokens** → balanced flows (user has both/all tokens)
- **Single token** → single-sided flows (user only has that token)

**On completion** (for each action):
1. Verify `execution-{action}.md` exists with complete test report
2. Update progress.yaml with artifacts list
3. Set `stages.2_{action}.status: completed`

---

## Stage 3: Write Blueprint

**Agent**: `blueprint-writer`

```
Convert execution flows to blueprint/instruction files.
Machine: {machine} (from intent.machine)
Source: scripts-factory/{protocol}/{chain}/{pool_id}/
Output: machines/{machine}/{network}/instructions/{protocol}-{pool}.yaml
```

**Base token handling**: Use `intent.base_tokens` to generate the appropriate instruction:
- The `affected_tokens` field should contain the base token address(es)
- Use the matching blueprint variant (balanced vs single-sided) based on the execution flow
- Read `intent.accounting_model` (set in Stage 0e) and select the archetype accordingly: POSITION -> `affected_tokens` = base tokens moved, value via convertToAssets/previewRedeem; BASE-TOKEN -> held token is a registered base token, accounting is pending-only, `affected_tokens` per the 0e matrix (deposit `[]`, request `[burned]`, claim `[arriving]`, account `[denomination]`).

**On completion**: Update progress.yaml `stages.3_blueprint.status: completed`

---

## Stage 4: Test Blueprint

**Agent**: `blueprint-tester`

Invoke with:
- **instruction_path**: `machines/{machine}/{network}/instructions/{protocol}-{pool}.yaml`
- **machine**: `{intent.machine}`
- **network**: `{chain}` (mainnet, arbitrum, etc.)
- **working_dir**: `scripts-factory/{protocol}/{chain}/{pool_id}/`

```
Test instruction file end-to-end on Tenderly.
Verify compilation, root update, and execution.
Write test report to {working_dir}/test-report.md
```

### Runtime expectations & how to run the tester (READ before launching)
- A cold `cargo build` of spellcaster plus fork spin-up is genuinely **20-40 minutes**. Set this expectation with the user; a long-running build is not 'stuck'.
- **Do NOT poll a background sub-agent.** Background agents only get compute while the main loop is idle — repeated status checks starve them and make them look hung. Prefer running the tester **synchronously**, or launch-and-yield and wait for its own completion signal. For hard e2e, consider driving the fork hands-on (see the `makina-cli` skill) instead of a background agent.

### Cross-repo machines-path plumbing (calibers that live only in the config repo)
Some calibers (e.g. `intMkSrRoyUSDC`) exist ONLY in this config repo, not in the rootfiles repo. spellcaster is invoked from rootfiles as:

    cargo run -p spellcaster -- --machines-path <rootfiles>/machines-local.toml --dev

so the config-repo caliber must be wired into a `machines-local.toml` / `config-local.toml` that points back at this repo's `machines/<machine>/<network>/`. Confirm this wiring exists before Stage 4 or the tester cannot find the caliber. (`machines*.toml` and `*local*` are gitignored, so these files stay local.)

**On completion**: Update progress.yaml `stages.4_test.status: completed`

**Integration complete when Stage 4 passes.**

---

## Error Handling

When a stage fails:

1. **Set status to `failed`** in progress.yaml
2. **Record the error message** in the `error` field
3. **Leave a comment** explaining:
   - What was attempted
   - Partial progress made
   - Potential fixes or workarounds
   - Any relevant transaction hashes or testnet IDs

### Stage-Specific Guidance

| Stage | Common Issues | Debug Approach |
|-------|---------------|----------------|
| 1 | Invalid pool ID, missing ABI | Check pool exists in pools_db, verify contract is verified on Etherscan |
| 1b | Contract not verified, library not found | Check Sourcify, use Tenderly decompiler, note in functions.md |
| 2 | Transaction reverts, wrong parameters | Use `tenderly:debug_tx`, check allowances, verify function signatures |
| 3 | Invalid YAML syntax, missing blueprint inputs | Run `/compile` to validate, check syntax.md |
| 4 | Caliber config mismatch, missing dependencies | Verify caliber.yaml has required config values |

### Example Failed Stage Update

```yaml
# Agent should update progress.yaml like this
stages:
  2_deposit:
    status: failed
    error: "Transaction reverted at add_liquidity()"
    comment: |
      Attempted deposit of 1000 USDC to Curve pool.
      Approval succeeded (tx: 0xabc...).
      add_liquidity failed - pool expects 3 tokens not 2.

      Suggestion: Use add_liquidity(uint256[3],uint256) instead.
      See Curve pool contract for correct interface.
    testnet_id: "tenderly-xyz"
    attempts: 1
    last_attempt: "2026-01-06T16:00:00Z"
```

## Committing & PR Hygiene

Only when the user asks to commit / open a PR:
1. **Run `dprint fmt` BEFORE committing.** CI runs a `formatting` (dprint) gate that reflows markdown tables and YAML; skipping it fails CI. Excludes are `.claude`, `CLAUDE.md`, `protocol_specs` (see `dprint.json`).
2. **Never stage secrets or local-only files.** Do NOT commit `.mcp.json` (holds a Tenderly access token) or `.claude/worktrees/` — neither is in `.gitignore`. Stage integration files explicitly (`git add scripts-factory/... machines/... blueprints/...`); never `git add -A`.
3. **Branching off main**: stash any pre-existing uncommitted edit first (e.g. a modified `test-report.md`) so the checkout is not blocked: `git stash -u && git checkout -b <branch> && git stash pop`.
4. Use the repo's commit/PR trailer convention (Co-Authored-By + Generated-with).

## Final Output

Report: specs location, execution reports, instruction file path, test status.
