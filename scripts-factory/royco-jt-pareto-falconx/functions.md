# Royco Junior Tranche - Pareto FalconX - Function Implementations

Chain: ethereum mainnet (chainId 1)
Generated: 2026-05-19T00:00:00Z

> **This is the JT sibling of `scripts-factory/royco-st-pareto-falconx/functions.md`.** The middleware contracts (Pareto IdleCDOEpochVariant, Pareto IdleCreditVault, Pareto KeyringIdleWhitelist, Royco Kernel, Royco AccessManager) are 1:1 the same instances and run the same code paths as the ST. **By design, this document does NOT re-derive their Solidity bodies.** For sections 1, 2, 4, and 5 below (Pareto CDO, FalconXUSDC, Royco Kernel, RoycoFactory) the canonical source-quotes are in the ST sibling — read that file alongside this one. The only material divergences (JT-impl source, `convertToAssets` slot semantics, AccessManager role id, coverage-gate direction) are spelled out in section 3 and at the bottom of this file.

## Overview

This integration spans the same 4 contract families as the ST sibling, plus a JT-specific tranche implementation.

| Layer                                | Proxy                                        | Implementation                                                                                                 | Verified                                                                                                                                                                                | Source                                                                                                                                                                                                                        |
| ------------------------------------ | -------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pareto IdleCDOEpochVariant           | `0x433D5B175148dA32Ffe1e1A37a939E1b7e79be4d` | `0x8016E6f35a4B32a5Ea4c3919418039C7DaffCcaf`                                                                   | YES                                                                                                                                                                                     | See ST sibling `functions.md` §1. Same instance.                                                                                                                                                                              |
| Pareto IdleCreditVault (FalconXUSDC) | `0x17E9Ab2992dfecBe779a06A92a6cDB9fE6aEeEf3` | (Pareto repo, Sol 0.8.10)                                                                                      | YES (by analogy)                                                                                                                                                                        | See ST sibling `functions.md` §2. Same instance.                                                                                                                                                                              |
| Pareto KeyringIdleWhitelist          | `0x6a6a91c7c7c05f9f6b8bc9f6e5ea231e460450e3` | (non-proxy)                                                                                                    | YES                                                                                                                                                                                     | See ST sibling `functions.md` §1 (Keyring sub-section). Same instance.                                                                                                                                                        |
| **Royco JUNIOR Tranche (this pool)** | `0x8e0EC43e51B88AA2324102E1A3D667822bE51a6d` | `0x1de7ca1aae266031eacd7bd9da40593d9af5e401`                                                                   | **UNVERIFIED** on Etherscan & Sourcify. Body recovered from verified sibling JT impl `0xd10deF48855fFbb525f23eBbd67bA19f94B80F9E` (syrupUSDC JT, Sol 0.8.34, Blockscout partial match). | Verified twin: `RoycoJuniorTranche.sol` + `RoycoVaultTranche.sol`. Only `TRANCHE_TYPE() == JUNIOR` (and the deposit/redeem dispatch to `kernel.jt*`) differs from the ST sibling impl.                                        |
| Royco Kernel (this market)           | `0x15bb63C07740ff972F76716cAcC5766f0C641791` | `0xAA9631dF7ec04AbB825bD6a663f96c9BB3Ed7e1e` (accountant subimpl `0x288bc6a8600d0bc1f179816c3b3001b00566c110`) | NOT verified                                                                                                                                                                            | Same recovery as ST sibling §4 (verified sibling `0xeb7c3a4a72b4c201e50add11003ada2566d276ea`). Same `RoycoKernel.sol` base + same `previewSyncTrancheAccounting` / `_deriveTrancheAssetClaims` path used for both ST and JT. |
| RoycoFactory (AccessManager)         | `0x7cC6fB28eC7b5e7afC3cB3986141797ffc27253C` | `0x34DB2f4215e55ec8e2c3dE0a826935EBF158be77`                                                                   | YES (Sourcify partial)                                                                                                                                                                  | Same `AccessManagerUpgradeable` base — see ST sibling §5. Only the role-id mapping for the JT selectors differs (`JT_LP` instead of `ST_LP`).                                                                                 |

