# Hop USDC/hUSDC - Function Implementations

Chain: Arbitrum
Generated: 2026-01-07

## Overview

| Function                         | Contract                                   | Type            |
| -------------------------------- | ------------------------------------------ | --------------- |
| addLiquidity                     | 0x10541b07d8Ad2647Dc6cD67abd4c03575dade261 | Entry + Library |
| removeLiquidity                  | 0x10541b07d8Ad2647Dc6cD67abd4c03575dade261 | Entry + Library |
| removeLiquidityOneToken          | 0x10541b07d8Ad2647Dc6cD67abd4c03575dade261 | Entry + Library |
| removeLiquidityImbalance         | 0x10541b07d8Ad2647Dc6cD67abd4c03575dade261 | Entry + Library |
| calculateTokenAmount             | 0x10541b07d8Ad2647Dc6cD67abd4c03575dade261 | View (Library)  |
| calculateRemoveLiquidity         | 0x10541b07d8Ad2647Dc6cD67abd4c03575dade261 | View (Library)  |
| calculateRemoveLiquidityOneToken | 0x10541b07d8Ad2647Dc6cD67abd4c03575dade261 | View (Library)  |
| getVirtualPrice                  | 0x10541b07d8Ad2647Dc6cD67abd4c03575dade261 | View (Library)  |

## Architecture

The Hop Swap contract uses a **library delegation pattern**. All liquidity operations in `Swap.sol` delegate to the `SwapUtils` library which operates on the `swapStorage` struct.

**Key Storage Structure (Swap struct):**

- `pooledTokens` - Array of ERC20 tokens in the pool
- `tokenPrecisionMultipliers` - Multipliers to normalize decimals to 18
- `balances` - Current token balances in the pool
- `lpToken` - LP token contract
- `swapFee` - Fee charged on swaps (in 1e-10 units)
- `adminFee` - Admin's share of swap fees
- `defaultWithdrawFee` - Withdraw fee for new depositors (decays over 4 weeks)
- `initialA`, `futureA` - Amplification parameter (for ramping)

---

## Deposit Functions

### addLiquidity

**Contract:** `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
**Signature:** `addLiquidity(uint256[],uint256,uint256)`
**Selector:** `0x4d49e87d`

```solidity
// Entry point (Swap.sol)
function addLiquidity(
    uint256[] calldata amounts,
    uint256 minToMint,
    uint256 deadline
)
    external
    nonReentrant
    // whenNotPaused
    deadlineCheck(deadline)
    returns (uint256)
{
    return swapStorage.addLiquidity(amounts, minToMint);
}
```

**Delegates to:** `SwapUtils.addLiquidity`

**Key observations:**

- Uses `nonReentrant` modifier (ReentrancyGuardUpgradeable)
- `whenNotPaused` is commented out (pausing disabled)
- `deadlineCheck(deadline)` modifier validates transaction timing
- Core logic is in SwapUtils library

**Modifiers:**

```solidity
modifier deadlineCheck(uint256 deadline) {
    require(block.timestamp <= deadline, "Deadline not met");
    _;
}
```

**Preconditions:**

1. Approve USDC (index 0): `0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8` to spender `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
2. Approve hUSDC (index 1): `0x0ce6c85cF43553DE10FC56cecA0aef6Ff0DD444d` to spender `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`

**Events emitted:**

- `AddLiquidity(address indexed provider, uint256[] tokenAmounts, uint256[] fees, uint256 invariant, uint256 lpTokenSupply)`
- `Transfer` on LP token (mint from zero address)

---

## Withdraw Functions

### removeLiquidity

