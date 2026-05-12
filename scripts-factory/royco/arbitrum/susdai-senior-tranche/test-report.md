# Blueprint Test Report

**Instruction**: `instructions/royco-st-susdai.yaml`
**Machine**: dusd
**Network**: arbitrum (chain ID 42161)
**Testnet ID**: `2fa81c44-8990-4102-9047-bb45975b1198`
**Date**: 2026-04-08

## Summary

Full end-to-end test of the Royco Senior Tranche sUSDai instruction file on Arbitrum. All 4 instructions were tested successfully including the complete withdraw cycle (request + claim):

1. **Deposit** (MANAGEMENT): PYUSD -> USDai -> sUSDai -> ST shares
2. **Account-NAV** (ACCOUNTING): NAV-based position valuation in USDC (slot 0) + queue value (slot 1)
3. **Withdraw Request** (MANAGEMENT): Redeem ST shares -> enter sUSDai redemption queue -> store ID in KV
4. **Withdraw Claim** (MANAGEMENT): Claim serviced redemption -> USDai -> PYUSD -> clear KV

**Key setup**: Added JT liquidity (50,000 PYUSD worth) to increase ST maxDeposit from ~0.1 sUSDai to ~417,000 sUSDai, enabling production-sized test positions. Deployed a fresh KeyValueStore on Arbitrum owned by the caliber.

## Contract Addresses

| Contract                | Address                                      |
| ----------------------- | -------------------------------------------- |
| Caliber (DUSD Arbitrum) | `0xd1a1c248b253f1fc60eacd90777b9a63f8c8c1bc` |
| Hub Machine Endpoint    | `0x2e28698A78e852276E94C6558cdBf429557C5904` |
| Mechanic                | `0x425BbC2cfF0c7E7960baA9BaC2f0Cb67B41d3beF` |
| Caliber AccessManager   | `0x0fCEfa3f1047F35521A49cD8B06faBd588665d7F` |
| OracleRegistry          | `0xc388b72ab90be82b230d919f9c05c87f9397f485` |
| KV Store (deployed)     | `0x65d2e1091f33b1290F8323adf9D2b4A5D5F09bb2` |
| PYUSD                   | `0x46850aD61C2B7d64d08c9C754F45254596696984` |
| USDai                   | `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF` |
| sUSDai                  | `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` |
| Senior Tranche (ST)     | `0x90465aad4e426948A4ea342AC49A1A38200B7017` |
| Junior Tranche (JT)     | `0xeB60a64039289a4c07879147073A1Ec5AEA91553` |
| ST AccessManager        | `0x7cc6fb28ec7b5e7afc3cb3986141797ffc27253c` |
| Kernel                  | `0xFdb17E53eA5d342124b8473188BCB9F05F1949CA` |

## Execution Steps

| Step                           | Status | Details                                                                          |
| ------------------------------ | ------ | -------------------------------------------------------------------------------- |
| Create VNet                    | PASS   | Tenderly VNet `2fa81c44-8990-4102-9047-bb45975b1198` forking Arbitrum            |
| Deploy KV Store                | PASS   | Deployed at `0x65d2e1091f33b1290F8323adf9D2b4A5D5F09bb2` with owner = caliber    |
| Fund Mechanic                  | PASS   | 10 ETH for gas                                                                   |
| Fund Caliber PYUSD             | PASS   | 10,000 PYUSD                                                                     |
| Grant ST AccessManager roles   | PASS   | Role `0x858ca8ea411ba2c3` to caliber, role `0xded17f6f89970f45` to helper for JT |
| Add JT Liquidity               | PASS   | 50,000 PYUSD -> USDai -> sUSDai -> JT, ST maxDeposit increased to ~417K sUSDai   |
| Set PYUSD oracle feed          | PASS   | USDC/USD Chainlink feed (`0x50834F3163758fcC1Df9973b6e91f0F0F0434aD3`) as proxy  |
| Add PYUSD as base token        | PASS   | Via AccessManager execute (required Hub riskManagerTimelock override)            |
| Set maxPositionIncreaseLossBps | PASS   | Set to 10000 (100%)                                                              |
| Set maxPositionDecreaseLossBps | PASS   | Set to 10000 (100%)                                                              |
| Compile instruction            | PASS   | Root: `0x4f632923b79136cb33c2ae1cd627d4e379847e67a8ca9a432999ca3aa91550f6`       |
| Update Root                    | PASS   | Via `dev-update-root`                                                            |

## Test Results

### 1. Deposit Test

| Metric      | Value                                                                 |
| ----------- | --------------------------------------------------------------------- |
| Status      | PASS                                                                  |
| Transaction | `0x16d3b8c6bf92dd446188514e3b3cb3c317cd466f7d5e1acfe509412feb5cb6f6`  |
| Input       | `pyusd_amount_to_deposit=5000000000 (5000 PYUSD), min_usdai_amount=0` |

**Command:**

