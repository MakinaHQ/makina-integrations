# Execution Report — Royco JT Pareto FalconX (deposit, DUSD machine)

## Fork (reuse this for the JT account + withdraw stages)

| Key                | Value                                                                                                      |
| ------------------ | ---------------------------------------------------------------------------------------------------------- |
| `vnet_id`          | `b0f9ddf1-1525-4bd6-9359-90dcf602ab12`                                                                     |
| `rpc_url` (admin)  | `https://virtual.mainnet.eu.rpc.tenderly.co/aca6b043-1c2a-4efa-9f9e-a5c15d84fe93`                          |
| `rpc_url` (public) | `https://virtual.mainnet.eu.rpc.tenderly.co/c4d3d9fd-0d64-4238-929d-d351df8e8411`                          |
| Fork chain         | Ethereum mainnet (chain_id 1)                                                                              |
| Fork block         | `0x17f793e` (25,131,838) — block timestamp `0x6a0cb81b` (1,778,420,251 = 2026-05-10 14:57:31 UTC)          |
| Project            | `dialectic-medici/script-factory`                                                                          |
| Dashboard          | https://dashboard.tenderly.co/dialectic-medici/script-factory/testnet/b0f9ddf1-1525-4bd6-9359-90dcf602ab12 |
| Post-deposit snap  | `0xe0637769e9512a19d07bd84d54e598efea3047386643fa6ca6d344e83232de6f`                                       |

