---
description: Compile an instruction file with the transpiler
argument-hint: [--keep] <path-to-instruction-file>
---

# Compile Instruction

Parse `$ARGUMENTS`:
- `--keep`: Preserve output files (default: cleanup)
- **instruction path**: e.g., `machines/dbit/mainnet/instructions/aavev3-supply-usdc.yaml`

Extract from path: `{fund}`, `{network}`, `{instruction_file}`

---

## Step 1: Read Caliber Config

```
Read: machines/{fund}/{network}/caliber.yaml
```

Extract the `config:` section only.

---

## Step 2: Create Test Caliber

Write `machines/{fund}/{network}/caliber-test.yaml`:

```yaml
config:
  # Copy config section from caliber.yaml

positions:
  - id: "999999999999999999999999999999999999999"
    group_id: "0"
    description: "Test compilation"
    instructions: !include "./instructions/{instruction_file}"
```

---

## Step 3: Run Transpiler

```bash
cd $TRANSPILER_PATH && cargo run -p transpiler -- \
  --input-file=machines/{fund}/{network}/caliber-test.yaml \
  --output-file=machines/{fund}/{network}/rootfiles/compile-output.toml
```

---

## Step 4: Report & Cleanup

**Success**: `COMPILATION SUCCESS - {instruction_path}`

**Failure**: Show error + common issues (missing config, invalid path, malformed YAML)

Unless `--keep`, delete:
- `caliber-test.yaml`
- `compile-output.toml`
