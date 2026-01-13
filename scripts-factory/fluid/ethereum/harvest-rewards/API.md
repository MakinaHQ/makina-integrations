# Fluid Protocol API Documentation

## Endpoint

```
GET https://merkle.api.fluid.instadapp.io/programs/inst-rewards-dec-2024/users/{ADDRESS}/claims
```

Where `{ADDRESS}` is the wallet address claiming rewards (e.g., the caliber address).

## Response Structure

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
      "..."
    ]
  }
]
```

## Fields

| Field                 | Type     | Description                                      |
| --------------------- | -------- | ------------------------------------------------ |
| `positionId`          | string   | Vault/position address (20 bytes, needs padding) |
| `positionType`        | number   | Position type enum (1 = lending vault)           |
| `user`                | string   | User wallet address                              |
| `cycle`               | number   | Merkle tree cycle number                         |
| `amount`              | string   | Current cycle rewards (human-readable)           |
| `amountWei`           | string   | Current cycle rewards (wei)                      |
| `cumulativeAmount`    | string   | Total cumulative rewards (human-readable)        |
| `cumulativeAmountWei` | string   | Total cumulative rewards (wei) - USE THIS        |
| `metadata`            | string   | Hex-encoded metadata bytes                       |
| `proof`               | string[] | Array of bytes32 merkle proof hashes             |

## Mapping to Contract Parameters

The API response maps to the `claim` function parameters:

| API Field             | Contract Parameter  | Type      | Transformation                   |
| --------------------- | ------------------- | --------- | -------------------------------- |
| `user`                | `recipient_`        | address   | Direct                           |
| `cumulativeAmountWei` | `cumulativeAmount_` | uint256   | Parse string to int              |
| `positionType`        | `positionType_`     | uint8     | Direct                           |
| `positionId`          | `positionId_`       | bytes32   | **Left-pad to 32 bytes**         |
| `cycle`               | `cycle_`            | uint256   | Direct                           |
| `proof`               | `merkleProof_`      | bytes32[] | Parse hex strings                |
| `metadata`            | `metadata_`         | bytes     | Parse hex string (usually empty) |

## Critical: Position ID Transformation

The `positionId` from the API is a **20-byte address** that must be **left-padded to 32 bytes**:

```
API returns:      0x6a29a46e21c730dca1d8b23d637c101cec605c5b
Contract expects: 0x0000000000000000000000006a29a46e21c730dca1d8b23d637c101cec605c5b
```

## Python Implementation

```python
import requests
from dataclasses import dataclass
from typing import List, Optional
from web3 import Web3


@dataclass
class FluidClaimData:
    """Data required for Fluid claim transaction."""
    recipient: str
    cumulative_amount: int
    position_type: int
    position_id: bytes  # 32 bytes, left-padded
    cycle: int
    merkle_proof: List[bytes]
    metadata: bytes

    @classmethod
    def fetch(cls, address: str, position_id_filter: Optional[str] = None) -> List["FluidClaimData"]:
        """
        Fetch claim data from Fluid API.

        Args:
            address: Wallet address to fetch claims for
            position_id_filter: Optional specific position to filter for

        Returns:
            List of FluidClaimData objects
        """
        url = f"https://merkle.api.fluid.instadapp.io/programs/inst-rewards-dec-2024/users/{address}/claims"
        response = requests.get(url)
        response.raise_for_status()

        data = response.json()
        if not isinstance(data, list):
            raise ValueError(f"Expected list response, got {type(data)}")

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

            claim = cls(
                recipient=Web3.to_checksum_address(item["user"]),
                cumulative_amount=int(item["cumulativeAmountWei"]),
                position_type=int(item["positionType"]),
                position_id=position_id_bytes,
                cycle=int(item["cycle"]),
                merkle_proof=merkle_proof,
                metadata=metadata,
            )

            if position_id_filter:
                filter_lower = position_id_filter.lower()
                if item["positionId"].lower() == filter_lower:
                    claims.append(claim)
            else:
                claims.append(claim)

        return claims

    def encode_calldata(self) -> bytes:
        """Encode as calldata for claim function."""
        from eth_abi import encode

        # Function signature: claim(address,uint256,uint8,bytes32,uint256,bytes32[],bytes)
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

        # Note: You'll need to prepend the function selector
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

    claims = FluidClaimData.fetch(CALIBER_ADDRESS)

    print(f"Found {len(claims)} claim(s) for {CALIBER_ADDRESS}")

    for i, claim in enumerate(claims):
        print(f"\n=== Claim {i + 1} ===")
        print(f"Recipient: {claim.recipient}")
        print(f"Cumulative Amount: {claim.cumulative_amount / 1e18:.6f} FLUID")
        print(f"Position Type: {claim.position_type}")
        print(f"Position ID: 0x{claim.position_id.hex()}")
        print(f"Cycle: {claim.cycle}")
        print(f"Proof Length: {len(claim.merkle_proof)} hashes")