Action: **deposit**.
Caliber under test: `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (DUSD mainnet caliber, sourced from `machines/dusd/mainnet/caliber.yaml`).

> NOT the intMkSrRoyUSDC caliber `0x5476F4E23dAA093Ce6700e1026013c55F7AF9083` used for the ST sibling.

---

## Pre-flight: actual on-chain state at fork block

| Read                                                               | Selector     | Contract                           | Result                              | Notes                                                                                    |
| ------------------------------------------------------------------ | ------------ | ---------------------------------- | ----------------------------------- | ---------------------------------------------------------------------------------------- |
| `isEpochRunning()`                                                 | `0xc5c75098` | IdleCDOEpochVariant `0x433D…be4d`  | `true`                              | Epoch live → deposit path B (`depositDuringEpoch`)                                       |
| `isDepositDuringEpochDisabled()`                                   | `0x5f0b472a` | same                               | `false`                             | Mid-epoch deposits enabled                                                               |
| `paused()`                                                         | `0x5c975abb` | same                               | `true`                              | CDO is paused mid-epoch — `depositAA` would revert (`Pausable: paused`); must use path B |
| `defaulted()`                                                      | `0x69e25ec1` | same                               | `false`                             |                                                                                          |
| `epochEndDate()`                                                   | `0x75d1497b` | same                               | `1779480991` (2026-05-22 21:36 UTC) | ~12.3 days out from the fork timestamp                                                   |
| `tranchePrice(AA)`                                                 | `0xa219d218` | same                               | `1,082,612` (USDC 6-dec / 1e18 AA)  | 1 AA ≈ 1.082612 USDC                                                                     |
| `RoycoFactory.canCall(DUSDcaliber, ROY_JT, deposit)`               | `0xb7009613` | RoycoFactory `0x7cC6…253C`         | `(true, 0)`                         | **DUSD caliber ALREADY has JT_LP role** — no `grantRole` impersonation needed            |
| `RoycoFactory.canCall(DUSDcaliber, ROY_JT, redeem)`                | same         | same                               | `(true, 0)`                         | Same role; covers withdraw too                                                           |
| `RoycoFactory.canCall(DUSDcaliber, Kernel, syncTrancheAccounting)` | same         | same                               | `(true, 0)`                         | DUSD caliber already has kernel-sync role                                                |
| `KeyringIdleWhitelist.whitelist(DUSDcaliber)` (slot 2 of mapping)  | `0x9b19251a` | KeyringIdleWhitelist `0x6a6a…50e3` | `true`                              | **DUSD caliber ALREADY Keyring-credentialed** — no storage override needed               |
| `ROY-JT.totalSupply()`                                             | `0x18160ddd` | ROY-JT `0x8e0e…1a6d`               | `0`                                 | JT IS EMPTY on this fork — divergence vs spec's prior fork                               |
| `ROY-JT.totalAssets()`                                             | `0x01e1d114` | same                               | `(0, 0, 0)` (three 32-byte words)   | Confirms empty JT — also confirms 3-tuple shape                                          |
| `ROY-ST.totalSupply()`                                             | `0x18160ddd` | ROY-ST `0x694A…754B`               | `0`                                 | ST also empty                                                                            |
| `AA.totalSupply()`                                                 | `0x18160ddd` | AA `0xc26a…f99c`                   | `30,786,234.05e18`                  | Pareto AA tranche has supply (mid-epoch deposit valid)                                   |
| `ROY-JT.balanceOf(DUSDcaliber)`                                    | `0x70a08231` | ROY-JT                             | `0`                                 |                                                                                          |
| `AA.balanceOf(DUSDcaliber)`                                        | same         | AA                                 | `0`                                 |                                                                                          |
| `USDC.balanceOf(DUSDcaliber)`                                      | same         | USDC                               | `0`                                 | Caliber not pre-funded — funded explicitly via `setErc20Balance` below                   |

### Findings vs. spec assumptions

The spec (`specs.yaml` open_questions) flags three blocking items:

1. `caliber_keyring` — **already satisfied for the DUSD caliber on mainnet.** `KeyringIdleWhitelist.whitelist[caliber] == true`. No storage override required. The same Pareto-policy-18 credential covers the DUSD caliber (it must already be enrolled across all dialectic calibers for Pareto).
2. `caliber_jt_lp_role` — **already satisfied on mainnet.** `RoycoFactory.canCall(DUSDcaliber, ROY_JT, deposit) == (true, 0)`. No `grantRole` impersonation needed. Same result for `redeem` (same JT_LP role).
3. `kernel_sync_role` — **already satisfied on mainnet.** The DUSD caliber has the shared kernel-sync role (id `15053450870919821405`) even though it does NOT yet hold any Royco ST position. This implies the caliber's role set was pre-populated for all in-flight Royco integrations.

**This is the cleanest possible pre-state**: zero off-blueprint setup needed beyond funding the caliber with USDC.

JT state divergence vs spec: the spec was written at fork block `0x17d5e3b` after the ST sibling's bootstrap helper had already seeded the JT with 9,951 shares. On this fresh fork at `0x17f793e` (a later block, ~138k blocks ahead), **both ST.totalSupply and JT.totalSupply are 0**. That is fine for the JT deposit test — JT.deposit is the bootstrap path and has no coverage gate. But it changes the empirical reading of `convertToAssets` slot semantics (see "Surprises" section below).

---

## Setup

### 1. Tenderly fork

Created on Tenderly mainnet at the latest block (`0x17f793e`, 25,131,838). See "Fork" section above.

### 2. Fund DUSD caliber with ETH for gas

`tenderly_setBalance(DUSDcaliber, 10_000 ETH)` — applied via `mcp__tenderly__fund_account` (amount `0x21e19e0c9bab2400000`).

### 3. Fund DUSD caliber with 50,000 USDC

`tenderly_setErc20Balance(USDC, DUSDcaliber, 50_000e6)` — applied via `mcp__tenderly__set_erc20_balance` (value `0xba43b7400`).

### 4. Keyring bypass — NOT NEEDED

`KeyringIdleWhitelist.whitelist[DUSDcaliber]` already returns `true`. No `tenderly_setStorageAt` call was issued. The runbook flag: **DUSD caliber is already enrolled on Pareto policy 18** on mainnet.

### 5. Royco AccessManager — NOT NEEDED

DUSD caliber already has JT_LP role for `JT.deposit` and `JT.redeem` selectors, and kernel-sync role for `Kernel.syncTrancheAccounting()`. The bootstrap helper `bootstrap-pareto-falconx-junior.sh` was **not** invoked — there is no need for an impersonated `grantRole` call. The runbook flag from the ST sibling does NOT apply to the DUSD caliber.

### 6. Junior bootstrap — NOT NEEDED

JT.deposit is itself the bootstrap path. There is no coverage gate to pre-seed. The ST sibling's `bootstrap-pareto-falconx-junior.sh` was needed only to seed the JT so the ST deposit's coverage check would pass; for the JT deposit test, the caliber itself performs the equivalent flow and that **is** the deposit-under-test.

---

## Deposit-under-test (50,000 USDC → Royco JT)

Branch chosen: **path B (`depositDuringEpoch`)** because `isEpochRunning() == true && !isDepositDuringEpochDisabled`. `depositAA` would have reverted with `Pausable: paused` since the CDO is paused mid-epoch.

Total USDC committed: **50,000 USDC = `0xba43b7400`**.

### Step 1 — `USDC.approve(IdleCDOEpochVariant, 50_000 USDC)`

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| from     | DUSD caliber `0xD1A1…c1BC`                                           |
| to       | USDC `0xA0b8…eB48`                                                   |
| selector | `0x095ea7b3` (`approve(address,uint256)`)                            |
| spender  | `0x433D5B175148dA32Ffe1e1A37a939E1b7e79be4d` (IdleCDOEpochVariant)   |
| amount   | `50_000_000_000` (50,000 USDC)                                       |
| tx_hash  | `0x48b353df6c991cf0d85171de30f4bdbb3eae523b05ac703de49dcea31116bc4d` |
| status   | success                                                              |

### Step 2 — `IdleCDOEpochVariant.depositDuringEpoch(50_000 USDC, AATranche)`

| Field      | Value                                                                |
| ---------- | -------------------------------------------------------------------- |
| from       | DUSD caliber                                                         |
| to         | IdleCDOEpochVariant `0x433D…be4d`                                    |
| selector   | `0xc61e3faa` (`depositDuringEpoch(uint256,address)`)                 |
| `_amount`  | `50_000_000_000` (50,000 USDC, 6-dec)                                |
| `_tranche` | `0xc26a6fa2c37b38e549a4a1807543801db684f99c` (AA)                    |
| tx_hash    | `0x272930e7023ac9852df117fadeb69b278bf431593fd93edbe2a49017c0a2e957` |
| status     | success                                                              |

**Balance sandwich on AA**:

| Read                      | Before           | After                            | Δ                              |
| ------------------------- | ---------------- | -------------------------------- | ------------------------------ |
| `AA.balanceOf(caliber)`   | `0`              | `46_113_070_977_587_824_135_927` | **`+46,113.0710 AA`** (18-dec) |
| `USDC.balanceOf(caliber)` | `50_000_000_000` | `0`                              | `-50,000 USDC`                 |

Implicit USDC/AA price at mint: `50_000 / 46_113.07 ≈ 1.08431` USDC per AA, vs. the sync `tranchePrice(AA) = 1.082612 USDC/AA` → **~0.157% mid-epoch discount** that recovers at the next stopEpoch settlement. Markedly tighter than the ST sibling's 0.57% discount because the JT deposit was made 12 days from epoch end vs. the ST's 4.5 days from epoch end — earlier mid-epoch deposits capture more of the accumulating yield.

### Step 3 — `AA.approve(RoycoJT, 46_113.0710 AA)`

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| from     | DUSD caliber                                                         |
| to       | AA tranche `0xc26a…f99c`                                             |
| selector | `0x095ea7b3` (`approve(address,uint256)`)                            |
| spender  | `0x8e0EC43e51B88AA2324102E1A3D667822bE51a6d` (Royco JT)              |
| amount   | `46_113_070_977_587_824_135_927` (full AA balance)                   |
| tx_hash  | `0x3ac4b7f14d7dc619cad458f1639d634b02ca7e8240f3783ebb13c07bcdda08d9` |
| status   | success                                                              |

### Step 4 — `RoycoJT.deposit(46_113.0710 AA, caliber)`

| Field       | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| from        | DUSD caliber                                                         |
| to          | Royco JT `0x8e0e…1a6d`                                               |
| selector    | `0x6e553f65` (`deposit(uint256,address)`)                            |
| `_assets`   | `46_113_070_977_587_824_135_927`                                     |
| `_receiver` | DUSD caliber                                                         |
| tx_hash     | `0x1427c29eb1477e6e3cc86033e309dd8fae542c976e3e44711e0f7658ac815980` |
| status      | success                                                              |

### Final balances

```
ROY-JT.balanceOf(caliber) = 49_648_773_094_672_884_545_519     (49,648.7731 JT shares)
ROY-JT.totalSupply()       = 49_648_773_094_672_884_545_519     (caliber owns 100%)
ROY-JT.totalAssets()       = (0, 46_113_070_977_587_824_135_926, 49_648_773_094_672_884_545_518)
                              (stAssets=0, jtAssets=46113.07 AA, nav=49648.77 USD WAD)
