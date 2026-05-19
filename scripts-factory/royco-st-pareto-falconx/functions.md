# Royco Senior Tranche - Pareto FalconX - Function Implementations

Chain: ethereum mainnet (chainId 1)
Generated: 2026-04-30T12:58:00Z

## Overview

This integration spans 4 contract families. Solidity sources were resolved as follows:

| Layer                                | Proxy                                        | Implementation                                                                                                     | Verified                                                                                    | Source                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------------------------------ | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pareto IdleCDOEpochVariant           | `0x433D5B175148dA32Ffe1e1A37a939E1b7e79be4d` | `0x8016E6f35a4B32a5Ea4c3919418039C7DaffCcaf`                                                                       | YES                                                                                         | Blockscout/Sourcify (full, exact match), Solidity 0.8.10                                                                                                                                                                                                                                                                                                                                        |
| Pareto IdleCreditVault (FalconXUSDC) | `0x17E9Ab2992dfecBe779a06A92a6cDB9fE6aEeEf3` | (deployed via the same Pareto repo, Solidity 0.8.10)                                                               | YES (by analogy via the IdleCDOEpochVariant verified bundle)                                | Same Pareto bundle: `contracts/strategies/idle/IdleCreditVault.sol`                                                                                                                                                                                                                                                                                                                             |
| Pareto KeyringIdleWhitelist          | `0x6a6a91c7c7c05f9f6b8bc9f6e5ea231e460450e3` | (non-proxy)                                                                                                        | YES                                                                                         | Blockscout (full match), Solidity 0.8.10                                                                                                                                                                                                                                                                                                                                                        |
| Royco Senior Tranche (this market)   | `0x694ADB3077BBecE31882B6d6A74fc4A4fA6a754b` | `0x98dF5263392C83dD739d8959A6bACf01EA034bba`                                                                       | UNVERIFIED on Etherscan, **VERIFIED on Sourcify (partial match)**, Solidity 0.8.34 (Prague) | Sourcify partial match — files: `RoycoSeniorTranche.sol`, `RoycoVaultTranche.sol`, `AccessManagedUpgradeable.sol`. Behaviour identical to the stcUSD/syrupUSDC ST family per `nav-investigation.md`.                                                                                                                                                                                            |
| Royco Kernel (this market)           | `0x15bb63C07740ff972F76716cAcC5766f0C641791` | `0xAA9631dF7ec04AbB825bD6a663f96c9BB3Ed7e1e` (and accountant subimpl `0x288bc6a8600d0bc1f179816c3b3001b00566c110`) | NOT verified on Sourcify or Etherscan                                                       | Recovered by analogy from a sibling Royco kernel impl `0xeb7c3a4a72b4c201e50add11003ada2566d276ea` (verified on Sourcify, contract name `Identical_ERC4626_ST_JT_SharePriceToChainlinkOracle_Kernel`, base `RoycoKernel.sol`). The Pareto kernel is the same `RoycoKernel` base + a different oracle quoter; the deposit/redeem dispatch and coverage-enforcement logic are inherited verbatim. |
| RoycoFactory (AccessManager)         | `0x7cC6fB28eC7b5e7afC3cB3986141797ffc27253C` | `0x34DB2f4215e55ec8e2c3dE0a826935EBF158be77`                                                                       | **VERIFIED on Sourcify (partial match)**, Solidity 0.8.34                                   | Sourcify partial match — `RoycoFactory.sol`, OpenZeppelin `AccessManagerUpgradeable.sol` (v5.4.0).                                                                                                                                                                                                                                                                                              |

> **Spec cross-reference.** Storage slots and access-control facts cited below are already documented in `specs.yaml` (sections `contracts.*.state_at_spec_time`, `access_control`, `pause_state`). The execution-explorer / blueprint-writer should NOT re-derive them — they are reproduced inline here only where the corresponding Solidity branch is shown.

| Function                                                                   | Contract                                              | Type                                                |
| -------------------------------------------------------------------------- | ----------------------------------------------------- | --------------------------------------------------- |
| `depositAA(uint256)`                                                       | IdleCDOEpochVariant (parent `IdleCDOCreditVault`)     | Sync deposit (between epochs)                       |
| `depositDuringEpoch(uint256,address)`                                      | IdleCDOEpochVariant                                   | Mid-epoch deposit                                   |
| `requestWithdraw(uint256,address)`                                         | IdleCDOEpochVariant                                   | Queued withdraw entry                               |
| `claimWithdrawRequest()`                                                   | IdleCDOEpochVariant -> IdleCreditVault                | Queued payout (NOT keyring-gated)                   |
| `tranchePrice(address)`                                                    | IdleCDOEpochVariant (parent)                          | View — used by accounting                           |
| `isEpochRunning() / isDepositDuringEpochDisabled() / epochEndDate()`       | IdleCDOEpochVariant (auto-getters)                    | View — epoch state for blueprint dispatch           |
| `isWalletAllowed(address)` -> `KeyringIdleWhitelist.checkCredential`       | IdleCDOEpochVariant + Keyring                         | KYC gate (mockable storage surface)                 |
| `RoycoSeniorTranche.deposit(uint256,address)`                              | RoycoSeniorTranche (impl `0x98dF…4bba`)               | Mints ST shares                                     |
| `RoycoSeniorTranche.redeem(uint256,address,address)`                       | RoycoSeniorTranche                                    | Burns ST, returns `AssetClaims` (3-tuple)           |
| `RoycoSeniorTranche.convertToAssets(uint256)`                              | RoycoSeniorTranche                                    | Returns `(stAssets, jtAssets, nav)`                 |
| `RoycoKernel.syncTrancheAccounting()`                                      | RoycoKernel                                           | Idempotent? See section below                       |
| `RoycoAccountant.postOpSyncTrancheAccountingAndEnforceCoverage(...)`       | RoycoAccountant (subimpl)                             | Coverage gate that reverts when `jtRawNAV == 0`     |
| `RoycoFactory.canCall(address,address,bytes4)` / `hasRole(uint64,address)` | RoycoFactory (`AccessManagerUpgradeable`)             | Authority check used by every `restricted` modifier |
| `_checkCanCall(address,bytes calldata)`                                    | OZ `AccessManagedUpgradeable` (used by ST and Kernel) | The actual call gate                                |

