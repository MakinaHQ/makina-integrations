"""Tests for scripts/validate_infra_addresses.py"""
from __future__ import annotations

import contextlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "validate_infra_addresses.py"
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "infra-address-check"

# Import the script as a module (same pattern as test_validate_token_chains.py)
SPEC = importlib.util.spec_from_file_location("validate_infra_addresses", MODULE_PATH)
validate_infra_addresses = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = validate_infra_addresses
SPEC.loader.exec_module(validate_infra_addresses)

DENYLIST = validate_infra_addresses.load_denylist()


class TestDenylist(unittest.TestCase):
    def test_denylist_is_non_empty(self) -> None:
        self.assertGreater(len(DENYLIST), 0)

    def test_all_bodies_are_lowercase_40_hex(self) -> None:
        for entry in DENYLIST:
            self.assertEqual(len(entry.body), 40)
            self.assertEqual(entry.body, entry.body.lower())
            self.assertTrue(all(c in "0123456789abcdef" for c in entry.body))

    def test_no_prod_addresses_leaked_in(self) -> None:
        # Canonical prod addresses must NOT be on the denylist (would break every PR).
        prod = {
            "0xc388b72ab90be82b230d919f9c05c87f9397f485",  # OracleRegistry
            "0x3d623b199e290358416415ea7e05b635e442e3c0",  # MathHelper
            "0x923c98b22f9c367a109e93f7dfbaca28b20c17c3",  # SwapModule
            "0xfd162a672928bf40e5a81f0d11501d2849841fa6",  # WeirollVM
        }
        bodies = {e.body for e in DENYLIST}
        self.assertEqual(prod & bodies, set())


class TestValidateRootfile(unittest.TestCase):
    def test_prod_addresses_pass(self) -> None:
        text = (FIXTURES_ROOT / "good-prod.toml").read_text()
        result = validate_infra_addresses.validate_rootfile_from_text(
            "machines/test/base/rootfiles/good-prod.toml", text, DENYLIST
        )
        assert result is not None
        self.assertTrue(result.ok)
        self.assertEqual(result.hits, [])

    def test_test_infra_address_embedded_in_command_word_is_caught(self) -> None:
        text = (FIXTURES_ROOT / "bad-test-oracle-registry.toml").read_text()
        result = validate_infra_addresses.validate_rootfile_from_text(
            "machines/test/base/rootfiles/bad.toml", text, DENYLIST
        )
        assert result is not None
        self.assertFalse(result.ok)
        self.assertEqual(len(result.hits), 1)
        self.assertIn("OracleRegistry", result.hits[0].label)
        self.assertEqual(
            result.hits[0].address, "0xe75e81E0995816eBcd510Ed9CDD84ED05aC60442"
        )

    def test_scan_is_case_insensitive(self) -> None:
        # Fixture stores the #79 MathHelper in uppercase.
        text = (FIXTURES_ROOT / "bad-nonprod-mathhelper.toml").read_text()
        result = validate_infra_addresses.validate_rootfile_from_text(
            "machines/test/base/rootfiles/bad.toml", text, DENYLIST
        )
        assert result is not None
        self.assertFalse(result.ok)
        self.assertEqual(len(result.hits), 1)
        self.assertIn("MathHelper", result.hits[0].label)

    def test_non_rootfile_path_returns_none(self) -> None:
        result = validate_infra_addresses.validate_rootfile_from_text(
            "some/random/path.toml", "0xe75e81e0995816ebcd510ed9cdd84ed05ac60442", DENYLIST
        )
        self.assertIsNone(result)


@contextlib.contextmanager
def _rootfile_in_tmp(contents: str):
    """Materialize a fixture at a machines/*/*/rootfiles/*.toml path inside a
    temp cwd so main() (which reads paths relative to cwd) can be exercised."""
    with tempfile.TemporaryDirectory() as tmp:
        rel = "machines/test/base/rootfiles/x.toml"
        dest = Path(tmp) / rel
        dest.parent.mkdir(parents=True)
        dest.write_text(contents)
        prev = Path.cwd()
        os.chdir(tmp)
        try:
            yield rel
        finally:
            os.chdir(prev)


class TestMainExitCode(unittest.TestCase):
    def test_no_rootfiles_returns_zero(self) -> None:
        self.assertEqual(validate_infra_addresses.main([]), 0)

    def test_clean_rootfile_returns_zero(self) -> None:
        with _rootfile_in_tmp((FIXTURES_ROOT / "good-prod.toml").read_text()) as rel:
            self.assertEqual(validate_infra_addresses.main([rel]), 0)

    def test_bad_rootfile_returns_one(self) -> None:
        with _rootfile_in_tmp(
            (FIXTURES_ROOT / "bad-test-oracle-registry.toml").read_text()
        ) as rel:
            self.assertEqual(validate_infra_addresses.main([rel]), 1)


if __name__ == "__main__":
    unittest.main()
