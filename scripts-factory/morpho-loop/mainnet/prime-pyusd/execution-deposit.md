# Execution Report — DEPOSIT (open / lever-up)

**Action**: deposit (open + increase leverage) — PRIME/PYUSD Morpho loop
**Chain**: mainnet (ethereum)
**Machine**: dusd
**Executor**: all state-changing calls sent AS the caliber `0xD1A1C248B253f1fc60eACd90777B9A63F8c8c1BC` (impersonated)

## Shared fork (reuse for account / withdraw)

| Field                                   | Value                                                                             |
| --------------------------------------- | --------------------------------------------------------------------------------- |
| Provider                                | Tenderly Virtual TestNet (mainnet fork)                                           |
| **testnet_id**                          | `8f992f50-3553-441e-aae5-26a38d5bb786`                                            |
| **admin_rpc** (impersonation + funding) | `https://virtual.mainnet.eu.rpc.tenderly.co/b7c578ff-ff43-42b7-a797-eacd4caa81ca` |
| public_rpc                              | `https://virtual.mainnet.eu.rpc.tenderly.co/9df9105b-c427-4059-a5e8-e2a3afa0ddb3` |
| Fork block                              | ~25,587,159                                                                       |

**navOracle preservation**: on this fork `PRIME.navOracle = 0xdF4ab20fA7752Be52E41e42F1FD667f37964d6a3` is intact and `getVerifiedNav() = 1049629415611939435` (~1.0496e18), so `convertToAssets`/`previewDeposit` work. No override needed on this fork. If a future fork ever returns `navOracle == 0` (convert/preview would revert `InvalidAddress`), reset the slot or re-fork; do NOT clear it.

## Setup verification (pre-flight, all pass)

| Check                                | Result                                                                         |
| ------------------------------------ | ------------------------------------------------------------------------------ |
| `oracle.price()`                     | `1049690555221613945938417681788095852` (~1.049691, scale 1e36) — matches spec |
| `idToMarketParams(id)`               | `(PYUSD, PRIME, 0x335e…b07e, 0x870a…00BC, 0.86e18)` — matches spec             |
| `PRIME.convertToAssets(1e6)`         | `1049629` wYLDS/PRIME (appreciating)                                           |
| `PRIME.previewDeposit(1e6 wYLDS)`    | `952717` PRIME/wYLDS (= 1/NAV)                                                 |
| `wYLDS.convertToShares(1e6 USDC)`    | `1000000` (1:1, `pure`)                                                        |
| caliber position (pre)               | `(0,0,0)` — fresh                                                              |
| market liquidity                     | totalSupply 129.89M / totalBorrow 116.11M PYUSD → ~13.78M free to borrow       |
| Morpho PYUSD balance (flash ceiling) | 46,080,662 PYUSD                                                               |

Funded caliber: 10 ETH (gas) + 100,000 PYUSD.

---

## PYUSD ⇄ USDC route (the swap leg)

The `swap_module` (`0x923c…17C3`) is a thin wrapper: it `transferFrom`s the input, `forceApprove`s the aggregator (`approvalTarget`), does a low-level `call(order.data)` to the aggregator (`executionTarget`), then transfers the output back and enforces `minOutputAmount`. `order.data` is offchain-fetched aggregator calldata. Registered swappers on the deployed module:

| swapperId | approval/exec target                         | aggregator                  |
| --------- | -------------------------------------------- | --------------------------- |
| 1         | `0xCf5540fFFCdC3d510B18bFcA6d2b9987b0772559` | 0x Exchange Proxy           |
| 2         | `0x888888888889758F76e7103c6CbF23ABbF58F946` | Odos Router V2              |
| 3         | `0x6131B5fae19EA4f9D964eAc0408E4408b66337b5` | KyberSwap MetaAggregator V2 |
| 4         | `0x3f04b65Ddbd87f9CE0A2e7Eb24d80e7fb87625b5` | (aggregator)                |
| 5         | `0x0000000000001fF3684f28c67538d4D072C22734` | 0x Settler v2               |

**Concrete venue behind the route: Curve PYUSD/USDC pool `0x383E6b4437b59fff47B619CBA855CA29342A8559`** (coin0 = PYUSD, coin1 = USDC; balances 19.29M PYUSD / 21.71M USDC). This is the deep, canonical PYUSD/USDC stable venue every aggregator above routes through for this pair.

- `get_dy(0→1, 100,000 PYUSD)` = **99,992.248598 USDC** → rate 0.999922, **slippage 0.0078%** (tight stable pair, as expected).
- For the fork test the swap was executed **directly on the Curve pool** (`exchange(0,1,dx,min_dy)`) rather than through an aggregator router, because live aggregator calldata cannot be generated deterministically against a fork. The swap_module wraps exactly this economic leg; Stage 3 supplies `swapperId` + offchain `data` at runtime.

---

## LAYER 1 — primitive legs (single cycle, no leverage)

