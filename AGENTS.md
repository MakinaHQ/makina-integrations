# Script Factory

Automated DeFi pool integration pipeline using Codex agents.

## Commands

| Command                                          | Description                                   |
| ------------------------------------------------ | --------------------------------------------- |
| `/integrate [--resume] [--context "..."] <pool>` | Full pipeline with checkpoint system          |
| `/add-instructions <pool> <machine>`             | Generate instruction from existing blueprint  |
| `/compile [--keep] <path>`                       | Compile instruction file (cleanup by default) |

## Pipeline

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        /integrate (pool-specific progress.yaml)                                            │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                            │
│  ┌──────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Stage 0  │  │ Stage 1     │  │ Stage 1b    │  │ Stage 1c    │  │ Stage 2     │  │ Stage 3     │  │ Stage 4     │        │
│  │ intent   │─▶│ pool-specs- │─▶│ specs-      │─▶│ offchain-   │─▶│ execution-  │─▶│ blueprint-  │─▶│ blueprint-  │        │
│  │          │  │ generator   │  │ enricher    │  │ analyzer    │  │ explorer×3  │  │ writer      │  │ tester      │        │
│  │          │  │ [opus]      │  │ [opus]      │  │ [opus]      │  │ [opus]      │  │ [opus]      │  │ [opus]      │        │
│  └──────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│       │              │                │                 │                │                │                │               │
│       │              ├────────────────┼─────────────────┼────────────────┼────────────────┼────────────────┤               │
│       │              │                │                 │                │                │                │               │
│       ▼              ▼                ▼                 ▼                ▼                ▼                ▼               │
│  progress.yaml  specs.yaml      functions.md     offchain_fetchers  execution-*.md  instructions/     e2e verified        │
│  (immutable     SUMMARY.md      (solidity code)  .md (conditional)  (deposit/        blueprints/                          │
│   intent)                                                            withdraw/acct)                                       │
│                                                                                                                            │
│  ◀─────────────────────── scripts-factory/{protocol}/{chain}/{pool_id}/progress.yaml ───────────────────────────────────▶  │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                       MCP Servers                                                          │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                            │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐                                                 │
│  │      pools_db       │  │      tenderly       │  │    Etherscan_MCP    │                                                 │
│  ├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤                                                 │
│  │ • get_pool_context  │  │ • create_testnet    │  │ • get_contract_abi  │                                                 │
│  │                     │  │ • execute_code      │  │ • get_contract_code │                                                 │
│  │                     │  │ • fund_address      │  │ • get_transactions  │                                                 │
│  │                     │  │ • debug_tx          │  │ • get_token_xfers   │                                                 │
│  │                     │  │ • get_rpc_url       │  │ • get_function_code │                                                 │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘                                                 │
│                                                                                                                            │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Checkpoint System (progress.yaml)

Each pool integration tracks progress in a pool-specific `progress.yaml` manifest:

```yaml
# scripts-factory/{protocol}/{chain}/{pool_id}/progress.yaml

# Intent - set at Stage 0, immutable
intent:
  pool_id: "278422b6a44a2c46fc1919acf4b0726e"
  pool_name: "Hop USDC/hUSDC"
  protocol: "hop"
  chain: "arb"
  machine: "mteth"
  actions: [deposit, withdraw, account]
  context: "pool uses external staking contract for rewards" # optional

# Progress tracking
current_stage: 2
stages:
  0_intent: { status: completed, timestamp: "2026-01-06T00:00:00Z" }
  1_specs: { status: completed }
  1b_enrich: { status: completed }
  1c_offchain: { status: completed } # conditional - skipped if no offchain patterns
  2_deposit: { status: in_progress }
  2_withdraw: { status: pending }
  2_account: { status: pending }
  3_blueprint: { status: pending }
  4_test: { status: pending }

# Shared resources (populated as stages run)
testnets: {}
```

**Stage status values**: `pending` | `in_progress` | `completed` | `failed`

**Failed stage schema** (with agent comment):

```yaml
2_deposit:
  status: failed
  error: "Transaction reverted: ERC20 insufficient allowance"
  comment: |
    Pool requires approval to router 0x1234... not pool directly.
    Partial progress saved in execution-deposit.md.
  testnet_id: "abc123"
  attempts: 2
```

**Resume interrupted/failed integrations**:

```bash
/integrate --resume mteth pool-xyz
```

## Agents

All agents use the **opus** model.

| Agent                | Purpose                                        | Output                               |
| -------------------- | ---------------------------------------------- | ------------------------------------ |
| pool-specs-generator | Collect pool data from on-chain                | `specs.yaml`, `SUMMARY.md`           |
| specs-enricher       | Fetch Solidity code for non-standard functions | `functions.md`                       |
| offchain-analyzer    | Research & generate offchain data fetchers     | `offchain_fetchers.md` (conditional) |
| execution-explorer   | Test flows on Tenderly forks                   | `execution-{action}.md`              |
| blueprint-writer     | Generate blueprint + instruction YAML          | `blueprints/`, `instructions/`       |
| blueprint-tester     | E2E validation with spellcaster                | Pass/fail report                     |

## Configuration

Set transpiler path in `.Codex/settings.local.json`:

```json
{
  "env": {
    "TRANSPILER_PATH": "/path/to/makina-rs"
  }
}
```

## File Structure

```
scripts-factory/
└── {protocol}/{chain}/{pool_id}/
    ├── specs.yaml           # Pool specifications
    ├── functions.md         # Solidity code for non-standard functions
    ├── offchain_fetchers.md # Python/Rust fetcher code (if offchain data needed)
    ├── SUMMARY.md           # Human-readable summary
    ├── progress.yaml        # Pipeline checkpoint state
    └── execution-*.md       # Execution test reports

blueprints/
└── {protocol}/
    ├── deposit.yaml
    ├── withdraw.yaml
    └── account.yaml

machines/
└── {machine}/{network}/
    ├── instructions/        # Pool-specific instructions
    └── rootfiles/           # Compiled TOML files
```

## Rules

### Instruction Files

- **Protocol-specific addresses should NOT be in config**: Addresses specific to a protocol (like `aavev3_core_instance`) should be hardcoded directly in the instruction files, not added to caliber.yaml config. Only fund-wide addresses (like `caliber_address`, `morpho_address`, helpers) belong in config.

## Quick Reference

```bash
# Full integration with checkpoints
/integrate aave-usdc-pool

# Integration with context hints
/integrate --context "uses external staking for rewards" curve-3pool

# Resume after crash/interrupt
/integrate --resume aave-usdc-pool

# Add instruction using existing blueprint
/add-instructions aave-usdc-pool deth

# Compile and validate (cleans up)
/compile machines/mteth/mainnet/instructions/aavev3-usdc.yaml

# Compile and keep output for debugging
/compile --keep machines/mteth/mainnet/instructions/aavev3-usdc.yaml
```
