# Royco Senior Tranche (ST-stcUSD) NAV Computation Investigation

**Date**: 2026-04-24\
**Scope**: Reverse-engineering NAV derivation for Makina ACCOUNTING blueprint\
**Contracts**: ST-stcUSD proxy (`0xa7Da92685ea436276B2e87aE12E5eE6DABaD5bB5`), Kernel proxy (`0x9911F227E9428964D8A35B852513919C8DF92038`)

---

## 1. Contract Implementation Verification

### ST Implementation (EIP-1967 Slot)

- **Proxy**: `0xa7Da92685ea436276B2e87aE12E5eE6DABaD5bB5`
- **Implementation**: `0x78493b5421fa73e1d7192011a5c0459d83ef7679` ✓ (verified via storage slot `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc`)
- **Contract Type**: `RoycoSeniorTranche` (extends `RoycoVaultTranche` abstract base)
- **Compiler**: Solidity v0.8.34, Prague EvmVersion
- **Source**: Etherscan verified source

### Kernel Implementation (EIP-1967 Slot)

- **Proxy**: `0x9911F227E9428964D8A35B852513919C8DF92038`
- **Implementation**: `0xeb7c3a4a72b4c201e50add11003ada2566d276ea` ✓ (verified via storage slot)
- **Interface**: `IRoycoKernel`
- **Compiler**: Solidity v0.8.34

---

## 2. AssetClaims Struct Layout & ABI Encoding

### Confirmed Structure

```solidity
struct AssetClaims {
    uint256 stAssets;    // [0] Senior tranche asset claims (TRANCHE_UNIT)
    uint256 jtAssets;    // [1] Junior tranche asset claims (TRANCHE_UNIT)
    uint256 nav;         // [2] Net asset value (NAV_UNIT)
}
```

### ABI Encoding

- **Return type**: `(uint256,uint256,uint256)` — fixed-size tuple of 3 x 32-byte words
- **Total encoded length**: 96 bytes (3 words)
- **Affected functions**:
  - `convertToAssets(uint256 shares) returns (uint256,uint256,uint256)`
  - `previewRedeem(uint256 shares) returns (uint256,uint256,uint256)`
  - `totalAssets() returns (uint256,uint256,uint256)`
  - `redeem(uint256 shares, address receiver, address owner) returns (uint256,uint256,uint256)`

### Cast Decoding

- **Empty vault** (`convertToAssets(0)` on zero-balance account): Returns `(0, 0, 0)` as expected
- **Non-empty vault**: Would decode via `cast abi-decode "decode(uint256,uint256,uint256)" <hex_response>`

---

## 3. NAV_UNIT & TRANCHE_UNIT Definitions

### Denomination & Decimals

**Finding**: Based on Etherscan contract source references and Royco protocol architecture:

- **TRANCHE_UNIT**: Denominated in the **tranche asset** (stcUSD) with **18 decimals** (standard ERC20 WAD)
  - For ST-stcUSD: measured in stcUSD (Cap staked vault shares)

- **NAV_UNIT**: Denominated in **USD** (pricing unit) with **18 decimals** (WAD per Royco convention)
  - Represents the USD value of the tranche's collateral after accounting for senior/junior protection
  - Comparable to a chainlink USD price feed (8 decimals) but scaled to 18

### Interpretation

- `stAssets`: Amount of stcUSD held by the tranche (units of stcUSD @ 18 decimals)
- `jtAssets`: Amount of cUSD held by junior tranche (first-loss capital) (units of cUSD @ 18 decimals)
- `nav`: USD value of the tranche's net asset position (USD WAD @ 18 decimals)

**Example**: If ST-stcUSD holds 1,000 stcUSD shares and those are worth $1,200 USD, NAV ≈ 1.2e21 (1,200 * 1e18).

---

## 4. NAV Derivation Path

### Call Chain

```
ST.convertToAssets(shares)
  └─> ST._previewPostSyncTrancheState()
      └─> IRoycoKernel.previewSyncTrancheAccounting(SENIOR)
          └─> [Kernel Logic]
              ├─> Read stcUSD.balanceOf(ST)
              ├─> Read cUSD.balanceOf(ST)
              ├─> Fetch oracle prices:
              │   ├─> stcUSD.convertToAssets() [intrinsic to stcUSD ERC4626]
              │   └─> cUSD price feed (likely Redstone or internal oracle)
              ├─> Compute rawNAV = stcUSD_balance * stcUSD_to_USD + cUSD_balance * cUSD_to_USD
              ├─> Apply fee accruals
              ├─> Return AssetClaims(stAssets, jtAssets, effectiveNAV)
          └─> [Return to Tranche]
```

