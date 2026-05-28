# Execution Report — Royco JT Pareto FalconX (withdraw, DUSD machine)

## Fork

| Key                       | Value                                                                                      |
| ------------------------- | ------------------------------------------------------------------------------------------ |
| `vnet_id`                 | `b0f9ddf1-1525-4bd6-9359-90dcf602ab12`                                                     |
| `rpc_url` (admin)         | `https://virtual.mainnet.eu.rpc.tenderly.co/aca6b043-1c2a-4efa-9f9e-a5c15d84fe93`          |
| Fork chain                | Ethereum mainnet (chain_id 1)                                                              |
| Reverted from             | post-account snapshot `0x259d550498f35c0f19d09664b5fcfb13557cf05f4a4bf8f6aac17f2a01afe224` |
| Post-stopEpoch-1 snapshot | `0x58cc150749916878305dc9ecc9d15ab7dce8762247fa359bbd40293ec339bab7`                       |
| Caliber under test        | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (DUSD mainnet caliber)                        |

Action: **withdraw (two-phase queued, JT)**. Mirrors the ST sibling
(`scripts-factory/royco-st-pareto-falconx/execution-withdraw.md`) with one
material divergence: the coverage gate is on `JT.redeem` (instead of
`ST.deposit`). On this fork the ST tranche is empty
(`ST.totalSupply == 0` and stays empty across the whole flow), so
`JT.maxRedeem(caliber)` returns `uint256.max` and a 50% redeem is well
within the coverage envelope.

Caliber pre-state at the post-account snapshot:

| Read                             | Value (raw)                                         | Decoded                                                                   |
| -------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------- |
| `JT.balanceOf(caliber)`          | `0xa8e90afcd4b596757ef`                             | `49,853,528,264,549,100,640,239` (49,853.5283 JT shares — 100% of supply) |
| `JT.totalSupply()`               | `0xa8e90afcd4b596757ef`                             | identical (caliber owns it all)                                           |
| `JT.totalAssets()`               | `(0, 0x9c184d5783c5bccbaf6, 0xa8e90afcd4b596757ef)` | `(0, 46,071.0916 AA, 49,853.5283 USD-WAD)`                                |
| `AA.balanceOf(caliber)`          | `0x0`                                               | 0                                                                         |
| `FalconXUSDC.balanceOf(caliber)` | `0x0`                                               | 0                                                                         |
| `USDC.balanceOf(caliber)`        | `0x0`                                               | 0                                                                         |
| `tranchePrice(AA)`               | `0x1082f4`                                          | 1,082,100 (USDC-6 per 1e18 AA)                                            |
| `isEpochRunning`                 | `1`                                                 | true                                                                      |
| `allowAAWithdrawRequest`         | `0`                                                 | false (paused mid-epoch)                                                  |
| `paused`                         | `1`                                                 | true                                                                      |
| `epochEndDate`                   | `0x6a1d521f`                                        | 1,779,480,991 (2026-05-22 21:36 UTC)                                      |
| `bufferPeriod`                   | `0x5460`                                            | 21,600 (6h)                                                               |
| `epochDuration`                  | `0x23b020`                                          | 2,339,360 (~27 days)                                                      |
| `defaulted`                      | `0`                                                 | false                                                                     |
| `IdleCreditVault.epochNumber()`  | `0x0a`                                              | 10                                                                        |
| `lastWithdrawRequest[caliber]`   | `0x0`                                               | 0 (first withdraw for caliber)                                            |
| `manager()` (strategy)           | `0x1fb0f3602f52e2420acff5cf04dbfde96378df58`        | Pareto ops EOA                                                            |
| `borrower()` (strategy)          | `0xc08f538b079be6edfb6594985e8b93784f41a2c6`        | FalconX EOA                                                               |
| `unscaledApr()` (strategy)       | `0x727de34a24f90000`                                | 8.25e18 (= 8.25%)                                                         |
| `pendingWithdraws()` (strategy)  | `0x771d414577e`                                     | 8,209,938.254206 USDC across all lenders                                  |
| `expectedEpochInterest()` (CDO)  | `0xb7e6b4d52c`                                      | 789,329.679148 USDC                                                       |
| `JT.maxRedeem(caliber)`          | `0xff…ff`                                           | `uint256.max` (no coverage limit since ST is empty)                       |

Test plan: redeem **50%** of JT shares (`shares_to_redeem =
24,926,764,132,274,550,320,119` = `0x5474857e6a5acb3abf7`) — within the
coverage envelope, and a useful stress for asymmetric position teardown.

