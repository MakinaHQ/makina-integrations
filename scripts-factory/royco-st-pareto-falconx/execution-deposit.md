# Execution Report — Royco ST Pareto FalconX (deposit)

## Fork (reuse this for subsequent stages)

| Key                | Value                                                                                                      |
| ------------------ | ---------------------------------------------------------------------------------------------------------- |
| `vnet_id`          | `5b132729-f79a-4ffc-8d2f-33bac4dc23f9`                                                                     |
| `rpc_url` (admin)  | `https://virtual.mainnet.eu.rpc.tenderly.co/4ed6c929-bd54-4f22-a18d-aa575d39b78d`                          |
| `rpc_url` (public) | `https://virtual.mainnet.eu.rpc.tenderly.co/87b35d4b-440e-4d0c-b0a8-144878619636`                          |
| Fork chain         | Ethereum mainnet (chain_id 1)                                                                              |
| Fork block         | `0x17d5d55` (24,992,981)                                                                                   |
| Project            | `dialectic-medici/script-factory`                                                                          |
| Dashboard          | https://dashboard.tenderly.co/dialectic-medici/script-factory/testnet/5b132729-f79a-4ffc-8d2f-33bac4dc23f9 |

Action: **deposit**
Caliber under test: `0x5476F4E23dAA093Ce6700e1026013c55F7AF9083` (intMkSrRoyUSDC mainnet caliber)

---

## Pre-flight: actual on-chain state at fork block

| Read                                                             | Selector     | Contract                          | Result                                                                                       | Notes                                                                                 |
| ---------------------------------------------------------------- | ------------ | --------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `isEpochRunning()`                                               | `0xc5c75098` | IdleCDOEpochVariant `0x433D…be4d` | `true`                                                                                       | Epoch live -> deposit path B (`depositDuringEpoch`)                                   |
| `isDepositDuringEpochDisabled()`                                 | `0x5f0b472a` | same                              | `false`                                                                                      | Mid-epoch deposits enabled                                                            |
| `epochEndDate()`                                                 | `0x75d1497b` | same                              | `1779480958` (2026-05-04 17:29:34 UTC)                                                       | Currently 4 days out                                                                  |
| `epochDuration()`                                                | `0x4ff0876a` | same                              | `2,790,207` s (~32.3 days)                                                                   |                                                                                       |
| `paused()`                                                       | `0x5c975abb` | same                              | `true`                                                                                       | Pareto pauses CDO during epoch (only `depositDuringEpoch` works)                      |
| `defaulted()`                                                    | `0x69e25ec1` | same                              | `false`                                                                                      |                                                                                       |
| `tranchePrice(AA)`                                               | `0xa219d218` | same                              | `1,074,982` (USDC 6-dec / 1e18 AA)                                                           | i.e. 1 AA ≈ 1.074982 USDC                                                             |
| `keyring()`                                                      | `0x9ed9de94` | same                              | `0x6a6a91c7…0e3` (KeyringIdleWhitelist)                                                      |                                                                                       |
| `keyringPolicyId()`                                              | `0xd636b05f` | same                              | `18`                                                                                         |                                                                                       |
| `whitelist(caliber)` (slot 2)                                    | `0x9b19251a` | KeyringIdleWhitelist              | **`true`**                                                                                   | Caliber already keyring-whitelisted on this fork — no override needed                 |
| `checkCredential(18, caliber)`                                   | `0x8776b120` | same                              | reverted (the real Keyring rejects, but the local `whitelist[caliber]` short-circuits first) |                                                                                       |
| `RoycoFactory.canCall(caliber, ROY_ST, deposit)`                 | `0xb7009613` | RoycoFactory `0x7cC6…253C`        | `(true, 0)`                                                                                  | Caliber **already has** ST_LP role                                                    |
| `RoycoFactory.canCall(caliber, ROY_ST, redeem)`                  | same         | same                              | `(true, 0)`                                                                                  | Already has redeem role                                                               |
| `RoycoFactory.canCall(caliber, Kernel, syncTrancheAccounting())` | same         | same                              | `(true, 0)`                                                                                  | Already has sync role                                                                 |
| `RoycoFactory.canCall(caliber, ROY_JT, deposit)`                 | same         | same                              | **`(false, 0)`**                                                                             | Caliber does NOT have JT_LP role — needed only for the testnet junior bootstrap below |
| `getTargetFunctionRole(ROY_ST, deposit)`                         | `0x6d5115bd` | RoycoFactory                      | `0x858ca8ea411ba2c3`                                                                         | ST_LP role id                                                                         |
| `getTargetFunctionRole(ROY_JT, deposit)`                         | same         | same                              | `0xded17f6f89970f45`                                                                         | JT_LP role id                                                                         |
| `getTargetFunctionRole(Kernel, syncTrancheAccounting)`           | same         | same                              | `0xd0e899cf7cf8785d`                                                                         | sync role id                                                                          |
| `RoycoSeniorTranche.totalSupply()`                               | `0x18160ddd` | ROY-ST `0x694A…754B`              | `0`                                                                                          | Empty market — coverage check WILL revert until JT seeded                             |
| `RoycoJuniorTranche.totalSupply()`                               | `0x18160ddd` | ROY-JT `0x8e0e…1a6d`              | `0`                                                                                          | Same                                                                                  |
| `AA.totalSupply()`                                               | `0x18160ddd` | AA `0xc26a…f99c`                  | `30,068,762.5e18`                                                                            | Pareto AA tranche has supply (mid-epoch deposit valid)                                |
| `BB.totalSupply()`                                               | `0x18160ddd` | BB `0xacbb…b3d6`                  | `0`                                                                                          | Pareto BB monotranche — irrelevant to Royco JT                                        |
| `ROY-ST.balanceOf(caliber)`                                      | `0x70a08231` | ROY-ST                            | `0`                                                                                          |                                                                                       |
| `AA.balanceOf(caliber)`                                          | same         | AA                                | `0`                                                                                          |                                                                                       |
| `USDC.balanceOf(caliber)`                                        | same         | USDC                              | `50,000,000,000` (50,000 USDC)                                                               | Caliber pre-funded on mainnet                                                         |

