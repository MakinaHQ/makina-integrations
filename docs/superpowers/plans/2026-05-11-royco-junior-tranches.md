# Royco Junior Tranches Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Royco junior-tranche (JT) instruction libraries for the stcUSD and syrupUSDC markets, mirroring the existing senior-tranche surface, with accounting denominated in cUSD/USDC (not USD-WAD).

**Architecture:** New blueprint folders `blueprints/royco/jt-stcusd/` (6 files) and `blueprints/royco/jt-syrupusdc/` (3 files), plus two instruction files (`instructions/royco-jt-stcusd.yaml` and `instructions/royco-jt-syrupusdc.yaml`). Each JT blueprint is byte-near-identical to its ST counterpart with the tranche address swapped; accounting blueprints take the sum `(stAssets + jtAssets)` from `JT.convertToAssets(jt_shares)` in TRANCHE_UNIT and apply a single vault hop (`stcUSD.convertToAssets` → cUSD, or `syrupUSDC.convertToExitAssets` → USDC).

**Tech Stack:** YAML blueprints/instructions consumed by the makina-rs transpiler; `/compile` slash command validates each instruction file; `blueprint-tester` validates end-to-end on a Tenderly fork.

**Reference spec:** `docs/superpowers/specs/2026-05-08-royco-junior-tranches-design.md`

**User-runs convention:** Per the project's standing instruction, the user runs the transpiler (`/compile`) themselves. The plan calls this out as "ask the user to run `/compile <path>`" — do NOT run it from a subagent.

---

## File Structure

**New blueprint files (9):**

| Path                                                | Responsibility                                               |
| --------------------------------------------------- | ------------------------------------------------------------ |
| `blueprints/royco/jt-stcusd/deposit.yaml`           | USDC→cUSD→stcUSD→JT, whitelist-gated                         |
| `blueprints/royco/jt-stcusd/withdraw.yaml`          | JT→stcUSD→cUSD→USDC, escape hatch                            |
| `blueprints/royco/jt-stcusd/withdraw-to-cusd.yaml`  | JT→stcUSD→cUSD (no Cap touch)                                |
| `blueprints/royco/jt-stcusd/deposit-from-cusd.yaml` | cUSD→stcUSD→JT (no Cap touch)                                |
| `blueprints/royco/jt-stcusd/burn-cusd-to-usdc.yaml` | cUSD→USDC standalone, whitelist-gated                        |
| `blueprints/royco/jt-stcusd/account.yaml`           | Reports JT position in cUSD (18 dec)                         |
| `blueprints/royco/jt-syrupusdc/deposit.yaml`        | USDC→syrupUSDC→JT                                            |
| `blueprints/royco/jt-syrupusdc/withdraw.yaml`       | JT→syrupUSDC→requestRedeem                                   |
| `blueprints/royco/jt-syrupusdc/account.yaml`        | Reports JT position in USDC (6 dec, includes pending escrow) |

**New instruction files (2):**

| Path                                   | Responsibility                                                           |
| -------------------------------------- | ------------------------------------------------------------------------ |
| `instructions/royco-jt-stcusd.yaml`    | 6 entries (5 MGMT + 1 ACCOUNTING) referencing `jt-stcusd/` blueprints    |
| `instructions/royco-jt-syrupusdc.yaml` | 3 entries (2 MGMT + 1 ACCOUNTING) referencing `jt-syrupusdc/` blueprints |

**Modified files (1):**

| Path                                                   | Responsibility                                                                                   |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| `scripts-factory/royco-st-stcusd/nav-investigation.md` | Correct the false claim that `jtAssets` is in cUSD — it's TRANCHE_UNIT (stcUSD) per `Types.sol`. |

**Constants (verified on-chain or sourced from Royco V2 repo):**

| Name                       | Address                                      |
| -------------------------- | -------------------------------------------- |
| `JT_STCUSD`                | `0xe4060e83ad26618c7ed56a02ce099beba4f73b29` |
| `JT_SYRUPUSDC`             | `0x5f340b400f892bbfded2e5c316369dcbf05c282a` |
| `STCUSD_KERNEL`            | `0x9911F227E9428964D8A35B852513919C8DF92038` |
| `SYRUPUSDC_KERNEL`         | `0xde1Ce2cF64808e50d000F93058784270E412B3A4` |
| `STCUSD`                   | `0x88887bE419578051FF9F4eb6C858A951921D8888` |
| `SYRUPUSDC`                | `0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b` |
| `CUSD`                     | `0xcCcc62962d17b8914c62D74FfB843d73B2a3cccC` |
| `USDC`                     | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` |
| `MAPLE_WITHDRAWAL_MANAGER` | `0x1bc47a0Dd0FdaB96E9eF982fdf1F34DC6207cfE3` |
| `CONTEXT_HELPER`           | `0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE` |
| `BOOLEAN_HELPER`           | `0x00c93e3b09Ca2f544487d4298339765EadCD8353` |
| `UNSIGNED_MATH_HELPER`     | `0x3D623B199E290358416415eA7e05B635E442e3c0` |
| `BYTES32_HELPER`           | `0x74DC739B8F98ad0F76Cd8900695DD8D5083E45D3` |

---

## Phase 1: `jt-stcusd/` blueprint folder

Six blueprint files. Each is a near-verbatim copy of the corresponding ST file with only the `senior_tranche_address` swapped for `junior_tranche_address` and protocol label changed to `royco-jt-stcusd`. The exception is `account.yaml`, which introduces the cUSD-denominated accounting pattern.

### Task 1: `jt-stcusd/deposit.yaml`

**Files:**

- Create: `blueprints/royco/jt-stcusd/deposit.yaml`

- [ ] **Step 1: Write the blueprint file**

```yaml
protocol: "royco-jt-stcusd"

# Royco Junior Tranche stcUSD - Deposit Blueprint
# Atomic chain: USDC -> cUSD (Cap Vault.mint) -> stcUSD (ERC4626) -> JT-stcUSD shares
# Reverts if caliber is not whitelisted on the Cap Vault (would otherwise be charged dynamic mint fees).
# Mirrors blueprints/royco/st-stcusd/deposit.yaml exactly; only the tranche address differs.

constants:
  context_helper_address:
    type: "address"
    value: "0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE"
  boolean_helper_address:
    type: "address"
    value: "0x00c93e3b09Ca2f544487d4298339765EadCD8353"
  usdc_address:
    type: "address"
    value: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
  cusd_address:
    type: "address"
    value: "0xcCcc62962d17b8914c62D74FfB843d73B2a3cccC"
  stcusd_address:
    type: "address"
    value: "0x88887bE419578051FF9F4eb6C858A951921D8888"
  junior_tranche_address:
    type: "address"
    value: "0xe4060e83ad26618c7ed56a02ce099beba4f73b29"

inputs: {}

