"""Tests for scripts/maple_escrow_prorate.py -- the Maple escrow split scheme.

Covers the full position lifecycle across the branches that matter:
request, sibling request, partial settlement, full settlement, reconcile,
maximally stale KV, unattributed escrow, rounding, and 3+ positions. Plus a
randomised lifecycle fuzz that re-checks every invariant after every step.

The headline properties under test:
  * sum of booked escrow can NEVER exceed the live aggregate (no double count)
  * sum EQUALS the aggregate (modulo floor rounding) whenever any weight is set
  * settlement self-clears every term, however stale the KV
  * a wrong reconcile misattributes but cannot inflate

The last test group is a config guard: the shared total key is what makes the
scheme safe, so a typo that gives two positions DIFFERENT total keys would
silently restore the full double count.
"""
from __future__ import annotations

import importlib.util
import random
import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "maple_escrow_prorate.py"

SPEC = importlib.util.spec_from_file_location("maple_escrow_prorate", MODULE_PATH)
maple_escrow_prorate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = maple_escrow_prorate
SPEC.loader.exec_module(maple_escrow_prorate)

MapleEscrowLedger = maple_escrow_prorate.MapleEscrowLedger
prorate = maple_escrow_prorate.prorate
mul_div = maple_escrow_prorate.mul_div
UINT256_MAX = maple_escrow_prorate.UINT256_MAX

# syrupUSDC shares are 6-decimal.
K = 1_000_000_000  # 1,000 shares

LOOP = "syrupUSDC/RLUSD loop"
JT = "Royco JT-syrupUSDC"


class ProrateFormulaTests(unittest.TestCase):
    """The formula itself, including the guard that keeps idle from reverting."""

    def test_idle_state_does_not_revert(self) -> None:
        # mulDiv(E, 0, 0) reverts on-chain with Panic 0x12; the max(wT, 1)
        # guard is what keeps the COMMON state (nothing pending) accountable.
        self.assertEqual(prorate(0, 0, 0), 0)
        self.assertEqual(prorate(100 * K, 0, 0), 0)

    def test_unguarded_muldiv_would_revert(self) -> None:
        with self.assertRaises(ZeroDivisionError):
            mul_div(100 * K, 0, 0)

    def test_matches_onchain_muldiv_fixture(self) -> None:
        # Verified against the live helper 0x836C9007...BaBb91:
        #   mulDiv(50000e6, 100000e6, 150000e6) = 33333333333
        # syrupUSDC is 6-decimal, so 50,000 shares == 50_000 * 10**6.
        self.assertEqual(
            mul_div(50_000 * 10**6, 100_000 * 10**6, 150_000 * 10**6), 33_333_333_333
        )

    def test_floor_never_rounds_up(self) -> None:
        for e, w, t in [(7, 3, 10), (1, 1, 3), (999, 333, 1000)]:
            self.assertLessEqual(prorate(e, w, t) * t, e * w)


