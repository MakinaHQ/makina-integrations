# Execution Report: Withdraw

**Action**: withdraw
**Chain**: Arbitrum (42161)
**VNet ID**: `1caf0022-d243-490b-8ff6-2cb769d513a9`
**Admin RPC**: `https://virtual.arbitrum.eu.rpc.tenderly.co/ee3b751d-a854-46b3-bf3f-3e831d4263b9`
**Test Address**: `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450`

---

## Withdraw Flow Summary

The full withdrawal path is: **ST shares -> sUSDai -> requestRedeem -> (admin serviceRedemptions) -> redeem/claim -> USDai -> PYUSD**

This is a multi-step, multi-transaction flow with an off-chain queue servicing step between requestRedeem and claim.

### Transaction 1 (User): ST.redeem + sUSDai.requestRedeem

### Admin Action: serviceRedemptions (off-chain, by STRATEGY_ADMIN)

### Transaction 2 (User): sUSDai.redeem (claim) + USDai.withdraw(PYUSD)

---

## Pre-flight Checks

| Check                                   | Value                                                                        |
| --------------------------------------- | ---------------------------------------------------------------------------- |
| ST.balanceOf(test)                      | 89,761,092,607,302,279 (0.0898 ST)                                           |
| sUSDai.balanceOf(test)                  | 0                                                                            |
| USDai.balanceOf(test)                   | 0                                                                            |
| USDC.balanceOf(test)                    | 1,000,000,000 (1000 USDC)                                                    |
| PYUSD.balanceOf(test)                   | 910,000 (0.91 PYUSD)                                                         |
| sUSDai.redemptionSharePrice()           | 1,077,670,916,550,901,664 (~1.078e18)                                        |
| sUSDai.totalAssets()                    | 224,714,701,715,921,653,114,954,548 (~224.7M USDai)                          |
| USDai.balanceOf(sUSDai)                 | 34,392,956,141,860,772,818,841,195 (~34.4M USDai)                            |
| AccessManager canCall(test, ST, redeem) | true (role `0x858ca8ea411ba2c3` granted during deposit test)                 |
| ST.previewRedeem(89761092607302279)     | stAssets=83,492,120,457,309,138 (~0.0835 sUSDai), nav=89,977,029,978,006,625 |

---

## Call 1: ST.redeem (Redeem Senior Tranche shares for sUSDai)

**Contract**: `0x90465aad4e426948A4ea342AC49A1A38200B7017` (Senior Tranche)
**Function**: `redeem(uint256 _shares, address _receiver, address _owner) returns (AssetClaims memory)`

**Inputs**:

| Param     | Value                                        | Type    |
| --------- | -------------------------------------------- | ------- |
| _shares   | 89,761,092,607,302,279                       | uint256 |
| _receiver | `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450` | address |
| _owner    | `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450` | address |

**Tx**: `0xe4c019679758a6f46f785be91512b60367dd43e5f4ae02e2d7c949ec57b2ef30` | Status: SUCCESS
**Gas**: 575,300

**Outputs (AssetClaims)**:

| Name     | Value                                  | Type    |
| -------- | -------------------------------------- | ------- |
| stAssets | 83,492,105,329,617,270 (0.0835 sUSDai) | uint256 |
| jtAssets | 0                                      | uint256 |
| nav      | 89,977,012,684,513,377 (0.0900 NAV)    | uint256 |

**Post-state**:

| Metric                 | Value                                  |
| ---------------------- | -------------------------------------- |
| ST.balanceOf(test)     | 0                                      |
| sUSDai.balanceOf(test) | 83,492,105,329,617,270 (0.0835 sUSDai) |

**Notes**:

- Uses `restricted` modifier (AccessManager role `0x858ca8ea411ba2c3`)
- Kernel transfers sUSDai directly to receiver
- Burns ST shares after kernel processes redemption

---

## Call 2: sUSDai.requestRedeem (FAILED - MIN_REDEMPTION_SHARES)

**Contract**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (sUSDai)
**Function**: `requestRedeem(uint256 shares, address controller, address owner) returns (uint256 redemptionId)`

**Inputs**:

| Param      | Value                                        | Type    |
| ---------- | -------------------------------------------- | ------- |
| shares     | 83,492,105,329,617,270 (0.0835 sUSDai)       | uint256 |
| controller | `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450` | address |
| owner      | `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450` | address |

**Tx**: `0xa7ae9980d07dcde33dc573520235502d87adcf4701795ed9b592884f4ed9d828` | Status: FAILED
**Gas**: 115,302 (reverted)
**Error**: `InvalidAmount()` (selector `0x2c5211c6`)

**Root Cause**: `RedemptionLogic._requestRedeem()` enforces `MIN_REDEMPTION_SHARES = 1e18` (1 sUSDai). Our balance of 0.0835 sUSDai is below this minimum.

**Critical Finding**: The sUSDai redemption queue has a minimum shares requirement of exactly **1e18 (1.0 sUSDai)**. Binary search confirmed:

- 999,999,999,999,999,999 (1e18 - 1): FAILS with InvalidAmount
- 1,000,000,000,000,000,000 (1e18): SUCCEEDS
- This means the deposit must produce at least 1 sUSDai to be withdrawable through the queue

---

## Testnet Override: Fund sUSDai for Queue Testing

Since the original ST deposit was small (limited by maxDeposit), the resulting sUSDai balance was below MIN_REDEMPTION_SHARES. To test the redemption queue flow, the test address was funded with 10 sUSDai via `set_erc20_balance`.

---

## Call 2 (Retry): sUSDai.requestRedeem (SUCCESS)

**Contract**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (sUSDai)
**Function**: `requestRedeem(uint256 shares, address controller, address owner) returns (uint256 redemptionId)`

**Inputs**:

| Param      | Value                                        | Type    |
| ---------- | -------------------------------------------- | ------- |
| shares     | 10,000,000,000,000,000,000 (10 sUSDai)       | uint256 |
| controller | `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450` | address |
| owner      | `0x7Eae5E2f495ffbe0781B99529A7E8F116BD60450` | address |

**Tx**: `0x47888a6dfe0e54531f3586f2edd53268c381cb2da5fed2d57f9f774103307d4e` | Status: SUCCESS
**Gas**: 288,684

**Outputs**:

| Name         | Value | Type    |
| ------------ | ----- | ------- |
| redemptionId | 2155  | uint256 |

**Post-state**:

| Metric                             | Value                                  |
| ---------------------------------- | -------------------------------------- |
| sUSDai.balanceOf(test)             | 0 (burned)                             |
| sUSDai.redemptionIds(test)         | [2155]                                 |
| pendingRedeemRequest(2155, test)   | 10,000,000,000,000,000,000 (10 sUSDai) |
| claimableRedeemRequest(2155, test) | 0                                      |
| Redemption.redemptionTimestamp     | 1,777,960,800 (2026-05-05T06:00:00Z)   |

**Notes**:

- Burns sUSDai immediately upon request
- Enters FIFO redemption queue
- Assigned redemptionTimestamp = next redemption window (weekly cycle from genesis)
- Must wait until block.timestamp > redemptionTimestamp before servicing

---

## Queue State Before Servicing

| Metric                           | Value                                             |
| -------------------------------- | ------------------------------------------------- |
| Queue head                       | 2120                                              |
| Queue tail                       | 2155 (our entry)                                  |
| Total pending shares             | 2,454,152,763,452,459,545,818,625 (~2.45M sUSDai) |
| Queue balance (already serviced) | 4,019,060,999,502,463,879,468,035 (~4.02M USDai)  |
| Entries before ours              | ~35 (IDs 2120-2154)                               |

---

## Admin Action: Time Warp + serviceRedemptions

### Time Warp

The `_processRedemptions` function requires `redemption.redemptionTimestamp < block.timestamp`. Used `increase_time(2397591)` + `mine_block()` to advance to 2026-05-06 (past the 2026-05-05 redemption window).

### serviceRedemptions (Partial - 10 shares)

First call only serviced 10 shares from the head entry, not reaching our entry.

**Tx**: `0x415190cd28499c2fcb0182407ef759abdedd24a168399460d6411be1ec47bb03` | Status: SUCCESS
**From**: `0xe7e53f940f8242fec57cbe88054463d4944b3670` (STRATEGY_ADMIN_ROLE holder, impersonated)

