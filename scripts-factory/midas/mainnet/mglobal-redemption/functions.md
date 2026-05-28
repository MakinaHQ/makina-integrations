# Midas mGLOBAL Redemption Vault (with Aave) — Function Implementations

Chain: Ethereum mainnet (chain_id 1)
Proxy (call target): `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B`
Implementation: `0xf687E76e3d62d62fE6F6A7f66ce9faE21df6438d` (`MGlobalRedemptionVaultWithAave`)
Compiler: `v0.8.9+commit.e5eed63a`
Source: blockscout (Ethereum mainnet), verified 2026-04-03

---

## Critical callouts (read before using specs.yaml)

1. **Live `mTokenDataFeed.getDataInBase18()` is invoked inside `_redeemRequest`.**
   The vault calls it on every `redeemRequest(...)` to snapshot `mTokenRate`
   into the Request struct. If the feed is unhealthy (currently true on mainnet
   per the 2026-05-15 probe), `redeemRequest` reverts with `DF: feed is
   unhealthy`. Accounting is unaffected because the snapshot is already stored.

2. **`Request.mTokenRate` is the snapshot rate used for accounting.**
   Read from the public `redeemRequests(uint256)` mapping. It is immune to
   later feed health issues. Note that admin can OVERWRITE this field on
   approval (`_approveRequest` sets `request.mTokenRate = newMTokenRate` before
   storing back).

3. **Recipient and msg.sender both gated by `_validateUserAccess`.**
   The 3-arg `redeemRequest` checks `_validateUserAccess(msg.sender)` and (if
   `recipient != msg.sender`) `_validateUserAccess(recipient)`. Both must pass
   greenlist + sanctions + blacklist gates. When the caliber calls with itself
   as recipient (`msg.sender == recipient`), only one check is performed.

4. **CORRECTION to `RequestStatus` enum in specs.yaml.**
   The actual Solidity enum in `IManageableVault.sol` is:
   ```solidity
   enum RequestStatus { Pending, Processed, Canceled }   // 0, 1, 2
   ```
   There is **no `None` variant**. specs.yaml currently says
   `{None=0, Pending=1, Processed=2, Canceled=3}` — this is wrong.
   Correct mapping: **Pending=0, Processed=1, Canceled=2**.
   For non-existent ids the struct comes back zeroed (sender=0x0,
   status=Pending(0), amountMToken=0, mTokenRate=0). The contract distinguishes
   "exists vs not" via `request.sender != address(0)` (see `_validateRequest`),
   NOT via status. Accounting blueprints must therefore check
   `sender != 0x0 && status == 0` to recognize a real Pending request.

5. **`MGlobalRedemptionVaultWithAave` adds NO override on the request path.**
   The mGLOBAL-flavored contract only overrides `vaultRole()` and
   `greenlistedRole()`. `RedemptionVaultWithAave` only overrides `_redeemInstant`
   (Aave-aware liquidity sourcing for the _instant_ path). Neither
   `_redeemRequest` nor `_approveRequest` is touched. The request flow is
   exactly `RedemptionVault._redeemRequest` / `_approveRequest` as documented
   below. `_validateLiquidity` is also unchanged (still pulls `balanceOf(requestRedeemer)`,
   only consulted by `safeBulkApproveRequest`; `approveRequest` ignores it).

6. **`currentRequestId.current()` view returns the NEXT id to be assigned.**
   `_redeemRequest` reads it pre-increment then increments. To capture the id
   in the same tx, read `currentRequestId()` immediately before the call.

---

## Overview

