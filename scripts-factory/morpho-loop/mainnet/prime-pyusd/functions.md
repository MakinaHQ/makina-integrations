# PRIME/PYUSD Morpho Loop — Function Implementations

Chain: ethereum (eth)
Generated: 2026-07-22
Source of truth: deployed verified sources + ABIs on Etherscan, resolved to implementations behind each EIP-1967 proxy; oracle immutables + Chainlink feeds read live via `cast` against mainnet.

## Proxy → implementation resolution

| Proxy (spec address)                                               | Kind         | Implementation read                          | Contract name                  |
| ------------------------------------------------------------------ | ------------ | -------------------------------------------- | ------------------------------ |
| wYLDS `0x6aD038cA6C04e885630851278ca0a856Ad9a66Cc`                 | ERC1967/UUPS | `0xda962f7a0308e9d4f2f60c5aab94f173c26d1a1d` | `YieldVault` (Hastra)          |
| PRIME `0x19ebb35279A16207Ec4ba82799CC64715065F7F6`                 | ERC1967/UUPS | `0x90fd843c68db38e2de0618acbb39341cba5a5abd` | `StakingVault` (Hastra)        |
| Morpho oracle `0x335e5718bC20028d5e357473a3736C187Ca6b07e`         | non-proxy    | (self)                                       | `MorphoChainlinkOracleV2`      |
| Morpho Blue `0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb`           | non-proxy    | (self)                                       | `Morpho`                       |
| flash_loan_aggregator `0x820D35e62Ad73a5Dc7b81d54cE993080d2064065` | non-proxy    | (self)                                       | `FlashloanAggregator` (makina) |

---

## ⚠️ TOP-LINE CORRECTIONS TO specs.yaml (verified from deployed code)

1. **The wYLDS whitelist is NOT a deposit/transfer gate. It does NOT block the caliber.**
   The `YieldVault._update` override (the only transfer hook) checks **only `frozen[]`** — there is **no whitelist check** on mint / deposit / transfer / `requestRedeem` / receiving `completeRedeem`. The `whitelistedAddresses` mapping is consulted in exactly two places: `withdrawUSDC(to,amount)` (a `WITHDRAWAL_ADMIN_ROLE` treasury function — `to` must be whitelisted) and `removeFromWhitelist` (existence check). **The redeemVault is whitelisted because it is a `withdrawUSDC` destination, not because deposits require it.**
   → `deposit.precondition_blocker.whitelist`, `intermediate.whitelist_gated: true`, `whitelist.gated: true`, and `open_items.whitelist_enforcement_point` are **incorrect**. A caliber can `deposit`, `requestRedeem`, and receive `completeRedeem` **without ever being whitelisted**. The only precondition is: not paused, caliber not `frozen`.

2. **wYLDS sync `redeem`/`withdraw` are hard-disabled** — they are `pure` overrides that `revert("Use requestRedeem/completeRedeem")` (not an ERC4626 max-revert). Exit is only via `requestRedeem` → admin `completeRedeem`. Confirms the async model.

3. **PRIME pricing uses a NAV oracle, not the ERC4626 share ratio.** `StakingVault._convertToShares/_convertToAssets` call `getVerifiedNav()` (a Chainlink FeedVerifier). `totalAssets()` is internal accounting (`_totalManagedAssets`), not `balanceOf`. Redeem/withdraw are standard synchronous ERC4626 (no async, no whitelist, `whenNotPaused` + `nonReentrant` + `frozen` check only). If `navOracle` were ever unset these convert/preview calls REVERT (`InvalidAddress`) — it is set on mainnet, so fine, but Stage 2 forks must preserve it.

4. **Morpho market oracle does NOT chain PRIME→wYLDS→USDC→PYUSD.** It composes exactly two Chainlink feeds and no vaults: `BASE_FEED_1 = "PRIME / WYLDS Exchange Rate"` (18 dec) divided by `QUOTE_FEED_1 = "PYUSD / USD"` (8 dec), with `SCALE_FACTOR = 1e26`. wYLDS is implicitly treated as \$1 (there is no USDC/USD hop). See the oracle section.

