# Execution Report: Fluid Protocol FLUID Token Harvest

**Action**: harvest (claim_rewards)
**Chain**: Ethereum Mainnet
**Testnet ID**: `b012ef92-874e-4988-b4c2-25f51cbfb6dd`
**Testnet RPC**: `https://virtual.mainnet.eu.rpc.tenderly.co/14928908-f7cd-4fe5-945a-75d44e12126f`
**Date**: 2026-01-12

---

## Summary

Successfully claimed 2727.350841 FLUID tokens for DUSD caliber address using merkle proof from Fluid API.

---

## Pre-Claim State

| Metric                 | Value                                                     |
| ---------------------- | --------------------------------------------------------- |
| Caliber Address        | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC`              |
| FLUID Token Balance    | 0 wei (0.000000 FLUID)                                    |
| Claimed (for position) | 0 wei (0.000000 FLUID)                                    |
| Position ID (vault)    | `0x6A29A46E21C730DcA1d8b23d637c101cec605C5B` (fGHO vault) |

---

## API Data Fetch

**Endpoint**: `GET https://merkle.api.fluid.instadapp.io/programs/inst-rewards-dec-2024/users/0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC/claims`

**Response**:

```json
[
  {
    "positionId": "0x6a29a46e21c730dca1d8b23d637c101cec605c5b",
    "positionType": 1,
    "user": "0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC",
    "cycle": 1182,
    "amount": "26.898124268414921856",
    "amountWei": "26898124268414921856",
    "cumulativeAmount": "2727.350840997779000000",
    "cumulativeAmountWei": "2727350840997778921955",
    "metadata": "0x",
    "proof": [
      "0x2765bd9da62b13f55655bb65c4f75eb45532044132a2c9638c039b6842375d5e",
      "0x3437e5107d6879a78885219338a226a0c02afdb9cdf5b475fbe8b4403bc26378",
      "0x652b31eedab6ef20abb76d43548d4e9e9770f2eb8f05307c1ea6d69c44c5b3e0",
      "0x46d18517f8f294b0b3616cda6451e4c54c9b56073374c3bc3c597e232892cc61",
      "0x88ee04a9481509a8c690882019e739be17f745fe1df4b5a6ca05177afbbe89be",
      "0xfec68c3f7bcff61589b496880fccc1a4fa8f001b2c65139b7c93078668b2e53c",
      "0xf60ebcfde87bbda5d42fedda9df6302f58ff591bcc5e25373be3eeabd68effff",
      "0x807b404a3e8017ed502fa6da2a10812d3892d675e7abc2cc90d10a0c948f343c",
      "0x92edbc4fb0165b608b022103669946879413f73bfd9c22161fd2869e34c59a25",
      "0xbbf041239037a8433f2e62564343463bb1c6b7af24bbef3a776972d0cab45dcb",
      "0x22fd515ca7b57b5b45ec6962de6d422026a74f0529be8c8e1d1e7e9e74628a7c",
      "0x69afe100fbcd8000451a3d35dac793c6040d27993abffd8ca376d738294d0f53",
      "0xb6ef69ced77bc6c13e471917336062b35ae8254644ae4975d6ec23e8ecfb5917",
      "0x8bd6ddafb1feaa46423a0c74ac7e4db48a7270624f9c48d82bc2bfa2a646e945"
    ]
  }
]
```

---

## Position ID Transformation

The `positionId` from the API is a 20-byte address that was left-padded to 32 bytes:

```
API returns:      0x6a29a46e21c730dca1d8b23d637c101cec605c5b
Contract expects: 0x0000000000000000000000006a29a46e21c730dca1d8b23d637c101cec605c5b
```

---

## Claimable Calculation

```
Cumulative Amount (from API): 2727350840997778921955 wei (2727.350841 FLUID)
Already Claimed (from contract): 0 wei (0.000000 FLUID)
Claimable: 2727350840997778921955 wei (2727.350841 FLUID)
```

**Formula**: `claimable = cumulativeAmount - claimed[recipient][positionId]`

---

## Call 1: claim

**Contract**: `0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0` (Fluid Merkle Claims)
**Function**: `claim(address recipient_, uint256 cumulativeAmount_, uint8 positionType_, bytes32 positionId_, uint256 cycle_, bytes32[] merkleProof_, bytes metadata_)`

