# Royco ST sUSDai - Function Implementations

Chain: Arbitrum (42161)
Generated: 2026-04-08

## Overview

| Function                                     | Contract       | Address                                    | Type            |
| -------------------------------------------- | -------------- | ------------------------------------------ | --------------- |
| deposit(uint256,address)                     | Senior Tranche | 0x90465aad...7017 (impl: 0x4afd9e...5bc5f) | Entry -> Kernel |
| redeem(uint256,address,address)              | Senior Tranche | 0x90465aad...7017                          | Entry -> Kernel |
| convertToAssets(uint256)                     | Senior Tranche | 0x90465aad...7017                          | View -> Kernel  |
| maxDeposit(address)                          | Senior Tranche | 0x90465aad...7017                          | View -> Kernel  |
| previewDeposit(TRANCHE_UNIT)                 | Senior Tranche | 0x90465aad...7017                          | View -> Kernel  |
| previewRedeem(uint256)                       | Senior Tranche | 0x90465aad...7017                          | View -> Kernel  |
| deposit(uint256,address)                     | sUSDai         | 0x0B2b2B20...55ef9 (impl: 0xda8c2f...8460) | Entry           |
| requestRedeem(uint256,address,address)       | sUSDai         | 0x0B2b2B20...55ef9                         | Entry           |
| redeem(uint256,address,address)              | sUSDai         | 0x0B2b2B20...55ef9                         | Entry           |
| withdraw(uint256,address,address)            | sUSDai         | 0x0B2b2B20...55ef9                         | Entry           |
| convertToAssets(uint256)                     | sUSDai         | 0x0B2b2B20...55ef9                         | View            |
| previewDeposit(uint256)                      | sUSDai         | 0x0B2b2B20...55ef9                         | View            |
| depositSharePrice()                          | sUSDai         | 0x0B2b2B20...55ef9                         | View            |
| redemptionSharePrice()                       | sUSDai         | 0x0B2b2B20...55ef9                         | View            |
| serviceRedemptions(uint256)                  | sUSDai         | 0x0B2b2B20...55ef9                         | Admin-only      |
| pendingRedeemRequest(uint256,address)        | sUSDai         | 0x0B2b2B20...55ef9                         | View            |
| claimableRedeemRequest(uint256,address)      | sUSDai         | 0x0B2b2B20...55ef9                         | View            |
| redemptionIds(address)                       | sUSDai         | 0x0B2b2B20...55ef9                         | View            |
| redemption(uint256)                          | sUSDai         | 0x0B2b2B20...55ef9                         | View            |
| maxRedeem(address)                           | sUSDai         | 0x0B2b2B20...55ef9                         | View            |
| maxWithdraw(address)                         | sUSDai         | 0x0B2b2B20...55ef9                         | View            |
| redemptionQueueInfo()                        | sUSDai         | 0x0B2b2B20...55ef9                         | View            |
| deposit(address,uint256,uint256,address)     | USDai          | 0x0A1a1A10...82EF (impl: 0x547707...87a2)  | Entry           |
| withdraw(address,uint256,uint256,address)    | USDai          | 0x0A1a1A10...82EF                          | Entry           |
| isBlacklisted(address)                       | USDai          | 0x0A1a1A10...82EF                          | View            |
| getTrancheUnitToNAVUnitConversionRateWAD()   | Kernel         | 0xFdb17E53...9CA (impl: 0x8c87ac...0dda)   | View            |
| getStoredConversionRateWAD()                 | Kernel         | 0xFdb17E53...9CA                           | View            |
| _convertTrancheUnitsToNAVUnits(TRANCHE_UNIT) | Kernel         | 0xFdb17E53...9CA                           | Internal View   |

---

## Deposit Functions

### Senior Tranche: deposit(uint256,address)

**Contract:** `0x90465aad4e426948A4ea342AC49A1A38200B7017` (proxy)
**Implementation:** `0x4afd9e2b4fbec1f11d09bf2e3d3f82869fa5bc5f`
**Signature:** `deposit(TRANCHE_UNIT _assets, address _receiver) returns (uint256 shares)`

