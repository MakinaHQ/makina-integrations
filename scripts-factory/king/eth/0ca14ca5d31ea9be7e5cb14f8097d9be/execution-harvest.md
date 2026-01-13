# Execution Report: King Protocol KING Token Harvest

**Action**: harvest (claim_rewards)
**Chain**: Ethereum Mainnet
**Testnet ID**: `198883f6-f99f-49fa-b596-644c5e477a8f`
**Testnet RPC**: `https://virtual.mainnet.eu.rpc.tenderly.co/c06cdece-d70e-4a52-bd09-efaf51254f86`
**Date**: 2026-01-07

---

## Summary

Successfully claimed 11.385833 KING tokens for caliber address using merkle proof from ether.fi API.

---

## Pre-Claim State

| Metric               | Value                                                                |
| -------------------- | -------------------------------------------------------------------- |
| Caliber Address      | `0xD1A2d9DF5db842DA2Ee81075Fa441602B2352915`                         |
| KING Token Balance   | 0 wei (0.000000 KING)                                                |
| Cumulative Claimed   | 0 wei (0.000000 KING)                                                |
| On-chain Merkle Root | `0xa5e4a3c599a82b6cb74148b61d77f327ff5ced4eac5faa5a3887c5f6402f6d01` |
| Contract Paused      | false                                                                |
| Claim EID            | 30101 (Ethereum mainnet)                                             |

---

## API Data Fetch

**Endpoint**: `GET https://www.ether.fi/api/dapp/king/0xD1A2d9DF5db842DA2Ee81075Fa441602B2352915`

**Response**:

```json
{
  "Amount": "11385832910371565296",
  "Root": "0xa5e4a3c599a82b6cb74148b61d77f327ff5ced4eac5faa5a3887c5f6402f6d01",
  "Proofs": [
    "0x02a250c15a0b9c2d2cb0a96c9484d2f960616f13bc56031c44546348332a695a",
    "0xd736cf29a4e862bd70b7edf3decb50fd85050195d868f6f6e5710012ac4e1b9f",
    "0x6ee7a0502228faf2cb63f1188070c25ac13508c72052a745e6627ddaee993745",
    "0xac62d82c0e359813a9d3112d3ba64f05aada039e406be5e9de3b6915f6908980",
    "0x32e3248699e9459e0972ddfa88d9d16defe25cbc60b87df7ba861ec92695c636",
    "0x47247cae508de9a866c781f27d8c009303a7ebd2958dc7254d4cfd4aea72122b",
    "0xd1376a32754a7abed5f0953b49880fc568b180cf4c90d4ec33a493ffa360bee7",
    "0xd3be335ea98edb74e4f3fc39a46c237940b00866c29423029875b6e348ff5bed",
    "0x18c61c2334fab77e0e3b887d06bebc1b088738fb5db035a932b8451d0ae1fae9",
    "0x1ff502def1037aaddc7a4671bd987670bace3cb7afc22b328c8f5e4fb07c47bc",
    "0x5f1d4f8ab020a445605eaf9257d877c656c9954ee8df8797bedb52157b081d04",
    "0x2be95b6782b3d5ef5b15bb1ae628aee7a84133d2f52f88cf6d303d747b30bb64",
    "0xaf710428ff2d1845f9e427f58de7388a3d09025900c587d0f425793ba2da7cae",
    "0x6dc2e24bd527f1f72728795e1c1436293291a669f55596b3089662505c257f12",
    "0xe6c75376151f41131f60a72d5439f26d26b753815c9127fcb43a6b4bd771d598",
    "0x96386fc24161d3ef731be279ab76c7b18f6d45e7ac680d37e67fc855f8e2de91",
    "0x718fe2db21ab60f2f53b1c6909497acb6e43d51371b74bc00c46961c60a96176",
    "0xbe261f3819d8b44852d49ff950f551af0e4d18917b8b1b781ee92acd0e26899b",
    "0x7baeff9ced214da3ae00c3ddd4a287577f38002eed36b92e5a91c777e006a2ba",
    "0x74ba55358ff6a27745a7c467a5ce2cb98dcf4e9098364cbc872e3db2629b194d"
  ]
}
```

---

## Claimable Calculation

```
Cumulative Amount (from API): 11385832910371565296 wei (11.385833 KING)
Already Claimed (from contract): 0 wei (0.000000 KING)
Claimable: 11385832910371565296 wei (11.385833 KING)
```