Per-leg call table (executor = caliber). Approvals are separate txs; "spender" = approved party.

| # | Call             | Target               | Selector                                                                                         | Key args                                                                    | Approval (spender, amount)                   | In → Out                                                                     | Gas     | Status |
| - | ---------------- | -------------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------------------- | ------- | ------ |
| 1 | swap PYUSD→USDC  | Curve `0x383E…8559`  | `exchange(int128,int128,uint256,uint256)` `0x3df02124`                                           | i=0,j=1,dx=100000e6,min=99902e6                                             | PYUSD → Curve, 100000e6 (gas 60,152)         | 100,000 PYUSD → **99,992.248598 USDC**                                       | 157,872 | ✅     |
| 2 | wrap USDC→wYLDS  | wYLDS `0x6aD0…66Cc`  | `deposit(uint256,address)` `0x6e553f65`                                                          | assets=99,992.248598e6, receiver=caliber                                    | USDC → wYLDS, 99,992.248598e6 (gas 55,570)   | 99,992.248598 USDC → **99,992.248598 wYLDS** (1:1)                           | 95,483  | ✅     |
| 3 | wrap wYLDS→PRIME | PRIME `0x19eb…F7F6`  | `deposit(uint256,address)` `0x6e553f65`                                                          | assets=99,992.248598e6, receiver=caliber                                    | wYLDS → PRIME, 99,992.248598e6 (gas 51,034)  | 99,992.248598 wYLDS → **95,264.335308 PRIME** (ratio 0.952717, NAV 1.049629) | 115,236 | ✅     |
| 4 | supplyCollateral | Morpho `0xBBBB…FFCb` | `supplyCollateral((address,address,address,address,uint256),uint256,address,bytes)` `0x238d6579` | marketParams, assets=95,264.335308e6, onBehalf=caliber, data=`0x`           | PRIME → Morpho, 95,264.335308e6 (gas 51,035) | +95,264.335308 PRIME collateral                                              | 73,918  | ✅     |
| 5 | borrow PYUSD     | Morpho `0xBBBB…FFCb` | `borrow((address,address,address,address,uint256),uint256,uint256,address,address)` `0x50d8cd4b` | marketParams, assets=43,000e6, shares=0, onBehalf=caliber, receiver=caliber | —                                            | → **43,000 PYUSD** received                                                  | 163,929 | ✅     |

`marketParams = (PYUSD 0x6c3e…A0e8, PRIME 0x19eb…F7F6, oracle 0x335e…b07e, irm 0x870a…00BC, lltv 860000000000000000)`.

**Tx hashes**

| Leg                | Tx                                                                   |
| ------------------ | -------------------------------------------------------------------- |
| 1 swap (exchange)  | `0x66715de84a616d0a5182d7d16d868d781a4b113cfb5ced4781c400a842d637e1` |
| 2 wYLDS.deposit    | `0xba5e9f8dc20858f47ac4d0242c70bbf33031b857dd6a51d391645d2fff642cda` |
| 3 PRIME.deposit    | `0xfacf7933685442a2120425c2f168a8f6613367c5c9ab1532d3cd0cad153d35c1` |
| 4 supplyCollateral | `0xc1abf8ba71851ad445bb26f14bcee62fc1755308e13aa25c5c7556009ee39219` |
| 5 borrow           | `0x18e898b08a300259bbaca44f0cd9c9ba76498ccce55783cf962d0ed19ab8bb71` |

**Open-item resolutions (from live fork):**

