# Blueprint System

Blueprints are YAML templates that define reusable instruction logic. The transpiler converts them into rootfile instructions.

## Directory Structure

```
rootfiles/
├── blueprints/
│   ├── aave/
│   │   ├── deposit.yaml
│   │   ├── withdraw.yaml
│   │   └── account.yaml
│   ├── convex/
│   └── morpho/
├── instructions/
|   ├── morpho/
|       └── morpho-vault-generic.yaml
└── machines/
    └── mteth/
        └── mainnet/
            ├── instructions/     # Machine specific (non generic) instructions
            └── rootfiles/        # Generated TOML
```

## Blueprint Structure

```yaml
# blueprints/aave/deposit.yaml
protocol: "aavev3"

inputs:
  aave_pool_instance:
    type: "address"
  on_behalf_of:
    type: "address"
  asset_address:
    type: "address"

actions:
  add_collateral:
    calls:
      - description: "Approve Aave pool"
        target: ${inputs.asset_address}
        selector: "approve(address,uint256)"
        parameters:
          - type: "address"
            value: ${inputs.aave_pool_instance}
          - type: "uint256"
            value: ${input_slots.amount_to_deposit}
      - description: "Supply to Aave"
        target: ${inputs.aave_pool_instance}
        selector: "supply(address,uint256,address,uint16)"
        parameters:
          - type: "address"
            value: ${inputs.asset_address}
          - type: "uint256"
            value: ${input_slots.amount_to_deposit}
          - type: "address"
            value: ${inputs.on_behalf_of}
          - type: "uint256"
            value: "0"
    input_slots:
      amount_to_deposit:
        type: "uint256"
        description: "Amount to deposit"
```

## Instruction Definition

```yaml
# instructions/aavev3-supply-weth.yaml
- name: add_collateral_weth
  is_debt: false
  instruction_type: "MANAGEMENT"
  affected_tokens:
    - "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2" # WETH
  instruction:
    label: "weth"
    path: "../../../blueprints/aave/deposit.yaml:add_collateral"
    inputs:
      on_behalf_of:
        type: "address"
        value: ${config.caliber_address}
      asset_address:
        type: "address"
        value: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
      aave_pool_instance:
        type: "address"
        value: "${config.aavev3_core_instance}"
```

## Blueprint to CLI Mapping

| Blueprint            | CLI Argument             |
| -------------------- | ------------------------ |
| `protocol:`          | `--protocol`             |
| action name          | `--action`               |
| `instruction.label:` | `--token`                |
| `input_slots:`       | `--inputs` (ABI-encoded) |

## Instruction Types

| Type                 | Value | Description                          |
| -------------------- | ----- | ------------------------------------ |
| MANAGEMENT           | 0     | Position changes (deposit, withdraw) |
| ACCOUNTING           | 1     | Balance updates                      |
| HARVEST              | 2     | Yield collection                     |
| FLASHLOAN_MANAGEMENT | 3     | Flashloan operations                 |

## Compiling Instructions

```bash
transpiler -- -i <caliber.yaml> -o <output.toml>
```

Example:

```bash
transpiler -- \
  -i /path/to/machines/deth/mainnet/caliber-test.yaml \
  -o /tmp/makina-test-output.toml
```

**Never send `-o`/`--output-file` into `machines/*/*/rootfiles/`.** Rootfiles are release-generated build artifacts now; `rootfiles-guard` rejects any PR that adds or modifies a file under a `rootfiles/` directory. Always write output outside the repo (`/tmp/...`).

## Notes

You can have position variables in positon definitions (to use in generic instructions etc)
