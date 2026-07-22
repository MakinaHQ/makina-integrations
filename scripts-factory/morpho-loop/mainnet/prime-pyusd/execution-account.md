# Execution Report — ACCOUNT (equity / NAV)

**Action**: account (equity in PYUSD, position model) — PRIME/PYUSD Morpho loop
**Chain**: mainnet (ethereum)
**Machine**: dusd
**Executor / reader**: caliber `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC`
**Testnet**: `8f992f50-3553-441e-aae5-26a38d5bb786` (SHARED fork, reused — no new fork created)
**Fork block**: 25,587,182
**Fork left**: OPEN + PRISTINE (position unchanged, no pending redemption, 43,000 loose PYUSD intact) for the withdraw test.

Equity model validated:

```
equity_PYUSD = max(0, collateral_PRIME * oracle.price()/1e36  -  debt_PYUSD)
             + pendingRedemptions(caliber).assets           (USDC ~1:1 -> PYUSD)
```

---

## Call 1 — `Morpho.position(id, caliber)` (collateral + borrowShares)

**Contract**: `0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb`
**Selector**: `position(bytes32,address)` = `0x93c52062`
**Args**: `id = 0x41c41d0c9aadbf4751f5ee215ed5a16954a4b34e1b70fca5393d4b08858fa3fa`, `user = 0xD1A1C248…c1BC`

**Returns** `(uint256 supplyShares, uint128 borrowShares, uint128 collateral)`:

| Field                | Raw               | Decoded                                                  |
| -------------------- | ----------------- | -------------------------------------------------------- |
| supplyShares         | 0                 | 0                                                        |
| borrowShares (idx 1) | 85277439518424200 | —                                                        |
| collateral (idx 2)   | 136227942710      | **136,227.942710 PRIME** ✅ matches spec (136227.942710) |

---

## Call 2 — `Morpho.market(id)` (debt reconstruction)

**Contract**: `0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb`
**Selector**: `market(bytes32)` = `0x5c60e39a`
**Arg**: `id = 0x41c41d0c…a3fa`

**Returns** `(uint128 totalSupplyAssets, totalSupplyShares, totalBorrowAssets, totalBorrowShares, lastUpdate, fee)`:

| Field                     | Raw                   |
| ------------------------- | --------------------- |
| totalSupplyAssets         | 129897187587635       |
| totalSupplyShares         | 128926859661347007442 |
| totalBorrowAssets (idx 2) | 116203129055442       |
| totalBorrowShares (idx 3) | 115226792730634483444 |
| lastUpdate                | 1784710492            |
| fee                       | 0                     |

**Debt formula** `debt = borrowShares * totalBorrowAssets / max(totalBorrowShares, 1)`:

```
den   = max(115226792730634483444, 1) = 115226792730634483444
num   = 85277439518424200 * 116203129055442
debt_down = num // den                      = 86000009850  = 86000.009850 PYUSD   (mulDiv, rounds DOWN)
debt_up   = (num + den - 1) // den           = 86000009851  = 86000.009851 PYUSD   (Morpho toAssetsUp, rounds UP)
```

**Rounding note (important).** Morpho itself accrues/settles borrow with `toAssetsUp` (round **up**). The stock blueprint reconstructs debt with `MathHelper.mulDiv` which rounds **down**. The two differ by exactly **1 wei** (86000.009850 vs 86000.009851). The blueprint therefore understates debt by ≤1 wei and overstates equity by ≤1 wei (1e-6 PYUSD). This is negligible and matches the wsrUSD precedent behaviour — no fix warranted, documented for completeness. The deposit report's stated debt (86000.009850) is the round-down value.

---

## Call 3 — `MorphoChainlinkOracleV2.price()` (collateral valuation)

**Contract**: `0x335e5718bC20028d5e357473a3736C187Ca6b07e`
**Selector**: `price()` = `0xa035b1fe`

**Returns**: `1049690555221613945938417681788095852` (~1.0496906) ✅ exactly matches spec `price_now`.

**Scaling derivation** (from functions.md oracle immutables — no ERC4626/USDC chaining):

