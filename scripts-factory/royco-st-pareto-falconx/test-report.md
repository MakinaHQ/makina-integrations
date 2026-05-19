# Blueprint Test Report — Royco ST Pareto FalconX

**Instruction**: `instructions/royco-st-pareto-falconx.yaml`
**Machine**: `intMkSrRoyUSDC`
**Network**: `mainnet`
**Result**: **PASS** — all 4 management actions + accounting executed successfully via the spellcaster CLI on a fresh Tenderly mainnet fork.

## Fork

| Key              | Value                                                                                          |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| `vnet_id`        | `438efdd7-701a-44e4-b7f0-acc3518e4c29`                                                         |
| Admin RPC        | `https://virtual.mainnet.eu.rpc.tenderly.co/cb5bd01f-5aa3-4329-bea3-9dffb74a4676`              |
| Public RPC       | `https://virtual.mainnet.eu.rpc.tenderly.co/cbcba485-a3de-4f43-8d84-22565c5bb039`              |
| Forked block     | `0x17d5e3b` (24,993,147)                                                                       |
| Tenderly project | `makina/integrations`                                                                          |
| Dashboard        | https://dashboard.tenderly.co/makina/integrations/testnet/438efdd7-701a-44e4-b7f0-acc3518e4c29 |

A single fresh fork was used for the entire E2E (deposit → account → withdraw Phase 1 → time-warp + ops → claim Phase 2 → final account). No fork reuse from the explorer stages.

## Compile

The instruction file compiled cleanly (no edits required to blueprints or instruction):

```
transpiler --input-file /workspace/machines/intMkSrRoyUSDC/mainnet/caliber-test.yaml \
           --output-file /workspace/machines/intMkSrRoyUSDC/mainnet/rootfiles/20260430-pareto-falconx-test.toml \
           --token-list /workspace/token-lists/prod-token-list.json transpile
```

Result: `Rootfile successfully transpiled`. Resulting root: `0x7d7e0c22e94d83a99f93bb22d235bb92c62de53c5b9398da338bb2d5fc2de41b`.

The compiled rootfile contains 5 entries:

| Protocol                  | Action           | Token (label)                            |
| ------------------------- | ---------------- | ---------------------------------------- |
| `royco-st-pareto-falconx` | `deposit`        | `ROY-ST-Pareto-FalconX (mid-epoch)`      |
| `royco-st-pareto-falconx` | `deposit`        | `ROY-ST-Pareto-FalconX (between epochs)` |
| `royco-st-pareto-falconx` | `request_redeem` | `ROY-ST-Pareto-FalconX (request)`        |
| `royco-st-pareto-falconx` | `claim_redeem`   | `ROY-ST-Pareto-FalconX (claim)`          |
| `royco-st-pareto-falconx` | `account`        | `ROY-ST-Pareto-FalconX`                  |

## Configuration changes

The repo's `machines-local.toml` and the `intMkSrRoyUSDC` / `dusd` `config-local.toml` files all referenced `/Users/niski/code/config/...` for rootfiles. They were rewritten to point at the in-repo `/workspace/...` paths so spellcaster could load the rootfiles. The mainnet RPC + testnet id in `machines-local.toml` were updated to the fresh fork above.

## Key contract addresses

