---
description: Find token addresses used in instructions/blueprints that are missing from the token list
argument-hint: ""
---

# Scan for Missing Tokens

This command scans all instruction and blueprint YAML files for ERC20 addresses that appear frequently but are not in `token-lists/prod-token-list.json`.

---

## Step 1: Run the Scanner

```bash
python3 scripts/manage_token_list.py scan
```

---

## Step 2: Identify Tokens

For each address found by the scanner, try to identify what it is:
- Check if it appears in `affected_tokens` fields (likely a token)
- Check if it appears in `caliber.yaml` config sections (likely a helper/contract, not a token)
- Check if it appears in `position_tokens` fields (likely a token)

Filter out addresses that are clearly contracts (helpers, pools, gauges) rather than tokens.

---

## Step 3: Suggest Additions

Present the likely-token addresses grouped by chain (infer chain from which machine directories they appear in).

Format as a ready-to-run command:

```
/add-tokens --chain <chain> <addr1> <addr2> ...
```

Ask the user to confirm before running.