```
price() = SCALE_FACTOR * BASE_FEED_1(PRIME/wYLDS,18d) / QUOTE_FEED_1(PYUSD/USD,8d)
SCALE_FACTOR = 1e26 = 10^(36 + loanDec(6) + quoteFeedDec(8) - collDec(6) - baseFeedDec(18))
Morpho oracle scale = 36 + loanDecimals - collDecimals = 36 + 6 - 6 = 36  (both tokens 6-dec -> clean 1e36)
```

**Collateral value** `collateral_PYUSD = collateral * price() / 1e36`:

```
= 136227942710 * 1049690555221613945938417681788095852 // 1e36
= 142997184819  = 142,997.184819 PYUSD          ✅ matches deposit report
```

Units check: `PRIME(6d) * price(1e36) / 1e36 = PYUSD(6d)`. ✅

---

## Position equity (Calls 1–3)

```
collateral_value = 142997.184819 PYUSD
debt (round-up)  =  86000.009851 PYUSD
equity           = max(0, 142997.184819 - 86000.009851) = 56997.174968 PYUSD
(blueprint mulDiv round-down debt -> equity = 56997.174969, +1 wei)
```

**Reconciliation to the 100k principal.** The position-model equity is **56,997.17 PYUSD**, _not_ 100k, because this is a ~2.5x leveraged position and the ACCOUNTING blueprint measures only the Morpho leg (collateral − debt). The other 43,000 PYUSD of the original principal is sitting **loose in the caliber** (the final unrepaid borrow of the manual 2-cycle lever-up on this fork) and is captured by the caliber's **native PYUSD base-token accounting**, not by this position blueprint. Full NAV reconciles:

| Component             | Source                       | Value (PYUSD)     |
| --------------------- | ---------------------------- | ----------------- |
| Position equity       | this blueprint (coll − debt) | 56,997.174968     |
| Loose PYUSD           | native base-token accounting | 43,000.000000     |
| Loose USDC (~1:1)     | native base-token accounting | 1.000001          |
| **Total caliber NAV** |                              | **99,998.174969** |

≈ 100,000 principal minus ~1.8 PYUSD of aggregate swap slippage across the two PYUSD→USDC legs. ✅ (In a true atomic flash-loop the final borrow repays the flash loan, so there would be no loose PYUSD and the full principal would live inside the Morpho position — the blueprint equity would then be ~100k directly. On this fork the loop was staged manually, so 43k is loose. Both cases NAV-reconcile.)

---

## Call 4 — PENDING TERM demonstration (snapshot → requestRedeem → revert)

To prove the pending-redemption term keeps NAV continuous across the async wYLDS→USDC window **without disturbing the Morpho position**, a snapshot was taken, a small separate 1,000 USDC balance was wrapped and redeem-requested as the caliber, the pending state was read, then the fork was reverted.

**Snapshot** `evm_snapshot` → `0x82b43606f7de7da168493d67d1fa71df99ecbb9e69b481b56107716557359737`

State BEFORE (pristine):

| Item                        | Value                                  |
| --------------------------- | -------------------------------------- |
| position(id, caliber)       | `[0, 85277439518424200, 136227942710]` |
| pendingRedemptions(caliber) | `[0, 0, 0]`                            |
| loose PYUSD                 | 43,000.000000                          |

Steps (executor = caliber, impersonated; USDC balance topped to 1,001 via `tenderly_setErc20Balance`):

| # | Call                       | Target              | Selector     | Status                            |
| - | -------------------------- | ------------------- | ------------ | --------------------------------- |
| a | `approve(wYLDS, 1000e6)`   | USDC                | `0x095ea7b3` | ✅ 1                              |
| b | `deposit(1000e6, caliber)` | wYLDS `0x6aD0…66Cc` | `0x6e553f65` | ✅ 1 → 1,000.0 wYLDS minted (1:1) |
| c | `requestRedeem(1000e6)`    | wYLDS `0x6aD0…66Cc` | `0xaa2f892d` | ✅ 1                              |

**`pendingRedemptions(caliber)` AFTER requestRedeem** (`0xe50fe9b9`) → `(shares, assets, timestamp)`:

| Field     | Raw        | Decoded                                          |
| --------- | ---------- | ------------------------------------------------ |
| shares    | 1000000000 | 1,000.0 wYLDS (locked in vault)                  |
| assets    | 1000000000 | **1,000.0 USDC owed** (the term added to equity) |
| timestamp | 1784710899 | request block time                               |

