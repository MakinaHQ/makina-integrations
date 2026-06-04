# Uniswap X Filler Makina Lite Design

## Scope

Create a new machine named `uniswap-x-filler` for the mainnet Makina Lite instance used by the Uniswap X filler. The machine represents a Safe plus MakinaLiteModule execution environment, not a normal caliber. The Safe is `0x81Aa9DA3b68ef186E34e96FB6Ae9ad16D7715C72`.

The machine will expose management instructions only. It will not include accounting instructions or caliber-style position valuation. The receiver, Aave `onBehalfOf`, and Aave withdraw recipient are always the Safe, not `caliber_address`.

## Architecture

Use the existing generic Aave v3 blueprints for standalone USDC inventory management:

- `blueprints/aave/deposit.yaml:add_collateral`
- `blueprints/aave/withdraw.yaml:withdraw_collateral`

Add a new protocol folder `blueprints/uniswap-x/` for Uniswap X settlement instructions. These blueprints handle only the Uniswap X Reactor fill path and the optional Aave leg needed for atomic inventory use during a fill.

Add a new machine folder:

- `machines/uniswap-x-filler/config.toml`
- `machines/uniswap-x-filler/mainnet/caliber.yaml`
- `machines/uniswap-x-filler/mainnet/instructions/aave-usdc.yaml`
- `instructions/uniswap-x.yaml`
- `machines/uniswap-x-filler/mainnet/rootfiles/`

The `caliber.yaml` filename is kept because the transpiler expects that source-file shape, but its config should use `safe_address` rather than `caliber_address`.

## Action Families

### Aave inventory management

Standalone instructions for moving Safe-owned USDC into and out of Aave:

- `aave/deposit/USDC`: approve Aave Pool to spend USDC, then call `Pool.supply(USDC, amount, Safe, 0)`.
- `aave/withdraw/USDC`: call `Pool.withdraw(USDC, amount, Safe)`.

These wrappers should point at the existing Aave blueprints and pass the Safe address through `on_behalf_of` and `to`.

### Uniswap X fills using Aave

Atomic settlement instructions that use the Safe's Aave USDC inventory:

- `buy_xstock_with_usdc_from_aave`: withdraw USDC from Aave to the Safe, approve the Reactor for the resolved USDC output amount, then call `Reactor.execute(order, sig)`.

The Reactor call must be a normal external CALL. It must not be encoded as a delegatecall or staticcall, because the Reactor checks `exclusiveFiller == msg.sender`, and the intended caller identity is the Safe.

### Uniswap X fills using direct balances

Atomic settlement instructions that use balances already held by the Safe:

- `buy_xstock_with_usdc_direct`: approve the Reactor for USDC, then call `Reactor.execute(order, sig)`.
- `sell_xstock_for_usdc_direct`: approve the Reactor for xStock, then call `Reactor.execute(order, sig)`.

These variants do not touch Aave. They are useful when the Safe intentionally keeps hot USDC or xStock inventory outside Aave.

## Constants

Protocol-specific addresses should be hardcoded in the machine instruction wrappers, not in shared config:

- Aave v3 Pool: `0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2`
- USDC: `${token_list.mainnet.USDC}`
- NVDAx: `${token_list.mainnet.NVDAx}`
- Uniswap X V2 Reactor: `0x00000011f84b9aa48e5f8aa8b9897600006289be`

The Safe address belongs in machine config as `safe_address`.

## Input Slots

All Uniswap X settlement blueprints need dynamic order data supplied at execution time:

- `order`: `bytes`
- `signature`: `bytes`

Token approval amount slots are named by the token delivered by the Safe:

- `usdc_amount`: `uint256`, USDC amount approved for the Reactor when buying xStock. In the Aave-backed buy action, this same amount is withdrawn from Aave first.
- `xstock_amount`: `uint256`, xStock amount approved for the Reactor when selling xStock.

The direct variants do not expose Aave amount slots.

The xStock token is a position variable, not a runtime input slot. New xStocks reuse `instructions/uniswap-x.yaml` and provide `label` plus `xstock_token` in the machine position vars.

## Error Handling

The blueprints rely on protocol reverts for unsafe states:

- Aave withdraw reverts if the Safe lacks withdrawable aUSDC liquidity or Aave pool liquidity.
- ERC20 approve or Reactor execution reverts if the Safe lacks the required output token balance.
- Reactor execution reverts if the order, signature, exclusive filler, or resolved amounts are invalid.

The filler's ParamsEncoder must supply the same slot order and ABI types as the compiled instructions. Any change to these blueprints requires updating the encoder golden tests.

## Testing

Implementation should verify the source files by compiling the new machine's mainnet `caliber.yaml` into a rootfile. The generated rootfile should be checked for the expected action paths and input slots.

Before mainnet use, run an anvil or Tenderly mainnet fork test for each family:

- standalone Aave deposit and withdraw;
- Aave-backed `buy_xstock_with_usdc` fill;
- direct `buy_xstock_with_usdc` fill;
- direct `sell_xstock_for_usdc` fill.

The Aave-backed and direct fill tests must confirm a Uniswap X fill event and the Safe as the effective exclusive filler.
