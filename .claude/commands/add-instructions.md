---
description: Add pool instruction to a fund - finds existing blueprints and generates instructions
argument-hint: [--actions=deposit,account,harvest,withdraw] <pool-identifier> <fund>
---

# Add Pool Instructions

Parse `$ARGUMENTS`:
- `--actions=<list>`: Comma-separated actions to test (default: `deposit,account,harvest,withdraw`)
- First positional: **pool identifier** (dialectic ID, address, or name)
- Second positional: **fund** (`mteth`, `dusd`, `deth`, `dbit`)

**Default actions**: `deposit`, `account`, `harvest`, `withdraw`

---

## Step 1: Get Pool Data

```
mcp__pools_db__get_pool_context(dialectic_id=<pool_identifier>)
```

Extract: protocol, chain, pool_address, supply_token_ids, category.

---

## Step 2: Find Blueprint (MANDATORY)

```bash
Glob: blueprints/{protocol_lowercase}/*.yaml
```

**If no blueprint found: STOP**
```
ERROR: No blueprint for '{protocol}'. Create first with:
  /integrate <fund> <pool-identifier>
```

---

## Step 3: Find Existing Instruction

```bash
Grep: {pool_address} in machines/
Glob: machines/**/instructions/*{protocol}*{token}*.yaml
```

**Case A**: Exact match exists -> copy to target fund
**Case B**: No match -> use similar instruction as template

---

## Step 4: Generate Instruction (if Case B)

Path: `machines/{fund}/{network}/instructions/{protocol}-{action}-{token}.yaml`

```yaml
- is_debt: false
  instruction_type: "MANAGEMENT"
  affected_tokens:
    - "{supply_token_address}"
  instruction:
    label: "{token_symbol}"
    path: "../../../blueprints/{protocol}/deposit.yaml:{action}"
    inputs:
      # Copy from template, replace pool-specific values
```

---

## Step 5: Test with execution-explorer

```
Test instruction at machines/{fund}/{network}/instructions/{file}.yaml
Execute selected actions on Tenderly.
```

Run for each action in `{actions}`:
- **deposit**: Test deposit flow
- **withdraw**: Test withdraw flow
- **account**: Test accounting
- **harvest**: Test reward claiming

Only run actions specified via `--actions` (or all defaults if not specified).

---

## Step 6: Test with blueprint-tester

```
End-to-end test: compile, update root, execute.
```

**Instruction ready when blueprint-tester passes.**

---

## Output

Report: pool info, blueprint used, instruction file created, test status.
