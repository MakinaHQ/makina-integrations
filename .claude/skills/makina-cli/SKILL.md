---
name: makina-cli
description: Run Makina spellcaster CLI to manage DeFi positions. Use when running CLI commands, managing positions, displaying balances, or executing transactions on calibers.
allowed-tools: Read, Bash(spellcaster:*), Bash(transpiler:*), Bash(cat:*), Grep, Glob
---

# Makina CLI

Spellcaster CLI for managing DeFi positions across calibers.

## Quick Start

```bash
# Interactive mode
spellcaster --dev

# Non-interactive
spellcaster --machine <MACHINE> --caliber <CHAIN> <COMMAND>
```

## Common Commands

| Command | Description |
|---------|-------------|
| `display-positions` | Show all positions |
| `display-balances` | Show token balances |
| `manage-position` | Execute instruction |
| `dev-update-root` | Update root on testnet |

## Transpiler

The transpiler is a SEPARATELY-INSTALLED binary. It is NOT on `$PATH` (`which transpiler` fails) and is NOT part of the local `makina-rs` checkout — that repo's `calldata` crate is an HTTP API server, not the transpiler. Resolve it in this order:

1. `$TRANSPILER_PATH` from `.claude/settings.local.json` `env`. The config repo does NOT set this by default (only the rootfiles repo does) — add it here.
2. Fallback absolute path (rev `9471437`):
   `/Users/augustin/.cargo/git/checkouts/transpiler-11f55d1751042103/9471437/target/debug/transpiler`

CLI: subcommands `transpile | check | root`; flags `-i/--input-file`, `-o/--output-file`, `-t/--token-list`, `--helpers`. **The subcommand goes LAST and there is no leading `--`.**

**`--token-list` is REQUIRED** for `transpile` and `check` because instructions reference `${token_list.*}`. Working command:

```bash
TP=/Users/augustin/.cargo/git/checkouts/transpiler-11f55d1751042103/9471437/target/debug/transpiler
"$TP" --input-file machines/<M>/<net>/caliber.yaml \
      --token-list token-lists/prod-token-list.json \
      [-o out.toml] transpile          # use `check` to validate without writing output
```

## Documentation

For detailed documentation, read these files when needed:

- **CLI Reference**: `.claude/skills/makina-cli/docs/cli-reference.md`
- **Root Updates**: `.claude/skills/makina-cli/docs/root-updates.md`
- **Blueprint System**: `.claude/skills/makina-cli/docs/blueprints.md`
- **Testing Workflows**: `.claude/skills/makina-cli/docs/testing.md`

## Local Config

Use `--config machines-local.toml` for local development.

### Config-only calibers (cross-repo plumbing)

Some calibers (e.g. `intMkSrRoyUSDC`) live ONLY in the config repo, not the rootfiles repo. spellcaster is run from the rootfiles / makina-rs workspace and reads a `machines-local.toml` there — `/Users/augustin/Desktop/git/rootfiles/machines-local.toml` — which currently lists only `deth`, `mteth`, `dusd`. To run the through-caliber lifecycle e2e against a config-only caliber you MUST wire it in first:

1. Add a `config-local.toml` for the machine and point its caliber include at the config-repo `caliber.yaml`.
2. Register the machine in the rootfiles `machines-local.toml`:
   ```toml
   [intMkSrRoyUSDC]
   config = "local:/Users/augustin/Desktop/git/rootfiles/machines/intMkSrRoyUSDC/config-local.toml"
   ```
3. Run spellcaster from the makina-rs workspace (it is NOT on `$PATH`), passing the wired file:
   ```bash
   cargo run -p spellcaster -- \
     --machines-path /Users/augustin/Desktop/git/rootfiles/machines-local.toml --dev \
     --machine intMkSrRoyUSDC --caliber mainnet display-positions
   ```

Flag note: recent spellcaster takes `--machines-path`; the `--config <machines-local.toml>` form used elsewhere in these docs is the older flag name. Run `cargo run -p spellcaster -- --help` and use whichever your build accepts.

## Forks (dev)

`--dev` needs a fork RPC in `DEV_MAINNET_RPC_URL`. Two options:

- **Tenderly MCP** (`create_tenderly_testnet` → use its `admin_rpc` as `DEV_MAINNET_RPC_URL`). WARNING: the claude.ai Tenderly connector token can EXPIRE mid-session and will block every fork call. If Tenderly starts failing auth, switch to anvil instead of debugging the connector.
- **Local anvil fork (reliable fallback, no connector required):**
  ```bash
  anvil --fork-url $MAINNET_RPC_URL      # foundry is installed; MAINNET_RPC_URL is in .claude/settings.local.json
  # then point spellcaster at it:
  DEV_MAINNET_RPC_URL=http://127.0.0.1:8545 spellcaster --dev ...
  ```
  anvil supports `anvil_impersonateAccount`, `anvil_setBalance`, `evm_increaseTime`, and contract deploy via `forge create` — enough to drive the full deposit/request/claim/account cycle by hand.
