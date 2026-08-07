# Uniswap X Blueprint Slot Layout

These blueprints service Uniswap X direct-fill orders through Makina Lite. The external Reactor call must remain a normal Weiroll `CALL` so the Reactor sees the Safe as `msg.sender`.

They live under `blueprints-x/` because every consumer is makina-x — Safe-module fillers with no NAV accounting, so there is no `account.yaml` and no core-Caliber caller. (Contrast `blueprints/morpho/`, which stays in `blueprints/` because it is genuinely shared with core calibers.)

## Files

| File        | Actions                                                                                      | Slot ABI                              |
| ----------- | -------------------------------------------------------------------------------------------- | ------------------------------------- |
| `fill.yaml` | `buy_stock_with_stable_{direct,from_aave,from_morpho_vault}`, `sell_stock_for_stable_direct` | 3 slots: `order`, `signature`, amount |
| `park.yaml` | `park_stable_in_{aave,morpho_vault}`                                                         | 1 slot: `stable_amount`               |

Split because the two halves have different slot ABIs and different submitters — the filler sends fills continuously and parks opportunistically. Both declare `protocol: "uniswapX"`, so they share one rootfile namespace and the split changes no generated path. The matching instruction templates are `instructions-x/uniswap-x/fills-*.yaml` and `park-*.yaml`.

## Naming

Actions are named `<side>_stock_<with|for>_stable[_from_<source>]`. **`stable` and `stock_token` name the two legs of a fill, not specific tokens** — `stable` is whatever stablecoin the order settles in, `stock_token` is the tokenized-equity leg. Nothing here is USDC- or xStock-specific.

The `_from_<source>` suffix names where the stable leg is sourced, and is the axis this blueprint grows along: one action per liquidity source, sharing the same settlement tail. Adding a source means adding one action plus its address input.

| Deployment                              | `stable` | `stock_token`                | Stable source         |
| --------------------------------------- | -------- | ---------------------------- | --------------------- |
| `uniswap-x-filler` / `mainnet`          | USDC     | xStocks (`NVDAx`, …)         | Aave v3               |
| `uniswap-x-filler` / `robinhood` (4663) | USDG     | Robinhood Tokens (`NVDA`, …) | Morpho ERC-4626 vault |

Shared instruction wrappers live in `instructions-x/uniswap-x/fills-aave.yaml` (Aave-buffered) and `instructions-x/uniswap-x/fills-morpho.yaml` (Morpho-buffered). Each position supplies:

- `label`: display label, for example `NVDAx` or `NVDA`
- `stock_token`: the tokenized equity delivered by or received by the Safe
- `stable_token`: the stable leg the order settles in — Morpho template only; the Aave template reads it from `config.stable_address`

## Mainnet constants (`uniswap-x-filler`)

- Safe: `0x81Aa9DA3b68ef186E34e96FB6Ae9ad16D7715C72`
- MakinaLiteModule: `0xA032aFD73Fd42deb549698f5Ac93E8b373330B09`
- Uniswap X V2 Reactor: `0x00000011f84b9aa48e5f8aa8b9897600006289be`
- Aave v3 Pool: `0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2`
- USDC: `${token_list.mainnet.USDC}`
- NVDAx: `${token_list.mainnet.NVDAx}`

## Robinhood Chain constants (`uniswap-x-filler` / `robinhood`, chainId 4663)

- Safe: `0x81Aa9DA3b68ef186E34e96FB6Ae9ad16D7715C72` (same address as mainnet, distinct Safe)
- MakinaXModule: `0xceD40B1f1A9A9B18B5C5618291eC65ad9B98a6c7`
- Uniswap X **V3** Reactor: `0x000000007A1C8e570011EeDF86A2A35593013cBA`
- Morpho steakUSDG vault: `0xBeEff033F34C046626B8D0A041844C5d1A5409dd`
- USDG: `0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168` (6 dec)

Note the V2/V3 reactor split: `execute((bytes,bytes))` is identical across both, so these blueprints are unchanged — but off-chain order construction must emit V3 Dutch orders for Robinhood. Robinhood is an Arbitrum Orbit chain, so V3 decay ticks on `ArbSys.arbBlockNumber()`.

## Actions

### `buy_stock_with_stable_direct`

Buys the stock leg, paying the stable leg out of the Safe's own balance.

| Slot | Name            | ABI type  |
| ---- | --------------- | --------- |
| 0    | `order`         | `bytes`   |
| 1    | `signature`     | `bytes`   |
| 2    | `stable_amount` | `uint256` |

### `buy_stock_with_stable_from_aave`

Withdraws the stable leg from Aave v3, then settles. Reverts if the supply cannot cover the exact order amount.

