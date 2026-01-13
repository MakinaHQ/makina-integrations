# King Protocol Metatypes

This document describes the custom metatype(s) required for King Protocol integration with the Makina transpiler.

---

## KingClaimData

A metatype for King Protocol's cumulative merkle drop claim function.

### Purpose

Encapsulates all parameters needed to claim KING token rewards via merkle proof verification.

### Type Definition (Rust - for transpiler)

Add to `transpiler/src/meta_sol_types.rs`:

```rust
KingClaimData(KingClaimDataDef) {
    properties: [
        ("account", DynSolType::Address),
        ("cumulative_amount", DynSolType::Uint(256)),
        ("expected_merkle_root", DynSolType::FixedBytes(32)),
        ("merkle_proof", DynSolType::Array(Box::new(DynSolType::FixedBytes(32)))),
    ]
},
```

### Fields

| Field                  | Solidity Type | Description                                    |
| ---------------------- | ------------- | ---------------------------------------------- |
| `account`              | address       | The address claiming rewards (caliber address) |
| `cumulative_amount`    | uint256       | Total lifetime claimable amount in wei         |
| `expected_merkle_root` | bytes32       | Merkle root the proof was generated against    |
| `merkle_proof`         | bytes32[]     | Array of merkle proof hashes                   |

### Contract Function Mapping

```solidity
function claim(
    address account,              // from KingClaimData.account
    uint256 cumulativeAmount,     // from KingClaimData.cumulative_amount
    bytes32 expectedMerkleRoot,   // from KingClaimData.expected_merkle_root
    bytes32[] calldata merkleProof // from KingClaimData.merkle_proof
) external
```

**Function Selector:** `0x1d7d4ebc`

---

## Offchain Data Fetcher

The `KingClaimData` metatype requires offchain data from the ether.fi API.

### API Endpoint

```
GET https://www.ether.fi/api/dapp/king/{ADDRESS}
```

### Response Schema

```json
{
  "Amount": "string (uint256 in decimal)",
  "Root": "string (bytes32 hex with 0x prefix)",
  "Proofs": ["string (bytes32 hex)", ...]
}
```

---

## Rust Fetcher Implementation

Add to the Makina Rust codebase for runtime data fetching:

```rust
use alloy_primitives::{Address, FixedBytes, U256};
use reqwest;
use serde::Deserialize;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct KingApiResponse {
    pub amount: String,
    pub root: String,
    pub proofs: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct KingClaimData {
    pub account: Address,
    pub cumulative_amount: U256,
    pub expected_merkle_root: FixedBytes<32>,
    pub merkle_proof: Vec<FixedBytes<32>>,
}

impl KingClaimData {
    /// Fetch claim data from ether.fi API
    pub async fn fetch(account: Address) -> Result<Self, KingClaimError> {
        let url = format!(
            "https://www.ether.fi/api/dapp/king/{}",
            account.to_checksum(None)
        );

        let response = reqwest::get(&url).await?;

        if response.status() == reqwest::StatusCode::NOT_FOUND {
            return Err(KingClaimError::NoRewardsAllocated);
        }

        let api_response: KingApiResponse = response.json().await?;

        // Parse cumulative amount from decimal string
        let cumulative_amount = U256::from_str_radix(&api_response.amount, 10)
            .map_err(|_| KingClaimError::InvalidAmount)?;

        if cumulative_amount.is_zero() {
            return Err(KingClaimError::NothingToClaim);
        }

        // Parse merkle root
        let expected_merkle_root = api_response.root
            .parse::<FixedBytes<32>>()
            .map_err(|_| KingClaimError::InvalidMerkleRoot)?;

        // Parse merkle proof array
        let merkle_proof: Result<Vec<FixedBytes<32>>, _> = api_response.proofs
            .iter()
            .map(|p| p.parse::<FixedBytes<32>>())
            .collect();
        let merkle_proof = merkle_proof.map_err(|_| KingClaimError::InvalidProof)?;

        Ok(Self {
            account,
            cumulative_amount,
            expected_merkle_root,
            merkle_proof,
        })
    }

    /// Encode as calldata for the claim function
    pub fn encode_calldata(&self) -> Vec<u8> {
        use alloy_sol_types::SolCall;

        // Function: claim(address,uint256,bytes32,bytes32[])
        // Selector: 0x1d7d4ebc
        sol! {
            function claim(
                address account,
                uint256 cumulativeAmount,
                bytes32 expectedMerkleRoot,
                bytes32[] calldata merkleProof
            ) external;
        }

        claimCall {
            account: self.account,
            cumulativeAmount: self.cumulative_amount,
            expectedMerkleRoot: self.expected_merkle_root,
            merkleProof: self.merkle_proof.clone(),
        }
        .abi_encode()
    }
}

#[derive(Debug, thiserror::Error)]
pub enum KingClaimError {
    #[error("No rewards allocated for this address")]
    NoRewardsAllocated,

    #[error("Nothing to claim (amount is zero)")]
    NothingToClaim,

    #[error("Invalid amount format in API response")]
    InvalidAmount,

    #[error("Invalid merkle root format in API response")]
    InvalidMerkleRoot,

    #[error("Invalid merkle proof format in API response")]
    InvalidProof,

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
class KingClaimData:
    """Data required to claim KING tokens via merkle proof."""
    account: str
    cumulative_amount: int
    expected_merkle_root: bytes
    merkle_proof: List[bytes]

    @classmethod
    def fetch(cls, account: str) -> "KingClaimData":
        """Fetch claim data from ether.fi API."""
        url = f"https://www.ether.fi/api/dapp/king/{account}"
        response = requests.get(url)

        if response.status_code == 404:
            raise ValueError(f"No rewards allocated for {account}")

        response.raise_for_status()
        data = response.json()

        amount = int(data["Amount"])
        if amount == 0:
            raise ValueError("Nothing to claim (amount is zero)")

        return cls(
            account=Web3.to_checksum_address(account),
            cumulative_amount=amount,
            expected_merkle_root=bytes.fromhex(data["Root"][2:]),
            merkle_proof=[bytes.fromhex(p[2:]) for p in data["Proofs"]],
        )

    def encode_calldata(self) -> bytes:
        """Encode as calldata for claim function."""
        # Function selector: claim(address,uint256,bytes32,bytes32[])
        selector = bytes.fromhex("1d7d4ebc")

        encoded_params = encode(
            ["address", "uint256", "bytes32", "bytes32[]"],
            [
                self.account,
                self.cumulative_amount,
                self.expected_merkle_root,
                self.merkle_proof,
            ],
        )

        return selector + encoded_params

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "account": self.account,
            "cumulative_amount": str(self.cumulative_amount),
            "expected_merkle_root": "0x" + self.expected_merkle_root.hex(),
            "merkle_proof": ["0x" + p.hex() for p in self.merkle_proof],
        }


# Example usage
if __name__ == "__main__":
    CALIBER_ADDRESS = "0xD1A2d9DF5db842DA2Ee81075Fa441602B2352915"

    try:
        claim_data = KingClaimData.fetch(CALIBER_ADDRESS)
        print(f"Account: {claim_data.account}")
        print(f"Cumulative Amount: {claim_data.cumulative_amount / 1e18:.6f} KING")
        print(f"Merkle Root: 0x{claim_data.expected_merkle_root.hex()}")
        print(f"Proof Length: {len(claim_data.merkle_proof)} hashes")
        print(f"Calldata: 0x{claim_data.encode_calldata().hex()}")
    except ValueError as e:
        print(f"Error: {e}")
```

---

## Blueprint Usage

Once `KingClaimData` is added to the transpiler, use in blueprints:

```yaml
# blueprints/king/harvest.yaml
input_slots:
  king_claim_data:
    type: "KingClaimData"
    description: "Claim data fetched from ether.fi API"

instructions:
  - call:
      contract: "0x6Db24Ee656843E3fE03eb8762a54D86186bA6B64"
      function: "claim(address,uint256,bytes32,bytes32[])"
      args:
        - $king_claim_data.account
        - $king_claim_data.cumulative_amount
        - $king_claim_data.expected_merkle_root
        - $king_claim_data.merkle_proof
```

---

## Integration Checklist

- [ ] Add `KingClaimData` to `transpiler/src/meta_sol_types.rs`
- [ ] Add Rust fetcher to Makina runtime
- [ ] Add Python fetcher for testing/CLI tools
- [ ] Update blueprint with new metatype
- [ ] Test compilation with `/compile` skill
- [ ] E2E test with blueprint-tester agent
