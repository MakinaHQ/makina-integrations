---
name: oracle
description: "**Read-only** - Query token prices and inspect feed routes/staleness on the Makina Oracle Registry. Use to check prices, verify a token's feed route (getFeedRoute), or debug PriceFeedStale reverts before/after base-token setup."
allowed-tools: Read, Bash(cast:*), mcp__pools_db__*
---

# Oracle Registry Query

Query token prices from the Makina oracle registry.

## Configuration

**Oracle Registry Address** (same on all chains):
```
0xC388B72AB90Be82B230D919F9C05c87F9397f485
```

**RPC URLs**:
| Chain | RPC URL |
|-------|---------|
| mainnet | https://eth.llamarpc.com |
| base | https://mainnet.base.org |
| arbitrum | https://arb1.arbitrum.io/rpc |
| optimism | https://mainnet.optimism.io |

## Deployed interface (verify against THIS, not local makina-core `main`)

The live OracleRegistry at `0xC388B72AB90Be82B230D919F9C05c87F9397f485` exposes:

| Purpose | Signature | Notes |
|---------|-----------|-------|
| Price | `getPrice(address base, address quote) -> uint256` | value of 1 base in quote terms |
| Route | `getFeedRoute(address token) -> (address feed1, address feed2)` | feeds used to price `token`; `feed2 == 0` means single-hop |
| Staleness | `getFeedStaleThreshold(address feed) -> uint256` | max age (seconds) for THAT feed |
| Authority | `authority() -> address` | the AccessManager `0x0fCEfa3f1047F35521A49cD8B06faBd588665d7F` |

> **WARNING (deployed != local source).** The deployed registry uses `setFeedRoute` / `getFeedRoute`. The makina-core `main` source RENAMED these to `setTokenFeedData` / `getTokenFeedData`; those selectors **revert with empty `0x`** on the deployed contract. Always encode against the deployed ABI (Etherscan / a prior test-report), never local source.

**Inspect a token's route and per-feed staleness:**
```bash
RPC=https://ethereum-rpc.publicnode.com
OR=0xC388B72AB90Be82B230D919F9C05c87F9397f485
# USDC -> (feed1, feed2); feed2==0 => single hop
cast call $OR "getFeedRoute(address)(address,address)" \
  0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 --rpc-url $RPC
# -> 0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6  (shared USDC/USD chainlink feed)
#    0x0000000000000000000000000000000000000000
cast call $OR "getFeedStaleThreshold(address)(uint256)" \
  0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6 --rpc-url $RPC   # -> 83400
```

### Single-hop vs 2-hop (ERC-4626) routes

`getPrice(base, quote)` composes the base token's route with the quote token's route, scaling by each hop's feed. Two shapes:

- **Single-hop**: `feed1` set, `feed2 == 0`. e.g. WETH -> ETH/USD chainlink (`getFeedRoute(WETH)` = `0x5f4ec3df9cbd43714fe2740f5e3616155c5b8419`, `0x0`).
- **2-hop (rate route)**: BOTH feeds set. Used for **ERC-4626 vault base tokens** (e.g. sUSN): `feed1` = a rate adapter (vault->underlying, i.e. `convertToAssets`), `feed2` = underlying->USD chainlink. `getFeedRoute` returns both; both feeds must be registered and BOTH need a staleness threshold set via `setFeedStaleThreshold`.

## Usage

When user asks for a price (e.g., "price of WETH in USDC on base"):

### 1. Identify Parameters
- **Chain**: mainnet, base, arbitrum, or optimism
- **Base token**: Token to price (symbol or address)
- **Quote token**: Unit of price (symbol or address)

### 2. Resolve Tokens
If token is a symbol (not 0x address), use pools_db MCP to find the address:
```
mcp__pools_db__get_pool_context(pool_id=<pool_on_chain>)
```