### serviceRedemptions (Full - all pending shares)

Serviced all 2,454,152,763,452,459,545,818,625 pending shares to drain the entire queue including our entry.

**Tx**: `0x28147f61701aa83b14ebbcafcd4a8f8b596341def2b645639fab2a4a4e0bd565` | Status: SUCCESS
**From**: `0xe7e53f940f8242fec57cbe88054463d4944b3670` (STRATEGY_ADMIN_ROLE holder, impersonated)

**sUSDai Access Control**:

| Role                                                     | Holder                                       |
| -------------------------------------------------------- | -------------------------------------------- |
| STRATEGY_ADMIN_ROLE (`keccak256("STRATEGY_ADMIN_ROLE")`) | `0xe7e53f940f8242fec57cbe88054463d4944b3670` |
| DEFAULT_ADMIN_ROLE                                       | `0x5f0bc72fb5952b2f3f2e11404398ed507b25841f` |

**Post-service state for redemption 2155**:

| Metric             | Value                                     |
| ------------------ | ----------------------------------------- |
| pendingShares      | 0                                         |
| redeemableShares   | 10,000,000,000,000,000,000 (10 sUSDai)    |
| withdrawableAmount | 10,813,219,382,782,749,720 (10.813 USDai) |
| maxRedeem(test)    | 10,000,000,000,000,000,000                |
| maxWithdraw(test)  | 10,813,219,382,782,749,720                |

### Calculation

```python
shares = 10_000_000_000_000_000_000  # 10 sUSDai
redemption_share_price = 1_081_321_833_265_802_360  # ~1.0813e18

# withdrawableAmount = (shares * redemptionSharePrice) / 1e18
withdrawable = (shares * redemption_share_price) // 10**18
# = 10,813,218,332,658,023,600 (~10.813 USDai)
# Actual: 10,813,219,382,782,749,720 (minor rounding from per-share processing)
```

---

## Call 3: sUSDai.redeem (Claim serviced redemption for USDai)

**Contract**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (sUSDai)
**Function**: `redeem(uint256 shares, address receiver, address controller) returns (uint256 amount)`

**Inputs**:

| Param      | Value                                        | Type    |
| ---------- | -------------------------------------------- | ------- |
| shares     | 10,000,000,000,000,000,000 (maxRedeem)       | uint256 |
| receiver   | `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450` | address |
| controller | `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450` | address |

**Tx**: `0xfc17d1fb5dcca658314b173fa9aa3675f8fbc0f9beb195191e030c5c43e78d94` | Status: SUCCESS
**Gas**: 130,346

**Outputs**:

| Name   | Value                                     | Type    |
| ------ | ----------------------------------------- | ------- |
| amount | 10,813,219,382,782,749,720 (10.813 USDai) | uint256 |

**Post-state**:

| Metric                     | Value                                     |
| -------------------------- | ----------------------------------------- |
| USDai.balanceOf(test)      | 10,813,219,382,782,749,720 (10.813 USDai) |
| sUSDai.redemptionIds(test) | [] (empty - fully claimed)                |
| maxRedeem(test)            | 0                                         |

**Notes**:

- Claims all redeemable shares from serviced redemptions
- Transfers USDai from sUSDai contract to receiver
- Removes redemption entry from the controller's redemptionIds set
- Use `maxRedeem(controller)` to get total claimable shares across all redemption IDs

---

## Call 4: USDai.withdraw(PYUSD) (Withdraw USDai to PYUSD)

**Contract**: `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF` (USDai)
**Function**: `withdraw(address withdrawToken, uint256 usdaiAmount, uint256 withdrawAmountMinimum, address recipient) returns (uint256)`

**Inputs**:

| Param                 | Value                                                | Type    |
| --------------------- | ---------------------------------------------------- | ------- |
| withdrawToken         | `0x46850aD61C2B7d64d08c9C754F45254596696984` (PYUSD) | address |
| usdaiAmount           | 10,813,219,382,782,749,720 (10.813 USDai)            | uint256 |
| withdrawAmountMinimum | 0                                                    | uint256 |
| recipient             | `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450`         | address |

