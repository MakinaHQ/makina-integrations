# Royco Junior Tranches — stcUSD & syrupUSDC

**Status:** spec, awaiting review
**Date:** 2026-05-08
**Branch:** `feat/dusd-royco-junior`
**Target machine:** DUSD (mainnet)
**Author:** platykurtic

## Context

DUSD already integrates the Royco **senior** tranches (ST) for stcUSD and syrupUSDC via:

- `instructions/royco-st-stcusd.yaml` (6 entries: 5 MGMT + 1 ACCOUNTING)
- `instructions/royco-st-syrupusdc.yaml` (3 entries: 2 MGMT + 1 ACCOUNTING)
- `blueprints/royco/st-stcusd/`
- `blueprints/royco/st-syrupusdc/`

Royco markets are tranched. The senior tranche earns a base yield with built-in protection; the **junior tranche** earns a leveraged yield in exchange for first-loss exposure. Both tranches share the same kernel and the same TRANCHE_UNIT (the deposit asset of the market: stcUSD for the stcUSD market, syrupUSDC for the syrupUSDC market).

This spec adds the JT counterpart for both markets while introducing one deliberate change versus ST: **accounting reports the JT position in the asset directly upstream of the tranche** (cUSD for stcUSD, USDC for syrupUSDC) rather than going through the kernel's USD NAV path.

## Goals

1. Operate the JT tranches with the same instruction surface as ST (deposit / withdraw / re-entry / accounting).
2. Avoid the USD-NAV accounting path: stay in cUSD or USDC.
3. Reuse existing patterns and helpers; introduce no new transpiler utilities.

## Non-goals

- Migrating the existing ST accounting path to the new style. Out of scope; ST keeps its NAV-based accounting blueprint as is.
- Cross-tranche flows (e.g., simultaneously sizing ST/JT). Operator orchestrates.
- Off-chain monitoring or alerting around Coverage / Protection Mode. Out of scope.

## Verified facts

### Junior tranche addresses

Discovered by replaying the kernel-init transactions for each market and identifying the address whose `TRANCHE_TYPE() == 1`:

| Market    | Junior tranche proxy                         | TRANCHE_UNIT (asset())                                         | Share decimals | Implementation                               |
| --------- | -------------------------------------------- | -------------------------------------------------------------- | -------------- | -------------------------------------------- |
| stcUSD    | `0xe4060e83ad26618c7ed56a02ce099beba4f73b29` | stcUSD `0x88887bE419578051FF9F4eb6C858A951921D8888` (18 dec)   | 18             | `0x93a3d70c2e05e62785887c2fb7d9a7927bd49eb9` |
| syrupUSDC | `0x5f340b400f892bbfded2e5c316369dcbf05c282a` | syrupUSDC `0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b` (6 dec) | 18             | `0xd10def48855ffbb525f23ebbd67ba19f94b80f9e` |

Both kernels are unchanged (`0x9911F22...` for stcUSD, `0xde1Ce2cF...` for syrupUSDC); we just point at a different tranche proxy.

### AssetClaims tuple shape

Source-of-truth, `royco/dawn-msig-orchestration/src/libraries/Types.sol:15-19`:

```solidity
struct AssetClaims {
    TRANCHE_UNIT stAssets; // [0] - in TRANCHE_UNIT
    TRANCHE_UNIT jtAssets; // [1] - in TRANCHE_UNIT
    NAV_UNIT     nav;      // [2] - in USD-WAD (18 dec)
}
```

