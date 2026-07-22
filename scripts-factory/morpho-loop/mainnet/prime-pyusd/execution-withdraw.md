# Execution Report — WITHDRAW (deleverage / exit)

**Action**: withdraw (deleverage / close) — PRIME/PYUSD Morpho loop
**Chain**: mainnet (ethereum)
**Machine**: dusd
**Executor**: state-changing calls sent AS the caliber `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (impersonated); `completeRedeem` sent as the Hastra REWARDS_ADMIN.
**Testnet**: `8f992f50-3553-441e-aae5-26a38d5bb786` (SHARED fork holding the open leveraged position — reused, no new fork)
**Fork left**: OPEN + PRISTINE — reverted to the clean baseline snapshot. `position(id,caliber) = [0, 85277439518424200, 136227942710]`, loose PYUSD 43,000.0, USDC 1.000001, PRIME 0, wYLDS 0, `pendingRedemptions=[0,0,0]`.

## Starting position (clean baseline)

| Metric                               | Value                                                          |
| ------------------------------------ | -------------------------------------------------------------- |
| collateral                           | 136,227.942710 PRIME                                           |
| borrowShares                         | 85,277,439,518,424,200                                         |
| debt (toAssetsUp)                    | 86,000.009851 PYUSD                                            |
| oracle `price()`                     | 1,049,690,555,221,613,945,938,417,681,788,095,852 (~1.0497e36) |
| collateral value (`coll*price/1e36`) | 142,997.184819 PYUSD                                           |
| position equity (coll_val − debt)    | 56,997.174968 PYUSD                                            |
| loose PYUSD                          | 43,000.000000                                                  |
| loose USDC                           | 1.000001                                                       |
| **caliber total NAV (equity_start)** | **99,998.174969 PYUSD**                                        |

The 43k loose PYUSD is the un-repaid final borrow from the manual 2-cycle lever-up (see deposit report); in a true atomic loop it would live inside the Morpho position. Total NAV reconciles to the ~100k principal minus deposit slippage.

---

# TASK 1 — Variant A feasibility (atomic close): DEX liquidity VERDICT = **FEASIBLE**

The spec/task assumed RWA illiquidity → no sync route. **This is WRONG for PRIME.** On-chain probe (Uniswap V2/V3 factories + Curve):

**wYLDS** — no DEX liquidity anywhere. `getPair`/`getPool(wYLDS, {PYUSD,USDC,WETH}, all fee tiers)` all return `address(0)`. wYLDS exit is async-only (confirmed).

**PRIME** — a **deep Uniswap V3 pool exists**:

| Pool       | `0x5B70A1582135BD04e39CA94A6a56Fc3A828e3115`        |
| ---------- | --------------------------------------------------- |
| pair / fee | PRIME (token0) / USDC (token1), **0.01% (fee=100)** |
| reserves   | 3,478,158.25 PRIME / 5,352,191.13 USDC              |
| liquidity  | 5,494,329,799,361,190                               |
| slot0 tick | 483                                                 |

QuoterV2 `quoteExactInputSingle` (PRIME→USDC, fee 100):

| PRIME in                         | USDC out         | rate (USDC/PRIME) | ticksCrossed |
| -------------------------------- | ---------------- | ----------------- | ------------ |
| 1,000                            | 1,049.3805       | 1.049381          | 0            |
| 50,000                           | 52,468.5463      | 1.049371          | 0            |
| 100,000                          | 104,936.1144     | 1.049361          | 0            |
| **136,227.94 (full collateral)** | **142,951.3442** | **1.049354**      | **0**        |

Selling the entire collateral crosses **zero ticks** — the pool's concentrated liquidity easily absorbs the full close at ~NAV. Realized rate 1.049354 vs PRIME NAV 1.049629 vs Morpho oracle mark 1.049691 → execution is only **~0.032% below the oracle mark**. There is **no direct PRIME/PYUSD pool**, so the sync route is two hops: `PRIME →(UniV3 0.01%)→ USDC →(Curve PYUSD/USDC 0x383E…8559)→ PYUSD`. Aggregators registered on `swap_module` (0x, Odos, Kyber, 0x Settler) all route PRIME→USDC through this pool; on the fork the legs were executed directly against the pool/Curve (aggregator calldata can't be generated deterministically against a fork), exactly as the deposit report did for the swap leg.

## Variant A — validated atomic close (per-leg)

Modeled the Morpho PYUSD flash loan by delivering the FL principal to the caliber (the zero-fee Morpho flashloan primitive via `flash_loan_aggregator` provider MORPHO=3 was already proven in the deposit report). All legs executed AS the caliber:

| # | Leg                        | Target               | Selector                                                   | Args                                                               | In → Out                                                       | Gas     | Status |
| - | -------------------------- | -------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------- | ------- | ------ |
| — | (FL deliver)               | —                    | —                                                          | +86,000.009851 PYUSD to caliber (models Morpho `flashLoan`, 0 fee) | —                                                              | —       | —      |
| 1 | approve                    | PYUSD `0x6c3e…A0e8`  | `approve` `0x095ea7b3`                                     | Morpho, max                                                        | —                                                              | 60,488  | ✅     |
| 2 | **repay full**             | Morpho `0xBBBB…FFCb` | `repay(MP,0,shares,onBehalf,0x)` `0x20b76e81`              | assets=0, **shares=85,277,439,518,424,200**, onBehalf=caliber      | −86,000.16586 PYUSD → borrowShares 0                           | 108,330 | ✅     |
| 3 | **withdrawCollateral all** | Morpho               | `withdrawCollateral(MP,assets,onBehalf,recv)` `0x8720316d` | assets=136,227.942710e6, onBehalf=recv=caliber                     | → 136,227.942710 PRIME to caliber                              | 109,449 | ✅     |
| 4 | approve                    | PRIME `0x19eb…F7F6`  | `approve`                                                  | UniV3 router `0xE592…1564`, max                                    | —                                                              | ~46k    | ✅     |
| 5 | **swap PRIME→USDC**        | UniV3 SwapRouter     | `exactInputSingle` `0x414bf389`                            | (PRIME,USDC,fee=100,recv=caliber,dl,136227.942710e6,0,0)           | 136,227.942710 PRIME → **142,951.344247 USDC** (rate 1.049354) | 129,872 | ✅     |
| 6 | approve                    | USDC `0xA0b8…eB48`   | `approve`                                                  | Curve `0x383E…8559`, max                                           | —                                                              | ~55k    | ✅     |
| 7 | **swap USDC→PYUSD**        | Curve PYUSD/USDC     | `exchange(1,0,dx,0)` `0x3df02124`                          | i=1(USDC), j=0(PYUSD), dx=142,951.344247e6                         | 142,951.344247 USDC → **142,933.814816 PYUSD** (rate 0.99988)  | 167,184 | ✅     |
| — | (repay FL)                 | —                    | —                                                          | −86,000.16586 PYUSD (exact, 0 fee)                                 | —                                                              | —       | —      |

`MP = marketParams = (PYUSD, PRIME, 0x335e…b07e, 0x870a…00BC, 860000000000000000)`.

**Round-trip:**

```
START equity                 = 99,998.174969 PYUSD  (pos 56,997.174968 + loose 43,000 + 1 USDC)
END   (PYUSD 99,933.492947 + USDC 1.000001)        = 99,934.492948 PYUSD, position [0,0,0]
round-trip cost              = 63.682 PYUSD  = 0.0637%
```

Cost breakdown: PRIME→USDC executes ~0.032% below oracle mark (≈46 PYUSD) + Curve USDC→PYUSD 0.012% (≈17.5) + ~0.16 interest accrued during the close.

**Variant A verdict: viable and atomic.** A single FLASHLOAN_MANAGEMENT instruction closes the whole position with **no async dependency and no Hastra operator involvement**. This is the preferred production path when the Uni V3 PRIME/USDC pool has depth for the position size.

---

# TASK 2 — Variant B (staged async exit): VALIDATED end-to-end

Because the wYLDS→USDC leg cannot settle in the same tx, a flash loan cannot bridge the whole close; the exit is staged and the wYLDS→USDC settlement is admin-gated. Full round-trip proven on the fork.

## Phase 1 — unwind to a pending redemption (executed AS caliber, one management envelope)

Repay funding modeled by delivering 86,000.009851 PYUSD to the caliber — represents the operator sourcing PYUSD from **fund idle liquidity** (NOT an atomic FL, which cannot be repaid across the async gap).

| # | Leg                                 | Target              | Selector                                                 | Args                                        | Result                                    | Gas     | Status |
| - | ----------------------------------- | ------------------- | -------------------------------------------------------- | ------------------------------------------- | ----------------------------------------- | ------- | ------ |
| a | approve + **repay full**            | Morpho              | `repay(MP,0,shares,caliber,0x)`                          | shares=85,277,439,518,424,200               | borrowShares → 0                          | 108,330 | ✅     |
| b | **withdrawCollateral all**          | Morpho              | `withdrawCollateral(MP,136227.942710e6,caliber,caliber)` | → 136,227.942710 PRIME to caliber           | collateral → 0                            | 109,449 | ✅     |
| c | **PRIME.redeem all → wYLDS** (SYNC) | PRIME `0x19eb…F7F6` | `redeem(shares,recv,owner)` `0xba087652`                 | shares=136,227.942710e6, recv=owner=caliber | → **142,988.855896 wYLDS** (NAV 1.049629) | 116,977 | ✅     |
| d | **wYLDS.requestRedeem** (ASYNC)     | wYLDS `0x6aD0…66Cc` | `requestRedeem(shares)` `0xaa2f892d`                     | shares=142,988.855896e6                     | wYLDS→0; pending recorded                 | 129,577 | ✅     |

**`pendingRedemptions(caliber)` after step d** = `(shares 142,988,855,896, assets 142,988,855,896, timestamp 1784712156)` → **142,988.855896 USDC owed**. `getPendingRedemption` = `[True, 142988855896, 142988855896]`.

**Handoff state (end of Phase 1):** Morpho position empty `[0,0,0]`; caliber holds a PENDING wYLDS redemption worth 142,988.855896 USDC captured by the ACCOUNTING pending term; caliber wYLDS balance 0 (shares locked in the wYLDS contract). NAV stays continuous.

### ⚠️ Blocker resolved — PRIME NAV oracle staleness (affects Variant B step c only)

`PRIME.redeem` first reverted: `getVerifiedNav()` → Hastra FeedVerifier `StalePrice`. The NAV oracle is **proxy `0xdF4ab20fA7752Be52E41e42F1FD667f37964d6a3`** (impl `0xbc6023cb49f8e8ca6cef563d5fd97ba4c6a5d937`), `navFeedId = 0x0007c8ed155d952e003b1e15ce7666fea785cfbe216577d578fce3920e997271`, price 1,049,629,415,611,939,435, `defaultMaxStaleness = 3600s`, `maxStalenessByFeed[navFeedId] = 0`. The fork's wall-clock had drifted ~4,192s past the feed's last update, exceeding 3,600s.

**Fix (fork):** the FeedVerifier proxy stores `defaultMaxStaleness` in **storage slot 306** (found empirically = 0xE10; `maxStalenessByFeed` mapping base is slot 307). Overrode slot 306 → 315,360,000 (10y) via `tenderly_setStorageAt` — `getVerifiedNav()` then returned 1.049629e18 and `convertToAssets(all)` = 142,988.855896 wYLDS. Cleaner alternative (no storage guess): impersonate the FeedVerifier DEFAULT_ADMIN `0x8D358B8aE881F8ea92C3d07783aBCA21727C6309` and call `setMaxStalenessByFeed(navFeedId, 315360000)` or `setMaxStaleness(315360000)` (both `onlyRole(DEFAULT_ADMIN_ROLE)`). **Variant A avoids this entirely** (it sells PRIME on the DEX and never calls `getVerifiedNav`). Stage 4 must preserve/extend this feed on any fork that time-warps.

## Phase 2 — settlement (admin-gated, separate tx / cross-cycle)

**REWARDS_ADMIN holders confirmed live on the fork** (`hasRole(keccak256("REWARDS_ADMIN")=0x5b1d…b54b, …)`):

- `0x8D358B8aE881F8ea92C3d07783aBCA21727C6309` — also DEFAULT_ADMIN ✅
- `0x997E2Efbce91D170B00EA402e35a66C887EE1da9` ✅
- redeemVault `0xA8C3CF…faCd` ✅

(Confirms the two `caller_role_holders` in specs.yaml. No `grantRole` was needed — impersonated an existing holder.)

| # | Leg                           | Target              | Selector                                                 | Args                        | Result                                                                                                               | Gas     | Status |
| - | ----------------------------- | ------------------- | -------------------------------------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------- | ------- | ------ |
| e | fund redeemVault              | (cheat)             | `tenderly_setErc20Balance`                               | USDC(redeemVault)=200,000e6 | vault had only 972.19 USDC (< 142,988.86 needed); allowance→wYLDS 5,881,907.90 already sufficient                    | —       | —      |
| f | **completeRedeem**            | wYLDS               | `completeRedeem(user)` `0x59d76fe7` (from REWARDS_ADMIN) | user=caliber                | pending → `[0,0,0]` (deleted); caliber USDC 1.000001 → **142,989.855897** (+142,988.855896); redeemVault → 57,011.14 | 87,470  | ✅     |
| g | approve + **swap USDC→PYUSD** | Curve `0x383E…8559` | `exchange(1,0,142988.855896e6,0)`                        | i=1(USDC), j=0(PYUSD)       | → **142,971.321812 PYUSD** (rate 0.99988)                                                                            | 167,184 | ✅     |

## Variant B round-trip & pending→settled NAV handoff (no double count)

```
START equity                                = 99,998.174969 PYUSD
FINAL caliber: PYUSD 185,971.170143 + USDC 1.000001
  minus fund PYUSD injected for repay (86,000.009851)
