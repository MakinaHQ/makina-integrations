# King Protocol KING Rewards Claim - Function Implementations

Chain: Ethereum Mainnet
Generated: 2026-01-07

## Overview

| Function          | Contract                                   | Type                 |
| ----------------- | ------------------------------------------ | -------------------- |
| claim             | 0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511 | External (via proxy) |
| verify            | 0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511 | View                 |
| _verifyAsm        | 0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511 | Private (Assembly)   |
| getClaimEid       | 0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511 | View                 |
| cumulativeClaimed | 0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511 | View (mapping)       |
| merkleRoot        | 0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511 | View (state)         |
| paused            | 0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511 | View                 |
| setMerkleRoot     | 0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511 | Admin                |

---

## Claim Function (Primary Entry Point)

### claim

**Contract:** `0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511` (CumulativeMerkleDrop implementation)
**Proxy:** `0x6Db24Ee656843E3fE03eb8762a54D86186bA6B64`
**Signature:** `claim(address,uint256,bytes32,bytes32[])`
**Selector:** `0x1d7d4ebc`

```solidity
function claim(
    address account,
    uint256 cumulativeAmount,
    bytes32 expectedMerkleRoot,
    bytes32[] calldata merkleProof
) external whenNotPaused nonReentrant {
    if (merkleRoot != expectedMerkleRoot) revert MerkleRootWasUpdated();

    // Verify the claim chain
    if (endpoint.eid() != getClaimEid(account)) revert InvalidChain();

    // Verify the merkle proof
    if (!verify(account, cumulativeAmount, expectedMerkleRoot, merkleProof)) revert InvalidProof();

    // Mark it claimed
    uint256 preclaimed = cumulativeClaimed[account];
    if (preclaimed >= cumulativeAmount) revert NothingToClaim();
    cumulativeClaimed[account] = cumulativeAmount;

    // Send the token
    unchecked {
        uint256 amount = cumulativeAmount - preclaimed;
        IERC20(token).safeTransfer(account, amount);
        emit Claimed(account, amount);
    }
}
```

**Key Observations:**

- Uses `whenNotPaused` modifier - contract must not be paused
- Uses `nonReentrant` modifier (transient storage variant for EIP-1153)
- Validates merkle root has not changed since proof was generated
- Validates caller is on the correct chain via LayerZero endpoint ID
- Validates merkle proof via `verify()` function
- Calculates actual transfer amount as `cumulativeAmount - cumulativeClaimed[account]`
- Uses `safeTransfer` for token transfer
- Emits `Claimed(address indexed account, uint256 amount)` event

**Revert Conditions:**

- `MerkleRootWasUpdated()` - merkle root changed since proof was generated
- `InvalidChain()` - user must claim on a different chain
- `InvalidProof()` - merkle proof verification failed
- `NothingToClaim()` - already claimed this cumulative amount or more

---

## Verification Functions

### verify

**Contract:** `0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511`
**Signature:** `verify(address,uint256,bytes32,bytes32[])`
**Selector:** `0xc23b139e`

```solidity
function verify(
    address account,
    uint256 cumulativeAmount,
    bytes32 expectedMerkleRoot,
    bytes32[] calldata merkleProof
) public pure returns (bool) {
    bytes32 leaf = keccak256(abi.encodePacked(account, cumulativeAmount));
    return _verifyAsm(merkleProof, expectedMerkleRoot, leaf);
}
```

**Key Observations:**

- Pure function - can be called off-chain to validate proofs
- Leaf is computed as `keccak256(abi.encodePacked(account, cumulativeAmount))`
- Delegates to assembly-optimized `_verifyAsm` for gas efficiency

### _verifyAsm

**Contract:** `0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511`
**Visibility:** Private

