---
name: caliber-token-setup
description: "**Setup** - Add tokens to Caliber with oracle feed configuration (requires Tenderly testnet). Sets oracle feed routes and adds base tokens by impersonating authorized addresses."
allowed-tools: Read, mcp__tenderly__*, mcp__pools_db__*
---

# Base Token & Oracle Setup Skill

## Overview
This skill enables adding tokens as base tokens to the Caliber protocol with proper oracle configuration. The process involves two operations:
1. Setting an oracle feed route in the Oracle Registry
2. Adding the token as a base token in Caliber

Both operations require impersonating authorized addresses on Tenderly testnet.

## When to Use
Use this skill when:
- Adding support for a new token in the Caliber protocol
- Configuring price feeds for tokens used in DeFi strategies
- Testing token integrations on Tenderly testnets
- Setting up oracle infrastructure for token valuations

## Prerequisites
- Tenderly testnet RPC URL
- Token must have a valid Chainlink (or compatible) price feed
- Access to addresses with proper permissions:
  - DAO address (for Oracle Registry operations)
  - Timelock Controller address (for Caliber operations)

## Contract Addresses Required
- **Oracle Registry**: Contract managing price feed routes
- **Caliber**: Token registry and base token management
- **Token Address**: The token to be added
- **Price Feed Address**: Chainlink oracle for the token
- **DAO Address**: Has permission to call `setFeedRoute`
- **Timelock Controller**: Has permission to call `addBaseToken`

## Step-by-Step Process

### Step 1: Set Oracle Feed Route
Configure the price feed in the Oracle Registry by impersonating the DAO address.

**Required ABI:**
```python
oracle_abi = [{
    "inputs": [
        {"name": "token", "type": "address"},
        {"name": "feed1", "type": "address"},
        {"name": "stalenessThreshold1", "type": "uint256"},
        {"name": "feed2", "type": "address"},
        {"name": "stalenessThreshold2", "type": "uint256"}
    ],
    "name": "setFeedRoute",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
}]
```

**Actions:**
1. Checksum all addresses
2. Impersonate DAO address using Tenderly
3. Fund DAO address with native tokens
4. Call `setFeedRoute(token, feed1, stalenessThreshold1, feed2, stalenessThreshold2)`
5. Wait for transaction receipt and verify success

**Parameters:**
- `token`: Token address
- `feed1`: Primary price feed address
- `stalenessThreshold1`: Maximum age for feed data (typically 86400 = 24 hours)
- `feed2`: Secondary feed (use zero address if not needed)
- `stalenessThreshold2`: Threshold for secondary feed (0 if not used)

### Step 2: Add Base Token to Caliber
Add the token as a base token by impersonating the Timelock Risk Manager.

**Required ABI:**
```python
caliber_abi = [{
    "inputs": [{"name": "token", "type": "address"}],
    "name": "addBaseToken",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
}]
```

**Actions:**
1. Impersonate Timelock Controller address
2. Fund Timelock with native tokens
3. Call `addBaseToken(token)`
4. Wait for transaction receipt and verify success

### Step 3: Verification
Verify the token was added successfully.

**Verification ABI:**
```python
verify_abi = [{
    "inputs": [{"name": "token", "type": "address"}],
    "name": "isBaseToken",
    "outputs": [{"name": "", "type": "bool"}],
    "stateMutability": "view",
    "type": "function"
}]
```

Call `isBaseToken(token)` to confirm it returns `true`.

## Implementation Example

