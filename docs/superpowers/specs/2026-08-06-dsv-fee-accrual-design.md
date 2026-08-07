# DSV Fee Accrual Keeper Position

**Date:** 2026-08-06\
**Branch:** `feat/dsv-fee-accrual`\
**Scope:** Ethereum mainnet only, `machines/intMkSrRoyUSDC` (the DSV's own machine). No
other caliber, chain, or machine is touched.

## Goal

Make every accounting cycle of the DSV mainnet caliber call `accrueYield()` on the
Dialectic Senior Vault, so that DSV fee shares are minted on a predictable schedule
tied to the Makina accounting cycle instead of at arbitrary times.

The vehicle is a dedicated, permanently-open position whose only job is to carry that
call. It holds no assets and is valued at a constant 1 wei USDC.

## Problem

`DSV.convertToAssets` does not account for fee shares that are pending mint. Any fee
distribution triggered independently of the Makina AUM update therefore makes the DSV
share price fall relative to the previous block. For a future tranching of the DSV
itself, such a distribution would register as a loss and be absorbed by the junior
tranche even though no loss occurred.

`accrueYield()` on the DSV is permissionless, so the caliber can call it.

## Fixed integration values

| Item                       | Value                                                     |
| -------------------------- | --------------------------------------------------------- |
| DSV (srRoyUSDC) proxy      | `0xcD9f5907F92818bC06c9Ad70217f089E190d2a32`              |
| DSV implementation         | `0x1b5cd91e61505d431d2a61192a1006146bd9bb28`              |
| Fee accrual selector       | `accrueYield()` → `0x059d9c75`                            |
| DSV asset                  | USDC `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` (6 dec) |
| Machine (`intMkSrRoyUSDC`) | `0xFa097420f0e2C72456B361a1eD85172B9ccd8c38`              |
| Mainnet caliber            | `0x5476F4E23dAA093Ce6700e1026013c55F7AF9083`              |
| DSV address home           | `constants.dsv_vault_address` in the blueprint            |
| Position ID                | `1`                                                       |
| Group ID                   | `0`                                                       |
| Position value             | 1 wei USDC, constant                                      |

Verified on-chain 2026-08-06:

- `accrueYield()` does not revert when simulated from a random EOA → permissionless,
  no role or allowlist needed for the caliber.
- The DSV's sole strategy holds the machine: `getTotalAllocated()` =
  `13011741178763` against `machine.lastTotalAum()` = `13011741178764`.
- Fees are already live: `performanceFee()` returns
  `(0xd6f9b6cdf8deb1b16e22b830166ad793fd9a0f9c, 1000)` — a 10% performance fee.
  `managementFee()` returns `(0x0, 0, <lastAccrual>)`, so the management fee is 0.
  `previewAccrueYield()` reports no delta only because there is no unrealized yield at
  rest, not because fees are unconfigured.

USDC is already the caliber's accounting token, so no token-list, base-token, or
Oracle Registry mutation is needed.

## Architecture

### Why a position at all

The requirement is "run on every accounting cycle". Only `ACCOUNTING` instructions run
then, and an `ACCOUNTING` instruction only runs if it belongs to a registered position.
`Caliber.accountForPosition` reverts `PositionDoesNotExist` (`Caliber.sol:331`) for an
unregistered position, and `_accountForPosition` removes a position whose accounting
returns 0 (`Caliber.sol:760`). So the position must exist and must value to something
non-zero, forever. 1 wei USDC is the smallest such value.

`ACCOUNTING` instructions execute through `_execute` → `delegatecall` into the weiroll
VM (`Caliber.sol:976`), not a staticcall, so state-mutating calls are permitted. This is
already relied on in production: eight Royco accounting blueprints call
`kernel.syncTrancheAccounting()`.

### Why no KV store flag

An earlier draft flipped a KV entry 0 → 1 in the management instruction so the accounting
could return 0 before the position was opened and 1 after. That is unnecessary.

`_managePosition` (`Caliber.sol:643`) runs the accounting instruction **twice** — once at
line 663, _before_ `_execute(mgmtInstruction)`, and once at line 681, after. On the
bootstrap call the pre-accounting hop sees `lastValue = 0, currentValue = 1`, enters the
`currentValue > 0` branch at line 771 with `lastValue == 0`, and performs
`_positionIds.add(posId)` + `PositionCreated`. The position is created by that hop.

The post-accounting hop then returns `change = 1 - 1 = 0`, and every downstream guard is
gated on `change != 0` (lines 708 and 713), so `_checkPositionMinDelta` and
`_checkPositionMaxDelta` never execute. `recoveryMode` at line 697 is gated on
`isPositionIncrease = change > 0`, which is false. Nothing is tripped.

Dropping the KV removes a storage key, a per-cycle `get` call, a per-open `set` call, and
a dependency on the caliber's KV authorization.

### Decommissioning

Closing the position via `managePosition` is impossible in either design and this is
accepted, not overlooked. A transition to value 0 gives `change = -1` with no base-token
inflow, so line 713 (`change != 0 && isDebt == isPositionIncrease`, i.e.
`false == false`) is true and `_checkPositionMaxDelta(1, 0, 500)` computes
`maxChange = 0` and reverts `MaxValueLossExceeded`.

Decommissioning therefore requires shipping a second `ACCOUNTING` action that returns a
literal 0 and calling it through `accountForPosition`, which applies no delta checks.
**That action is deliberately not shipped now.** No instruction file in this repo carries
two `ACCOUNTING` entries, and a second one would likely make the accounting bot close the
position on every cycle. It is a one-rootfile change if and when the position is retired.

## Files

### `blueprints/royco/dsv/accrue-yield.yaml` (new)

`protocol: "royco-dsv"`, matching the `royco-st-dmg` / `royco-jt-dmg` convention for
`blueprints/royco/<pool>/`. Both actions live in this one file — they are two calls
between them.

No inputs. The DSV address is a blueprint `constant`, since this blueprint is specific to
one named contract and there is no second instance to parameterise for. That keeps the
instruction at `inputs: {}` and needs no caliber config entry.

- **`open_position`** (MANAGEMENT) — one call, `accrueYield()` on the vault. This is a
  bootstrap ritual: its on-chain effect is nil for the caliber's balance sheet, and the
  position is actually created by the pre-accounting hop described above. It calls
  `accrueYield()` rather than being empty because no blueprint in the repo ships a
  MANAGEMENT action with `calls: []`, and an empty weiroll command array through
  `_execute` is untested here. It doubles as a manual accrual trigger for the operator.
- **`account`** (ACCOUNTING) — one call, `accrueYield()` on the vault, then:

  ```yaml
  reserved_slots:
    - { type: "uint256", value: "${builtins.UINT256_1}" } # 1 wei USDC
    - { type: "uint256", value: "${builtins.UINT256_MAX}" } # ACCOUNTING_OUTPUT_STATE_END
  ```

Reserved slots occupy state indices `0..n-1`: `transpile_reserved_slots` feeds
`planner.plan(reserved_slots)`, and `transpile_input_slots` offsets input slot indices by
`action.reserved_slots.len()`. `_decodeAccountingOutputState` reads from index 0 until the
terminator (`Caliber.sol:804`), so it decodes `amounts = [1]`. `1` is not the terminator,
which is `bytes32(type(uint256).max)` (`Caliber.sol:37`).

The `1` is a `Scalar` reserved slot, so the transpiler pushes it into `checked_slots`, it
enters the state bitmap, and it is hashed into the merkle leaf by
`_checkInstructionIsAllowed` (`Caliber.sol:881`). The operator cannot substitute a
different value at call time.

### `machines/intMkSrRoyUSDC/mainnet/instructions/dsv-fee-accrual.yaml` (new)

Machine-local, alongside `merkl.yaml`, not a generic `instructions/` template. No position
`vars` and `inputs: {}` on both entries; USDC is written inline.

Blueprint paths are `../../../blueprints/royco/dsv/accrue-yield.yaml:<action>` — three
levels, resolved relative to the **caliber** directory rather than the instruction file,
because `!include` inlines the instruction into `caliber.yaml`. This matches
`merkl.yaml:6`.

| Entry | `instruction_type` | `is_debt` | `affected_tokens` | Action          |
| ----- | ------------------ | --------- | ----------------- | --------------- |
| 1     | `MANAGEMENT`       | `false`   | `[]`              | `open_position` |
| 2     | `ACCOUNTING`       | `false`   | `[USDC]`          | `account`       |

`affected_tokens: []` on the MANAGEMENT entry sets `atLen = 0`, so
`affectedTokensValueBefore == affectedTokensValueAfter == 0`. This is an established
shape for flag-flip management instructions (`instructions/3jane-susd3.yaml:71`).

The ACCOUNTING entry's `affected_tokens` must have exactly one element to match
`amounts.length` (`Caliber.sol:748`), and it must be a base token (`Caliber.sol:753`).
USDC is the accounting token, so `_accountingValueOf(USDC, 1)` returns `1` directly at
line 851 with no oracle hop.

Label `"DSV Fee Accrual"` — unique for the `(protocol, type, label)` triple under
`royco-dsv`.

### `machines/intMkSrRoyUSDC/mainnet/caliber.yaml` (modified)

No config entry — the DSV address is a blueprint constant, which also keeps CLAUDE.md's
"protocol-specific addresses stay out of caliber config" rule intact. One position
appended in its own section:

```yaml
# ── DSV Fee Accrual Keeper (group_id: 0) ─────────────────────────
- id: "1"
  group_id: "0"
  description: "DSV Fee Accrual Keeper (srRoyUSDC)"
  instructions: !include "./instructions/dsv-fee-accrual.yaml"
```

No `position_tokens` (it holds none, and a non-empty list would register phantom position
tokens at line 779). No `vars`.

`group_id: 0` keeps the position ungrouped so plain `accountForPosition` works — line 333
rejects a grouped position whose group has more than one member.

Position ID `1` is unused in this caliber and is the smallest legal value;
`_managePosition` rejects `0` at line 650. Ordering within `positions:` is cosmetic — see
"This is not atomic with the AUM update" below for why placement cannot affect when the
accrual lands.

## Consequences and accepted risks

### This is not atomic with the AUM update

`DSV.totalAssets()` moves only when `machine.updateTotalAum()` runs; it does not move
while caliber positions are being accounted. So `accrueYield()` fired from caliber
accounting always accrues against the **previous** AUM update, and where this position
sits in `caliber.yaml` or in an `accountForPositionBatch` array makes no difference.

What is delivered is "once per cycle, immediately before the AUM update" rather than
atomicity. The per-cycle share-price dip is not eliminated; it is moved to a predictable
point and narrowed to the gap between the accounting transaction and the
`updateTotalAum` transaction.

The dip closes entirely only if the operator bundles `accountForPositionBatch` and
`updateTotalAum` into a single transaction, which is the wrapper-contract option. That is
out of scope here and is recorded as the natural follow-up.

### Liveness coupling

`positionStaleThreshold` on this caliber is `10800` (3h). If `accrueYield()` ever
reverts, this position goes stale within 3h, `getDetailedAum()` reverts
`PositionAccountingStale` (`Caliber.sol:275`), and machine AUM updates halt — which in
turn freezes the DSV, whose price reads the machine.

There is no try/catch primitive in the weiroll helper set, so this cannot be guarded
inside the blueprint. Recovery is an instruction-root update through the risk manager.
This is the price of the design and is accepted.

### Cost

`accrueYield()` executes three times in the bootstrap `managePosition` transaction
(pre-accounting, management, post-accounting; the second and third are no-ops), then once
per accounting cycle. AUM is inflated by a permanent 1 wei USDC, i.e. $1e-6.

## Test plan

Local, before any chain work:

1. `/compile` the instruction file; confirm the two actions transpile and the reserved
   slots land at state indices 0 and 1.
2. Confirm `scripts/compute_affected_calibers.py` picks up the new machine-local
   instruction (it is under `machines/`, so the existing per-caliber path logic applies;
   no `GLOBAL_PREFIXES` change is needed because the blueprint lives under `blueprints/`,
   which is already covered).

### DSV side — DONE 2026-08-06

Executed on Tenderly virtual testnet `dsv-fee-accrual-20260806` (project `script-factory`),
forked from mainnet block 25698004. No transpiler needed for any of this.

- **`accrueYield()` succeeds as a real transaction sent from the caliber address**
  (`0x5476F4E2…9083`), status `0x1`, 79,705 gas idle / 101,743 gas when it mints.
- **No re-entry into the caliber.** `debug_traceTransaction` callTracer shows the whole
  tree as `DSV → adapter 0xc5FeF644… → shareToken.balanceOf → machine.convertToAssets
  → shareToken.totalSupply`, every hop after the first a `STATICCALL`. `nonReentrant`
  on `accountForPosition` is therefore not at risk.
- **The adapter reads `machine.convertToAssets` (`0x07a2d13a`)**, i.e. `lastTotalAum`.
  This is direct confirmation that the DSV cannot see value that `updateTotalAum()` has
  not yet published, which is the basis of the non-atomicity consequence below.
- **Fee minting works and is correctly sized.** Injecting +1,000,000 USDC into
  `Machine._lastTotalAum` (slot `0x55fe…bd906`, struct field 6) and calling
  `accrueYield()` from the caliber moved totalSupply 12,720,786.694465 →
  12,812,185.060379, matching `previewAccrueYield()` to the wei. The 91,398.365914
  shares minted are worth ≈100,000 USDC at the post-accrual price — exactly the 10%
  performance fee on the injected yield. Price per share stepped 1.101972 → 1.094111
  (−0.713%), which is the dip this position exists to schedule.

Note: donating USDC directly to the DSV does **not** move `totalAssets` — the vault
tracks idle internally rather than reading its own balance, so yield must be simulated
through the machine.

### Caliber side — DONE 2026-08-06

Executed on Tenderly vnet `dsv-fee-accrual-caliber-e2e`
(`5c534c6b-0bbe-4e2b-872e-9ed2688081f4`) against rootfile `E2E-TEST.toml`
(root `0x6f4c512cd6f0b72d44602044234306140515bc102ef883341aff38ab87840490`),
driven through spellcaster.

These results were produced when the DSV address was a blueprint _input_ bound through a
caliber config key. It was since moved to a blueprint _constant_. Both resolve to the same
address literal at transpile time, so `commands`, `state`, `bitmap` and every other leaf
field are expected to be byte-identical and the root should still be
`0x6f4c512c…840490`. **Confirm that on the next transpile**; if the root changes, the run
below must be repeated.

1. **Transpiled output matches the design.** ACCOUNTING carries
   `state = [0x…01, 0xff…ff]` at indices 0/1 with `bitmap = 0xC0000000…` (both slots
   hash-committed, so the 1 wei cannot be substituted at call time). MANAGEMENT carries
   `state = []`, `bitmap = 0`. Both are one CALL to the DSV with the return discarded.
2. **Negative check passes.** `accountForPosition(1)` before any `managePosition` reverts
   `PositionDoesNotExist()` (`0xf7b3b391`). The bootstrap is genuinely required.
3. **Bootstrap works exactly as traced.** `managePosition(open_position, account)`
   returned `(1, 0)` — value 1 wei, `change == 0` — confirming the position is created by
   the pre-accounting hop and that both delta guards are skipped. Position count 10 → 11,
   `getPosition(1)` = `(lastAccountingTime, 1, false)`, displayed as `0.000001 USDC`.
4. **The accrual fires on every accounting cycle.** Across three successive
   `account-positions` transactions the DSV's `lastFeeAccrual` advanced each time
   (`0x6a7484d7` → `0x6a74e87a` → `0x6a74e8c7` → `0x6a74e947` → …), and position 1 held
   at exactly 1 wei throughout.
5. **Fee shares mint inside the caliber's own accounting transaction.** With +1,000,000
   USDC of machine AUM injected, one `account-positions` tx moved DSV totalSupply
   12,720,786.694465 → 12,812,185.060379 and price/share 1.101972 → 1.094111. The
   91,398.365914 shares minted are ≈100,000 USDC, exactly the 10% performance fee.
6. **The hub caliber still aggregates correctly.** `getDetailedAum()` succeeds with
   position 1 registered, returning 11 positions including position 1 at value 1.

Not verified, for an environment reason unrelated to this change:
`machine.updateTotalAum()` reverts `CaliberAccountingStale(42161)` — the **Arbitrum
spoke** caliber has no fresh Wormhole CCQ data on a mainnet fork. The hub-side
precondition that this change could have broken (`getDetailedAum()`) is verified above.

Two incidental observations worth following up independently of this work:

- The caliber's live instruction root on mainnet (`0xa2b0d205…`) matches **no** committed
  rootfile, so production is ahead of this repo.
- `machine.getSpokeChainIds()` reports 2 spokes including Arbitrum (42161), but
  `machines/intMkSrRoyUSDC/config.toml` wires only `mainnet` and `base`.

### Caliber side — original plan (superseded by the results above)

Requires the transpiler, which the user runs. On a **fresh** vnet (the one above has
mutated AUM and three accruals against it):

3. Set the instruction root for the new rootfile via the risk-manager timelock
   (`0x7c405bbD131e42af506d14e752f2e59B19D49997`, which also happens to be `DSV.owner()`).
4. Negative check, and it must run **before** step 5 because the bootstrap is not
   reversible on the fork: confirm `accountForPosition` on position 1 reverts
   `PositionDoesNotExist`, establishing that the bootstrap call is genuinely required.
5. `managePosition` with (`open_position`, `account`). Assert `PositionCreated(1, 1)`,
   position value 1, and `change == 0` on the returned tuple.
6. `accountForPosition` on position 1. Assert it succeeds and value stays 1.
7. Assert `machine.updateTotalAum()` still succeeds with position 1 registered. Note
   this needs all positions accounted first — `isAccountingFresh()` was observed
   `false` on mainnet itself on 2026-08-06, with all 10 positions last accounted
   11.4h earlier against a 3h threshold.

## Out of scope

- The wrapper contract that would make caliber accounting and `updateTotalAum` atomic.
- A zero-returning `ACCOUNTING` action for decommissioning.
- Any DSV-side change; `accrueYield()` is used exactly as deployed.
- Base caliber, and every other machine.
