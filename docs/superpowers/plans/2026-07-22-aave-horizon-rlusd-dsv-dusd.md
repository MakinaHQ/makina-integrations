# Aave Horizon RLUSD Supply for DSV and DUSD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parameterize shared Aave V3 Pool selection, add Horizon RLUSD supply to DSV and DUSD, and add DMG mainnet Merkl harvest.

**Architecture:** Shared Aave instructions take `position.aave_pool_instance`. Existing generic positions bind the standard Core Pool explicitly; the two new lenders bind Horizon. The existing aToken balance accounting remains unchanged. DMG uses the canonical single-action Merkl wrapper.

**Tech Stack:** Caliber YAML, Weiroll blueprints, Python `unittest`, Makina transpiler, dprint, generated TOML rootfiles.

## Global Constraints

- Ethereum mainnet only; DSV is `machines/intMkSrRoyUSDC`.
- Horizon Pool: `0xAe05Cd22df81871bc7cC2a04BeCfb516bFe332C8`; it is a position variable, not shared config.
- RLUSD: `0x8292Bb45bf1Ee4d140127049757C2E0fF06317eD`; aHorRwaRLUSD: `0xe3190143eB552456F88464662F0C0C4AC67A77Eb`.
- Both Horizon lenders use ID `90412308966732131550279441858106449200`, group `3`, and the `aavev3` supply wrapper.
- Preserve existing `aavev3_core_instance` config keys for machine-local wrappers; migrate only positions that include the two shared Aave wrappers.
- Add Merkl only to `machines/dmg/mainnet`; do not create or modify DMG Base files.
- Generate rootfiles; never hand-edit TOML. Do not change Oracle routes, base tokens, token list, rewards, borrowing, or aToken transfers.

---

## File Structure

| File                                           | Responsibility                                                       |
| ---------------------------------------------- | -------------------------------------------------------------------- |
| `blueprints/aave/borrow.yaml`                  | Takes the Aave Pool as an input rather than a Core-Pool constant.    |
| `instructions/aavev3-{supply,borrow}.yaml`     | Maps the Pool from each position into Aave management calls.         |
| Five mainnet caliber YAML files                | Add explicit Core-Pool variables to existing generic positions.      |
| DUSD and DSV caliber YAML                      | Add the Horizon RLUSD lenders.                                       |
| `machines/dmg/mainnet/instructions/merkl.yaml` | DMG's canonical Merkl claim wrapper.                                 |
| `tests/test_aavev3_position_instance.py`       | Regression coverage for all requirements.                            |
| Three dated rootfiles                          | Transpiled migration roots for the new DUSD, DSV, and DMG positions. |

### Task 1: Parameterize shared Aave V3 Pool selection

**Files:**

- Create: `tests/test_aavev3_position_instance.py`
- Modify: `blueprints/aave/borrow.yaml`
- Modify: `instructions/aavev3-supply.yaml`
- Modify: `instructions/aavev3-borrow.yaml`
- Modify: `machines/dbit/mainnet/caliber.yaml`
- Modify: `machines/dqaeeth/mainnet/caliber.yaml`
- Modify: `machines/dusd/mainnet/caliber.yaml`
- Modify: `machines/intMkSrRoyUSDC/mainnet/caliber.yaml`
- Modify: `machines/tstETH2/mainnet/caliber.yaml`

**Interfaces:**

- Consumes: `position.label`, `position.asset_address`, `position.aave_token`, and `position.debt_token`.
- Produces: Required `position.aave_pool_instance: address` for shared supply and borrow positions.

- [ ] **Step 1: Write the failing regression test**

Create `tests/test_aavev3_position_instance.py`:

```python
"""Regression coverage for per-position Aave V3 Pool instances."""
from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_POOL_BINDING = 'aave_pool_instance: "${config.aavev3_core_instance}"'
CORE_POOL_BINDING_COUNTS = {
    "machines/dbit/mainnet/caliber.yaml": 6,
    "machines/dqaeeth/mainnet/caliber.yaml": 1,
    "machines/dusd/mainnet/caliber.yaml": 5,
    "machines/intMkSrRoyUSDC/mainnet/caliber.yaml": 4,
    "machines/tstETH2/mainnet/caliber.yaml": 1,
}
HORIZON_POSITION_ID = "90412308966732131550279441858106449200"
HORIZON_POOL = "0xAe05Cd22df81871bc7cC2a04BeCfb516bFe332C8"
HORIZON_ATOKEN = "0xe3190143eB552456F88464662F0C0C4AC67A77Eb"


class AaveV3PositionInstanceTests(unittest.TestCase):
    def test_shared_wrappers_take_pool_from_position(self) -> None:
        supply = (REPO_ROOT / "instructions/aavev3-supply.yaml").read_text()
        borrow = (REPO_ROOT / "instructions/aavev3-borrow.yaml").read_text()
        blueprint = (REPO_ROOT / "blueprints/aave/borrow.yaml").read_text()

        for wrapper in (supply, borrow):
            self.assertIn("${position.aave_pool_instance}", wrapper)
            self.assertNotIn("${config.aavev3_core_instance}", wrapper)
        self.assertIn("  aave_pool_instance:\n    type: \"address\"", blueprint)
        self.assertIn("target: ${inputs.aave_pool_instance}", blueprint)
        self.assertNotIn("constants:", blueprint)

    def test_existing_generic_positions_bind_core_explicitly(self) -> None:
        for path, expected_count in CORE_POOL_BINDING_COUNTS.items():
            self.assertEqual((REPO_ROOT / path).read_text().count(CORE_POOL_BINDING), expected_count)

    def test_dusd_and_dsv_define_identical_horizon_rlusd_lenders(self) -> None:
        for path in ("machines/dusd/mainnet/caliber.yaml", "machines/intMkSrRoyUSDC/mainnet/caliber.yaml"):
            caliber = (REPO_ROOT / path).read_text()
            self.assertIn(f'  - id: "{HORIZON_POSITION_ID}"\n    group_id: "3"', caliber)
            self.assertIn('description: "AaveV3 Horizon Supply RLUSD"', caliber)
            self.assertIn(f'position_tokens: ["{HORIZON_ATOKEN}"]', caliber)
            self.assertIn('label: "RLUSD - Horizon Lend"', caliber)
            self.assertIn(f'aave_token: "{HORIZON_ATOKEN}"', caliber)
            self.assertIn(f'aave_pool_instance: "{HORIZON_POOL}"', caliber)
            self.assertNotIn("aave_horizon_pool_address", caliber)

    def test_dmg_mainnet_has_canonical_merkl_harvest(self) -> None:
        caliber = (REPO_ROOT / "machines/dmg/mainnet/caliber.yaml").read_text()
        wrapper = (REPO_ROOT / "machines/dmg/mainnet/instructions/merkl.yaml").read_text()
        self.assertIn('  - id: "777"\n    group_id: "0"\n    description: "Merkl Harvest"', caliber)
        self.assertIn('instructions: !include "./instructions/merkl.yaml"', caliber)
        self.assertIn('instruction_type: "HARVEST"', wrapper)
        self.assertIn('path: "../../../blueprints/merkl/harvest.yaml:harvest"', wrapper)
        self.assertIn('value: "0x3Ef3D8bA38EBe18DB133cEc108f4D14CE00Dd9Ae"', wrapper)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Verify the test is red**

Run:

```bash
python3 -m unittest tests.test_aavev3_position_instance
```

Expected: FAIL because the generic wrappers use config/Core constants, no Core bindings are present in the positions, Horizon is absent, and DMG has no Merkl wrapper.

- [ ] **Step 3: Change the borrow blueprint and shared supply wrapper**

In `blueprints/aave/borrow.yaml`, delete the complete `constants.aave_pool`
mapping, add this input, and make the borrow call target it:

```yaml
  aave_pool_instance:
    type: "address"

        target: ${inputs.aave_pool_instance}
```

In both Pool-input blocks of `instructions/aavev3-supply.yaml`, replace the
Core config reference with:

```yaml
aave_pool_instance:
  type: "address"
  value: "${position.aave_pool_instance}"
```

- [ ] **Step 4: Change the shared borrow wrapper**

Document `aave_pool_instance` as an expected position variable. Bind its
borrow blueprint input and replace repayment's `pool_address` as follows:

```yaml
aave_pool_instance:
  type: "address"
  value: "${position.aave_pool_instance}"

pool_address:
  type: "address"
  value: "${position.aave_pool_instance}"
