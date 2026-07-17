---
name: caliber-token-setup
description: "**Setup** - Add base tokens to Caliber with oracle feed configuration on a mainnet FORK (Tenderly testnet OR local anvil). Registers oracle feed routes, then adds base tokens by impersonating authorized addresses."
allowed-tools: Read, mcp__tenderly__*
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
- Tenderly testnet RPC URL (both public and admin/dev)
- Token must have a valid Chainlink (or compatible) price feed
- Access to addresses with proper permissions:
  - **AccessManager admin (role 0)**: Can grant roles to other addresses
  - **Role 1 holder**: Has permission to call `setFeedRoute` on OracleRegistry
  - **riskManagerTimelock**: Has permission to call `addBaseToken` on Caliber

## Fork Options (Tenderly testnet OR local anvil)
Two interchangeable ways to get a mainnet fork. Prefer **local anvil** whenever the Tenderly MCP connector token has expired / is unavailable — anvil needs no connector and is the reliable fallback that unblocks the whole flow.

**Local anvil (foundry, no connector needed):**
```bash
anvil --fork-url "$MAINNET_RPC_URL"        # serves http://127.0.0.1:8545
# RPC cheats used throughout this skill:
#   cast rpc anvil_impersonateAccount <addr>
#   cast rpc anvil_setBalance <addr> 0x56BC75E2D63100000
#   cast rpc evm_increaseTime <seconds>              # time-warp (see Staleness Thresholds)
#   forge create ... --rpc-url http://127.0.0.1:8545 # deploy helper/mock contracts
# Send impersonated txs with:  cast send <to> "<sig>" <args> --from <addr> --unlocked --rpc-url ...
```

**Tenderly testnet (MCP):** use `mcp__tenderly__fund_address`, `mcp__tenderly__send_transaction`, `mcp__tenderly__call_view_function` with the same calldata as the cast examples (impersonation is implicit).

Every `cast`/`anvil` example below assumes `RPC_URL` points at whichever fork you started.

## Contract Addresses Required
- **Oracle Registry**: Contract managing price feed routes
- **AccessManager**: Controls who can call `setFeedRoute` (role-based access via OpenZeppelin AccessManager)
- **Caliber**: Token registry and base token management
- **Token Address**: The token to be added
- **Price Feed Address**: Chainlink oracle for the token
- **riskManagerTimelock**: Has `addBaseToken` permission on Caliber (query via `caliber.riskManagerTimelock()`)

## Known Addresses (mainnet)

| Contract | Address |
|----------|---------|
| OracleRegistry | `0xC388B72AB90Be82B230D919F9C05c87F9397f485` |
| AccessManager (proxy — is the `authority()` of BOTH OracleRegistry and Caliber) | `0x0FceFa3f1047F35521A49cD8B06faBd588665d7f` |
| **Zero-delay ADMIN (role 0) — USE THIS ONE for grants** | `0x8d28a69328561ef9f171c58996fecb9f494e070c` |
| Delayed Safe admin (role 0, has execution delay — grants do NOT take effect immediately, DO NOT USE) | `0x62244c74e1d09b3d86ef7342d354b5d7770bde10` |
| riskManagerTimelock (calls 1-arg `addBaseToken` on Caliber) | `0x7c405bbd131e42af506d14e752f2e59b19d49997` |
| Shared USDC/USD quote feed (2nd hop of most routes — bump ITS staleness too) | `0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6` |
| Caliber (dusd example) | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` |

## Step-by-Step Process

### Step 1: Ensure Oracle Permissions (AccessManager Role 1)

The OracleRegistry uses **OpenZeppelin AccessManager** for access control. `setFeedRoute` requires **role 1**.

**Discovery process** (if addresses are not known):

```bash
# 1. Find the AccessManager from OracleRegistry
ACCESS_MANAGER=$(cast call $ORACLE_REGISTRY "authority()(address)" --rpc-url "$RPC_URL")