```solidity
function deposit(TRANCHE_UNIT _assets, address _receiver) public virtual override whenNotPaused restricted returns (uint256 shares) {
    require(_receiver != address(0), ERC20InvalidReceiver(address(0)));
    require(_assets != toTrancheUnits(0), MUST_DEPOSIT_NON_ZERO_ASSETS());

    // Transfer the assets to the kernel
    IERC20(ASSET).safeTransferFrom(msg.sender, KERNEL, toUint256(_assets));

    // Deposit the assets into the Royco market and get the fraction of total assets allocated
    (NAV_UNIT valueAllocated, NAV_UNIT effectiveNAVToMintAt) =
        (TRANCHE_TYPE() == TrancheType.SENIOR ? IRoycoKernel(KERNEL).stDeposit(_assets) : IRoycoKernel(KERNEL).jtDeposit(_assets));

    // effectiveNAVToMint at can be zero initially when the tranche is deployed
    require(valueAllocated != ZERO_NAV_UNITS, INVALID_VALUE_ALLOCATED());

    // valueAllocated represents the value of the assets deposited in the asset that the tranche's NAV is denominated in
    // shares are minted to the user at the effective NAV of the tranche
    // effectiveNAVToMintAt is the effective NAV of the tranche before the deposit is made, ie. the NAV at which the shares will be minted
    shares = _convertToShares(valueAllocated, totalSupply(), effectiveNAVToMintAt, Math.Rounding.Floor);

    // Mint the shares to the receiver
    _mint(_receiver, shares);

    emit Deposit(msg.sender, _receiver, _assets, shares);
}
```

**Key observations:**

- Uses `whenNotPaused` and `restricted` (AccessManaged) modifiers
- `ASSET` = sUSDai, `KERNEL` = 0xFdb17E53eA5d342124b8473188BCB9F05F1949CA
- Calls `safeTransferFrom(msg.sender, KERNEL, ...)` -- approval must be to the ST contract address
- Delegates deposit accounting to `IRoycoKernel(KERNEL).stDeposit(_assets)`
- 2-argument function (assets, receiver), NOT 3-argument like sNUSD ST

**Internal: _convertToShares**

```solidity
function _convertToShares(NAV_UNIT _assets, uint256 _totalSupply, NAV_UNIT _totalAssets, Math.Rounding _rounding) internal pure returns (uint256 shares) {
    return _withVirtualShares(_totalSupply).mulDiv(_assets, _withVirtualAssets(_totalAssets), _rounding);
}
```

---

### sUSDai: deposit(uint256,address)

**Contract:** `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (proxy)
**Implementation:** `0xda8c2f3da2857e9d66f813d11baba555aab46460`
**Signature:** `deposit(uint256 amount, address receiver) returns (uint256)`

```solidity
// Entry point
function deposit(uint256 amount, address receiver) external returns (uint256) {
    return _deposit(amount, receiver, 0);
}

// Internal implementation
function _deposit(
    uint256 amount,
    address receiver,
    uint256 minShares
) internal whenNotPaused nonReentrant nonZeroUint(amount) nonZeroAddress(receiver) returns (uint256) {
    /* Compute shares */
    uint256 shares = convertToShares(amount);

    /* If shares is 0 or less than min shares, revert */
    if (shares == 0 || shares < minShares) revert InvalidAmount();

    /* If initial deposit, mint locked shares */
    _mintLockedShares();

    /* Mint shares */
    _mint(receiver, shares);

    /* Update deposits balance */
    _getDepositsStorage().balance += amount;

    /* Deposit assets */
    IERC20(asset()).safeTransferFrom(msg.sender, address(this), amount);

    /* Emit Deposit */
    emit Deposit(msg.sender, receiver, amount, shares);

    return shares;
}
```

**Key observations:**

- Standard ERC4626 deposit -- transfers USDai from msg.sender to sUSDai contract
- `whenNotPaused`, `nonReentrant` modifiers
- 2-arg version passes `minShares=0` (no slippage protection); 3-arg overload allows minShares
- Uses `convertToShares(amount)` for share calculation based on `depositSharePrice()`

**Helper: convertToShares**

```solidity
function convertToShares(uint256 assets) public view returns (uint256) {
    bool initialDeposit = totalSupply() < LOCKED_SHARES;
    return ((assets * FIXED_POINT_SCALE) / depositSharePrice()) - (initialDeposit ? LOCKED_SHARES : 0);
}
```

---

### USDai: deposit(address,uint256,uint256,address)

**Contract:** `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF` (proxy)
**Implementation:** `0x5477072aa366cff31c1c28b81ed783a2a1cf87a2`
**Signature:** `deposit(address depositToken, uint256 depositAmount, uint256 usdaiAmountMinimum, address recipient) returns (uint256)`

```solidity
// Entry point (4-arg version, uses empty swap path)
function deposit(
    address depositToken,
    uint256 depositAmount,
    uint256 usdaiAmountMinimum,
    address recipient
) external nonReentrant returns (uint256) {
    return _deposit(depositToken, depositAmount, usdaiAmountMinimum, recipient, msg.data[0:0]);
}

