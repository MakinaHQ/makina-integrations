# Re Protocol — reUSD Synthetic Swap (dusd mainnet) — Integration Summary

Network: Ethereum mainnet (chain id 1)
Protocol: Re Protocol (re.xyz) — Insurance Capital Layer + Redemption Gateway
Machine: dusd · caliber `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC`
Scope: SWAP IN (USDC→reUSD) + SWAP OUT (reUSD→sUSDe), accounting = 0

## Addresses (verified on-chain 2026-06-01)

| Name                                    | Address                                      | Notes                                            |
| --------------------------------------- | -------------------------------------------- | ------------------------------------------------ |
| reUSD (share token)                     | `0x5086bf358635B81D8C47C66d1C8b9E567Db70c72` | 18-dec ERC20 `ShareToken`; senior tranche        |
| reUSD ICL (mint layer)                  | `0x4691C475bE804Fa85f91c2D6D0aDf03114de3093` | EIP-1967 proxy → impl `0x06d4…9670`              |
| RedemptionGateway                       | `0x8aEb9453EF22Cb38abC7a3Af9c208F65C1BfE31e` | public instant/window redeem entry               |
| InstantRedemption                       | `0xa31deEbb3680A3007120e74bCbDf4df36F042A40` | reUSD approval spender; burns + pays from buffer |
| KYC Registry                            | `0x82F1806AEab5Ecb9a485eb041d5Ed4940b123995` | shared by deposit + redeem                       |
| Deposit Token Registry                  | `0x73d37A98C0fCBd049BfFFfe67Bf9af36d603c0F6` | accepted: USDC, USDT, USDe, sUSDe                |
| Daily Instant Redemption Vault (buffer) | `0x5C454f5526e41fBE917b63475CD8CA7E4631B147` | payout reserve                                   |
| AccessManager                           | `0x3f0DA1C363e34802C6f12F9C27276dC0e6696FD8` | governs `restricted` fns                         |
| USDC (swap-in)                          | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` | 6-dec                                            |
| sUSDe (swap-out payout)                 | `0x9D39A5DE30e57443BfF2A8307A4256c8797A3497` | 18-dec; = `activePayoutToken()` today            |

Share price (2026-06-01): 1 reUSD = 1.081066 USDC. Redemption fee = 6 bps.

## Swap in — USDC → reUSD (synchronous, always available)

`ICL.deposit(address token, uint256 amount, uint256 minShares)`

1. `USDC.approve(ICL, amount)`
2. `ICL.deposit(USDC, amount, minShares)` → mints reUSD to the caliber (msg.sender).

- `onlyKYCUser`; `isKYCApproved(caliber) == true` ✓. `depositEnabled() == true`.
- `amount` in USDC native decimals (6); `minShares` in reUSD (18), operator-supplied
  (off-chain via `ICL.convertToShares`/`previewDeposit` minus tolerance). USDC deposit fee = 0.
- The ICL also accepts USDT/USDe/sUSDe — `asset_address` is parameterised.

## Swap out — reUSD → sUSDe (atomic, buffer-gated)

`RedemptionGateway.redeemInstant(uint256 shares, uint256 minPayout)`

1. `reUSD.approve(InstantRedemption, shares)` — the **InstantRedemption** contract does the
   `transferFrom`, so it (not the gateway) is the approval spender.
2. `caliber → gateway.redeemInstant(shares, minPayout)` →
   `InstantRedemption.redeemFor(caliber, shares, minPayout)` →
   burns reUSD, pays `activePayoutToken()` (sUSDe) from the buffer to the caliber.

- `redeemInstant` is **not** AccessManager-restricted: gated only by `kyc.isKYCApproved(msg.sender)`
  (caliber passes) and `currentMode() == INSTANT` (enum `{NONE,INSTANT,WINDOW}`; mode = INSTANT now,
  `isWindowOpen() == false`). The gateway already holds the role to call `redeemFor`
  (`canCall(gateway, InstantRedemption, redeemFor) == true`).
- `previewRedemption(caliber, shares)` → `(grossPayout, fee, netPayout, available)`; reverts if buffer
  short, below min (USD value < `minRedemption` ≈ 0.01 reUSD) / above max (1M), daily/user limit hit,
  or `netPayout < minPayout`. Capacity ~42M sUSDe; daily limit ~14M.
- Payout token is NOT a parameter — always the protocol's active payout token for the day (sUSDe now).
  On a non-sUSDe day this yields a different base token.

### Fallback exit

When the instant buffer is short (or mode ≠ INSTANT), exit via the caliber `swap_module`
(`0x923c98b22F9c367A109E93f7dfBaCa28b20C17C3`) at market — reUSD is a base token, so no dedicated
blueprint is needed. (The gateway window-redemption flow — `submitWindowRequest`/`claimWindowPayout` —
is async and not modelled here.)

## Accounting

**Base-token model.** reUSD is a caliber base token, priced by the OracleRegistry reUSD/USD feed.
`account.yaml:account_0` returns 0 (its value is captured by the base-token registry — accounting it
here would double-count). Both legs settle into base tokens (USDC→reUSD, reUSD→sUSDe), so the
MANAGEMENT instructions use `affected_tokens=[]`. Value conservation is enforced by the
`min_shares` / `min_payout` slippage args inside the deposit/withdraw instructions. Same model as the
mGLOBAL "swap in (synthetic)" position.

(Why `affected_tokens=[]`: with `account_0` the position value change is always 0, so declaring any
`affected_tokens` makes the caliber's loss reconciliation `_checkPositionMinDelta(0, loss, bps)` revert
on the swap's loss leg. The position-token alternative — reUSD as a position token with real accounting
and `affected=[USDC]`/`[sUSDe]` — would enable the 3%/5% caliber reconciliation but was not chosen.)

## Files

| Path                                 | Role                                                 |
| ------------------------------------ | ---------------------------------------------------- |
| `blueprints/re/deposit.yaml`         | `swap_asset_for_reusd`                               |
| `blueprints/re/withdraw.yaml`        | `redeem` (absolute) + `redeem_relative` (bps)        |
| `blueprints/re/account.yaml`         | `account_0` (returns 0)                              |
| `instructions/reusd-swap.yaml`       | wires the 4 instructions into one position           |
| `machines/dusd/mainnet/caliber.yaml` | position id `keccak256("re.reusd.swap")`, group_id 0 |
| `token-lists/prod-token-list.json`   | reUSD entry                                          |

## Prerequisites before live use (on-chain setup, outside these files)

1. **reUSD base token + feed route**: `addBaseToken(reUSD)` on the caliber AND `setFeedRoute(reUSD, …)`
   in the OracleRegistry (so the base-token registry can price reUSD). (sUSDe + USDC already set up.)
2. **Redeem availability** depends on the protocol: `currentMode() == INSTANT`, buffer holding enough
   sUSDe, and `activePayoutToken() == sUSDe`. None require any grant to the caliber — the gateway path
   works today for the KYC'd caliber. (Deposit is unconditional.)

## Not compiled

Per instruction, the instruction file was NOT transpiled. Compile with
`/compile machines/dusd/mainnet/instructions/…` (or the repo's transpiler) when ready.