```solidity
function _verifyAsm(bytes32[] calldata proof, bytes32 root, bytes32 leaf) private pure returns (bool valid) {
    /// @solidity memory-safe-assembly
    assembly {  // solhint-disable-line no-inline-assembly
        let ptr := proof.offset

        for { let end := add(ptr, mul(0x20, proof.length)) } lt(ptr, end) { ptr := add(ptr, 0x20) } {
            let node := calldataload(ptr)

            switch lt(leaf, node)
            case 1 {
                mstore(0x00, leaf)
                mstore(0x20, node)
            }
            default {
                mstore(0x00, node)
                mstore(0x20, leaf)
            }

            leaf := keccak256(0x00, 0x40)
        }

        valid := eq(root, leaf)
    }
}
```

**Key Observations:**

- Assembly-optimized merkle proof verification (gas efficient)
- Standard merkle tree verification algorithm
- Orders leaf and node by value before hashing (sorted pair hashing)
- Returns true if computed root matches expected root

---

## State Query Functions

### getClaimEid

**Contract:** `0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511`
**Signature:** `getClaimEid(address)`
**Selector:** `0x7f5a7c7a`

```solidity
function getClaimEid(address user) public view returns (uint32) {
    if (claimEid[user] == 0) {
        return 30101;
    } else {
        return claimEid[user];
    }
}
```

**Key Observations:**

- Returns LayerZero endpoint ID where user should claim
- Default is `30101` (Ethereum mainnet) if not explicitly set
- Users can switch chains via `updateClaimEid()` if enabled

### cumulativeClaimed

**Contract:** `0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511`
**Signature:** `cumulativeClaimed(address)`
**Selector:** `0x865590b9`

```solidity
// State variable (mapping)
mapping(address => uint256) public cumulativeClaimed;
```

**Key Observations:**

- Returns total amount already claimed by an address
- Used to calculate remaining claimable: `cumulativeAmount - cumulativeClaimed[account]`

### merkleRoot

**Contract:** `0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511`
**Signature:** `merkleRoot()`
**Selector:** `0x2eb4a7ab`

```solidity
// State variable
bytes32 public merkleRoot;
```

**Key Observations:**

- Current merkle root for proof verification
- Must match `expectedMerkleRoot` parameter in `claim()` call
- Updated by admin via `setMerkleRoot()` or `setAndBroadcastMerkleRoot()`

### paused

**Contract:** `0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511`
**Signature:** `paused()`
**Selector:** `0x5c975abb`

```solidity
function paused() public view virtual returns (bool) {
    PausableStorage storage $ = _getPausableStorage();
    return $._paused;
}
```

**Key Observations:**

- Returns true if contract is paused
- Uses ERC-7201 namespaced storage pattern
- Claims are blocked when paused

---

## Modifiers

### whenNotPaused

```solidity
modifier whenNotPaused() {
    _requireNotPaused();
    _;
}

function _requireNotPaused() internal view virtual {
    if (paused()) {
        revert EnforcedPause();
    }
}
```

**Key Observations:**

- Reverts with `EnforcedPause()` if contract is paused
- Applied to `claim()` function

### nonReentrant (Transient Storage Variant)

```solidity
// Uses EIP-1153 transient storage for gas efficiency
modifier nonReentrant() {
    _nonReentrantBefore();
    _;
    _nonReentrantAfter();
}

function _nonReentrantBefore() private {
    // On the first call to nonReentrant, _status will be NOT_ENTERED
    if (_reentrancyGuardEntered()) {
        revert ReentrancyGuardReentrantCall();
    }

    // Any calls to nonReentrant after this point will fail
    REENTRANCY_GUARD_STORAGE.asBoolean().tstore(true);
}

function _nonReentrantAfter() private {
    REENTRANCY_GUARD_STORAGE.asBoolean().tstore(false);
}

function _reentrancyGuardEntered() internal view returns (bool) {
    return REENTRANCY_GUARD_STORAGE.asBoolean().tload();
}
```

**Key Observations:**

