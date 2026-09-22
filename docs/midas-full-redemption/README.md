# Midas full-redemption vault

A synchronous exit from a Midas mToken, settling at a rate frozen in advance rather than
at whatever rate an operator chooses days later.

Midas provisions a **dedicated** `RedemptionVaultWithSwapper` per caliber, funds it with
the payout stablecoin, and freezes the redemption rate at that moment. The caliber then
calls `redeemInstant` and receives the stablecoin in the same transaction. This is a
different contract from the standard redeemer used by
[`instructions/midas-redemption.yaml`](../../instructions/midas-redemption.yaml), and it
is wired as a separate position rather than another action on the existing one.

Both routes stay available. The full-redemption vault buys **execution certainty** —
atomic settlement, a rate that cannot move mid-unwind, no operator-side rejection risk,
and ring-fenced liquidity. It does not automatically buy a better price: whether it beats
the standard path depends entirely on the mToken, because it is the standard redeemer's
pricing feed that varies. Re-measure both routes before each cycle.

## Two money paths that never touch on-chain

Using the vault requires an off-chain cycle with Midas. They ask for a deposit sized to
the value you intend to redeem, sent to an MPC wallet, before they de-allocate the
underlying and fund the vault. It is returned once you tell them the cycle is finished.

```
     ┌──────────────── CALIBER ────────────────┐
     │                                         │
 ① deposit                              ③ mToken in
     │                                         │
     ▼                                         ▼
MPC EOA wallet                       full-redemption vault
(NOT the vault)                                │
     │                                  ④ stablecoin out
② Midas funds the vault ─────────────────────▶ │
     │                                         ▼
⑤ deposit refunded ──────────────────────▶ CALIBER
```

The two paths reconcile only in Midas' books. The recipient is an externally owned
account, deliberately **not** the vault's `tokensReceiver` or `feeReceiver`, so the
deposit and the redemption can never net out on-chain.

That is why the deposit is booked as a **claim** rather than a transfer: a claim keeps
NAV continuous across ① through ⑤, where an unaccounted outbound transfer would show up
as a NAV drop on the way out and a NAV jump on the way back.

## Positions

Each participating caliber gets two positions — the redemption itself, and the deposit
claim that carries the off-chain leg.

| Caliber       | Redemption position                     | Deposit claim         |
| ------------- | --------------------------------------- | --------------------- |
| `dmg/mainnet` | `mGLOBAL Full Redemption`               | `mGLOBAL MPC Deposit` |
| `dmg/base`    | `mGLO Full Redemption`                  | `mGLO MPC Deposit`    |
| `dmw/mainnet` | `mWIN Full Redemption`, and a PYUSD leg | `mWIN MPC Deposit`    |

Position ids are the full keccak256 of the string in each trailing comment:
`cast keccak "<string>" | cast to-dec`. Labels are matched literally by tooling, so
treat them as part of the interface.

Where a vault accepts more than one payout token, each gets its own position rather than
an extra action — `token_out_address` is a per-position var and the instruction files
take exactly one.

Source files:

- [`blueprints/midas/full-redemption.yaml`](../../blueprints/midas/full-redemption.yaml)
  — `redeem_instant`
- [`instructions/midas-full-redemption.yaml`](../../instructions/midas-full-redemption.yaml)
- [`blueprints/makina/custodian-deposit.yaml`](../../blueprints/makina/custodian-deposit.yaml)
  — `deposit_capped`, `settle_full`, `settle_residual`, `account_claim`
- [`instructions/makina-custodian-deposit.yaml`](../../instructions/makina-custodian-deposit.yaml)

## How the vault is configured — and the failure modes

Both settings are ordinary `RedemptionVaultWithSwapper` configuration, not a new contract
type. Both are also the things that break.

### The frozen rate is a single-round aggregator

`mTokenDataFeed()` points at a feed unique to each full-redemption vault, whose aggregator
holds exactly one round, written when Midas funded it. `MGlobalDataFeed._getDataInBase18`
enforces:

```solidity
require(block.timestamp - updatedAt <= healthyDiff
        && answer >= minExpectedAnswer && answer <= maxExpectedAnswer,
        "DF: feed is unhealthy");
```

So a full-redemption vault is **self-destructing**. Once that single round goes stale,
every redemption reverts and only Midas can re-freeze it. `healthyDiff` is per-vault and
has been as short as 30 days. The async path has no equivalent deadline — this is the
single biggest operational difference between the two routes.

**Check the feed is healthy before starting an unwind, not after.**

### The 100% fee is an access-control list, not a fee

These vaults carry `tokensConfig(tokenOut).fee = 10000`, and
`ManageableVault.ONE_HUNDRED_PERCENT` is also `10000`. `_calcAndValidateRedeem` ends with:

```solidity
require(amountMTokenIn > result.feeAmount, "RV: amountMTokenIn < fee");
```

Any caller _not_ in `waivedFeeRestriction` therefore reverts outright — a hard lock
rather than a silent confiscation. For a waived caliber `_getFeeAmount` returns 0 and
`instantFee` is 0, so nothing is paid on-chain.

Two consequences:

- **The gate is keyed per payment token.** A payout token left at `fee = 0` has no gate
  at all. When checking readiness, read `fee` _and_ `allowance` for every payout token,
  not just the one you intend to use.
- **Losing the waiver and losing the fee look identical from outside** — both surface as
  `RV: amountMTokenIn < fee`.

### The mToken is deliberately never approved

`redeemInstant` burns from the caller via a role, so the happy path needs no allowance.
If the vault is under-funded the call diverts into the `WithSwapper` fallback, which
_does_ need one. Withholding the approval makes an under-funded vault **fail closed**
with `ERC20: insufficient allowance` instead of quietly executing at a worse route.

## What needs accounting

Less than you would expect — the redemption itself is fully covered by the base-token
registry.

| Stage                     | Where the value sits                           | Accounted by           |
| ------------------------- | ---------------------------------------------- | ---------------------- |
| baseline                  | mToken as collateral, plus stablecoin          | existing positions     |
| deposit sent              | MPC wallet (an EOA, outside the caliber)       | **the claim position** |
| waiting for de-allocation | unchanged, for days or weeks                   | the claim carries it   |
| vault funded, rate frozen | unchanged on our side                          | the claim carries it   |
| collateral unwound        | mToken in the caliber wallet                   | base-token registry    |
| `redeem_instant`          | mToken burned and stablecoin received, same tx | `account_0`            |
| deposit returned          | stablecoin back in the caliber                 | `settle_full` — run it |

The deposit is the only leg where value leaves the caliber's sight.

**There is no pending-redemption state to account for**, and that is the structural
difference from the async flow. The async path escrows the mToken inside the vault where
the base-token registry cannot see it, so it needs a KV key and
[`blueprints/midas/account.yaml`](../../blueprints/midas/account.yaml) `:account` to value
the in-flight request. `redeemInstant` is atomic: the mToken is priced by the registry
right up to the block it is burned, and the stablecoin arrives in the same transaction.
Hence `account_0`, and hence no KV key.

Two NAV effects that are **not** accounting gaps:

1. **Realized basis at redemption.** The frozen rate generally differs from the Makina
   mark. The management leg declares `affected_tokens: []`, so no delta check runs and
   the difference is absorbed as a NAV movement in the redemption block. Expected — size
   it in advance.
2. **Latent basis while holding the mToken.** Between unwinding the collateral and
   redeeming, the caliber carries the mToken at the Makina mark but can only realize the
   frozen rate. Keep that window short.

## Review checklist

- **Distinct `kv_store_key` per position.** The deposit blueprint tracks one outstanding
  claim per key and the async withdraw blueprint tracks one in-flight request per key.
  Sharing a key between two positions lets them overwrite each other.
- **First use of any MPC recipient must be a dust deposit**, confirmed received. The
  address has no on-chain corroboration, and a transfer to a wrong-but-valid address
  succeeds silently while the delta check passes by construction. The amount is a runtime
  slot, so the probe costs nothing.
- **`max_deposit_amount` bounds cumulative outstanding**, not a single call, and it
  self-relaxes as claims settle. Raising it requires a release.
- **Close the claim only when the refund lands** — `settle_full`, then account positions,
  then confirm the position reads zero. Settling at notification understates NAV.
- **Leave a settled deposit position in place.** Removing it while a claim is booked makes
  `getNetAum()` revert permanently.
- **Some mTokens carry a residual min-balance hook**, so a partial exit leaving a nonzero
  balance below the minimum reverts. Combined with the vault's own `minAmount`, exit
  sizing can be very coarse.

## Chain-specific helper addresses

`boolean_helper_address` and `caliber_helper_address` are the two Makina helpers that are
**not** deployed at the same address on every chain. They are declared as blueprint
`inputs` and bound per caliber from `${config.*}`, never hardcoded as blueprint constants.

This matters more than it looks. The guard helpers (`revertIfTrue`, `revertIfFalse`)
declare no return value, so their weiroll out-slot is `0xFF` and the VM skips the output
check. A call to a **codeless** address therefore succeeds with empty returndata and the
guard silently passes — a hardcoded mainnet address would not fail loudly on another
chain, it would simply stop guarding.

The other helpers (math, bytes32, context) genuinely are deployed at one address
everywhere and remain blueprint constants.
