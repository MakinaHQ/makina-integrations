# Execution Report — Royco JT Pareto FalconX (account, DUSD machine)

## Fork

| Key                   | Value                                                                                      |
| --------------------- | ------------------------------------------------------------------------------------------ |
| `vnet_id`             | `b0f9ddf1-1525-4bd6-9359-90dcf602ab12`                                                     |
| `rpc_url` (admin)     | `https://virtual.mainnet.eu.rpc.tenderly.co/aca6b043-1c2a-4efa-9f9e-a5c15d84fe93`          |
| Fork chain            | Ethereum mainnet (chain_id 1)                                                              |
| Reverted from         | post-deposit snapshot `0xe0637769e9512a19d07bd84d54e598efea3047386643fa6ca6d344e83232de6f` |
| Post-account snapshot | `0x259d550498f35c0f19d09664b5fcfb13557cf05f4a4bf8f6aac17f2a01afe224`                       |
| Current block         | `0x17f7945` (25,131,333)                                                                   |
| Caliber under test    | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (DUSD mainnet caliber)                        |

> Note: the auto-incrementing fork clock advanced ~9.2 days between the deposit recipe (block timestamp `1,778,420,251`) and the time the snapshot was reverted (block timestamp `1,779,218,563`). That accrued ~205 JT shares of compounded fee mint on top of the originally observed 49,648.7731. Pre-state is therefore measured at the snapshot's post-revert reading, NOT verbatim from `execution-deposit.md`.

---

## Pre-state at the reverted snapshot (no `syncTrancheAccounting` yet)

| Read                             | Selector     | Contract                  | Result (raw hex)                                    | Decoded                                                    |
| -------------------------------- | ------------ | ------------------------- | --------------------------------------------------- | ---------------------------------------------------------- |
| `JT.balanceOf(caliber)`          | `0x70a08231` | ROY-JT `0x8e0e…1a6d`      | `0xa8e90afcd4b596757ef`                             | `49,853,528,264,549,100,640,239` (`49,853.5283 JT shares`) |
| `AA.balanceOf(caliber)`          | `0x70a08231` | AA `0xc26a…f99c`          | `0x0`                                               | `0` (no stranded AA)                                       |
| `FalconXUSDC.balanceOf(caliber)` | `0x70a08231` | FalconXUSDC `0x17E9…eEf3` | `0x0`                                               | `0` (no pending withdraw receipt)                          |
| `USDC.balanceOf(caliber)`        | `0x70a08231` | USDC `0xA0b8…eB48`        | `0x0`                                               | `0`                                                        |
| `JT.totalSupply()`               | `0x18160ddd` | ROY-JT                    | `0xa8e90afcd4b596757ef`                             | `49,853.5283 JT` (caliber owns 100%)                       |
| `JT.totalAssets()` (3-tuple)     | `0x01e1d114` | ROY-JT                    | `(0, 0x9c184d5783c5bccbaf6, 0xa8e90afcd4b596757ef)` | `(0, 46,071.0916 AA, 49,853.5283 USD-WAD)`                 |
| `ST.totalSupply()`               | `0x18160ddd` | ROY-ST `0x694A…754B`      | `0x0`                                               | `0` (ST tranche empty on this fork)                        |
| `tranchePrice(AA)`               | `0xa219d218` | CDO `0x433D…be4d`         | `0x1082f4`                                          | `1,082,100` (USDC-6 per 1e18 AA)                           |

> Empirical baseline: JT is the only tranche populated on this fork; no AA stranded; no FalconXUSDC pending. Caliber's full position lives in JT shares.

---

## Step 1: `Kernel.syncTrancheAccounting()` from the caliber

State-changing entrypoint. Caliber executes it (already has the shared `KERNEL_SYNC` role id `15053450870919821405`).

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| from     | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (DUSD caliber)          |
| to       | Royco Kernel `0x15bb63C07740ff972F76716cAcC5766f0C641791`            |
| selector | `0x9c8e2dc0` (`syncTrancheAccounting()`)                             |
| tx_hash  | `0x28b8d86de0585729f39b1880adc270a6a9b68240b76124987275788c093c0428` |
| status   | success                                                              |