actions:
  deposit:
    calls:
      - description: "Get caliber's address"
        target: ${constants.context_helper_address}
        selector: "msgSender()"
        parameters: []
        return:
          name: "caliber_address"
          type: "address"

      - description: "Read whitelist status of caliber on Cap Vault"
        target: "${constants.cusd_address}"
        selector: "whitelisted(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "is_whitelisted"
          type: "bool"

      - description: "Revert if caliber is not whitelisted (would incur mint fees)"
        target: "${constants.boolean_helper_address}"
        selector: "revertIfFalse(bool)"
        parameters:
          - type: "bool"
            value: "${returns.is_whitelisted}"

      - description: "Approve USDC spending by Cap Vault"
        target: "${constants.usdc_address}"
        selector: "approve(address,uint256)"
        parameters:
          - type: "address"
            value: "${constants.cusd_address}"
          - type: "uint256"
            value: "${input_slots.usdc_amount_to_deposit}"

      - description: "Mint cUSD from USDC via Cap Vault (no fees because whitelisted)"
        target: "${constants.cusd_address}"
        selector: "mint(address,uint256,uint256,address,uint256)"
        parameters:
          - type: "address"
            value: "${constants.usdc_address}"
          - type: "uint256"
            value: "${input_slots.usdc_amount_to_deposit}"
          - type: "uint256"
            value: "${input_slots.min_cusd_out}"
          - type: "address"
            value: "${returns.caliber_address}"
          - type: "uint256"
            value: "${builtins.UINT256_MAX}"
        return:
          name: "cusd_minted"
          type: "uint256"

      - description: "Approve cUSD spending by stcUSD vault"
        target: "${constants.cusd_address}"
        selector: "approve(address,uint256)"
        parameters:
          - type: "address"
            value: "${constants.stcusd_address}"
          - type: "uint256"
            value: "${returns.cusd_minted}"

      - description: "Deposit cUSD into stcUSD vault to receive stcUSD shares"
        target: "${constants.stcusd_address}"
        selector: "deposit(uint256,address)"
        parameters:
          - type: "uint256"
            value: "${returns.cusd_minted}"
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "stcusd_shares"
          type: "uint256"

      - description: "Approve stcUSD spending by Junior Tranche"
        target: "${constants.stcusd_address}"
        selector: "approve(address,uint256)"
        parameters:
          - type: "address"
            value: "${constants.junior_tranche_address}"
          - type: "uint256"
            value: "${returns.stcusd_shares}"

      - description: "Deposit stcUSD into Junior Tranche to receive JT shares"
        target: "${constants.junior_tranche_address}"
        selector: "deposit(uint256,address)"
        parameters:
          - type: "uint256"
            value: "${returns.stcusd_shares}"
          - type: "address"
            value: "${returns.caliber_address}"

    input_slots:
      usdc_amount_to_deposit:
        type: "uint256"
        description: "Amount of USDC to deposit (6 decimals)"
      min_cusd_out:
        type: "uint256"
        description: "Minimum cUSD to receive from Cap Vault.mint (18 decimals). Whitelisted callers pay no fee but the rate is NOT exactly 1:1 — it tracks the Vault's value-per-cUSD (Lender interest, basket PnL) and moves over time. As of 2026-04 the whitelisted rate is ~1.0000009 cUSD per USDC, but it can drift either way. Operator must quote fresh via cUSD.getMintAmount(caliber, USDC, usdc_amount_to_deposit) immediately before broadcasting and apply a small tolerance (e.g., 1-2 bps)."
```

### Task 2: `jt-stcusd/withdraw.yaml`

**Files:**

- Create: `blueprints/royco/jt-stcusd/withdraw.yaml`

- [ ] **Step 1: Write the blueprint file**

```yaml
protocol: "royco-jt-stcusd"

# Royco Junior Tranche stcUSD - Full Withdraw Blueprint
# Atomic unwind: JT-stcUSD -> stcUSD -> cUSD (ERC4626) -> USDC (Cap Vault.burn)
# Mirrors blueprints/royco/st-stcusd/withdraw.yaml; only the tranche address differs.
# Junior tranche redeem is synchronous (no queue at the tranche layer).

constants:
  context_helper_address:
    type: "address"
    value: "0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE"
  unsigned_math_helper_address:
    type: "address"
    value: "0x3D623B199E290358416415eA7e05B635E442e3c0"
  usdc_address:
    type: "address"
    value: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
  cusd_address:
    type: "address"
    value: "0xcCcc62962d17b8914c62D74FfB843d73B2a3cccC"
  stcusd_address:
    type: "address"
    value: "0x88887bE419578051FF9F4eb6C858A951921D8888"
  junior_tranche_address:
    type: "address"
    value: "0xe4060e83ad26618c7ed56a02ce099beba4f73b29"

inputs: {}

actions:
  withdraw:
    calls:
      - description: "Get caliber's address"
        target: ${constants.context_helper_address}
        selector: "msgSender()"
        parameters: []
        return:
          name: "caliber_address"
          type: "address"

      - description: "Get Junior Tranche share balance"
        target: "${constants.junior_tranche_address}"
        selector: "balanceOf(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "jt_shares"
          type: "uint256"

      - description: "Calculate JT shares to redeem based on basis points"
        target: "${constants.unsigned_math_helper_address}"
        selector: "mulDiv(uint256,uint256,uint256)"
        parameters:
          - type: "uint256"
            value: "${returns.jt_shares}"
          - type: "uint256"
            value: "${input_slots.bps_to_redeem}"
          - type: "uint256"
            value: "10000"
        return:
          name: "shares_to_redeem"
          type: "uint256"

      - description: "Get stcUSD balance before JT redeem"
        target: "${constants.stcusd_address}"
        selector: "balanceOf(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "stcusd_before"
          type: "uint256"

      - description: "Redeem Junior Tranche shares to receive stcUSD"
        target: "${constants.junior_tranche_address}"
        selector: "redeem(uint256,address,address)"
        parameters:
          - type: "uint256"
            value: "${returns.shares_to_redeem}"
          - type: "address"
            value: "${returns.caliber_address}"
          - type: "address"
            value: "${returns.caliber_address}"

      - description: "Get stcUSD balance after JT redeem"
        target: "${constants.stcusd_address}"
        selector: "balanceOf(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "stcusd_after"
          type: "uint256"

      - description: "Compute stcUSD received from JT redeem"
        target: "${constants.unsigned_math_helper_address}"
        selector: "sub(uint256,uint256)" # sub(a, b) = a - b; pass (after, before) → after - before
        parameters:
          - type: "uint256"
            value: "${returns.stcusd_after}"
          - type: "uint256"
            value: "${returns.stcusd_before}"
        return:
          name: "stcusd_received"
          type: "uint256"

      - description: "Redeem stcUSD for cUSD"
        target: "${constants.stcusd_address}"
        selector: "redeem(uint256,address,address)"
        parameters:
          - type: "uint256"
            value: "${returns.stcusd_received}"
          - type: "address"
            value: "${returns.caliber_address}"
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "cusd_received"
          type: "uint256"

      - description: "Burn cUSD for USDC via Cap Vault"
        target: "${constants.cusd_address}"
        selector: "burn(address,uint256,uint256,address,uint256)"
        parameters:
          - type: "address"
            value: "${constants.usdc_address}"
          - type: "uint256"
            value: "${returns.cusd_received}"
          - type: "uint256"
            value: "${input_slots.min_usdc_out}"
          - type: "address"
            value: "${returns.caliber_address}"
          - type: "uint256"
            value: "${builtins.UINT256_MAX}"

    input_slots:
      bps_to_redeem:
        type: "uint256"
        description: "Basis points of JT shares to redeem (10000 = 100%)"
      min_usdc_out:
        type: "uint256"
        description: "Minimum USDC to receive from Cap Vault.burn (6 decimals). The exact output depends on (a) the Vault's current value-per-cUSD rate, which moves with Lender interest and basket PnL — even whitelisted users do NOT get an exact 1:1 conversion (rate was ~0.999999149 USDC/cUSD as of 2026-04); and (b) the dynamic burn fee, which whitelisted callers bypass but un-whitelisted callers pay (~0.1% as of 2026-04, but verify on-chain). Operator must quote fresh via cUSD.getBurnAmount(caliber, USDC, cusd_received) immediately before broadcasting and apply a small tolerance (e.g., 1-2 bps)."
```

NOTE on `sub(a, b)`: the mainnet `unsigned_math_helper.sub(a, b)` returns `a - b` (verified on-chain 2026-05-11: `sub(5, 3) = 2`, `sub(3, 5)` reverts). An older `MEMORY.md` note claimed `b - a` (reversed) — wrong for this helper. The argument order `(after, before)` is correct under `a - b` semantics and produces the positive delta we want. Keep the inline comment as a reader hint.

### Task 3: `jt-stcusd/withdraw-to-cusd.yaml`

**Files:**

- Create: `blueprints/royco/jt-stcusd/withdraw-to-cusd.yaml`

- [ ] **Step 1: Write the blueprint file**

```yaml
protocol: "royco-jt-stcusd"

# Royco Junior Tranche stcUSD - Partial Withdraw Blueprint (stops at cUSD)
# JT-stcUSD -> stcUSD (kernel sends asset) -> cUSD; leaves cUSD in caliber.
# Use when the Cap Vault is illiquid for cUSD->USDC and you want to exit
# Royco/stcUSD anyway. Pair with burn-cusd-to-usdc.yaml when Vault liquidity returns.
# No whitelist guard needed — does not touch the Cap Vault.

constants:
  context_helper_address:
    type: "address"
    value: "0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE"
  unsigned_math_helper_address:
    type: "address"
    value: "0x3D623B199E290358416415eA7e05B635E442e3c0"
  stcusd_address:
    type: "address"
    value: "0x88887bE419578051FF9F4eb6C858A951921D8888"
  junior_tranche_address:
    type: "address"
    value: "0xe4060e83ad26618c7ed56a02ce099beba4f73b29"