| Function                                                                                       | Source contract                      | Type                           |
| ---------------------------------------------------------------------------------------------- | ------------------------------------ | ------------------------------ |
| `redeemRequest(address,uint256,address)`                                                       | `RedemptionVault.sol`                | External (call target)         |
| `_redeemRequest(...)`                                                                          | `RedemptionVault.sol`                | Internal (logic)               |
| `approveRequest(uint256,uint256)`                                                              | `RedemptionVault.sol`                | External admin                 |
| `_approveRequest(...)`                                                                         | `RedemptionVault.sol`                | Internal (settlement logic)    |
| `_calcAndValidateRedeem(...)`                                                                  | `RedemptionVault.sol`                | Internal (fee + min)           |
| `redeemRequests(uint256)`                                                                      | `RedemptionVault.sol`                | Public mapping getter          |
| `currentRequestId()`                                                                           | `ManageableVault.sol`                | Public Counters.Counter        |
| `_getFeeAmount(...)`                                                                           | `ManageableVault.sol`                | Internal view                  |
| `_tokenTransferFromUser(...)`                                                                  | `ManageableVault.sol`                | Internal                       |
| `_requireAndUpdateAllowance(...)`                                                              | `ManageableVault.sol`                | Internal                       |
| `_validateUserAccess(...)`                                                                     | `ManageableVault.sol`                | Internal view (gate)           |
| `tokensConfig(address)`                                                                        | `ManageableVault.sol`                | Public mapping getter          |
| `vaultRole()` / `greenlistedRole()`                                                            | `MGlobalRedemptionVaultWithAave.sol` | Role override                  |
| `_redeemInstant(...)` Aave override                                                            | `RedemptionVaultWithAave.sol`        | Override (NOT on request path) |
| `Request` struct                                                                               | `IRedemptionVault.sol`               | Storage layout                 |
| `RequestStatus` enum                                                                           | `IManageableVault.sol`               | Status values                  |
| `TokenConfig` struct                                                                           | `IManageableVault.sol`               | tokensConfig shape             |
| Events: `RedeemRequest`, `RedeemRequestWithCustomRecipient`, `ApproveRequest`, `RejectRequest` | `IRedemptionVault.sol`               |                                |

---

## Structs and Enums

### `Request` struct — `contracts/interfaces/IRedemptionVault.sol`

```solidity
/**
 * @notice Redeem request struct
 * @param sender user address who create
 * @param tokenOut tokenOut address
 * @param status request status
 * @param amountMToken amount mToken
 * @param mTokenRate rate of mToken at request creation time
 * @param tokenOutRate rate of tokenOut at request creation time
 */
struct Request {
    address sender;
    address tokenOut;
    RequestStatus status;
    uint256 amountMToken;
    uint256 mTokenRate;
    uint256 tokenOutRate;
}
```

ABI tuple order for the auto-generated `redeemRequests(uint256)` getter:
`(address sender, address tokenOut, uint8 status, uint256 amountMToken, uint256 mTokenRate, uint256 tokenOutRate)`.

For our request the `sender` field is set to the `recipient` argument of
`redeemRequest(address tokenOut, uint256 amountMTokenIn, address recipient)`
(see `_redeemRequest` below), i.e. the caliber address — NOT the
`msg.sender` of the call. This is what causes USDC to land on the caliber at
settlement: `_approveRequest` does `_tokenTransferFromTo(..., request.sender, ...)`.

### `RequestStatus` enum — `contracts/interfaces/IManageableVault.sol`

```solidity
enum RequestStatus {
    Pending,    // 0
    Processed,  // 1
    Canceled    // 2
}
```

> **No `None` variant.** Use `sender != address(0)` to detect existence.

### `TokenConfig` struct — `contracts/interfaces/IManageableVault.sol`

```solidity
/**
 * @param dataFeed data feed token/USD address
 * @param fee fee by token, 1% = 100
 * @param allowance token allowance (decimals 18)
 */
struct TokenConfig {
    address dataFeed;
    uint256 fee;
    uint256 allowance;
    bool stable;
}
```

ABI tuple order for the auto-generated `tokensConfig(address)` getter:
`(address dataFeed, uint256 fee, uint256 allowance, bool stable)`.

For USDC on this vault (verified 2026-05-15):
`(0x3aAc6fd73fA4e16Ec683BD4aaF5Ec89bb2C0EdC2, 0, ~1e27, true)`.
`fee = 0` means **zero per-token fee** on both instant and request paths.
`stable = true` means `_getTokenRate` short-circuits and returns `STABLECOIN_RATE = 1e18`.

---

## Events (from `IRedemptionVault.sol`)