---

## 1. Pareto IdleCDOEpochVariant

Address: proxy `0x433D5B175148dA32Ffe1e1A37a939E1b7e79be4d`, impl `0x8016E6f35a4B32a5Ea4c3919418039C7DaffCcaf` — **verified, exact match**, Solidity 0.8.10. Source bundle: `contracts/IdleCDOEpochVariant.sol` (extends `IdleCDOCreditVault`).

### `depositAA(uint256)` — sync deposit between epochs

> Why the blueprint cares: this is path A in `flows.deposit`. It is `whenNotPaused` (the contract pauses itself **whenever an epoch is running** — see `startEpoch` setting `_pause()`), so the blueprint must branch on `isEpochRunning()` and only call this when `isEpochRunning == false` AND `paused == false`. Mints AA tranche tokens 1:1 in tranche-units against the current AA `tranchePrice`.

Inherited from parent `IdleCDOCreditVault`:

```solidity
// contracts/IdleCDOCreditVault.sol
function depositAA(uint256 _amount) external returns (uint256) {
    return _deposit(_amount, AATranche);
}

function _deposit(uint256 _amount, address _tranche)
    internal virtual
    whenNotPaused
    returns (uint256 _minted)
{
    if (_amount == 0) {
        return _minted;
    }
    _guarded(_amount);          // GuardedLaunch limit check
    _updateAccounting();        // re-prices AA / BB based on accrued PnL
    address _token = token;
    uint256 _preBal = _contractTokenBalance(_token);
    _transferUnderlyingsFrom(msg.sender, address(this), _amount);
    _minted = _mintSharesAtCurrPrice(
        _contractTokenBalance(_token) - _preBal, msg.sender, _tranche
    );
    _updateSplitRatio(_getAARatio(true));
    if (directDeposit) {
        IIdleCDOStrategy(strategy).deposit(_amount);
    }
}
```

The IdleCDOEpochVariant child overrides `_deposit` to add the Keyring gate:

```solidity
// contracts/IdleCDOEpochVariant.sol
function _deposit(uint256 _amount, address _tranche)
    internal override
    whenNotPaused
    returns (uint256)
{
    _checkNotAllowed(!isWalletAllowed(msg.sender));   // <-- Keyring gate
    _skimDonatedAssets();
    return super._deposit(_amount, _tranche);
}
```

`_mintSharesAtCurrPrice` is the leaf that determines mint amount:

```solidity
function _mintSharesAtCurrPrice(uint256 _amount, address _to, address _tranche)
    internal virtual
    returns (uint256 _minted)
{
    _minted = _amount * ONE_TRANCHE_TOKEN / _tranchePrice(_tranche);
    _mintShares(_tranche, _to, _minted, _amount);
}
```

Note: `tranchePrice(AA)` is what the Royco kernel reads for accounting and is also the divisor here, so the AA shares minted ≈ `usdcAmount * 1e18 / tranchePriceAA`. With `tranchePrice_AA = 1_074_982` (USDC 6-dec, see `specs.yaml.contracts.pareto_credit_vault.state_at_spec_time.tranchePrice_AA`), `1 USDC` mints `~0.93 AA`.

### `depositDuringEpoch(uint256,address)` — path B (mid-epoch)

> Why the blueprint cares: this is the **only** way to deposit while `paused == true` (i.e. while `isEpochRunning == true`). It re-implements the inherited `_deposit` flow and _bypasses_ `whenNotPaused`. It mints _fewer_ shares than `depositAA` because it discounts the late depositor's principal by the prorated remaining-epoch interest. The big preconditions to check: `isDepositDuringEpochDisabled == false`, AYS off, `block.timestamp < epochEndDate`, AA tranche has nonzero supply, `isWalletAllowed(msg.sender)`.

```solidity
function depositDuringEpoch(uint256 _amount, address _tranche)
    external
    returns (uint256 _minted)
{
    _checkNotAllowed(
        isDepositDuringEpochDisabled ||
        isAYSActive ||
        !isEpochRunning || block.timestamp >= epochEndDate ||
        !(_tranche == AATranche || _tranche == BBTranche) ||
        !isWalletAllowed(msg.sender)             // <-- Keyring gate
    );

    if (_amount == 0) {
        return _minted;
    }

    uint256 _trancheTotSupply = _trancheSupply(_tranche);
    _checkNotAllowed(_trancheTotSupply == 0);    // first mid-epoch deposit must seed in sync

    _guarded(_amount);
    _skimDonatedAssets();
    _transferUnderlyingsFrom(msg.sender, address(this), _amount);

    // Prorate the remaining-epoch interest the depositor will earn:
    //   interest = _calcInterest(_amount) * (epochEndDate - now + buffer) / (epochDuration + buffer)
    uint256 buffer = bufferPeriod;
    uint256 interest = _calcInterest(_amount) *
        (epochEndDate - block.timestamp + buffer) /
        (epochDuration + buffer);

    uint256 feeComplement = FULL_ALLOC - fee;
    uint256 expectedInt  = expectedEpochInterest;
    uint256 pendingFees  = pendingWithdrawFees;
    uint256 trancheExpected;
    if (expectedInt > pendingFees) {
        trancheExpected = _calcTrancheInterestShare(
            (expectedInt - pendingFees) * feeComplement / FULL_ALLOC, _tranche);
    }
    uint256 trancheInterest = _calcTrancheInterestShare(
        interest * feeComplement / FULL_ALLOC, _tranche);
    uint256 expectedFinal   = _lastSavedNAV(_tranche) + trancheExpected;

    // Discounted mint:
    //   minted = (amount + trancheInterest) * trancheTotSupply / expectedFinal
    _minted = (_amount + trancheInterest) * _trancheTotSupply / expectedFinal;
    _mintShares(_tranche, msg.sender, _minted, _amount);

    expectedEpochInterest += interest;
    IdleCreditVault(strategy).mintStrategyTokens(_amount);
    _transferUnderlyings(_borrower(), _amount);    // funds go straight to borrower
    _updateSplitRatio(_getAARatio(true));
}
```