| Function                                                              | Contract                              | Type / Status                                             |
| --------------------------------------------------------------------- | ------------------------------------- | --------------------------------------------------------- |
| `depositAA(uint256)`                                                  | IdleCDOEpochVariant                   | Path A deposit — **see ST §1**, identical                 |
| `depositDuringEpoch(uint256,address)`                                 | IdleCDOEpochVariant                   | Path B deposit — **see ST §1**, identical                 |
| `requestWithdraw(uint256,address)`                                    | IdleCDOEpochVariant                   | Phase 1 burn — **see ST §1**, identical                   |
| `claimWithdrawRequest()`                                              | IdleCDOEpochVariant → IdleCreditVault | Phase 2 USDC payout — **see ST §1**, identical            |
| `tranchePrice(address)` / epoch getters / `isWalletAllowed(address)`  | IdleCDOEpochVariant + Keyring         | Views — **see ST §1**, identical                          |
| `FalconXUSDC.balanceOf(caliber)` / `_transfer` lockout                | IdleCreditVault                       | Accounting receipt — **see ST §2**, identical             |
| **`RoycoJuniorTranche.TRANCHE_TYPE()`**                               | RoycoJuniorTranche                    | Returns `TrancheType.JUNIOR` — JT-only marker; §3.1       |
| **`RoycoVaultTranche.deposit(uint256,address)`** (JT instance)        | RoycoVaultTranche (JT)                | Dispatches to `kernel.jtDeposit` — §3.2                   |
| **`RoycoVaultTranche.redeem(uint256,address,address)`** (JT instance) | RoycoVaultTranche (JT)                | Dispatches to `kernel.jtRedeem` — §3.3                    |
| **`RoycoVaultTranche.convertToAssets(uint256)`** (JT instance)        | RoycoVaultTranche (JT)                | Returns `AssetClaims` from JT POV — §3.4 (slot semantics) |
| `kernel.jtDeposit / jtRedeem` (coverage gate inversion)               | RoycoKernel                           | §3.5                                                      |
| `RoycoFactory.canCall` for JT selectors                               | RoycoFactory                          | §3.6 — role id `0xded17f6f89970f45` (JT_LP)               |

---

## 1. Pareto IdleCDOEpochVariant

**No JT-specific divergence here.** The middleware contract is the same instance, the Keyring gate is the same, the AA tranche mint/burn arithmetic is the same. See `scripts-factory/royco-st-pareto-falconx/functions.md` §1 for the verified Solidity bodies of:

- `depositAA(uint256)` and `_deposit(uint256,address)` (path A — between epochs)
- `depositDuringEpoch(uint256,address)` (path B — mid-epoch)
- `requestWithdraw(uint256,address)` + `_withdrawOps`
- `claimWithdrawRequest()` (the strategy passthrough)
- `tranchePrice(address)` and the epoch-state public getters
- `isWalletAllowed(address)` + KeyringIdleWhitelist

The blueprint dispatch logic (`isEpochRunning ? depositDuringEpoch : depositAA`, `requestWithdraw` only when `allowAAWithdrawRequest == true`, `claimWithdrawRequest` after at least one `stopEpoch`) is unchanged from the ST.

> **The only operational change at this layer for JT:** the caller is now the JT contract, but the Keyring check (`isWalletAllowed(msg.sender)`) is on the **caliber**, not the tranche contract — so it's the same wallet credentialed in policy 18. Already true on the existing fork.

---

## 2. Pareto IdleCreditVault (FalconXUSDC)

**No JT-specific divergence.** See ST sibling §2 verbatim. The receipt token is non-transferrable while solvent (`canTransfer == false`), `balanceOf(caliber)` returns USDC owed at next stopEpoch in 6-dec, and only the CDO can mint/burn it. The accounting flow adds `FalconXUSDC.balanceOf(caliber)` directly to the USDC total — same recipe.

---

## 3. Royco JUNIOR Tranche — JT-specific code

