# Execution Report: Withdraw (Balanced)

**Action**: withdraw (removeLiquidity - proportional)
**Chain**: Arbitrum
**Testnet ID**: 688cef17-7366-4d83-84bb-0ac25a905d34
**Date**: 2026-01-07

## Summary

Successfully executed a balanced withdrawal from the Hop USDC/hUSDC pool using the `removeLiquidity` function. The withdrawal returns both USDC and hUSDC tokens proportionally based on the current pool ratio.

**Key Discovery**: The Hop LP token requires explicit approval to the Swap contract before `removeLiquidity` can be called. This is because the contract uses `lpToken.burnFrom()` which checks allowance.

---

## Test Setup

### Testnet Configuration

- **Admin RPC**: `https://virtual.arbitrum.eu.rpc.tenderly.co/53f1d609-e867-400d-878d-82c6d66ae963`
- **Test Address**: `0x1234567890123456789012345678901234567890`

### Initial Funding

| Asset | Amount | Purpose           |
| ----- | ------ | ----------------- |
| ETH   | 10.0   | Gas               |
| USDC  | 10,000 | Deposit to get LP |
| hUSDC | 10,000 | Deposit to get LP |

### Pre-withdraw Deposit

To get LP tokens for testing, we first deposited:

- **TX**: `4fd3f65ecde7f000aa0f19f8de1b7ca7bcb0f05ec2603c1a29348f0ee32b6c42`
- **USDC deposited**: 5,000.00
- **hUSDC deposited**: 5,000.00
- **LP received**: 9,538.479231 LP
- **Gas used**: 270,172

---

## Withdraw Execution

### Precondition: LP Token Approval

**IMPORTANT**: Unlike many LP tokens, the Hop LP token requires approval before withdrawal.

**Contract**: `0xB67c014FA700E69681a673876eb8BAFAA36BFf71` (HOP-LP-USDC)
**Function**: `approve(address spender, uint256 amount)`

| Param   | Value                                      | Type    |
| ------- | ------------------------------------------ | ------- |
| spender | 0x10541b07d8Ad2647Dc6cD67abd4c03575dade261 | address |
| amount  | 9538479231072155770262                     | uint256 |

**TX**: `e8bf8e322b768fb8157c54d23f5a64a203f6ac522ad41578e840bd6e7d52cb31`
**Status**: SUCCESS
**Gas Used**: 46,194

---

### Call 1: calculateRemoveLiquidity (Preview)

**Contract**: `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
**Function**: `calculateRemoveLiquidity(address account, uint256 amount)`

| Param   | Value                                      | Type    |
| ------- | ------------------------------------------ | ------- |
| account | 0x1234567890123456789012345678901234567890 | address |
| amount  | 9538479231072155770262                     | uint256 |

**Outputs**:

| Name       | Value      | Formatted          |
| ---------- | ---------- | ------------------ |
| amounts[0] | 3873660088 | 3,873.660088 USDC  |
| amounts[1] | 6128784468 | 6,128.784468 hUSDC |

---

### Call 2: removeLiquidity (Execute)

**Contract**: `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
**Function**: `removeLiquidity(uint256 amount, uint256[] minAmounts, uint256 deadline)`
**Selector**: `0x31cd52b0`

**Inputs**:

| Param         | Value                  | Type    | Formatted                        |
| ------------- | ---------------------- | ------- | -------------------------------- |
| amount        | 9538479231072155770262 | uint256 | 9,538.479231 LP                  |
| minAmounts[0] | 3834923487             | uint256 | 3,834.923487 USDC (1% slippage)  |
| minAmounts[1] | 6067496623             | uint256 | 6,067.496623 hUSDC (1% slippage) |
| deadline      | 1767790143             | uint256 | Unix timestamp                   |

**TX**: `695bd6efbf32c80838cd7d834c06ef1f0d3e73ac217e226bc61d462b8a9babdb`
**Status**: SUCCESS
**Block**: 418838975
**Gas Used**: 131,345

**Outputs**:

| Name       | Value      | Type    | Formatted          |
| ---------- | ---------- | ------- | ------------------ |
| amounts[0] | 3873660088 | uint256 | 3,873.660088 USDC  |
| amounts[1] | 6128784468 | uint256 | 6,128.784468 hUSDC |

---

## Events Emitted

### Event 1: Transfer (USDC)

```
Transfer(
    from: 0x10541b07d8Ad2647Dc6cD67abd4c03575dade261,  // Swap contract
    to: 0x1234567890123456789012345678901234567890,    // User
    value: 3873660088                                   // 3,873.660088 USDC
)
```

### Event 2: Transfer (hUSDC)

```
Transfer(
    from: 0x10541b07d8Ad2647Dc6cD67abd4c03575dade261,  // Swap contract
    to: 0x1234567890123456789012345678901234567890,    // User
    value: 6128784468                                   // 6,128.784468 hUSDC
)
```

