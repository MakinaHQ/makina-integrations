#!/usr/bin/env python3
"""Validate that every affected_token in a rootfile is a registered base token
on the corresponding Caliber contract.

Intended to run in CI on every PR that adds new rootfiles. The script:
  1. Picks the latest added rootfile per (machine, chain) pair.
  2. Reads caliber.yaml to get the caliber contract address.
  3. Parses the rootfile TOML to collect all unique affected_tokens.
  4. Queries the on-chain Caliber.isBaseToken(address) for each token.
  5. Reports any tokens that are NOT base tokens.

Required repo secret:
  - ALCHEMY_API_KEY
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

import yaml


ROOTFILE_PATH_RE = re.compile(r"^machines/([^/]+)/([^/]+)/rootfiles/([^/]+\.toml)$")

CHAIN_ALCHEMY_SLUG = {
    "mainnet": "eth-mainnet",
    "base": "base-mainnet",
    "arbitrum": "arb-mainnet",
    "monad": "monad-mainnet",
}

ICaliber_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "token", "type": "address"}],
        "name": "isBaseToken",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class BaseTokenChecker(Protocol):
    """Protocol for checking whether a token is a base token on a Caliber.
    Swappable in tests with a FakeChecker that returns canned data."""

    def is_base_token(self, caliber_address: str, token_address: str) -> bool:
        ...


@dataclass(frozen=True)
class RootfileTarget:
    machine: str
    chain: str
    rootfile_path: Path
    caliber_path: Path


@dataclass(frozen=True)
class ValidationResult:
    target: RootfileTarget
    caliber_address: str
    affected_tokens: list[str]
    non_base_tokens: list[str]

    @property
    def ok(self) -> bool:
        return not self.non_base_tokens


class RpcBaseTokenChecker:
    def __init__(self, chain: str, block_number: int | None = None):
        try:
            from web3 import Web3
        except ImportError as exc:
            raise RuntimeError("web3 is required to query Caliber base tokens") from exc

        self.block_number = block_number
        self.web3 = Web3(Web3.HTTPProvider(resolve_rpc_url(chain)))
        self._contracts: dict[str, object] = {}

    def is_base_token(self, caliber_address: str, token_address: str) -> bool:
        contract = self._get_contract(caliber_address)
        checksum_token = self.web3.to_checksum_address(token_address)
        return self._call(contract.functions.isBaseToken(checksum_token))

    def _get_contract(self, caliber_address: str) -> object:
        addr = caliber_address.lower()
        if addr not in self._contracts:
            checksum = self.web3.to_checksum_address(caliber_address)
            self._contracts[addr] = self.web3.eth.contract(address=checksum, abi=ICaliber_ABI)
        return self._contracts[addr]

    def _call(self, fn: object) -> object:
        if self.block_number is None:
            return fn.call()
        return fn.call(block_identifier=self.block_number)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that all affected_tokens in rootfiles are registered base tokens on the Caliber."
    )
    parser.add_argument("rootfiles", nargs="*", help="Added rootfile paths relative to the repository root.")
    parser.add_argument(
        "--block-number",
        type=int,
        help="Optional historical block number to pin all contract reads to.",
    )
    return parser.parse_args(argv)


def select_latest_rootfiles(rootfiles: Iterable[str]) -> list[RootfileTarget]:
    """From a list of added rootfile paths, keep only the latest one per
    (machine, chain) pair. "Latest" is determined by lexicographic filename
    comparison, which works because rootfiles are prefixed with YYYYMMDD."""
    latest_by_pair: dict[tuple[str, str], RootfileTarget] = {}
    for raw_path in rootfiles:
        match = ROOTFILE_PATH_RE.match(raw_path)
        if not match:
            continue

        machine, chain, _ = match.groups()
        rootfile_path = Path(raw_path)
        target = RootfileTarget(
            machine=machine,
            chain=chain,
            rootfile_path=rootfile_path,
            caliber_path=rootfile_path.parents[1] / "caliber.yaml",
        )
        pair = (machine, chain)
        current = latest_by_pair.get(pair)
        if current is None or target.rootfile_path.name > current.rootfile_path.name:
            latest_by_pair[pair] = target

    return sorted(latest_by_pair.values(), key=lambda target: (target.machine, target.chain))


class _PermissiveLoader(yaml.SafeLoader):
    """YAML loader that ignores custom tags like !include."""

_PermissiveLoader.add_multi_constructor("!", lambda _loader, _suffix, _node: None)


def extract_caliber_address(caliber_path: Path) -> str:
    """Parse caliber.yaml to extract the caliber contract address."""
    data = yaml.load(caliber_path.read_text(), Loader=_PermissiveLoader)

    try:
        return data["config"]["caliber_address"]["value"]
    except (KeyError, TypeError):
        pass

    config_toml_path = caliber_path.parents[1] / "config.toml"
    try:
        config_data = tomllib.loads(config_toml_path.read_text())
        chain = caliber_path.parent.name
        return config_data["calibers"][chain]["address"]
    except Exception as exc:
        raise ValueError(
            f"could not find Caliber address in `[calibers.{caliber_path.parent.name}].address` within {config_toml_path}"
        ) from exc


def extract_affected_tokens(rootfile_path: Path) -> set[str]:
    """Parse a rootfile TOML and collect all unique affected_tokens addresses."""
    data = tomllib.loads(rootfile_path.read_text())
    tokens: set[str] = set()
    _walk_for_affected_tokens(data.get("instructions", {}), tokens)
    return tokens


def _walk_for_affected_tokens(root: object, tokens: set[str]) -> None:
    """Walk the nested TOML instruction tree iteratively, collecting
    all addresses found in affected_tokens arrays."""
    stack: list[object] = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if "affected_tokens" in node:
                for addr in node["affected_tokens"]:
                    if addr:  # skip empty strings
                        tokens.add(addr.lower())
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def validate_target(target: RootfileTarget, checker: BaseTokenChecker) -> ValidationResult:
    """Check every affected_token in the rootfile against isBaseToken on-chain."""
    caliber_address = extract_caliber_address(target.caliber_path)
    affected_tokens = sorted(extract_affected_tokens(target.rootfile_path))

    non_base_tokens = [
        token for token in affected_tokens
        if not checker.is_base_token(caliber_address, token)
    ]

    return ValidationResult(
        target=target,
        caliber_address=caliber_address,
        affected_tokens=affected_tokens,
        non_base_tokens=non_base_tokens,
    )


def resolve_rpc_url(chain: str) -> str:
    slug = CHAIN_ALCHEMY_SLUG.get(chain)
    if slug is None:
        raise RuntimeError(f"unsupported chain '{chain}'. Supported: {', '.join(CHAIN_ALCHEMY_SLUG)}")

    api_key = os.getenv("ALCHEMY_API_KEY")
    if not api_key:
        raise RuntimeError("missing ALCHEMY_API_KEY environment variable")

    return f"https://{slug}.g.alchemy.com/v2/{api_key}"


def print_result(result: ValidationResult) -> None:
    print(
        f"Validated {result.target.rootfile_path} "
        f"(machine={result.target.machine}, chain={result.target.chain}, caliber={result.caliber_address})"
    )
    print(f"  Unique affected tokens: {len(result.affected_tokens)}")
    print(f"  Non-base tokens: {format_addrs(result.non_base_tokens)}")


def format_addrs(values: list[str]) -> str:
    if not values:
        return "none"
    return ", ".join(values)


def write_github_summary(results: list[ValidationResult]) -> None:
    """Write a markdown summary to $GITHUB_STEP_SUMMARY."""
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = ["## Base Token Validation\n"]
    for r in results:
        status = "Pass" if r.ok else "Fail"
        icon = "\u2705" if r.ok else "\u274c"
        lines.append(f"### {icon} `{r.target.machine}/{r.target.chain}` \u2014 {status}\n")
        lines.append(f"Rootfile: `{r.target.rootfile_path}`\n")
        lines.append("| Check | Result |")
        lines.append("|-------|--------|")
        lines.append(f"| Unique affected tokens | {len(r.affected_tokens)} |")
        lines.append(f"| Non-base tokens | {format_addrs(r.non_base_tokens)} |")
        lines.append("")

    with open(summary_path, "a") as f:
        f.write("\n".join(lines))


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    targets = select_latest_rootfiles(args.rootfiles)
    if not targets:
        print("No added rootfiles to validate.")
        return 0

    exit_code = 0
    results: list[ValidationResult] = []
    checkers: dict[str, RpcBaseTokenChecker] = {}
    for target in targets:
        checker = checkers.setdefault(
            target.chain, RpcBaseTokenChecker(target.chain, block_number=args.block_number)
        )
        try:
            result = validate_target(target, checker)
        except Exception as exc:
            print(f"Validation failed for {target.rootfile_path}: {exc}", file=sys.stderr)
            return 1

        print_result(result)
        results.append(result)
        if not result.ok:
            exit_code = 1

    write_github_summary(results)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