```solidity
event RedeemRequest(
    uint256 indexed requestId,
    address indexed user,
    address indexed tokenOut,
    uint256 amountMTokenIn,
    uint256 feeAmount
);

event RedeemRequestWithCustomRecipient(
    uint256 indexed requestId,
    address indexed user,         // msg.sender of redeemRequest
    address indexed tokenOut,
    address recipient,            // = Request.sender stored in struct
    uint256 amountMTokenIn,
    uint256 feeAmount
);

event ApproveRequest(uint256 indexed requestId, uint256 newMTokenRate);

event RejectRequest(uint256 indexed requestId, address indexed user);
```

For our caliber flow we emit `RedeemRequestWithCustomRecipient` (3-arg overload).

---

## Withdraw path

### `redeemRequest(address tokenOut, uint256 amountMTokenIn, address recipient)` (3-arg)

Source: `contracts/RedemptionVault.sol`

```solidity
function redeemRequest(
    address tokenOut,
    uint256 amountMTokenIn,
    address recipient
)
    external
    whenFnNotPaused(_REDEEM_REQUEST_WITH_CUSTOM_RECIPIENT_SELECTOR)
    returns (uint256 /*requestId*/)
{
    _validateUserAccess(msg.sender);

    if (recipient != msg.sender) {
        _validateUserAccess(recipient);
    }

    (
        uint256 requestId,
        CalcAndValidateRedeemResult memory calcResult
    ) = _redeemRequest(tokenOut, amountMTokenIn, false, recipient);

    emit RedeemRequestWithCustomRecipient(
        requestId,
        msg.sender,
        tokenOut,
        recipient,
        amountMTokenIn,
        calcResult.feeAmount
    );

    return requestId;
}
```

- Selector: `redeemRequest(address,uint256,address)`
- Pausable per-selector via `whenFnNotPaused`. If the caliber calls with itself
  as `recipient`, only one `_validateUserAccess` call is made.

### `_redeemRequest(...)` (internal logic) — `RedemptionVault.sol`

```solidity
function _redeemRequest(
    address tokenOut,
    uint256 amountMTokenIn,
    bool isFiat,
    address recipient
)
    internal
    returns (
        uint256 requestId,
        CalcAndValidateRedeemResult memory calcResult
    )
{
    if (!isFiat) {
        require(
            tokenOut != MANUAL_FULLFILMENT_TOKEN,
            "RV: tokenOut == fiat"
        );
    }

    address user = msg.sender;

    calcResult = _calcAndValidateRedeem(
        user,
        tokenOut,
        amountMTokenIn,
        false,   // isInstant = false   -> instantFee NOT added
        isFiat
    );

    address tokenOutCopy = tokenOut;

    // assigning the default value which is gonna be used
    // only for fiat redemptions
    uint256 tokenOutRate = 1e18;

    if (!isFiat) {
        TokenConfig storage config = tokensConfig[tokenOutCopy];
        tokenOutRate = _getTokenRate(config.dataFeed, config.stable);
        // USDC.stable = true -> short-circuits to STABLECOIN_RATE = 1e18
    }

    uint256 mTokenRate = mTokenDataFeed.getDataInBase18();
    // ^^^ reverts if mGLOBAL feed is unhealthy

    _tokenTransferFromUser(
        address(mToken),
        address(this),                              // escrow into vault
        calcResult.amountMTokenWithoutFee,
        18 // mToken always have 18 decimals
    );
    if (calcResult.feeAmount > 0)
        _tokenTransferFromUser(
            address(mToken),
            feeReceiver,
            calcResult.feeAmount,
            18
        );
    // With tokensConfig[USDC].fee = 0 and isInstant = false,
    // _getFeeAmount returns 0, so amountMTokenWithoutFee == amountMTokenIn
    // and the feeReceiver branch is skipped.

    requestId = currentRequestId.current();   // pre-increment value
    currentRequestId.increment();

    redeemRequests[requestId] = Request({
        sender: recipient,                    // <-- USDC will be pushed here at settlement
        tokenOut: tokenOutCopy,
        status: RequestStatus.Pending,        // == 0
        amountMToken: calcResult.amountMTokenWithoutFee,
        mTokenRate: mTokenRate,
        tokenOutRate: tokenOutRate            // = 1e18 for USDC (stable=true)
    });

    return (requestId, calcResult);
}
```