Both `stAssets` AND `jtAssets` are in TRANCHE_UNIT (the market's deposit asset). Only `nav` is USD-WAD. The earlier `scripts-factory/royco-st-stcusd/nav-investigation.md` mistakenly claimed `jtAssets` is denominated in cUSD; this spec corrects that and the file should be patched.

### convertToAssets returns caliber-pro-rata, both fields populated

Direct on-chain measurement against `convertToAssets(totalSupply)`:

```
JT-stcUSD     → (stAssets=1.85e15 stcUSD, jtAssets=2.10e18 stcUSD, nav=2.23e18 USD-WAD)
JT-syrupUSDC  → (stAssets=2.10e7 syrup,   jtAssets=3.18e10 syrup,  nav=3.71e22 USD-WAD)
```

Two observations that drive the design:

1. **Both fields are non-zero for JT** — the kernel distributes the JT's pro-rata claim across both layer accumulators. Therefore `(stAssets + jtAssets)` is the correct caliber-pro-rata claim in TRANCHE_UNIT, **mirroring the existing ST pattern in `blueprints/royco/st-syrupusdc/account.yaml` which already does this sum**. We are not introducing a new accounting motif.
2. **Cross-check**: `(2.10e7 + 3.18e10) syrupUSDC ≈ 31,855 syrupUSDC × ~1.16 USDC/syrup ≈ ~$36.9k`, vs `nav ≈ 3.71e22 ≈ $37.1k`. Sub-percent gap (different fee/floor accounting) — the two paths agree.

### Interface

Both JT proxies expose the V2 interface (same as the integrated ST proxies):

- `deposit(uint256 assets, address receiver) → uint256 shares` (AccessManaged-restricted; verified by `AccessManagedUnauthorized(address)` selector `0x068ca9d8` on revert from a non-roled caller)
- `redeem(uint256 shares, address receiver, address owner) → AssetClaims claims`
- `convertToAssets(uint256 shares) → (uint256 stAssets, uint256 jtAssets, uint256 nav)`
- `balanceOf(address) → uint256`
- `TRANCHE_TYPE() → 1` (JUNIOR)
- `asset() → TRANCHE_UNIT` (same as the ST sibling)

No `requestRedeem` flow on the JT itself — JT redeem is synchronous and returns TRANCHE_UNIT to the caliber. Any queueing happens **downstream** at the syrupUSDC vault (Maple `WithdrawalManager`), identical to the ST flow.

## Design

### File layout (mirrors ST exactly)

```
blueprints/royco/jt-stcusd/
├── deposit.yaml             USDC → cUSD → stcUSD → JT          (whitelist-gated on Cap.mint)
├── withdraw.yaml            JT → stcUSD → cUSD → USDC          (escape hatch, not gated)
├── withdraw-to-cusd.yaml    JT → stcUSD → cUSD                 (no Cap touch)
├── deposit-from-cusd.yaml   cUSD → stcUSD → JT                 (no Cap touch)
├── burn-cusd-to-usdc.yaml   cUSD → USDC                        (whitelist-gated)
└── account.yaml             reports JT position in cUSD (18 dec)

blueprints/royco/jt-syrupusdc/
├── deposit.yaml             USDC → syrupUSDC → JT
├── withdraw.yaml            JT → syrupUSDC → requestRedeem (Maple queue)
└── account.yaml             reports JT position in USDC (6 dec, includes pending escrow)

instructions/
├── royco-jt-stcusd.yaml     6 entries, 1:1 mirror of royco-st-stcusd.yaml
└── royco-jt-syrupusdc.yaml  3 entries, 1:1 mirror of royco-st-syrupusdc.yaml
```

The cUSD-leg blueprints are duplicated into `jt-stcusd/` rather than shared with `st-stcusd/`. Self-contained per tranche, no cross-folder references in instruction files. Light duplication is acceptable.

Labels follow the `ROY-JT-{market}` convention (vs `ROY-ST-{market}` for senior), matching the disambiguation rule in `MEMORY.md`.

### Accounting blueprints (the only new pattern)

#### `blueprints/royco/jt-stcusd/account.yaml` — reports cUSD (18 dec)

```
1. context.msgSender()                         → caliber
2. kernel.syncTrancheAccounting()
3. JT.balanceOf(caliber)                       → jt_shares
4. JT.convertToAssets(jt_shares)               → asset_claims tuple
5. bytes32_helper.getTupleWord(claims, 0)      → stAssets   (stcUSD, 18 dec)
6. bytes32_helper.getTupleWord(claims, 1)      → jtAssets   (stcUSD, 18 dec)
7. unsigned_math_helper.add(stAssets, jtAssets) → total_stcusd
8. stcUSD.convertToAssets(total_stcusd)        → cusd_value (cUSD, 18 dec)
9. reserved_slots: [cusd_value (uint256), MAX (uint256)]
```

The DUSD machine already prices cUSD (the senior tranche's path goes through cUSD as an intermediate, so cUSD is a recognized accounting asset on this machine). No new oracle wiring.

#### `blueprints/royco/jt-syrupusdc/account.yaml` — reports USDC (6 dec)

```
1.  context.msgSender()                                          → caliber
2.  kernel.syncTrancheAccounting()
3.  JT.balanceOf(caliber)                                        → jt_shares
4.  JT.convertToAssets(jt_shares)                                → asset_claims tuple
5.  bytes32_helper.getTupleWord(claims, 0)                       → stAssets (syrupUSDC, 6 dec)
6.  bytes32_helper.getTupleWord(claims, 1)                       → jtAssets (syrupUSDC, 6 dec)
7.  unsigned_math_helper.add(stAssets, jtAssets)                 → active_syrup
8.  Maple_WithdrawalManager.userEscrowedShares(caliber)          → escrowed_syrup
9.  unsigned_math_helper.add(active_syrup, escrowed_syrup)       → total_syrup
10. syrupUSDC.convertToExitAssets(total_syrup)                   → usdc_value (USDC, 6 dec)
11. reserved_slots: [usdc_value (uint256), MAX (uint256)]
```

Identical shape to `blueprints/royco/st-syrupusdc/account.yaml`, just retargeted at the JT proxy. The Maple `WithdrawalManager` is the same `0x1bc47a0Dd0FdaB96E9eF982fdf1F34DC6207cfE3` because the queue is keyed on syrupUSDC redemption requests, not on which tranche fed the syrupUSDC.

### MANAGEMENT blueprints

For each of `deposit`, `withdraw`, `withdraw-to-cusd`, `deposit-from-cusd` — copy the ST blueprint and swap the senior_tranche address for the junior_tranche address. The Cap Vault, stcUSD vault, syrupUSDC vault, USDC, and cUSD addresses stay identical, as does the V2 deposit/redeem signature.

For `burn-cusd-to-usdc` (stcUSD market) — pure Cap Vault burn, no tranche reference. Logic is identical to ST's `burn-cusd-to-usdc.yaml`; we just duplicate the file inside `jt-stcusd/` to keep the folder self-contained.

For `withdraw` (syrupUSDC market) — copy the ST flow:

1. Compute shares-to-redeem from `bps_to_redeem`
2. Sandwich syrupUSDC balance around `JT.redeem(shares, caliber, caliber)`
3. `syrupUSDC.requestRedeem(syrupUSDC_delta, caliber)` to enter the Maple queue

### Instruction file structure

Both files mirror their ST sibling 1:1. Examples:

`instructions/royco-jt-stcusd.yaml` — same structure as `royco-st-stcusd.yaml`, with:

- All paths repointed to `../../../blueprints/royco/jt-stcusd/...`
- Label `ROY-JT-stcUSD` (or `ROY-JT-stcUSD-DepositFromCUSD` for the cUSD re-entry instruction, mirroring the ST suffix)
- `affected_tokens` unchanged from ST (the asset graph is identical)

`instructions/royco-jt-syrupusdc.yaml` — same structure as `royco-st-syrupusdc.yaml`, with:

- Paths repointed to `../../../blueprints/royco/jt-syrupusdc/...`
- Label `ROY-JT-syrupUSDC` / `ROY-JT-syrupUSDC-NAV` (existing ST already mislabels accounting as `-NAV`; for JT we'll use `ROY-JT-syrupUSDC` and `ROY-JT-syrupUSDC-USDC` to reflect the actual reporting unit, or leave both `ROY-JT-syrupUSDC` if the unique-label rule is per-(protocol, type, label) tuple — the type differs between MGMT and ACCOUNTING so reuse is allowed).

## Trade-offs and considerations

**Why JT accounting in cUSD/USDC instead of USD-WAD:**

1. No `mulDiv(nav, 1, 1e12)` truncation when scaling 18-dec NAV down to 6-dec USDC.
2. No reliance on the kernel's USD oracle path (cUSD→USD price feed).
3. Single rate everywhere — `convertToAssets` / `convertToExitAssets` is the same rate an actual exit uses, so the position's marked value matches realizable value.
4. DUSD policy: stay in stable units, avoid USD pricing.

**Why duplicate cUSD-leg blueprints rather than reach into `st-stcusd/`:**

Self-contained tranche folders keep responsibility unambiguous: opening `jt-stcusd/` shows the full surface of the junior integration. The marginal duplication cost (one short YAML file, no logic) is well below the readability benefit.

**JT first-loss semantics (operational, not blueprint-affecting):**

Per the Royco curator guide: during a drawdown, the market enters Protection Mode (e.g., 7 days). Senior withdrawals are paused; 100% of yield is redirected to junior. If losses persist past Protection Mode, junior absorbs them. JT redemptions during Protection Mode behave like normal redemptions for JT (junior is not paused — only senior is). This is not a blueprint concern, but operators should know the risk profile is materially different from ST.

**AccessManager roles:**

Each JT contract is AccessManaged. The caliber will need separate role grants on both `0xe4060e83...` and `0x5f340b40...` before deposit/redeem succeed. This is operational onboarding (mirroring the syrupUSDC ST onboarding which required two role IDs), not a blueprint concern. Document required role IDs once obtained from Royco team and add to `MEMORY.md` once assigned.

## Known risk: syrupUSDC pending-withdrawal double-counting

`Maple_WithdrawalManager.userEscrowedShares(caliber)` is keyed on caliber address, not on tranche. If the caliber simultaneously has pending withdrawals from **both** the ST and JT syrupUSDC positions, both `account.yaml` files (ST's existing one and JT's new one) will each add the full escrowed amount to their own report — double-counting the pending USDC.

The safe operating constraint is: at any given time, run `requestRedeem` from at most one of {ST-syrupUSDC, JT-syrupUSDC} on the same caliber. Practically this is fine for a steady-state deployment (you typically size into one tranche and stay there), but it's a footgun worth noting.

Mitigation options to evaluate during implementation:

1. **Accept and document** — codify the operating constraint in a `MEMORY.md` entry and in the JT instruction file's leading comment. Cheapest; matches expected operator discipline.
2. **Move the escrow term out of both tranche `account.yaml` files** into a standalone ACCOUNTING instruction that reports the pending USDC exactly once (e.g., a `royco-syrupusdc-pending.yaml` entry on the machine). Cleaner but requires a one-off accounting blueprint that doesn't fit the `blueprints/royco/{tranche}/` folder convention.
3. **Drop the escrow term from JT only** — gives an under-report on JT pending withdrawals but never double-counts. Asymmetric and surprising.

Recommendation for the implementation PR: option 1, with a clear comment in `jt-syrupusdc/account.yaml` and a note in the operator runbook. Revisit option 2 if the constraint becomes operationally painful.

## Open questions / follow-ups (non-blocking)

- Confirm the JT AccessManager role IDs for both markets before going to mainnet. Tenderly testing can use impersonation.
- Decide whether to also fix `scripts-factory/royco-st-stcusd/nav-investigation.md` in this PR (one-line correction) or in a separate cleanup. Recommend: include in this PR since we're already touching the topic.
- Future: consider migrating the ST stcUSD accounting to the same cUSD-denominated path for consistency. Out of scope here.

## Acceptance criteria

1. New blueprint files compile (`/compile`) without errors.
2. Both new instruction files pass blueprint tester end-to-end on a Tenderly fork:
   - JT-stcUSD: full deposit (USDC→JT) → accounting → withdraw (JT→USDC); cycle through escape-hatch variants.
   - JT-syrupUSDC: deposit (USDC→JT) → accounting → withdraw (request_redeem) → run accounting and observe pending balance reflected via `userEscrowedShares`.
3. Reported caliber accounting matches `convertToAssets`-derived value within rounding tolerance.
4. Labels are unique per (protocol, type, label) tuple per `MEMORY.md` rule.

## References

- `royco/dawn-msig-orchestration/src/libraries/Types.sol` — `AssetClaims` struct
- `royco/dawn-msig-orchestration/src/interfaces/tranche/IRoycoVaultTrancheV2.sol` — V2 interface
- `royco/dawn-msig-orchestration/CURATOR_GUIDE.md` — tranche risk semantics
- `blueprints/royco/st-stcusd/` and `blueprints/royco/st-syrupusdc/` — patterns to mirror
- `scripts-factory/royco-st-stcusd/nav-investigation.md` — needs correction (jtAssets is TRANCHE_UNIT, not cUSD)