**Contract:** `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
**Signature:** `removeLiquidity(uint256,uint256[],uint256)`
**Selector:** `0x31cd52b0`

```solidity
// Entry point (Swap.sol)
function removeLiquidity(
    uint256 amount,
    uint256[] calldata minAmounts,
    uint256 deadline
) external nonReentrant deadlineCheck(deadline) returns (uint256[] memory) {
    return swapStorage.removeLiquidity(amount, minAmounts);
}
```

**Delegates to:** `SwapUtils.removeLiquidity`

**Key observations:**

- Proportional withdrawal - returns both tokens in current pool ratio
- No swap fee on proportional withdrawals
- Withdraw fee may apply if deposited recently (decays over 4 weeks)
- Uses `nonReentrant` and `deadlineCheck` modifiers

**Events emitted:**

- `RemoveLiquidity(address indexed provider, uint256[] tokenAmounts, uint256 lpTokenSupply)`

---

### removeLiquidityOneToken

**Contract:** `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
**Signature:** `removeLiquidityOneToken(uint256,uint8,uint256,uint256)`
**Selector:** `0x3e3a1560`

```solidity
// Entry point (Swap.sol)
function removeLiquidityOneToken(
    uint256 tokenAmount,
    uint8 tokenIndex,
    uint256 minAmount,
    uint256 deadline
)
    external
    nonReentrant
    // whenNotPaused
    deadlineCheck(deadline)
    returns (uint256)
{
    return
        swapStorage.removeLiquidityOneToken(
            tokenAmount,
            tokenIndex,
            minAmount
        );
}
```

**Delegates to:** `SwapUtils.removeLiquidityOneToken`

**Key observations:**

- Single-sided withdrawal incurs swap fees (imbalances the pool)
- `tokenIndex`: 0 = USDC, 1 = hUSDC
- Withdraw fee may apply based on deposit timestamp
- Price impact possible for large withdrawals

**Events emitted:**

- `RemoveLiquidityOne(address indexed provider, uint256 lpTokenAmount, uint256 lpTokenSupply, uint256 boughtId, uint256 tokensBought)`

---

### removeLiquidityImbalance

**Contract:** `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
**Signature:** `removeLiquidityImbalance(uint256[],uint256,uint256)`
**Selector:** `0x84cdd9bc`

```solidity
// Entry point (Swap.sol)
function removeLiquidityImbalance(
    uint256[] calldata amounts,
    uint256 maxBurnAmount,
    uint256 deadline
)
    external
    nonReentrant
    // whenNotPaused
    deadlineCheck(deadline)
    returns (uint256)
{
    return swapStorage.removeLiquidityImbalance(amounts, maxBurnAmount);
}
```

**Delegates to:** `SwapUtils.removeLiquidityImbalance`

**Key observations:**

- Specify exact output amounts, LP tokens burned is variable
- `maxBurnAmount` provides slippage protection
- Incurs fees if withdrawal ratio differs from pool ratio

**Events emitted:**

- `RemoveLiquidityImbalance(address indexed provider, uint256[] tokenAmounts, uint256[] fees, uint256 invariant, uint256 lpTokenSupply)`

---

## View Functions

### calculateTokenAmount

**Contract:** `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
**Signature:** `calculateTokenAmount(address,uint256[],bool)`

```solidity
// Entry point (Swap.sol)
function calculateTokenAmount(
    address account,
    uint256[] calldata amounts,
    bool deposit
) external view returns (uint256) {
    return swapStorage.calculateTokenAmount(account, amounts, deposit);
}
```

**Key observations:**

- `account` parameter affects withdraw fee calculation
- `deposit = true` for deposit preview, `false` for withdrawal preview
- Returns LP tokens that would be minted (deposit) or burned (withdraw)
- Account for withdraw fee if `deposit = false` and user deposited recently

---

### calculateRemoveLiquidity

**Contract:** `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
**Signature:** `calculateRemoveLiquidity(address,uint256)`

```solidity
// Entry point (Swap.sol)
function calculateRemoveLiquidity(address account, uint256 amount)
    external
    view
    returns (uint256[] memory)
{
    return swapStorage.calculateRemoveLiquidity(account, amount);
}
```

**Key observations:**

- Returns array `[USDC_amount, hUSDC_amount]` for proportional withdrawal
- `account` affects withdraw fee calculation
- Useful for previewing `removeLiquidity` output

---

### calculateRemoveLiquidityOneToken

**Contract:** `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
**Signature:** `calculateRemoveLiquidityOneToken(address,uint256,uint8)`