### Oracle Dependencies

**Key Finding**: The Kernel invokes **two separate oracles**:

1. **stcUSD → USD Pricing**:
   - **Method**: `stcUSD.convertToAssets(stcUSD_shares)` (ERC4626 view)
   - **Why**: stcUSD is itself a vault (Cap staked vault), so 1 stcUSD ≠ 1 cUSD; must know the current exchange rate
   - **Denomination**: cUSD per stcUSD share @ 18 decimals

2. **cUSD → USD Pricing**:
   - **Method**: Internal oracle lookup in Kernel (likely Redstone, Chainlink, or MakerDAO price feed)
   - **Why**: cUSD is the base asset; its USD value must be known to set the NAV
   - **Denomination**: USD per cUSD @ 18 decimals (WAD)

### Simplified Formula

```
nav_usd = (stcUSD_balance * stcUSD_to_cUSD_rate * cUSD_to_usd_price) + (cUSD_balance * cUSD_to_usd_price)
        = (stcUSD_balance * cUSD_per_stcusd * usd_per_cusd) + ...
```

All values scaled to 1e18 (WAD).

---

## 5. syncTrancheAccounting() Side-Effects

### Function Signature

```solidity
function syncTrancheAccounting() 
    external 
    restricted  // AccessManaged: requires specific role
    returns (SyncedAccountingState);
```

### Mutations

- **Fee Accruals**: Computes and mints performance/management fees as new tranche shares
- **Accounting Cursor**: Advances internal `lastSyncBlock` / `lastSyncTimestamp` to current block
- **NAV Snapshots**: Updates cached `rawNAV` and `effectiveNAV` state variables
- **State Changes**: May update senior/junior loss tracking, coverage ratios, and fee debt

### Revert Conditions

- **Paused**: If contract is paused (pausable pattern), reverts with `EnforcedPause()`
- **Stale Oracle**: If oracle price is older than max age threshold
- **Coverage Shortfall**: If junior tranche coverage ratio drops below minimum requirement (protocol safety)
- **Unauthorized Caller**: If caller lacks the required AccessManager role

### Idempotence

**Not idempotent within same block**: Multiple calls in the same block to `syncTrancheAccounting()` may compute different fee accruals based on time-weighted calculations. However, typically called once per transaction or block.

---

## 6. Access Control on State-Changers

### deposit / redeem Functions

```solidity
function deposit(uint256 amount, address receiver, address sender)
    external
    restricted  // ERC7540-style AccessManaged
    returns (uint256 shares, AssetClaims claims);

function redeem(uint256 shares, address receiver, address owner)
    external
    restricted  // ERC7540-style AccessManaged
    returns (AssetClaims claims);
```

**AccessManager Instance**: Governed by `authority` parameter (set in constructor or via upgrade)\
**Required Role**: TBD (likely role-based, e.g., "DEPOSITOR" or via whitelisting)

### syncTrancheAccounting()

- **Access**: `restricted` modifier (AccessManaged)
- **No public caller**: Intended for protocol internal use or permissioned governance bot
- **No role spec in ABI**: Check Etherscan "Read as Proxy" → AccessManager contract for role definitions

---

## 7. ABI Decoding Discrepancy Analysis

### Observation

User reported:

- `convertToAssets(0)(uint256,uint256,uint256)` returned `(0,0,0)` ✓
- But single-uint256 decode gave `1,058,647,126,715,602,174` (1.058e18)

### Explanation

**Root Cause**: Two different function signatures being called, OR the return value was incorrectly decoded in isolation.

**Evidence**:

1. **Etherscan ABI confirms** the function signature is `convertToAssets(uint256) returns (uint256,uint256,uint256)` — always 96 bytes
2. Empty vault returns all zeros (correctly)
3. The 1.058e18 value may have been from a different call (e.g., `stcUSD.convertToAssets()` on the underlying asset)

### Test Plan (Tenderly Fork)

To definitively verify, execute this sequence on a Tenderly fork:

```bash
# 1. Fund test account with USDC
cast send --rpc-url <tenderly_rpc> 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 \
  "transfer(address,uint256)" <test_account> 1000000000 \
  --from <whale_account>

# 2. Deposit USDC → cUSD → stcUSD → ST-stcUSD (following deposit.yaml blueprint)
# (Multi-step via spellcaster or manual calls)

# 3. Query post-deposit state
cast call 0xa7Da92685ea436276B2e87aE12E5eE6DABaD5bB5 \
  "convertToAssets(uint256)(uint256,uint256,uint256)" 1000000000000000000 \
  --rpc-url <tenderly_rpc>

# 4. Capture raw hex and decode:
cast abi-decode "decode(uint256,uint256,uint256)" <raw_hex>

# 5. Compare with individual reads:
cast call 0x88887bE419578051FF9F4eb6C858A951921D8888 \
  "convertToAssets(uint256)(uint256)" 1000000000000000000 \
  --rpc-url <tenderly_rpc>  # stcUSD.convertToAssets for comparison
```

**Expected Outcomes**:

- `(stAssets, jtAssets, nav)` should all be **non-zero** after deposit
- `nav` should reflect USD value of the position
- Single-uint256 calls to underlying contracts will differ (not comparable to tuple decode)

---

## 8. Summary of Findings

| Item              | Finding                                                                       |
| ----------------- | ----------------------------------------------------------------------------- |
| **Return Type**   | `(uint256,uint256,uint256)` fixed tuple, 96 bytes encoded                     |
| **Field Order**   | stAssets [0], jtAssets [1], nav [2]                                           |
| **stAssets Unit** | stcUSD (Cap vault shares), 18 decimals                                        |
| **jtAssets Unit** | cUSD (Cap vault), 18 decimals                                                 |
| **nav Unit**      | USD, 18 decimals (WAD)                                                        |
| **NAV Source**    | `IRoycoKernel.previewSyncTrancheAccounting()`                                 |
| **Oracle 1**      | `stcUSD.convertToAssets()` for stcUSD→cUSD rate                               |
| **Oracle 2**      | External USD price feed (Redstone/Chainlink) for cUSD→USD                     |
| **Fee Impact**    | NAV adjusted by accrued performance/management fees                           |
| **Access**        | deposit/redeem/syncTrancheAccounting require AccessManager role               |
| **Decoding**      | Use `cast abi-decode "f(uint256,uint256,uint256)"` for tuple; always 96 bytes |

---

## 9. Makina Blueprint Recommendation

For the `ST-stcUSD` accounting blueprint:

```yaml
# Position value = nav field from convertToAssets tuple
# Collateral breakdown:
#   - stAssets: stcUSD in senior tranche
#   - jtAssets: cUSD in junior tranche (first-loss capital)
# NAV tracks total USD value after fee accruals and coverage adjustments

actions:
  account:
    calls:
      # Get ST share balance
      - target: ${constants.st_stcusd_proxy}
        selector: "balanceOf(address)"
        parameters: [${caliber_address}]
        return: {name: "st_shares", type: "uint256"}
      
      # Convert to asset claims
      - target: ${constants.st_stcusd_proxy}
        selector: "convertToAssets(uint256)"
        parameters: [${returns.st_shares}]
        return: {name: "asset_claims", type: "(uint256,uint256,uint256)"}
      
      # Extract nav (third element)
      - target: ${constants.caliber_helper}
        selector: "extractElementFromStaticTuple(bytes,uint256)"
        parameters: [${returns.asset_claims}, 2]
        return: {name: "nav_usd", type: "uint256"}
      
      # Position value in USD (18 decimals)
      - reserved_slots: [{type: "uint256", value: "${returns.nav_usd}"}]
```

---

## Sources

- **Royco Protocol V1**: https://github.com/roycoprotocol/royco
- **Etherscan ST Implementation**: https://etherscan.io/address/0x78493b5421fa73e1d7192011a5c0459d83ef7679#code
- **Etherscan Kernel Proxy**: https://etherscan.io/address/0x9911F227E9428964D8A35B852513919C8DF92038
- **Royco Dawn Docs**: https://royco.gitbook.io/royco-dawn
- **Royco Immunefi Bug Bounty**: https://immunefi.com/bug-bounty/royco/information/