---

## Setup: time control and impersonations

Real wall-clock at this stage: ~`1,779,563,000` (2026-05-19 19:50 UTC).
Fork auto-incrementing clock was at `1,779,218,587` after the
revert — `262,404 s` (~3 days) behind `epochEndDate=1,779,480,991`.

### Tenderly time-control quirk discovered for the JT integration

**The fork's `latest` block ts and the EVM `block.timestamp` seen by a
`send_vnet_transaction` are NOT the same value.** Empirically on this
vnet:

- `evm_increaseTime` + `mine_block` advanced the fork's head to ts
  `1,780,308,480` (= initial fork ts + 1,089,893 s).
- `tenderly_setNextBlockTimestamp(t)` correctly stamped the _next_
  block at the requested ts (verified via `eth_getBlockByNumber`).
- BUT a `send_vnet_transaction` invoking `startEpoch()` reverted with
  `NotAllowed()` at the `block.timestamp < (epochEndDate + bufferPeriod)`
  guard, even though the _block's_ recorded ts was 1,780,310,016 — well
  past `epochEndDate + bufferPeriod = 1,779,502,591`.
- A `simulate_vnet_transaction` of the same call against the same
  block produced the identical revert.

This matches the `MEMORY.md` warning that Tenderly's send/simulate paths
do not always honor warped time. The exact symptom: the EVM evidently
sees an earlier `block.timestamp` than what the API reports.

### Workaround used: storage-override `epochEndDate`

The CDO contract storage layout (recovered by exhaustive slot scan):

| Slot    | Field           | Pre-override value           | Post-override value          |
| ------- | --------------- | ---------------------------- | ---------------------------- |
| `0x11f` | `epochDuration` | `0x23b020` = 2,339,360       | unchanged                    |
| `0x122` | `epochEndDate`  | `0x6a1d521f` = 1,779,480,991 | `0x65530000` = 1,700,000,000 |
| `0x12a` | `bufferPeriod`  | `0x5460` = 21,600            | unchanged                    |

Overriding slot `0x122` to a small ts (`1,700,000,000`) makes
`block.timestamp < epochEndDate + bufferPeriod` trivially false under any
plausible `block.timestamp` value the EVM might use. This unblocked both
`startEpoch()` and the _second_ `stopEpoch()` (the first `stopEpoch()`
did not need this trick because the auto-incrementing fork-time +
`tenderly_setNextBlockTimestamp` happened to align on the first try).

The runbook for production blueprints does NOT need this override — it
is purely a Tenderly testing workaround. Live mainnet `stopEpoch` /
`startEpoch` are Pareto ops responsibilities outside the blueprint's
scope.

### Borrower and manager funded, borrower approves CDO

| Action                                               | Tool                       | Result                                                                           |
| ---------------------------------------------------- | -------------------------- | -------------------------------------------------------------------------------- |
| `set_erc20_balance(borrower, USDC, 0x1d1a94a200000)` | `tenderly_setErc20Balance` | 512,000,000 USDC (way over need)                                                 |
| `fund_account(borrower, 1 ETH)`                      | `tenderly_fund_account`    | gas                                                                              |
| `fund_account(manager, 1 ETH)`                       | `tenderly_fund_account`    | gas                                                                              |
| `USDC.approve(CDO, type(uint256).max)` from borrower | `eth_sendTransaction`      | tx `0xffdfa26c13f8d7a0082bf2328cd692931b7c5abf6c9a89f5d35271a182c33345`, success |

---

## Step W1 — First `stopEpoch(8.25e18, 0)` (close the running epoch)

| Field       | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| from        | manager `0x1fb0…df58` (impersonated)                                 |
| to          | IdleCDOEpochVariant `0x433D…be4d`                                    |
| selector    | `0xd48099ad` (`stopEpoch(uint256,uint256)`)                          |
| `_newApr`   | `0x727de34a24f90000` = 8.25e18                                       |
| `_interest` | `0` (use already-accrued `expectedEpochInterest`)                    |
| tx_hash     | `0x805054d80e43f6970e1ae987175dc1092dd276dde8d523159c92fcc8bbf069f2` |
| status      | success                                                              |

> Note: this first `stopEpoch` succeeded WITHOUT the storage override,
> but only after a preliminary failure where `tenderly_setNextBlockTimestamp`
> (0x6a1d574d) wasn't applied. Burning a block ts (via a second
> `setNextBlockTimestamp` of `0x6a1d5800` = 1,780,307,968) before the
> retry succeeded. The retry pattern: `evm_increaseTime(263000)`
>
> - `evm_mine` then `tenderly_setNextBlockTimestamp(...)`
>   immediately before each `send_vnet_transaction`.

