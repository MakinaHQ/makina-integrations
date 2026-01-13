# Execution Report: Deposit (addLiquidity)

**Action**: deposit (balanced)
**Chain**: Arbitrum
**Testnet ID**: `21952dce-5be7-4f4b-bf1f-ff732271fbbb`
**RPC**: `https://virtual.arbitrum.eu.rpc.tenderly.co/47366be2-e1a3-44e6-9708-63e0420ffb8d`
**Date**: 2026-01-07

---

## Overview

Successfully executed a balanced deposit of USDC and hUSDC into the Hop USDC/hUSDC AMM pool on Arbitrum. The deposit required:

1. Approval of USDC to Swap contract
2. Approval of hUSDC to Swap contract
3. Call to `addLiquidity` with both token amounts

---

## Contracts

| Contract | Address                                      |
| -------- | -------------------------------------------- |
| Swap     | `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261` |
| LP Token | `0xB67c014FA700E69681a673876eb8BAFAA36BFf71` |
| USDC     | `0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8` |
| hUSDC    | `0x0ce6c85cF43553DE10FC56cecA0aef6Ff0DD444d` |

**Test Address**: `0x1234567890123456789012345678901234567890`

---

## Call 1: USDC Approval

**Contract**: `0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8` (USDC)
**Function**: `approve(address spender, uint256 amount)`

**Inputs**:

| Param   | Value                                        | Type    |
| ------- | -------------------------------------------- | ------- |
| spender | `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261` | address |
| amount  | `1000000000`                                 | uint256 |

**Tx**: `0x71ec5b9ad702768dbc176e076ecdc1baf972a448409a0cf8cc2ccd36ef04e6ca`
**Status**: SUCCESS
**Gas Used**: 60,035
**Block**: 418838945

**Events**:

- `Approval(owner=0x1234...7890, spender=0x10541b07d8Ad2647Dc6cD67abd4c03575dade261, value=1000000000)`

---

## Call 2: hUSDC Approval

**Contract**: `0x0ce6c85cF43553DE10FC56cecA0aef6Ff0DD444d` (hUSDC)
**Function**: `approve(address spender, uint256 amount)`

**Inputs**:

| Param   | Value                                        | Type    |
| ------- | -------------------------------------------- | ------- |
| spender | `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261` | address |
| amount  | `1000000000`                                 | uint256 |

**Tx**: `0x284d2db46d2b781d5cec3a44f3557bc51c1d86a32471367fad85661841503b36`
**Status**: SUCCESS
**Gas Used**: 46,110
**Block**: 418838946

**Events**:

- `Approval(owner=0x1234...7890, spender=0x10541b07d8Ad2647Dc6cD67abd4c03575dade261, value=1000000000)`

---

## Call 3: addLiquidity

**Contract**: `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261` (Hop Swap)
**Function**: `addLiquidity(uint256[] amounts, uint256 minToMint, uint256 deadline)`
**Selector**: `0x4d49e87d`

**Inputs**:

| Param     | Value                      | Type      | Description               |
| --------- | -------------------------- | --------- | ------------------------- |
| amounts   | `[1000000000, 1000000000]` | uint256[] | [1000 USDC, 1000 hUSDC]   |
| minToMint | `1888722937356060983296`   | uint256   | ~1888.72 LP (1% slippage) |
| deadline  | `1767790097`               | uint256   | Unix timestamp            |

**Tx**: `0xa8ff051236687c8cc1ec13b5350c5f9b09c502b686172c61a45bf507b1503ea5`
**Status**: SUCCESS
**Gas Used**: 270,136
**Block**: 418838947

**Return Value**:

| Name     | Value                    | Type    | Description              |
| -------- | ------------------------ | ------- | ------------------------ |
| lpAmount | `1907710360002743195989` | uint256 | 1907.71 LP tokens minted |

**Events** (6 total):