inputs: {}

actions:
  withdraw_to_cusd:
    calls:
      - description: "Get caliber's address"
        target: ${constants.context_helper_address}
        selector: "msgSender()"
        parameters: []
        return:
          name: "caliber_address"
          type: "address"

      - description: "Get Junior Tranche share balance"
        target: "${constants.junior_tranche_address}"
        selector: "balanceOf(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "jt_shares"
          type: "uint256"

      - description: "Calculate JT shares to redeem based on basis points"
        target: "${constants.unsigned_math_helper_address}"
        selector: "mulDiv(uint256,uint256,uint256)"
        parameters:
          - type: "uint256"
            value: "${returns.jt_shares}"
          - type: "uint256"
            value: "${input_slots.bps_to_redeem}"
          - type: "uint256"
            value: "10000"
        return:
          name: "shares_to_redeem"
          type: "uint256"

      - description: "Get stcUSD balance before JT redeem"
        target: "${constants.stcusd_address}"
        selector: "balanceOf(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "stcusd_before"
          type: "uint256"

      - description: "Redeem Junior Tranche shares to receive stcUSD"
        target: "${constants.junior_tranche_address}"
        selector: "redeem(uint256,address,address)"
        parameters:
          - type: "uint256"
            value: "${returns.shares_to_redeem}"
          - type: "address"
            value: "${returns.caliber_address}"
          - type: "address"
            value: "${returns.caliber_address}"

      - description: "Get stcUSD balance after JT redeem"
        target: "${constants.stcusd_address}"
        selector: "balanceOf(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "stcusd_after"
          type: "uint256"

      - description: "Compute stcUSD received from JT redeem"
        target: "${constants.unsigned_math_helper_address}"
        selector: "sub(uint256,uint256)" # sub(a, b) = a - b; pass (after, before) → after - before
        parameters:
          - type: "uint256"
            value: "${returns.stcusd_after}"
          - type: "uint256"
            value: "${returns.stcusd_before}"
        return:
          name: "stcusd_received"
          type: "uint256"

      - description: "Redeem stcUSD for cUSD (leaves cUSD in caliber)"
        target: "${constants.stcusd_address}"
        selector: "redeem(uint256,address,address)"
        parameters:
          - type: "uint256"
            value: "${returns.stcusd_received}"
          - type: "address"
            value: "${returns.caliber_address}"
          - type: "address"
            value: "${returns.caliber_address}"

    input_slots:
      bps_to_redeem:
        type: "uint256"
        description: "Basis points of JT shares to redeem (10000 = 100%)"
```

### Task 4: `jt-stcusd/deposit-from-cusd.yaml`

**Files:**

- Create: `blueprints/royco/jt-stcusd/deposit-from-cusd.yaml`

- [ ] **Step 1: Write the blueprint file**

```yaml
protocol: "royco-jt-stcusd"

# Royco Junior Tranche stcUSD - Deposit from cUSD Blueprint
# cUSD (already in caliber) -> stcUSD (ERC4626) -> JT-stcUSD shares.
# Used to re-enter from caliber-held cUSD WITHOUT touching the Cap Vault —
# avoids the burn->mint roundtrip and any Cap fee/whitelist exposure.
# No whitelist guard needed — does not touch the Cap Vault.

constants:
  context_helper_address:
    type: "address"
    value: "0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE"
  cusd_address:
    type: "address"
    value: "0xcCcc62962d17b8914c62D74FfB843d73B2a3cccC"
  stcusd_address:
    type: "address"
    value: "0x88887bE419578051FF9F4eb6C858A951921D8888"
  junior_tranche_address:
    type: "address"
    value: "0xe4060e83ad26618c7ed56a02ce099beba4f73b29"

inputs: {}

actions:
  deposit_from_cusd:
    calls:
      - description: "Get caliber's address"
        target: ${constants.context_helper_address}
        selector: "msgSender()"
        parameters: []
        return:
          name: "caliber_address"
          type: "address"

      - description: "Approve cUSD spending by stcUSD vault"
        target: "${constants.cusd_address}"
        selector: "approve(address,uint256)"
        parameters:
          - type: "address"
            value: "${constants.stcusd_address}"
          - type: "uint256"
            value: "${input_slots.cusd_amount_to_deposit}"

      - description: "Deposit cUSD into stcUSD vault to receive stcUSD shares"
        target: "${constants.stcusd_address}"
        selector: "deposit(uint256,address)"
        parameters:
          - type: "uint256"
            value: "${input_slots.cusd_amount_to_deposit}"
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "stcusd_shares"
          type: "uint256"

      - description: "Approve stcUSD spending by Junior Tranche"
        target: "${constants.stcusd_address}"
        selector: "approve(address,uint256)"
        parameters:
          - type: "address"
            value: "${constants.junior_tranche_address}"
          - type: "uint256"
            value: "${returns.stcusd_shares}"

      - description: "Deposit stcUSD into Junior Tranche to receive JT shares"
        target: "${constants.junior_tranche_address}"
        selector: "deposit(uint256,address)"
        parameters:
          - type: "uint256"
            value: "${returns.stcusd_shares}"
          - type: "address"
            value: "${returns.caliber_address}"

    input_slots:
      cusd_amount_to_deposit:
        type: "uint256"
        description: "Amount of cUSD to deposit (18 decimals). Operator must ensure caliber holds at least this amount of cUSD before calling, otherwise the approve/deposit step reverts with insufficient balance."
```

### Task 5: `jt-stcusd/burn-cusd-to-usdc.yaml`

**Files:**

- Create: `blueprints/royco/jt-stcusd/burn-cusd-to-usdc.yaml`

- [ ] **Step 1: Write the blueprint file**

This file is IDENTICAL to `blueprints/royco/st-stcusd/burn-cusd-to-usdc.yaml` except for the `protocol:` field. Pure Cap Vault burn — no tranche reference.

```yaml
protocol: "royco-jt-stcusd"

# Royco Junior Tranche stcUSD - Burn cUSD -> USDC (standalone)
# Drains caliber-held cUSD into USDC via Cap Vault.burn.
# Whitelist-gated: reverts if caliber is not whitelisted (would otherwise incur burn fees).
# Identical in logic to the ST sibling; duplicated for folder self-containment.

constants:
  context_helper_address:
    type: "address"
    value: "0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE"
  boolean_helper_address:
    type: "address"
    value: "0x00c93e3b09Ca2f544487d4298339765EadCD8353"
  usdc_address:
    type: "address"
    value: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
  cusd_address:
    type: "address"
    value: "0xcCcc62962d17b8914c62D74FfB843d73B2a3cccC"

inputs: {}

actions:
  burn_cusd_to_usdc:
    calls:
      - description: "Get caliber's address"
        target: ${constants.context_helper_address}
        selector: "msgSender()"
        parameters: []
        return:
          name: "caliber_address"
          type: "address"

      - description: "Read whitelist status of caliber on Cap Vault"
        target: "${constants.cusd_address}"
        selector: "whitelisted(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "is_whitelisted"
          type: "bool"

      - description: "Revert if caliber is not whitelisted (would incur burn fees)"
        target: "${constants.boolean_helper_address}"
        selector: "revertIfFalse(bool)"
        parameters:
          - type: "bool"
            value: "${returns.is_whitelisted}"

      - description: "Burn cUSD for USDC via Cap Vault"
        target: "${constants.cusd_address}"
        selector: "burn(address,uint256,uint256,address,uint256)"
        parameters:
          - type: "address"
            value: "${constants.usdc_address}"
          - type: "uint256"
            value: "${input_slots.cusd_amount_to_burn}"
          - type: "uint256"
            value: "${input_slots.min_usdc_out}"
          - type: "address"
            value: "${returns.caliber_address}"
          - type: "uint256"
            value: "${builtins.UINT256_MAX}"

    input_slots:
      cusd_amount_to_burn:
        type: "uint256"
        description: "Amount of cUSD to burn (18 decimals). Operator must ensure caliber holds at least this amount of cUSD before calling, otherwise the burn step reverts with insufficient balance."
      min_usdc_out:
        type: "uint256"
        description: "Minimum USDC to receive from Cap Vault.burn (6 decimals). Whitelisted callers pay no fee but the rate is NOT exactly 1:1 — it tracks the Vault's value-per-cUSD (Lender interest, basket PnL) and moves over time. As of 2026-04 the whitelisted rate is ~0.999999149 USDC per cUSD, but it can drift either way. Operator must quote fresh via cUSD.getBurnAmount(caliber, USDC, cusd_amount_to_burn) immediately before broadcasting and apply a small tolerance (e.g., 1-2 bps)."