- `prime_deposit_open` → **RESOLVED**: PRIME.deposit(wYLDS) by the caliber succeeded (leg 3). No KYC/cap/whitelist gate. `whenNotPaused`+`nonReentrant` only.
- `whitelist_enforcement_point` → **RESOLVED (confirms Stage 1B correction #1)**: `wYLDS.deposit(USDC, caliber)` succeeded (leg 2) with the caliber **NOT** whitelisted. Whitelisting is NOT a deposit gate. No `addToWhitelist` fork step is needed for deposit.

### Position after Layer 1 (single cycle)

| Metric                                | Value                          |
| ------------------------------------- | ------------------------------ |
| collateral                            | 95,264.335308 PRIME            |
| borrowShares                          | 42,638,724,643,084,590         |
| debt                                  | 43,000.000000 PYUSD            |
| collateral value (PRIME·price/1e36)   | 99,998.073022 PYUSD            |
| max borrow (·lltv 0.86)               | 85,998.342798 PYUSD            |
| **LTV**                               | **43.00%** (target 50% of max) |
| **health factor** (collVal·lltv/debt) | **2.00**                       |

### Calculations

```
USDC_out       = get_dy(0,1, 100000e6)           = 99,992.248598 USDC        (0.0078% slip)
wYLDS_out      = USDC_out (1:1)                   = 99,992.248598 wYLDS
PRIME_out      = wYLDS_out / NAV(1.049629)        = 95,264.335308 PRIME
collateral_val = PRIME_out * price / 1e36
               = 95264335308 * 1.049691e36 / 1e36 = 99,998.073022 PYUSD
max_borrow     = collateral_val * 0.86            = 85,998.342798 PYUSD
borrow (≈50%)  =                                    43,000.000000 PYUSD  → LTV 43.00%, HF 2.00
```

---

## LAYER 2 — leveraged loop (production shape)

### (a) Morpho PYUSD flash-loan primitive — PROVEN

Deployed a minimal receiver `FlashTest` at `0x99c51EcCB10A54C1145E4555e17AB4407cf01E0f` that calls `Morpho.flashLoan(PYUSD, amount, data)` and repays in `onMorphoFlashLoan`.

| Field                           | Value                                                                |
| ------------------------------- | -------------------------------------------------------------------- |
| flash amount                    | 200,000 PYUSD                                                        |
| `assets` seen in callback       | 200,000,000,000 (200,000 PYUSD)                                      |
| PYUSD balance held mid-callback | 200,000,000,000 — funds delivered                                    |
| repaid                          | 200,000 PYUSD (**fee = 0**), residual balance 0                      |
| gas                             | 125,683                                                              |
| tx                              | `0xc87eff3985c55249a0c3aeef625bd41fdfad89bd910e4c988cf93575487f34b1` |

Confirms: PYUSD is flash-loanable via **provider MORPHO (enum 3)** at zero fee; Morpho holds 46.08M PYUSD (huge ceiling).

**Aggregator wiring confirmed on fork:**

- `FlashloanAggregator (0x820D…4065).morphoPool = 0xBBBB…FFCb` (Morpho Blue) — Morpho path is wired.
- `requestFlashloan((uint8,(uint256,bool,uint256,uint8,address[],address[],bytes32[],bytes[],uint128,bytes32[]),address,uint256))` selector = **`0x4140b286`** (`onlyCaliber`).
- `onMorphoFlashLoan(uint256,bytes)` selector = **`0x31f57072`**.

### (b) Loop body chaining under leverage — PROVEN

Replayed the `loop_in` body treating the 43,000 loose PYUSD from Layer-1 leg 5 as a flash-borrowed tranche: swap → wYLDS.deposit → PRIME.deposit → supplyCollateral → borrow(43,000 to repay FL). All legs chained (each status = 1):

```
43,000 PYUSD → 42,996.607299 USDC → 42,996.607299 wYLDS → 40,963.607402 PRIME (supplied)
then borrow 43,000 PYUSD (repays the flash tranche)
```

### Final leveraged position (after 2 cycles)

| Metric                      | Value                  |
| --------------------------- | ---------------------- |
| collateral                  | 136,227.942710 PRIME   |
| borrowShares                | 85,277,439,518,424,200 |
| debt                        | 86,000.009850 PYUSD    |
| collateral value            | 142,997.184819 PYUSD   |
| **LTV**                     | **60.14%**             |
| **health factor**           | **1.43**               |
| leverage (collVal / equity) | **~2.51x**             |

(In a true atomic flash-loop the final borrow repays the flash loan so net loose PYUSD = 0 and the leverage sits entirely in the Morpho position on the original equity.)

---

## Stage-3 wiring notes (bespoke deposit blueprint required)

The stock `blueprints/morpho-loop/deposit-swap.yaml:loop_in` assumes **one** DEX swap `loan_token → collateral_token`. PRIME/PYUSD needs **three** conversion legs the DEX aggregator will NOT do end-to-end:

```
PYUSD --swap_module.swap(swapperId,data,PYUSD,USDC,in,min)--> USDC        (aggregator, offchain calldata)
USDC  --wYLDS.deposit(assets, caliber)---------------------> wYLDS        (ERC4626 wrap 1, 1:1)
wYLDS --PRIME.deposit(assets, caliber)---------------------> PRIME        (ERC4626 wrap 2, /NAV)
PRIME --Morpho.supplyCollateral(marketParams, primeOut, caliber, 0x)
PYUSD --Morpho.borrow(marketParams, flash_loan_amount, 0, caliber, caliber)  (repays FL)
```

So the loop_in blueprint must insert **two extra ERC4626 `deposit(uint256,address)` legs (USDC→wYLDS, wYLDS→PRIME), each preceded by an `approve`**, between the swap and `supplyCollateral`, and the `supplyCollateral` amount must be the PRIME output of the second wrap (not the swap output). Everything else (flashloan-request MANAGEMENT entry with `flash_loan_venue = 3` Morpho, `idToMarketParams` + `extractElementFromStaticTuple` tuple rebuild, `borrow(flash_loan_amount)`) mirrors `instructions/morpho-loop-swap.yaml` unchanged.

Per-leg approvals required in the deposit path: PYUSD→swap_module, USDC→wYLDS, wYLDS→PRIME, PRIME→Morpho.

## Reverts encountered

None. Every leg (Layer 1 legs 1–5, the flash-loan primitive, and the Layer-2 loop cycle) returned status = 1 on first attempt.