**Formula**: `claimable = cumulativeAmount - cumulativeClaimed[account]`

---

## Proof Verification (Pre-Transaction)

**Contract**: `0x6Db24Ee656843E3fE03eb8762a54D86186bA6B64`
**Function**: `verify(address account, uint256 cumulativeAmount, bytes32 expectedMerkleRoot, bytes32[] merkleProof)`
**Selector**: `0xc23b139e`

| Parameter          | Value                                                                | Type      |
| ------------------ | -------------------------------------------------------------------- | --------- |
| account            | `0xD1A2d9DF5db842DA2Ee81075Fa441602B2352915`                         | address   |
| cumulativeAmount   | `11385832910371565296`                                               | uint256   |
| expectedMerkleRoot | `0xa5e4a3c599a82b6cb74148b61d77f327ff5ced4eac5faa5a3887c5f6402f6d01` | bytes32   |
| merkleProof        | (20 proof hashes)                                                    | bytes32[] |

**Result**: `true` (proof valid)

---

## Call 1: claim

**Contract**: `0x6Db24Ee656843E3fE03eb8762a54D86186bA6B64` (CumulativeMerkleDrop Proxy)
**Function**: `claim(address account, uint256 cumulativeAmount, bytes32 expectedMerkleRoot, bytes32[] merkleProof)`
**Selector**: `0x1d7d4ebc`

### Inputs

| Parameter          | Value                                                                | Type      |
| ------------------ | -------------------------------------------------------------------- | --------- |
| account            | `0xD1A2d9DF5db842DA2Ee81075Fa441602B2352915`                         | address   |
| cumulativeAmount   | `11385832910371565296`                                               | uint256   |
| expectedMerkleRoot | `0xa5e4a3c599a82b6cb74148b61d77f327ff5ced4eac5faa5a3887c5f6402f6d01` | bytes32   |
| merkleProof        | 20 hashes (see API response above)                                   | bytes32[] |

### Transaction

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| Tx Hash  | `0x04249224c7db8952d68fa447858d2c6a75256e620ee57ce0629d336b13f3a22a` |
| Status   | SUCCESS                                                              |
| Block    | 24184385                                                             |
| Gas Used | 114,509                                                              |
| From     | `0xD1A2d9DF5db842DA2Ee81075Fa441602B2352915`                         |
| To       | `0x6Db24Ee656843E3fE03eb8762a54D86186bA6B64`                         |

### Calldata

```
0x1d7d4ebc000000000000000000000000d1a2d9df5db842da2ee81075fa441602b23529150000000000000000000000000000000000000000000000009e029ab50ea62ef0a5e4a3c599a82b6cb74148b61d77f327ff5ced4eac5faa5a3887c5f6402f6d010000000000000000000000000000000000000000000000000000000000000080000000000000000000000000000000000000000000000000000000000000001402a250c15a0b9c2d2cb0a96c9484d2f960616f13bc56031c44546348332a695ad736cf29a4e862bd70b7edf3decb50fd85050195d868f6f6e5710012ac4e1b9f6ee7a0502228faf2cb63f1188070c25ac13508c72052a745e6627ddaee993745ac62d82c0e359813a9d3112d3ba64f05aada039e406be5e9de3b6915f690898032e3248699e9459e0972ddfa88d9d16defe25cbc60b87df7ba861ec92695c63647247cae508de9a866c781f27d8c009303a7ebd2958dc7254d4cfd4aea72122bd1376a32754a7abed5f0953b49880fc568b180cf4c90d4ec33a493ffa360bee7d3be335ea98edb74e4f3fc39a46c237940b00866c29423029875b6e348ff5bed18c61c2334fab77e0e3b887d06bebc1b088738fb5db035a932b8451d0ae1fae91ff502def1037aaddc7a4671bd987670bace3cb7afc22b328c8f5e4fb07c47bc5f1d4f8ab020a445605eaf9257d877c656c9954ee8df8797bedb52157b081d042be95b6782b3d5ef5b15bb1ae628aee7a84133d2f52f88cf6d303d747b30bb64af710428ff2d1845f9e427f58de7388a3d09025900c587d0f425793ba2da7cae6dc2e24bd527f1f72728795e1c1436293291a669f55596b3089662505c257f12e6c75376151f41131f60a72d5439f26d26b753815c9127fcb43a6b4bd771d59896386fc24161d3ef731be279ab76c7b18f6d45e7ac680d37e67fc855f8e2de91718fe2db21ab60f2f53b1c6909497acb6e43d51371b74bc00c46961c60a96176be261f3819d8b44852d49ff950f551af0e4d18917b8b1b781ee92acd0e26899b7baeff9ced214da3ae00c3ddd4a287577f38002eed36b92e5a91c777e006a2ba74ba55358ff6a27745a7c467a5ce2cb98dcf4e9098364cbc872e3db2629b194d
```

