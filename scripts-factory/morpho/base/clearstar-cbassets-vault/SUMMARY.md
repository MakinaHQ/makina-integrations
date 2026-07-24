# Clearstar cbAssets Vault (CSCBUSDC) — Morpho VaultV2 on Base

MakinaX (Safe-module) integration, **management-only**. No caliber, no on-chain
NAV accounting, no harvest (no rewards). Actions spec'd: **deposit**, **withdraw**.

## Identity

| Field               | Value                                                                                           |
| ------------------- | ----------------------------------------------------------------------------------------------- |
| Vault / share token | `0x91C056B6d4311a743614FBc03ac32d4E6A2d3a3c` (CSCBUSDC, 18 dp)                                  |
| Underlying asset    | USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` (6 dp)                                        |
| Type                | Morpho **VaultV2** (ERC-4626). `MORPHO()` reverts, `firstTotalAssets()` OK -> not MetaMorpho V1 |
| Chain               | Base (chainId 8453)                                                                             |
| dialectic_id        | `643d8eaaa76be6f28b34754444aa8ba9`                                                              |
| makina position id  | `133242423309628000059155946577244883881`                                                       |
| Share price         | 1 CSCBUSDC = 1.020751 USDC                                                                      |

## Execution model

Executed **as the Safe** `0x9f0f855A7370cc30e24924258214681A782A34aC` via
MakinaXModule `0x785db5f3F3Ad18D6291689907D319954AF79A03E`. The Safe is the
`onBehalf` (share recipient / owner) and the `receiver` on every call.

## Deposit / withdraw call signatures (verified against DEPLOYED ABI)

**Approval target: the vault itself** (ERC-4626 pulls USDC via `transferFrom`). No router/periphery.

Deposit (2 calls):

1. `approve(address spender, uint256 amount)` on **USDC**, spender = vault `0x91C0...3a3c`
2. `deposit(uint256 assets, address onBehalf)` on the vault, `onBehalf = Safe` -> returns shares
   - alt: `mint(uint256 shares, address onBehalf)` -> returns assets

Withdraw (single call, no approval — Safe burns its own shares):

- `redeem(uint256 shares, address receiver, address onBehalf)`, `receiver = onBehalf = Safe` -> returns assets
- alt (exact asset): `withdraw(uint256 assets, address receiver, address onBehalf)`, `receiver = onBehalf = Safe` -> returns shares

Note the arg ordering: on VaultV2, `deposit`/`mint` take the recipient as arg #2
(named `onBehalf`); `withdraw`/`redeem` take `(amount, receiver, onBehalf-owner)`.

## VaultV2 gating / constraints (read on-chain)

- **Gates all unset** (zero address) -> fully permissionless. `canReceiveShares` / `canSendShares` / `canReceiveAssets` / `canSendAssets` all return `true` for the Safe.
- **No per-address caps.** Absolute/relative caps exist only on internal allocation ids and are enforced on curator `allocate`, not on user deposit.
- **`maxDeposit` / `maxMint` / `maxWithdraw` / `maxRedeem` are `pure` and always return 0** — a known VaultV2 trait, NOT a cap-full/gate signal. Do not use them to size or gate transactions.
- **Timelocks apply only to curator governance** (cap/adapter/fee changes), never to user deposit/withdraw. User flows are immediate.

## Liquidity / redemption

- **Fully synchronous** — no request/claim, no withdrawal queue.
- Idle assets currently 0; all assets sit in the single liquidity adapter `0x812B71c33Ae5EAfEbAe967C5670e37eca3cab0ac`. `withdraw`/`redeem` consume idle first, then auto-deallocate from that adapter.
- A withdraw can **revert if the requested amount exceeds adapter/underlying-market liquidity** (a liquidity revert, not a queue). Fallback: `forceDeallocate(adapter, data, assets, onBehalf)` pulls from a specific adapter with a **0.3% penalty** (3e15 WAD).

## Accounting / oracle

- No on-chain accounting instruction (makina-x management-only).
- Off-chain valuation as an ERC-4626 position: `balanceOf(Safe)` -> `convertToAssets(shares)` (or `previewRedeem`).
- No `addBaseToken`, no OracleRegistry feed required to ship.
