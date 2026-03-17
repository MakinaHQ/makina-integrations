"""Tests for scripts/validate_token_chains.py"""
from __future__ import annotations

import importlib.util
import sys
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "validate_token_chains.py"
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "token-chain-check"

# Import the script as a module (same pattern as test_validate_open_positions.py)
SPEC = importlib.util.spec_from_file_location("validate_token_chains", MODULE_PATH)
validate_token_chains = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = validate_token_chains
SPEC.loader.exec_module(validate_token_chains)


def _load_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text())


class TestTokenListRefRegex(unittest.TestCase):
    def test_parses_valid_ref(self) -> None:
        m = validate_token_chains.TOKEN_LIST_REF_RE.match(
            "${token_list.mainnet.USDC}"
        )
        assert m is not None
        self.assertEqual(m.group(1), "mainnet")
        self.assertEqual(m.group(2), "USDC")

    def test_parses_ref_with_digits(self) -> None:
        m = validate_token_chains.TOKEN_LIST_REF_RE.match(
            "${token_list.arbitrum.USDT0}"
        )
        assert m is not None
        self.assertEqual(m.group(1), "arbitrum")
        self.assertEqual(m.group(2), "USDT0")

    def test_rejects_non_token_list_key(self) -> None:
        m = validate_token_chains.TOKEN_LIST_REF_RE.match("some_plain_key")
        self.assertIsNone(m)


class TestValidateRootfile(unittest.TestCase):
    def test_correct_chain_passes(self) -> None:
        fixture = FIXTURES_ROOT / "good-mainnet.toml"
        result = validate_token_chains.validate_rootfile_from_data(
            rootfile_path="machines/test/mainnet/rootfiles/good-mainnet.toml",
            data=_load_toml(fixture),
        )
        assert result is not None
        self.assertTrue(result.ok)
        self.assertEqual(result.token_chain_mismatches, [])
        self.assertEqual(result.chain_id_mismatches, [])

    def test_wrong_chain_in_token_ref_fails(self) -> None:
        fixture = FIXTURES_ROOT / "bad-mainnet-has-base.toml"
        result = validate_token_chains.validate_rootfile_from_data(
            rootfile_path="machines/test/mainnet/rootfiles/bad.toml",
            data=_load_toml(fixture),
        )
        assert result is not None
        self.assertFalse(result.ok)
        # Chain name mismatch: token_list.base but rootfile is in mainnet/
        self.assertEqual(len(result.token_chain_mismatches), 1)
        self.assertEqual(result.token_chain_mismatches[0].expected_chain, "mainnet")
        self.assertEqual(result.token_chain_mismatches[0].actual_chain, "base")
        # Also triggers chainId mismatch: chainId=8453 but mainnet expects 1
        self.assertEqual(len(result.chain_id_mismatches), 1)
        self.assertEqual(result.chain_id_mismatches[0].expected_chain_id, 1)
        self.assertEqual(result.chain_id_mismatches[0].actual_chain_id, 8453)

    def test_wrong_chain_id_fails(self) -> None:
        fixture = FIXTURES_ROOT / "bad-chainid-mismatch.toml"
        result = validate_token_chains.validate_rootfile_from_data(
            rootfile_path="machines/test/mainnet/rootfiles/bad.toml",
            data=_load_toml(fixture),
        )
        assert result is not None
        self.assertFalse(result.ok)
        self.assertEqual(len(result.chain_id_mismatches), 1)
        self.assertEqual(result.chain_id_mismatches[0].expected_chain_id, 1)
        self.assertEqual(result.chain_id_mismatches[0].actual_chain_id, 8453)

    def test_no_tokens_section_passes(self) -> None:
        fixture = FIXTURES_ROOT / "no-tokens.toml"
        result = validate_token_chains.validate_rootfile_from_data(
            rootfile_path="machines/test/monad/rootfiles/no-tokens.toml",
            data=_load_toml(fixture),
        )
        assert result is not None
        self.assertTrue(result.ok)

    def test_non_rootfile_path_returns_none(self) -> None:
        result = validate_token_chains.validate_rootfile(
            "some/random/path.toml"
        )
        self.assertIsNone(result)


class TestMainExitCode(unittest.TestCase):
    def test_no_rootfiles_returns_zero(self) -> None:
        code = validate_token_chains.main([])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
