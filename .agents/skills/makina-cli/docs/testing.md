# Testing on Tenderly

End-to-end testing of blueprint instruction files on Tenderly testnets.

## Quick Workflow

1. Compile instruction -> rootfile
2. Create Tenderly testnet
3. Update root (see `root-updates.md`)
4. Fund caliber with test tokens
5. Execute manage-position
6. Verify results

## Step 1: Compile

```bash
transpiler -- \
  --input-file=/path/to/caliber-test.yaml \
  --output-file=/tmp/makina-test-output.toml
```

**Never send `--output-file` into `machines/*/*/rootfiles/`.** Rootfiles are release-generated build artifacts now; `rootfiles-guard` rejects any PR that adds or modifies a file under a `rootfiles/` directory. Always write output outside the repo (`/tmp/...`), as above.

## Step 2: Create Tenderly Testnet

```
mcp__tenderly__create_tenderly_testnet(chain="ethereum")
```

Returns `admin_rpc` URL for subsequent commands.

## Step 3: Update Root

See `root-updates.md` for details.

```bash
DEV_MAINNET_RPC_URL="{admin_rpc}" \
spellcaster -- \
  --config machines-local.toml --dev \
  --machine {fund} --caliber {network} \
  dev-update-root --rootfile /tmp/makina-test-output.toml
```

## Step 4: Fund Caliber

### Native ETH

```
mcp__tenderly__fund_address(
  admin_rpc="{admin_rpc}",
  address_to_fund="{caliber_address}",
  token_address="0x0000000000000000000000000000000000000000",
  amount=10000000000000000000
)
```

### ERC20 Tokens

```
mcp__tenderly__fund_address(
  admin_rpc="{admin_rpc}",
  address_to_fund="{caliber_address}",
  token_address="{token_address}",
  amount={amount_in_base_units}
)
```

### Common Tokens (mainnet)

| Token  | Address                                    | Decimals |
| ------ | ------------------------------------------ | -------- |
| USDC   | 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 | 6        |
| WETH   | 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 | 18       |
| wstETH | 0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0 | 18       |

## Step 5: Execute Instruction

### Check input slots

```bash
grep -A 5 'inputs_slots' /tmp/makina-test-output.toml
```

### Encode inputs

**IMPORTANT**: Use **separate `--inputs` flags** for each input slot. Do NOT concatenate multiple inputs into one hex string.

```bash
# Single input slot
cast abi-encode "f(uint256)" 1000000000000000000

# Multiple input slots - encode EACH separately
cast abi-encode "f(uint256)" 1000000000000000000  # -> input 1
cast abi-encode "f(uint256)" 0                     # -> input 2
```

### Run manage-position

Single input:

```bash
DEV_MAINNET_RPC_URL="{admin_rpc}" \
spellcaster -- \
  --config machines-local.toml --dev \
  --machine {fund} --caliber {network} \
  manage-position \
    --protocol {protocol} \
    --action {action} \
    --token {token} \
    --inputs {encoded_amount}
```

Multiple inputs (e.g., amount + min_shares):

```bash
DEV_MAINNET_RPC_URL="{admin_rpc}" \
spellcaster -- \
  --config machines-local.toml --dev \
  --machine {fund} --caliber {network} \
  manage-position \
    --protocol {protocol} \
    --action {action} \
    --token {token} \
    --inputs 0x<first_input> \
    --inputs 0x<second_input>
```

## Step 6: Verify

```bash
DEV_MAINNET_RPC_URL="{admin_rpc}" \
spellcaster -- \
  --config machines-local.toml --dev \
  --machine {fund} --caliber {network} \
  display-positions
```

## Troubleshooting

| Error                                 | Solution                                          |
| ------------------------------------- | ------------------------------------------------- |
| "incorrect number of inputs supplied" | Use separate `--inputs` flags for each input slot |
| "no matching rootfile"                | Re-run `dev-update-root`                          |
| "could not find instruction"          | Check --protocol, --action, --token               |
| "transaction reverted"                | Fund caliber with ETH and tokens                  |

Debug: `mcp__tenderly__debug_tx(testnet_id="{id}", tx_hash="{hash}")`