// Internal implementation (5-arg with custom swap path)
function _deposit(
    address depositToken,
    uint256 depositAmount,
    uint256 usdaiAmountMinimum,
    address recipient,
    bytes calldata data
) internal nonZeroUint(depositAmount) nonZeroAddress(recipient) returns (uint256) {
    /* Accrue base yield */
    _accrue();

    /* Transfer token in from sender to this contract */
    IERC20(depositToken).safeTransferFrom(msg.sender, address(this), depositAmount);

    /* If the deposit token isn't base token, swap in */
    uint256 usdaiAmount;
    if (depositToken != address(_baseToken)) {
        /* Approve the adapter to spend the token in */
        IERC20(depositToken).forceApprove(address(_swapAdapter), depositAmount);

        /* Swap in deposit token for base token */
        usdaiAmount = _scale(_swapAdapter.swapIn(depositToken, depositAmount, _unscaleUp(usdaiAmountMinimum), data));
    } else {
        usdaiAmount = _scale(depositAmount);
    }

    /* Check if the supply cap is exceeded */
    if (!hasRole(DEPOSIT_ADMIN_ROLE, msg.sender) && usdaiAmount + totalSupply() + bridgedSupply() > supplyCap()) {
        revert SupplyCapExceeded();
    }

    /* Mint to the recipient */
    _mint(recipient, usdaiAmount);

    /* Emit deposited event */
    emit Deposited(msg.sender, recipient, depositToken, depositAmount, usdaiAmount);

    return usdaiAmount;
}
```

**Key observations:**

- `nonReentrant` modifier on entry; `nonZeroUint` and `nonZeroAddress` on internal
- When `depositToken != _baseToken` (PYUSD), swaps via `_swapAdapter.swapIn()` (Uniswap V3)
- When `depositToken == _baseToken` (PYUSD), just scales: `_scale(depositAmount)` = amount * _scaleFactor
- For USDC (6 decimals), the swap adapter converts USDC -> PYUSD, then `_scale` converts 6-decimal PYUSD to 18-decimal USDai
- Supply cap check can be bypassed by DEPOSIT_ADMIN_ROLE

**Helpers: _scale / _unscale**

```solidity
function _scale(uint256 value) public view returns (uint256) {
    return value * _scaleFactor;  // _scaleFactor = 1e12 for 6-decimal base token
}

function _unscale(uint256 value) public view returns (uint256) {
    return value / _scaleFactor;
}
```

---

## Withdraw Functions

### Senior Tranche: redeem(uint256,address,address)

**Contract:** `0x90465aad4e426948A4ea342AC49A1A38200B7017` (proxy)
**Implementation:** `0x4afd9e2b4fbec1f11d09bf2e3d3f82869fa5bc5f`
**Signature:** `redeem(uint256 _shares, address _receiver, address _owner) returns (AssetClaims memory claims)`

```solidity
function redeem(uint256 _shares, address _receiver, address _owner) public virtual override whenNotPaused restricted returns (AssetClaims memory claims) {
    require(_receiver != address(0), ERC20InvalidReceiver(address(0)));
    require(_shares != 0, MUST_REQUEST_NON_ZERO_SHARES());

    // Spend allowance if msg.sender is not the owner
    if (msg.sender != _owner) {
        _spendAllowance(_owner, msg.sender, _shares);
    }

    // Process the withdrawal from the Royco market
    // It is expected that the kernel transfers the assets directly to the receiver
    claims =
    (TRANCHE_TYPE() == TrancheType.SENIOR
            ? IRoycoKernel(KERNEL).stRedeem(_shares, _receiver, false)
            : IRoycoKernel(KERNEL).jtRedeem(_shares, _receiver, false));

    // Burn shares after kernel processes redemption (kernel depends on pre-burn total supply)
    _burn(_owner, _shares);

    emit Redeem(msg.sender, _receiver, claims, _shares);
}
```

**Key observations:**

- Returns `AssetClaims` struct with (stAssets, jtAssets, nav)
- Kernel transfers sUSDai directly to receiver (no intermediate step)
- Burns shares AFTER kernel processes redemption (kernel depends on pre-burn total supply)
- If `msg.sender != _owner`, spends ERC20 allowance

---

### sUSDai: requestRedeem(uint256,address,address)

**Contract:** `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (proxy)
**Implementation:** `0xda8c2f3da2857e9d66f813d11baba555aab46460`
**Signature:** `requestRedeem(uint256 shares, address controller, address owner) returns (uint256 redemptionId)`

```solidity
function requestRedeem(
    uint256 shares,
    address controller,
    address owner
)
    external
    whenNotPaused
    nonReentrant
    nonZeroUint(shares)
    nonZeroAddress(controller)
    nonZeroAddress(owner)
    returns (uint256)
{
    /* Validate address is not blacklisted */
    _isBlacklisted(controller);

    /* Validate caller */
    if (owner != msg.sender && !_getIsOperatorStorage().isOperator[owner][msg.sender]) revert InvalidCaller();

    /* Validate balance */
    if (balanceOf(owner) < shares) revert InsufficientBalance();

    /* Burn sUSDai shares */
    _burn(owner, shares);

    /* Request redeem */
    uint256 redemptionId =
        RedemptionLogic._requestRedeem(_getRedemptionStateStorage(), _genesisTimestamp, shares, controller);

    /* Emit redeem request */
    emit RedeemRequest(controller, owner, redemptionId, msg.sender, shares);

    return redemptionId;
}
```

