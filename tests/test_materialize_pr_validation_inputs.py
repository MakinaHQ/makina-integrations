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

BASE_REPOSITORY = "MakinaHQ/makina-integrations"
HEAD_REPOSITORY = "attacker/integration-fork"


class FakeGitHubApi:
    """In-memory GitHub contents API used to keep materialization tests offline."""

    def __init__(self, contents: dict[tuple[str, str, str], bytes]) -> None:
        self.contents = contents
        self.requests: list[tuple[str, str, str]] = []

    def fetch_contents(self, repository: str, ref: str, path: str) -> bytes:
        request = (repository, ref, path)
        self.requests.append(request)
        try:
            return self.contents[request]
        except KeyError as exc:
            raise materialize_pr_validation_inputs.MaterializationError(
                f"GitHub API request failed with HTTP 404 for {path}"
            ) from exc


class ClassificationTests(unittest.TestCase):
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

    def test_renamed_and_copied_data_files_are_still_classified(self) -> None:
        """GitHub reports a rename-with-edit as 'renamed'; skipping it would bypass validation."""
        files = [
            {
                "filename": "token-lists/mainnet.json",
                "status": "renamed",
                "previous_filename": "token-lists/prod-token-list.json",
            },
            {"filename": "token-lists/base.json", "status": "copied"},
            {"filename": "token-lists/arbitrum.json", "status": "changed"},
            {
                "filename": "machines/dusd/mainnet/rootfiles/20260807-renamed.toml",
                "status": "renamed",
            },
        ]

        result = materialize_pr_validation_inputs.classify_pull_request_files(files)

        self.assertEqual(
            result.token_list_paths,
            (
                "token-lists/arbitrum.json",
                "token-lists/base.json",
                "token-lists/mainnet.json",
            ),
        )
        self.assertEqual(
            result.rootfile_paths,
            ("machines/dusd/mainnet/rootfiles/20260807-renamed.toml",),
        )

    def test_removed_data_files_are_not_classified(self) -> None:
        """A deleted file has no head content to validate."""
        files = [
            {"filename": "token-lists/prod-token-list.json", "status": "removed"},
            {"filename": "machines/dusd/mainnet/rootfiles/20260807-gone.toml", "status": "removed"},
        ]

        result = materialize_pr_validation_inputs.classify_pull_request_files(files)

        self.assertEqual(result.token_list_paths, ())
        self.assertEqual(result.rootfile_paths, ())

    def test_unknown_status_on_an_allowlisted_path_fails_loudly(self) -> None:
        """A future GitHub status must fail the check, not silently drop validation."""
        files = [{"filename": "token-lists/prod-token-list.json", "status": "teleported"}]

        with self.assertRaises(materialize_pr_validation_inputs.MaterializationError):
            materialize_pr_validation_inputs.classify_pull_request_files(files)

    def test_unknown_status_outside_the_allowlist_is_ignored(self) -> None:
        """Only allowlisted data paths gate the check; unrelated files never do."""
        files = [{"filename": "README.md", "status": "teleported"}]

        result = materialize_pr_validation_inputs.classify_pull_request_files(files)

        self.assertEqual(result.token_list_paths, ())
        self.assertEqual(result.rootfile_paths, ())


