#!/usr/bin/env python3
"""One-time migration: rename every `morpho-vault.yaml` include to v1 or v2.

For each caliber.yaml in the repository that includes
`instructions/morpho-vault.yaml`, this script:

  1. Splits the file into position blocks (`^  - id:` ... next `^  - id:` boundary).
  2. For each block referencing morpho-vault.yaml, extracts vault_address from vars.
  3. Calls scripts/morpho_vault_version.py to detect v1 vs v2 on-chain.
  4. Rewrites the include path within that block to morpho-vault-v1.yaml or
     morpho-vault-v2.yaml.
  5. After all calibers are processed, deletes the obsolete
     instructions/morpho-vault.yaml.

At this point morpho-vault-v1.yaml and morpho-vault-v2.yaml are byte-identical
copies of the original, so the compiled rootfiles should be unchanged.

Usage:
  python3 scripts/migrate_morpho_vault_includes.py [--dry-run]

Chain RPCs: mainnet uses the built-in Tenderly RPC; other chains read from env
RPC_<CHAIN_UPPER>. If a chain has no RPC available, the script skips that block
and reports it as a warning - the user must rerun after providing the RPC.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY = "morpho-vault.yaml"
V1 = "morpho-vault-v1.yaml"
V2 = "morpho-vault-v2.yaml"
DETECT_SCRIPT = REPO_ROOT / "scripts" / "morpho_vault_version.py"

# Chains where the Morpho VaultV2LiquidityLib lens is deployed. The V2 instruction
# file depends on the lens (its action `emergency_redeem_vault_v2` calls
# `lens.maxRedeem`), so V2 vaults on chains NOT in this set get pinned to the V1
# instruction file - they will still function (same ERC4626 surface) but lose
# the lens-aware emergency action until the lens is deployed and this set is
# updated. Source: blueprints/morpho/emergency.yaml.
V2_SUPPORTED_CHAINS = {"mainnet"}

VAULT_ADDR_RE = re.compile(r'vault_address:\s*"(0x[0-9a-fA-F]{40})"')
POSITION_SPLIT_RE = re.compile(r"(?m)(?=^  - id:)")
CHAIN_FROM_PATH_RE = re.compile(r"/(?:machines|tests/fixtures)/[^/]+/([^/]+)/caliber\.yaml$")


def chain_from_path(path: Path) -> str:
    m = CHAIN_FROM_PATH_RE.search(str(path))
    return m.group(1) if m else "mainnet"


def detect_version(vault: str, chain: str) -> tuple[str, str]:
    """Returns (version, evidence)."""
    proc = subprocess.run(
        [sys.executable, str(DETECT_SCRIPT), vault, "--chain", chain, "--json"],
        capture_output=True,
        text=True,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return "unknown", proc.stderr.strip() or "no JSON output from detection script"
    return data["version"], data["evidence"]


def find_caliber_files() -> list[Path]:
    files = []
    for path in REPO_ROOT.rglob("caliber.yaml"):
        if "blueprints" in path.parts:
            continue
        if ".git" in path.parts:
            continue
        try:
            text = path.read_text()
        except OSError:
            continue
        if LEGACY in text:
            files.append(path)
    return sorted(files)


def migrate_file(path: Path, dry_run: bool) -> list[tuple[str, str, str]]:
    """Returns list of (vault, version, status) tuples for reporting."""
    text = path.read_text()
    chain = chain_from_path(path)
    chunks = POSITION_SPLIT_RE.split(text)
    new_chunks: list[str] = []
    report: list[tuple[str, str, str]] = []

    for chunk in chunks:
        if LEGACY not in chunk:
            new_chunks.append(chunk)
            continue
        m = VAULT_ADDR_RE.search(chunk)
        if not m:
            head = chunk.splitlines()[0] if chunk.splitlines() else "<empty>"
            print(f"  WARN: no vault_address in block starting {head!r}; leaving unchanged", file=sys.stderr)
            new_chunks.append(chunk)
            report.append(("?", "skipped", "no vault_address in block"))
            continue
        vault = m.group(1)
        version, evidence = detect_version(vault, chain)
        if version == "v1":
            replacement = V1
        elif version == "v2":
            if chain in V2_SUPPORTED_CHAINS:
                replacement = V2
            else:
                replacement = V1
                evidence += f" (chain {chain!r} not in V2_SUPPORTED_CHAINS - pinned to V1 instruction)"
                version = "v2->v1"
        else:
            print(
                f"  WARN: {vault} ({chain}) detection inconclusive: {evidence}; leaving unchanged",
                file=sys.stderr,
            )
            new_chunks.append(chunk)
            report.append((vault, version, evidence))
            continue
        chunk = chunk.replace(LEGACY, replacement)
        new_chunks.append(chunk)
        report.append((vault, version, evidence))

    new_text = "".join(new_chunks)
    if new_text != text and not dry_run:
        path.write_text(new_text)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="report planned changes without writing")
    args = ap.parse_args()

    files = find_caliber_files()
    if not files:
        print("No caliber.yaml files reference morpho-vault.yaml. Nothing to do.")
        return 0

    print(f"Found {len(files)} caliber.yaml file(s) referencing {LEGACY}:")
    total = {"v1": 0, "v2": 0, "unknown": 0, "skipped": 0}
    inconclusive: list[tuple[Path, str, str]] = []

    for path in files:
        rel = path.relative_to(REPO_ROOT)
        chain = chain_from_path(path)
        print(f"\n- {rel} (chain: {chain})")
        report = migrate_file(path, dry_run=args.dry_run)
        for vault, version, evidence in report:
            tag = version if version in ("v1", "v2", "v2->v1") else "WARN"
            print(f"    {tag:7s}  {vault}  {evidence}")
            if version == "v1":
                total["v1"] += 1
            elif version == "v2":
                total["v2"] += 1
            elif version == "v2->v1":
                total["v1"] += 1
                total["v2_pinned_to_v1"] = total.get("v2_pinned_to_v1", 0) + 1
            else:
                inconclusive.append((path, vault, evidence))
                total["unknown"] += 1

    legacy_path = REPO_ROOT / "instructions" / LEGACY
    if legacy_path.exists():
        if inconclusive:
            print(f"\nKeeping {legacy_path.relative_to(REPO_ROOT)} because {len(inconclusive)} block(s) could not be migrated.")
        elif args.dry_run:
            print(f"\n[dry-run] Would delete {legacy_path.relative_to(REPO_ROOT)}")
        else:
            legacy_path.unlink()
            print(f"\nDeleted {legacy_path.relative_to(REPO_ROOT)}")

    print(f"\n=== Summary (dry-run={args.dry_run}) ===")
    print(f"  -> v1 instruction: {total['v1']}")
    print(f"  -> v2 instruction: {total['v2']}")
    if total.get("v2_pinned_to_v1"):
        print(f"     (of v1, {total['v2_pinned_to_v1']} are V2 on chains without lens support; pinned to V1)")
    print(f"  unmigrated:        {total['unknown']}")
    print(f"  V2 supported chains: {sorted(V2_SUPPORTED_CHAINS)}")

    return 0 if total["unknown"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