**Key observations:**

- `whenNotPaused`, `nonReentrant` modifiers
- Burns sUSDai shares immediately
- Delegates to `RedemptionLogic._requestRedeem()` library (enters FIFO queue)
- Returns unique `redemptionId` for tracking this specific redemption
- Blacklist check on controller address
- Operator support: if `owner != msg.sender`, must be registered operator

---

### sUSDai: redeem(uint256,address,address) -- claim serviced redemption

**Contract:** `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (proxy)
**Implementation:** `0xda8c2f3da2857e9d66f813d11baba555aab46460`
**Signature:** `redeem(uint256 shares, address receiver, address controller) returns (uint256 amount)`

```solidity
function redeem(
    uint256 shares,
    address receiver,
    address controller
)
    external
    whenNotPaused
    nonReentrant
    nonZeroUint(shares)
    nonZeroAddress(receiver)
    nonZeroAddress(controller)
    returns (uint256)
{
    /* Validate controller is not blacklisted */
    _isBlacklisted(controller);

    /* Validate caller */
    if (controller != msg.sender && !_getIsOperatorStorage().isOperator[controller][msg.sender]) {
        revert InvalidCaller();
    }

    /* Redeem shares */
    uint256 amount = RedemptionLogic._redeem(_getRedemptionStateStorage(), shares, controller);

    /* Update deposits balance */
    _getDepositsStorage().balance -= amount;

    /* Transfer assets */
    if (amount > 0) IERC20(asset()).safeTransfer(receiver, amount);

    /* Emit Withdraw */
    emit Withdraw(msg.sender, receiver, controller, amount, shares);

    return amount;
}
```

**Key observations:**

- Claims from serviced (redeemable) shares only -- reverts if insufficient redeemable
- Delegates to `RedemptionLogic._redeem()` library
- Transfers USDai (the underlying asset) to receiver
- Operator check is on `controller` (not owner), different from requestRedeem

---

### sUSDai: withdraw(uint256,address,address) -- claim by USDai amount

**Contract:** `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (proxy)
**Implementation:** `0xda8c2f3da2857e9d66f813d11baba555aab46460`
**Signature:** `withdraw(uint256 amount, address receiver, address controller) returns (uint256 shares)`

```solidity
function withdraw(
    uint256 amount,
    address receiver,
    address controller
)
    external
    whenNotPaused
    nonReentrant
    nonZeroUint(amount)
    nonZeroAddress(receiver)
    nonZeroAddress(controller)
    returns (uint256)
{
    /* Validate controller is not blacklisted */
    _isBlacklisted(controller);

    /* Validate caller */
    if (controller != msg.sender && !_getIsOperatorStorage().isOperator[controller][msg.sender]) {
        revert InvalidCaller();
    }

    /* Withdraw amount */
    uint256 shares = RedemptionLogic._withdraw(_getRedemptionStateStorage(), amount, controller);

    /* Update deposits balance */
    _getDepositsStorage().balance -= amount;

    /* Transfer assets */
    IERC20(asset()).safeTransfer(receiver, amount);

    /* Emit Withdraw */
    emit Withdraw(msg.sender, receiver, controller, amount, shares);

    return shares;
}
```

**Key observations:**

- Alternative to `redeem()` -- claims by USDai amount instead of share amount
- Same mechanics as `redeem()` but input/output inverted
- Use `maxWithdraw(controller)` to get available USDai amount

---

### USDai: withdraw(address,uint256,uint256,address)

**Contract:** `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF` (proxy)
**Implementation:** `0x5477072aa366cff31c1c28b81ed783a2a1cf87a2`
**Signature:** `withdraw(address withdrawToken, uint256 usdaiAmount, uint256 withdrawAmountMinimum, address recipient) returns (uint256)`

```solidity
// Entry point (4-arg version, uses empty swap path)
function withdraw(
    address withdrawToken,
    uint256 usdaiAmount,
    uint256 withdrawAmountMinimum,
    address recipient
) external nonReentrant returns (uint256) {
    return _withdraw(withdrawToken, usdaiAmount, withdrawAmountMinimum, recipient, msg.data[0:0]);
}

// Internal implementation (5-arg with custom swap path)
function _withdraw(
    address withdrawToken,
    uint256 usdaiAmount,
    uint256 withdrawAmountMinimum,
    address recipient,
    bytes calldata data
) internal nonZeroUint(usdaiAmount) nonZeroAddress(recipient) returns (uint256) {
    /* Accrue base yield */
    _accrue();

    /* Burn USD.ai tokens */
    _burn(msg.sender, usdaiAmount);

    /* If the withdraw token isn't base token, swap out */
    uint256 withdrawAmount;
    if (withdrawToken != address(_baseToken)) {
        uint256 baseTokenAmount = _unscale(usdaiAmount);

        /* Approve the adapter to spend the token in */
        _baseToken.forceApprove(address(_swapAdapter), baseTokenAmount);

        /* Swap base token input for withdraw token */
        withdrawAmount = _swapAdapter.swapOut(withdrawToken, baseTokenAmount, withdrawAmountMinimum, data);
    } else {
        withdrawAmount = _unscale(usdaiAmount);
    }

    /* Transfer token output from this contract to the recipient address */
    IERC20(withdrawToken).safeTransfer(recipient, withdrawAmount);

    /* Emit withdrawn event */
    emit Withdrawn(msg.sender, recipient, withdrawToken, usdaiAmount, withdrawAmount);

    return withdrawAmount;
}
```

