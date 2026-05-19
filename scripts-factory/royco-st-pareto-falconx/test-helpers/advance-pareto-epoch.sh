#!/usr/bin/env bash
# Advance the Pareto FalconX CDO by one full epoch boundary.
#
# Two modes, picked from live state:
#   A. If isEpochRunning == true:
#        warp past epochEndDate, then stopEpoch.
#        Result: between epochs, allowAAWithdrawRequest == true.
#        Use this to ENABLE requestWithdraw.
#   B. If isEpochRunning == false:
#        warp past epochEndDate + bufferPeriod, startEpoch,
#        warp past the new epochEndDate, then stopEpoch.
#        Result: epochNumber incremented, between epochs again.
#        Use this AFTER requestWithdraw to ENABLE claimWithdrawRequest.
#
# Borrower and manager are funded + impersonated. Safe to delete after use.

set -euo pipefail

export FOUNDRY_DISABLE_NIGHTLY_WARNING=1

# NOTE: SET RPC URL IN ENVIRONMENT VARIABLE
if [ -z "${RPC:-}" ]; then
  echo "Error: RPC environment variable is not set"
  exit 1
fi

CDO=0x433D5B175148dA32Ffe1e1A37a939E1b7e79be4d
CREDIT_VAULT=0x17E9Ab2992dfecBe779a06A92a6cDB9fE6aEeEf3
USDC=0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48
AA=0xC26A6Fa2C37b38E549a4a1807543801Db684f99C

ETH_BAL=0x21e19e0c9bab2400000        # 10,000 ETH
USDC_BORROWER_BAL=0x1d1a94a200000     # 512,000,000 USDC
TIME_PAD_SECONDS=600                  # how far past each deadline to jump

read_uint() { cast call "$1" "$2" --rpc-url "$RPC" | awk '{print $1}'; }

set_next_ts() {
  local ts=$1
  local ts_hex
  ts_hex=$(printf '0x%x' "$ts")
  cast rpc tenderly_setNextBlockTimestamp "$ts_hex" --rpc-url "$RPC" >/dev/null
}

fund_borrower_and_manager() {
  cast rpc tenderly_setBalance "$MANAGER"  "$ETH_BAL" --rpc-url "$RPC" >/dev/null
  cast rpc tenderly_setBalance "$BORROWER" "$ETH_BAL" --rpc-url "$RPC" >/dev/null
  cast rpc tenderly_setErc20Balance "$USDC" "$BORROWER" "$USDC_BORROWER_BAL" --rpc-url "$RPC" >/dev/null
  cast send --unlocked --from "$BORROWER" "$USDC" \
      "approve(address,uint256)" "$CDO" \
      0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff \
      --rpc-url "$RPC" >/dev/null
}

do_stop_epoch() {
  local apr=$1
  echo "  stopEpoch(_newApr=$apr, _interest=0) from manager"
  cast send --unlocked --from "$MANAGER" "$CDO" \
      "stopEpoch(uint256,uint256)" "$apr" 0 \
      --rpc-url "$RPC" >/dev/null
}

do_start_epoch() {
  echo "  startEpoch() from manager"
  cast send --unlocked --from "$MANAGER" "$CDO" \
      "startEpoch()" \
      --rpc-url "$RPC" >/dev/null
}

# ---------- Read live state ----------
echo "==> 0. Read live CDO + CreditVault state"
EPOCH_END=$(read_uint "$CDO" "epochEndDate()(uint256)")
EPOCH_RUNNING=$(cast call "$CDO" "isEpochRunning()(bool)" --rpc-url "$RPC")
APR=$(read_uint "$CREDIT_VAULT" "unscaledApr()(uint256)")
MANAGER=$(cast call "$CREDIT_VAULT" "manager()(address)" --rpc-url "$RPC")
BORROWER=$(cast call "$CREDIT_VAULT" "borrower()(address)" --rpc-url "$RPC")
BUFFER=$(read_uint "$CDO" "bufferPeriod()(uint256)")
EPOCH_DURATION=$(read_uint "$CDO" "epochDuration()(uint256)")
PENDING_WITHDRAWS=$(read_uint "$CREDIT_VAULT" "pendingWithdraws()(uint256)")
EXPECTED_INTEREST=$(read_uint "$CDO" "expectedEpochInterest()(uint256)")
EPOCH_NUMBER=$(read_uint "$CREDIT_VAULT" "epochNumber()(uint256)")

echo "  epochEndDate         = $EPOCH_END"
echo "  isEpochRunning       = $EPOCH_RUNNING"
echo "  bufferPeriod         = $BUFFER"
echo "  epochDuration        = $EPOCH_DURATION"
echo "  unscaledApr          = $APR"
echo "  manager              = $MANAGER"
echo "  borrower             = $BORROWER"
echo "  pendingWithdraws     = $PENDING_WITHDRAWS"
echo "  expectedEpochInterest= $EXPECTED_INTEREST"
echo "  epochNumber          = $EPOCH_NUMBER"

echo
echo "==> 1. Fund manager and borrower (eth + usdc + approval)"
fund_borrower_and_manager

if [ "$EPOCH_RUNNING" = "true" ]; then
  # ---------- Mode A: just stop the running epoch ----------
  echo
  echo "==> Mode A: epoch running -> warp past epochEndDate and stopEpoch"
  set_next_ts $(( EPOCH_END + TIME_PAD_SECONDS ))
  do_stop_epoch "$APR"
else
  # ---------- Mode B: full cycle (start a new epoch, run it, stop it) ----------
  echo
  echo "==> Mode B: epoch not running -> startEpoch + warp + stopEpoch"

  # Step 1: warp past previous epochEndDate + bufferPeriod and startEpoch
  START_TS=$(( EPOCH_END + BUFFER + TIME_PAD_SECONDS ))
  echo "  warp to $START_TS (= epochEndDate + bufferPeriod + ${TIME_PAD_SECONDS}s)"
  set_next_ts "$START_TS"
  do_start_epoch

  # Read the freshly-set epochEndDate (= start_ts + epochDuration)
  NEW_EPOCH_END=$(read_uint "$CDO" "epochEndDate()(uint256)")
  echo "  new epochEndDate     = $NEW_EPOCH_END"

  # Step 2: warp past the new epochEndDate and stopEpoch
  echo "  warp to $(( NEW_EPOCH_END + TIME_PAD_SECONDS )) (= new epochEndDate + ${TIME_PAD_SECONDS}s)"
  set_next_ts $(( NEW_EPOCH_END + TIME_PAD_SECONDS ))
  do_stop_epoch "$APR"
fi

echo
echo "==> Verify post-state"
echo "  isEpochRunning           = $(cast call "$CDO" "isEpochRunning()(bool)" --rpc-url "$RPC")"
echo "  paused                   = $(cast call "$CDO" "paused()(bool)" --rpc-url "$RPC")"
echo "  allowAAWithdrawRequest   = $(cast call "$CDO" "allowAAWithdrawRequest()(bool)" --rpc-url "$RPC")"
echo "  epochNumber              = $(read_uint "$CREDIT_VAULT" "epochNumber()(uint256)")"
echo "  tranchePrice(AA) (6dec)  = $(cast call "$CDO" "tranchePrice(address)(uint256)" "$AA" --rpc-url "$RPC")"

echo
echo "Done. If you just ran Mode B after a requestWithdraw, claimWithdrawRequest"
echo "should now be callable (epochNumber > lastWithdrawRequest[caliber])."