**Tx**: `0x5bdc2cbc023070380c50feeb5a9a2034131b1a38c6f06fc7931d2b4ab1c986bf` | Status: SUCCESS
**Gas**: 133,042

**Outputs**:

| Name           | Value                     | Type    |
| -------------- | ------------------------- | ------- |
| withdrawAmount | 10,813,219 (10.813 PYUSD) | uint256 |

### Calculation

```python
usdai_amount = 10_813_219_382_782_749_720  # 10.813 USDai (18 decimals)

# _unscale: usdai / scaleFactor  where scaleFactor = 1e12 (6->18 decimal difference)
pyusd_amount = usdai_amount // 10**12
# = 10,813,219 (10.813 PYUSD, 6 decimals)

# No swap needed - PYUSD is the base token, direct unscale
```

**Notes**:

- PYUSD is the base token of USDai, so no Uniswap swap occurs
- Direct descaling: `_unscale(usdaiAmount)` divides by 1e12 to convert 18-decimal USDai to 6-decimal PYUSD
- Burns USDai and transfers PYUSD to recipient

---

## USDC Withdrawal Path (FAILED - No Uniswap Liquidity)

**Tested**: `USDai.withdraw(USDC, 1e18, 0, test)` via static call
**Result**: Reverted (same as deposit path -- the Uniswap V3 USDC/PYUSD pool at 100bps fee tier has zero liquidity on Arbitrum)

This confirms the same issue found during deposit testing. The USDC path through USDai's internal swap adapter is not functional on Arbitrum.

---

## State Changes

| Metric                     | Before                             | After                                                    |
| -------------------------- | ---------------------------------- | -------------------------------------------------------- |
| ST balance                 | 89,761,092,607,302,279 (0.0898 ST) | 0                                                        |
| sUSDai balance             | 0                                  | 0                                                        |
| USDai balance              | 0                                  | 1,000,000,000,000,000,000 (1.0 USDai, from test funding) |
| PYUSD balance              | 910,000 (0.91 PYUSD)               | 11,723,219 (11.72 PYUSD)                                 |
| USDC balance               | 1,000,000,000 (1000 USDC)          | 1,000,000,000 (unchanged)                                |
| sUSDai.redemptionIds(test) | []                                 | []                                                       |

**Note**: The PYUSD gain of 10,813,219 (10.813 PYUSD) corresponds to the funded 10 sUSDai test amount, not the original 0.0835 sUSDai from the ST redeem (which was below MIN_REDEMPTION_SHARES).

---

## Gas Summary

| Step                   | Function                                    | Gas Used      | Status                         |
| ---------------------- | ------------------------------------------- | ------------- | ------------------------------ |
| 1                      | ST.redeem(shares, receiver, owner)          | 575,300       | SUCCESS                        |
| 2a                     | sUSDai.requestRedeem(0.0835 sUSDai)         | 115,302       | FAILED (MIN_REDEMPTION_SHARES) |
| 2b                     | sUSDai.requestRedeem(10 sUSDai)             | 288,684       | SUCCESS                        |
| 3                      | sUSDai.redeem(shares, receiver, controller) | 130,346       | SUCCESS                        |
| 4                      | USDai.withdraw(PYUSD, amount, 0, recipient) | 133,042       | SUCCESS                        |
| **Total (user steps)** |                                             | **1,127,372** |                                |

---

## Critical Findings for Blueprint Design

### 1. MIN_REDEMPTION_SHARES = 1e18

The sUSDai redemption queue enforces a minimum of **exactly 1e18 (1.0 sUSDai)** per requestRedeem call. This is a hard-coded constant in `RedemptionLogic` (internal, not readable via getter). If the sUSDai amount from ST.redeem is less than 1e18, the withdrawal will revert.

**Impact**: For the blueprint, the withdraw action must either:

- Ensure the ST position is large enough to produce >= 1 sUSDai on redeem
- Handle the revert gracefully (e.g., skip requestRedeem if sUSDai balance < 1e18)

### 2. Queue-Based Withdrawal (Not Atomic)

The sUSDai withdrawal is **not atomic**. It requires:

