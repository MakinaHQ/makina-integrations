# Blueprint Test Report

**Instruction**: /Users/augustin/Desktop/git/rootfiles/machines/dusd/mainnet/instructions/fluid-gho.yaml
**Machine**: dusd
**Network**: mainnet
**Testnet ID**: 3067c749-9cac-471c-910a-d505ee1c55a4
**Date**: 2026-01-08

## Summary

Tested the Fluid GHO vault instruction file containing 4 actions:

- `deposit` - Deposit GHO into fGHO vault
- `account` - Get position value from vault shares
- `redeem` - Redeem vault shares for GHO (absolute amount)
- `redeem_relative` - Redeem vault shares for GHO (percentage-based)

## Contract Addresses

| Contract   | Address                                    |
| ---------- | ------------------------------------------ |
| Caliber    | 0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC |
| Machine    | 0x6b006870C83b1Cd49E766Ac9209f8d68763Df721 |
| Mechanic   | 0x425BbC2cfF0c7E7960baA9BaC2f0Cb67B41d3beF |
| fGHO Vault | 0x6A29A46E21C730DcA1d8b23d637c101cec605C5B |
| GHO Token  | 0x40D16FC0246aD3160Ccc09B8D0D3A2cD28aE6C2f |

## Execution Steps

| Step          | Status | Details                                                                |
| ------------- | ------ | ---------------------------------------------------------------------- |
| Compile       | PASS   | Rootfile generated at machines/dusd/mainnet/rootfiles/test-output.toml |
| Update Root   | PASS   | Root updated on testnet                                                |
| Fund Mechanic | PASS   | 10 ETH for gas                                                         |
| Fund Caliber  | PASS   | 1000 GHO for operations                                                |

## Test Results

### 1. Deposit Test

| Metric      | Value                                                              |
| ----------- | ------------------------------------------------------------------ |
| Status      | PASS                                                               |
| Transaction | 0xcfdbcf37cb8521b90bfa8cf680184a2d3b2d3168421d47edf9c5fe18b67081d6 |
| Input       | asset_amount=1000 GHO, min_vault_shares=0                          |

**Command:**

```bash
cd /Users/augustin/Desktop/git/makina-rs && \
DEV_MAINNET_RPC_URL="<RPC_URL>" \
TENDERLY_ACCOUNT_SLUG="<ACCOUNT>" \
TENDERLY_PROJECT_SLUG="<PROJECT>" \
TENDERLY_API_KEY="<API_KEY>" \
TENDERLY_MAINNET_TESTNET_ID="<TESTNET_ID>" \
cargo run -p spellcaster -- \
  --machines-path /Users/augustin/Desktop/git/rootfiles/machines-local.toml \
  --dev \
  --machine dusd \
  --caliber mainnet \
  manage-position \
    --protocol fluid \
    --action deposit \
    --token GHO \
    --inputs 0x00000000000000000000000000000000000000000000003635c9adc5dea00000 \
    --inputs 0x0000000000000000000000000000000000000000000000000000000000000000
```

**Position Changes:**

| Balance        | Before           | After            | Change        |
| -------------- | ---------------- | ---------------- | ------------- |
| Position Value | 2,903,276.3 USDC | 2,904,277.5 USDC | +1,001.2 USDC |

### 2. Account Test

| Metric | Value                              |
| ------ | ---------------------------------- |
| Status | FAIL                               |
| Error  | transaction reverted in simulation |

**Command:**

```bash
cd /Users/augustin/Desktop/git/makina-rs && \
DEV_MAINNET_RPC_URL="<RPC_URL>" \
TENDERLY_ACCOUNT_SLUG="<ACCOUNT>" \
TENDERLY_PROJECT_SLUG="<PROJECT>" \
TENDERLY_API_KEY="<API_KEY>" \
TENDERLY_MAINNET_TESTNET_ID="<TESTNET_ID>" \
cargo run -p spellcaster -- \
  --machines-path /Users/augustin/Desktop/git/rootfiles/machines-local.toml \
  --dev \
  --machine dusd \
  --caliber mainnet \
  manage-position \
    --protocol fluid \
    --action account \
    --token GHO
```

**Notes:**

- Direct RPC calls to `balanceOf` and `convertToAssets` work correctly
- Issue appears to be in how the caliber contract executes the accounting instruction
- The underlying vault functions return expected values (shares: 2.63M, assets: 2.87M GHO)