Proxy `0x8e0EC43e51B88AA2324102E1A3D667822bE51a6d`, impl `0x1de7ca1aae266031eacd7bd9da40593d9af5e401`. **Impl is unverified on Etherscan and on Sourcify.** Confirmed via:

```bash
$ curl https://sourcify.dev/server/v2/contract/1/0x1De7cA1Aae266031eAcD7Bd9Da40593d9aF5e401
{"match":null,"creationMatch":null,"runtimeMatch":null,"chainId":"1","address":"..."}
```

A verified sibling `RoycoJuniorTranche` impl exists on **another Royco JT market** (syrupUSDC JT, impl `0xd10deF48855fFbb525f23eBbd67bA19f94B80F9E`, Sourcify/Blockscout partial match, Solidity 0.8.34, Royco repo). It is the same `RoycoJuniorTranche` thin contract sitting over the same `RoycoVaultTranche` base — the **only difference between two JT impls** in the Royco V2 deployment matrix is the immutable `ASSET` and `KERNEL` set at construction. The behaviour and storage layout are identical; the bodies quoted below are the verified twin's bytecode-equivalent source.

### 3.1 `RoycoJuniorTranche.TRANCHE_TYPE()` — the JT marker

This is the **only** function that distinguishes the JT impl from the ST impl. Both inherit `RoycoVaultTranche`; only this override changes the kernel dispatch from `st*` to `jt*`.

```solidity
// src/tranches/RoycoJuniorTranche.sol  (verified sibling)
contract RoycoJuniorTranche is RoycoVaultTranche {
    constructor(address _asset, address _kernel) RoycoVaultTranche(_asset, _kernel) { }

    function initialize(RoycoTrancheInitParams calldata _jtParams) external initializer {
        __RoycoTranche_init(_jtParams);
    }

    function TRANCHE_TYPE() public pure virtual override(RoycoVaultTranche) returns (TrancheType) {
        return TrancheType.JUNIOR;
    }
}
```

For comparison, the ST sibling is the same contract with `return TrancheType.SENIOR;` instead — see ST functions.md §3. **Everything else** (`deposit`, `redeem`, `convertToAssets`, `_checkCanCall`, `whenNotPaused`, `_update` -> `preTrancheBalanceUpdateHook`) is inherited verbatim from `RoycoVaultTranche`.

### 3.2 `RoycoVaultTranche.deposit(uint256,address)` — JT instance

The base class body is identical to the ST sibling's quote (ST §3 `deposit`), but with `TRANCHE_TYPE() == TrancheType.JUNIOR` the kernel call resolves to `IRoycoKernel(KERNEL).jtDeposit(_assets)`:

```solidity
// src/tranches/base/RoycoVaultTranche.sol  (verified sibling, lines 69-92)
function deposit(TRANCHE_UNIT _assets, address _receiver)
    public virtual override(IRoycoVaultTranche)
    whenNotPaused
    restricted                                                      // <-- AccessManaged gate
    returns (uint256 shares)
{
    require(_receiver != address(0), ERC20InvalidReceiver(address(0)));

    // Pull AA tranche tokens to the kernel:
    IERC20(ASSET).safeTransferFrom(msg.sender, KERNEL, toUint256(_assets));

    // Hand off to the kernel — for the JT this is jtDeposit:
    (NAV_UNIT valueAllocated, NAV_UNIT effectiveNAVToMintAt) =
        (TRANCHE_TYPE() == TrancheType.SENIOR
            ? IRoycoKernel(KERNEL).stDeposit(_assets)
            : IRoycoKernel(KERNEL).jtDeposit(_assets));   // <-- THIS branch on the JT

    require(valueAllocated != ZERO_NAV_UNITS, INVALID_VALUE_ALLOCATED());

    shares = _convertToShares(
        valueAllocated, totalSupply(), effectiveNAVToMintAt, Math.Rounding.Floor);
    require(shares != 0, MUST_MINT_NON_ZERO_SHARES());

    _mint(_receiver, shares);
    emit Deposit(msg.sender, _receiver, _assets, shares);
}
```

