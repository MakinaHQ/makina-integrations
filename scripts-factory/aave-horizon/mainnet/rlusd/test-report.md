# Blueprint Test Report — Aave Horizon RLUSD supply (makina-x)

**Instruction**: machines/chronograph-x/mainnet/instructions/aave-horizon-rlusd.yaml
**Blueprints**: blueprints-x/aave-horizon/{deposit,withdraw}.yaml
**Machine**: chronograph-x (makina-x)
**Network**: mainnet (ethereum)
**Position**: id `47445753596645566272224472924421400103` (pools_db makina_id — Aave Horizon RLUSD lending)
**Fork**: mainnet fork via forge `createSelectFork` (`$MAINNET_RPC_URL`, chainId 1)
**Date**: 2026-07-23
**Method**: forge fork-test harness `scripts/makinax_e2e_harness.py` (`/test_e2e_x`)
**Transpiler**: rootfile committed at `rootfiles/20260723-aave-horizon-rlusd.toml` (compiled with `--lite`)

## Summary

End-to-end test of the makina-x Aave Horizon RLUSD supply blueprint. makina-x is a **Safe-module**
architecture: the position is held by the **Safe** and executed by the **`MakinaXModule`** Safe
module — there is no caliber and positions are **not NAV-accounted on-chain**, so this is
**management-only with NO ACCOUNTING action** (by design).

Because the local `makina-rs` spellcaster does not support lite modules, the standard
`spellcaster manage-position` lifecycle does not apply here. Instead the **exact compiled weiroll
instructions** from the committed rootfile are executed against the **real deployed
`MakinaXModule`** on a mainnet fork, in the Safe's context (`execTransactionFromModule` → DelegateCall
into the weiroll VM).

**Result: PASS.** No blueprint fixes required.

Flows proven:

- **compile validation** — the recomputed composite merkle root of the two instructions equals the
  transpiler root in the committed rootfile (`0x67cce340…eff4`), i.e. the compile matches the
  module's on-chain leaf encoding.
- **deposit (`add_collateral` → `supply`)** — RLUSD pulled from the Safe 1:1, aToken minted 1:1 to
  the Safe (`on_behalf_of = Safe`).
- **withdraw (`withdraw_collateral` → `withdraw`, `type(uint256).max`)** — aToken fully redeemed,
  RLUSD returned to the Safe (`to = Safe`).

## Contract Addresses

| Contract                             | Address                                      |
| ------------------------------------ | -------------------------------------------- |
| Safe (position holder)               | `0x9f0f855A7370cc30e24924258214681A782A34aC` |
| MakinaXModule (`makina_lite_module`) | `0x785db5f3F3Ad18D6291689907D319954AF79A03E` |
| Weiroll VM                           | `0x28F767b3687ceAcEeE54B44C98Ef411CB54FbB7a` |
| Horizon Pool                         | `0xAe05Cd22df81871bc7cC2a04BeCfb516bFe332C8` |
| RLUSD (base token, 18 dec)           | `0x8292Bb45bf1Ee4d140127049757C2E0fF06317eD` |
| aToken aHorRwaRLUSD (position)       | `0xE3190143Eb552456F88464662f0c0C4aC67A77eB` |

## Setup / Execution Steps

| Step                   | Status | Details                                                                                                |
| ---------------------- | ------ | ------------------------------------------------------------------------------------------------------ |
| Module introspection   | PASS   | `safe()` == config Safe; module enabled on Safe; `paused`/`suspendedByProvider` false                  |
| Operating mode         | PASS   | `operatingMode()` == 1 (FENCED) → unguarded: management-only, no mandatory accounting, no value checks |
| Compile-root check     | PASS   | recomputed composite root == committed transpiler root `0x67cce340…eff4`                               |
| Authorize (prank Safe) | PASS   | `addOperator` + `setAllowedInstrRoot` (single-leaf tree, empty proof)                                  |
| Fund                   | PASS   | `deal` 100,000 RLUSD to the Safe                                                                       |

## Lifecycle Results (100,000 RLUSD)

| Action                    | Safe RLUSD | Safe aToken | Result |
| ------------------------- | ---------- | ----------- | ------ |
| before                    | 100,000    | 0           | —      |
| deposit (`supply`)        | 0          | 100,000     | PASS   |
| withdraw (`withdraw` max) | 100,000    | 0           | PASS   |

| Check                                   | Result                    |
| --------------------------------------- | ------------------------- |
| compiled root == on-chain leaf encoding | PASS                      |
| deposit → withdraw lifecycle            | PASS                      |
| accounting                              | N/A (makina-x, by design) |

**Overall: PASS.**

## Reproduce

```bash
uv run scripts/makinax_e2e_harness.py \
  machines/chronograph-x/mainnet/caliber.yaml --amount 100000 \
  --out scripts-factory/aave-horizon/mainnet/rlusd/test-report.md
```
