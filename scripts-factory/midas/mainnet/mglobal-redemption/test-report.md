# Blueprint Test Report — Midas mGLOBAL Redemption (Re-run after Option B refactor)

**Instruction**: `/workspace/machines/dusd/mainnet/instructions/midas-mglobal-redemption.yaml`
**Machine**: `dusd`
**Network**: `mainnet`
**Tenderly Testnet ID**: `48f42712-156d-42c3-a8e8-34e06ee0665e`
**Admin RPC**: `https://virtual.mainnet.eu.rpc.tenderly.co/ed37611b-de57-4ac9-a5c5-1aae7eaf39be`
**Fork block**: `0x17f03af`
**Date**: 2026-05-18
**Rootfile**: `/workspace/machines/dusd/mainnet/rootfiles-test/test-output.toml`
**Merkle root**: `0x32854e566d0a296630821c5b0ed519f268019c4b06eaaa18ba5f94ccc74f939d`

## Summary

Third end-to-end re-run, this time validating the **Option B refactor** of both
`blueprints/midas/withdraw.yaml` and `blueprints/midas/account.yaml`. Compared
with the second run (`0x7ab58b85…dd1a`), the blueprints now:

1. Store the **raw `requestId`** in KV (no `+1` sentinel offset).
2. Disambiguate "KV=0 → never written" vs. "KV=0 → tracking real id 0" by
   reading the on-chain `Request` struct and requiring **both**
   `status == Pending(0)` AND `sender != address(0)` for the request to be
   considered in-flight. The withdraw guard now reverts via
   `revertIfTrue(in_flight)` instead of the old `revertIfFalse(eq(kv, 0))`.

The accounting `max`/`sub` decoding gymnastics (used previously to recover the
request id from `KV - 1` without underflow on KV=0) are gone. The account flow
is one step shorter for ids != 0 and behaviourally identical for ids == 0.

All seven phases pass on a fresh Tenderly fork. The new KV trace is
**0 → 0 → 0 → revert → 0 → 0 → 1 → 1** (was **0 → 1 → 1 → revert → 0 → 0 → 2 → 2**
under the +1 sentinel). Behavioural assertions (slot 0 == raw escrowed
mGLOBAL, USDC payout on approve, no auto-refund on reject, position USD value
via base-token oracle) are unchanged.

### Refactor verification (call-trace evidence)

- Account flow has **0** `add`, `max`, `sub`, or `mulDiv` calls inside
  WeirollVM. Only `eq` (×2 — `eq(status, 0)` on math_helper and `eq(sender,
  bytes32(0))` on bytes32_helper), `not`, `and`, `ternary`, and `mul` (×2).
- Withdraw flow's pre-flight guard runs **exactly** the new sequence:
  `kv.get → redeemRequests → extract(sender) → extract(status) → eq(status,0)
  → eq(sender, 0) → not → and → revertIfTrue`. The old single-step
  `revertIfFalse(eq(kv,0))` is gone.
- Phase 4 revert fires at `revertIfTrue(true)` at absolute_position 401 in the
  Tenderly trace, confirmed via `search_vnet_call_trace` with
  `function_name=revertIfTrue`.
- Phase 1 first-ever-withdraw correctness (KV=0 + sender=0 must permit a new
  request) is validated by **Phase 2**: a fresh testnet with no prior request
  ran `redeem_request` successfully, proving the guard does NOT spuriously
  reject when both KV and on-chain sender are zero.

## Contract Addresses