Common token addresses:
| Token | Mainnet | Base | Arbitrum |
|-------|---------|------|----------|
| WETH | 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 | 0x4200000000000000000000000000000000000006 | 0x82aF49447D8a07e3bd95BD0d56f35241523fBab1 |
| USDC | 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 | 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 | 0xaf88d065e77c8cC2239327C5EDb3A432268e5831 |
| USDT | 0xdAC17F958D2ee523a2206206994597C13D831ec7 | 0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2 | 0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9 |

### 3. Execute Query

Use `cast call` to query the oracle:

```bash
cast call 0xC388B72AB90Be82B230D919F9C05c87F9397f485 \
  "getPrice(address,address)(uint256)" \
  <base_token_address> <quote_token_address> \
  --rpc-url <rpc_url>
```

### 4. Format Result
The result is: **value of 1 base token in quote token terms**

Example: `getPrice(WETH, USDC)` returns how many USDC 1 WETH is worth.

Format considering quote token decimals:
- USDC/USDT: 6 decimals → divide by 1e6
- WETH/most tokens: 18 decimals → divide by 1e18

## Examples

**Price of WETH in USDC on base:**
```bash
cast call 0xC388B72AB90Be82B230D919F9C05c87F9397f485 \
  "getPrice(address,address)(uint256)" \
  0x4200000000000000000000000000000000000006 \
  0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  --rpc-url https://mainnet.base.org
# Result: 3086027068 → 3,086.03 USDC (divide by 1e6)
```

**Price of WETH in USDC on mainnet:**
```bash
cast call 0xC388B72AB90Be82B230D919F9C05c87F9397f485 \
  "getPrice(address,address)(uint256)" \
  0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 \
  0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 \
  --rpc-url https://eth.llamarpc.com
```

## Configuring feed routes (write side)

Read-only queries use `cast call`. To *set* a route you need a fork (Tenderly or local anvil) and write permissions — see the `caliber-token-setup` skill for the full add-base-token flow. Oracle-specific facts:

- `setFeedRoute(address token, address feed1, uint256 staleness1, address feed2, uint256 staleness2)` and `setFeedStaleThreshold(address feed, uint256)` require **role 1** on the AccessManager `0x0fCEfa3f1047F35521A49cD8B06faBd588665d7F` (== `OracleRegistry.authority()`).
- To grant yourself role 1: impersonate the **zero-delay admin (role 0)** `0x8d28a69328561ef9f171c58996fecb9f494e070c`, call `grantRole(1, <yourEOA>, 0)`, THEN `setFeedRoute`.
  - **Do NOT use** `0x62244c74e1d09b3d86ef7342d354b5d7770bde10` (a delayed Safe admin that `caliber-token-setup` currently lists) — its grant is subject to an execution delay and does NOT take effect immediately.
- Register the feed route **before** `addBaseToken` — `addBaseToken` reverts if the token has no route.

## Error Handling
- **Reverts / empty `0x` (token not registered)**: token has no feed route. Check with `getFeedRoute(token)` (empty/zero => not registered).
- **Reverts `PriceFeedStale`**: a feed in the route is older than its staleness threshold. `getPrice(base, quote)` reads EVERY feed in BOTH the base's and the quote's routes, so a stale **quote** feed reverts the call too — most commonly the shared USDC/USD feed `0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6` (default threshold `83400`s).
  - On a **time-warped fork** (`evm_increaseTime` / +7d), on-chain feeds stop updating so `now - updatedAt` exceeds the threshold. Raise the threshold on EVERY touched feed — INCLUDING the shared USDC quote feed `0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6` — to a large value (10 years = `315360000`) via `setFeedStaleThreshold(feed, 315360000)` (role 1). Forgetting the USDC quote feed is the usual cause of "the route looks right but getPrice still reverts".
- **Wrong function name**: `setTokenFeedData` / `getTokenFeedData` (local-source names) revert with empty `0x` — use `setFeedRoute` / `getFeedRoute` (see Deployed interface).
- **Returns 0**: may indicate an unregistered pair.
- **Token not found**: ask user for address directly.
