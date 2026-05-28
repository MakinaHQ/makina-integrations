# Execution Report — Midas mGLOBAL Redemption Vault: WITHDRAW

**Action**: withdraw (`redeemRequest(address,uint256,address)`)
**Chain**: ethereum mainnet (chain_id 1)
**Vault proxy**: `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B`
**Vault implementation**: `0xf687E76e3d62d62fE6F6A7f66ce9faE21df6438d`
**Caliber under test**: `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (dusd mainnet)
**Tenderly testnet**: `a8d4ee98-ff6c-4047-a0b4-201583af7725`
**Admin RPC**: `https://virtual.mainnet.eu.rpc.tenderly.co/a09bfee8-88e1-469c-9ffe-f806142a9a7f`
**Fork block**: `0x17f03af`

---

## 0. Fork prep (gotchas resolved before any redeemRequest call)

### (A) Unhealthy `mTokenDataFeed.getDataInBase18()`

Live call on mainnet reverts with `DF: feed is unhealthy`:

```
to:   0xb468A6F63868cB6C6D99105EDfbe73d6B21f139E
data: 0x63692905
err:  0x08c379a0… "DF: feed is unhealthy"
```

**Workaround applied**: stubbed the _implementation_ of the data feed proxy via
`tenderly_setCode`. Implementation = `0x94Cd5b8904c1F1426f9408eE5c98b789c6a864c6`.
Stub deployed bytecode returns `1e18` from `getDataInBase18()`:

```
0x6080604052348015600e575f5ffd5b50600436106026575f3560e01c80636369290514602a575b5f5ffd5b60306044565b604051603b91906069565b60405180910390f35b5f670de0b6b3a7640000905090565b5f819050919050565b6063816053565b82525050565b5f602082019050607a5f830184605c565b9291505056fea2646970667358221220b0faedf5f054304f0dc3dc9766799664cb1b397bde07bbc6c72d344999bcacf164736f6c63430008210033
```

RPC call: `tenderly_setCode(0x94Cd5b8904c1F1426f9408eE5c98b789c6a864c6, <bytecode>)`.
Post-override: `getDataInBase18()` on the proxy now returns `0xde0b6b3a7640000` (1e18).

### (B) Greenlist gate (`M_GLOBAL_GREENLISTED_ROLE`)

`greenlistEnabled` reads `1` on the vault. The mGLOBAL token (`mTokenPermissioned`) ALSO requires both `from` and `to` to be greenlisted on every transfer. Therefore we need the role granted to BOTH:

1. The caliber `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (msg.sender + recipient)
2. The vault `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B` (transfer destination)

**Workaround applied**: direct storage write on `MidasAccessControl` proxy (`0x0312a9d1fF2372dDeDCBB21e4B6389AfC919AC4b`). Storage layout: `_roles` mapping at slot **101** (Initializable→ContextUpgradeable.__gap[50]→ERC165Upgradeable.__gap[50]→AccessControlUpgradeable._roles). `_roles[role].members[account]` slot computed via `keccak256(account || keccak256(role || 101))`.

| Account                | Role                                                                                                          | Member slot                                                          | Value   |
| ---------------------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------- |
| caliber                | `M_GLOBAL_GREENLISTED_ROLE` = `0x49a103d47daa98d445728ba0f2e848dccbbd73dea56729c961450eeb09890acc`            | `0x64f4eb6ce737961e945f41a04b7560e31c4c2f01f8eaa5dc988410f969eb5e65` | `0x…01` |
| vault                  | same                                                                                                          | `0x3db9aef8a011b0a3f535c57f3a97638501bd2b65ce71ba264a31901e51846827` | `0x…01` |
| test EOA `0x5fd792B3…` | `M_GLOBAL_REDEMPTION_VAULT_ADMIN_ROLE` = `0x4f489379521d284f6d62800bc46b6bc11dd3de438eba9c5a37a9e70f84ceb552` | `0x5e41830e091c5bbf32d8f55233323eb75bc3d3fa6d060edaacb2f302f910d2b7` | `0x…01` |

Post-override: `hasRole(M_GLOBAL_GREENLISTED_ROLE, caliber)` returns `0x…01`.

### (C) Per-selector pause (`fnPaused[selector]`)

The selector `redeemRequest(address,uint256,address)` = `0x15571a04` is currently per-selector paused on mainnet. First redeem attempt reverted with `Pausable: fn paused` (call trace operation `193f7af1-552b-4539-b833-cd17350a9e8c`).

**Workaround applied**: from the test EOA holding `M_GLOBAL_REDEMPTION_VAULT_ADMIN_ROLE` (which equals `pauseAdminRole()`), call `unpauseFn(bytes4)`:

- to: `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B`
- data: `0x3807be7d15571a0400000000000000000000000000000000000000000000000000000000`
- from: `0x5fd792B3a904832DBB63FfD0741949B44f88cd4F`
- tx: `0xad7ac8c10686333e9d4097968937479b55ac7e9985661cec6981e15256278af4` (status success)

### (D) Funding

| Account                           | Token                  | Amount (hex / decimal)              | RPC                        |
| --------------------------------- | ---------------------- | ----------------------------------- | -------------------------- |
| caliber                           | ETH                    | `0x21e19e0c9bab2400000` = 10000 ETH | `tenderly_setBalance`      |
| EOA admin                         | ETH                    | `0x21e19e0c9bab2400000` = 10000 ETH | `tenderly_setBalance`      |
| caliber                           | mGLOBAL                | `0x3635c9adc5dea00000` = 1000e18    | `tenderly_setErc20Balance` |
| requestRedeemer (`0xaB9dA7953D…`) | USDC                   | `0x174876e800` = 100,000e6          | `tenderly_setErc20Balance` |
| requestRedeemer                   | USDC allowance → vault | `MAX_UINT256`                       | `approve` tx `0x0e826144…` |

> Note: native mGLOBAL transfer hook (`mTokenPermissioned._beforeTokenTransfer`) blocks transfers to non-greenlisted destinations. Verified: with the vault greenlisted, `transferFrom(caliber → vault)` inside `redeemRequest` succeeds and emits a standard ERC-20 `Transfer` event (logIndex 1 below). NO blacklist or pause hit on the request path.

---

## Phase 1 — Pre-flight read: `currentRequestId()`

**Call (read)**

| Field | Value                                        |
| ----- | -------------------------------------------- |
| to    | `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B` |
| data  | `0x5ae2bfdb`                                 |

**Return**: `0x0000…0000` → `next_id = 0`.

This is the value the caliber MUST capture pre-call and (per the chosen ID-0 sentinel scheme) store as `next_id + 1 = 1` in the KV store.

---

## Phase 2 — `mGLOBAL.approve(vault, amount)`

**Tx data**

| Field | Value                                                                                                                                        |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| from  | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (caliber, impersonated)                                                                         |
| to    | `0x7433806912Eae67919e66aea853d46Fa0aef98A8` (mGLOBAL)                                                                                       |
| data  | `0x095ea7b3000000000000000000000000a0fc8bdfb1e6a705c1375810989b1d70a982b01b0000000000000000000000000000000000000000000000056bc75e2d63100000` |

`approve(0xA0Fc…, 100e18)`. Tx hash: `0x76b5817ce905ad8f7314b434ded5ef16f8ad3e65aa8595a3fab34e4d6596aa18`, status success.

**Post-state**: `allowance(caliber, vault) = 0x056bc75e2d63100000 = 100e18`. ✓

---

## Phase 3 — `redeemRequest(USDC, 100e18, caliber)` — FIRST request

**Tx data**

| Field     | Value                                                                                                                                                                                                        |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| from      | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (caliber, impersonated)                                                                                                                                         |
| to        | `0xA0Fc8BDFb1E6a705C1375810989B1d70a982b01B` (vault proxy)                                                                                                                                                   |
| data      | `0x15571a04000000000000000000000000a0b86991c6218b36c1d19d4a2e9eb0ce3606eb480000000000000000000000000000000000000000000000056bc75e2d63100000000000000000000000000000d1a1c248b253f1fc60eacd90777b9a63f8c8c1bc` |
| gas limit | 2,000,000                                                                                                                                                                                                    |

**Selector breakdown**

| Arg            | Value                                                  |
| -------------- | ------------------------------------------------------ |
| tokenOut       | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` (USDC)    |
| amountMTokenIn | `100e18`                                               |
| recipient      | `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (caliber) |

**Result**: success. Tx hash: `0xd2f953234c8d75a89a98ca1c2bf105f995a8b3c7e37d50cbf5ff6c5a8879351c`. **Gas used: 332,031** (`0x512ff`).

**Events emitted** (in tx receipt order):

1. `Approval(owner=caliber, spender=vault, value=0)` on mGLOBAL — allowance consumed.
2. `Transfer(from=caliber, to=vault, value=100e18)` on mGLOBAL — escrow into vault.
3. `RedeemRequestWithCustomRecipient` on vault (topic0 `0x691cd372bb63a5126a324513b634040d0ba3747c0a625207d99b6ba302c51a23`):

| Field                    | Value                           | Notes                                                     |
| ------------------------ | ------------------------------- | --------------------------------------------------------- |
| requestId (indexed t1)   | `0`                             | **id-0 sentinel confirmed**                               |
| user (indexed t2)        | `0xd1a1…c1bc`                   | caliber (msg.sender)                                      |
| tokenOut (indexed t3)    | `0xa0b8…eb48`                   | USDC                                                      |
| recipient (data[0])      | `0xd1a1…c1bc`                   | caliber (recipient)                                       |
| amountMTokenIn (data[1]) | `0x056bc75e2d63100000` = 100e18 | full input                                                |
| feeAmount (data[2])      | `0`                             | tokensConfig[USDC].fee = 0, request path skips instantFee |

**Assertion `event.requestId == pre-flight next_id`**: 0 == 0 ✓

---

## Phase 4 — Post-state checks

| Metric                  | Before  | After  | Delta                           |
| ----------------------- | ------- | ------ | ------------------------------- |
| `currentRequestId()`    | 0       | 1      | +1 (pre-incremented internally) |
| caliber mGLOBAL balance | 1000e18 | 900e18 | −100e18 ✓                       |
| vault mGLOBAL balance   | 0       | 100e18 | +100e18 ✓ (escrowed)            |
| caliber USDC balance    | 0       | 0      | UNCHANGED ✓ (no instant payout) |

`redeemRequests(0)` read (data `0xe85ba3e90…0`):

```
0x
00000000000000000000000  d1a1c248b253f1fc60eacd90777b9a63f8c8c1bc   sender    = caliber
00000000000000000000000  a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48   tokenOut  = USDC
00000000000000000000000000000000000000000000000000000000000000   00   status    = 0 (Pending)
00000000000000000000000000000000000000000000  056bc75e2d63100000   amountMToken = 100e18
000000000000000000000000000000000000000000000000   0de0b6b3a7640000   mTokenRate    = 1e18 (stub)
000000000000000000000000000000000000000000000000   0de0b6b3a7640000   tokenOutRate  = 1e18 (STABLECOIN_RATE)
```

Since `fee=0`, `Request.amountMToken == amountMTokenIn` exactly (no rounding).

---

## Phase 5 — Sentinel & one-in-flight verification

### Sentinel: first request gets id=0 (CONFIRMED)

`currentRequestId` was 0 pre-call and is 1 post-call. The pre-increment pattern in
`_redeemRequest` assigns `requestId = 0` to the first ever request.

**Blueprint implication**: KV-store-based "one-in-flight" tracking must NOT use the
raw stored `requestId` as a sentinel (since 0 is a valid id AND the zero-init value).
The blueprint-writer must apply the documented (a) option: store `requestId + 1` in KV.

### One-in-flight is NOT enforced on-chain (CONFIRMED)

Approved another 50e18 and called `redeemRequest` again WITHOUT admin settling id=0:

- Approve tx: `0x9530cada9d036743c79c726540d8f09975f469f67b2840dfac1cf2d1807fb677`
- Redeem tx: `0xb04a9369cc4ef840326d469ea4c89fd11580183051591376e3961cd405989433`

Result: **success**. `currentRequestId()` advanced to `2`. `redeemRequests(1)` shows another fully populated Pending request:

```
sender       = 0xd1a1…c1bc
tokenOut     = USDC
status       = 0 (Pending)
amountMToken = 0x2b5e3af16b1880000 = 50e18
mTokenRate   = 1e18
tokenOutRate = 1e18
```

**Blueprint implication**: the contract permits unlimited in-flight requests per
caller. Our invariant of one-in-flight per caliber MUST be enforced in the
blueprint via a KV check before the call:

```
kv.get(key)         # must be 0
... pre-flight read currentRequestId() ...
... approve ...
... redeemRequest ...
kv.set(key, next_id + 1)
```

---

## Failure modes hit and resolutions

| Step                               | Error                                                | Resolution                                                                                                                                  |
| ---------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| First `redeemRequest` attempt      | `Pausable: fn paused` (selector `0x15571a04`)        | Granted vault admin role to test EOA via storage; called `unpauseFn(0x15571a04)`                                                            |
| Second `redeemRequest` attempt     | `WMAC: hasnt role` from inside mGLOBAL transfer hook | Granted `M_GLOBAL_GREENLISTED_ROLE` to the _vault_ (not just caliber) via storage write — mGLOBAL transfer hook checks BOTH `from` and `to` |
| `mTokenDataFeed.getDataInBase18()` | `DF: feed is unhealthy`                              | Replaced data-feed implementation code with `pure 1e18` stub via `tenderly_setCode`                                                         |

---

## Raw RPC reference (canonical call sequences for blueprint)

Per the spec design, the withdraw blueprint sequence in pseudocode:

1. `kv.get(key)` → revert if != 0
2. `vault.currentRequestId()` → `next_id` (e.g. `0`)
3. `mGLOBAL.approve(vault, amount)`
4. `vault.redeemRequest(USDC, amount, caliber)` → emits `RedeemRequestWithCustomRecipient(next_id, …)`
5. `kv.set(key, next_id + 1)`

The on-chain leg verified above (steps 2–4) is unchanged from the design. Steps 1 & 5 are KV operations the blueprint adds on top.
