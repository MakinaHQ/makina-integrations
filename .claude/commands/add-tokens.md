---
description: Add ERC20 tokens to the token list by fetching metadata on-chain
argument-hint: --chain <chain> <address1> [address2] [...]
---

# Add Tokens to Token List

Parse `$ARGUMENTS`:
- `--chain <chain>`: Chain name (mainnet, base, arbitrum, hyperevm). **Required.**
- Positional: One or more ERC20 token addresses. All must be on the same chain.

---

## Step 1: Add Tokens via Script

Run the Python script which handles all the logic (duplicate detection, on-chain fetching, saving):

```bash
python3 scripts/manage_token_list.py add $ARGUMENTS
```

Report the output to the user.

If any tokens failed (could not fetch metadata), warn the user and suggest verifying the addresses.

---

## Step 2: Validate New Entries

After adding, spawn an independent agent to validate ALL entries in the token list against on-chain data:

```
Agent(subagent_type="general-purpose", description="Validate token list entries", run_in_background=true, prompt="""
Run the token list validator and report any issues:

```bash
python3 scripts/manage_token_list.py validate
```

If there are mismatches between the token list and on-chain data (wrong symbol, decimals, or name), report each issue clearly. If everything is valid, confirm success.
""")
```

Report the validation result to the user when it completes.