| Contract                                     | Address                                      |
| -------------------------------------------- | -------------------------------------------- |
| Caliber (dusd mainnet)                       | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` |
| Machine (dusd hub)                           | `0x6b006870C83b1Cd49E766Ac9209f8d68763Df721` |
| Mechanic                                     | `0x425BbC2cfF0c7E7960baA9BaC2f0Cb67B41d3beF` |
| Midas mGLOBAL vault proxy                    | `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B` |
| Midas mGLOBAL vault impl                     | `0xf687E76e3d62d62fE6F6A7f66ce9faE21df6438d` |
| mGLOBAL token                                | `0x7433806912Eae67919e66aea853d46Fa0aef98A8` |
| USDC                                         | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` |
| requestRedeemer (Midas)                      | `0xaB9dA7953D82d81006639A6f87883d59594918b9` |
| mTokenDataFeed proxy                         | `0xb468A6F63868cB6C6D99105EDfbe73d6B21f139E` |
| mTokenDataFeed impl (stubbed)                | `0x94Cd5b8904c1F1426f9408eE5c98b789c6a864c6` |
| USDC dataFeed proxy                          | `0x3aAc6fd73fA4e16Ec683BD4aaF5Ec89bb2C0EdC2` |
| USDC dataFeed impl (stubbed)                 | `0xB93b94c99c6Df85cc9FaA338e68c27c72484251e` |
| MidasAccessControl                           | `0x0312a9d1fF2372dDeDCBB21e4B6389AfC919AC4b` |
| KeyValueStore (dusd)                         | `0xa81fC382489F9560211AB15aD87f001b98C92E91` |
| Test admin EOA (Midas vault)                 | `0x5fd792B3a904832DBB63FfD0741949B44f88cd4F` |
| Dialectic AccessManager                      | `0x0fCEfa3f1047F35521A49cD8B06faBd588665d7F` |
| Dialectic Admin (role 0)                     | `0x62244c74e1d09b3d86ef7342d354b5d7770bde10` |
| OracleRegistry                               | `0xC388B72AB90Be82B230D919F9C05c87F9397f485` |
| Chainlink USDC/USD feed (reused for mGLOBAL) | `0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6` |
| Caliber riskManagerTimelock                  | `0x38542447c49D24e617fc06113295D7AaA3BEc4b6` |
| math_helper                                  | `0x3D623B199E290358416415eA7e05B635E442e3c0` |
| boolean_helper                               | `0x00c93e3b09Ca2f544487d4298339765EadCD8353` |
| bytes32_helper                               | `0x74DC739B8F98ad0F76Cd8900695DD8D5083E45D3` |
| caliber_helper                               | `0x6E2ED2f457c41F38556Ab0c2b1185cc9e6563d8D` |
| context_helper                               | `0x0f431322E1fF2500D4C5a4E090A7Da7344F953BE` |

## Execution Steps (fork prep)

| Step                                                     | Status | Details                                                                        |
| -------------------------------------------------------- | ------ | ------------------------------------------------------------------------------ |
| Create fresh Tenderly testnet                            | PASS   | `48f42712…0665e` forked at block `0x17f03af`.                                  |
| Compile rootfile                                         | PASS   | `transpiler` produced root `0x32854e56…f939d` (new vs `0x7ab58b85…dd1a`).      |
| Update root on testnet                                   | PASS   | `dev-update-root` via spellcaster CLI.                                         |
| Stub mTokenDataFeed impl (returns 1e18)                  | PASS   | `tenderly_setCode` on `0x94Cd…64c6`.                                           |
| Stub USDC dataFeed impl (returns 1e18)                   | PASS   | `tenderly_setCode` on `0xB93b…251e`.                                           |
| Greenlist caliber                                        | PASS   | `tenderly_setStorageAt` on `_roles[GREENLISTED].members[caliber]` (slot 101).  |
| Greenlist vault                                          | PASS   | Same, for the vault address.                                                   |
| Grant `M_GLOBAL_REDEMPTION_VAULT_ADMIN_ROLE` to test EOA | PASS   | Storage write at slot 101.                                                     |
| Unpause selector `0x15571a04`                            | PASS   | `unpauseFn(bytes4)` from test admin (tx `0xad7ac8c1…`).                        |
| Grant role 1 to Dialectic admin                          | PASS   | `grantRole(1, admin, 0)` on AccessManager (tx `0xc45f57ab…`).                  |
| Set feed route mGLOBAL                                   | PASS   | `setFeedRoute(mGLOBAL, USDC/USD, 315360000, 0, 0)` (tx `0x6bd2d42d…`).         |
| Add mGLOBAL as base token                                | PASS   | `caliber.addBaseToken(mGLOBAL)` from `riskManagerTimelock` (tx `0x12e142e4…`). |
| Fund caliber                                             | PASS   | 10000 ETH + 1000e18 mGLOBAL.                                                   |
| Fund mechanic                                            | PASS   | 10000 ETH for gas.                                                             |
| Fund requestRedeemer                                     | PASS   | 100,000 USDC + MAX allowance to vault (tx `0x0e826144…`).                      |