### Findings vs. spec assumptions

The spec (`specs.yaml`) flags three blocking items:

1. `caliber_keyring` — **already satisfied on mainnet.** `KeyringIdleWhitelist.whitelist[caliber] == true`. No storage override required.
2. `caliber_royco_role` — **already satisfied on mainnet** for `ST.deposit`, `ST.redeem`, and `Kernel.syncTrancheAccounting`. Verified directly via `RoycoFactory.canCall`.
3. `junior_bootstrap` — **still required.** `ROY-JT.totalSupply == 0` and `jtRawNAV == 0`, so the kernel coverage check will revert any senior deposit until a junior position is seeded.

Only one access gate was missing for the test setup: **the JT_LP role for the caliber**, needed solely so that the _same_ caliber could perform the junior-leg bootstrap on this fork. On real mainnet this would be done by Royco/Pareto via a dedicated junior bootstrapper, not via the caliber itself.

---

## Setup

### 1. Tenderly fork

Created at the latest block (`0x17d5d55`, ~24,992,981). See "Fork" section above.

### 2. Fund caliber with USDC

`tenderly_setErc20Balance` — set `USDC.balanceOf(caliber) = 0x174876E800` = **100,000 USDC**.

### 3. Keyring bypass — NOT NEEDED

`KeyringIdleWhitelist.whitelist[caliber]` already returns `true` at storage slot `keccak256(abi.encode(caliber, uint256(2)))`. Reading the slot directly via `eth_getStorageAt` confirmed this. No `tenderly_setStorageAt` call was issued.

