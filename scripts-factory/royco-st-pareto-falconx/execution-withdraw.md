# Execution Report — Royco ST Pareto FalconX (withdraw)

## Fork (reused from deposit/account stages — NOT recreated)

| Key                              | Value                                                                             |
| -------------------------------- | --------------------------------------------------------------------------------- |
| `vnet_id`                        | `5b132729-f79a-4ffc-8d2f-33bac4dc23f9`                                            |
| `rpc_url` (admin)                | `https://virtual.mainnet.eu.rpc.tenderly.co/4ed6c929-bd54-4f22-a18d-aa575d39b78d` |
| Fork chain                       | Ethereum mainnet (chain_id 1)                                                     |
| Initial fork block               | `0x17d5d55` (24,992,981)                                                          |
| Block at this stage's first read | 24,993,119 (heads naturally advanced from deposit chain)                          |

Action: **withdraw (two-phase queued)**
Caliber under test: `0x5476F4E23dAA093Ce6700e1026013c55F7AF9083` (intMkSrRoyUSDC mainnet caliber)

ST balance carried over from deposit stage: **49,715.824587 ST shares** (`49_715_824_587_036_367_035_218`).

Two scenarios were run on the **same fork**, isolated via Tenderly snapshots:

- **Scenario A — Full redeem**: Redeem all 49,715.825 ST shares.
- **Scenario B — Partial redeem**: Revert to a snapshot taken just before the first `redeem`; redeem half (24,857.912 ST shares).

The caliber's mainnet Keyring whitelist (`whitelist[caliber] == true` on `KeyringIdleWhitelist 0x6a6a91c7…0e3`) and Royco AccessManager grants for `(ST, deposit)`, `(ST, redeem)`, and `(Kernel, syncTrancheAccounting)` were all already satisfied from the deposit stage — no additional access bypass was needed for the caliber to perform the withdraw flow.

---

## Why Phase 1 cannot run on the post-deposit fork as-is

Pre-flight reads at the post-deposit block (24,993,119) on the IdleCDOEpochVariant `0x433D…be4d`:

| Read                       | Selector     | Value                                  | Implication                                       |
| -------------------------- | ------------ | -------------------------------------- | ------------------------------------------------- |
| `isEpochRunning()`         | `0xc5c75098` | `true`                                 | epoch is live                                     |
| `epochEndDate()`           | `0x75d1497b` | `1779480958` (2026-05-04 17:29:34 UTC) | ~22 days out from fork ts                         |
| `epochDuration()`          | `0x4ff0876a` | `2,790,207` (~32.3 days)               |                                                   |
| `bufferPeriod()`           | `0x0553c2e7` | `21,600` (6 hours)                     | window between epochs                             |
| `paused()`                 | `0x5c975abb` | `true`                                 | CDO paused while epoch is running                 |
| `allowAAWithdrawRequest()` | `0x4da4f603` | **`false`**                            | requestWithdraw(AA) blocked                       |
| `defaulted()`              | `0x69e25ec1` | `false`                                |                                                   |
| `keyringAllowWithdraw()`   | `0x04a3a343` | `false`                                | requestWithdraw still requires Keyring credential |
| `disableInstantWithdraw()` | `0x58cdd22b` | `true`                                 | queued path only                                  |
| `tranchePrice(AA)`         | `0xa219d218` | `1,074,982`                            | unchanged from deposit stage                      |

`requestWithdraw` requires `allowAAWithdrawRequest == true`, which is only set back to `true` by `stopEpoch`. Thus **Phase 1 cannot run mid-epoch**; we must time-warp past `epochEndDate`, run `stopEpoch` (manager-gated), then run `redeem` + `requestWithdraw` between epochs.

Strategy contract reads (IdleCreditVault `0x17E9…eef3`, FalconXUSDC):

| Read                            | Value                                        | Notes                                                           |
| ------------------------------- | -------------------------------------------- | --------------------------------------------------------------- |
| `manager()`                     | `0x1fb0f3602f52e2420acff5cf04dbfde96378df58` | the role authorised to call `stopEpoch` / `startEpoch`          |
| `borrower()`                    | `0x653f71339144e8641a645758f4df4e317fe998a3` | must repay during `stopEpoch`                                   |
| `unscaledApr()`                 | `8.25e18` (8.25 %)                           | seed for the first `stopEpoch` `_newApr` argument below         |
| `pendingWithdraws()`            | `7,591,538.116535` USDC                      | total pending across all users (other lenders, not the caliber) |
| `expectedEpochInterest()` (CDO) | `938,876.443458` USDC                        | epoch interest the borrower must repay at `stopEpoch`           |

---

## Time-warp + manual `stopEpoch` setup (shared between both scenarios)

