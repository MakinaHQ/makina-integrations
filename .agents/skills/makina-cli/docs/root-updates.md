# Root Updates

The instruction root is a merkle root that authorizes which instructions a caliber can execute.

## Commands

| Command           | Environment        | Behavior                           |
| ----------------- | ------------------ | ---------------------------------- |
| `display-root`    | Any                | Show current on-chain root         |
| `dev-update-root` | Tenderly (`--dev`) | Set root immediately (no timelock) |
| `update-root`     | Production         | Submit tx, respects timelock       |

## Display Root

### From on-chain

```bash
spellcaster -- \
  --config machines-local.toml --dev \
  --machine {fund} --caliber {network} \
  display-root
```

### From a rootfile

```bash
spellcaster -- \
  --config machines-local.toml --dev \
  --machine {fund} --caliber {network} \
  display-root --rootfile /path/to/rootfile.toml
```

## Update Root (Dev/Testnet)

```bash
DEV_MAINNET_RPC_URL="{tenderly_rpc}" \
spellcaster -- \
  --config machines-local.toml --dev \
  --machine {fund} --caliber {network} \
  dev-update-root --rootfile /path/to/rootfile.toml
```

## Update Root (Production)

```bash
spellcaster -- \
  --machine {fund} --caliber {network} \
  update-root --rootfile /path/to/rootfile.toml
```

## Arguments

| Argument     | Description                             |
| ------------ | --------------------------------------- |
| `--root`     | Merkle root hash (bytes32) directly     |
| `--rootfile` | Path to rootfile to compute merkle root |

## Rootfile Directory Behavior

**Important**: Spellcaster loads ALL `.toml` files from the rootfiles directory and computes a combined merkle root.

When testing a single instruction:

- Move other rootfiles out of the directory, OR
- Use `dev-update-root --rootfile` with the specific file

## Verifying Root Update

After updating, verify the on-chain root matches:

```bash
DEV_MAINNET_RPC_URL="{tenderly_rpc}" \
spellcaster -- \
  --config machines-local.toml --dev \
  --machine {fund} --caliber {network} \
  display-root
```

## Prerequisites

### All Caliber Directories Must Have Rootfiles

**Critical**: When the CLI starts, it resolves **all calibers** for the machine, not just the one specified with `--caliber`. Each caliber's `rootfiles` directory must contain at least one `.toml` file.

For example, if `dusd` has calibers `mainnet`, `base`, `arbitrum`, `polygon`:

```
machines/dusd/
├── mainnet/rootfiles/   # Must have at least 1 rootfile
├── base/rootfiles/      # Must have at least 1 rootfile
├── arbitrum/rootfiles/  # Must have at least 1 rootfile
└── polygon/rootfiles/   # Must have at least 1 rootfile
```

**If any directory is empty, all commands will fail with "no rootfile found".**

Create placeholder rootfiles for empty directories:

```bash
echo 'instructions = []' > /path/to/caliber/rootfiles/20250101-empty.toml
```

**This placeholder is local-only and must NEVER be committed.** Rootfiles are release-generated
build artifacts now (see README's "Updating the rootfiles"): `rootfiles-guard` rejects any PR
that adds or modifies a file under a `rootfiles/` directory, and a committed rootfile can only
come from a published GitHub Release. The `echo` above is fine to unblock a local spellcaster run
that genuinely needs at least one rootfile per caliber directory to start — just don't `git add`
it.

## Troubleshooting

| Error                              | Cause                             | Solution                                             |
| ---------------------------------- | --------------------------------- | ---------------------------------------------------- |
| "no rootfile found"                | A caliber directory is empty      | Add at least one rootfile to ALL caliber directories |
| "no matching rootfile in root_dir" | On-chain root doesn't match local | Re-run `dev-update-root`                             |
| "could not find instruction"       | Instruction not in active root    | Update root with rootfile containing instruction     |
| Root mismatch after update         | Multiple rootfiles in directory   | Use `--rootfile` flag or isolate test file           |
