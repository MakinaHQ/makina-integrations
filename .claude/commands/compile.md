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

The transpiler is a **standalone binary that is NOT on `$PATH`** and is separate from the `makina-rs` checkout (that checkout's `calldata` crate is an HTTP API server, not the transpiler, and its `abu` branch lacks the transpiler crate). Resolve it from `$TRANSPILER_PATH`; if that env var is unset (it is NOT set in this repo's `.claude/settings.local.json`), fall back to the pinned install path:

```bash
TRANSPILER="${TRANSPILER_PATH:-/Users/augustin/.cargo/git/checkouts/transpiler-11f55d1751042103/9471437/target/debug/transpiler}"

"$TRANSPILER" \
  --input-file machines/{fund}/{network}/caliber-test.yaml \
  --token-list token-lists/prod-token-list.json \
  --output-file machines/{fund}/{network}/rootfiles/compile-output.toml \
  transpile
```

- `--token-list token-lists/prod-token-list.json` is **REQUIRED**: instructions reference `${token_list.*}` and the run fails to resolve them without it (applies to both `transpile` and `check`).
- The subcommand is a **positional argument that comes AFTER the flags**: `transpile` emits TOML, `check` validates only (`root` also exists).
- Short flags: `-i` = `--input-file`, `-o` = `--output-file`, `-t` = `--token-list`.
- Do NOT write `transpiler -- ...`; the leading `--` is a `cargo run` artifact and is wrong for the standalone binary.

---

## Step 4: Report & Cleanup

**Success**: `COMPILATION SUCCESS - {instruction_path}`

**Failure**: Show error + common issues (missing `--token-list` → unresolved `${token_list.*}` references; missing config variable; invalid `!include` path; malformed YAML; wrong `$TRANSPILER_PATH`/binary not found).

Unless `--keep`, delete:
- `caliber-test.yaml`
- `compile-output.toml`

---

## Step 5: Format Before Commit (dprint CI gate)

CI runs a `formatting` (dprint) check that reflows YAML/Markdown/TOML. After editing any instruction or caliber file, run:

```bash
dprint fmt
```

`dprint.json` excludes `.claude`, `CLAUDE.md`, and `protocol_specs`. Forgetting this is a frequent red CI run — always run it before committing or opening a PR.