> Blueprint impact:
>
> - The exact AA amount minted is **non-trivial**. The blueprint MUST sandwich `AA.balanceOf(caliber)` rather than try to predict `_minted`.
> - `_amount` flows: USDC enters the CDO contract, then immediately leaves to the borrower (`_transferUnderlyings(_borrower(), _amount)`) — strategy tokens are minted to the CDO instead. So a `Transfer` event sequence per `flows.deposit.events_to_monitor` will see `USDC: caliber -> CDO -> borrower`.

### `requestWithdraw(uint256,address)` — queued withdraw entry

> Why the blueprint cares: this is Phase 1 of `flows.withdraw`. It is **not** `whenNotPaused`, but it requires `allowAAWithdrawRequest == true`, which the contract sets to `false` whenever `startEpoch` is called and back to `true` on `stopEpoch`. So Phase 1 is only callable **between epochs** (i.e. `isEpochRunning == false`).
>
> It (a) burns AA tranche tokens **immediately** by calling `_withdrawOps`, and (b) mints a `FalconXUSDC` receipt to `msg.sender` via `IdleCreditVault.requestWithdraw`. The receipt is the principal-plus-next-epoch-net-interest USDC that will be claimable after the next `stopEpoch`.

```solidity
function requestWithdraw(uint256 _amount, address _tranche) external returns (uint256) {
    address aa = AATranche;
    address bb = BBTranche;
    _checkNotAllowed(!(_tranche == aa || _tranche == bb) ||
        (!allowAAWithdrawRequest && _tranche == aa) ||
        (!allowBBWithdrawRequest && _tranche == bb) ||
        (!keyringAllowWithdraw && !isWalletAllowed(msg.sender))   // <-- Keyring gate (skippable if keyringAllowWithdraw)
    );

    _skimDonatedAssets();
    _updateAccounting();

    IdleCreditVault creditVault = IdleCreditVault(strategy);
    uint256 _underlyings = _trancheToUnderlyings(_amount, _tranche);
    uint256 _userTrancheTokens = _userTrancheBal(msg.sender, _tranche);

    if (!disableInstantWithdraw) {
        if (lastEpochApr > (creditVault.unscaledApr() + instantWithdrawAprDelta)) {
            // INSTANT path - taken only if APR dropped enough. With disableInstantWithdraw == true
            // (the spec-time configuration), this branch is dead.
            _underlyings = _amount == 0
                ? _trancheToUnderlyings(_userTrancheBal(msg.sender, _tranche), _tranche)
                : _underlyings;
            creditVault.requestInstantWithdraw(_underlyings, msg.sender);
            if (_amount == 0) { _amount = _userTrancheTokens; }
            _withdrawOps(_amount, _underlyings, _tranche);
            return _underlyings;
        }
    }

    // NORMAL queued path:
    if (_amount == 0) {
        _underlyings = _trancheToUnderlyings(_userTrancheTokens, _tranche);
        _amount = _userTrancheTokens;
    }

    (uint256 interest, int256 diff) = _calcInterestWithdrawRequest(_underlyings, _tranche);
    uint256 fees       = interest * fee / FULL_ALLOC;
    uint256 netInterest = interest - fees;
    _underlyings += netInterest;                         // user owed = principal + next-epoch net interest
    pendingWithdrawFees += fees;
    interestForOverUnderPerformance += diff;

    // Burns strategyTokens from CDO and mints `FalconXUSDC` (1:1 USDC) receipt to msg.sender:
    creditVault.requestWithdraw(_underlyings, msg.sender, netInterest);
    // Burns AA tranche tokens from msg.sender and decreases lastNAVAA:
    _withdrawOps(_amount, _underlyings - netInterest, _tranche);
    return _underlyings;
}
```

`_withdrawOps`:

```solidity
function _withdrawOps(uint256 _amount, uint256 _underlyings, address _tranche) internal {
    IdleCDOTranche(_tranche).burn(msg.sender, _amount);   // <-- AA burn comes from msg.sender
    if (_tranche == AATranche) lastNAVAA -= _underlyings; else lastNAVBB -= _underlyings;
    _updateSplitRatio(_getAARatio(true));
}
```

The `IdleCreditVault.requestWithdraw` body that mints the receipt:

```solidity
// contracts/strategies/idle/IdleCreditVault.sol  -> IdleCreditVault
function requestWithdraw(uint256 _amount, address _user, uint256 _netInterest) external {
    _onlyIdleCDO();
    if (_amount == 0) return;
    // burn strategy tokens from cdo (we don't burn interest here, only the principal)
    _burn(msg.sender, _amount - _netInterest);
    // mint equal amount of strategy tokens to the user as receipt (interest included)
    _mint(_user, _amount);                       // <-- caliber receives FalconXUSDC (6 dec, == USDC owed)
    pendingWithdraws += _amount;
    lastWithdrawRequest[_user] = epochNumber;
    if (_netInterest == 0 && unscaledApr == 0) { _requestWithdrawApr0(_amount, _user); return; }
    withdrawsRequests[_user] += _amount;
}
```

### `claimWithdrawRequest()` — payout, NOT keyring-gated

> Why the blueprint cares: this is Phase 2 of `flows.withdraw`. The IdleCDOEpochVariant entry is a thin wrapper that calls into the strategy's `claimWithdrawRequest(msg.sender)` — it does **not** pass `msg.sender` through `isWalletAllowed`, and it does NOT take an amount argument: the caliber claims its **entire** outstanding `withdrawsRequests[caliber]` in a single call.
>
> Confirms `access_control.pareto.notes`: "claimWithdrawRequest() is NOT keyring-checked". This is the key reason the caliber can be safely de-listed from Keyring after Phase 1.

```solidity
// IdleCDOEpochVariant.sol
function claimWithdrawRequest() external {
    IdleCreditVault(strategy).claimWithdrawRequest(msg.sender);
}
```