Post-first-`stopEpoch` state:

| Read                            | Pre-value                        | Post-value  | Δ                                                     |
| ------------------------------- | -------------------------------- | ----------- | ----------------------------------------------------- |
| `isEpochRunning()`              | `true`                           | `false`     | flipped                                               |
| `allowAAWithdrawRequest()`      | `false`                          | `true`      | flipped                                               |
| `paused()`                      | `true`                           | `false`     | flipped (`_unpause()` inside `stopEpoch`)             |
| `tranchePrice(AA)`              | `1,082,100`                      | `1,088,114` | **+0.555%** (interest crystallised)                   |
| `IdleCreditVault.epochNumber()` | `10`                             | `11`        | incremented (consequence of `_strategy.deposit(...)`) |
| `JT.balanceOf(caliber)`         | `49,853,528,264,549,100,640,239` | unchanged   | redeem hasn't run yet                                 |

> **Snapshot S1** = `0x58cc150749916878305dc9ecc9d15ab7dce8762247fa359bbd40293ec339bab7` — taken immediately after Step W1. Anchor for downstream phases.

---

## Phase 1 — `request_redeem` (atomic, between epochs)

Phase 1 = step 1 (`JT.redeem`) immediately followed by step 2
(`requestWithdraw`). Both run from the caliber.

### Step P1.1 — `JT.redeem(half_shares, caliber, caliber)`

Pre-state (sandwich for `aaBefore`):

| Read                    | Value              |
| ----------------------- | ------------------ |
| `AA.balanceOf(caliber)` | `0`                |
| `JT.balanceOf(caliber)` | `49,853.528264 JT` |
| `JT.totalSupply()`      | `49,853.528264 JT` |

Tx:

| Field       | Value                                                                      |
| ----------- | -------------------------------------------------------------------------- |
| from        | caliber `0xD1A1…c1BC`                                                      |
| to          | Royco JT `0x8e0E…1a6d`                                                     |
| selector    | `0xba087652` (`redeem(uint256,address,address)`)                           |
| `_shares`   | `24_926_764_132_274_550_320_119` (= 50% of caliber's JT, ≈ 24,926.7641 JT) |
| `_receiver` | caliber                                                                    |
| `_owner`    | caliber                                                                    |
| tx_hash     | `0x5fe103d832f31706c403c85c7bbfce29465ce5234880d32496dce9854adfce8c`       |
| status      | success                                                                    |

Post-state:

| Read                    | Value (raw)             | Decoded                                                      |
| ----------------------- | ----------------------- | ------------------------------------------------------------ |
| `AA.balanceOf(caliber)` | `0x4e0c26abc1e2de65d7a` | **23,035.545820 AA** received (= `aaDelta` for the sandwich) |
| `JT.balanceOf(caliber)` | `0x5474857e6a5acb3abf8` | 24,926.764132 JT remaining                                   |
| `JT.totalSupply()`      | `0x5474857e6a5acb3abf8` | 24,926.764132 JT (caliber still owns 100%)                   |

So `aaAfter - aaBefore = 23,035,545,820,418,214,878,586` ≈ **23,035.546 AA**. This is the JT's `jtAssets`-per-share × `sharesRedeemed`. Caliber retains the other 24,926.764 JT shares (the unredeemed half).

> **Coverage check** fired here on the JT (per Stage 1b notes — the JT
> mirrors ST.deposit's coverage gate, not ST.redeem's open path).
> With `ST.totalSupply == 0` the coverage envelope is unbounded, so
> a 50% redeem passes trivially. If a future state had a senior position
> the same call would have to be sized via `JT.maxRedeem(caliber)`.

### Step P1.2 — `IdleCDOEpochVariant.requestWithdraw(aaDelta, AATranche)`

| Field      | Value                                                                |
| ---------- | -------------------------------------------------------------------- |
| from       | caliber                                                              |
| to         | CDO `0x433D…be4d`                                                    |
| selector   | `0xccc143b8` (`requestWithdraw(uint256,address)`)                    |
| `_amount`  | `23_035_545_820_418_214_878_586` (≈ 23,035.546 AA)                   |
| `_tranche` | `0xc26a6fa2c37b38e549a4a1807543801db684f99c` (AATranche)             |
| tx_hash    | `0xbb3fcbce5216222686d1f5b3bebc67cd32cb948c3a472c16376da81db8645401` |
| status     | success                                                              |

Caliber state after Phase 1:

| Read                                           | Value (raw)     | Decoded                                   |
| ---------------------------------------------- | --------------- | ----------------------------------------- |
| `AA.balanceOf(caliber)`                        | `0`             | burned by `_withdrawOps`                  |
| `FalconXUSDC.balanceOf(caliber)`               | `0x5de3c4098`   | **25,203.327128 USDC** (6-dec receipt)    |
| `IdleCreditVault.withdrawsRequests(caliber)`   | `0x5de3c4098`   | matches the receipt 1:1                   |
| `IdleCreditVault.lastWithdrawRequest(caliber)` | `0x0b`          | 11 (snapshot of `epochNumber` at request) |
| `IdleCreditVault.epochNumber()`                | `0x0b`          | 11 (unchanged)                            |
| `USDC.balanceOf(caliber)`                      | `0`             | unchanged                                 |
| `JT.balanceOf(caliber)`                        | `24,926.764132` | unredeemed half RETAINED                  |

Readiness check: `epochNumber (11) > lastWithdrawRequest[caliber] (11)` ⇒ **NOT READY**. Premature claim must revert.

---

## Pending-window account valuation (between Phase 1 and Phase 2)

Run the account recipe (mirroring the production accountant) on this
pending state:

| Term                                                | Raw value               | Decoded                        |
| --------------------------------------------------- | ----------------------- | ------------------------------ |
| `JT.balanceOf(caliber)` = `jt_shares`               | `0x5474857e6a5acb3abf8` | 24,926.764132 JT               |
| `JT.convertToAssets(jt_shares)` slot 1 (`jtAssets`) | `0x4e0c26abc1e2de65d7b` | 23,035.545820 AA               |
| `JT.convertToAssets(...)` slot 2 (`nav`)            | `0x54ecae9d5ccd5f05c4e` | 25,065.299905 USD-WAD          |
| `AA.balanceOf(caliber)` = `stranded_aa`             | `0`                     | 0                              |
| `tranchePrice(AA)`                                  | `0x109a72`              | 1,088,114 (USDC-6 per 1e18 AA) |
| `FalconXUSDC.balanceOf(caliber)` = `pending_usdc`   | `0x5de3c4098`           | 25,203.327128 USDC             |

Compute (asset-space, blueprint path):

```
total_aa  = jtAssets + stranded_aa = 23,035.545820 AA
usdc_from_aa = total_aa * tranchePrice(AA) / 1e18 = 25,065.299904 USDC
total_usdc   = usdc_from_aa + pending_usdc       = 50,268.627032 USDC
```

NAV-space cross-check:

```
nav / 1e12 + pending_usdc = 25,065.299904 + 25,203.327128 = 50,268.627032 USDC
```

Both paths agree to the wei. **Pending-window total = 50,268.627032 USDC**.

Pre-withdraw account valuation (from `execution-account.md`) was
`49,853.528264 USDC`. The +415.099 USDC delta (+0.833%) comes from:

1. `tranchePrice(AA)` advance from 1,082,100 → 1,088,114 due to the
   first `stopEpoch` interest crystallisation (+0.555%).
2. `requestWithdraw` pre-crediting the _next_ epoch's net interest into
   the `FalconXUSDC` receipt (per `_calcInterestWithdrawRequest`).

So **the blueprint's accountant correctly tracks the position through
the pending window** — even though half the position is sitting as a
receipt rather than JT shares, the formula
`jtAssets*tranchePrice + FalconXUSDC.balanceOf` resolves to a coherent
USDC valuation that reflects the protocol's actual liability to the
caliber.

---

## Premature claim — should revert `NotAllowed()`

`simulate_vnet_transaction` of `claimWithdrawRequest()` from the caliber
on the post-Phase-1 state:

| Field                                     | Value                                   |
| ----------------------------------------- | --------------------------------------- |
| from                                      | caliber                                 |
| to                                        | CDO `0x433D…be4d`                       |
| selector                                  | `0x33986ffa` (`claimWithdrawRequest()`) |
| `simulate_vnet_transaction.decoded_error` | `NotAllowed`                            |
| revert hex                                | `0x3d693ada`                            |
| status                                    | reverted (✅ as expected)               |

Source confirmation: `IdleCreditVault.claimWithdrawRequest(_user)`
reverts at `if (epochNumber <= lastWithdrawRequest[_user]) revert NotAllowed();`.
With `epochNumber == 11` and `lastWithdrawRequest[caliber] == 11`,
`11 <= 11` ⇒ revert.

**Blueprint detection without try/catch**:

```
ready = IdleCreditVault.epochNumber() > IdleCreditVault.lastWithdrawRequest(caliber)
```

---

## Phase 2 setup — drive the protocol to the next epoch boundary

### Step W2 — `startEpoch()` (manager)

Required: `block.timestamp >= epochEndDate + bufferPeriod`. To work
around the Tenderly EVM-vs-block-ts mismatch documented above, the
storage override was applied:

| Action                                           | Result                                                                                                                                   |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `tenderly_setStorageAt(CDO, 0x122, 0x…65530000)` | epochEndDate written to 1,700,000,000 (forces `block.timestamp >= epochEndDate + bufferPeriod` to trivially true under any plausible ts) |

Tx:

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| from     | manager `0x1fb0…df58`                                                |
| to       | CDO `0x433D…be4d`                                                    |
| selector | `0xa2c8b177` (`startEpoch()`)                                        |
| tx_hash  | `0xd739fbfe92889ec08fe871fc6cb0742e416a63fb6415aff4e51177dc2d1b1b9c` |
| status   | success                                                              |

Post-`startEpoch` state:

- `isEpochRunning()` = `true`
- new `epochEndDate()` = `0x6a411146` = 1,781,797,702 (= `block.timestamp` at exec + `epochDuration`)
- `paused()` = `true`
- `allowAAWithdrawRequest()` = `false`
- `epochNumber()` = `11` (unchanged — does not bump on startEpoch)

### Step W3 — Second `stopEpoch(8.25e18, 0)`

Re-apply the storage override (`startEpoch` reset `epochEndDate`), then
call `stopEpoch` again. With the override, `stopEpoch`'s
`block.timestamp < epochEndDate` guard is trivially false.

| Action                                           | Result                              |
| ------------------------------------------------ | ----------------------------------- |
| `tenderly_setStorageAt(CDO, 0x122, 0x…65530000)` | epochEndDate reset to 1,700,000,000 |

Tx:

| Field       | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| from        | manager                                                              |
| to          | CDO                                                                  |
| selector    | `0xd48099ad`                                                         |
| `_newApr`   | `0x727de34a24f90000` = 8.25e18                                       |
| `_interest` | `0`                                                                  |
| tx_hash     | `0xc11137edcd03d8303bb11a6967f3b2bb46863425ce440778024fa1949f5add67` |
| status      | success                                                              |

Post-second-stopEpoch state:

| Read                                         | Value                  | Δ vs Phase 1 finish                            |
| -------------------------------------------- | ---------------------- | ---------------------------------------------- |
| `isEpochRunning()`                           | `false`                | flipped                                        |
| `allowAAWithdrawRequest()`                   | `true`                 | flipped                                        |
| `paused()`                                   | `false`                | flipped                                        |
| `tranchePrice(AA)`                           | `0x10b211` = 1,094,673 | +0.602% (another interest crystallisation)     |
| `IdleCreditVault.epochNumber()`              | `0x0c` = **12**        | +1                                             |
| `lastWithdrawRequest[caliber]`               | `0x0b` = 11            | unchanged (request stamp persists until claim) |
| `FalconXUSDC.balanceOf(caliber)`             | `25,203.327128`        | unchanged (receipt still held)                 |
| `IdleCreditVault.withdrawsRequests(caliber)` | `25,203.327128`        | unchanged                                      |

Readiness check: `epochNumber (12) > lastWithdrawRequest[caliber] (11)` ⇒ **READY**.

---

## Phase 2 — `claim_redeem`

Pre-Phase-2 caliber `USDC.balanceOf = 0`.

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| from     | caliber                                                              |
| to       | CDO `0x433D…be4d`                                                    |
| selector | `0x33986ffa` (`claimWithdrawRequest()`)                              |
| calldata | `0x33986ffa` (no args)                                               |
| tx_hash  | `0xe64f9d1dbd90d557b81e568a95f45452902047db14d7ab1c505eb97481214077` |
| status   | success                                                              |

Post-Phase-2 caliber state:

| Read                                           | Value (raw)        | Decoded                                                  |
| ---------------------------------------------- | ------------------ | -------------------------------------------------------- |
| `USDC.balanceOf(caliber)`                      | `0x5de3c4098`      | **25,203.327128 USDC** (= entire FalconXUSDC receipt)    |
| `FalconXUSDC.balanceOf(caliber)`               | `0x0`              | 0 (burned)                                               |
| `AA.balanceOf(caliber)`                        | `0x0`              | 0                                                        |
| `JT.balanceOf(caliber)`                        | `24,926.764132 JT` | unchanged (the unredeemed half still belongs to caliber) |
| `IdleCreditVault.withdrawsRequests(caliber)`   | `0x0`              | reset                                                    |
| `IdleCreditVault.lastWithdrawRequest(caliber)` | `0x0`              | reset                                                    |

**Receipt → claim slippage = 0 wei.** The Phase 2 USDC payout
(25,203,327,128) is byte-identical to the Phase 1 receipt face value
(25,203,327,128). Unlike the ST sibling's partial-redeem case
(`prepareStopEpochWithApr0` consumed 1.9 USDC), the JT half-redeem here
saw no slip — the strategy's APR0 settlement happened to net out
exactly, presumably because the request was the only outstanding one
in this epoch's `pendingWithdraws`.

> **Verification that Phase 2 is NOT keyring-gated and NOT role-gated**:
> the caliber called `claimWithdrawRequest()` directly with no prior
> Keyring credential refresh and no AccessManager role grant for that
> selector. Source: the CDO's `claimWithdrawRequest()` body forwards
> `msg.sender` to the strategy without any `_checkNotAllowed` /
> `isWalletAllowed` call. JT spec note `access_control.pareto.notes`
> "claimWithdrawRequest() is NOT keyring-checked" is confirmed.

---

## P&L over the simulated cycle

| Metric                                             | Value                                                                                                                                                                                                                                                                       |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Original deposit (Stage 2 deposit)                 | 50,000.000000 USDC                                                                                                                                                                                                                                                          |
| JT shares minted at deposit                        | 49,648.773095                                                                                                                                                                                                                                                               |
| JT shares at withdraw start (post fee-mint, ~9.2d) | 49,853.528264                                                                                                                                                                                                                                                               |
| Fee-mint shares added                              | +204.755169 (+0.412% over ~9.2 days)                                                                                                                                                                                                                                        |
| Shares redeemed (50%)                              | 24,926.764132                                                                                                                                                                                                                                                               |
| Shares retained (50%)                              | 24,926.764132                                                                                                                                                                                                                                                               |
| AA received from `JT.redeem`                       | 23,035.545820                                                                                                                                                                                                                                                               |
| FalconXUSDC receipt minted                         | 25,203.327128 USDC                                                                                                                                                                                                                                                          |
| USDC paid by Phase 2 claim                         | 25,203.327128 USDC                                                                                                                                                                                                                                                          |
| Slippage receipt → claim                           | **0 wei**                                                                                                                                                                                                                                                                   |
| Allocated principal (50% of 50k)                   | 25,000.000000 USDC                                                                                                                                                                                                                                                          |
| Net on redeemed half                               | **+203.327128 USDC (+0.813%)**                                                                                                                                                                                                                                              |
| Implied annualised yield on the cycle              | ~4.18% APR (this comprises the post-deposit mid-epoch discount unwind + one full pre-credited epoch + half of two `stopEpoch`-triggered AA repricings; production-realistic redemptions sized to the deposit-epoch boundary would yield closer to the unscaledApr of 8.25%) |

The unredeemed half (24,926.764132 JT) sits on the caliber's books with
the same per-share NAV as before; running the account recipe on it
returns `jtAssets ≈ 23,035.546 AA × tranchePrice(AA) = 25,065.299904 USDC`
of book value, plus accrued tranchePrice up-tick that will continue
across future epochs. The caliber can redeem that remainder via the same
two-phase machinery any time after the next `stopEpoch`.

---

## Runbook concerns for the blueprint

1. **`stopEpoch` is a Pareto-ops step, not a blueprint step.** It is
   gated to `IdleCreditVault.manager()` (an EOA controlled by Pareto).
   The caliber blueprint can NEVER trigger it. The blueprint must
   instead detect the result of a `stopEpoch` having happened — the
   only reliable readiness signal is
   `IdleCreditVault.epochNumber() > IdleCreditVault.lastWithdrawRequest(caliber)`.
   This is a pure state read, no try/catch needed.

2. **Phase 1 timing constraint.** Phase 1 step 2 (`requestWithdraw`)
   requires `isEpochRunning == false && allowAAWithdrawRequest == true`,
   i.e. it can only run in the inter-epoch window. End-to-end this
   means up to `2 * epochDuration + bufferPeriod ≈ 60 days` worst case
   (request just before `startEpoch`) and ~`epochDuration ≈ 30 days`
   best case (request just after `stopEpoch`).

3. **Phase 1 atomicity.** Step 1 (`JT.redeem`) and step 2
   (`requestWithdraw`) MUST be in the same blueprint transaction. If a
   `startEpoch` lands between them, the AA tranche tokens received by
   step 1 will be stuck in the caliber until the next inter-epoch
   window. The blueprint should sandwich `AA.balanceOf(caliber)`
   before/after step 1 to derive `aaDelta` and feed it directly into
   step 2 — do not trust the 3-tuple decode from `JT.redeem` here, the
   sandwich is the wei-correct value.

4. **Phase 2 atomicity.** Phase 2 is a single `claimWithdrawRequest()`
   call with no args, no role gate, no keyring gate, and no epoch-time
   gate beyond the `epochNumber > lastWithdrawRequest` invariant. Run
   it as its own blueprint, scheduled by an orchestration layer
   watching the readiness condition.

5. **Coverage gate on `JT.redeem` (vs ST sibling).** Unlike the ST
   where `redeem` is unrestricted, `JT.redeem` runs through
   `kernel.jtRedeem` which fires
   `_postOpSyncTrancheAccountingAndEnforceCoverage(Operation.JT_REDEEM)`.
   When the ST tranche is empty (current state) this gate is loose
   (`JT.maxRedeem(caliber) == uint256.max`). When a senior position
   exists the redeem is bounded by `JT.maxRedeem(caliber)`. The
   blueprint should size the redeem to
   `min(desired, JT.maxRedeem(caliber))` defensively, even though in
   the current state the cap is not binding.

6. **Receipt token is wei-perfect on this path.** Unlike the ST
   sibling's partial-redeem path (which observed a 1.9 USDC slip from
   `prepareStopEpochWithApr0`), the JT half-redeem here saw 0 wei slip.
   The slip is path-dependent — it can be 0 OR up to ~basis points,
   depending on how the strategy's APR0 bookkeeping resolves during
   the intervening `stopEpoch`. For the accountant blueprint,
   `FalconXUSDC.balanceOf(caliber)` should be treated as a
   near-upper-bound on the eventual USDC payout, not a guarantee. A
   sub-cent haircut at claim is normal.