> **Blueprint impact unchanged from ST**: AA is pulled `caliber -> KERNEL`, not `caliber -> JT`. Approve target = JT (`0x8e0E…1a6d`); `Transfer` recipient = Kernel (`0x15bb…1791`). The selector is `0x6e553f65` (same as ERC4626 deposit — see §3.6 for the role gate).

### 3.3 `RoycoVaultTranche.redeem(uint256,address,address)` — JT instance

```solidity
// src/tranches/base/RoycoVaultTranche.sol  (verified sibling, lines 95-126)
function redeem(uint256 _shares, address _receiver, address _owner)
    public virtual override(IRoycoVaultTranche)
    whenNotPaused
    restricted                                                      // <-- AccessManaged gate
    returns (AssetClaims memory claims)
{
    require(_receiver != address(0), ERC20InvalidReceiver(address(0)));
    require(_shares != 0, MUST_REQUEST_NON_ZERO_SHARES());

    if (msg.sender != _owner) {
        _spendAllowance(_owner, msg.sender, _shares);
    }

    // For the JT this is jtRedeem (coverage-gated on the kernel side — see §3.5):
    claims =
    (TRANCHE_TYPE() == TrancheType.SENIOR
            ? IRoycoKernel(KERNEL).stRedeem(_shares, _receiver, false)
            : IRoycoKernel(KERNEL).jtRedeem(_shares, _receiver, false));   // <-- THIS branch on the JT

    _burn(_owner, _shares);
    emit Redeem(msg.sender, _receiver, claims, _shares);
}
```

Selector `0xba087652`.

### 3.4 `convertToAssets(uint256)` — JT slot semantics (CRITICAL divergence)

```solidity
// src/tranches/base/RoycoVaultTranche.sol  (verified sibling, lines 233-237)
function convertToAssets(uint256 _shares)
    public view virtual override(IRoycoVaultTranche)
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
        IRoycoKernel(KERNEL).previewSyncTrancheAccounting(TRANCHE_TYPE());   // <-- TRANCHE_TYPE = JUNIOR here
}
```

The struct shape is fixed by `Types.sol`:

```solidity
// src/libraries/Types.sol  (verified sibling, lines 33-37)
struct AssetClaims {
    TRANCHE_UNIT stAssets;   // slot 0 in the ABI tuple
    TRANCHE_UNIT jtAssets;   // slot 1
    NAV_UNIT     nav;        // slot 2
}
```

`UtilsLib.scaleAssetClaims` simply multiplies each field by `_shares / trancheTotalShares`:

```solidity
// src/libraries/UtilsLib.sol  (verified sibling)
function scaleAssetClaims(AssetClaims memory _claims, uint256 _shares, uint256 _totalTrancheShares)
    internal pure returns (AssetClaims memory scaledClaims)
{
    scaledClaims.nav      = _claims.nav.mulDiv(_shares, _totalTrancheShares, Math.Rounding.Floor);
    scaledClaims.stAssets = _claims.stAssets.mulDiv(_shares, _totalTrancheShares, Math.Rounding.Floor);
    scaledClaims.jtAssets = _claims.jtAssets.mulDiv(_shares, _totalTrancheShares, Math.Rounding.Floor);
}
```

So **on the wire** the tuple is always `(stAssets, jtAssets, nav)`. The slot layout is **role-fixed**, NOT caller-relative: the kernel's `_deriveTrancheAssetClaims(TrancheType, state)` populates the struct fields by tranche role — `stAssets` is the SENIOR tranche's AA claim (populated when ST is solvent-positive), `jtAssets` is the JUNIOR tranche's AA claim (populated when JT is solvent-positive), `nav` is the calling tranche's NAV in USD WAD. Caller perspective does NOT shift the slot order; the only thing it changes is which field is filled in (the ST's vs JT's claim from that POV) and the `nav` value.

**Definitive empirical verification on fork b0f9ddf1 at the post-deposit snapshot** (full citation + bootstrap cross-check in `execution-account.md`):

