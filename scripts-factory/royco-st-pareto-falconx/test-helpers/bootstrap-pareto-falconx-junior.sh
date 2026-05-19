#!/usr/bin/env bash
# Temporary script: bootstrap the Royco JT for Pareto FalconX so the senior
# coverage check stops reverting. Caliber acts as the bootstrapper.
# Stops after the JT bootstrap — does not touch the senior side.
# Safe to delete after use.

set -euo pipefail

export FOUNDRY_DISABLE_NIGHTLY_WARNING=1

# NOTE: SET RPC URL IN ENVIRONMENT VARIABLE
if [ -z "${RPC:-}" ]; then
  echo "Error: RPC environment variable is not set"
  exit 1
fi
CALIBER=0x5476F4E23dAA093Ce6700e1026013c55F7AF9083
ADMIN=0x7c405bbd131e42af506d14e752f2e59b19d49997
ACCESS_MGR=0x7cC6fB28eC7b5e7afC3cB3986141797ffc27253C
USDC=0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48
CDO=0x433D5B175148dA32Ffe1e1A37a939E1b7e79be4d
AA=0xC26A6Fa2C37b38E549a4a1807543801Db684f99C
ROY_JT=0x8e0EC43e51B88AA2324102E1A3D667822bE51a6d
JT_LP_ROLE=0xded17f6f89970f45
DEPOSIT_SELECTOR=0x6e553f65

JT_BOOTSTRAP_USDC=10000000000     # 10,000 USDC (6 dec)
JT_BOOTSTRAP_USDC_HEX=0x2540be400  # same value as hex for tenderly_setErc20Balance
GAS_BAL=0x21e19e0c9bab2400000      # 10,000 ETH (for both ADMIN and CALIBER)

echo "==> 0. Fund admin and caliber with ETH for gas"
cast rpc tenderly_setBalance "$ADMIN"   "$GAS_BAL" --rpc-url "$RPC" >/dev/null
cast rpc tenderly_setBalance "$CALIBER" "$GAS_BAL" --rpc-url "$RPC" >/dev/null

echo "==> 1. Grant JT_LP role to caliber on Royco AccessManager"
cast send --unlocked --from "$ADMIN" "$ACCESS_MGR" \
    "grantRole(uint64,address,uint32)" "$JT_LP_ROLE" "$CALIBER" 0 \
    --rpc-url "$RPC" >/dev/null
echo "  canCall(caliber, ROY_JT, deposit) -> $(cast call "$ACCESS_MGR" \
    "canCall(address,address,bytes4)(bool,uint32)" \
    "$CALIBER" "$ROY_JT" "$DEPOSIT_SELECTOR" --rpc-url "$RPC" | tr '\n' ' ')"

echo "==> 2. Fund caliber with $JT_BOOTSTRAP_USDC base-units USDC for bootstrap"
cast rpc tenderly_setErc20Balance "$USDC" "$CALIBER" "$JT_BOOTSTRAP_USDC_HEX" --rpc-url "$RPC" >/dev/null

echo "==> 3. Acquire AA via Pareto CDO"
EPOCH_RUNNING=$(cast call "$CDO" "isEpochRunning()(bool)" --rpc-url "$RPC")
echo "  isEpochRunning() = $EPOCH_RUNNING"

cast send --unlocked --from "$CALIBER" "$USDC" \
    "approve(address,uint256)" "$CDO" "$JT_BOOTSTRAP_USDC" --rpc-url "$RPC" >/dev/null

if [ "$EPOCH_RUNNING" = "true" ]; then
    echo "  -> depositDuringEpoch(${JT_BOOTSTRAP_USDC}, AATranche)"
    cast send --unlocked --from "$CALIBER" "$CDO" \
        "depositDuringEpoch(uint256,address)" "$JT_BOOTSTRAP_USDC" "$AA" \
        --rpc-url "$RPC" >/dev/null
else
    echo "  -> depositAA(${JT_BOOTSTRAP_USDC})"
    cast send --unlocked --from "$CALIBER" "$CDO" \
        "depositAA(uint256)" "$JT_BOOTSTRAP_USDC" --rpc-url "$RPC" >/dev/null
fi

AA_BAL=$(cast call "$AA" "balanceOf(address)(uint256)" "$CALIBER" --rpc-url "$RPC" | awk '{print $1}')
echo "  AA acquired: $AA_BAL"

echo "==> 4. Deposit all AA into Royco JT"
cast send --unlocked --from "$CALIBER" "$AA" \
    "approve(address,uint256)" "$ROY_JT" "$AA_BAL" --rpc-url "$RPC" >/dev/null
cast send --unlocked --from "$CALIBER" "$ROY_JT" \
    "deposit(uint256,address)" "$AA_BAL" "$CALIBER" --rpc-url "$RPC" >/dev/null

JT_TOTAL=$(cast call "$ROY_JT" "totalSupply()(uint256)" --rpc-url "$RPC")
JT_BAL=$(cast call "$ROY_JT" "balanceOf(address)(uint256)" "$CALIBER" --rpc-url "$RPC")
echo "  Royco JT totalSupply: $JT_TOTAL"
echo "  Royco JT caliber bal: $JT_BAL"

echo
echo "JT bootstrap complete. Senior coverage check should now pass."
echo "Caliber USDC remainder (won't be 0 if depositDuringEpoch refunded a discount):"
cast call "$USDC" "balanceOf(address)(uint256)" "$CALIBER" --rpc-url "$RPC"