class LifecycleBranchTests(unittest.TestCase):
    """One test per branch of the two-position lifecycle."""

    def setUp(self) -> None:
        self.ledger = MapleEscrowLedger(positions=[LOOP, JT])

    def test_branch_0_idle(self) -> None:
        self.ledger.check_invariants()
        self.assertEqual(self.ledger.account_all(), {LOOP: 0, JT: 0})

    def test_branch_1_single_request_is_exactly_attributed(self) -> None:
        self.ledger.request(LOOP, 100 * K)
        self.ledger.check_invariants()
        # The loop owns all of it; the JT books nothing. Under the old scheme
        # the JT would have booked the full 100k as its own value.
        self.assertEqual(self.ledger.account(LOOP), 100 * K)
        self.assertEqual(self.ledger.account(JT), 0)
        self.assertTrue(self.ledger.in_sync())

    def test_branch_2_simultaneous_requests_are_exact(self) -> None:
        # Forbidden under the old design; correct under this one.
        self.ledger.request(LOOP, 100 * K)
        self.ledger.request(JT, 50 * K)
        self.ledger.check_invariants()
        self.assertEqual(self.ledger.account(LOOP), 100 * K)
        self.assertEqual(self.ledger.account(JT), 50 * K)
        self.assertEqual(self.ledger.booked_total(), 150 * K)

    def test_branch_3_sibling_request_does_not_move_my_term(self) -> None:
        self.ledger.request(LOOP, 100 * K)
        before = self.ledger.account(LOOP)
        self.ledger.request(JT, 50 * K)
        after = self.ledger.account(LOOP)
        # E and wT grow by the same amount, so an unrelated position opening a
        # redemption leaves my value untouched.
        self.assertEqual(before, after)
        self.ledger.check_invariants()

    def test_branch_4_partial_settlement_preserves_nav_not_attribution(self) -> None:
        self.ledger.request(LOOP, 100 * K)
        self.ledger.request(JT, 50 * K)
        # Maple settles the loop's request in full; KV not yet reconciled.
        self.ledger.settle(100 * K)
        self.ledger.check_invariants()

        self.assertEqual(self.ledger.escrow_aggregate, 50 * K)
        # NAV is exact to within the floor-rounding loss, which is always
        # DOWNWARD: both terms floor, so the sum is E - 1 here, never E + 1.
        self.assertEqual(self.ledger.booked_total(), 50 * K - 1)
        # ...but the split is wrong, and wrong in a bounded, transient way.
        self.assertEqual(self.ledger.account(LOOP), 33_333_333_333)
        self.assertEqual(self.ledger.account(JT), 16_666_666_666)
        self.assertEqual(self.ledger.truth[LOOP], 0)
        self.assertEqual(self.ledger.truth[JT], 50 * K)
        self.assertFalse(self.ledger.in_sync())

    def test_branch_5_reconcile_restores_exactness(self) -> None:
        self.ledger.request(LOOP, 100 * K)
        self.ledger.request(JT, 50 * K)
        self.ledger.settle(100 * K)
        self.ledger.release(LOOP, UINT256_MAX)  # release-all
        self.ledger.check_invariants()

        self.assertEqual(self.ledger.account(LOOP), 0)
        self.assertEqual(self.ledger.account(JT), 50 * K)
        self.assertTrue(self.ledger.in_sync())

    def test_branch_6_fully_settled_stale_kv_self_clears(self) -> None:
        self.ledger.request(LOOP, 100 * K)
        self.ledger.request(JT, 50 * K)
        self.ledger.settle(150 * K)
        # Operator never reconciled: weights still carry the full amounts.
        self.assertEqual(self.ledger.weights[LOOP], 100 * K)
        self.assertEqual(self.ledger.weights[JT], 50 * K)
        self.ledger.check_invariants()
        # Nothing is booked anyway. This is the branch a stored escrow AMOUNT
        # would get wrong -- it would keep booking 150k on top of the USDC
        # that has already landed in the caliber.
        self.assertEqual(self.ledger.booked_total(), 0)

    def test_branch_7_unattributed_escrow_understates(self) -> None:
        # Escrow created outside both instrumented paths: no weights exist.
        self.ledger.escrow_aggregate = 80 * K
        self.ledger.truth[LOOP] = 80 * K  # keep the truth model consistent
        self.ledger.queue.append(maple_escrow_prorate._Request(LOOP, 80 * K))
        booked = self.ledger.booked_total()
        # Wrong, but in the safe direction -- understated, never overstated.
        self.assertEqual(booked, 0)
        self.assertLess(booked, self.ledger.escrow_aggregate)
        self.ledger.check_invariants()

    def test_branch_7b_surplus_escrow_is_absorbed_not_lost(self) -> None:
        # If ANY position holds weight, a surplus gets absorbed into the split
        # rather than vanishing -- sum still equals the aggregate.
        self.ledger.request(LOOP, 100 * K)
        self.ledger.escrow_aggregate += 80 * K  # surplus with no weight
        self.ledger.truth[JT] += 80 * K
        self.ledger.queue.append(maple_escrow_prorate._Request(JT, 80 * K))
        self.assertEqual(self.ledger.booked_total(), 180 * K)
        self.ledger.check_invariants()

    def test_branch_8_release_clamps_and_cannot_underflow(self) -> None:
        self.ledger.request(JT, 40 * K)
        # Releasing more than held is clamped, not reverted.
        released = self.ledger.release(JT, 999 * K)
        self.assertEqual(released, 40 * K)
        self.assertEqual(self.ledger.weights[JT], 0)
        self.assertEqual(self.ledger.stored_total, 0)
        # Releasing again is a no-op.
        self.assertEqual(self.ledger.release(JT, 10 * K), 0)
        self.ledger.check_invariants()

    def test_branch_9_wrong_reconcile_misattributes_but_cannot_inflate(self) -> None:
        self.ledger.request(LOOP, 100 * K)
        self.ledger.request(JT, 50 * K)
        self.ledger.settle(100 * K)
        # Operator supplies a wrong number (releases 70k instead of 100k).
        self.ledger.release(LOOP, 70 * K)
        self.ledger.check_invariants()
        # NAV still exact; only the split is off.
        self.assertEqual(self.ledger.booked_total(), 50 * K)
        self.assertFalse(self.ledger.in_sync())

    def test_partial_fill_of_a_single_request(self) -> None:
        self.ledger.request(LOOP, 100 * K)
        self.ledger.settle(30 * K)  # queue partially filled
        self.ledger.check_invariants()
        self.assertEqual(self.ledger.escrow_aggregate, 70 * K)
        self.assertEqual(self.ledger.booked_total(), 70 * K)

    def test_repeat_requests_accumulate(self) -> None:
        # Maple's _addRequest does `userEscrowedShares[owner] += shares`, one
        # linked-list entry per request; the weights must accumulate the same way.
        self.ledger.request(LOOP, 10 * K)
        self.ledger.request(LOOP, 25 * K)
        self.assertEqual(self.ledger.weights[LOOP], 35 * K)
        self.assertEqual(self.ledger.account(LOOP), 35 * K)
        self.ledger.check_invariants()


