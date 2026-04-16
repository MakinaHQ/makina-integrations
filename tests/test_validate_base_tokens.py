"""Tests for scripts/validate_base_tokens.py

Unit tests use a FakeChecker to avoid RPC calls. The integration test at the
bottom hits a real RPC and is skipped unless ALCHEMY_API_KEY is set.

Fixtures reuse the existing tests/fixtures/dusd/mainnet/ directory.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "validate_base_tokens.py"
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures"

# Import the script as a module (it lives outside a Python package).
SPEC = importlib.util.spec_from_file_location("validate_base_tokens", MODULE_PATH)
validate_base_tokens = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = validate_base_tokens
SPEC.loader.exec_module(validate_base_tokens)


class FakeChecker:
    """Stub implementing BaseTokenChecker with a fixed set of base tokens."""

    def __init__(self, base_tokens: set[str]):
        self.base_tokens = {t.lower() for t in base_tokens}

    def is_base_token(self, caliber_address: str, token_address: str) -> bool:
        return token_address.lower() in self.base_tokens


class ValidateBaseTokensTests(unittest.TestCase):
    def test_select_latest_rootfiles_keeps_latest_per_machine_chain(self) -> None:
        targets = validate_base_tokens.select_latest_rootfiles(
            [
                "machines/dusd/mainnet/rootfiles/20260309-march-batch.toml",
                "machines/dusd/mainnet/rootfiles/20260311-reservoir-morpho-vault.toml",
                "machines/dbit/mainnet/rootfiles/20260223-usdt-morpho-vaults.toml",
            ]
        )
        self.assertEqual(
            [(t.machine, t.chain, t.rootfile_path.name) for t in targets],
            [
                ("dbit", "mainnet", "20260223-usdt-morpho-vaults.toml"),
                ("dusd", "mainnet", "20260311-reservoir-morpho-vault.toml"),
            ],
        )

    def test_extract_affected_tokens_collects_unique_addresses(self) -> None:
        rootfile = FIXTURES_ROOT / "dusd" / "mainnet" / "rootfiles" / "20260311-reservoir-morpho-vault.toml"
        tokens = validate_base_tokens.extract_affected_tokens(rootfile)
        # Should find at least USDC, USDT, GHO (lowercased)
        self.assertIn("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", tokens)  # USDC
        self.assertIn("0xdac17f958d2ee523a2206206994597c13d831ec7", tokens)  # USDT
        self.assertIn("0x40d16fc0246ad3160ccc09b8d0d3a2cd28ae6c2f", tokens)  # GHO

    def test_validate_target_all_base_tokens_passes(self) -> None:
        rootfile = FIXTURES_ROOT / "dusd" / "mainnet" / "rootfiles" / "20260311-reservoir-morpho-vault.toml"
        tokens = validate_base_tokens.extract_affected_tokens(rootfile)

        target = validate_base_tokens.RootfileTarget(
            machine="dusd",
            chain="mainnet",
            rootfile_path=rootfile,
            caliber_path=FIXTURES_ROOT / "dusd" / "mainnet" / "caliber.yaml",
        )
        checker = FakeChecker(tokens)  # all tokens are base tokens

        result = validate_base_tokens.validate_target(target, checker)
        self.assertTrue(result.ok)
        self.assertEqual(result.non_base_tokens, [])

    def test_validate_target_reports_non_base_token(self) -> None:
        rootfile = FIXTURES_ROOT / "dusd" / "mainnet" / "rootfiles" / "20260311-reservoir-morpho-vault.toml"
        tokens = validate_base_tokens.extract_affected_tokens(rootfile)

        # Remove USDC from fake base tokens — it should be flagged
        usdc = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
        fake_base = tokens - {usdc}

        target = validate_base_tokens.RootfileTarget(
            machine="dusd",
            chain="mainnet",
            rootfile_path=rootfile,
            caliber_path=FIXTURES_ROOT / "dusd" / "mainnet" / "caliber.yaml",
        )
        checker = FakeChecker(fake_base)

        result = validate_base_tokens.validate_target(target, checker)
        self.assertFalse(result.ok)
        self.assertIn(usdc, result.non_base_tokens)

    def test_validate_target_no_base_tokens_registered(self) -> None:
        """When the checker has zero base tokens, all affected tokens should fail."""
        target = validate_base_tokens.RootfileTarget(
            machine="dusd",
            chain="mainnet",
            rootfile_path=FIXTURES_ROOT / "dusd" / "mainnet" / "rootfiles" / "20260311-reservoir-morpho-vault.toml",
            caliber_path=FIXTURES_ROOT / "dusd" / "mainnet" / "caliber.yaml",
        )
        checker = FakeChecker(set())
        result = validate_base_tokens.validate_target(target, checker)
        self.assertFalse(result.ok)
        self.assertEqual(len(result.non_base_tokens), len(result.affected_tokens))

    def test_dusd_mainnet_iusd_not_base_token(self) -> None:
        """Integration test: at block 24721023, iUSD (0x48f9...) is NOT a
        base token on the DUSD mainnet caliber, so the rootfile
        20260319-dusd-march-batch.toml should fail validation.
        Skipped without ALCHEMY_API_KEY."""
        api_key = os.getenv("ALCHEMY_API_KEY")
        if not api_key:
            self.skipTest("ALCHEMY_API_KEY is required")

        block_number = 24721023
        rootfile_path = REPO_ROOT / "machines" / "dusd" / "mainnet" / "rootfiles" / "20260319-dusd-march-batch.toml"
        caliber_path = REPO_ROOT / "machines" / "dusd" / "mainnet" / "caliber.yaml"

        if not rootfile_path.exists():
            self.skipTest(f"{rootfile_path} does not exist")

        target = validate_base_tokens.RootfileTarget(
            machine="dusd",
            chain="mainnet",
            rootfile_path=rootfile_path,
            caliber_path=caliber_path,
        )
        checker = validate_base_tokens.RpcBaseTokenChecker("mainnet", block_number=block_number)
        result = validate_base_tokens.validate_target(target, checker)

        self.assertFalse(result.ok)
        self.assertIn("0x48f9e38f3070ad8945dfeae3fa70987722e3d89c", result.non_base_tokens)


if __name__ == "__main__":
    unittest.main()
