"""Tests for scripts/validate_token_list.py

Unit tests mock all RPC calls so no network access is needed.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "validate_token_list.py"

# Import the script as a module (same pattern as other test files)
SPEC = importlib.util.spec_from_file_location("validate_token_list", MODULE_PATH)
vtl = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = vtl
SPEC.loader.exec_module(vtl)


def _make_token(
    chain_id: int = 1,
    address: str = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    name: str = "USD Coin",
    symbol: str = "USDC",
    decimals: int = 6,
) -> dict:
    return {
        "chainId": chain_id,
        "address": address,
        "name": name,
        "symbol": symbol,
        "decimals": decimals,
    }


def _make_token_list(*tokens: dict) -> dict:
    return {"name": "Test", "timestamp": "2026-01-01", "tokens": list(tokens)}


def _mock_w3(
    name: str = "USD Coin",
    symbol: str = "USDC",
    decimals: int = 6,
    *,
    error: Exception | None = None,
) -> MagicMock:
    """Create a mock Web3 instance. If error is set, contract calls raise instead."""
    w3 = MagicMock()
    contract = MagicMock()
    if error:
        contract.functions.symbol.return_value.call.side_effect = error
    else:
        contract.functions.name.return_value.call.return_value = name
        contract.functions.symbol.return_value.call.return_value = symbol
        contract.functions.decimals.return_value.call.return_value = decimals
    w3.eth.contract.return_value = contract
    return w3


class TestValidateTokenList(unittest.TestCase):
    """Test the core validate_token_list function with mocked RPC."""

    @patch.object(vtl, "_get_w3")
    def test_valid_token_passes(self, mock_get_w3: MagicMock) -> None:
        mock_get_w3.return_value = _mock_w3("USD Coin", "USDC", 6)
        data = _make_token_list(_make_token())
        result = vtl.validate_token_list("test.json", data)
        self.assertTrue(result.ok)
        self.assertEqual(result.checked, 1)
        self.assertEqual(result.errors, [])

    @patch.object(vtl, "_get_w3")
    def test_symbol_mismatch_fails(self, mock_get_w3: MagicMock) -> None:
        mock_get_w3.return_value = _mock_w3("USD Coin", "USDC", 6)
        token = _make_token(symbol="WRONG")
        data = _make_token_list(token)
        result = vtl.validate_token_list("test.json", data)
        self.assertFalse(result.ok)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("symbol", result.errors[0].message)

    @patch.object(vtl, "_get_w3")
    def test_decimals_mismatch_fails(self, mock_get_w3: MagicMock) -> None:
        mock_get_w3.return_value = _mock_w3("USD Coin", "USDC", 6)
        token = _make_token(decimals=18)
        data = _make_token_list(token)
        result = vtl.validate_token_list("test.json", data)
        self.assertFalse(result.ok)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("decimals", result.errors[0].message)

    @patch.object(vtl, "_get_w3")
    def test_name_mismatch_fails(self, mock_get_w3: MagicMock) -> None:
        mock_get_w3.return_value = _mock_w3("Wrong Name", "USDC", 6)
        token = _make_token()
        data = _make_token_list(token)
        result = vtl.validate_token_list("test.json", data)
        self.assertFalse(result.ok)
        self.assertIn("name", result.errors[0].message)

    @patch.object(vtl, "_get_w3")
    def test_contract_not_found_fails(self, mock_get_w3: MagicMock) -> None:
        mock_get_w3.return_value = _mock_w3(error=Exception("not found"))
        data = _make_token_list(_make_token())
        result = vtl.validate_token_list("test.json", data)
        self.assertFalse(result.ok)
        self.assertIn("not found", result.errors[0].message)

    @patch.object(vtl, "_get_w3")
    def test_unknown_chain_id_fails(self, mock_get_w3: MagicMock) -> None:
        token = _make_token(chain_id=99999)
        data = _make_token_list(token)
        result = vtl.validate_token_list("test.json", data)
        self.assertFalse(result.ok)
        self.assertIn("unknown chainId", result.errors[0].message)
        mock_get_w3.assert_not_called()

    @patch.object(vtl, "_get_w3")
    def test_no_rpc_for_chain_fails(self, mock_get_w3: MagicMock) -> None:
        mock_get_w3.return_value = None
        data = _make_token_list(_make_token())
        result = vtl.validate_token_list("test.json", data)
        self.assertFalse(result.ok)
        self.assertIn("no RPC", result.errors[0].message)

    @patch.object(vtl, "_get_w3")
    def test_multiple_tokens_mixed_results(self, mock_get_w3: MagicMock) -> None:
        mock_get_w3.return_value = _mock_w3("USD Coin", "USDC", 6)
        good = _make_token()
        bad = _make_token(
            address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
            symbol="WRONG",
            name="Dai Stablecoin",
            decimals=18,
        )
        data = _make_token_list(good, bad)
        result = vtl.validate_token_list("test.json", data)
        self.assertFalse(result.ok)
        self.assertEqual(result.checked, 2)
        # Only the second token should have errors (symbol mismatch)
        self.assertEqual(len(result.errors), 1)

    def test_empty_token_list_passes(self) -> None:
        data = _make_token_list()
        result = vtl.validate_token_list("test.json", data)
        self.assertTrue(result.ok)
        self.assertEqual(result.checked, 0)

    @patch.object(vtl, "_get_w3")
    def test_multiple_chains_uses_separate_w3(self, mock_get_w3: MagicMock) -> None:
        mock_get_w3.return_value = _mock_w3("USD Coin", "USDC", 6)
        t1 = _make_token(chain_id=1)
        t2 = _make_token(chain_id=8453)
        data = _make_token_list(t1, t2)
        result = vtl.validate_token_list("test.json", data)
        # _get_w3 called once per chain
        self.assertEqual(mock_get_w3.call_count, 2)
        self.assertEqual(result.checked, 2)


class TestMainExitCode(unittest.TestCase):
    def test_no_files_returns_zero(self) -> None:
        code = vtl.main([])
        self.assertEqual(code, 0)


class TestChainIdToName(unittest.TestCase):
    def test_all_expected_chains_present(self) -> None:
        expected = {1, 8453, 42161, 10143, 998}
        self.assertEqual(set(vtl.CHAIN_ID_TO_NAME.keys()), expected)


class TestFetchErc20Metadata(unittest.TestCase):
    def test_unicode_normalization(self) -> None:
        """Tether uses ₮ (U+20AE) which should be normalized to T."""
        w3 = _mock_w3("Tether \u20aeoken", "\u20aeether", 6)
        meta = vtl.fetch_erc20_metadata(w3, "0xdAC17F958D2ee523a2206206994597C13D831ec7")
        assert meta is not None
        self.assertEqual(meta["symbol"], "Tether")
        self.assertEqual(meta["name"], "Tether Token")


if __name__ == "__main__":
    unittest.main()
