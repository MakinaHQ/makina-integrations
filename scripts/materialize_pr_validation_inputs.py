#!/usr/bin/env python3
"""Fetch allowlisted pull-request data without executing a pull-request checkout."""

from __future__ import annotations

import argparse
import base64
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
        if status in {"added", "modified"} and TOKEN_LIST_RE.fullmatch(filename):
            token_list_paths.add(filename)
        elif status == "added" and ROOTFILE_RE.fullmatch(filename):
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

    def request_json(self, url: str) -> Any:
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "makina-pr-validation-materializer/1.0",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            raise MaterializationError(f"GitHub API request failed with HTTP {exc.code}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise MaterializationError("GitHub API request failed") from exc

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
        """Fetch one base64-encoded file from a fixed repository commit."""
        validate_repository(repository)
        validate_sha(ref)
        safe_path = quote(path, safe="/")
        payload = self.request_json(
            f"{self.api_url}/repos/{repository}/contents/{safe_path}?{urlencode({'ref': ref})}"
        )
        if not isinstance(payload, dict) or payload.get("encoding") != "base64":
            raise MaterializationError(f"GitHub API did not return base64 file contents for {path}")
        encoded_content = payload.get("content")
        if not isinstance(encoded_content, str):
            raise MaterializationError(f"GitHub API returned invalid file contents for {path}")
        try:
            content = base64.b64decode("".join(encoded_content.split()), validate=True)
        except ValueError as exc:
            raise MaterializationError(f"GitHub API returned invalid base64 file contents for {path}") from exc
        if len(content) > MAX_FILE_BYTES:
            raise MaterializationError(f"refusing {path}: file exceeds {MAX_FILE_BYTES} bytes")
        return content


def materialize_inputs(
    *,
    api: GitHubApi,
    repository: str,
    head_sha: str,
    destination: Path,
    classification: Classification,
    include_token_lists: bool,
    include_rootfiles: bool,
) -> tuple[str, ...]:
    """Fetch exactly the data the trusted validators need into destination."""
    validate_repository(repository)
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
        write_file(destination, path, api.fetch_contents(repository, head_sha, path))
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
        classification = classify_pull_request_files(
            api.list_pull_request_files(args.repository, args.pull_number)
        )
        if args.command == "classify":
            write_classification_output(classification)
            print(
                f"Token lists: {len(classification.token_list_paths)}; "
                f"added rootfiles: {len(classification.rootfile_paths)}"
            )
            return 0

        if not args.token_lists and not args.rootfiles:
            raise MaterializationError("select --token-lists and/or --rootfiles")
        materialized = materialize_inputs(
            api=api,
            repository=args.head_repository,
            head_sha=args.head_sha,
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