**Calldata Breakdown**:

- `0x1d7d4ebc` - Function selector
- Bytes 4-36: account address (padded)
- Bytes 36-68: cumulativeAmount (uint256)
- Bytes 68-100: expectedMerkleRoot (bytes32)
- Bytes 100-132: offset to merkleProof array (0x80 = 128)
- Bytes 132-164: length of merkleProof array (0x14 = 20)
- Bytes 164+: 20 merkle proof hashes (32 bytes each)

---

## Events Emitted

### Event 1: Transfer (ERC-20)

**Contract**: `0x8F08B70456eb22f6109F57b8fafE862ED28E6040` (KING Token)
**Signature**: `Transfer(address indexed from, address indexed to, uint256 value)`
**Topic**: `0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef`

| Parameter | Value                                                          |
| --------- | -------------------------------------------------------------- |
| from      | `0x6Db24Ee656843E3fE03eb8762a54D86186bA6B64` (Claims Contract) |
| to        | `0xD1A2d9DF5db842DA2Ee81075Fa441602B2352915` (Caliber)         |
| value     | `11385832910371565296` (11.385833 KING)                        |

### Event 2: Claimed

**Contract**: `0x6Db24Ee656843E3fE03eb8762a54D86186bA6B64` (Claims Contract)
**Signature**: `Claimed(address indexed account, uint256 amount)`
**Topic**: `0xd8138f8a3f377c5259ca548e70e4c2de94f129f5a11036a15b69513cba2b426a`

| Parameter | Value                                                  |
| --------- | ------------------------------------------------------ |
| account   | `0xD1A2d9DF5db842DA2Ee81075Fa441602B2352915` (Caliber) |
| amount    | `11385832910371565296` (11.385833 KING)                |

---

## Post-Claim State

| Metric             | Value                                     |
| ------------------ | ----------------------------------------- |
| KING Token Balance | 11385832910371565296 wei (11.385833 KING) |
| Cumulative Claimed | 11385832910371565296 wei (11.385833 KING) |

---

## State Changes

| Metric             | Before | After                | Change          |
| ------------------ | ------ | -------------------- | --------------- |
| KING Balance       | 0      | 11385832910371565296 | +11.385833 KING |
| Cumulative Claimed | 0      | 11385832910371565296 | +11.385833 KING |

---

## Verification

| Check                                | Result |
| ------------------------------------ | ------ |
| Merkle Root Match (API vs On-chain)  | PASS   |
| Proof Verification                   | PASS   |
| Transaction Success                  | PASS   |
| KING Balance matches claimed amount  | PASS   |
| Cumulative Claimed updated correctly | PASS   |

---

## Key Observations

1. **Cumulative Model**: The contract uses a cumulative claiming model where `cumulativeAmount` represents the total lifetime claimable amount. The actual transfer is `cumulativeAmount - alreadyClaimed`.

2. **No Approval Required**: This is a claim/transfer from the contract to the user, so no token approval is needed.

3. **Merkle Proof Source**: The proof must be fetched from ether.fi API - the contract only stores the merkle root, not individual claim data.

4. **Chain Validation**: The contract validates that claims happen on the correct chain (EID 30101 for Ethereum mainnet by default).

5. **Gas Usage**: The claim transaction used 114,509 gas with 20 proof hashes.

---

## Issues Encountered

None. The claim executed successfully on the first attempt.

---

## Contract Addresses Reference

| Contract                         | Address                                      |
| -------------------------------- | -------------------------------------------- |
| Claims Contract (Proxy)          | `0x6Db24Ee656843E3fE03eb8762a54D86186bA6B64` |
| Claims Contract (Implementation) | `0x5E226B1De8b0F387d7C77f78CBa2571D2a1be511` |
| KING Token                       | `0x8F08B70456eb22f6109F57b8fafE862ED28E6040` |
| LayerZero Endpoint               | `0x1a44076050125825900e736c501f859c50fE728c` |
