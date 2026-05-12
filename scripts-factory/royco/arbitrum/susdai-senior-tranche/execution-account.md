## Execution Report

**Action**: account
**Chain**: Arbitrum (42161)
**VNet ID**: `1caf0022-d243-490b-8ff6-2cb769d513a9`
**RPC URL**: `https://virtual.arbitrum.eu.rpc.tenderly.co/ee3b751d-a854-46b3-bf3f-3e831d4263b9`
**Test Address**: `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450`

All calls in this report are **view calls** (no gas, no state changes).

---

### Call 1: Kernel.syncTrancheAccounting()

**Contract**: `0xFdb17E53eA5d342124b8473188BCB9F05F1949CA` (Kernel)
**Function**: `syncTrancheAccounting()`
**Type**: State-changing (attempted)

**Result**: FAILED -- AccessManaged, caller not authorized for `syncTrancheAccounting` selector `0x9c8e2dc0`.

**Note**: This call is **NOT required** for accounting. `ST.convertToAssets()` internally calls `_previewPostSyncTrancheState()` which delegates to `Kernel.previewSyncTrancheAccounting()`, applying NAV reconciliation as a view. The blueprint should skip this call.

---

### Call 2: SeniorTranche.balanceOf(account)

**Contract**: `0x90465aad4e426948A4ea342AC49A1A38200B7017` (Senior Tranche)
**Function**: `balanceOf(address) returns (uint256)`
**Type**: View

**Inputs**:

| Param   | Value                                      | Type    |
| ------- | ------------------------------------------ | ------- |
| account | 0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450 | address |

**Outputs**:

| Name      | Value (raw)       | Value (human)     | Type    |
| --------- | ----------------- | ----------------- | ------- |
| st_shares | 89761092607302279 | ~0.0898 ST shares | uint256 |

**Raw return hex**: `0x000000000000000000000000000000000000000000000000013ee53cf7825a87`

---

### Call 3: SeniorTranche.convertToAssets(st_shares)

**Contract**: `0x90465aad4e426948A4ea342AC49A1A38200B7017` (Senior Tranche)
**Function**: `convertToAssets(uint256) returns (uint256 stAssets, uint256 jtAssets, uint256 nav)`
**Type**: View
**CRITICAL**: Returns a 3-element tuple `(uint256, uint256, uint256)`, NOT a single uint256.

**Inputs**:

| Param  | Value             | Type    |
| ------ | ----------------- | ------- |
| shares | 89761092607302279 | uint256 |

**Outputs**:

| Name     | Value (raw)       | Value (human)     | Type    |
| -------- | ----------------- | ----------------- | ------- |
| stAssets | 83492137488708642 | ~0.0835 sUSDai    | uint256 |
| jtAssets | 0                 | 0                 | uint256 |
| nav      | 89976994963548222 | ~0.0900 USD (18d) | uint256 |

**Raw return hex**: `0x00000000000000000000000000000000000000000000000001289fa81c8d74220000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000013fa999a6c2683e`

**Tuple extraction verified**: `extractElementFromStaticTuple(bytes, 2)` on Arbitrum revertable caliber helper `0x6b09a22087B5D6C7E1051ee9a8AA94eA56C91008` correctly returns `0x000000000000000000000000000000000000000000000000013fa999a6c2683e` = 89976994963548222.

---

### Call 4: Scale NAV to USDC (18 dec -> 6 dec)

**Contract**: `0x49a05b9c885086D0BA363281628e48E0aB86dEAf` (Arbitrum Math Helper)
**Function**: `mulDiv(uint256,uint256,uint256) returns (uint256)`
**Type**: View

**Inputs**:

| Param       | Value             | Type    |
| ----------- | ----------------- | ------- |
| x           | 89976994963548222 | uint256 |
| y           | 1                 | uint256 |
| denominator | 1000000000000     | uint256 |

**Outputs**:

| Name       | Value (raw) | Value (human) | Type    |
| ---------- | ----------- | ------------- | ------- |
| usdc_value | 89976       | 0.089976 USDC | uint256 |

**Note**: `div(uint256,uint256)` is NOT available on the Arbitrum math helper. Must use `mulDiv(nav, 1, 1e12)` instead.

