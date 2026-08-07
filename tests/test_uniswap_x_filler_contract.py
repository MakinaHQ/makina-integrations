"""Guards the Uniswap-X Filler <-> Machine Contract (normative).

The filler's runtime ABI is not expressible in the type system, so these are the
tests that hold it. Two properties in particular have no other guard:

  * Slot indices come from the DECLARATION ORDER of a blueprint's `input_slots:`
    block, not from order of use. (Proven in the live mainnet rootfile: the aave
    buy consumes `stable_amount` in its FIRST call, yet the slot lands at index 2
    because it is declared third.) So a well-meaning alphabetical tidy of that
    block silently breaks every filler on the chain, and nothing else notices.

  * Parking is keyed by the STABLE label while fills are keyed by the STOCK label.
    Including a parking template from a per-stock template would therefore emit N
    identical `uniswapX/park_stable_in_<source>/{stable_label}` keys and collide.

What these tests deliberately do NOT cover: emitted slot indices and the `# root:`
hash. Both require running the transpiler, which happens in the release workflow
(.github/actions/transpile-validate). These assert the SOURCE invariants that
determine those outputs.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

# makina-x only: these blueprints have no core-Caliber consumer, so they live under
# blueprints-x/. Split fill vs park because the two halves have different slot ABIs.
BLUEPRINT_DIR = REPO_ROOT / "blueprints-x" / "uniswap-x"
FILL_BLUEPRINT = BLUEPRINT_DIR / "fill.yaml"
PARK_BLUEPRINT = BLUEPRINT_DIR / "park.yaml"

# Contract section 2 -- the canonical action names, and the slot layout each must
# expose per section 3. Order of the tuple IS the required declaration order.
CANONICAL_FILL_SLOTS = {
    "buy_stock_with_stable_direct": ("order", "signature", "stable_amount"),
    "buy_stock_with_stable_from_aave": ("order", "signature", "stable_amount"),
    "buy_stock_with_stable_from_morpho_vault": ("order", "signature", "stable_amount"),
    "sell_stock_for_stable_direct": ("order", "signature", "stock_amount"),
}
CANONICAL_PARKING_SLOTS = {
    "park_stable_in_aave": ("stable_amount",),
    "park_stable_in_morpho_vault": ("stable_amount",),
}
CANONICAL_ACTIONS = {**CANONICAL_FILL_SLOTS, **CANONICAL_PARKING_SLOTS}

# Contract section 2 -- migration-only names that must not appear in new sources.
LEGACY_ACTION_NAMES = (
    "buy_xstock_with_usdc_direct",
    "buy_xstock_with_usdc_from_aave",
    "sell_xstock_for_usdc_direct",
)

# Every contract-governed instruction template lives in this one directory, so the
# governed surface is enumerable rather than pattern-matched out of a flat folder.
TEMPLATE_DIR = REPO_ROOT / "instructions-x" / "uniswap-x"

PARKING_TEMPLATES = {
    "park-aave.yaml": "park_stable_in_aave",
    "park-morpho.yaml": "park_stable_in_morpho_vault",
}
FILL_TEMPLATES = ("fills-aave.yaml", "fills-morpho.yaml")


class _IncludeLoader(yaml.SafeLoader):
    """Caliber files use `!include`; resolve it to a marker rather than a file read.

    Subclasses SafeLoader and adds ONE constructor returning a plain dict, so the
    `yaml.load` calls below keep safe_load semantics -- `!!python/object/apply` and
    `!!python/name` still raise ConstructorError (verified). Do not swap the base
    class for FullLoader/UnsafeLoader.
    """


_IncludeLoader.add_constructor(
    "!include", lambda loader, node: {"__include__": loader.construct_scalar(node)}
)


def _load(path: Path):
    return yaml.load(path.read_text(), Loader=_IncludeLoader)


def _uniswap_x_templates() -> list[Path]:
    """Every template in the isolated contract-governed directory."""
    return sorted(TEMPLATE_DIR.glob("*.yaml"))


def _calibers() -> list[Path]:
    return sorted(
        p
        for p in REPO_ROOT.glob("machines/*/*/caliber.yaml")
        if ".deprecated" not in str(p)
    )


class TestGovernedSurfaceIsIsolated(unittest.TestCase):
    """The contract-governed surface is exactly instructions-x/uniswap-x/ + blueprints-x/uniswap-x/.

    Isolating the templates is what makes the surface enumerable: an ungoverned
    filler template added elsewhere becomes a test failure instead of an unnoticed
    path that skips every check below.
    """

    def test_directory_contains_exactly_the_expected_templates(self) -> None:
        found = {p.name for p in _uniswap_x_templates()}
        expected = set(FILL_TEMPLATES) | set(PARKING_TEMPLATES)
        self.assertEqual(
            found,
            expected,
            "a template was added to or removed from the governed directory; "
            "update this test deliberately, and the contract if the surface changed",
        )

    def test_no_uniswap_x_template_lives_outside_the_governed_directory(self) -> None:
        marker = "blueprints-x/uniswap-x/"
        candidates = [
            *(REPO_ROOT / "instructions-x").glob("*.yaml"),
            *(REPO_ROOT / "instructions").glob("*.yaml"),
            *REPO_ROOT.glob("machines/*/*/instructions/*.yaml"),
        ]
        strays = [
            p.relative_to(REPO_ROOT)
            for p in candidates
            if ".deprecated" not in str(p) and marker in p.read_text()
        ]
        self.assertEqual(
            strays,
            [],
            f"these invoke the uniswapX blueprint but sit outside {TEMPLATE_DIR.name}/, "
            "so the contract guards do not see them",
        )


class TestBlueprintSlotAbi(unittest.TestCase):
    """Contract section 3: slot names and declaration order are the ABI."""

    def setUp(self) -> None:
        self.fill_actions = _load(FILL_BLUEPRINT)["actions"]
        self.park_actions = _load(PARK_BLUEPRINT)["actions"]
        self.actions = {**self.fill_actions, **self.park_actions}

    def test_fill_and_park_actions_live_in_their_own_files(self) -> None:
        # The split is the point: mixing them back together would put a 3-slot and a
        # 1-slot ABI in one `inputs:` namespace.
        self.assertEqual(set(self.fill_actions), set(CANONICAL_FILL_SLOTS))
        self.assertEqual(set(self.park_actions), set(CANONICAL_PARKING_SLOTS))

    def test_both_blueprints_share_the_uniswapx_protocol_namespace(self) -> None:
        # Splitting the file must not split the generated rootfile namespace.
        for path in (FILL_BLUEPRINT, PARK_BLUEPRINT):
            self.assertEqual(_load(path)["protocol"], "uniswapX", path.name)

    def test_every_canonical_action_exists(self) -> None:
        for name in CANONICAL_ACTIONS:
            self.assertIn(name, self.actions, f"missing canonical action {name}")

    def test_no_legacy_action_names(self) -> None:
        for name in LEGACY_ACTION_NAMES:
            self.assertNotIn(name, self.actions, f"legacy action {name} must not be generated")

    def test_slot_declaration_order_matches_contract(self) -> None:
        # The load preserves mapping order (dicts are insertion-ordered), which is
        # exactly what the transpiler turns into slot indices.
        for name, expected in CANONICAL_ACTIONS.items():
            with self.subTest(action=name):
                declared = tuple(self.actions[name].get("input_slots", {}))
                self.assertEqual(
                    declared,
                    expected,
                    f"{name} slot order is the filler ABI; got {declared}, want {expected}",
                )

    def test_fills_take_exactly_three_slots_and_parking_exactly_one(self) -> None:
        for name in CANONICAL_FILL_SLOTS:
            self.assertEqual(len(self.actions[name]["input_slots"]), 3, name)
        for name in CANONICAL_PARKING_SLOTS:
            self.assertEqual(len(self.actions[name]["input_slots"]), 1, name)

    def test_parking_takes_neither_order_nor_signature(self) -> None:
        for name in CANONICAL_PARKING_SLOTS:
            slots = self.actions[name]["input_slots"]
            self.assertNotIn("order", slots, name)
            self.assertNotIn("signature", slots, name)

    def test_amount_slots_are_uint256(self) -> None:
        for name, expected in CANONICAL_ACTIONS.items():
            amount = expected[-1]
            self.assertEqual(
                self.actions[name]["input_slots"][amount]["type"], "uint256", name
            )


class TestInstructionTemplates(unittest.TestCase):
    """Contract sections 2 and 5: canonical paths and affected-token lists."""

    def test_templates_reference_only_canonical_actions(self) -> None:
        for tmpl in _uniswap_x_templates():
            for entry in _load(tmpl):
                action = entry["instruction"]["path"].rsplit(":", 1)[-1]
                with self.subTest(template=tmpl.name, action=action):
                    self.assertIn(action, CANONICAL_ACTIONS)

    def test_fill_entries_declare_both_legs_and_parking_declares_only_stable(self) -> None:
        # Section 5 makes affected_tokens the authoritative stable-leg check, since
        # the sell path carries no stable symbol.
        for tmpl in _uniswap_x_templates():
            for entry in _load(tmpl):
                action = entry["instruction"]["path"].rsplit(":", 1)[-1]
                tokens = entry["affected_tokens"]
                with self.subTest(template=tmpl.name, action=action):
                    if action in CANONICAL_PARKING_SLOTS:
                        self.assertEqual(len(tokens), 1, "parking touches the stable only")
                    else:
                        self.assertEqual(len(tokens), 2, "a fill touches stable and stock")

    def test_parking_templates_hold_exactly_one_entry(self) -> None:
        # More than one entry would mean more than one key per stable label.
        for name, action in PARKING_TEMPLATES.items():
            path = TEMPLATE_DIR / name
            with self.subTest(template=name):
                entries = _load(path)
                self.assertEqual(len(entries), 1)
                self.assertTrue(entries[0]["instruction"]["path"].endswith(f":{action}"))

    def test_parking_label_is_a_position_var(self) -> None:
        # The label is the last path segment the filler is configured against, so it
        # must come from the position, not be hardcoded in the shared template.
        for name in PARKING_TEMPLATES:
            path = TEMPLATE_DIR / name
            with self.subTest(template=name):
                self.assertRegex(_load(path)[0]["instruction"]["label"], r"^\$\{position\.")


class TestCaliberWiring(unittest.TestCase):
    """Contract section 2: parking is one position per profile, never per stock."""

    def test_parking_included_at_most_once_per_caliber(self) -> None:
        for caliber in _calibers():
            includes = [
                p["instructions"]["__include__"]
                for p in (_load(caliber).get("positions") or [])
                if isinstance(p.get("instructions"), dict)
                and "__include__" in p["instructions"]
            ]
            for name in PARKING_TEMPLATES:
                count = sum(1 for inc in includes if inc.endswith(name))
                with self.subTest(caliber=str(caliber.relative_to(REPO_ROOT)), tmpl=name):
                    self.assertLessEqual(
                        count, 1, f"{name} included {count}x; parking keys would collide"
                    )

    def test_parking_positions_use_a_bare_stable_symbol_label(self) -> None:
        # e.g. "USDG", not "USDG - steakUSDG". The label is the configured path segment.
        for caliber in _calibers():
            for position in _load(caliber).get("positions") or []:
                inc = position.get("instructions")
                if not (isinstance(inc, dict) and "__include__" in inc):
                    continue
                if not any(inc["__include__"].endswith(n) for n in PARKING_TEMPLATES):
                    continue
                label = position["vars"]["label"]
                with self.subTest(caliber=str(caliber.relative_to(REPO_ROOT)), label=label):
                    self.assertRegex(
                        label,
                        r"^[A-Za-z0-9]+$",
                        "parking label must be a bare stable symbol",
                    )


if __name__ == "__main__":
    unittest.main()