7. **Coverage check operationally clean even with mid-epoch position
   activity.** Phase 1 ran successfully even though Phase 1 step 2
   only became possible after Step W1 closed the epoch. No coverage
   error was observed on the 50% JT.redeem at any point. The runbook
   should still verify `JT.maxRedeem` before sizing, since markets
   that later add an ST position will tighten this envelope.

8. **Tenderly time control caveat.** For the blueprint-tester
   (Stage 4), driving the protocol through a full `stopEpoch` →
   `startEpoch` → `stopEpoch` cycle on a Tenderly vnet may require
   `tenderly_setStorageAt` on CDO slot `0x122` (`epochEndDate`) when
   the EVM `block.timestamp` does not honor the warped fork time. This
   is the trick used here. Spellcaster simulation runs at real time and
   doesn't need it.

---

## Snapshot ledger for downstream stages

| Snapshot                                  | Created at                    | Status                                                            |
| ----------------------------------------- | ----------------------------- | ----------------------------------------------------------------- |
| `account_done_snapshot` (`0x259d5504…`)   | End of `execution-account.md` | Reverted to at the start of this stage; consumed by `revert_vnet` |
| `S1 post-first-stopEpoch` (`0x58cc1507…`) | After Step W1                 | Anchor for Phase 1; not reverted in this stage (kept for re-runs) |