```bash
DEV_ARBITRUM_RPC_URL="<RPC_URL>" \
DEV_MAINNET_RPC_URL="<MAINNET_RPC>" \
TENDERLY_ACCOUNT_SLUG="<ACCOUNT>" \
TENDERLY_PROJECT_SLUG="<PROJECT>" \
TENDERLY_API_KEY="<API_KEY>" \
spellcaster --config /workspace/machines-local.toml \
  --dev --machine dusd --caliber arbitrum \
  manage-position \
    --protocol royco-st-susdai \
    --action deposit \
    --token ROY-ST-sUSDai \
    --inputs 0x000000000000000000000000000000000000000000000000000000012a05f200 \
    --inputs 0x0000000000000000000000000000000000000000000000000000000000000000
```

**Position Changes:**

| Balance         | Before | After            | Change       |
| --------------- | ------ | ---------------- | ------------ |
| ST Position NAV | 0 USDC | 4998.647923 USDC | +4998.647923 |
| PYUSD           | 10000  | 5000             | -5000        |

**Display Positions Output (after deposit):**

```
========================================
# total AUM: 9998.647923 USDC
========================================

| ID                                      | PROTOCOL        | TOKEN             | VALUE         |
|999999999999999999999999999999999999999   | royco-st-susdai | ROY-ST-sUSDai-NAV | 4998.647923 USDC |
```

### 2. Account-NAV Test (before withdrawal)

| Metric      | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| Status      | PASS                                                                 |
| Transaction | `0xe7dd537256dcaac57a5b4b85178fb506494ff37c888c6e0b69309c1abcadb10b` |

**Command:**

```bash
DEV_ARBITRUM_RPC_URL="<RPC_URL>" \
DEV_MAINNET_RPC_URL="<MAINNET_RPC>" \
TENDERLY_ACCOUNT_SLUG="<ACCOUNT>" \
TENDERLY_PROJECT_SLUG="<PROJECT>" \
TENDERLY_API_KEY="<API_KEY>" \
spellcaster --config /workspace/machines-local.toml \
  --dev --machine dusd --caliber arbitrum \
  account-positions
```

**Notes:**

- Slot 0 (ST NAV): ~4998 USDC (active ST position correctly valued)
- Slot 1 (Queue): 0 USDC (no pending/claimable redemptions)
- Total position: 4998.648034 USDC

### 3. Withdraw Request Test

| Metric      | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| Status      | PASS                                                                 |
| Transaction | `0xd2ee04ab3ac90461e312263335e9894d93d4154c4bc4fd7fba4beeb0a79e9362` |
| Input       | `bps_to_redeem=10000 (100%)`                                         |

**Command:**

```bash
DEV_ARBITRUM_RPC_URL="<RPC_URL>" \
DEV_MAINNET_RPC_URL="<MAINNET_RPC>" \
TENDERLY_ACCOUNT_SLUG="<ACCOUNT>" \
TENDERLY_PROJECT_SLUG="<PROJECT>" \
TENDERLY_API_KEY="<API_KEY>" \
spellcaster --config /workspace/machines-local.toml \
  --dev --machine dusd --caliber arbitrum \
  manage-position \
    --protocol royco-st-susdai \
    --action withdraw_request \
    --token ROY-ST-sUSDai \
    --inputs 0x0000000000000000000000000000000000000000000000000000000000002710
```

**Notes:**

- ST shares balance: 0 (all redeemed)
- KV store redemption ID: 2162 (stored correctly)
- sUSDai pendingRedeemRequest(2162): 4,638,173,552,241,584,400,621 shares (~4638 sUSDai)
- Position value maintained at ~4998 USDC via queue accounting (slot 1)

### 4. Account-NAV Test (during pending withdrawal)

| Metric      | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| Status      | PASS                                                                 |
| Transaction | `0x3628a4e1c72d026f167969d0c089f1319f5469476753017dc0c331e0fba420d2` |

**Notes:**

- Slot 0 (ST NAV): 0 USDC (all ST shares redeemed)
- Slot 1 (Queue): ~4998 USDC (pending sUSDai priced via Kernel conversion)
- Total position: 4998.648384 USDC -- correctly tracks queue value

### 5. Queue Servicing (admin operation)

| Metric      | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| Status      | PASS                                                                 |
| Transaction | `0x61495688229c7a995d44b2bc72fc03b6b21052a97e1c1fd8014312d72e6fc682` |

**Notes:**

- Time-warped ~30 days forward (sUSDai redemption delay)
- Called `sUSDai.serviceRedemptions(totalPendingShares)` from STRATEGY_ADMIN
- Required servicing ALL pending shares across all queued requests (not just ours)
- Extended oracle staleness to 10 years for both PYUSD and USDC feeds
- claimableRedeemRequest(2162) = 4,638,173,552,241,584,400,621 (confirmed claimable)

### 6. Account-NAV Test (after servicing - claimable)

| Metric      | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| Status      | PASS                                                                 |
| Transaction | `0x58ab1b2271ec5cd3e4812ba8263ddd7a405c95c7f4ce888d7ff7f6112f4a8bcc` |

**Notes:**

- Slot 0: 0 USDC (no ST shares)
- Slot 1: ~4998 USDC (claimable sUSDai in queue, same pricing)
- Total: 4998.409197 USDC