# 2. Find the admin (role 0) who can grant roles
# Query RoleGranted events filtered by role 0
cast logs --from-block 0 --to-block latest \
  --address $ACCESS_MANAGER \
  "RoleGranted(uint64,address,uint32,uint48,bool)" \
  0x0000000000000000000000000000000000000000000000000000000000000000 \
  --rpc-url "$RPC_URL"

# 3. Verify the admin still has role 0
cast call $ACCESS_MANAGER "hasRole(uint64,address)(bool,uint32)" 0 $ADMIN_ADDRESS --rpc-url "$RPC_URL"

# 4. Get the riskManagerTimelock from caliber (good candidate for role 1)
RISK_MANAGER_TIMELOCK=$(cast call $CALIBER_ADDRESS "riskManagerTimelock()(address)" --rpc-url "$RPC_URL")
```

**Grant role 1 to your caller EOA** — impersonate the ZERO-DELAY admin:

> WARNING: role 0 has TWO holders. The **delayed Safe admin `0x62244c74e1d09b3d86ef7342d354b5d7770bde10`** carries an execution delay, so a `grantRole` from it does NOT take effect immediately and your later `setFeedRoute` still reverts `AccessManagerUnauthorizedAccount`. ALWAYS impersonate the **zero-delay admin `0x8d28a69328561ef9f171c58996fecb9f494e070c`**.

```bash
ADMIN=0x8d28a69328561ef9f171c58996fecb9f494e070c            # zero-delay role-0 admin
ACCESS_MANAGER=0x0FceFa3f1047F35521A49cD8B06faBd588665d7f
CALLER=<your EOA that will send setFeedRoute/setFeedStaleThreshold>

# anvil: fund + impersonate the zero-delay admin, then grant role 1 to your EOA with 0 execution delay
cast rpc anvil_setBalance $ADMIN 0x56BC75E2D63100000 --rpc-url "$RPC_URL"
cast rpc anvil_impersonateAccount $ADMIN --rpc-url "$RPC_URL"
cast send $ACCESS_MANAGER "grantRole(uint64,address,uint32)" 1 $CALLER 0 \
  --from $ADMIN --unlocked --rpc-url "$RPC_URL"
# Tenderly equivalent: mcp__tenderly__fund_address + mcp__tenderly__send_transaction with the same calldata
```

Note: `addBaseToken` is NOT role-gated — it must come from `riskManagerTimelock` `0x7c405bbd131e42af506d14e752f2e59b19d49997` (Step 3), not from your role-1 EOA.

### Step 2: Set Oracle Feed Route
Configure the price feed in the Oracle Registry using an address with role 1.

**Function signature:**
```
setFeedRoute(address token, address feed1, uint256 stalenessThreshold1, address feed2, uint256 stalenessThreshold2)
```

**Actions:**
1. Fund the role-1 caller (riskManagerTimelock) with ETH for gas
2. Encode and send the `setFeedRoute` call impersonating the role-1 address
3. Verify transaction receipt status == 1

**Parameters:**
- `token`: Token address
- `feed1`: Primary price feed address
- `stalenessThreshold1`: Maximum age for feed data (use `315360000` = 10 years on a fork; see Staleness Thresholds)
- `feed2`: Secondary feed (use zero address if not needed)
- `stalenessThreshold2`: Threshold for secondary feed (0 if not used)

**Using cast (preferred over Python):**
```bash
RISK_MANAGER_TIMELOCK="0x..."  # from caliber.riskManagerTimelock()
CALLDATA=$(cast calldata "setFeedRoute(address,address,uint256,address,uint256)" \
  "$TOKEN_ADDRESS" "$ORACLE_ADDRESS" "315360000" \
  "0x0000000000000000000000000000000000000000" "0")