| State                  | Caller | `convertToAssets(totalSupply)[0]` (stAssets) | `convertToAssets(totalSupply)[1]` (jtAssets) | `[2]` (nav)       |
| ---------------------- | ------ | -------------------------------------------- | -------------------------------------------- | ----------------- |
| JT-only (ST empty)     | JT     | **0** (ST has no claim)                      | **46,071.09 AA** ← JT's own AA claim         | 49,853.53 USD-WAD |
| JT + ST (1k bootstrap) | JT     | **0** (still — solvent state, no writedown)  | **46,071.09 AA** ← JT's claim unchanged      | 49,853.53 USD-WAD |
| JT + ST                | ST     | **921.42 AA** ← ST's own AA claim            | 0                                            | 997.07 USD-WAD    |

And the kernel's authoritative `previewSyncTrancheAccounting(JUNIOR)` returns `claims.jtAssets = 46_071.09e18` in slot 1 of the AssetClaims struct — proving by source that the JT's AA claim lives in slot 1.

So:

- For the ST, slot 0 = stAssets = ST's own AA claim. Read with `getTupleWord(_, 0)`.
- For the JT, slot 1 = jtAssets = JT's own AA claim. Read with `getTupleWord(_, 1)`.
- Slot 0 from a JT call carries a value ONLY in the senior-writedown state (when ST has been reassigned junior assets). In the solvent state it's always 0.

The Stage-1 reading (recorded in `progress.yaml.stages.1_specs.notes` and previously asserted here) that "JT.totalAssets() == JT.convertToAssets(totalSupply)[0]" was a misindexing of the tuple — on this fork at the post-deposit snapshot, `JT.totalAssets()[0] = 0` (NOT the JT's claim) and `JT.totalAssets()[1] = 46_071.09 AA` (the JT's claim).

**Blueprint implication** (consistent with `specs.yaml.helpers.bytes32_helper` after the slot-resolution fix):

```
jt_aa_per_share = getTupleWord(JT.convertToAssets(shares), 1)        // index 1 — jtAssets in role-fixed layout
total_aa        = jt_aa_per_share + AA.balanceOf(caliber)
usdc            = total_aa * tranchePrice(AA) / 1e18 + FalconXUSDC.balanceOf(caliber)
```

Do NOT sum slot 0 + slot 1: slot 0 is the ST's claim (0 in solvent state, nonzero in writedown). Summing would either be a no-op (solvent) or over-credit the JT (writedown). Use slot 1 only.

### 3.5 Kernel coverage gate — DIRECTION INVERTED for the JT

Per the verified-sibling Kernel quoted in the ST sibling functions.md §4, the four operations route to the accountant as follows:

```solidity
// RoycoKernel.sol  (verified sibling 0xeb7c3a4a72b4c201e50add11003ada2566d276ea — same base for FalconX)
function stDeposit(...) {
    ...
    _postOpSyncTrancheAccountingAndEnforceCoverage(Operation.ST_DEPOSIT);   // <-- enforces coverage
}
function stRedeem(...) {
    ...
    _postOpSyncTrancheAccounting(Operation.ST_REDEEM, ...);                 // <-- NO coverage enforcement
}
function jtDeposit(...) {
    ...
    _postOpSyncTrancheAccounting(Operation.JT_DEPOSIT, ...);                // <-- NO coverage enforcement (BOOTSTRAP path)
}
function jtRedeem(...) {
    ...
    _postOpSyncTrancheAccountingAndEnforceCoverage(Operation.JT_REDEEM);    // <-- enforces coverage (MIRROR of ST_DEPOSIT)
}
```

`_postOpSyncTrancheAccountingAndEnforceCoverage` calls into the accountant subimpl with the post-op `_stRawNAV` and `_jtRawNAV`. The coverage formula (`UtilsLib.computeUtilization`, verified-sibling lines 36-53):

```solidity
function computeUtilization(NAV_UNIT _stRawNAV, NAV_UNIT _jtRawNAV, uint256 _betaWAD, uint256 _coverageWAD, NAV_UNIT _jtEffectiveNAV)
    internal pure returns (uint256 utilization)
{
    if (_stRawNAV == ZERO_NAV_UNITS) return 0;
    if (_jtEffectiveNAV == ZERO_NAV_UNITS) return type(uint256).max;
    utilization = _coverageWAD.mulDiv(
        (_stRawNAV + _jtRawNAV.mulDiv(_betaWAD, WAD, Math.Rounding.Ceil)),
        _jtEffectiveNAV,
        Math.Rounding.Ceil
    );
    // Reverts in the accountant when utilization > liquidationUtilizationWAD.
}
```