**Key observations:**

- Burns USDai from msg.sender
- When `withdrawToken != _baseToken` (PYUSD), swaps PYUSD -> withdrawToken via `_swapAdapter.swapOut()`
- `withdrawAmountMinimum` provides slippage protection for the PYUSD->USDC swap
- `_unscale(usdaiAmount)` converts 18-decimal USDai to 6-decimal PYUSD
- No whitelist enforcement (unlike NUSD Router)

---

## Admin Functions

### sUSDai: serviceRedemptions(uint256)

**Contract:** `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (proxy)
**Implementation:** `0xda8c2f3da2857e9d66f813d11baba555aab46460`
**Signature:** `serviceRedemptions(uint256 shares) returns (uint256 amountProcessed)`

```solidity
function serviceRedemptions(
    uint256 shares
) external onlyRole(STRATEGY_ADMIN_ROLE) nonZeroUint(shares) returns (uint256) {
    /* Process redemptions */
    (uint256 amountProcessed, bool allRedemptionsServiced) =
        RedemptionLogic._processRedemptions(_getRedemptionStateStorage(), shares, redemptionSharePrice());

    /* Validate amount is available to be serviced */
    if (amountProcessed > _depositBalance()) revert InsufficientBalance();

    /* Update redemption balance */
    _getRedemptionStateStorage().balance += amountProcessed;

    /* Emit RedemptionsServiced */
    emit RedemptionsServiced(shares, amountProcessed, allRedemptionsServiced);

    return amountProcessed;
}
```

**Key observations:**

- `onlyRole(STRATEGY_ADMIN_ROLE)` -- only callable by admin
- Processes shares from the FIFO queue using `redemptionSharePrice()`
- Converts pending shares to redeemable shares with associated USDai amount
- Validates sufficient deposit balance is available
- This is the external process that must run between `requestRedeem()` and `redeem()`

---

## View Functions

### Senior Tranche: convertToAssets(uint256)

**Contract:** `0x90465aad4e426948A4ea342AC49A1A38200B7017`
**Signature:** `convertToAssets(uint256 _shares) returns (AssetClaims memory claims)`

```solidity
function convertToAssets(uint256 _shares) public view virtual override(IRoycoVaultTranche) returns (AssetClaims memory claims) {
    // Get the post-sync tranche state: applying NAV reconciliation.
    (AssetClaims memory trancheClaims, uint256 trancheTotalShares) = _previewPostSyncTrancheState();
    return UtilsLib.scaleAssetClaims(trancheClaims, _shares, trancheTotalShares);
}