| Slot | Name            | ABI type  |
| ---- | --------------- | --------- |
| 0    | `order`         | `bytes`   |
| 1    | `signature`     | `bytes`   |
| 2    | `stable_amount` | `uint256` |

### `buy_stock_with_stable_from_morpho_vault`

Withdraws the stable leg from a Morpho ERC-4626 vault, then settles. Reverts if the vault cannot cover the exact order amount — deliberately, since a fill needs the full amount. Sizing an exit against actual available liquidity is inventory management, not settlement: that lives in the operator sleeve (`instructions-x/morpho-vault-v2.yaml`, whose `emergency_redeem_vault_v2` sizes itself from the VaultV2 liquidity lens).

| Slot | Name            | ABI type  |
| ---- | --------------- | --------- |
| 0    | `order`         | `bytes`   |
| 1    | `signature`     | `bytes`   |
| 2    | `stable_amount` | `uint256` |

### `sell_stock_for_stable_direct`

Sells the stock leg from Safe balance and receives the stable leg.

| Slot | Name           | ABI type  |
| ---- | -------------- | --------- |
| 0    | `order`        | `bytes`   |
| 1    | `signature`    | `bytes`   |
| 2    | `stock_amount` | `uint256` |

`order` and `signature` are passed to `IReactor.execute((bytes,bytes))` as the `SignedOrder` tuple `(order, sig)`.

## Parking vs. the operator liquidity sleeve

Two paths supply the same stable to the same venue, on purpose:

| Path                                                                                 | Who submits it            | Why it exists                                                                   |
| ------------------------------------------------------------------------------------ | ------------------------- | ------------------------------------------------------------------------------- |
| `uniswapX/park_stable_in_aave/{stable_label}`                                        | the filler, automatically | canonical, contract-governed parking — fixed one-slot ABI                       |
| `aavev3/add_collateral/{label}`                                                      | operator only             | part of the generic Aave sleeve, alongside `withdraw_collateral`                |
| `uniswapX/park_stable_in_morpho_vault/{stable_label}`                                | the filler, automatically | canonical, contract-governed parking                                            |
| `morpho/deposit_vault/{label}` and the rest of `instructions-x/morpho-vault-v2.yaml` | operator only             | generic sleeve — `withdraw_vault`, `redeem_vault*`, `emergency_redeem_vault_v2` |

The sleeve is retained deliberately. The canonical parking actions only _supply_; every unwind
path (Aave `withdraw_collateral`, Morpho `withdraw_vault` / `redeem_vault*` /
`emergency_redeem_vault_v2`) exists only in the generic namespace, so removing the sleeve would
leave the operator unable to pull inventory back outside a fill. The overlap on the supply side
is the accepted cost.

The filler must never submit sleeve paths automatically — its only parking path is the
`uniswapX/park_stable_in_*` one for its configured source.

Parking is **one position per profile, keyed by the stable label**, while fills are keyed by the
stock label. Including a parking template from a per-stock template would emit one identical
parking key per stock and collide; `tests/test_uniswap_x_filler_contract.py` asserts it appears
at most once per caliber.

## Renaming actions

A leaf hashes `(commands, state, bitmap, position_id, is_debt, group_id, affected_tokens, position_tokens, instruction_type)`. Which of the three kinds of name survives into that preimage is **not** uniform, so they have different costs:

| Renaming                                        | In the leaf?                                   | Root moves? |
| ----------------------------------------------- | ---------------------------------------------- | ----------- |
| the **action** (`buy_stock_with_stable_direct`) | no — a TOML table key only                     | no          |
| the **label** (`NVDAx`)                         | no — a TOML table key only                     | no          |
| an **`input_slots` name** (`stable_amount`)     | **yes** — `state[i]` is `keccak256(slot_name)` | **yes**     |

The slot-name case is easy to get wrong. An unfilled runtime slot is represented in `state` by the keccak of its own name, so the name is hashed data, not metadata. Verified empirically against two generated mainnet rootfiles: renaming `buy_xstock_with_usdc_direct` → `buy_stock_with_stable_direct` left `commands`, `bitmap`, `affected_tokens`, `position_id`, `is_debt`, `group_id`, `instruction_type` and `state[0]`, `state[1]`, `state[3]` byte-identical, and moved only `state[2]` — from `keccak256("usdc_amount")` = `0xaaff9c29…` to `keccak256("stable_amount")` = `0xefe54415…`.

So an action-only rename is free and needs no governance transaction. Renaming a slot, or adding an instruction, changes the root and needs a Safe-only `setAllowedInstrRoot`. Callers must be updated in lockstep either way, since the action name is how an instruction selects an action.