## Test Results

### Phase 1 — `account` with no request (KV=0)

| Metric                      | Value                                                                |
| --------------------------- | -------------------------------------------------------------------- |
| Status                      | PASS                                                                 |
| Transaction                 | `0xa45ca25d019c44274ac6c613c296c22d3a1350823e7bda3049ad8c1ec45a0f98` |
| KV before / after           | `0` / `0`                                                            |
| `getPosition(100000000001)` | `(0, 0, false)` — no positions on caliber yet                        |
| Receipt status              | 1 (success)                                                          |

Note: on a fresh caliber the spellcaster `account-positions` does not visit
the midas position (no positions tracked yet by the caliber's position set —
positions are created via `manage-position`). This is operationally identical
to a no-op accounting call and demonstrates that no revert occurs when KV=0 +
no request exists. The critical "first-ever request" check is exercised by
Phase 2 below (which calls the withdraw guard with KV=0 and zero-init struct).

**Command:**

```bash
DEV_MAINNET_RPC_URL="<RPC_URL>" \
TENDERLY_ACCOUNT_SLUG="<ACCOUNT>" TENDERLY_PROJECT_SLUG="<PROJECT>" \
TENDERLY_API_KEY="<API_KEY>" TENDERLY_MAINNET_TESTNET_ID="<TESTNET_ID>" \
spellcaster --config /workspace/machines-local.toml --dev \
  --machine dusd --caliber mainnet \
  account-positions
```

### Phase 2 — `redeem_request` 100e18 (first-ever, KV=0, struct zero)

| Metric               | Value                                                                |
| -------------------- | -------------------------------------------------------------------- |
| Status               | PASS                                                                 |
| Transaction          | `0xea457888a54197bb9af3c31414858e44548fd58f42f813c9b62b4f4f1dba2887` |
| Gas used             | 912,705                                                              |
| Receipt status       | 1 (success)                                                          |
| KV before / after    | `0` → **`0`** (raw next_id=0; +1 sentinel removed)                   |
| Caliber mGLOBAL      | `1000e18` → `900e18`                                                 |
| Vault mGLOBAL        | `0` → `100e18` (escrowed)                                            |
| `currentRequestId()` | `0` → `1`                                                            |
| `redeemRequests(0)`  | `(caliber, USDC, status=0, 100e18, 1e18, 1e18)`                      |

**Critical assertion (Phase 1 correctness):** before this tx, KV was 0 AND
`redeemRequests(0).sender == address(0)` (zero-init struct). The new guard
sequence runs:

1. `kv.get` → `0`
2. `vault.redeemRequests(0)` → zero-init struct (sender=0, status=0)
3. `eq(status, 0)` → `true`
4. `eq(sender_b32, 0x0…)` → `true`
5. `not(true)` → `false` (sender_is_nonzero = **false**)
6. `and(true, false)` → `false` (in_flight = **false**)
7. `revertIfTrue(false)` → no revert ✓

The transaction proceeded past the guard, captured `currentRequestId() = 0`,
submitted the request, and wrote `kv.set(key, 0)` (storing the raw next_id).
**This is the regression-prevention check for the Option B refactor:** under
the old `revertIfFalse(eq(kv,0))` design, a hypothetical "KV=0 means
nothing-tracked" worked, but Option B's struct-based check must also permit
the first request — and it does.

**Command:**