```

### Task 6: `jt-stcusd/account.yaml` — the new cUSD-denominated accounting pattern

**Files:**

- Create: `blueprints/royco/jt-stcusd/account.yaml`

- [ ] **Step 1: Write the blueprint file**

```yaml
protocol: "royco-jt-stcusd"

# Royco Junior Tranche stcUSD - Account Blueprint (cUSD-denominated)
# Reports the caliber's JT position in cUSD (18 decimals). NAV path NOT used.
#
# Components:
#   1. JT.convertToAssets(jt_shares) returns AssetClaims = (stAssets, jtAssets, nav)
#      - Both stAssets and jtAssets are in TRANCHE_UNIT = stcUSD (18 dec).
#      - Both fields are populated for JT (the kernel distributes the JT pro-rata claim
#        across both layer accumulators). Verified on-chain 2026-05-08 vs totalSupply.
#   2. total_stcusd = stAssets + jtAssets   (caliber's pro-rata claim in stcUSD)
#   3. cusd_value = stcUSD.convertToAssets(total_stcusd)
#
# Why not nav: avoids 18->6-dec floor truncation, avoids dependence on the kernel's
# USD oracle path, and ties accounting to the same vault rate an actual exit uses.

constants:
  context_helper_address:
    type: "address"
    value: "0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE"
  unsigned_math_helper_address:
    type: "address"
    value: "0x3D623B199E290358416415eA7e05B635E442e3c0"
  bytes32_helper_address:
    type: "address"
    value: "0x74DC739B8F98ad0F76Cd8900695DD8D5083E45D3"
  junior_tranche_address:
    type: "address"
    value: "0xe4060e83ad26618c7ed56a02ce099beba4f73b29"
  kernel_address:
    type: "address"
    value: "0x9911F227E9428964D8A35B852513919C8DF92038"
  stcusd_address:
    type: "address"
    value: "0x88887bE419578051FF9F4eb6C858A951921D8888"

inputs: {}

actions:
  account:
    calls:
      - description: "Get caliber's address"
        target: ${constants.context_helper_address}
        selector: "msgSender()"
        parameters: []
        return:
          name: "caliber_address"
          type: "address"

      - description: "Sync tranche accounting on the Royco kernel"
        target: "${constants.kernel_address}"
        selector: "syncTrancheAccounting()"
        parameters: []

      - description: "Get Junior Tranche share balance"
        target: "${constants.junior_tranche_address}"
        selector: "balanceOf(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "jt_shares"
          type: "uint256"

      - description: "Convert JT shares to asset claims (stAssets, jtAssets, nav) scaled to caliber pro-rata"
        target: "${constants.junior_tranche_address}"
        selector: "convertToAssets(uint256)"
        parameters:
          - type: "uint256"
            value: "${returns.jt_shares}"
        return:
          name: "asset_claims"
          type: "(uint256,uint256,uint256)"

      - description: "Extract stAssets (TRANCHE_UNIT = stcUSD, 18 dec) from claims tuple"
        target: "${constants.bytes32_helper_address}"
        selector: "getTupleWord(bytes,uint256)"
        parameters:
          - type: "(uint256,uint256,uint256)"
            value: "${returns.asset_claims}"
          - type: "uint256"
            value: "0"
        return:
          name: "st_assets"
          type: "uint256"

      - description: "Extract jtAssets (TRANCHE_UNIT = stcUSD, 18 dec) from claims tuple"
        target: "${constants.bytes32_helper_address}"
        selector: "getTupleWord(bytes,uint256)"
        parameters:
          - type: "(uint256,uint256,uint256)"
            value: "${returns.asset_claims}"
          - type: "uint256"
            value: "1"
        return:
          name: "jt_assets"
          type: "uint256"

      - description: "Sum total_stcusd = stAssets + jtAssets"
        target: "${constants.unsigned_math_helper_address}"
        selector: "add(uint256,uint256)"
        parameters:
          - type: "uint256"
            value: "${returns.st_assets}"
          - type: "uint256"
            value: "${returns.jt_assets}"
        return:
          name: "total_stcusd"
          type: "uint256"

      - description: "Convert total stcUSD to cUSD via stcUSD.convertToAssets (ERC4626)"
        target: "${constants.stcusd_address}"
        selector: "convertToAssets(uint256)"
        parameters:
          - type: "uint256"
            value: "${returns.total_stcusd}"
        return:
          name: "cusd_value"
          type: "uint256"

    reserved_slots:
      - type: "uint256"
        value: "${returns.cusd_value}"
      - type: "uint256"
        value: "${builtins.UINT256_MAX}"
```

### Task 7: Commit Phase 1

- [ ] **Step 1: Stage and commit the jt-stcusd folder**

```bash
git add blueprints/royco/jt-stcusd/
git status   # should show 6 new files in blueprints/royco/jt-stcusd/
git commit -m "$(cat <<'EOF'
feat: blueprints for Royco junior tranche stcUSD

Adds the jt-stcusd folder mirroring st-stcusd, with a new cUSD-denominated
account.yaml that sums AssetClaims.stAssets + jtAssets in TRANCHE_UNIT and
hops to cUSD via stcUSD.convertToAssets — skipping the USD-WAD nav path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: clean commit, 6 new files.

---

## Phase 2: `jt-syrupusdc/` blueprint folder

Three blueprints. The accounting blueprint additionally reads the Maple `WithdrawalManager.userEscrowedShares(caliber)` to include pending withdrawals — note the known double-counting risk in the spec.

### Task 8: `jt-syrupusdc/deposit.yaml`

**Files:**

- Create: `blueprints/royco/jt-syrupusdc/deposit.yaml`

- [ ] **Step 1: Write the blueprint file**

```yaml
protocol: "royco-jt-syrupusdc"

# Royco Junior Tranche syrupUSDC Deposit Blueprint
# Multi-step deposit: USDC -> syrupUSDC (Maple ERC4626) -> Junior Tranche shares
# NOTE: syrupUSDC has PERMISSIONED deposits -- caliber must be whitelisted by Maple poolPermissionManager.
# Mirrors blueprints/royco/st-syrupusdc/deposit.yaml; only the tranche address differs.

constants:
  context_helper_address:
    type: "address"
    value: "0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE"
  usdc_address:
    type: "address"
    value: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
  syrupusdc_address:
    type: "address"
    value: "0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b"
  junior_tranche_address:
    type: "address"
    value: "0x5f340b400f892bbfded2e5c316369dcbf05c282a"

inputs: {}

actions:
  deposit:
    calls:
      - description: "Get caliber's address"
        target: ${constants.context_helper_address}
        selector: "msgSender()"
        parameters: []
        return:
          name: "caliber_address"
          type: "address"

      - description: "Approve USDC spending by syrupUSDC vault"
        target: "${constants.usdc_address}"
        selector: "approve(address,uint256)"
        parameters:
          - type: "address"
            value: "${constants.syrupusdc_address}"
          - type: "uint256"
            value: "${input_slots.usdc_amount_to_deposit}"

      - description: "Deposit USDC into syrupUSDC vault to receive syrupUSDC shares"
        target: "${constants.syrupusdc_address}"
        selector: "deposit(uint256,address)"
        parameters:
          - type: "uint256"
            value: "${input_slots.usdc_amount_to_deposit}"
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "syrupusdc_shares"
          type: "uint256"

      - description: "Approve syrupUSDC spending by Junior Tranche"
        target: "${constants.syrupusdc_address}"
        selector: "approve(address,uint256)"
        parameters:
          - type: "address"
            value: "${constants.junior_tranche_address}"
          - type: "uint256"
            value: "${returns.syrupusdc_shares}"

      - description: "Deposit syrupUSDC into Junior Tranche to receive JT shares"
        target: "${constants.junior_tranche_address}"
        selector: "deposit(uint256,address)"
        parameters:
          - type: "uint256"
            value: "${returns.syrupusdc_shares}"
          - type: "address"
            value: "${returns.caliber_address}"

    input_slots:
      usdc_amount_to_deposit:
        type: "uint256"
        description: "Amount of USDC to deposit (6 decimals)"
```