// Internal helper
function _previewPostSyncTrancheState() internal view returns (AssetClaims memory trancheClaims, uint256 trancheTotalShares) {
    (, trancheClaims, trancheTotalShares) = IRoycoKernel(KERNEL).previewSyncTrancheAccounting(TRANCHE_TYPE());
}
```

**Key observations:**

- Returns `AssetClaims` struct: `(uint256 stAssets, uint256 jtAssets, uint256 nav)`
- `stAssets` = sUSDai amount claimable (TRANCHE_UNIT, 18 decimals)
- `jtAssets` = always 0 for Senior Tranche
- `nav` = NAV value in USD (18 decimals) -- use this for pricing
- Delegates to Kernel's `previewSyncTrancheAccounting()`

---

### Senior Tranche: maxDeposit(address)

```solidity
function maxDeposit(address _receiver) external view virtual override(IRoycoVaultTranche) returns (TRANCHE_UNIT assets) {
    assets = (TRANCHE_TYPE() == TrancheType.SENIOR ? IRoycoKernel(KERNEL).stMaxDeposit(_receiver) : IRoycoKernel(KERNEL).jtMaxDeposit(_receiver));
}
```

---

### Senior Tranche: previewDeposit(TRANCHE_UNIT)

```solidity
function previewDeposit(TRANCHE_UNIT _assets) external view virtual override(IRoycoVaultTranche) returns (uint256 shares) {
    // Get the state of the tranche before the deposit and the value allocated to the tranche
    (SyncedAccountingState memory stateBeforeDeposit, NAV_UNIT valueAllocated) =
        (TRANCHE_TYPE() == TrancheType.SENIOR ? IRoycoKernel(KERNEL).stPreviewDeposit(_assets) : IRoycoKernel(KERNEL).jtPreviewDeposit(_assets));

    // Preview the total tranche shares after minting any protocol fee shares post-sync
    NAV_UNIT feeAccrued = TRANCHE_TYPE() == TrancheType.SENIOR ? stateBeforeDeposit.stProtocolFeeAccrued : stateBeforeDeposit.jtProtocolFeeAccrued;
    NAV_UNIT effectiveNAV = TRANCHE_TYPE() == TrancheType.SENIOR ? stateBeforeDeposit.stEffectiveNAV : stateBeforeDeposit.jtEffectiveNAV;
    (uint256 feeSharesMinted,) = previewMintProtocolFeeShares(feeAccrued, effectiveNAV);

    // Calculate the shares to be minted to the receiver, considering the protocol fee shares
    shares = _convertToShares(valueAllocated, feeSharesMinted + totalSupply(), effectiveNAV, Math.Rounding.Floor);
}
```

---

### Senior Tranche: previewRedeem(uint256)

```solidity
function previewRedeem(uint256 _shares) external view virtual override(IRoycoVaultTranche) returns (AssetClaims memory claims) {
    claims = (TRANCHE_TYPE() == TrancheType.SENIOR ? IRoycoKernel(KERNEL).stPreviewRedeem(_shares) : IRoycoKernel(KERNEL).jtPreviewRedeem(_shares));
}
```

---

### sUSDai: convertToAssets(uint256)

```solidity
function convertToAssets(uint256 shares) public view returns (uint256) {
    /* Check if initial deposit */
    bool initialDeposit = totalSupply() < LOCKED_SHARES;

    /* Compute assets. If initial deposit, price locked shares */
    return ((((initialDeposit ? LOCKED_SHARES : 0) + shares) * depositSharePrice()) + FIXED_POINT_SCALE - 1)
        / FIXED_POINT_SCALE;
}
```

**Key observations:**

- Uses `depositSharePrice()` (OPTIMISTIC valuation) for conversion
- Rounds up (ceiling division via `+ FIXED_POINT_SCALE - 1`)
- FIXED_POINT_SCALE = 1e18

---

### sUSDai: previewDeposit(uint256)

```solidity
function previewDeposit(uint256 assets) external view returns (uint256) {
    return convertToShares(assets);
}

// Helper
function convertToShares(uint256 assets) public view returns (uint256) {
    bool initialDeposit = totalSupply() < LOCKED_SHARES;
    return ((assets * FIXED_POINT_SCALE) / depositSharePrice()) - (initialDeposit ? LOCKED_SHARES : 0);
}
```

---

### sUSDai: depositSharePrice() / redemptionSharePrice()

```solidity
function depositSharePrice() public view returns (uint256) {
    return _sharePrice(ValuationType.OPTIMISTIC);
}

function redemptionSharePrice() public view returns (uint256) {
    return _sharePrice(ValuationType.CONSERVATIVE);
}

// Internal
function _sharePrice(ValuationType valuationType) internal view returns (uint256) {
    return totalShares() == 0 ? FIXED_POINT_SCALE : (_assets(valuationType) * FIXED_POINT_SCALE) / totalShares();
}

function totalShares() public view returns (uint256) {
    return totalSupply() + bridgedSupply() + _getRedemptionStateStorage().pending;
}
```

**Key observations:**

- Two separate share prices: OPTIMISTIC (deposits) and CONSERVATIVE (redemptions)
- `totalShares()` includes pending redemption shares in the denominator
- `_assets()` aggregates BasePositionManager, LoanRouterPositionManager, and deposit balance

---

### sUSDai: pendingRedeemRequest / claimableRedeemRequest

```solidity
function pendingRedeemRequest(uint256 redemptionId, address controller) external view returns (uint256) {
    Redemption storage redemption_ = _getRedemptionStateStorage().redemptions[redemptionId];
    if (redemption_.controller != controller) return 0;
    return redemption_.pendingShares;
}

function claimableRedeemRequest(uint256 redemptionId, address controller) external view returns (uint256) {
    Redemption storage redemption_ = _getRedemptionStateStorage().redemptions[redemptionId];
    if (redemption_.controller != controller) return 0;
    return redemption_.redeemableShares;
}
```

---

### sUSDai: redemptionIds / redemption

```solidity
function redemptionIds(address controller) external view nonZeroAddress(controller) returns (uint256[] memory) {
    return _getRedemptionStateStorage().redemptionIds[controller].values();
}