```bash
spellcaster --config /workspace/machines-local.toml --dev \
  --machine dusd --caliber mainnet \
  manage-position \
    --protocol midas \
    --action redeem_request \
    --token "mGLOBAL Redemption Request" \
    --inputs 0x0000000000000000000000000000000000000000000000056bc75e2d63100000
```

### Phase 3 — `account` while Pending (KV=0, struct says in-flight)

| Metric                                                | Value                                                                   |
| ----------------------------------------------------- | ----------------------------------------------------------------------- |
| Status                                                | PASS                                                                    |
| Transaction                                           | `0xd5ede7337a7ce91780c9d9dcc9f0bd2b84ce4b92437080cdb9d98e14401603c7`    |
| KV before / after                                     | `0` / **`0`** (no-op writeback: `tracked_id=0 * is_pending_mask=1 = 0`) |
| Slot 0 (WeirollVM `mul(100e18, 1)`)                   | `100000000000000000000` = 100e18 mGLOBAL (raw)                          |
| Caliber oracle conversion `mulDiv(100e18, 1e6, 1e18)` | `100000000` (100 USDC)                                                  |
| `getPosition(100000000001).value`                     | `100000000` (100 USDC, 6 dec)                                           |
| `display-positions` value                             | `100 USDC`                                                              |

**Call-trace assertions (Tenderly `search_vnet_call_trace`, op_id `0686f56d-…`):**

- 1× `redeemRequests(0)` on vault proxy → returns the Pending struct.
- 3× CALL to `caliber_helper` (`extractElementFromStaticTuple`) — sender,
  status, amountMToken.
- 1× `eq` on math_helper: `eq(status=0, 0) = true`.
- 1× `eq` on bytes32_helper: `eq(sender=caliber, bytes32(0)) = false`.
- 1× `not(false) = true` on boolean_helper.
- 1× `and(true, true) = true` on boolean_helper.
- 1× `ternary(true, 1, 0) = 1` on math_helper (is_pending_mask).
- 2× `mul` on math_helper:
  - `mul(100e18, 1) = 100e18` — slot 0 escrowed amount.
  - `mul(0, 1) = 0` — KV writeback (`tracked_id * mask`).
- 0× `mulDiv` inside WeirollVM. Caliber-side mulDivs come from oracle scaling.
- 0× `add`, 0× `max`, 0× `sub` — confirmed via `function_name` filter.
  The only `add` matches are Chainlink `EACAggregatorProxy.addPhase` /
  `addPhaseIds` (unrelated to the blueprint).

### Phase 4 — One-in-flight guard (expected revert via new struct check)

| Metric                           | Value                                                            |
| -------------------------------- | ---------------------------------------------------------------- |
| Status                           | PASS (revert as expected)                                        |
| Tenderly operation_id            | `29413635-0ca8-4c05-ab36-5495ae068efb`                           |
| Revert location                  | `boolean_helper.revertIfTrue(true)` at absolute_position **401** |
| KV read                          | `0` (unchanged from Phase 3)                                     |
| `redeemRequests(0)` re-read      | `(caliber, USDC, status=0, 100e18, 1e18, 1e18)` — still Pending  |
| `eq(status=0, 0)`                | `true` (tracked_status_is_pending)                               |
| `eq(sender=caliber, bytes32(0))` | `false` (tracked_sender_is_zero)                                 |
| `not(false)`                     | `true` (tracked_sender_is_nonzero)                               |
| `and(true, true)`                | `true` (tracked_is_in_flight)                                    |
| `revertIfTrue(true)`             | **REVERT**                                                       |
| KV after                         | `0` (no state change)                                            |

**This is the headline check.** The revert path is the new struct-based guard,
NOT the old `revertIfFalse(eq(kv, 0))`. Verified end-to-end via Tenderly's
search_vnet_call_trace:

```
absolute_position 358: DELEGATECALL redeemRequests(0) → (caliber, USDC, 0, 100e18, 1e18, 1e18)
absolute_position 392: CALL not(false)        → true   (sender_is_nonzero)
absolute_position 397: CALL and(true, true)   → true   (in_flight)
absolute_position 401: CALL revertIfTrue(true) → revert (execution reverted)
```

