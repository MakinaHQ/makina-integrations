# Rootfiles Syntax Reference

This document defines all conventions, schemas, and best practices for instruction and blueprint files in the rootfiles project.

---

## Table of Contents

1. [Overview](#overview)
2. [File Organization](#file-organization)
3. [Instruction Files](#instruction-files)
4. [Blueprint Files](#blueprint-files)
5. [Template Variables](#template-variables)
6. [Data Types](#data-types)
7. [Naming Conventions](#naming-conventions)
8. [Common Patterns](#common-patterns)
9. [Protocol-Specific Patterns](#protocol-specific-patterns)
10. [Validation Rules](#validation-rules)

---

## Overview

The rootfiles system uses two primary file types:

| File Type        | Purpose                                              | Location                                     |
| ---------------- | ---------------------------------------------------- | -------------------------------------------- |
| **Instructions** | Define pool-specific operations with concrete values | `machines/{machine}/{network}/instructions/` |
| **Blueprints**   | Define reusable, generic action templates            | `blueprints/{protocol}/`                     |

**Relationship**: Instructions reference blueprint actions and provide concrete parameter values. Multiple instructions can reuse the same blueprint with different parameters.

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
└── machines/
    └── {machine}/
        └── {network}/
            ├── instructions/
            │   ├── aavev3-borrow-usdc.yaml
            │   ├── convex-curve-weth-reth.yaml
            │   └── {protocol}-{identifier}.yaml
            └── rootfiles/
                └── {compiled}.toml
```

### Blueprint Protocols

Available protocols (35 total):

```
aave            aave-umbrella     across-v2         aerodrome-cl
auto            convex-curve      convex-curve-metapool  convex-fx
curve           curve-llamalend   dolomite          euler-earn
euler-lend      fluid             fluid-lite        fxsave
lagoon          makina            merkl             morpho
morpho-pendle-pt-loop  pendle-pt  shroomy           silo
stakedao-curve  stakedao-yearn    sturdy-v2         summerfi
superform       tokemak           tydro             velodrome-cl
```

---

## Instruction Files

### File Naming

Pattern: `{protocol}-{pool-identifier}.yaml`

Examples:

- `aavev3-borrow-usdc.yaml` - Protocol-action-token
- `convex-curve-weth-reth.yaml` - Protocol-subprotocol-token-pair
- `morpho-market-wsteth-usdc-collateral.yaml` - Protocol-market-tokens-role
- `across-v2-usdc.yaml` - Protocol-version-token

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

### Path Format

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

### Config Variables

Common configuration variables:

```yaml
${config.caliber_address}           # Main contract address
${config.caliber_helper_address}    # Helper contract
${config.morpho_address}            # Morpho protocol address
${config.unsigned_math_helper_address}  # Math utilities
${config.aave_umbrella_batch_helper}    # Aave helper
${config.flash_loan_aggregator}     # Flash loan provider
${config.swap_module}               # DEX aggregator
${config.aavev3_core_instance}      # Aave instance
${config.kv_store_address}          # Key-value store
${config.safe_address}              # Safe/multisig
${config.revertable_caliber_helper} # Revertable operations
```

### Builtins

```yaml
${builtins.UINT256_MAX}   # Maximum uint256 (2^256 - 1)
${builtins.UINT128_MAX}   # Maximum uint128 (2^128 - 1)
${builtins.UINT256_1}     # Value of 1
```

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
| Instruction files | protocol-identifier | `convex-curve-weth-reth.yaml`   |

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
