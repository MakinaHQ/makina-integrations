# Blueprint Test Report — PRIME/PYUSD Morpho Loop

**Instruction**: machines/dusd/mainnet/instructions/morpho-loop-prime-pyusd.yaml
**Machine**: dusd
**Network**: mainnet (ethereum)
**Fork**: Tenderly Virtual TestNet `a6064c32-06f6-496f-a4ea-b8cfdf0e4e4b` (dialectic-medici/makina), forked at block 25,587,578
**Date**: 2026-07-22
**CLI**: prebuilt `spellcaster` (makina-rs `main`, release) at `/Users/augustin/Desktop/makina/makina-rs/target/release/spellcaster`
**Transpiler**: rev 9471437 (standalone)

## Summary

End-to-end test of the 9-entry PRIME/PYUSD one-legged Morpho loop (POSITION accounting model,
equity in PYUSD + async wYLDS pending-redemption term). All position-management and accounting
actions were driven through the **spellcaster CLI** (`manage-position`, `encode-swap`,
`encode-flashloan-instruction`, `account-positions`, `display-positions`, `dev-update-root`).

**Result: PASS.** Every MUST-HAVE flow executed successfully via the CLI, plus the full
best-effort Variant B async cycle. One **required config fix** was found and applied
(`flash_loan_aggregator` address was stale — see Blueprint Fixes); without it every
FLASHLOAN_MANAGEMENT entry reverts `NotFlashLoanModule()`.

Flows proven via CLI:

- **account (idle, equity 0 + pending 0)** — `display-positions`/`account-positions`
- **add_collateral (build position)** — MANAGEMENT + PYUSD→USDC aggregator swap
- **borrow** — MANAGEMENT (create PYUSD debt)
- **Variant A `close_loop_swap` (atomic flashloan close, PREFERRED exit)** — via
  `encode-flashloan-instruction` → `flashloan_request`
- **Variant B `unwind_to_pending` → completeRedeem → `swap_to_loan`** — full async
  request→settle→swap cycle, incl. the pending-term NAV bridge
- **repay** — exercised inside `close_loop_swap` and `unwind_to_pending`

## Contract Addresses

| Contract                          | Address                                                              |
| --------------------------------- | -------------------------------------------------------------------- |
| Caliber (dusd mainnet)            | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC`                         |
| Machine / hub                     | `0x6b006870C83b1Cd49E766Ac9209f8d68763Df721`                         |
| Mechanic (gas payer)              | `0x425BbC2cfF0c7E7960baA9BaC2f0Cb67B41d3beF`                         |
| CoreRegistry                      | `0x0FAEeCEab0BCb63bE2Fe984Ea8c77778989d53eA`                         |
| Registry.flashLoanModule (LIVE)   | `0xa36F64152EA5df6a0eC732aAa7950dcb930fF3D4`                         |
| flash_loan_aggregator (in config) | `0x820D35e62Ad73a5Dc7b81d54cE993080d2064065` (**STALE — wrong**)     |
| swap_module                       | `0x923c98b22F9c367A109E93f7dfBaCa28b20C17C3`                         |
| Morpho Blue                       | `0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb`                         |
| Morpho market id                  | `0x41c41d0c9aadbf4751f5ee215ed5a16954a4b34e1b70fca5393d4b08858fa3fa` |
| Morpho oracle (PRIME/PYUSD)       | `0x335e5718bC20028d5e357473a3736C187Ca6b07e`                         |
| PRIME (collateral)                | `0x19ebb35279A16207Ec4ba82799CC64715065F7F6`                         |
| wYLDS (async ERC4626)             | `0x6aD038cA6C04e885630851278ca0a856Ad9a66Cc`                         |
| PYUSD (loan / base token)         | `0x6c3ea9036406852006290770BEdFcAbA0e23A0e8`                         |
| USDC (intermediate / acct token)  | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`                         |
| NAV FeedVerifier (proxy)          | `0xdF4ab20fA7752Be52E41e42F1FD667f37964d6a3`                         |
| REWARDS_ADMIN (Hastra)            | `0x8D358B8aE881F8ea92C3d07783aBCA21727C6309`                         |
| wYLDS redeemVault                 | `0xA8C3CF6183D49d5D372f8FC149BD2cb5CFC0faCd`                         |

## Setup / Execution Steps