Spellcaster surfaces the revert at the simulation layer and refuses to send
the transaction (`Error: transaction reverted in simulation`).

**Command (reverts):**

```bash
spellcaster --config /workspace/machines-local.toml --dev \
  --machine dusd --caliber mainnet \
  manage-position --protocol midas --action redeem_request \
  --token "mGLOBAL Redemption Request" \
  --inputs 0x0000000000000000000000000000000000000000000000056bc75e2d63100000
# Error: transaction reverted in simulation
```

### Phase 4b — `redeem_request_relative` shares the same guard

After Phase 7 (KV=1, request 1 Pending), an attempt to call the relative
variant with `bps_to_redeem=5000` was executed via spellcaster. Result:
revert at the **same** trace coordinate, confirming both withdraw actions
share the same struct-based guard sequence.

| Metric                      | Value                                                            |
| --------------------------- | ---------------------------------------------------------------- |
| Status                      | PASS (revert as expected)                                        |
| Tenderly operation_id       | `70ac7d06-6f90-4cec-ab27-77990bd0d21c`                           |
| Revert location             | `boolean_helper.revertIfTrue(true)` at absolute_position **401** |
| KV after                    | `1` (unchanged)                                                  |
| `redeemRequests(1)` re-read | `(caliber, USDC, 0, 50e18, 1e18, 1e18)` — still Pending          |

**Command (reverts):**

```bash
spellcaster --config /workspace/machines-local.toml --dev \
  --machine dusd --caliber mainnet \
  manage-position --protocol midas --action redeem_request_relative \
  --token "mGLOBAL Redemption Request (relative)" \
  --inputs 0x0000000000000000000000000000000000000000000000000000000000001388
# Error: transaction reverted in simulation
```

### Phase 5 — Settlement (`approveRequest`) + `account`

Snapshot `0x903ac1152f849bc3195e5e2574a72d379978ef84597803ca77324ec6081bf226`
taken before the admin tx.

| Metric                       | Value                                                                |
| ---------------------------- | -------------------------------------------------------------------- |
| `approveRequest(0, 1e18)` tx | `0xe2f21672d3b25a5e2e573e5de9e76cfa24a3f3d562429e6818cfa6592cc54d0f` |
| `redeemRequests(0).status`   | `0` → `1` (Processed)                                                |
| Vault mGLOBAL                | `100e18` → `0` (burnt)                                               |
| Caliber USDC                 | `0` → `100,000,000` (100 USDC delivered)                             |
| `account` tx (CLI)           | `0xed44e5748c16c87530a240051c3fc7e04984af06533d621a6ea9de0df7c545d7` |
| KV after `account`           | `0` (was 0; `0 * 0 = 0` — no-op since status=1 → mask=0)             |
| `getPosition.value`          | `0`                                                                  |

The KV writeback after Phase 5 evaluates to `tracked_id=0 * mask=0 = 0`. With
Option B the cleanup is identical regardless of whether tracked_id was 0 or
non-zero, because the mask multiplication zeroes either case.

### Phase 6 — Cancellation (revert + `rejectRequest`) + `account`

Reverted vnet to snapshot `0x903ac1…26`, then admin called `rejectRequest`.

| Metric                     | Value                                                                                                                                          |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Post-revert state          | KV=0, Request 0 Pending, vault=100e18, caliber USDC=0                                                                                          |
| `rejectRequest(0)` tx      | `0xa6f5b06d90bf38b482ee3757d3264ed80e6bcc192fa71d0931919d291bebf298`                                                                           |
| `redeemRequests(0).status` | `0` → `2` (Canceled)                                                                                                                           |
| Vault mGLOBAL              | still `100e18` (NOT auto-refunded — documented risk)                                                                                           |
| `account` tx (CLI)         | `0xed44e5748c16c87530a240051c3fc7e04984af06533d621a6ea9de0df7c545d7` (same hash as Phase 5 — deterministic encoding at same post-revert block) |
| KV after `account`         | `0` (was 0; mask=0 since status=2)                                                                                                             |
| `getPosition.value`        | `0`                                                                                                                                            |