END equity (net)                            = 99,972.160293 PYUSD
round-trip cost                             = 26.014 PYUSD = 0.0260%
```

Variant B is **cheaper than Variant A** (26.0 vs 63.7 PYUSD): PRIME redeems at full NAV (1.049629) and wYLDS→USDC is 1:1 with no DEX slippage — only the Curve USDC→PYUSD leg (0.012%) + the oracle-vs-NAV mark gap (~8.3) + interest cost anything. The price is the async settlement window + the hard Hastra REWARDS_ADMIN dependency.

**No double count at the handoff (verified):** during the async window the 142,988.855896 wYLDS shares are locked inside the wYLDS contract (caliber wYLDS = 0, not in loose balances) while the ACCOUNTING pending term supplies their USDC value. At `completeRedeem`, `pendingRedemptions[caliber]` is `delete`d in the **same tx** the 142,988.855896 USDC lands loose — observed `pending [0,0,0]` and caliber USDC +142,988.855896 simultaneously. USDC is a registered base token on dusd; the term and native USDC accounting never overlap. (Matches execution-account.md.)

---

# TASK 3 — Partial deleverage (no repay): VIABLE

Withdraw collateral headroom above LLTV without touching debt — needs **no external PYUSD**.

```
min_collateral_to_stay_healthy = debt * 1e36 / (price * lltv)
                               = 86,000.009851e6 * 1e36 / (1.049690555e36 * 0.86)
                               = 95,266.181978 PRIME