### Task 9: `jt-syrupusdc/withdraw.yaml`

**Files:**

- Create: `blueprints/royco/jt-syrupusdc/withdraw.yaml`

- [ ] **Step 1: Write the blueprint file**

```yaml
protocol: "royco-jt-syrupusdc"

# Royco Junior Tranche syrupUSDC Withdraw Blueprint
# Two-step manual withdrawal via Maple WithdrawalManager:
#   1. request_redeem - Redeem JT shares -> syrupUSDC -> requestRedeem (Maple queue).
#   2. USDC is airdropped later (need to run accounting to clear pendings).
# Mirrors blueprints/royco/st-syrupusdc/withdraw.yaml; only the tranche address differs.

constants:
  context_helper_address:
    type: "address"
    value: "0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE"
  unsigned_math_helper_address:
    type: "address"
    value: "0x3D623B199E290358416415eA7e05B635E442e3c0"
  syrupusdc_address:
    type: "address"
    value: "0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b"
  junior_tranche_address:
    type: "address"
    value: "0x5f340b400f892bbfded2e5c316369dcbf05c282a"
  withdrawal_manager_address:
    type: "address"
    value: "0x1bc47a0Dd0FdaB96E9eF982fdf1F34DC6207cfE3"

inputs: {}

actions:
  request_redeem:
    calls:
      - description: "Get caliber's address"
        target: ${constants.context_helper_address}
        selector: "msgSender()"
        parameters: []
        return:
          name: "caliber_address"
          type: "address"

      - description: "Get Junior Tranche share balance"
        target: "${constants.junior_tranche_address}"
        selector: "balanceOf(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "jt_shares"
          type: "uint256"

      - description: "Calculate shares to redeem based on basis points"
        target: "${constants.unsigned_math_helper_address}"
        selector: "mulDiv(uint256,uint256,uint256)"
        parameters:
          - type: "uint256"
            value: "${returns.jt_shares}"
          - type: "uint256"
            value: "${input_slots.bps_to_redeem}"
          - type: "uint256"
            value: "10000"
        return:
          name: "shares_to_redeem"
          type: "uint256"

      - description: "Get syrupUSDC balance before JT redeem"
        target: "${constants.syrupusdc_address}"
        selector: "balanceOf(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "syrupusdc_before"
          type: "uint256"

      - description: "Redeem Junior Tranche shares to receive syrupUSDC"
        target: "${constants.junior_tranche_address}"
        selector: "redeem(uint256,address,address)"
        parameters:
          - type: "uint256"
            value: "${returns.shares_to_redeem}"
          - type: "address"
            value: "${returns.caliber_address}"
          - type: "address"
            value: "${returns.caliber_address}"

      - description: "Get syrupUSDC balance after JT redeem"
        target: "${constants.syrupusdc_address}"
        selector: "balanceOf(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "syrupusdc_after"
          type: "uint256"

      - description: "Calculate syrupUSDC received from JT redeem (after - before)"
        target: "${constants.unsigned_math_helper_address}"
        selector: "sub(uint256,uint256)" # sub(a, b) = a - b; pass (after, before) → after - before
        parameters:
          - type: "uint256"
            value: "${returns.syrupusdc_after}"
          - type: "uint256"
            value: "${returns.syrupusdc_before}"
        return:
          name: "syrupusdc_delta"
          type: "uint256"

      - description: "Request syrupUSDC redemption via Maple withdrawal queue"
        target: "${constants.syrupusdc_address}"
        selector: "requestRedeem(uint256,address)"
        parameters:
          - type: "uint256"
            value: "${returns.syrupusdc_delta}"
          - type: "address"
            value: "${returns.caliber_address}"

    input_slots:
      bps_to_redeem:
        type: "uint256"
        description: "Basis points of JT shares to redeem (10000 = 100%)"
```

### Task 10: `jt-syrupusdc/account.yaml`

**Files:**

- Create: `blueprints/royco/jt-syrupusdc/account.yaml`

- [ ] **Step 1: Write the blueprint file**

```yaml
protocol: "royco-jt-syrupusdc"

# Royco Junior Tranche syrupUSDC Account Blueprint (USDC-denominated)
# Sums caliber's exposure in syrupUSDC space, then converts ONCE to USDC via
# syrupUSDC.convertToExitAssets. Mirrors blueprints/royco/st-syrupusdc/account.yaml;
# only the tranche address differs.
#
# WARNING (double-counting): Maple_WithdrawalManager.userEscrowedShares is keyed on
# the caliber address, not on which tranche fed the queue. If the same caliber has
# pending withdrawals from BOTH the ST and JT positions simultaneously, both
# account.yaml files will each count the full escrow — double-counting the pending
# USDC. Operating constraint: keep pending withdrawals on at most one tranche per
# caliber. Documented in docs/superpowers/specs/2026-05-08-royco-junior-tranches-design.md.
#
# Components:
#   1. Active JT position: JT.convertToAssets(jt_shares) -> (stAssets, jtAssets, nav)
#      Both stAssets and jtAssets are in TRANCHE_UNIT = syrupUSDC (6 dec) and both are
#      populated for JT (kernel distributes pro-rata claim across both accumulators).
#   2. Pending Maple withdrawal: WithdrawalManager.userEscrowedShares(caliber)  (syrupUSDC, 6 dec)
#   3. total_syrup = stAssets + jtAssets + escrowed_syrup
#   4. usdc_value = syrupUSDC.convertToExitAssets(total_syrup)

constants:
  context_helper_address:
    type: "address"
    value: "0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE"
  unsigned_math_helper_address:
    type: "address"
    value: "0x3D623B199E290358416415eA7e05B635E442e3c0"
  bytes32_helper_address:
    type: "address"
    value: "0x74DC739B8F98ad0F76Cd8900695DD8D5083E45D3"
  junior_tranche_address:
    type: "address"
    value: "0x5f340b400f892bbfded2e5c316369dcbf05c282a"
  kernel_address:
    type: "address"
    value: "0xde1Ce2cF64808e50d000F93058784270E412B3A4"
  syrupusdc_address:
    type: "address"
    value: "0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b"
  withdrawal_manager_address:
    type: "address"
    value: "0x1bc47a0Dd0FdaB96E9eF982fdf1F34DC6207cfE3"

inputs: {}

actions:
  account:
    calls:
      - description: "Get caliber's address"
        target: ${constants.context_helper_address}
        selector: "msgSender()"
        parameters: []
        return:
          name: "caliber_address"
          type: "address"

      - description: "Sync tranche accounting on the market kernel"
        target: "${constants.kernel_address}"
        selector: "syncTrancheAccounting()"
        parameters: []

      - description: "Get Junior Tranche share balance"
        target: "${constants.junior_tranche_address}"
        selector: "balanceOf(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "jt_shares"
          type: "uint256"

      - description: "Convert JT shares to asset claims (stAssets, jtAssets, nav) scaled to caliber pro-rata"
        target: "${constants.junior_tranche_address}"
        selector: "convertToAssets(uint256)"
        parameters:
          - type: "uint256"
            value: "${returns.jt_shares}"
        return:
          name: "asset_claims"
          type: "(uint256,uint256,uint256)"

      - description: "Extract stAssets (TRANCHE_UNIT = syrupUSDC, 6 dec) from claims tuple"
        target: "${constants.bytes32_helper_address}"
        selector: "getTupleWord(bytes,uint256)"
        parameters:
          - type: "(uint256,uint256,uint256)"
            value: "${returns.asset_claims}"
          - type: "uint256"
            value: "0"
        return:
          name: "active_st_assets"
          type: "uint256"

      - description: "Extract jtAssets (TRANCHE_UNIT = syrupUSDC, 6 dec) from claims tuple"
        target: "${constants.bytes32_helper_address}"
        selector: "getTupleWord(bytes,uint256)"
        parameters:
          - type: "(uint256,uint256,uint256)"
            value: "${returns.asset_claims}"
          - type: "uint256"
            value: "1"
        return:
          name: "active_jt_assets"
          type: "uint256"

      - description: "Get escrowed syrupUSDC shares from Maple WithdrawalManager"
        target: "${constants.withdrawal_manager_address}"
        selector: "userEscrowedShares(address)"
        parameters:
          - type: "address"
            value: "${returns.caliber_address}"
        return:
          name: "escrowed_syrup"
          type: "uint256"

      - description: "Sum active = stAssets + jtAssets"
        target: "${constants.unsigned_math_helper_address}"
        selector: "add(uint256,uint256)"
        parameters:
          - type: "uint256"
            value: "${returns.active_st_assets}"
          - type: "uint256"
            value: "${returns.active_jt_assets}"
        return:
          name: "total_tranche_assets"
          type: "uint256"

      - description: "Sum total_syrup = active + escrowed"
        target: "${constants.unsigned_math_helper_address}"
        selector: "add(uint256,uint256)"
        parameters:
          - type: "uint256"
            value: "${returns.total_tranche_assets}"
          - type: "uint256"
            value: "${returns.escrowed_syrup}"
        return:
          name: "total_syrup"
          type: "uint256"

      - description: "Convert total syrupUSDC to USDC via convertToExitAssets"
        target: "${constants.syrupusdc_address}"
        selector: "convertToExitAssets(uint256)"
        parameters:
          - type: "uint256"
            value: "${returns.total_syrup}"
        return:
          name: "total_usdc"
          type: "uint256"

    reserved_slots:
      - type: "uint256"
        value: "${returns.total_usdc}"
      - type: "uint256"
        value: "${builtins.UINT256_MAX}"
```