class ThreePositionTests(unittest.TestCase):
    """The n>2 case: adding a position must not require touching the others."""

    def setUp(self) -> None:
        self.ledger = MapleEscrowLedger(positions=["A", "B", "C"])

    def test_three_way_exact_when_in_sync(self) -> None:
        self.ledger.request("A", 100 * K)
        self.ledger.request("B", 50 * K)
        self.ledger.request("C", 50 * K)
        self.ledger.check_invariants()
        self.assertEqual(self.ledger.account_all(), {"A": 100 * K, "B": 50 * K, "C": 50 * K})

    def test_three_way_smear_on_partial_settlement(self) -> None:
        self.ledger.request("A", 100 * K)
        self.ledger.request("B", 50 * K)
        self.ledger.request("C", 50 * K)
        self.ledger.settle(100 * K)  # A settles in full
        self.ledger.check_invariants()
        # The misattribution spreads across all three, but the total is exact.
        self.assertEqual(self.ledger.booked_total(), 100 * K)
        self.assertEqual(self.ledger.account("A"), 50 * K)
        self.assertEqual(self.ledger.account("B"), 25 * K)
        self.assertEqual(self.ledger.account("C"), 25 * K)

    def test_rounding_loss_bounded_by_n_minus_1(self) -> None:
        # Weights chosen so the division does not divide evenly.
        self.ledger.request("A", 1)
        self.ledger.request("B", 1)
        self.ledger.request("C", 1)
        self.ledger.settle(1)  # aggregate 2, total weight 3
        booked = self.ledger.booked_total()
        self.assertLessEqual(booked, 2)
        self.assertGreaterEqual(booked, 2 - 2)
        self.ledger.check_invariants()


class BrokenInvariantTests(unittest.TestCase):
    """Why the paired write matters: this is the only way to reintroduce the bug."""

    def test_broken_invariant_wt_too_low_inflates(self) -> None:
        ledger = MapleEscrowLedger(positions=[LOOP, JT])
        ledger.request(LOOP, 100 * K)
        ledger.request(JT, 50 * K)
        # Simulate a blueprint bug: a weight written without its total delta.
        ledger.stored_total -= 50 * K
        booked = ledger.booked_total()
        self.assertGreater(booked, ledger.escrow_aggregate)  # double count is back
        with self.assertRaises(AssertionError):
            ledger.check_invariants()

    def test_broken_invariant_wt_too_high_understates(self) -> None:
        ledger = MapleEscrowLedger(positions=[LOOP, JT])
        ledger.request(LOOP, 100 * K)
        ledger.stored_total += 100 * K
        # Understates rather than inflates -- the safe direction of the bug.
        self.assertLess(ledger.booked_total(), ledger.escrow_aggregate)
        with self.assertRaises(AssertionError):
            ledger.check_invariants()