```python
from web3 import Web3

# Configuration
RPC_URL = "https://virtual.mainnet.eu.rpc.tenderly.co/YOUR-TESTNET-ID"
web3 = Web3(Web3.HTTPProvider(RPC_URL))

# Addresses (checksum)
oracle_registry = Web3.to_checksum_address("ORACLE_REGISTRY_ADDRESS")
caliber = Web3.to_checksum_address("CALIBER_ADDRESS")
token = Web3.to_checksum_address("TOKEN_ADDRESS")
price_feed = Web3.to_checksum_address("PRICE_FEED_ADDRESS")
dao = Web3.to_checksum_address("DAO_ADDRESS")
timelock = Web3.to_checksum_address("TIMELOCK_ADDRESS")
zero_address = Web3.to_checksum_address("0x0000000000000000000000000000000000000000")

# Step 1: Set Oracle Feed
oracle_abi = [{"inputs": [...], "name": "setFeedRoute", ...}]
web3.provider.make_request("tenderly_setBalance", [[dao], "0x56BC75E2D63100000"])
web3.provider.make_request("tenderly_impersonateAccount", [dao])

oracle_contract = web3.eth.contract(address=oracle_registry, abi=oracle_abi)
tx1 = oracle_contract.functions.setFeedRoute(
    token, price_feed, 86400, zero_address, 0
).transact({"from": dao, "gas": 500000})

receipt1 = web3.eth.wait_for_transaction_receipt(tx1)
assert receipt1['status'] == 1, "Oracle setup failed"

# Step 2: Add Base Token
caliber_abi = [{"inputs": [...], "name": "addBaseToken", ...}]
web3.provider.make_request("tenderly_setBalance", [[timelock], "0x56BC75E2D63100000"])
web3.provider.make_request("tenderly_impersonateAccount", [timelock])

caliber_contract = web3.eth.contract(address=caliber, abi=caliber_abi)
tx2 = caliber_contract.functions.addBaseToken(token).transact(
    {"from": timelock, "gas": 500000}
)

receipt2 = web3.eth.wait_for_transaction_receipt(tx2)
assert receipt2['status'] == 1, "Base token addition failed"

# Step 3: Verify
verify_abi = [{"inputs": [...], "name": "isBaseToken", ...}]
verify_contract = web3.eth.contract(address=caliber, abi=verify_abi)
is_base = verify_contract.functions.isBaseToken(token).call()
assert is_base == True, "Verification failed"

print(f"✓ Token added successfully!")
print(f"Oracle TX: {tx1.hex()}")
print(f"Base Token TX: {tx2.hex()}")
```

## Important Notes

### Order of Operations
**CRITICAL**: Oracle feed must be set BEFORE adding the token as a base token. Caliber likely checks for oracle existence when adding base tokens.

### Impersonation
- Each operation requires impersonating a different address
- Always fund addresses before impersonating (use `tenderly_setBalance`)
- Funding amount: `0x56BC75E2D63100000` (100 ETH in wei)

### Staleness Thresholds
- **86400 seconds (24 hours)**: Standard for most assets
- **3600 seconds (1 hour)**: For volatile assets requiring fresh data
- Adjust based on oracle update frequency and risk tolerance

### Gas Limits
- Oracle operations: ~100k-150k gas
- Base token operations: ~100k-150k gas
- Set transaction gas to 500k for safety margin

### Error Handling
Always check transaction receipts:
```python
if receipt['status'] != 1:
    raise Exception(f"Transaction failed: {tx_hash.hex()}")
```

### Secondary Feeds
For dual oracle setups:
- Set `feed2` to a valid oracle address
- Set appropriate `stalenessThreshold2`
- Provides redundancy and increased security
- Most setups use single feed (set feed2 to zero address)

## Common Issues

### Transaction Reverts
- **"Unauthorized"**: Wrong impersonation address or insufficient permissions
- **"Oracle not set"**: When adding base token before setting oracle
- **"Invalid feed"**: Price feed address incorrect or incompatible

### Verification Failures
- Allow a few seconds after transaction for state updates
- Re-query if initial verification returns false
- Check transaction logs for events

## Testing Checklist
- [ ] Oracle feed address is valid and active
- [ ] Token address is correct (not a proxy if unintended)
- [ ] DAO address has `setFeedRoute` permission
- [ ] Timelock has `addBaseToken` permission
- [ ] Both transactions succeeded (status == 1)
- [ ] Verification confirms `isBaseToken` returns true
- [ ] Gas usage is reasonable (under 200k per transaction)

## Integration with MCP Tools

When using Tenderly MCP tools:
```python
# Use tenderly:execute_code for full transaction flow
# Use tenderly:debug_tx for transaction analysis if issues occur
# Use tenderly:get_tenderly_rpc_url for RPC endpoint retrieval
```

## Related Operations
- **Removing base tokens**: Use `removeBaseToken` (requires timelock)
- **Updating oracle feeds**: Call `setFeedRoute` again with new parameters
- **Checking oracle prices**: Use `getPrice` or `getLatestPrice` on Oracle Registry