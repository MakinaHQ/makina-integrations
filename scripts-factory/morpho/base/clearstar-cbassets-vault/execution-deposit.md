# Execution Report — Deposit

**Action**: deposit (supply USDC → mint CSCBUSDC shares)
**Chain**: base (chainId 8453)
**Fork**: local anvil `--fork-url https://base.gateway.tenderly.co/...` @ block 49020047
**Executed AS the Safe** `0x9f0f855A7370cc30e24924258214681A782A34aC` (impersonated, `--unlocked --from Safe`)
**Model**: MakinaX (Safe module), management-only. No caliber, no accounting.

Deposit = **2 calls**: (1) approve USDC to the vault, (2) `deposit(assets, onBehalf=Safe)` on the vault.
Test amount: **10,000 USDC** (10000000000, 6 dp).

---

## Call 1: approve (USDC)

**Contract**: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` (USDC)
**Function**: `approve(address spender, uint256 amount)`
**Selector**: `0x095ea7b3`
**Approval requirement**: REQUIRED. ERC-4626 `enter` pulls USDC via `transferFrom(msg.sender, vault, assets)`, so the Safe must approve **the vault itself** (not a router/periphery).

**Inputs**:

| Param   | Value                                                | Type    |
| ------- | ---------------------------------------------------- | ------- |
| spender | `0x91C056B6d4311a743614FBc03ac32d4E6A2d3a3c` (vault) | address |
| amount  | `10000000000` (10,000 USDC)                          | uint256 |

**Calldata**:

```
0x095ea7b300000000000000000000000091c056b6d4311a743614fbc03ac32d4e6a2d3a3c00000000000000000000000000000000000000000000000000000002540be400
```

**Tx**: `0x1a0b365c1bfbe4a351cf4aa72824022bb1a693f5d71f4e697a5aa8f97a06404f` | Status: ✅ 0x1 | Gas: 55,449
**Result**: allowance(Safe → vault) = `10000000000`

---

## Call 2: deposit (vault)

**Contract**: `0x91C056B6d4311a743614FBc03ac32d4E6A2d3a3c` (CSCBUSDC VaultV2)
**Function**: `deposit(uint256 assets, address onBehalf) returns (uint256 shares)`
**Selector**: `0x6e553f65`

> VaultV2 arg ordering: arg #2 is named **`onBehalf`** (the share **recipient**), NOT the ERC-4626 `receiver`. The funder is always `msg.sender` (the Safe). Set `onBehalf = Safe`.

**Inputs**:

| Param    | Value                                               | Type    |
| -------- | --------------------------------------------------- | ------- |
| assets   | `10000000000` (10,000 USDC, 6 dp)                   | uint256 |
| onBehalf | `0x9f0f855A7370cc30e24924258214681A782A34aC` (Safe) | address |

**Calldata**:

```
0x6e553f6500000000000000000000000000000000000000000000000000000002540be4000000000000000000000000009f0f855a7370cc30e24924258214681a782a34ac
```

**Tx**: `0x7aa6e99c253e5df2ff538df42d5566ed41c35243531a78781bb9f5dfc0de9e1c` | Status: ✅ 0x1 | Gas: 320,181

**Outputs**:

| Name   | Value                                               | Type    |
| ------ | --------------------------------------------------- | ------- |
| shares | `9796682955588686826394` (~9796.68 CSCBUSDC, 18 dp) | uint256 |

**Events**: `Deposit(sender, onBehalf, assets, shares)` (topic0 `0x4dec04e7...`), share `Transfer(0x0 → Safe)`, USDC `Transfer(Safe → vault)`, then auto-allocation to the liquidity adapter `0x812B71c3...` (deposited assets are immediately allocated; vault idle stays ~0).

### State Changes

| Metric                   | Before      | After                         |
| ------------------------ | ----------- | ----------------------------- |
| USDC balanceOf(Safe)     | 20000000000 | 10000000000 (−10,000 USDC)    |
| CSCBUSDC balanceOf(Safe) | 0           | 9796682955588686826394        |
| convertToAssets(shares)  | —           | 9999999999 (9999.999999 USDC) |

### Calculations / gotchas

- **Share/asset conversion at current rate**: 1 CSCBUSDC = 1.020753 USDC (`convertToAssets(1e18)=1020753`). So 10,000 USDC → 10000e6 / 1.020753 ≈ 9796.68 shares.
- **previewDeposit(10000 USDC) = 9796683737808073703569**; actual minted `9796682955588686826394` (marginally fewer). Difference is `accrueInterest()` running inside `deposit` and nudging the price up between the static preview and the state-changing call. Rounds **down** on mint (ERC-4626), so re-valuing the minted shares gives `9999999999` = 10,000 USDC − 1 wei (expected round-trip dust loss).
- **Gates**: all unset → `canReceiveShares(Safe)` & `canSendAssets(Safe)` both `true`. Permissionless, no allowlist step.
- `maxDeposit`/`maxMint` are `pure` and return 0 on VaultV2 — do NOT use them to size the deposit.

---

## Confirmed working calldata (deposit)

```
# 1) USDC.approve(vault, 10000000000)  -> to 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
0x095ea7b300000000000000000000000091c056b6d4311a743614fbc03ac32d4e6a2d3a3c00000000000000000000000000000000000000000000000000000002540be400

# 2) vault.deposit(10000000000, Safe)  -> to 0x91C056B6d4311a743614FBc03ac32d4E6A2d3a3c
0x6e553f6500000000000000000000000000000000000000000000000000000002540be4000000000000000000000000009f0f855a7370cc30e24924258214681a782a34ac
```