### 7. Withdraw Claim Test

| Metric      | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| Status      | PASS                                                                 |
| Transaction | `0x912c7628cef3bb203e21ac739ddcbb4f616f5aa0f15dd9430b015dcb85fc3abc` |
| Input       | `min_pyusd_amount=0`                                                 |

**Command:**

```bash
DEV_ARBITRUM_RPC_URL="<RPC_URL>" \
DEV_MAINNET_RPC_URL="<MAINNET_RPC>" \
TENDERLY_ACCOUNT_SLUG="<ACCOUNT>" \
TENDERLY_PROJECT_SLUG="<PROJECT>" \
TENDERLY_API_KEY="<API_KEY>" \
spellcaster --config /workspace/machines-local.toml \
  --dev --machine dusd --caliber arbitrum \
  manage-position \
    --protocol royco-st-susdai \
    --action withdraw_claim \
    --token ROY-ST-sUSDai \
    --inputs 0x0000000000000000000000000000000000000000000000000000000000000000
```

**Notes:**

- KV store cleared: redemption ID = 0
- PYUSD received: 10,019,277,312 (10,019 PYUSD -- started with 10,000, deposited 5,000, got back ~5,019 including yield accrual)
- Full pipeline: sUSDai.maxRedeem -> sUSDai.redeem -> USDai.withdraw(PYUSD) -> KV store clear

### 8. Final Account Test

| Metric      | Value                                                                |
| ----------- | -------------------------------------------------------------------- |
| Status      | PASS                                                                 |
| Transaction | `0x19081d935faa0126f0e2348934079f65d90beddeee47a35476817f4f5d4ec167` |

**Display Positions Output (final):**

```
========================================
# total AUM: 10019.277312 USDC
========================================

(no positions - all withdrawn)
```

**Notes:**

- Slot 0 = 0 (no ST position)
- Slot 1 = 0 (no queue position, KV store cleared)
- All value returned as PYUSD

## Setup Notes

### KV Store Deployment

The DUSD machine did not have a KeyValueStore on Arbitrum. A minimal KV store was compiled with Forge and deployed via Tenderly impersonation, with `owner = caliber`. The KV store address was set in `caliber-test.yaml`.

### JT Liquidity

The Senior Tranche has a utilization cap enforced by the Royco Accountant. At fork time, ST maxDeposit was only ~0.1 sUSDai. To enable production-sized deposits:

1. Funded helper with 100,000 PYUSD
2. Deposited 50,000 PYUSD -> USDai -> sUSDai -> JT
3. Required JT deposit role (`0xded17f6f89970f45`) on the ST AccessManager
4. ST maxDeposit increased to ~417,000 sUSDai

### Hub riskManagerTimelock Override

The Caliber's `addBaseToken` checks `msg.sender == hub.riskManagerTimelock()`. Since calls route through the AccessManager, the actual msg.sender at the Caliber is the AccessManager proxy, not the riskManagerTimelock. Fixed by overriding the Hub's storage slot for riskManagerTimelock to point to the AccessManager address.

- Hub storage namespace: `0x7e702089668346e906996be6de3dfc0cb2b0c125fc09b3c0391871825913e000`
- Slot +3 contains packed `(bool initialized, address riskManagerTimelock)`

### sUSDai Redemption Queue

The sUSDai contract uses ERC-7540 async redemptions with a ~30-day delay:

- `requestRedeem()` enters a FIFO queue, returns a redemption ID
- `serviceRedemptions(shares)` processes the queue (admin-only, requires timestamp past `redemptionTimestamp`)
- `redeem()` claims serviced USDai
- Servicing required processing ALL pending shares (including 42 pre-fork requests), not just the caliber's shares

## Validation Checklist

| Requirement                                           | Status                                                 |
| ----------------------------------------------------- | ------------------------------------------------------ |
| Root synced via CLI (`dev-update-root`)               | YES                                                    |
| Deposit executed via CLI (`manage-position`)          | YES                                                    |
| Withdraw Request executed via CLI (`manage-position`) | YES                                                    |
| Withdraw Claim executed via CLI (`manage-position`)   | YES                                                    |
| Harvest executed via CLI (`harvest-position`)         | N/A (no harvest instruction)                           |
| Positions verified via CLI (`display-positions`)      | YES                                                    |
| Accounting verified via CLI (`account-positions`)     | YES (4 times: pre-withdraw, pending, claimable, final) |

## Result: PASS

All 4 instructions validated end-to-end via the spellcaster CLI:

- **Deposit**: PYUSD -> USDai -> sUSDai -> ST shares (full multi-hop pipeline)
- **Account-NAV**: Correctly reports ST position NAV (slot 0) and redemption queue value (slot 1) across all states
- **Withdraw Request**: Redeems ST shares, enters sUSDai redemption queue, stores redemption ID in KV store
- **Withdraw Claim**: Claims serviced redemption, converts USDai to PYUSD, clears KV store

The full deposit-withdraw cycle preserves value (deposited 5000 PYUSD, recovered ~5019 PYUSD including ~30 days of yield accrual).
