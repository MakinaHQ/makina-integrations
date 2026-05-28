# Midas mGLOBAL Redemption Vault (with Aave) — Integration Summary

Network: Ethereum mainnet (chain id 1)
Protocol: Midas (RedDuck) — MGlobalRedemptionVaultWithAave
Scope: WITHDRAW + ACCOUNT (no deposit, no harvest)

## Addresses

- Vault proxy (call target): `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B`
- Implementation: `0xf687E76e3d62d62fE6F6A7f66ce9faE21df6438d`
- mGLOBAL (mToken): `0x7433806912Eae67919e66aea853d46Fa0aef98A8`
- USDC (tokenOut): `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`
- requestRedeemer (USDC liquidity): `0xaB9dA7953D82d81006639A6f87883d59594918b9`
- mTokenDataFeed: `0xb468A6F63868cB6C6D99105EDfbe73d6B21f139E`
- USDC dataFeed: `0x3aAc6fd73fA4e16Ec683BD4aaF5Ec89bb2C0EdC2`

## Mechanism

Asynchronous, admin-settled redemption. Caliber escrows mGLOBAL in a single call (recipient = caliber); admin later calls `approveRequest(id, newRate)` which pulls USDC from `requestRedeemer` and pushes it directly to the caliber, then burns the escrowed mGLOBAL. No on-chain claim function.

## Withdraw flow (`redeem_request`)

1. `kv.get(key)` → revert if non-zero (one-in-flight invariant).
2. `vault.currentRequestId()` → `next_id` (pre-increment value).
3. `mGLOBAL.approve(vault, amountMTokenIn)`.
4. `vault.redeemRequest(USDC, amountMTokenIn, caliber_address)`.
5. `kv.set(key, next_id)`.

## Account flow

1. `kv.get(key)` → `stored_id`.
2. `vault.redeemRequests(stored_id)` → `Request(sender, tokenOut, status, amountMToken, mTokenRate, tokenOutRate)`.
3. If `status == Pending(1)`: value (USD18) = `amountMToken * mTokenRate / 1e18` — using the **stored** snapshot rate, not the live feed.
4. Else: value = 0; KV reset is housekeeping.
5. Caliber's normal mGLOBAL base-token accounting handles the un-redeemed balance — do not double-count it here.

## Fees & rates

- `tokensConfig[USDC].fee = 0` → zero per-token redemption fee.
- `tokensConfig[USDC].stable = true` → `tokenOutRate` hard-pinned to `1e18`.
- `instantFee = 50` (0.5%) — NOT applied on the request path.
- `minAmount = 0` → no minimum mGLOBAL per request.
- `currentRequestId = 0` → vault is brand new.

## Risks (off-chain monitoring required)

- `rejectRequest` does NOT auto-refund escrowed mGLOBAL — admin must manually `withdrawToken` to recover. Blueprint reports 0 once status != Pending.
- `approveRequest` does NOT enforce `variationTolerance` (only `safeApproveRequest` does). Admin can settle at any rate. Mitigation: accounting uses the stored snapshot rate, not the future settlement rate.
- `mTokenDataFeed.getDataInBase18()` currently **reverts** with `DF: feed is unhealthy`. Accounting is immune (uses stored rate from Request struct). New `redeemRequest` txs WILL revert until the feed recovers — verify before submitting.
- USDC payout truncated to 6 decimals (dust < $1e-6 lost).
- Greenlist gate: caliber must hold `M_GLOBAL_GREENLISTED_ROLE`.
- Single-in-flight: blueprint enforces one Pending request at a time.

## Out of scope

- `redeemInstant` (would pay 0.5% fee, consumes vault liquidity).
- `redeemFiatRequest` (fiat path).
- Deposit on this vault (Midas mints mGLOBAL via a separate DepositVault).
- Aave-related "harvest" (no rewards emitted to redeemers).

## Reference

Pattern mirrors `blueprints/infinifi/{withdraw,account}.yaml` (KV one-in-flight, helper usage, reserved_slots shape).
