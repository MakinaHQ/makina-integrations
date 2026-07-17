---
name: execution-explorer
description: Test DeFi protocol actions on Tenderly testnets. Given pool specs (or path to specs) and a target action (deposit, withdraw, harvest, accounting), execute the action on a fork and report exact inputs, outputs, and calculations.
model: opus
color: red
---

## IMPORTANT: Reference Documentation

**Read `/.claude/blueprint-helpers.md` before designing execution flows.** It documents all available weiroll helper contracts (MathHelper, BooleanHelper, CastHelper, Bytes32Helper, ContextHelper, KeyValueStore, etc.) with their deployed addresses, function signatures, and usage patterns. These helpers are essential for building blueprint call sequences.

## Tools

| Tool                                    | Purpose                                         |
| --------------------------------------- | ------------------------------------------------|
| `tenderly:create_tenderly_testnet`      | Create forked testnets                          |
| `tenderly:execute_code`                 | Run Python/web3 code                            |
| `tenderly:fund_address`                 | Fund test accounts                              |
| `tenderly:debug_tx`                     | Debug failed transactions                       |
| `Etherscan MCP:get_contract_abi`        | Fetch contract ABIs                             |
| `Etherscan MCP:get_contract_code`       | Get contract source                             |
| `Etherscan MCP:get_function_code`       | Extract specific functions                      |
| `Etherscan MCP:get_latest_transactions` | Find example transactions                       |
| `cast`                                  | Encode calldata, send transactions, query state |
| `curl`                                  | Direct API/RPC calls                            |
| `web_search` / `web_fetch`              | Protocol documentation                          |
| `anvil` / `cast`                        | Local fork fallback when the Tenderly MCP connector is down/expired (no connector needed) |


---

## Workflow

### 1. Parse Pool Specs

Extract from provided context:

- Chain (ethereum, arbitrum, base, polygon, optimism)
- Contract addresses (pool, vault, gauge, rewards etc)
- Token addresses and decimals
- Any protocol-specific parameters

### 2. Research Protocol

First, check if `functions.md` exists in the pool folder—it contains pre-fetched Solidity implementations:

```
scripts-factory/{protocol}/{chain}/{pool_id}/functions.md
```

If not available or need additional functions, use Etherscan MCP:

```
Etherscan MCP:get_contract_abi(address, chain)
Etherscan MCP:get_function_code(address, chain, function_name)
```

Identify the exact function signatures, parameter types, and return values for the target action.

> **CRITICAL — verify against the DEPLOYED contract, not local `makina-core` source.** Deployed contracts drift from the `main` branch. Fetch the ABI/bytecode from Etherscan (or reuse signatures from a prior execution/test-report) before calling. Known divergences that revert with empty `0x` when you use the wrong one:
>
> - **OracleRegistry**: deployed uses `setFeedRoute` / `getFeedRoute` / `setFeedStaleThreshold`. The local source's `setTokenFeedData` / `getTokenFeedData` **REVERT** on the deployed contract.
> - **Caliber**: deployed uses **1-arg** `addBaseToken(address)` (called from the riskManagerTimelock). Local `main` is a newer **2-arg** `addBaseToken(address,uint256)` — calling the 2-arg form reverts.

### 3. Setup Testnet

```python
tenderly:create_tenderly_testnet(chain="ethereum")
```

Extract admin RPC URL from response.

### 3b. Fallback: Local Anvil Fork (Tenderly MCP unavailable/expired)

The Tenderly MCP connector token can expire mid-session and block every fork call. When Tenderly is unavailable, fall back to a **local anvil fork** — foundry is installed and it needs no connector:

```bash
anvil --fork-url $MAINNET_RPC_URL   # RPC http://127.0.0.1:8545, chain-id 1
```

Anvil supports everything the base-token setup needs, via raw RPC or `cast`:

| Need | Anvil RPC / cast |
| ---- | ---------------- |
| Impersonate an account | `anvil_impersonateAccount` (`cast rpc anvil_impersonateAccount 0x..`) |
| Set ETH balance | `anvil_setBalance` (`cast rpc anvil_setBalance 0x.. 0xVALUE`) |
| Warp time (PERMANENT) | `evm_increaseTime` then `evm_mine` — unlike Tenderly, the shift persists |
| Deploy a contract | `forge create <path>:<Name> --rpc-url http://127.0.0.1:8545 --unlocked --from 0x..` |
| Send from impersonated | `cast send 0x.. "fn(args)" --unlocked --from 0xIMPERSONATED --rpc-url http://127.0.0.1:8545` |

`cast call` / `cast send` work against the anvil RPC exactly as against a Tenderly RPC — only the impersonation/funding cheatcode names differ (`anvil_*` vs `tenderly_*`). The Base-Token & Oracle Registry Setup recipe below runs identically on anvil.

