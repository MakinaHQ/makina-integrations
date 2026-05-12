# Royco sUSDai Senior Tranche (Arbitrum) - Integration Summary

## Overview

The Royco Senior Tranche sUSDai pool is a yield-bearing tranche vault on Arbitrum that accepts sUSDai (Staked USDai) deposits and issues senior tranche shares. The integration involves a multi-step path through the USDai protocol stack:

**USDC -> USDai (via USDai.deposit with internal Uniswap V3 swap) -> sUSDai (ERC4626) -> Senior Tranche Shares**

## Key Contracts

| Contract       | Address                                      | Role                                        |
| -------------- | -------------------------------------------- | ------------------------------------------- |
| Senior Tranche | `0x90465aad4e426948A4ea342AC49A1A38200B7017` | Final vault (Royco ST, UUPS proxy)          |
| sUSDai         | `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` | ERC4626 staking vault for USDai (proxy)     |
| USDai          | `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF` | Stablecoin wrapping PYUSD (proxy)           |
| Kernel         | `0xFdb17E53eA5d342124b8473188BCB9F05F1949CA` | Royco kernel for accounting (UUPS proxy)    |
| Swap Adapter   | `0x56adba107dA1cB73E423c19EC7685E8312d0Ef04` | Uniswap V3 adapter for USDC<->PYUSD swaps   |
| USDC           | `0xaf88d065e77c8cC2239327C5EDb3A432268e5831` | Base token (6 decimals)                     |
| PYUSD          | `0x46850aD61C2B7d64d08c9C754F45254596696984` | USDai's base token (PayPal USD, 6 decimals) |

## Token Decimals

- USDC: 6 decimals
- PYUSD: 6 decimals
- USDai: 18 decimals
- sUSDai: 18 decimals
- Senior Tranche (ROY-ST-sUSDai): 18 decimals
- TRANCHE_UNIT: 18 decimals (same denomination as sUSDai)

## Deposit Flow (Single Transaction)

```
USDC --(USDai.deposit)--> USDai --(sUSDai.deposit)--> sUSDai --(ST.deposit)--> ST Shares
```

1. Approve USDC to USDai contract
2. USDai.deposit(USDC, amount, minUSDai, receiver) -> get USDai (internally swaps USDC->PYUSD via Uniswap V3)
3. Approve USDai to sUSDai
4. sUSDai.deposit(usdaiAmount, receiver) -> get sUSDai
5. Approve sUSDai to Senior Tranche
6. SeniorTranche.deposit(susdaiAmount, receiver) -> get ST shares

**Key difference from sNUSD**: ST deposit is 2-arg `deposit(uint256,address)`, NOT 3-arg.

## Withdraw Flow (Two Transactions, variable gap)

### Transaction 1: Redeem + Request Redemption

```
ST Shares --(ST.redeem)--> sUSDai --(sUSDai.requestRedeem)--> [IN QUEUE]
```

1. SeniorTranche.redeem(shares, receiver, owner) -> get sUSDai
2. sUSDai.requestRedeem(shares, controller, owner) -> returns redemptionId, enters queue

### Transaction 2: Claim + Withdraw (after admin services queue)

```
[SERVICED] --(sUSDai.redeem)--> USDai --(USDai.withdraw)--> USDC
```

1. sUSDai.redeem(shares, receiver, controller) -> get USDai
2. USDai.withdraw(USDC, usdaiAmount, minUSDC, recipient) -> get USDC

**Key difference from sNUSD**: sUSDai uses a queue-based redemption, NOT a cooldown. There is no fixed 10-day wait. Instead, an admin must call `serviceRedemptions()` to process the queue.

## Accounting

Position value spans five possible states:

| State                | Query                                        | Description                                         |
| -------------------- | -------------------------------------------- | --------------------------------------------------- |
| Active ST shares     | `SeniorTranche.balanceOf(account)`           | Primary position                                    |
| sUSDai held          | `sUSDai.balanceOf(account)`                  | Transient (between redeem and requestRedeem)        |
| In queue (pending)   | `sUSDai.pendingRedeemRequest(id, account)`   | Shares awaiting admin service                       |
| In queue (claimable) | `sUSDai.claimableRedeemRequest(id, account)` | Shares serviced, ready to claim                     |
| USDai held           | `USDai.balanceOf(account)`                   | Transient (between sUSDai claim and USDai withdraw) |

