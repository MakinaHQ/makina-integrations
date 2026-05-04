# VBILL Integration — Pending Steps to Mainnet

Caliber: `intMkSrRoyUSDC` mainnet `0x5476F4E23dAA093Ce6700e1026013c55F7AF9083`
dsToken: VBILL `0x2255718832bC9fD3bE1CaF75084F4803DA14FF01` (6 dec)
Onramp: `0x488EFd3eD474b205A0AaDe3732E4741432cba50B`
Offramp: `0x1eD617529d80AE87E6611f11D8de8532ECED42bC` → pays RLUSD
Pricing: Makina OracleRegistry `0xC388B72AB90Be82B230D919F9C05c87F9397f485` (routes VBILL→USD→USDC via Redstone)
Investor record (mainnet): `69723351665859488de7bccf`, country `VG`

## Status snapshot (2026-05-01)

|    |                                                                                                                                       |
| -- | ------------------------------------------------------------------------------------------------------------------------------------- |
| ✅ | Blueprint `blueprints/securitize/deposit.yaml` (`deposit` action)                                                                     |
| ✅ | Blueprint `blueprints/securitize/account.yaml` (`account` via OracleRegistry)                                                         |
| ✅ | Blueprint `blueprints/securitize/withdraw.yaml` (`redeem`, `redeem_relative`)                                                         |
| ✅ | Generic instruction `instructions/securitize.yaml`                                                                                    |
| ✅ | Position wired into `machines/intMkSrRoyUSDC/mainnet/caliber.yaml`                                                                    |
| ✅ | VBILL added to `token-lists/prod-token-list.json`                                                                                     |
| ✅ | Vtestnet caliber whitelist (tx `0x78834112…83e22`)                                                                                    |
| ✅ | **Securitize KYC of caliber on mainnet** — `isWallet(caliber)` returns true; investor `69723351…7bccf`, country `VG` (not restricted) |
| ⬜ | Mainnet rootfile compile + deploy                                                                                                     |
| ⬜ | First mainnet deposit (≥ 50,000 USDC) + accounting verification                                                                       |
| ⬜ | First mainnet redeem dry-run (small amount → RLUSD → curve-usdc-rlusd round-trip)                                                     |

---

## 1. End-to-end test on vtestnet

Vtestnet RPC: `https://virtual.mainnet.eu.rpc.tenderly.co/b150deab-7307-410e-af4f-8824ab7b02b4`

1. **Compile rootfile** with the new VBILL position (`/compile machines/intMkSrRoyUSDC/mainnet/instructions/...` or run the transpiler against the caliber).
2. **Fund caliber with USDC** (need ≥ `minSubscriptionAmount` = 50,000 USDC):
   - `tenderly_setStorageAt` on USDC `balanceOf` slot, or `tenderly_setBalance` + impersonate USDC whale + transfer.
3. **Run the deposit instruction** via spellcaster against the vtestnet:
   - Verify `swap()` succeeds.
   - Verify `VBILL.balanceOf(caliber)` increased by ~`liquidity_amount` (NAV currently 1:1).
4. **Run the accounting instruction**:
   - Verify reserved slot returns `vbill_balance * oracle_price / 1e8` ≈ deposited USDC amount.
5. **Sanity-check the position appears in the caliber's position list** with the right value.

Expected: round-trip USDC → VBILL → USDC-denominated position value, with no reverts and no rounding surprises (>0 dust is acceptable).

---

## 2. Securitize KYC of caliber on mainnet — DONE ✅

Securitize registered the caliber under investor `69723351665859488de7bccf`, country `VG`. Verified on mainnet:

```bash
$ cast call 0x897e452425bd1c860d7F9bc14eA045cBbC0fA0d4 \
    'isWallet(address)(bool)' 0x5476F4E23dAA093Ce6700e1026013c55F7AF9083 \
    --rpc-url https://mainnet.gateway.tenderly.co/4RJdRn4mYCONnOO2E9Jq6Q
true
```

`swap()` from the caliber will now satisfy the `investorExists` modifier on the on-ramp.

---

## 3. Pre-flight checks before first mainnet deposit

Re-verify these immediately before scheduling the first deposit, since some can drift:

```bash
RPC="https://mainnet.gateway.tenderly.co/4RJdRn4mYCONnOO2E9Jq6Q"
ONRAMP=0x488EFd3eD474b205A0AaDe3732E4741432cba50B
CALIBER=0x5476F4E23dAA093Ce6700e1026013c55F7AF9083
VBILL=0x2255718832bC9fD3bE1CaF75084F4803DA14FF01
USDC=0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48
ORACLE_REG=0xC388B72AB90Be82B230D919F9C05c87F9397f485

# Caliber must be a registered investor wallet
cast call 0x897e452425bd1c860d7F9bc14eA045cBbC0fA0d4 'isWallet(address)(bool)' $CALIBER --rpc-url $RPC
# Headless swap must be enabled
cast call $ONRAMP 'investorSubscriptionEnabled()(bool)' --rpc-url $RPC
# minSubscriptionAmount (could rise above 50,000 USDC)
cast call $ONRAMP 'minSubscriptionAmount()(uint256)' --rpc-url $RPC
# Onramp not paused
cast call $ONRAMP 'paused()(bool)' --rpc-url $RPC
# Caliber USDC balance ≥ minSubscriptionAmount
cast call $USDC 'balanceOf(address)(uint256)' $CALIBER --rpc-url $RPC
# OracleRegistry has a feed route registered for VBILL
cast call $ORACLE_REG 'isFeedRouteRegistered(address)(bool)' $VBILL --rpc-url $RPC
# Live VBILL→USDC price from the registry (≈1.00, in USDC's 6 decimals)
cast call $ORACLE_REG 'getPrice(address,address)(uint256)' $VBILL $USDC --rpc-url $RPC
```

**Slippage**: pick `min_out_amount` around `liquidity_amount * 0.999` (allows for tiny rounding from the NAV calc but rejects malicious rate moves).

---

## 4. Mainnet deployment

1. PR: blueprint files + instruction + caliber edit (already on `feat/vbill`).
2. Land the rootfile compile output to `machines/intMkSrRoyUSDC/mainnet/rootfiles/{date}-securitize-vbill.toml` (or whatever date-stamped name fits the convention).
3. Standard caliber rootfile-update flow.

---

## 5. First mainnet deposit + accounting verification

After Securitize confirms KYC + rootfile is live:

1. Trigger the deposit instruction (operator-side, normal makina flow) with `liquidity_amount = 50_000_000_000` (= 50,000 USDC) and `min_out_amount = 49_950_000_000` (0.1% slippage).
2. Watch the tx land. Expect:
   - USDC transfer caliber → onramp → custodian `0x8114d1FF…6799`
   - `Transfer(0x0, caliber, 50_000_000_000)` from VBILL (mint to caliber)
   - `Swap(...)` event from onramp
3. Run the accounting instruction. Expect ≈50,000 USDC value (modulo NAV ≠ 1.0).
4. Confirm the position appears in the fund's NAV calc.

---

## 6. Known caveats / things to watch

- **NAV rate drift**: The accounting blueprint reads the Redstone oracle, which tracks NAV. As NAV grows from T-bill yield, the position value grows accordingly — no rebasing on the token side.
- **Redemption pays out RLUSD, not USDC**: `SecuritizeOffRamp.redeem(amount, minOut)` at `0x1eD61752…42bc` swaps VBILL → RLUSD via a Ripple-operated `AllowanceLiquidityProvider`. There is no on-chain VBILL→USDC off-ramp — every Securitize off-ramp deployed today (BUIDL, VBILL, HLSCOPE) routes through RLUSD. After redeem, run a separate RLUSD→USDC swap (an existing `curve-usdc-rlusd.yaml` instruction handles this on `mteth`/`dbit`).
- **Redemption liquidity**: gated by `availableLiquidity() = min(LP wallet RLUSD balance, allowance)`. Currently ~4.7M RLUSD. For large exits, batch across multiple txs or coordinate with Ripple's market-maker desk to top up.
- **Country gating on redeem**: the off-ramp checks the redeemer's investor country against `restrictedCountries`. The investor we attached the caliber to (`a52a655d…30e8`) has country `BM` (Bermuda); the restricted set is currently empty for all common ISO codes tested. Re-verify before each redemption — Securitize can update this list.
- **Min subscription = 50,000 USDC**: every deposit must clear this. The blueprint doesn't enforce it (the contract does, with `MinSubscriptionAmountError`).
- **Oracle staleness**: Redstone updates on a heartbeat. If the feed goes stale, accounting still returns a value but it may be wrong. Consider monitoring `latestRoundData().updatedAt`.
- **Caliber-helper dependency**: the accounting blueprint relies on `0x6E2ED2f4…3d8D` exposing `int256ToUint256`. Verified on mainnet today; flag if that helper ever gets re-deployed.