**`getPendingRedemption(caliber)`** (`0x163421d0`) → `[True, 1000000000, 1000000000]` (hasPending, shares, assets). ✅

Balance hand-off during the async window (no double-count):

- caliber wYLDS balance → **0** (the 1,000 shares moved into the wYLDS contract)
- caliber USDC balance → **1.000001** (the 1,000 USDC left the loose balance)
- So native USDC accounting drops by 1,000 exactly as the pending term rises by 1,000 → NAV flat.

**Equity WITH pending term:**

```
equity_with_pending = position_equity + pendingRedemptions.assets
                    = 56997.174968 + 1000.000000
                    = 57997.174968 PYUSD
```

When Hastra's REWARDS_ADMIN later calls `completeRedeem(caliber)`, `pendingRedemptions[caliber]` is `delete`d (term → 0) at the same instant the 1,000 USDC lands loose in the caliber (recaptured by native accounting). No moment of NAV dip, no double count. Confirmed by functions.md `completeRedeem` (deletes the mapping before the transfer).

**Revert** `evm_revert(snap_id)` → `True`. State AFTER revert (pristine, verified):

| Item                        | Value                                  | Match to before |
| --------------------------- | -------------------------------------- | --------------- |
| position(id, caliber)       | `[0, 85277439518424200, 136227942710]` | ✅ unchanged    |
| pendingRedemptions(caliber) | `[0, 0, 0]`                            | ✅ zero         |
| loose PYUSD                 | 43,000.000000                          | ✅ unchanged    |
| caliber wYLDS               | 0                                      | ✅              |

**The Morpho position was never touched** — the demonstration used only an isolated, freshly-funded wYLDS balance, and the revert restored everything.

---

## Mapping to the ACCOUNT blueprint primitives (verified on deployed helpers)

The stock `blueprints/morpho-loop/account.yaml:account_equity` (the wsrUSD/USDC precedent) was replayed against the **deployed** helper contracts and reproduces every intermediate value bit-for-bit:

**caliber_helper `0x6E2ED2f457c41F38556Ab0c2b1185cc9e6563d8D`** — `extractElementFromStaticTuple(bytes,uint256)`:

| Extract                             | idx | Result                | == on-chain |
| ----------------------------------- | --- | --------------------- | ----------- |
| collateral from position tuple      | 2   | 136227942710          | ✅          |
| borrowShares from position tuple    | 1   | 85277439518424200     | ✅          |
| totalBorrowShares from market tuple | 3   | 115226792730634483444 | ✅          |
| totalBorrowAssets from market tuple | 2   | 116203129055442       | ✅          |

**unsigned_math_helper `0x836C9007DbD73fcFC473190304C72b7E39BaBb91`**:

| Op               | Call                                                                | Result                                                     |
| ---------------- | ------------------------------------------------------------------- | ---------------------------------------------------------- |
| debt             | `mulDiv(borrowShares, totalBorrowAssets, max(totalBorrowShares,1))` | 86000009850 (86000.009850, rounds down)                    |
| floor            | `max(totalBorrowShares, 1)`                                         | 115226792730634483444                                      |
| collateral value | `mulDiv(collateral, price, 1e36)`                                   | 142997184819 (142997.184819)                               |
| capped debt      | `min(debt, collateral_value)`                                       | 86000009850                                                |
| equity           | `sub(capped_debt, collateral_value)` (note: `sub(a,b)=b-a`)         | 56997174969 (56997.174969)                                 |
| **pending fold** | `add(equity, pending_assets)`                                       | 57997174969 — **`add` op confirmed present** on the helper |

### Blueprint delta vs the wsrUSD/USDC precedent (`account_equity`)