### Phase 7 — Cycle freshness (50e18 redeem + account)

Following Phase 6 (which left KV=0, status=Canceled, currentRequestId=1).

| Metric                                    | Value                                                                |
| ----------------------------------------- | -------------------------------------------------------------------- |
| `redeem_request 50e18` tx                 | `0x34aa54aa89fc801798f02b7a0e506c1377280005af41a2ec99d56fd5186b3b15` |
| Receipt status                            | 1 (success)                                                          |
| Gas used                                  | 891,595                                                              |
| `currentRequestId()`                      | `1` → `2`                                                            |
| `redeemRequests(1)`                       | `(caliber, USDC, 0, 50e18, 1e18, 1e18)`                              |
| KV (post-redeem)                          | `0` → **`1`** (raw next_id=1; +1 sentinel removed)                   |
| `account` tx                              | `0x44870edafe34346c1c5557bc6b481a25bc37ba5c9b7df2cedee994a97c4fe9c4` |
| Slot 0 (WeirollVM `mul(50e18, 1)`)        | `50000000000000000000` = 50e18 mGLOBAL                               |
| Caliber oracle `mulDiv(50e18, 1e6, 1e18)` | `50000000` (50 USDC)                                                 |
| `getPosition.value`                       | `50000000` (50 USDC)                                                 |
| `display-positions` value                 | `50 USDC`                                                            |
| KV after `account`                        | `1` (no-op: `mul(1, 1) = 1`)                                         |

The guard correctly **permitted** the new redeem despite KV=0, because
`redeemRequests(0).status == 2 (Canceled)` → `eq(status, 0) == false` →
`and(false, …) = false` → `revertIfTrue(false)` no-op.

**Phase 7 account math_helper trace (op_id `557670f8-…`):**

- `eq(0, 0) = true`
- `ternary(true, 1, 0) = 1`
- `mul(50e18, 1) = 50e18` (slot 0)
- `mul(1, 1) = 1` (KV writeback — raw tracked_id, not tracked_id+1)

**Command (redeem):**

```bash
spellcaster --config /workspace/machines-local.toml --dev \
  --machine dusd --caliber mainnet \
  manage-position --protocol midas --action redeem_request \
  --token "mGLOBAL Redemption Request" \
  --inputs 0x000000000000000000000000000000000000000000000002b5e3af16b1880000
```

**Final `display-positions` output:**

```
========================================
# total AUM: stale accounting
========================================

╭──────────────┬──────────┬────────────────────────────┬─────────╮
│      ID      │ PROTOCOL │           TOKEN            │  VALUE  │
├══════════════┼══════════┼════════════════════════════┼═════════┤
│ 100000000001 │ midas    │ mGLOBAL Redemption Request │ 50 USDC │
╰──────────────┴──────────┴════════════════════════════┴─────────╯
```

## KV State Transitions

| Phase             | Operation                      | KV before | KV after | Notes                                          |
| ----------------- | ------------------------------ | --------- | -------- | ---------------------------------------------- |
| 1                 | account (no positions)         | 0         | 0        | spellcaster skips — no positions tracked yet   |
| 2                 | redeem_request 100e18          | 0         | **0**    | next_id=0 stored raw (was 1 under +1 sentinel) |
| 3                 | account (Pending, id 0)        | 0         | **0**    | no-op writeback `0 * 1 = 0`                    |
| 4                 | redeem_request 100e18 (second) | 0         | 0        | reverted before state change                   |
| 5 (after approve) | account (Processed)            | 0         | 0        | `0 * 0 = 0`                                    |
| 6 (after reject)  | account (Canceled)             | 0         | 0        | `0 * 0 = 0`                                    |
| 7                 | redeem_request 50e18           | 0         | **1**    | next_id=1 stored raw (was 2 under +1 sentinel) |
| 7                 | account (Pending, id 1)        | 1         | **1**    | no-op writeback `1 * 1 = 1`                    |

All transitions match the Option B design.

