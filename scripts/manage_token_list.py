#!/usr/bin/env python3
"""Manage the Makina token list: add tokens, validate entries, find missing tokens.

Usage:
  # Add tokens (all must be on the same chain)
  python3 scripts/manage_token_list.py add --chain mainnet 0xAddr1 0xAddr2 ...

  # Validate all entries in the token list against on-chain data
  python3 scripts/manage_token_list.py validate

  # Find frequently used token addresses in instructions that are not in the token list
  python3 scripts/manage_token_list.py scan
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TOKEN_LIST_PATH = Path(__file__).parent.parent / "token-lists" / "prod-token-list.json"

CHAIN_TO_CHAIN_ID: dict[str, int] = {
    "mainnet": 1,
    "base": 8453,
    "arbitrum": 42161,
    "monad": 143,
    "hyperevm": 998,
}

# Fallback public RPCs — overridden by RPC_<CHAIN> env vars (set in .claude/settings.local.json)
_FALLBACK_RPC: dict[str, str] = {
    "mainnet": "https://eth.llamarpc.com",
    "base": "https://mainnet.base.org",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "monad": "https://rpc.monad.xyz",
    "hyperevm": "https://rpc.hyperliquid.xyz/evm",
}


def get_rpc(chain: str) -> str | None:
    """Get RPC URL for a chain. Reads RPC_<CHAIN> env var, falls back to public RPC."""
    env_key = f"RPC_{chain.upper()}"
    return os.environ.get(env_key) or _FALLBACK_RPC.get(chain)

# Matches bare hex addresses in YAML values (not inside ${...} template expressions)
ADDRESS_RE = re.compile(r"(?<!\$\{)\b(0x[0-9a-fA-F]{40})\b")

# Common non-token addresses to exclude from scan results
KNOWN_NON_TOKEN_ADDRESSES = {
    "0x0000000000000000000000000000000000000000",
    "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb",  # Morpho
    "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",  # Aave V3
    "0x3333333333333333333333333333333333333333",  # HyperCore CoreWriter
    "0x5555555555555555555555555555555555555555",  # WHYPE (native)
}



def load_token_list() -> dict:
    return json.loads(TOKEN_LIST_PATH.read_text())


def save_token_list(data: dict) -> None:
    TOKEN_LIST_PATH.write_text(json.dumps(data, indent=2) + "\n")


def cast_call(address: str, sig: str, rpc_url: str) -> str | None:
    """Run a cast call and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["cast", "call", address, sig, "--rpc-url", rpc_url],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def fetch_token_metadata(address: str, rpc_url: str) -> dict | None:
    """Fetch name, symbol, decimals for an ERC20 token via cast."""
    name = cast_call(address, "name()(string)", rpc_url)
    symbol = cast_call(address, "symbol()(string)", rpc_url)
    decimals = cast_call(address, "decimals()(uint8)", rpc_url)

    if symbol is None or decimals is None:
        return None

    # cast wraps strings in quotes
    if name and name.startswith('"') and name.endswith('"'):
        name = name[1:-1]
    if symbol and symbol.startswith('"') and symbol.endswith('"'):
        symbol = symbol[1:-1]

    # Normalize Tether unicode characters (₮ → T) for consistent ASCII spelling
    if symbol:
        symbol = symbol.replace("\u20ae", "T")
    if name:
        name = name.replace("\u20ae", "T")

    try:
        dec = int(decimals)
    except ValueError:
        return None

    return {
        "name": name or symbol,
        "symbol": symbol,
        "decimals": dec,
    }