### Value Conversion Chain

```
ST shares -> convertToAssets(shares).stAssets [sUSDai amount]
    -> convertToAssets(shares).nav [USD NAV, directly]
sUSDai amount -> sUSDai.convertToAssets(amount) [USDai amount]
USDai amount -> USDai._unscale(amount) [~USDC amount, 6 decimals, 1:1 approx]
```

For Kernel-based conversion:

```
sUSDai -> Kernel.stConvertTrancheUnitsToNAVUnits(sUSDaiAmount) -> USD NAV (18 decimals)
Rate = sUSDai.redemptionSharePrice() * Kernel.getStoredConversionRateWAD() / 1e18
```

## Critical Differences from sNUSD Integration

| Aspect                | sNUSD (mainnet)                      | sUSDai (Arbitrum)                       |
| --------------------- | ------------------------------------ | --------------------------------------- |
| Entry token swap      | NUSD Router mint (USDC->NUSD)        | USDai.deposit (USDC->PYUSD internally)  |
| ST deposit args       | 3-arg (assets, receiver, controller) | 2-arg (assets, receiver)                |
| Withdrawal mechanism  | Cooldown (10-day fixed)              | Queue-based (variable, admin-serviced)  |
| Withdrawal initiation | sNUSD.cooldownShares()               | sUSDai.requestRedeem()                  |
| Withdrawal claim      | sNUSD.unstake()                      | sUSDai.redeem() / sUSDai.withdraw()     |
| Exit token swap       | NUSD Router redeem (NUSD->USDC)      | USDai.withdraw (PYUSD->USDC internally) |
| Redeem whitelist      | YES (NUSD Router enforces)           | NO (USDai has no redeem whitelist)      |
| Blacklist             | NUSD denylist                        | USDai blacklist (also used by Kernel)   |
| Multiple withdrawals  | Overwrites previous cooldown         | Creates separate queue entries          |
| Base token            | NUSD (18 decimals)                   | USDai wrapping PYUSD (6 decimals base)  |

## On-Chain Parameters (as of 2026-04-08)

- sUSDai depositSharePrice: ~1.078e18 (1 sUSDai = ~1.078 USDai for deposits)
- sUSDai redemptionSharePrice: ~1.078e18 (1 sUSDai = ~1.078 USDai for redemptions)
- sUSDai totalAssets: ~224.7M USDai
- sUSDai totalSupply: ~127.9M sUSDai
- Kernel storedConversionRateWAD: 1e18 (USDai:USD = 1:1)
- Kernel getTrancheUnitToNAVUnitConversionRateWAD: ~1.078e18 (sUSDai:USD)
- ST totalSupply: ~8.60e17 (very small)
- ST maxDeposit: ~1.03e17 (low -- near capacity or utilization limits)
- Kernel blacklist: enabled
- Kernel transfer whitelist: NOT enforced
- SwapAdapter whitelisted tokens: USDC, USDT, wM

## Testing Notes

1. **No redeem whitelist needed**: Unlike sNUSD, USDai.withdraw does not enforce a whitelist. Any non-blacklisted address can withdraw.

2. **Blacklist for testnet**: The USDai blacklist is active. Ensure the test address is NOT blacklisted. Check with `USDai.isBlacklisted(address)`.

3. **Redemption queue servicing**: On testnet, to test the full withdraw flow, the STRATEGY_ADMIN_ROLE on sUSDai must call `serviceRedemptions()` to process the queue. This may require granting the role or impersonating an admin.

4. **Swap slippage**: USDai deposit/withdraw involves a Uniswap V3 swap between USDC and PYUSD. Set appropriate slippage parameters. On testnet with forked state, the pool liquidity should match mainnet.

5. **Low maxDeposit**: The ST currently shows a very low maxDeposit (~0.1 sUSDai). This may limit deposit testing amounts.
