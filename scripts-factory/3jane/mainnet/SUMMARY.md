# 3Jane USD3 / sUSD3 — Integration Summary (dusd mainnet)

Network: Ethereum mainnet (chain id 1)
Protocol: 3Jane — tranched credit money market (MorphoCredit). Vaults are Yearn-V3 TokenizedStrategy ERC4626.
Machine: dusd · caliber `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC`
Scope: USD3 (senior) + sUSD3 (junior) positions, each deposit + withdraw. Verified 2026-06-02.

## Addresses

| Name           | Address                                      | Notes                               |
| -------------- | -------------------------------------------- | ----------------------------------- |
| USD3 (senior)  | `0x056B269Eb1f75477a8666ae8C7fE01b64dD55eCc` | ERC4626, `asset()`=USDC, 6-dec      |
| sUSD3 (junior) | `0xf689555121e529Ff0463e191F9Bd9d1E496164a7` | ERC4626, `asset()`=USD3, 6-dec      |
| USDC           | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` | 6-dec                               |
| Helper         | `0x82736F81A56935c8429ADdbDa4aEBec737444505` | (not used; we call vaults directly) |

Live prices (2026-06-02): 1 USD3 = 1.1556 USDC; 1 sUSD3 = 1.2615 USDC (= 1.0917 USD3 × 1.1556).

## USD3 position (senior) — synchronous ERC4626

- deposit USDC→USD3 (`deposit(assets,receiver)`), withdraw USD3→USDC (`redeem(shares,receiver,owner,maxLoss)`).
- `minCommitmentTime=0` (synchronous), whitelist **off**, `minDeposit=1000 USDC`.
- Position token (`position_tokens=[USD3]`); accounting `previewRedeem(USD3 bal)→USDC`. `affected_tokens=[USDC]` → caliber 3%/5% reconciliation on both legs.

## sUSD3 position (junior) — USDC-denominated, routed through USD3

sUSD3.asset() is USD3 (a position token, not base), so a direct sUSD3→USD3 redeem would fail the caliber's
loss reconciliation (`_checkPositionMaxDelta(absChange, 0, …)` reverts). The position is therefore
USDC-denominated and routes through USD3 atomically:

- deposit: `USDC → USD3 → sUSD3` (`affected=[USDC]`)
- withdraw: `start_cooldown` (when cooldown active) then `sUSD3 → USD3 → USDC` (`affected=[USDC]`)
- accounting: double `previewRedeem` (sUSD3→USD3→USDC), value in USDC (`position_tokens=[sUSD3]`).

### Redemption delay — NO KV needed

- 30-day initial **lock** per deposit (`lockedUntil`); startCooldown/redeem revert until it elapses.
- Optional **cooldown** (`cooldownDuration` from ProtocolConfig; **0 as of 2026-06-02** → redeem works directly).
  When >0: `startCooldown(shares)` → wait `cooldownEnd` → redeem within `withdrawalWindow` (2 days).
- KV is NOT used: `startCooldown` does **not** escrow shares (they stay in the caliber) and overwrites any prior
  cooldown, so `previewRedeem(balanceOf)` accounting is correct in every state and there's no in-flight request
  to track. (Differs from mGLOBAL/infinifi, which escrow tokens and therefore need KV.)
- **`availableDepositLimit(caliber)=0`** as of 2026-06-02 (junior subordination cap full) → sUSD3 deposits revert
  until the cap reopens.

## Liquidity constraint (USD3 redemption is NOT always atomic)

USD3 is a senior credit-market tranche — its USDC is lent out. Redemption is capped by
`USD3.availableWithdrawLimit` = `idleUSDC + redeemable waUSDC` (idle USDC = 0 as of 2026-06-02;
availableWithdrawLimit ≈ 711k of ~20.63M total, ~3.4% liquid). Exceeding it **reverts** the `USD3.redeem`.

Consequences:

- The USD3 position's own withdraw is capped by this limit.
- The sUSD3 `sUSD3→USD3→USDC` withdraw reverts if the redeemed amount exceeds USD3's available liquidity
  (the USD3→USDC leg). Atomic, so a revert strands nothing — operator retries smaller.
- **Use `max_loss_bps = 0`** so an illiquid/oversized redeem reverts cleanly instead of burning shares for less USDC.
- Size exits ≤ `availableWithdrawLimit` and use the `*_relative` (bps) variants to take partials and sequence them
  as liquidity frees up. Fully decoupling the junior exit (unwrap sUSD3→USD3, hold USD3, redeem later) would need
  USD3 to be a base token with a price feed — not available for 3Jane today.

## Files

| Path                                 | Role                                                                                                                                           |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `blueprints/3jane/deposit.yaml`      | `deposit` (USDC→USD3), `deposit_junior` (USDC→USD3→sUSD3)                                                                                      |
| `blueprints/3jane/withdraw.yaml`     | `redeem`/`redeem_relative` (USD3→USDC), `redeem_junior`/`redeem_junior_relative` (sUSD3→USD3→USDC), `start_cooldown`/`start_cooldown_relative` |
| `blueprints/3jane/account.yaml`      | `account` (single previewRedeem→USDC), `account_junior` (double→USDC)                                                                          |
| `instructions/3jane-usd3.yaml`       | USD3 position (deposit + account + redeem + redeem_relative)                                                                                   |
| `instructions/3jane-susd3.yaml`      | sUSD3 position (deposit + account + 2× cooldown + 2× redeem)                                                                                   |
| `machines/dusd/mainnet/caliber.yaml` | positions `keccak256("3jane.usd3")`, `keccak256("3jane.susd3")`, group_id 0                                                                    |
| `token-lists/prod-token-list.json`   | USD3 + sUSD3 entries (6-dec)                                                                                                                   |

## Not compiled

Per instruction, not transpiled. Compile with the repo transpiler when ready. RPC used for verification:
`https://mainnet.gateway.tenderly.co/222fLlhBgZC7ZknhONQXgI`.
