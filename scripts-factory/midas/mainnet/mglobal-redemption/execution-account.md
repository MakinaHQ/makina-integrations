# Execution Report — Midas mGLOBAL Redemption Vault: ACCOUNT

**Action**: account (read `redeemRequests(id)` + compute USD-18 value)
**Chain**: ethereum mainnet (chain_id 1)
**Vault proxy**: `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B`
**Caliber under test**: `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (dusd mainnet)
**Tenderly testnet**: `a8d4ee98-ff6c-4047-a0b4-201583af7725` (shared with execution-withdraw.md)
**Admin RPC**: `https://virtual.mainnet.eu.rpc.tenderly.co/a09bfee8-88e1-469c-9ffe-f806142a9a7f`

This report walks through every accounting state by directly reading the on-chain `redeemRequests(uint256)` getter. Each phase records the exact call, the decoded return tuple, and the USD-18 value the accounting blueprint should report. See `execution-withdraw.md` for the fork prep (data-feed override, greenlist grants, unpause).

---

## ABI tuple for `redeemRequests(uint256)`

```
(address sender, address tokenOut, uint8 status, uint256 amountMToken, uint256 mTokenRate, uint256 tokenOutRate)
```

Status enum (canonical): **`{Pending=0, Processed=1, Canceled=2}`** — no `None` variant. Distinguish "no request" via `sender == address(0)` (zero-init slot).

---

## Phase 1 — No request exists yet

State: testnet freshly forked, no `redeemRequest` calls made yet.

**Read call**

| Field | Value                                                                                                                      |
| ----- | -------------------------------------------------------------------------------------------------------------------------- |
| to    | `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B`                                                                               |
| data  | `0xe85ba3e9` + 32-byte id (`0x00…00`) → full: `0xe85ba3e90000000000000000000000000000000000000000000000000000000000000000` |

**Return**: all-zero struct (192 bytes of zeros):

```
sender       = 0x0000000000000000000000000000000000000000
tokenOut     = 0x0000000000000000000000000000000000000000
status       = 0 (Pending)   ← AMBIGUOUS without sender check
amountMToken = 0
mTokenRate   = 0
tokenOutRate = 0
```

> Status = 0 is identical to Pending and to "never written." Solidity zero-initialises
> the slot for unset keys. **Existence test MUST be `sender != address(0)`** — this is
> what the contract itself does in `_validateRequest`.

**Accounting blueprint decision**: KV `stored_id_plus_one == 0` (no request tracked) → value = 0.

---

## Phase 2 — Request pending (after `redeemRequest`)

State: caliber called `redeemRequest(USDC, 100e18, caliber)` (see execution-withdraw.md phase 3). Tx hash `0xd2f953234c8d75a89a98ca1c2bf105f995a8b3c7e37d50cbf5ff6c5a8879351c`. Snapshot ID `0xae46922bcf289a5a32cb65f1b4d1b26083d3c5f92f24701d72ea164cabe9b12b` taken after this.

**Read call**

| Field | Value                                                                        |
| ----- | ---------------------------------------------------------------------------- |
| to    | `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B`                                 |
| data  | `0xe85ba3e90000000000000000000000000000000000000000000000000000000000000000` |

**Return** (raw):

```
0x
000000000000000000000000  d1a1c248b253f1fc60eacd90777b9a63f8c8c1bc
000000000000000000000000  a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
00000000000000000000000000000000000000000000000000000000000000  00
0000000000000000000000000000000000000000000000  056bc75e2d63100000
000000000000000000000000000000000000000000000000  0de0b6b3a7640000
000000000000000000000000000000000000000000000000  0de0b6b3a7640000
```

**Decoded**:

| Field        | Value                                        | Notes                                                |
| ------------ | -------------------------------------------- | ---------------------------------------------------- |
| sender       | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` | caliber (set from the `recipient` arg)               |
| tokenOut     | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` | USDC                                                 |
| status       | `0`                                          | Pending                                              |
| amountMToken | `0x056bc75e2d63100000` = 100e18              | full input (fee=0)                                   |
| mTokenRate   | `0x0de0b6b3a7640000` = 1e18                  | snapshot from stub feed at request time              |
| tokenOutRate | `0x0de0b6b3a7640000` = 1e18                  | `tokensConfig[USDC].stable = true` → STABLECOIN_RATE |

**Existence test** (per blueprint logic): `sender != 0` ✓ AND `status == 0` ✓ → request is real and Pending.

### USD-18 value calculation for blueprint

Per spec, blueprint computes:

```
value_18 = amountMToken * mTokenRate_stored / 1e18
```