> **Operational implications for the JT integration:**
>
> 1. `JT.deposit` is the **unblocked bootstrap path** — it does NOT call `_postOpSyncTrancheAccountingAndEnforceCoverage`, so it succeeds even on an empty market (`jtRawNAV == 0` before the op, JT shares minted, no coverage check). This is the symmetric counterpart of the ST sibling's `open_questions.junior_bootstrap` blocker.
> 2. `JT.redeem` IS coverage-gated. A redeem that drops `jtEffectiveNAV` below the threshold (`coveredExposure / jtEffectiveNAV > liquidationUtilizationWAD` or `coverage < coverageWAD`) reverts inside the accountant. In practice the JT cannot be fully drained while ST shares exist; partial redeems are bounded by the live coverage params. The execution-explorer should size the test redeem accordingly (see `specs.yaml.open_questions.jt_redeem_coverage_sizing`).
>
> `maxRedeem(_owner)` on the JT (verified-sibling lines 283-308) is the on-chain self-bound for this constraint:
>
> ```solidity
> function maxRedeem(address _owner) public view virtual returns (uint256 shares) {
>     uint256 sharesOwned = balanceOf(_owner);
>     (NAV_UNIT claimOnStNAV, NAV_UNIT claimOnJtNAV,
>      NAV_UNIT stMaxWithdrawableNAV, NAV_UNIT jtMaxWithdrawableNAV,
>      uint256 totalSharesAfterMintingFees) =
>         (TRANCHE_TYPE() == TrancheType.SENIOR
>             ? IRoycoKernel(KERNEL).stMaxWithdrawable(_owner)
>             : IRoycoKernel(KERNEL).jtMaxWithdrawable(_owner));
>     if (claimOnStNAV + claimOnJtNAV == ZERO_NAV_UNITS) return 0;
>     uint256 sBasedOnST = claimOnStNAV == ZERO_NAV_UNITS ? sharesOwned
>         : totalSharesAfterMintingFees.mulDiv(stMaxWithdrawableNAV, claimOnStNAV, Math.Rounding.Floor);
>     uint256 sBasedOnJT = claimOnJtNAV == ZERO_NAV_UNITS ? sharesOwned
>         : totalSharesAfterMintingFees.mulDiv(jtMaxWithdrawableNAV, claimOnJtNAV, Math.Rounding.Floor);
>     shares = Math.min(sharesOwned, Math.min(sBasedOnST, sBasedOnJT));
> }
> ```
>
> Calling `JT.maxRedeem(caliber)` returns the largest amount that will pass the coverage check without simulating the revert. This is the cheaper sizing primitive than trial-and-error.

### 3.6 `_checkCanCall` for the JT selectors (JT_LP role)

`AccessManagedUpgradeable._checkCanCall(caller, data)` body is identical to the one quoted in ST functions.md §3 (OpenZeppelin v5.4.0). What changes for the JT is the **role id** that `RoycoFactory.getTargetFunctionRole(target, selector)` returns:

```solidity
// AccessManagerUpgradeable.canCall — relevant branch (unchanged from ST sibling §5)
uint64 roleId = getTargetFunctionRole(target, selector);
(bool isMember, uint32 currentDelay) = hasRole(roleId, caller);
return isMember ? (currentDelay == 0, currentDelay) : (false, 0);
```

Verified on-chain at fork block 0x17d5e3b (calls to `RoycoFactory.getTargetFunctionRole(target, selector)`, recorded in `progress.yaml.stages.1_specs.notes`):