```solidity
// IdleCreditVault.sol
function claimWithdrawRequest(address _user) external returns (uint256 amount) {
    _onlyIdleCDO();   // <-- only the CDO can call here, but msg.sender of the *outer* call propagates as _user
    // Must wait at least one epoch (incremented in stopEpoch via deposit() side-effect):
    if (IIdleCDOEpochVariant(idleCDO).epochEndDate() != 0
        && (epochNumber <= lastWithdrawRequest[_user])) {
        revert NotAllowed();
    }
    _settleApr0(_user);
    Apr0UserData storage _apr0User = apr0Users[_user];
    uint256 normalAmount = withdrawsRequests[_user];
    uint256 apr0PrincipalAmount = _apr0User.settledPrincipal + _apr0User.principal;
    uint256 apr0InterestAmount  = _apr0User.settledInterest;
    amount = normalAmount + apr0PrincipalAmount + apr0InterestAmount;
    _burn(_user, normalAmount + apr0PrincipalAmount);  // burn FalconXUSDC receipt
    withdrawsRequests[_user] = 0;
    lastWithdrawRequest[_user] = 0;
    if (apr0PrincipalAmount != 0 || apr0InterestAmount != 0) { delete apr0Users[_user]; }
    underlyingToken.safeTransfer(_user, amount);       // <-- USDC flows out
}
```

> Blueprint timing: the `epochNumber` only increments inside `IdleCreditVault.deposit(...)` which is called by `stopEpoch`'s `_strategy.deposit(...)`. So `claimWithdrawRequest` reverts with `NotAllowed()` until at least one full `stopEpoch` has run after Phase 1. Per spec, this is up to ~37 days end-to-end.

### `tranchePrice(address)` — accounting view (used by Royco kernel and by the asset-space accounting path)

```solidity
// IdleCDOCreditVault.sol
function tranchePrice(address _tranche) external view returns (uint256) {
    return _tranchePrice(_tranche);
}

function _tranchePrice(address _tranche) internal view returns (uint256) {
    if (_trancheSupply(_tranche) == 0) {
        return oneToken;            // <-- 1e6 for USDC; "virtual" price before any tranche supply
    }
    return _tranche == AATranche ? priceAA : priceBB;
}
```

> Important denomination note (cross-references `flows.accounting`): `tranchePrice` returns USDC 6-dec **per 1e18 AA shares**. The blueprint's `usdc_value = aaUnits * tranchePrice / 1e18` is correct.

### Epoch-state views — exposed as Solidity public-state-variable getters

There are no hand-written getter bodies for these — they are auto-generated from the `public` storage declarations in `IdleCDOEpochVariant.sol`:

```solidity
bool    public isEpochRunning;
bool    public isDepositDuringEpochDisabled;
uint256 public epochEndDate;
bool    public allowAAWithdrawRequest;
bool    public defaulted;
bool    public allowInstantWithdraw;
bool    public disableInstantWithdraw;
uint256 public bufferPeriod;
uint256 public epochDuration;
```

> Tenderly mocking surface: these are sequential storage slots beginning at slot 0 of the IdleCDOEpochVariant child contract (after the parent storage layout). For an end-to-end test that needs to _force_ `isEpochRunning == false`, the explorer should call `tenderly_setStorageAt` on the proxy directly — but be warned that `_pause()` from `startEpoch` sets the OZ Pausable storage slot, so you must **also** flip that slot, or re-call `_unpause()` via the manager. (Manager / owner addresses are queryable via `IdleCreditVault(strategy).manager()` and `Ownable.owner()`.)

### `isWalletAllowed(address)` — Keyring gate

```solidity
// IdleCDOEpochVariant.sol
function isWalletAllowed(address _user) public view returns (bool) {
    address _keyring = keyring;
    return _keyring == address(0) || IKeyring(_keyring).checkCredential(keyringPolicyId, _user);
}
```

The Keyring contract at `0x6a6a91c7c7c05f9f6b8bc9f6e5ea231e460450e3` is in fact the `KeyringIdleWhitelist` shim, NOT a raw Keyring credential cache. Source verified:

```solidity
// contracts/KeyringIdleWhitelist.sol
contract KeyringIdleWhitelist {
    address public keyring;                       // 0xb0B5E2176E10B12d70e60E3a68738298A7DFe666 (real Keyring)
    address public admin;                         // 0xFb3bD022D5DAcF95eE28a6B07825D4Ff9C5b3814 (Pareto treasury)
    mapping(address => bool) public whitelist;    // <-- THIS is the cheap mocking surface

    function checkCredential(uint256 policyId, address entity) external view returns(bool) {
        return whitelist[entity] || Keyring(keyring).checkCredential(policyId, entity);
    }

    function setWhitelistStatus(address entity, bool status) external {
        if (msg.sender != admin) revert NotAdmin(msg.sender);
        ...
        whitelist[entity] = status;
        emit Whitelist(entity, status);
    }
}
```

> Blueprint / tester note (mockable surface): `whitelist` lives at storage slot `2` of `KeyringIdleWhitelist` (slot 0 = `keyring`, slot 1 = `admin`, slot 2 = `whitelist`). For the Tenderly bypass, write `keccak256(abi.encode(caliber, uint256(2)))` -> `1` and `checkCredential(18, caliber)` will return true without any external call to the real Keyring. This is materially cheaper than impersonating the admin and calling `setWhitelistStatus`.

---

## 2. Pareto IdleCreditVault (FalconXUSDC) — `0x17E9Ab2992dfecBe779a06A92a6cDB9fE6aEeEf3`

`balanceOf(caliber)` is the standard `ERC20Upgradeable.balanceOf` (no override). The mint/burn hooks live on this contract but are exclusively called by the IdleCDOEpochVariant — that gating is `_onlyIdleCDO()`:

```solidity
function _onlyIdleCDO() internal view {
    if (msg.sender != idleCDO) {
        revert NotAllowed();
    }
}
```