```

Leave the borrow selector, interest-rate mode, repayment selector, and
accounting `balanceOf` calls untouched.

- [ ] **Step 5: Bind existing generic positions to the standard Core Pool**

Add the following variable to each listed position's `vars:` mapping:

```yaml
aave_pool_instance: "${config.aavev3_core_instance}"
```

| File                                           | Position descriptions                                                                                                                               |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `machines/dbit/mainnet/caliber.yaml`           | `AaveV3 Supply USDC`, `AaveV3 Supply WBTC`, `AaveV3 Borrow USDC`, `AaveV3 Borrow USDT`, `AaveV3 Borrow USDtb`, `AaveV3 Borrow USDe`                 |
| `machines/dqaeeth/mainnet/caliber.yaml`        | `AaveV3 Supply WETH`                                                                                                                                |
| `machines/dusd/mainnet/caliber.yaml`           | `AaveV3 Supply USDC`, `AaveV3 Supply USDG`, `AaveV3 Supply USDe (E-Mode)`, `AaveV3 Borrow USDC (sUSDe E-Mode)`, `AaveV3 Borrow USDT (sUSDe E-Mode)` |
| `machines/intMkSrRoyUSDC/mainnet/caliber.yaml` | `AaveV3 Supply USDC`, `AaveV3 Supply RLUSD`, `AaveV3 Supply USDG`, `AaveV3 Supply USDtb`                                                            |
| `machines/tstETH2/mainnet/caliber.yaml`        | `AaveV3 Supply WETH`                                                                                                                                |

- [ ] **Step 6: Verify the shared refactor is green**

Run:

```bash
python3 -m unittest tests.test_aavev3_position_instance.AaveV3PositionInstanceTests.test_shared_wrappers_take_pool_from_position tests.test_aavev3_position_instance.AaveV3PositionInstanceTests.test_existing_generic_positions_bind_core_explicitly
```

Expected: PASS with 2 tests. The Horizon and DMG tests remain red until their
respective tasks add the missing configuration.

- [ ] **Step 7: Commit the shared refactor**

```bash
git add blueprints/aave/borrow.yaml instructions/aavev3-supply.yaml instructions/aavev3-borrow.yaml machines/dbit/mainnet/caliber.yaml machines/dqaeeth/mainnet/caliber.yaml machines/dusd/mainnet/caliber.yaml machines/intMkSrRoyUSDC/mainnet/caliber.yaml machines/tstETH2/mainnet/caliber.yaml tests/test_aavev3_position_instance.py
git commit -m "refactor: parameterize Aave V3 pool instances"
```

### Task 2: Add the Horizon RLUSD lenders

**Files:**

- Modify: `machines/dusd/mainnet/caliber.yaml`
- Modify: `machines/intMkSrRoyUSDC/mainnet/caliber.yaml`
- Modify: `tests/test_aavev3_position_instance.py`

**Interfaces:**

- Consumes: Task 1's `position.aave_pool_instance` supply wrapper.
- Produces: `aavev3/add_collateral`, `withdraw_collateral`, and `account` instructions labelled `RLUSD - Horizon Lend` on both machines.

- [ ] **Step 1: Confirm the Horizon test remains red**

Run:

```bash
python3 -m unittest tests.test_aavev3_position_instance.AaveV3PositionInstanceTests.test_dusd_and_dsv_define_identical_horizon_rlusd_lenders
```

Expected: FAIL because neither caliber yet contains the group-3 position.

- [ ] **Step 2: Insert the identical position in both calibers**

In DUSD, insert this block after standard Aave V3 supply and before the sUSDe
E-Mode section. In DSV, insert it after standard Aave V3 supply and before the
Aave V4 section:

```yaml
# ── AaveV3 Horizon Supply (group_id: 3) ──────────────────────────
- id: "90412308966732131550279441858106449200"
  group_id: "3"
  description: "AaveV3 Horizon Supply RLUSD"
  instructions: !include "../../../instructions/aavev3-supply.yaml"
  position_tokens: ["0xe3190143eB552456F88464662F0C0C4AC67A77Eb"]
  vars:
    label: "RLUSD - Horizon Lend"
    asset_address: ${token_list.mainnet.RLUSD}
    aave_token: "0xe3190143eB552456F88464662F0C0C4AC67A77Eb"
    aave_pool_instance: "0xAe05Cd22df81871bc7cC2a04BeCfb516bFe332C8"
```

- [ ] **Step 3: Verify the Horizon test is green**

Run:

```bash
python3 -m unittest tests.test_aavev3_position_instance.AaveV3PositionInstanceTests.test_dusd_and_dsv_define_identical_horizon_rlusd_lenders
```

Expected: PASS; each lender has the same ID, aToken, Pool, group, and label.

- [ ] **Step 4: Commit the Horizon positions**

```bash
git add machines/dusd/mainnet/caliber.yaml machines/intMkSrRoyUSDC/mainnet/caliber.yaml tests/test_aavev3_position_instance.py
git commit -m "feat: add Aave Horizon RLUSD supply"
```

### Task 3: Add DMG mainnet Merkl harvest

**Files:**

- Create: `machines/dmg/mainnet/instructions/merkl.yaml`
- Modify: `machines/dmg/mainnet/caliber.yaml`
- Modify: `tests/test_aavev3_position_instance.py`

**Interfaces:**

- Consumes: `MerklClaimData` and `blueprints/merkl/harvest.yaml:harvest`.
- Produces: a group-0 `merkl/harvest/Merkl` instruction under position ID `777`.

- [ ] **Step 1: Confirm the DMG Merkl test is red**

Run:

```bash
python3 -m unittest tests.test_aavev3_position_instance.AaveV3PositionInstanceTests.test_dmg_mainnet_has_canonical_merkl_harvest
```

Expected: FAIL with `FileNotFoundError` because DMG's Merkl wrapper is absent.

- [ ] **Step 2: Create the canonical Merkl wrapper**

Create `machines/dmg/mainnet/instructions/merkl.yaml` with:

```yaml
- is_debt: false
  instruction_type: "HARVEST"
  affected_tokens: []
  instruction:
    label: "Merkl"
    path: "../../../blueprints/merkl/harvest.yaml:harvest"
    inputs:
      merkl_distributor_address:
        type: "address"
        value: "0x3Ef3D8bA38EBe18DB133cEc108f4D14CE00Dd9Ae"