Time control on Tenderly is finicky. **`evm_increaseTime` does not always persist past one block**, so the working pattern is: jump time roughly with `evm_increaseTime` + `evm_mine`, and where strict ordering matters use `tenderly_setNextBlockTimestamp(t)` immediately before the next `eth_sendTransaction`. Empirically, even after `evm_increaseTime(2,790,300)` + a fresh block whose `block.timestamp` was greater than `epochEndDate`, a follow-up `stopEpoch` reverted with `NotAllowed()` — but with `tenderly_setNextBlockTimestamp` in front of the same transaction it succeeded immediately. This is the `evm_increaseTime` quirk noted in `MEMORY.md` materialising in practice; **the runbook below uses `tenderly_setNextBlockTimestamp` for every load-bearing time check.**

### Step W1 — Warp past the first `epochEndDate`

| Action    | Method             | Args                     | Result                                         |
| --------- | ------------------ | ------------------------ | ---------------------------------------------- |
| Bulk warp | `evm_increaseTime` | 1,926,200 s (~22.3 days) | head ts → 1,779,481,407 (epochEndDate + 449 s) |
| Mine      | `evm_mine`         | —                        | block 24,993,121                               |

### Step W2 — Fund the borrower so it can repay

`stopEpoch` will internally call `getFundsFromBorrower(_expectedInterest, _pendingWithdraws, 0)` which `safeTransferFrom`s **(`expectedEpochInterest` + `pendingWithdraws`) ≈ 938,876 + 7,591,538 = ~8.53 M USDC** from the borrower to the CDO. The borrower address `0x653f…98a3` is held by FalconX off-chain, so we override its USDC balance and approval on the testnet:

| Action                              | Tool                                                        | Result                           |
| ----------------------------------- | ----------------------------------------------------------- | -------------------------------- |
| Set borrower USDC                   | `tenderly_setErc20Balance(borrower, USDC, 0x1d1a94a200000)` | 512,000,000 USDC (way over need) |
| Fund borrower ETH                   | `tenderly_fund_account(borrower, 1 ETH)`                    | for gas                          |
| Borrower → USDC `approve(CDO, max)` | `eth_sendTransaction`                                       | tx `0xb7e7…1c11`, status success |
| Fund manager ETH                    | `tenderly_fund_account(manager, 1 ETH)`                     | manager `0x1fb0…df58` for gas    |

### Step W3 — `stopEpoch(8.25e18, 0)` from the manager

Uses `_newApr = 8.25e18` (= existing `unscaledApr`) and `_interest = 0` (use `expectedEpochInterest` already accrued):

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| from     | `0x1fb0f3602f52e2420acff5cf04dbfde96378df58` (impersonated manager)  |
| to       | IdleCDOEpochVariant `0x433D…be4d`                                    |
| selector | `0xd48099ad` (`stopEpoch(uint256,uint256)`)                          |
| calldata | `0xd48099ad` + `727de34a24f90000` (8.25e18) + `0…0` (interest=0)     |
| tx_hash  | `0xcb35644e0e1b89e0a4a4506498c1c67a42c45a3b032b220bdb78cdc4c04360d8` |
| status   | success                                                              |

Post-`stopEpoch` state:

| Read                       | Value           | Δ                                         |
| -------------------------- | --------------- | ----------------------------------------- |
| `isEpochRunning()`         | `false`         | flipped                                   |
| `allowAAWithdrawRequest()` | `true`          | flipped                                   |
| `paused()`                 | `false`         | flipped (`_unpause()` inside `stopEpoch`) |
| `tranchePrice(AA)`         | `1,082,228`     | **+0.674 %** (interest crystallised)      |
| `defaulted()`              | `false`         | unchanged                                 |
| `epochEndDate()`           | `1,779,480,958` | unchanged (will reset on `startEpoch`)    |

> **Snapshot S1**: `0x668dfdc4850f59bddcce7efba7fcf63a9d0d581d19758bb3b4ed353e7940315d` — taken immediately after Step W3 to anchor scenario A and B at the same start.

---

## Scenario A — Full redeem (49,715.825 ST shares)

### Pre-redeem caliber state

| Read                             | Value (raw)                                                           | Decoded                                                                                |
| -------------------------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `ST.balanceOf(caliber)`          | `49_715_824_587_036_367_035_218`                                      | 49,715.824587 ST shares                                                                |
| `AA.balanceOf(caliber)`          | `0`                                                                   | —                                                                                      |
| `USDC.balanceOf(caliber)`        | `40_000_000_000`                                                      | 40,000.000000 USDC                                                                     |
| `FalconXUSDC.balanceOf(caliber)` | `0`                                                                   | —                                                                                      |
| `ST.convertToAssets(stShares)`   | `(46_201_203_592_984_507_191_157, 0, 49_994_322_407_968_535_231_552)` | stAssets ≈ 46,201.204 AA, jtAssets = 0, nav = 49,994.322 USD WAD                       |
| `AA.balanceOf(Kernel)`           | `55_564_210_234_997_499_500_040`                                      | 55,564.210 AA (= 46,201.204 senior + 9,381.953 JT-bootstrap, post-stopEpoch repricing) |

