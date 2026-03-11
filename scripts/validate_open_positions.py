#!/usr/bin/env python3
"""Validate that every open on-chain Caliber position has a matching
accounting instruction in the latest added rootfile.

Intended to run in CI on every PR that adds new rootfiles. The script:
  1. Picks the latest added rootfile per (machine, chain) pair.
  2. Reads the caliber.yaml to get the caliber address and declared position ids.
  3. Queries the on-chain Caliber contract to get currently open positions.
  4. Parses the rootfile TOML to find which positions have accounting entries.
  5. Reports any mismatches: missing accounting, missing caliber entries, or duplicates.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol


# Extracts (machine, chain, filename) from a rootfile path like
# "machines/dusd/mainnet/rootfiles/20260311-batch.toml"
ROOTFILE_PATH_RE = re.compile(r"^machines/([^/]+)/([^/]+)/rootfiles/([^/]+\.toml)$")

# Matches the caliber_address block in caliber.yaml. The address sits on a
# separate `value:` line below the `caliber_address:` key due to YAML structure.
CALIBER_ADDRESS_RE = re.compile(r"^\s*caliber_address:\s*$.*?^\s*value:\s*\"(0x[a-fA-F0-9]{40})\"\s*$", re.M | re.S)

# Matches position id declarations like `- id: "12345"` in caliber.yaml.
POSITION_ID_RE = re.compile(r'^\s*-\s+id:\s*"(\d+)"\s*$', re.M)

# Each chain must declare its own RPC env var(s). The first set var wins.
CHAIN_RPC_ENV_VARS = {
    "mainnet": ("ETHEREUM_MAINNET_RPC_URL",),
    "base": ("BASE_RPC_URL",),
    "arbitrum": ("ARBITRUM_RPC_URL",),
    "monad": ("MONAD_RPC_URL",),
}

# Minimal ABI for the Caliber contract — only the functions needed to
# enumerate positions and check which ones are open (value > 0).
ICaliber_ABI = [
    {
        "inputs": [],
        "name": "getPositionsLength",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "idx", "type": "uint256"}],
        "name": "getPositionId",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "id", "type": "uint256"}],
        "name": "getPosition",
        "outputs": [
            {
                "components": [
                    {"internalType": "uint256", "name": "lastAccountingTime", "type": "uint256"},
                    {"internalType": "uint256", "name": "value", "type": "uint256"},
                    {"internalType": "bool", "name": "isDebt", "type": "bool"},
                ],
                "internalType": "struct ICaliber.Position",
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


class CaliberReader(Protocol):
    """Protocol for reading open position ids from a Caliber contract.
    Swappable in tests with a FakeReader that returns canned data."""

    def get_open_position_ids(self, caliber_address: str) -> list[str]:
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
    open_position_ids: list[str]
    missing_in_caliber: list[str]
    missing_in_rootfile: list[str]
    duplicate_accounting: list[str]

    @property
    def ok(self) -> bool:
        return not (self.missing_in_caliber or self.missing_in_rootfile or self.duplicate_accounting)


class RpcCaliberReader:
    def __init__(self, chain: str, block_number: int | None = None):
        self.chain = chain
        self.block_number = block_number
        self.rpc_url = resolve_rpc_url(chain)

    def get_open_position_ids(self, caliber_address: str) -> list[str]:
        """Query the on-chain Caliber contract and return ids of positions
        whose value is > 0 (i.e. currently open / non-zero balance)."""
        try:
            from web3 import Web3  # deferred import — only needed for live RPC
        except ImportError as exc:
            raise RuntimeError("web3 is required to query live Caliber positions") from exc

        web3 = Web3(Web3.HTTPProvider(self.rpc_url))
        checksum_address = web3.to_checksum_address(caliber_address)
        contract = web3.eth.contract(address=checksum_address, abi=ICaliber_ABI)
        positions_length = self._call(contract.functions.getPositionsLength())

        # Enumerate all positions by index, then filter to open ones.
        # A position is "open" when its value field is non-zero.
        open_position_ids: list[str] = []
        for index in range(positions_length):
            position_id = self._call(contract.functions.getPositionId(index))
            position = self._call(contract.functions.getPosition(position_id))
            position_value = int(position[1])  # tuple: (lastAccountingTime, value, isDebt)
            if position_value > 0:
                open_position_ids.append(str(position_id))
        return open_position_ids

    def _call(self, fn: object) -> object:
        if self.block_number is None:
            return fn.call()
        return fn.call(block_identifier=self.block_number)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that latest added rootfiles contain accounting instructions for every open on-chain Caliber position."
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


def extract_caliber_metadata(caliber_path: Path) -> tuple[str, set[str]]:
    """Parse caliber.yaml with regexes to extract the caliber contract address
    and the set of declared position ids. Uses regexes instead of a YAML parser
    to avoid a pyyaml dependency (web3 is already heavy enough)."""
    content = caliber_path.read_text()
    caliber_address_match = CALIBER_ADDRESS_RE.search(content)
    if caliber_address_match is None:
        raise ValueError(f"could not find caliber_address in {caliber_path}")

    caliber_address = caliber_address_match.group(1)
    position_ids = set(POSITION_ID_RE.findall(content))
    if not position_ids:
        raise ValueError(f"could not find any position ids in {caliber_path}")

    return caliber_address, position_ids


def extract_accounting_counts(rootfile_path: Path) -> Counter[str]:
    """Parse a rootfile TOML and count how many accounting instructions
    (instruction_type == 1) exist per position_id."""
    data = tomllib.loads(rootfile_path.read_text())
    accounting_counts: Counter[str] = Counter()
    walk_instruction_tree(data.get("instructions", {}), accounting_counts)
    return accounting_counts


def walk_instruction_tree(root: object, accounting_counts: Counter[str]) -> None:
    """Walk the nested TOML instruction tree iteratively, counting nodes
    that have both position_id and instruction_type == 1 (accounting)."""
    stack = [root]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        if {"position_id", "instruction_type"} <= node.keys():
            if int(node["instruction_type"]) == 1:
                accounting_counts[str(node["position_id"])] += 1
        stack.extend(node.values())


def validate_target(target: RootfileTarget, reader: CaliberReader) -> ValidationResult:
    """Cross-check a rootfile against the live on-chain state:
    - missing_in_caliber: open on-chain but not declared in caliber.yaml
    - missing_in_rootfile: open on-chain but no accounting instruction in the rootfile
    - duplicate_accounting: accounted for more than once in the rootfile"""
    caliber_address, caliber_position_ids = extract_caliber_metadata(target.caliber_path)
    open_ids_set = set(reader.get_open_position_ids(caliber_address))
    open_position_ids = sorted(open_ids_set, key=int)
    accounting_counts = extract_accounting_counts(target.rootfile_path)

    missing_in_caliber = sorted(open_ids_set - caliber_position_ids, key=int)
    missing_in_rootfile = sorted(open_ids_set - set(accounting_counts), key=int)
    duplicate_accounting = sorted(
        [position_id for position_id in open_position_ids if accounting_counts[position_id] > 1],
        key=int,
    )

    return ValidationResult(
        target=target,
        caliber_address=caliber_address,
        open_position_ids=open_position_ids,
        missing_in_caliber=missing_in_caliber,
        missing_in_rootfile=missing_in_rootfile,
        duplicate_accounting=duplicate_accounting,
    )


def resolve_rpc_url(chain: str) -> str:
    env_var_names = CHAIN_RPC_ENV_VARS.get(chain)
    if env_var_names is None:
        raise RuntimeError(f"unsupported chain '{chain}'. Supported: {', '.join(CHAIN_RPC_ENV_VARS)}")

    for env_var_name in env_var_names:
        value = os.getenv(env_var_name)
        if value:
            return value

    env_var_list = ", ".join(env_var_names)
    raise RuntimeError(f"missing RPC URL for chain '{chain}'. Set one of: {env_var_list}")


def print_result(result: ValidationResult) -> None:
    print(
        f"Validated {result.target.rootfile_path} "
        f"(machine={result.target.machine}, chain={result.target.chain}, caliber={result.caliber_address})"
    )
    print(f"  Open positions on-chain: {len(result.open_position_ids)}")
    print(f"  Missing in caliber.yaml: {format_ids(result.missing_in_caliber)}")
    print(f"  Missing accounting in rootfile: {format_ids(result.missing_in_rootfile)}")
    print(f"  Duplicate accounting entries: {format_ids(result.duplicate_accounting)}")


def format_ids(values: list[str]) -> str:
    if not values:
        return "none"
    return ", ".join(values)


def write_github_summary(results: list[ValidationResult]) -> None:
    """Write a markdown summary to $GITHUB_STEP_SUMMARY so results are
    visible directly on the PR checks page without digging into logs."""
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = ["## Open Positions Validation\n"]
    for r in results:
        status = "Pass" if r.ok else "Fail"
        icon = "\u2705" if r.ok else "\u274c"
        lines.append(f"### {icon} `{r.target.machine}/{r.target.chain}` — {status}\n")
        lines.append(f"Rootfile: `{r.target.rootfile_path}`\n")
        lines.append(f"| Check | Result |")
        lines.append(f"|-------|--------|")
        lines.append(f"| Open positions on-chain | {len(r.open_position_ids)} |")
        lines.append(f"| Missing in caliber.yaml | {format_ids(r.missing_in_caliber)} |")
        lines.append(f"| Missing accounting in rootfile | {format_ids(r.missing_in_rootfile)} |")
        lines.append(f"| Duplicate accounting entries | {format_ids(r.duplicate_accounting)} |")
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
    readers: dict[str, RpcCaliberReader] = {}
    for target in targets:
        reader = readers.setdefault(
            target.chain, RpcCaliberReader(target.chain, block_number=args.block_number)
        )
        try:
            result = validate_target(target, reader)
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