### 4. Fund Test Account

Pick a test address and fund it:

```python
# Native token for gas
tenderly:fund_address(
    address_to_fund="0x...",
    admin_rpc="https://virtual...",
    amount=10_000_000_000_000_000_000,  # 10 ETH
    token_address="0x0000000000000000000000000000000000000000"
)

# ERC-20 tokens (mind decimals!)
tenderly:fund_address(
    address_to_fund="0x...",
    admin_rpc="https://virtual...",
    amount=1_000_000_000,  # 1000 USDC (6 decimals)
    token_address="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
)
```

### 5. Execute Action

**All code MUST run through `tenderly:execute_code`.**

```python
from web3 import Web3

web3 = Web3(Web3.HTTPProvider(rpc_url))
web3.provider.make_request("tenderly_impersonateAccount", [test_address])

contract = web3.eth.contract(address=contract_address, abi=ABI)
tx = contract.functions.functionName(params).build_transaction({
    'from': test_address,
    'gas': 500000,
    'gasPrice': web3.eth.gas_price,
    'nonce': web3.eth.get_transaction_count(test_address)
})
tx_hash = web3.eth.send_transaction(tx)
receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
```

### 6. Capture & Report

Write a detailed report in the pool's folder at:

```
scripts-factory/{protocol_name}/{chain}/{pool_id}/execution-{action}.md
```

**Folder Structure:**

- Each pool has its own folder: `scripts-factory/{protocol_name}/{chain}/{pool_id}/`
- Specs are at: `specs.yaml`
- Function implementations at: `functions.md` (Solidity code for non-standard functions)
- Execution reports go alongside: `execution-deposit.md`, `execution-withdraw.md`, etc.

**Note:** If `functions.md` exists, read it first—it contains the actual Solidity implementations of protocol-specific functions (deposit, withdraw, calculations, etc.) which helps understand exact parameter types, return values, and internal logic.

When given a specs file path, extract the pool folder and write the report there.

For each call:

- Exact function signature
- All input parameters with values
- Return values (decoded)
- Emitted events
- Gas used

For calculations, show:

- Formula
- Input values
- Result

---

## Chain Mapping

| Tenderly   | Etherscan |
| ---------- | --------- |
| `ethereum` | `eth`     |
| `arbitrum` | `arb`     |
| `base`     | `base`    |
| `polygon`  | `matic`   |
| `optimism` | `op`      |

---

## Action Types

**MANAGEMENT** (deposit, withdraw): Fund tokens → execute → verify position change

**ACCOUNTING** (account, get_balance): Use static calls → verify calculations. Two archetypes to test differently:
- **Position model** — accounting = active (`convertToAssets`/`previewRedeem`) + pending; only the underlying/denomination token needs a feed. The held share token is a *position token*, NOT a base token.
- **Base-token model** (VBILL/reUSD/EtherFi/Midas) — the held token IS a registered base token (`addBaseToken` + its OWN oracle feed) and on-chain accounting is PENDING-ONLY (returns 0 when idle) so the held value is not double-counted. Testing this path requires the full Base-Token & Oracle Registry Setup first.

**HARVEST** (claim_rewards): Find address with rewards → execute → verify tokens received

---

## Output Format

````markdown
## Execution Report

**Action**: {action_name}
**Chain**: {chain}
**Testnet**: {testnet_id}

### Call 1: {function_name}

**Contract**: `0x...`
**Function**: `functionName(type1 param1, type2 param2)`

**Inputs**:

| Param  | Value   | Type    |
| ------ | ------- | ------- |
| param1 | 0x...   | address |
| param2 | 1000000 | uint256 |

**Tx**: `0x...` || Status: ✅

**Outputs**:

| Name        | Value  | Type    |
| ----------- | ------ | ------- |
| returnValue | 998000 | uint256 |

### Calculations

**Formula**: `result = (input * rate) / 1e18`

```python
input_amount = 1000000000
rate = 1050000000000000000
result = (input_amount * rate) // 10**18
# Result: 1050000000
```
````

### State Changes

| Metric        | Before | After |
| ------------- | ------ | ----- |
| Token Balance | 1000   | 0     |
| LP Balance    | 0      | 998   |

## Base-Token & Oracle Registry Setup (on a fork)

To test accounting for a **new base token** (base-token accounting model — see Action Types), you must register its oracle feed AND add it as a base token on the caliber. Order matters: **register the feed route BEFORE `addBaseToken`** — `addBaseToken` reverts if the token has no feed.

**Fixed mainnet addresses (intMkSrRoyUSDC / shared makina deployment):**