## Validation Checklist

| Requirement                                                                                | Status |
| ------------------------------------------------------------------------------------------ | ------ |
| Compilation passes                                                                         | YES    |
| Root active on testnet (`allowedInstrRoot` matches `0x32854e56…f939d`)                     | YES    |
| `redeem_request` executed via CLI (success path)                                           | YES    |
| One-in-flight guard fires via CLI (struct-based revert)                                    | YES    |
| Admin `approveRequest` settles + `account` resets KV via CLI                               | YES    |
| Admin `rejectRequest` + `account` resets KV via CLI                                        | YES    |
| Cycle freshness: second redeem + `account` via CLI                                         | YES    |
| Positions verified via CLI (`display-positions`, `getPosition`)                            | YES    |
| **Refactor verified:** KV stores raw requestId (no +1 sentinel)                            | YES    |
| **Refactor verified:** account flow has no `max`/`sub`/`add` in WeirollVM trace            | YES    |
| **Refactor verified:** withdraw guard runs new struct-based check                          | YES    |
| **Refactor verified:** Phase 4 reverts at `revertIfTrue(true)`, not `revertIfFalse(false)` | YES    |
| **Refactor verified:** Phase 2 first-ever withdraw permitted via KV=0 + struct-sender=0    | YES    |

## Refactor regression matrix (vs. prior runs)

| Property                                      | Pre-refactor (run 1, root 0x20cd…) | Account-only refactor (run 2, root 0x7ab5…) | Option B (run 3, root 0x3285…) |
| --------------------------------------------- | ---------------------------------- | ------------------------------------------- | ------------------------------ |
| KV after Phase 2                              | 1                                  | 1                                           | **0** (raw next_id)            |
| KV after Phase 7 redeem                       | 2                                  | 2                                           | **1** (raw next_id)            |
| Account `mulDiv` in WeirollVM                 | 1                                  | 0                                           | **0**                          |
| Account `mul` in WeirollVM                    | 1                                  | 2                                           | **2**                          |
| Account `max` / `sub` ops                     | 1 / 1                              | 1 / 1                                       | **0 / 0**                      |
| Account `extractElementFromStaticTuple` count | 4                                  | 3                                           | **3**                          |
| Account commands in rootfile                  | 17                                 | 15                                          | **13**                         |
| Withdraw `revertIfFalse(eq(kv,0))`            | YES                                | YES                                         | **NO**                         |
| Withdraw `revertIfTrue(in_flight)`            | NO                                 | NO                                          | **YES**                        |
| Withdraw commands in rootfile                 | 8                                  | 8                                           | **14** (struct guard added)    |

## Result: PASS

Option B behaves exactly as designed:

- The withdraw guard reads the on-chain `Request` struct and correctly
  distinguishes "zero-init slot" (sender=0 → not in-flight) from "tracking
  real id 0" (sender=caliber → in-flight).
- The account flow writes the raw `tracked_id * is_pending_mask` value to KV,
  which is `0` when not pending and the raw id (including id=0) when pending.
- The Phase 1 critical check passes: first-ever redeem with KV=0 succeeds
  because the on-chain struct sender is also 0.
- The Phase 4 critical check passes: revert fires at the new struct-based
  guard, never at the old `eq(kv, 0)` check.
- No `+1` / `max` / `sub` / `add` operations remain in the account or
  withdraw traces.

---

## Previous run (superseded — kept for historical comparison)

The previous `test-report.md` (2026-05-18, testnet `e89e74ff-…`, root
`0x7ab58b85…dd1a`) validated the **account-only refactor** that moved from
USD-18 valuation to raw-mGLOBAL slot-0 reporting. KV semantics in that run
still used the **+1 sentinel** (KV values 0 → 1 → 2 across the cycle). That
report is now superseded by the Option B run documented above.

The run before that (2026-05-15, testnet `7d4954d8-…`, root `0x20cd…`)
validated the pre-refactor blueprint with USD-18 slot 0 and `mulDiv` inside
WeirollVM. Also superseded.