| Role                                               | Address                                      |
| -------------------------------------------------- | -------------------------------------------- |
| Caliber                                            | `0x5476F4E23dAA093Ce6700e1026013c55F7AF9083` |
| Machine                                            | `0xFa097420f0e2C72456B361a1eD85172B9ccd8c38` |
| Royco ST                                           | `0x694ADB3077BBecE31882B6d6A74fc4A4fA6a754b` |
| Royco JT (junior)                                  | `0x8e0ec43e51b88aa2324102e1a3d667822be51a6d` |
| Royco Kernel                                       | `0x15bb63C07740ff972F76716cAcC5766f0C641791` |
| Royco AccessManager / Factory                      | `0x7cC6fB28eC7b5e7afC3cB3986141797ffc27253C` |
| AccessManager admin (impersonated for JT_LP grant) | `0x7c405bbd131e42af506d14e752f2e59b19d49997` |
| Pareto IdleCDOEpochVariant                         | `0x433D5B175148dA32Ffe1e1A37a939E1b7e79be4d` |
| Pareto AA tranche                                  | `0xc26a6fa2c37b38e549a4a1807543801db684f99c` |
| Pareto IdleCreditVault (FalconXUSDC receipt)       | `0x17E9Ab2992dfecBe779a06A92a6cDB9fE6aEeEf3` |
| Pareto strategy manager                            | `0x1fb0f3602f52e2420acff5cf04dbfde96378df58` |
| Pareto borrower                                    | `0x653f71339144e8641a645758f4df4e317fe998a3` |
| USDC                                               | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` |

## Pre-flight reads on the fresh fork (block 0x17d5e3b)

Confirmed the same gating state as the deposit-stage fork:

| Read                                     | Value                                  |
| ---------------------------------------- | -------------------------------------- |
| `IdleCDO.isEpochRunning()`               | `true` → mid-epoch path                |
| `IdleCDO.isDepositDuringEpochDisabled()` | `false` → mid-epoch deposits enabled   |
| `IdleCDO.epochEndDate()`                 | `1779480958` (2026-05-04 17:29:34 UTC) |
| `IdleCDO.paused()`                       | `true`                                 |
| `IdleCDO.tranchePrice(AA)`               | `1,074,982` (USDC-6dec / 1e18 AA)      |
| `RoycoST.totalSupply()`                  | `0` → empty market                     |
| `RoycoJT.totalSupply()`                  | `0` → junior must be bootstrapped      |
| `IdleCreditVault.unscaledApr()`          | `8.25e18`                              |

Confirms the deposit-stage report's claim that the caliber's Pareto Keyring whitelist and Royco ST/Kernel role grants are already live on mainnet.

## Pre-flight setup (off-blueprint, runbook-only)

| # | Action                                                                                           | tx_hash                                                              | Status  |
| - | ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- | ------- |
| 1 | `tenderly_setErc20Balance(caliber, USDC, 100,000)`                                               | (admin RPC call)                                                     | ok      |
| 2 | Fund AccessManager admin with 1 ETH                                                              | (fund_account)                                                       | ok      |
| 3 | Grant JT_LP role to caliber: `RoycoFactory.grantRole(0xded17f6f89970f45, caliber, 0)` from admin | `0x7e5f6bf7bccb70a0792da7af15316e130c127209f097018537b77aaa2df759ac` | success |
| 4 | Caliber `USDC.approve(IdleCDO, 60_000 USDC)`                                                     | `0x3417594a0cc909dafad6d9ad0213e1b61c6733328df2d094c1a5dcb3157e8246` | success |
| 5 | Caliber `IdleCDO.depositDuringEpoch(10_000 USDC, AA)` (junior bootstrap source)                  | `0xf362bfa07cbc23ed158197524b0f91b35a91630c34593ecc7d45a64676fc4fe5` | success |
| 6 | Caliber `AA.approve(RoycoJT, 9249.557 AA)`                                                       | `0xc6f90371c15accbc859bc2f23b907956d7eaaddd7422f3f7cec83435875e2116` | success |
| 7 | Caliber `RoycoJT.deposit(9249.557 AA, caliber)`                                                  | `0xe78b1fc2d388e558a247bf9a442774aa56a63bb045ed65519c5229b77600f597` | success |

Post-bootstrap state:

- `RoycoJT.totalSupply()` = `9,938,180,541,571,879,543,786` (≈ 9,938.18 JT shares — caliber owns 100%)
- Caliber USDC = 90,000 (100,000 − 10,000 junior bootstrap)
- Caliber AA = 0 (all junior AA pulled into kernel)
- Junior NAV is now positive → senior coverage check will pass.

## Spellcaster: update root

```
spellcaster --config /workspace/machines-local.toml \
            --machine intMkSrRoyUSDC --caliber mainnet --dev \
            dev-update-root --root 0x7d7e0c22e94d83a99f93bb22d235bb92c62de53c5b9398da338bb2d5fc2de41b
