---
description: Test if an instruction file compiles with the transpiler
argument-hint: <path-to-instruction-file>
---

# Test Compile Instruction

Parse the arguments: `$ARGUMENTS`

- First argument: **instruction file path** (e.g., `machines/dbit/mainnet/instructions/aavev3-supply-usdc.yaml`)

---

## Step 1: Parse the Instruction Path

Extract from the path:
- **fund**: The machine/fund name (e.g., `dbit`, `mteth`, `dusd`, `deth`)
- **network**: The network (e.g., `mainnet`, `arbitrum`)
- **instruction_file**: The instruction filename

Expected path format: `machines/{fund}/{network}/instructions/{instruction_file}.yaml`

---

## Step 2: Read the Fund's Caliber Config

Read the config section from the fund's caliber.yaml:

```
Read: machines/{fund}/{network}/caliber.yaml
```

Extract just the `config:` section (not the positions).

---

## Step 3: Create Temporary Test Caliber

Create a minimal caliber file at `machines/{fund}/{network}/caliber-test.yaml`:

```yaml
config:
  # Copy the entire config section from the original caliber.yaml

positions:
  - id: "999999999999999999999999999999999999999"
    group_id: "0"
    description: "Test compilation"
    instructions: !include "./instructions/{instruction_filename}"
```

---

## Step 4: Run the Transpiler

Execute the transpiler using the `TRANSPILER_PATH` environment variable (set in `.claude/settings.local.json`):

```bash
transpiler -- \
  --input-file=/Users/augustin/Desktop/git/rootfiles/machines/{fund}/{network}/caliber-test.yaml \
  --output-file=/Users/augustin/Desktop/git/rootfiles/machines/{fund}/{network}/rootfiles/test-compile-output.toml
```

If `TRANSPILER_PATH` is not set, report an error asking the user to configure it in `.claude/settings.local.json`.

---

## Step 5: Report Result

### If successful:
```
✅ COMPILATION SUCCESS

Instruction: {instruction_path}
Transpiler output: Valid TOML generated
```

### If failed:
```
❌ COMPILATION FAILED

Instruction: {instruction_path}
Error: {error_message}

Common issues:
- Missing config variable referenced in instruction
- Invalid blueprint path
- Malformed YAML syntax
- Missing required inputs in blueprint
```

---

## Step 6: Cleanup

Always delete the temporary files:

```bash
rm machines/{fund}/{network}/caliber-test.yaml
rm machines/{fund}/{network}/rootfiles/test-compile-output.toml  # if created
```

---

## Example Usage

```
/test-compile machines/dbit/mainnet/instructions/aavev3-supply-usdc.yaml
```