Key observations for the withdraw blueprint:

- `requestId = currentRequestId.current()` is the PRE-INCREMENT value, so a
  same-tx read of `currentRequestId()` (the public Counters.Counter getter
  exposes `.current()` semantics via storage slot read; see below) returns
  exactly the id about to be assigned.
- `Request.sender` is `recipient`, NOT `msg.sender`. This is the field the
  settlement path reads to know where to push USDC. Set `recipient = caliber`.
- `Request.tokenOutRate = 1e18` for USDC (stable). Hard-pinned regardless of
  feed value.
- `mTokenRate` is captured here. Live feed revert is the only place the
  request path can fail on the rate.
- mGLOBAL escrow uses `_tokenTransferFromUser(mToken, address(this), ...)` —
  pulls from `msg.sender` (caliber) to the vault. Approval must therefore be
  granted by the caliber to the vault on mGLOBAL beforehand.

### `_calcAndValidateRedeem(...)` — `RedemptionVault.sol`

```solidity
function _calcAndValidateRedeem(
    address user,
    address tokenOut,
    uint256 amountMTokenIn,
    bool isInstant,
    bool isFiat
) internal view returns (CalcAndValidateRedeemResult memory result) {
    require(amountMTokenIn > 0, "RV: invalid amount");

    if (!isFreeFromMinAmount[user]) {
        uint256 minRedeemAmount = isFiat ? minFiatRedeemAmount : minAmount;
        require(minRedeemAmount <= amountMTokenIn, "RV: amount < min");
    }

    result.feeAmount = _getFeeAmount(
        user,
        tokenOut,
        amountMTokenIn,
        isInstant,
        isFiat ? fiatAdditionalFee : 0
    );

    if (isFiat) {
        require(
            tokenOut == MANUAL_FULLFILMENT_TOKEN,
            "RV: tokenOut != fiat"
        );
        if (!waivedFeeRestriction[user]) result.feeAmount += fiatFlatFee;
    } else {
        _requireTokenExists(tokenOut);   // tokenOut must be in _paymentTokens
    }

    require(amountMTokenIn > result.feeAmount, "RV: amountMTokenIn < fee");

    result.amountMTokenWithoutFee = amountMTokenIn - result.feeAmount;
}
```

For our path: `isInstant = false`, `isFiat = false`, `tokenOut = USDC`.

- `minAmount = 0` on this vault → first require passes for any positive amount.
- `_getFeeAmount(..., isInstant=false, additionalFee=0)` returns
  `(amount * tokensConfig[USDC].fee) / ONE_HUNDRED_PERCENT`. Since
  `tokensConfig[USDC].fee == 0`, `feeAmount = 0`.
- `_requireTokenExists(USDC)` passes (USDC is registered).
- Final: `amountMTokenWithoutFee == amountMTokenIn`.

### `_getFeeAmount(...)` — `ManageableVault.sol`

```solidity
function _getFeeAmount(
    address sender,
    address token,
    uint256 amount,
    bool isInstant,
    uint256 additionalFee
) internal view returns (uint256) {
    if (waivedFeeRestriction[sender]) return 0;

    uint256 feePercent;
    if (additionalFee == 0) {
        TokenConfig storage tokenConfig = tokensConfig[token];
        feePercent = tokenConfig.fee;       // <-- request path uses this
    } else {
        feePercent = additionalFee;
    }

    if (isInstant) feePercent += instantFee;   // <-- skipped on request path

    if (feePercent > ONE_HUNDRED_PERCENT) feePercent = ONE_HUNDRED_PERCENT;

    return (amount * feePercent) / ONE_HUNDRED_PERCENT;
}
```

Proves: on the request path (`isInstant = false`, `additionalFee = 0`), fee is
purely `tokensConfig[tokenOut].fee`. USDC fee = 0 on this vault.