### 3. Redeem Test

| Metric      | Value                                                              |
| ----------- | ------------------------------------------------------------------ |
| Status      | PASS                                                               |
| Transaction | 0x2dac0adbd0b421911895c7aa5f03f18a32f2de65737814fac0dec1056ee47211 |
| Input       | shares_to_redeem=500                                               |

**Command:**

```bash
cd /Users/augustin/Desktop/git/makina-rs && \
DEV_MAINNET_RPC_URL="<RPC_URL>" \
TENDERLY_ACCOUNT_SLUG="<ACCOUNT>" \
TENDERLY_PROJECT_SLUG="<PROJECT>" \
TENDERLY_API_KEY="<API_KEY>" \
TENDERLY_MAINNET_TESTNET_ID="<TESTNET_ID>" \
cargo run -p spellcaster -- \
  --machines-path /Users/augustin/Desktop/git/rootfiles/machines-local.toml \
  --dev \
  --machine dusd \
  --caliber mainnet \
  manage-position \
    --protocol fluid \
    --action redeem \
    --token GHO \
    --inputs 0x00000000000000000000000000000000000000000000001b1ae4d6e2ef500000
```

**Position Changes:**

| Balance        | Before           | After            | Change      |
| -------------- | ---------------- | ---------------- | ----------- |
| Position Value | 2,904,277.5 USDC | 2,903,731.7 USDC | -545.8 USDC |

### 4. Redeem Relative Test

| Metric      | Value                                                              |
| ----------- | ------------------------------------------------------------------ |
| Status      | PASS                                                               |
| Transaction | 0xb8ecec9e9602b865b587ca852c0e5cd523645f3a50d4f691aed7de077150eaf7 |
| Input       | bps_to_redeem=100 (1%)                                             |

**Command:**

```bash
cd /Users/augustin/Desktop/git/makina-rs && \
DEV_MAINNET_RPC_URL="<RPC_URL>" \
TENDERLY_ACCOUNT_SLUG="<ACCOUNT>" \
TENDERLY_PROJECT_SLUG="<PROJECT>" \
TENDERLY_API_KEY="<API_KEY>" \
TENDERLY_MAINNET_TESTNET_ID="<TESTNET_ID>" \
cargo run -p spellcaster -- \
  --machines-path /Users/augustin/Desktop/git/rootfiles/machines-local.toml \
  --dev \
  --machine dusd \
  --caliber mainnet \
  manage-position \
    --protocol fluid \
    --action redeem_relative \
    --token GHO \
    --inputs 0x0000000000000000000000000000000000000000000000000000000000000064
```

**Position Changes:**

| Balance        | Before           | After            | Change               |
| -------------- | ---------------- | ---------------- | -------------------- |
| Position Value | 2,903,731.7 USDC | 2,874,694.5 USDC | -29,037.2 USDC (~1%) |

**Display Positions Output (Final):**

```
========================================
# total AUM: stale accounting
========================================

+-------------------------------------------+----------+-------+----------------+
|                   ID                      | PROTOCOL | TOKEN |     VALUE      |
+-------------------------------------------+----------+-------+----------------+
| 187487145492373933671944618718033568251   | fluid    | GHO   | 2874694.5 USDC |
+-------------------------------------------+----------+-------+----------------+
```

## Validation Checklist

| Requirement                                                     | Status      |
| --------------------------------------------------------------- | ----------- |
| Root synced via CLI (`dev-update-root`)                         | YES         |
| Deposit executed via CLI (`manage-position`)                    | YES         |
| Withdraw (redeem) executed via CLI (`manage-position`)          | YES         |
| Withdraw (redeem_relative) executed via CLI (`manage-position`) | YES         |
| Account executed via CLI (`manage-position`)                    | NO - FAILED |
| Positions verified via CLI (`display-positions`)                | YES         |

## Result: PARTIAL PASS

- **deposit**: PASS - Successfully deposited 1000 GHO
- **account**: FAIL - Transaction reverted in simulation (needs investigation)
- **redeem**: PASS - Successfully redeemed 500 vault shares
- **redeem_relative**: PASS - Successfully redeemed 1% of position

### Recommendation

The `account` action requires investigation. The underlying vault calls work correctly when executed directly, suggesting the issue is in the compiled instruction bytecode or caliber execution. Management actions (deposit, redeem, redeem_relative) work correctly.
