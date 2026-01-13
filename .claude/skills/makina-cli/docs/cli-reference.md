# CLI Reference

## Modes

### Interactive Mode
```bash
cargo run -- --dev
```

### Non-Interactive Mode
```bash
cargo run -- --machine <MACHINE> --caliber <CHAIN> <COMMAND> [OPTIONS]
```

## Configuration

### Local Config
Update machines.toml to point to local config files:
```toml
[deth]
config = "local:/path/to/machines/deth/config-local.toml"
```

Or use: `--machines-path /path/to/machines-local.toml`

## Environment

- `--dev`: Use Tenderly testnet RPCs (`DEV_MAINNET_RPC_URL`, etc.)
- Live mode: Requires `MAINNET_RPC_URL`, etc. in `.env`

## Global Flags

| Flag | Description |
|------|-------------|
| `--dev` | Use Tenderly testnet RPCs |
| `--force-execute` | Execute transaction even if simulation fails. Useful for debugging on Tenderly |
| `--machine <MACHINE>` | Specify the machine in non-interactive mode |
| `--caliber <CALIBER>` | Specify the caliber/chain in non-interactive mode |
| `--machines-path <PATH>` | Path to machines.toml file |
| `--signer <SIGNER>` | Signing method: `gcp`, `private-key`, `ledger`, `trezor`, `unsigned` |
| `--safe <SAFE>` | Safe address for multisig transactions |



## Commands

| Command | Description |
|---------|-------------|
| `display-positions` | Show all positions with values |
| `display-balances` | Show base token balances |
| `display-root` | Show instruction root |
| `manage-position` | Execute management instructions |
| `harvest-position` | Harvest yield |
| `account-positions` | Update position accounting |
| `swap-tokens` | Swap tokens via swapper |

### Dev Commands (--dev only)

| Command | Description |
|---------|-------------|
| `dev-set-balance` | Set ETH balance |
| `dev-set-erc20-balance` | Set token balance |
| `dev-increase-blocks` | Mine blocks |
| `dev-increase-time` | Advance time |
| `dev-update-root` | Update root immediately |

See `root-updates.md` for root management details.

## manage-position Command

### Arguments

| Argument | Description |
|----------|-------------|
| `--protocol` | Protocol name (e.g., `aavev3`, `morpho`) |
| `--action` | Action (e.g., `add_collateral`, `withdraw_collateral`) |
| `--token` | Token identifier (e.g., `weth`, `usdc`) |
| `--inputs` | ABI-encoded input values |

### Input Slots

Types: `Uint`, `Int`, `Address`, `Bytes`, `Bool`, `Swap`

### Finding Input Slots
```bash
grep -A 20 'instructions.aavev3.add_collateral.weth' \
  machines/*/mainnet/rootfiles/*.toml
```

### Encoding Inputs
```bash
cast abi-encode "f(uint256)" 1000000000000000000
```

### Multiple Input Slots

**IMPORTANT**: When an instruction has multiple input slots, use **separate `--inputs` flags** for each slot. Do NOT concatenate them into a single hex string.

```bash
# WRONG - concatenated inputs
--inputs 0x<amount><min_shares>

# CORRECT - separate flags for each input slot
--inputs 0x<amount> --inputs 0x<min_shares>
```

The CLI collects each `--inputs` flag into a vector and validates that the count matches the instruction's `inputs_slots` count.

### Example (single input)
```bash
cargo run -- \
  --machines-path machines-local.toml --dev \
  --machine mteth --caliber mainnet \
  manage-position \
    --protocol aavev3 \
    --action add_collateral \
    --token weth \
    --inputs 0x00000000000000000000000000000000000000000000000006f05b59d3b20000
```

### Example (multiple inputs)
```bash
# Fluid deposit requires: asset_amount + min_vault_shares
cargo run -- \
  --machines-path machines-local.toml --dev \
  --machine dusd --caliber mainnet \
  manage-position \
    --protocol fluid \
    --action deposit \
    --token GHO \
    --inputs 0x00000000000000000000000000000000000000000000003635c9adc5dea00000 \
    --inputs 0x0000000000000000000000000000000000000000000000000000000000000000
```

## Signers

- `--signer private-key`: Uses `PRIVATE_KEY` from env
- `--signer ledger`: Hardware wallet
- `--signer unsigned`: Output unsigned tx

## Common Protocols

| Protocol | Actions |
|----------|---------|
| `aavev3` | `add_collateral`, `withdraw_collateral`, `account` |
| `convex-curve` | `deposit_balanced`, `withdraw_balanced`, `harvest` |
| `morpho` | `supply`, `withdraw`, `account` |
