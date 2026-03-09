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

Helper contracts are pre-deployed utility contracts (from [makina-periphery/weiroll-helpers](https://github.com/MakinaHQ/makina-periphery/tree/main/src/weiroll-helpers)) that provide common operations not available in standard EVM opcodes. They are referenced in blueprints via `${config.*}` or `${constants.*}` template variables and called like any other contract.

| Helper | Source Contract | Purpose | Primary Use Case |
|--------|----------------|---------|------------------|
| **Context Helper** | `ContextHelper.sol` | Execution context | Get caliber address, block timestamp, balances |
| **Math Helper** | `MathHelper.sol` | Unsigned math operations | LP accounting, mulDiv, comparisons, scaling |
| **Signed Math Helper** | `SignedMathHelper.sol` | Signed math operations | Signed arithmetic for int256 values |
| **Cast Helper** | `CastHelper.sol` | Type conversions | int256/uint256 casting, bytes to string |
| **Bytes32 Helper** | `Bytes32Helper.sol` | Bytes32 operations | Equality, ternary, tuple/array indexing |
| **Boolean Helper** | `BooleanHelper.sol` | Boolean logic | Conditional flows, revert guards |
| **Key-Value Store** | `KeyValueStore.sol` | Persistent state | NFT token IDs, unwinding timestamps |
| **Caliber Helper** | *(custom)* | Tuple extraction | Morpho market params, complex return values |
| **Revertable Caliber Helper** | *(custom)* | Conditional execution + tuples | Validation checks, position verification |

---

## Core Helpers

### Context Helper

Provides execution context information (caller address, block data).

| Network | Address |
|---------|---------|
| Mainnet | `0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE` |

**Typically used as**: Blueprint constant (same address across all machines)

**Functions**:

```yaml
# Get the caller (caliber) address
selector: "msgSender()"
return:
  type: "address"

# Get current block timestamp
selector: "blockTimestamp()"
return:
  type: "uint256"

# Get current block number
selector: "blockNumber()"
return:
  type: "uint256"

# Get native token balance of an account
selector: "balance(address)"
return:
  type: "uint256"
```

**Example usage** (get caliber address):

```yaml
- description: "Get caliber's address"
  target: ${constants.context_helper_address}
  selector: "msgSender()"
  parameters: []
  return:
    name: "caliber_address"
    type: "address"
```

**Note**: The context helper is typically defined as a blueprint `constant` rather than an `input`, since its address is the same across all machines.

---

### Math Helper (MathHelper.sol)

Provides safe unsigned mathematical operations for fixed-point arithmetic, comparisons, and decimal scaling.

| Network | Address |
|---------|---------|
| Mainnet | `0x836C9007DbD73fcFC473190304C72b7E39BaBb91` |
| Mainnet (newer) | `0x3D623B199E290358416415eA7e05B635E442e3c0` |
| Arbitrum | `0x49a05b9c885086D0BA363281628e48E0aB86dEAf` |

**Config keys**: `unsigned_math_helper_address`, `math_helper`, `math_helper_address`

**Functions — Arithmetic**:

```yaml
# Addition: a + b
selector: "add(uint256,uint256)"
return: { type: "uint256" }

# Subtraction: a - b
selector: "sub(uint256,uint256)"
return: { type: "uint256" }

# Multiplication: a * b
selector: "mul(uint256,uint256)"
return: { type: "uint256" }

# Division: a / b
selector: "div(uint256,uint256)"
return: { type: "uint256" }

# Ceiling division: ceil(a / b)
selector: "ceilDiv(uint256,uint256)"
return: { type: "uint256" }

# Fixed-point multiplication then division: (x * y) / denominator (rounds down)
selector: "mulDiv(uint256,uint256,uint256)"
return: { type: "uint256" }

# Ceiling mulDiv: ceil((x * y) / denominator)
selector: "ceilMulDiv(uint256,uint256,uint256)"
return: { type: "uint256" }

# Square root: sqrt(a)
selector: "sqrt(uint256)"
return: { type: "uint256" }

# Average: (a + b) / 2 (no overflow)
selector: "average(uint256,uint256)"
return: { type: "uint256" }
```

**Functions — Comparisons**:

```yaml
# Equality: a == b
selector: "eq(uint256,uint256)"
return: { type: "bool" }

# Less than: a < b
selector: "lt(uint256,uint256)"
return: { type: "bool" }

# Less than or equal: a <= b
selector: "lte(uint256,uint256)"
return: { type: "bool" }

# Greater than: a > b
selector: "gt(uint256,uint256)"
return: { type: "bool" }

# Greater than or equal: a >= b
selector: "gte(uint256,uint256)"
return: { type: "bool" }
```

**Functions — Selection & Constants**:

```yaml
# Maximum of two values
selector: "max(uint256,uint256)"
return: { type: "uint256" }

# Minimum of two values
selector: "min(uint256,uint256)"
return: { type: "uint256" }

# Ternary: condition ? a : b
selector: "ternary(bool,uint256,uint256)"
return: { type: "uint256" }

# Max uint128 value
selector: "uint128Max()"
return: { type: "uint128" }

# Max uint256 value
selector: "uint256Max()"
return: { type: "uint256" }
```

**Functions — Decimal Scaling**:

```yaml
# Scale amount between different decimal precisions
# e.g., USDC (6 dec) to 18 dec: scaleAmount(1000000, 6, 18) = 1000000000000000000
selector: "scaleAmount(uint256,uint8,uint8)"
return: { type: "uint256" }
```

**Functions — Logarithms**:

```yaml
selector: "log2(uint256)"
return: { type: "uint256" }

selector: "log10(uint256)"
return: { type: "uint256" }

selector: "log256(uint256)"
return: { type: "uint256" }
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

**Example usage** (decimal scaling):

```yaml
- description: "Scale USDC amount (6 dec) to 18 decimals"
  target: "${inputs.math_helper_address}"
  selector: "scaleAmount(uint256,uint8,uint8)"
  parameters:
    - type: "uint256"
      value: "${returns.usdc_balance}"
    - type: "uint8"
      value: "6"
    - type: "uint8"
      value: "18"
  return:
    name: "scaled_amount"
    type: "uint256"
```

---

### Signed Math Helper (SignedMathHelper.sol)

Provides safe signed integer (int256) arithmetic. Use when dealing with protocol functions that return signed values.

**Functions**:

```yaml
# Addition: a + b
selector: "add(int256,int256)"
return: { type: "int256" }

# Subtraction: a - b
selector: "sub(int256,int256)"
return: { type: "int256" }

# Multiplication: a * b
selector: "mul(int256,int256)"
return: { type: "int256" }

# Division: a / b
selector: "div(int256,int256)"
return: { type: "int256" }

# Maximum of two signed values
selector: "max(int256,int256)"
return: { type: "int256" }

# Minimum of two signed values
selector: "min(int256,int256)"
return: { type: "int256" }

# Average: (a + b) / 2
selector: "average(int256,int256)"
return: { type: "int256" }

# Absolute value: |a|
selector: "abs(int256)"
return: { type: "uint256" }
```

---

### Cast Helper (CastHelper.sol)

Provides type conversions between int256/uint256 and bytes/string.

**Functions**:

```yaml
# Convert int256 to uint256 (reverts if negative)
selector: "int256ToUint256(int256)"
return: { type: "uint256" }

# Convert uint256 to int256 (reverts if > max int256)
selector: "uint256ToInt256(uint256)"
return: { type: "int256" }

# Cast bytes to string
selector: "bytesToString(bytes)"
return: { type: "string" }
```

**Example usage** (convert signed return value to unsigned):

```yaml
- description: "Get signed balance from protocol"
  target: "${inputs.protocol_address}"
  selector: "getBalance(address)"
  parameters:
    - type: "address"
      value: "${returns.caliber_address}"
  return:
    name: "signed_balance"
    type: "int256"

- description: "Convert to unsigned for accounting"
  target: "${constants.cast_helper_address}"
  selector: "int256ToUint256(int256)"
  parameters:
    - type: "int256"
      value: "${returns.signed_balance}"
  return:
    name: "balance"
    type: "uint256"
```

---

### Bytes32 Helper (Bytes32Helper.sol)

Provides bytes32 operations including equality, ternary selection, and indexing into tuples/arrays.

**Functions**:

```yaml
# Equality: a == b
selector: "eq(bytes32,bytes32)"
return: { type: "bool" }

# Ternary: condition ? a : b
selector: "ternary(bool,bytes32,bytes32)"
return: { type: "bytes32" }

# Create array from two values
selector: "arrayOf(bytes32,bytes32)"
return: { type: "bytes32[]" }

# Extract 32-byte word at index from a bytes-encoded tuple
# Useful for decoding packed return values
selector: "getTupleWord(bytes,uint256)"
return: { type: "bytes32" }

# Extract 32-byte word at index from a dynamic array
selector: "getArrayWord(bytes32[],uint256)"
return: { type: "bytes32" }
```

**Example usage** (conditional bytes32 selection):

```yaml
- description: "Select address based on condition"
  target: "${constants.bytes32_helper_address}"
  selector: "ternary(bool,bytes32,bytes32)"
  parameters:
    - type: "bool"
      value: "${returns.use_alternative}"
    - type: "bytes32"
      value: "${inputs.primary_address}"
    - type: "bytes32"
      value: "${inputs.alternative_address}"
  return:
    name: "selected_address"
    type: "bytes32"
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

### Boolean Helper (BooleanHelper.sol)

Provides boolean logic operations and conditional revert guards.

| Network | Address |
|---------|---------|
| Mainnet | `0x00c93e3b09Ca2f544487d4298339765EadCD8353` |

**Config key**: `boolean_helper_address`

**Functions**:

```yaml
# Logical NOT
selector: "not(bool)"
return: { type: "bool" }

# Logical AND
selector: "and(bool,bool)"
return: { type: "bool" }

# Logical OR
selector: "or(bool,bool)"
return: { type: "bool" }

# Revert if condition is true (guard: "must be false")
selector: "revertIfTrue(bool)"
# No return - reverts with ConditionIsTrue() or continues

# Revert if condition is false (guard: "must be true")
selector: "revertIfFalse(bool)"
# No return - reverts with ConditionIsFalse() or continues
```

**Note**: `revertIfTrue`/`revertIfFalse` are part of `BooleanHelper.sol`. They are also available on the Revertable Caliber Helper (custom contract). Use whichever is already referenced in your blueprint.

---

### Key-Value Store (KeyValueStore.sol)

Provides persistent storage for tracking position state across transactions. Each KV store is owned by a specific caliber and only that caliber can write to it.

| Network | Address (varies by machine) |
|---------|---------|
| Mainnet (deth) | `0xF5B4dF5E5a446a64c89294fD4a6a1cAA56E77437` |
| Mainnet (dusd) | `0xa81fC382489F9560211AB15aD87f001b98C92E91` |

**Config keys**: `key_value_store_address`, `kv_store_address`

**Functions**:

```yaml
# Get value by string key
selector: "get(string)"
parameters:
  - type: "string"
    value: "position_token_id"
return:
  type: "bytes32"

# Set value with string key
selector: "set(string,bytes32)"
parameters:
  - type: "string"
    value: "position_token_id"
  - type: "bytes32"
    value: "${returns.token_id}"
# No return

# Get value by bytes32 key (preferred for parameterized instructions)
selector: "get(bytes32)"
parameters:
  - type: "bytes32"
    value: "${inputs.kv_storage_key}"
return:
  type: "uint256"

# Set value with bytes32 key (preferred for parameterized instructions)
selector: "set(bytes32,bytes32)"
parameters:
  - type: "bytes32"
    value: "${inputs.kv_storage_key}"
  - type: "uint256"
    value: "${returns.some_value}"
# No return

# Delete/reset a key (sets value to zero)
selector: "reset(bytes32)"
parameters:
  - type: "bytes32"
    value: "${inputs.kv_storage_key}"
# No return
```

**Choosing string vs bytes32 keys**: Use `bytes32` keys when the key needs to be parameterized via position variables (e.g., `${inputs.kv_storage_key}` from `${position.kv_storage_key}`). Use `string` keys for simple, hardcoded key names. The `bytes32` variant is preferred for general instructions because the key can be different per position.

**KV storage key convention**: Generate keys using `keccak256("makina.{network}.{protocol}.{identifier}")`. Document the source string in a comment in the caliber.yaml vars.

**Example usage** (store and retrieve with string keys):

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

**Example usage** (store and retrieve with bytes32 keys — preferred for parameterized instructions):

```yaml
# Store a timestamp
- description: "Store unwinding timestamp in KV store"
  target: "${constants.kv_store_address}"
  selector: "set(bytes32,bytes32)"
  parameters:
    - type: "bytes32"
      value: "${inputs.kv_storage_key}"
    - type: "uint256"
      value: "${returns.unwinding_timestamp}"

# Retrieve a timestamp
- description: "Get unwinding timestamp from KV store"
  target: "${constants.kv_store_address}"
  selector: "get(bytes32)"
  parameters:
    - type: "bytes32"
      value: "${inputs.kv_storage_key}"
  return:
    name: "unwinding_timestamp"
    type: "uint256"
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

**String keys** (simple, hardcoded):
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

**Bytes32 keys** (preferred for parameterized instructions with position vars):
```yaml
calls:
  # Store unwinding timestamp (key from position vars)
  - description: "Store unwinding timestamp"
    target: "${constants.kv_store_address}"
    selector: "set(bytes32,bytes32)"
    parameters:
      - type: "bytes32"
        value: "${inputs.kv_storage_key}"
      - type: "uint256"
        value: "${returns.unwinding_timestamp}"

  # Check for existing unwinding + guard
  - description: "Get existing unwinding timestamp"
    target: "${constants.kv_store_address}"
    selector: "get(bytes32)"
    parameters:
      - type: "bytes32"
        value: "${inputs.kv_storage_key}"
    return:
      name: "existing_timestamp"
      type: "uint256"

  - description: "Check if no existing unwinding (timestamp == 0)"
    target: "${constants.math_helper_address}"
    selector: "eq(uint256,uint256)"
    parameters:
      - type: "uint256"
        value: "${returns.existing_timestamp}"
      - type: "uint256"
        value: "0"
    return:
      name: "no_existing"
      type: "bool"

  - description: "Revert if already unwinding"
    target: "${constants.boolean_helper_address}"
    selector: "revertIfFalse(bool)"
    parameters:
      - type: "bool"
        value: "${returns.no_existing}"
```

---

## Quick Reference

### Functions Table

| Helper | Function | Signature | Return |
|--------|----------|-----------|--------|
| **Context** | msgSender | `msgSender()` | `address` |
| Context | blockTimestamp | `blockTimestamp()` | `uint256` |
| Context | blockNumber | `blockNumber()` | `uint256` |
| Context | balance | `balance(address)` | `uint256` |
| **Math** | add | `add(uint256,uint256)` | `uint256` |
| Math | sub | `sub(uint256,uint256)` | `uint256` |
| Math | mul | `mul(uint256,uint256)` | `uint256` |
| Math | div | `div(uint256,uint256)` | `uint256` |
| Math | ceilDiv | `ceilDiv(uint256,uint256)` | `uint256` |
| Math | mulDiv | `mulDiv(uint256,uint256,uint256)` | `uint256` |
| Math | ceilMulDiv | `ceilMulDiv(uint256,uint256,uint256)` | `uint256` |
| Math | sqrt | `sqrt(uint256)` | `uint256` |
| Math | average | `average(uint256,uint256)` | `uint256` |
| Math | max | `max(uint256,uint256)` | `uint256` |
| Math | min | `min(uint256,uint256)` | `uint256` |
| Math | ternary | `ternary(bool,uint256,uint256)` | `uint256` |
| Math | eq | `eq(uint256,uint256)` | `bool` |
| Math | lt | `lt(uint256,uint256)` | `bool` |
| Math | lte | `lte(uint256,uint256)` | `bool` |
| Math | gt | `gt(uint256,uint256)` | `bool` |
| Math | gte | `gte(uint256,uint256)` | `bool` |
| Math | scaleAmount | `scaleAmount(uint256,uint8,uint8)` | `uint256` |
| Math | uint128Max | `uint128Max()` | `uint128` |
| Math | uint256Max | `uint256Max()` | `uint256` |
| **Signed Math** | add | `add(int256,int256)` | `int256` |
| Signed Math | sub | `sub(int256,int256)` | `int256` |
| Signed Math | mul | `mul(int256,int256)` | `int256` |
| Signed Math | div | `div(int256,int256)` | `int256` |
| Signed Math | max | `max(int256,int256)` | `int256` |
| Signed Math | min | `min(int256,int256)` | `int256` |
| Signed Math | average | `average(int256,int256)` | `int256` |
| Signed Math | abs | `abs(int256)` | `uint256` |
| **Cast** | int256ToUint256 | `int256ToUint256(int256)` | `uint256` |
| Cast | uint256ToInt256 | `uint256ToInt256(uint256)` | `int256` |
| Cast | bytesToString | `bytesToString(bytes)` | `string` |
| **Bytes32** | eq | `eq(bytes32,bytes32)` | `bool` |
| Bytes32 | ternary | `ternary(bool,bytes32,bytes32)` | `bytes32` |
| Bytes32 | arrayOf | `arrayOf(bytes32,bytes32)` | `bytes32[]` |
| Bytes32 | getTupleWord | `getTupleWord(bytes,uint256)` | `bytes32` |
| Bytes32 | getArrayWord | `getArrayWord(bytes32[],uint256)` | `bytes32` |
| **Boolean** | not | `not(bool)` | `bool` |
| Boolean | and | `and(bool,bool)` | `bool` |
| Boolean | or | `or(bool,bool)` | `bool` |
| Boolean | revertIfTrue | `revertIfTrue(bool)` | - |
| Boolean | revertIfFalse | `revertIfFalse(bool)` | - |
| **Caliber** | extractElement | `extractElementFromStaticTuple(bytes,uint256)` | varies |
| **Revertable** | eq | `eq(uint256,uint256)` | `bool` |
| Revertable | revertIfTrue | `revertIfTrue(bool)` | - |
| Revertable | revertIfFalse | `revertIfFalse(bool)` | - |
| Revertable | extractElement | `extractElementFromStaticTuple(bytes,uint256)` | varies |
| **KV Store** | get (string) | `get(string)` | `bytes32` |
| KV Store | set (string) | `set(string,bytes32)` | - |
| KV Store | get (bytes32) | `get(bytes32)` | `uint256` |
| KV Store | set (bytes32) | `set(bytes32,bytes32)` | - |
| KV Store | reset | `reset(bytes32)` | - |

### When to Use Each Helper

| Scenario | Helper to Use |
|----------|---------------|
| Calculate LP token values, mulDiv, scaling | Math Helper |
| Compare uint256 values (eq, lt, gt, etc.) | Math Helper |
| Scale between token decimals (6→18, etc.) | Math Helper (`scaleAmount`) |
| Conditional uint256 selection | Math Helper (`ternary`) |
| Signed integer arithmetic (int256) | Signed Math Helper |
| Convert between int256 and uint256 | Cast Helper |
| Compare bytes32 values | Bytes32 Helper |
| Conditional bytes32 selection | Bytes32 Helper (`ternary`) |
| Index into tuples/arrays by position | Bytes32 Helper (`getTupleWord`/`getArrayWord`) |
| Extract fields from protocol return values | Caliber Helper (`extractElementFromStaticTuple`) |
| Validate state before proceeding | Boolean Helper or Revertable Caliber Helper |
| Complex boolean conditions | Boolean Helper |
| Track positions across transactions | Key-Value Store |
| Get caliber address at runtime | Context Helper (`msgSender`) |
| Get block timestamp for time logic | Context Helper (`blockTimestamp`) |