5. **wYLDS/PRIME use OpenZeppelin's non-enumerable `AccessControl`** — there is **no `getRoleMember`/`getRoleMemberCount`**. The `caller_role_holders` / `admin_holder` addresses in specs.yaml cannot be confirmed via an on-chain enumerator; they must come from `RoleGranted` event history or `hasRole(role, addr)` spot checks. `isWhitelisted(addr)` and `getWhitelistedAddresses()` DO exist (whitelist is array-backed).

6. **Flash loan for PYUSD: use provider `MORPHO` (enum = 3), zero fee.** The aggregator imposes no PYUSD-specific restriction (only the DSS/Maker path is token-restricted to DAI). Morpho Blue `flashLoan` lends against its own token balance at 0 fee, so PYUSD is flash-loanable as long as Morpho holds ≥ the requested amount (PYUSD is this market's loan token, so it does). See the flash-loan section.

---

## Overview

| Function                                              | Contract                            | Type                                              | Selector                |
| ----------------------------------------------------- | ----------------------------------- | ------------------------------------------------- | ----------------------- |
| deposit(uint256,address)                              | wYLDS / PRIME                       | Entry (ERC4626 + `whenNotPaused nonReentrant`)    | 0x6e553f65              |
| mint(uint256,address)                                 | wYLDS / PRIME                       | Entry                                             | 0x94bf804d              |
| requestRedeem(uint256)                                | wYLDS                               | Async exit step 1                                 | 0xaa2f892d              |
| completeRedeem(address)                               | wYLDS                               | Async exit step 2 (REWARDS_ADMIN)                 | 0x59d76fe7              |
| cancelRedeem()                                        | wYLDS                               | Async exit reversal                               | 0xe6a29666              |
| getPendingRedemption(address)                         | wYLDS                               | View                                              | 0x163421d0              |
| pendingRedemptions(address)                           | wYLDS                               | View (struct getter)                              | 0xe50fe9b9              |
| addToWhitelist(address)                               | wYLDS                               | Admin (WHITELIST_ADMIN) — treasury-only relevance | 0xe43252d7              |
| isWhitelisted(address)                                | wYLDS                               | View                                              | 0x3af32abf              |
| redeem(uint256,address,address)                       | wYLDS=`pure revert` / PRIME=sync    | —                                                 | 0xba087652              |
| withdraw(uint256,address,address)                     | wYLDS=`pure revert` / PRIME=sync    | —                                                 | 0xb460af94              |
| convertToAssets/Shares                                | wYLDS=`pure` 1:1 / PRIME=NAV `view` | View                                              | 0x07a2d13a / 0xc6e6f592 |
| getVerifiedNav()                                      | PRIME                               | View (Chainlink)                                  | 0x552e725b              |
| supplyCollateral(...)                                 | Morpho Blue                         | State                                             | 0x238d6579              |
| borrow(...)                                           | Morpho Blue                         | State                                             | 0x50d8cd4b              |
| repay(...)                                            | Morpho Blue                         | State                                             | 0x20b76e81              |
| withdrawCollateral(...)                               | Morpho Blue                         | State                                             | 0x8720316d              |
| position(bytes32,address)                             | Morpho Blue                         | View                                              | 0x93c52062              |
| market(bytes32)                                       | Morpho Blue                         | View                                              | 0x5c60e39a              |
| price()                                               | Morpho oracle                       | View                                              | 0xa035b1fe              |
| requestFlashloan((uint8,Instruction,address,uint256)) | flash aggregator                    | State (onlyCaliber)                               | 0x4140b286              |
| onMorphoFlashLoan(uint256,bytes)                      | flash aggregator                    | Callback                                          | 0x31f57072              |

---

## 1. wYLDS — `YieldVault` (impl `0xda962f7a…`)

ERC4626 over USDC. `decimals() = 6` (inherits underlying). `asset() = USDC 0xA0b8…eB48`.
Roles (constants): `REWARDS_ADMIN_ROLE=keccak256("REWARDS_ADMIN")`, `WHITELIST_ADMIN_ROLE=keccak256("WHITELIST_ADMIN")`, `WITHDRAWAL_ADMIN_ROLE=keccak256("WITHDRAWAL_ADMIN")`, `FREEZE_ADMIN_ROLE=keccak256("FREEZE_ADMIN")`, plus `PAUSER_ROLE`, `UPGRADER_ROLE`, `DEFAULT_ADMIN_ROLE`.

### deposit(uint256 assets, address receiver) → shares

**Selector:** `0x6e553f65`. **Divergence from spec:** deposit is NOT whitelist-gated (see correction #1).

```solidity
function deposit(uint256 assets, address receiver)
    public override whenNotPaused nonReentrant returns (uint256 shares)
{
    return super.deposit(assets, receiver);   // OZ ERC4626: previewDeposit -> _deposit
}
// _deposit (OZ base, no override of transfer semantics): safeTransferFrom(USDC, caller, vault, assets); _mint(receiver, shares)
// maxDeposit(address) = type(uint256).max
```

`mint(shares,receiver)` (0x94bf804d) is the symmetric variant, same modifiers. `depositWithPermit(...)` wraps `super.deposit`. Because wYLDS is 1:1 (see convert), `shares == assets`.

**Whitelist enforcement — pinpointed.** The ONLY transfer hook:

```solidity
function _update(address from, address to, uint256 amount) internal override(ERC20Upgradeable) {
    if (from != address(0) && frozen[from]) revert AccountIsFrozen();
    if (to   != address(0) && frozen[to])   revert AccountIsFrozen();
    super._update(from, to, amount);          // NO whitelist check anywhere
}
```

`whitelistedAddresses[]` is referenced only here:

```solidity
function withdrawUSDC(address to, uint256 amount) external onlyRole(WITHDRAWAL_ADMIN_ROLE) whenNotPaused nonReentrant {
    ...
    if (!whitelistedAddresses[to]) revert AddressNotWhitelisted();   // treasury egress only
    ...
}
function removeFromWhitelist(address account) external onlyRole(WHITELIST_ADMIN_ROLE) {
    if (!whitelistedAddresses[account]) revert AddressNotInWhitelist();
    ...
}
```

So `AddressNotWhitelisted` can only be thrown by `withdrawUSDC`, and `AddressNotInWhitelist` only by `removeFromWhitelist`. **Neither is reachable on the caliber's deposit/exit path.** → whitelisting the caliber is unnecessary; Stage 4 does not need the `addToWhitelist(caliber)` fork step for deposits to succeed.

### requestRedeem(uint256 shares) [selector 0xaa2f892d]

```solidity
function requestRedeem(uint256 shares) external whenNotPaused nonReentrant {
    if (shares == 0) revert InvalidAmount();
    if (pendingRedemptions[msg.sender].shares != 0) revert RedemptionAlreadyPending();
    uint256 assets = convertToAssets(shares);                 // 1:1, USDC units
    _transfer(msg.sender, address(this), shares);             // shares LOCKED in the vault (frozen check only)
    pendingRedemptions[msg.sender] = PendingRedemption({ shares: shares, assets: assets, timestamp: block.timestamp });
    emit RedemptionRequested(msg.sender, shares, assets, block.timestamp);
}
```

- One pending redemption per address (`RedemptionAlreadyPending` otherwise). Shares are moved to the vault (not burned yet). No whitelist. No timelock.

### completeRedeem(address user) [selector 0x59d76fe7]

```solidity
function completeRedeem(address user) external onlyRole(REWARDS_ADMIN_ROLE) nonReentrant {
    if (frozen[user]) revert AccountIsFrozen();
    PendingRedemption memory redemption = pendingRedemptions[user];
    if (redemption.shares == 0) revert NoRedemptionPending();
    uint256 vaultBalance = IERC20(asset()).balanceOf(redeemVault);
    if (vaultBalance < redemption.assets) revert InsufficientVaultBalance();
    delete pendingRedemptions[user];                          // pending term self-drops to 0 here
    _burn(address(this), redemption.shares);                  // locked shares burned
    SafeERC20.safeTransferFrom(IERC20(asset()), redeemVault, user, redemption.assets);   // USDC redeemVault -> user
    emit RedemptionCompleted(user, redemption.shares, redemption.assets, block.timestamp);
}
```

- **Gate:** `onlyRole(REWARDS_ADMIN_ROLE)` — the caliber CANNOT call this itself. Operational dependency on Hastra.
- **Vault-balance check:** reverts `InsufficientVaultBalance` unless `USDC.balanceOf(redeemVault) >= pending.assets`. `redeemVault` must also have an ERC20 allowance to the wYLDS contract (the `safeTransferFrom` spender is the vault). Spec's live values: redeemVault `0xA8C3CF…faCd` held ~972 USDC and had allowance `5881907903360` to wYLDS — large redemptions revert until Hastra funds it. On a fork: fund redeemVault with USDC (+ set allowance if the fork resets it) before calling.
- Also reverts `AccountIsFrozen` if the receiving user is frozen.

### cancelRedeem() [0xe6a29666]

```solidity
function cancelRedeem() external nonReentrant {
    PendingRedemption memory redemption = pendingRedemptions[msg.sender];
    if (redemption.shares == 0) revert NoRedemptionPending();
    delete pendingRedemptions[msg.sender];
    _transfer(address(this), msg.sender, redemption.shares);  // shares returned to caller
    emit RedemptionCancelled(msg.sender, redemption.shares);
}
```

Caliber-callable; reverses a pending request and returns the locked shares. No admin gate.

### Storage layout / views for the async pending term

`struct PendingRedemption { uint256 shares; uint256 assets; uint256 timestamp; }` stored in `mapping(address => PendingRedemption) public pendingRedemptions`.

- `pendingRedemptions(address)` (0xe50fe9b9) → `(uint256 shares, uint256 assets, uint256 timestamp)`.
- `getPendingRedemption(address)` (0x163421d0) → `(bool hasPending, uint256 shares, uint256 assets)` where `hasPending = shares != 0`.
  Both return zeros after `completeRedeem` (mapping `delete`d) — the accounting pending term auto-zeros exactly when USDC lands loose, so no double count. Confirms spec `account.pending_query`.

### Whitelist admin

```solidity
function addToWhitelist(address account) external onlyRole(WHITELIST_ADMIN_ROLE) {
    if (account == address(0)) revert InvalidAddress();
    if (whitelistedAddresses[account]) revert AddressAlreadyWhitelisted();
    whitelistedAddresses[account] = true; _whitelistArray.push(account); emit AddressWhitelisted(account);
}
```

`isWhitelisted(addr)` → `whitelistedAddresses[addr]`. `getWhitelistedAddresses()` / `getWhitelistCount()` expose the array. (Relevant only to `withdrawUSDC` egress — not to the caliber flow.)

### convert / sync-exit disabled

```solidity
function convertToShares(uint256 assets) public pure override returns (uint256) { return assets; } // 1:1
function convertToAssets(uint256 shares) public pure override returns (uint256) { return shares; } // 1:1
function withdraw(uint256,address,address) public pure override returns (uint256) { revert("Use requestRedeem/completeRedeem"); }
function redeem(uint256,address,address)   public pure override returns (uint256) { revert("Use requestRedeem/completeRedeem"); }
```

---

## 2. PRIME — `StakingVault` (impl `0x90fd843c…`)

ERC4626 over **wYLDS**. `asset() = wYLDS 0x6aD0…66Cc`. `decimals() = 6`.
Roles: `REWARDS_ADMIN_ROLE`, `FREEZE_ADMIN_ROLE`, `NAV_ORACLE_UPDATER_ROLE`, `PAUSER_ROLE`, `UPGRADER_ROLE`, `DEFAULT_ADMIN_ROLE`. **No whitelist mechanism at all** (no `whitelistedAddresses`, no `getWhitelistCount` — confirms spec note that `getWhitelistCount` reverts on PRIME).

### deposit / mint / redeem / withdraw — SYNCHRONOUS standard ERC4626

```solidity
function deposit(uint256 assets, address receiver) public override whenNotPaused nonReentrant returns (uint256 shares) { return super.deposit(assets, receiver); }
function mint  (uint256 shares, address receiver) public override whenNotPaused nonReentrant returns (uint256 assets) { return super.mint(shares, receiver); }
function redeem(uint256 shares, address receiver, address owner) public override whenNotPaused nonReentrant returns (uint256 assets) { return super.redeem(shares, receiver, owner); }
function withdraw(uint256 assets, address receiver, address owner) public override whenNotPaused nonReentrant returns (uint256 shares) { return super.withdraw(assets, receiver, owner); }
```

- **No async, no whitelist, no request/complete.** Standard OZ redeem/withdraw run instantly. Only extra gating is `whenNotPaused` + `nonReentrant` + the `frozen` check in `_update` (same shape as wYLDS `_update`). `maxRedeem(owner) = balanceOf(owner)` (OZ default). Confirms spec `collateral.redemption: SYNCHRONOUS`.
- `redeem`/`withdraw` selectors: `0xba087652` / `0xb460af94`.

### Share price math (the ~1.0497 / 1.049629 source)

PRIME does NOT use `balanceOf`/supply ratio. It uses a NAV feed:

```solidity
function totalAssets() public view override returns (uint256) { return _totalManagedAssets; }   // internal accounting

function _convertToShares(uint256 assets, Math.Rounding rounding) internal view override returns (uint256) {
    uint256 nav = getVerifiedNav();            // reverts if oracle unset / price<=0
    return assets.mulDiv(1e18, nav, rounding);  // shares = assets * 1e18 / NAV
}
function _convertToAssets(uint256 shares, Math.Rounding rounding) internal view override returns (uint256) {
    uint256 nav = getVerifiedNav();
    return shares.mulDiv(nav, 1e18, rounding);  // assets(wYLDS) = shares * NAV / 1e18
}
function getVerifiedNav() public view returns (uint256 nav) {
    if (navOracle == address(0)) revert InvalidAddress();
    int192 price = IFeedVerifier(navOracle).priceOf(navFeedId);
    if (price <= 0) revert NavInvalid();
    nav = uint256(uint192(price));              // 1e18-scaled wYLDS-per-PRIME
}
```

- NAV is **wYLDS per PRIME, 1e18-scaled**. `convertToAssets(1e6 PRIME) = 1e6 * NAV / 1e18`. With NAV ≈ 1.0496e18 this gives ≈ 1.049629e6 wYLDS — matches spec `convert_to_assets_1e6: 1049629`. PRIME appreciates as NAV rises.
- **Fork note:** these are `view` and will REVERT if `navOracle` is address(0) or the FeedVerifier price is stale/≤0. Mainnet has it set; preserve on forks or PRIME deposit/redeem previews revert.
- `_deposit`/`_withdraw` maintain `_totalManagedAssets` (donation-attack guard) and revert `ZeroAmount` on 0 assets.

---

## 3. Morpho market oracle — `MorphoChainlinkOracleV2` (`0x335e…b07e`)

Standard Morpho Chainlink oracle. `price()`:

```solidity
function price() external view returns (uint256) {
    return SCALE_FACTOR.mulDiv(
        BASE_VAULT.getAssets(BASE_VAULT_CONVERSION_SAMPLE) * BASE_FEED_1.getPrice() * BASE_FEED_2.getPrice(),
        QUOTE_VAULT.getAssets(QUOTE_VAULT_CONVERSION_SAMPLE) * QUOTE_FEED_1.getPrice() * QUOTE_FEED_2.getPrice()
    );
}
// getAssets returns 1 when the vault is address(0); getPrice returns 1 when the feed is address(0)
```

**Live immutables (read via `cast`):**

| Immutable    | Value                                                                                                     |
| ------------ | --------------------------------------------------------------------------------------------------------- |
| BASE_VAULT   | `0x0` (none)                                                                                              |
| QUOTE_VAULT  | `0x0` (none)                                                                                              |
| BASE_FEED_1  | `0xf17C0EdcAA28371e9c8012D7699bF40ECF0F58d1` — "PRIME / WYLDS Exchange Rate", **18 dec**, ≈ `1.049593e18` |
| BASE_FEED_2  | `0x0`                                                                                                     |
| QUOTE_FEED_1 | `0x8f1dF6D7F2db73eECE86a18b4381F4707b918FB1` — "PYUSD / USD", **8 dec**, ≈ `0.99990747e8`                 |
| QUOTE_FEED_2 | `0x0`                                                                                                     |
| SCALE_FACTOR | `1e26` (`100000000000000000000000000`)                                                                    |

So effectively:

```
price() = 1e26 * pricePRIMEperWYLDS(1e18) / pricePYUSDperUSD(1e8)
        = PRIME-in-PYUSD scaled by 1e36   (both tokens 6 dec → clean 1e36 Morpho convention)
```

`= 1e26 * 1.049593e18 / 0.9999e8 ≈ 1.04969e36`. Matches spec `price_now 1049690555221613945938417681788095852`.

**Composition reality (vs spec guess):** it is `PRIME→wYLDS` (exchange-rate feed) ÷ `PYUSD/USD`. There is **no USDC feed / no ERC4626 vault chaining**; wYLDS is implicitly valued at \$1 (the "PRIME/WYLDS" feed number is used as if PRIME/USD). SCALE_FACTOR check: `1e26 = 10^(36 + 6[PYUSD dec] + 8[fpQ1] − 6[PRIME dec] − 18[fpB1])`. ✓
Morpho Blue accounting: `collateral_in_pyusd = collateral(PRIME, 6dec) * price() / 1e36`. Confirms spec `collateral_value_formula`.

---

## 4. Morpho Blue (`0xBBBB…FFCb`)

`MarketParams` struct order = **(address loanToken, address collateralToken, address oracle, address irm, uint256 lltv)**. `Id` = keccak256 of the params. For this market: `(PYUSD, PRIME, 0x335e…b07e, 0x870a…00BC, 860000000000000000)`; id `0x41c4…a3fa`.

### supplyCollateral(MarketParams,uint256 assets,address onBehalf,bytes data) [0x238d6579]

```solidity
function supplyCollateral(MarketParams memory marketParams, uint256 assets, address onBehalf, bytes calldata data) external {
    Id id = marketParams.id();
    require(market[id].lastUpdate != 0, ErrorsLib.MARKET_NOT_CREATED);
    require(assets != 0, ErrorsLib.ZERO_ASSETS);
    require(onBehalf != address(0), ErrorsLib.ZERO_ADDRESS);
    position[id][onBehalf].collateral += assets.toUint128();
    emit EventsLib.SupplyCollateral(id, msg.sender, onBehalf, assets);
    if (data.length > 0) IMorphoSupplyCollateralCallback(msg.sender).onMorphoSupplyCollateral(assets, data);
    IERC20(marketParams.collateralToken).safeTransferFrom(msg.sender, address(this), assets);
}
```

No health check (adding collateral only improves health). Requires prior PRIME approval to Morpho. `data = 0x`.

### borrow(MarketParams,uint256 assets,uint256 shares,address onBehalf,address receiver) → (assets,shares) [0x50d8cd4b]

```solidity
require(UtilsLib.exactlyOneZero(assets, shares), ...);   // pass assets, shares=0
require(_isSenderAuthorized(onBehalf), UNAUTHORIZED);    // caliber must be onBehalf or authorized
_accrueInterest(marketParams, id);
if (assets > 0) shares = assets.toSharesUp(totalBorrowAssets, totalBorrowShares);
position[id][onBehalf].borrowShares += shares.toUint128();
market[id].totalBorrowShares += ...; market[id].totalBorrowAssets += ...;
require(_isHealthy(marketParams, id, onBehalf), INSUFFICIENT_COLLATERAL);   // enforces lltv 0.86
require(totalBorrowAssets <= totalSupplyAssets, INSUFFICIENT_LIQUIDITY);
IERC20(loanToken).safeTransfer(receiver, assets);
```

`onBehalf = receiver = caliber`. For the flash-loan `loop_in`, `assets = flashLoanAmount` to repay the FL.

### repay(MarketParams,uint256 assets,uint256 shares,address onBehalf,bytes data) → (assets,shares) [0x20b76e81]

```solidity
require(UtilsLib.exactlyOneZero(assets, shares), ...);
_accrueInterest;
if (assets > 0) shares = assets.toSharesDown(totalBorrowAssets, totalBorrowShares);
else            assets = shares.toAssetsUp (totalBorrowAssets, totalBorrowShares);   // FULL close: assets=0, shares=borrowShares
position[id][onBehalf].borrowShares -= shares.toUint128();
market[id].totalBorrowAssets = zeroFloorSub(totalBorrowAssets, assets).toUint128();
if (data.length > 0) IMorphoRepayCallback(msg.sender).onMorphoRepay(assets, data);
IERC20(loanToken).safeTransferFrom(msg.sender, address(this), assets);
```

Requires PYUSD approval to Morpho. Full close pattern: `assets=0, shares=borrowShares` (reads via `position`). `data=0x`.

### withdrawCollateral(MarketParams,uint256 assets,address onBehalf,address receiver) [0x8720316d]

```solidity
require(assets != 0, ZERO_ASSETS);
require(_isSenderAuthorized(onBehalf), UNAUTHORIZED);
_accrueInterest;
position[id][onBehalf].collateral -= assets.toUint128();
require(_isHealthy(marketParams, id, onBehalf), INSUFFICIENT_COLLATERAL);  // must stay healthy → repay first
IERC20(collateralToken).safeTransfer(receiver, assets);
```

### position(bytes32 id,address user) [0x93c52062] → (uint256 supplyShares, uint128 borrowShares, uint128 collateral)

### market(bytes32 id) [0x5c60e39a] → (uint128 totalSupplyAssets, uint128 totalSupplyShares, uint128 totalBorrowAssets, uint128 totalBorrowShares, uint128 lastUpdate, uint128 fee)

Confirms spec indices: `collateral_index=2`, `borrow_shares_index=1`; `total_borrow_assets_index=2`, `total_borrow_shares_index=3`.
**Debt (PYUSD):** `debt = borrowShares * totalBorrowAssets / totalBorrowShares` (round up = `toAssetsUp`; use `max(totalBorrowShares,1)` guard as in spec). Matches `debt_formula`.
`idToMarketParams(bytes32)` selector `0x2c3c9157` (used by blueprints to expand the tuple).

---

## 5. flash_loan_aggregator — `FlashloanAggregator` (makina, `0x820D…4065`)

### Entry: requestFlashloan(FlashloanRequest) [selector 0x4140b286]

```solidity
struct FlashloanRequest { FlashloanProvider provider; ICaliber.Instruction instruction; address token; uint256 amount; }
enum FlashloanProvider { AAVE_V3, BALANCER_V2, BALANCER_V3, MORPHO, DSS_FLASH }   // MORPHO = 3

function requestFlashloan(FlashloanRequest calldata request) external override onlyCaliber {
    _dispatchFlashloanRequest(request);   // routes by provider
}
```

- `onlyCaliber` (caller must be a Caliber registered in `caliberFactory`).
- ABI signature used by the blueprint (`flashloan-request.yaml`): the `Instruction` tuple is `(uint256,bool,uint256,uint8,address[],address[],bytes32[],bytes[],uint128,bytes32[])`, so the full selector is over `requestFlashloan((uint8,(uint256,bool,uint256,uint8,address[],address[],bytes32[],bytes[],uint128,bytes32[]),address,uint256))` = **0x4140b286**.

### Morpho path (what to use for PYUSD)

```solidity
function _requestMorphoFlashloan(FlashloanRequest calldata request) internal {
    if (morphoPool == address(0)) revert MorphoPoolNotSet();
    bytes memory data = abi.encode(request.token, msg.sender, request.instruction);
    _setExpectedDataHash(data);
    IMorpho(morphoPool).flashLoan(request.token, request.amount, data);   // Morpho Blue flashLoan, ZERO fee
}
function onMorphoFlashLoan(uint256 assets, bytes calldata data) external {   // selector 0x31f57072
    _isValidExpectedDataHash(data); _clearExpectedDataHash();
    if (msg.sender != morphoPool) revert NotMorpho();
    (address token, address caliber, ICaliber.Instruction memory instruction) = abi.decode(data, (address,address,ICaliber.Instruction));
    _handleFlashloanCallback(caliber, instruction, token, assets);
    IERC20(token).safeIncreaseAllowance(morphoPool, assets);   // repay exactly `assets` (fee = 0)
}
```

- **PYUSD support:** there is **no per-token allowlist** for the Morpho path (only `_requestDssFlashloan` restricts `token == dai`, reverting `InvalidToken` otherwise). Morpho Blue `flashLoan(token,assets,data)` (selector `0xe0232b42`) lends from Morpho's own balance of `token` at **0 fee**; repayment is `assets` exactly. PYUSD is this market's loan token so Morpho holds a large PYUSD balance → PYUSD flash loans succeed up to that balance. **Use `provider = MORPHO (3)`, `token = PYUSD`.**
- Balancer V2/V3 also viable if those pools hold PYUSD, but Morpho is the natural zero-fee choice and matches the precedent.
- The `_handleFlashloanCallback` re-enters the caliber to run the `Instruction` (the `loop_in`/`loop_out`/`close_loop` blueprint) via the FLASHLOAN_MANAGEMENT wiring.

### Existing wiring to reuse (Stage 3)

`instructions/morpho-loop-swap.yaml` already implements the full 9-entry template for this exact archetype (loan_token flash-loaned, swap↔collateral, Morpho supply/borrow/repay/withdraw, oracle accounting):

- **1/9** `blueprints/makina/flashloan-request.yaml:flashloan_request` — MANAGEMENT; `flash_loan_venue` uint8 (**Morpho = 3**), `flash_loan_token`, `flash_loan_amount`, `flash_loan_data`.
- **2/9 loop_in** `blueprints/morpho-loop/deposit-swap.yaml:loop_in` — FLASHLOAN_MANAGEMENT: approve+swap loan→collateral, `idToMarketParams`+`extractElementFromStaticTuple` to rebuild the tuple, `supplyCollateral`, then `borrow(flash_loan_amount)` to repay FL.
- **3/9 loop_out** / **4/9 close_loop** `blueprints/morpho-loop/withdraw-swap.yaml` — repay (by amount / by shares), `withdrawCollateral`, swap collateral→loan to repay FL.
- **5/9 add_collateral**, **6/9 borrow** (`blueprints/morpho/borrow.yaml`), **7/9 repay** (`blueprints/morpho/repay.yaml:repay_asset`), **8/9 withdraw_collateral** (`blueprints/morpho-loop/withdraw.yaml`), **9/9 account** (`blueprints/morpho-loop/account.yaml:account_equity`).
- config keys consumed: `flash_loan_aggregator`, `swap_module`, `morpho_address`, `caliber_helper_address`, `caliber_address`, `unsigned_math_helper_address`; position vars: `collateral_token`, `loan_token`, `morpho_market_id`, `oracle_address`, `label`.

**PRIME/PYUSD divergence from that generic template (Stage 2/3 must resolve):** the generic `deposit-swap:loop_in` assumes a single-call DEX swap `loan_token → collateral_token`. Here the collateral path is `PYUSD →(swap)→ USDC →(wYLDS.deposit)→ wYLDS →(PRIME.deposit)→ PRIME` — two ERC4626 wraps that a DEX aggregator will not do. And **exit is async** (`wYLDS.requestRedeem`→admin `completeRedeem`), so `withdraw-swap:loop_out/close_loop` (atomic swap collateral→loan inside the FL callback) is only viable if a **synchronous DEX route PRIME/wYLDS→PYUSD exists** (spec open_item `synchronous_dex_route`; likely thin/absent for RWA). Absent that route, exit is the staged VARIANT B unwind and a bespoke deposit blueprint (with the two wrap steps) is needed rather than the stock `deposit-swap.yaml`.

---

## Fetch-status notes

- All signatures confirmed against the deployed implementation ABIs (`get_contract_abi` on the impls) and, for the whitelist/NAV logic, against the full verified sources pulled from Etherscan (`YieldVault.sol`, `StakingVault.sol`) — `get_function_code` alone returned OZ base stubs for `deposit/_deposit/_update/redeem/convertToAssets`, so the contract-level overrides were read from the full source (exactly the ambiguity spec flagged).
- Oracle immutables and both Chainlink feeds read live on mainnet via `cast`.
- Not on-chain verifiable: exact `REWARDS_ADMIN_ROLE`/`WHITELIST_ADMIN_ROLE` holder set (non-enumerable AccessControl — use `RoleGranted` logs or `hasRole` spot checks; the spec's holder addresses were not confirmable via an enumerator).
