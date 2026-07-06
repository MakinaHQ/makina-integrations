# Aave V4 supply blueprints + USDG/frxUSD on dusd mainnet

**Date:** 2026-06-18
**Branch:** `feat/aave-v4-usdg`

## Goal

First Aave **V4** integration. Add reusable supply (deposit / withdraw / account)
blueprints and wire two lend-only positions into the dusd mainnet caliber:
USDG and frxUSD.

## Aave V4 architecture (Hub & Spoke), verified on-chain

| Component          | Address                                               | Role                                              |
| ------------------ | ----------------------------------------------------- | ------------------------------------------------- |
| Spoke (user entry) | `0x94e7A5dCbE816e498b89aB752661904E2F56c485`          | `supply`/`withdraw`/`borrow`; per-user accounting |
| Hub                | `0xCca852Bc40e560adC3b1Cc58CA5b55638ce826c9`          | aggregate liquidity / underlying custody          |
| USDG               | `0xe343167631d89B6Ffc58B88d6b7fB0228795491D` (6 dec)  | reserve_id `11`, hub assetId 8                    |
| frxUSD             | `0xCAcd6fd266aF91b8AeD52aCCc382b4e165586E29` (18 dec) | reserve_id `12`, hub assetId 9                    |

Markets are identified by a numeric `reserveId` on the Spoke (not by asset
address like V3). The Spoke pulls the underlying from the caller and forwards it
to the Hub; the supplier balance is tracked per-`(reserveId, user)` in Spoke
storage — **no aToken is minted**.

### Flows (from the supply/withdraw txs + ABI)

- **Supply:** `approve(asset → Spoke, amt)` then `supply(uint256 reserveId, uint256 amount, address onBehalfOf)`.
  (EOAs use `permitReserve`+`multicall` for a gasless approve; a caliber uses a plain `approve`.)
- **Withdraw:** `withdraw(uint256 reserveId, uint256 amount, address onBehalfOf)` — funds return to the caller (caliber = onBehalfOf = recipient).
- **Account:** `getUserSuppliedAssets(uint256 reserveId, address user) → uint256` — returns the supplied balance **directly in the underlying** (interest-inclusive); no share conversion.

## Deliverables

| File                                 | Action                                                |
| ------------------------------------ | ----------------------------------------------------- |
| `blueprints/aave-v4/deposit.yaml`    | new — `protocol: aavev4`, action `supply`             |
| `blueprints/aave-v4/withdraw.yaml`   | new — action `withdraw`                               |
| `blueprints/aave-v4/account.yaml`    | new — action `account`                                |
| `instructions/aavev4-supply.yaml`    | new — 3 entries, Spoke/reserve-parameterized          |
| `token-lists/prod-token-list.json`   | add frxUSD                                            |
| `machines/dusd/mainnet/caliber.yaml` | add USDG (reserve 11) + frxUSD (reserve 12) positions |

- Blueprints are reserve-agnostic; the instruction takes vars `label`, `asset_address`, `spoke_address`, `reserve_id`. The Spoke remains protocol-specific and position-scoped rather than fund-wide config because future V4 Spokes may have separate reserve and liquidation domains.
- Caliber positions: `group_id: "2"` (dedicated to this Spoke), **no `position_tokens`** (no aToken; accounted via view). Position ids (operator-assigned): USDG `102356596921134877304003836794819117820`, frxUSD `64048496748963625189377001215830228790`.
  - Supply-only today carries no debt, so `group_id 0` would also be valid — but the V4 liquidation domain is the whole Spoke (one health factor per user; `liquidationCall` crosses any collateral reserve against any debt reserve). Pre-allocated to a dedicated group so a future borrow on this Spoke already has its collateral + debt grouped, with no position migration. One group per Spoke; a different Spoke gets its own.
- Labels `USDG`/`frxUSD` are unique under the `(protocol, type, label)` rule since `protocol=aavev4` differs from the existing `aavev3`.

## External prerequisite for frxUSD (owned by fund ops, outside these files)

frxUSD is **not** priceable on dusd today: `getPrice(frxUSD, USDC)` reverts
`PriceFeedRouteNotRegistered(frxUSD)` and `isBaseToken(frxUSD)` is `false`
(dusd accounting token is USDC). Before the frxUSD position can account:

1. `setFeedRoute` on OracleRegistry `0xC388B72AB90Be82B230D919F9C05c87F9397f485` (frxUSD → USDC route).
2. `addBaseToken(frxUSD)` on the dusd caliber `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC`.

USDG is already a base token with a working feed, so it accounts immediately.

## Validation

Tenderly fork via spellcaster: USDG full deposit → account → withdraw with
wei-level accounting match against `getUserSuppliedAssets`. For frxUSD, register
the feed route + base token on the fork (storage override) to validate the
identical cycle.
