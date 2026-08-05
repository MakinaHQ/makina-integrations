#!/usr/bin/env python3
"""Reference model for the Maple escrow prorate scheme ("design A").

Maple's `WithdrawalManager.userEscrowedShares` is keyed on the OWNER (the
caliber), not on which Makina position fed the queue. When two or more
positions on one caliber redeem through the same withdrawal manager, each of
their ACCOUNTING blueprints reads the same aggregate and books it in full ->
NAV is overstated by one extra copy per extra reader.

The protocol exposes no per-position attribution (every request is the same
`owner`), so the split has to come from Makina-side state. This model mirrors
the on-chain scheme:

    E      = WM.userEscrowedShares(caliber)        # live aggregate, syrupUSDC shares
    wP     = KV.get(position_key)                  # this position's weight
    wT     = KV.get(total_key)                     # shared cumulative total
    wTsafe = max(wT, 1)                            # mulDiv(x, 0, 0) reverts (Panic 0x12)
    sP     = mulDiv(E, wP, wTsafe)                 # floor division

Two properties do the real work:

1. `E` is the multiplicand, so the terms are fractions of something real. As
   long as `wT == sum(wP)`, `sum(sP) == E` (modulo floor rounding) for ANY
   weights. The weights are a SPLIT KEY only -- they cannot move the total.
   A wrong reconcile misattributes between positions; it cannot inflate NAV.

2. Settlement drives `E` to 0, which drives every `sP` to 0 regardless of how
   stale the KV is. The scheme is self-clearing, which a stored escrow AMOUNT
   would not be.

The single invariant that must hold is `wT == sum(wP)`. It is maintained by
writing `wP += d` and `wT += d` in the same weiroll action (atomic per tx, and
read-modify-write composes across serial txs). If `wT` ever drifts BELOW
`sum(wP)`, `sum(sP) > E` and the double-count returns -- see
`test_broken_invariant_wt_too_low_inflates`.

Used by tests/test_maple_escrow_prorate.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

UINT256_MAX = 2**256 - 1


def mul_div(a: int, b: int, denominator: int) -> int:
    """Mirror of the unsigned math helper's mulDiv: floor((a * b) / denominator).

    Reverts (Panic 0x12) on a zero denominator, like the on-chain helper.
    """
    if denominator == 0:
        raise ZeroDivisionError("Panic 0x12: division by zero")
    return (a * b) // denominator


def prorate(escrow_aggregate: int, position_weight: int, stored_total: int) -> int:
    """This position's share of the caliber-wide escrow.

    Exact mirror of the accounting call sequence, including the max(wT, 1)
    guard. Without the guard the idle state (wT == 0) reverts -- and idle is
    the common state.
    """
    total_safe = max(stored_total, 1)
    return mul_div(escrow_aggregate, position_weight, total_safe)


@dataclass
class _Request:
    position: str
    shares: int


@dataclass
class MapleEscrowLedger:
    """Simulates one withdrawal manager's accumulator plus the KV state.

    Tracks `truth` (what each position actually has escrowed) alongside the
    modelled KV weights, so tests can distinguish "NAV correct" from
    "attribution correct".
    """

    positions: list[str]
    escrow_aggregate: int = 0
    weights: dict[str, int] = field(default_factory=dict)
    stored_total: int = 0
    truth: dict[str, int] = field(default_factory=dict)
    queue: list[_Request] = field(default_factory=list)

    def __post_init__(self) -> None:
        for p in self.positions:
            self.weights.setdefault(p, 0)
            self.truth.setdefault(p, 0)

    # ---- operations -----------------------------------------------------

    def request(self, position: str, shares: int) -> None:
        """MANAGEMENT: requestRedeem + the paired KV writes (wP += x, wT += x)."""
        self.escrow_aggregate += shares
        self.truth[position] += shares
        self.queue.append(_Request(position, shares))
        # Paired write -- same weiroll action, so these cannot come apart.
        self.weights[position] += shares
        self.stored_total += shares

    def settle(self, shares: int) -> int:
        """Maple's delegate processes `shares` off the front of our own queue.

        Requests settle in the order they were made (the global queue is
        FIFO by request id), and a single request can be partially filled.
        Escrow and truth move; the KV weights do NOT -- that is the whole
        source of the transient attribution error.
        """
        remaining = min(shares, self.escrow_aggregate)
        settled = remaining
        while remaining > 0 and self.queue:
            head = self.queue[0]
            take = min(remaining, head.shares)
            head.shares -= take
            self.truth[head.position] -= take
            self.escrow_aggregate -= take
            remaining -= take
            if head.shares == 0:
                self.queue.pop(0)
        return settled

    def release(self, position: str, shares: int) -> int:
        """MANAGEMENT: paired decrement, clamped so wP cannot underflow.

        Pass UINT256_MAX to release everything this position still holds.
        """
        effective = min(shares, self.weights[position])
        self.weights[position] -= effective
        # Safe because the invariant gives stored_total >= weights[position].
        if effective > self.stored_total:
            raise AssertionError("stored_total underflow -- invariant was already broken")
        self.stored_total -= effective
        return effective

    # ---- reads ----------------------------------------------------------

    def account(self, position: str) -> int:
        """ACCOUNTING: this position's escrow term, in syrupUSDC shares."""
        return prorate(self.escrow_aggregate, self.weights[position], self.stored_total)

    def account_all(self) -> dict[str, int]:
        return {p: self.account(p) for p in self.positions}

    def booked_total(self) -> int:
        return sum(self.account_all().values())

    # ---- invariants -----------------------------------------------------

    def weights_sum(self) -> int:
        return sum(self.weights.values())

    def check_invariants(self) -> None:
        """Assert the properties that must hold after every operation."""
        n = len(self.positions)

        # The structural invariant, maintained by paired writes.
        assert self.stored_total == self.weights_sum(), (
            f"stored_total {self.stored_total} != sum(weights) {self.weights_sum()}"
        )

        booked = self.booked_total()

        # INV1 -- never inflate. The property the whole design exists for.
        assert booked <= self.escrow_aggregate, (
            f"booked {booked} > escrow {self.escrow_aggregate}"
        )

        # INV2 -- exact up to floor rounding whenever any weight is recorded.
        if self.stored_total > 0:
            assert booked >= self.escrow_aggregate - (n - 1), (
                f"booked {booked} lost more than {n - 1} wei vs {self.escrow_aggregate}"
            )

        # INV3 -- self-clearing: settled escrow books nothing, however stale the KV.
        if self.escrow_aggregate == 0:
            assert booked == 0, f"escrow 0 but booked {booked}"

        # INV4 -- no position can book more than the whole aggregate.
        for p in self.positions:
            assert self.account(p) <= self.escrow_aggregate

        # Sanity on the truth model itself.
        assert sum(self.truth.values()) == self.escrow_aggregate
        assert all(v >= 0 for v in self.truth.values())

    def in_sync(self) -> bool:
        """True when the KV weights match reality, i.e. attribution is exact."""
        return all(self.weights[p] == self.truth[p] for p in self.positions)