Mint paths (used by the IdleCDOEpochVariant and surfaced to the caliber as `FalconXUSDC.Transfer(0x0, caliber, x)` events):

```solidity
function requestWithdraw(uint256 _amount, address _user, uint256 _netInterest) external { /* mints to _user — see IdleCDOEpochVariant section above */ }
function requestInstantWithdraw(uint256 _amount, address _user) external                  { /* mints to _user, instant path */ }
```

Burn paths (used during Phase 2 claim and during stopEpoch):

```solidity
function claimWithdrawRequest(address _user) external returns (uint256 amount) { /* burns from _user, transfers USDC */ }
function claimInstantWithdrawRequest(address _user) external                   { /* burns from _user, transfers USDC */ }
function burnStrategyTokens(uint256 _amount) external                          { _onlyIdleCDO(); _burn(msg.sender, _amount); }
function _transfer(address sender, address recipient, uint256 amount) internal virtual override {
    if (msg.sender != idleCDO && !canTransfer) { revert NotAllowed(); }
    super._transfer(sender, recipient, amount);
}
```

> **Critical for accounting**: `_transfer` is **disabled** for end users in normal operation (`canTransfer` defaults to `false` and is only flipped post-default by the manager). FalconXUSDC therefore is **non-transferrable** while solvent. The caliber cannot lose its receipt token in transit; it can only be redeemed via `claimWithdrawRequest()`.

> **Blueprint dependency for accounting (`flows.accounting.pareto_pending_receipt`)**: `IdleCreditVault.balanceOf(caliber)` returns the USDC owed to the caliber at the next stopEpoch (6-dec, no scaling). Add directly to caliber USDC value.

---

## 3. Royco Senior Tranche

Address: proxy `0x694ADB3077BBecE31882B6d6A74fc4A4fA6a754b`, impl `0x98dF5263392C83dD739d8959A6bACf01EA034bba`. **Verified on Sourcify (partial match), Solidity 0.8.34 (Prague)**. Files: `RoycoSeniorTranche.sol`, `RoycoVaultTranche.sol`, OpenZeppelin v5.4.0 `AccessManagedUpgradeable.sol`. The thin `RoycoSeniorTranche.sol` body just sets `TRANCHE_TYPE = SENIOR` and forwards to `RoycoVaultTranche`:

```solidity
contract RoycoSeniorTranche is RoycoVaultTranche {
    constructor(address _asset, address _kernel) RoycoVaultTranche(_asset, _kernel) { }
    function initialize(RoycoTrancheInitParams calldata _stParams) external initializer {
        __RoycoTranche_init(_stParams);
    }
    function TRANCHE_TYPE() public pure virtual override returns (TrancheType) {
        return TrancheType.SENIOR;
    }
}
```

> ASSET / KERNEL are immutable — `ASSET = 0xc26a...f99c (AA tranche)` and `KERNEL = 0x15bb...1791`. They cannot be changed by any admin operation.

### `deposit(uint256,address)` — gated by access manager + kernel

> Why the blueprint cares: This is step 4 of `flows.deposit`. The blueprint MUST first call `RoycoFactory.canCall(caliber, ROY_ST, deposit_selector)` and assert `(allowed=true, delay=0)` before submitting. Otherwise the call reverts with `AccessManagedUnauthorized(caller)`. The `whenNotPaused` modifier means the spec's `pause_state.royco_st.paused_at_spec_time == false` precondition must also hold.

```solidity
// RoycoVaultTranche.sol
function deposit(TRANCHE_UNIT _assets, address _receiver)
    public
    virtual
    override(IRoycoVaultTranche)
    whenNotPaused
    restricted                                            // <-- AccessManaged gate
    returns (uint256 shares)
{
    require(_receiver != address(0), ERC20InvalidReceiver(address(0)));

    // 1) Pull AA tranche tokens straight from msg.sender to the kernel:
    IERC20(ASSET).safeTransferFrom(msg.sender, KERNEL, toUint256(_assets));

    // 2) Hand off to the kernel: ST tranche -> kernel.stDeposit
    (NAV_UNIT valueAllocated, NAV_UNIT effectiveNAVToMintAt) =
        (TRANCHE_TYPE() == TrancheType.SENIOR
            ? IRoycoKernel(KERNEL).stDeposit(_assets)
            : IRoycoKernel(KERNEL).jtDeposit(_assets));

    require(valueAllocated != ZERO_NAV_UNITS, INVALID_VALUE_ALLOCATED());

    // 3) shares = valueAllocated * (totalSupply + 1) / (effectiveNAVToMintAt + 1)
    shares = _convertToShares(
        valueAllocated, totalSupply(), effectiveNAVToMintAt, Math.Rounding.Floor);
    require(shares != 0, MUST_MINT_NON_ZERO_SHARES());

    _mint(_receiver, shares);
    emit Deposit(msg.sender, _receiver, _assets, shares);
}
```

> Note the `safeTransferFrom(msg.sender, KERNEL, ...)` — the AA approval the blueprint posts in step 3 is **for the ST contract**, but the AA actually moves from `msg.sender` to `KERNEL`, NOT to the ST. (The ST is the spender; the recipient is the kernel.) This matches `flows.deposit.events_to_monitor`: `AA.Transfer(caliber, RoycoKernel, aaMinted)`.

### `redeem(uint256,address,address)` — burns ST shares, returns 3-tuple `AssetClaims`

> Why the blueprint cares: This is the entry of Phase 1 of `flows.withdraw`. Unlike a standard ERC4626 `redeem`, this returns `AssetClaims memory claims = (uint256 stAssets, uint256 jtAssets, uint256 nav)` — the 3-tuple format the spec describes. Encoded as `(uint256,uint256,uint256)` — 96 bytes. The blueprint should sandwich `AA.balanceOf(caliber)` rather than rely on tuple decode (already noted in spec).

