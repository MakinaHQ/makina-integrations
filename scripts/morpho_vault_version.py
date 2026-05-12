#!/usr/bin/env python3
"""Detect whether a Morpho-style ERC4626 vault is V1 (MetaMorpho) or V2 (VaultV2).

V1 (MetaMorpho) exposes `MORPHO()(address)` returning the Morpho Blue address.
V2 (VaultV2)  exposes `firstTotalAssets()(uint256)`, a V2-only state variable,
              while `MORPHO()` reverts.

Usage:
  python3 scripts/morpho_vault_version.py <vault_address> [--chain mainnet] [--rpc-url URL] [--json]

Chains without a built-in default RPC require --rpc-url (or env RPC_<CHAIN_UPPER>).
mainnet defaults to the project's private Tenderly RPC.

Exit codes:
  0  detected (v1 or v2)
  1  could not detect (RPC missing / vault not Morpho-style / probe inconclusive)
  2  bad arguments
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

DEFAULT_RPC = {
    "mainnet": "https://mainnet.gateway.tenderly.co/4RJdRn4mYCONnOO2E9Jq6Q",
    "arbitrum": "https://arbitrum.gateway.tenderly.co/4RJdRn4mYCONnOO2E9Jq6Q",
}

INSTRUCTION_FILE = {
    "v1": "instructions/morpho-vault-v1.yaml",
    "v2": "instructions/morpho-vault-v2.yaml",
}


def cast_call(rpc_url: str, target: str, sig: str, *args: str) -> tuple[bool, str]:
    """Run `cast call` and return (ok, stdout-or-stderr)."""
    cmd = ["cast", "call", target, sig, *args, "--rpc-url", rpc_url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        return False, "cast not found on PATH"
    except subprocess.TimeoutExpired:
        return False, "cast call timed out"
    if proc.returncode == 0:
        return True, proc.stdout.strip()
    return False, (proc.stderr or proc.stdout).strip()


def detect_version(vault: str, rpc_url: str) -> dict:
    v1_ok, v1_out = cast_call(rpc_url, vault, "MORPHO()(address)")
    v2_ok, v2_out = cast_call(rpc_url, vault, "firstTotalAssets()(uint256)")

    if v1_ok and not v2_ok:
        return {"version": "v1", "evidence": f"MORPHO()={v1_out}"}
    if v2_ok and not v1_ok:
        return {"version": "v2", "evidence": f"firstTotalAssets()={v2_out}"}
    if v1_ok and v2_ok:
        return {
            "version": "unknown",
            "evidence": "both V1 and V2 probes succeeded - not a clean MetaMorpho/VaultV2",
        }
    return {
        "version": "unknown",
        "evidence": f"neither probe succeeded (v1: {v1_out!r}, v2: {v2_out!r})",
    }


def resolve_rpc(chain: str, override: str | None) -> str | None:
    if override:
        return override
    env_key = f"RPC_{chain.upper()}"
    if env_key in os.environ:
        return os.environ[env_key]
    return DEFAULT_RPC.get(chain)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("vault_address")
    ap.add_argument("--chain", default="mainnet")
    ap.add_argument("--rpc-url", default=None)
    ap.add_argument("--json", action="store_true", help="emit JSON instead of human-readable")
    args = ap.parse_args()

    rpc = resolve_rpc(args.chain, args.rpc_url)
    if not rpc:
        msg = (
            f"no RPC for chain {args.chain!r}: provide --rpc-url or set RPC_{args.chain.upper()}"
        )
        if args.json:
            print(json.dumps({"version": "unknown", "evidence": msg, "vault": args.vault_address, "chain": args.chain}))
        else:
            print(f"error: {msg}", file=sys.stderr)
        return 1

    result = detect_version(args.vault_address, rpc)
    result["vault"] = args.vault_address
    result["chain"] = args.chain
    result["instruction_file"] = INSTRUCTION_FILE.get(result["version"])

    if args.json:
        print(json.dumps(result))
    else:
        print(f"{result['version']:<7} {args.vault_address} ({args.chain}) - {result['evidence']}")
        if result["instruction_file"]:
            print(f"        instruction: {result['instruction_file']}")

    return 0 if result["version"] in ("v1", "v2") else 1


if __name__ == "__main__":
    raise SystemExit(main())
