#!/usr/bin/env python3
"""Reject rootfiles that hardcode a known non-prod / test-infra Makina address.

This is the prod repo (makina-integrations): rootfiles here go on-chain against
production deployments, so every Makina infra address a rootfile embeds
(OracleRegistry, MathHelper, SwapModule, WeirollVM, registries, beacons, bridge
adapters, ...) MUST be the prod address. Source config PRs are frequently authored
against test infra, so a test address can leak all the way into a generated rootfile.

Infra addresses land in the transpiled rootfile as the trailing 20 bytes of Weiroll
command words, so they appear as a lowercase 40-hex-char substring of the raw TOML
text regardless of where they sit in a command word. This validator therefore scans
the raw text of each changed rootfile for any address on the denylist
(scripts/non_prod_infra.json) rather than parsing structured fields.

Exit code 0 = all clean, 1 = a denylisted address was found.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Extracts (machine, chain, filename) from a rootfile path like
# "machines/dusd/mainnet/rootfiles/20260311-batch.toml"
ROOTFILE_PATH_RE = re.compile(
    r"^machines/([^/]+)/([^/]+)/rootfiles/([^/]+\.toml)$"
)

DENYLIST_PATH = Path(__file__).resolve().parent / "non_prod_infra.json"


@dataclass(frozen=True)
class DenylistEntry:
    address: str  # checksummed / original form, for display
    body: str  # lowercase 40-hex body (no 0x), used for matching
    label: str


@dataclass(frozen=True)
class InfraHit:
    address: str
    label: str


@dataclass(frozen=True)
class ValidationResult:
    rootfile_path: str
    machine: str
    chain: str
    hits: list[InfraHit]

    @property
    def ok(self) -> bool:
        return not self.hits


def load_denylist(path: Path = DENYLIST_PATH) -> list[DenylistEntry]:
    """Load and normalize the non-prod infra denylist."""
    data = json.loads(path.read_text())
    entries: list[DenylistEntry] = []
    for item in data["addresses"]:
        address = item["address"]
        body = address.lower().removeprefix("0x")
        if len(body) != 40 or not all(c in "0123456789abcdef" for c in body):
            raise ValueError(f"Malformed address in denylist: {address!r}")
        entries.append(
            DenylistEntry(address=address, body=body, label=item["label"])
        )
    return entries


def validate_rootfile_from_text(
    rootfile_path: str, text: str, denylist: list[DenylistEntry]
) -> ValidationResult | None:
    """Scan rootfile text for denylisted addresses.
    Returns None if the path doesn't match the rootfile pattern."""
    match = ROOTFILE_PATH_RE.match(rootfile_path)
    if not match:
        return None

    machine, chain, _ = match.groups()
    haystack = text.lower()
    hits = [
        InfraHit(address=entry.address, label=entry.label)
        for entry in denylist
        if entry.body in haystack
    ]
    return ValidationResult(
        rootfile_path=rootfile_path, machine=machine, chain=chain, hits=hits
    )


def validate_rootfile(
    rootfile_path: str, denylist: list[DenylistEntry]
) -> ValidationResult | None:
    """Load a rootfile from disk and scan it for denylisted addresses."""
    if not ROOTFILE_PATH_RE.match(rootfile_path):
        return None
    text = Path(rootfile_path).read_text()
    return validate_rootfile_from_text(rootfile_path, text, denylist)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reject rootfiles containing known non-prod / test-infra addresses."
    )
    parser.add_argument(
        "rootfiles",
        nargs="*",
        help="Rootfile paths relative to the repository root.",
    )
    return parser.parse_args(argv)


def print_result(result: ValidationResult) -> None:
    print(f"Scanned {result.rootfile_path} (machine={result.machine}, chain={result.chain})")
    if result.ok:
        print("  No non-prod infra addresses found.")
        return
    for hit in result.hits:
        # GitHub Actions annotation so the error surfaces on the PR file view.
        print(
            f"::error file={result.rootfile_path}::Contains non-prod infra address "
            f"{hit.address} ({hit.label}) — must be the prod address."
        )


def write_github_summary(results: list[ValidationResult]) -> None:
    """Write a markdown summary to $GITHUB_STEP_SUMMARY so results are visible
    directly on the PR checks page without digging into logs."""
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = ["## Non-Prod Infra Address Check\n"]
    for r in results:
        status = "Pass" if r.ok else "Fail"
        icon = "✅" if r.ok else "❌"
        lines.append(f"### {icon} `{r.machine}/{r.chain}` — {status}\n")
        lines.append(f"Rootfile: `{r.rootfile_path}`\n")
        if not r.ok:
            lines.append("**Non-prod infra addresses found:**\n")
            for hit in r.hits:
                lines.append(f"- `{hit.address}` — {hit.label}")
        lines.append("")

    with open(summary_path, "a") as f:
        f.write("\n".join(lines))


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.rootfiles:
        print("No rootfiles to scan.")
        return 0

    denylist = load_denylist()

    results: list[ValidationResult] = []
    for rootfile_path in args.rootfiles:
        result = validate_rootfile(rootfile_path, denylist)
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