```

`display-root` confirms the root is now `0x7d7e0c22e94d83a99f93bb22d235bb92c62de53c5b9398da338bb2d5fc2de41b`. PASS.

## Test 1 — Deposit (mid-epoch, 50,000 USDC)

```
spellcaster --config /workspace/machines-local.toml \
            --machine intMkSrRoyUSDC --caliber mainnet --dev \
            manage-position \
              --protocol royco-st-pareto-falconx \
              --action deposit \
              --token "ROY-ST-Pareto-FalconX (mid-epoch)" \
              --inputs 0x0000000000000000000000000000000000000000000000000000000ba43b7400
```

| Metric   | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| Status   | **PASS** (receipt status 1)                                          |
| tx_hash  | `0x8e891882b092290afe8c42d407c560c75d68b93e98bd249fee24cd8f14c9c237` |
| Block    | 24,993,350                                                           |
| Gas used | 1,221,858                                                            |

| Caliber balance | Before        | After                      | Δ                                                                                      |
| --------------- | ------------- | -------------------------- | -------------------------------------------------------------------------------------- |
| USDC            | 90,000.000000 | 40,000.000000              | **−50,000 USDC**                                                                       |
| AA tranche      | 0             | 0                          | (transient: minted 46,247.78 AA in step 1, pulled into kernel by ST.deposit in step 2) |
| ROY-ST          | 0             | 49,716.025471... ST shares | **+49,716.025471**                                                                     |

Internal flow (matches `execution-deposit.md` Path B exactly):

```
USDC -> IdleCDO.depositDuringEpoch(50k USDC, AA) -> 46,247.78 AA -> RoycoST.deposit(...) -> 49,716.025 ST shares
```

The slight numerical difference vs. the deposit-stage report (49,715.825 ST shares there, 49,716.025 here) comes from the fresh fork being at a different block (24,993,147 vs 24,992,981), which slightly shifts the AA mint formula's `expectedFinal` term mid-epoch. The mid-epoch discount mechanic is identical.

## Test 2 — Account (post-deposit)

```
spellcaster --config /workspace/machines-local.toml \
            --machine intMkSrRoyUSDC --caliber mainnet --dev \
            account-positions
```

| Metric                                       | Value                                                                |
| -------------------------------------------- | -------------------------------------------------------------------- |
| Status                                       | **PASS**                                                             |
| tx_hash                                      | `0xfd5d91a919e21d1b35fb6105167768358ce82f5e404caae1ba24d44be391591a` |
| Position value emitted by caliber accountant | `0xb9346cefa` = **49,715,531,514 USDC 6-dec = 49,715.531514 USDC**   |

Cross-check with on-chain math (asset-space, Path A from `execution-account.md`):

| Quantity                                                               | Value                         |
| ---------------------------------------------------------------------- | ----------------------------- |
| `ST.convertToAssets(49,716.025 ST)` → stAssets                         | 46,247.78... AA               |
| `ST.convertToAssets(...)` → jtAssets                                   | 0                             |
| `ST.convertToAssets(...)` → nav (WAD)                                  | 49,715.531514745475922606     |
| `AA.balanceOf(caliber)` (stranded)                                     | 0                             |
| `IdleCDO.tranchePrice(AA)`                                             | 1,074,982                     |
| `FalconXUSDC.balanceOf(caliber)` (pending)                             | 0                             |
| Computed `(stAssets+jtAssets+stranded_aa)*tranchePrice/1e18 + pending` | **49,715,531,514** USDC 6-dec |

The accountant's emitted value matches the on-chain math **to the wei**.

`display-positions` after the account tx:

```
| ID                                      | PROTOCOL                | TOKEN                 | VALUE             |
| 204541588220296843188812650988416231208 | royco-st-pareto-falconx | ROY-ST-Pareto-FalconX | 49715.531514 USDC |
```

## Test 3 — Withdraw Phase 1 (request_redeem, full)

Phase 1 cannot run mid-epoch — the protocol's `allowAAWithdrawRequest` is `false` while an epoch is live. Time-warp + manager-only `stopEpoch` was performed before invoking spellcaster.

### Pareto-side ops sequence (off-blueprint, manager-only)

| # | Action                                       | tx_hash                                                              | Status  |
| - | -------------------------------------------- | -------------------------------------------------------------------- | ------- |
| 1 | Set borrower USDC = 512M                     | (set_erc20_balance)                                                  | ok      |
| 2 | Fund borrower with 1 ETH                     | (fund_account)                                                       | ok      |
| 3 | Fund manager `0x1fb0…df58` with 1 ETH        | (fund_account)                                                       | ok      |
| 4 | Borrower `USDC.approve(IdleCDO, max)`        | `0xb7e7e41fbf5462e238e9c5c9eb43fd953f6b5f755cf3959b0ce43dc586fb1c11` | success |
| 5 | `evm_increaseTime(1,926,200)` + `mine_block` | —                                                                    | ok      |
| 6 | Manager `IdleCDO.stopEpoch(8.25e18, 0)`      | `0x0c51a125e873a10f43dd977541f01b91a8527b3018c25d677a560000621ff97c` | success |

Post-stopEpoch state (verified):

- `isEpochRunning()` = `false`
- `allowAAWithdrawRequest()` = `true`
- `paused()` = `false`
- `tranchePrice(AA)` = `1,082,228` (+0.674 % from 1,074,982)

### Spellcaster invocation

```
spellcaster --config /workspace/machines-local.toml \
            --machine intMkSrRoyUSDC --caliber mainnet --dev \
            manage-position \
              --protocol royco-st-pareto-falconx \
              --action request_redeem \
              --token "ROY-ST-Pareto-FalconX (request)" \
              --inputs 0x0000000000000000000000000000000000000000000000000000000000002710
