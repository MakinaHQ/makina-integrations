# Blueprint Helper Contracts Reference

This document defines all helper contracts used in blueprints, their functions, and usage patterns.

---

## Table of Contents

1. [Overview](#overview)
2. [Core Helpers](#core-helpers)
3. [Configuration](#configuration)
4. [Usage Patterns](#usage-patterns)
5. [Quick Reference](#quick-reference)

---

## Overview

Helper contracts are pre-deployed utility contracts that provide common operations not available in standard EVM opcodes. They are referenced in blueprints via `${config.*}` template variables and called like any other contract.

| Helper | Purpose | Primary Use Case |
|--------|---------|------------------|
| **Unsigned Math Helper** | Mathematical operations | LP token accounting, multiplications |
| **Caliber Helper** | Tuple extraction | Morpho market params, complex return values |
| **Revertable Caliber Helper** | Conditional execution | Validation checks, position verification |
| **Boolean Helper** | Boolean logic | Complex conditional flows |
| **Key-Value Store** | Persistent state | NFT token IDs, request tracking |

---

## Core Helpers

### Unsigned Math Helper

Provides safe mathematical operations for fixed-point arithmetic.

| Network | Address |
|---------|---------|
| Mainnet | `0x836C9007DbD73fcFC473190304C72b7E39BaBb91` |
| Arbitrum | `0x49a05b9c885086D0BA363281628e48E0aB86dEAf` |

**Config key**: `unsigned_math_helper_address`

**Functions**:

```yaml
# Returns maximum of two values
selector: "max(uint256,uint256)"
return:
  type: "uint256"

# Fixed-point multiplication then division: (a * b) / c
selector: "mulDiv(uint256,uint256,uint256)"
return:
  type: "uint256"
```

**Example usage** (LP accounting):

```yaml
- description: "Calculate LP token value"
  target: "${inputs.unsigned_math_helper_address}"
  selector: "mulDiv(uint256,uint256,uint256)"
  parameters:
    - type: "uint256"
      value: "${returns.lp_balance}"
    - type: "uint256"
      value: "${returns.virtual_price}"
    - type: "uint256"
      value: "1000000000000000000"  # 1e18
  return:
    name: "lp_value"
    type: "uint256"
```

---

### Caliber Helper (Executor Helper)

Provides tuple manipulation and element extraction from encoded return values.

| Network | Address |
|---------|---------|
| Mainnet | `0x6E2ED2f457c41F38556Ab0c2b1185cc9e6563d8D` |

**Config keys**: `caliber_helper_address`, `executor_helper_address`

**Functions**:

```yaml
# Extract element at index from ABI-encoded tuple
selector: "extractElementFromStaticTuple(bytes,uint256)"
parameters:
  - type: "(tuple_signature)"  # Pass tuple as bytes
    value: "${returns.tuple_value}"
  - type: "uint256"
    value: "0"  # Index to extract
return:
  type: "address"  # Type of element at index
```

**Example usage** (extract from tuple):

```yaml
# Step 1: Get tuple return value
- description: "Get market params"
  target: "${inputs.protocol_address}"
  selector: "getParams(bytes32)"
  parameters:
    - type: "bytes32"
      value: "${inputs.id}"
  return:
    name: "params"
    type: "(address,address,address,address,uint256)"

# Step 2: Extract first element (index 0)
- description: "Extract first address from params"
  target: "${inputs.executor_helper}"
  selector: "extractElementFromStaticTuple(bytes,uint256)"
  parameters:
    - type: "(address,address,address,address,uint256)"
      value: "${returns.params}"
    - type: "uint256"
      value: "0"
  return:
    name: "first_address"
    type: "address"

# Step 3: Extract second element (index 1)
- description: "Extract second address from params"
  target: "${inputs.executor_helper}"
  selector: "extractElementFromStaticTuple(bytes,uint256)"
  parameters:
    - type: "(address,address,address,address,uint256)"
      value: "${returns.params}"
    - type: "uint256"
      value: "1"
  return:
    name: "second_address"
    type: "address"
```

---

### Revertable Caliber Helper

Provides conditional execution with revert capabilities for validation.

| Network | Address |
|---------|---------|
| Mainnet (deth) | `0xC6B5888830eB10D19267680b339FeBcD75569B62` |
| Arbitrum | `0x6b09a22087B5D6C7E1051ee9a8AA94eA56C91008` |

**Config key**: `revertable_caliber_helper`

**Functions**:

```yaml
# Equality check
selector: "eq(uint256,uint256)"
return:
  type: "bool"

# Revert if condition is true
selector: "revertIfTrue(bool)"
# No return - reverts or continues

# Revert if condition is false
selector: "revertIfFalse(bool)"
# No return - reverts or continues

# Same as caliber helper
selector: "extractElementFromStaticTuple(bytes,uint256)"
```

**Example usage** (validation):

```yaml
# Check if value is zero
- description: "Check if token ID is zero"
  target: "${inputs.revertable_caliber_helper}"
  selector: "eq(uint256,uint256)"
  parameters:
    - type: "uint256"
      value: "${returns.token_id}"
    - type: "uint256"
      value: "0"
  return:
    name: "is_zero"
    type: "bool"

# Revert if condition is true
- description: "Revert if no position exists"
  target: "${inputs.revertable_caliber_helper}"
  selector: "revertIfTrue(bool)"
  parameters:
    - type: "bool"
      value: "${returns.is_zero}"
```

---

### Boolean Helper

Provides boolean logic operations.

| Network | Address |
|---------|---------|
| Mainnet | `0x00c93e3b09Ca2f544487d4298339765EadCD8353` |

**Config key**: `boolean_helper_address`

**Functions**:

```yaml
# AND operation
selector: "and(bool,bool)"
return:
  type: "bool"

# OR operation
selector: "or(bool,bool)"
return:
  type: "bool"

# NOT operation
selector: "not(bool)"
return:
  type: "bool"
```

---

### Key-Value Store

Provides persistent storage for tracking position state across transactions.

| Network | Address (varies by machine) |
|---------|---------|
| Mainnet (deth) | `0xF5B4dF5E5a446a64c89294fD4a6a1cAA56E77437` |
| Mainnet (dusd) | `0xa81fC382489F9560211AB15aD87f001b98C92E91` |

**Config keys**: `key_value_store_address`, `kv_store_address`

**Functions**:

```yaml
# Get value by key
selector: "get(string)"
parameters:
  - type: "string"
    value: "position_token_id"
return:
  type: "bytes32"

# Set value with key
selector: "set(string,bytes32)"
parameters:
  - type: "string"
    value: "position_token_id"
  - type: "bytes32"
    value: "${returns.token_id}"
# No return
```

**Example usage** (store and retrieve):

```yaml
# Store a value
- description: "Store position token ID in KV store"
  target: "${inputs.kv_store_address}"
  selector: "set(string,bytes32)"
  parameters:
    - type: "string"
      value: "my_position_id"
    - type: "bytes32"
      value: "${returns.minted_token_id}"

# Retrieve a value
- description: "Get position token ID from KV store"
  target: "${inputs.kv_store_address}"
  selector: "get(string)"
  parameters:
    - type: "string"
      value: "my_position_id"
  return:
    name: "stored_token_id"
    type: "bytes32"
```

---

## Configuration

### Machine Configuration (caliber.yaml)

Helpers are defined in machine caliber files:

```yaml
# machines/{machine}/{network}/caliber.yaml
config:
  caliber_address: 0xD1A2d9DF5db842DA2Ee81075Fa441602B2352915
  unsigned_math_helper_address: 0x836C9007DbD73fcFC473190304C72b7E39BaBb91
  caliber_helper_address: 0x6E2ED2f457c41F38556Ab0c2b1185cc9e6563d8D
  revertable_caliber_helper: 0xC6B5888830eB10D19267680b339FeBcD75569B62
  boolean_helper_address: 0x00c93e3b09Ca2f544487d4298339765EadCD8353
  key_value_store_address: 0xF5B4dF5E5a446a64c89294fD4a6a1cAA56E77437
```

### Blueprint Inputs

Reference helpers via inputs in blueprints:

```yaml
inputs:
  unsigned_math_helper_address:
    type: "address"
  executor_helper:
    type: "address"
  revertable_caliber_helper:
    type: "address"
  kv_store_address:
    type: "address"
```

### Instruction Reference

Pass config values to blueprint inputs:

```yaml
instruction:
  inputs:
    unsigned_math_helper_address:
      type: "address"
      value: "${config.unsigned_math_helper_address}"
    executor_helper:
      type: "address"
      value: "${config.caliber_helper_address}"
```

---

## Usage Patterns

### Pattern 1: LP Token Accounting with Math Helper

```yaml
calls:
  # Get LP balance
  - description: "Get LP token balance"
    target: "${inputs.lp_token}"
    selector: "balanceOf(address)"
    parameters:
      - type: "address"
        value: "${inputs.caliber_address}"
    return:
      name: "lp_balance"
      type: "uint256"

  # Get virtual price
  - description: "Get pool virtual price"
    target: "${inputs.pool_address}"
    selector: "get_virtual_price()"
    return:
      name: "virtual_price"
      type: "uint256"

  # Calculate value: (lp_balance * virtual_price) / 1e18
  - description: "Calculate LP value in underlying"
    target: "${inputs.unsigned_math_helper_address}"
    selector: "mulDiv(uint256,uint256,uint256)"
    parameters:
      - type: "uint256"
        value: "${returns.lp_balance}"
      - type: "uint256"
        value: "${returns.virtual_price}"
      - type: "uint256"
        value: "1000000000000000000"
    return:
      name: "underlying_value"
      type: "uint256"
```

### Pattern 2: Tuple Extraction

```yaml
calls:
  # Get position data (returns tuple)
  - description: "Get position"
    target: "${inputs.protocol}"
    selector: "position(bytes32,address)"
    parameters:
      - type: "bytes32"
        value: "${inputs.position_id}"
      - type: "address"
        value: "${inputs.caliber_address}"
    return:
      name: "position"
      type: "(uint256,uint128,uint128)"

  # Extract first field (index 0)
  - description: "Extract first field"
    target: "${inputs.executor_helper}"
    selector: "extractElementFromStaticTuple(bytes,uint256)"
    parameters:
      - type: "(uint256,uint128,uint128)"
        value: "${returns.position}"
      - type: "uint256"
        value: "0"
    return:
      name: "first_field"
      type: "uint256"
```

### Pattern 3: Validation with Revertable Helper

```yaml
calls:
  # Check condition
  - description: "Check if balance is sufficient"
    target: "${inputs.revertable_caliber_helper}"
    selector: "eq(uint256,uint256)"
    parameters:
      - type: "uint256"
        value: "${returns.balance}"
      - type: "uint256"
        value: "0"
    return:
      name: "balance_is_zero"
      type: "bool"

  # Revert if balance is zero
  - description: "Revert if no balance"
    target: "${inputs.revertable_caliber_helper}"
    selector: "revertIfTrue(bool)"
    parameters:
      - type: "bool"
        value: "${returns.balance_is_zero}"
```

### Pattern 4: Persistent State with KV Store

```yaml
calls:
  # Store NFT token ID after mint
  - description: "Store token ID"
    target: "${inputs.kv_store_address}"
    selector: "set(string,bytes32)"
    parameters:
      - type: "string"
        value: "position_token_id"
      - type: "bytes32"
        value: "${returns.minted_token_id}"

  # Later: retrieve for withdrawal
  - description: "Get stored token ID"
    target: "${inputs.kv_store_address}"
    selector: "get(string)"
    parameters:
      - type: "string"
        value: "position_token_id"
    return:
      name: "token_id"
      type: "bytes32"
```

---

## Quick Reference

### Functions Table

| Helper | Function | Signature | Return |
|--------|----------|-----------|--------|
| Math | max | `max(uint256,uint256)` | `uint256` |
| Math | mulDiv | `mulDiv(uint256,uint256,uint256)` | `uint256` |
| Caliber | extractElement | `extractElementFromStaticTuple(bytes,uint256)` | varies |
| Revertable | eq | `eq(uint256,uint256)` | `bool` |
| Revertable | revertIfTrue | `revertIfTrue(bool)` | - |
| Revertable | revertIfFalse | `revertIfFalse(bool)` | - |
| Boolean | and | `and(bool,bool)` | `bool` |
| Boolean | or | `or(bool,bool)` | `bool` |
| Boolean | not | `not(bool)` | `bool` |
| KV Store | get | `get(string)` | `bytes32` |
| KV Store | set | `set(string,bytes32)` | - |

### When to Use Each Helper

| Scenario | Helper to Use |
|----------|---------------|
| Calculate LP token values | Unsigned Math Helper |
| Extract fields from protocol return values | Caliber Helper |
| Validate state before proceeding | Revertable Caliber Helper |
| Complex boolean conditions | Boolean Helper |
| Track positions across transactions | Key-Value Store |