```solidity
// RoycoVaultTranche.sol
function redeem(uint256 _shares, address _receiver, address _owner)
    public
    virtual
    override(IRoycoVaultTranche)
    whenNotPaused
    restricted                                            // <-- AccessManaged gate
    returns (AssetClaims memory claims)
{
    require(_receiver != address(0), ERC20InvalidReceiver(address(0)));
    require(_shares != 0, MUST_REQUEST_NON_ZERO_SHARES());

    if (msg.sender != _owner) {
        _spendAllowance(_owner, msg.sender, _shares);
    }

    // Kernel transfers AA tranche tokens directly to _receiver:
    claims =
    (TRANCHE_TYPE() == TrancheType.SENIOR
            ? IRoycoKernel(KERNEL).stRedeem(_shares, _receiver, false)
            : IRoycoKernel(KERNEL).jtRedeem(_shares, _receiver, false));

    // Burn shares AFTER kernel processes redemption (kernel depends on pre-burn total supply):
    _burn(_owner, _shares);

    emit Redeem(msg.sender, _receiver, claims, _shares);
}
```

### `convertToAssets(uint256)` — view, the 3-tuple confirmation

> Why the blueprint cares: This is the accounting helper for `flows.accounting.st_to_assets`. **Confirms** the 3-tuple shape `(uint256 stAssets, uint256 jtAssets, uint256 nav)`. Both `stAssets` and `jtAssets` are in tranche-asset units (here, AA tranche tokens, 18-dec). `nav` is in NAV_UNIT (USD WAD, 18-dec). For this Pareto market, with `jtTotalSupply == 0`, `jtAssets == 0` in steady state — including it in the asset-space conversion is defensive only. The recommended path (asset-space) is `(stAssets + jtAssets) * tranchePrice(AA) / 1e18`.

```solidity
// RoycoVaultTranche.sol
function convertToAssets(uint256 _shares)
    public
    view
    virtual
    override(IRoycoVaultTranche)
    returns (AssetClaims memory claims)
{
    (AssetClaims memory trancheClaims, uint256 trancheTotalShares) = _previewPostSyncTrancheState();
    return UtilsLib.scaleAssetClaims(trancheClaims, _shares, trancheTotalShares);
}

function _previewPostSyncTrancheState()
    internal view
    returns (AssetClaims memory trancheClaims, uint256 trancheTotalShares)
{
    (, trancheClaims, trancheTotalShares) =
        IRoycoKernel(KERNEL).previewSyncTrancheAccounting(TRANCHE_TYPE());
}
```

### `_checkCanCall` — the actual call gate (OpenZeppelin v5.4.0)

> Why the blueprint cares: every `restricted` modifier on the ST and Kernel runs through this. If the role grant has any `executionDelay > 0`, the call goes into `consumeScheduledOp` and reverts unless the caliber pre-scheduled it. The blueprint MUST verify `(allowed = true, delay = 0)` from `RoycoFactory.canCall` before sending — see section 5.

```solidity
// AccessManagedUpgradeable.sol (OZ v5.4.0)
modifier restricted() {
    _checkCanCall(_msgSender(), _msgData());
    _;
}

function _checkCanCall(address caller, bytes calldata data) internal virtual {
    AccessManagedStorage storage $ = _getAccessManagedStorage();
    (bool immediate, uint32 delay) = AuthorityUtils.canCallWithDelay(
        authority(),                    // RoycoFactory
        caller,
        address(this),
        bytes4(data[0:4])
    );
    if (!immediate) {
        if (delay > 0) {
            $._consumingSchedule = true;
            IAccessManager(authority()).consumeScheduledOp(caller, data);
            $._consumingSchedule = false;
        } else {
            revert AccessManagedUnauthorized(caller);
        }
    }
}
```

---

## 4. Royco Kernel

Address: proxy `0x15bb63C07740ff972F76716cAcC5766f0C641791`, impl `0xAA9631dF7ec04AbB825bD6a663f96c9BB3Ed7e1e`, accountant subimpl `0x288bc6a8600d0bc1f179816c3b3001b00566c110`. **Neither verified on Sourcify nor Etherscan.** The bodies below are the verified `RoycoKernel.sol` from the sibling impl `0xeb7c3a4a72b4c201e50add11003ada2566d276ea` (Sourcify partial match, Solidity 0.8.34, contract `Identical_ERC4626_ST_JT_SharePriceToChainlinkOracle_Kernel` extends `RoycoKernel`). The deposit / redeem / sync / coverage logic is in the `RoycoKernel` base and is identical across markets — only the oracle quoter differs. This is the same recovery pattern used by the `royco-st-stcusd` and `royco-st-syrupusdc` integrations.

### `syncTrancheAccounting()` — the access-restricted PnL crystalliser

> Why the blueprint cares: This is the function `flows.accounting.queries.sync` calls before reading `convertToAssets`. **It is NOT idempotent within a single tx** — it mints fee shares, advances cursors, and updates state. It is also `whenNotPaused restricted nonReentrant`, so the caliber needs the role grant for `(target=Kernel, selector=syncTrancheAccounting())`. The internal call `_preOpSyncTrancheAccounting()` is what does the work; `syncTrancheAccounting` is the externally-callable wrapper.

```solidity
// RoycoKernel.sol
function syncTrancheAccounting()
    public
    virtual
    override(IRoycoKernel)
    whenNotPaused
    restricted              // <-- ACL
    nonReentrant
    withQuoterCache
    returns (SyncedAccountingState memory state)
{
    return _preOpSyncTrancheAccounting();
}
```

For _view-safe_ reads, `previewSyncTrancheAccounting(TrancheType)` is the read-only mirror used internally by `convertToAssets`:

```solidity
function previewSyncTrancheAccounting(TrancheType _trancheType)
    public
    view
    virtual
    override(IRoycoKernel)
    returns (SyncedAccountingState memory state, AssetClaims memory claims, uint256 totalTrancheShares)
{
    state = _previewSyncTrancheAccounting();
    claims = _deriveTrancheAssetClaims(_trancheType, state);
    if (_trancheType == TrancheType.SENIOR) {
        (, totalTrancheShares) = IRoycoVaultTranche(SENIOR_TRANCHE)
            .previewMintProtocolFeeShares(state.stProtocolFeeAccrued, state.stEffectiveNAV);
    } else {
        (, totalTrancheShares) = IRoycoVaultTranche(JUNIOR_TRANCHE)
            .previewMintProtocolFeeShares(state.jtProtocolFeeAccrued, state.jtEffectiveNAV);
    }
}
```