mcp__tenderly__send_transaction(chain, from_address=RISK_MANAGER_TIMELOCK, to_address=ORACLE_REGISTRY, data=CALLDATA)
```

### Step 3: Add Base Token to Caliber
Add the token as a base token by impersonating the riskManagerTimelock.

**Function signature:**
```
addBaseToken(address token)
```

**Actions:**
1. Fund riskManagerTimelock with ETH for gas (if not already funded)
2. Encode and send `addBaseToken` call
3. Verify transaction receipt status == 1

**Using cast (preferred):**
```bash
CALLDATA=$(cast calldata "addBaseToken(address)" "$TOKEN_ADDRESS")
mcp__tenderly__send_transaction(chain, from_address=RISK_MANAGER_TIMELOCK, to_address=CALIBER_ADDRESS, data=CALLDATA)
```

**Note**: `addBaseToken` requires `riskManagerTimelock` specifically (different from the AccessManager role system used by OracleRegistry).

### Step 4: Verification
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

### Deployed Contracts != Local makina-core Source
The live contracts are an OLDER deployment than makina-core `main`. ALWAYS verify function signatures against the DEPLOYED ABI/bytecode (Etherscan or a prior test-report), NEVER against local source — a wrong signature reverts with an empty `0x` and no reason string. Known mainnet divergences:

| Operation | DEPLOYED (use this) | local `main` (WILL REVERT on-chain) |
|-----------|---------------------|-------------------------------------|
| OracleRegistry set/read feed | `setFeedRoute(...)` / `getFeedRoute(...)` | `setTokenFeedData` / `getTokenFeedData` |
| Caliber add base token | 1-arg `addBaseToken(address)` from `riskManagerTimelock` | 2-arg `addBaseToken(address,uint256)` |

### Order of Operations
**CRITICAL**: Oracle feed must be set BEFORE adding the token as a base token. Caliber likely checks for oracle existence when adding base tokens.

### Impersonation
- Each operation requires impersonating a different address
- Always fund addresses before impersonating (use `tenderly_setBalance`)
- Funding amount: `0x56BC75E2D63100000` (100 ETH in wei)

### Staleness Thresholds
**Use a LARGE staleness on EVERY feed in a route — default to 10 years = `315360000`.**
Fork e2e tests routinely `evm_increaseTime` by +7d (async cooldowns, NAV time-warps). Any feed left at `86400` (24h) then makes `getPrice` revert `PriceFeedStale`, breaking `account`/NAV. This includes the **shared USDC/USD quote feed `0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6`** used as the 2nd hop of most routes — bump ITS staleness too, or the route goes stale even though your token's own feed is fresh.

Per-feed staleness is set with the role-1 function `setFeedStaleThreshold(address feed, uint256 threshold)` (separate from `setFeedRoute`), so you can raise the shared USDC feed independently:

```bash
cast send $ORACLE_REGISTRY "setFeedStaleThreshold(address,uint256)" \
  0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6 315360000 --from $CALLER --unlocked --rpc-url "$RPC_URL"
```

Also replace the `"86400"` values in Step 2's Parameters bullet and cast example with `"315360000"`. Only tighten below 10y for a real production config; on a fork, larger is always safer.

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
- **"Unauthorized"**: Wrong impersonation address or insufficient permissions. For `setFeedRoute`, the caller needs **role 1** on the **AccessManager** (not just any admin). Use `cast call $ACCESS_MANAGER "hasRole(uint64,address)(bool,uint32)" 1 $CALLER --rpc-url "$RPC_URL"` to verify.
- **"Oracle not set"**: When adding base token before setting oracle. Always set feed route FIRST.
- **"Invalid feed"**: Price feed address incorrect or incompatible
- **"AccessManagerUnauthorizedAccount"**: The caller does not have the required role. Grant the role first (see Step 1).

### AccessManager Role Discovery
If you don't know which address has the admin role:
1. Query `RoleGranted` events on the AccessManager contract
2. Filter by role 0 (topic1 = `0x00...00`) to find admin addresses
3. Verify current status with `hasRole(0, address)` since roles can be revoked

### Verification Failures
- Always check transaction receipt `status` field (1=success, 0=revert)
- Use `mcp__tenderly__debug_transaction` to get revert reasons for failed txs
- Re-query if initial verification returns false

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