The 0.674 % AA price advance from the first `stopEpoch` lifted `nav` from 49,715.825 → 49,994.322 USD WAD (+278.5 USD), recovering most of the mid-epoch deposit discount captured at deposit time. `stAssets` itself fell from 46,248.053 → 46,201.204 AA (-46.85 AA = -0.10 %) — the senior tranche's AA-share-balance shrinks slightly because the ST share price tracks NAV, not AA, and a portion of senior NAV migrated to junior NAV during the sync.

### Phase 1 step 1 — `RoycoST.redeem(stShares, caliber, caliber)`

| Field       | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| from        | caliber `0x5476F4…9083`                                              |
| to          | Royco ST `0x694A…754B`                                               |
| selector    | `0xba087652` (`redeem(uint256,address,address)`)                     |
| `_shares`   | `49_715_824_587_036_367_035_218`                                     |
| `_receiver` | caliber                                                              |
| `_owner`    | caliber                                                              |
| tx_hash     | `0xc06ddb207a5bf69521a90cdb79bfe7b207fa8ba239a0e221cbb58ef047e88f9f` |
| status      | success                                                              |

Caliber AA balance after redeem: `46_201_203_592_984_507_191_157` (= **46,201.204 AA**, exactly equal to the `stAssets` field of `convertToAssets`). Kernel AA balance dropped to `9_381_953_002_380_000_724_115` ≈ 9,381.953 AA (the JT-bootstrap residue). ST balance = 0; ST totalSupply burns to 0.

> **Verification of `redeem` `receiver` argument**: the AA tokens land at `_receiver` (here, the caliber). It is NOT a no-op pass-through. Source (`RoycoVaultTranche.redeem` → `IRoycoKernel.stRedeem(_shares, _receiver, false)` → `_withdrawAssets(userAssetClaims, _receiver)`) confirms the kernel transfers AA tranche tokens directly to `_receiver`.

> **Receipt-time vs request-time sandwich**: Per `specs.yaml` the blueprint should sandwich `AA.balanceOf(caliber)` rather than rely on the 3-tuple decode. Empirically the AA balance delta equals `stAssets` exactly (jtAssets = 0 in steady senior-only state), so on this market both methods agree; the sandwich is still the right defence against a future variant that introduces non-zero `jtAssets`.

### Phase 1 step 2 — `IdleCDOEpochVariant.requestWithdraw(46,201.204 AA, AATranche)`

Encoding the AA address as a 32-byte word as the `_tranche` argument:

| Field      | Value                                                                     |
| ---------- | ------------------------------------------------------------------------- |
| from       | caliber                                                                   |
| to         | IdleCDOEpochVariant `0x433D…be4d`                                         |
| selector   | `0xccc143b8` (`requestWithdraw(uint256,address)`)                         |
| `_amount`  | `46_201_203_592_984_507_191_157` (≈ 46,201.204 AA)                        |
| `_tranche` | `0xc26a6fa2c37b38e549a4a1807543801db684f99c` (AATranche address, 20-byte) |
| tx_hash    | `0x1f9d5d3ab03624f174a8368daa800fbf784325f5d40dcee7947b0d159726a2eb`      |
| status     | success                                                                   |

> **Verification of `requestWithdraw` 2nd argument**: the parameter is the **AA tranche address**, not an enum-like value. Source confirms `function requestWithdraw(uint256 _amount, address _tranche)` and the runtime branch `(_tranche == aa || _tranche == bb)` on the literal AA / BB addresses.

Caliber state after Phase 1:

| Read                                           | Value (raw)      | Decoded                                  |
| ---------------------------------------------- | ---------------- | ---------------------------------------- |
| `AA.balanceOf(caliber)`                        | `0`              | burned by `_withdrawOps`                 |
| `FalconXUSDC.balanceOf(caliber)`               | `50_326_617_406` | **50,326.617406 USDC** (6-dec receipt)   |
| `IdleCreditVault.withdrawsRequests(caliber)`   | `50_326_617_406` | matches the receipt 1:1                  |
| `IdleCreditVault.lastWithdrawRequest(caliber)` | `10`             | strategy's epoch counter at request time |
| `USDC.balanceOf(caliber)`                      | `40_000_000_000` | unchanged                                |
| `ST.balanceOf(caliber)`                        | `0`              | already burned in Phase 1 step 1         |

> **Receipt token denomination**: `FalconXUSDC.balanceOf(caliber)` is **already in USDC 6-decimals** — the account blueprint's `pending_usdc` term needs no scaling. Verified by direct numerical comparison (`amount transferred USDC ≈ FalconXUSDC.balanceOf` within 1 wei, see "Reconciling claim payout vs. receipt face value" below).

The receipt of 50,326.617 USDC against a senior NAV of 49,994.322 USD reflects the protocol's "principal + next-epoch net interest minus fees" formula in `requestWithdraw`:

```
_underlyings  = trancheToUnderlyings(_amount, AA) = 46,201.2036 * 1.082228 = 49,997.2... USDC
(interest, _) = _calcInterestWithdrawRequest(_underlyings, AA)
fees          = interest * 10% / 100%
netInterest   = interest - fees
_underlyings += netInterest  → ≈ 50,326.617 USDC
```

