#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["PyYAML==6.0.2", "tomli==2.0.1"]
# ///
"""
makina-x (MakinaX Safe-module) e2e harness.

Drives the REAL deployed MakinaXModule on a fork, executing the exact compiled
weiroll instructions from the rootfile as the Safe, then asserts the deposit and
withdraw token flows. makina-x is management-only: NO on-chain NAV accounting is
asserted (unless the module is WALLED, in which case an ACCOUNTING instruction +
oracle feed routes are required — see --feeds).

Inputs: a makina-x caliber.yaml (has `makina_lite_module` + `safe_address`) and a
compiled rootfile TOML (auto-discovered in the sibling rootfiles/ dir, or --rootfile).
This tool does NOT recompile: makina-x calibers need a `--lite` transpiler the local
fallback lacks, and the rootfile is committed. Recompile separately if you changed source.

Usage:
  uv run scripts/makinax_e2e_harness.py <caliber.yaml> [--rootfile T.toml]
      [--amount 100000] [--position-id 1] [--feeds "0xTok=0xFeed1[:0xFeed2],..."]
      [--makina-x-path DIR] [--rpc-url URL] [--out report.md] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

DEFAULT_MAKINA_X = "/Users/augustin/Desktop/git/makina-x"
FORGE = shutil.which("forge") or "/Users/augustin/.foundry/bin/forge"

# chainId -> (foundry alias, [env var candidates], tenderly gateway slug)
CHAINS = {
    1: ("mainnet", ["MAINNET_RPC_URL"], "mainnet"),
    8453: ("base", ["BASE_RPC_URL"], "base"),
    42161: ("arbitrum_one", ["ARBITRUM_RPC_URL"], "arbitrum"),
    10: ("optimism", ["OPTIMISM_RPC_URL"], "optimism"),
    137: ("polygon", ["POLYGON_RPC_URL"], "polygon"),
    43114: ("avalanche", ["AVALANCHE_RPC_URL"], "avalanche"),
}

DEPOSIT_KW = ("add", "supply", "deposit", "increase", "stake", "mint", "open", "enter", "lend")
WITHDRAW_KW = ("withdraw", "remove", "redeem", "exit", "unstake", "decrease", "close", "unwind")


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(2)


# ---- caliber.yaml (tolerate the custom !include tag) ----
class _Loader(yaml.SafeLoader):
    pass


_Loader.add_constructor("!include", lambda l, n: l.construct_scalar(n))


def load_caliber(path: Path) -> dict:
    with open(path) as f:
        data = yaml.load(f, Loader=_Loader)
    cfg = data.get("config", {})

    def val(key):
        v = cfg.get(key)
        return v.get("value") if isinstance(v, dict) else v

    module = val("makina_lite_module")
    safe = val("safe_address")
    if not module or not safe:
        die(f"{path} is not a makina-x caliber (missing makina_lite_module / safe_address)")
    positions = {}
    for p in data.get("positions", []) or []:
        positions[str(p.get("id"))] = [t for t in (p.get("position_tokens") or [])]
    return {"module": module, "safe": safe, "positions": positions}


def repo_root_of(path: Path) -> Path | None:
    for parent in [path] + list(path.parents):
        if (parent / ".claude").is_dir():
            return parent
    return None


def discover_rootfile(caliber_path: Path) -> Path:
    rf_dir = caliber_path.parent / "rootfiles"
    if not rf_dir.is_dir():
        die(f"no rootfiles/ dir next to {caliber_path}; pass --rootfile")
    tomls = sorted(rf_dir.glob("*.toml"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not tomls:
        die(f"no *.toml in {rf_dir}; pass --rootfile")
    return tomls[0]


def parse_rootfile(path: Path) -> dict:
    text = path.read_text()
    m = re.search(r"#\s*root:\s*(0x[0-9a-fA-F]{64})", text)
    root = m.group(1) if m else None
    data = tomllib.loads(text)
    tokens = {}
    for _key, t in (data.get("tokens") or {}).items():
        tokens[t["address"].lower()] = {"decimals": t["decimals"], "symbol": t.get("symbol", "?"),
                                        "chainId": t.get("chainId", 1)}
    instrs = []
    for protocol, actions in (data.get("instructions") or {}).items():
        for action, labels in actions.items():
            for label, ix in labels.items():
                slots = ix.get("inputs_slots") or []
                instrs.append({
                    "protocol": protocol, "action": action, "label": label,
                    "position_id": str(ix.get("position_id")),
                    "is_debt": bool(ix.get("is_debt", False)),
                    "group_id": int(ix.get("group_id", 0)),
                    "instruction_type": int(ix.get("instruction_type", 0)),
                    "affected_tokens": [a.lower() for a in ix.get("affected_tokens", [])],
                    "position_tokens": [a.lower() for a in ix.get("position_tokens", [])],
                    "commands": ix.get("commands", []),
                    "state": ix.get("state", []),
                    "bitmap": int(ix.get("bitmap", 0)),
                    "input_slots": [{"index": int(s["index"]), "name": s["name"]} for s in slots],
                })
    return {"root": root, "tokens": tokens, "instructions": instrs}


def classify(action: str, label: str) -> str | None:
    hay = f"{action} {label}".lower()
    if any(k in hay for k in WITHDRAW_KW):
        return "withdraw"
    if any(k in hay for k in DEPOSIT_KW):
        return "deposit"
    return None


# ---- Solidity generation ----
def _sol_addr_array(field: str, addrs: list[str]) -> list[str]:
    out = [f"ix.{field} = new address[]({len(addrs)});"]
    for i, a in enumerate(addrs):
        out.append(f"ix.{field}[{i}] = {to_checksum(a)};")
    return out


def to_checksum(addr: str) -> str:
    # EIP-55 checksum via keccak (avoid extra deps; implement Keccak-256).
    a = addr.lower().replace("0x", "")
    h = keccak(a.encode())
    out = "0x"
    for i, c in enumerate(a):
        out += c.upper() if (c in "abcdef" and h[i >> 1] >> (0 if i % 2 else 4) & 0x8) else c
    return out


# --- minimal Keccak-256 (for EIP-55 checksums only) ---
def keccak(data: bytes) -> bytes:
    RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
          0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
          0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
          0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
          0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
          0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
    ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
           [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
    rate = 136
    mask = (1 << 64) - 1
    pad = bytearray(data)
    pad.append(0x01)
    while len(pad) % rate != 0:
        pad.append(0x00)
    pad[-1] ^= 0x80
    S = [[0] * 5 for _ in range(5)]
    for off in range(0, len(pad), rate):
        block = pad[off:off + rate]
        for i in range(rate // 8):
            x, y = i % 5, i // 5
            S[x][y] ^= int.from_bytes(block[i * 8:i * 8 + 8], "little")
        for rnd in range(24):
            C = [S[x][0] ^ S[x][1] ^ S[x][2] ^ S[x][3] ^ S[x][4] for x in range(5)]
            D = [C[(x - 1) % 5] ^ (((C[(x + 1) % 5] << 1) | (C[(x + 1) % 5] >> 63)) & mask) for x in range(5)]
            for x in range(5):
                for y in range(5):
                    S[x][y] ^= D[x]
            B = [[0] * 5 for _ in range(5)]
            for x in range(5):
                for y in range(5):
                    r = ROT[x][y]
                    B[y][(2 * x + 3 * y) % 5] = ((S[x][y] << r) | (S[x][y] >> (64 - r))) & mask
            for x in range(5):
                for y in range(5):
                    S[x][y] = B[x][y] ^ (~B[(x + 1) % 5][y] & B[(x + 2) % 5][y])
            S[0][0] ^= RC[rnd]
    out = bytearray()
    for i in range(4):
        x, y = i % 5, i // 5
        out += (S[x][y] & mask).to_bytes(8, "little")
    return bytes(out[:32])


def build_instr(ix: dict, amount_expr_by_slot: dict[int, str]) -> str:
    lines = [
        f"ix.positionId = {int(ix['position_id'])};",
        f"ix.isDebt = {str(ix['is_debt']).lower()};",
        f"ix.groupId = {ix['group_id']};",
        f"ix.instructionType = {ix['instruction_type']};",
    ]
    lines += _sol_addr_array("affectedTokens", ix["affected_tokens"])
    lines += _sol_addr_array("positionTokens", ix["position_tokens"])
    lines.append(f"ix.commands = new bytes32[]({len(ix['commands'])});")
    for i, c in enumerate(ix["commands"]):
        lines.append(f"ix.commands[{i}] = {c};")
    lines.append(f"ix.state = new bytes[]({len(ix['state'])});")
    for i, s in enumerate(ix["state"]):
        if i in amount_expr_by_slot:
            lines.append(f"ix.state[{i}] = {amount_expr_by_slot[i]}; // input slot")
        else:
            word = s.lower().replace("0x", "")
            lines.append(f'ix.state[{i}] = hex"{word}";')
    lines.append(f"ix.stateBitmap = uint128({ix['bitmap']});")
    lines.append("ix.merkleProof = new bytes32[](0);")
    return "\n        " + "\n        ".join(lines)


def empty_builder() -> str:
    return ("\n        ix.affectedTokens = new address[](0);"
            "\n        ix.positionTokens = new address[](0);"
            "\n        ix.commands = new bytes32[](0);"
            "\n        ix.state = new bytes[](0);"
            "\n        ix.merkleProof = new bytes32[](0);")


def amount_slots(ix: dict, name_sub: str, expr: str) -> dict[int, str]:
    slots = {s["index"]: expr for s in ix["input_slots"] if name_sub in s["name"].lower()}
    if not slots and ix["input_slots"]:
        # fall back: first input slot
        slots = {ix["input_slots"][0]["index"]: expr}
    return slots


def parse_feeds(spec: str | None) -> str:
    if not spec:
        return "        // (no feeds provided)"
    out = []
    for entry in spec.split(","):
        entry = entry.strip()
        if not entry:
            continue
        tok, _, feeds = entry.partition("=")
        parts = [p for p in feeds.split(":") if p]
        f1 = parts[0] if parts else "address(0)"
        f2 = parts[1] if len(parts) > 1 else "address(0)"
        out.append(f"IMakinaXModule(MODULE).setFeedRoute({to_checksum(tok)}, {to_checksum(f1)}, {to_checksum(f2)});")
    return "        " + "\n        ".join(out)


def ensure_forge_std(makina_x: Path) -> str:
    std = makina_x / "lib" / "forge-std" / "src"
    if not (std / "Test.sol").exists():
        print("forge-std missing in makina-x; initializing submodule…", file=sys.stderr)
        subprocess.run(["git", "submodule", "update", "--init", "lib/forge-std"],
                       cwd=makina_x, check=True)
    if not (std / "Test.sol").exists():
        die(f"could not locate forge-std at {std}")
    return str(std) + "/"


def resolve_rpc(chain_id: int, repo_root: Path | None, override: str | None) -> tuple[str, str, str]:
    alias, env_candidates, slug = CHAINS.get(chain_id, ("mainnet", ["MAINNET_RPC_URL"], "mainnet"))
    if override:
        return alias, override, "MAINNETLIKE_RPC_URL"
    env = {}
    if repo_root:
        sp = repo_root / ".claude" / "settings.local.json"
        if sp.exists():
            env = (json.loads(sp.read_text()).get("env") or {})
    for c in env_candidates:
        if env.get(c) or os.environ.get(c):
            return alias, env.get(c) or os.environ[c], c
    # gateway fallback from a tenderly mainnet key
    main = env.get("MAINNET_RPC_URL") or os.environ.get("MAINNET_RPC_URL", "")
    m = re.match(r"https://[\w.-]*gateway\.tenderly\.co/(.+)$", main)
    if m:
        return alias, f"https://{slug}.gateway.tenderly.co/{m.group(1)}", env_candidates[0]
    die(f"no RPC for chainId {chain_id}; set {env_candidates[0]} or pass --rpc-url")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("caliber", help="path to makina-x caliber.yaml")
    ap.add_argument("--rootfile", help="compiled rootfile TOML (else newest in sibling rootfiles/)")
    ap.add_argument("--position-id", help="restrict to this position id")
    ap.add_argument("--amount", type=float, default=10000.0, help="deposit amount, human units")
    ap.add_argument("--feeds", help='WALLED: "0xTok=0xFeed1[:0xFeed2],..."')
    ap.add_argument("--makina-x-path", default=os.environ.get("MAKINA_X_PATH", DEFAULT_MAKINA_X))
    ap.add_argument("--rpc-url", help="override fork RPC")
    ap.add_argument("--out", help="write markdown report here")
    ap.add_argument("--workdir", help="forge project dir (default: temp)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    caliber_path = Path(args.caliber).resolve()
    if not caliber_path.exists():
        die(f"caliber not found: {caliber_path}")
    cal = load_caliber(caliber_path)
    rootfile = Path(args.rootfile).resolve() if args.rootfile else discover_rootfile(caliber_path)
    rf = parse_rootfile(rootfile)
    repo_root = repo_root_of(caliber_path)

    # group MANAGEMENT instructions by position, pick deposit + withdraw
    by_pos: dict[str, dict] = {}
    acct_by_pos: dict[str, dict] = {}
    for ix in rf["instructions"]:
        if args.position_id and ix["position_id"] != str(args.position_id):
            continue
        if ix["instruction_type"] == 1:  # ACCOUNTING
            acct_by_pos[ix["position_id"]] = ix
            continue
        kind = classify(ix["action"], ix["label"])
        by_pos.setdefault(ix["position_id"], {})[kind or ix["action"]] = ix

    targets = {p: v for p, v in by_pos.items() if "deposit" in v and "withdraw" in v}
    if not targets:
        die("could not find a deposit+withdraw MANAGEMENT pair in the rootfile "
            f"(instructions: {[ (i['action'], i['label']) for i in rf['instructions'] ]})")
    pos_id = args.position_id or sorted(targets)[0]
    if pos_id not in targets:
        die(f"position {pos_id} has no deposit+withdraw pair")
    dep, wd = targets[pos_id]["deposit"], targets[pos_id]["withdraw"]

    base = dep["affected_tokens"][0]
    tok = rf["tokens"].get(base, {"decimals": 18, "chainId": 1, "symbol": "?"})
    decimals = tok["decimals"]
    chain_id = tok["chainId"]
    amount_scaled = int(args.amount * (10 ** decimals))
    pos_tokens = cal["positions"].get(pos_id) or []
    if not pos_tokens:
        die(f"caliber position {pos_id} has no position_tokens (needed to assert balance)")
    position_token = pos_tokens[0]

    total_leaves = len([i for i in rf["instructions"]
                        if not args.position_id or i["position_id"] == str(args.position_id)])
    check_root = "true" if (total_leaves == 2 and rf["root"]) else "false"

    acct = acct_by_pos.get(pos_id)
    dep_builder = build_instr(dep, amount_slots(dep, "amount", "abi.encode(amount)"))
    wd_builder = build_instr(wd, amount_slots(wd, "amount", "abi.encode(amount)"))
    acct_builder = build_instr(acct, {}) if acct else empty_builder()

    alias, rpc_url, _envname = resolve_rpc(chain_id, repo_root, args.rpc_url)
    makina_x = Path(args.makina_x_path).resolve()
    std_remap = ensure_forge_std(makina_x)

    tmpl = (Path(__file__).parent / "templates" / "MakinaXE2E.t.sol.tmpl").read_text()
    sol = (tmpl
           .replace("@@MODULE@@", to_checksum(cal["module"]))
           .replace("@@SAFE@@", to_checksum(cal["safe"]))
           .replace("@@BASE_TOKEN@@", to_checksum(base))
           .replace("@@POSITION_TOKEN@@", to_checksum(position_token))
           .replace("@@DEFAULT_AMOUNT@@", str(amount_scaled))
           .replace("@@TRANSPILER_ROOT@@", rf["root"] or "bytes32(0)")
           .replace("@@CHECK_COMPOSITE_ROOT@@", check_root)
           .replace("@@RPC_ALIAS@@", alias)
           .replace("@@DEPOSIT_BUILDER@@", dep_builder)
           .replace("@@WITHDRAW_BUILDER@@", wd_builder)
           .replace("@@ACCT_BUILDER@@", acct_builder)
           .replace("@@FEEDS_SETUP@@", parse_feeds(args.feeds)))

    work = Path(args.workdir).resolve() if args.workdir else Path(tempfile.mkdtemp(prefix="makinax-e2e-"))
    (work / "test").mkdir(parents=True, exist_ok=True)
    (work / "test" / "MakinaXE2E.t.sol").write_text(sol)
    (work / "foundry.toml").write_text(
        "[profile.default]\n"
        'src = "src"\nout = "out"\ntest = "test"\nlibs = ["lib"]\n'
        'evm_version = "prague"\nsolc_version = "0.8.28"\noptimizer = true\nffi = false\n'
        f'remappings = ["forge-std/={std_remap}"]\n\n'
        f'[rpc_endpoints]\n{alias} = "${{{alias.upper()}_RPC_URL}}"\n'
    )

    env = dict(os.environ)
    env[f"{alias.upper()}_RPC_URL"] = rpc_url
    env["FOUNDRY_DISABLE_NIGHTLY_WARNING"] = "1"
    print(f"→ target: {caliber_path.parent.name} pos {pos_id}  base={tok['symbol']}({base})  "
          f"chain={chain_id}  amount={args.amount}  workdir={work}", file=sys.stderr)
    proc = subprocess.run([FORGE, "test", "--match-contract", "MakinaXE2E", "-vv"],
                          cwd=work, env=env, capture_output=True, text=True)
    out = proc.stdout + "\n" + proc.stderr

    def status(fn: str) -> str:
        if re.search(rf"\[PASS\]\s+{fn}\(", out):
            return "PASS"
        if re.search(rf"\[FAIL[^\]]*\]\s+{fn}\(", out):
            return "FAIL"
        return "N/A"

    lifecycle = status("test_depositThenWithdraw")
    rootcheck = status("test_compiledRootMatchesTranspiler")
    overall = "PASS" if lifecycle == "PASS" and rootcheck in ("PASS", "N/A") else "FAIL"

    report = f"""# makina-x E2E — {caliber_path.parent.parent.name} / {caliber_path.parent.name} (pos {pos_id})

**Rootfile:** `{rootfile}`
**Module:** `{cal['module']}`  ·  **Safe:** `{cal['safe']}`
**Base token:** {tok['symbol']} `{base}` ({decimals} dec)  ·  **Position token:** `{position_token}`
**Chain:** {chain_id} ({alias})  ·  **Deposit amount:** {args.amount}
**Type:** makina-x, management-only — **no NAV accounting asserted** (by design).

| Check | Result |
|---|---|
| compiled root == on-chain leaf encoding | {rootcheck} |
| deposit → withdraw lifecycle | {lifecycle} |

**Overall: {overall}**

<details><summary>forge output</summary>

```
{out.strip()}
```
</details>
"""
    if args.out:
        Path(args.out).write_text(report)
        print(f"report written to {args.out}", file=sys.stderr)

    if args.json:
        print(json.dumps({"overall": overall, "lifecycle": lifecycle, "root_check": rootcheck,
                          "position_id": pos_id, "workdir": str(work)}))
    else:
        print(report)
    sys.exit(0 if overall == "PASS" else 1)


if __name__ == "__main__":
    main()