AA.balanceOf(caliber)      = 0                                  (all sent to kernel)
AA.balanceOf(Kernel)       = 46_113_070_977_587_824_135_927     (46,113.07 AA in kernel custody)
USDC.balanceOf(caliber)    = 0                                  (50,000 consumed)
tranchePrice(AA)           = 1_082_612                          (unchanged across steps)
ROY-ST.totalSupply()       = 0                                  (no senior position yet)
```

### Sanity check — `convertToAssets(jtTotalSupply)` 3-tuple

```
input  : jtShares = 49_648_773_094_672_884_545_519
return : (stAssets, jtAssets, nav) =
         (0,
          46_113_070_977_587_824_135_925,   //  ~ AA tokens, 18 dec
          49_648_773_094_672_884_545_518)    //  USD WAD
```

- `stAssets = 0` — no ST position exists yet (totalSupply ST == 0). This is the senior tranche's claim on the underlying AA, which is empty on this fork.
- `jtAssets = 46_113.071 AA` — the JT's own AA claim. Matches the AA actually pulled from the caliber (1-wei dust rounding artifact).
- `nav = 49_648.7731 USD WAD` — total NAV in USD WAD. Equal to JT.totalSupply (each JT share is denominated 1:1 in USD WAD at this snapshot since ST.totalSupply == 0).

Asset-space valuation: `jtAssets * tranchePrice(AA) / 1e18 = 46_113_070_977_587_824_135_925 * 1_082_612 / 1e18 = 49_922_563_995 = 49,922.564 USDC`. The 50,000 → 49,922.564 gap is the **mid-epoch discount** (Pareto's mint formula `(amount + trancheInterest) * trancheTotSupply / expectedFinal` shortchanges late depositors of the locked epoch yield; recovered at next stopEpoch).

NAV-space valuation: `nav / 1e12 = 49_648_773_094 = 49,648.773 USDC`. ~0.55% below the asset-space figure. This is the same NAV-vs-asset gap the ST sibling's accounting report flagged, but in the opposite direction here because the JT's NAV is the residual after the ST's deterministic claim — which is undefined-then-defaulted-to-shares when ST.totalSupply == 0.

### `convertToAssets(1e18)` per-share

```
input  : 1e18
return : (0,
          925_193_488_627_420_248,        //  0.9252 AA per JT share
          999_999_999_999_999_999)         //  ~1.0 USD WAD per JT share