class MaterializePrValidationInputsTests(unittest.TestCase):
    def test_materialization_fetches_only_rootfile_validation_dependencies(self) -> None:
        """Rootfile validation needs its rootfile, caliber and machine config—nothing else."""
        head_sha = "a" * 40
        rootfile = "machines/dusd/mainnet/rootfiles/20260807-safe.toml"
        caliber = "machines/dusd/mainnet/caliber.yaml"
        config = "machines/dusd/config.toml"
        api = FakeGitHubApi(
            {
                (BASE_REPOSITORY, head_sha, rootfile): b"[instructions]\n",
                (BASE_REPOSITORY, head_sha, caliber): b"positions: []\n",
                (BASE_REPOSITORY, head_sha, config): b"[calibers.mainnet]\naddress = '0x1'\n",
            }
        )
        classification = materialize_pr_validation_inputs.Classification(
            token_list_paths=(), rootfile_paths=(rootfile,)
        )

        with tempfile.TemporaryDirectory() as tempdir:
            destination = Path(tempdir) / "inputs"
            materialize_pr_validation_inputs.materialize_inputs(
                api=api,
                content_repositories=(BASE_REPOSITORY, HEAD_REPOSITORY),
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
                (BASE_REPOSITORY, head_sha, rootfile),
                (BASE_REPOSITORY, head_sha, caliber),
                (BASE_REPOSITORY, head_sha, config),
            ],
        )

    def test_fork_content_is_read_through_the_base_repository(self) -> None:
        """Fork commits stay reachable via the base repo after the fork is deleted."""
        head_sha = "b" * 40
        token_list = "token-lists/prod-token-list.json"
        api = FakeGitHubApi({(BASE_REPOSITORY, head_sha, token_list): b"{}\n"})
        classification = materialize_pr_validation_inputs.Classification(
            token_list_paths=(token_list,), rootfile_paths=()
        )

        with tempfile.TemporaryDirectory() as tempdir:
            destination = Path(tempdir) / "inputs"
            materialize_pr_validation_inputs.materialize_inputs(
                api=api,
                content_repositories=(BASE_REPOSITORY, HEAD_REPOSITORY),
                head_sha=head_sha,
                destination=destination,
                classification=classification,
                include_token_lists=True,
                include_rootfiles=False,
            )

            self.assertEqual((destination / token_list).read_bytes(), b"{}\n")

        # The fork is never contacted while the base repository serves the commit.
        self.assertEqual(api.requests, [(BASE_REPOSITORY, head_sha, token_list)])

    def test_fork_repository_is_used_as_a_fallback(self) -> None:
        """A base-repository miss must not fail validation outright."""
        head_sha = "c" * 40
        token_list = "token-lists/prod-token-list.json"
        api = FakeGitHubApi({(HEAD_REPOSITORY, head_sha, token_list): b"{}\n"})
        classification = materialize_pr_validation_inputs.Classification(
            token_list_paths=(token_list,), rootfile_paths=()
        )

        with tempfile.TemporaryDirectory() as tempdir:
            destination = Path(tempdir) / "inputs"
            materialize_pr_validation_inputs.materialize_inputs(
                api=api,
                content_repositories=(BASE_REPOSITORY, HEAD_REPOSITORY),
                head_sha=head_sha,
                destination=destination,
                classification=classification,
                include_token_lists=True,
                include_rootfiles=False,
            )

            self.assertEqual((destination / token_list).read_bytes(), b"{}\n")

        self.assertEqual(
            api.requests,
            [
                (BASE_REPOSITORY, head_sha, token_list),
                (HEAD_REPOSITORY, head_sha, token_list),
            ],
        )

    def test_missing_content_everywhere_is_an_error(self) -> None:
        """Silently materializing nothing would make the validation step a no-op."""
        head_sha = "d" * 40
        classification = materialize_pr_validation_inputs.Classification(
            token_list_paths=("token-lists/prod-token-list.json",), rootfile_paths=()
        )

        with tempfile.TemporaryDirectory() as tempdir:
            with self.assertRaises(materialize_pr_validation_inputs.MaterializationError):
                materialize_pr_validation_inputs.materialize_inputs(
                    api=FakeGitHubApi({}),
                    content_repositories=(BASE_REPOSITORY, HEAD_REPOSITORY),
                    head_sha=head_sha,
                    destination=Path(tempdir) / "inputs",
                    classification=classification,
                    include_token_lists=True,
                    include_rootfiles=False,
                )

    def test_head_movement_during_environment_approval_is_rejected(self) -> None:
        """Classifying the current head while fetching the approved one would either
        404 or validate a change set nobody approved."""
        approved = "a" * 40
        pushed = "e" * 40

        materialize_pr_validation_inputs.require_unchanged_head(approved, approved.upper())

        with self.assertRaises(materialize_pr_validation_inputs.MaterializationError):
            materialize_pr_validation_inputs.require_unchanged_head(approved, pushed)

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
