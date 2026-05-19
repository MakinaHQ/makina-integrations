# Royco Senior Tranche — Pareto FalconX (USDC)

## TL;DR

Senior tranche over **Pareto Credit's FalconX USDC vault**. The integration superficially resembles the existing Royco ST family (autousd, snusd, smokehouse-usdc, stcusd, syrupusdc) but the **middle layer is materially different** — instead of an ERC4626 yield vault, the ST sits on top of an **IdleCDOTranche** managed by an **IdleCDOEpochVariant** with **epoch-queued withdrawals** (~32-day epoch + 5-day buffer) and **two independent off-chain gates** (Pareto Keyring + Royco AccessManager).

## Token / Contract Map

| Role                                      | Address                                      | Notes                                                                                                                             |
| ----------------------------------------- | -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Royco ST (caliber holds shares of this)   | `0x694ADB3077BBecE31882B6d6A74fc4A4fA6a754b` | ERC4626-shape, NAV-priced; impl unverified                                                                                        |
| Royco Kernel                              | `0x15bb63C07740ff972F76716cAcC5766f0C641791` | `syncTrancheAccounting()` required pre-read                                                                                       |
| RoycoFactory / AccessManager              | `0x7cC6fB28eC7b5e7afC3cB3986141797ffc27253C` | Off-chain role grants gate `deposit` / `redeem` / `syncTrancheAccounting`                                                         |
| AA tranche (ST's `asset()`)               | `0xc26a6fa2c37b38e549a4a1807543801db684f99c` | `IdleCDOTranche`, 18 dec, **NOT ERC4626**                                                                                         |
| BB tranche                                | `0xacbb25b7dd30b6b2f7131865dc1023622de3b3d6` | Junior                                                                                                                            |
| Pareto IdleCDOEpochVariant                | `0x433D5B175148dA32Ffe1e1A37a939E1b7e79be4d` | Verified; deposit/withdraw entry; `depositAA` / `depositDuringEpoch(amt, AATranche)` / `requestWithdraw` / `claimWithdrawRequest` |
| Pareto IdleCreditVault (withdraw receipt) | `0x17E9Ab2992dfecBe779a06A92a6cDB9fE6aEeEf3` | 6 dec, ERC20 "FalconXUSDC" — minted on `requestWithdraw`, burned on `claim`                                                       |
| Pareto Keyring                            | `0x6a6a91c7c7c05f9f6b8bc9f6e5ea231e460450e3` | Policy id `18` gates deposit / requestWithdraw (no on-chain bypass)                                                               |
| Pareto TranchesChainlinkOracle            | `0x50449B3D1f5931d568A1951Ee506A9534e7f7dFf` | Used by Morpho, **NOT** by the Royco kernel                                                                                       |
| USDC                                      | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` | 6 dec                                                                                                                             |

## Flows

### Deposit (atomic, single-tx)

USDC → Pareto IdleCDOEpochVariant → AA tranche token → Royco ST shares.

Branch on epoch state:

- `isEpochRunning() == true && !isDepositDuringEpochDisabled` → `depositDuringEpoch(amount, AATranche)`
- `isEpochRunning() == false` → `depositAA(amount)`

Then `ST.deposit(aaAmount, caliber)` mints ST shares to the caliber.

**Coverage check**: kernel reverts senior deposit if `jtRawNAV == 0` (utilization = uint256.max). **A junior must be bootstrapped first** before any senior deposit will succeed.

### Withdraw (queued, two-phase, ~32–37 days between phases)

1. `phase_1_request_redeem`: `ST.redeem(shares, caliber, caliber)` → AA tranche tokens. Then `IdleCDOEpochVariant.requestWithdraw(aaAmount, AATranche)` → mints `FalconXUSDC` (6-dec ERC20 receipt) to caliber. AA tokens are burned at request time.
2. **Wait for next epoch close** (`epochEndDate` + ~5 day buffer; epoch duration ≈ 2,790,207 s).
3. `phase_2_claim_redeem`: `IdleCDOEpochVariant.claimWithdrawRequest()` burns the receipt and pays out USDC. **Not Keyring-gated** — claim works even if the caliber's credential is later revoked.

### Account (NAV-style, with pending receipt added back)

Use **asset-space** accounting (avoids the `mulDiv(nav, 1, 1e12)` 1-wei truncation that hurt syrupUSDC):

```
1. ST.balanceOf(caliber) → st_shares
2. Kernel.syncTrancheAccounting()
3. ST.convertToAssets(st_shares) → (stAssets, jtAssets, nav)   [3-tuple, 18-dec AA units]
4. AA.balanceOf(caliber) → stranded_aa
5. total_aa = stAssets + jtAssets + stranded_aa
6. tranche_price = IdleCDOEpochVariant.tranchePrice(AATranche)  [USDC-6dec per 1e18 AA]
7. usdc_from_aa = total_aa * tranche_price / 1e18
8. pending_usdc = FalconXUSDC.balanceOf(caliber)  [already 6-dec USDC]
9. total_usdc = usdc_from_aa + pending_usdc
```

The 3-tuple `convertToAssets` shape (`stAssets`, `jtAssets`, `nav`) is preserved across the family — the existing `getTupleWord(bytes,uint256)` helper works verbatim.

## Access Control (BLOCKERS for testing)

Two independent off-chain gates, both must be granted before any deposit / requestWithdraw will succeed on a real chain:

1. **Pareto Keyring credential** on policy `18` for the caliber address. Gates `depositAA`, `depositDuringEpoch`, `requestWithdraw`. No on-chain bypass.
2. **Royco AccessManager role grants**:
   - `(ST 0x694A…, deposit selector 0x6e553f65)`
   - `(ST 0x694A…, redeem selector …)`
   - `(Kernel 0x15bb…, syncTrancheAccounting selector)`
     Verify post-grant via `RoycoFactory.canCall(caliber, target, selector) → (true, 0)`.

For **Tenderly testing** we will override both gates via storage writes / impersonation — this is the same workaround pattern used in the syrupusdc / stcusd execution-explorer runs.

## Divergence vs. Reference Integrations

| Aspect                  | syrupUSDC / stcUSD                                                            | Pareto FalconX                                                                    |
| ----------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Middle layer            | ERC4626 vault                                                                 | IdleCDOTranche (custom)                                                           |
| Mid-layer entry         | `vault.deposit(amount, recipient)`                                            | `cdo.depositAA(amount)` or `depositDuringEpoch(amount, AATranche)`                |
| Withdraw cadence        | Synchronous (syrupUSDC has Maple WithdrawalManager queue but not epoch-bound) | **Epoch-queued (~32 days)**                                                       |
| Withdraw receipt        | Maple `userEscrowedShares` view                                               | Standalone ERC20 (`FalconXUSDC` 6-dec)                                            |
| Keyring gate            | None                                                                          | **Yes** (Pareto policy 18, deposits + requestWithdraw)                            |
| Coverage gate on senior | Same                                                                          | Same — but FalconX market currently has `jtRawNAV = 0`, blocking senior bootstrap |
| Account precision       | NAV via `mulDiv(nav,1,1e12)` (loses 1 wei) or syrup-style asset-space         | **Asset-space recommended** (cleaner via `tranchePrice`)                          |

## Open / Blocking Items

1. **Junior bootstrap.** Senior cannot be the first deposit — coverage check reverts. Confirm with Royco who bootstraps the junior leg.
2. **Caliber Keyring enrollment** on policy 18 — off-chain workflow with Pareto.
3. **Caliber Royco role grants** for ST `deposit`/`redeem` and Kernel `syncTrancheAccounting`.
4. **Reference deposit through the Royco ST does not yet exist on mainnet.** The user's "reference mint tx" `0xbb9c2e…` is a Pareto-direct deposit by a Keyring'd EOA, not via the Royco ST `0x694A…`. The ST has zero deposits as of spec time. Pattern was validated against a real syrupUSDC ST mainnet deposit (`0xf1b63b…`) instead.
5. **No harvest action in scope.** If the ST has Royco campaign rewards, flag for a follow-up — current intent is deposit/withdraw/account only.

## Files in this Working Directory

- `progress.yaml` — pipeline state
- `specs.yaml` — full pool specs (deposit / withdraw split into `phase_1_request_redeem` + `phase_2_claim_redeem` / accounting flows, helpers, access matrix)
- `SUMMARY.md` — this file