Substituting:

```
value_18 = 100e18 * 1e18 / 1e18 = 100e18
```

In Python:

```python
amount_m_token = 100 * 10**18
m_token_rate  = 10**18  # stored snapshot
value_18 = amount_m_token * m_token_rate // 10**18
# Result: 100_000_000_000_000_000_000
```

USD-18 (`100e18`) is the conservative best-estimate the accounting blueprint reports.
This matches the realised settlement (Phase 3) when admin uses the same rate.

### Pricing source comparison

| Source                                  | Value                             | Reliable? |
| --------------------------------------- | --------------------------------- | --------- |
| Live `mTokenDataFeed.getDataInBase18()` | reverts (`DF: feed is unhealthy`) | NO        |
| `Request.mTokenRate` (stored snapshot)  | 1e18                              | YES       |

The accounting blueprint MUST use the stored field, not a live feed read.

---

## Phase 3 — Request processed (after admin `approveRequest`)

State: from the snapshot state of Phase 2, admin called `approveRequest(0, 1e18)`. Tx hash `0x57c63d1053e2ea4215a2ec740e3cb9f215740b80a30606e0b58c1ab3b11f40f1`.

**Approve call data** (informational, not on caliber path):

| Field | Value                                                                                                                                                                          |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| from  | `0x5fd792B3a904832DBB63FfD0741949B44f88cd4F` (test EOA holding `M_GLOBAL_REDEMPTION_VAULT_ADMIN_ROLE`)                                                                         |
| to    | `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B`                                                                                                                                   |
| data  | `0x2c0a90a900000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000de0b6b3a7640000` (requestId=0, newMTokenRate=1e18) |

**Read call after approval**: same as Phase 2, `redeemRequests(0)`.

**Return** (raw):

```
0x
000000000000000000000000  d1a1c248b253f1fc60eacd90777b9a63f8c8c1bc
000000000000000000000000  a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
00000000000000000000000000000000000000000000000000000000000000  01
0000000000000000000000000000000000000000000000  056bc75e2d63100000
000000000000000000000000000000000000000000000000  0de0b6b3a7640000
000000000000000000000000000000000000000000000000  0de0b6b3a7640000
```

**Decoded changes vs Phase 2**:

| Field        | Before                          | After                                                           |
| ------------ | ------------------------------- | --------------------------------------------------------------- |
| sender       | caliber                         | **caliber (unchanged)** ✓                                       |
| tokenOut     | USDC                            | USDC                                                            |
| status       | 0 (Pending)                     | **1 (Processed)**                                               |
| amountMToken | 100e18                          | 100e18                                                          |
| mTokenRate   | 1e18 (snapshot at request time) | **1e18 (overwritten with `newMTokenRate`)** — see callout below |
| tokenOutRate | 1e18                            | 1e18                                                            |

> Per `_approveRequest`: `request.mTokenRate = newMTokenRate;` is written before
> the storage put. The `mTokenRate` field stored after settlement is the rate
> admin used, NOT the original snapshot. In this test they happen to match (both
> 1e18). If admin had used e.g. 1.05e18, the post-state `mTokenRate` would be 1.05e18.

**Accounting blueprint decision**: status != 0 → value = 0 (the caliber's USDC balance now reflects the realised proceeds, accounted separately by the caliber's native asset registry).

### Realised USDC delivery verification

| Metric                | Before approve               | After approve                                 | Delta             |
| --------------------- | ---------------------------- | --------------------------------------------- | ----------------- |
| caliber USDC balance  | 0                            | `0x5f5e100` = 100,000,000 (= 100 USDC, 6 dec) | +100 USDC ✓       |
| vault mGLOBAL balance | 150e18 (id 0: 100, id 1: 50) | `0x2b5e3af16b1880000` = 50e18 (just id 1)     | −100e18 (burnt) ✓ |

Formula check (matches contract `_truncate((amountMToken * newMTokenRate) / tokenOutRate, 6)`):

```python
amount_m_token = 100 * 10**18
new_m_token_rate = 10**18
token_out_rate = 10**18
# value in 18 decimals
value_18 = amount_m_token * new_m_token_rate // token_out_rate   # 100e18
# truncate to USDC's 6 decimals
amount_usdc = value_18 // 10**12
# Result: 100_000_000
```

On-chain: `100_000_000`. Match exact ✓.

---

## Phase 4 — Request canceled (after admin `rejectRequest`)

State: testnet reverted back to the snapshot from end of withdraw phase 5 (two pending requests, id 0 and id 1). Then admin called `rejectRequest(0)`. Tx hash `0x191d931aace4009e48bd9f4d0475a122322eed72befc6811686a517199052cfd`.