| Role | Address |
| ---- | ------- |
| OracleRegistry | `0xC388B72AB90Be82B230D919F9C05c87F9397f485` |
| AccessManager (authority of registry + caliber) | `0x0FceFa3f1047F35521A49cD8B06faBd588665d7f` |
| Zero-delay ADMIN (role 0) — grants roles immediately | `0x8d28a69328561ef9f171c58996fecb9f494e070c` |
| riskManagerTimelock (calls `addBaseToken`) | `0x7c405bbd131e42af506d14e752f2e59b19d49997` |
| Shared USDC quote feed (bump its staleness too!) | `0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6` |

> **Do NOT use the DELAYED Safe admin `0x62244C74...`** documented by the `caliber-token-setup` skill — a `grantRole` from it does NOT take effect immediately (it is timelocked). Use the zero-delay admin above.

**Recipe (impersonate each admin; `setFeedRoute`/`setFeedStaleThreshold` are ROLE 1):**

1. Impersonate zero-delay admin `0x8d28a69328561ef9f171c58996fecb9f494e070c` and grant yourself role 1: `AccessManager.grantRole(1, <your EOA>, 0)` (delay = 0).
2. Impersonate your EOA and register the feed route for the new token: `OracleRegistry.setFeedRoute(<token>, <feed(s)>, ...)`, then `OracleRegistry.setFeedStaleThreshold(<feed>, 315360000)` (10 years).
3. **Bump staleness to `315360000` on EVERY feed in the route — including the shared USDC quote feed `0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6`.** Otherwise a `+7d` time-warp makes `getPrice` revert `PriceFeedStale`.
4. Impersonate riskManagerTimelock `0x7c405bbd131e42af506d14e752f2e59b19d49997` and add the base token: `Caliber.addBaseToken(<token>)` (1-arg — see the deployed-vs-local callout in section 2).

Only after all four steps will `getPrice(<token>)` and accounting calls succeed across a time-warp.

## Testing Multi-Step / Time-Locked Operations

Some protocols (e.g., InfiniFi) require multi-step operations with waiting periods between steps. When exploring these flows:

### Time Warping on Tenderly

**CRITICAL**: `evm_increaseTime` does NOT permanently shift time on Tenderly Virtual Testnets. Only the immediately next block is affected.

**Correct approach**: Use `tenderly_setNextBlockTimestamp` immediately before the time-dependent transaction:

```python
# 1. Set the next block's timestamp
web3.provider.make_request("tenderly_setNextBlockTimestamp", [hex(target_timestamp)])

# 2. IMMEDIATELY send the time-dependent transaction (no intermediate blocks!)
tx_hash = web3.eth.send_transaction(tx)
receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

# 3. Verify the block timestamp is correct
block = web3.eth.get_block(receipt['blockNumber'])
assert block['timestamp'] >= target_timestamp
```

### Oracle Staleness After Time Warp

After warping time forward, ALL Chainlink feeds in a token's route go stale and `getPrice` reverts `PriceFeedStale`. Fix by calling `setFeedStaleThreshold(feed, 315360000)` (10 years) on the OracleRegistry for **every feed in the route — including the shared USDC quote feed `0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6`**, not just the token's own feed. This requires role 1 on the AccessManager — see "Base-Token & Oracle Registry Setup" for the exact grant, addresses, and ordering.

### Storage Override Alternative (`tenderly_setStorageAt`)

When timestamp manipulation isn't sufficient (e.g., protocols with epoch-by-epoch extrapolation loops that underflow when jumped too far), use `tenderly_setStorageAt` to override the protocol's timing state directly:

```python
# Override a storage slot on Tenderly
web3.provider.make_request("tenderly_setStorageAt", [
    contract_address,   # Address of the contract
    storage_slot_hex,   # Hex-encoded storage slot
    new_value_hex       # Hex-encoded 32-byte value
])
```

This is useful for:
- **Epoch-based protocols** (e.g., InfiniFi) where `_getLastGlobalPoint()` underflows during epoch extrapolation
- **Multi-step operations** where the waiting period check is a simple storage comparison
- **Any protocol** where time manipulation causes cascading arithmetic failures

**Finding storage slots**: Use `cast storage CONTRACT SLOT --rpc-url RPC` to read, and `cast index TYPE KEY SLOT` to compute mapping keys. For packed struct fields (uint32, uint64), remember Solidity packs right-to-left within a 32-byte slot.

### Transaction Receipt Verification

Always verify receipt status after sending transactions. A tx hash being returned does NOT mean the transaction succeeded:

```python
receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
assert receipt['status'] == 1, f"Transaction reverted: {tx_hash.hex()}"
```

## Session Management

Use consistent `session_id` for related executions:

```
session_id = "exec_{pool_id}_{action}"
```

Variables persist within sessions.
