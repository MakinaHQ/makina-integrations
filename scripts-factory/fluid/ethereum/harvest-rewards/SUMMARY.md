# Fluid Protocol INST/FLUID Rewards Claim

## Overview

This is a **Merkle-based rewards distribution** contract for claiming FLUID token rewards from Fluid Protocol (formerly Instadapp). The contract uses merkle proofs to verify eligibility and distributes rewards based on a cumulative claiming model, tracked per (user, positionId) pair.

## Contract Architecture

| Contract        | Address                                      | Type                 |
| --------------- | -------------------------------------------- | -------------------- |
| Claims Contract | `0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0` | Merkle Claims        |
| FLUID Token     | `0x6f40d4A6237C257fff2dB00FA0510DeEECd303eb` | ERC-20 (18 decimals) |

## Key Function: `claim`

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

### Parameters

| Parameter           | Type      | Description                                         |
| ------------------- | --------- | --------------------------------------------------- |
| `recipient_`        | address   | The address claiming rewards (must == msg.sender)   |
| `cumulativeAmount_` | uint256   | Total lifetime claimable amount (wei)               |
| `positionType_`     | uint8     | Position type (1 = lending vault)                   |
| `positionId_`       | bytes32   | Position ID (vault address left-padded to 32 bytes) |
| `cycle_`            | uint256   | Merkle cycle number                                 |
| `merkleProof_`      | bytes32[] | Array of proof hashes                               |
| `metadata_`         | bytes     | Additional metadata (usually empty 0x)              |

## How It Works

1. **Cumulative Model**: The `cumulativeAmount` represents the TOTAL amount ever claimable, not the amount for this specific claim.

2. **Position Tracking**: Claims are tracked per (recipient, positionId) pair, allowing multiple positions per user.

3. **Claim Calculation**:
   ```
   actual_claim = cumulativeAmount - claimed[recipient][positionId]
   ```

4. **No Approval Needed**: This is a transfer FROM the contract TO the user.

## Important: Position ID Transformation

The `positionId` from the API is a 20-byte address that must be **left-padded to 32 bytes**:

```
API returns:      0x6a29a46e21c730dca1d8b23d637c101cec605c5b
Contract expects: 0x0000000000000000000000006a29a46e21c730dca1d8b23d637c101cec605c5b
```

## Query Functions

| Function                   | Returns                                |
| -------------------------- | -------------------------------------- |
| `claimed(address,bytes32)` | uint256 - Already claimed for position |
| `currentMerkleCycle()`     | tuple - Current cycle data and root    |
| `TOKEN()`                  | address - Reward token address         |
| `paused()`                 | bool - Pause status                    |

## Events

```solidity
event LogClaimed(
    address user,
    uint256 amount,
    uint256 cycle,
    uint8 positionType,
    bytes32 positionId,
    uint256 timestamp,
    uint256 blockNumber
);
```

## Obtaining Merkle Proof Data

The merkle proof and cumulative amount must be obtained from Fluid's claim API - they are not stored on-chain. Only the merkle root is stored in the contract.

**API Endpoint:**

```
GET https://merkle.api.fluid.instadapp.io/programs/inst-rewards-dec-2024/users/{ADDRESS}/claims
```

## Example Response

```json
[
  {
    "positionId": "0x6a29a46e21c730dca1d8b23d637c101cec605c5b",
    "positionType": 1,
    "user": "0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC",
    "cycle": 1182,
    "cumulativeAmountWei": "2727350840997778921955",
    "proof": ["0x...", "0x...", ...]
  }
]
```

## Security Notes

- Contract has pause functionality
- `msg.sender` MUST equal `recipient_` parameter
- Merkle cycle updates periodically - use fresh API data

---

## Offchain Components

This protocol requires **offchain data** to construct the claim transaction. The merkle proof and cumulative amount cannot be computed on-chain and must be fetched from an external API.

### Required Offchain Data

| Field              | Type      | Source | Description                                    |
| ------------------ | --------- | ------ | ---------------------------------------------- |
| `cumulativeAmount` | uint256   | API    | Total lifetime claimable amount (wei)          |
| `positionType`     | uint8     | API    | Position type enum (1 = lending vault)         |
| `positionId`       | bytes32   | API    | Vault address left-padded to 32 bytes          |
| `cycle`            | uint256   | API    | Merkle cycle number                            |
| `merkleProof`      | bytes32[] | API    | Array of proof hashes (typically 10-20 hashes) |
| `metadata`         | bytes     | API    | Additional metadata (typically empty 0x)       |

### When to Fetch

- Fetch **before** constructing the claim transaction
- The merkle root is updated periodically (check `cycle` field)
- Always use the latest API data to ensure the cycle matches on-chain

### Error Handling

- **Empty array `[]`**: Address has no rewards allocated
- **HTTP 404**: Address not found
- **Stale cycle**: Refetch after merkle root update

See `API.md` for full Python and Rust implementation code.
