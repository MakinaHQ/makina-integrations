# PRIME / PYUSD Leveraged Morpho Loop — Summary

**Machine:** dusd (mainnet) · **Base token:** PYUSD · **Actions:** deposit / withdraw / account · **Harvest:** out of scope

One-legged Morpho Blue loop: supply **PRIME** collateral, borrow **PYUSD**, re-invest to lever up. Equity reported in PYUSD. Same archetype as the existing `morpho-loop-wsrusd-usdc` position.

## Token stack (all 6 decimals — Morpho oracle scale is a clean 1e36)

```
USDC ──deposit──▶ wYLDS ──deposit──▶ PRIME ──supplyCollateral──▶ Morpho ──borrow──▶ PYUSD
      (WL-gated,           (SYNC ERC4626,
       async redeem)        appreciating ~1.0497)
```

| Token          | Address                                      | Redemption                                     |
| -------------- | -------------------------------------------- | ---------------------------------------------- |
| PRIME (Hastra) | `0x19ebb35279A16207Ec4ba82799CC64715065F7F6` | **SYNCHRONOUS** ERC4626 over wYLDS             |
| wYLDS          | `0x6aD038cA6C04e885630851278ca0a856Ad9a66Cc` | **ASYNC, admin-gated** ERC4626 over USDC (1:1) |
| PYUSD          | `0x6c3ea9036406852006290770BEdFcAbA0e23A0e8` | loan / denomination                            |
| USDC           | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` | intermediate                                   |

Market `0x41c4...a3fa` on Blue `0xBBBB...FFCb` · oracle `0x335e5718bC20028d5e357473a3736C187Ca6b07e` (`price()`≈1.0497e36, scale 1e36) · IRM `0x870aC1...` · LLTV **0.86**.

## Key verified findings

- **PRIME = plain synchronous ERC4626.** `maxRedeem=balanceOf`, `maxDeposit=uint256.max`, plain `_update` (no whitelist/hook), no async functions. Not whitelist-gated. PRIME.deposit and PRIME.redeem are instant.
- **wYLDS redemption is async-only** — `redeem`/`withdraw` are `pure` stubs (disabled). Exit = `requestRedeem(shares)` → `completeRedeem(user)`.
- **`completeRedeem` is `onlyRole(REWARDS_ADMIN_ROLE)` with NO on-chain time cooldown** — it only checks redeemVault USDC balance. The caliber **cannot self-settle**; it depends on the Hastra REWARDS_ADMIN + funded vault. "Cooldown" is operational latency, not a timelock.
- **redeemVault `0xA8C3CF...faCd` has NO code (EOA)**, holds only **~972 USDC** now (large USDC allowance to wYLDS already set). Large redemptions revert `InsufficientVaultBalance` until Hastra funds it.
- **wYLDS deposit/mint is whitelist-gated; caliber NOT whitelisted** (`isWhitelisted(caliber)=false`). Whitelist = `[0xEcDEb94b..., redeemVault]`. Transfers appear open (PRIME holds ~255M wYLDS while unwhitelisted).
- **PYUSD oracle feed exists** (`getFeedRoute(PYUSD)`=`0x8f1dF6D7...`, single hop). PRIME needs no registry feed (priced by Morpho market oracle in accounting). **Go-live gate: PASS.**

## Admin handles (Stage 4 fork setup)

- **WHITELIST_ADMIN_ROLE** (`0x9cc798...63b6`) held by **`0x8d358b8ae881f8ea92c3d07783abca21727c6309`** → impersonate it and call `wYLDS.addToWhitelist(0xD1A1C248...c1BC)`.
- **REWARDS_ADMIN_ROLE** (completeRedeem) held by `0x8d358b8a...` and `0x997e2efbce91d170b00ea402e35a66c887ee1da9` → fund redeemVault with USDC, impersonate, call `wYLDS.completeRedeem(caliber)`.

## Accounting (position model, equity in PYUSD)

```
equity = max(0, collateral * price()/1e36 − debt) + wYLDS.pendingRedemptions(caliber).assets (USDC≈PYUSD)
```

- `collateral` (idx 2), `borrowShares` (idx 1) from `Morpho.position(id, caliber)`.
- `debt = borrowShares * totalBorrowAssets / max(totalBorrowShares,1)` from `Morpho.market(id)` (idx 2/3).
- **Pending term** keeps NAV continuous across the async gap; `pendingRedemptions` is deleted on `completeRedeem`, so it auto-zeros exactly when USDC lands loose — no double-count.

## Flows

- **Deposit / lever up:** PYUSD →(swap_module)→ USDC →(wYLDS.deposit)→ wYLDS →(PRIME.deposit)→ PRIME →(Morpho.supplyCollateral)→ borrow PYUSD → loop. Preferred as a flash-loan `loop_in` (mirrors `blueprints/morpho-loop/deposit-swap.yaml`). **Blocker: caliber must be whitelisted on wYLDS first.**
- **Withdraw / exit — chicken/egg flagged:** repay PYUSD → withdrawCollateral(PRIME) → PRIME.redeem→wYLDS → wYLDS.requestRedeem → _(admin)_ completeRedeem → USDC →(swap)→ PYUSD.
  - **VARIANT A (atomic, preferred):** only viable if a **synchronous DEX route PRIME/wYLDS→PYUSD exists** on swap_module — then a Morpho flash-loan close works. RWA tokens likely have thin/no DEX liquidity — must verify.
  - **VARIANT B (staged async unwind, fallback):** source PYUSD elsewhere to repay, withdraw PRIME, PRIME.redeem→wYLDS, requestRedeem, then cross-cycle admin `completeRedeem`→USDC→swap→PYUSD. Atomic flash-loan close is **impossible** because wYLDS→USDC cannot settle in one tx.

## Open items for Stage 1b / Stage 2

1. **Whitelist enforcement point** — deposit-only vs transfer gating; confirm whitelisting the caliber suffices.
2. **Synchronous DEX route** PRIME/wYLDS→PYUSD (decides exit VARIANT A vs B).
3. **redeemVault funding** on fork before `completeRedeem`.
4. **flash_loan_aggregator** (`0x820D35...`) PYUSD support + FLASHLOAN_MANAGEMENT callback wiring (reuse swap-loop precedent).
5. **PRIME deposit** has no KYC/cap gate (confirm on fork).
