"""Drift guard for machine manifests (`machines/<machine>/config.toml` with [modules.*]).

A manifest restates addresses that already live in the calibers it points at, so the two
can disagree. That disagreement is invisible: the transpiler never reads config.toml, and
neither on-chain validator does either (both bail on `makina_lite_module` calibers before
reaching it). Nothing else in CI would notice, so these tests are the only thing standing
between a stale manifest and a filler that quotes against the wrong deployment.

Every assertion below compares the manifest to the caliber, or to the repo's own chain
registry -- never to a hardcoded copy of the same fact.

Discovery is by shape, not by name: any `machines/*/config.toml` containing a `[modules.*]`
table is a manifest and gets these guarantees, so a future fund inherits them for free.
Full-Makina configs (`[calibers.*]`) and flat single-chain MakinaLite configs are ignored.
"""
from __future__ import annotations

import importlib.util
import sys
import tomllib
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

# The repo's chain-name -> chain-id registry, imported rather than duplicated.
_SPEC = importlib.util.spec_from_file_location(
    "manage_token_list", REPO_ROOT / "scripts" / "manage_token_list.py"
)
manage_token_list = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
sys.modules[_SPEC.name] = manage_token_list
_SPEC.loader.exec_module(manage_token_list)
CHAIN_TO_CHAIN_ID = manage_token_list.CHAIN_TO_CHAIN_ID

# liquidity_source -> the parking template a caliber of that profile must include.
# Mirrors the Uniswap-X Filler <-> Machine Contract section 2.
SOURCE_TO_PARK_TEMPLATE = {
    "aave_v3": "park-aave.yaml",
    "morpho_vault_v2": "park-morpho.yaml",
    "direct": None,  # a direct profile has no parking action
}


class _IncludeLoader(yaml.SafeLoader):
    """Resolve `!include` to a marker. SafeLoader subclass plus ONE dict-returning
    constructor, so `!!python/object/apply` and `!!python/name` still raise."""


_IncludeLoader.add_constructor(
    "!include", lambda loader, node: {"__include__": loader.construct_scalar(node)}
)


def _load_yaml(path: Path):
    return yaml.load(path.read_text(), Loader=_IncludeLoader)


def manifests() -> list[Path]:
    """Machine-root config.toml files that declare [modules.*]."""
    return sorted(
        p
        for p in REPO_ROOT.glob("machines/*/config.toml")
        if ".deprecated" not in str(p) and "modules" in tomllib.loads(p.read_text())
    )


def _positions(caliber: Path) -> list[dict]:
    return _load_yaml(caliber).get("positions") or []


def _includes(caliber: Path) -> list[str]:
    return [
        p["instructions"]["__include__"]
        for p in _positions(caliber)
        if isinstance(p.get("instructions"), dict) and "__include__" in p["instructions"]
    ]


class TestManifestsExist(unittest.TestCase):
    def test_at_least_one_manifest_is_discovered(self) -> None:
        # Guards against the glob silently matching nothing, which would make every
        # other test in this file vacuously pass.
        self.assertTrue(manifests(), "no machine manifest found; did the layout change?")


class TestManifestAgreesWithCalibers(unittest.TestCase):
    def test_every_module_entry_has_a_caliber(self) -> None:
        for m in manifests():
            data = tomllib.loads(m.read_text())
            for chain in data["modules"]:
                with self.subTest(manifest=m.parent.name, chain=chain):
                    self.assertTrue(
                        (m.parent / chain / "caliber.yaml").is_file(),
                        f"[modules.{chain}] has no {chain}/caliber.yaml; the table key "
                        "must be the network directory name",
                    )

    def test_every_caliber_has_a_module_entry(self) -> None:
        # The reverse direction: adding a chain without registering it would leave the
        # backend unable to discover it.
        for m in manifests():
            declared = set(tomllib.loads(m.read_text())["modules"])
            on_disk = {p.parent.name for p in m.parent.glob("*/caliber.yaml")}
            with self.subTest(manifest=m.parent.name):
                self.assertEqual(
                    on_disk - declared,
                    set(),
                    "these chains have a caliber but no [modules.<chain>] entry",
                )

    def test_module_address_matches_the_calibers_makina_lite_module(self) -> None:
        for m in manifests():
            for chain, entry in tomllib.loads(m.read_text())["modules"].items():
                caliber = m.parent / chain / "caliber.yaml"
                if not caliber.is_file():
                    continue
                declared = _load_yaml(caliber)["config"]["makina_lite_module"]["value"]
                with self.subTest(manifest=m.parent.name, chain=chain):
                    self.assertEqual(
                        entry["address"].lower(),
                        declared.lower(),
                        "manifest module address disagrees with the caliber's "
                        "config.makina_lite_module",
                    )

    def test_chain_id_matches_the_repo_chain_registry(self) -> None:
        for m in manifests():
            for chain, entry in tomllib.loads(m.read_text())["modules"].items():
                with self.subTest(manifest=m.parent.name, chain=chain):
                    self.assertIn(
                        chain,
                        CHAIN_TO_CHAIN_ID,
                        f"'{chain}' is not in CHAIN_TO_CHAIN_ID; register it in scripts/ "
                        "so token_list refs and chain-id checks resolve",
                    )
                    self.assertEqual(entry["chain_id"], CHAIN_TO_CHAIN_ID[chain])

    def test_rootfiles_path_points_at_this_machine_and_chain(self) -> None:
        for m in manifests():
            machine = m.parent.name
            for chain, entry in tomllib.loads(m.read_text())["modules"].items():
                with self.subTest(manifest=machine, chain=chain):
                    self.assertTrue(
                        entry["rootfiles"].endswith(f"machines/{machine}/{chain}/rootfiles"),
                        f"rootfiles should end with machines/{machine}/{chain}/rootfiles, "
                        f"got {entry['rootfiles']}",
                    )


