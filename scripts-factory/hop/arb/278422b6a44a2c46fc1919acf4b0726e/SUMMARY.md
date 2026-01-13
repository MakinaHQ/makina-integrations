# Hop Protocol USDC/hUSDC Pool - Arbitrum

## Overview

This is a StableSwap AMM pool operated by Hop Protocol on Arbitrum, facilitating liquidity provision and swaps between USDC and hUSDC (Hop's wrapped USDC token used for cross-chain transfers).

| Property      | Value                            |
| ------------- | -------------------------------- |
| **Pool ID**   | 278422b6a44a2c46fc1919acf4b0726e |
| **Protocol**  | Hop Protocol v1                  |
| **Network**   | Arbitrum                         |
| **Pool Type** | StableSwap AMM (Saddle fork)     |

## Contract Addresses

| Contract     | Address                                      | Purpose                                     |
| ------------ | -------------------------------------------- | ------------------------------------------- |
| **Swap**     | `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261` | Main pool contract for liquidity operations |
| **LP Token** | `0xB67c014FA700E69681a673876eb8BAFAA36BFf71` | HOP-LP-USDC receipt token                   |
| **USDC**     | `0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8` | Bridged USDC.e (index 0)                    |
| **hUSDC**    | `0x0ce6c85cF43553DE10FC56cecA0aef6Ff0DD444d` | Hop wrapped USDC (index 1)                  |

## Token Details

| Token              | Symbol | Decimals | Index | Type             |
| ------------------ | ------ | -------- | ----- | ---------------- |
| USD Coin (Arb1)    | USDC   | 6        | 0     | Canonical        |
| USD Coin Hop Token | hUSDC  | 6        | 1     | Hop Bridge Token |

## Pool Parameters

| Parameter     | Value   | Description                                    |
| ------------- | ------- | ---------------------------------------------- |
| A Parameter   | 200     | Amplification coefficient (tighter = higher A) |
| Swap Fee      | 0.04%   | Fee taken on swaps (4000000 / 1e10)            |
| Admin Fee     | 0%      | Protocol's share of swap fees                  |
| Withdraw Fee  | 0%      | Default fee on withdrawals                     |
| Virtual Price | ~1.0485 | LP token value in underlying (grows with fees) |

## Interaction Flows

### Deposit (Add Liquidity)

**Function:** `addLiquidity(uint256[] amounts, uint256 minToMint, uint256 deadline)`

**Steps:**

1. Approve USDC spending to Swap contract (if depositing USDC)
2. Approve hUSDC spending to Swap contract (if depositing hUSDC)
3. Call `addLiquidity` with:
   - `amounts`: Array of [USDC_amount, hUSDC_amount] - can deposit one or both
   - `minToMint`: Minimum LP tokens to receive (slippage protection)
   - `deadline`: Unix timestamp deadline

**Example:**

```solidity
// Deposit 1000 USDC only
amounts = [1000000000, 0]  // 1000 USDC (6 decimals), 0 hUSDC
minToMint = 990000000000000000000  // ~990 LP tokens minimum
deadline = block.timestamp + 600  // 10 minutes
```

### Withdraw (Remove Liquidity)

Three withdrawal methods are available:

#### 1. Proportional Withdrawal

**Function:** `removeLiquidity(uint256 amount, uint256[] minAmounts, uint256 deadline)`

Returns both tokens proportionally based on pool composition.

#### 2. Single Token Withdrawal

**Function:** `removeLiquidityOneToken(uint256 tokenAmount, uint8 tokenIndex, uint256 minAmount, uint256 deadline)`

Withdraws entirely in one token. May incur price impact for large amounts.

- `tokenIndex = 0`: Receive USDC
- `tokenIndex = 1`: Receive hUSDC

#### 3. Imbalanced Withdrawal

**Function:** `removeLiquidityImbalance(uint256[] amounts, uint256 maxBurnAmount, uint256 deadline)`

Specify exact output amounts; LP burn amount is variable.

### Account (Position Queries)

| Query          | Function                                          | Purpose                            |
| -------------- | ------------------------------------------------- | ---------------------------------- |
| LP Balance     | `LPToken.balanceOf(address)`                      | Check LP token holdings            |
| Position Value | `Swap.calculateRemoveLiquidity(address, uint256)` | Calculate underlying token amounts |
| Virtual Price  | `Swap.getVirtualPrice()`                          | Get LP token's underlying value    |
| Pool Balances  | `Swap.getTokenBalance(uint8)`                     | Check pool reserves                |

## Important Notes

1. **Token Indices**: USDC is always index 0, hUSDC is always index 1
2. **Decimal Handling**: Both tokens use 6 decimals, LP token uses 18 decimals
3. **No Router**: Interact directly with the Swap contract (no separate router)
4. **Withdraw Fees**: Currently 0%, but may apply and decay over 4 weeks after deposit
5. **USDC Type**: This is bridged USDC.e, not native USDC on Arbitrum

## Useful View Functions

```solidity
// Preview deposit
Swap.calculateTokenAmount(account, [usdcAmount, husdcAmount], true) returns (uint256 lpAmount)

// Preview proportional withdrawal
Swap.calculateRemoveLiquidity(account, lpAmount) returns (uint256[] amounts)

// Preview single-token withdrawal
Swap.calculateRemoveLiquidityOneToken(account, lpAmount, tokenIndex) returns (uint256 amount)

// Get pool state
Swap.getVirtualPrice() returns (uint256)
Swap.getTokenBalance(0) returns (uint256)  // USDC balance
Swap.getTokenBalance(1) returns (uint256)  // hUSDC balance
Swap.getA() returns (uint256)  // Amplification parameter
```

## Events to Monitor

| Event                                                                                                                                  | Description                         |
| -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| `AddLiquidity(address indexed provider, uint256[] tokenAmounts, uint256[] fees, uint256 invariant, uint256 lpTokenSupply)`             | Emitted on deposits                 |
| `RemoveLiquidity(address indexed provider, uint256[] tokenAmounts, uint256 lpTokenSupply)`                                             | Emitted on proportional withdrawals |
| `RemoveLiquidityOne(address indexed provider, uint256 lpTokenAmount, uint256 lpTokenSupply, uint256 boughtId, uint256 tokensBought)`   | Emitted on single-token withdrawals |
| `RemoveLiquidityImbalance(address indexed provider, uint256[] tokenAmounts, uint256[] fees, uint256 invariant, uint256 lpTokenSupply)` | Emitted on imbalanced withdrawals   |

## References

- [Hop Protocol Documentation](https://docs.hop.exchange/)
- [Hop Protocol Integration Guide](https://docs.hop.exchange/developer-docs/smart-contracts/integration)
- [Arbiscan - Swap Contract](https://arbiscan.io/address/0x10541b07d8Ad2647Dc6cD67abd4c03575dade261)
- [Arbiscan - LP Token](https://arbiscan.io/address/0xB67c014FA700E69681a673876eb8BAFAA36BFf71)
