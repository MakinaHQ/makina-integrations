# DLC — Dialectic Liquid CUSHY (Base)

- Machine `0xa3A54CCC825fc9af87b6F2d9A2A4d0E67d641B8c`, hub caliber
  `0x51609da6D79088a70E033f290F3DF43b385f67f6`, share token DLC, accounting token USDC.
- Takes USDC in and subscribes/redeems CUSHY (Coinbase Tokenized Stablecoin Yield US Feeder
  Fund; Superstate is the transfer agent) through the caliber's attached Safe
  `0x2D30B1d886c7b6EFDF7E730F7fD50b3E57C72767`. See `docs/superstate-offchain/README.md`.
- CUSHY: monthly subscriptions, quarterly redemptions, monthly NAV.
- KeyValueStore `0x41bba463250c4c5513e1d42c03ef6f7b428be701` is deployed and bound to the
  caliber (`caliber()` checked 2026-10-28).

## Go-live prerequisites

1. **CUSHY price feed and base token.** There is no Chainlink CUSHY feed. Add an
   OracleRegistry route for CUSHY, then `addBaseToken(CUSHY)` from the riskManagerTimelock.
   The feed must:
   - report the strike NAV before a settle. A month of CUSHY accretion (~0.7%) exceeds the
     caliber's 0.5% position-loss limit, so a lagging feed makes settle revert;
   - accrue between monthly prints rather than step. A step trips the machine's
     `maxSharePriceChangeRate` (30%/yr) in `updateTotalAum`.
2. **Deposit address.** CUSHY subscriptions go through **Northern Trust** (the fund
   administrator), not Superstate. Get the USDC subscription address from them. The CUSHY
   positions in `caliber.yaml` are commented out until then: uncomment them and set
   `deposit_address`.
3. **Superstate allowlist, for the caliber and the Safe:**
   `setAllowed(addr, CUSHY, true)` on AllowList `0x157dAe58e832459CD2bD3A8007E50b2b1B3FCf1A`.
   CUSHY is a private instrument. The caliber's current grant,
   `setAllowed(caliber, 0x0, true)`, covers public instruments only, so
   `CUSHY.isAllowed(caliber)` is false (2026-10-26).
4. **Destinations and redemptions, with Northern Trust:** the Safe as purchase and payout
   destination, whether a caliber's `offchainRedeem` counts as a redemption request, and
   what happens to a rejected subscription.
