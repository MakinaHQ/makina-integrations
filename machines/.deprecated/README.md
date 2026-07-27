# Deprecated machines

Machines here are retained for historical reference only. They are **out of scope for
all CI**: the release workflow does not transpile them, the PR gate does not validate
them, and `rootfiles-guard` does not police their rootfiles.

A machine lands here when it is no longer operated and its `caliber.yaml` no longer
builds — typically because a shared blueprint gained a required input that the machine's
instructions were never updated to supply.

| Machine  | Deprecated | Reason                                                                                                                                                                                     |
| -------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ctfeth` | 2026-07-27 | Last touched 2025-10-06. `ctfeth/mainnet` fails to transpile: `blueprints/aave/borrow.yaml` requires `aave_pool_instance`, which its instructions do not supply.                           |
| `mteth`  | 2026-07-27 | Last touched 2025-10-29 (mainnet 2026-01-16). All four networks fail to transpile; `mteth/arbitrum` is missing `stakedao_accountant_address` for `blueprints/stakedao-curve/harvest.yaml`. |

To bring a machine back, move it out of this directory and fix its `caliber.yaml` until
it transpiles — CI will pick it up automatically.
