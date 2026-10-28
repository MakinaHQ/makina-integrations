# Superstate off-chain subscribe / redeem

For Superstate funds with no on-chain subscribe or redemption contract (for example USCC:
`supportedStablecoins(USDC)` = 0x0, `getRedemptionContract()` = 0x0). Not for USTB, which
has an atomic `subscribe()`.

Blueprints in [`blueprints/superstate/`](../../blueprints/superstate), one action per file:

| File             | Type       | What it does                                                                   |
| ---------------- | ---------- | ------------------------------------------------------------------------------ |
| `subscribe.yaml` | MANAGEMENT | stablecoin → Superstate subscription address; claim += amount                  |
| `redeem.yaml`    | MANAGEMENT | `offchainRedeem(amount)` burns fund tokens; claim += amount (fund-token units) |
| `settle.yaml`    | MANAGEMENT | pull the delivery from the attached Safe into the caliber and zero the claim   |
| `account.yaml`   | ACCOUNTING | report the claim, in its own token                                             |

Instruction files: `instructions/superstate-offchain-{subscription,redemption}.yaml`. One
position per direction, each with its own claim key. Both deliveries (the minted fund
token, the redemption payout) land on the caliber's
[attached Safe](../attached-safe/README.md), never on the caliber.

## Accounting: the claim only, until settle

`account` reports the claim and nothing else. A delivery sitting on the Safe is counted
nowhere until `settle` moves it into the caliber **and** zeroes the claim in the same tx,
so a forgotten settle cannot double count.

`settle` is a MANAGEMENT action, so the caliber's delta check is the evidence gate: the
claim's value must be covered by what arrives, within `maxPositionDecreaseLossBps`.
Settling before or short of the delivery reverts `MaxValueLossExceeded`. `settle` pulls the
Safe's **whole** balance of the delivery token, so no two positions of a caliber may settle
the same token from one Safe.

There is no write-down action: a write-off is a new root.

## Superstate setup (off-chain)

- Each caliber uses its **own Superstate subaccount**, which has its own USDC subscription
  address (`deposit_address`). Set the subaccount's purchase destination **and** payout
  address to the caliber's attached Safe.
- Superstate allowlists both the caliber and the Safe for the fund.
- Bring-up: run `create` and check the Safe first, then share its address with Superstate.

USCC: subscriptions are priced at the 5pm ET NAV; redemption payouts arrive T+1 (T+2 for
requests after 5pm ET).
