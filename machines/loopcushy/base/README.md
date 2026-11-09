# loopCUSHY — Dialectic Looped CUSHY (Base)

- Machine `0x29CF13a5D5C16fD7Ca78d7357F16A0F75b0E24F0`, hub caliber
  `0x1986e1eb669e95a9F4488E9Ba34378805B5c15F7`, share token loopCUSHY
  `0xE4c4AFf51Ad4FfbE8B09A1D3F7430Efd9Ee602FE`, accounting token USDC.
- Depositor `0x79d6c39F8bDC4fCB83cdDf83545C6B53f13Ab7fc` and Redeemer
  `0xFb6D2375A07AE6d98C5823b670cB9744Ed7cadc4`, both with whitelists on. Redeemer
  `minRedeemAmount` is 10 shares.
- KeyValueStore `0x98ef61f76cb7c16bebe1b36c43c9ed6971d7dcc9` is deployed and bound to the caliber.
- Sibling of DLC, Dialectic Liquid CUSHY (`machines/dlc/`).
- Attached Safe (`docs/attached-safe/README.md`) at `0x00506C4D0f4Ca19A4B3e17Fc0A53504C8843A1bf`,
  salt = caliber ++ 12 zero bytes. Not created yet. After `create`, run
  MakinaHQ/config's `scripts/attached_safe.py verify` before giving the address to a counterparty. `create` uses
  the Base CalldataEncoder `0x1a7f03da41d0d0a09476def4f7a922acc2d63d34`, which is not at the
  mainnet address.
- The caliber has no strategy positions yet: only the attached Safe's `create`.
- DUSD's Base caliber holds loopCUSHY shares (`machines/dusd/base/caliber.yaml`). It is
  whitelisted on the Depositor and Redeemer (checked 2026-10-29).

Read on-chain 2026-10-28, whitelist rechecked 2026-10-29.
