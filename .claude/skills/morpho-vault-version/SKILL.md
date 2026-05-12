---
name: morpho-vault-version
description: Detect whether a Morpho vault is V1 (MetaMorpho) or V2 (VaultV2) before adding or modifying any Morpho vault instruction. Use when adding, replacing, or editing a Morpho vault position in any caliber.yaml or instruction file — Claude MUST invoke `scripts/morpho_vault_version.py` before deciding which instruction file (morpho-vault-v1.yaml vs morpho-vault-v2.yaml) to point at.
allowed-tools: Bash(python3:*), Bash(scripts/morpho_vault_version.py:*), Read
---

# Morpho Vault Version Detection

## When to use

Invoke this skill any time you are about to:
- Add a new Morpho vault position to a caliber.yaml
- Change the `vault_address` of an existing Morpho vault position
- Edit a position that currently uses `morpho-vault-v1.yaml` or `morpho-vault-v2.yaml`
- Audit whether an existing position is wired to the correct instruction file

The user does not need to ask. If the task mentions a Morpho vault address, run the script.

## What it does

`scripts/morpho_vault_version.py` queries the vault on-chain via `cast call` and returns whether it is V1 or V2:
- **V1 (MetaMorpho)** → `MORPHO()(address)` succeeds → use `instructions/morpho-vault-v1.yaml`
- **V2 (VaultV2)** → `firstTotalAssets()(uint256)` succeeds → use `instructions/morpho-vault-v2.yaml`

## How to run

```bash
# Human-readable
python3 scripts/morpho_vault_version.py <VAULT_ADDRESS> [--chain mainnet|arbitrum]

# JSON (best for programmatic use)
python3 scripts/morpho_vault_version.py <VAULT_ADDRESS> --chain mainnet --json
```

Built-in RPCs:
- `mainnet` → Tenderly private gateway
- `arbitrum` → Tenderly private gateway

For other chains, pass `--rpc-url <URL>` or set env `RPC_<CHAIN_UPPER>`.

## Important: lens deployment status

`instructions/morpho-vault-v2.yaml` requires the Morpho VaultV2LiquidityLib lens, which is referenced via `${config.morpho_v2_liquidity_lens_address}`. The lens is currently deployed on:

| chain | lens address |
|---|---|
| mainnet | `0x5171Bc00DA5Fc7Ae1eDe189d88B980cAEfb6c690` |
| arbitrum | NOT YET DEPLOYED |

If you detect a V2 vault on a chain where the lens is not yet deployed, **wire it to `morpho-vault-v1.yaml`** instead and leave a note. Don't add `morpho_v2_liquidity_lens_address` to that caliber's `config:` block.

## Output → action mapping

| script output | caliber.yaml `!include` | requires lens config |
|---|---|---|
| `v1` | `instructions/morpho-vault-v1.yaml` | no |
| `v2` on mainnet | `instructions/morpho-vault-v2.yaml` | yes (`morpho_v2_liquidity_lens_address`) |
| `v2` on chain without lens | `instructions/morpho-vault-v1.yaml` (with note) | no |
| `unknown` | stop and report — likely not a Morpho-style vault | n/a |

## Bulk renaming

For a one-shot rewrite of every existing `morpho-vault.yaml` include in the repo to the right v1/v2 path, use `scripts/migrate_morpho_vault_includes.py` (already used during the V1/V2 split migration). It calls the detection script per vault.

## Source

- Detection logic: `scripts/morpho_vault_version.py`
- V2 emergency blueprint that depends on the lens: `blueprints/morpho/emergency.yaml` (`emergency_redeem_vault_v2`)
- Lens contract source (audit-pinned, commit 9293142): https://github.com/morpho-org/morpho-snippets/blob/9293142da55804b6bcfccdd0ddfe237ee9b4d27a/src/vault-v2/VaultV2LiquidityLib.sol