class LifecycleFuzzTests(unittest.TestCase):
    """Randomised lifecycles; every invariant re-checked after every step."""

    def test_fuzz_random_lifecycles(self) -> None:
        rng = random.Random(20260805)
        for trial in range(400):
            n = rng.randint(2, 4)
            names = [f"p{i}" for i in range(n)]
            ledger = MapleEscrowLedger(positions=names)
            for _step in range(rng.randint(1, 25)):
                op = rng.choices(
                    ["request", "settle", "release"], weights=[5, 3, 2], k=1
                )[0]
                if op == "request":
                    ledger.request(rng.choice(names), rng.randint(1, 500) * K)
                elif op == "settle":
                    if ledger.escrow_aggregate:
                        ledger.settle(rng.randint(1, ledger.escrow_aggregate))
                else:
                    amount = rng.choice([UINT256_MAX, rng.randint(1, 500) * K])
                    ledger.release(rng.choice(names), amount)
                try:
                    ledger.check_invariants()
                except AssertionError as exc:  # pragma: no cover - diagnostic
                    self.fail(f"trial {trial} step {_step} ({op}): {exc}")

    def test_fuzz_exact_attribution_while_never_settling(self) -> None:
        # With no settlement, weights track truth exactly, so attribution must
        # be exact for every position at every step.
        rng = random.Random(7)
        for _trial in range(200):
            names = [f"p{i}" for i in range(rng.randint(2, 4))]
            ledger = MapleEscrowLedger(positions=names)
            for _step in range(rng.randint(1, 15)):
                ledger.request(rng.choice(names), rng.randint(1, 900) * K)
                ledger.check_invariants()
                self.assertTrue(ledger.in_sync())
                for p in names:
                    self.assertEqual(ledger.account(p), ledger.truth[p])


class _PermissiveLoader(yaml.SafeLoader):
    """YAML loader that ignores custom tags like !include.

    Derives from SafeLoader, so python/object tags remain unconstructible; the
    multi-constructor below only maps unknown "!" tags to None. Same pattern as
    scripts/validate_open_positions.py and scripts/validate_base_tokens.py.
    """


_PermissiveLoader.add_multi_constructor("!", lambda _loader, _suffix, _node: None)

# The two dusd mainnet positions that redeem through syrupUSDC's withdrawal
# manager 0x1bc47a0Dd0FdaB96E9eF982fdf1F34DC6207cfE3. Adding a third syrupUSDC
# position means adding it here too.
DUSD_SYRUPUSDC_POSITION_IDS = {
    "813730204756382920165748392016574839201",  # syrupUSDC/RLUSD Morpho Loop
    "324471518229524566118053937012927109991",  # Royco Junior Tranche syrupUSDC
}
EXPECTED_TOTAL_KEY = "0xae849168e6d7749681faf272835a2e925066d5475dc8b36e32c1cb9f2f5e6160"


class CaliberKeyWiringTests(unittest.TestCase):
    """Guards the wiring the whole scheme depends on.

    If two positions end up with DIFFERENT total keys, each prorates by its own
    weight alone (wT == wP), every term becomes the full aggregate, and the
    original double count is silently restored. This is the highest-value
    mechanical check in the suite.
    """

    @classmethod
    def setUpClass(cls) -> None:
        path = REPO_ROOT / "machines" / "dusd" / "mainnet" / "caliber.yaml"
        with path.open() as fh:
            cls.caliber = yaml.load(fh, Loader=_PermissiveLoader)
        cls.positions = cls.caliber.get("positions") or []

    def _escrow_positions(self) -> dict[str, dict]:
        out = {}
        for pos in self.positions:
            variables = pos.get("vars") or {}
            if "maple_escrow_position_key" in variables or "maple_escrow_total_key" in variables:
                out[str(pos["id"])] = variables
        return out

    def test_expected_positions_carry_the_keys(self) -> None:
        self.assertEqual(set(self._escrow_positions()), DUSD_SYRUPUSDC_POSITION_IDS)

    def test_keys_come_in_pairs(self) -> None:
        for pos_id, variables in self._escrow_positions().items():
            self.assertIn("maple_escrow_position_key", variables, pos_id)
            self.assertIn("maple_escrow_total_key", variables, pos_id)

    def test_all_syrupusdc_positions_share_one_total_key(self) -> None:
        totals = {v["maple_escrow_total_key"] for v in self._escrow_positions().values()}
        self.assertEqual(
            totals,
            {EXPECTED_TOTAL_KEY},
            "syrupUSDC positions must share exactly one total key or the double count returns",
        )

    def test_position_keys_are_distinct(self) -> None:
        keys = [v["maple_escrow_position_key"] for v in self._escrow_positions().values()]
        self.assertEqual(len(keys), len(set(keys)), "position weight keys must be unique")

    def test_position_keys_differ_from_total_key(self) -> None:
        for pos_id, variables in self._escrow_positions().items():
            self.assertNotEqual(
                variables["maple_escrow_position_key"],
                variables["maple_escrow_total_key"],
                pos_id,
            )

    def test_syrupusdt_loop_does_not_share_the_syrupusdc_key(self) -> None:
        # syrupUSDT uses withdrawal manager 0x86eBDf90...eB8C -- a separate
        # accumulator. It must never be prorated against syrupUSDC's total.
        for pos in self.positions:
            variables = pos.get("vars") or {}
            wm = str(variables.get("maple_withdrawal_manager_address", "")).lower()
            if wm and wm != "0x1bc47a0dd0fdab96e9ef982fdf1f34dc6207cfe3":
                self.assertNotEqual(
                    variables.get("maple_escrow_total_key"), EXPECTED_TOTAL_KEY
                )


