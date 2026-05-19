# Execution Report — Royco ST Pareto FalconX (account)

## Fork (reused from deposit stage — NOT recreated)

| Key                              | Value                                                                             |
| -------------------------------- | --------------------------------------------------------------------------------- |
| `vnet_id`                        | `5b132729-f79a-4ffc-8d2f-33bac4dc23f9`                                            |
| `rpc_url` (admin)                | `https://virtual.mainnet.eu.rpc.tenderly.co/4ed6c929-bd54-4f22-a18d-aa575d39b78d` |
| Fork chain                       | Ethereum mainnet (chain_id 1)                                                     |
| Initial fork block               | `0x17d5d55` (24,992,981)                                                          |
| Block at this stage's first read | 24,993,119 (heads naturally advanced from deposit chain)                          |

Action: **account**
Caliber under test: `0x5476F4E23dAA093Ce6700e1026013c55F7AF9083` (intMkSrRoyUSDC mainnet caliber)

ST balance carried over from deposit stage: **49,715.824587 ST shares** (`49_715_824_587_036_367_035_218`).

---

## Methodology

Followed the **9-step asset-space** algorithm in `SUMMARY.md` plus the two comparison paths (NAV/1e12, simple-stAssets-only) requested. To answer the "is `syncTrancheAccounting()` strictly required?" question, took a fork snapshot, called `convertToAssets` BEFORE syncing, then called `syncTrancheAccounting()`, then re-called `convertToAssets`, then advanced time +1h and re-called once more, finally reverted the snapshot to keep the post-deposit state pristine for the withdraw stage.

Snapshot lifecycle:

- `evm_snapshot` → `0x900217a2a8365d8148d7521131bc8d0e51cf0c270ea2312ed55fd34c7f7c1db4`
- ran sync + reads
- `evm_revert` of the same snapshot id → returned `true`
- post-revert verified: `ST.balanceOf(caliber) == 49_715_824_587_036_367_035_218`, block height back to `24,993,119`.

---

## On-chain reads (asset-space algorithm)

### Step 1 — `ST.balanceOf(caliber)`

| Field            | Value                                                                        |
| ---------------- | ---------------------------------------------------------------------------- |
| to               | Royco ST `0x694ADB3077BBecE31882B6d6A74fc4A4fA6a754b`                        |
| selector         | `0x70a08231`                                                                 |
| calldata         | `0x70a082310000000000000000000000005476f4e23daa093ce6700e1026013c55f7af9083` |
| return (uint256) | `49715824587036367035218` (≈ **49,715.824587 ST shares**, 18-dec)            |

### Step 2 — `Kernel.syncTrancheAccounting()` (state-mutating, called once)

