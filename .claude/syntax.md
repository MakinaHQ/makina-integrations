# Rootfiles Syntax Reference

This document defines all conventions, schemas, and best practices for instruction and blueprint files in the rootfiles project.

---

## Table of Contents

1. [Overview](#overview)
2. [File Organization](#file-organization)
3. [Caliber Files](#caliber-files)
4. [Instruction Files](#instruction-files)
5. [Blueprint Files](#blueprint-files)
6. [Template Variables](#template-variables)
7. [Data Types](#data-types)
8. [Naming Conventions](#naming-conventions)
9. [Common Patterns](#common-patterns)
10. [Protocol-Specific Patterns](#protocol-specific-patterns)
11. [Validation Rules](#validation-rules)

---

## Overview

The rootfiles system uses two primary file types:

| File Type        | Purpose                                              | Location                                     |
| ---------------- | ---------------------------------------------------- | -------------------------------------------- |
| **Instructions** | Define pool-specific operations with concrete values | `instructions/` (general) or `machines/{machine}/{network}/instructions/` (machine-specific) |
| **Blueprints**   | Define reusable, generic action templates            | `blueprints/{protocol}/`                     |

**Relationship**: Instructions reference blueprint actions and provide concrete parameter values. Multiple instructions can reuse the same blueprint with different parameters.

**General vs Machine-Specific Instructions**: Prefer placing instructions in the top-level `instructions/` directory when they can be reused across multiple machines or positions (especially when parameterized with position vars). Only place instructions in `machines/{machine}/{network}/instructions/` when they are truly specific to one machine and cannot be generalized.

---

## File Organization

### Directory Structure

```
rootfiles/
├── blueprints/
│   ├── aave/
│   │   ├── account.yaml
│   │   ├── borrow.yaml
│   │   └── deposit.yaml
│   ├── convex-curve/
│   │   ├── account.yaml
│   │   ├── deposit.yaml
│   │   ├── harvest.yaml
│   │   └── withdraw.yaml
│   └── {protocol}/
│       └── {action}.yaml
│
├── instructions/                          # PREFERRED: General instructions (reusable across machines)
│   ├── infinifi-liusd.yaml               # Parameterized via position vars
│   └── {protocol}-{identifier}.yaml
│
└── machines/
    └── {machine}/
        └── {network}/
            ├── caliber.yaml              # Position definitions with !include and vars
            ├── instructions/             # Machine-specific instructions (when not generalizable)
            │   ├── aavev3-borrow-usdc.yaml
            │   ├── convex-curve-weth-reth.yaml
            │   └── {protocol}-{identifier}.yaml
            └── rootfiles/
                └── {compiled}.toml
```

### General vs Machine-Specific Instructions

**Prefer general instructions** in the top-level `instructions/` directory. Use machine-specific instructions only when necessary.

| Location | When to Use | `!include` Path (from caliber.yaml) |
|----------|-------------|--------------------------------------|
| `instructions/` | Instruction can serve multiple machines/positions via position vars | `"../../../instructions/{file}.yaml"` |
| `machines/{machine}/{network}/instructions/` | Truly machine-specific (unique config, addresses, etc.) | `"./instructions/{file}.yaml"` |

**When to use general instructions:**
- The same protocol instruction works across multiple machines (e.g., different funds)
- The instruction can be parameterized via position vars (e.g., different lock durations, token addresses)
- Multiple positions in the same machine use the same instruction with different vars

**Example**: InfiniFi liUSD instruction is general—one file serves both 1-week and 4-week lock positions by varying `${position.weeks}` and `${position.share_token_address}`.

### Blueprint Protocols

Available protocols (there may be more):

```
aave            aave-umbrella     across-v2         aerodrome-cl
auto            convex-curve      convex-curve-metapool  convex-fx
curve           curve-llamalend   dolomite          euler-earn
euler-lend      fluid             fluid-lite        fxsave
infinifi        lagoon            makina            merkl
morpho          morpho-pendle-pt-loop  pendle-pt    shroomy
silo            stakedao-curve    stakedao-yearn    sturdy-v2
summerfi        superform         tokemak           tydro
velodrome-cl
```

---

## Caliber Files

### Position Definitions

Caliber files (`caliber.yaml` or `caliber-test.yaml`) define positions that reference instruction files via `!include`:

```yaml
config:
  some_address:
    type: "address"
    value: "0x..."
  # ... other machine-wide config

positions:
  - id: "11"
    group_id: "0"
    description: "InfiniFi liUSD 1-Week Lock"
    instructions: !include "../../../instructions/infinifi-liusd.yaml"
    vars:
      weeks: "1"
      share_token_address: "0x12b004719fb632f1E7c010c6F5D6009Fb4258442"
      kv_storage_key: "0xbbfbcd1a..."

  - id: "14"
    group_id: "0"
    description: "InfiniFi liUSD 4-Week Lock"
    instructions: !include "../../../instructions/infinifi-liusd.yaml"
    vars:
      weeks: "4"
      share_token_address: "0x66bCF6151D5558AfB47c38B20663589843156078"
      kv_storage_key: "0x7a6ea5e1..."
```

### `!include` Directive

The `!include` directive inlines the contents of a YAML file at that location. The path is relative to the caliber file's location.

| Instruction Location | `!include` Path |
|---------------------|-----------------|
| `instructions/infinifi-liusd.yaml` (general) | `"../../../instructions/infinifi-liusd.yaml"` |
| `./instructions/aavev3-supply-usdc.yaml` (machine-specific) | `"./instructions/aavev3-supply-usdc.yaml"` |

### Position Variables (`vars`)

The `vars` field on a position defines key-value pairs that are available in the instruction file as `${position.var_name}`. This enables **one instruction file to serve multiple positions** with different parameters.

**Convention for KV storage keys**: Use `keccak256("makina.{network}.{protocol}.{identifier}")` to generate unique bytes32 keys per position/bucket. Document the source string in a comment.

```yaml
vars:
  weeks: "1"
  share_token_address: "0x12b004719fb632f1E7c010c6F5D6009Fb4258442" # liUSD-1w
  kv_storage_key: "0xbbfbcd1a..." # ${keccak256(makina.mainnet.infinifi.liusd-1w)}
```

---

## Instruction Files

### File Naming

Pattern: `{protocol}-{optional action, pool-identifier, or token if it can't be generalised}.yaml`

Examples:

- `aavev3-borrow.yaml` - Protocol-action (general by action, things like token can be position vars)
- `infinifi-liusd.yaml` - Protocol-token (general, things like epoch can be via position vars)
- `convex-curve.yaml` - Protocol-subprotocol-token-pair (general, token paris can be position vars)
- `morpho-market-collateral.yaml` - Protocol-market-role
- `across-v2-usdc.yaml` - Protocol-version-token (very specific, usually in machine specific instructions)


### Schema

Instructions are YAML arrays where each element is an operation:

```yaml
- is_debt: boolean
  instruction_type: string
  affected_tokens:
    - "0x..." # TOKEN_SYMBOL
  instruction:
    label: string
    path: string
    inputs:
      parameter_name:
        type: string
        value: string
```

### Field Reference

| Field                | Type    | Required | Description                                          |
| -------------------- | ------- | -------- | ---------------------------------------------------- |
| `is_debt`            | boolean | Yes      | `true` for borrow/debt operations, `false` otherwise |
| `instruction_type`   | string  | Yes      | Type of operation (see below)                        |
| `affected_tokens`    | array   | Yes      | List of token addresses affected                     |
| `instruction.label`  | string  | Yes      | Human-readable label                                 |
| `instruction.path`   | string  | Yes      | Reference to blueprint action                        |
| `instruction.inputs` | object  | Yes      | Input parameters for the action                      |

### Instruction Types

| Type                   | Description                                                           |
| ---------------------- | --------------------------------------------------------------------- |
| `MANAGEMENT`           | Executes state-changing transactions (deposits, withdrawals, borrows) |
| `ACCOUNTING`           | Read-only operations for balance calculations                         |
| `HARVEST`              | Claims rewards from protocols                                         |
| `FLASHLOAN_MANAGEMENT` | Operations executed within flash loan context                         |

### Path Field Format For Including Blueprints

```
../../../blueprints/{protocol}/{action-file}.yaml:{action-name}
```

Examples:

- `../../../blueprints/convex-curve/deposit.yaml:deposit_single_sided_token_a`
- `../../../blueprints/morpho/account.yaml:account_collateral`
- `../../../blueprints/aave/borrow.yaml:borrow_asset`

### Input Parameters

Each input requires `type` and `value`:

```yaml
inputs:
  vault_address:
    type: "address"
    value: "0x1234567890abcdef..."
  pool_id:
    type: "uint256"
    value: "287"
  caliber_address:
    type: "address"
    value: "${config.caliber_address}"
```

### Example Instructions

**Simple Deposit:**

```yaml
- is_debt: false
  instruction_type: "MANAGEMENT"
  affected_tokens:
    - "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" # USDC
  instruction:
    label: "USDC"
    path: "../../../blueprints/aave/deposit.yaml:deposit"
    inputs:
      token:
        type: "address"
        value: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
      caliber_address:
        type: "address"
        value: "${config.caliber_address}"
```

**Borrow Operation:**

```yaml
- is_debt: true
  instruction_type: "MANAGEMENT"
  affected_tokens:
    - "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" # USDC
  instruction:
    label: "USDC"
    path: "../../../blueprints/aave/borrow.yaml:borrow_asset"
    inputs:
      token:
        type: "address"
        value: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
      interest_rate_mode:
        type: "uint256"
        value: "2"
      referral_code:
        type: "uint256"
        value: "0"
```

**Accounting Operation:**

```yaml
- is_debt: false
  instruction_type: "ACCOUNTING"
  affected_tokens:
    - "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0" # wstETH
  instruction:
    label: "wstETH"
    path: "../../../blueprints/morpho/account.yaml:account_collateral"
    inputs:
      market_id:
        type: "bytes32"
        value: "0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc"
      morpho:
        type: "address"
        value: "${config.morpho_address}"
```

**Harvest Operation:**

```yaml
- is_debt: false
  instruction_type: "HARVEST"
  affected_tokens: []
  instruction:
    label: "rewards"
    path: "../../../blueprints/convex-curve/harvest.yaml:harvest"
    inputs:
      convex_reward_contract_address:
        type: "address"
        value: "0x1234..."
      caliber_address:
        type: "address"
        value: "${config.caliber_address}"
```

---

## Blueprint Files

### Schema

```yaml
protocol: string
constants: # Optional
  constant_name:
    type: string
    value: string
inputs:
  parameter_name:
    type: string
actions:
  action_name:
    calls:
      - description: string
        target: string
        selector: string
        parameters: array
        return: object # Optional
    input_slots: # Optional
      slot_name:
        type: string
        description: string
    reserved_slots: # For accounting actions
      - type: string
        value: string
```

### Field Reference

| Field       | Type   | Required | Description                                    |
| ----------- | ------ | -------- | ---------------------------------------------- |
| `protocol`  | string | Yes      | Protocol identifier (e.g., `aavev3`, `morpho`) |
| `constants` | object | No       | Shared constant values for all actions         |
| `inputs`    | object | Yes      | Input parameter definitions                    |
| `actions`   | object | Yes      | Named action definitions                       |

### Actions Structure

Each action contains:

| Field            | Type   | Required | Description                 |
| ---------------- | ------ | -------- | --------------------------- |
| `calls`          | array  | Yes      | Sequence of contract calls  |
| `input_slots`    | object | No       | Runtime dynamic inputs      |
| `reserved_slots` | array  | No       | Output slots for accounting |

### Call Structure

```yaml
- description: "Approve token spending"
  target: "${inputs.token_address}"
  selector: "approve(address,uint256)"
  parameters:
    - type: "address"
      value: "${inputs.spender}"
    - type: "uint256"
      value: "${builtins.UINT256_MAX}"
  return:
    name: "approval_result"
    type: "bool"
```

### Selector Format

Function signature with parameter types:

- `"approve(address,uint256)"`
- `"deposit(uint256,address)"`
- `"add_liquidity(uint256[],uint256)"`
- `"balanceOf(address)"`
- `"getPosition(address,bytes32)"`

### Array Parameters

```yaml
parameters:
  - type: "uint256[]"
    value:
      - type: "uint256"
        value: "${input_slots.amount_a}"
      - type: "uint256"
        value: "0"
```

### Example Blueprint

```yaml
protocol: convex-curve

inputs:
  asset_a_address:
    type: "address"
  asset_b_address:
    type: "address"
  curve_pool_address:
    type: "address"
  convex_booster_address:
    type: "address"
  pool_id:
    type: "uint256"
  caliber_address:
    type: "address"

actions:
  deposit_single_sided_token_a:
    calls:
      - description: "Approve Curve pool to spend token A"
        target: "${inputs.asset_a_address}"
        selector: "approve(address,uint256)"
        parameters:
          - type: "address"
            value: "${inputs.curve_pool_address}"
          - type: "uint256"
            value: "${builtins.UINT256_MAX}"

      - description: "Add liquidity to Curve pool"
        target: "${inputs.curve_pool_address}"
        selector: "add_liquidity(uint256[],uint256)"
        parameters:
          - type: "uint256[]"
            value:
              - type: "uint256"
                value: "${input_slots.amount_to_deposit}"
              - type: "uint256"
                value: "0"
          - type: "uint256"
            value: "${input_slots.min_lp_amount}"
        return:
          name: "lp_tokens_received"
          type: "uint256"

      - description: "Deposit LP into Convex"
        target: "${inputs.convex_booster_address}"
        selector: "deposit(uint256,uint256,bool)"
        parameters:
          - type: "uint256"
            value: "${inputs.pool_id}"
          - type: "uint256"
            value: "${returns.lp_tokens_received}"
          - type: "bool"
            value: true

    input_slots:
      amount_to_deposit:
        type: "uint256"
        description: "Amount of token A to deposit"
      min_lp_amount:
        type: "uint256"
        description: "Minimum LP tokens to receive"
```

---

## Template Variables

### Syntax

All template variables use `${...}` syntax:

```yaml
value: "${inputs.token_address}"
value: "${config.caliber_address}"
value: "${returns.balance}"
value: "${builtins.UINT256_MAX}"
```

### Variable Categories

| Category    | Syntax                | Description                    |
| ----------- | --------------------- | ------------------------------ |
| Inputs      | `${inputs.name}`      | Blueprint input parameters     |
| Config      | `${config.name}`      | Runtime configuration values   |
| Returns     | `${returns.name}`     | Previous call return values    |
| Constants   | `${constants.name}`   | Blueprint-defined constants    |
| Input Slots | `${input_slots.name}` | Action-specific runtime inputs |
| Builtins    | `${builtins.NAME}`    | System-provided constants      |
| Position    | `${position.name}`    | Position-specific vars from caliber.yaml (but use these inside instruction files only to not have position -> blueprint dependency) |

### Config Variables

Common configuration variables:

```yaml
${constants.caliber_helper_address}    # Helper contract
${constants.unsigned_math_helper_address}  # Math utilities
${config.flash_loan_aggregator}     # Flash loan provider
${config.swap_module}               # DEX aggregator
${constants.kv_store_address}          # Key-value store
```

### Builtins

```yaml
${builtins.UINT256_MAX}   # Maximum uint256 (2^256 - 1)
${builtins.UINT128_MAX}   # Maximum uint128 (2^128 - 1)
${builtins.UINT256_1}     # Value of 1
...
```

### Position Variables

Position variables are defined in the caliber.yaml `vars` field and referenced in instructions as `${position.name}`. They enable one instruction file to serve multiple positions with different parameters.

```yaml
# In instruction file:
unwinding_epochs:
  type: "uint32"
  value: ${position.weeks}        # Resolved from caliber.yaml vars
share_token_address:
  type: "address"
  value: ${position.share_token_address}  # Resolved from caliber.yaml vars
kv_storage_key:
  type: "bytes32"
  value: ${position.kv_storage_key}       # Resolved from caliber.yaml vars
```

Note: Position variable references do NOT use quotes around the `${position.*}` value


## In general look at other blueprints/instructions to see anything that you think should already exist (as it might)
---

## Data Types

### EVM Types

| Type      | Description              | Example                                                                |
| --------- | ------------------------ | ---------------------------------------------------------------------- |
| `address` | 20-byte Ethereum address | `"0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"`                         |
| `uint256` | 256-bit unsigned integer | `"1000000000000000000"`                                                |
| `uint128` | 128-bit unsigned integer | `"340282366920938463463374607431768211455"`                            |
| `uint16`  | 16-bit unsigned integer  | `"65535"`                                                              |
| `int128`  | 128-bit signed integer   | `"-1000"`                                                              |
| `bytes32` | 32-byte value            | `"0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc"` |
| `bytes`   | Variable-length bytes    | `"0x..."`                                                              |
| `bool`    | Boolean                  | `true` or `false`                                                      |

### Array Types

```yaml
type: "uint256[]"
value:
  - type: "uint256"
    value: "100"
  - type: "uint256"
    value: "200"
```

### Tuple Types

```yaml
type: "(address,address,address,address,uint256)"
```

### Formatting Rules

1. **Addresses**: Always checksummed, with `0x` prefix
   ```yaml
   value: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
   ```

2. **Numbers**: Always as strings in YAML
   ```yaml
   value: "287"
   value: "1000000000000000000" # 1e18
   ```

3. **Comments**: Token symbols after addresses
   ```yaml
   affected_tokens:
     - "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" # USDC
     - "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2" # WETH
   ```

---

## Naming Conventions

### File Names

| Component         | Convention          | Example                         |
| ----------------- | ------------------- | ------------------------------- |
| Protocol          | lowercase, hyphens  | `convex-curve`, `aave-umbrella` |
| Action files      | lowercase, singular | `deposit.yaml`, `account.yaml`  |
| Instruction files | protocol-<optional identifiers> | `convex-curve.yaml` or `morpho-market-supply.yaml`   |

### Action Names

Use `snake_case` with descriptive naming:

**Deposit Actions:**

- `deposit` - Simple deposit
- `deposit_single_sided_token_a` - Single-sided (token A)
- `deposit_single_sided_token_b` - Single-sided (token B)
- `deposit_balanced` - Balanced multi-token
- `add_collateral` - Add collateral to lending

**Withdraw Actions:**

- `withdraw` - Simple withdrawal
- `withdraw_single_sided_token_a` - Single-sided to token A
- `withdraw_single_sided_token_a_relative` - Percentage-based
- `withdraw_balanced` - Balanced withdrawal
- `withdraw_collateral` - Remove collateral
- `redeem` - Redeem vault shares

**Account Actions:**

- `account` - Standard position accounting
- `account_single_sided_token_a` - Single-sided accounting
- `account_balanced` - Balanced pool accounting
- `account_collateral` - Collateral position
- `account_debt` - Debt position
- `account_loan` - Loan position

**Multi-Step Withdraw Actions:**

- `start_unwinding_relative` - Step 1: initiate time-locked withdrawal (percentage-based)
- `complete_withdraw` - Step 2: claim tokens after lock period expires

**Other Actions:**

- `harvest` - Claim rewards
- `borrow_asset` - Borrow from lending
- `repay_asset` - Repay borrowed assets
- `stake` - Stake tokens
- `loop_in` - Enter leveraged position

### Variable Names

| Context     | Convention   | Example                              |
| ----------- | ------------ | ------------------------------------ |
| Inputs      | `snake_case` | `token_address`, `pool_id`           |
| Input slots | `snake_case` | `amount_to_deposit`, `min_lp_amount` |
| Returns     | `snake_case` | `lp_tokens_received`, `balance`      |
| Config      | `snake_case` | `caliber_address`, `morpho_address`  |

---

## Common Patterns

### Blueprint Constants for Shared Helpers

When helper contract addresses are the same across all machines (e.g., context helper, boolean helper), define them as blueprint `constants` rather than `inputs`. This avoids requiring every instruction to pass the same addresses.

```yaml
# In blueprint:
constants:
  context_helper_address:
    type: "address"
    value: "0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE"
  math_helper_address:
    type: "address"
    value: "0x3D623B199E290358416415eA7e05B635E442e3c0"
  boolean_helper_address:
    type: "address"
    value: "0x00c93e3b09Ca2f544487d4298339765EadCD8353"
  kv_store_address:
    type: "address"
    value: "0xa81fC382489F9560211AB15aD87f001b98C92E91"

# Only protocol-specific addresses go in inputs:
inputs:
  gateway_address:
    type: "address"
  share_token_address:
    type: "address"
```

**When to use constants vs inputs:**
- **Constants**: Addresses shared across all deployments (helpers, stores). Hardcoded in the blueprint.
- **Inputs**: Protocol-specific addresses that vary per pool/position. Provided by the instruction file.
- **Config**: Machine-level addresses (kv store is per machine for example). Provided at runtime by the machine config.

### Approve-Then-Execute

```yaml
calls:
  - description: "Approve spender"
    target: "${inputs.token_address}"
    selector: "approve(address,uint256)"
    parameters:
      - type: "address"
        value: "${inputs.spender}"
      - type: "uint256"
        value: "${builtins.UINT256_MAX}"

  - description: "Execute operation"
    target: "${inputs.protocol_address}"
    selector: "deposit(uint256)"
    parameters:
      - type: "uint256"
        value: "${input_slots.amount}"
```

### Query-Then-Use

```yaml
calls:
  - description: "Get balance"
    target: "${inputs.token}"
    selector: "balanceOf(address)"
    parameters:
      - type: "address"
        value: "${inputs.caliber_address}"
    return:
      name: "balance"
      type: "uint256"

  - description: "Withdraw all"
    target: "${inputs.vault}"
    selector: "withdraw(uint256)"
    parameters:
      - type: "uint256"
        value: "${returns.balance}"
```

### Tuple Extraction

```yaml
calls:
  - description: "Get market params"
    target: "${inputs.morpho}"
    selector: "idToMarketParams(bytes32)"
    parameters:
      - type: "bytes32"
        value: "${inputs.market_id}"
    return:
      name: "market_params"
      type: "(address,address,address,address,uint256)"

  - description: "Extract loan token"
    target: "${inputs.executor_helper}"
    selector: "extractElementFromStaticTuple(bytes,uint256)"
    parameters:
      - type: "(address,address,address,address,uint256)"
        value: "${returns.market_params}"
      - type: "uint256"
        value: "0"
    return:
      name: "loan_token"
      type: "address"
```

### Slippage Protection

Always include minimum output amounts:

```yaml
input_slots:
  amount_to_deposit:
    type: "uint256"
    description: "Amount to deposit"
  min_lp_amount:
    type: "uint256"
    description: "Minimum LP tokens (slippage protection)"
```

### Relative vs Absolute

**Absolute**: Exact amounts

```yaml
actions:
  withdraw_single_sided_token_a:
    input_slots:
      amount_to_withdraw:
        type: "uint256"
        description: "Exact amount to withdraw"
```

**Relative**: Percentage-based (basis points)

```yaml
actions:
  withdraw_single_sided_token_a_relative:
    input_slots:
      bps_to_withdraw:
        type: "uint256"
        description: "Basis points to withdraw (10000 = 100%)"
```

### Multi-Step Withdrawal with KV Store

For protocols with time-locked withdrawals (e.g., epoch-based locks), use the KV store to track the unwinding timestamp across transactions:

```yaml
# Step 1 (start_unwinding): Burns shares, stores block.timestamp in KV store
calls:
  # ... guard: check no existing unwinding (KV value == 0) ...
  # ... calculate shares from bps ...
  # ... approve + call startUnwinding ...
  - description: "Get block timestamp"
    target: "${constants.context_helper_address}"
    selector: "blockTimestamp()"
    parameters: []
    return:
      name: "unwinding_timestamp"
      type: "uint256"
  - description: "Store unwinding timestamp in KV store"
    target: "${constants.kv_store_address}"
    selector: "set(bytes32,bytes32)"
    parameters:
      - type: "bytes32"
        value: "${inputs.kv_storage_key}"
      - type: "uint256"
        value: "${returns.unwinding_timestamp}"

# Step 2 (complete_withdraw): Reads timestamp from KV store, withdraws, clears KV store
calls:
  - description: "Get unwinding timestamp from KV store"
    target: "${constants.kv_store_address}"
    selector: "get(bytes32)"
    parameters:
      - type: "bytes32"
        value: "${inputs.kv_storage_key}"
    return:
      name: "unwinding_timestamp"
      type: "uint256"
  # ... guard: revert if timestamp == 0 ...
  - description: "Withdraw using stored timestamp"
    target: "${inputs.gateway_address}"
    selector: "withdraw(uint256)"
    parameters:
      - type: "uint256"
        value: "${returns.unwinding_timestamp}"
  - description: "Clear KV store"
    target: "${constants.kv_store_address}"
    selector: "set(bytes32,bytes32)"
    parameters:
      - type: "bytes32"
        value: "${inputs.kv_storage_key}"
      - type: "uint256"
        value: "0"
```

### Parameterized Instructions with Position Variables

Use `${position.*}` to write one instruction file that serves multiple positions:

```yaml
# instructions/infinifi-liusd.yaml (general, parameterized)
- is_debt: false
  instruction_type: "MANAGEMENT"
  affected_tokens:
    - "0x48f9e38f3070AD8945DFEae3FA70987722E3D89c" # iUSD
  instruction:
    label: "liUSD Lock"
    path: "../../../blueprints/infinifi/deposit.yaml:deposit"
    inputs:
      gateway_address:
        type: "address"
        value: "0x3f04b65Ddbd87f9CE0A2e7Eb24d80e7fb87625b5"
      iusd_address:
        type: "address"
        value: "0x48f9e38f3070AD8945DFEae3FA70987722E3D89c"
      unwinding_epochs:
        type: "uint32"
        value: ${position.weeks}          # Resolved from caliber vars
```

Then in caliber.yaml, each position provides different vars:

```yaml
positions:
  - id: "11"
    instructions: !include "../../../instructions/infinifi-liusd.yaml"
    vars:
      weeks: "1"
      share_token_address: "0x12b004719fb632f1E7c010c6F5D6009Fb4258442"
      kv_storage_key: "0xbbfbcd1a..."
  - id: "14"
    instructions: !include "../../../instructions/infinifi-liusd.yaml"
    vars:
      weeks: "4"
      share_token_address: "0x66bCF6151D5558AfB47c38B20663589843156078"
      kv_storage_key: "0x7a6ea5e1..."
```

---

## Protocol-Specific Patterns

### Aave V3

```yaml
# Interest rate mode: 2 = variable rate
interest_rate_mode:
  type: "uint256"
  value: "2"

# Referral code (usually 0)
referral_code:
  type: "uint256"
  value: "0"
```

### Morpho

```yaml
# Market ID identifies the market
market_id:
  type: "bytes32"
  value: "0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc"

# Market params tuple: (loanToken, collateral, oracle, irm, lltv)
type: "(address,address,address,address,uint256)"
```

### Convex/Curve

```yaml
# Pool ID in Convex booster
pool_id:
  type: "uint256"
  value: "287"

# Two-token arrays for add_liquidity
parameters:
  - type: "uint256[]"
    value:
      - type: "uint256"
        value: "${input_slots.amount_a}"
      - type: "uint256"
        value: "0"
```

### Flash Loans

```yaml
# Use FLASHLOAN_MANAGEMENT type
instruction_type: "FLASHLOAN_MANAGEMENT"

# Reference flash loan aggregator
flash_loan_aggregator:
  type: "address"
  value: "${config.flash_loan_aggregator}"
```

---

## Validation Rules

### Required Fields

**Instructions:**

- `is_debt` - Must be boolean
- `instruction_type` - Must be valid type
- `affected_tokens` - Must be array (can be empty)
- `instruction.label` - Must be string
- `instruction.path` - Must be valid path format
- `instruction.inputs` - Must have all required blueprint inputs

**Blueprints:**

- `protocol` - Must be string
- `inputs` - Must define all referenced parameters
- `actions` - Must have at least one action
- Each action must have `calls` array

### Path Validation

```
../../../blueprints/{protocol}/{action}.yaml:{action_name}
```

- Relative path must resolve to existing file
- Action name must exist in referenced blueprint
- Protocol in path must match blueprint's protocol field

### Type Matching

- Input types must match blueprint definitions
- Return types must match function signatures
- Array element types must be consistent

### Address Format

- Must be 42 characters (0x + 40 hex chars)
- Must be checksummed
- Should include comment with symbol

### No Placeholders

Never use placeholder values:

```yaml
# BAD
value: "0x..."
value: "TODO"
value: "${placeholder}"

# GOOD
value: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
value: "${config.caliber_address}"
```

---

## Quick Reference

### Instruction Template

```yaml
- is_debt: false
  instruction_type: "MANAGEMENT"
  affected_tokens:
    - "0x..." # SYMBOL
  instruction:
    label: "description"
    path: "../../../blueprints/{protocol}/{action}.yaml:{action_name}"
    inputs:
      param:
        type: "address"
        value: "0x..."
```

### Blueprint Template

```yaml
protocol: protocol-name

inputs:
  param:
    type: "address"

actions:
  action_name:
    calls:
      - description: "What this does"
        target: "${inputs.contract}"
        selector: "function(type)"
        parameters:
          - type: "type"
            value: "${inputs.param}"
        return:
          name: "result"
          type: "type"
    input_slots:
      amount:
        type: "uint256"
        description: "Amount to use"
```