POSITION_KEY_REF = "${inputs.maple_escrow_position_key}"
TOTAL_KEY_REF = "${inputs.maple_escrow_total_key}"

# (blueprint, request action, release action, sub(a,b) semantics of its helper)
#   "b-a" -> unsigned math helper 0x836C9007...BaBb91 (dusd/deth caliber config)
#   "a-b" -> unsigned math helper 0x3D623B19...e3c0   (royco blueprint constants)
ATTRIBUTED_WITHDRAW_BLUEPRINTS = [
    (
        "blueprints/morpho-loop/maple/withdraw-maple-redeem-attributed.yaml",
        "withdraw_collateral_and_request_maple_redeem",
        "release_maple_escrow_weight",
        "b-a",
    ),
    (
        "blueprints/royco/jt-syrupusdc/withdraw.yaml",
        "request_redeem",
        "release_maple_escrow_weight",
        "a-b",
    ),
]

ATTRIBUTED_ACCOUNT_BLUEPRINTS = [
    (
        "blueprints/morpho-loop/maple/account-equity.yaml",
        "account_equity_and_maple_withdrawal",
    ),
    ("blueprints/royco/jt-syrupusdc/account.yaml", "account"),
]


def _load_blueprint(rel_path: str) -> dict:
    with (REPO_ROOT / rel_path).open() as fh:
        return yaml.load(fh, Loader=_PermissiveLoader)


def _calls(blueprint: dict, action: str) -> list[dict]:
    return blueprint["actions"][action]["calls"]


def _by_selector(calls: list[dict], selector: str) -> list[dict]:
    return [c for c in calls if c.get("selector") == selector]


def _param_values(call: dict) -> list[str]:
    return [str(p.get("value")) for p in call.get("parameters", [])]


