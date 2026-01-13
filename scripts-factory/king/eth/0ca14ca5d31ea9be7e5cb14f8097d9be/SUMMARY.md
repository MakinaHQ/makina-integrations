# King Protocol KING Rewards Claim

## Overview

This is a **CumulativeMerkleDrop** contract for claiming KING token rewards from King Protocol (associated with ether.fi). The contract uses merkle proofs to verify eligibility and distributes rewards based on a cumulative claiming model.

## Contract Architecture

| Contract                | Address                                      | Type                 |
| ----------------------- | -------------------------------------------- | -------------------- |
| Claims Contract (Proxy) | `0x6Db24Ee656843E3fE03eb8762a54D86186bA6B64` | UUPS Proxy           |
| Implementation          | `0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511` | CumulativeMerkleDrop |
| KING Token              | `0x8F08B70456eb22f6109F57b8fafE862ED28E6040` | ERC-20 (18 decimals) |

## Key Function: `claim`

```solidity
function claim(
    address account,
    uint256 cumulativeAmount,
    bytes32 expectedMerkleRoot,
    bytes32[] calldata merkleProof
) external
```

### Parameters

| Parameter            | Type      | Description                                 |
| -------------------- | --------- | ------------------------------------------- |
| `account`            | address   | The address claiming rewards                |
| `cumulativeAmount`   | uint256   | Total lifetime claimable amount (wei)       |
| `expectedMerkleRoot` | bytes32   | Merkle root the proof was generated against |
| `merkleProof`        | bytes32[] | Array of proof hashes                       |

### Function Selector

`0x1d7d4ebc`

## How It Works

1. **Cumulative Model**: The `cumulativeAmount` represents the TOTAL amount ever claimable, not the amount for this specific claim.

2. **Claim Calculation**:
   ```
   actual_claim = cumulativeAmount - cumulativeClaimed[account]
   ```

3. **Merkle Verification**: The leaf is computed as:
   ```
   leaf = keccak256(abi.encodePacked(account, cumulativeAmount))
   ```

4. **No Approval Needed**: This is a transfer FROM the contract TO the user.

## Important Checks

Before claiming, the contract verifies:

- `expectedMerkleRoot == merkleRoot` (root hasn't changed)
- User is claiming on correct chain (`getClaimEid(account)`)
- Merkle proof is valid
- `cumulativeAmount > cumulativeClaimed[account]` (something to claim)
- Contract is not paused

## Query Functions

| Function                                    | Selector     | Returns                                  |
| ------------------------------------------- | ------------ | ---------------------------------------- |
| `cumulativeClaimed(address)`                | `0x865590b9` | uint256 - Already claimed amount         |
| `merkleRoot()`                              | `0x2eb4a7ab` | bytes32 - Current merkle root            |
| `verify(address,uint256,bytes32,bytes32[])` | `0xc23b139e` | bool - Proof validity                    |
| `paused()`                                  | `0x5c975abb` | bool - Pause status                      |
| `getClaimEid(address)`                      | `0x7f5a7c7a` | uint32 - LayerZero chain ID for claiming |

## Events

```solidity
event Claimed(address indexed account, uint256 amount);
```

## Obtaining Merkle Proof Data

The merkle proof and cumulative amount must be obtained from King Protocol's claim interface or API - they are not stored on-chain. Only the merkle root is stored in the contract.

## Cross-Chain Support

This contract integrates with LayerZero V2 for cross-chain claiming:

- LayerZero Endpoint: `0x1a44076050125825900e736c501f859c50fE728c`
- Users may be assigned to claim on specific chains
- Check `getClaimEid(account)` to verify the claim chain

## Example Transaction

Recent successful claim: [0xa944538...](https://etherscan.io/tx/0xa944538eed3363e91c933a15f8f39980a04496d2c92ab6fc2d10a6d6d8de4c0b)

## Security Notes

- Contract uses ReentrancyGuard
- Pausable by PAUSER_ROLE
- UUPS upgradeable proxy pattern
- Merkle root updates controlled by OPERATING_ADMIN_ROLE

---

## Offchain Components

This protocol requires **offchain data** to construct the claim transaction. The merkle proof and cumulative amount cannot be computed on-chain and must be fetched from an external API.

### Required Offchain Data

| Field                | Type      | Source | Description                                    |
| -------------------- | --------- | ------ | ---------------------------------------------- |
| `cumulativeAmount`   | uint256   | API    | Total lifetime claimable amount (wei)          |
| `expectedMerkleRoot` | bytes32   | API    | Merkle root the proof was generated against    |
| `merkleProof`        | bytes32[] | API    | Array of proof hashes (typically 15-25 hashes) |

### API Endpoint

```
GET https://www.ether.fi/api/dapp/king/{ADDRESS}
```

**Response:**

```json
{
  "Amount": "11385832910371565296",
  "Root": "0xa5e4a3c599a82b6cb74148b61d77f327ff5ced4eac5faa5a3887c5f6402f6d01",
  "Proofs": ["0x...", "0x...", ...]
}
```

### Field Mapping

| API Response | Contract Parameter   | Transformation                  |
| ------------ | -------------------- | ------------------------------- |
| `Amount`     | `cumulativeAmount`   | Parse string to uint256         |
| `Root`       | `expectedMerkleRoot` | Use as-is (bytes32 hex)         |
| `Proofs`     | `merkleProof`        | Use as-is (bytes32[] hex array) |

### When to Fetch

- Fetch **before** constructing the claim transaction
- The merkle root is updated periodically (typically weekly)
- Always use the latest API data to ensure the root matches on-chain

### Error Handling

- **404**: Address not in merkle tree (no rewards allocated)
- **Amount = "0"**: No rewards to claim
- **Root mismatch**: API data stale, refetch after merkle root update

See `API.md` for full Python and Rust implementation code.
