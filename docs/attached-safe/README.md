# Attached Safe

A caliber may own exactly one **attached Safe**: a Safe v1.4.1 whose only owner and only
module is the caliber (threshold 1, no fallback handler, no guard). Counterparties that
_push_ funds to a fixed address (for example Superstate mints and payouts) deliver there. The
Safe is outside the caliber's AUM, so nothing is counted until the caliber pulls it in.

Blueprint: [`blueprints/safe/lifecycle.yaml`](../../blueprints/safe/lifecycle.yaml), one
action, `create` (HARVEST, once per caliber), wired as its own position through
[`instructions/attached-safe.yaml`](../../instructions/attached-safe.yaml). Used by
[Superstate off-chain subscribe/redeem](../superstate-offchain/README.md).

## create

1. Revert if the registry slot is already set (one Safe per caliber).
2. Deploy a SafeProxy v1.4.1 **through CreateX** with an empty initializer, and revert unless
   it landed at `attached_safe_address`.
3. Call `setup` in the same tx, so nobody else can initialise it: owners `[caliber]`,
   threshold 1, module `[caliber]` (via the canonical `SafeModuleSetup`), no fallback handler
   (no ERC-1271 surface), no payment.
4. Check owners == `[caliber]` and modules == `[caliber]`.
5. Write the Safe into the caliber's key-value store at `attached_safe_kv_key`, as the
   **last** call.

There is no way to register an externally deployed Safe: a contract at an arbitrary
address can fake `getOwners()`, a proxy this caliber just deployed cannot.

## The address

`attached_safe_salt` is the caliber's address followed by 12 zero bytes. CreateX
(`0xba5Ed099633D3B313e4D5F7bdc1305d3c28ba5Ed`, same bytecode on every chain) reserves such a
salt for the caller, so **nobody else can deploy at the Safe's address**:

```
guardedSalt = keccak256(bytes32(caliber) ++ salt)
address     = CREATE2(CreateX, guardedSalt, keccak256(initCode))
initCode    = SafeProxyFactory(0x4e1D…ec67).proxyCreationCode() ++ uint256(Safe v1.4.1 singleton)
```

It is a standard Safe proxy, just not deployed by Safe's factory: add it to the Safe UI by
address if needed. Deploy and check it **before** asking a counterparty to allowlist the
address or deliver to it.

## Checks

Weiroll call targets cannot come from a return value, so the Safe is a compile-time input
(`attached_safe_address` in caliber config).

- **Registry check**, first in every action that can reach the Safe or a counterparty: the
  input must equal `KV[attached_safe_kv_key]`. Only `create` writes that slot, after its
  checks, so before `create` every such action reverts.
- **Owner and module checks**, in `create` only. Nothing can change the Safe afterwards: the
  caliber cannot sign, and no blueprint calls into the Safe other than `setup` (in `create`),
  read-only getters, and a module **CALL** of `token.transfer(caliber, amount)`.

## Module calls

The caliber acts as the Safe's module: `execTransactionFromModule(to, 0, data, CALL)`.
`execTransactionFromModule` returns `false` instead of reverting when the inner call fails,
so every caller reverts on `false`.

Weiroll cannot build `bytes`, so `data` comes from the CalldataEncoder
(`calldata_encoder_address`, caliber config). Called with the selector and arguments of a
call, it returns that call's calldata as `bytes`, which the next command passes on. `create`
builds `setup`'s `enableModules([caliber])` the same way.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

contract CalldataEncoder {
    fallback(bytes calldata input) external returns (bytes memory) {
        return abi.encode(input);
    }
}
```

The encoder's output is the calldata the Safe executes, so `calldata_encoder_address` must be
this contract. The mainnet deployment, `0x6843d773eE6D6F173428EEa127b5a16E09cB041b` (runtime
code hash `0xbec230991fca2c717f5f6efd5db938ee4d193b9bb5d936af75e6cae3af334966`), is
**unaudited** and its source is **not verified** on Etherscan. Each chain has its own
deployment address: on Base it is `0x1a7f03da41d0d0a09476def4f7a922acc2d63d34`, with the same
runtime code hash (DLC and loopCUSHY).

`boolean_helper_address` and `caliber_helper_address` are caliber config inputs: they are not
at the same address on every chain.