### Event 3: Approval (LP Token)

```
Approval(
    owner: 0x1234567890123456789012345678901234567890,
    spender: 0x10541b07d8Ad2647Dc6cD67abd4c03575dade261,
    value: 0                                            // Reduced to 0
)
```

### Event 4: Transfer (LP Token Burn)

```
Transfer(
    from: 0x1234567890123456789012345678901234567890,  // User
    to: 0x0000000000000000000000000000000000000000,    // Zero address (burn)
    value: 9538479231072155770262                       // 9,538.479231 LP burned
)
```

### Event 5: RemoveLiquidity

```
RemoveLiquidity(
    provider: 0x1234567890123456789012345678901234567890,
    tokenAmounts: [3873660088, 6128784468],
    lpTokenSupply: <new total supply>
)
```

---

## State Changes

### User Balances

| Asset    | Before       | After     | Change        |
| -------- | ------------ | --------- | ------------- |
| LP Token | 9,538.479231 | 0.000000  | -9,538.479231 |
| USDC     | 5,000.00     | 8,873.66  | +3,873.66     |
| hUSDC    | 5,000.00     | 11,128.78 | +6,128.78     |

### Pool State

| Metric        | Before     | After      | Change        |
| ------------- | ---------- | ---------- | ------------- |
| USDC Balance  | 77,349.95  | 73,476.29  | -3,873.66     |
| hUSDC Balance | 122,380.69 | 116,251.90 | -6,128.78     |
| Virtual Price | 1.048502   | 1.048502   | 0 (unchanged) |

---

## Calculation Verification

The withdrawal is **proportional** - tokens received match the pool ratio:

```python
# Pool ratio at withdrawal time
pool_usdc = 77349.95
pool_husdc = 122380.69
total_pool = pool_usdc + pool_husdc  # 199,730.64

usdc_ratio = pool_usdc / total_pool  # 0.3873 (38.73%)
husdc_ratio = pool_husdc / total_pool  # 0.6127 (61.27%)

# LP value calculation
lp_withdrawn = 9538.479231
virtual_price = 1.048502
lp_value_usd = lp_withdrawn * virtual_price  # ~10,001.67 USD

# Expected amounts
expected_usdc = lp_value_usd * usdc_ratio  # ~3,873.66 USDC
expected_husdc = lp_value_usd * husdc_ratio  # ~6,128.78 hUSDC

# Actual matches expected within rounding
```

**Note**: No swap fee is charged on proportional withdrawals. The withdraw fee is also 0 (defaultWithdrawFee = 0 for this pool).

---

## Flow Summary for Blueprint

```
1. APPROVE LP Token to Swap Contract
   - Contract: LP_TOKEN (0xB67c014FA700E69681a673876eb8BAFAA36BFf71)
   - Function: approve(SWAP_CONTRACT, lp_amount)

2. CALCULATE expected outputs (optional, for slippage)
   - Contract: SWAP (0x10541b07d8Ad2647Dc6cD67abd4c03575dade261)
   - Function: calculateRemoveLiquidity(user, lp_amount)
   - Returns: [usdc_amount, husdc_amount]

3. EXECUTE withdrawal
   - Contract: SWAP (0x10541b07d8Ad2647Dc6cD67abd4c03575dade261)
   - Function: removeLiquidity(lp_amount, [min_usdc, min_husdc], deadline)
   - Returns: [actual_usdc, actual_husdc]
```

---

## Issues Encountered

### Issue 1: LP Token Approval Required

**Problem**: Initial withdrawal attempt failed with "ERC20: burn amount exceeds allowance"

**Cause**: The Hop LP token uses `burnFrom()` instead of direct `burn()`, which requires the user to approve the Swap contract to spend their LP tokens.

**Solution**: Add approval step before calling `removeLiquidity`:

```solidity
lpToken.approve(swapContract, lpAmount);
swapContract.removeLiquidity(lpAmount, minAmounts, deadline);
```

**TX (Failed)**: `c535f1cedb2efe272409eff98602c61cbcff99b975680c1f1ad7af14773695f4`
**TX (Success after approval)**: `695bd6efbf32c80838cd7d834c06ef1f0d3e73ac217e226bc61d462b8a9babdb`

---

## Gas Analysis

| Operation       | Gas Used    |
| --------------- | ----------- |
| Approve LP      | 46,194      |
| removeLiquidity | 131,345     |
| **Total**       | **177,539** |

---

## Verification Checklist

- [x] LP tokens burned correctly
- [x] USDC received matches calculation
- [x] hUSDC received matches calculation
- [x] Pool balances updated correctly
- [x] Virtual price unchanged (no fee impact on proportional withdrawal)
- [x] All expected events emitted
- [x] Return value matches actual token transfers
