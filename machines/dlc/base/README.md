# DLC — Dialectic Liquid CUSHY (Base)

- Machine `0xa3A54CCC825fc9af87b6F2d9A2A4d0E67d641B8c`, hub caliber
  `0x51609da6D79088a70E033f290F3DF43b385f67f6`, share token DLC, accounting token USDC.
- Takes USDC in and subscribes/redeems CUSHY (Coinbase Tokenized Stablecoin Yield US Feeder
  Fund; Superstate is the transfer agent) through the caliber's attached Safe
  `0x2D30B1d886c7b6EFDF7E730F7fD50b3E57C72767`. See `docs/superstate-offchain/README.md`.
- CUSHY: monthly subscriptions, quarterly redemptions, monthly NAV.
- KeyValueStore `0x41bba463250c4c5513e1d42c03ef6f7b428be701` is deployed and bound to the
  caliber (`caliber()` checked 2026-10-28). The attached Safe is created and passes MakinaHQ/config's
  `scripts/attached_safe.py verify` (2026-10-29).
- CUSHY subscription, **deposit only**: `subscribe` sends USDC to the subscription address
  `0xd68b109b841aEa3527D382364DAD7a3F48a8a845` and books the claim in USDC; `account`
  reports it. No settle and no redemption yet, so CUSHY minted to the Safe is counted
  nowhere until settle is added.

## Before the first subscription

1. **Superstate allowlist, for the caliber and the Safe:**
   `setAllowed(addr, CUSHY, true)` on AllowList `0x157dAe58e832459CD2bD3A8007E50b2b1B3FCf1A`.
   CUSHY is a private instrument. `CUSHY.isAllowed` is false for both the caliber and the
   Safe (2026-10-29). Without it the mint cannot land: the USDC waits and the claim stays
   booked.
2. **Destinations, with Northern Trust (the fund administrator):** the Safe as purchase
   destination, and what happens to a rejected subscription. loopCUSHY subscribes through
   the same address, so each subscription must be attributed to the sending caliber and
   minted to that caliber's own Safe.

## Before settle and redemptions

3. **CUSHY price feed and base token, then settle.** There is no Chainlink CUSHY feed. Add
   an OracleRegistry route for CUSHY, then `addBaseToken(CUSHY)` from the
   riskManagerTimelock, then point the subscription at
   `superstate-offchain-subscription.yaml` (same id and `claim_kv_key`, add `fund_token`).
   The feed must:
   - report the strike NAV before a settle. A month of CUSHY accretion (~0.7%) exceeds the
     caliber's 0.5% position-loss limit, so a lagging feed makes settle revert;
   - accrue between monthly prints rather than step. A step trips the machine's
     `maxSharePriceChangeRate` (30%/yr) in `updateTotalAum`.
4. **Redemptions, with Northern Trust:** the flow differs from Superstate's off-chain
   redemption. Confirm it, the Safe as payout destination, and whether a caliber's
   `offchainRedeem` counts as a redemption request.
