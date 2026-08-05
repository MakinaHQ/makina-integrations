# Maple escrow attribution (design A)

**Date:** 2026-08-05
**Status:** implemented
**Affects:** dusd/mainnet (syrupUSDC/RLUSD Morpho loop, Royco JT-syrupUSDC), tstUSDC3/mainnet (Royco JT-syrupUSDC)

## Problem

`Maple_WithdrawalManager.userEscrowedShares` is keyed on the **owner** — the caliber — not on
which Makina position queued the redemption, and it accumulates per owner:

```solidity
userEscrowedShares[owner_] += shares_;   // WithdrawalManagerQueue._addRequest
```

Two dusd positions redeem through syrupUSDC's manager `0x1bc47a0Dd0FdaB96E9eF982fdf1F34DC6207cfE3`:

| Position                       | id                                        |
| ------------------------------ | ----------------------------------------- |
| syrupUSDC/RLUSD Morpho Loop    | `813730204756382920165748392016574839201` |
| Royco Junior Tranche syrupUSDC | `324471518229524566118053937012927109991` |

Both ACCOUNTING blueprints read that one slot and booked it **in full**. Consequences:

- One pending redemption is already counted twice — **simultaneity is not required**.
- A fully unwound loop still reports the sibling's escrow as its own value, because its
  equity leg is `add(max(0, collateral − debt), escrow)` and collapses to `add(0, escrow)`.
- `accountForPositionBatch` carries no `_checkPositionMaxDelta` (that guard lives in
  `_managePosition`), so the inflated value is accepted silently.

No on-chain fix exists. Every request is the same `owner`, so `requestIds` / `requestsByOwner`
are owner-keyed too — the protocol cannot distinguish the positions. Attribution must come from
Makina-side state.

## Design

Keep a weight per position and a shared cumulative total in the caliber's KV store, and book

```
my_escrow = mulDiv(E, wP, max(wT, 1))
      E   = WM.userEscrowedShares(caliber)     # LIVE aggregate
      wP  = KV[position_key]                   # this position's requested shares
      wT  = KV[total_key]                      # shared total for THIS withdrawal manager
```

### Why it works

Two properties do all the work. Both follow from `E` being the **multiplicand** rather than a
stored amount.

**1. The weights cannot move the total.** With the invariant `wT == Σ wP` and `wT > 0`:

```
Σ_P mulDiv(E, wP, wT) = Σ_P floor(E·wP / wT) = E − r,   0 ≤ r ≤ n−1
```

The terms sum to the live aggregate for **any** weights. The weights are a _split key_ only.
Therefore a stale or even wrong weight misattributes between positions but **cannot inflate NAV**.
This is what reduces the reconcile from a trust boundary to a reporting nicety.

Rounding is always _downward_ (`floor`), so the sum can only undershoot, never overshoot.

**2. Self-clearing.** Maple's `_processRequest` decrements escrow and calls `pool.redeem` in the
same transaction, so `E → 0` exactly when the USDC lands. Since `E` multiplies every term,
settlement drives all terms to 0 **regardless of how stale the KV is**.

### The invariant

`wT == Σ wP`. It is maintained by writing `wP += δ` and `wT += δ` with the **same δ** inside one
weiroll action — atomic per tx, and read-modify-write composes across serial txs like any ERC20
balance. If `wT` ever drifts _below_ `Σ wP`, then `Σ terms > E` and the double count returns.
If it drifts _above_, NAV is understated (safe direction).

### Key namespacing

- `total_key` MUST be identical across every position sharing a withdrawal manager. A mismatch
  gives each position `wT == wP`, hence `term == E` for all of them — the **full double count**,
  silently.
- `total_key` MUST differ across withdrawal managers. dusd also runs a syrupUSDT loop on
  `0x86eBDf902d800F2a82038290B6DBb2A5eE29eB8C`, a separate accumulator; sharing one key would
  prorate syrupUSDC's escrow by syrupUSDT's weights.
- KV stores are **per caliber** (dusd `0xa81fC382…`, tstUSDC3 `0x7f49f751…`), so keys need no
  caliber namespace and the same strings are safely reused across calibers.

Keys are `keccak256` of a namespace string, precomputed as bytes32 vars because the transpiler
cannot resolve `${position.*}` inside `keccak256()`:

| Preimage                                           | Key                                                                  |
| -------------------------------------------------- | -------------------------------------------------------------------- |
| `maple.mainnet.syrupusdc.escrow_total`             | `0xae849168e6d7749681faf272835a2e925066d5475dc8b36e32c1cb9f2f5e6160` |
| `maple.mainnet.syrupusdc.escrow.morpho_loop_rlusd` | `0x9f4ab16ad4a68f81d7d1de9e18ed36b4f81549e155d78736e322e200f0b5c563` |
| `maple.mainnet.syrupusdc.escrow.royco_jt`          | `0x7276e080a62efc9f57da5b928414fda8c105e83889c29b89e1b6735375aba616` |

### The reconcile, and why it is guarded

`release_maple_escrow_weight` zeroes `wP` and decrements `wT` by the same amount, **guarded on
`userEscrowedShares(caliber) == 0`**.

The guard is not defensive dressing. Releasing while other escrow is still pending would drop
this position's phantom term in a single step — e.g. 33,333 shares (~39,225 USDC) on a ~$232k
position — and revert on `maxPositionDecreaseLossBps`, i.e. precisely in the branch where the
reconcile is wanted. With `E == 0` every term is already 0, so the action is **value-neutral**
and cannot trip the check. It also makes the operating rule enforced on-chain rather than
documented.

Skipping the reconcile is NAV-safe by property 1; it only restores exact attribution.

### Known limitation

Between settlement and reconcile, attribution is approximate while the total stays exact. The
residual cannot be closed on-chain: deducing how much of a drop in `E` was _this_ position's
requires the attribution the protocol does not expose, and the queue is global across all Maple
LPs so FIFO does not recover it. Closing it exactly needs an operator-supplied number — which,
by property 1, can only misattribute, never inflate.

## Value neutrality — why the escrow leg uses the market oracle

`withdraw_collateral_and_request_maple_redeem` receives **no base tokens**: it converts Morpho
collateral into Maple escrow, both position-internal. `_managePosition` therefore compares the
position value change against an affected-token change of **zero** (`Caliber.sol:711-715`):

```solidity
} else {                                   // no affected-token inflow
    if (change != 0 && isDebt == isPositionIncrease) {   // isDebt=false ⇒ true iff DECREASE
        _checkPositionMaxDelta(absChange, 0, maxLossBps);
        //  maxChange = 0 * (MAX_BPS + bps) / MAX_BPS = 0  ⇒ any decrease reverts
    }
}
```

A 1-wei decrease reverts exactly as hard as a large one — it is an infinite relative loss — and
`maxPositionDecreaseLossBps` is irrelevant, since 500 bps of zero is zero. A change of exactly 0
skips the branch entirely. So the action **requires** value neutrality; it is not a nicety.

Two things originally broke it, both fixed in this blueprint:

1. **Different valuation sources.** The collateral leg used the Morpho oracle while the escrow leg
   used `pool.convertToExitAssets` plus a decimal bridge, leaving a ~1.8 bps basis. The escrow leg
   now uses the **same market oracle** (`mulDiv(shares, oracle.price(), 1e36)`), so removing X of
   collateral and escrowing X cancels to the wei. This also deleted the `escrow_scale_mul/div`
   inputs — the oracle price already carries the `1e36 * 10^loanDec / 10^collDec` scaling.
2. **Pending Morpho interest.** `withdrawCollateral` accrues interest between the pre- and
   post-accounting of the same `managePosition` call, so the position "lost" that interest with no
   inflow to justify it. The accounting now calls `Morpho.accrueInterest` up front, so both
   readings see the same debt. (The market-params tuple must be rebuilt element by element —
   `accrueInterest` takes a static tuple, and passing the raw `idToMarketParams` return bytes
   misaligns the calldata and Morpho rejects it with "market not created".)

Relying on a favourable basis instead would have been fragile in the worst way:
`convertToExitAssets` subtracts `unrealizedLosses` while the oracle does not, so a Maple pool
taking losses inverts the sign and **no withdrawal size** succeeds — exactly when exiting matters.
The 1.8 bps is not lost, only recognised later: settlement pays USDC at Maple NAV and that lands
as a base token.

Measured on the vtestnet: 10,000 syrupUSDC withdrawn and escrowed moved the position by
**+0.031 USDC on 11,768 USDC**, i.e. 0.0003% — versus the 1.8 bps that previously reverted it.

