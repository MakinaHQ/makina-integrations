"""Tests for the trusted fork-PR validation input materializer."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "materialize_pr_validation_inputs.py"
SPEC = importlib.util.spec_from_file_location("materialize_pr_validation_inputs", MODULE_PATH)
assert SPEC and SPEC.loader
materialize_pr_validation_inputs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = materialize_pr_validation_inputs
SPEC.loader.exec_module(materialize_pr_validation_inputs)


class FakeGitHubApi:
    """In-memory GitHub contents API used to keep materialization tests offline."""

    def __init__(self, contents: dict[tuple[str, str, str], bytes]) -> None:
        self.contents = contents
        self.requests: list[tuple[str, str, str]] = []

    def fetch_contents(self, repository: str, ref: str, path: str) -> bytes:
        request = (repository, ref, path)
        self.requests.append(request)
        return self.contents[request]


class MaterializePrValidationInputsTests(unittest.TestCase):
    def test_classification_uses_only_changed_token_lists_and_added_rootfiles(self) -> None:
        """A status/path regression must not make workflow or old-rootfile data privileged input."""
        files = [
            {"filename": "token-lists/prod-token-list.json", "status": "modified"},
            {
                "filename": "machines/dusd/mainnet/rootfiles/20260807-safe.toml",
                "status": "added",
            },
            {"filename": ".github/workflows/pwn.yaml", "status": "modified"},
            {
                "filename": "machines/dusd/mainnet/rootfiles/20260806-old.toml",
                "status": "modified",
            },
        ]

        result = materialize_pr_validation_inputs.classify_pull_request_files(files)

        self.assertEqual(result.token_list_paths, ("token-lists/prod-token-list.json",))
        self.assertEqual(
            result.rootfile_paths,
            ("machines/dusd/mainnet/rootfiles/20260807-safe.toml",),
        )

    def test_materialization_fetches_only_rootfile_validation_dependencies(self) -> None:
        """Rootfile validation needs its rootfile, caliber and machine config—nothing else."""
        repository = "attacker/integration-fork"
        head_sha = "a" * 40
        rootfile = "machines/dusd/mainnet/rootfiles/20260807-safe.toml"
        caliber = "machines/dusd/mainnet/caliber.yaml"
        config = "machines/dusd/config.toml"
        api = FakeGitHubApi(
            {
                (repository, head_sha, rootfile): b"[instructions]\n",
                (repository, head_sha, caliber): b"positions: []\n",
                (repository, head_sha, config): b"[calibers.mainnet]\naddress = '0x1'\n",
            }
        )
        classification = materialize_pr_validation_inputs.Classification(
            token_list_paths=(), rootfile_paths=(rootfile,)
        )

        with tempfile.TemporaryDirectory() as tempdir:
            destination = Path(tempdir) / "inputs"
            materialize_pr_validation_inputs.materialize_inputs(
                api=api,
                repository=repository,
                head_sha=head_sha,
                destination=destination,
                classification=classification,
                include_token_lists=False,
                include_rootfiles=True,
            )

            self.assertEqual((destination / rootfile).read_bytes(), b"[instructions]\n")
            self.assertEqual((destination / caliber).read_bytes(), b"positions: []\n")
            self.assertEqual(
                (destination / config).read_bytes(),
                b"[calibers.mainnet]\naddress = '0x1'\n",
            )

        self.assertEqual(
            api.requests,
            [
                (repository, head_sha, rootfile),
                (repository, head_sha, caliber),
                (repository, head_sha, config),
            ],
        )

    def test_write_file_rejects_traversal_before_creating_a_file(self) -> None:
        """Removing the resolved-path containment check would let a fork overwrite base code."""
        with tempfile.TemporaryDirectory() as tempdir:
            destination = Path(tempdir) / "inputs"
            outside = Path(tempdir) / "outside.txt"

            with self.assertRaises(materialize_pr_validation_inputs.MaterializationError):
                materialize_pr_validation_inputs.write_file(destination, "../../outside.txt", b"pwn")

            self.assertFalse(outside.exists())

    def test_repository_name_is_validated_before_contents_are_requested(self) -> None:
        """A malformed head repository must not be interpolated into a GitHub API path."""
        with self.assertRaises(materialize_pr_validation_inputs.MaterializationError):
            materialize_pr_validation_inputs.validate_repository("attacker/repo/../../other")


if __name__ == "__main__":
    unittest.main()