```

## Rust Implementation

```rust
use reqwest;
use serde::Deserialize;
use alloy_primitives::{Address, FixedBytes, U256};

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FluidApiClaimResponse {
    pub position_id: String,
    pub position_type: u8,
    pub user: Address,
    pub cycle: u64,
    pub amount: String,
    pub amount_wei: String,
    pub cumulative_amount: String,
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
    pub async fn fetch(address: Address) -> Result<Vec<Self>, FluidClaimError> {
        let url = format!(
            "https://merkle.api.fluid.instadapp.io/programs/inst-rewards-dec-2024/users/{}/claims",
            address.to_checksum(None)
        );

        let response = reqwest::get(&url).await?;

        if response.status() == reqwest::StatusCode::NOT_FOUND {
            return Ok(vec![]);
        }

        let api_responses: Vec<FluidApiClaimResponse> = response.json().await?;

        let mut claims = Vec::new();
        for api_response in api_responses {
            let claim = Self::from_api_response(api_response)?;
            claims.push(claim);
        }

        Ok(claims)
    }

    fn from_api_response(response: FluidApiClaimResponse) -> Result<Self, FluidClaimError> {
        // Parse position ID and left-pad to 32 bytes
        let position_id_str = response.position_id
            .strip_prefix("0x")
            .unwrap_or(&response.position_id);

        // Left-pad 20-byte address to 32 bytes
        let mut position_id_bytes = [0u8; 32];
        let addr_bytes = hex::decode(position_id_str)?;
        position_id_bytes[12..32].copy_from_slice(&addr_bytes);

        // Parse cumulative amount
        let cumulative_amount = U256::from_str_radix(&response.cumulative_amount_wei, 10)
            .map_err(|_| FluidClaimError::InvalidAmount)?;

        // Parse merkle proof
        let merkle_proof: Result<Vec<FixedBytes<32>>, _> = response.proof
            .iter()
            .map(|p| {
                let hex_str = p.strip_prefix("0x").unwrap_or(p);
                let bytes = hex::decode(hex_str)?;
                Ok(FixedBytes::from_slice(&bytes))
            })
            .collect();
        let merkle_proof = merkle_proof?;

        // Parse metadata
        let metadata = if response.metadata == "0x" || response.metadata.is_empty() {
            vec![]
        } else {
            let hex_str = response.metadata.strip_prefix("0x").unwrap_or(&response.metadata);
            hex::decode(hex_str)?
        };

        Ok(Self {
            recipient: response.user,
            cumulative_amount,
            position_type: response.position_type,
            position_id: FixedBytes::from(position_id_bytes),
            cycle: U256::from(response.cycle),
            merkle_proof,
            metadata,
        })
    }

    /// Encode as calldata for claim() function
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
    #[error("Invalid amount format in API response")]
    InvalidAmount,

    #[error("Invalid hex format: {0}")]
    HexDecode(#[from] hex::FromHexError),

    #[error("HTTP request failed: {0}")]
    Request(#[from] reqwest::Error),
}
```

## Calculating Claimable Amount

The actual claimable amount is:

```
claimable = API.cumulativeAmountWei - contract.claimed(address, positionId)
```

To check if there's anything to claim:

```python
from web3 import Web3

def get_claimable_amount(web3: Web3, address: str, position_id: bytes) -> int:
    """Calculate actual claimable FLUID tokens."""
    CLAIMS_CONTRACT = "0x7060FE0Dd3E31be01EFAc6B28C8D38018fD163B0"

    # Get cumulative amount from API
    claims = FluidClaimData.fetch(address)
    if not claims:
        return 0

    claim = claims[0]  # Or filter by position_id
    cumulative_amount = claim.cumulative_amount

    # Get already claimed from contract
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(CLAIMS_CONTRACT),
        abi=[{
            "inputs": [
                {"name": "", "type": "address"},
                {"name": "", "type": "bytes32"}
            ],
            "name": "claimed",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }]
    )

    already_claimed = contract.functions.claimed(
        Web3.to_checksum_address(address),
        position_id
    ).call()

    return cumulative_amount - already_claimed
```

## Error Handling

The API may return:

- **200**: Success with claim data (array)
- **200 with `[]`**: No rewards allocated for this address
- **404**: Address not found
- **500**: Server error

Handle gracefully:

```python
def get_fluid_claim_data_safe(address: str) -> list | None:
    """Fetch claim data, returning None if no rewards."""
    try:
        response = requests.get(
            f"https://merkle.api.fluid.instadapp.io/programs/inst-rewards-dec-2024/users/{address}/claims"
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        if not data or len(data) == 0:
            return None
        return data
    except requests.RequestException:
        return None
```
