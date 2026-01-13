---
name: oracle
description: "**Read-only** - Query token prices from Oracle Registry. Use to check current prices or verify token registration."
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

## Error Handling
- **Reverted call**: Token pair not registered
- **Returns 0**: May indicate unregistered pair
- **Token not found**: Ask user for address directly