withdrawable headroom          = 136,227.942710 − 95,266.181978 = 40,961.760732 PRIME (~42,997.17 PYUSD) @ HF=1.0
```

**Validated on-chain:**

- `withdrawCollateral(40,000 PRIME)` → ✅ status 1, gas 157,102. New collateral 96,227.942710 PRIME, **HF 1.010, LTV 0.8514**, 40,000 PRIME to caliber.
- `withdrawCollateral(+2,000 PRIME)` (total 42,000 > headroom) → **reverted** (Morpho `_isHealthy` → INSUFFICIENT_COLLATERAL).

Viable as a leverage-reduction path that avoids sourcing PYUSD. At the cap HF≈1.0 (immediately liquidatable) — in production leave a buffer (e.g. keep HF≥1.1 → withdrawable ≈ `coll − debt·1.1/(price·lltv)` ≈ 27.3k PRIME). The freed PRIME then exits via `PRIME.redeem → wYLDS.requestRedeem` (async) or a sync Uni V3 sale (Variant-A route).

---

# What the Stage 3 WITHDRAW blueprint must expose & operator sequencing

**A deep sync DEX route for PRIME EXISTS**, so unlike a typical RWA loop, Variant A is available and should be the primary close path. Both variants should be wired:

1. **Variant A — atomic close (primary, one FLASHLOAN_MANAGEMENT instruction).** Sequence inside the Morpho flash-loan callback: `repay(shares=borrowShares)` (full) → `withdrawCollateral(all PRIME)` → `swap PRIME→USDC` (swap_module, offchain aggregator calldata, UniV3 0.01% venue) → `swap USDC→PYUSD` (swap_module, Curve venue) → repay FL from proceeds. Mirrors `blueprints/morpho-loop/withdraw-swap.yaml:close_loop` but with **two swap legs** (no direct PRIME/PYUSD pool) instead of one, and **no ERC4626 unwrap** (PRIME is sold, not redeemed). Approvals: PYUSD→Morpho, PRIME→swap_module, USDC→swap_module. Sizeable amounts must respect Uni V3 pool depth (fine at ~136k; monitor for larger positions). This is the only leg the operator runs — self-contained, no async gap.

2. **Variant B — staged async unwind (fallback / NAV-optimal / large size).** Split across the async gap:
   - **Instruction B1 (management, one tx):** `repay(shares=borrowShares)` + `withdrawCollateral(all PRIME)` + `PRIME.redeem(all)→wYLDS` + `wYLDS.requestRedeem(all)`. Repay funded from **idle fund PYUSD** (a same-tx FL is impossible here — it cannot be repaid before settlement). Leaves a pending redemption; ACCOUNTING's pending term keeps NAV flat.
   - **[async gap — OFF-CHAIN, not a caliber instruction]:** Hastra REWARDS_ADMIN calls `wYLDS.completeRedeem(caliber)` once redeemVault is funded. Hard operational dependency; no on-chain timelock. `completeRedeem` reverts `InsufficientVaultBalance` until the vault holds ≥ pending.assets (live mainnet vault held only ~972 USDC).
   - **Instruction B2 (management, separate tx, after USDC lands):** `swap USDC→PYUSD` (swap_module, Curve). Operator triggers this once `pendingRedemptions(caliber)==0` and USDC is loose.
   - ACCOUNTING blueprint (already designed, execution-account.md) needs no change — its `pendingRedemptions(caliber).assets` term bridges B1→B2.

3. **Partial deleverage:** a bare `withdrawCollateral` management instruction (`blueprints/morpho-loop/withdraw.yaml`), amount bounded off-chain by the health headroom; PRIME then exits via A- or B-style legs.

**Operator sequencing summary:** Variant A = single tx, no gap. Variant B = B1 (tx) → wait for Hastra completeRedeem (cross-cycle, off-chain) → B2 (tx); NAV is continuous throughout via the pending term.

---

## Environment / methodology notes

- Tenderly `execute_code` timed out on multi-transaction blocks and dropped `def` helpers between calls; ran one tx per block with `send_transaction` (Tenderly auto-mines) and read receipts in a following block.
- Two nested snapshots used (Variant A, Variant B), each reverted after; a stray `setErc20Balance` from a timed-out block briefly bumped loose PYUSD to 129k and was restored to 43,000 before anchoring the baseline. Final state reverted to the clean OPEN baseline.
- Fork wall-clock has drifted forward during testing, so PRIME's NAV feed is now stale under the original 3,600s window — Stage 4 should use a fresh fork or extend `defaultMaxStaleness` (slot 306 on `0xdF4ab20f…`, or admin `setMaxStalenessByFeed`) before any `PRIME.redeem`/`convertToAssets`.

## Tx hashes (final validated runs)

| Leg                   | Tx                                                                   |
| --------------------- | -------------------------------------------------------------------- |
| A repay               | `0xd621b02933b82ab653397dd42d4454ecb391e509cf6490b2846e28a5b36c09a1` |
| A withdrawCollateral  | `0x91e68d53b763778e81d7f82c10cb8458f5045cb01f9eb793128c2247c3cbd9d7` |
| A swap PRIME→USDC     | `0x03b177df2e1ff2d8b8d0d63d6d02b93dbe62409e0d9fb39b465ad5b1095ead28` |
| A swap USDC→PYUSD     | `0xd7cd8fbe16855e3b0b9c3ef494f8fb4989d29224b8bd215b14ee2fff6f4bded6` |
| B PRIME.redeem        | `0x4d03a7313be9f9de6c42594b9c5d37fffc3a6d668bad4f45884da545c4dd705f` |
| B wYLDS.requestRedeem | `0x39a0ec3c2330a3989fee008a612bde4db3f1ce7b36075f6dab65a7fc536ab557` |
| B completeRedeem      | `0x37368cdf6c7905c6eecd87f8f281913a08217874f9942cebf2415505a012b395` |
| B swap USDC→PYUSD     | `0xa3996afe130f01a3d427d9fab4d4c91ab6fcaf4e4bec2d11a5c36e7fa878dd35` |

**No unexplained reverts.** The only revert (PRIME.redeem StalePrice) was root-caused and fixed. Both close variants and the partial deleverage validated; fork restored to the pristine OPEN baseline.
