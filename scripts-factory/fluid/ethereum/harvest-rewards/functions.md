# Fluid Protocol INST Rewards Claim - Function Implementations

Chain: Ethereum Mainnet
Generated: 2026-01-12

## Overview

| Function           | Contract                                   | Type     |
| ------------------ | ------------------------------------------ | -------- |
| claim              | 0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0 | External |
| claimed            | 0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0 | View     |
| currentMerkleCycle | 0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0 | View     |
| TOKEN              | 0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0 | View     |
| paused             | 0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0 | View     |

---

## Claim Function (Primary Entry Point)

### claim

**Contract:** `0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0`
**Signature:** `claim(address,uint256,uint8,bytes32,uint256,bytes32[],bytes)`

```solidity
function claim(
    address recipient_,
    uint256 cumulativeAmount_,
    uint8 positionType_,
    bytes32 positionId_,
    uint256 cycle_,
    bytes32[] calldata merkleProof_,
    bytes calldata metadata_
) external
```

**Key Observations:**

- `recipient_` must equal `msg.sender` (enforced by contract)
- Uses cumulative claiming model - tracks per (recipient, positionId) pair
- Validates merkle proof against current cycle's root
- Transfers `cumulativeAmount - claimed[recipient][positionId]` tokens
- Emits `LogClaimed` event on success

**Revert Conditions:**

- `MsgSenderNotRecipient()` - msg.sender != recipient_
- `InvalidCycle()` - cycle doesn't match current merkle cycle
- `InvalidProof()` - merkle proof verification failed
- `NothingToClaim()` - already claimed this cumulative amount or more
- `Paused()` - contract is paused

---

## State Query Functions

### claimed

**Contract:** `0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0`
**Signature:** `claimed(address,bytes32)`

```solidity
mapping(address => mapping(bytes32 => uint256)) public claimed;
```

**Key Observations:**

- Returns total amount already claimed by an address for a specific positionId
- Used to calculate remaining claimable: `cumulativeAmount - claimed[recipient][positionId]`
- The bytes32 key is the positionId (left-padded vault address)

### currentMerkleCycle

**Contract:** `0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0`
**Signature:** `currentMerkleCycle()`

```solidity
function currentMerkleCycle() external view returns (MerkleCycle memory)

struct MerkleCycle {
    bytes32 merkleRoot;
    bytes32 merkleContentHash;
    uint40 cycle;
    uint40 timestamp;
    uint40 publishBlock;
    uint40 startBlock;
    uint40 endBlock;
}
```

**Key Observations:**

- Returns current merkle cycle data including root
- The `cycle` field should match the cycle from API data
- `merkleRoot` is used for proof verification

### TOKEN

**Contract:** `0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0`
**Signature:** `TOKEN()`

```solidity
IERC20 public immutable TOKEN;
```

**Key Observations:**

- Returns the reward token address (FLUID: `0x6f40d4A6237C257fff2dB00FA0510DeEECd303eb`)
- Immutable - set at contract deployment

### paused

**Contract:** `0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0`
**Signature:** `paused()`

```solidity
function paused() public view returns (bool)
```

**Key Observations:**

- Returns true if contract is paused
- Claims are blocked when paused

---

## Events

```solidity
// Emitted when rewards are successfully claimed
event LogClaimed(
    address user,
    uint256 amount,
    uint256 cycle,
    uint8 positionType,
    bytes32 positionId,
    uint256 timestamp,
    uint256 blockNumber
);

// Emitted when merkle root is updated
event LogRootUpdated(
    uint256 cycle,
    bytes32 root,
    bytes32 contentHash,
    uint256 timestamp,
    uint256 blockNumber
);
```

---

## Custom Errors

```solidity
error InvalidCycle();           // Cycle doesn't match current merkle cycle
error InvalidParams();          // Invalid parameters provided
error InvalidProof();           // Merkle proof verification failed
error MsgSenderNotRecipient();  // msg.sender != recipient_
error NothingToClaim();         // Already claimed this amount or more
error Unauthorized();           // Not authorized for admin functions
```

---

## Execution Flow Summary

```
claim(recipient_, cumulativeAmount_, positionType_, positionId_, cycle_, merkleProof_, metadata_)
    |
    +-- Check msg.sender == recipient_
    |       |
    |       +-- if not equal -> revert MsgSenderNotRecipient()
    |
    +-- Check !paused()
    |       |
    |       +-- if paused -> revert (Pausable)
    |
    +-- Check cycle_ == currentMerkleCycle.cycle
    |       |
    |       +-- if not equal -> revert InvalidCycle()
    |
    +-- Verify merkle proof against currentMerkleCycle.merkleRoot
    |       |
    |       +-- if invalid -> revert InvalidProof()
    |
    +-- Check claimed[recipient_][positionId_] < cumulativeAmount_
    |       |
    |       +-- if not -> revert NothingToClaim()
    |
    +-- Calculate amount = cumulativeAmount_ - claimed[recipient_][positionId_]
    |
    +-- Update claimed[recipient_][positionId_] = cumulativeAmount_
    |
    +-- TOKEN.transfer(recipient_, amount)
    |
    +-- emit LogClaimed(recipient_, amount, cycle_, positionType_, positionId_, timestamp, blockNumber)
```

---

## Testing Considerations

1. **Merkle Proof Source:** The proof and `cumulativeAmount` must be obtained from Fluid's off-chain API. The contract only stores the root.

2. **Position ID Transformation:** The API returns a 20-byte address for `positionId`. It must be left-padded to 32 bytes for the contract call.

3. **Cumulative Model:** The `cumulativeAmount` is the lifetime total, not per-claim. If user has already claimed 100 FLUID and `cumulativeAmount` is 150, they will receive 50 FLUID.

4. **Cycle Staleness:** If the merkle cycle is updated between fetching proof and claiming, the transaction will revert with `InvalidCycle()`.

5. **msg.sender Requirement:** The caliber must call claim directly - `recipient_` must equal `msg.sender`.
