#!/usr/bin/env python3
"""Validate token list entries against on-chain ERC-20 metadata.

For each token in the given JSON token-list files, checks:
  1. The address is a deployed contract on the declared chain.
  2. The on-chain name, symbol, and decimals match the listed values.

Requires: web3

Exit code 0 = all good, 1 = validation errors found.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from web3 import Web3
except ImportError:
    print("Error: web3 is required. Install with: pip install web3", file=sys.stderr)
    sys.exit(1)

CHAIN_ID_TO_NAME: dict[int, str] = {
    1: "mainnet",
    8453: "base",
    42161: "arbitrum",
    10143: "monad",
    998: "hyperevm",
}

# Alchemy kebabCaseId per chain — used to build the RPC URL from a single
# ALCHEMY_API_KEY secret: https://{slug}.g.alchemy.com/v2/{key}
CHAIN_ALCHEMY_SLUG: dict[str, str] = {
    "mainnet": "eth-mainnet",
    "base": "base-mainnet",
    "arbitrum": "arb-mainnet",
}

# Tether uses ₮ (U+20AE) in name/symbol — normalize to ASCII "T"
_TETHER_TUGRIK = "\u20ae"

# Minimal ERC-20 ABI for name, symbol, decimals
ERC20_ABI = json.loads(
    '[{"inputs":[],"name":"name","outputs":[{"type":"string"}],"stateMutability":"view","type":"function"},'
    '{"inputs":[],"name":"symbol","outputs":[{"type":"string"}],"stateMutability":"view","type":"function"},'
    '{"inputs":[],"name":"decimals","outputs":[{"type":"uint8"}],"stateMutability":"view","type":"function"}]'
)


def resolve_rpc_url(chain: str) -> str | None:
    """Build the Alchemy RPC URL for a chain. Returns None if chain unsupported or key missing."""
    slug = CHAIN_ALCHEMY_SLUG.get(chain)
    if not slug:
        return None
    api_key = os.getenv("ALCHEMY_API_KEY")
    if not api_key:
        return None
    return f"https://{slug}.g.alchemy.com/v2/{api_key}"


def _get_w3(chain: str) -> Web3 | None:
    rpc = resolve_rpc_url(chain)
    if not rpc:
        return None
    return Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 15}))


@dataclass(frozen=True)
class TokenError:
    address: str
    chain_id: int
    symbol: str
    message: str


@dataclass
class ValidationResult:
    file_path: str
    checked: int = 0
    errors: list[TokenError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def fetch_erc20_metadata(w3: Web3, address: str) -> dict | None:
    """Fetch name, symbol, decimals from an ERC-20 contract. Returns None on failure."""
    try:
        checksum = Web3.to_checksum_address(address)
        contract = w3.eth.contract(address=checksum, abi=ERC20_ABI)
        symbol = contract.functions.symbol().call()
        decimals = contract.functions.decimals().call()
        try:
            name = contract.functions.name().call()
        except Exception:
            name = symbol  # Some tokens don't implement name()
        if isinstance(symbol, str):
            symbol = symbol.replace(_TETHER_TUGRIK, "T")
        if isinstance(name, str):
            name = name.replace(_TETHER_TUGRIK, "T")
        return {"name": name, "symbol": symbol, "decimals": decimals}
    except Exception:
        return None


def validate_token_list(file_path: str, data: dict) -> ValidationResult:
    """Validate all tokens in a parsed token-list JSON dict."""
    result = ValidationResult(file_path=file_path)
    tokens = data.get("tokens", [])

    # Cache Web3 instances per chain
    w3_cache: dict[str, Web3 | None] = {}

    for token in tokens:
        chain_id = token.get("chainId")
        address = token.get("address", "")
        symbol = token.get("symbol", "?")

        chain_name = CHAIN_ID_TO_NAME.get(chain_id)
        if chain_name is None:
            result.errors.append(
                TokenError(address, chain_id, symbol, f"unknown chainId {chain_id}")
            )
            continue

        if chain_name not in w3_cache:
            w3_cache[chain_name] = _get_w3(chain_name)

        w3 = w3_cache[chain_name]
        if w3 is None:
            result.errors.append(
                TokenError(address, chain_id, symbol, f"no RPC for chain {chain_name}")
            )
            continue

        result.checked += 1
        meta = fetch_erc20_metadata(w3, address)

        if meta is None:
            result.errors.append(
                TokenError(
                    address, chain_id, symbol,
                    f"contract not found or not ERC-20 on {chain_name}",
                )
            )
            continue

        issues = [
            f"{field}: list={token.get(field)}, chain={meta[field]}"
            for field in ("symbol", "decimals", "name")
            if meta[field] != token.get(field)
        ]
        if issues:
            result.errors.append(
                TokenError(address, chain_id, symbol, "; ".join(issues))
            )

    return result


def validate_token_list_file(file_path: str) -> ValidationResult:
    """Load a token-list JSON file from disk and validate it."""
    data = json.loads(Path(file_path).read_text())
    return validate_token_list(file_path, data)


def print_result(result: ValidationResult) -> None:
    print(f"Validated {result.file_path}: {result.checked} token(s) checked")
    if result.ok:
        print("  All tokens valid.")
    else:
        print(f"  {len(result.errors)} error(s):")
        for e in result.errors:
            chain = CHAIN_ID_TO_NAME.get(e.chain_id, f"chain-{e.chain_id}")
            print(f"    {e.symbol} ({e.address}) on {chain}: {e.message}")


def write_github_summary(results: list[ValidationResult]) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = ["## Token List Validation\n"]
    for r in results:
        icon = "\u2705" if r.ok else "\u274c"
        status = "Pass" if r.ok else "Fail"
        lines.append(f"### {icon} `{r.file_path}` \u2014 {status}\n")
        lines.append(f"Tokens checked: {r.checked}\n")
        if not r.ok:
            lines.append("| Token | Chain | Issue |")
            lines.append("|-------|-------|-------|")
            for e in r.errors:
                chain = CHAIN_ID_TO_NAME.get(e.chain_id, f"chain-{e.chain_id}")
                lines.append(f"| {e.symbol} (`{e.address[:10]}...`) | {chain} | {e.message} |")
        lines.append("")

    with open(summary_path, "a") as f:
        f.write("\n".join(lines))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate token list entries against on-chain data."
    )
    parser.add_argument(
        "files", nargs="*", help="Token list JSON files to validate."
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.files:
        print("No token list files to validate.")
        return 0

    results: list[ValidationResult] = []
    for file_path in args.files:
        result = validate_token_list_file(file_path)
        results.append(result)
        print_result(result)

    write_github_summary(results)
    return 1 if any(not r.ok for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
