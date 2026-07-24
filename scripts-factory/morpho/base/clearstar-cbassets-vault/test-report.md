# makina-x E2E — chronograph-x / base (pos 133242423309628000059155946577244883881)

**Rootfile:** `/Users/augustin/Desktop/makina/config/machines/chronograph-x/base/rootfiles/20260723-morpho-clearstar-cbassets.toml`
**Module:** `0x785db5f3F3Ad18D6291689907D319954AF79A03E` · **Safe:** `0x9f0f855A7370cc30e24924258214681A782A34aC`
**Base token:** USDC `0x833589fcd6edb6e08f4c7c32d4f71b54bda02913` (6 dec) · **Position token:** `0x91C056B6d4311a743614FBc03ac32d4E6A2d3a3c`
**Chain:** 8453 (base) · **Deposit amount:** 10000.0
**Type:** makina-x, management-only — **no NAV accounting asserted** (by design).

| Check                                   | Result |
| --------------------------------------- | ------ |
| compiled root == on-chain leaf encoding | PASS   |
| deposit → withdraw lifecycle            | PASS   |

**Overall: PASS**

<details><summary>forge output</summary>

```
Compiling 20 files with Solc 0.8.28
Solc 0.8.28 finished in 787.02ms
Compiler run successful with warnings:
Warning (5667): Unused function parameter. Remove or comment out the variable name to silence this warning.
   --> test/MakinaXE2E.t.sol:115:29:
    |
115 |     function _withdrawInstr(uint256 amount) internal pure returns (IMakinaXModule.Instruction memory ix) {
    |                             ^^^^^^^^^^^^^^


Ran 2 tests for test/MakinaXE2E.t.sol:MakinaXE2E
[PASS] test_compiledRootMatchesTranspiler() (gas: 11311)
Logs:
  0x249b881a6fe68d76bc50a47b62c1aa7e691300f3212a602be648be3d42170365

[PASS] test_depositThenWithdraw() (gas: 744652)
Logs:
  operatingMode: 1
  base before: 10000000000
  posToken before: 0
  base after deposit: 0
  posToken after deposit: 9796658797661645694004
  base after withdraw: 9999999999
  posToken after withdraw: 0

Suite result: ok. 2 passed; 0 failed; 0 skipped; finished in 5.28s (5.17s CPU time)

Ran 1 test suite in 5.31s (5.28s CPU time): 2 tests passed, 0 failed, 0 skipped (2 total tests)
```

</details>
