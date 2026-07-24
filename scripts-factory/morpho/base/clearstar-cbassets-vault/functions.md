# Clearstar cbAssets Vault (CSCBUSDC) — Function Implementations

Chain: base (chainId 8453)
Vault / share token: `0x91C056B6d4311a743614FBc03ac32d4E6A2d3a3c` (Morpho **VaultV2**, ERC-4626, self-contained — the vault IS the share token)
Underlying: USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` (6 dp)
Liquidity adapter (single): `0x812B71c33Ae5EAfEbAe967C5670e37eca3cab0ac`
Generated: 2026-07-23

Source: Basescan verified source, bundle `lib/vault-v2/src/VaultV2.sol` (Morpho Association, Solidity 0.8.28). Not a proxy — the address holds the verified `VaultV2` implementation directly. All signatures/selectors below were confirmed against the **deployed ABI** (`get_contract_abi`) and live state was read over the Base RPC.

## Overview

| Function                                         | Selector     | State mutability | Type                                   |
| ------------------------------------------------ | ------------ | ---------------- | -------------------------------------- |
| `deposit(uint256,address)`                       | `0x6e553f65` | nonpayable       | Entry (deposit) → `enter`              |
| `mint(uint256,address)`                          | `0x94bf804d` | nonpayable       | Entry (deposit, alt) → `enter`         |
| `withdraw(uint256,address,address)`              | `0xb460af94` | nonpayable       | Entry (withdraw, exact-asset) → `exit` |
| `redeem(uint256,address,address)`                | `0xba087652` | nonpayable       | Entry (withdraw, by-share) → `exit`    |
| `forceDeallocate(address,bytes,uint256,address)` | `0xe4d38cd8` | nonpayable       | Liquidity fallback (penalty)           |
| `canReceiveShares(address)`                      | `0x98c9b49c` | view             | Gate check (deposit recipient)         |
| `canSendAssets(address)`                         | `0x20fe8d58` | view             | Gate check (deposit funder)            |
| `canSendShares(address)`                         | `0x8e511e4d` | view             | Gate check (withdraw owner)            |
| `canReceiveAssets(address)`                      | `0x0d326b18` | view             | Gate check (withdraw recipient)        |
| `previewDeposit(uint256)`                        | `0xef8b30f7` | view             | assets→shares                          |
| `previewRedeem(uint256)`                         | `0x4cdad506` | view             | shares→assets                          |
| `previewWithdraw(uint256)`                       | `0x0a28a477` | view             | assets→shares                          |
| `convertToAssets(uint256)`                       | `0x07a2d13a` | view             | shares→assets (off-chain valuation)    |

**Divergence from morpho-org `main`:** none observed. The deployed `deposit`/`mint` take the share recipient as arg #2 named `onBehalf` (NOT the ERC-4626-standard `receiver`), and `withdraw`/`redeem` take `(amount, receiver, onBehalf)` where `onBehalf` is the share **owner**. This is the VaultV2 convention and matches the deployed ABI exactly. `maxDeposit/maxMint/maxWithdraw/maxRedeem` are `pure` and return `0` on the deployed contract (confirmed in ABI) — a known VaultV2 trait, not a cap/gate signal.

---

## Deposit Functions

### deposit

**Signature (deployed ABI):** `deposit(uint256 assets, address onBehalf) returns (uint256 shares)`
**Selector:** `0x6e553f65`

```solidity
/// @dev Returns minted shares.
function deposit(uint256 assets, address onBehalf) external returns (uint256) {
    accrueInterest();
    uint256 shares = previewDeposit(assets);
    enter(assets, shares, onBehalf);
    return shares;
}
```

**Why it matters:** Primary deposit entry. `assets` is in USDC (6 dp); `onBehalf` is the **share recipient** (the Safe), NOT the funder. The funder is always `msg.sender` (the Safe, acting via MakinaXModule). Returns freshly minted shares (18 dp). Approval must be granted on **USDC to the vault** because `enter` pulls via `transferFrom(msg.sender, vault, assets)`.

### mint (alt deposit entry)

**Signature (deployed ABI):** `mint(uint256 shares, address onBehalf) returns (uint256 assets)`
**Selector:** `0x94bf804d`

```solidity
/// @dev Returns deposited assets.
function mint(uint256 shares, address onBehalf) external returns (uint256) {
    accrueInterest();
    uint256 assets = previewMint(shares);
    enter(assets, shares, onBehalf);
    return assets;
}
```

**Why it matters:** Share-first alternative to `deposit` if an exact share amount is desired. Same `onBehalf` = recipient semantics, same USDC-to-vault approval requirement (pulled inside `enter`).

### enter (internal — shared deposit path)

```solidity
/// @dev Internal function for deposit and mint.
function enter(uint256 assets, uint256 shares, address onBehalf) internal {
    require(canReceiveShares(onBehalf), ErrorsLib.CannotReceiveShares());
    require(canSendAssets(msg.sender), ErrorsLib.CannotSendAssets());

    SafeERC20Lib.safeTransferFrom(asset, msg.sender, address(this), assets);
    createShares(onBehalf, shares);
    _totalAssets += assets.toUint128();
    emit EventsLib.Deposit(msg.sender, onBehalf, assets, shares);

    if (liquidityAdapter != address(0)) allocateInternal(liquidityAdapter, liquidityData, assets);
}
```

**Why it matters:** This is where a deposit can actually revert for a non-curator caller:

- `canReceiveShares(onBehalf)` — the Safe as recipient must pass the receive-shares gate. **Live: gate unset → true.**
- `canSendAssets(msg.sender)` — the Safe as funder must pass the send-assets gate. **Live: gate unset → true.**
- `safeTransferFrom(asset, msg.sender, ...)` — needs USDC allowance to the vault (revert `TransferFromReverted`/`ReturnedFalse` otherwise).
- After minting, deposited assets are **immediately allocated to the liquidity adapter** (`liquidityAdapter != 0`), so idle stays ~0. This is a curator-configured auto-allocation; it can revert if the allocation would exceed the adapter's absolute/relative caps (`AbsoluteCapExceeded`/`RelativeCapExceeded`), which is a supply-side constraint on the deposit path.

---

## Withdraw Functions

### redeem (by-share entry)

**Signature (deployed ABI):** `redeem(uint256 shares, address receiver, address onBehalf) returns (uint256 assets)`
**Selector:** `0xba087652`

```solidity
/// @dev Returns withdrawn assets.
function redeem(uint256 shares, address receiver, address onBehalf) external returns (uint256) {
    accrueInterest();
    uint256 assets = previewRedeem(shares);
    exit(assets, shares, receiver, onBehalf);
    return assets;
}
```

**Why it matters:** Primary withdraw entry. `shares` (18 dp) burned from `onBehalf` (the Safe = owner), USDC (6 dp) sent to `receiver` (the Safe). No approval needed when `msg.sender == onBehalf` (Safe burns its own shares). Returns assets paid out.

### withdraw (exact-asset alt entry)

**Signature (deployed ABI):** `withdraw(uint256 assets, address receiver, address onBehalf) returns (uint256 shares)`
**Selector:** `0xb460af94`

```solidity
/// @dev Returns redeemed shares.
function withdraw(uint256 assets, address receiver, address onBehalf) public returns (uint256) {
    accrueInterest();
    uint256 shares = previewWithdraw(assets);
    exit(assets, shares, receiver, onBehalf);
    return shares;
}
```

**Why it matters:** Use when an exact USDC amount out is required. Note it is `public` (called internally by `forceDeallocate`). Returns shares burned.

### exit (internal — shared withdraw path + deallocation)

```solidity
/// @dev Internal function for withdraw and redeem.
function exit(uint256 assets, uint256 shares, address receiver, address onBehalf) internal {
    require(canSendShares(onBehalf), ErrorsLib.CannotSendShares());
    require(canReceiveAssets(receiver), ErrorsLib.CannotReceiveAssets());

    uint256 idleAssets = IERC20(asset).balanceOf(address(this));
    if (assets > idleAssets && liquidityAdapter != address(0)) {
        deallocateInternal(liquidityAdapter, liquidityData, assets - idleAssets);
    }

    if (msg.sender != onBehalf) {
        uint256 _allowance = allowance[onBehalf][msg.sender];
        if (_allowance != type(uint256).max) allowance[onBehalf][msg.sender] = _allowance - shares;
    }

    deleteShares(onBehalf, shares);
    _totalAssets -= assets.toUint128();
    SafeERC20Lib.safeTransfer(asset, receiver, assets);
    emit EventsLib.Withdraw(msg.sender, receiver, onBehalf, assets, shares);
}
```

**Why it matters — this is the withdraw deallocation path.** In order:

1. `canSendShares(onBehalf)` — Safe (owner) must pass the send-shares gate. **Live: gate unset → true.**
2. `canReceiveAssets(receiver)` — Safe (recipient) must pass the receive-assets gate; note `receiver == address(this)` is always allowed (used by `forceDeallocate`). **Live: gate unset → true.**
3. **Liquidity sourcing:** consumes idle USDC first; if `assets > idle`, it **automatically deallocates the shortfall from the single `liquidityAdapter`** via `deallocateInternal`. Live idle is `0`, so essentially the full amount is pulled from the adapter on every withdraw.
4. Allowance is only decremented when `msg.sender != onBehalf` — not our case (Safe burns its own shares), so no share allowance is required.

A withdraw **reverts if the adapter cannot return `assets - idle`** (underlying Morpho-market liquidity constraint inside `IAdapter.deallocate`) — a synchronous liquidity revert, not an async queue.

### deallocateInternal (the adapter pull invoked by exit)

```solidity
function deallocateInternal(address adapter, bytes memory data, uint256 assets)
    internal
    returns (bytes32[] memory)
{
    require(isAdapter[adapter], ErrorsLib.NotAdapter());

    (bytes32[] memory ids, int256 change) = IAdapter(adapter).deallocate(data, assets, msg.sig, msg.sender);

    for (uint256 i; i < ids.length; i++) {
        Caps storage _caps = caps[ids[i]];
        require(_caps.allocation > 0, ErrorsLib.ZeroAllocation());
        _caps.allocation = (int256(_caps.allocation) + change).toUint256();
    }

    SafeERC20Lib.safeTransferFrom(asset, adapter, address(this), assets);
    emit EventsLib.Deallocate(msg.sender, adapter, assets, ids, change);
    return ids;
}
```

**Why it matters:** Called by `exit` with `adapter = liquidityAdapter` (`0x812B...b0ac`, `isAdapter == true`, live-confirmed). It asks the adapter to unwind `assets - idle` from the underlying Morpho market and `transferFrom`s that USDC back into the vault. When invoked through the standard withdraw/redeem path there is **no penalty** — the penalty only exists on the explicit `forceDeallocate` entry below. Reverts here (adapter can't source the assets) are what surface as withdraw liquidity reverts.

---

## Liquidity Fallback

### forceDeallocate

**Signature (deployed ABI):** `forceDeallocate(address adapter, bytes data, uint256 assets, address onBehalf) returns (uint256 penaltyShares)`
**Selector:** `0xe4d38cd8`

```solidity
/// @dev Returns shares withdrawn as penalty.
/// @dev When calling this function, a penalty is taken from onBehalf, in order to discourage allocation
/// manipulations.
function forceDeallocate(address adapter, bytes memory data, uint256 assets, address onBehalf)
    external
    returns (uint256)
{
    bytes32[] memory ids = deallocateInternal(adapter, data, assets);
    uint256 penaltyAssets = assets.mulDivUp(forceDeallocatePenalty[adapter], WAD);
    uint256 penaltyShares = withdraw(penaltyAssets, address(this), onBehalf);
    emit EventsLib.ForceDeallocate(msg.sender, adapter, assets, onBehalf, ids, penaltyAssets);
    return penaltyShares;
}
```

**Why it matters — penalty semantics.** This forcibly pulls `assets` from a specific `adapter` back into the vault (idle), then charges a penalty by calling `withdraw(penaltyAssets, address(this), onBehalf)` — i.e. it burns `onBehalf`'s shares worth `penaltyAssets` and returns those assets **to the vault itself** (`receiver = address(this)`, which is why `canReceiveAssets` whitelists `address(this)`). Net effect: the requested `assets` become idle/liquid but `onBehalf` pays a share-denominated penalty.

- Penalty rate = `forceDeallocatePenalty[adapter]` (WAD). **Live for the liquidity adapter `0x812B...b0ac`: `3000000000000000` = 3e15 = 0.30%.**
- `penaltyAssets = assets * penalty / WAD` (rounded up). So force-deallocating `X` assets costs the Safe ~`0.003 * X` worth of shares.
- **Not needed for normal management.** It is only a fallback to make liquidity available when the standard `withdraw`/`redeem` path is blocked by adapter illiquidity: force-deallocate into idle, then `redeem` normally. It does not itself send USDC to the Safe — it moves adapter assets to idle and takes a cut.

---

## Gate Checks (view)

All four gates are **unset (zero address) on the deployed vault**, so every check returns `true` for any account. Live-confirmed `true` for the Safe `0x9f0f855A7370cc30e24924258214681A782A34aC` on all four.

```solidity
function canReceiveShares(address account) public view returns (bool) {
    return receiveSharesGate == address(0) || IReceiveSharesGate(receiveSharesGate).canReceiveShares(account);
}