The fork now sits in the **post-claim** state: caliber holds 24,926.764
JT shares + 25,203.327128 USDC. The DUSD machine could either redeem
the remainder via another withdraw cycle or hold the JT half indefinitely.

---

## Summary table (matches the JT blueprint shape — same as ST)

### Phase 1 — request_redeem (atomic, between epochs)

| # | Action                                                    | Contract             | Selector               | Inputs                                  | Output observation                                  |
| - | --------------------------------------------------------- | -------------------- | ---------------------- | --------------------------------------- | --------------------------------------------------- |
| 1 | (optional) `Kernel.syncTrancheAccounting()`               | `0x15bb…1791`        | `0x9c8e2dc0`           | none                                    | crystallise NAV before `redeem`                     |
| 2 | (sandwich pre) `AA.balanceOf(caliber)`                    | AA `0xc26a…f99c`     | `0x70a08231`           | caliber                                 | `aaBefore`                                          |
| 3 | (size) `JT.maxRedeem(caliber)` → cap shares to redeem     | JT `0x8e0E…1a6d`     | `0x402d267d`           | caliber                                 | `cap` (uint256.max if no senior)                    |
| 4 | `JT.redeem(min(shares, cap), caliber, caliber)`           | JT                   | `0xba087652`           | shares, receiver=caliber, owner=caliber | returns `(0, jtAssets, nav)`; AA arrives at caliber |
| 5 | (sandwich post) `AA.balanceOf(caliber)`                   | AA                   | `0x70a08231`           | caliber                                 | `aaAfter`                                           |
| 6 | `aaDelta = aaAfter - aaBefore` (`UnsignedMathHelper.sub`) | helper `0x3D62…E3c0` | `sub(uint256,uint256)` | (aaAfter, aaBefore)                     | `aaDelta` (≈ `jtAssets`-scaled-to-redeemed-shares)  |
| 7 | `IdleCDOEpochVariant.requestWithdraw(aaDelta, AATranche)` | CDO `0x433D…be4d`    | `0xccc143b8`           | _amount=aaDelta, _tranche=AA addr       | mints FalconXUSDC receipt to caliber                |

