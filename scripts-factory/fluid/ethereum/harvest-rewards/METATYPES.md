# Fluid Protocol Metatypes

This document describes the custom metatype(s) required for Fluid Protocol integration with the Makina transpiler.

---

## FluidClaimData

A metatype for Fluid Protocol's merkle-based rewards claim function.

### Purpose

Encapsulates all parameters needed to claim FLUID token rewards via merkle proof verification.

### Type Definition (Rust - for transpiler)

Add to `transpiler/src/meta_sol_types.rs`:

```rust
FluidClaimData(FluidClaimDataDef) {
    properties: [
        ("recipient", DynSolType::Address),
        ("cumulative_amount", DynSolType::Uint(256)),
        ("position_type", DynSolType::Uint(8)),
        ("position_id", DynSolType::FixedBytes(32)),
        ("cycle", DynSolType::Uint(256)),
        ("merkle_proof", DynSolType::Array(Box::new(DynSolType::FixedBytes(32)))),
        ("metadata", DynSolType::Bytes),
    ]
},
```

### Fields

| Field               | Solidity Type | Description                                         |
| ------------------- | ------------- | --------------------------------------------------- |
| `recipient`         | address       | The address claiming rewards (must == msg.sender)   |
| `cumulative_amount` | uint256       | Total lifetime claimable amount in wei              |
| `position_type`     | uint8         | Position type enum (1 = lending vault)              |
| `position_id`       | bytes32       | Position ID - vault address left-padded to 32 bytes |
| `cycle`             | uint256       | Merkle cycle number                                 |
| `merkle_proof`      | bytes32[]     | Array of merkle proof hashes                        |
| `metadata`          | bytes         | Additional metadata (typically empty 0x)            |

### Contract Function Mapping

```solidity
function claim(
    address recipient_,           // from FluidClaimData.recipient
    uint256 cumulativeAmount_,    // from FluidClaimData.cumulative_amount
    uint8 positionType_,          // from FluidClaimData.position_type
    bytes32 positionId_,          // from FluidClaimData.position_id
    uint256 cycle_,               // from FluidClaimData.cycle
    bytes32[] calldata merkleProof_, // from FluidClaimData.merkle_proof
    bytes memory metadata_        // from FluidClaimData.metadata
) external
```

**Contract Address:** `0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0`

---

## Offchain Data Fetcher

The `FluidClaimData` metatype requires offchain data from the Fluid API.

### API Endpoint

```
GET https://merkle.api.fluid.instadapp.io/programs/inst-rewards-dec-2024/users/{ADDRESS}/claims
```

### Response Schema

```json
[
  {
    "positionId": "string (20-byte address, needs left-padding to 32 bytes)",
    "positionType": "number (uint8)",
    "user": "string (address)",
    "cycle": "number (uint256)",
    "cumulativeAmountWei": "string (uint256 in decimal)",
    "metadata": "string (hex bytes)",
    "proof": ["string (bytes32 hex)", ...]
  }
]
```

### Critical Transformation: Position ID

The `positionId` from the API is a 20-byte address that must be **left-padded to 32 bytes**:

```
API:      0x6a29a46e21c730dca1d8b23d637c101cec605c5b (20 bytes)
Contract: 0x0000000000000000000000006a29a46e21c730dca1d8b23d637c101cec605c5b (32 bytes)
```

---

## Rust Fetcher Implementation

Add to the Makina Rust codebase for runtime data fetching:

```rust
use alloy_primitives::{Address, FixedBytes, U256};
use reqwest;
use serde::Deserialize;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FluidApiClaimResponse {
    pub position_id: String,
    pub position_type: u8,
    pub user: Address,
    pub cycle: u64,
    pub cumulative_amount_wei: String,
    pub metadata: String,
    pub proof: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct FluidClaimData {
    pub recipient: Address,
    pub cumulative_amount: U256,
    pub position_type: u8,
    pub position_id: FixedBytes<32>,
    pub cycle: U256,
    pub merkle_proof: Vec<FixedBytes<32>>,
    pub metadata: Vec<u8>,
}

impl FluidClaimData {
    /// Fetch claim data from Fluid API
    pub async fn fetch(account: Address) -> Result<Vec<Self>, FluidClaimError> {
        let url = format!(
            "https://merkle.api.fluid.instadapp.io/programs/inst-rewards-dec-2024/users/{}/claims",
            account.to_checksum(None)
        );

        let response = reqwest::get(&url).await?;

        if response.status() == reqwest::StatusCode::NOT_FOUND {
            return Err(FluidClaimError::NoRewardsAllocated);
        }

        let api_responses: Vec<FluidApiClaimResponse> = response.json().await?;

        if api_responses.is_empty() {
            return Err(FluidClaimError::NothingToClaim);
        }

        let mut claims = Vec::new();
        for api_response in api_responses {
            // Parse position ID and left-pad to 32 bytes
            let position_id_str = api_response.position_id
                .strip_prefix("0x")
                .unwrap_or(&api_response.position_id);

            let mut position_id_bytes = [0u8; 32];
            let addr_bytes = hex::decode(position_id_str)?;
            position_id_bytes[12..32].copy_from_slice(&addr_bytes);

            // Parse cumulative amount
            let cumulative_amount = U256::from_str_radix(&api_response.cumulative_amount_wei, 10)
                .map_err(|_| FluidClaimError::InvalidAmount)?;

            // Parse merkle proof
            let merkle_proof: Result<Vec<FixedBytes<32>>, _> = api_response.proof
                .iter()
                .map(|p| {
                    let hex_str = p.strip_prefix("0x").unwrap_or(p);
                    let bytes = hex::decode(hex_str)?;
                    Ok(FixedBytes::from_slice(&bytes))
                })
                .collect();
            let merkle_proof = merkle_proof?;

            // Parse metadata
            let metadata = if api_response.metadata == "0x" || api_response.metadata.is_empty() {
                vec![]
            } else {
                let hex_str = api_response.metadata.strip_prefix("0x").unwrap_or(&api_response.metadata);
                hex::decode(hex_str)?
            };

            claims.push(Self {
                recipient: api_response.user,
                cumulative_amount,
                position_type: api_response.position_type,
                position_id: FixedBytes::from(position_id_bytes),
                cycle: U256::from(api_response.cycle),
                merkle_proof,
                metadata,
            });
        }

        Ok(claims)
    }

    /// Encode as calldata for the claim function
    pub fn encode_calldata(&self) -> Vec<u8> {
        use alloy_sol_types::SolCall;

        sol! {
            function claim(
                address recipient_,
                uint256 cumulativeAmount_,
                uint8 positionType_,
                bytes32 positionId_,
                uint256 cycle_,
                bytes32[] calldata merkleProof_,
                bytes memory metadata_
            ) external;
        }

        claimCall {
            recipient_: self.recipient,
            cumulativeAmount_: self.cumulative_amount,
            positionType_: self.position_type,
            positionId_: self.position_id,
            cycle_: self.cycle,
            merkleProof_: self.merkle_proof.clone(),
            metadata_: self.metadata.clone().into(),
        }
        .abi_encode()
    }
}

#[derive(Debug, thiserror::Error)]
pub enum FluidClaimError {
    #[error("No rewards allocated for this address")]
    NoRewardsAllocated,

    #[error("Nothing to claim (empty response)")]
    NothingToClaim,

    #[error("Invalid amount format in API response")]
    InvalidAmount,

    #[error("Invalid hex format: {0}")]
    HexDecode(#[from] hex::FromHexError),

    #[error("HTTP request failed: {0}")]
    Request(#[from] reqwest::Error),
}
```

---

## Python Fetcher Implementation

For testing and scripting:

```python
from dataclasses import dataclass
from typing import List
import requests
from web3 import Web3
from eth_abi import encode


@dataclass
class FluidClaimData:
    """Data required to claim FLUID tokens via merkle proof."""
    recipient: str
    cumulative_amount: int
    position_type: int
    position_id: bytes  # 32 bytes, left-padded
    cycle: int
    merkle_proof: List[bytes]
    metadata: bytes

    @classmethod
    def fetch(cls, account: str) -> List["FluidClaimData"]:
        """Fetch claim data from Fluid API."""
        url = f"https://merkle.api.fluid.instadapp.io/programs/inst-rewards-dec-2024/users/{account}/claims"
        response = requests.get(url)

        if response.status_code == 404:
            raise ValueError(f"No rewards allocated for {account}")

        response.raise_for_status()
        data = response.json()

        if not data:
            raise ValueError("Nothing to claim (empty response)")

        claims = []
        for item in data:
            # Left-pad positionId from 20 bytes to 32 bytes
            position_id_hex = item["positionId"]
            position_id_clean = position_id_hex[2:] if position_id_hex.startswith("0x") else position_id_hex
            position_id_padded = position_id_clean.zfill(64)
            position_id_bytes = bytes.fromhex(position_id_padded)

            # Parse metadata
            metadata_hex = item["metadata"]
            if metadata_hex == "0x" or metadata_hex == "":
                metadata = b""
            else:
                metadata = bytes.fromhex(metadata_hex[2:] if metadata_hex.startswith("0x") else metadata_hex)

            # Parse merkle proof
            merkle_proof = [
                bytes.fromhex(p[2:] if p.startswith("0x") else p)
                for p in item["proof"]
            ]

            claims.append(cls(
                recipient=Web3.to_checksum_address(item["user"]),
                cumulative_amount=int(item["cumulativeAmountWei"]),
                position_type=int(item["positionType"]),
                position_id=position_id_bytes,
                cycle=int(item["cycle"]),
                merkle_proof=merkle_proof,
                metadata=metadata,
            ))

        return claims

    def encode_calldata(self) -> bytes:
        """Encode as calldata for claim function."""
        encoded_params = encode(
            ["address", "uint256", "uint8", "bytes32", "uint256", "bytes32[]", "bytes"],
            [
                self.recipient,
                self.cumulative_amount,
                self.position_type,
                self.position_id,
                self.cycle,
                self.merkle_proof,
                self.metadata,
            ],
        )

        return encoded_params

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "recipient": self.recipient,
            "cumulative_amount": str(self.cumulative_amount),
            "position_type": self.position_type,
            "position_id": "0x" + self.position_id.hex(),
            "cycle": self.cycle,
            "merkle_proof": ["0x" + p.hex() for p in self.merkle_proof],
            "metadata": "0x" + self.metadata.hex() if self.metadata else "0x",
        }


# Example usage
if __name__ == "__main__":
    CALIBER_ADDRESS = "0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC"

    try:
        claims = FluidClaimData.fetch(CALIBER_ADDRESS)
        for claim in claims:
            print(f"Recipient: {claim.recipient}")
            print(f"Cumulative Amount: {claim.cumulative_amount / 1e18:.6f} FLUID")
            print(f"Position Type: {claim.position_type}")
            print(f"Position ID: 0x{claim.position_id.hex()}")
            print(f"Cycle: {claim.cycle}")
            print(f"Proof Length: {len(claim.merkle_proof)} hashes")
    except ValueError as e:
        print(f"Error: {e}")
```

---

## Blueprint Usage

Once `FluidClaimData` is added to the transpiler, use in blueprints:

```yaml
# blueprints/fluid/harvest.yaml
protocol: "fluid"

inputs:
  claims_contract_address:
    type: "address"

actions:
  harvest:
    calls:
      - description: "Claim FLUID rewards using merkle proof"
        target: "${inputs.claims_contract_address}"
        selector: "claim(address,uint256,uint8,bytes32,uint256,bytes32[],bytes)"
        parameters:
          - type: "address"
            value: "${input_slots.fluid_claim_data.recipient}"
          - type: "uint256"
            value: "${input_slots.fluid_claim_data.cumulative_amount}"
          - type: "uint8"
            value: "${input_slots.fluid_claim_data.position_type}"
          - type: "bytes32"
            value: "${input_slots.fluid_claim_data.position_id}"
          - type: "uint256"
            value: "${input_slots.fluid_claim_data.cycle}"
          - type: "bytes32[]"
            value: "${input_slots.fluid_claim_data.merkle_proof}"
          - type: "bytes"
            value: "${input_slots.fluid_claim_data.metadata}"

    input_slots:
      fluid_claim_data:
        type: "FluidClaimData"
```

---

## Integration Checklist

- [ ] Add `FluidClaimData` to `transpiler/src/meta_sol_types.rs`
- [ ] Add Rust fetcher to Makina runtime
- [ ] Add Python fetcher for testing/CLI tools
- [ ] Update blueprint with new metatype
- [ ] Test compilation with `/compile` skill
- [ ] E2E test with blueprint-tester agent