| Step                 | Status | Details                                                                                                    |
| -------------------- | ------ | ---------------------------------------------------------------------------------------------------------- |
| Compile (transpiler) | PASS   | `caliber-test.yaml` → isolated rootfile; `check`+`transpile` EXIT=0; position id + addrs present           |
| Fork provisioning    | PASS   | Fresh vnet created **under dialectic-medici/makina** (see Env Gotcha #1) at block 25,587,578               |
| Config wiring        | PASS   | Isolated spellcaster `config.toml` → dusd mainnet rootfiles = isolated dir (other calibers reuse existing) |
| Update root (CLI)    | PASS   | `dev-update-root --root <hash>`; on-chain root == rootfile root (post-fix root `0x7eae220d…1427`)          |
| Fund mechanic (ETH)  | PASS   | 10 ETH for gas (Tenderly `tenderly_setBalance`)                                                            |
| Fund caliber (PYUSD) | PASS   | 300,000 PYUSD (Tenderly `tenderly_setErc20Balance`)                                                        |
| NAV staleness fix    | PASS   | FeedVerifier slot 306 `3600` → `315360000` (protects PRIME.redeem in Variant B; see Gotcha #3)             |

## Test Results

Every state-changing transaction below was **submitted by the spellcaster CLI** and mined on the
fork (impersonated mechanic in dev mode). Receipt status verified with `cast receipt … status`.

### 1. Account — idle (equity read, pending = 0)

| Metric                    | Value                                                                           |
| ------------------------- | ------------------------------------------------------------------------------- |
| Status                    | PASS                                                                            |
| `account-positions` tx    | `0xc0eba4d1d42743a400c51686d85582c1581af6aebf37b20ae0a9c32be7ea4187` (status 1) |
| `display-positions` value | **0 USDC** (no collateral, no debt, pending = 0)                                |

```bash
spellcaster --config <config.toml> --dev --machine dusd --caliber mainnet account-positions
spellcaster --config <config.toml> --dev --machine dusd --caliber mainnet display-positions
```

### 2. add_collateral — build position (MANAGEMENT + swap)

| Metric                    | Value                                                                           |
| ------------------------- | ------------------------------------------------------------------------------- |
| Status                    | PASS                                                                            |
| Tx                        | `0xb5c224fcf70e384530d67f4c057c4d5d0db1943edfe787de9389d626710dc8bb` (status 1) |
| Swap                      | PYUSD 100,000 → USDC ~100,002.29 (swapperId 3, aggregator via `encode-swap`)    |
| Position after            | collateral **95,272.916035 PRIME**, debt 0                                      |
| `display-positions` value | **100,010.980406 USDC**                                                         |

Swap data generated by the CLI and decomposed into the 4 SwapData sub-slots:

```bash
# 1) generate the swap order
spellcaster --config <config.toml> --dev --machine dusd --caliber mainnet encode-swap \
  --input-address 0x6c3ea9036406852006290770BEdFcAbA0e23A0e8 \
  --output-address 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 \
  --input-amount 100000000000 --slippage 0.5
# 2) supply the 4 slots (swapperId, data, inputAmount, minOutputAmount)
spellcaster --config <config.toml> --dev --machine dusd --caliber mainnet manage-position \
  --protocol morpho --action add_collateral \
  --token "PRIME/PYUSD Morpho Loop - Add Collateral" \
  --inputs 0x<swapperId(uint256)> \
  --inputs 0x<abi_encode(bytes data)[32:]  # length-prefixed, 32-padded> \
  --inputs 0x<inputAmount(uint256)> \
  --inputs 0x<minOutputAmount(uint256)>
```

### 3. borrow — create debt (MANAGEMENT)

| Metric         | Value                                                                                    |
| -------------- | ---------------------------------------------------------------------------------------- |
| Status         | PASS                                                                                     |
| Tx             | `0xdeffaa1183b5c9a626161ffbaf1fdd41958879e4b6395310f1dd174ffd7510d3` (status 1)          |
| Amount         | 40,000 PYUSD                                                                             |
| Position after | collateral 95,272.916035 PRIME, borrowShares 39,663,640,413,710,579 (~40,000 PYUSD debt) |

```bash
spellcaster --config <config.toml> --dev --machine dusd --caliber mainnet manage-position \
  --protocol morpho --action borrow --token "PRIME/PYUSD Morpho Loop - Borrow" \
  --inputs 0x000000000000000000000000000000000000000000000000000000094a5c1000  # 40000e6
```

### 4. Variant A — `close_loop_swap` (atomic flashloan close, PREFERRED exit)

| Metric                 | Value                                                                                                           |
| ---------------------- | --------------------------------------------------------------------------------------------------------------- |
| Status                 | PASS                                                                                                            |
| `flashloan_request` tx | `0xabe721c5e8b55fdb881d55f660762f38f4f1d3e395870b6af9b89d98b42978d9` (status 1)                                 |
| Callback body          | repay ALL (shares) → withdraw ALL PRIME → PRIME→USDC (swapperId 10001) → USDC→PYUSD (swapperId 3) → repay flash |
| Position after         | **[0, 0, 0]** (fully closed)                                                                                    |
| Caliber after          | PYUSD 299,472.339770 + USDC 500.878922 dust, PRIME 0                                                            |

FLASHLOAN_MANAGEMENT is not runnable via non-interactive `manage-position` (which filters to
`Management`), so it is driven by the two-step flashloan path: `encode-flashloan-instruction`
produces the callback (with merkle proof), which becomes the `flash_loan_data` slot of the
`flashloan_request` MANAGEMENT instruction.

```bash
# encode both swap legs with encode-swap (PRIME->USDC for full collateral, USDC->PYUSD for swap1 minOut)
# then:
FLD=$(spellcaster --config <config.toml> --dev --machine dusd --caliber mainnet \
  encode-flashloan-instruction --protocol morpho --action close_loop_swap \
  --token "PRIME/PYUSD Morpho Loop - Close Loop (atomic, Variant A)" \
  --inputs <prime_usdc.swapperId> --inputs <prime_usdc.data> --inputs <prime_usdc.inputAmount> --inputs <prime_usdc.minOut> \
  --inputs <usdc_loan.swapperId> --inputs <usdc_loan.data> --inputs <usdc_loan.inputAmount> --inputs <usdc_loan.minOut>)
spellcaster --config <config.toml> --dev --machine dusd --caliber mainnet manage-position \
  --protocol makina-flashloan --action flashloan_request \
  --token "PRIME/PYUSD Morpho Loop - Flash Loan Request" \
  --inputs 0x<PYUSD address>       \
  --inputs 0x<flash_loan_amount 45000e6> \
  --inputs $FLD                    \
  --inputs 0x…03                    # venue = 3 (Morpho)
```

**Round-trip (Variant A):** pre-close total ≈ 300,010.98 USDC-equiv (240,000 loose PYUSD +
60,010.98 position equity) → post-close 299,472.34 PYUSD + 500.88 USDC ≈ **299,973.22** →
cost ≈ 37.8 USDC (~0.013%): two aggregator swaps + accrued interest. Confirmed `display-positions` = 0
and `account-positions` tx `0x0c0bc30772a448b3b05ec6ae57ead372804468a9a4487d7c7e2fb7624b3a80e5` (status 1).

### 5. Variant B — staged async exit (best-effort, FULLY proven)

Rebuilt a fresh position (add_collateral tx `0xf970231ab7b041e9e142c5848ee42cb0387a80dafbccee00425c9613f8db2070`,
borrow tx `0x3927a183c9bf4a5f295e16d970c0903fc58d02be7dc89c6e0a7136ea72c71a67`), then:

**B1 — `unwind_to_pending`** (MANAGEMENT, no input slots; repay from idle PYUSD + withdraw all +
PRIME.redeem→wYLDS + wYLDS.requestRedeem):

| Metric                        | Value                                                                           |
| ----------------------------- | ------------------------------------------------------------------------------- |
| Status                        | PASS                                                                            |
| Tx                            | `0x6a4d313e39ca89da8bdbf775d88bf3b04fa71dd573253855da617f468a59df1b` (status 1) |
| Position after                | [0, 0, 0]                                                                       |
| `pendingRedemptions(caliber)` | shares 100,002.291917, **assets 100,002.291917 USDC**, ts 1784716266            |
| caliber wYLDS / PRIME         | 0 / 0 (shares locked in the wYLDS contract)                                     |

**Pending-term NAV bridge (verified):** with the Morpho position empty, `display-positions`
still reports **100,006.192006 USDC** for the position — i.e. the accounting's
`pendingRedemptions.assets` term supplies the value during the async window, so NAV stays
continuous (no dip to 0). `account-positions` tx
`0x9525b8fcedfb142138917666921fbbd779c9c99499922cd050195a0f7cdcb760` (status 1).

**completeRedeem** (Hastra REWARDS_ADMIN — off-chain admin step, modeled by impersonation +
funding the redeemVault with USDC; NOT a caliber CLI instruction):

| Metric | Value                                                                                                |
| ------ | ---------------------------------------------------------------------------------------------------- |
| Status | PASS                                                                                                 |
| Caller | REWARDS_ADMIN `0x8D358B8a…` (impersonated)                                                           |
| Effect | `pendingRedemptions` → [0,0,0]; caliber USDC 500.878922 → **100,503.170839** (+100,002.291917 exact) |

No double count: the pending mapping is deleted in the same tx the USDC lands loose (recaptured by
native USDC base-token accounting).

**B2 — `swap_to_loan`** (MANAGEMENT + USDC→PYUSD swap):

| Metric           | Value                                                                           |
| ---------------- | ------------------------------------------------------------------------------- |
| Status           | PASS                                                                            |
| Tx               | `0x9a080389979fbf3c9b5f815740507a47981b2867149fc15f093e4b4d27a4aa70` (status 1) |
| Swap             | USDC 100,002.291917 → PYUSD (swapperId 3)                                       |
| Position after   | 0 (fully exited, no pending)                                                    |
| Final account tx | `0xb9f69c9b950bdbff73336f8acd0b1ef789164ef3680883a89e8f4dc485ad173a` (status 1) |

```bash
spellcaster --config <config.toml> --dev --machine dusd --caliber mainnet manage-position \
  --protocol morpho --action swap_to_loan \
  --token "PRIME/PYUSD Morpho Loop - Swap To Loan (Variant B2)" \
  --inputs 0x<swapperId> --inputs 0x<data> --inputs 0x<inputAmount> --inputs 0x<minOut>
```

## Final Caliber NAV vs Expected

| Component                 | Value (USDC-equiv)           |
| ------------------------- | ---------------------------- |
| PRIME/PYUSD position      | 0 (fully exited both cycles) |
| Loose PYUSD               | 299,471.068733               |
| Loose USDC                | 500.878922                   |
| **My test principal NAV** | **~299,971.95**              |

Started from 300,000 PYUSD. After **two full open→close cycles** (Variant A + Variant B, i.e. 4
aggregator swaps + 2 borrow/repay-interest legs) the residual ≈ 300,000 − 299,972 ≈ **28 USDC
(~0.0093%)** — consistent with cumulative swap slippage + Morpho borrow interest. NAV reconciles;
no value leaked. (The fork also carries unrelated pre-existing mainnet base-token balances such as
reUSD/RLUSD that are not part of this test.)

## Blueprint / Config Fixes Required

1. **REQUIRED — `flash_loan_aggregator` is stale (blocks Variant A + loop_in).**
   The instruction/config uses `config.flash_loan_aggregator = 0x820D35e62Ad73a5Dc7b81d54cE993080d2064065`,
   but the caliber's `manageFlashLoan` only accepts callbacks from the address registered as
   `CoreRegistry.flashLoanModule()`, which on mainnet is
   **`0xa36F64152EA5df6a0eC732aAa7950dcb930fF3D4`**. With the stale address the flashloan callback
   reverts `NotFlashLoanModule()` (inner selector `0x15cd345c`, wrapped as
   `ExecutionFailed(uint256,address,string)` `0xef3dcb2f`). Fixing `config.flash_loan_aggregator`
   to `0xa36F64152EA5df6a0eC732aAa7950dcb930fF3D4` made Variant A pass first try.
   **Scope warning:** `flash_loan_aggregator` is fund-wide config in `machines/dusd/mainnet/caliber.yaml`;
   the same stale value is shared by every other dusd morpho loop (sUSDS/USDT, syrupUSDC/*, etc.), so
   those FLASHLOAN_MANAGEMENT flows would fail identically until the config is updated. `0xa36F64…` is
   interface-compatible (`morphoPool()` = Morpho Blue, same `requestFlashloan`/`onMorphoFlashLoan` selectors).

2. **No instruction-file bug otherwise.** All 9 entries compiled, synced, and executed as designed;
   accounting (equity + pending term), the two-hop swap close, and the async unwind all behaved exactly
   per the execution reports.

## Operator / Tooling Notes (not blueprint bugs)

- **FLASHLOAN_MANAGEMENT can't run via non-interactive `manage-position`** — that command filters to
  `InstructionType::Management`. Drive `loop_in` / `close_loop_swap` via
  `encode-flashloan-instruction` (produces the proof-bearing callback) → pass it as the
  `flash_loan_data` slot of the `flashloan_request` MANAGEMENT instruction (or use interactive mode).
- **Non-interactive SwapData `data` sub-slot encoding.** For MANAGEMENT swaps (add_collateral,
  swap_to_loan) the `data` Bytes slot must be supplied as `abi_encode(bytes)[32:]` (length-prefix +
  zero-pad to a 32-byte multiple). Passing the raw aggregator calldata reverts
  `"Dynamic state variables must be a multiple of 32 bytes"`. The interactive SwapData flow does this
  automatically (`swap_order_to_mapping`); the other three sub-slots (swapperId/inputAmount/minOut) are
  plain 32-byte uints. `encode-swap` output = `abi_encode_params(SwapOrder)`, decode with
  `(uint16,bytes,address,address,uint256,uint256)`.
- **Aggregator routes reproduced on the fork.** With the fork only ~1,000 blocks behind live, `encode-swap`
  (Odos / meta-matcha) produced calldata that executed on-fork for PYUSD↔USDC (swapperId 3) and
  PRIME→USDC (swapperId 10001). No manual DEX substitution was needed (unlike Stage 2). Keep the fork
  close to head; for stale forks fall back to the UniV3 PRIME/USDC 0.01% pool + Curve PYUSD/USDC directly.

## Environment Gotchas Encountered

1. **Tenderly simulation auth.** State-changing CLI txs run a Tenderly _simulation_ against
   `api.tenderly.co/.../account/dialectic-medici/project/makina/...` using the `.env` API key. A testnet
   created by the claude.ai Tenderly MCP connector lives in a **different** account → `401 Unauthorized`.
   Fix: create the fork **under dialectic-medici/makina** via the Tenderly REST API (`X-Access-Key` = the
   `.env` key) so simulation + RPC align. (Read-only `display-*` work regardless.)
2. **CLI config format.** The prebuilt `main` `spellcaster` uses a full `config.toml`
   (`[machines]`, `[dev_rpc_urls]`, `[tenderly]`, `[tenderly.testnets]`), not the old
   `machines-local.toml` shape, and `dev-update-root` takes `--root <hash>` (not `--rootfile`).
3. **NAV oracle staleness.** spellcaster mines the fork forward to wall-clock before each tx, so the
   Hastra NAV feed can drift past the 3600 s window and make `PRIME.redeem` (Variant B) revert
   `StalePrice`. Pre-extended `FeedVerifier` (`0xdF4ab20f…`) slot 306 → `315360000`. (Variant A never
   touches the NAV oracle — it sells PRIME on the DEX.)

## Validation Checklist

| Requirement                                                                                         | Status |
| --------------------------------------------------------------------------------------------------- | ------ |
| Root synced via CLI (`dev-update-root`)                                                             | YES    |
| Account read via CLI (idle = 0 incl. pending)                                                       | YES    |
| Deposit/add_collateral executed via CLI (`manage-position`)                                         | YES    |
| Borrow executed via CLI (`manage-position`)                                                         | YES    |
| Exit executed via CLI — Variant A atomic close (`encode-flashloan-instruction`+`flashloan_request`) | YES    |
| Exit executed via CLI — Variant B (`unwind_to_pending` + `swap_to_loan`)                            | YES    |
| Async completeRedeem (off-chain admin, impersonated)                                                | YES    |
| Positions verified via CLI (`display-positions` / `account-positions`)                              | YES    |
| Pending-term NAV continuity verified                                                                | YES    |

## Result: PASS

All MUST-HAVE flows (idle account, add_collateral build, Variant A atomic exit) plus the full
best-effort Variant B async cycle executed **through the spellcaster CLI** and verified on-chain.
One required config fix (`flash_loan_aggregator` → `0xa36F64152EA5df6a0eC732aAa7950dcb930fF3D4`) was
identified, applied, and validated. No instruction-file changes required.
