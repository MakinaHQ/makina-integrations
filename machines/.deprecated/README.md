# Deprecated machines

Machines here are retained for historical reference only. They are **out of scope for
all CI**: the release workflow does not transpile them, the PR gate does not validate
them, and `rootfiles-guard` does not police their rootfiles.

A machine lands here when it is no longer operated. Most often its `caliber.yaml` no
longer builds — typically because a shared blueprint gained a required input that the
machine's instructions were never updated to supply. `stusd` and `popbtc` are the
exception: both still transpile cleanly, but the funds are retired and their source has
drifted ahead of the last committed rootfile, so leaving them in scope would make every
release regenerate rootfiles for dead funds.

| Machine  | Deprecated | Reason                                                                                                                                                                                     |
| -------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ctfeth` | 2026-07-27 | Last touched 2025-10-06. `ctfeth/mainnet` fails to transpile: `blueprints/aave/borrow.yaml` requires `aave_pool_instance`, which its instructions do not supply.                           |
| `mteth`  | 2026-07-27 | Last touched 2025-10-29 (mainnet 2026-01-16). All four networks fail to transpile; `mteth/arbitrum` is missing `stakedao_accountant_address` for `blueprints/stakedao-curve/harvest.yaml`. |
| `stusd`  | 2026-07-27 | Source last changed 2025-08-15, newest rootfile `20250805-morpho-vault.toml`. Still transpiles cleanly, but the fund is retired and source has drifted past the committed rootfile.        |
| `popbtc` | 2026-07-27 | Source last changed 2025-08-19, newest rootfile `20250819-empty.toml`. Still transpiles cleanly, but the fund is retired and source has drifted past the committed rootfile.               |

To bring a machine back, move it out of this directory and fix its `caliber.yaml` until
it transpiles — CI will pick it up automatically.