```solidity
// Entry point (Swap.sol)
function calculateRemoveLiquidityOneToken(
    address account,
    uint256 tokenAmount,
    uint8 tokenIndex
) external view returns (uint256 availableTokenAmount) {
    (availableTokenAmount, ) = swapStorage.calculateWithdrawOneToken(
        account,
        tokenAmount,
        tokenIndex
    );
}
```

**Delegates to:** `SwapUtils.calculateWithdrawOneToken`

```solidity
// Library implementation (SwapUtils.sol)
function calculateWithdrawOneToken(
    Swap storage self,
    address account,
    uint256 tokenAmount,
    uint8 tokenIndex
) public view returns (uint256, uint256) {
    uint256 dy;
    uint256 newY;

    (dy, newY) = calculateWithdrawOneTokenDY(self, tokenIndex, tokenAmount);

    // dy_0 (without fees)
    // dy, dy_0 - dy

    uint256 dySwapFee =
        _xp(self)[tokenIndex]
            .sub(newY)
            .div(self.tokenPrecisionMultipliers[tokenIndex])
            .sub(dy);

    dy = dy
        .mul(
        FEE_DENOMINATOR.sub(calculateCurrentWithdrawFee(self, account))
    )
        .div(FEE_DENOMINATOR);

    return (dy, dySwapFee);
}
```

**Key observations:**

- Returns net amount after swap fee and withdraw fee
- Internal `calculateWithdrawOneTokenDY` computes raw withdrawal amount
- Withdraw fee is subtracted from `dy` based on user's deposit timestamp

---

### getVirtualPrice

**Contract:** `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
**Signature:** `getVirtualPrice()`

```solidity
// Entry point (Swap.sol)
function getVirtualPrice() external view returns (uint256) {
    return swapStorage.getVirtualPrice();
}
```

**Key observations:**

- Returns LP token price in 18 decimals (1e18 = $1.00)
- Value increases as pool earns swap fees
- Current value: ~1.0485 (pool has earned ~4.85% in fees since inception)
- Formula: `D / totalSupply` where D is the StableSwap invariant

---

### getTokenBalance

**Contract:** `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
**Signature:** `getTokenBalance(uint8)`

```solidity
// Entry point (Swap.sol)
function getTokenBalance(uint8 index) external view returns (uint256) {
    require(index < swapStorage.pooledTokens.length, "Index out of range");
    return swapStorage.balances[index];
}
```

**Key observations:**

- Index 0 = USDC balance, Index 1 = hUSDC balance
- Returns raw balance in token decimals (6 for both)

---

### calculateCurrentWithdrawFee

**Contract:** `0x10541b07d8Ad2647Dc6cD67abd4c03575dade261`
**Signature:** `calculateCurrentWithdrawFee(address)`

```solidity
// Entry point (Swap.sol)
function calculateCurrentWithdrawFee(address user)
    external
    view
    returns (uint256)
{
    return swapStorage.calculateCurrentWithdrawFee(user);
}
```

**Key observations:**

- Returns current withdraw fee for user in basis points
- Fee decays linearly from `defaultWithdrawFee` to 0 over 4 weeks
- Current pool has `defaultWithdrawFee = 0`, so this always returns 0

---

## Internal Library Functions

### getD (StableSwap Invariant)

```solidity
// SwapUtils.sol
function getD(uint256[] memory xp, uint256 a)
    internal
    pure
    returns (uint256)
{
    uint256 numTokens = xp.length;
    uint256 s;
    for (uint256 i = 0; i < numTokens; i++) {
        s = s.add(xp[i]);
    }
    if (s == 0) {
        return 0;
    }

    uint256 prevD;
    uint256 d = s;
    uint256 nA = a.mul(numTokens);

    for (uint256 i = 0; i < MAX_LOOP_LIMIT; i++) {
        uint256 dP = d;
        for (uint256 j = 0; j < numTokens; j++) {
            dP = dP.mul(d).div(xp[j].mul(numTokens));
        }
        prevD = d;
        d = nA.mul(s).div(A_PRECISION).add(dP.mul(numTokens)).mul(d).div(
            nA.sub(A_PRECISION).mul(d).div(A_PRECISION).add(
                numTokens.add(1).mul(dP)
            )
        );
        if (d.within1(prevD)) {
            return d;
        }
    }

    revert("D does not converge");
}
```

