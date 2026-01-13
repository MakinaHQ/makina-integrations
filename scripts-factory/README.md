# Scripts Factory

Working directory for the automated DeFi pool integration pipeline.

## Structure

```
scripts-factory/
└── {protocol}/{chain}/{pool_id}/
    ├── progress.yaml        # Pipeline checkpoint state
    ├── specs.yaml           # Pool specifications (on-chain data)
    ├── SUMMARY.md           # Human-readable pool summary
    ├── execution-deposit.md # Deposit flow test report
    ├── execution-withdraw.md# Withdraw flow test report
    └── execution-account.md # Account flow test report
```

## Files

| File             | Stage | Description                                   |
| ---------------- | ----- | --------------------------------------------- |
| `progress.yaml`  | 0+    | Tracks pipeline progress, enables `--resume`  |
| `specs.yaml`     | 1     | Pool contracts, tokens, methods from on-chain |
| `SUMMARY.md`     | 1     | Human-readable summary of the pool            |
| `execution-*.md` | 2     | Tenderly fork test results for each action    |

## Pipeline Stages

```
Stage 0: Intent        → progress.yaml created
Stage 1: Specs         → specs.yaml, SUMMARY.md
Stage 2: Execution     → execution-{deposit,withdraw,account}.md
Stage 3: Blueprint     → blueprints/{protocol}/*.yaml
Stage 4: Test          → E2E validation complete
```

## Usage

```bash
# Start new integration
/integrate mteth hop-usdc-pool

# Resume interrupted integration
/integrate --resume mteth hop-usdc-pool
```

## Notes

- Each pool gets its own folder identified by `pool_id`
- The `progress.yaml` intent section is immutable after Stage 0
- Final outputs (blueprints, instructions) are written outside this folder
- This folder contains intermediate working files for the pipeline