**Empirical observation**: in this state (no time elapsed in the same block between the deposit-time mint sync and this sync), `syncTrancheAccounting()` does NOT change the subsequent reads — `JT.convertToAssets(jtShares)`, `JT.totalSupply()`, `JT.balanceOf(caliber)`, and `tranchePrice(AA)` are byte-identical before and after the call (multicall results above and below match). This matches the documented "no-op when the same block already synced" idempotence behaviour from `functions.md` §4 of the ST sibling.

The blueprint still MUST call `syncTrancheAccounting()` because the read-time block is generally NOT the deposit-time block — yield accrues and protocol fees mint between caliber transactions.

---

## Step 2: post-sync reads (the actual accounting inputs)

| Read                                      | Contract    | Result (raw hex)                                    | Decoded                                                          |
| ----------------------------------------- | ----------- | --------------------------------------------------- | ---------------------------------------------------------------- |
| `JT.balanceOf(caliber)`                   | ROY-JT      | `0xa8e90afcd4b596757ef`                             | `49,853.5283 JT shares` (= `jt_shares`)                          |
| `JT.convertToAssets(jt_shares)` (3-tuple) | ROY-JT      | `(0, 0x9c184d5783c5bccbaf5, 0xa8e90afcd4b596757ee)` | `(stAssets=0, jtAssets=46,071.0916 AA, nav=49,853.5283 USD-WAD)` |
| `AA.balanceOf(caliber)`                   | AA tranche  | `0x0`                                               | `0`                                                              |
| `tranchePrice(AA)`                        | CDO         | `0x1082f4`                                          | `1,082,100` (USDC-6 per 1e18 AA)                                 |
| `FalconXUSDC.balanceOf(caliber)`          | FalconXUSDC | `0x0`                                               | `0`                                                              |

The relevant 3-tuple words (per `Types.sol.AssetClaims`, `struct AssetClaims { TRANCHE_UNIT stAssets; TRANCHE_UNIT jtAssets; NAV_UNIT nav; }`):

```
slot 0 (stAssets) = 0
slot 1 (jtAssets) = 46_071_091_640_836_429_757_173       // 18-dec AA — the JT's own AA claim
slot 2 (nav)      = 49_853_528_264_549_100_640_238       // 18-dec USD WAD
```

---

## Slot resolution — DEFINITIVE

Stage 1 had claimed `JT.convertToAssets(jt_shares)` index 0 was the JT's own AA claim (slot 0). Stage 2 deposit observed slot 0 = 0 and slot 1 = JT's claim. The two recipes were both correct empirically — what differed was their interpretation. **This account stage resolves the question definitively**.

### Method 1 — direct kernel `previewSyncTrancheAccounting(TrancheType)`

The kernel exposes the authoritative source of `_deriveTrancheAssetClaims(...)`:

```solidity
function previewSyncTrancheAccounting(TrancheType _trancheType)
    public view
    returns (SyncedAccountingState memory state, AssetClaims memory claims, uint256 totalTrancheShares);
```

It is the same code path `RoycoVaultTranche._previewPostSyncTrancheState()` uses to feed `convertToAssets`.

Reading on the **post-revert snapshot (ST empty, JT non-empty)**:

| call                                     | `claims.stAssets` (slot 0) | `claims.jtAssets` (slot 1)          | `claims.nav` (slot 2)            | `totalTrancheShares`                                       |
| ---------------------------------------- | -------------------------- | ----------------------------------- | -------------------------------- | ---------------------------------------------------------- |
| `previewSyncTrancheAccounting(SENIOR=0)` | 0                          | 0                                   | 0                                | 1                                                          |
| `previewSyncTrancheAccounting(JUNIOR=1)` | 0                          | `46,071,091,640,836,429,757,174 AA` | `49,853,528,264,549,100,640,239` | `49,853,528,264,549,100,640,240` (= jtShares + 1 fee dust) |

`previewSyncTrancheAccounting(JUNIOR=1)` returns:

```
claims = AssetClaims{
    stAssets = 0,
    jtAssets = 46,071.0916e18,   // 46071091640836429757174  <-- the JT's own AA claim
    nav      = 49,853.5283e18    // 49853528264549100640239
}
```

Then `convertToAssets(jtShares)` = `UtilsLib.scaleAssetClaims(claims, jtShares, totalTrancheShares)` ⇒ each field multiplied by `49853...239 / 49853...240`, which is essentially `1` with sub-wei rounding-down:

| field    | preview        | convertToAssets(shares) | matches?             |
| -------- | -------------- | ----------------------- | -------------------- |
| stAssets | `0`            | `0`                     | yes                  |
| jtAssets | `46,071...174` | `46,071...173` (−1 wei) | yes (Floor rounding) |
| nav      | `49,853...239` | `49,853...238` (−1 wei) | yes (Floor rounding) |

**Conclusion: `claims.jtAssets` is slot 1 of the ABI tuple, and `jtAssets` IS the JT's own AA-tranche claim.** The slot layout is **role-fixed**, not caller-relative.

### Method 2 — independent cross-check (bootstrap a small ST, re-read JT)

To rule out the alternative "calling-tranche convention" hypothesis from Stage 1, on the same fork I bootstrapped a small ST position and re-read `JT.convertToAssets`:

1. Funded caliber with 1,000 USDC (the only addition; JT position retained).
2. `USDC.approve(CDO, 1_000_000_000)` — tx `0xea8b209ba3969be9d770ccf9544afc83a8d6a8a355effec953e7e06b1851c115`.
3. `CDO.depositDuringEpoch(1_000 USDC, AATranche)` — tx `0x3f77337ff1b1f8443a3d3957ee469399b18abdb059b7cde9915725b7e0c65ad3`.
   - Caliber received `921.4203 AA` (18-dec).