function redemption(uint256 redemptionId) external view returns (Redemption memory, uint256) {
    return RedemptionLogic._redemption(_getRedemptionStateStorage(), redemptionId);
}
```

**Key observations:**

- `redemptionIds()` returns array of all active redemption IDs for a controller
- `redemption()` returns full struct: (prev, next, pendingShares, redeemableShares, withdrawableAmount, controller, redemptionTimestamp) + index

---

### sUSDai: maxRedeem / maxWithdraw

```solidity
function maxRedeem(address controller) external view returns (uint256) {
    (, uint256 shares) = RedemptionLogic._redemptionAvailable(_getRedemptionStateStorage(), controller);
    return shares;
}

function maxWithdraw(address controller) external view returns (uint256) {
    (uint256 amount,) = RedemptionLogic._redemptionAvailable(_getRedemptionStateStorage(), controller);
    return amount;
}
```

**Key observations:**

- `maxRedeem()` returns total redeemable shares across ALL redemptions for controller
- `maxWithdraw()` returns total withdrawable USDai amount across ALL redemptions
- Both delegate to `RedemptionLogic._redemptionAvailable()`

---

### sUSDai: redemptionQueueInfo()

```solidity
function redemptionQueueInfo()
    external
    view
    returns (uint256 index, uint256 head, uint256 tail, uint256 pending, uint256 balance)
{
    return (
        _getRedemptionStateStorage().index,
        _getRedemptionStateStorage().head,
        _getRedemptionStateStorage().tail,
        _getRedemptionStateStorage().pending,
        _getRedemptionStateStorage().balance
    );
}
```

**Key observations:**

- `pending` = total shares still awaiting servicing
- `balance` = total USDai reserved for serviced redemptions
- `head`/`tail` = FIFO linked list pointers
- `index` = next redemption ID counter

---

### USDai: isBlacklisted(address)

```solidity
function isBlacklisted(address account) public view returns (bool) {
    /* Check local blacklist */
    if (_getBlacklistStorage().blacklist[account]) return true;

    /* If not on Arbitrum, skip remaining checks */
    if (block.chainid != 42161) return false;

    /* Exclude Staked USDai and OUSDaiUtility */
    if (
        account == 0x0B2b2B2076d95dda7817e785989fE353fe955ef9
            || account == 0x24a92E28a8C5D8812DcfAf44bCb20CC0BaBd1392
    ) return false;

    /* Check USDC and USDT blacklists */
    return IBlacklist(0xaf88d065e77c8cC2239327C5EDb3A432268e5831).isBlacklisted(account)
        || IBlacklist(0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9).isBlocked(account);
}
```

**Key observations:**

- Checks local blacklist first
- On Arbitrum (chain 42161), also checks USDC and USDT blacklists
- sUSDai (0x0B2b...) and OUSDaiUtility (0x24a9...) are explicitly excluded
- USDC uses `isBlacklisted()`, USDT uses `isBlocked()` (different interface names)

---

## Kernel Conversion Functions

### Kernel: getTrancheUnitToNAVUnitConversionRateWAD()

**Contract:** `0xFdb17E53eA5d342124b8473188BCB9F05F1949CA` (proxy)
**Implementation:** `0x8c87ac66d7970f557c742357eaa26cacb9130dda`
**Signature:** `getTrancheUnitToNAVUnitConversionRateWAD() returns (uint256 sUSDaiToUSDConversionRateWAD)`

```solidity
function getTrancheUnitToNAVUnitConversionRateWAD() public view override(IdenticalAssetsOracleQuoter) returns (uint256 sUSDaiToUSDConversionRateWAD) {
    // Fetch the conversion rate from one sUSDai to USDai
    // NOTE: The output is already scaled to WAD precision since USDai has 18 decimals of precision
    uint256 sUSDaiToUSDaiConversionRateWAD = IStakedUSDai(ST_ASSET).redemptionSharePrice();

    // Fetch the USDai to USD conversion rate from the admin set oracle, scaled to WAD precision
    uint256 usdaiToUSDConversionRateWAD = getStoredConversionRateWAD();

    // Calculate the conversion rate from sUSDai to USD, scaled to WAD precision
    sUSDaiToUSDConversionRateWAD = sUSDaiToUSDaiConversionRateWAD.mulDiv(usdaiToUSDConversionRateWAD, WAD, Math.Rounding.Floor);
}
```

**Key observations:**

- Combines two rates: sUSDai->USDai (from sUSDai.redemptionSharePrice()) and USDai->USD (admin-set oracle)
- Uses CONSERVATIVE valuation (redemptionSharePrice, not depositSharePrice)
- Current rate: ~1.077e18 (1 sUSDai ~ 1.077 USD)
- WAD = 1e18

---

### Kernel: getStoredConversionRateWAD()

```solidity
function getStoredConversionRateWAD() public view returns (uint256) {
    return _getIdenticalAssetsOracleQuoterStorage().conversionRateWAD;
}
```

**Key observations:**

- Admin-set oracle for USDai:USD rate
- Currently 1e18 (1:1 peg)

---

### Kernel: _convertTrancheUnitsToNAVUnits(TRANCHE_UNIT) (internal)

```solidity
function _convertTrancheUnitsToNAVUnits(TRANCHE_UNIT _assets) internal view returns (NAV_UNIT) {
    return toNAVUnits(toUint256(_assets.mulDiv(_getCachedTrancheUnitToNAVUnitConversionRateWAD(), TRANCHE_UNIT_SCALE_FACTOR, Math.Rounding.Floor)));
}
```

**Key observations:**

- Uses cached conversion rate (not live) for gas efficiency
- `TRANCHE_UNIT_SCALE_FACTOR` = WAD (1e18) since sUSDai is 18 decimals

---

### Kernel: syncTrancheAccounting / stConvertTrancheUnitsToNAVUnits / stDeposit / stRedeem

**Status:** Interface signatures only -- implementation is in the Kernel's complex inheritance hierarchy (RoycoKernel inherits from multiple base contracts). The Etherscan source code for the implementation contract returns interface definitions from `IRoycoKernel.sol` for these functions.

**Interface signatures:**

```solidity
function syncTrancheAccounting() external returns (SyncedAccountingState memory state);