---

### Call 5: sUSDai.balanceOf(account)

**Contract**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (sUSDai)
**Function**: `balanceOf(address) returns (uint256)`
**Type**: View

**Inputs**:

| Param   | Value                                      | Type    |
| ------- | ------------------------------------------ | ------- |
| account | 0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450 | address |

**Outputs**:

| Name           | Value (raw) | Value (human) | Type    |
| -------------- | ----------- | ------------- | ------- |
| susdai_balance | 0           | 0             | uint256 |

---

### Call 6: USDai.balanceOf(account)

**Contract**: `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF` (USDai)
**Function**: `balanceOf(address) returns (uint256)`
**Type**: View

**Inputs**:

| Param   | Value                                      | Type    |
| ------- | ------------------------------------------ | ------- |
| account | 0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450 | address |

**Outputs**:

| Name          | Value (raw) | Value (human) | Type    |
| ------------- | ----------- | ------------- | ------- |
| usdai_balance | 0           | 0             | uint256 |

---

### Call 7: sUSDai.redemptionIds(account)

**Contract**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (sUSDai)
**Function**: `redemptionIds(address) returns (uint256[])`
**Type**: View

**Inputs**:

| Param      | Value                                      | Type    |
| ---------- | ------------------------------------------ | ------- |
| controller | 0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450 | address |

**Outputs**:

| Name           | Value (raw) | Value (human)          | Type      |
| -------------- | ----------- | ---------------------- | --------- |
| redemption_ids | [] (empty)  | No pending redemptions | uint256[] |

---

### Call 8: sUSDai.maxRedeem(account)

**Contract**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (sUSDai)
**Function**: `maxRedeem(address) returns (uint256)`
**Type**: View

**Inputs**:

| Param      | Value                                      | Type    |
| ---------- | ------------------------------------------ | ------- |
| controller | 0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450 | address |

**Outputs**:

| Name              | Value (raw) | Value (human)           | Type    |
| ----------------- | ----------- | ----------------------- | ------- |
| redeemable_shares | 0           | No serviced redemptions | uint256 |

---

### Call 9: Kernel.getTrancheUnitToNAVUnitConversionRateWAD()

**Contract**: `0xFdb17E53eA5d342124b8473188BCB9F05F1949CA` (Kernel)
**Function**: `getTrancheUnitToNAVUnitConversionRateWAD() returns (uint256)`
**Type**: View

**Outputs**:

| Name                         | Value (raw)         | Value (human)      | Type    |
| ---------------------------- | ------------------- | ------------------ | ------- |
| sUSDaiToUSDConversionRateWAD | 1077670277344577296 | ~1.0777 sUSDai:USD | uint256 |

**Raw return hex**: `0x0000000000000000000000000000000000000000000000000ef4a768521ec710`

---

### Call 10: sUSDai.redemptionSharePrice()

**Contract**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (sUSDai)
**Function**: `redemptionSharePrice() returns (uint256)`
**Type**: View

**Outputs**:

| Name                 | Value (raw)         | Value (human)        | Type    |
| -------------------- | ------------------- | -------------------- | ------- |
| redemptionSharePrice | 1077670277344577296 | ~1.0777 sUSDai:USDai | uint256 |

**Note**: Matches the sUSDai-to-USDai component of `getTrancheUnitToNAVUnitConversionRateWAD()` since `storedConversionRateWAD` = 1e18 (1:1 USDai:USD peg).

---

### Call 11: Kernel.getStoredConversionRateWAD()

**Contract**: `0xFdb17E53eA5d342124b8473188BCB9F05F1949CA` (Kernel)
**Function**: `getStoredConversionRateWAD() returns (uint256)`
**Type**: View

**Outputs**:

| Name                    | Value (raw)         | Value (human) | Type    |
| ----------------------- | ------------------- | ------------- | ------- |
| storedConversionRateWAD | 1000000000000000000 | 1.0 (1:1 peg) | uint256 |

---

### Call 12: sUSDai.depositSharePrice()

**Contract**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (sUSDai)
**Function**: `depositSharePrice() returns (uint256)`
**Type**: View

**Outputs**:

| Name              | Value (raw)         | Value (human)        | Type    |
| ----------------- | ------------------- | -------------------- | ------- |
| depositSharePrice | 1077945961643850095 | ~1.0779 sUSDai:USDai | uint256 |

**Note**: Slightly higher than `redemptionSharePrice` (1077670277344577296) -- the OPTIMISTIC vs CONSERVATIVE valuation spread is ~0.026%.

---

### Edge Cases Tested

| Scenario              | Input              | Result    | Notes                               |
| --------------------- | ------------------ | --------- | ----------------------------------- |
| ST convertToAssets(0) | 0                  | (0, 0, 0) | Safe -- returns all zeros           |
| sUSDai balanceOf = 0  | balanceOf(account) | 0         | Expected when fully deposited in ST |
| USDai balanceOf = 0   | balanceOf(account) | 0         | Expected when not mid-withdrawal    |
| redemptionIds empty   | redemptionIds(acc) | []        | No active redemptions               |
| maxRedeem = 0         | maxRedeem(account) | 0         | No serviced redemptions to claim    |

---

### Full Accounting Calculation

```
Step 1: st_shares          = SeniorTranche.balanceOf(account)              = 89,761,092,607,302,279 (~0.0898 shares)
Step 2: (stAssets, _, nav)  = SeniorTranche.convertToAssets(st_shares)
                              stAssets = 83,492,137,488,708,642 (~0.0835 sUSDai)
                              nav      = 89,976,994,963,548,222 (~0.0900 USD, 18 decimals)
Step 3: usdc_value          = mulDiv(nav, 1, 1e12)                         = 89,976 (0.089976 USDC)
Step 4: susdai_balance      = sUSDai.balanceOf(account)                    = 0
Step 5: usdai_balance       = USDai.balanceOf(account)                     = 0
Step 6: maxRedeem            = sUSDai.maxRedeem(account)                    = 0 (no queue value)
```

**Result**: Position value = **0.089976 USDC** (deposited 0.09 PYUSD worth ~0.09 USD, difference = -0.000024 from rounding/fees)

---

### Math Verification

**NAV derivation** (manual):

```python
st_shares = 89761092607302279
stAssets = 83492137488708642          # sUSDai claim from ST shares
redemptionSharePrice = 1077670277344577296  # sUSDai -> USDai rate (CONSERVATIVE)
storedConversionRate = 1000000000000000000  # USDai -> USD rate (1:1)

# nav = stAssets * redemptionSharePrice * storedConversionRate / WAD^2
nav_manual = (stAssets * redemptionSharePrice * storedConversionRate) // (10**18 * 10**18)
# = 89,976,994,963,548,221 (off by 1 from 89,976,994,963,548,222 due to rounding in Kernel)

# Scale to USDC (6 decimals)
usdc_value = nav_manual // 10**12
# = 89,976 (0.089976 USDC)
```

**Cross-check**: `sUSDai.convertToAssets(stAssets)` returns 90,000,012,434,966,585 (~0.0900 USDai), consistent with `stAssets * depositSharePrice / 1e18` using the OPTIMISTIC rate.

---

### Exchange Rate Context

| Metric                                          | Value                             |
| ----------------------------------------------- | --------------------------------- |
| sUSDai redemptionSharePrice                     | 1,077,670,277,344,577,296         |
| sUSDai depositSharePrice                        | 1,077,945,961,643,850,095         |
| Kernel storedConversionRateWAD                  | 1,000,000,000,000,000,000         |
| Kernel getTrancheUnitToNAVUnitConversionRateWAD | 1,077,670,277,344,577,296         |
| sUSDai/USDai rate (redemption)                  | ~1.0777 USDai per sUSDai          |
| sUSDai/USDai rate (deposit)                     | ~1.0779 USDai per sUSDai          |
| USDai/USD rate                                  | 1.0000 (admin-set oracle)         |
| ST totalSupply                                  | 949,546,868,773,544,846 (~0.9495) |
| ST share price (nav/share)                      | ~1.0024 USD per share             |
| ST share price (stAssets/share)                 | ~0.9301 sUSDai per share          |

---

### Blueprint Mapping

The accounting blueprint must execute view calls and one math operation. Here is the call sequence mapped to blueprint steps:

**Slot 0: USDC value of active ST position**:

```
Blueprint Call Sequence (Slot 0):
  1. context_helper.msgSender()                                    -> caliber_address
  2. senior_tranche.balanceOf(caliber_address)                     -> st_shares
  3. senior_tranche.convertToAssets(st_shares)                     -> asset_claims (bytes tuple)
  4. caliber_helper.extractElementFromStaticTuple(asset_claims, 2) -> nav_18dec (uint256)
  5. math_helper.mulDiv(nav_18dec, 1, 1e12)                        -> usdc_value (SLOT 0)
```

**Slot 1: Value of sUSDai in redemption queue (pending + redeemable)**:

```
Blueprint Call Sequence (Slot 1):
  6. susdai.maxRedeem(caliber_address)                             -> redeemable_shares
  7. [If needed: sum pending shares from redemptionIds iteration -- complex, see note]
  8. [Convert queue shares to USD via Kernel rate and scale to USDC]
  9. Result                                                        -> queue_usdc_value (SLOT 1)
```

**Note on Slot 1**: `maxRedeem` returns only redeemable (serviced) shares. Pending shares require iterating `redemptionIds` and summing `pendingRedeemRequest` per ID. Since weiroll cannot iterate dynamic arrays, the blueprint should either:

- Use a fixed number of redemption ID slots (like sNUSD cooldowns approach), or
- Only track redeemable shares (conservative -- understates value during queue wait), or
- Use a custom helper that sums all pending + redeemable shares

**Slot 2: Sentinel**:

```
10. math_helper.uint256Max()                                     -> UINT256_MAX (SLOT 2)
```

**Helper contracts needed (Arbitrum)**:

| Helper                    | Address                                      | Purpose                        |
| ------------------------- | -------------------------------------------- | ------------------------------ |
| Context Helper            | `0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE` | Get caliber address at runtime |
| Revertable Caliber Helper | `0x6b09a22087B5D6C7E1051ee9a8AA94eA56C91008` | Extract nav from tuple return  |
| Math Helper (Arbitrum)    | `0x49a05b9c885086D0BA363281628e48E0aB86dEAf` | mulDiv for decimal scaling     |

**Key blueprint details**:

1. **`syncTrancheAccounting()` is NOT needed** -- `convertToAssets()` internally previews post-sync state. Also, the function is access-controlled and would revert from the caliber address.
2. **Senior Tranche `convertToAssets`** returns `(uint256, uint256, uint256)` -- must use `extractElementFromStaticTuple(bytes, 2)` to get `nav` (index 2, the USD value).
3. **NAV is already in USD** (18 decimals) -- scale to USDC with `mulDiv(nav, 1, 1e12)`.
4. **Arbitrum math helper does NOT have `div()`** -- must use `mulDiv(x, 1, d)` as workaround.
5. **Arbitrum math helper does NOT have `scaleAmount()`** -- must use `mulDiv`.
6. **Queue value (Slot 1)**: For a minimal implementation, use `maxRedeem(caliber)` for redeemable shares. To get pending shares, would need to iterate `redemptionIds` array -- this is complex in weiroll. If the withdrawal blueprint always processes one redemption at a time, consider tracking the redemption ID in KV store and querying `pendingRedeemRequest(id, controller)` + `claimableRedeemRequest(id, controller)` directly.
7. All calls except `syncTrancheAccounting` are **pure view calls** -- no approvals, no state changes.
8. The final `usdc_value` result is the position value in USDC with 6 decimal places.

---

### Position State Summary

| State                      | Balance          | USD Value        | Notes                                                              |
| -------------------------- | ---------------- | ---------------- | ------------------------------------------------------------------ |
| Active ST shares           | 0.0898 ST shares | 0.089977 USD     | Primary position                                                   |
| sUSDai held directly       | 0                | 0                | Transient -- only nonzero between ST redeem and requestRedeem      |
| USDai held directly        | 0                | 0                | Transient -- only nonzero between sUSDai redeem and USDai withdraw |
| sUSDai in redemption queue | 0                | 0                | Nonzero between requestRedeem and redeem (after service)           |
| **Total**                  |                  | **0.089977 USD** | **= 0.089976 USDC (after 18->6 truncation)**                       |
