# Execution Report — Withdraw

**Action**: withdraw (redeem CSCBUSDC shares → USDC)
**Chain**: base (chainId 8453)
**Fork**: local anvil forking Base @ block 49020047 — **same fork, run sequentially after the deposit**
**Executed AS the Safe** `0x9f0f855A7370cc30e24924258214681A782A34aC` (impersonated)
**Model**: MakinaX (Safe module), management-only.

Withdraw = **single call**, no approval (Safe burns its own shares; `msg.sender == onBehalf` so no share allowance is decremented). Redeemed the **full** share balance minted by the deposit test.

---

## Call: redeem (vault)

**Contract**: `0x91C056B6d4311a743614FBc03ac32d4E6A2d3a3c` (CSCBUSDC VaultV2)
**Function**: `redeem(uint256 shares, address receiver, address onBehalf) returns (uint256 assets)`
**Selector**: `0xba087652`

> VaultV2 arg ordering: `(amount, receiver, onBehalf)` where **`receiver`** = USDC recipient and **`onBehalf`** = share **owner** (burned from). Both = Safe.

**Inputs**:

| Param    | Value                                               | Type    |
| -------- | --------------------------------------------------- | ------- |
| shares   | `9796682955588686826394` (full balance, 18 dp)      | uint256 |
| receiver | `0x9f0f855A7370cc30e24924258214681A782A34aC` (Safe) | address |
| onBehalf | `0x9f0f855A7370cc30e24924258214681A782A34aC` (Safe) | address |

**Calldata**:

```
0xba08765200000000000000000000000000000000000000000000021314498b0e9b9bcb9a0000000000000000000000009f0f855a7370cc30e24924258214681a782a34ac0000000000000000000000009f0f855a7370cc30e24924258214681a782a34ac
```

**Tx**: `0x132b8773d6fd6035c919f39e886231e7966a147c228604f63aff949f0ef4de11` | Status: ✅ 0x1 | Gas: 294,256

**Outputs**:

| Name   | Value                             | Type    |
| ------ | --------------------------------- | ------- |
| assets | `10000000393` (10000.000393 USDC) | uint256 |

**Events**: `Withdraw(sender, receiver, onBehalf, assets, shares)` (topic0 `0xfbde797d...`), share `Transfer(Safe → 0x0)` (burn), USDC `Transfer(vault → Safe)`. Because vault idle was 0, `exit` auto-deallocated the full amount from the liquidity adapter `0x812B71c3...` via `deallocateInternal` (no penalty on the standard path).

### State Changes

| Metric                   | Before (post-deposit)  | After                            |
| ------------------------ | ---------------------- | -------------------------------- |
| CSCBUSDC balanceOf(Safe) | 9796682955588686826394 | **0** ✅                         |
| USDC balanceOf(Safe)     | 10000000000            | 20000000393 (+10000.000393 USDC) |

### Calculations / gotchas

- **USDC returned = 10000.000393**, slightly MORE than the 10,000 deposited. `redeem` calls `accrueInterest()` first; a few blocks/seconds of interest accrued on the fork between deposit and redeem, nudging the share price up. `previewRedeem(shares)` read `9999999999` an instant before; the on-chain redeem realized `10000000393` because it accrued at its own (later) block. Net: full round-trip with a tiny positive drift, shares fully burned.
- **No approval needed**: `msg.sender == onBehalf == Safe`, so the `allowance[onBehalf][msg.sender]` branch in `exit` is skipped entirely.
- **Deallocation liquidity**: idle was 0, so the entire redemption was sourced by synchronously deallocating from the single adapter. This succeeded for 10k USDC. For LARGE amounts the auto-deallocation can revert (underlying Morpho-market liquidity), a synchronous liquidity revert — NOT an async queue. Fallback is `forceDeallocate(adapter, data, assets, onBehalf)` (0.3% / 3e15 WAD penalty) to force liquidity into idle, then redeem.
- `maxWithdraw`/`maxRedeem` are `pure` and return 0 on VaultV2 — do NOT use them to size the withdraw.

### redeem vs withdraw — which to use

| Variant                | Signature / selector                                                        | Semantics                                                          | When preferable                                                                                  |
| ---------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| **redeem** (used here) | `redeem(uint256 shares,address receiver,address onBehalf)` / `0xba087652`   | burn an exact **share** amount → variable USDC out                 | Exiting a **full position** — pass `balanceOf(Safe)` and shares land at exactly 0, no dust left. |
| withdraw (alt)         | `withdraw(uint256 assets,address receiver,address onBehalf)` / `0xb460af94` | pull an exact **USDC** amount → variable shares burned (rounds up) | Exact-asset-out — when a precise USDC figure is required and a share remainder is acceptable.    |

**For a full exit, `redeem` is preferable** (guarantees shares → 0). `withdraw` is preferable only when an exact USDC amount out matters; note it rounds shares **up** and could leave a share remainder if you don't request the exact `convertToAssets(balance)`.

---

## Confirmed working calldata (withdraw / full exit)

```
# vault.redeem(fullShares, Safe, Safe)  -> to 0x91C056B6d4311a743614FBc03ac32d4E6A2d3a3c
# (shares value is position-specific; below = the full balance from the deposit test)
0xba08765200000000000000000000000000000000000000000000021314498b0e9b9bcb9a0000000000000000000000009f0f855a7370cc30e24924258214681a782a34ac0000000000000000000000009f0f855a7370cc30e24924258214681a782a34ac
```