i.e. the receipt is principal-at-current-AA-price PLUS the net interest the position would have earned over the _next_ epoch (already pre-credited at request time). Real claim payout is bounded by the borrower's actual epoch performance — in our happy path here the borrower repays in full.

### Phase 1.5 — Why the claim is NOT yet ready, and how to confirm

A premature `claimWithdrawRequest()` simulation reverts with `NotAllowed()` (selector `0x3d693ada`):

| Field                                     | Value                                   |
| ----------------------------------------- | --------------------------------------- |
| from                                      | caliber                                 |
| to                                        | IdleCDOEpochVariant `0x433D…be4d`       |
| selector                                  | `0x33986ffa` (`claimWithdrawRequest()`) |
| `simulate_vnet_transaction` decoded_error | `NotAllowed`                            |
| revert hex                                | `0x3d693ada`                            |

Source: `IdleCreditVault.claimWithdrawRequest(_user)` reverts at `epochNumber <= lastWithdrawRequest[_user]`. The `epochNumber` field is incremented inside `IdleCreditVault.deposit(...)` which is called by `stopEpoch`'s `_strategy.deposit(netInterest)` near the end. So the caliber must wait for **another full epoch + `stopEpoch`** to elapse before `claimWithdrawRequest` succeeds.

> **Detectability for the blueprint**: rather than try/catching the revert, the blueprint can compute readiness as
>
> ```
> ready = IdleCreditVault.epochNumber() > IdleCreditVault.lastWithdrawRequest(caliber)
> ```
>
> Both fields are public auto-getters on `0x17E9…eef3`. As of Phase 1 finish: `epochNumber == 10` and `lastWithdrawRequest[caliber] == 10` — not ready. After the next `stopEpoch`: `epochNumber == 11` — ready.

### Phase 1.6 — Drive the protocol to the next epoch boundary

#### `startEpoch()` (manager)