### Task 11: Commit Phase 2

- [ ] **Step 1: Stage and commit the jt-syrupusdc folder**

```bash
git add blueprints/royco/jt-syrupusdc/
git status   # should show 3 new files
git commit -m "$(cat <<'EOF'
feat: blueprints for Royco junior tranche syrupUSDC

Adds the jt-syrupusdc folder mirroring st-syrupusdc, with a USDC-denominated
account.yaml that sums AssetClaims.stAssets + jtAssets + escrowed_syrup in
TRANCHE_UNIT and hops to USDC via syrupUSDC.convertToExitAssets. Same single-rate
pattern as the ST sibling; does not use the USD-WAD nav field.

Includes a leading comment flagging the WithdrawalManager double-counting risk
(escrow is keyed on caliber, not tranche).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: clean commit, 3 new files.

---

## Phase 3: Instruction files

### Task 12: `instructions/royco-jt-stcusd.yaml`

**Files:**

- Create: `instructions/royco-jt-stcusd.yaml`

- [ ] **Step 1: Write the instruction file**

```yaml
# Royco Junior Tranche stcUSD (Cap Protocol)
# Atomic chain: USDC <-> cUSD (Cap Vault) <-> stcUSD (ERC4626) <-> JT-stcUSD
#
# Six instructions covering all reasonable transitions:
#   1 ACCOUNTING: cUSD-denominated (no nav), via JT.convertToAssets sum + stcUSD.convertToAssets
#   5 MANAGEMENT covering this state graph at the caliber level:
#         USDC ──deposit──► JT
#         USDC ◄─withdraw── JT
#         cUSD ◄─withdraw-to-cusd── JT     (escape hatch: skip Cap Vault on exit)
#         cUSD ──burn-cusd-to-usdc──► USDC (drain leftover cUSD when re-whitelisted)
#         cUSD ──deposit-from-cusd──► JT   (re-enter without the burn->mint roundtrip)
#
# Whitelist guards on Cap Vault touches (BooleanHelper.revertIfFalse):
#   - DEPOSIT (USDC->cUSD mint): GUARDED — never enter unless whitelisted
#   - BURN-CUSD (cUSD->USDC burn): GUARDED — only call when re-whitelisted (no fee path)
#   - WITHDRAW (full unwind): NOT GUARDED — escape hatch, may pay Cap fee if un-whitelisted
#   - WITHDRAW-TO-CUSD / DEPOSIT-FROM-CUSD: no Cap touch, no guard needed

# DEPOSIT: USDC -> cUSD -> stcUSD -> JT shares (atomic, whitelist-gated)
- is_debt: false
  instruction_type: "MANAGEMENT"
  affected_tokens:
    - "${token_list.mainnet.USDC}"
  instruction:
    label: "ROY-JT-stcUSD"
    path: "../../../blueprints/royco/jt-stcusd/deposit.yaml:deposit"
    inputs: {}

# cUSD-DENOMINATED ACCOUNTING: Sync tranche + sum stAssets+jtAssets in stcUSD, then convertToAssets to cUSD
- is_debt: false
  instruction_type: "ACCOUNTING"
  affected_tokens:
    - "${token_list.mainnet.cUSD}"
  instruction:
    label: "ROY-JT-stcUSD"
    path: "../../../blueprints/royco/jt-stcusd/account.yaml:account"
    inputs: {}

# WITHDRAW (full): redeem JT -> stcUSD -> cUSD -> USDC (atomic, escape hatch)
- is_debt: false
  instruction_type: "MANAGEMENT"
  affected_tokens:
    - "${token_list.mainnet.USDC}"
  instruction:
    label: "ROY-JT-stcUSD"
    path: "../../../blueprints/royco/jt-stcusd/withdraw.yaml:withdraw"
    inputs: {}

# WITHDRAW-TO-CUSD (partial): redeem JT -> stcUSD -> cUSD; leaves cUSD in caliber
- is_debt: false
  instruction_type: "MANAGEMENT"
  affected_tokens:
    - "${token_list.mainnet.cUSD}"
  instruction:
    label: "ROY-JT-stcUSD"
    path: "../../../blueprints/royco/jt-stcusd/withdraw-to-cusd.yaml:withdraw_to_cusd"
    inputs: {}

# BURN-CUSD: drain caliber-held cUSD into USDC via Cap Vault.burn (whitelist-gated)
- is_debt: false
  instruction_type: "MANAGEMENT"
  affected_tokens:
    - "${token_list.mainnet.USDC}"
    - "${token_list.mainnet.cUSD}"
  instruction:
    label: "ROY-JT-stcUSD"
    path: "../../../blueprints/royco/jt-stcusd/burn-cusd-to-usdc.yaml:burn_cusd_to_usdc"
    inputs: {}

# DEPOSIT-FROM-CUSD: re-enter JT from caliber-held cUSD (skips Cap Vault entirely)
- is_debt: false
  instruction_type: "MANAGEMENT"
  affected_tokens:
    - "${token_list.mainnet.cUSD}"
  instruction:
    label: "ROY-JT-stcUSD-DepositFromCUSD"
    path: "../../../blueprints/royco/jt-stcusd/deposit-from-cusd.yaml:deposit_from_cusd"
    inputs: {}
```

Notes on labels (per `MEMORY.md` rule "Labels must be unique per (protocol, type, label) trouple"):

- All 5 MANAGEMENT instructions share the label `ROY-JT-stcUSD` EXCEPT the deposit-from-cusd entry, which uses `ROY-JT-stcUSD-DepositFromCUSD` — matching the ST file's disambiguation for the same instruction.
- The ACCOUNTING instruction uses `ROY-JT-stcUSD` (different `instruction_type` from any MGMT entry, so the trouple is unique).

Verify the file is identical in structure to `instructions/royco-st-stcusd.yaml` aside from `jt-`/`JT` substitutions:

```bash
diff <(sed 's/jt-stcusd\|JT-stcUSD\|JT/__/g' instructions/royco-jt-stcusd.yaml) \
     <(sed 's/st-stcusd\|ST-stcUSD\|ST/__/g' instructions/royco-st-stcusd.yaml)
```

The diff should be small — limited to:

- Different ACCOUNTING `affected_tokens` (cUSD for JT vs USDC for ST)
- Comment language ("cUSD-denominated" vs "NAV-based")

### Task 13: `instructions/royco-jt-syrupusdc.yaml`

**Files:**

- Create: `instructions/royco-jt-syrupusdc.yaml`

- [ ] **Step 1: Write the instruction file**

```yaml
# Royco Junior Tranche syrupUSDC
# Multi-step deposit: USDC -> syrupUSDC (Maple ERC4626) -> Junior Tranche shares
# Queue-based withdraw: redeem JT -> syrupUSDC -> requestRedeem (manual withdrawal). USDC airdropped later.
# Accounting: USDC-denominated (no nav) + pending syrupUSDC from Maple WithdrawalManager.
#
# Prerequisites:
#   - Caliber must be whitelisted on Maple PoolPermissionManager for deposits
#   - Caliber must have AccessManager roles on the JT contract (separate from ST roles)
#
# WARNING: WithdrawalManager.userEscrowedShares is keyed on caliber, not tranche.
# Do not hold simultaneous pending withdrawals from both ST and JT on the same caliber,
# or accounting will double-count the pending USDC across the two account.yaml runs.

