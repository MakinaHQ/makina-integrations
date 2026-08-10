#!/usr/bin/env python3
"""Fetch allowlisted pull-request data without executing a pull-request checkout."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


MAX_CHANGED_FILES = 1_000
MAX_FILE_BYTES = 5 * 1024 * 1024
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
TOKEN_LIST_RE = re.compile(r"^token-lists/[A-Za-z0-9][A-Za-z0-9._-]*\.json$")
ROOTFILE_RE = re.compile(
    r"^machines/([A-Za-z0-9][A-Za-z0-9._-]*)/"
    r"([A-Za-z0-9][A-Za-z0-9._-]*)/rootfiles/"
    r"([A-Za-z0-9][A-Za-z0-9._-]*\.toml)$"
)

# Every file status the GitHub pull-request files API is documented to return.
# An allowlisted path carrying a status outside this set is a hard error rather
# than a silent skip, so a future API addition cannot quietly drop validation.
KNOWN_FILE_STATUSES = frozenset(
    {"added", "removed", "modified", "renamed", "copied", "changed", "unchanged"}
)
# Statuses where the file exists at the pull-request head and its content differs
# from the base revision. A rename that also edits content reports "renamed", so
# restricting this to {added, modified} would skip validation entirely.
CHANGED_AT_HEAD_STATUSES = frozenset({"added", "modified", "renamed", "copied", "changed"})
# Statuses that put a file at a path the base revision did not have, which is what
# "newly added rootfile" means for open-position validation.
NEW_PATH_STATUSES = frozenset({"added", "renamed", "copied"})


class MaterializationError(RuntimeError):
    """Raised when untrusted pull-request data cannot safely be materialized."""


class GitHubApi(Protocol):
    """The small GitHub API surface needed by the materializer."""

    def fetch_contents(self, repository: str, ref: str, path: str) -> bytes: ...


@dataclass(frozen=True)
class Classification:
    """The only PR paths permitted to become privileged validation input."""

    token_list_paths: tuple[str, ...]
    rootfile_paths: tuple[str, ...]


def validate_repository(repository: str) -> str:
    """Validate a GitHub owner/repository value before building an API URL."""
    if not REPOSITORY_RE.fullmatch(repository):
        raise MaterializationError(f"invalid GitHub repository name: {repository!r}")
    return repository


def validate_sha(sha: str) -> str:
    """Require an immutable Git object identifier for every content request."""
    if not SHA_RE.fullmatch(sha):
        raise MaterializationError("head SHA must be a full 40-character hexadecimal commit ID")
    return sha


def classify_pull_request_files(files: Sequence[object]) -> Classification:
    """Select only token lists and newly added rootfiles from GitHub PR metadata."""
    token_list_paths: set[str] = set()
    rootfile_paths: set[str] = set()

    for entry in files:
        if not isinstance(entry, dict):
            continue
        filename = entry.get("filename")
        status = entry.get("status")
        if not isinstance(filename, str) or not isinstance(status, str):
            continue

        is_token_list = TOKEN_LIST_RE.fullmatch(filename) is not None
        is_rootfile = ROOTFILE_RE.fullmatch(filename) is not None
        if not is_token_list and not is_rootfile:
            continue
        if status not in KNOWN_FILE_STATUSES:
            raise MaterializationError(
                f"unrecognized GitHub file status {status!r} for {filename!r}; "
                "refusing to classify this pull request"
            )

        if is_token_list and status in CHANGED_AT_HEAD_STATUSES:
            token_list_paths.add(filename)
        elif is_rootfile and status in NEW_PATH_STATUSES:
            rootfile_paths.add(filename)

    return Classification(
        token_list_paths=tuple(sorted(token_list_paths)),
        rootfile_paths=tuple(sorted(rootfile_paths)),
    )


def rootfile_dependencies(rootfile_path: str) -> tuple[str, str]:
    """Return the two trusted-validator data dependencies of an added rootfile."""
    match = ROOTFILE_RE.fullmatch(rootfile_path)
    if match is None:
        raise MaterializationError(f"rootfile path is not allowlisted: {rootfile_path!r}")
    machine, chain, _ = match.groups()
    return f"machines/{machine}/{chain}/caliber.yaml", f"machines/{machine}/config.toml"


def write_file(destination: Path, relative_path: str, content: bytes) -> None:
    """Write a fetched file only if its resolved path remains under destination."""
    path = PurePosixPath(relative_path)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise MaterializationError(f"refusing unsafe relative path: {relative_path!r}")

    root = destination.resolve()
    target = (root / Path(*path.parts)).resolve()
    if target != root and root not in target.parents:
        raise MaterializationError(f"refusing to write outside destination: {relative_path!r}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


class GitHubRestApi:
    """Minimal GitHub REST client; it never invokes a shell or git checkout."""

    def __init__(self, token: str, api_url: str | None = None) -> None:
        if not token:
            raise MaterializationError("GITHUB_TOKEN is required")
        self.token = token
        self.api_url = (api_url or "https://api.github.com").rstrip("/")

    def _headers(self, accept: str) -> dict[str, str]:
        return {
            "Accept": accept,
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "makina-pr-validation-materializer/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def request_json(self, url: str) -> Any:
        request = Request(url, headers=self._headers("application/vnd.github+json"))
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            raise MaterializationError(f"GitHub API request failed with HTTP {exc.code}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise MaterializationError("GitHub API request failed") from exc

    def request_bytes(self, url: str, accept: str, limit: int) -> bytes:
        """Read at most limit + 1 bytes so an oversized blob cannot exhaust memory."""
        request = Request(url, headers=self._headers(accept))
        try:
            with urlopen(request, timeout=30) as response:
                return response.read(limit + 1)
        except HTTPError as exc:
            raise MaterializationError(f"GitHub API request failed with HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise MaterializationError("GitHub API request failed") from exc

    def get_pull_request_head_sha(self, repository: str, pull_number: int) -> str:
        """Return the pull request's current head commit."""
        validate_repository(repository)
        if pull_number < 1:
            raise MaterializationError("pull request number must be positive")
        payload = self.request_json(f"{self.api_url}/repos/{repository}/pulls/{pull_number}")
        if not isinstance(payload, dict):
            raise MaterializationError("GitHub API returned an invalid pull-request response")
        head = payload.get("head")
        sha = head.get("sha") if isinstance(head, dict) else None
        if not isinstance(sha, str):
            raise MaterializationError("GitHub API returned no pull-request head SHA")
        return validate_sha(sha)

    def list_pull_request_files(self, repository: str, pull_number: int) -> list[object]:
        """Return all changed files, rejecting excessive PRs before data retrieval."""
        validate_repository(repository)
        if pull_number < 1:
            raise MaterializationError("pull request number must be positive")

        files: list[object] = []
        page = 1
        while True:
            query = urlencode({"per_page": "100", "page": str(page)})
            payload = self.request_json(
                f"{self.api_url}/repos/{repository}/pulls/{pull_number}/files?{query}"
            )
            if not isinstance(payload, list):
                raise MaterializationError("GitHub API returned an invalid pull-request files response")
            files.extend(payload)
            if len(files) > MAX_CHANGED_FILES:
                raise MaterializationError(f"pull request changes more than {MAX_CHANGED_FILES} files")
            if len(payload) < 100:
                return files
            page += 1

    def fetch_contents(self, repository: str, ref: str, path: str) -> bytes:
        """Fetch one file's raw bytes from a fixed repository commit.

        The raw media type is used deliberately: the JSON representation omits
        `content` for blobs larger than 1 MB, which would make MAX_FILE_BYTES
        unreachable and turn an oversized rootfile into a misleading API error.
        """
        validate_repository(repository)
        validate_sha(ref)
        safe_path = quote(path, safe="/")
        content = self.request_bytes(
            f"{self.api_url}/repos/{repository}/contents/{safe_path}?{urlencode({'ref': ref})}",
            "application/vnd.github.raw+json",
            MAX_FILE_BYTES,
        )
        if len(content) > MAX_FILE_BYTES:
            raise MaterializationError(f"refusing {path}: file exceeds {MAX_FILE_BYTES} bytes")
        return content


