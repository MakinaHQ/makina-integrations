# Morpho Vault V2 Curation Blueprints

These blueprints cover the non-owner Morpho Vault V2 curation surface from
Linear `DIA-502`. The files are partitioned by the authority required to use
the action:

- `curator.yaml`: Curator timelock lifecycle helpers, timelocked target calls,
  and Curator/Sentinel instant cap decreases.
- `allocator.yaml`: instant Allocator actions.
- `sentinel.yaml`: instant Sentinel de-risking actions.
- `permissionless.yaml`: calls any address may execute.

Owner actions are intentionally not included: `setOwner`, `setCurator`,
`setIsSentinel`, `setName`, and `setSymbol`.

## Timelocked Curator Flow

Most Curator setters are timelocked. The blueprint DSL can encode the call it is
currently making, but it does not have a helper for `abi.encodeCall(...)` of a
different function. For that reason the submit/revoke helpers take pre-encoded
calldata:

| Step | Action                                        | Caller                   | Notes                                                            |
| ---- | --------------------------------------------- | ------------------------ | ---------------------------------------------------------------- |
| 1    | `submit_curator_call`                         | Curator                  | `call_data` is the exact ABI calldata for the target setter.     |
| 2    | matching `execute_*` action                   | Any address after expiry | Calls the target setter directly and consumes the pending entry. |
| 3    | `revoke_curator_call` / `revoke_pending_call` | Curator or Sentinel      | Cancels the same `call_data` before execution.                   |

Instruction wrappers should define one path per target action and keep the
off-chain params encoder in lockstep with the target selector and slot order.
That mirrors the `uniswap-x-filler` pattern where dynamic bytes are supplied by
the service.

The operator-facing app is responsible for ABI encoding each target call into
`call_data` before invoking `submit_curator_call` or `revoke_curator_call`.
Blueprints intentionally treat that value as opaque `bytes`.

## Curator Target Calls

The `execute_*` naming means "execute the underlying timelocked call after it
has been submitted and matured". These actions are not submit wrappers.

| Action                                  | Target selector                              | Slots                     |
| --------------------------------------- | -------------------------------------------- | ------------------------- |
| `execute_add_adapter`                   | `addAdapter(address)`                        | `adapter`                 |
| `execute_remove_adapter`                | `removeAdapter(address)`                     | `adapter`                 |
| `execute_set_adapter_registry`          | `setAdapterRegistry(address)`                | `adapter_registry`        |
| `execute_set_is_allocator`              | `setIsAllocator(address,bool)`               | `account`, `is_allocator` |
| `execute_set_receive_shares_gate`       | `setReceiveSharesGate(address)`              | `gate`                    |
| `execute_set_send_shares_gate`          | `setSendSharesGate(address)`                 | `gate`                    |
| `execute_set_receive_assets_gate`       | `setReceiveAssetsGate(address)`              | `gate`                    |
| `execute_set_send_assets_gate`          | `setSendAssetsGate(address)`                 | `gate`                    |
| `execute_increase_absolute_cap`         | `increaseAbsoluteCap(bytes,uint256)`         | `id_data`, `absolute_cap` |
| `execute_increase_relative_cap`         | `increaseRelativeCap(bytes,uint256)`         | `id_data`, `relative_cap` |
| `execute_set_performance_fee`           | `setPerformanceFee(uint256)`                 | `performance_fee`         |
| `execute_set_management_fee`            | `setManagementFee(uint256)`                  | `management_fee`          |
| `execute_set_performance_fee_recipient` | `setPerformanceFeeRecipient(address)`        | `recipient`               |
| `execute_set_management_fee_recipient`  | `setManagementFeeRecipient(address)`         | `recipient`               |
| `execute_increase_timelock`             | `increaseTimelock(bytes4,uint256)`           | `selector`, `duration`    |
| `execute_decrease_timelock`             | `decreaseTimelock(bytes4,uint256)`           | `selector`, `duration`    |
| `execute_abdicate`                      | `abdicate(bytes4)`                           | `selector`                |
| `execute_set_force_deallocate_penalty`  | `setForceDeallocatePenalty(address,uint256)` | `adapter`, `penalty`      |

Instant cap decreases are provided in both `curator.yaml` and `sentinel.yaml`
because both roles may de-risk.