### Inputs

| Parameter         | Value                                                                | Type      |
| ----------------- | -------------------------------------------------------------------- | --------- |
| recipient_        | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC`                         | address   |
| cumulativeAmount_ | `2727350840997778921955`                                             | uint256   |
| positionType_     | `1`                                                                  | uint8     |
| positionId_       | `0x0000000000000000000000006a29a46e21c730dca1d8b23d637c101cec605c5b` | bytes32   |
| cycle_            | `1182`                                                               | uint256   |
| merkleProof_      | 14 hashes (see API response above)                                   | bytes32[] |
| metadata_         | `0x` (empty)                                                         | bytes     |

### Transaction

| Field    | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| Tx Hash  | `0x2f443a35f5d062458fd250952a70aef1bb79dc975d33462f37025294acfd7cf7` |
| Status   | SUCCESS                                                              |
| Gas Used | 114,913                                                              |
| From     | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC`                         |
| To       | `0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0`                         |

---

## Events Emitted

### Event 1: Transfer (ERC-20)

**Contract**: `0x6f40d4A6237C257fff2dB00FA0510DeEECd303eb` (FLUID Token)
**Signature**: `Transfer(address indexed from, address indexed to, uint256 value)`

| Parameter | Value                                                          |
| --------- | -------------------------------------------------------------- |
| from      | `0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0` (Claims Contract) |
| to        | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (Caliber)         |
| value     | `2727350840997778921955` (2727.350841 FLUID)                   |

### Event 2: LogClaimed

**Contract**: `0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0` (Claims Contract)
**Signature**: `LogClaimed(address user, uint256 amount, uint256 cycle, uint8 positionType, bytes32 positionId, uint256 timestamp, uint256 blockNumber)`

| Parameter    | Value                                                                |
| ------------ | -------------------------------------------------------------------- |
| user         | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (Caliber)               |
| amount       | `2727350840997778921955` (2727.350841 FLUID)                         |
| cycle        | `1182`                                                               |
| positionType | `1`                                                                  |
| positionId   | `0x0000000000000000000000006a29a46e21c730dca1d8b23d637c101cec605c5b` |

---

## Post-Claim State

| Metric              | Value                                          |
| ------------------- | ---------------------------------------------- |
| FLUID Token Balance | 2727350840997778921955 wei (2727.350841 FLUID) |
| Claimed (position)  | 2727350840997778921955 wei (2727.350841 FLUID) |

---

## State Changes

| Metric             | Before | After                  | Change             |
| ------------------ | ------ | ---------------------- | ------------------ |
| FLUID Balance      | 0      | 2727350840997778921955 | +2727.350841 FLUID |
| Claimed (position) | 0      | 2727350840997778921955 | +2727.350841 FLUID |

---

## Verification

| Check                                | Result |
| ------------------------------------ | ------ |
| Position ID correctly padded         | PASS   |
| Merkle proof valid                   | PASS   |
| Transaction Success                  | PASS   |
| FLUID Balance matches claimed amount | PASS   |
| Claimed mapping updated correctly    | PASS   |

---

## Key Observations

1. **Position ID Transformation**: The `positionId` from the API is a 20-byte vault address that must be left-padded to 32 bytes for the contract call.

2. **Cumulative Model**: The contract uses a cumulative claiming model where `cumulativeAmount` represents the total lifetime claimable amount. The actual transfer is `cumulativeAmount - alreadyClaimed`.

3. **msg.sender Requirement**: The contract requires `msg.sender == recipient_`. The caliber must call claim directly.

4. **No Approval Required**: This is a claim/transfer from the contract to the user, so no token approval is needed.

5. **Merkle Proof Source**: The proof must be fetched from Fluid API - the contract only stores the merkle root, not individual claim data.

6. **Gas Usage**: The claim transaction used 114,913 gas with 14 proof hashes.

---

## Issues Encountered

None. The claim executed successfully on the first attempt.

---

## Contract Addresses Reference

| Contract        | Address                                      |
| --------------- | -------------------------------------------- |
| Claims Contract | `0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0` |
| FLUID Token     | `0x6f40d4A6237C257fff2dB00FA0510DeEECd303eb` |
| fGHO Vault      | `0x6A29A46E21C730DcA1d8b23d637c101cec605C5B` |
