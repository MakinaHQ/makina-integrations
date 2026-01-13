# King Protocol API Documentation

## Endpoint

```
GET https://www.ether.fi/api/dapp/king/{ADDRESS}
```

Where `{ADDRESS}` is the wallet address claiming rewards (e.g., the caliber address).

## Response Structure

```json
{
  "Amount": "11385832910371565296",
  "Root": "0xa5e4a3c599a82b6cb74148b61d77f327ff5ced4eac5faa5a3887c5f6402f6d01",
  "Proofs": [
    "0x...",
    "0x...",
    // ... array of bytes32 proof hashes
  ],
  "HistoricalRewards": [
    {
      "Amount": "11385832910371565296",
      "AwardDate": "2025-12-21T00:00:00Z",
      "Root": "0x..."
    }
    // ... historical records
  ]
}
```

## Fields

| Field               | Type     | Description                                      |
| ------------------- | -------- | ------------------------------------------------ |
| `Amount`            | string   | Cumulative claimable amount in wei (18 decimals) |
| `Root`              | string   | Merkle root the proofs were generated against    |
| `Proofs`            | string[] | Array of bytes32 merkle proof hashes             |
| `HistoricalRewards` | array    | Historical distribution records                  |

## Mapping to Contract Parameters

The API response maps directly to the `claim` function parameters:

| API Field | Contract Parameter   | Type      |
| --------- | -------------------- | --------- |
| `Amount`  | `cumulativeAmount`   | uint256   |
| `Root`    | `expectedMerkleRoot` | bytes32   |
| `Proofs`  | `merkleProof`        | bytes32[] |
| (caller)  | `account`            | address   |

## Python Implementation

```python
import requests
from web3 import Web3

def get_king_claim_data(address: str) -> dict:
    """
    Fetch King Protocol claim data for an address.

    Args:
        address: The wallet address to fetch claim data for

    Returns:
        dict with keys: account, cumulative_amount, merkle_root, merkle_proof
    """
    url = f"https://www.ether.fi/api/dapp/king/{address}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    return {
        "account": Web3.to_checksum_address(address),
        "cumulative_amount": int(data["Amount"]),
        "merkle_root": data["Root"],
        "merkle_proof": data["Proofs"],
    }


def build_claim_calldata(claim_data: dict) -> bytes:
    """
    Build the calldata for the claim function.

    Function signature: claim(address,uint256,bytes32,bytes32[])
    Selector: 0x1d7d4ebc
    """
    from eth_abi import encode

    # Encode parameters
    encoded = encode(
        ['address', 'uint256', 'bytes32', 'bytes32[]'],
        [
            claim_data["account"],
            claim_data["cumulative_amount"],
            bytes.fromhex(claim_data["merkle_root"][2:]),
            [bytes.fromhex(p[2:]) for p in claim_data["merkle_proof"]]
        ]
    )

    # Prepend function selector
    selector = bytes.fromhex("1d7d4ebc")
    return selector + encoded


# Example usage
if __name__ == "__main__":
    CALIBER_ADDRESS = "0xD1A2d9DF5db842DA2Ee81075Fa441602B2352915"

    claim_data = get_king_claim_data(CALIBER_ADDRESS)

    print(f"Account: {claim_data['account']}")
    print(f"Cumulative Amount: {claim_data['cumulative_amount']} wei")
    print(f"Cumulative Amount: {claim_data['cumulative_amount'] / 1e18:.6f} KING")
    print(f"Merkle Root: {claim_data['merkle_root']}")
    print(f"Proof Length: {len(claim_data['merkle_proof'])} hashes")
```

## Rust Implementation

```rust
use reqwest;
use serde::{Deserialize, Serialize};
use alloy_primitives::{Address, U256, FixedBytes};

#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct KingApiResponse {
    pub amount: String,
    pub root: String,
    pub proofs: Vec<String>,
    pub historical_rewards: Option<Vec<HistoricalReward>>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct HistoricalReward {
    pub amount: String,
    pub award_date: String,
    pub root: String,
}

#[derive(Debug)]
pub struct KingClaimData {
    pub account: Address,
    pub cumulative_amount: U256,
    pub merkle_root: FixedBytes<32>,
    pub merkle_proof: Vec<FixedBytes<32>>,
}

impl KingClaimData {
    pub async fn fetch(address: &str) -> Result<Self, reqwest::Error> {
        let url = format!("https://www.ether.fi/api/dapp/king/{}", address);
        let response: KingApiResponse = reqwest::get(&url).await?.json().await?;

        let account = address.parse::<Address>().expect("Invalid address");
        let cumulative_amount = U256::from_str_radix(&response.amount, 10)
            .expect("Invalid amount");
        let merkle_root = response.root.parse::<FixedBytes<32>>()
            .expect("Invalid merkle root");
        let merkle_proof: Vec<FixedBytes<32>> = response.proofs
            .iter()
            .map(|p| p.parse::<FixedBytes<32>>().expect("Invalid proof hash"))
            .collect();

        Ok(Self {
            account,
            cumulative_amount,
            merkle_root,
            merkle_proof,
        })
    }
}

// Example usage with alloy for contract interaction
/*
use alloy_sol_types::sol;

sol! {
    #[sol(rpc)]
    interface IKingClaim {
        function claim(
            address account,
            uint256 cumulativeAmount,
            bytes32 expectedMerkleRoot,
            bytes32[] calldata merkleProof
        ) external;

        function cumulativeClaimed(address account) external view returns (uint256);
        function merkleRoot() external view returns (bytes32);
    }
}

async fn claim_king_rewards(
    contract: &IKingClaimInstance,
    claim_data: &KingClaimData,
) -> Result<TransactionReceipt, Error> {
    let tx = contract.claim(
        claim_data.account,
        claim_data.cumulative_amount,
        claim_data.merkle_root,
        claim_data.merkle_proof.clone(),
    );

    tx.send().await?.get_receipt().await
}
*/
```

## Calculating Claimable Amount

The actual claimable amount is:

```
claimable = API.Amount - contract.cumulativeClaimed(address)
```

To check if there's anything to claim:

```python
from web3 import Web3

def get_claimable_amount(web3: Web3, address: str) -> int:
    """Calculate actual claimable KING tokens."""
    CLAIMS_CONTRACT = "0x6Db24Ee656843E3fE03eb8762a54D86186bA6B64"

    # Get cumulative amount from API
    claim_data = get_king_claim_data(address)
    cumulative_amount = claim_data["cumulative_amount"]

    # Get already claimed from contract
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(CLAIMS_CONTRACT),
        abi=[{
            "inputs": [{"name": "account", "type": "address"}],
            "name": "cumulativeClaimed",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }]
    )

    already_claimed = contract.functions.cumulativeClaimed(
        Web3.to_checksum_address(address)
    ).call()

    return cumulative_amount - already_claimed
```

## Error Handling

The API may return:

- **200**: Success with claim data
- **404**: Address not found in merkle tree (no rewards)
- **500**: Server error

If the address has no rewards allocated, handle gracefully:

```python
def get_king_claim_data_safe(address: str) -> dict | None:
    """Fetch claim data, returning None if no rewards."""
    try:
        response = requests.get(f"https://www.ether.fi/api/dapp/king/{address}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        if not data.get("Amount") or data["Amount"] == "0":
            return None
        return {
            "account": Web3.to_checksum_address(address),
            "cumulative_amount": int(data["Amount"]),
            "merkle_root": data["Root"],
            "merkle_proof": data["Proofs"],
        }
    except requests.RequestException:
        return None
```