class TestManifestAgreesWithFillerProfile(unittest.TestCase):
    """liquidity_source and stable_label are what the filler configures itself from,
    so they must match what the caliber actually generates."""

    def test_liquidity_source_matches_the_parking_template_included(self) -> None:
        for m in manifests():
            for chain, entry in tomllib.loads(m.read_text())["modules"].items():
                source = entry.get("liquidity_source")
                caliber = m.parent / chain / "caliber.yaml"
                if source is None or not caliber.is_file():
                    continue
                with self.subTest(manifest=m.parent.name, chain=chain, source=source):
                    self.assertIn(source, SOURCE_TO_PARK_TEMPLATE, "unknown liquidity_source")
                    expected = SOURCE_TO_PARK_TEMPLATE[source]
                    parking = [i for i in _includes(caliber) if "/uniswap-x/park-" in i]
                    if expected is None:
                        self.assertEqual(parking, [], "a direct profile must not park")
                    else:
                        self.assertEqual(
                            [Path(p).name for p in parking],
                            [expected],
                            f"liquidity_source={source} requires exactly {expected}",
                        )

    def test_stable_label_matches_the_parking_positions_label(self) -> None:
        # The parking rootfile path is uniswapX/park_stable_in_<source>/<stable_label>,
        # so a mismatch here silently unroutes the filler's parking action.
        for m in manifests():
            for chain, entry in tomllib.loads(m.read_text())["modules"].items():
                label = entry.get("stable_label")
                caliber = m.parent / chain / "caliber.yaml"
                if label is None or not caliber.is_file():
                    continue
                parking = [
                    p
                    for p in _positions(caliber)
                    if isinstance(p.get("instructions"), dict)
                    and "/uniswap-x/park-" in p["instructions"].get("__include__", "")
                ]
                with self.subTest(manifest=m.parent.name, chain=chain):
                    if not parking:
                        continue
                    self.assertEqual(
                        parking[0]["vars"]["label"],
                        label,
                        "manifest stable_label disagrees with the parking position's "
                        "label var, which is the rootfile path segment",
                    )


class TestManifestDesignRules(unittest.TestCase):
    def test_no_top_level_chain_or_address(self) -> None:
        # A makina-x fund has no hub chain and no hub contract; every chain is co-equal.
        for m in manifests():
            data = tomllib.loads(m.read_text())
            with self.subTest(manifest=m.parent.name):
                self.assertNotIn("chain", data, "no privileged chain at the machine root")
                self.assertNotIn("address", data, "no hub contract for a makina-x fund")

    def test_no_safe_declared_anywhere(self) -> None:
        # The Safe is read from MakinaXModule.safe(). Declaring it here would be a second
        # source of truth that can drift from what the module actually drives.
        for m in manifests():
            data = tomllib.loads(m.read_text())
            with self.subTest(manifest=m.parent.name):
                self.assertNotIn("safe", data)
                for chain, entry in data["modules"].items():
                    self.assertNotIn(
                        "safe",
                        entry,
                        f"[modules.{chain}].safe: read it from module.safe() instead",
                    )

    def test_every_module_entry_declares_the_required_keys_in_full(self) -> None:
        # Nothing inherits, so each entry must be complete on its own.
        for m in manifests():
            for chain, entry in tomllib.loads(m.read_text())["modules"].items():
                with self.subTest(manifest=m.parent.name, chain=chain):
                    for key in ("chain_id", "address", "rootfiles"):
                        self.assertIn(key, entry, f"[modules.{chain}] must declare {key}")

    def test_module_addresses_are_distinct_across_chains(self) -> None:
        # A module is a per-chain deployment; the same address on two chains would mean
        # one of the entries is a copy-paste error. (Safes may legitimately share an
        # address -- modules are created by a factory and do not.)
        for m in manifests():
            entries = tomllib.loads(m.read_text())["modules"]
            addrs = [e["address"].lower() for e in entries.values()]
            with self.subTest(manifest=m.parent.name):
                self.assertEqual(len(addrs), len(set(addrs)), "duplicate module address")


if __name__ == "__main__":
    unittest.main()