`startEpoch` requires `block.timestamp >= epochEndDate + bufferPeriod` (i.e. past the 6-hour buffer after the previous `stopEpoch`'s recorded `epochEndDate`). On this fork:

| Pre-call ts                           | `epochEndDate + bufferPeriod`            | Action         |
| ------------------------------------- | ---------------------------------------- | -------------- |
| `1,779,481,500` (right after Phase 1) | `1,779,480,958 + 21,600 = 1,779,502,558` | warp ~22,000 s |

`tenderly_setNextBlockTimestamp(0x6a1110c4 = 1,779,503,300)` then:

| Field    | Value                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------ |
| from     | manager `0x1fb0…df58`                                                                            |
| to       | CDO `0x433D…be4d`                                                                                |
| selector | `0xa2c8b177` (`startEpoch()`)                                                                    |
| tx_hash  | `0x855a68377abab739e2c1e2df3d0250c708ec77b35a86045c29958531349766d5` (also reused in Scenario B) |
| status   | success                                                                                          |

Post-`startEpoch`:

- `isEpochRunning() == true`
- `epochEndDate() == 1,782,293,815` (= startEpoch ts + epochDuration)
- `paused() == true`
- `allowAAWithdrawRequest() == false`

#### Warp past the new `epochEndDate`, then `stopEpoch` again

| Pre-call ts     | `epochEndDate`  | Action            |
| --------------- | --------------- | ----------------- |
| `1,779,503,595` | `1,782,293,815` | warp +2,790,300 s |

Then `tenderly_setNextBlockTimestamp(0x6a3ba8a0 = 1,782,294,688)` to land just past the new `epochEndDate`, and re-run `stopEpoch(8.25e18, 0)` from the manager:

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| from     | manager                                                              |
| to       | CDO                                                                  |
| selector | `0xd48099ad`                                                         |
| calldata | `0xd48099ad` + `727de34a24f90000` + `0…0`                            |
| tx_hash  | `0xbdddda82ca4434c9c230c1584230df6db0f840ccfd0003af8dde127093d87f52` |
| status   | success                                                              |

Post-second-`stopEpoch`:

- `isEpochRunning() == false`
- `allowAAWithdrawRequest() == true`
- `paused() == false`
- `tranchePrice(AA) == 1,089,265` (+0.65 % vs. the post-first-stopEpoch price, +1.33 % vs. the deposit-time price)
- `IdleCreditVault.epochNumber() == 11` (was 10) ⇒ readiness condition `11 > 10` satisfied.

### Phase 2 — `IdleCDOEpochVariant.claimWithdrawRequest()`

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| from     | caliber                                                              |
| to       | CDO `0x433D…be4d`                                                    |
| selector | `0x33986ffa` (`claimWithdrawRequest()`)                              |
| calldata | `0x33986ffa` (no args)                                               |
| tx_hash  | `0xb43dd2cad2dc31de8bf4010bbcfc356fd648353fbd0719502e60b1787f2369a1` |
| status   | success                                                              |

> **Verification of the `claimWithdrawRequest()` arg shape**: takes **NO arguments** and claims the **entire** outstanding `withdrawsRequests[caliber]` in a single call. Source confirms: `function claimWithdrawRequest() external { IdleCreditVault(strategy).claimWithdrawRequest(msg.sender); }`. There is no per-request id; partial claims are not exposed.

> **Verification that claim is NOT Keyring-gated**: the test deliberately did **not** touch `KeyringIdleWhitelist.whitelist[caliber]` between Phase 1 and Phase 2, and the claim succeeded. Source: the CDO's `claimWithdrawRequest()` body forwards `msg.sender` to the strategy without any `_checkNotAllowed`/`isWalletAllowed` call. The Pareto integration's `access_control.pareto.notes` line "claimWithdrawRequest() is NOT keyring-checked" is therefore confirmed empirically.

### Final caliber state — Scenario A

| Read                             | Pre-Phase-1                      | Post-Phase-2     | Δ                                                                 |
| -------------------------------- | -------------------------------- | ---------------- | ----------------------------------------------------------------- |
| `ST.balanceOf(caliber)`          | `49_715_824_587_036_367_035_218` | `0`              | -49,715.824587 ST shares (full burn)                              |
| `AA.balanceOf(caliber)`          | `0`                              | `0`              | (transient: held 46,201.204 AA between Phase 1 step 1 and step 2) |
| `FalconXUSDC.balanceOf(caliber)` | `0`                              | `0`              | (transient: held 50,326.617 between Phase 1 and Phase 2)          |
| `USDC.balanceOf(caliber)`        | `40_000_000_000`                 | `90_326_617_406` | **+50,326.617406 USDC**                                           |

P&L vs. the caliber's original 50,000 USDC senior commitment:

```
Senior position originally cost          : 50,000.000000 USDC
USDC returned by Phase 2 claim           : 50,326.617406 USDC
Net senior gain                          :    +326.617406 USDC  (+0.653%)
Wall-clock between deposit and claim     : ~57 days
Implied APR                              :  ~4.18% (mid-epoch deposit yields less than a full epoch)
```

The remainder of the caliber's books from the deposit stage (10,000 USDC junior bootstrap → 9,943.166 JT shares) is unaffected by this withdraw — only the senior position was unwound.

---

## Scenario B — Partial redeem (24,857.912 ST shares = half)

Reverted to **snapshot S1** (`0x668d…315d`, taken immediately after the first `stopEpoch`) before running this scenario. State after revert verified bit-identical to the pre-Scenario-A baseline:

| Read                             | Value                            | OK? |
| -------------------------------- | -------------------------------- | --- |
| `ST.balanceOf(caliber)`          | `49_715_824_587_036_367_035_218` | ✅  |
| `AA.balanceOf(caliber)`          | `0`                              | ✅  |
| `USDC.balanceOf(caliber)`        | `40_000_000_000`                 | ✅  |
| `FalconXUSDC.balanceOf(caliber)` | `0`                              | ✅  |
| `isEpochRunning`                 | `false`                          | ✅  |
| `allowAAWithdrawRequest`         | `true`                           | ✅  |
| `tranchePrice(AA)`               | `1,082,228`                      | ✅  |

### Phase 1 step 1 — `RoycoST.redeem(half_shares, caliber, caliber)`

`half_shares = 49_715_824_587_036_367_035_218 // 2 = 24_857_912_293_518_183_517_609`

| Field       | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| from        | caliber                                                              |
| to          | Royco ST `0x694A…754B`                                               |
| selector    | `0xba087652`                                                         |
| `_shares`   | `24_857_912_293_518_183_517_609` (≈ 24,857.912294 ST)                |
| `_receiver` | caliber                                                              |
| `_owner`    | caliber                                                              |
| tx_hash     | `0xac058e04870fde4f244e54b7259cff8d105ac1cb55fe0cf7b41322e813072b00` |
| status      | success                                                              |

Post-redeem state:

- `ST.balanceOf(caliber)` = `24_857_912_293_518_183_517_609` (the unredeemed half)
- `AA.balanceOf(caliber)` = `23_100_601_796_492_253_595_578` ≈ **23,100.602 AA** (≈ half of the full-redeem 46,201.204, with sub-wei rounding)
- Post-redeem `convertToAssets(remaining_shares)` returns `(46_201_203_592_984_507_191_158, 0, 49_994_322_407_968_535_231_554)` — i.e. for the _unredeemed_ half the per-share NAV is preserved; the kernel's net AA stake declined by `(2,257,956,492,253,595,462)` ≈ 23,100.6 AA wei (matches the partial AA pull, rounded).

### Phase 1 step 2 — `requestWithdraw(23_100.602 AA, AATranche)`

| Field      | Value                                                                |
| ---------- | -------------------------------------------------------------------- |
| from       | caliber                                                              |
| to         | CDO                                                                  |
| selector   | `0xccc143b8`                                                         |
| `_amount`  | `23_100_601_796_492_253_595_578`                                     |
| `_tranche` | `0xc26a6fa2c37b38e549a4a1807543801db684f99c`                         |
| tx_hash    | `0xc079c6175be23948e08c44eb5db57b481ef8066a9f19ce0a9d3c7779dc957f50` |
| status     | success                                                              |

Post-Phase-1 caliber state:

- `AA.balanceOf(caliber)` = `0`
- `FalconXUSDC.balanceOf(caliber)` = `25_163_308_446` (≈ **25,163.308446 USDC**, ≈ half of the 50,326.617 in Scenario A — wei-perfect halving modulo rounding)
- `ST.balanceOf(caliber)` = `24_857_912_293_518_183_517_609` (unredeemed half — RETAINED, as required)
- `USDC.balanceOf(caliber)` = `40_000_000_000` (unchanged)

### Phase 1.5 / 1.6 — same `startEpoch` + warp + second `stopEpoch` machinery as Scenario A

Same calldata as Scenario A; on this snapshot the timing offsets are identical because the snapshot anchor was taken at the same point. Tx hashes:

| Step                                     | tx_hash                                                              |
| ---------------------------------------- | -------------------------------------------------------------------- |
| `startEpoch()` (manager)                 | `0x855a68377abab739e2c1e2df3d0250c708ec77b35a86045c29958531349766d5` |
| Second `stopEpoch(8.25e18, 0)` (manager) | `0xad1b233192b432592d21b80a1297b142330548977e61c1cde9de0843017103e8` |

Post-second-`stopEpoch` `tranchePrice(AA) == 1,089,265` — same as Scenario A. `epochNumber == 11`, `lastWithdrawRequest[caliber] == 10` ⇒ ready.

### Phase 2 — `claimWithdrawRequest()` (partial)

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| from     | caliber                                                              |
| to       | CDO                                                                  |
| selector | `0x33986ffa`                                                         |
| tx_hash  | `0xb43dd2cad2dc31de8bf4010bbcfc356fd648353fbd0719502e60b1787f2369a1` |
| status   | success                                                              |

### Final caliber state — Scenario B

| Read                             | Pre-Phase-1                      | Post-Phase-2                     | Δ                                                            |
| -------------------------------- | -------------------------------- | -------------------------------- | ------------------------------------------------------------ |
| `ST.balanceOf(caliber)`          | `49_715_824_587_036_367_035_218` | `24_857_912_293_518_183_517_609` | -24,857.9123 ST (exact half burned)                          |
| `AA.balanceOf(caliber)`          | `0`                              | `0`                              | (transient: 23,100.602 AA between Phase 1 step 1 and step 2) |
| `FalconXUSDC.balanceOf(caliber)` | `0`                              | `0`                              | (transient: 25,163.308 USDC across the inter-epoch wait)     |
| `USDC.balanceOf(caliber)`        | `40_000_000_000`                 | `65_161_407_902`                 | **+25,161.407902 USDC**                                      |

The unredeemed half ST shares are preserved with the same per-share NAV — `convertToAssets(24_857.9123) → (23_100.602 AA, 0, 24_997.161 USD WAD)`. The caliber can `redeem` the rest later through the same two-phase machinery (subject to the next epoch boundary).

---

## Reconciling claim payout vs. receipt face value

A subtle behaviour worth flagging for the blueprint:

| Scenario           | `FalconXUSDC.balanceOf(caliber)` pre-claim (raw) | USDC delta on `claimWithdrawRequest()` (raw) | Diff                             |
| ------------------ | ------------------------------------------------ | -------------------------------------------- | -------------------------------- |
| A — Full redeem    | `50_326_617_406`                                 | `+50_326_617_406`                            | **0 wei**                        |
| B — Partial redeem | `25_163_308_446`                                 | `+25_161_407_902`                            | **−1,900,544 wei (~−1.90 USDC)** |

Tenderly's asset-transfer trace for the second `stopEpoch` shows that the strategy received only `25,161.407902 USDC` worth of `collectWithdrawFunds` for the caliber's request (separate from the bulk transfer of `863,411.027 USDC` for the rest of the protocol's pending withdraws and `95,934.559 USDC` of fee-receiver payments). The 1.90 USDC delta is consumed inside `IdleCreditVault.prepareStopEpochWithApr0(0)` — the strategy adjusts `withdrawsRequests[caliber]` downward and migrates the same amount into an internal `apr0` settlement bucket, then `claimWithdrawRequest` only burns the post-adjustment `normalAmount` and transfers it.

Practical implications for the blueprint's accounting term:

- **`FalconXUSDC.balanceOf(caliber)` is a _near-upper-bound_ on the eventual USDC payout, not an exact pre-image.** The slip is sub-cent at this scale (1.90 USDC on a 25,163 USDC receipt = 0.008 %), but a correct accountant should treat the receipt as best-effort rather than a guarantee.
- The full-redeem case shows the slip can be **0**, so it is not a deterministic fee — it is path-dependent on the strategy's APR0 bookkeeping during the intervening `stopEpoch`. For a production-realistic withdraw cadence (where the caliber redeems an exact `stShares` amount minted in a single deposit) the slip is bounded but not always zero.
- The slip is **paid into the protocol fee receiver / strategy bucket**, not lost; from the caliber's perspective it is a one-time small-basis-point haircut that a downstream sync would likely re-credit if more deposits exist.
- Because the slip lives between Phase 1 and Phase 2 and is not on-caliber-state, the blueprint cannot detect it pre-claim. A defensive `account` blueprint can simply use `FalconXUSDC.balanceOf` as the pending-USDC term with the documented understanding that realised payout may be 1–2 wei (in 6-dec) below at claim time.

---

## Open question answers (all six requested verifications)

1. **`RoycoST.redeem(shares, receiver, owner)` — where does the AA land?**
   AA is transferred _directly to `_receiver`_. Confirmed by the post-Phase-1-step-1 balance: `AA.balanceOf(caliber) == stAssets` exactly (caliber was both `_receiver` and `_owner`). The kernel's `_withdrawAssets(userAssetClaims, _receiver)` is the leaf that transfers the AA out. **NOT a no-op pass-through.**

2. **`requestWithdraw(uint256, address)` — second arg type.**
   It is the **AA tranche address** (`0xc26a6fa2c37b38e549a4a1807543801db684f99c`), encoded as a 32-byte right-padded `address` word. The runtime branches on `(_tranche == aa || _tranche == bb)` against the literal AA / BB addresses. Not an enum, not a tranche-side flag.

3. **Receipt token decimals.**
   `FalconXUSDC` (`0x17E9…eef3`) is **6-decimals USDC-equivalent**. `FalconXUSDC.balanceOf(caliber)` after `requestWithdraw` returned `50_326_617_406` raw → 50,326.617406 USDC, matching (within ≤ 1.9 USDC slip, see above) the actual Phase 2 USDC payout. The accountant blueprint's `pending_usdc` term can add this directly without scaling.

4. **`claimWithdrawRequest()` — single shot or per-id?**
   **Takes no argument; claims the _entire_ outstanding receipt of the caller in one call.** Burns `withdrawsRequests[caliber]` worth of `FalconXUSDC` and transfers the same USDC. There is no `requestId`. Partial claims are not supported.

5. **Premature claim revert reason and detection.**
   Reverts with **`NotAllowed()`** (4-byte error selector `0x3d693ada`). Revert location: `IdleCreditVault.claimWithdrawRequest(_user)` at `if (epochNumber <= lastWithdrawRequest[_user]) revert NotAllowed();`. **Detection without try/catch**:
   ```
   ready = IdleCreditVault.epochNumber() > IdleCreditVault.lastWithdrawRequest(caliber)
   ```
   Both are simple `uint256` auto-getters. If `ready == false`, the blueprint should NOT call `claimWithdrawRequest` — it will revert.

6. **Re-entry idempotency after claim.**
   Yes — the caliber can immediately re-deposit. Final state of every Royco/Pareto handle on the caliber after Phase 2 is **clean** (`ST = 0`, `AA = 0`, `FalconXUSDC = 0`, `withdrawsRequests = 0`, `lastWithdrawRequest = 0`). The kernel automatically synced its accounting on each `redeem` (`_postOpSyncTrancheAccounting`) and on each `stopEpoch` via `_updateAccounting`, so no separate "post-claim sync" is required. The deposit blueprint's preconditions (epoch state, Keyring, role grants, junior NAV nonzero) still apply but no caliber-side "reset" is needed.

---

## Failure mode catalogue (for the blueprint)

| Step                                       | Pre-condition                                                                                                         | Failure on miss                                                                                                                  | Recovery                                                                  |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `RoycoST.redeem`                           | `marketState == PERPETUAL`, ST role granted, `paused() == false`                                                      | `restricted` modifier reverts with `AccessManagedUnauthorized` if role missing; OZ pausable reverts on `whenNotPaused` if paused | role grant by Royco ops; unpause by Royco timelock                        |
| `IdleCDOEpochVariant.requestWithdraw` (AA) | `isEpochRunning == false`, `allowAAWithdrawRequest == true`, `defaulted == false`, `isWalletAllowed(caliber) == true` | `NotAllowed()` (`0x3d693ada`) on any miss                                                                                        | wait for `stopEpoch`; check Keyring whitelist                             |
| `claimWithdrawRequest`                     | `epochNumber > lastWithdrawRequest[caliber]`                                                                          | `NotAllowed()` (`0x3d693ada`)                                                                                                    | wait for next `stopEpoch`                                                 |
| Time progression                           | `stopEpoch` requires `block.timestamp >= epochEndDate` AND `_pendingInstant() == 0` AND borrower funded/approved      | `NotAllowed()` if any miss; ERC20 transfer revert if borrower under-funded                                                       | manager-side ops; this is **NOT** part of the caliber's blueprint surface |

The `stopEpoch` row is **not** a step in the caliber blueprint — it is a Pareto-side runbook operation that the caliber waits for. The caliber's withdraw is intrinsically **two atomic on-caliber chains separated by an epoch boundary the caliber does not control**. Any framework / orchestration layer that drives the caliber should:

1. Run **Phase 1** (redeem + requestWithdraw) atomically, only when `isEpochRunning == false && allowAAWithdrawRequest == true`.
2. Schedule **Phase 2** (claimWithdrawRequest) after observing `IdleCreditVault.epochNumber()` advance past the request-time `lastWithdrawRequest[caliber]`.

End-to-end this is up to `2 * epochDuration + bufferPeriod ≈ 65 days` worst case (request just before `startEpoch`), or `~32 days` best case (request just after `stopEpoch`).

---

## Snapshot ledger (what was created and consumed during this stage)

| Snapshot                                      | Created at                                                          | Used for                                                                                                                               | Status                                                |
| --------------------------------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Pre-time-warp anchor (`0x900217a2…1db4`)      | Account stage (re-created at start of this stage as a no-op safety) | Carried over from the account stage; was consumed by that stage's revert and a fresh same-id snapshot taken here was likewise pre-warp | not used here (we proceeded forward)                  |
| **S1 — post-first-stopEpoch** (`0x668d…315d`) | After Step W3 of this stage                                         | Anchor for Scenario A and Scenario B                                                                                                   | **consumed by `evm_revert` between Scenario A and B** |

After Scenario B finished, no further snapshot was taken; the fork now sits in the post-Scenario-B state. The deposit and account stages' carry-over invariant of "ST = 49,715.824587 ST shares" is no longer satisfied. Subsequent stages should re-establish their own anchor or roll forward from here.

---

## Summary table for the blueprint-writer

### Phase 1 — request_redeem (atomic, between epochs)

| # | Action                                                    | Contract             | Selector               | Inputs                                  | Output observation                                         |
| - | --------------------------------------------------------- | -------------------- | ---------------------- | --------------------------------------- | ---------------------------------------------------------- |
| 1 | (optional) `Kernel.syncTrancheAccounting()`               | `0x15bb…1791`        | `0x9c8e2dc0`           | none                                    | crystallise NAV before `redeem`                            |
| 2 | `AA.balanceOf(caliber)` (sandwich pre)                    | AA `0xc26a…f99c`     | `0x70a08231`           | caliber                                 | `aaBefore`                                                 |
| 3 | `RoycoST.redeem(stShares, caliber, caliber)`              | ST `0x694A…754B`     | `0xba087652`           | shares, receiver=caliber, owner=caliber | returns `(stAssets, jtAssets, nav)`; AA arrives at caliber |
| 4 | `AA.balanceOf(caliber)` (sandwich post)                   | AA                   | `0x70a08231`           | caliber                                 | `aaAfter`                                                  |
| 5 | `aaDelta = aaAfter - aaBefore` (`UnsignedMathHelper.sub`) | helper `0x3D62…E3c0` | `sub(uint256,uint256)` | (aaAfter, aaBefore)                     | `aaDelta` (≈ `stAssets` in steady state)                   |
| 6 | `IdleCDOEpochVariant.requestWithdraw(aaDelta, AATranche)` | CDO `0x433D…be4d`    | `0xccc143b8`           | _amount=aaDelta, _tranche=AA addr       | mints FalconXUSDC receipt to caliber                       |

### Phase 2 — claim_redeem (atomic, after the next `stopEpoch`)

| # | Action                                                                        | Contract               | Selector     | Inputs  | Output observation                     |
| - | ----------------------------------------------------------------------------- | ---------------------- | ------------ | ------- | -------------------------------------- |
| 1 | (readiness probe) `IdleCreditVault.epochNumber()`                             | Strategy `0x17E9…eef3` | `0xf4145a83` | none    | uint256                                |
| 2 | (readiness probe) `IdleCreditVault.lastWithdrawRequest(caliber)`              | Strategy               | `0xe2988e6e` | caliber | uint256                                |
| 3 | (gate) require `epochNumber > lastWithdrawRequest[caliber]` (`BooleanHelper`) | helpers                | —            | —       | revert if not ready                    |
| 4 | `IdleCDOEpochVariant.claimWithdrawRequest()`                                  | CDO                    | `0x33986ffa` | none    | burns receipt; USDC arrives at caliber |

The blueprint **cannot** be made fully atomic — Phase 1 and Phase 2 must be separate transactions separated by at least one full Pareto epoch + buffer. The epoch boundary is a Pareto-ops responsibility (`startEpoch` + `stopEpoch` from `IdleCreditVault.manager()`), NOT a caliber primitive.

Aggregate reconciliation across both scenarios:

| Scenario | ST burned     | USDC out (deposit)        | USDC in (claim) | Net Δ vs. 50k senior commit  | Wall-clock |
| -------- | ------------- | ------------------------- | --------------- | ---------------------------- | ---------- |
| A — full | 49,715.824587 | 50,000.000000             | 50,326.617406   | **+326.617 USDC (+0.653 %)** | ~57 days   |
| B — half | 24,857.912294 | 25,000.000000 (allocable) | 25,161.407902   | **+161.408 USDC (+0.646 %)** | ~57 days   |

The half-redeem return rate is consistent with the full-redeem rate (within the 1.9 USDC `prepareStopEpochWithApr0` slip), confirming the partial redeem flow is mechanically equivalent to the full redeem at the per-share level.