1. `Transfer` (USDC): from=0x1234...7890 to=0x10541b07d8Ad2647Dc6cD67abd4c03575dade261, value=1000000000
2. `Approval` (USDC): reset allowance after transfer
3. `Transfer` (hUSDC): from=0x1234...7890 to=0x10541b07d8Ad2647Dc6cD67abd4c03575dade261, value=1000000000
4. `Approval` (hUSDC): reset allowance after transfer
5. `Transfer` (LP Token): from=0x0 to=0x1234...7890, value=1907710360002743195989 (mint)
6. `AddLiquidity` (Swap): provider=0x1234...7890, tokenAmounts=[1000000000, 1000000000]

---

## Calculations

### LP Token Preview vs Actual

```python
# Preview calculation
expected_lp = calculateTokenAmount(account, [1000000000, 1000000000], True)
# Result: 1907800946824304215091 (1907.80 LP)

# Actual received
actual_lp = 1907710360002743195989  # 1907.71 LP

# Difference: -0.09 LP (-0.0047%)
# Minor difference due to block timing / state changes
```

### Value Analysis

```python
# Inputs
usdc_amount = 1000.0  # $1000
husdc_amount = 1000.0  # $1000
total_value_in = 2000.0  # USD

# LP Token value
lp_received = 1907.710360002743
virtual_price = 1.0484998210929037  # LP value in 18 decimals
lp_value_usd = lp_received * virtual_price / 10**12  # Adjust decimals
# Result: ~$2000.23 (slight gain due to virtual price > 1)
```

---

## State Changes

### User Balances

| Token       | Before   | After    | Change    |
| ----------- | -------- | -------- | --------- |
| USDC        | 10,000.0 | 9,000.0  | -1,000.0  |
| hUSDC       | 10,000.0 | 9,000.0  | -1,000.0  |
| HOP-LP-USDC | 0.0      | 1,907.71 | +1,907.71 |

### Pool Balances

| Token | Before     | After      | Change   |
| ----- | ---------- | ---------- | -------- |
| USDC  | 72,349.95  | 73,349.95  | +1,000.0 |
| hUSDC | 117,380.69 | 118,380.69 | +1,000.0 |

### Pool Metrics

| Metric        | Before       | After        |
| ------------- | ------------ | ------------ |
| Virtual Price | 1.0484993016 | 1.0484998211 |

---

## Gas Summary

| Operation      | Gas Used    |
| -------------- | ----------- |
| USDC Approval  | 60,035      |
| hUSDC Approval | 46,110      |
| addLiquidity   | 270,136     |
| **Total**      | **376,281** |

---

## Key Observations

1. **Direct Contract Interaction**: Hop does not use a router - interact directly with the Swap contract
2. **Balanced Deposit**: Providing both tokens results in minimal slippage/fees
3. **Virtual Price**: Pool has accrued ~4.85% in fees since inception (vPrice = 1.0485)
4. **Token Precision**: Both USDC and hUSDC use 6 decimals, LP token uses 18 decimals
5. **Approval Pattern**: The contract resets allowance after `transferFrom` (shown in Approval events)

---

## Reproducibility

```python
from web3 import Web3
import time

# Connect
web3 = Web3(Web3.HTTPProvider(RPC_URL))
web3.provider.make_request("tenderly_impersonateAccount", [TEST_ADDRESS])

# Contracts
SWAP = "0x10541b07d8Ad2647Dc6cD67abd4c03575dade261"
USDC = "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"
HUSDC = "0x0ce6c85cF43553DE10FC56cecA0aef6Ff0DD444d"

# Approve both tokens
usdc.functions.approve(SWAP, amount).transact({'from': TEST_ADDRESS})
husdc.functions.approve(SWAP, amount).transact({'from': TEST_ADDRESS})

# Deposit
deadline = int(time.time()) + 3600
swap.functions.addLiquidity(
    [usdc_amount, husdc_amount],  # amounts array
    min_lp_out,                   # slippage protection
    deadline                       # transaction deadline
).transact({'from': TEST_ADDRESS})
```
