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

The transpiler is a **separately-installed binary** — it is NOT on `PATH`, and it is NOT in the local makina-rs checkout (that repo's `calldata` crate is an HTTP API server, not the transpiler). Resolve the binary in this order:

1. `$TRANSPILER_PATH` if it is set in `.claude/settings.local.json`.
2. Otherwise fall back to the known build:
   `/Users/augustin/.cargo/git/checkouts/transpiler-11f55d1751042103/9471437/target/debug/transpiler`

Run from the **config repo root**. Global options come BEFORE the `transpile` subcommand, and `--token-list` is **required** because instructions reference `${token_list.*}`:

```bash
TRANSPILER="${TRANSPILER_PATH:-/Users/augustin/.cargo/git/checkouts/transpiler-11f55d1751042103/9471437/target/debug/transpiler}"

"$TRANSPILER" \
  --input-file machines/{fund}/{network}/caliber-test.yaml \
  --token-list token-lists/prod-token-list.json \
  --output-file /tmp/makina-test-compile-output.toml \
  transpile
```

- Paths are relative to the **config repo root** — do NOT point at `/Users/.../git/rootfiles`. Many calibers (e.g. `intMkSrRoyUSDC`) live ONLY in the config repo, not the rootfiles repo.
- The subcommand (`transpile` or `check`) is a positional argument and goes LAST, after the flags. There is no `--` separator — that syntax is only for `cargo run -- …`.
- If the instruction also references `${helpers.*}`, add `--helpers <path-to-helpers.json>`.
- **Never write `--output-file` into `machines/*/*/rootfiles/`.** Rootfiles are release-generated build artifacts now; `rootfiles-guard` rejects any PR that adds or modifies a file under a `rootfiles/` directory, so always send output outside the repo (`/tmp/...`).

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
- Missing `--token-list token-lists/prod-token-list.json` (shows up as an unresolved `${token_list.*}` reference, not a syntax error), or a missing `--helpers` list when the instruction uses `${helpers.*}`
```

---

## Step 6: Cleanup

Always delete the temporary files:

```bash
rm machines/{fund}/{network}/caliber-test.yaml
rm /tmp/makina-test-compile-output.toml  # if created
```

---

## Example Usage

```
/test-compile machines/dbit/mainnet/instructions/aavev3-supply-usdc.yaml
```
