# Uniswap X filler instruction templates

Every template in this directory is governed by the **Uniswap-X Filler ↔ Machine Contract**
(normative). They are isolated here rather than sitting loose in `instructions-x/` because
their action names, slot layout, labels and `affected_tokens` are a runtime ABI that a
separate filler process is configured against — changing one silently breaks fills on a live
chain. Isolation makes that surface enumerable, and
`tests/test_uniswap_x_filler_contract.py` asserts nothing invoking
`blueprints-x/uniswap-x/` exists outside this directory.

If you are adding an ordinary makina-x position, you almost certainly want the flat
`instructions-x/` directory instead.

## Layout

One `fills-*` plus one `park-*` template per liquidity source. A profile picks exactly one
source and uses that pair.

| File                | Source            | Emits                                                                                                                            |
| ------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `fills-aave.yaml`   | `aave_v3`         | `uniswapX/buy_stock_with_stable_{direct,from_aave}/{stock_label}`, `uniswapX/sell_stock_for_stable_direct/{stock_label}`         |
| `park-aave.yaml`    | `aave_v3`         | `uniswapX/park_stable_in_aave/{stable_label}`                                                                                    |
| `fills-morpho.yaml` | `morpho_vault_v2` | `uniswapX/buy_stock_with_stable_{direct,from_morpho_vault}/{stock_label}`, `uniswapX/sell_stock_for_stable_direct/{stock_label}` |
| `park-morpho.yaml`  | `morpho_vault_v2` | `uniswapX/park_stable_in_morpho_vault/{stable_label}`                                                                            |

Blueprint implementations and the slot tables live in `blueprints-x/uniswap-x/` (`fill.yaml`, `park.yaml`, `README.md`).

## Rules that are easy to break

**Fills are per stock; parking is per profile.** A `fills-*` template is included once per
stock, with `label` set to the stock symbol. A `park-*` template is included **exactly once
per caliber**, in its own position, with `label` set to the bare stable symbol (`USDC`,
`USDG` — not `USDG - steakUSDG`). Including parking from a per-stock template emits one
identical parking key per stock and collides.

**`label` is a routing path segment, not a display string.** It is the last segment of the
path the filler is configured against. Renaming it silently unroutes that stock or the
parking action.

**Slot declaration order in the blueprint is the ABI.** The transpiler assigns slot indices
from the order keys appear in `input_slots:`, not from order of use. Reordering that block
breaks every filler on the chain, and nothing but the contract test notices.

**`affected_tokens` is the authoritative stable-leg check.** The sell path carries no stable
symbol, so a fill entry must list both legs (stable and stock) and a parking entry must list
the stable only.

**Only canonical action names.** `buy_xstock_with_usdc_*`, `sell_xstock_for_usdc_*` and
`aavev3/add_collateral/USDC` are migration-only inputs and must not be generated.

## The operator liquidity sleeve

The canonical parking actions only _supply_. Every unwind path — Aave `withdraw_collateral`,
Morpho `withdraw_vault` / `redeem_vault*` / `emergency_redeem_vault_v2` — exists only in the
generic protocol namespace. A caliber therefore keeps its generic sleeve position alongside
canonical parking (`machines/uniswap-x-filler/mainnet/instructions/aave-usdc.yaml`,
`instructions-x/morpho-vault-v2.yaml`), and the duplicate supply path is the accepted cost.

The filler must never submit sleeve paths automatically; its only parking path is
`uniswapX/park_stable_in_<source>/{stable_label}`.

## Adding a liquidity source

1. Add `buy_stock_with_stable_from_<source>` and `park_stable_in_<source>` to
   `blueprints-x/uniswap-x/fill.yaml` and `park.yaml` respectively, respecting the slot layout.
2. Add `fills-<source>.yaml` and `park-<source>.yaml` here.
3. Register both in `CANONICAL_*_SLOTS`, `FILL_TEMPLATES` and `PARKING_TEMPLATES` in
   `tests/test_uniswap_x_filler_contract.py` — the directory-contents test fails until you do,
   deliberately.
4. Amend the contract, since the filler's source enum is part of it.

Adding a parking action to an existing caliber **adds a Merkle leaf**, so it changes the
instruction root and needs a Safe-only `setAllowedInstrRoot`. Renaming an **action** or a
**label** does not — those are TOML table keys only. Renaming an **`input_slots` name**
_does_: `state[i]` is `keccak256(slot_name)`, so a slot name is hashed data rather than
metadata. See the table in `blueprints-x/uniswap-x/README.md`.