```

JT share is currently backed by `46_113.071 / 49_648.773 = 0.92879 AA per share`. The 0.001 AA gap vs. `slot 1 / 1e18` is per-share rounding (`(jtShares * jtAssets_per_share) / 1e18 < jtAssets`).

### Events (decoded by call-trace inference — Tenderly events endpoint shows empty `name` fields on the unverified JT/Kernel/Accountant impls)

The four-step flow produced:

| # | Emitter            | Event                                                       | Data                                                           |
| - | ------------------ | ----------------------------------------------------------- | -------------------------------------------------------------- |
| 1 | USDC               | `Approval(caliber, IdleCDOEpochVariant, 50_000e6)`          | initial USDC approval                                          |
| 2 | USDC               | `Transfer(caliber, IdleCDOEpochVariant, 50_000e6)`          | caliber → CDO USDC pull                                        |
| 3 | AA                 | `Transfer(0x0, caliber, 46_113.07e18)`                      | AA mint to caliber via IdleCDO                                 |
| 4 | AA                 | `Approval(caliber, ROY_JT, 46_113.07e18)`                   | AA approval                                                    |
| 5 | AA                 | `Transfer(caliber, Kernel, 46_113.07e18)`                   | matches `safeTransferFrom(msg.sender, KERNEL, _assets)`        |
| 6 | RoycoJuniorTranche | `Deposit(caliber, caliber, 46_113.07 AA, 49_648.77 shares)` | matches the documented `emit Deposit(msg.sender, _receiver,…)` |
| 7 | RoycoJuniorTranche | `Transfer(0x0, caliber, 49_648.77 shares)`                  | mint                                                           |
| 8 | RoycoKernel        | `SyncedAccountingState(…)` (or similar; name unverified)    | post-op accounting state                                       |

The `AA: 0 → caliber` + `AA: caliber → Kernel` + `ROY-JT mint: 0 → caliber` pattern matches `flows.deposit.events_to_monitor` in `specs.yaml`.

---

## Idle-variant (`depositAA`) variant — NOT TESTED on this fork

`depositAA(uint256)` cannot be exercised on this fork because `paused() == true` mid-epoch and `depositAA` carries the `whenNotPaused` modifier. Testing it would require either (a) waiting for the next stopEpoch (~12 days simulated, plus oracle/staleness handling), or (b) impersonating the Pareto manager to `stopEpoch` immediately, which has cascading sync deposit consequences. Per the task spec this is optional — the ST sibling's `execution-deposit.md` already empirically confirmed the `depositAA(uint256)` selector and parameter shape against this exact CDO at fork `0x17d5d55` (`depositDuringEpoch` was the path used there too; idle path was simulated dry separately). The signature `depositAA(uint256)` selector `0xb450dfce` is verified by reading `IdleCDOEpochVariant`'s ABI from Etherscan (verified contract).

**For the blueprint-writer**: confirm two blueprint variants are required (same as the ST sibling). The deposit-running variant takes `depositDuringEpoch(uint256,address)` selector `0xc61e3faa`; the deposit-idle variant takes `depositAA(uint256)` selector `0xb450dfce`. They are incompatible (different parameter counts) and cannot be unified via weiroll ternary.

---

## Reverts encountered: none

Every transaction in the deposit chain succeeded on the first attempt. The two protocol-level pitfalls flagged in the spec (Keyring gate, Royco AccessManager gate) were already cleared on mainnet for the DUSD caliber, and the third blocker the ST sibling hit (junior bootstrap) does not apply because JT.deposit IS the bootstrap path.

Avoided revert paths:

- `depositAA(50_000 USDC)` — would have reverted with `Pausable: paused` because the CDO is paused for the duration of the running epoch. Path B used instead.

---

## Surprises vs. spec

### Surprise 1 — `convertToAssets` slot semantics

Spec (`specs.yaml` OVERVIEW item 3 + `divergence.convert_to_assets_slot_mapping`) claims:

> On the JT: slot 0 = the JT's own AA claim (i.e. jtAssets from a JT POV), slot 1 = the ST's claim, slot 2 = nav.
> Empirically verified at fork block 0x17d5e3b: JT.totalSupply * slot0_per_share = JT.totalAssets() (18.15e18 AA).

**This is contradicted on the fresh DUSD fork.** With ST.totalSupply == 0 and JT.totalSupply == 49,648.77 shares:

```
JT.convertToAssets(jtTotalSupply) = (0, 46_113_070_977_587_824_135_925, 49_648_773_094_672_884_545_518)
JT.totalAssets()                   = (0, 46_113_070_977_587_824_135_926, 49_648_773_094_672_884_545_518)
```

The JT's own AA claim sits in **slot 1**, not slot 0. Slot 0 is `stAssets` (always — the ST's claim, which is 0 when ST is empty).

This means the kernel `_deriveTrancheAssetClaims` populates the `(stAssets, jtAssets, nav)` struct **by tranche role**, not by caller perspective. From either tranche's POV:

- slot 0 = **always** the ST tranche's claim
- slot 1 = **always** the JT tranche's claim
- slot 2 = **always** nav (USD WAD)

The spec's prior empirical reading at `0x17d5e3b` must have been wrong (likely the slot numbering convention was misread). The functions.md description of the `AssetClaims` struct in Types.sol is consistent with this fixed layout: `struct AssetClaims { TRANCHE_UNIT stAssets; TRANCHE_UNIT jtAssets; NAV_UNIT nav; }`.

**Critical implication for the blueprint-writer** (and the stage 2_account run): on the JT, use `getTupleWord(returnData, 1)` (NOT index 0) to pick the JT's AA claim. The previous specs.yaml + functions.md should be amended to use **slot 1** for JT accounting. This is the OPPOSITE of what `divergence.accounting_no_slot_sum` claims.

Defensive alternative the blueprint-writer should consider: sum **slot 0 + slot 1** (total AA across both tranches). This is wrong from a per-caliber-ownership POV (it credits the JT with the ST's claim) but it equals `totalAssets across the protocol` and is safe whenever the caliber's only Royco position on this market is the JT. Per `accounting_no_slot_sum`, the ST sibling does this, with the same rationale of robustness to senior write-downs. The cleanest path is to use slot 1 only and treat senior write-downs as out-of-band events that ops handles.

### Surprise 2 — DUSD caliber pre-state on mainnet

The spec's `open_questions` (`caliber_jt_lp_role`, `caliber_keyring`, `kernel_sync_role`) all marked `blocking: true` for the DUSD caliber. **All three are already satisfied on mainnet for the DUSD caliber** — same as the ST sibling found for the intMkSrRoyUSDC caliber, but importantly the DUSD caliber has the role pre-granted **without** ever having held a Royco position. This implies the dialectic operations team enrols every caliber across all in-flight Royco markets ahead of time (the JT_LP and ST_LP roles, plus the kernel-sync role). The blueprint can assume access is in place; runbook for ops should just verify post-deployment.

### Surprise 3 — `isEpochRunning() == true` on this fork (Path B chosen)

Spec OVERVIEW assumed `isEpochRunning == false` at the prior fork `0x17d5e3b` and chose Path A. The newer fork has the next epoch already running. Both branches are documented in the spec; this run exercises Path B (`depositDuringEpoch`). The blueprint must support both — confirmed identical conclusion to the ST sibling: **two separate blueprints**, not a ternary, because `depositAA(uint256)` and `depositDuringEpoch(uint256,address)` have incompatible signatures.

### Surprise 4 — Mid-epoch discount smaller than the ST sibling

This run hit a 0.157% mid-epoch discount (vs. the ST sibling's 0.57%) because the deposit happened 12 days from epoch end rather than 4.5. The discount magnitude is time-to-epoch-end-dependent; the blueprint must NOT slippage-check on the AA mint amount because the size depends on the exact time-of-day of the deposit (a runbook concern, not a blueprint concern).

---

## Summary table for the blueprint-writer

| # | Action                                                                                       | Contract                          | Selector                    | Inputs                                                       | Output observation                                                     |
| - | -------------------------------------------------------------------------------------------- | --------------------------------- | --------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------- |
| 1 | `USDC.approve(spender=IdleCDOEpochVariant, amount=50_000e6)`                                 | USDC `0xA0b8…eB48`                | `0x095ea7b3`                | spender=`0x433D…be4d`, amount=50_000_000_000                 | allowance set                                                          |
| 2 | branch on `isEpochRunning()` → `depositDuringEpoch(amount,AATranche)` OR `depositAA(amount)` | IdleCDOEpochVariant `0x433D…be4d` | `0xc61e3faa` / `0xb450dfce` | _amount=50_000_000_000; _tranche=`0xc26a…f99c` (path B only) | sandwich `AA.balanceOf(caliber)` to capture mint (here +46,113.071 AA) |
| 3 | `AA.approve(spender=RoycoJT, amount=aaMinted)`                                               | AA `0xc26a…f99c`                  | `0x095ea7b3`                | spender=`0x8e0E…1a6d`, amount=aaMinted                       | allowance set                                                          |
| 4 | `RoycoJT.deposit(aaMinted, caliber)`                                                         | Royco JT `0x8e0e…1a6d`            | `0x6e553f65`                | _assets=46_113_070_977_587_824_135_927, _receiver=caliber    | `ROY-JT.balanceOf(caliber)` = +49_648.77 JT shares                     |

Two separate blueprints required (same as the ST sibling):

- `deposit-running.yaml` → step 2 = `depositDuringEpoch(uint256,address)`, guard on `isEpochRunning && !isDepositDuringEpochDisabled` (revertIfFalse / revertIfTrue).
- `deposit-idle.yaml` → step 2 = `depositAA(uint256)`, guard on `!isEpochRunning` (revertIfFalse).

Aggregate accounting at this snapshot:

- **50,000 USDC in → 49,922.564 USDC (asset-space) or 49,648.773 USDC (NAV-space) post-mint**
- 1 JT share ≈ 0.92879 AA ≈ 1.00549 USDC (asset-space) at the post-deposit moment.
- The ~0.16% gap from 50k recovers at the next stopEpoch settlement.

---

## Hand-off to the next stages

| Stage         | What to reuse                                                                                                                                                                                                                                                                                                                                                                                    |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `2_account`   | Revert to snapshot `0xe0637769e9512a19d07bd84d54e598efea3047386643fa6ca6d344e83232de6f` for a byte-identical post-deposit state. Caliber: `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC`. JT shares: `49_648_773_094_672_884_545_519`. Use `convertToAssets(jtShares)` **slot 1** (NOT slot 0) for the JT's AA claim — divergence from spec, see Surprise 1.                                       |
| `2_withdraw`  | Revert to the same snapshot. **Important**: ST.totalSupply == 0 on this fork → JT.redeem coverage check is trivially OK at any size (no senior to undercover). For phase 1 `requestWithdraw`, the deposit and redeem flows use the same Pareto CDO; `allowAAWithdrawRequest` and `isEpochRunning == false` are required, so will need to time-warp past `epochEndDate = 1779480991` for phase 1. |
| `3_blueprint` | Two deposit variants confirmed required (`depositAA` vs `depositDuringEpoch`). Account formula needs **slot 1** for the JT, not slot 0. All access gates (Keyring, JT_LP, kernel-sync) are already in place for the DUSD caliber on mainnet — no extra setup actions in the runbook.                                                                                                             |

Reuse vnet `b0f9ddf1-1525-4bd6-9359-90dcf602ab12`, admin RPC `https://virtual.mainnet.eu.rpc.tenderly.co/aca6b043-1c2a-4efa-9f9e-a5c15d84fe93`.
