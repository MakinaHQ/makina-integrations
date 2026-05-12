# Execution Report: Deposit

**Action**: deposit
**Chain**: Arbitrum (42161)
**VNet ID**: `1caf0022-d243-490b-8ff6-2cb769d513a9`
**Admin RPC**: `https://virtual.arbitrum.eu.rpc.tenderly.co/ee3b751d-a854-46b3-bf3f-3e831d4263b9`
**Public RPC**: `https://virtual.arbitrum.eu.rpc.tenderly.co/3707b1ef-24da-4c82-b267-62ccf025636f`
**Fork Block**: `0x1ad750e8` (450318568)
**Test Address**: `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450`

---

## Pre-flight Checks

| Check                        | Result                                                       |
| ---------------------------- | ------------------------------------------------------------ |
| USDC.balanceOf(test)         | 1,000,000,000 (1000 USDC)                                    |
| PYUSD.balanceOf(test)        | 1,000,000 (1 PYUSD, funded for testing)                      |
| USDai.isBlacklisted(test)    | false                                                        |
| ST.maxDeposit(test)          | 102,619,666,002,360,518 (~0.1026 sUSDai)                     |
| ST.balanceOf(test)           | 0                                                            |
| sUSDai.depositSharePrice()   | 1,077,944,765,680,022,074 (~1.078e18)                        |
| sUSDai.convertToShares(1e18) | 927,691,317,624,377,002 (~0.928 sUSDai per 1 USDai)          |
| ST.authority()               | `0x7cc6fb28ec7b5e7afc3cb3986141797ffc27253c` (AccessManager) |

### AccessManager Role Analysis

The ST contract uses OpenZeppelin `AccessManaged` with `restricted` modifier on `deposit()` and `redeem()`.

| Query                                           | Value                                       |
| ----------------------------------------------- | ------------------------------------------- |
| getTargetFunctionRole(ST, 0x6e553f65 [deposit]) | `0x858ca8ea411ba2c3` (9623252227852051139)  |
| getTargetFunctionRole(ST, 0xba087652 [redeem])  | `0x858ca8ea411ba2c3` (same role)            |
| getRoleAdmin(0x858ca8ea411ba2c3)                | `0xa82ebdc1d01dc0a3` (12118832287418532003) |
| getRoleAdmin(0xa82ebdc1d01dc0a3)                | `0x0` (ADMIN_ROLE)                          |
| canCall(test, ST, deposit) **before** grant     | (false, 0) -- blocked                       |
| canCall(test, ST, deposit) **after** grant      | (true, 0) -- allowed                        |

**Critical Finding**: No accounts have been granted role `0x858ca8ea411ba2c3` on-chain. The deposit/redeem functions are currently inaccessible to all EOAs. The protocol has not yet opened deposits to the public.

**Workaround Applied**: Used `set_storage_at` to override AccessManager storage and grant the deposit role to the test address:

- Storage slot: `0xecf46ca4d466da44ee2c413d4f458f382ae6d47267ebb5a532bbf32bc4098b58`
  - Computed as: `keccak256(abi.encode(test_address, keccak256(abi.encode(roleId, roles_mapping_slot))))`
  - Where `roles_mapping_slot` = AccessManager ERC-7201 base + 1
- Value set: `0x0000...0001` (Access.since = 1, delay = 0)

For production: the Makina caliber address must be granted role `0x858ca8ea411ba2c3` on the AccessManager at `0x7cc6fb28ec7b5e7afc3cb3986141797ffc27253c` before deposit/withdraw operations will work.

---

## USDC Deposit Path (FAILED - No Uniswap Liquidity)

The USDC deposit path via USDai uses Uniswap V3 to swap USDC -> PYUSD. This currently fails because the USDC/PYUSD pool at 100 bps fee tier (`0xc79aefdeafae136a1092f997fae88b8fd365c5f7`) has **zero liquidity**.

| Fee Tier        | Pool Address                                 | Status                                 |
| --------------- | -------------------------------------------- | -------------------------------------- |
| 100 bps (0.01%) | `0xc79aefdeafae136a1092f997fae88b8fd365c5f7` | No liquidity (swap exhausts all ticks) |
| 500 bps (0.05%) | Not deployed                                 | N/A                                    |
| 3000 bps (0.3%) | `0xbe7648914a1665dcd47d1b964e6714e2bbf01c76` | Exists (not tested)                    |
| 10000 bps (1%)  | `0x33a2f1bc5e213e13ae2871efa6fd2fbe7890e521` | Exists (not tested)                    |