| Target (proxy)       | Selector     | Function                            | Role id (uint64)       | Role id (hex)        | Notes                                                                                                               |
| -------------------- | ------------ | ----------------------------------- | ---------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------- |
| JT `0x8e0E…1a6d`     | `0x6e553f65` | `deposit(uint256,address)`          | `16055754263579004741` | `0xded17f6f89970f45` | **JT_LP role**                                                                                                      |
| JT `0x8e0E…1a6d`     | `0xba087652` | `redeem(uint256,address,address)`   | `16055754263579004741` | `0xded17f6f89970f45` | **JT_LP role — SAME id as deposit. Single grant covers both.**                                                      |
| JT `0x8e0E…1a6d`     | `0xb460af94` | `withdraw(uint256,address,address)` | `0`                    | `0x0`                | PUBLIC_ROLE — not used by integration                                                                               |
| JT `0x8e0E…1a6d`     | `0xa9059cbb` | `transfer(address,uint256)`         | `0`                    | `0x0`                | PUBLIC_ROLE                                                                                                         |
| Kernel `0x15bb…1791` | `0x9c8e2dc0` | `syncTrancheAccounting()`           | `15053450870919821405` | (KERNEL_SYNC role)   | **Shared with ST integration** — no new grant needed for the JT if the caliber already has it from the ST bootstrap |
| ST `0x694A…754b`     | `0x6e553f65` | (ST.deposit, for contrast)          | `9623252227852051139`  | (ST_LP)              | ST_LP, different from JT_LP                                                                                         |

> **Tenderly bypass for the JT_LP grant** (mirrors `scripts-factory/royco-st-pareto-falconx/test-helpers/bootstrap-pareto-falconx-junior.sh`): the role id `0xded17f6f89970f45` is the same `JT_LP_ROLE` the ST bootstrap helper already grants — that helper can be reused verbatim for the JT caliber grant.

---

## 4. Royco Kernel

**No JT-specific divergence** beyond the dispatch routing called out in §3.5 above. The full `syncTrancheAccounting()`, `previewSyncTrancheAccounting(TrancheType)`, `stDeposit/stRedeem/jtDeposit/jtRedeem` flow, the `SyncedAccountingState` struct, and the `withQuoterCache` / `nonReentrant` / `restricted` modifiers are all quoted verbatim from the verified sibling impl in ST functions.md §4.

For accounting:

- `syncTrancheAccounting()` is the same access-restricted state-changing reader. JT integration shares the kernel-sync role grant with the ST integration (role id `15053450870919821405`).
- `previewSyncTrancheAccounting(JUNIOR)` is the view-safe path the JT's `convertToAssets` calls into. **Idempotence caveat is the same**: do not batch multiple `syncTrancheAccounting()` calls in a single tx; call it once, then read.

---

## 5. RoycoFactory (AccessManager)

**No JT-specific divergence** in the contract bodies. The `canCall(caller, target, selector) -> (immediate, delay)` and `hasRole(roleId, account) -> (isMember, executionDelay)` paths are the OpenZeppelin v5.4.0 bodies quoted in ST functions.md §5. What differs from the ST integration is the role-id mapping for the JT selectors — see §3.6 above for the verified mapping.

For the integration:

```solidity
// pre-submit check, off-chain:
RoycoFactory.canCall(caliber, ROY_JT, 0x6e553f65) -> (true, 0)   // deposit (JT_LP)
RoycoFactory.canCall(caliber, ROY_JT, 0xba087652) -> (true, 0)   // redeem  (JT_LP, same role)
RoycoFactory.canCall(caliber, KERNEL, 0x9c8e2dc0) -> (true, 0)   // sync    (KERNEL_SYNC, shared with ST)
```

> **Tenderly bypass: same recipe as the ST bootstrap helper.** Impersonate the AccessManager admin (`RoycoFactory.getRoleAdmin(JT_LP_ROLE)`) and call `grantRole(JT_LP_ROLE, caliber, 0)`. The existing `bootstrap-pareto-falconx-junior.sh` already grants `JT_LP_ROLE = 0xded17f6f89970f45` to the caliber on this vnet.

---

## Citations / Sibling references