```

- [ ] **Step 3: Register the harvest-only position**

Insert this block immediately after `positions:` in
`machines/dmg/mainnet/caliber.yaml`:

```yaml
# ── Harvest-only ──────────────────────────────────────────────────
- id: "777"
  group_id: "0"
  description: "Merkl Harvest"
  instructions: !include "./instructions/merkl.yaml"
```

- [ ] **Step 4: Verify the DMG Merkl test is green**

Run:

```bash
python3 -m unittest tests.test_aavev3_position_instance.AaveV3PositionInstanceTests.test_dmg_mainnet_has_canonical_merkl_harvest
```

Expected: PASS with the canonical mainnet distributor and no DMG Base files.

- [ ] **Step 5: Commit the DMG Merkl position**

```bash
git add machines/dmg/mainnet/caliber.yaml machines/dmg/mainnet/instructions/merkl.yaml tests/test_aavev3_position_instance.py
git commit -m "feat: add DMG Merkl harvest"
```

### Task 4: Generate rootfiles and validate

**Files:**

- Create: `machines/dusd/mainnet/rootfiles/20260722-aave-horizon-rlusd.toml`
- Create: `machines/intMkSrRoyUSDC/mainnet/rootfiles/20260722-aave-horizon-rlusd.toml`
- Create: `machines/dmg/mainnet/rootfiles/20260722-merkl-harvest.toml`

**Interfaces:**

- Consumes: final full Caliber YAML plus `token-lists/prod-token-list.json`.
- Produces: generated roots exposing the new positions.

- [ ] **Step 1: Format and check the three affected calibers**

Run:

```bash
dprint fmt
TP="${TRANSPILER_PATH:-/Users/augustin/.cargo/git/checkouts/transpiler-11f55d1751042103/9471437/target/debug/transpiler}"
test -x "$TP"
"$TP" --input-file machines/dusd/mainnet/caliber.yaml --token-list token-lists/prod-token-list.json check
"$TP" --input-file machines/intMkSrRoyUSDC/mainnet/caliber.yaml --token-list token-lists/prod-token-list.json check
"$TP" --input-file machines/dmg/mainnet/caliber.yaml --token-list token-lists/prod-token-list.json check
```

Expected: formatter succeeds and all three transpiler checks exit zero.

- [ ] **Step 2: Transpile the migration roots**

Run:

```bash
"$TP" --input-file machines/dusd/mainnet/caliber.yaml --token-list token-lists/prod-token-list.json --output-file machines/dusd/mainnet/rootfiles/20260722-aave-horizon-rlusd.toml transpile
"$TP" --input-file machines/intMkSrRoyUSDC/mainnet/caliber.yaml --token-list token-lists/prod-token-list.json --output-file machines/intMkSrRoyUSDC/mainnet/rootfiles/20260722-aave-horizon-rlusd.toml transpile
"$TP" --input-file machines/dmg/mainnet/caliber.yaml --token-list token-lists/prod-token-list.json --output-file machines/dmg/mainnet/rootfiles/20260722-merkl-harvest.toml transpile
rg -n "AaveV3 Horizon Supply RLUSD" machines/dusd/mainnet/rootfiles/20260722-aave-horizon-rlusd.toml machines/intMkSrRoyUSDC/mainnet/rootfiles/20260722-aave-horizon-rlusd.toml
rg -n 'instructions.merkl.harvest.Merkl' machines/dmg/mainnet/rootfiles/20260722-merkl-harvest.toml
```

Expected: the two Horizon roots contain the lender and the DMG root contains Merkl harvest.

- [ ] **Step 3: Run the full static suite**

Run:

```bash
python3 -m unittest discover -s tests
python3 scripts/validate_token_chains.py
git diff --check
```

Expected: all tests pass, token-chain validation has no mismatch, and the diff check has no output.

- [ ] **Step 4: Commit generated rootfiles**

```bash
git add machines/dusd/mainnet/rootfiles/20260722-aave-horizon-rlusd.toml machines/intMkSrRoyUSDC/mainnet/rootfiles/20260722-aave-horizon-rlusd.toml machines/dmg/mainnet/rootfiles/20260722-merkl-harvest.toml
git commit -m "chore: generate Horizon and Merkl rootfiles"
```