For the blueprint runbook: on mainnet today the caliber is **already enrolled on Pareto policy 18** (the spec's open-question `caliber_keyring` is resolved).

### 4. Royco AccessManager — partial bypass

Caliber already has the senior-side roles (ST_LP, sync). The only role missing is **JT_LP** (`0xded17f6f89970f45`), needed for the junior bootstrap step below.

Granted via `grantRole(uint64,address,uint32)` from the AccessManager admin (role 0). Admin discovered by scanning `RoleGranted(uint64,address,uint32,uint48,bool)` events on the AccessManager — first event in the contract's history granted role `0` (admin) to:

> `0x7c405bbd131e42af506d14e752f2e59b19d49997` (Royco/Dialectic deployer multisig)

#### Tx — grant JT_LP to caliber

| Field    | Value                                                                                                                                   |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| from     | `0x7c405bbd131e42af506d14e752f2e59b19d49997` (impersonated admin)                                                                       |
| to       | `0x7cC6fB28eC7b5e7afC3cB3986141797ffc27253C` (RoycoFactory)                                                                             |
| selector | `0x25c471a0` (`grantRole(uint64,address,uint32)`)                                                                                       |
| calldata | `0x25c471a0` `+ 000…ded17f6f89970f45` (roleId) `+ 000…5476F4E23dAA093Ce6700e1026013c55F7AF9083` (caliber) `+ 000…00` (executionDelay 0) |
| tx_hash  | `0x7e5f6bf7bccb70a0792da7af15316e130c127209f097018537b77aaa2df759ac`                                                                    |
| status   | success                                                                                                                                 |

Verified post-grant: `RoycoFactory.canCall(caliber, ROY_JT, deposit) == (true, 0)`.

> **Runbook flag for the blueprint-writer**: in production this grant must come from Royco off-chain. The senior-side grants (ST.deposit / ST.redeem / Kernel.sync) already exist on mainnet for this caliber. Junior-side grants are NOT necessary for the blueprint itself — they were used here only to bootstrap the test.

### 5. Junior leg bootstrap

Path chosen: **Caliber acquires a small AA position via `depositDuringEpoch(AA)`, then deposits all of it into the Royco junior tranche**. The Royco JT's `asset()` is the AA tranche (same as ST), so the junior leg is denominated in AA units — there is no need to mint Pareto BB. The `IdleCDOEpochVariant.depositBB(uint256)` route would have failed because (a) the CDO is `whenNotPaused` and currently paused, and (b) `_trancheTotSupply(BB) == 0` would also block `depositDuringEpoch(BB)` per the source's first-mid-epoch-deposit guard.

`tenderly_setStorageAt` to override the kernel's `jtRawNAV` directly was rejected as the second-choice option: the kernel impl `0xAA9631dF7ec04AbB825bD6a663f96c9BB3Ed7e1e` is unverified and the accountant subimpl `0x288bc6a8…c110` is unverified, so the precise storage layout for `jtRawNAV` is not known. The Royco-JT-deposit path uses real protocol state and is therefore more faithful.

#### Tx 5a — caliber approves USDC to IdleCDOEpochVariant (60,000 USDC)

| Field    | Value                                                                        |
| -------- | ---------------------------------------------------------------------------- |
| from     | caliber `0x5476F4…9083`                                                      |
| to       | USDC `0xA0b8…eB48`                                                           |
| selector | `0x095ea7b3` (`approve(address,uint256)`)                                    |
| spender  | `0x433D5B175148dA32Ffe1e1A37a939E1b7e79be4d` (IdleCDOEpochVariant)           |
| amount   | `60_000_000_000` (60,000 USDC; 10k for JT bootstrap + 50k for ST under test) |
| tx_hash  | `0x3417594a0cc909dafad6d9ad0213e1b61c6733328df2d094c1a5dcb3157e8246`         |
| status   | success                                                                      |

#### Tx 5b — bootstrap AA acquisition: `depositDuringEpoch(10_000 USDC, AATranche)`

Branch: `isEpochRunning() == true && !isDepositDuringEpochDisabled` → path B.

| Field      | Value                                                                |
| ---------- | -------------------------------------------------------------------- |
| from       | caliber                                                              |
| to         | IdleCDOEpochVariant `0x433D…be4d`                                    |
| selector   | `0xc61e3faa` (`depositDuringEpoch(uint256,address)`)                 |
| `_amount`  | `10_000_000_000` (10,000 USDC, 6-dec)                                |
| `_tranche` | `0xc26a6fa2c37b38e549a4a1807543801db684f99c` (AA)                    |
| tx_hash    | `0xf362bfa07cbc23ed158197524b0f91b35a91630c34593ecc7d45a64676fc4fe5` |
| status     | success                                                              |

**Balance sandwich**: `AA.balanceOf(caliber)` before = 0, after = `9,249,611,701,838,568,793,265` (≈ **9,249.61 AA**, 18-dec). Mid-epoch effective price ≈ `10,000 / 9,249.61 = 1.0811 USDC per AA`.

#### Tx 5c — caliber approves AA to Royco JT

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| from     | caliber                                                              |
| to       | AA tranche `0xc26a…f99c`                                             |
| selector | `0x095ea7b3` (`approve(address,uint256)`)                            |
| spender  | `0x8e0ec43e51b88aa2324102e1a3d667822be51a6d` (Royco JT)              |
| amount   | `9_249_611_701_838_568_793_265` (full AA balance)                    |
| tx_hash  | `0x6d04d456c77e877461abd652bf90b1a4499b8ce1a1d5d8036de7dcb4c92bbd73` |
| status   | success                                                              |

#### Tx 5d — bootstrap junior NAV: `RoycoJT.deposit(aaAmt, caliber)`

| Field       | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| from        | caliber                                                              |
| to          | Royco JT `0x8e0e…1a6d`                                               |
| selector    | `0x6e553f65` (`deposit(uint256,address)`)                            |
| `_assets`   | `9_249_611_701_838_568_793_265`                                      |
| `_receiver` | caliber                                                              |
| tx_hash     | `0x08245f4da4887808cdeeaa98264c09ee240553b658a2f47f7bc918dac3bf0743` |
| status      | success                                                              |

Post-state:

- `ROY-JT.balanceOf(caliber) = 9_938_180_541_571_879_535_993` (≈ **9,938.18 JT shares**)
- `ROY-JT.totalSupply() = 9_938_180_541_571_879_535_993` (caliber owns 100%)
- `AA.balanceOf(caliber) = 0` (all sent to kernel)
- `AA.balanceOf(Kernel) = 9_249_611_701_838_568_793_265` (bootstrap AA now in kernel custody)

The junior tranche now has positive NAV → the kernel coverage check for the senior deposit can succeed.

> **Runbook flag**: the blueprint must NOT replicate this junior-bootstrap step. On mainnet the junior leg is bootstrapped by Royco/Pareto out-of-band before the caliber is ever invoked. The blueprint-writer should treat `jtRawNAV > 0` as a precondition the operator/operations team verifies before activating the senior position.

---

## Deposit-under-test (50,000 USDC senior)

Total USDC committed in the senior step: **50,000 USDC = `0x9_502F9000`**.

### Step 1 — `USDC.approve(IdleCDOEpochVariant, 50_000 USDC)`

Already covered by the bulk approval in Tx 5a (60k = 10k bootstrap + 50k senior). 50,000 USDC of allowance remained after Tx 5b. No additional approve needed.

### Step 2 — `IdleCDOEpochVariant.depositDuringEpoch(50_000 USDC, AATranche)`

Branch chosen: `isEpochRunning() == true && !isDepositDuringEpochDisabled` → **path B (`depositDuringEpoch`)**. `depositAA` would have reverted because the CDO is `whenNotPaused` and `paused() == true`.

| Field    | Value                                                                                                                           |
| -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| from     | caliber `0x5476…9083`                                                                                                           |
| to       | IdleCDOEpochVariant `0x433D…be4d`                                                                                               |
| selector | `0xc61e3faa` (`depositDuringEpoch(uint256,address)`)                                                                            |
| calldata | `0xc61e3faa` `+ 000…0ba43b7400` (`_amount = 50_000_000_000`) `+ 000…c26a6fa2c37b38e549a4a1807543801db684f99c` (`_tranche = AA`) |
| tx_hash  | `0x4b251bda8dd3cd97d23304e141458ff2eabdb7bf7c96b79c01234f5303421be0`                                                            |
| status   | success                                                                                                                         |

**Balance sandwich on AA**:

| Read                      | Before                 | After                            | Δ                    |
| ------------------------- | ---------------------- | -------------------------------- | -------------------- |
| `AA.balanceOf(caliber)`   | `0`                    | `46_248_053_071_620_145_300_311` | **`+46,248.053 AA`** |
| `USDC.balanceOf(caliber)` | `90_000_000_000` (90k) | `40_000_000_000` (40k)           | `-50,000 USDC`       |
| `tranchePrice(AA)`        | `1_074_982`            | `1_074_982`                      | unchanged            |

Mid-epoch effective USDC/AA: `50_000 / 46_248.053 ≈ 1.08125 USDC per AA`. The implicit discount vs. the sync price of `1.074982 USDC per AA` (~0.6%) reflects Pareto's mid-epoch mint formula:

```
minted = (_amount + trancheInterest) * trancheTotSupply / expectedFinal
```

Pareto's 32.3-day epoch with ~4.5 days remaining at deposit time → late-depositors miss most of the locked interest, so they get fewer AA shares per USDC compared to the next sync mint.

### Step 3 — `AA.approve(RoycoSeniorTranche, 46_248.053 AA)`

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| from     | caliber                                                              |
| to       | AA tranche `0xc26a…f99c`                                             |
| selector | `0x095ea7b3` (`approve(address,uint256)`)                            |
| spender  | `0x694ADB3077BBecE31882B6d6A74fc4A4fA6a754b` (Royco ST)              |
| amount   | `46_248_053_071_620_145_300_311`                                     |
| tx_hash  | `0x9759043d76cb575d90d59bb0fee519eee2761b01eac6401b78db4b10599b2e61` |
| status   | success                                                              |

### Step 4 — `RoycoSeniorTranche.deposit(46_248.053 AA, caliber)`

| Field                | Value                                                                |
| -------------------- | -------------------------------------------------------------------- |
| from                 | caliber                                                              |
| to                   | Royco ST `0x694A…754B`                                               |
| selector             | `0x6e553f65` (`deposit(uint256,address)`)                            |
| `_assets`            | `46_248_053_071_620_145_300_311`                                     |
| `_receiver`          | caliber                                                              |
| calldata             | `0x6e553f65` `+ 000…9cb1caac3f3a40a4357` `+ 000…5476F4…9083`         |
| tx_hash              | `0x7521a4f9aa17e9bb18078fc487686c53930ebaafaf6a8978a7d7b3a183e5e8fd` |
| status               | success                                                              |
| gas used (top frame) | 320,812                                                              |

**Internal call trace highlights** (from `getVnetSimulationCallTrace`):

```
caliber
 └── RoycoSeniorTranche.deposit (proxy 0x694A…754B → impl 0x98dF…4bba via DELEGATECALL)
      ├── RoycoFactory.canCall(...)            (StaticCall to AccessManager → impl 0x34DB…be77)
      ├── AA.transferFrom(caliber, Kernel, 46,248.053 AA)
      └── RoycoKernel.stDeposit(...)           (proxy 0x15bb…1791 → impl 0xAA96…7e1e)
           ├── IdleCDOEpochVariant.tranchePrice(AA)        (StaticCall, reads accounting)
           ├── IdleCreditVault.balanceOf / unscaledApr / pendingWithdraws  (Static reads)
           ├── AA.balanceOf(Kernel)                        (Static, post-pull supply)
           └── RoycoAccountant.postOpSyncTrancheAccountingAndEnforceCoverage(ST_DEPOSIT, stRawNAV', jtRawNAV')
                (impl proxy 0x37543d7c… → 0x288bc6a8…c110)
                returns SyncedAccountingState — coverage now passes because jtRawNAV > 0
```

### Final balances

```
ROY-ST.balanceOf(caliber) = 49_715_824_587_036_367_035_218     (49,715.8246 ST shares)
ROY-ST.totalSupply()       = 49_715_824_587_036_367_035_218     (caliber owns 100%)
ROY-JT.balanceOf(caliber)  = 9_943_166_086_465_828_358_521      (9,943.166 JT — slightly above the bootstrap value because the post-deposit sync accrued JT NAV)
ROY-JT.totalSupply()       = 9_943_166_086_465_828_358_521
AA.balanceOf(caliber)      = 0
AA.balanceOf(Kernel)       = 55_497_664_773_458_714_093_576     (≈ 55,497.66 AA = bootstrap 9,249.61 + senior 46,248.053)
USDC.balanceOf(caliber)    = 40_000_000_000                      (40,000 USDC — 60k consumed: 10k JT + 50k ST)
tranchePrice(AA)           = 1_074_982                           (unchanged across all 4 deposit steps)
```

### Sanity check — `convertToAssets(stShares)` 3-tuple

```
input  : stShares = 49_715_824_587_036_367_035_218
return : (stAssets, jtAssets, nav) =
         (46_248_053_071_620_145_300_309,
          0,
          49_715_824_587_036_367_035_217)   // USD WAD
```

- `stAssets = 46,248.053 AA` — 2-wei dust below the AA actually pulled from the caliber (ST `(totalSupply+1)/(navToMintAt+1)` rounding artifact, identical pattern to syrupUSDC ST). Asset-space NAV via `stAssets * tranchePrice(AA) / 1e18 = 49,715.824587 USDC`.
- `jtAssets = 0` — junior NAV is held by the JT tranche, not redeemable to senior holders in steady state.
- `nav = 49,715.824587 USD` (WAD) — matches the asset-space conversion exactly (no truncation here because tranchePrice is exact 6-dec).

**Effective USDC price per ST share**: `50,000 / 49,715.824587 = 1.005715 USDC/ST share`. The 0.57% premium vs. par is the same mid-epoch discount captured at the AA layer — the senior holder paid 50k USDC up-front for a position currently worth 49,716 USDC at the kernel's chosen AA price oracle. Once the epoch closes (`stopEpoch` → `_updateAccounting`), the AA price re-marks to the post-epoch interest level and this premium is recovered.

### Events emitted (from senior `ST.deposit` tx, decoded by signature inference from the trace)

The Tenderly events endpoint returned empty `name` fields for every log (the unverified RoycoSeniorTranche/Kernel/Accountant impls have no symbol DB on Tenderly). The events were inferred from the call trace structure:

| # | Emitter            | Event                                                             | Data                                                                          |
| - | ------------------ | ----------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| 1 | AA `0xc26a…f99c`   | `Approval(caliber, ROY_ST, 0)`                                    | (allowance reset to 0 after consumed transferFrom)                            |
| 2 | AA                 | `Transfer(caliber, Kernel, 46_248.053…)`                          | matches `safeTransferFrom(msg.sender, KERNEL, _assets)`                       |
| 3 | RoycoFactory       | (none — `canCall` is view)                                        | —                                                                             |
| 4 | RoycoSeniorTranche | `Deposit(caliber, caliber, 46_248.053… AA, 49_715.824… shares)`   | matches the documented `emit Deposit(msg.sender, _receiver, _assets, shares)` |
| 5 | RoycoSeniorTranche | `Transfer(0x0, caliber, 49_715.824… shares)`                      | mint                                                                          |
| 6 | RoycoKernel        | `SyncedAccountingState(...)` (or similar — exact name unverified) | post-op coverage state                                                        |

The `AA: caliber → Kernel` and `ROY-ST mint: 0 → caliber` flows match `flows.deposit.events_to_monitor` in `specs.yaml`. There is **no** `AA: 0 → caliber` mint Transfer in the senior step (the AA was minted in the earlier `depositDuringEpoch` step) and no `Transfer(caliber, RoycoKernel, aaMinted)` because it is consolidated with the ST `deposit` `transferFrom` — the spec's `events_to_monitor` listing of "AA.Transfer(0x0, caliber, aaMinted) # mint via IdleCDO" applies to step 2 (Pareto deposit), and "AA.Transfer(caliber, RoycoKernel, aaMinted) # ST pulls into kernel" applies to step 4 (Royco ST deposit).

---

## Reverts encountered: none

Every transaction in the deposit chain succeeded on the first attempt. The two protocol-level pitfalls flagged in the spec (Keyring gate, Royco AccessManager gate) were already cleared on mainnet for this caliber, leaving only the junior bootstrap to set up.

The expected revert path that was AVOIDED:

- If the caliber had attempted `RoycoSeniorTranche.deposit(...)` against the empty kernel (`jtRawNAV == 0` and `stRawNAV == 0` pre-bootstrap), the call would have hit `RoycoAccountant.postOpSyncTrancheAccountingAndEnforceCoverage(ST_DEPOSIT, ...)` and reverted because `coveredExposure / jtEffectiveNAV` is undefined when the divisor is 0 (per the doc-comment math in `RoycoKernel._computeMaxUtilizationNeutralBonus`). The exact custom error string cannot be confirmed from the unverified accountant impl. The bootstrap step neutralised this.
- `depositAA(50_000 USDC)` — would have reverted with `"Pausable: paused"` because the CDO is paused for the duration of the running epoch.

---

## Summary table for the blueprint-writer

| # | Action                                                                                                                         | Contract                          | Selector                    | Inputs                                                       | Output observation                                                     |
| - | ------------------------------------------------------------------------------------------------------------------------------ | --------------------------------- | --------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------- |
| 1 | `USDC.approve(spender=IdleCDOEpochVariant, amount=50_000e6)`                                                                   | USDC `0xA0b8…eB48`                | `0x095ea7b3`                | spender=`0x433D…be4d`, amount=50_000_000_000                 | allowance set                                                          |
| 2 | branch on `isEpochRunning()` → `depositDuringEpoch(amount, AATranche)` (this fork) **or** `depositAA(amount)` (between epochs) | IdleCDOEpochVariant `0x433D…be4d` | `0xc61e3faa` / `0xb450dfce` | _amount=50_000_000_000; _tranche=`0xc26a…f99c` (path B only) | sandwich `AA.balanceOf(caliber)` to capture mint (here +46_248.053 AA) |
| 3 | `AA.approve(spender=RoycoST, amount=aaMinted)`                                                                                 | AA `0xc26a…f99c`                  | `0x095ea7b3`                | spender=`0x694A…754B`, amount=aaMinted                       | allowance set                                                          |
| 4 | `RoycoST.deposit(aaMinted, caliber)`                                                                                           | Royco ST `0x694A…754B`            | `0x6e553f65`                | _assets=46_248_053_071_620_145_300_311, _receiver=caliber    | `ROY-ST.balanceOf(caliber)` = +49_715.824 ST shares                    |

Aggregate accounting:

- **50,000 USDC in → 49,715.82 USDC equivalent (asset-space, post-sync NAV)**
- 1 ST share == 1 / 49,715.824587 of the senior position == backed by `46,248.053 / 49,715.824587 = 0.93005 AA per ST share` at this snapshot.

All reads, all selectors, all calldata, and all transitions match the `flows.deposit` Path B description in `specs.yaml`. The only deviation worth flagging in the blueprint runbook is the **junior bootstrap precondition** — the caliber's deposit blueprint will revert in production if Royco/Pareto have not seeded the junior tranche before the senior is activated.
