# Uniswap X Filler Makina Lite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add initial config, blueprints, and instruction wrappers for the `uniswap-x-filler` Makina Lite Safe.

**Architecture:** The machine is modeled as a Safe-backed Makina Lite instance rather than a Caliber account. Aave USDC inventory management reuses the existing Aave v3 blueprints, while Uniswap X direct-fill settlement lives in a new `blueprints/uniswap-x` folder with direct and Aave-composed variants.

**Tech Stack:** Makina YAML instruction wrappers, Weiroll-style blueprint calls, Aave v3 Pool, Uniswap X V2 Reactor, Makina Lite Safe/module config.

---

### Task 1: Plan And Slot Documentation

**Files:**

- Create: `docs/superpowers/plans/2026-06-04-uniswap-x-filler-makina-lite.md`
- Create: `blueprints/uniswap-x/README.md`

- [ ] **Step 1: Create this plan**

Add this implementation plan so the review has an explicit map of the files and verification steps.

- [ ] **Step 2: Document Uniswap X slot layouts**

Add `blueprints/uniswap-x/README.md` documenting the param order for:

- `buy_xstock_with_usdc_direct`
- `buy_xstock_with_usdc_from_aave`
- `sell_xstock_for_usdc_direct`

- [ ] **Step 3: Verify documentation references**

Run: `rg -n "buy_xstock_with_usdc|sell_xstock_for_usdc|MakinaLiteModule|0x81Aa9DA3b68ef186E34e96FB6Ae9ad16D7715C72" blueprints/uniswap-x machines/uniswap-x-filler docs/superpowers/plans/2026-06-04-uniswap-x-filler-makina-lite.md`

Expected: the new Uniswap X variants and Safe/module addresses are discoverable.

### Task 2: Uniswap X Blueprint

**Files:**

- Create: `blueprints/uniswap-x/execute.yaml`

- [ ] **Step 1: Add direct xStock to USDC settlement**

Create `buy_xstock_with_usdc_direct`: approve the Reactor for the USDC output amount, then call `execute((bytes,bytes))` with `order` and `signature`.

- [ ] **Step 2: Add Aave-funded xStock to USDC settlement**

Create `buy_xstock_with_usdc_from_aave`: withdraw USDC from Aave to the Safe, approve the Reactor for the USDC output amount, then call `execute((bytes,bytes))`.

- [ ] **Step 3: Add direct USDC to xStock settlement**

Create `sell_xstock_for_usdc_direct`: approve the Reactor for the xStock output amount using the position-level `xstock_token`, then call `execute((bytes,bytes))`.

### Task 3: Machine Setup

**Files:**

- Create: `machines/uniswap-x-filler/config.toml`
- Create: `machines/uniswap-x-filler/mainnet/caliber.yaml`
- Create: `machines/uniswap-x-filler/mainnet/instructions/aave-usdc.yaml`
- Create: `instructions/uniswap-x.yaml`

- [ ] **Step 1: Add machine config**

Use Safe `0x81Aa9DA3b68ef186E34e96FB6Ae9ad16D7715C72` as the machine/caliber address and MakinaLiteModule `0xA032aFD73Fd42deb549698f5Ac93E8b373330B09` as the `swapper` field for the initial setup.

- [ ] **Step 2: Add mainnet caliber file**

Define Safe, module, Aave Pool, USDC, and Reactor addresses in `config`. Add one Aave USDC position and one NVDAx Uniswap X settlement position. Do not add accounting instructions.

- [ ] **Step 3: Add Aave USDC instruction wrappers**

Use existing Aave blueprints:

- `../../../blueprints/aave/deposit.yaml:add_collateral`
- `../../../blueprints/aave/withdraw.yaml:withdraw_collateral`

- [ ] **Step 4: Add Uniswap X instruction wrappers**

Create `instructions/uniswap-x.yaml`, parameterized by `position.label` and `position.xstock_token`, and reference the three Uniswap X actions from `../../../blueprints/uniswap-x/execute.yaml`.

- [ ] **Step 5: Defer rootfile creation until transpiler output is available**

Do not add a placeholder rootfile. New rootfiles must match transpiler output in CI.

### Task 4: Verification

**Files:**

- Read: all files added above

- [ ] **Step 1: Search for required files and constants**

Run: `rg -n "0x81Aa9DA3b68ef186E34e96FB6Ae9ad16D7715C72|0xA032aFD73Fd42deb549698f5Ac93E8b373330B09|0x00000011f84b9aa48e5f8aa8b9897600006289be|execute\\(\\(bytes,bytes\\)\\)" blueprints/uniswap-x machines/uniswap-x-filler`

Expected: Safe, module, Reactor, and execute selector appear in the new files.

- [ ] **Step 2: Run transpiler compile if available**

Run: `transpiler -- --input-file=machines/uniswap-x-filler/mainnet/caliber.yaml --output-file=/private/tmp/uniswap-x-filler-rootfile.toml`

Expected: either a compiled TOML is produced, or the local environment reports that the transpiler binary is not available.

- [ ] **Step 3: Inspect git diff**

Run: `git diff -- blueprints/uniswap-x machines/uniswap-x-filler docs/superpowers/plans/2026-06-04-uniswap-x-filler-makina-lite.md`

Expected: only the planned files are changed.