function stConvertTrancheUnitsToNAVUnits(TRANCHE_UNIT _stAssets) external view returns (NAV_UNIT nav);

function stDeposit(TRANCHE_UNIT _assets) external returns (NAV_UNIT valueAllocated, NAV_UNIT navToMintSharesAt);

function stRedeem(uint256 _shares, address _receiver, bool _bypassRedemptionRestrictions) external returns (AssetClaims memory userAssetClaims);

function previewSyncTrancheAccounting(TrancheType _trancheType) external view returns (SyncedAccountingState memory state, AssetClaims memory claims, uint256 totalTrancheShares);
```

**Note:** The actual implementations are in the Kernel's base contracts which compile into a single flattened contract. The key behavior is documented via the interface NatSpec comments and the calling patterns in the Senior Tranche functions above.

---

## Library Delegations

### RedemptionLogic (sUSDai)

The sUSDai contract delegates redemption queue operations to the `RedemptionLogic` library:

| sUSDai Function             | Library Call                                                                    |
| --------------------------- | ------------------------------------------------------------------------------- |
| requestRedeem()             | `RedemptionLogic._requestRedeem(storage, genesisTimestamp, shares, controller)` |
| redeem()                    | `RedemptionLogic._redeem(storage, shares, controller)`                          |
| withdraw()                  | `RedemptionLogic._withdraw(storage, amount, controller)`                        |
| maxRedeem() / maxWithdraw() | `RedemptionLogic._redemptionAvailable(storage, controller)`                     |
| redemption()                | `RedemptionLogic._redemption(storage, redemptionId)`                            |
| serviceRedemptions()        | `RedemptionLogic._processRedemptions(storage, shares, sharePrice)`              |

**Note:** The RedemptionLogic library source code is not directly fetchable from the implementation contract. The library manages a FIFO linked list of redemption requests with (pendingShares, redeemableShares, withdrawableAmount) per entry.

### UtilsLib (Senior Tranche)

The Senior Tranche uses `UtilsLib.scaleAssetClaims()` for proportional scaling in `convertToAssets()`.

---

## Key Struct Definitions

### AssetClaims (Royco Kernel/Tranche)

```
struct AssetClaims {
    TRANCHE_UNIT stAssets;   // sUSDai amount from Senior Tranche (18 decimals)
    TRANCHE_UNIT jtAssets;   // sUSDai amount from Junior Tranche (0 for ST users)
    NAV_UNIT nav;            // NAV value in USD (18 decimals)
}
```

### Redemption (sUSDai)

```
struct Redemption {
    uint256 prev;              // Previous redemption ID in linked list
    uint256 next;              // Next redemption ID in linked list
    uint256 pendingShares;     // Shares awaiting servicing
    uint256 redeemableShares;  // Shares serviced, available to claim
    uint256 withdrawableAmount; // USDai amount available to withdraw
    address controller;        // Controller address
    uint256 redemptionTimestamp; // When the next service batch occurs
}
```

---

## Functions Not Found on Etherscan

| Function                         | Contract          | Reason                                    |
| -------------------------------- | ----------------- | ----------------------------------------- |
| previewDeposit(address,uint256)  | USDai (0x5477...) | Function does not exist in implementation |
| previewWithdraw(address,uint256) | USDai (0x5477...) | Function does not exist in implementation |

**Note:** USDai does not have preview functions. To estimate output, use `_scale(depositAmount)` for same-token deposits, or query the Uniswap V3 pool for swap quotes when depositing non-base tokens (USDC).
