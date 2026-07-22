# Aave Horizon RLUSD Supply for DSV and DUSD

**Issue:** DIA-906\
**Date:** 2026-07-22\
**Scope:** Ethereum mainnet only. DSV is `intMkSrRoyUSDC`. DMG Base is explicitly out of scope because its caliber is not on `main`.

## Goal

Enable the DSV and DUSD calibers to supply and withdraw RLUSD in the Aave
Horizon market, and make the shared Aave V3 wrappers select their Pool per
position rather than assuming the standard Core Pool. Add the missing Merkl
harvest-only position to DMG mainnet.

## Fixed integration values

| Item                        | Value                                        |
| --------------------------- | -------------------------------------------- |
| Horizon Pool                | `0xAe05Cd22df81871bc7cC2a04BeCfb516bFe332C8` |
| RLUSD                       | `0x8292Bb45bf1Ee4d140127049757C2E0fF06317eD` |
| aHorRwaRLUSD                | `0xe3190143eB552456F88464662F0C0C4AC67A77Eb` |
| Merkl distributor (mainnet) | `0x3Ef3D8bA38EBe18DB133cEc108f4D14CE00Dd9Ae` |

RLUSD is already in the production token list and is a base token with a live
price route on both target calibers. No token-list or Oracle Registry mutation
is needed.

## Architecture

### Per-position Aave Pool selection

Backport the focused Aave portion of historical commit `8803ba6`:

- `blueprints/aave/borrow.yaml` accepts `aave_pool_instance` as an input and
  targets it instead of a hardcoded Core Pool.
- `instructions/aavev3-supply.yaml` and `instructions/aavev3-borrow.yaml`
  bind that input from `position.aave_pool_instance`.
- Every existing position that includes either shared wrapper receives its
  current Aave Core Pool as a position variable. This preserves compiled
  behavior for DBIT, DQAEETH, DUSD, DSV, and TSTETH2 while allowing a distinct
  Pool for Horizon.

The legacy `aavev3_core_instance` config values remain for machine-local
instructions that still intentionally consume them. The new Horizon address is
never added to shared `config:`; it lives only on its two Horizon positions.

### Horizon RLUSD positions

Add one lender position to each of:

- `machines/dusd/mainnet/caliber.yaml`
- `machines/intMkSrRoyUSDC/mainnet/caliber.yaml`

The positions share ID `90412308966732131550279441858106449200` (the low 128
bits of `keccak256("aavev3.horizon.rlusd.supply")`) and use group `3`. Groups
`1` and `2` already represent the standard Aave V3 and Aave V4 liability
domains respectively; group `3` isolates the independent Horizon Pool domain
for future Horizon positions.

Each position supplies these variables:

- `label: "RLUSD - Horizon Lend"`;
- RLUSD as `asset_address`;
- `aHorRwaRLUSD` as the single `position_tokens` item and `aave_token`;
- the Horizon Pool as `aave_pool_instance`.

The existing Aave supply wrapper produces the standard flow: approve RLUSD to
the selected Pool, call `supply`, call `withdraw` for management, and account
with `aToken.balanceOf(caliber)`. It does not transfer the aToken, so it is
unaffected by the RWA aToken transfer policy. A frozen or paused reserve is
left to the deployed Pool's normal revert behavior; no local bypass or special
withdrawal logic is introduced.

### DMG mainnet Merkl harvest

Create `machines/dmg/mainnet/instructions/merkl.yaml` following the established
mainnet wrapper and add a group-0 harvest-only position to
`machines/dmg/mainnet/caliber.yaml`:

- ID `777`;
- description `Merkl Harvest`;
- include `./instructions/merkl.yaml`.

The wrapper calls the canonical Merkl distributor with operator-provided
`MerklClaimData`. It has no affected or position tokens, matching the existing
harvest convention. No Base files are created or changed.

## Validation

Test-driven regression coverage will first fail against the current checkout,
then assert:

1. Generic Aave supply and borrow instructions forward the Pool from the
   position, and the borrow blueprint has no Core-Pool constant.
2. Every migrated generic Aave position explicitly selects the existing Core
   Pool, while both new RLUSD positions select Horizon, use group `3`, and carry
   the correct RLUSD/aToken addresses.
3. DMG mainnet has the canonical Merkl wrapper and position `777`; DMG Base is
   absent from the change.

After the tests are green, format with `dprint`, compile the affected full
calibers, and retain generated, dated rootfiles for DUSD, DSV, and DMG mainnet.
Run the Python test suite, token-chain validation, `git diff --check`, and the
focused compile checks. A fork lifecycle test may additionally exercise
supply, account, and withdraw where the local spellcaster environment is
available; it is not a prerequisite for Oracle setup because both target
calibers already price and accept RLUSD.

## Out of scope

- Creating or modifying `machines/dmg/base`, its registry entry, or its
  rootfiles.
- New Oracle routes, Base-token registration, or token-list entries.
- Borrowing, collateral enablement, reward-controller integration, and direct
  aToken transfers on Aave Horizon.
