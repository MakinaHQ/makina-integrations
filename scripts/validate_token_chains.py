#!/usr/bin/env python3
"""Validate that rootfile token_list references use the correct chain.

Parses [tokens."${token_list.<chain>.<SYMBOL>}"] entries in rootfile TOML
files and checks:
  1. The <chain> matches the directory the rootfile lives in.
  2. The chainId field matches the expected value for that chain.

Exit code 0 = all good, 1 = mismatches found.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Extracts (machine, chain, filename) from a rootfile path like
# "machines/dusd/mainnet/rootfiles/20260311-batch.toml"
ROOTFILE_PATH_RE = re.compile(
    r"^machines/([^/]+)/([^/]+)/rootfiles/([^/]+\.toml)$"
)

# Extracts (chain, symbol) from a token_list key like
# "${token_list.mainnet.USDC}"
TOKEN_LIST_REF_RE = re.compile(
    r"^\$\{token_list\.([^.]+)\.([^}]+)\}$"
)

CHAIN_TO_CHAIN_ID: dict[str, int] = {
    "mainnet": 1,
    "base": 8453,
    "arbitrum": 42161,
    "monad": 10143,
}


@dataclass(frozen=True)
class TokenMismatch:
    token_key: str
    expected_chain: str
    actual_chain: str


@dataclass(frozen=True)
class ChainIdMismatch:
    token_key: str
    chain: str
    expected_chain_id: int
    actual_chain_id: int


@dataclass(frozen=True)
class ValidationResult:
    rootfile_path: str
    machine: str
    expected_chain: str
    token_count: int
    token_chain_mismatches: list[TokenMismatch]
    chain_id_mismatches: list[ChainIdMismatch]

    @property
    def ok(self) -> bool:
        return not (self.token_chain_mismatches or self.chain_id_mismatches)


def validate_rootfile_from_data(
    rootfile_path: str, data: dict
) -> ValidationResult | None:
    """Validate token_list chain references given pre-parsed TOML data.
    Returns None if the path doesn't match the rootfile pattern."""
    match = ROOTFILE_PATH_RE.match(rootfile_path)
    if not match:
        return None

    machine, expected_chain, _ = match.groups()
    tokens = data.get("tokens", {})
    expected_chain_id = CHAIN_TO_CHAIN_ID.get(expected_chain)

    token_chain_mismatches: list[TokenMismatch] = []
    chain_id_mismatches: list[ChainIdMismatch] = []

    for token_key, token_data in tokens.items():
        ref_match = TOKEN_LIST_REF_RE.match(token_key)
        if not ref_match:
            continue

        actual_chain, _symbol = ref_match.groups()

        # Check 1: chain name in token_list ref matches directory chain
        if actual_chain != expected_chain:
            token_chain_mismatches.append(
                TokenMismatch(
                    token_key=token_key,
                    expected_chain=expected_chain,
                    actual_chain=actual_chain,
                )
            )

        # Check 2: chainId in token data matches expected chainId for the
        # directory chain (not the referenced chain). This catches cases where
        # the chainId is wrong relative to where the rootfile lives.
        chain_id = token_data.get("chainId")
        if (
            chain_id is not None
            and expected_chain_id is not None
            and int(chain_id) != expected_chain_id
        ):
            actual_chain_id = int(chain_id)
            chain_id_mismatches.append(
                ChainIdMismatch(
                    token_key=token_key,
                    chain=expected_chain,
                    expected_chain_id=expected_chain_id,
                    actual_chain_id=actual_chain_id,
                )
            )

    return ValidationResult(
        rootfile_path=rootfile_path,
        machine=machine,
        expected_chain=expected_chain,
        token_count=len(tokens),
        token_chain_mismatches=token_chain_mismatches,
        chain_id_mismatches=chain_id_mismatches,
    )


def validate_rootfile(rootfile_path: str) -> ValidationResult | None:
    """Load a rootfile from disk and validate its token_list chain references."""
    if not ROOTFILE_PATH_RE.match(rootfile_path):
        return None
    data = tomllib.loads(Path(rootfile_path).read_text())
    # validate_rootfile_from_data re-matches the path to extract groups;
    # the compiled regex makes this negligible vs. the file I/O above.
    return validate_rootfile_from_data(rootfile_path, data)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that rootfile token_list references use the correct chain."
    )
    parser.add_argument(
        "rootfiles",
        nargs="*",
        help="Rootfile paths relative to the repository root.",
    )
    return parser.parse_args(argv)


def format_mismatches(mismatches: list[TokenMismatch] | list[ChainIdMismatch]) -> str:
    if not mismatches:
        return "none"
    return ", ".join(m.token_key for m in mismatches)


def print_result(result: ValidationResult) -> None:
    print(
        f"Validated {result.rootfile_path} "
        f"(machine={result.machine}, chain={result.expected_chain})"
    )
    print(f"  Tokens checked: {result.token_count}")
    print(f"  Chain mismatches: {format_mismatches(result.token_chain_mismatches)}")
    print(f"  ChainId mismatches: {format_mismatches(result.chain_id_mismatches)}")
    for m in result.token_chain_mismatches:
        print(
            f"    -> {m.token_key} references chain "
            f"'{m.actual_chain}' but rootfile is in '{m.expected_chain}/' directory"
        )
    for m in result.chain_id_mismatches:
        print(
            f"    -> {m.token_key} has chainId={m.actual_chain_id} "
            f"but expected {m.expected_chain_id} for chain '{m.chain}'"
        )


def write_github_summary(results: list[ValidationResult]) -> None:
    """Write a markdown summary to $GITHUB_STEP_SUMMARY so results are
    visible directly on the PR checks page without digging into logs."""
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = ["## Token Chain Validation\n"]
    for r in results:
        status = "Pass" if r.ok else "Fail"
        icon = "\u2705" if r.ok else "\u274c"
        lines.append(f"### {icon} `{r.machine}/{r.expected_chain}` \u2014 {status}\n")
        lines.append(f"Rootfile: `{r.rootfile_path}`\n")
        lines.append("| Check | Result |")
        lines.append("|-------|--------|")
        lines.append(f"| Tokens checked | {r.token_count} |")
        lines.append(f"| Chain mismatches | {format_mismatches(r.token_chain_mismatches)} |")
        lines.append(f"| ChainId mismatches | {format_mismatches(r.chain_id_mismatches)} |")
        if not r.ok:
            lines.append("")
            lines.append("**Details:**\n")
            for m in r.token_chain_mismatches:
                lines.append(
                    f"- `{m.token_key}`: references chain `{m.actual_chain}`, "
                    f"expected `{m.expected_chain}`"
                )
            for m in r.chain_id_mismatches:
                lines.append(
                    f"- `{m.token_key}`: chainId={m.actual_chain_id}, "
                    f"expected {m.expected_chain_id}"
                )
        lines.append("")

    with open(summary_path, "a") as f:
        f.write("\n".join(lines))


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.rootfiles:
        print("No rootfiles to validate.")
        return 0

    results: list[ValidationResult] = []
    for rootfile_path in args.rootfiles:
        result = validate_rootfile(rootfile_path)
        if result is not None:
            results.append(result)

    if not results:
        print("No matching rootfiles found.")
        return 0

    exit_code = 0
    for result in results:
        print_result(result)
        if not result.ok:
            exit_code = 1

    write_github_summary(results)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