def require_unchanged_head(approved_head_sha: str, current_head_sha: str) -> None:
    """Refuse to materialize when the pull request moved under the running job.

    The changed-file list is always the pull request's current state while the
    head SHA is pinned to the commit the workflow — and its environment reviewer —
    approved. Classifying against one commit and fetching another either 404s or
    silently validates a different change set than the one that was approved.
    """
    if validate_sha(current_head_sha).lower() != validate_sha(approved_head_sha).lower():
        raise MaterializationError(
            f"pull request head moved from {approved_head_sha} to {current_head_sha} "
            "after this run started; re-run the workflow so classification, content "
            "and approval all cover the same commit"
        )


def fetch_from_first_available(
    api: GitHubApi, repositories: Sequence[str], ref: str, path: str
) -> bytes:
    """Fetch path@ref from the first repository that serves it.

    Fork pull-request commits are reachable through the base repository, which
    keeps validation working after the contributor deletes their fork or branch.
    The fork is only a fallback for the rare case where the base repository has
    not yet observed the commit.
    """
    if not repositories:
        raise MaterializationError("no content repository was configured")
    last_error: MaterializationError | None = None
    for repository in repositories:
        try:
            return api.fetch_contents(repository, ref, path)
        except MaterializationError as exc:
            last_error = exc
    raise MaterializationError(
        f"could not fetch {path} at {ref} from any of {', '.join(repositories)}: {last_error}"
    ) from last_error