function canSendShares(address account) public view returns (bool) {
    return sendSharesGate == address(0) || ISendSharesGate(sendSharesGate).canSendShares(account);
}

function canReceiveAssets(address account) public view returns (bool) {
    return account == address(this) || receiveAssetsGate == address(0)
        || IReceiveAssetsGate(receiveAssetsGate).canReceiveAssets(account);
}

function canSendAssets(address account) public view returns (bool) {
    return sendAssetsGate == address(0) || ISendAssetsGate(sendAssetsGate).canSendAssets(account);
}
```

| Gate check         | Selector     | Guards                                                              | Live gate addr | Result for Safe |
| ------------------ | ------------ | ------------------------------------------------------------------- | -------------- | --------------- |
| `canReceiveShares` | `0x98c9b49c` | deposit/mint recipient (`enter`)                                    | `0x0`          | `true`          |
| `canSendAssets`    | `0x20fe8d58` | deposit/mint funder (`enter`)                                       | `0x0`          | `true`          |
| `canSendShares`    | `0x8e511e4d` | withdraw/redeem owner (`exit`)                                      | `0x0`          | `true`          |
| `canReceiveAssets` | `0x0d326b18` | withdraw/redeem recipient (`exit`); always true for `address(this)` | `0x0`          | `true`          |

**Why they matter:** These are the only permission gates on the user deposit/withdraw path. With all unset the flows are permissionless — no allowlist step is required for the Safe. If a curator ever sets a gate, deposits/withdrawals for the Safe would need the Safe whitelisted or they revert with `CannotReceiveShares` / `CannotSendAssets` / `CannotSendShares` / `CannotReceiveAssets`.

---

## Valuation / Preview (view)

```solidity
function previewDeposit(uint256 assets) public view returns (uint256) { /* assets → shares, rounds down */ }
function previewRedeem(uint256 shares) public view returns (uint256)  { /* shares → assets, rounds down */ }
function previewWithdraw(uint256 assets) public view returns (uint256){ /* assets → shares, rounds up   */ }
function convertToAssets(uint256 shares) external view returns (uint256) { return previewRedeem(shares); }
```

**Why they matter:** All fold in accrued performance/management fees via `accrueInterestView()` (fee shares added to supply). For off-chain position valuation the integration uses `balanceOf(Safe)` then `convertToAssets(shares)` / `previewRedeem(shares)` (both 18dp shares → 6dp USDC). Selectors: `previewDeposit 0xef8b30f7`, `previewRedeem 0x4cdad506`, `previewWithdraw 0x0a28a477`, `convertToAssets 0x07a2d13a`.

---

## Live state confirmation (Base RPC, this session)

| Field                                                                           | Value                                        |
| ------------------------------------------------------------------------------- | -------------------------------------------- |
| `receiveSharesGate` / `sendSharesGate` / `receiveAssetsGate` / `sendAssetsGate` | all `0x0` (unset)                            |
| `liquidityAdapter`                                                              | `0x812B71c33Ae5EAfEbAe967C5670e37eca3cab0ac` |
| `adaptersLength`                                                                | `1`                                          |
| `isAdapter(0x812B…b0ac)`                                                        | `true`                                       |
| `forceDeallocatePenalty(0x812B…b0ac)`                                           | `3000000000000000` (0.30%)                   |
| `canReceiveShares/canSendShares/canReceiveAssets/canSendAssets(Safe)`           | all `true`                                   |
| vault idle USDC balance                                                         | `0` (all assets in the adapter)              |