| Field    | Value                                                                                                                                                                        |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| from     | caliber `0x5476…9083` (must hold the kernel's `sync` role — verified in the deposit stage: `RoycoFactory.canCall(caliber, Kernel, syncTrancheAccounting) == (true, 0)`)      |
| to       | RoycoKernel `0x15bb63C07740ff972F76716cAcC5766f0C641791`                                                                                                                     |
| selector | `0x9c8e2dc0`                                                                                                                                                                 |
| calldata | `0x9c8e2dc0` (no args)                                                                                                                                                       |
| tx_hash  | `0x8fc97d9b77fcdc80f31471196a11063f86261e5c7588fe1328f13a2fa2f60bf9`                                                                                                         |
| status   | success                                                                                                                                                                      |
| gas used | 189,506 (`0x2e642`)                                                                                                                                                          |
| events   | 3 logs from the kernel + accountant impls (event names not in Tenderly's symbol DB — `0xed36d3…` from impl `0x37543d7c…` carries the new `(stRawNAV, jtRawNAV)`-style words) |

### Step 3 — `ST.convertToAssets(stShares)` (the 3-tuple)

| Field       | Value                                                                                                          |
| ----------- | -------------------------------------------------------------------------------------------------------------- |
| to          | Royco ST `0x694A…754B`                                                                                         |
| selector    | `0x07a2d13a`                                                                                                   |
| calldata    | `0x07a2d13a000000000000000000000000000000000000000000000a8719aa102e8df89b52`                                   |
| return type | `(uint256 stAssets, uint256 jtAssets, uint256 nav)` — 18-dec AA / 18-dec AA / 18-dec USD WAD                   |
| stAssets    | `46248053071620145300309` (≈ **46,248.053072 AA**)                                                             |
| jtAssets    | `0`                                                                                                            |
| nav         | `49715824587036367035217` (≈ **49,715.824587 USD WAD**, 1 wei below `stAssets * tranchePrice / 1e18` rounding) |

### Step 4 — `AA.balanceOf(caliber)` (stranded AA)

| Field    | Value                                                                                                                                      |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| to       | AA tranche `0xc26a6fa2c37b38e549a4a1807543801db684f99c`                                                                                    |
| selector | `0x70a08231`                                                                                                                               |
| calldata | `0x70a082310000000000000000000000005476f4e23daa093ce6700e1026013c55f7af9083`                                                               |
| return   | `0` — caliber holds no stranded AA after the deposit chain (all AA was consumed by `RoycoST.deposit` + the JT-bootstrap `RoycoJT.deposit`) |

### Step 5 — `total_aa`

```
total_aa = stAssets + jtAssets + stranded_aa
        = 46_248_053_071_620_145_300_309 + 0 + 0
        = 46_248_053_071_620_145_300_309   (18-dec AA)
```

### Step 6 — `IdleCDOEpochVariant.tranchePrice(AA)`

| Field    | Value                                                                                             |
| -------- | ------------------------------------------------------------------------------------------------- |
| to       | IdleCDOEpochVariant `0x433D5B175148dA32Ffe1e1A37a939E1b7e79be4d`                                  |
| selector | `0xa219d218`                                                                                      |
| calldata | `0xa219d218000000000000000000000000c26a6fa2c37b38e549a4a1807543801db684f99c`                      |
| return   | `1074982` (USDC-6dec per 1e18 AA) — i.e. **1 AA ≈ 1.074982 USDC** at the current Pareto sync mark |

The tranche price is a pure on-chain view (`virtualPrice / lastNAVAA` style read on `IdleCDOEpochVariant`'s verified impl) — **no prior state mutation required**. Returned the same value before sync, after sync, and after a +1h time advance with no further sync. This is independent of the Royco kernel's accounting; Pareto's price only re-marks on `stopEpoch` / `startEpoch`.

### Step 7 — `usdc_from_aa`

```
usdc_from_aa = total_aa * tranche_price / 1e18
            = 46_248_053_071_620_145_300_309 * 1_074_982 / 10**18
            = 49_715_824_587_036_367_035_216_769_438 / 10**18
            = 49_715_824_587   (rounding-down truncation, residue = 36_367_035_216_769_438)
```

i.e. **49,715.824587 USDC**.

### Step 8 — `FalconXUSDC.balanceOf(caliber)` (pending withdraw receipt)

| Field    | Value                                                                             |
| -------- | --------------------------------------------------------------------------------- |
| to       | IdleCreditVault `0x17E9Ab2992dfecBe779a06A92a6cDB9fE6aEeEf3` (FalconXUSDC, 6-dec) |
| selector | `0x70a08231`                                                                      |
| calldata | `0x70a082310000000000000000000000005476f4e23daa093ce6700e1026013c55f7af9083`      |
| return   | `0`                                                                               |

`pending_usdc == 0` as expected — no `requestWithdraw` has been issued on this fork yet (the withdraw stage will exercise this leg).

### Step 9 — `total_usdc` (asset-space final)

```
total_usdc = usdc_from_aa + pending_usdc
          = 49_715_824_587 + 0
          = 49_715_824_587   (USDC 6-dec)
          = 49_715.824587 USDC
```

---

## Comparison: the three paths

All three are computed against the same on-chain state captured above.

| Path                     | Formula                                                                        | Result (USDC raw 6-dec) | USDC          | Δ vs. asset-space |
| ------------------------ | ------------------------------------------------------------------------------ | ----------------------- | ------------- | ----------------- |
| A — Asset-space (full)   | `(stAssets + jtAssets + stranded_aa) * tranchePrice / 1e18 + pending_usdc`     | `49_715_824_587`        | 49,715.824587 | 0 wei             |
| B — NAV path             | `nav / 1e12` (WAD → 6dec)                                                      | `49_715_824_587`        | 49,715.824587 | 0 wei             |
| C — Simple stAssets-only | `stAssets * tranchePrice / 1e18` (ignores jtAssets, stranded_aa, pending_usdc) | `49_715_824_587`        | 49,715.824587 | 0 wei             |

**All three paths agree to the wei at this snapshot.** The deltas are all zero because:

- `jtAssets == 0` (the senior tranche by construction never owns junior NAV — the junior NAV sits on `RoycoJuniorTranche`, not on the senior holder)
- `stranded_aa == 0` (the deposit blueprint atomically pulls every minted AA into the kernel; the only way to have `AA.balanceOf(caliber) > 0` would be a half-finished deposit or a bug)
- `pending_usdc == 0` (no withdraw has been requested)
- The `nav / 1e12` truncation residue (`36_367_035_217`) and the `stAssets * tranchePrice / 1e18` truncation residue (`36_367_035_216_769_438` / 1e18 ≈ `36_367_035_216`) happen to round to the same 6-dec floor at this particular share count.

### Internal consistency cross-check

Asset-space → NAV check:

```
stAssets * tranchePrice / 1e18 = 46_248_053_071_620_145_300_309 * 1_074_982 / 1e18
                              = 49_715_824_587 (USDC 6-dec)
                              = 49_715_824_587_000_000_000_000 (WAD)
nav (returned by kernel)        = 49_715_824_587_036_367_035_217 (WAD)
Δ                               = +36_367_035_217 wei in WAD = +0 wei in USDC after /1e12 floor
```

The kernel's `nav` carries 12 extra significant digits (residual stAssets-fraction × tranchePrice modulo 1e18) that are exactly the bits the `nav / 1e12` floor truncates. Both paths converge on the same 6-dec USDC integer.

---

## Sync requirement — is `syncTrancheAccounting()` actually load-bearing here?

Tested empirically on the fork (with snapshot/revert):

| Sequence                                                                               | `convertToAssets(stShares)` returned `(stAssets, jtAssets, nav)`      |
| -------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Pre-sync (fork at deposit-block, never re-synced after deposit stage)                  | `(46_248_053_071_620_145_300_309, 0, 49_715_824_587_036_367_035_217)` |
| Immediately after `Kernel.syncTrancheAccounting()` (same block as the sync tx)         | `(46_248_053_071_620_145_300_309, 0, 49_715_824_587_036_367_035_217)` |
| Same fork, **second** call without re-sync, +1h `evm_increaseTime` and one mined block | `(46_248_053_071_620_145_300_309, 0, 49_715_824_587_036_367_035_217)` |

**On this fork the three reads are bit-identical.** This is because the deposit transaction itself ended with `RoycoAccountant.postOpSyncTrancheAccountingAndEnforceCoverage(...)` (visible in the deposit-stage call trace), which already brought kernel accounting current as of the deposit block. No yield has accrued in the interim — Pareto's epoch-priced AA does not re-mark between sync events, and the +1h time travel doesn't move `tranchePrice`, so the senior NAV stays flat.

**However**, this does NOT mean the blueprint can drop the sync. Two cases force a sync:

1. **Multiple blocks since the last sync, with junior-side activity in between.** `RoycoKernel.stRawNAV` and `jtRawNAV` are stored values updated only on every `*-deposit / *-redeem / requestWithdraw / claim / stopEpoch / sync` op. Between such events, off-chain state (Pareto epoch maturing, `tranchePrice` stepping after a `stopEpoch`) can render the stored NAVs stale. Reading `convertToAssets` against stale state returns the last-marked answer, which under-reports gain or under-counts loss.
2. **Cross-tranche exposure netting.** The accountant's max-utilization-neutral bonus formula (`_computeMaxUtilizationNeutralBonus`) re-weights senior vs. junior NAV using the **current** `tranchePrice(AA)`. If `tranchePrice` has advanced (epoch closed), the kernel's stored `stRawNAV` can lag the kernel's view of how much senior NAV the AA pool actually backs. `syncTrancheAccounting()` is the cheap way to force the kernel to re-read `tranchePrice` and re-apply the netting before the caliber's accounting read.

**Recommendation for the blueprint**: include the sync as the **first** step of every `account` call, before any `convertToAssets`. Cost is ~190k gas, single block, no input args, no failure mode (the role check passed unconditionally on the deposit stage and the sync function has no other external dependencies). The cost is dwarfed by the risk of accruing silent NAV drift across infrequent accounting ticks.

---

## Edge-case probes

### `ST.convertToAssets(0)`

| Input          | Output                            |
| -------------- | --------------------------------- |
| `stShares = 0` | `(stAssets=0, jtAssets=0, nav=0)` |

Sanity passes — no surprise reverts on the zero-share path.

### `tranchePrice(AA)` callability

`tranchePrice` is a pure on-chain view on `IdleCDOEpochVariant`'s verified implementation. Tested before sync, after sync, after time advance — always returns `1_074_982`. **Does not require any prior state mutation.** This means the blueprint's accounting flow could safely call `tranchePrice` BEFORE `syncTrancheAccounting` if we want to parallelize / batch reads — though in practice the order in `SUMMARY.md` (sync → convertToAssets → tranchePrice → balances) is fine and is what the deposit chain established at deposit-block.

### Idempotency of `convertToAssets` within a block

Two back-to-back `convertToAssets(stShares)` calls in the same block (no intervening tx) returned identical bytes. The kernel's `convertToAssets` is a pure view function over the stored `stRawNAV` / `jtRawNAV`; it does not lazy-update. This rules out the "non-deterministic read" failure mode that would have made batching multiple accounting reads in a single multicall unsafe.

---

## Recommendation: which path should the blueprint use?

**Use Path A (asset-space, full).**

Reasoning:

1. **Deltas are zero today, but only by coincidence.** The numerical equivalence between A, B, C above depends on `jtAssets == 0` and `stranded_aa == 0`, which are both _invariants of the deposit blueprint as written_, not protocol invariants. If a future deposit blueprint variant ever leaves stranded AA on the caliber (e.g. partial-fill `depositDuringEpoch` if Pareto adds caps), Path B and Path C will silently under-report. Path A's `+ stranded_aa * tranchePrice` term picks it up automatically.
2. **`pending_usdc` term must be present once withdraw is wired in.** During the multi-week window between `requestWithdraw` and `claimWithdrawRequest` the caliber holds the FalconXUSDC receipt instead of AA. Neither Path B (the kernel's `nav` doesn't include the receipt — the AA was burned) nor Path C captures that. **Only Path A is correct during withdraw.** This is the same reason `SUMMARY.md` calls out the asset-space path.
3. **Path B's WAD→6dec truncation is harmless on this share count but compounds.** With `nav = stAssets * tranchePrice + ε` the residue is ≤ 1 wei in USDC at the snapshot above. But on a heavier balance with more `tranchePrice` resolution, B starts losing 1-wei more than A. The syrupUSDC ST integration explicitly cited this as the reason to migrate to asset-space — same playbook applies here.
4. **Path C (simple stAssets-only) is the most fragile.** It works only when (a) `jtAssets == 0` and (b) no `stranded_aa` and (c) no `pending_usdc`. Conditions (a) holds in steady state; (b) holds for the deposit blueprint as designed; (c) fails for the entire withdraw window. Not viable.

**Concrete blueprint sequence**:

```
1. CALL  Kernel.syncTrancheAccounting()                               (state)
2. STATIC ST.balanceOf(caliber)                          -> st_shares
3. STATIC ST.convertToAssets(st_shares)                  -> (stA, jtA, nav)        [3-tuple, weiroll word 0,1,2]
4. STATIC AA.balanceOf(caliber)                          -> stranded_aa
5. STATIC IdleCDOEpochVariant.tranchePrice(AA)           -> p
6. STATIC FalconXUSDC.balanceOf(caliber)                 -> pending
7. compute total_aa = stA + jtA + stranded_aa            (MathHelper.add x2)
8. compute usdc_from_aa = total_aa * p / 1e18            (MathHelper.mulDiv)
9. compute total_usdc = usdc_from_aa + pending           (MathHelper.add)
10. return total_usdc as accountant.value (USDC 6-dec)
```

Every output above can be carried in a 32-byte weiroll register; the 3-tuple `convertToAssets` shape is decoded with the existing `getTupleWord(bytes,uint256)` helper (same pattern used by syrupusdc / stcusd).

---

## Final state-changes recap

After this stage's `evm_revert` to the pre-sync snapshot, the fork is **byte-identical** to the post-deposit state:

| Read                             | Value                            | Note                                                                                                                          |
| -------------------------------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `ST.balanceOf(caliber)`          | `49_715_824_587_036_367_035_218` | unchanged from deposit                                                                                                        |
| `AA.balanceOf(caliber)`          | `0`                              | unchanged                                                                                                                     |
| `FalconXUSDC.balanceOf(caliber)` | `0`                              | unchanged                                                                                                                     |
| `tranchePrice(AA)`               | `1_074_982`                      | unchanged                                                                                                                     |
| Block height                     | `24,993,119`                     | matches the post-deposit fork tip — the snapshot was taken before the sync tx, so the sync tx's block was discarded on revert |

The withdraw stage can resume on this fork with the deposit-state intact.

---

## Summary table for the blueprint-writer

| # | Action                                 | Contract                                     | Selector     | Calldata template                    | Return                                              |
| - | -------------------------------------- | -------------------------------------------- | ------------ | ------------------------------------ | --------------------------------------------------- |
| 1 | `Kernel.syncTrancheAccounting()`       | `0x15bb63C07740ff972F76716cAcC5766f0C641791` | `0x9c8e2dc0` | `0x9c8e2dc0`                         | (state mutation)                                    |
| 2 | `ST.balanceOf(caliber)`                | `0x694ADB3077BBecE31882B6d6A74fc4A4fA6a754b` | `0x70a08231` | `0x70a08231` + caliber               | `uint256 st_shares`                                 |
| 3 | `ST.convertToAssets(st_shares)`        | `0x694A…754B`                                | `0x07a2d13a` | `0x07a2d13a` + st_shares             | `(uint256 stAssets, uint256 jtAssets, uint256 nav)` |
| 4 | `AA.balanceOf(caliber)`                | `0xc26a6fa2c37b38e549a4a1807543801db684f99c` | `0x70a08231` | `0x70a08231` + caliber               | `uint256 stranded_aa`                               |
| 5 | `IdleCDOEpochVariant.tranchePrice(AA)` | `0x433D5B175148dA32Ffe1e1A37a939E1b7e79be4d` | `0xa219d218` | `0xa219d218` + AA addr `0xc26a…f99c` | `uint256 tranche_price` (USDC-6dec / 1e18 AA)       |
| 6 | `FalconXUSDC.balanceOf(caliber)`       | `0x17E9Ab2992dfecBe779a06A92a6cDB9fE6aEeEf3` | `0x70a08231` | `0x70a08231` + caliber               | `uint256 pending_usdc`                              |

Final calc: `total_usdc = ((stAssets + jtAssets + stranded_aa) * tranche_price / 1e18) + pending_usdc`. Result is **USDC, 6-dec**, ready to flow to the accountant's value register.

At the snapshot used for this report: **`total_usdc = 49,715.824587 USDC`** (`49_715_824_587` raw 6-dec) for the caliber's `49,715.824587 ST shares` (50,000 USDC originally deposited; the ~0.57% par-discount is the live mid-epoch AA mint premium that the next `stopEpoch` will recover).