1. **Oracle scaling — UNCHANGED.** wsrUSD/USDC already uses `account_equity` with `mulDiv(collateral, price, 1e36)`. PRIME/PYUSD is identical: both loan and collateral are 6-dec, so the Morpho oracle scale is a clean `1e36` and the exact same `1000000000000000000000000000000000000` divisor constant applies verbatim. No scaling change is needed. (The base variant `account_loop`, which uses `convertToAssets`, is _not_ applicable here because PRIME's underlying is wYLDS, not the PYUSD loan token — `account_equity` is the correct precedent.)

2. **ADDED PENDING TERM — the only real delta.** Append three calls after the existing `equity_in_loan_token` step and move the reserved slot to the summed value:
   - `wYLDS.pendingRedemptions(caliber)` → `(uint256,uint256,uint256)` tuple _(target = wYLDS `0x6aD0…66Cc`, selector `0xe50fe9b9`)_
   - `caliber_helper.extractElementFromStaticTuple(tuple, 1)` → `pending_assets` (the USDC owed; index 1) — verified extractable
   - `math_helper.add(equity_in_loan_token, pending_assets)` → `equity_with_pending` — `add` verified present on the deployed math helper
   - `reserved_slots[0]` becomes `${returns.equity_with_pending}` instead of `${returns.equity_in_loan_token}`.

3. **KV mirror — NOT required.** `pendingRedemptions` is read **live on-chain** and self-zeros on `completeRedeem` (mapping `delete`d before the USDC transfer), so the term hands off cleanly to the caliber's native USDC base-token accounting with no double-count and no stale value. A `key_value_store` (`0xa81fC382489F9560211AB15aD87f001b98C92E91`) mirror is only warranted if the reference framework mandates a fixed accounting-call count or if reading a struct-getter tuple in the accounting path is disallowed; functionally it is unnecessary here. USDC being a registered base token on dusd is safe: during the async window the USDC is locked inside the wYLDS contract (caliber USDC balance excludes it) while the pending term supplies its value; at completion the mapping is deleted the same instant the USDC lands loose.

### Blueprint inputs for PRIME/PYUSD `account_equity`

```
morpho_address    = 0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb
morpho_market_id  = 0x41c41d0c9aadbf4751f5ee215ed5a16954a4b34e1b70fca5393d4b08858fa3fa
oracle_address    = 0x335e5718bC20028d5e357473a3736C187Ca6b07e
caliber_helper    = 0x6E2ED2f457c41F38556Ab0c2b1185cc9e6563d8D
math_helper       = 0x836C9007DbD73fcFC473190304C72b7E39BaBb91
caliber_address   = 0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC
# + pending term extension: wylds_address = 0x6aD038cA6C04e885630851278ca0a856Ad9a66Cc (pendingRedemptions selector 0xe50fe9b9)
```

---

## Summary of validation results

| Check                                                       | Result                                                                                    |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| collateral matches spec/deposit                             | ✅ 136,227.942710 PRIME                                                                   |
| debt reconstruction (mulDiv, round-down vs Morpho round-up) | ✅ 86000.009850 (blueprint) / 86000.009851 (Morpho); ≤1 wei, documented                   |
| oracle price + 1e36 scaling                                 | ✅ 1.0496906e36; scale = 36 + loanDec − collDec = 36                                      |
| collateral value                                            | ✅ 142,997.184819 PYUSD                                                                   |
| position equity                                             | ✅ 56,997.174968 PYUSD (blueprint 56,997.174969, +1 wei)                                  |
| NAV reconciles to ~100k principal                           | ✅ 99,998.17 PYUSD (position 56,997 + loose 43,000 + 1 USDC; ~1.8 slippage)               |
| pending term readable live                                  | ✅ pendingRedemptions.assets = 1,000 USDC; getPendingRedemption confirms                  |
| pending term keeps NAV continuous                           | ✅ USDC leaves loose balance exactly as pending term rises; self-zeros on complete        |
| deployed helpers reproduce arithmetic                       | ✅ extractElementFromStaticTuple / mulDiv / max / min / sub / add all match               |
| KV mirror needed                                            | ❌ Not required (live read self-zeros)                                                    |
| oracle-scaling delta vs wsrUSD                              | none (identical 1e36) — only delta is added pending term                                  |
| **fork left OPEN + PRISTINE**                               | ✅ position `[0, 85277439518424200, 136227942710]`, pending `[0,0,0]`, loose PYUSD 43,000 |

**No reverts.** All reads and the pending demonstration succeeded on first attempt; the fork is ready for the withdraw test.