# DEPOSIT: USDC -> syrupUSDC -> Junior Tranche shares
- is_debt: false
  instruction_type: "MANAGEMENT"
  affected_tokens:
    - "${token_list.mainnet.USDC}"
  instruction:
    label: "ROY-JT-syrupUSDC"
    path: "../../../blueprints/royco/jt-syrupusdc/deposit.yaml:deposit"
    inputs: {}

# USDC-DENOMINATED ACCOUNTING: Active JT in syrupUSDC + pending escrow, then convertToExitAssets to USDC
- is_debt: false
  instruction_type: "ACCOUNTING"
  affected_tokens:
    - "${token_list.mainnet.USDC}"
  instruction:
    label: "ROY-JT-syrupUSDC"
    path: "../../../blueprints/royco/jt-syrupusdc/account.yaml:account"
    inputs: {}

# WITHDRAW: Redeem JT -> syrupUSDC -> requestRedeem (Maple queue)
- is_debt: false
  instruction_type: "MANAGEMENT"
  affected_tokens: []
  instruction:
    label: "ROY-JT-syrupUSDC"
    path: "../../../blueprints/royco/jt-syrupusdc/withdraw.yaml:request_redeem"
    inputs: {}
```

### Task 14: User compile-check

- [ ] **Step 1: Ask the user to run `/compile` on both instruction files**

Per the standing project rule, the user runs the transpiler. Print this message and wait:

> Ready for compile-check. Please run:
>
> ```
> /compile instructions/royco-jt-stcusd.yaml
> /compile instructions/royco-jt-syrupusdc.yaml
> ```
>
> Report any compile errors back. Common failure modes: unknown selector type (a tuple mismatch), missing token in token list (run `/scan-tokens` if so), or a broken `!include`/`path:` reference.

- [ ] **Step 2: If compile errors surface, fix in-place and re-request compile-check**

Most likely issues to fix:

- Path typos in `instructions/*.yaml`
- A protocol field mismatch between an instruction's blueprint path and the blueprint file's `protocol:` line
- Tuple selector shape `(uint256,uint256,uint256)` parameters — the existing ST blueprints use the exact same form, so this should succeed.

- [ ] **Step 3: Commit the instruction files once compile succeeds**

```bash
git add instructions/royco-jt-stcusd.yaml instructions/royco-jt-syrupusdc.yaml
git status
git commit -m "$(cat <<'EOF'
feat: instruction files for Royco junior tranches (stcUSD, syrupUSDC)

Wires up the jt-stcusd (6 entries) and jt-syrupusdc (3 entries) instruction
libraries against the new blueprints. Mirrors the senior-tranche files 1:1
in structure; ACCOUNTING entries report in cUSD / USDC respectively (no nav).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: clean commit, 2 new files.

---

## Phase 4: Documentation cleanup

### Task 15: Fix `nav-investigation.md`

**Files:**

- Modify: `scripts-factory/royco-st-stcusd/nav-investigation.md:64-76`, `:243-244`, `:263`

- [ ] **Step 1: Read the current text at the lines to be fixed**

Run: `cat scripts-factory/royco-st-stcusd/nav-investigation.md | sed -n '60,80p;240,265p'`

This will show the offending section. The doc claims:

- "jtAssets: Amount of cUSD held by junior tranche (first-loss capital) (units of cUSD @ 18 decimals)"

The correct interpretation per `royco/dawn-msig-orchestration/src/libraries/Types.sol`:

- Both `stAssets` and `jtAssets` are typed `TRANCHE_UNIT`, which for the stcUSD market is **stcUSD** (not cUSD). The deposit asset of the tranche, not the underlying.

- [ ] **Step 2: Apply edits**

Edit `scripts-factory/royco-st-stcusd/nav-investigation.md`:

Replace at the "Denomination & Decimals" subsection:

```
- **TRANCHE_UNIT**: Denominated in the **tranche asset** (stcUSD) with **18 decimals** (standard ERC20 WAD)
  - For ST-stcUSD: measured in stcUSD (Cap staked vault shares)
```

Replace with:

```
- **TRANCHE_UNIT**: Denominated in the **tranche's deposit asset** (the result of `tranche.asset()`).
  - For the stcUSD market (both ST and JT): TRANCHE_UNIT == stcUSD @ 18 decimals.
  - Both `stAssets` AND `jtAssets` in the AssetClaims tuple are in this unit. They do NOT cross
    denominations — `jtAssets` is in stcUSD, not cUSD. Source: `royco/dawn-msig-orchestration/src/libraries/Types.sol:15-19`.
```

Replace at the "Interpretation" subsection:

```
- `stAssets`: Amount of stcUSD held by the tranche (units of stcUSD @ 18 decimals)
- `jtAssets`: Amount of cUSD held by junior tranche (first-loss capital) (units of cUSD @ 18 decimals)
- `nav`: USD value of the tranche's net asset position (USD WAD @ 18 decimals)
```

Replace with:

```
- `stAssets`: Caliber's pro-rata claim on the senior layer's accumulator, in stcUSD (18 dec).
- `jtAssets`: Caliber's pro-rata claim on the junior layer's accumulator, in stcUSD (18 dec).
- `nav`: Caliber's pro-rata USD value of the position (USD WAD @ 18 decimals).

Both `stAssets` and `jtAssets` are typically non-zero on either tranche side; the kernel
distributes the caller's claim across both accumulators. Summing the two gives the caliber's
total stcUSD-denominated entitlement — this is the basis of the alternative cUSD-denominated
accounting in `blueprints/royco/jt-stcusd/account.yaml`.
```

Replace in the Summary table:

| stAssets Unit | stcUSD (Cap vault shares), 18 decimals |
| jtAssets Unit | cUSD (Cap vault), 18 decimals |

with:

| stAssets Unit | stcUSD (TRANCHE_UNIT for the stcUSD market), 18 decimals |
| jtAssets Unit | stcUSD (TRANCHE_UNIT for the stcUSD market), 18 decimals — NOT cUSD |

Replace in the Makina Blueprint Recommendation comment:

```
#   - jtAssets: cUSD in junior tranche (first-loss capital)
```

with:

```
#   - jtAssets: stcUSD claim on the junior layer (TRANCHE_UNIT, same as stAssets)
```

- [ ] **Step 3: Commit**

```bash
git add scripts-factory/royco-st-stcusd/nav-investigation.md
git commit -m "$(cat <<'EOF'
docs: correct AssetClaims interpretation in royco nav-investigation

The earlier note claimed jtAssets is denominated in cUSD; the on-chain Types.sol
declares both stAssets and jtAssets as TRANCHE_UNIT (stcUSD for this market).
Empirically verified during the JT integration.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 5: End-to-end validation

Validation is gated on wiring the new instructions into a machine. The instruction library files are protocol-agnostic; they're consumed by a machine's `caliber.yaml`. There are two options for this validation pass, depending on the operator's intent. Pick one with the user before proceeding.

### Task 16: Decide validation target

- [ ] **Step 1: Confirm with the user whether to validate via:**
  - **Option A (recommended):** Wire the JT instructions into the existing `intMkSrRoyUSDC` machine alongside its ST counterparts. That machine already has the cUSD and USDC oracles registered and a known-good test harness. Add two new entries to `machines/intMkSrRoyUSDC/mainnet/caliber.yaml` mirroring the ST entries:
    - Position id (deterministic — derive from sha256 of a namespaced string, mirroring how the existing JT V1 ids are assigned in the codebase). Compute: `python3 -c "import hashlib; print(int.from_bytes(hashlib.sha256(b'makina.mainnet.intMkSrRoyUSDC.royco.jt-stcusd'.encode()).digest()[:16], 'big'))"`. Repeat for syrupUSDC.
    - `group_id`: `"0"` (same as the other Royco V2 entries — first-loss positions can share the same group for accounting bucketing)
    - `position_tokens`: list the tranche-relevant tokens (stcUSD + JT-stcUSD; or syrupUSDC + JT-syrupUSDC)
  - **Option B:** Defer wiring; let the operator wire into DUSD or another machine separately. The blueprint+instruction layer is complete and reviewable on its own. Skip Tasks 17-19.

### Task 17: (Option A) Wire into `intMkSrRoyUSDC`

**Files:**

- Modify: `machines/intMkSrRoyUSDC/mainnet/caliber.yaml`

- [ ] **Step 1: Compute deterministic position ids**

Run:

```bash
python3 -c "
import hashlib
for s in ['makina.mainnet.intMkSrRoyUSDC.royco.jt-stcusd', 'makina.mainnet.intMkSrRoyUSDC.royco.jt-syrupusdc']:
    h = hashlib.sha256(s.encode()).digest()[:16]
    print(f'{s} -> {int.from_bytes(h, \"big\")} (0x{h.hex()})')
"
```

Record the two integers — they go into the `id:` fields. Verify the convention matches the existing entries (look at the comments above the existing `id:` fields in the caliber.yaml — they document how the id was derived, and we should follow the same naming convention).

If the existing comment convention says e.g., `# id = uint128(sha256("makina.mainnet.intMkSrRoyUSDC.royco-stcusd"))`, derive the JT id with the matching string (e.g., `"makina.mainnet.intMkSrRoyUSDC.royco-jt-stcusd"`). Match the existing format exactly.

- [ ] **Step 2: Add two new position entries**

After the existing Royco V2 block (`# ── Royco Positions V2 (group_id: 0) ──`), append:

```yaml
- id: "<computed_uint128_for_stcusd_jt>"
  group_id: "0"
  description: "Royco Junior Tranche stcUSD (Cap Protocol)"
  instructions: !include "../../../instructions/royco-jt-stcusd.yaml"
  position_tokens:
    - "0x88887bE419578051FF9F4eb6C858A951921D8888" # stcUSD
    - "0xe4060e83ad26618c7ed56a02ce099beba4f73b29" # JT-stcUSD
- id: "<computed_uint128_for_syrupusdc_jt>"
  group_id: "0"
  description: "Royco Junior Tranche syrupUSDC"
  instructions: !include "../../../instructions/royco-jt-syrupusdc.yaml"
  position_tokens:
    - "0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b" # syrupUSDC
    - "0x5f340b400f892bbfded2e5c316369dcbf05c282a" # JT-syrupUSDC
```

Replace `<computed_...>` with the integers from Step 1.

- [ ] **Step 3: Ask the user to run `/compile` on the rootfile target**

Print:

> Please run `/compile` against the rootfile that includes these instructions (likely a new `machines/intMkSrRoyUSDC/mainnet/rootfiles/20260511-royco-jt.toml` or similar — check current rootfile convention). Report any errors.

- [ ] **Step 4: Once compile succeeds, commit**

```bash
git add machines/intMkSrRoyUSDC/mainnet/caliber.yaml
# stage rootfile too if one was added in Step 3
git status
git commit -m "$(cat <<'EOF'
feat: wire Royco JT instructions into intMkSrRoyUSDC

Adds JT-stcUSD and JT-syrupUSDC positions alongside the existing ST entries.
Position ids derived deterministically from sha256-of-namespace strings.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 18: (Option A) End-to-end test via blueprint-tester

- [ ] **Step 1: Run the blueprint-tester subagent against the two new instruction files**

Run the blueprint-tester end-to-end on a Tenderly fork. Per `CLAUDE.md`, this is the project's standard E2E gate. The tester needs to verify:

1. **JT-stcUSD deposit → account → withdraw cycle:**
   - Fund caliber with USDC
   - Whitelist caliber on Cap Vault (impersonation if needed)
   - Grant AccessManager role on JT-stcUSD (impersonation if needed; role ID TBD — ask Royco team or read from on-chain)
   - Call ROY-JT-stcUSD deposit → JT shares appear on caliber
   - Call ROY-JT-stcUSD account → reserved_slots[0] should be a non-trivial cUSD amount (18 dec)
   - Independently compute expected: `JT.convertToAssets(jt_shares)` → sum stAssets+jtAssets → stcUSD.convertToAssets(sum) → cUSD. Should match within rounding.
   - Call ROY-JT-stcUSD withdraw (bps=10000) → caliber back to USDC

2. **JT-stcUSD escape-hatch loop:** withdraw-to-cusd → burn-cusd-to-usdc, and withdraw-to-cusd → deposit-from-cusd. Confirm cUSD enters caliber on the partial unwind and leaves correctly on either branch.

3. **JT-syrupUSDC deposit → account → withdraw cycle:**
   - Fund caliber with USDC
   - Whitelist on Maple PoolPermissionManager (impersonation)
   - Grant AccessManager role on JT-syrupUSDC
   - Call ROY-JT-syrupUSDC deposit
   - Call ROY-JT-syrupUSDC account → reserved_slots[0] should be a USDC amount (6 dec) close to original USDC in
   - Call ROY-JT-syrupUSDC withdraw (bps=10000) → JT shares burn, syrupUSDC enters Maple queue
   - Call ROY-JT-syrupUSDC account again → reserved_slots[0] should now reflect the queued amount (via WithdrawalManager.userEscrowedShares)

Use the same dispatch pattern as other end-to-end blueprint tests in this codebase. If the tester reports any revert, drop into the systematic-debugging skill before patching.

- [ ] **Step 2: If E2E surfaces issues, fix in-place, re-run, commit fixes**

Each fix should land as its own follow-up commit. Do not amend the earlier feature commits.

### Task 19: (Option A) Update MEMORY.md with the operating constraint

**Files:**

- Modify: `MEMORY.md` (the user's auto-memory index)

The double-counting risk warrants a memory note so future conversations have it. The memory framework requires a separate markdown file plus an index pointer.

- [ ] **Step 1: Write the memory file**

Create `/Users/theodorecurtil/.claude/projects/-Users-theodorecurtil-Desktop-dialectic-makina-config/memory/feedback_royco_jt_escrow.md` with:

```markdown
---
name: Royco JT/ST shared withdrawal queue
description: Maple WithdrawalManager.userEscrowedShares is per-caliber, not per-tranche — pending withdrawals can double-count across ST and JT account.yaml runs
type: feedback
---

For the Royco syrupUSDC market, both `blueprints/royco/st-syrupusdc/account.yaml` and `blueprints/royco/jt-syrupusdc/account.yaml` add `Maple_WithdrawalManager.userEscrowedShares(caliber)` to their reported value. That getter is keyed on the caliber address only — it does NOT distinguish which tranche fed the queue. A caliber that simultaneously holds pending withdrawals from BOTH ST and JT on the same syrupUSDC market will see the escrow added twice in total accounting.

**Why:** Surfaced during the Royco JT integration (2026-05-11). Operating constraint baked into both account.yaml files.

**How to apply:** When wiring Royco syrupUSDC positions into a machine, ensure operators only run `requestRedeem` from one of {ST, JT} on the same caliber at any given time. If a use case requires both, factor escrow out into a standalone ACCOUNTING instruction that reports the pending USDC exactly once.
```

- [ ] **Step 2: Add a pointer to `MEMORY.md`**

Append under the "Feedback" section:

```
- [feedback_royco_jt_escrow.md](feedback_royco_jt_escrow.md) — Royco JT/ST share the same Maple WithdrawalManager; don't run pending redeems on both simultaneously
```

- [ ] **Step 3: (No commit) — these files are outside the repo**

The memory directory lives under `~/.claude/projects/.../memory/`. Not git-tracked from this repo. Skip the commit.

---

## Self-review against the spec

After completing the implementation tasks above, verify:

- [ ] All 9 blueprint files exist and compile (Phases 1 and 2).
- [ ] Both instruction files exist and compile (Phase 3).
- [ ] `nav-investigation.md` no longer claims jtAssets is in cUSD (Phase 4).
- [ ] Position-id assignment in machine wiring follows the existing convention (Phase 5 / Task 17).
- [ ] If Option A chosen: blueprint-tester E2E passes on a Tenderly fork.
- [ ] Acceptance criteria from the spec (`docs/superpowers/specs/2026-05-08-royco-junior-tranches-design.md` § Acceptance criteria) are all checked.
- [ ] Labels in instruction files are unique per (protocol, type, label) tuple — verified by reading both new files alongside their ST siblings and the `MEMORY.md` rule.

If any check fails, fix in-place, re-run `/compile`, re-run blueprint-tester, and commit fixes.
