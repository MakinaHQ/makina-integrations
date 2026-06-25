# Morpho Vault V2 Curation Blueprints

These blueprints cover the non-owner Morpho Vault V2 curation surface from
Linear `DIA-502`. The files are partitioned by the authority required to use
the action:

- `curator.yaml`: Curator timelock lifecycle helpers, timelocked target calls,
  matured timelock execution calls, and Curator instant cap decreases.
- `allocator.yaml`: instant Allocator actions.
- `sentinel.yaml`: Sentinel revoke and instant de-risking actions.
- `permissionless.yaml`: calls any address may execute.

Owner actions are intentionally not included: `setOwner`, `setCurator`,
`setIsSentinel`, `setName`, and `setSymbol`.

## Encoder Model

Every operator-facing action uses typed inputs. Raw `bytes` values required by
Vault V2 are produced on-chain by `VaultV2CalldataEncoder` and passed through
Weiroll return values.

There are two helper patterns:

| Flow                               | Blueprint pattern                                                                                    |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Submit/revoke timelocked calls     | Encode full target calldata, then call `submit(bytes)` or `revoke(bytes)`.                           |
| Execute/direct bytes-bearing calls | Encode only the argument payload (`idData` or adapter `data`), then call the real Vault V2 function. |

Vault V2 execution is not `execute(bytes)`: once a timelock matures, the caller
executes by calling the original Vault V2 function with the same arguments that
were submitted.

## Typed Payload Coverage

Cap actions are split by the supported Vault V2 allocation id schema:

- `*_this`: `abi.encode("this", adapter)`
- `*_collateral_token`: `abi.encode("collateralToken", collateralToken)`
- `*_morpho_market_v1_adapter_v2`: `abi.encode("this/marketParams", adapter, marketParams)`

Adapter data actions are split by adapter data schema:

- `*_morpho_vault_v1_adapter`: empty adapter data (`hex""`)
- `*_morpho_market_v1_adapter_v2`: `abi.encode(MarketParams)`

The helper is intentionally scoped to Vault V2-level curation. The separate
internal timelock on `MorphoMarketV1AdapterV2` is out of scope for these
blueprints.

## Instructions

The instruction wrappers require a `vault_v2_calldata_encoder` config value.
The `morpho-curator` mainnet machine config points at the deployed helper.

Instruction wrappers that require `bytes4` selector inputs are commented out
until the production crate supports them. This currently affects
selector-level timelock settings and abdication.