### `_validateUserAccess(...)` — `ManageableVault.sol`

```solidity
function _validateUserAccess(address user)
    internal
    view
    onlyGreenlisted(user)
    onlyNotBlacklisted(user)
    onlyNotSanctioned(user)
{}
```

Three modifier gates. The mGLOBAL contract overrides `greenlistedRole()` to
return `M_GLOBAL_GREENLISTED_ROLE`, so the caliber must hold that exact role
(not the generic `GREENLISTED_ROLE`).

### `_tokenTransferFromUser(...)` — `ManageableVault.sol`

```solidity
function _tokenTransferFromUser(
    address token,
    address to,
    uint256 amount,
    uint256 tokenDecimals
) internal returns (uint256 transferAmount) {
    transferAmount = amount.convertFromBase18(tokenDecimals);

    require(
        amount == transferAmount.convertToBase18(tokenDecimals),
        "MV: invalid rounding"
    );

    IERC20(token).safeTransferFrom(msg.sender, to, transferAmount);
}
```

mGLOBAL has 18 decimals, so `convertFromBase18(18) == identity` and the
rounding check is trivially satisfied. The function pulls from `msg.sender`
(the caliber), which is why the caliber must `approve(vault, amountMTokenIn)`
on mGLOBAL before calling `redeemRequest`.

### `_requireAndUpdateAllowance(...)` — `ManageableVault.sol`

```solidity
function _requireAndUpdateAllowance(address token, uint256 amount)
    internal
{
    uint256 prevAllowance = tokensConfig[token].allowance;
    if (prevAllowance == MAX_UINT) return;

    require(prevAllowance >= amount, "MV: exceed allowance");

    tokensConfig[token].allowance -= amount;
}
```

NOT called during `_redeemRequest` (only in `_approveRequest` and
`_redeemInstant`). For our path it only matters at settlement: admin's
`approveRequest` consumes from `tokensConfig[USDC].allowance` (currently ~1e27,
effectively uncapped).

---

## Settlement path (admin-only; informational)

### `_approveRequest(...)` — `RedemptionVault.sol`

```solidity
function _approveRequest(
    uint256 requestId,
    uint256 newMTokenRate,
    bool isSafe,
    bool safeValidateLiquidity
)
    internal
    returns (bool /* success */)
{
    Request memory request = redeemRequests[requestId];

    _validateRequest(request.sender, request.status);

    if (isSafe) {
        _requireVariationTolerance(request.mTokenRate, newMTokenRate);
    }

    bool isFiat = request.tokenOut == MANUAL_FULLFILMENT_TOKEN;

    uint256 tokenDecimals = isFiat ? 18 : _tokenDecimals(request.tokenOut);

    uint256 amountTokenOutWithoutFee = _truncate(
        (request.amountMToken * newMTokenRate) / request.tokenOutRate,
        tokenDecimals
    );

    if (!isFiat) {
        if (
            safeValidateLiquidity &&
            !_validateLiquidity(
                request.tokenOut,
                amountTokenOutWithoutFee,
                tokenDecimals
            )
        ) {
            return false;
        }

        _tokenTransferFromTo(
            request.tokenOut,
            requestRedeemer,                 // USDC pulled from here
            request.sender,                  // <-- caliber address from recipient
            amountTokenOutWithoutFee,
            tokenDecimals
        );
    }

    _requireAndUpdateAllowance(request.tokenOut, amountTokenOutWithoutFee);

    mToken.burn(address(this), request.amountMToken);   // escrowed mGLOBAL burnt

    request.status = RequestStatus.Processed;
    request.mTokenRate = newMTokenRate;                 // <-- snapshot OVERWRITTEN
    redeemRequests[requestId] = request;

    return true;
}
```

Key points for accounting:

- `approveRequest(id, newRate)` calls `_approveRequest(id, newRate, false, false)`
  — neither `isSafe` (variation tolerance) nor `safeValidateLiquidity` is on.
  Admin can set any `newMTokenRate`.