The swap adapter defaults to 100 bps fee tier when no custom path is provided (4-arg deposit). A custom path via the 5-arg deposit could use 3000 or 10000 bps pools if they have liquidity.

**For blueprint design**: The USDC deposit path should either:

1. Swap USDC -> PYUSD externally (outside USDai), then deposit PYUSD to USDai
2. Use 5-arg `USDai.deposit(address, uint256, uint256, address, bytes)` with a custom Uniswap path specifying a working fee tier
3. Use PYUSD directly as the deposit token (simplest, if caliber holds PYUSD)

---

## Successful Deposit Flow: PYUSD -> USDai -> sUSDai -> ST

Used PYUSD (base token) for the deposit path which avoids the Uniswap swap entirely.

**Amount**: 90,000 PYUSD (0.09 PYUSD, 6 decimals) -- chosen to produce sUSDai amount below maxDeposit limit.

### Call 1: PYUSD.approve(USDai)

**Contract**: `0x46850aD61C2B7d64d08c9C754F45254596696984` (PYUSD)
**Function**: `approve(address spender, uint256 amount)`

| Param   | Value                                        | Type    |
| ------- | -------------------------------------------- | ------- |
| spender | `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF` | address |
| amount  | 90000                                        | uint256 |

**Tx**: `0x929b9ab3ed7d056a74ce7b06c2d23868eef8a6a8b8bfb136b74c8e4836092cf3` | Status: SUCCESS
**Gas**: 60,749
**Output**: true

---

### Call 2: USDai.deposit(PYUSD)

**Contract**: `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF` (USDai)
**Function**: `deposit(address depositToken, uint256 depositAmount, uint256 usdaiAmountMinimum, address recipient)`

| Param              | Value                                                | Type    |
| ------------------ | ---------------------------------------------------- | ------- |
| depositToken       | `0x46850aD61C2B7d64d08c9C754F45254596696984` (PYUSD) | address |
| depositAmount      | 90000                                                | uint256 |
| usdaiAmountMinimum | 0                                                    | uint256 |
| recipient          | `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450`         | address |

**Tx**: `0x8a2a5193cc4eff74908526928aaec4322672175073b3f10ae74b1aeeb113f89d` | Status: SUCCESS
**Gas**: 163,185

| Output      | Value                               | Type    |
| ----------- | ----------------------------------- | ------- |
| usdaiAmount | 90,000,000,000,000,000 (0.09 USDai) | uint256 |

**Note**: Since PYUSD is the base token, no swap occurs. The deposit is a direct scale: `90000 * 1e12 = 9e16`.

---

### Call 3: USDai.approve(sUSDai)

**Contract**: `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF` (USDai)
**Function**: `approve(address spender, uint256 amount)`

| Param   | Value                                        | Type    |
| ------- | -------------------------------------------- | ------- |
| spender | `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` | address |
| amount  | 90,000,000,000,000,000                       | uint256 |

**Tx**: `0x842d7412ef915e6d960aa02f277276d3b315e12f25233179f8809ad56d9f18bc` | Status: SUCCESS
**Gas**: 51,638
**Output**: true

---

### Call 4: sUSDai.deposit(USDai)

**Contract**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (sUSDai)
**Function**: `deposit(uint256 amount, address receiver)` (ERC4626)

| Param    | Value                                        | Type    |
| -------- | -------------------------------------------- | ------- |
| amount   | 90,000,000,000,000,000 (0.09 USDai)          | uint256 |
| receiver | `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450` | address |

**Tx**: `0x7cfc58dbacc95ef32c2d3c6a53a0621a9a718c529e806e8306898bdd90a7963e` | Status: SUCCESS
**Gas**: 345,098

| Output | Value                                  | Type    |
| ------ | -------------------------------------- | ------- |
| shares | 83,492,139,394,441,125 (0.0835 sUSDai) | uint256 |

### Calculation

```python
deposit_share_price = 1077944765680022074  # ~1.078e18
usdai_amount = 90000000000000000  # 0.09 USDai

# convertToShares: (assets * FIXED_POINT_SCALE) / depositSharePrice
# FIXED_POINT_SCALE = 1e18
shares = (usdai_amount * 10**18) // deposit_share_price
# = 83,492,139,394,441,125 (0.0835 sUSDai)
```

---

### Call 5: sUSDai.approve(ST)