1. **Transaction 1** (user): `ST.redeem` + `sUSDai.requestRedeem`
2. **Wait**: Admin calls `serviceRedemptions` (off-chain process)
3. **Transaction 2** (user): `sUSDai.redeem` + `USDai.withdraw`

This is a fundamentally **two-transaction** flow with an off-chain dependency.

### 3. Redemption Queue is FIFO

The redemption queue processes from head to tail. If there are many pending redemptions ahead, the `serviceRedemptions` may need multiple calls (or a single call with enough shares) to reach our entry. The queue has `MAX_REDEMPTION_QUEUE_SCAN_COUNT = 150` entries per call.

### 4. redemptionTimestamp Gate

Each redemption gets assigned a `redemptionTimestamp` (the next redemption window). The `_processRedemptions` function requires `redemptionTimestamp < block.timestamp` before the entry can be serviced. The redemption windows follow a weekly cycle from genesis.

### 5. USDC Path Not Functional

Same as deposit: the `USDai.withdraw(USDC, ...)` path fails due to zero Uniswap V3 liquidity in the PYUSD/USDC 100bps pool on Arbitrum. The blueprint must use PYUSD as the withdrawal token.

### 6. sUSDai.redeem vs sUSDai.withdraw (Claim)

Two equivalent ways to claim from serviced redemptions:

- `sUSDai.redeem(shares, receiver, controller)` -- input is shares, returns USDai amount
- `sUSDai.withdraw(amount, receiver, controller)` -- input is USDai amount, returns shares consumed

Use `maxRedeem(controller)` for the shares input or `maxWithdraw(controller)` for the amount input. The `redeem` variant is preferred as it naturally uses the full claimable amount.

### 7. Function Signatures

| Step             | Contract       | Function                                    | Selector     |
| ---------------- | -------------- | ------------------------------------------- | ------------ |
| ST redeem        | Senior Tranche | `redeem(uint256,address,address)`           | `0xba087652` |
| Request redeem   | sUSDai         | `requestRedeem(uint256,address,address)`    | `0x7d41c86e` |
| Claim (redeem)   | sUSDai         | `redeem(uint256,address,address)`           | `0xba087652` |
| Claim (withdraw) | sUSDai         | `withdraw(uint256,address,address)`         | `0xb460af94` |
| USDai withdraw   | USDai          | `withdraw(address,uint256,uint256,address)` | `0x16762eed` |

### 8. AccessManager Role for ST

Both `ST.deposit` and `ST.redeem` require role `0x858ca8ea411ba2c3` on AccessManager `0x7cc6fb28ec7b5e7afc3cb3986141797ffc27253c`. The caliber address must be granted this role before any operations.

### 9. Blueprint Withdraw Design

The withdraw blueprint needs to be split into two separate actions:

**Action: withdraw_request** (Transaction 1)

1. `ST.redeem(st_balance, caliber, caliber)` -- get sUSDai
2. `sUSDai.requestRedeem(susdai_balance, caliber, caliber)` -- enter queue

**Action: withdraw_claim** (Transaction 2, after servicing)

1. `sUSDai.redeem(maxRedeem, caliber, caliber)` -- claim USDai
2. `USDai.withdraw(PYUSD, usdai_balance, 0, caliber)` -- convert to PYUSD

---

## Production Flow (Without Testnet Overrides)

In production, the flow is:

1. **Prerequisite**: Caliber address must have AccessManager role `0x858ca8ea411ba2c3`
2. **Prerequisite**: ST balance must produce >= 1 sUSDai on redeem (MIN_REDEMPTION_SHARES)
3. **Tx 1**: `ST.redeem(shares, caliber, caliber)` returns sUSDai
4. **Tx 1**: `sUSDai.requestRedeem(susdai_balance, caliber, caliber)` enters queue
5. **Wait**: External admin calls `serviceRedemptions()` (STRATEGY_ADMIN_ROLE = `0xe7e53f940f8242fec57cbe88054463d4944b3670`)
6. **Wait**: Must be past `redemptionTimestamp` (weekly cycle)
7. **Tx 2**: `sUSDai.redeem(maxRedeem(caliber), caliber, caliber)` claims USDai
8. **Tx 2**: `USDai.withdraw(PYUSD, usdai_amount, min_amount, caliber)` converts to PYUSD