### Phase 2 — claim_redeem (atomic, after next `stopEpoch`)

| # | Action                                                                        | Contract               | Selector     | Inputs  | Output observation                     |
| - | ----------------------------------------------------------------------------- | ---------------------- | ------------ | ------- | -------------------------------------- |
| 1 | (readiness probe) `IdleCreditVault.epochNumber()`                             | Strategy `0x17E9…eef3` | `0xf4145a83` | none    | uint256                                |
| 2 | (readiness probe) `IdleCreditVault.lastWithdrawRequest(caliber)`              | Strategy               | `0x93f88d4c` | caliber | uint256                                |
| 3 | (gate) require `epochNumber > lastWithdrawRequest[caliber]` (`BooleanHelper`) | helpers                | —            | —       | revert if not ready                    |
| 4 | `IdleCDOEpochVariant.claimWithdrawRequest()`                                  | CDO                    | `0x33986ffa` | none    | burns receipt; USDC arrives at caliber |

The blueprint **cannot** be made fully atomic — Phase 1 and Phase 2 must
be separate transactions separated by at least one full Pareto epoch +
buffer, with `stopEpoch` triggered by the Pareto manager
(NOT a caliber primitive).

---

## Surprises vs the spec / ST sibling

1. **JT.maxRedeem == uint256.max in the bootstrap-only state.** The
   spec flagged "JT.redeem may revert on coverage; size to ~10%". In
   practice, with `ST.totalSupply == 0` the kernel's coverage formula
   has no senior to protect, so the redeem is unlimited. Confirmed
   empirically by 50% redeem succeeding without coverage revert. The
   blueprint should still call `JT.maxRedeem` defensively for the case
   where an ST position is later added on this market.