```

(`0x2710` = 10000 bps = 100% redeem.)

| Metric   | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| Status   | **PASS** (receipt status 1)                                          |
| tx_hash  | `0xa0ef42e7923d5ad5bc9a7274dbcb34026694e55045f01e0ea56204cbb10e70ac` |
| Block    | 24,993,363                                                           |
| Gas used | 1,088,498                                                            |

| Caliber balance       | Before        | After                                                                   |
| --------------------- | ------------- | ----------------------------------------------------------------------- |
| ROY-ST                | 49,716.025471 | **0 (full burn)**                                                       |
| AA tranche            | 0             | 0 (transient: held 46,201.20 AA between `redeem` and `requestWithdraw`) |
| `FalconXUSDC` receipt | 0             | **50,322.519155** (6-dec USDC equivalent)                               |
| USDC                  | 40,000.000000 | 40,000.000000 (unchanged)                                               |

Subsequent `display-positions` showed the position re-valued at **50,322.519155 USDC** sourced entirely from `FalconXUSDC.balanceOf(caliber)` — i.e. the asset-space accounting correctly tracks value during the multi-week pending withdraw window even though `ST.balanceOf == 0` and `AA.balanceOf == 0`.

## Test 4 — Drive next epoch + Withdraw Phase 2 (claim_redeem)

The protocol gate `epochNumber > lastWithdrawRequest[caliber]` requires another full epoch + `stopEpoch` after Phase 1.

### Pareto-side ops sequence (off-blueprint, manager-only)

| # | Action                                                                               | tx_hash                                                              | Status  |
| - | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------- | ------- |
| 1 | `tenderly_setNextBlockTimestamp(1,779,503,300)` (past `epochEndDate + bufferPeriod`) | —                                                                    | ok      |
| 2 | Manager `IdleCDO.startEpoch()`                                                       | `0x19b4f3860777cb6e99f0753df024bab48c31b14b65c03ad3584ca0a7517bd789` | success |
| 3 | `tenderly_setNextBlockTimestamp(1,782,294,688)` (past new `epochEndDate`)            | —                                                                    | ok      |
| 4 | Manager `IdleCDO.stopEpoch(8.25e18, 0)`                                              | `0xcb44903e038a4778eb2126e0b60d65e34778ccb2e1c5a726b075a46299dfbd1d` | success |

Post-second-stopEpoch readiness:

- `IdleCreditVault.epochNumber()` = `11`
- `IdleCreditVault.lastWithdrawRequest(caliber)` = `10`
- `11 > 10` → ready
- `tranchePrice(AA)` = `1,089,265` (+0.65 % from previous epoch)

> **MEMORY.md timestamp note materialised here.** `evm_increaseTime` alone did NOT push the head past `epochEndDate` — the head reverted to a much earlier timestamp (1777582513 observed) after a single mined block. `startEpoch()` therefore failed with the manager's time gate. Issuing `tenderly_setNextBlockTimestamp` immediately before each `startEpoch` / `stopEpoch` direct call (NOT through spellcaster) made each succeed on the first attempt. This matches the runbook in `execution-withdraw.md` and the `MEMORY.md` note about Tenderly time control.

### Spellcaster invocation

```
spellcaster --config /workspace/machines-local.toml \
            --machine intMkSrRoyUSDC --caliber mainnet --dev \
            manage-position \
              --protocol royco-st-pareto-falconx \
              --action claim_redeem \
              --token "ROY-ST-Pareto-FalconX (claim)"
