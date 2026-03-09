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

| Command             | Description            |
| ------------------- | ---------------------- |
| `display-positions` | Show all positions     |
| `display-balances`  | Show token balances    |
| `manage-position`   | Execute instruction    |
| `dev-update-root`   | Update root on testnet |

## Documentation

For detailed documentation, read these files when needed:

- **CLI Reference**: `.Codex/skills/makina-cli/docs/cli-reference.md`
- **Root Updates**: `.Codex/skills/makina-cli/docs/root-updates.md`
- **Blueprint System**: `.Codex/skills/makina-cli/docs/blueprints.md`
- **Testing Workflows**: `.Codex/skills/makina-cli/docs/testing.md`

## Local Config

Use `--config machines-local.toml` for local development.

Set `DEV_MAINNET_RPC_URL` for Tenderly testnets.