4. `AA.approve(ROY_ST, 921.4203 AA)` — tx `0xcc8b2665cd003b5b9de84eb436c86ac940a5106d9b308fb57272bbfb4c2f1926`.
5. `ROY_ST.deposit(921.4203 AA, caliber)` — tx `0xb68a7113b684003e8bea0b1445282141a57050906962687d0ab505f387ff8220`. Coverage check passed because jtRawNAV (~49,853e18) is enormous vs. stRawNAV (~997e18).
6. State after ST bootstrap:
   - `ST.totalSupply` = `997.0689 ST` (caliber holds 100%)
   - `ST.totalAssets()` = `(921.4203 AA, 0, 997.0689 USD-WAD)` ⇒ ST's claim is in slot 0.
   - `ST.convertToAssets(ST_shares)` = `(921.4203 AA, 0, 997.0689 USD-WAD)` — same.
   - `JT.totalAssets()` = `(0, 46,071.0916 AA, 49,853.5283 USD-WAD)` — slot 0 still 0, slot 1 still has the JT's claim.
   - `JT.convertToAssets(JT_shares)` = `(0, 46,071.0916 AA, 49,853.5283 USD-WAD)` — slot 0 still 0.
   - `previewSyncTrancheAccounting(JUNIOR)`:
     - state.stRawNAV = 997.0689e18 (ST is now populated)
     - state.jtRawNAV = 49,853.5283e18
     - claims.stAssets = **0** (not the ST's AA claim!)
     - claims.jtAssets = `46,071.0916e18` (JT's claim, unchanged)
     - claims.nav = `49,853.5283e18`
   - `previewSyncTrancheAccounting(SENIOR)`:
     - claims.stAssets = `921.4203e18` (ST's claim)
     - claims.jtAssets = 0
     - claims.nav = `997.0689e18`

After the bootstrap, `JT.convertToAssets(jt_shares)` slot 1 is **unchanged** at `46,071.0916 AA`. Slot 0 stays at 0 — even though the ST tranche is now populated and holds 921 AA. So `claims.stAssets` returned to the JT does NOT mean "the ST tranche's AA holdings"; that field is reserved for senior write-down state (which is not active here). Slot 0 in the JT view stays `0` in the normal solvent state, regardless of ST size.

The bootstrap state was reverted via the snapshot, so the post-account snapshot is back to JT-only.

### Method 3 — `totalAssets()` cross-check (matches Stage 1's recipe)

`RoycoVaultTranche.totalAssets()` is equivalent to `convertToAssets(totalSupply())`. The Stage 1 spec used the identity `JT.totalSupply * slot0_per_share == JT.totalAssets()` to claim slot 0 was the JT's claim — but at fork `0x17d5e3b` the JT had ~9,951 shares from the ST sibling's bootstrap helper, and the ST had ~30,802 shares from prior ST testing.

If we apply the same identity on this fork at the post-revert snapshot:

- `JT.totalSupply()` = `49,853.5283 JT shares`
- `JT.totalAssets()` (3-tuple) = `(0, 46,071.0916 AA, 49,853.5283 USD-WAD)`
- `JT.totalAssets()[0]` = `0` — does **NOT** equal the JT's AA balance.
- `JT.totalAssets()[1]` = `46,071.0916 AA` — DOES equal the JT's own AA claim.

The Stage 1 reading must have been misindexed. **Slot 1 is the JT's own AA claim on both forks** — verified by source (`previewSyncTrancheAccounting(JUNIOR)` returns `claims.jtAssets` as slot 1, and the `Types.sol.AssetClaims` struct has `jtAssets` as the second field).

### Citation — `Types.sol.AssetClaims`

From `functions.md` §3.4 of this pool's working dir, with verbatim quote from the verified-twin sibling `0xd10deF48855fFbb525f23eBbd67bA19f94B80F9E` (Royco V2 syrupUSDC JT, Sourcify/Blockscout partial match, Sol 0.8.34):

```solidity
// src/libraries/Types.sol
struct AssetClaims {
    TRANCHE_UNIT stAssets;   // slot 0 in the ABI tuple
    TRANCHE_UNIT jtAssets;   // slot 1
    NAV_UNIT     nav;        // slot 2
}
```

The wire encoding `(uint256, uint256, uint256)` always serialises `stAssets` first, then `jtAssets`, then `nav`. The kernel's `_deriveTrancheAssetClaims(TrancheType, state)` populates this struct by **tranche role** — `stAssets` is filled when the SENIOR tranche has an AA claim, `jtAssets` when the JUNIOR does. Caller perspective does NOT shift the slot order.

### Final answer

**Use `getTupleWord(returnData, 1)` to extract the JT's own AA-tranche claim from `JT.convertToAssets(uint256)`.**

This matches `execution-deposit.md` Surprise 1 and contradicts both:

- `specs.yaml.queries.jt_to_assets.accounting_slot = 0`
- `specs.yaml.helpers.bytes32_helper.purpose` ("For the JT, INDEX 0 is the relevant slot")
- `functions.md` §3.4 paragraph "For the JT, slot 0 = the JT's own AA claim"
- `progress.yaml.stages.1_specs.notes` ("Therefore for JT accounting we use slot 0")

The Stage-1 conclusion was wrong; `execution-deposit.md` Surprise 1 was right. `specs.yaml` and `functions.md` have been amended in-place (see "Doc fixes" section below).

---

## Step 3: compute the final accounting

Per `specs.yaml.flows.accounting`:

```
jt_aa        = getTupleWord(JT.convertToAssets(shares), 1)        // 18 dec, slot 1
stranded_aa  = AA.balanceOf(caliber)                                // 18 dec
total_aa     = jt_aa + stranded_aa                                  // 18 dec
tranche_price = IdleCDOEpochVariant.tranchePrice(AATranche)         // USDC-6 per 1e18 AA
usdc_from_aa = total_aa * tranche_price / 1e18                      // 6 dec
pending_usdc = FalconXUSDC.balanceOf(caliber)                       // 6 dec
total_usdc   = usdc_from_aa + pending_usdc                          // 6 dec
```

With the post-sync values:

| Variable         | Value                                                                  | Decimals               |
| ---------------- | ---------------------------------------------------------------------- | ---------------------- |
| `jt_aa`          | `46_071_091_640_836_429_757_173`                                       | 18 (AA tranche tokens) |
| `stranded_aa`    | `0`                                                                    | 18                     |
| `total_aa`       | `46_071_091_640_836_429_757_173`                                       | 18                     |
| `tranche_price`  | `1_082_100`                                                            | 6 USDC per 1e18 AA     |
| `usdc_from_aa`   | `46_071_091_640_836_429_757_173 * 1_082_100 / 1e18` = `49_853_528_264` | 6                      |
| `pending_usdc`   | `0`                                                                    | 6                      |
| **`total_usdc`** | **`49_853_528_264`** = **`49,853.528264 USDC`**                        | 6                      |

NAV-space cross-check (slot 2 / 1e12):

```
nav_wad   = JT.convertToAssets(jt_shares)[2] = 49_853_528_264_549_100_640_238   // 18 dec USD WAD
nav_usdc  = nav_wad / 1e12                   = 49_853_528_264                   // 6 dec
```

**Asset-space and NAV-space agree to the wei** at this snapshot (`49,853_528_264` ↔ `49,853_528_264`). The difference observed in the deposit report (`49,922.564` asset-space vs `49,648.773` NAV-space, ~0.55% gap) has collapsed because the mid-epoch discount has unwound as the fork clock advanced ~9.2 days closer to the next stopEpoch. Both measures are now consistent and both equal the JT's NAV.

> Even when the two paths disagree mid-epoch, Path A (asset-space) is the correct accounting source: it values the caliber's underlying AA claim at the protocol-defined tranchePrice. NAV-space is informational — it's the kernel's USD-denominated view that already includes share-vs-NAV ratio effects.

---

## Pipeline verification (the full read recipe end-to-end)

| #  | Action                                           | Contract      | Selector     | Result                                                                            |
| -- | ------------------------------------------------ | ------------- | ------------ | --------------------------------------------------------------------------------- |
| 1  | `JT.balanceOf(caliber)` → `jt_shares`            | ROY-JT        | `0x70a08231` | `49,853,528,264,549,100,640,239`                                                  |
| 2  | `Kernel.syncTrancheAccounting()` (caliber)       | Kernel        | `0x9c8e2dc0` | tx `0x28b8...0428`, status success (state-changing; MUST run in MANAGEMENT batch) |
| 3  | `JT.convertToAssets(jt_shares)` → 3-tuple        | ROY-JT        | `0x07a2d13a` | `(0, 46_071_091_640_836_429_757_173, 49_853_528_264_549_100_640_238)`             |
| 4  | extract `jt_aa = getTupleWord(returnData, 1)`    | Bytes32Helper | `0x...`      | `46_071_091_640_836_429_757_173`                                                  |
| 5  | `AA.balanceOf(caliber)` → `stranded_aa`          | AA tranche    | `0x70a08231` | `0`                                                                               |
| 6  | `total_aa = jt_aa + stranded_aa`                 | UnsignedMath  | `add`        | `46_071_091_640_836_429_757_173`                                                  |
| 7  | `tranche_price = CDO.tranchePrice(AATranche)`    | CDO           | `0xa219d218` | `1_082_100`                                                                       |
| 8  | `usdc_from_aa = total_aa * tranche_price / 1e18` | UnsignedMath  | `mulDiv`     | `49_853_528_264`                                                                  |
| 9  | `pending_usdc = FalconXUSDC.balanceOf(caliber)`  | FalconXUSDC   | `0x70a08231` | `0`                                                                               |
| 10 | `total_usdc = usdc_from_aa + pending_usdc`       | UnsignedMath  | `add`        | `49_853_528_264`                                                                  |

---

## Doc fixes applied during this stage

The slot-resolution finding made `specs.yaml` and `functions.md` actively wrong. They have been amended in-place (no Stage 3 blueprint-writer should ever see the wrong slot guidance):

| File           | Fix                                                                                                                                                                                                                                                                     |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `specs.yaml`   | Overview item 3, divergence `convert_to_assets_slot_mapping`, divergence `accounting_no_slot_sum`, `helpers.bytes32_helper.purpose`, `queries.jt_to_assets.accounting_slot`, and `flows.accounting.description` ALL updated to say "index 1" (jtAssets), not "index 0". |
| `functions.md` | §3.4 (convertToAssets slot semantics) and the "Summary of divergences" item 4 rewritten to say slot 1 is the JT's claim. The layout is **role-fixed** (slot 0 = stAssets always, slot 1 = jtAssets always, slot 2 = nav).                                               |

The role-fixed layout finding is the most important downstream fact: `getTupleWord(JT.convertToAssets(shares), 1)` is the JT's AA claim, and `getTupleWord(ST.convertToAssets(shares), 0)` is the ST's AA claim. The "calling-tranche-occupies-slot-0" hypothesis from Stage 1 is wrong.

---

## Recommendations for the blueprint-writer

1. **Path A (asset-space full), mirror ST sibling's `account-default.yaml`** with the following adaptations:
   - JT instead of ST address: `0x8e0EC43e51B88AA2324102E1A3D667822bE51a6d`.
   - `getTupleWord(returnData, 1)` (NOT 0) to extract the JT's own AA-tranche claim.
   - Do NOT sum slot 0 + slot 1. Slot 0 is `stAssets` from the kernel's POV; in the JT context it stays at 0 in the solvent state and only carries a value in a senior write-down. Adding it would either be a no-op (solvent state) or double-count the ST's claim (write-down state). Stick to slot 1 only.
   - Order: `JT.balanceOf → Kernel.syncTrancheAccounting (state-changing!) → JT.convertToAssets → getTupleWord(_,1) → AA.balanceOf → add → tranchePrice → mulDiv → FalconXUSDC.balanceOf → add`.
2. **Single accounting blueprint covers all epoch states.** Unlike `deposit` (two variants for `depositAA` vs `depositDuringEpoch`), the accounting flow is identical between in-epoch and between-epoch states. `tranchePrice(AA)` is defined and meaningful in both regimes (it crystallises at `stopEpoch` and stays constant during the epoch; the per-AA value is the same protocol-wide).
3. **MANAGEMENT context required.** `syncTrancheAccounting()` is state-changing (not pure view). The blueprint must run from the caliber's MANAGEMENT batch context, not a static-call/account-view context. This matches the ST sibling's setup.
4. **Idempotence**: do NOT call `syncTrancheAccounting()` more than once in the same blueprint. The kernel mutates `lastSyncTimestamp` and quoter caches; a double-call wastes gas and (per ST `functions.md` §4) can produce surprising state. Single call at the top of the flow only.
5. **Decimals**: `jt_aa` is 18-dec AA, `tranche_price` is 6-dec USDC per 1e18 AA, `pending_usdc` is 6-dec USDC. The product `total_aa * tranche_price / 1e18` lands on 6-dec USDC. Sum-with-`pending_usdc` is dimensionally consistent.

The blueprint-writer should produce `blueprints/royco/jt-pareto-falconx/account.yaml` (single file) following the ST sibling's `blueprints/royco/st-pareto-falconx/account.yaml` template byte-for-byte except for: JT address, ST_LP→JT_LP role id (`16055754263579004741`, same as JT.deposit), and the tuple index `1` instead of `0`.

---

## Hand-off to subsequent stages

| Stage         | What to reuse                                                                                                                                                                                                                        |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `2_withdraw`  | Revert to snapshot `0x259d550498f35c0f19d09664b5fcfb13557cf05f4a4bf8f6aac17f2a01afe224`. ST.totalSupply == 0 here → JT.redeem has no coverage constraint. Use the same JT shares (`49_853_528_264_549_100_640_239`) from this state. |
| `3_blueprint` | Single account blueprint. Use `getTupleWord(_, 1)` for the JT's AA claim. Path A asset-space. Specs/functions.md already amended.                                                                                                    |
| `4_test`      | The accounting blueprint, when applied to the post-deposit snapshot, must produce `49,853,528,264` USDC (≈ `49,853.528264` USDC) on the DUSD caliber. This is the empirical reference value.                                         |