- The `Request.mTokenRate` field is overwritten by `newMTokenRate` upon
  settlement. So if we read `redeemRequests(id)` after settlement we get the
  admin's settlement rate, not the original snapshot. Status will also flip
  to `Processed (1)` so our accounting blueprint treats it as value = 0
  regardless (the USDC has already landed on the caliber's wallet and is
  counted by the caliber's normal asset registry).
- `_truncate` rounds the USDC payout down to 6 decimals.

### `_validateRequest(...)` — `RedemptionVault.sol`

```solidity
function _validateRequest(address sender, RequestStatus status)
    internal
    pure
{
    require(sender != address(0), "RV: request not exist");
    require(status == RequestStatus.Pending, "RV: request not pending");
}
```

This is the canonical "existence" test: `sender == address(0)` means the slot
was never written. Accounting blueprints should mirror this when interpreting
a `redeemRequests(id)` read.

### `_validateLiquidity(...)` — `RedemptionVault.sol`

```solidity
function _validateLiquidity(
    address token,
    uint256 requiredLiquidity,
    uint256 tokenDecimals
)
    internal
    view
    returns (bool /* success */)
{
    uint256 balance = IERC20(token).balanceOf(requestRedeemer);
    return balance >= requiredLiquidity.convertFromBase18(tokenDecimals);
}
```

Only consulted by `safe*` admin entry points (bulk safe approvals). The plain
`approveRequest` path does not check liquidity — if `requestRedeemer` lacks
USDC or allowance, the `safeTransferFrom` inside `_tokenTransferFromTo` will
revert and the whole tx fails.

---

## Public state getters used by the blueprints

### `currentRequestId` — `ManageableVault.sol`

```solidity
/**
 * @notice last request id
 */
Counters.Counter public currentRequestId;
```

Public state variable of type `Counters.Counter`. Solidity auto-generates a
getter that returns the underlying `_value` field, which equals
`currentRequestId.current()` — i.e. the NEXT id to be assigned (pre-increment
semantics).

> ABI: `currentRequestId() returns (uint256)`. Reading this in the same tx
> as `redeemRequest` is the canonical pattern to recover the assigned id
> without parsing return data.

### `redeemRequests(uint256)` mapping — `RedemptionVault.sol`

```solidity
/**
 * @notice mapping, requestId to request data
 */
mapping(uint256 => Request) public redeemRequests;
```

Auto-generated getter signature:

```
redeemRequests(uint256) returns (
    address sender,
    address tokenOut,
    uint8 status,
    uint256 amountMToken,
    uint256 mTokenRate,
    uint256 tokenOutRate
)
```

### `tokensConfig(address)` mapping — `ManageableVault.sol`

```solidity
mapping(address => TokenConfig) public tokensConfig;
```

Auto-generated getter signature:

```
tokensConfig(address) returns (
    address dataFeed,
    uint256 fee,
    uint256 allowance,
    bool stable
)
```

---

## `MGlobalRedemptionVaultWithAave` overrides (the entire wrapper)

Source: `contracts/products/mGLOBAL/MGlobalRedemptionVaultWithAave.sol`

```solidity
contract MGlobalRedemptionVaultWithAave is
    RedemptionVaultWithAave,
    MGlobalMidasAccessControlRoles
{
    uint256[50] private __gap;

    function vaultRole() public pure override returns (bytes32) {
        return M_GLOBAL_REDEMPTION_VAULT_ADMIN_ROLE;
    }

    function greenlistedRole() public pure override returns (bytes32) {
        return M_GLOBAL_GREENLISTED_ROLE;
    }
}
```

Only role-name overrides. **No logic changes.** All redemption logic lives
in `RedemptionVault.sol` (request path) and `RedemptionVaultWithAave.sol`
(instant path only).

---

## `RedemptionVaultWithAave` — relevant overrides (none on request path)

Source: `contracts/RedemptionVaultWithAave.sol`

This contract overrides ONLY `_redeemInstant` (to source USDC liquidity from
an Aave V3 pool by burning aTokens when the vault's spot balance is short).
It does NOT override:

- `_redeemRequest`
- `_approveRequest`
- `_validateLiquidity`

So everything on the request path (our path) inherits unchanged from
`RedemptionVault.sol`.

```solidity
function _redeemInstant(
    address tokenOut,
    uint256 amountMTokenIn,
    uint256 minReceiveAmount,
    address recipient
)
    internal
    override
    returns (
        CalcAndValidateRedeemResult memory calcResult,
        uint256 amountTokenOutWithoutFee
    )
{
    // ... [full body in source, omitted: not on our path]
    // The notable additions vs RedemptionVault:
    //   - amountTokenOutWithoutFee is computed at the truncated 6-dec level
    //     then converted back to base18 for the min-amount check.
    //   - Calls _checkAndRedeemAave(tokenOutCopy, ...) to top up the vault's
    //     USDC balance via pool.withdraw() if internal balance is short.
}

function _checkAndRedeemAave(address tokenOut, uint256 amountTokenOut)
    internal
{
    uint256 contractBalanceTokenOut = IERC20(tokenOut).balanceOf(address(this));
    if (contractBalanceTokenOut >= amountTokenOut) return;

    IAaveV3Pool pool = aavePools[tokenOut];
    require(address(pool) != address(0), "RVA: no pool for token");

    uint256 missingAmount = amountTokenOut - contractBalanceTokenOut;

    address aToken = pool.getReserveAToken(tokenOut);
    require(aToken != address(0), "RVA: token not in Aave pool");

    uint256 aTokenBalance = IERC20(aToken).balanceOf(address(this));
    require(aTokenBalance >= missingAmount, "RVA: insufficient aToken balance");

    uint256 withdrawnAmount = pool.withdraw(tokenOut, missingAmount, address(this));
    require(withdrawnAmount >= missingAmount, "RVA: withdrawn < needed");
}
```

> Aave plumbing is irrelevant to the request flow. Settlement (`approveRequest`)
> pulls USDC from `requestRedeemer` (an external address) — NOT from the vault's
> internal balance or its Aave aTokens. The "WithAave" suffix only matters
> for the instant path.

---

## Sanity-check matrix (verified from source above)

| Claim in specs.yaml                                               | Status    | Evidence                                                                                                                                |
| ----------------------------------------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Request path uses `tokensConfig[USDC].fee` only (no instantFee)   | OK        | `_calcAndValidateRedeem` calls `_getFeeAmount(..., isInstant=false, additionalFee=0)`; `instantFee` branch is gated by `if (isInstant)` |
| `Request.sender = recipient` (3-arg variant)                      | OK        | `_redeemRequest` writes `sender: recipient` into the struct                                                                             |
| `tokenOutRate = 1e18` for USDC                                    | OK        | `tokensConfig[USDC].stable == true` → `_getTokenRate` returns `STABLECOIN_RATE = 10**18`                                                |
| `currentRequestId` pre-increment                                  | OK        | `requestId = currentRequestId.current(); currentRequestId.increment();`                                                                 |
| `redeemRequest` reverts if mGLOBAL feed unhealthy                 | OK        | `_redeemRequest` calls `mTokenDataFeed.getDataInBase18()` directly                                                                      |
| `approveRequest` not gated by variationTolerance                  | OK        | `approveRequest` passes `isSafe = false` to `_approveRequest`                                                                           |
| `rejectRequest` does NOT refund mGLOBAL                           | OK        | Only sets `status = Canceled`; no transfer back                                                                                         |
| MGlobal wrapper only overrides roles                              | OK        | `MGlobalRedemptionVaultWithAave.sol` body is 4 lines + gap                                                                              |
| `RequestStatus` is `{None=0, Pending=1, Processed=2, Canceled=3}` | **WRONG** | Actual: `{Pending=0, Processed=1, Canceled=2}` (see callout #4)                                                                         |

---

## Files inspected

- `contracts/products/mGLOBAL/MGlobalRedemptionVaultWithAave.sol`
- `contracts/RedemptionVault.sol`
- `contracts/RedemptionVaultWithAave.sol`
- `contracts/abstract/ManageableVault.sol`
- `contracts/interfaces/IRedemptionVault.sol`
- `contracts/interfaces/IManageableVault.sol`