def materialize_inputs(
    *,
    api: GitHubApi,
    content_repositories: Sequence[str],
    head_sha: str,
    destination: Path,
    classification: Classification,
    include_token_lists: bool,
    include_rootfiles: bool,
) -> tuple[str, ...]:
    """Fetch exactly the data the trusted validators need into destination."""
    repositories = tuple(validate_repository(repository) for repository in content_repositories)
    validate_sha(head_sha)

    paths: list[str] = []
    if include_token_lists:
        paths.extend(classification.token_list_paths)
    if include_rootfiles:
        for rootfile_path in classification.rootfile_paths:
            paths.append(rootfile_path)
            paths.extend(rootfile_dependencies(rootfile_path))

    unique_paths = tuple(dict.fromkeys(paths))
    for path in unique_paths:
        write_file(destination, path, fetch_from_first_available(api, repositories, head_sha, path))
    return unique_paths


def write_classification_output(classification: Classification) -> None:
    """Expose classification to GitHub Actions without exposing file content."""
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as output:
        output.write(f"token_lists={'true' if classification.token_list_paths else 'false'}\n")
        output.write(f"rootfiles={'true' if classification.rootfile_paths else 'false'}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    classify = subparsers.add_parser("classify", help="classify changed PR data files")
    classify.add_argument("--repository", required=True)
    classify.add_argument("--pull-number", required=True, type=int)

    materialize = subparsers.add_parser("materialize", help="write selected PR data files safely")
    materialize.add_argument("--repository", required=True)
    materialize.add_argument("--pull-number", required=True, type=int)
    materialize.add_argument("--head-repository", required=True)
    materialize.add_argument("--head-sha", required=True)
    materialize.add_argument("--destination", required=True, type=Path)
    materialize.add_argument("--token-lists", action="store_true")
    materialize.add_argument("--rootfiles", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        api = GitHubRestApi(os.getenv("GITHUB_TOKEN", ""), os.getenv("GITHUB_API_URL"))

        if args.command == "classify":
            classification = classify_pull_request_files(
                api.list_pull_request_files(args.repository, args.pull_number)
            )
            write_classification_output(classification)
            print(
                f"Token lists: {len(classification.token_list_paths)}; "
                f"added rootfiles: {len(classification.rootfile_paths)}"
            )
            return 0

        if not args.token_lists and not args.rootfiles:
            raise MaterializationError("select --token-lists and/or --rootfiles")

        approved_head_sha = validate_sha(args.head_sha)
        require_unchanged_head(
            approved_head_sha,
            api.get_pull_request_head_sha(args.repository, args.pull_number),
        )

        classification = classify_pull_request_files(
            api.list_pull_request_files(args.repository, args.pull_number)
        )
        materialized = materialize_inputs(
            api=api,
            content_repositories=(args.repository, args.head_repository),
            head_sha=approved_head_sha,
            destination=args.destination,
            classification=classification,
            include_token_lists=args.token_lists,
            include_rootfiles=args.rootfiles,
        )
        print(f"Materialized {len(materialized)} trusted validation input file(s).")
        return 0
    except MaterializationError as exc:
        print(f"PR validation input error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