- Uses transient storage (EIP-1153) for gas efficiency
- Storage slot: `0x9b779b17422d0df92223018b32b4d1fa46e071723d6817e2486d003becc55f00`
- Reverts with `ReentrancyGuardReentrantCall()` on reentrant calls

---

## Admin Functions

### setMerkleRoot

**Contract:** `0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511`
**Signature:** `setMerkleRoot(bytes32)`

```solidity
function setMerkleRoot(bytes32 merkleRoot_) public onlyRole(DEFAULT_ADMIN_ROLE) {
    emit MerkleRootUpdated(merkleRoot, merkleRoot_);
    merkleRoot = merkleRoot_;
}
```

**Key Observations:**

- Only callable by `DEFAULT_ADMIN_ROLE`
- Emits `MerkleRootUpdated(bytes32 oldRoot, bytes32 newRoot)` event
- When root changes, existing proofs become invalid

---

## Events

```solidity
// Emitted when rewards are successfully claimed
event Claimed(address indexed account, uint256 amount);

// Emitted when merkle root is updated
event MerkleRootUpdated(bytes32 oldMerkleRoot, bytes32 newMerkleRoot);

// Emitted when user's claim chain is updated
event ClaimEidUpdated(address indexed account, uint32 newChain);
```

---

## Custom Errors

```solidity
error MerkleRootWasUpdated();      // Merkle root changed since proof generation
error InvalidChain();              // User must claim on different chain
error InvalidProof();              // Merkle proof verification failed
error NothingToClaim();            // Already claimed this amount or more
error EnforcedPause();             // Contract is paused
error ReentrancyGuardReentrantCall(); // Reentrant call detected
```

---

## Execution Flow Summary

```
claim(account, cumulativeAmount, expectedMerkleRoot, merkleProof)
    |
    +-- whenNotPaused modifier
    |       |
    |       +-- _requireNotPaused()
    |               |
    |               +-- if paused() -> revert EnforcedPause()
    |
    +-- nonReentrant modifier
    |       |
    |       +-- _nonReentrantBefore() [tstore(true)]
    |
    +-- Check merkleRoot == expectedMerkleRoot
    |       |
    |       +-- if not equal -> revert MerkleRootWasUpdated()
    |
    +-- Check endpoint.eid() == getClaimEid(account)
    |       |
    |       +-- if not equal -> revert InvalidChain()
    |
    +-- verify(account, cumulativeAmount, expectedMerkleRoot, merkleProof)
    |       |
    |       +-- Compute leaf = keccak256(abi.encodePacked(account, cumulativeAmount))
    |       +-- _verifyAsm(proof, root, leaf)
    |       +-- if false -> revert InvalidProof()
    |
    +-- Check cumulativeClaimed[account] < cumulativeAmount
    |       |
    |       +-- if not -> revert NothingToClaim()
    |
    +-- Update cumulativeClaimed[account] = cumulativeAmount
    |
    +-- Calculate amount = cumulativeAmount - preclaimed
    |
    +-- IERC20(token).safeTransfer(account, amount)
    |
    +-- emit Claimed(account, amount)
    |
    +-- _nonReentrantAfter() [tstore(false)]
```

---

## Testing Considerations

1. **Merkle Proof Source:** The proof and `cumulativeAmount` must be obtained from King Protocol's off-chain data source (API or merkle tree). The contract only stores the root.

2. **Chain Validation:** For Ethereum mainnet testing, ensure `getClaimEid(account)` returns `30101` (default).

3. **Cumulative Model:** The `cumulativeAmount` is the lifetime total, not per-claim. If user has already claimed 100 KING and `cumulativeAmount` is 150, they will receive 50 KING.

4. **Root Staleness:** If the merkle root is updated between fetching proof and claiming, the transaction will revert with `MerkleRootWasUpdated()`.

5. **No Approval Required:** This is a claim/transfer from the contract - no token approval needed from the claimer.
