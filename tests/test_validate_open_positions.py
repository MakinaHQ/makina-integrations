"""Tests for scripts/validate_open_positions.py

Unit tests use a FakeReader to avoid RPC calls. The integration test at the
bottom (test_dusd_mainnet_fixed_block_rootfile_outcomes) hits a real RPC and
is skipped unless ALCHEMY_API_KEY is set.

Fixtures live in tests/fixtures/dusd/mainnet/ — a caliber.yaml and two rootfiles
that represent a known scenario: the older rootfile is missing accounting for
position 128264429154381135287798106504544985667, and the newer one includes it.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "validate_open_positions.py"
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures"

# Import the script as a module. It lives outside a Python package (in scripts/),
# so we use importlib to load it by file path.
SPEC = importlib.util.spec_from_file_location("validate_open_positions", MODULE_PATH)
validate_open_positions = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = validate_open_positions
SPEC.loader.exec_module(validate_open_positions)


class FakeReader:
    """Stub implementing CaliberReader protocol with canned position ids."""

    def __init__(self, open_position_ids: list[str]):
        self.open_position_ids = open_position_ids

    def get_open_position_ids(self, caliber_address: str) -> list[str]:
        return list(self.open_position_ids)


class ValidateOpenPositionsTests(unittest.TestCase):
    def test_select_latest_rootfiles_keeps_latest_per_machine_chain(self) -> None:
        targets = validate_open_positions.select_latest_rootfiles(
            [
                "machines/dusd/mainnet/rootfiles/20260309-march-batch.toml",
                "machines/dusd/mainnet/rootfiles/20260311-reservoir-morpho-vault.toml",
                "machines/dbit/mainnet/rootfiles/20260223-usdt-morpho-vaults.toml",
                "machines/dbit/mainnet/rootfiles/20260303-syrup-loops.toml",
                "machines/deth/base/rootfiles/20251103-empty.toml",
            ]
        )

        self.assertEqual(
            [(target.machine, target.chain, target.rootfile_path.name) for target in targets],
            [
                ("dbit", "mainnet", "20260303-syrup-loops.toml"),
                ("deth", "base", "20251103-empty.toml"),
                ("dusd", "mainnet", "20260311-reservoir-morpho-vault.toml"),
            ],
        )

    def test_extract_caliber_metadata_reads_address_and_positions(self) -> None:
        caliber_path = FIXTURES_ROOT / "dusd" / "mainnet" / "caliber.yaml"
        caliber_address, position_ids = validate_open_positions.extract_caliber_metadata(caliber_path)

        self.assertEqual(caliber_address, "0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC")
        self.assertIn("128264429154381135287798106504544985667", position_ids)
        self.assertEqual(len(position_ids), 25)

    def test_extract_caliber_metadata_allows_empty_positions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            machine_dir = Path(tmpdir) / "machines" / "example"
            chain_dir = machine_dir / "monad"
            chain_dir.mkdir(parents=True)
            caliber_path = chain_dir / "caliber.yaml"
            caliber_path.write_text(
                "config:\n"
                "  caliber_address:\n"
                "    value: 0x1111111111111111111111111111111111111111\n"
                "positions: []\n"
            )

            caliber_address, position_ids = validate_open_positions.extract_caliber_metadata(caliber_path)

            self.assertEqual(caliber_address, "0x1111111111111111111111111111111111111111")
            self.assertEqual(position_ids, set())

    def test_validate_target_allows_initial_empty_rootfile_and_empty_positions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            machine_dir = Path(tmpdir) / "machines" / "example"
            chain_dir = machine_dir / "monad"
            rootfiles_dir = chain_dir / "rootfiles"
            rootfiles_dir.mkdir(parents=True)

            caliber_path = chain_dir / "caliber.yaml"
            caliber_path.write_text(
                "config:\n"
                "  caliber_address:\n"
                "    value: 0x1111111111111111111111111111111111111111\n"
                "positions: []\n"
            )
            rootfile_path = rootfiles_dir / "20260101-empty.toml"
            rootfile_path.write_text("[instructions]\n")

            target = validate_open_positions.RootfileTarget(
                machine="example",
                chain="monad",
                rootfile_path=rootfile_path,
                caliber_path=caliber_path,
            )
            reader = FakeReader([])

            result = validate_open_positions.validate_target(target, reader)

            self.assertTrue(result.ok)
            self.assertEqual(result.missing_in_caliber, [])
            self.assertEqual(result.missing_in_rootfile, [])
            self.assertEqual(result.duplicate_accounting, [])

    def test_extract_accounting_counts_detects_reservoir_position(self) -> None:
        working_rootfile = (
            FIXTURES_ROOT
            / "dusd"
            / "mainnet"
            / "rootfiles"
            / "20260311-reservoir-morpho-vault.toml"
        )
        old_rootfile = (
            FIXTURES_ROOT / "dusd" / "mainnet" / "rootfiles" / "20260309-march-batch.toml"
        )

        working_counts = validate_open_positions.extract_accounting_counts(working_rootfile)
        old_counts = validate_open_positions.extract_accounting_counts(old_rootfile)

        self.assertEqual(working_counts["128264429154381135287798106504544985667"], 1)
        self.assertNotIn("128264429154381135287798106504544985667", old_counts)

    def test_validate_target_reports_missing_accounting_for_open_position(self) -> None:
        target = validate_open_positions.RootfileTarget(
            machine="dusd",
            chain="mainnet",
            rootfile_path=FIXTURES_ROOT / "dusd" / "mainnet" / "rootfiles" / "20260309-march-batch.toml",
            caliber_path=FIXTURES_ROOT / "dusd" / "mainnet" / "caliber.yaml",
        )
        reader = FakeReader(["128264429154381135287798106504544985667"])

        result = validate_open_positions.validate_target(target, reader)

        self.assertFalse(result.ok)
        self.assertEqual(result.missing_in_caliber, [])
        self.assertEqual(result.missing_in_rootfile, ["128264429154381135287798106504544985667"])
        self.assertEqual(result.duplicate_accounting, [])

    def test_validate_target_reports_missing_caliber_position(self) -> None:
        target = validate_open_positions.RootfileTarget(
            machine="dusd",
            chain="mainnet",
            rootfile_path=FIXTURES_ROOT / "dusd" / "mainnet" / "rootfiles" / "20260311-reservoir-morpho-vault.toml",
            caliber_path=FIXTURES_ROOT / "dusd" / "mainnet" / "caliber.yaml",
        )
        reader = FakeReader(["999"])

        result = validate_open_positions.validate_target(target, reader)

        self.assertFalse(result.ok)
        self.assertEqual(result.missing_in_caliber, ["999"])
        self.assertEqual(result.missing_in_rootfile, ["999"])

    def test_dusd_mainnet_fixed_block_rootfile_outcomes(self) -> None:
        """Integration test: hits a real RPC at a pinned block to verify that
        the older rootfile fails validation (missing accounting) while the
        newer one passes. Skipped without RPC env vars."""
        api_key = os.getenv("ALCHEMY_API_KEY")
        if not api_key:
            self.skipTest("ALCHEMY_API_KEY is required")
        block_number = 24635682

        old_target = validate_open_positions.RootfileTarget(
            machine="dusd",
            chain="mainnet",
            rootfile_path=FIXTURES_ROOT / "dusd" / "mainnet" / "rootfiles" / "20260309-march-batch.toml",
            caliber_path=FIXTURES_ROOT / "dusd" / "mainnet" / "caliber.yaml",
        )
        new_target = validate_open_positions.RootfileTarget(
            machine="dusd",
            chain="mainnet",
            rootfile_path=FIXTURES_ROOT / "dusd" / "mainnet" / "rootfiles" / "20260311-reservoir-morpho-vault.toml",
            caliber_path=FIXTURES_ROOT / "dusd" / "mainnet" / "caliber.yaml",
        )
        reader = validate_open_positions.RpcCaliberReader("mainnet", block_number=block_number)

        old_result = validate_open_positions.validate_target(old_target, reader)
        new_result = validate_open_positions.validate_target(new_target, reader)

        self.assertFalse(old_result.ok)
        self.assertEqual(
            old_result.missing_in_rootfile,
            ["128264429154381135287798106504544985667"],
        )
        self.assertTrue(new_result.ok)


if __name__ == "__main__":
    unittest.main()