**Contract**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9` (sUSDai)
**Function**: `approve(address spender, uint256 amount)`

| Param   | Value                                        | Type    |
| ------- | -------------------------------------------- | ------- |
| spender | `0x90465aad4e426948A4ea342AC49A1A38200B7017` | address |
| amount  | 83,492,139,394,441,125                       | uint256 |

**Tx**: `0xf4e3b205408a2efab2f101390c65b28e1f43f942387716b391bd395235fef8f5` | Status: SUCCESS
**Gas**: 51,719
**Output**: true

---

### Call 6: ST.deposit(sUSDai)

**Contract**: `0x90465aad4e426948A4ea342AC49A1A38200B7017` (Senior Tranche)
**Function**: `deposit(uint256 _assets, address _receiver)` (2-arg, NOT 3-arg)

| Param     | Value                                        | Type    |
| --------- | -------------------------------------------- | ------- |
| _assets   | 83,492,139,394,441,125 (0.0835 sUSDai)       | uint256 |
| _receiver | `0x7Eae5E2f495ffbE0781B99529A7E8F116BD60450` | address |

**Tx**: `0xc7b1bb1d15191b5f0473ec6dae1c574a7ecd6583e364e5f2643cc8d1455ef926` | Status: SUCCESS
**Gas**: 563,464

| Output | Value                              | Type    |
| ------ | ---------------------------------- | ------- |
| shares | 89,761,092,607,302,279 (0.0898 ST) | uint256 |

**Call trace**: ST -> safeTransferFrom(sUSDai from msg.sender to Kernel) -> Kernel.stDeposit() -> accounting

---

## State Changes

| Metric         | Before                    | After                              |
| -------------- | ------------------------- | ---------------------------------- |
| PYUSD balance  | 1,000,000 (1.0 PYUSD)     | 910,000 (0.91 PYUSD)               |
| USDai balance  | 0                         | 0                                  |
| sUSDai balance | 0                         | 0                                  |
| ST balance     | 0                         | 89,761,092,607,302,279 (0.0898 ST) |
| USDC balance   | 1,000,000,000 (1000 USDC) | 1,000,000,000 (unchanged)          |

---

## Gas Summary

| Step      | Function              | Gas Used      |
| --------- | --------------------- | ------------- |
| 1         | PYUSD.approve(USDai)  | 60,749        |
| 2         | USDai.deposit(PYUSD)  | 163,185       |
| 3         | USDai.approve(sUSDai) | 51,638        |
| 4         | sUSDai.deposit(USDai) | 345,098       |
| 5         | sUSDai.approve(ST)    | 51,719        |
| 6         | ST.deposit(sUSDai)    | 563,464       |
| **Total** |                       | **1,235,853** |

---

## Critical Issues for Blueprint Design

### 1. AccessManager Role Required

The ST deposit and redeem functions require role `0x858ca8ea411ba2c3` on AccessManager `0x7cc6fb28ec7b5e7afc3cb3986141797ffc27253c`. This role has NOT been granted to any address on-chain as of the fork block. The caliber address must be granted this role before operations will work.

### 2. Very Low maxDeposit (~0.1 sUSDai)

The ST has a maxDeposit of only ~~0.1026 sUSDai (~~$0.11). This severely limits deposit size. The maxDeposit is determined by the Kernel's `stMaxDeposit()` which depends on the JT/ST ratio and the tranche capacity configuration. This may increase as more JT is deposited or protocol parameters are adjusted.

### 3. USDC -> PYUSD Swap Failure

The default USDai.deposit with USDC fails because the Uniswap V3 USDC/PYUSD pool at 100 bps fee tier has no liquidity on Arbitrum. Options:

- Use PYUSD directly (tested and working)
- Use 5-arg deposit with custom Uniswap path specifying fee tier 3000 or 10000
- Swap USDC -> PYUSD externally before depositing to USDai

### 4. Multi-step Transaction

The deposit requires 6 transactions (3 approvals + 3 deposits). In a weiroll blueprint, approvals can use `type(uint256).max` for efficiency, and the approve+deposit pairs can be combined into sequential calls.

### 5. Deposit Function Signatures

- **USDai**: `deposit(address,uint256,uint256,address)` -- 4-arg, selector `0x8b6099db`
- **sUSDai**: `deposit(uint256,address)` -- 2-arg ERC4626, selector `0x6e553f65`
- **ST**: `deposit(uint256,address)` -- 2-arg, selector `0x6e553f65` (same selector as sUSDai)