2. **Receipt → claim slippage = 0 wei on this redeem.** The ST
   sibling's partial-redeem documented a 1.9 USDC slip from
   `prepareStopEpochWithApr0`. This JT half-redeem saw no slip. The
   slip is path-dependent — when the caliber's request is the only
   `pendingWithdraws` entry routed through the next `stopEpoch`
   (which is roughly true here: `pendingWithdraws` was 25,203 USDC
   pre-second-stopEpoch, equal to caliber's own request), there is
   nothing for the APR0 bucket to net against and the payout is
   wei-exact. The blueprint accountant should still treat the receipt
   as an upper-bound — production conditions with other lenders'
   requests aggregated may reintroduce the sub-cent slip.

3. **Tenderly EVM `block.timestamp` mismatch.** Documented in the
   Setup section above and `MEMORY.md`. The fix used here is
   `tenderly_setStorageAt` on CDO slot `0x122` to override
   `epochEndDate` to a small value. NOT a blueprint concern, but
   blueprint-tester (Stage 4) will need to know about it.

4. **Caliber retained JT shares for the unredeemed half.** Confirmed
   by `JT.balanceOf(caliber) == 24,926.764132` after Phase 2 finished.
   The unredeemed JT is fully spendable in a subsequent withdraw
   cycle, with the same per-share NAV. No "cooldown" on the retained
   shares. The kernel auto-synced its accounting on each `redeem` via
   `_postOpSyncTrancheAccounting`, so no separate post-claim sync was
   needed.