**Reject call data**:

| Field | Value                                                                                      |
| ----- | ------------------------------------------------------------------------------------------ |
| from  | `0x5fd792B3a904832DBB63FfD0741949B44f88cd4F` (admin)                                       |
| to    | `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B`                                               |
| data  | `0x2d7788db0000000000000000000000000000000000000000000000000000000000000000` (requestId=0) |

**Read call after rejection**: same as Phase 2, `redeemRequests(0)`.

**Return** (raw):

```
0x
000000000000000000000000  d1a1c248b253f1fc60eacd90777b9a63f8c8c1bc
000000000000000000000000  a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
00000000000000000000000000000000000000000000000000000000000000  02
0000000000000000000000000000000000000000000000  056bc75e2d63100000
000000000000000000000000000000000000000000000000  0de0b6b3a7640000
000000000000000000000000000000000000000000000000  0de0b6b3a7640000
```

**Decoded changes vs Phase 2**:

| Field        | Before      | After            |
| ------------ | ----------- | ---------------- |
| status       | 0 (Pending) | **2 (Canceled)** |
| (all others) | unchanged   | unchanged        |

> `rejectRequest` only flips status; it does NOT refund the escrowed mGLOBAL.

**Accounting blueprint decision**: status != 0 → value = 0; reset KV. Off-chain monitoring required to detect this state and trigger admin `withdrawToken` for recovery.

### Escrow NOT refunded — verified

| Metric                  | After cancel                    | Expected                                      |
| ----------------------- | ------------------------------- | --------------------------------------------- |
| caliber mGLOBAL balance | `0x2e141ea081ca080000` = 850e18 | 1000 − 100 (id 0) − 50 (id 1) = 850e18 ✓      |
| vault mGLOBAL balance   | `0x821ab0d4414980000` = 150e18  | escrow for id 0 (100) + id 1 (50) **stays** ✓ |

The escrowed 100e18 mGLOBAL for the canceled request id=0 remains in the vault — confirming the documented risk in `progress.yaml` ("Admin can rejectRequest → status=Canceled and escrowed mGLOBAL is NOT auto-refunded").

---

## Phase 5 — Pricing source comparison summary

| Read                                                                            | Live behaviour                                                                                              |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `mTokenDataFeed.getDataInBase18()` (proxy `0xb468…139E`, selector `0x63692905`) | Reverts `DF: feed is unhealthy` on mainnet; works only because we stubbed the implementation on the testnet |
| `redeemRequests(id).mTokenRate`                                                 | Always readable; equals the snapshot at request time (Pending) or the admin's `newMTokenRate` (Processed)   |

**Conclusion**: the accounting blueprint must read `redeemRequests(id).mTokenRate` and never call the live data feed.

---

## Storage slot reference (caliber doesn't need these, but useful for debugging)

The `redeemRequests` mapping is laid out under the `RedemptionVault` slot range; each `Request` occupies 6 sequential slots:

| Offset | Field        | Type    | Encoding             |
| ------ | ------------ | ------- | -------------------- |
| 0      | sender       | address | right-aligned in 32B |
| 1      | tokenOut     | address | right-aligned in 32B |
| 2      | status       | uint8   | low byte             |
| 3      | amountMToken | uint256 | full slot            |
| 4      | mTokenRate   | uint256 | full slot            |
| 5      | tokenOutRate | uint256 | full slot            |

The blueprint reads via the auto-generated getter (selector `0xe85ba3e9`), so no slot computation is needed at runtime.

---

## Accounting blueprint state-machine summary

```
KV (stored_id_plus_one) │ status │ sender         │ value reported │ action
────────────────────────┼────────┼────────────────┼────────────────┼──────────────────────────
0 (sentinel: none)      │ —      │ —              │ 0              │ noop
N (stored_id = N-1)     │ 0      │ caliber        │ amount*rate/1e18 │ keep KV
N                       │ 0      │ address(0)     │ 0              │ defensive: reset KV (shouldn't happen)
N                       │ 1      │ caliber        │ 0              │ reset KV (settled — USDC already on caliber)
N                       │ 2      │ caliber        │ 0              │ reset KV (canceled — off-chain recovery required)
```

Per the spec correction in `progress.yaml`:

- "Request exists & is pending" requires BOTH `status == 0` AND `sender != 0`.
- Live `mTokenDataFeed` is unusable; use the stored `mTokenRate` field.
- Settlement may update `mTokenRate` to admin's chosen rate, but by then status flips so it doesn't affect the value report.