**Key observations:**

- Computes the StableSwap invariant D using Newton's method
- `xp` is normalized balances (adjusted for precision)
- `a` is the amplification parameter (A_PRECISION = 100)
- MAX_LOOP_LIMIT prevents infinite loops (typically converges in 4 iterations)

---

### getYD (Calculate Token Amount for Given D)

```solidity
// SwapUtils.sol
function getYD(
    uint256 a,
    uint8 tokenIndex,
    uint256[] memory xp,
    uint256 d
) internal pure returns (uint256) {
    uint256 numTokens = xp.length;
    require(tokenIndex < numTokens, "Token not found");

    uint256 c = d;
    uint256 s;
    uint256 nA = a.mul(numTokens);

    for (uint256 i = 0; i < numTokens; i++) {
        if (i != tokenIndex) {
            s = s.add(xp[i]);
            c = c.mul(d).div(xp[i].mul(numTokens));
        }
    }
    c = c.mul(d).mul(A_PRECISION).div(nA.mul(numTokens));

    uint256 b = s.add(d.mul(A_PRECISION).div(nA));
    uint256 yPrev;
    uint256 y = d;
    for (uint256 i = 0; i < MAX_LOOP_LIMIT; i++) {
        yPrev = y;
        y = y.mul(y).add(c).div(y.mul(2).add(b).sub(d));
        if (y.within1(yPrev)) {
            return y;
        }
    }
    revert("Approximation did not converge");
}
```

**Key observations:**

- Solves for token balance given target D value
- Used in single-token withdrawal calculations
- Newton's method iteration with convergence check

---

### calculateWithdrawOneTokenDY

```solidity
// SwapUtils.sol
function calculateWithdrawOneTokenDY(
    Swap storage self,
    uint8 tokenIndex,
    uint256 tokenAmount
) internal view returns (uint256, uint256) {
    require(
        tokenIndex < self.pooledTokens.length,
        "Token index out of range"
    );

    uint256[] memory xp = _xp(self);
    CalculateWithdrawOneTokenDYInfo memory v =
        CalculateWithdrawOneTokenDYInfo(0, 0, 0, 0, 0);
    v.preciseA = _getAPrecise(self);
    v.d0 = getD(xp, v.preciseA);
    v.d1 = v.d0.sub(tokenAmount.mul(v.d0).div(self.lpToken.totalSupply()));

    require(tokenAmount <= xp[tokenIndex], "Withdraw exceeds available");

    v.newY = getYD(v.preciseA, tokenIndex, xp, v.d1);

    uint256[] memory xpReduced = new uint256[](xp.length);

    v.feePerToken = _feePerToken(self);
    for (uint256 i = 0; i < self.pooledTokens.length; i++) {
        uint256 xpi = xp[i];
        xpReduced[i] = xpi.sub(
            (
                (i == tokenIndex)
                    ? xpi.mul(v.d1).div(v.d0).sub(v.newY)
                    : xpi.sub(xpi.mul(v.d1).div(v.d0))
            )
                .mul(v.feePerToken)
                .div(FEE_DENOMINATOR)
        );
    }

    uint256 dy =
        xpReduced[tokenIndex].sub(
            getYD(v.preciseA, tokenIndex, xpReduced, v.d1)
        );
    dy = dy.sub(1).div(self.tokenPrecisionMultipliers[tokenIndex]);

    return (dy, v.newY);
}
```

**Key observations:**

- Core calculation for single-token withdrawals
- Computes new D after burning LP tokens
- Applies fee to imbalanced withdrawal
- Returns `(dy, newY)` - amount out and new balance

---

### _xp (Normalize Balances)

