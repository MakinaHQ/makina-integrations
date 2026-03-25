"""Tests for scripts/validate_token_lists.py."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "validate_token_lists.py"

SPEC = importlib.util.spec_from_file_location("validate_token_lists", MODULE_PATH)
validate_token_lists = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = validate_token_lists
SPEC.loader.exec_module(validate_token_lists)


def abi_string(value: str) -> str:
    encoded_bytes = value.encode("utf-8")
    encoded = encoded_bytes.hex()
    padded_length = f"{len(encoded_bytes):064x}"
    padded_data = encoded.ljust(((len(encoded) + 63) // 64) * 64, "0")
    return "0x" + f"{32:064x}" + padded_length + padded_data


def abi_uint(value: int) -> str:
    return "0x" + f"{value:064x}"


class FakeRpcClient:
    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url

    def eth_get_code(self, address: str) -> str:
        return RPC_FIXTURES[self.rpc_url][("eth_getCode", address)]

    def eth_call(self, address: str, data: str) -> str:
        response = RPC_FIXTURES[self.rpc_url][("eth_call", address, data)]
        if isinstance(response, Exception):
            raise response
        return response


RPC_FIXTURES: dict[str, dict[tuple[str, ...], object]] = {}


def _make_token(
    chain_id: int = 1,
    address_byte: str = "1",
    name: str = "USD Coin",
    symbol: str = "USDC",
    decimals: int = 6,
) -> validate_token_lists.TokenEntry:
    return validate_token_lists.TokenEntry(
        file_path=Path("token-lists/prod-token-list.json"),
        index=0,
        chain_id=chain_id,
        address="0x" + (address_byte * 40),
        name=name,
        symbol=symbol,
        decimals=decimals,
    )


class ValidateTokenListsTests(unittest.TestCase):
    def setUp(self) -> None:
        global RPC_FIXTURES
        RPC_FIXTURES = {}

    def write_json(self, payload: object) -> Path:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        path = Path(tempdir.name) / "token-list.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_extract_network_mapping_walks_nested_trpc_payload(self) -> None:
        payload = {
            "result": {
                "data": [
                    {"chainId": "ETH", "networkChainId": 1, "kebabCaseId": "eth-mainnet"},
                    {
                        "nested": {
                            "chainId": "BASE",
                            "networkChainId": "8453",
                            "kebabCaseId": "base-mainnet",
                        }
                    },
                ]
            },
            "other": [{"chainId": "ARB", "networkChainId": 42161, "kebabCaseId": "arb-mainnet"}],
        }

        mapping = validate_token_lists.extract_network_mapping(payload)

        self.assertEqual(
            mapping,
            {
                1: "eth-mainnet",
                8453: "base-mainnet",
                42161: "arb-mainnet",
            },
        )

    def test_load_token_entries_rejects_invalid_json(self) -> None:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        path = Path(tempdir.name) / "broken.json"
        path.write_text("{", encoding="utf-8")

        with self.assertRaises(validate_token_lists.ValidationError):
            validate_token_lists.load_token_entries(path)

    def test_load_token_entries_requires_fields(self) -> None:
        path = self.write_json({"tokens": [{"chainId": 1, "address": "0x" + ("1" * 40)}]})

        with self.assertRaises(validate_token_lists.ValidationError):
            validate_token_lists.load_token_entries(path)

    def test_build_rpc_urls_requires_chain_to_exist(self) -> None:
        with self.assertRaises(validate_token_lists.ValidationError):
            validate_token_lists.build_rpc_urls({10}, {1: "eth-mainnet"}, "key")

    def test_validate_entries_reports_missing_bytecode(self) -> None:
        token = _make_token()
        rpc_url = "https://eth-mainnet.g.alchemy.com/v2/key"
        global RPC_FIXTURES
        RPC_FIXTURES = {
            rpc_url: {
                ("eth_getCode", token.address.lower()): "0x",
            }
        }

        with mock.patch.object(validate_token_lists, "RpcClient", FakeRpcClient):
            results, issues = validate_token_lists.validate_entries([token], {1: rpc_url})

        self.assertFalse(results[0].ok)
        self.assertEqual(results[0].issues, ["address has no contract bytecode"])
        self.assertEqual(len(issues), 1)

    def test_validate_entries_reports_rpc_failure(self) -> None:
        token = _make_token(address_byte="2")
        rpc_url = "https://eth-mainnet.g.alchemy.com/v2/key"
        global RPC_FIXTURES
        RPC_FIXTURES = {
            rpc_url: {
                ("eth_getCode", token.address.lower()): "0x1234",
                ("eth_call", token.address.lower(), validate_token_lists.TOTAL_SUPPLY_SELECTOR): (
                    validate_token_lists.ValidationError("eth_call RPC error")
                ),
            }
        }

        with mock.patch.object(validate_token_lists, "RpcClient", FakeRpcClient):
            results, issues = validate_token_lists.validate_entries([token], {1: rpc_url})

        self.assertFalse(results[0].ok)
        self.assertIn("eth_call RPC error", results[0].issues[0])
        self.assertEqual(len(issues), 1)

    def test_validate_entries_reports_metadata_mismatches(self) -> None:
        token = _make_token(chain_id=42161, address_byte="3")
        rpc_url = "https://arb-mainnet.g.alchemy.com/v2/key"
        global RPC_FIXTURES
        RPC_FIXTURES = {
            rpc_url: {
                ("eth_getCode", token.address.lower()): "0x1234",
                ("eth_call", token.address.lower(), validate_token_lists.TOTAL_SUPPLY_SELECTOR): abi_uint(1),
                ("eth_call", token.address.lower(), validate_token_lists.NAME_SELECTOR): abi_string("Wrong Name"),
                ("eth_call", token.address.lower(), validate_token_lists.SYMBOL_SELECTOR): abi_string("WRONG"),
                ("eth_call", token.address.lower(), validate_token_lists.DECIMALS_SELECTOR): abi_uint(18),
            }
        }

        with mock.patch.object(validate_token_lists, "RpcClient", FakeRpcClient):
            results, issues = validate_token_lists.validate_entries([token], {42161: rpc_url})

        self.assertFalse(results[0].ok)
        self.assertEqual(len(results[0].issues), 3)
        self.assertEqual(len(issues), 3)

    def test_validate_entries_passes_for_resolved_chain(self) -> None:
        token = _make_token(chain_id=8453, address_byte="4")
        rpc_url = "https://base-mainnet.g.alchemy.com/v2/key"
        global RPC_FIXTURES
        RPC_FIXTURES = {
            rpc_url: {
                ("eth_getCode", token.address.lower()): "0x1234",
                ("eth_call", token.address.lower(), validate_token_lists.TOTAL_SUPPLY_SELECTOR): abi_uint(1),
                ("eth_call", token.address.lower(), validate_token_lists.NAME_SELECTOR): abi_string("USD Coin"),
                ("eth_call", token.address.lower(), validate_token_lists.SYMBOL_SELECTOR): abi_string("USDC"),
                ("eth_call", token.address.lower(), validate_token_lists.DECIMALS_SELECTOR): abi_uint(6),
            }
        }

        with mock.patch.object(validate_token_lists, "RpcClient", FakeRpcClient):
            results, issues = validate_token_lists.validate_entries([token], {8453: rpc_url})

        self.assertTrue(results[0].ok)
        self.assertEqual(issues, [])

    def test_validate_entries_normalizes_tether_unicode(self) -> None:
        """On-chain ₮ (U+20AE) in name/symbol should be normalized to T for comparison."""
        token = _make_token(address_byte="5", name="Tether USD", symbol="USDT")
        rpc_url = "https://eth-mainnet.g.alchemy.com/v2/key"
        global RPC_FIXTURES
        RPC_FIXTURES = {
            rpc_url: {
                ("eth_getCode", token.address.lower()): "0x1234",
                ("eth_call", token.address.lower(), validate_token_lists.TOTAL_SUPPLY_SELECTOR): abi_uint(1),
                ("eth_call", token.address.lower(), validate_token_lists.NAME_SELECTOR): abi_string("\u20aeether USD"),
                ("eth_call", token.address.lower(), validate_token_lists.SYMBOL_SELECTOR): abi_string("USD\u20ae"),
                ("eth_call", token.address.lower(), validate_token_lists.DECIMALS_SELECTOR): abi_uint(6),
            }
        }

        with mock.patch.object(validate_token_lists, "RpcClient", FakeRpcClient):
            results, issues = validate_token_lists.validate_entries([token], {1: rpc_url})

        self.assertTrue(results[0].ok)
        self.assertEqual(issues, [])

    def test_main_fails_when_network_config_missing_chain(self) -> None:
        path = self.write_json(
            {
                "tokens": [
                    {
                        "chainId": 10,
                        "address": "0x" + ("5" * 40),
                        "name": "Test",
                        "symbol": "TEST",
                        "decimals": 18,
                    }
                ]
            }
        )

        env_patch = {"ALCHEMY_API_KEY": "key"}
        if "GITHUB_STEP_SUMMARY" in os.environ:
            env_patch["GITHUB_STEP_SUMMARY"] = ""
        with mock.patch.dict("os.environ", env_patch, clear=False):
            with mock.patch.object(
                validate_token_lists,
                "fetch_network_config",
                return_value={
                    "result": {
                        "data": [{"chainId": "ETH", "networkChainId": 1, "kebabCaseId": "eth-mainnet"}]
                    }
                },
            ):
                exit_code = validate_token_lists.main([str(path)])

        self.assertEqual(exit_code, 1)


class TestNormalizeOnchainString(unittest.TestCase):
    def test_replaces_tugrik(self) -> None:
        self.assertEqual(validate_token_lists.normalize_onchain_string("\u20aeether"), "Tether")

    def test_no_op_for_ascii(self) -> None:
        self.assertEqual(validate_token_lists.normalize_onchain_string("USDC"), "USDC")


if __name__ == "__main__":
    unittest.main()