class BlueprintWiringTests(unittest.TestCase):
    """Static checks on the emitted call chains.

    The model tests cover the arithmetic; these cover the wiring the model
    cannot see -- a set() aimed at the wrong key, an unpaired delta, a reversed
    sub() for the helper in use, or a missing denominator guard.
    """

    def test_request_action_writes_both_keys(self) -> None:
        for rel_path, request_action, _release, _sub in ATTRIBUTED_WITHDRAW_BLUEPRINTS:
            with self.subTest(rel_path):
                calls = _calls(_load_blueprint(rel_path), request_action)
                sets = _by_selector(calls, "set(bytes32,bytes32)")
                written = [_param_values(c)[0] for c in sets]
                self.assertEqual(
                    sorted(written), sorted([POSITION_KEY_REF, TOTAL_KEY_REF])
                )

    def test_request_action_deltas_are_paired(self) -> None:
        # The wT == sum(wP) invariant lives or dies here: both add() calls must
        # apply the SAME delta.
        for rel_path, request_action, _release, _sub in ATTRIBUTED_WITHDRAW_BLUEPRINTS:
            with self.subTest(rel_path):
                calls = _calls(_load_blueprint(rel_path), request_action)
                adds = _by_selector(calls, "add(uint256,uint256)")
                self.assertEqual(len(adds), 2, "expected exactly two paired add() calls")
                deltas = []
                for call in adds:
                    operands = _param_values(call)
                    deltas.append([v for v in operands if not v.endswith("_before}")])
                self.assertEqual(len(deltas[0]), 1)
                self.assertEqual(deltas[0], deltas[1], "paired writes must share one delta")

    def test_release_zeroes_position_key_not_total(self) -> None:
        # The bug this test exists for: aiming the zero-write at the total key
        # wipes the shared accumulator and then underflows it.
        for rel_path, _request, release_action, _sub in ATTRIBUTED_WITHDRAW_BLUEPRINTS:
            with self.subTest(rel_path):
                calls = _calls(_load_blueprint(rel_path), release_action)
                sets = {_param_values(c)[0]: _param_values(c)[1] for c in
                        _by_selector(calls, "set(bytes32,bytes32)")}
                self.assertEqual(sets.get(POSITION_KEY_REF), "0")
                self.assertIn(TOTAL_KEY_REF, sets)
                self.assertNotEqual(sets.get(TOTAL_KEY_REF), "0")

    def test_release_is_guarded_on_drained_queue(self) -> None:
        # Without the guard the action moves position values and would revert on
        # maxPositionDecreaseLossBps in exactly the branch it is needed.
        for rel_path, _request, release_action, _sub in ATTRIBUTED_WITHDRAW_BLUEPRINTS:
            with self.subTest(rel_path):
                calls = _calls(_load_blueprint(rel_path), release_action)
                self.assertTrue(_by_selector(calls, "userEscrowedShares(address)"))
                self.assertTrue(_by_selector(calls, "eq(uint256,uint256)"))
                self.assertTrue(_by_selector(calls, "revertIfFalse(bool)"))

    def test_release_sub_argument_order_matches_its_helper(self) -> None:
        # Two mainnet math helpers have OPPOSITE sub() argument order. Getting
        # this backwards underflows (Panic 0x11) or corrupts the total.
        for rel_path, _request, release_action, sub_semantics in ATTRIBUTED_WITHDRAW_BLUEPRINTS:
            with self.subTest(rel_path):
                calls = _calls(_load_blueprint(rel_path), release_action)
                subs = _by_selector(calls, "sub(uint256,uint256)")
                self.assertEqual(len(subs), 1)
                first, second = _param_values(subs[0])
                if sub_semantics == "b-a":
                    # sub(a, b) = b - a, so (weight, total) yields total - weight.
                    self.assertIn("position_weight", first)
                    self.assertIn("escrow_total_before", second)
                else:
                    # sub(a, b) = a - b, so (total, weight) yields total - weight.
                    self.assertIn("escrow_total_before", first)
                    self.assertIn("position_weight", second)

    def test_accounting_guards_the_denominator(self) -> None:
        for rel_path, action in ATTRIBUTED_ACCOUNT_BLUEPRINTS:
            with self.subTest(rel_path):
                calls = _calls(_load_blueprint(rel_path), action)
                maxes = _by_selector(calls, "max(uint256,uint256)")
                guard = [c for c in maxes if "1" in _param_values(c)]
                self.assertTrue(guard, "missing max(total, 1) denominator guard")

    def test_accounting_prorates_aggregate_by_weights(self) -> None:
        for rel_path, action in ATTRIBUTED_ACCOUNT_BLUEPRINTS:
            with self.subTest(rel_path):
                calls = _calls(_load_blueprint(rel_path), action)
                muldivs = _by_selector(calls, "mulDiv(uint256,uint256,uint256)")
                prorates = [
                    c for c in muldivs
                    if "escrow_position_weight" in " ".join(_param_values(c))
                ]
                self.assertEqual(len(prorates), 1, "expected one prorate mulDiv")
                a, b, denominator = _param_values(prorates[0])
                # Multiplicand MUST be the live aggregate -- that is what makes
                # the terms sum to it and self-clear on settlement.
                self.assertIn("aggregate", a + b)
                self.assertIn("escrow_position_weight", a + b)
                self.assertIn("safe", denominator)

    def test_accounting_does_not_book_the_raw_aggregate(self) -> None:
        # Regression guard: the raw userEscrowedShares result must never flow
        # straight into convertToExitAssets again.
        for rel_path, action in ATTRIBUTED_ACCOUNT_BLUEPRINTS:
            with self.subTest(rel_path):
                calls = _calls(_load_blueprint(rel_path), action)
                aggregate_returns = {
                    c["return"]["name"]
                    for c in _by_selector(calls, "userEscrowedShares(address)")
                }
                for convert in _by_selector(calls, "convertToExitAssets(uint256)"):
                    for value in _param_values(convert):
                        for name in aggregate_returns:
                            self.assertNotEqual(value, "${returns.%s}" % name)


if __name__ == "__main__":
    unittest.main()