def to_checksum_address(addr: str) -> str:
    """EIP-55 checksum encoding via cast (Keccak-256 based)."""
    try:
        result = subprocess.run(
            ["cast", "to-check-sum-address", addr],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return addr  # fallback: return as-is


def normalize_address(addr: str) -> str:
    """Lowercase an address for comparison."""
    return addr.lower()


def find_existing(tokens: list[dict], address: str, chain_id: int) -> dict | None:
    """Check if a token already exists in the list."""
    addr_lower = normalize_address(address)
    for t in tokens:
        if normalize_address(t["address"]) == addr_lower and t["chainId"] == chain_id:
            return t
    return None


# ── ADD command ──────────────────────────────────────────────────────────

def cmd_add(args: argparse.Namespace) -> int:
    chain = args.chain
    if chain not in CHAIN_TO_CHAIN_ID:
        print(f"Error: unknown chain '{chain}'. Known: {', '.join(CHAIN_TO_CHAIN_ID)}")
        return 1
    rpc_url = get_rpc(chain)
    if not rpc_url:
        print(f"Error: no RPC configured for chain '{chain}'. Set RPC_{chain.upper()} env var.")
        return 1

    chain_id = CHAIN_TO_CHAIN_ID[chain]
    data = load_token_list()
    tokens = data["tokens"]

    added = []
    skipped = []
    failed = []

    for address in args.addresses:
        # Normalize for comparison but keep original case for storage
        existing = find_existing(tokens, address, chain_id)
        if existing:
            skipped.append((address, existing["symbol"]))
            continue

        meta = fetch_token_metadata(address, rpc_url)
        if meta is None:
            failed.append(address)
            continue

        entry = {
            "chainId": chain_id,
            "address": to_checksum_address(address),
            "name": meta["name"],
            "decimals": meta["decimals"],
            "symbol": meta["symbol"],
        }
        tokens.append(entry)
        added.append(entry)

    if added:
        # Sort tokens by chainId then symbol for consistency
        data["tokens"] = sorted(tokens, key=lambda t: (t["chainId"], t["symbol"]))
        save_token_list(data)

    # Report
    if added:
        print(f"Added {len(added)} token(s):")
        for t in added:
            print(f"  + {t['symbol']} ({t['address']}) - {t['name']}, {t['decimals']} decimals")
    if skipped:
        print(f"Skipped {len(skipped)} (already in list):")
        for addr, sym in skipped:
            print(f"  ~ {sym} ({addr})")
    if failed:
        print(f"Failed {len(failed)} (could not fetch metadata):")
        for addr in failed:
            print(f"  ! {addr}")

    return 1 if failed else 0


# ── VALIDATE command ─────────────────────────────────────────────────────

def cmd_validate(args: argparse.Namespace) -> int:
    data = load_token_list()
    tokens = data["tokens"]
    errors = []

    # Group by chain for efficient RPC batching
    by_chain: dict[int, list[dict]] = {}
    for t in tokens:
        by_chain.setdefault(t["chainId"], []).append(t)

    chain_id_to_name = {v: k for k, v in CHAIN_TO_CHAIN_ID.items()}

    for chain_id, chain_tokens in sorted(by_chain.items()):
        chain_name = chain_id_to_name.get(chain_id, f"chain-{chain_id}")
        rpc_url = get_rpc(chain_name)
        if not rpc_url:
            print(f"Warning: no RPC for {chain_name} (chainId={chain_id}), skipping validation")
            continue

        print(f"Validating {len(chain_tokens)} token(s) on {chain_name}...")
        for t in chain_tokens:
            meta = fetch_token_metadata(t["address"], rpc_url)
            if meta is None:
                errors.append(f"  {t['symbol']} ({t['address']}): could not fetch metadata")
                continue

            issues = []
            if meta["symbol"] != t["symbol"]:
                issues.append(f"symbol: list={t['symbol']}, chain={meta['symbol']}")
            if meta["decimals"] != t["decimals"]:
                issues.append(f"decimals: list={t['decimals']}, chain={meta['decimals']}")
            if meta["name"] != t["name"]:
                issues.append(f"name: list={t['name']}, chain={meta['name']}")

            if issues:
                errors.append(f"  {t['symbol']} ({t['address']}): {'; '.join(issues)}")
            else:
                print(f"  OK {t['symbol']} ({t['address']})")

    if errors:
        print(f"\n{len(errors)} issue(s) found:")
        for e in errors:
            print(e)
        return 1

    print("\nAll tokens validated successfully.")
    return 0


# ── SCAN command ─────────────────────────────────────────────────────────

def cmd_scan(_args: argparse.Namespace) -> int:
    data = load_token_list()
    known_addresses: set[str] = set()
    for t in data["tokens"]:
        known_addresses.add(normalize_address(t["address"]))

    # Also exclude known non-token addresses
    known_addresses.update(normalize_address(a) for a in KNOWN_NON_TOKEN_ADDRESSES)

    # Scan instruction files and blueprint files for hex addresses
    address_counts: dict[str, int] = {}
    scan_dirs = [
        Path("instructions"),
        Path("machines"),
        Path("blueprints"),
    ]

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for yaml_file in scan_dir.rglob("*.yaml"):
            content = yaml_file.read_text()
            for match in ADDRESS_RE.finditer(content):
                addr = normalize_address(match.group(1))
                if addr not in known_addresses:
                    address_counts[addr] = address_counts.get(addr, 0) + 1

    if not address_counts:
        print("No unknown token addresses found in instruction/blueprint files.")
        return 0

    # Sort by frequency descending
    sorted_addrs = sorted(address_counts.items(), key=lambda x: -x[1])

    # Filter: only show addresses that appear 2+ times (likely tokens, not one-off contracts)
    frequent = [(addr, count) for addr, count in sorted_addrs if count >= 2]

    if not frequent:
        print("No frequently used unknown addresses found (all appear only once).")
        return 0

    print(f"Found {len(frequent)} unknown address(es) used 2+ times:\n")
    print(f"{'Address':<44} {'Count':>5}")
    print("-" * 50)
    for addr, count in frequent:
        print(f"{addr}  {count:>5}")

    print(f"\nTo add them, run:")
    print(f"  python3 scripts/manage_token_list.py add --chain <chain> <address1> <address2> ...")

    return 0


# ── NORMALIZE command ────────────────────────────────────────────────────

def cmd_normalize(_args: argparse.Namespace) -> int:
    """Normalize all addresses in the token list to EIP-55 checksum format."""
    data = load_token_list()
    changed = 0
    for t in data["tokens"]:
        checksummed = to_checksum_address(t["address"])
        if t["address"] != checksummed:
            print(f"  {t['symbol']}: {t['address']} -> {checksummed}")
            t["address"] = checksummed
            changed += 1

    if changed:
        save_token_list(data)
        print(f"\nNormalized {changed} address(es).")
    else:
        print("All addresses already checksummed.")
    return 0


# ── Main ─────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the Makina token list")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add
    add_parser = subparsers.add_parser("add", help="Add tokens to the token list")
    add_parser.add_argument("--chain", required=True, help="Chain name (mainnet, base, arbitrum, hyperevm)")
    add_parser.add_argument("addresses", nargs="+", help="ERC20 token addresses to add")

    # validate
    subparsers.add_parser("validate", help="Validate all entries against on-chain data")

    # scan
    subparsers.add_parser("scan", help="Find frequently used addresses not in the token list")

    # normalize
    subparsers.add_parser("normalize", help="Normalize all addresses to EIP-55 checksum")

    args = parser.parse_args(argv)
    if args.command == "add":
        return cmd_add(args)
    elif args.command == "validate":
        return cmd_validate(args)
    elif args.command == "scan":
        return cmd_scan(args)
    elif args.command == "normalize":
        return cmd_normalize(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