- **ST sibling, primary upstream:** `scripts-factory/royco-st-pareto-falconx/functions.md` — Pareto IdleCDOEpochVariant, FalconXUSDC, Royco Kernel, RoycoFactory verified bodies. Reuse for sections 1, 2, 4, 5.
- **JT verified twin (Blockscout, partial match, Solidity 0.8.34):** `0xd10deF48855fFbb525f23eBbd67bA19f94B80F9E` — Royco V2 syrupUSDC JT impl. Source files `RoycoJuniorTranche.sol`, `RoycoVaultTranche.sol`, `UtilsLib.sol`, `Types.sol` cited verbatim in §3. Behaviour for the FalconX JT impl `0x1de7ca1aae266031eacd7bd9da40593d9af5e401` is identical apart from the immutable `(ASSET, KERNEL)` set in the constructor.
- **Kernel verified twin (Sourcify, partial match):** `0xeb7c3a4a72b4c201e50add11003ada2566d276ea` — `RoycoKernel.sol` base (`Identical_ERC4626_ST_JT_SharePriceToChainlinkOracle_Kernel`). The JT/ST deposit/redeem dispatch and `_postOpSyncTrancheAccountingAndEnforceCoverage` path are in this base class.
- **Sibling JT blueprints (different middleware, same Royco JT shape):** `blueprints/royco/jt-syrupusdc/`, `blueprints/royco/jt-stcusd/` — same `deposit(uint256,address)` / `redeem(uint256,address,address)` selectors against a different underlying ERC4626 asset.
- **Pareto integrators docs:** https://docs.pareto.credit/developers/integrators/smart-contract — `depositAA` / `depositDuringEpoch` / `requestWithdraw` / `claimWithdrawRequest` flow and Keyring policy 18 gate.

## Coverage of fetch failures

| Impl                                                                     | Status                             | Mitigation                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------------------------------------ | ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `0x1de7ca1aae266031eacd7bd9da40593d9af5e401` (this JT impl)              | Unverified on Etherscan & Sourcify | Bodies recovered from verified sibling JT `0xd10deF…F9E` (syrupUSDC JT, same `RoycoJuniorTranche` + `RoycoVaultTranche` source files).                                                                                                                                                                     |
| `0xAA9631dF7ec04AbB825bD6a663f96c9BB3Ed7e1e` (this market's kernel impl) | Unverified                         | Same as ST sibling §4: recovered from verified sibling `0xeb7c3a…6ea`.                                                                                                                                                                                                                                     |
| `0x288bc6a8600d0bc1f179816c3b3001b00566c110` (accountant subimpl)        | Unverified                         | Same as ST sibling: accountant exact revert string for the JT coverage gate cannot be confirmed from source. Execution-explorer should capture the revert reason on the first oversized `JT.redeem` to pin it down. Expected error family: `RoycoAccountant_CoverageNotMet` / `RoycoAccountant: coverage`. |

## Summary of divergences vs ST sibling (for the downstream stages)

1. **JT impl source** — only `TRANCHE_TYPE() == JUNIOR` differs from the ST impl. The kernel dispatch picks `jtDeposit` / `jtRedeem` instead of `stDeposit` / `stRedeem`.
2. **AccessManager role id** for `JT.deposit` and `JT.redeem` is `0xded17f6f89970f45` (JT_LP). **Both selectors share the same role id**, so a single `grantRole(JT_LP_ROLE, caliber, 0)` covers both flows. `Kernel.syncTrancheAccounting` keeps role `15053450870919821405`, which is shared with the ST integration.
3. **Coverage gate inverted.** `JT.deposit` is the bootstrap path (no coverage check). `JT.redeem` IS coverage-gated — fully redeeming a JT position is impossible while ST shares exist. Use `JT.maxRedeem(caliber)` to size test redeems.
4. **`convertToAssets` slot semantics.** Wire format is `(stAssets, jtAssets, nav)` and the layout is **role-fixed**: slot 0 is always the SENIOR tranche's AA claim, slot 1 is always the JUNIOR tranche's AA claim, slot 2 is the calling tranche's NAV. For the JT, the JT's own AA claim is in **slot 1**. Use `getTupleWord(_, 1)` for JT accounting (and `getTupleWord(_, 0)` for ST accounting). Do NOT sum slot 0 + slot 1 on the JT — slot 0 is the ST's claim, zero in the solvent state.
