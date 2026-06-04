# Uniswap X Blueprint Slot Layout

These blueprints service Uniswap X direct-fill orders through Makina Lite. The external Reactor call must remain a normal Weiroll `CALL` so the Reactor sees the Safe as `msg.sender`.

Mainnet constants used by the `uniswap-x-filler` machine:

- Safe: `0x81Aa9DA3b68ef186E34e96FB6Ae9ad16D7715C72`
- MakinaLiteModule: `0xA032aFD73Fd42deb549698f5Ac93E8b373330B09`
- Uniswap X V2 Reactor: `0x00000011f84b9aa48e5f8aa8b9897600006289be`
- Aave v3 Pool: `0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2`
- USDC: `${token_list.mainnet.USDC}`
- NVDAx: `${token_list.mainnet.NVDAx}`

Shared instruction wrappers are defined in `instructions/uniswap-x.yaml`. Each xStock position supplies:

- `label`: display label, for example `NVDAx`
- `xstock_token`: xStock token delivered by or received by the Safe

## Actions

### `buy_xstock_with_usdc_direct`

The filler buys xStock from the swapper and delivers USDC from Safe balance.

| Slot | Name          | ABI type  |
| ---- | ------------- | --------- |
| 0    | `order`       | `bytes`   |
| 1    | `signature`   | `bytes`   |
| 2    | `usdc_amount` | `uint256` |

### `buy_xstock_with_usdc_from_aave`

The filler buys xStock from the swapper and withdraws USDC from Aave before settlement.

| Slot | Name          | ABI type  |
| ---- | ------------- | --------- |
| 0    | `order`       | `bytes`   |
| 1    | `signature`   | `bytes`   |
| 2    | `usdc_amount` | `uint256` |

### `sell_xstock_for_usdc_direct`

The filler sells xStock from Safe balance and receives USDC.

| Slot | Name            | ABI type  |
| ---- | --------------- | --------- |
| 0    | `order`         | `bytes`   |
| 1    | `signature`     | `bytes`   |
| 2    | `xstock_amount` | `uint256` |

`order` and `signature` are passed to `IReactor.execute((bytes,bytes))` as the `SignedOrder` tuple `(order, sig)`.