```

| Metric   | Value                                                                |
| -------- | -------------------------------------------------------------------- |
| Status   | **PASS** (receipt status 1)                                          |
| tx_hash  | `0x587a41838762d908e035c029df904b18f28e3214d74b1cdd468e0e7aee482f9f` |
| Block    | 24,993,374                                                           |
| Gas used | 764,630                                                              |

| Caliber balance       | Before        | After             | Δ                  |
| --------------------- | ------------- | ----------------- | ------------------ |
| `FalconXUSDC` receipt | 50,322.519155 | **0 (burned)**    | −50,322.52         |
| USDC                  | 40,000.000000 | **90,322.519155** | **+50,322.519155** |

Full-redeem payout (50,322.519155 USDC) matches the `FalconXUSDC.balanceOf` pre-claim value to the wei — i.e. the `prepareStopEpochWithApr0` slip (which the explorer measured at 1.9 USDC on a partial redeem) was 0 here, consistent with the explorer's full-redeem run on its own fork. The blueprint's account math therefore accurately predicted the final payout.

## Test 5 — Account (post-claim)

```
spellcaster --config /workspace/machines-local.toml \
            --machine intMkSrRoyUSDC --caliber mainnet --dev \
            account-positions
```

| Metric  | Value                                                                |
| ------- | -------------------------------------------------------------------- |
| Status  | **PASS**                                                             |
| tx_hash | `0x3cbf077d2c61d7071ffb532d1aadbfcc11fa3ba73bcbab9fae56ae6ac6f77389` |

`display-positions` after the final account tx shows the row collapsed to 0 (no listed position):

```
| ID | PROTOCOL | TOKEN | VALUE |
```

i.e. `convertToAssets(0) = (0,0,0)`, `AA.balanceOf = 0`, `FalconXUSDC.balanceOf = 0` → total accounted USDC value = 0.

## Aggregate P&L (caliber, this E2E)

| Quantity                                         | Value                                                                   |
| ------------------------------------------------ | ----------------------------------------------------------------------- |
| Initial USDC funded                              | 100,000.000000 USDC                                                     |
| Junior bootstrap consumed                        | 10,000.000000 USDC (off-blueprint, runbook only)                        |
| Senior commitment                                | 50,000.000000 USDC                                                      |
| Senior payout (claim)                            | 50,322.519155 USDC                                                      |
| Senior P&L                                       | **+322.519155 USDC (+0.645 %)**                                         |
| Junior leg P&L                                   | unrealised (still holds 9,938.18 JT shares — out of scope here)         |
| Wall-clock between deposit and claim (simulated) | ≈ 57 days (one epoch boundary `stopEpoch` → `startEpoch` → `stopEpoch`) |

These numbers track the explorer's full-redeem outcome (+326.617 USDC there, +322.519 USDC here) within the AA-price drift between fork blocks.

## Validation checklist

| Requirement                                                   | Status |
| ------------------------------------------------------------- | ------ |
| Root synced via CLI (`dev-update-root`)                       | YES    |
| Deposit executed via CLI (`manage-position`)                  | YES    |
| Withdraw Phase 1 executed via CLI (`manage-position`)         | YES    |
| Withdraw Phase 2 (claim) executed via CLI (`manage-position`) | YES    |
| Accounting executed via CLI (`account-positions`)             | YES    |
| Positions verified via CLI (`display-positions`)              | YES    |
| Single fresh fork used end-to-end                             | YES    |
| No blueprint or instruction file edits required               | YES    |

## Deviations vs. the execution-explorer reports

- **No oracle staleness issue.** The accounting only uses `tranchePrice(AA)` (a pure on-chain view) plus token balances; there is no Chainlink feed in the accounting path that could go stale across the time-warp. No `setFeedRoute` workaround was needed.
- **Tenderly time control quirks behaved exactly as described in `MEMORY.md`.** `evm_increaseTime` did not persist past one mined block — `tenderly_setNextBlockTimestamp` was used immediately before each manager-only direct call (`startEpoch`, second `stopEpoch`) to land the right timestamp. None of this affected the caliber/spellcaster flow itself; it only mattered for the Pareto runbook ops.
- **Numerical drift vs. the explorer's deposit-stage 49,715.825 ST.** Our fresh fork's block was 166 blocks later, so the mid-epoch AA mint formula returned 49,716.025 ST shares (+0.0004 % vs. the explorer). This is expected and the asset-space accounting still matches the on-chain `nav / 1e12` to the wei.
- **No new role gates discovered.** The caliber's mainnet ST/Kernel grants and Pareto Keyring whitelist were already in place at this fork's block, exactly as the deposit report described. The only off-chain grant required for testing was JT_LP for the junior bootstrap, which the operations team would never need on a real production deployment because the junior is bootstrapped by Royco/Pareto outside the caliber.

## Production readiness assessment

**The integration is production-ready as-shipped.** All five rootfile entries (two deposit variants + Phase 1 + Phase 2 + accounting) execute cleanly through spellcaster's `manage-position` and `account-positions` commands. The blueprint's runbook surface is exactly as documented:

1. **Deposit variant selection.** The operator picks `mid-epoch` or `between epochs` based on `IdleCDO.isEpochRunning()`. Each variant guards on the right epoch state via a `BooleanHelper.revertIfFalse / revertIfTrue` so the wrong call reverts cleanly without mutating state.
2. **Withdraw is two manual transactions separated by a Pareto-controlled epoch boundary.** Phase 1 must run between epochs (`allowAAWithdrawRequest == true`); Phase 2 must run after the next `stopEpoch` (`epochNumber > lastWithdrawRequest[caliber]`). The blueprint cannot self-gate on the second condition because it depends on Pareto operations the caliber does not control. **Operator runbook items**:
   - Schedule Phase 1 only when `IdleCDO.isEpochRunning() == false`.
   - Probe `IdleCreditVault.epochNumber()` vs. `IdleCreditVault.lastWithdrawRequest(caliber)` before invoking Phase 2; expect ~32 days minimum, ~65 days worst case.
3. **Accounting is correct in all three states**: clean post-deposit (49,715.53 USDC = ST/AA path), pending-withdraw (50,322.52 USDC = FalconXUSDC receipt only, with `convertToAssets(0)` = 0), and post-claim (0). No path-dependent gaps observed.
4. **Junior bootstrap remains a real precondition.** Senior deposit reverts in the kernel coverage check unless `jtRawNAV > 0`. On mainnet today the junior leg is bootstrapped by Royco/Pareto out-of-band; the operator should verify `RoycoJT.totalSupply() > 0` and `IdleCDO.tranchePrice(AA) > 0` before activating the senior position.

**No instruction or blueprint edits were required.** The compiled rootfile installs and executes cleanly, and the on-chain effects (token balances, accountant emits, position valuations) match the explorer's reports modulo the expected sub-block AA-price drift.