Note the caliber's 60s `cooldownDuration`: `executionHash` keys on `(positionId, commands,
direction)` and the amount lives in `state`, not `commands`, so two native redeems on the same
position inside 60s collide with `OngoingCooldown`.

## Alternatives rejected

**syrupUSDC as a base token, with the exit split into two actions** (withdraw-to-caliber, then
request-redeem) so each leg has a real base-token flow to justify its value change. Rejected:
syrupUSDC cannot be a base token on this caliber. The oracle-priced escrow leg above achieves the
same end — a slippage check that passes deterministically — without touching the base-token set.

**Stored escrow amount in KV** (the obvious KV design). Rejected: it is _worse than the bug_.
`userEscrowedShares` is atomically self-clearing; a stored amount is not. From settlement until
manual cleanup the caliber counts the received USDC **and** the stale amount. Measured on the
vtestnet run below: it would have booked **147,106.683550 + 58,842.673420 USDC** of phantom on
top of the **206,005.108020 USDC** actually received — roughly 100% inflation across the pair,
persisting indefinitely and needing no second position to trigger.

**Derive `wT` by reading every sibling's key** instead of storing it. Safe by construction, but
O(n²) wiring: every position hardcodes every sibling's key, so adding a third means editing all
the existing ones. Rejected in favour of the stored cumulative total once it was established
that paired writes cannot come apart (atomic per tx; no interleaving between serial txs).

**One designated native redeemer**, the other exiting via the DEX aggregator. Genuinely
independent positions, zero new machinery, ~3bps of exit basis on the non-redeemer. Viable and
preferable at n ≤ 2; rejected because dusd is already at three Maple-queue positions across two
managers and the aggregator cost compounds while this is one-time.

**A second mainnet caliber** so the owners differ. Clean, but `machines/*/config.toml` keys
calibers per chain (`[calibers.mainnet]`), so this is a deployment change, not a config one.

## Implementation

| File                                                                 | Change                                                            |
| -------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `blueprints/morpho-loop/maple/withdraw-maple-redeem-attributed.yaml` | **new** — request + paired writes, and the guarded release        |
| `blueprints/morpho-loop/maple/account-equity.yaml`                   | prorated term                                                     |
| `blueprints/royco/jt-syrupusdc/withdraw.yaml`                        | paired writes + guarded release                                   |
| `blueprints/royco/jt-syrupusdc/account.yaml`                         | prorated term                                                     |
| `instructions/morpho-loop-swap-maple.yaml`                           | entry 10 repointed, entry 11 (reconcile), KV inputs on accounting |
| `instructions/royco-jt-syrupusdc.yaml`                               | KV inputs, reconcile entry                                        |
| `machines/dusd/mainnet/caliber.yaml`                                 | keys on both positions; constraint box replaced                   |
| `machines/tstUSDC3/mainnet/caliber.yaml`                             | keys on its JT position                                           |

`withdraw-maple-redeem-attributed.yaml` is a **new file** rather than an edit so the live
syrupUSDT/USDT loop keeps `withdraw-maple-redeem.yaml` byte-identical.

tstUSDC3's JT is the only escrow reader on that caliber (its two syrupUSDC Morpho loops use the
swap variant, which has no escrow term), so the prorate degenerates to the identity
`mulDiv(E, wP, wP) == E` — behaviour-neutral there.

**Two mainnet math helpers have opposite `sub()` argument order** and both are in play here:
`0x836C9007DbD73fcFC473190304C72b7E39BaBb91` (dusd caliber config) is `b − a`, while
`0x3D623B199E290358416415eA7e05B635E442e3c0` (Royco blueprint constants) is `a − b`. The two
release actions pass their operands accordingly; a static test pins it.

## Verification

### Model + branch tests — `tests/test_maple_escrow_prorate.py` (38 tests)

Reference model in `scripts/maple_escrow_prorate.py` mirrors the on-chain sequence exactly
(floor `mulDiv`, `max(wT,1)` guard). Coverage: idle, single request, simultaneous requests,
sibling-request neutrality, partial settlement, partial fill of one request, reconcile,
maximally stale KV, unattributed escrow, surplus absorption, release clamping, wrong reconcile,
repeat-request accumulation, three positions, rounding bounds, and both directions of a broken
invariant. Plus a 400-trial randomised lifecycle fuzz asserting every invariant after every step.

Static checks on the emitted call chains catch what the model cannot see: paired deltas, which
key each `set()` targets, per-helper `sub()` argument order, the denominator guard, and a config
guard that fails if the two positions' total keys ever diverge.

### On-chain — Tenderly vtestnet `7f2aa39d-11a7-4227-be5d-381fa636db65`

Live contracts, dusd caliber impersonated. Amounts in syrupUSDC shares (6 dec).

| Branch                                   | E    | wLoop | wJT | loop  | jt    | Σ  | raw-aggregate design |
| ---------------------------------------- | ---- | ----- | --- | ----- | ----- | -- | -------------------- |
| idle (guard passes, no revert at `wT=0`) | 0    | 0     | 0   | 0     | 0     | 0  | 0                    |
| loop requests 100k                       | 100k | 100k  | 0   | 100k  | 0     | =E | 200k                 |
| JT also requests 50k                     | 150k | 100k  | 50k | 100k  | 50k   | =E | 300k                 |
| loop repeats +25k                        | 175k | 125k  | 50k | 125k  | 50k   | =E | 350k                 |
| settled, KV untouched                    | 0    | 125k  | 50k | **0** | **0** | 0  | —                    |

Also confirmed:

- `revertIfFalse` reverts (`0x925139b3`) while escrow is pending, and passes at `E == 0`.
- `mulDiv(x, 0, 0)` reverts with **Panic 0x12**, so the `max(wT,1)` guard is load-bearing — the
  idle state is the common state.
- Real delegate-driven settlement: `processRedemptions` as pool delegate
  `0xC1e18FFD8825FfB286D177DDEbeba345EC70B49f`, queue head 17072 → 17089, `E → 0`, caliber
  received **206,005.108020 USDC** for 175,000 shares.
- Paired decrement with correct per-helper `sub()` order returned the keys to 0 / 0 / 0.
- Repeat requests accumulate per owner, matching `userEscrowedShares[owner] += shares`.

## Reviewer checklist

```bash
# model + branch + wiring + config-key tests
uv run --with pytest --with pyyaml pytest tests/test_maple_escrow_prorate.py -v

# the two helpers really do disagree on sub()
cast call 0x3D623B199E290358416415eA7e05B635E442e3c0 "sub(uint256,uint256)(uint256)" 5 3 --rpc-url $MAINNET_RPC_URL  # 2
cast call 0x836C9007DbD73fcFC473190304C72b7E39BaBb91 "sub(uint256,uint256)(uint256)" 5 3 --rpc-url $MAINNET_RPC_URL  # Panic 0x11

# the guard is required
cast call 0x836C9007DbD73fcFC473190304C72b7E39BaBb91 "mulDiv(uint256,uint256,uint256)(uint256)" 100 0 0 --rpc-url $MAINNET_RPC_URL  # Panic 0x12

# keys match their preimages
cast keccak "maple.mainnet.syrupusdc.escrow_total"
cast keccak "maple.mainnet.syrupusdc.escrow.morpho_loop_rlusd"
cast keccak "maple.mainnet.syrupusdc.escrow.royco_jt"

# the two positions share one total key, and syrupUSDT does not
grep -n "maple_escrow_" machines/dusd/mainnet/caliber.yaml
```

Worth reviewing closely:

1. Both `set()` calls in each request path use the **same delta** — the invariant depends on it.
2. The release action zeroes the **position** key (not the total) and decrements the total by the
   old weight.
3. `maple_escrow_total_key` is byte-identical on both dusd positions.
4. The syrupUSDT loop is untouched and shares no key.

## Operational notes

- **Deploy only while `userEscrowedShares(caliber) == 0`.** Escrow predating the KV writes has no
  weight and would book as 0 (NAV understated) until it settles. Verified 0 on dusd
  (`0xD1A1C248…`) and tstUSDC3 (`0xAc9c5477…`) on 2026-08-05.
- Simultaneous pending redemptions across positions are now **permitted**.
- `release_maple_escrow_weight` is a new MANAGEMENT entry someone must call to restore exact
  attribution. Nothing breaks if it is never called.
- The transpiler has **not** been run against these files. `instructions/` is a `GLOBAL_PREFIX`,
  so the gate re-transpiles broadly.

## Related

- `.claude/blueprint-helpers.md` — helper contracts, including the `sub()` divergence
- `docs/superpowers/specs/2026-05-08-royco-junior-tranches-design.md` — Royco tranche design