> **Idempotence answer for the blueprint**: `previewSyncTrancheAccounting` is `view`-pure. `syncTrancheAccounting` is **not** idempotent — running it twice in the same tx will accrue fees the second time at zero (the time delta is zero), but the call will still mutate state (e.g. `lastSyncTimestamp` doesn't move because `block.timestamp` is the same — but the underlying quoter cache initializes/clears). The safe blueprint pattern is: `syncTrancheAccounting` once at the top of the account flow, then `convertToAssets` for the read. **DO NOT batch multiple `syncTrancheAccounting` calls.**

### `stDeposit` — kernel handoff invoked by `RoycoSeniorTranche.deposit`

> Why the blueprint cares: This is the function whose `_postOpSyncTrancheAccountingAndEnforceCoverage(Operation.ST_DEPOSIT)` reverts when `jtRawNAV == 0` (the bootstrap-required case in `open_questions.junior_bootstrap`).

```solidity
function stDeposit(TRANCHE_UNIT _assets)
    external
    virtual
    override(IRoycoKernel)
    whenNotPaused
    onlySeniorTranche
    nonReentrant
    withQuoterCache
    returns (NAV_UNIT valueAllocated, NAV_UNIT navToMintSharesAt)
{
    SyncedAccountingState memory state = _preOpSyncTrancheAccounting();
    require(state.stImpermanentLoss == ZERO_NAV_UNITS, ST_DEPOSIT_DISABLED_IN_LOSS());

    _stDepositAssets(_assets);

    // <<< THIS IS THE BOOTSTRAP-BLOCKING CALL >>>
    NAV_UNIT stPostDepositNAV =
        (_postOpSyncTrancheAccountingAndEnforceCoverage(Operation.ST_DEPOSIT)).stEffectiveNAV;

    navToMintSharesAt = state.stEffectiveNAV;
    valueAllocated = (stPostDepositNAV - navToMintSharesAt);
}

function _postOpSyncTrancheAccountingAndEnforceCoverage(Operation _op)
    internal virtual
    returns (SyncedAccountingState memory state)
{
    state = IRoycoAccountant(ACCOUNTANT)
        .postOpSyncTrancheAccountingAndEnforceCoverage(_op, _getSeniorTrancheRawNAV(), _getJuniorTrancheRawNAV());
}
```

The `IRoycoAccountant` interface declaration that the (unverified) accountant impl satisfies:

```solidity
// IRoycoAccountant.sol
function postOpSyncTrancheAccountingAndEnforceCoverage(
    Operation _op,
    NAV_UNIT _stRawNAV,
    NAV_UNIT _jtRawNAV
)
    external
    returns (SyncedAccountingState memory state);
```

Per the interface natspec (verbatim):

> "Reverts if the coverage requirement is unsatisfied after the NAVs have been marked to market."

The coverage condition itself is encoded in `SyncedAccountingState`:

```solidity
struct SyncedAccountingState {
    MarketState marketState;
    NAV_UNIT stRawNAV;             // <-- "The senior tranche's current raw NAV: the pure value of its invested assets"
    NAV_UNIT jtRawNAV;             // <-- "The junior tranche's current raw NAV"
    NAV_UNIT stEffectiveNAV;
    NAV_UNIT jtEffectiveNAV;
    NAV_UNIT stImpermanentLoss;
    NAV_UNIT jtImpermanentLoss;
    NAV_UNIT stProtocolFeeAccrued;
    NAV_UNIT jtProtocolFeeAccrued;
    uint256  utilizationWAD;       // <-- compared to liquidationUtilizationWAD
    uint32   fixedTermEndTimestamp;
    uint256  coverageWAD;          // <-- compared to coverage requirement
    uint256  betaWAD;
    uint256  liquidationUtilizationWAD;
}
```

The closed-form utilization expression used elsewhere in the kernel (`_computeMaxUtilizationNeutralBonus`, line 901):

```solidity
// From the doc-comment block of RoycoKernel._computeMaxUtilizationNeutralBonus:
//   COVERED_EXPOSURE = ST_RAW_NAV + JT_RAW_NAV * β
//   U = (COVERED_EXPOSURE * COV) / JT_EFFECTIVE_NAV
NAV_UNIT totalCoveredExposure =
    _state.stRawNAV + _state.jtRawNAV.mulDiv(_state.betaWAD, WAD, Math.Rounding.Ceil);
```

> **Bootstrap-blocking math**: with `jtRawNAV == 0` and `betaWAD == 1e18`, `coveredExposure = stRawNAV`. With `jtEffectiveNAV == 0`, utilization is `division by zero` (or, more precisely, the accountant's internal helper rounds this to "infinite > liquidationUtilizationWAD"), so any positive `stRawNAV` post-deposit causes `postOpSyncTrancheAccountingAndEnforceCoverage` to revert. This is the bootstrap blocker called out in `open_questions.junior_bootstrap`. **The accountant's exact revert string cannot be confirmed** because the accountant impl `0x288bc6a8600d0bc1f179816c3b3001b00566c110` is unverified; based on the interface naming convention used elsewhere in this codebase the expected error is `RoycoAccountant_CoverageNotMet()` or similar.

### `stRedeem` — kernel handoff invoked by `RoycoSeniorTranche.redeem`

```solidity
function stRedeem(uint256 _shares, address _receiver, bool _bypassRedemptionRestrictions)
    external
    virtual
    override(IRoycoKernel)
    whenNotPaused
    onlySeniorTranche
    nonReentrant
    withQuoterCache
    returns (AssetClaims memory userAssetClaims)
{
    SyncedAccountingState memory state;
    uint256 totalTrancheShares;
    (state, userAssetClaims, totalTrancheShares) = _preOpSyncTrancheAccounting(TrancheType.SENIOR);
    require(_bypassRedemptionRestrictions || state.marketState == MarketState.PERPETUAL,
            ST_REDEEM_DISABLED_IN_FIXED_TERM_STATE());

    userAssetClaims = UtilsLib.scaleAssetClaims(userAssetClaims, _shares, totalTrancheShares);

    NAV_UNIT stSelfLiquidationBonusNAV;
    (userAssetClaims, stSelfLiquidationBonusNAV) =
        _applySeniorTrancheSelfLiquidationBonus(state, userAssetClaims);

    // Transfers AA tranche tokens directly to _receiver (here, the caliber):
    _withdrawAssets(userAssetClaims, _receiver);

    // Post-op sync (no coverage enforcement on ST redeem):
    _postOpSyncTrancheAccounting(Operation.ST_REDEEM, stSelfLiquidationBonusNAV);
}
```

> Note: ST redemption does NOT enforce coverage — only ST deposits and JT redemptions do. So Phase 1 of `flows.withdraw` will not run into the same bootstrap revert as deposit; once the caliber holds ST shares, redeem is unblocked (subject to `marketState == PERPETUAL`).

---

## 5. RoycoFactory (AccessManager)

Address: proxy `0x7cC6fB28eC7b5e7afC3cB3986141797ffc27253C`, impl `0x34DB2f4215e55ec8e2c3dE0a826935EBF158be77`. **Verified on Sourcify (partial match)**, Solidity 0.8.34. Inherits OpenZeppelin v5.4.0 `AccessManagerUpgradeable`. The verified factory adds Royco-specific role IDs (`ADMIN_ACCOUNTANT_ROLE`, `ADMIN_KERNEL_ROLE`, `ST_LP_ROLE`, `JT_LP_ROLE`, etc.) on top of the OZ AccessManager primitives but does **not** override `canCall` or `hasRole`, so the OZ implementations apply verbatim.

### `canCall(address caller, address target, bytes4 selector)` — the gate every Royco entrypoint passes through

> Why the blueprint cares: This is the **off-chain probe** the integration must run before submitting any of `ST.deposit / ST.redeem / Kernel.syncTrancheAccounting`. Both `(allowed == true)` AND `(delay == 0)` are required — a nonzero delay routes the call into `consumeScheduledOp`, which is incompatible with atomic blueprint execution.

```solidity
// AccessManagerUpgradeable.sol  (OpenZeppelin v5.4.0, used verbatim by RoycoFactory)
function canCall(
    address caller,
    address target,
    bytes4 selector
) public view virtual returns (bool immediate, uint32 delay) {
    if (isTargetClosed(target)) {
        return (false, 0);
    } else if (caller == address(this)) {
        return (_isExecuting(target, selector), 0);
    } else {
        uint64 roleId = getTargetFunctionRole(target, selector);
        (bool isMember, uint32 currentDelay) = hasRole(roleId, caller);
        return isMember ? (currentDelay == 0, currentDelay) : (false, 0);
    }
}

function hasRole(
    uint64 roleId,
    address account
) public view virtual returns (bool isMember, uint32 executionDelay) {
    if (roleId == PUBLIC_ROLE) {
        return (true, 0);
    } else {
        (uint48 hasRoleSince, uint32 currentDelay, , ) = getAccess(roleId, account);
        return (hasRoleSince != 0 && hasRoleSince <= Time.timestamp(), currentDelay);
    }
}
```

> Mocking surface for Tenderly: the factory storage is keyed on `_roles[roleId].members[account]` and `_targets[target].allowedRoles[selector]`. Per OZ v5.4.0 the storage namespace is `keccak256(abi.encode(uint256(keccak256("openzeppelin.storage.AccessManager")) - 1)) & ~bytes32(0xff)`. Rather than computing each slot by hand, the cheapest Tenderly bypass is to call `grantRole(roleId, caliber, 0)` impersonating the admin (`getRoleAdmin(roleId)`); the admin for ST/Kernel role IDs in this market is the same Dialectic / Royco multisig the existing royco-st-* integrations use.

> Cross-reference with `specs.yaml.access_control.royco`: granted off-chain at subscription time. Verify by calling `RoycoFactory.canCall(caliber, ROY_ST, 0x6e553f65 /* deposit(uint256,address) */)` and similar for `redeem(uint256,address,address)` and `syncTrancheAccounting()`.

---

## Citations / Sibling references

- `royco-st-syrupusdc` (sibling integration): identical `RoycoVaultTranche` family, same access pattern, recommended asset-space accounting path.
- `royco-st-stcusd` (sibling integration): see `nav-investigation.md` for the verified-twin RoycoSeniorTranche analysis (`0x78493b...`); confirms `(stAssets, jtAssets, nav)` 3-tuple shape with 96-byte ABI encoding.
- Pareto integrators docs (https://docs.pareto.credit/developers/integrators/smart-contract): confirms the `depositAA` / `depositDuringEpoch` / `requestWithdraw` / `claimWithdrawRequest` flow, epoch lifecycle, and Keyring policy id 18 gate.

## Coverage of fetch failures

The only impls that did NOT have a verified copy on either Etherscan or Sourcify are:

1. The Pareto-FalconX-specific Royco kernel impl `0xAA9631dF7ec04AbB825bD6a663f96c9BB3Ed7e1e`.
2. The accountant subimpl for this market `0x288bc6a8600d0bc1f179816c3b3001b00566c110`.

For both, this document uses code from a sibling Royco kernel impl on the same `RoycoKernel.sol` base, verified on Sourcify (`0xeb7c3a4a72b4c201e50add11003ada2566d276ea`). The deposit/redeem dispatch, coverage-enforcement flow, and `SyncedAccountingState` shape are inherited from the same `RoycoKernel` base class, so the function signatures, modifiers, and revert paths quoted are accurate. The exact accountant revert string (`RoycoAccountant: coverage` per the spec, or some equivalent custom error) cannot be confirmed without the verified accountant source — the execution-explorer should pin this down by capturing the revert reason on the first failed `stDeposit` against the empty (`jtRawNAV == 0`) market.