```solidity
// SwapUtils.sol
function _xp(
    uint256[] memory balances,
    uint256[] memory precisionMultipliers
) internal pure returns (uint256[] memory) {
    uint256 numTokens = balances.length;
    require(
        numTokens == precisionMultipliers.length,
        "Balances must match multipliers"
    );
    uint256[] memory xp = new uint256[](numTokens);
    for (uint256 i = 0; i < numTokens; i++) {
        xp[i] = balances[i].mul(precisionMultipliers[i]);
    }
    return xp;
}
```

**Key observations:**

- Normalizes token balances to 18 decimal precision
- USDC (6 decimals) multiplied by 10^12
- hUSDC (6 decimals) multiplied by 10^12

---

### _feePerToken

```solidity
// SwapUtils.sol
function _feePerToken(Swap storage self) internal view returns (uint256) {
    return
        self.swapFee.mul(self.pooledTokens.length).div(
            self.pooledTokens.length.sub(1).mul(4)
        );
}
```

**Key observations:**

- Calculates effective fee per token for imbalanced operations
- For 2 tokens: `swapFee * 2 / (1 * 4) = swapFee / 2`
- Current swapFee: 4000000 (0.04%), so feePerToken: 2000000 (0.02%)

---

### _getAPrecise

```solidity
// SwapUtils.sol
function _getAPrecise(Swap storage self) internal view returns (uint256) {
    uint256 t1 = self.futureATime; // time when ramp is finished
    uint256 a1 = self.futureA; // final A value when ramp is finished

    if (block.timestamp < t1) {
        uint256 t0 = self.initialATime; // time when ramp is started
        uint256 a0 = self.initialA; // initial A value when ramp is started
        if (a1 > a0) {
            return
                a0.add(
                    a1.sub(a0).mul(block.timestamp.sub(t0)).div(t1.sub(t0))
                );
        } else {
            return
                a0.sub(
                    a0.sub(a1).mul(block.timestamp.sub(t0)).div(t1.sub(t0))
                );
        }
    } else {
        return a1;
    }
}
```

**Key observations:**

- Returns current amplification parameter with ramping support
- A parameter affects curve shape (higher A = tighter peg)
- Current A = 200 (A_PRECISE = 20000 with A_PRECISION = 100)

---

## Constants

```solidity
// SwapUtils.sol
uint256 public constant MAX_LOOP_LIMIT = 256;
uint256 public constant A_PRECISION = 100;
uint256 public constant FEE_DENOMINATOR = 10**10;
uint256 public constant POOL_PRECISION_DECIMALS = 18;
uint256 public constant MAX_A = 10**6;
uint256 public constant MAX_A_CHANGE = 10;
uint256 public constant MIN_RAMP_TIME = 1 days;
uint256 public constant MAX_SWAP_FEE = 10**8;           // 1%
uint256 public constant MAX_ADMIN_FEE = 10**10;         // 100%
uint256 public constant MAX_WITHDRAW_FEE = 10**8;       // 1%
uint256 public constant WITHDRAW_FEE_DECAY_TIME = 4 weeks;
```

---

## Summary for Execution Explorer

**Deposit (addLiquidity):**

1. Approve tokens to Swap contract (not a router)
2. Call `addLiquidity([usdc_amount, husdc_amount], minToMint, deadline)`
3. Can deposit one or both tokens
4. LP tokens minted to caller

**Withdraw Proportional (removeLiquidity):**

1. No approval needed (LP tokens burned internally)
2. Call `removeLiquidity(lpAmount, [minUsdc, minHusdc], deadline)`
3. Returns both tokens in pool ratio

**Withdraw Single Token (removeLiquidityOneToken):**

1. No approval needed
2. Call `removeLiquidityOneToken(lpAmount, tokenIndex, minAmount, deadline)`
3. `tokenIndex`: 0 = USDC, 1 = hUSDC
4. Incurs swap fee due to imbalance

**Preview Functions:**

- `calculateTokenAmount(account, amounts, true)` - preview deposit
- `calculateRemoveLiquidity(account, lpAmount)` - preview proportional withdraw
- `calculateRemoveLiquidityOneToken(account, lpAmount, tokenIndex)` - preview single token withdraw
- `getVirtualPrice()` - LP token value (for accounting)
