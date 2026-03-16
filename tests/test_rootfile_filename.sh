#!/usr/bin/env bash
# Tests for the rootfile filename validation logic in .github/workflows/transpiler.yaml
# (step: "Verify added rootfiles are newer than existing").
# Keep run_check() in sync with that workflow step.
#
# Usage: bash tests/test_rootfile_filename.sh
set -euo pipefail
export LC_ALL=C

PASS=0
FAIL=0

# Mirrors the workflow logic. Takes space-separated list of added rootfile paths.
# Returns 0 if all pass, 1 if any fail.
run_check() {
  local added_rootfiles="$1"

  for file in ${added_rootfiles}; do
    local dir base
    dir=$(cd -- "$(dirname -- "$file")" && pwd)
    base=$(basename -- "$file")

    # Find newest pre-existing (non-added) file in this directory
    local newest_preexisting=""
    for candidate in $(cd -- "$dir" && LC_ALL=C ls -1Ap | grep -v '/$' | LC_ALL=C sort -r); do
      local cand_rel
      cand_rel="$(dirname -- "$file")/$candidate"
      if ! echo " ${added_rootfiles} " | grep -qF " ${cand_rel} "; then
        newest_preexisting="$candidate"
        break
      fi
    done

    # Bootstrap: no pre-existing files — any name is fine
    [[ -z "$newest_preexisting" ]] && continue

    if [[ ! "$base" > "$newest_preexisting" ]]; then
      return 1
    fi
  done

  return 0
}

assert_pass() {
  local name="$1"; shift
  if run_check "$*"; then
    echo "  PASS: $name"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $name (expected pass)"
    FAIL=$((FAIL + 1))
  fi
}

assert_fail() {
  local name="$1"; shift
  if run_check "$*"; then
    echo "  FAIL: $name (expected fail)"
    FAIL=$((FAIL + 1))
  else
    echo "  PASS: $name"
    PASS=$((PASS + 1))
  fi
}

# ── Setup ────────────────────────────────────────────────────────────
TEST_TMPDIR=$(mktemp -d)
trap 'rm -rf "$TEST_TMPDIR"' EXIT

# ── Test 1: single added file is the newest → pass ──────────────────
echo "Test 1: single added file is the newest"
d="$TEST_TMPDIR/t1/rootfiles"; mkdir -p "$d"
touch "$d/20260101-init.toml" "$d/20260313-new.toml"
assert_pass "single newest file" "$d/20260313-new.toml"

# ── Test 2: single added file is NOT the newest → fail ──────────────
echo "Test 2: single added file is not the newest"
d="$TEST_TMPDIR/t2/rootfiles"; mkdir -p "$d"
touch "$d/20260101-old.toml" "$d/20260313-existing.toml"
assert_fail "single older file" "$d/20260101-old.toml"

# ── Test 3: bootstrap — multiple added, no pre-existing → pass ──────
echo "Test 3: bootstrap with two files, no pre-existing"
d="$TEST_TMPDIR/t3/rootfiles"; mkdir -p "$d"
touch "$d/20260217-current.toml" "$d/20260313-add-merkl.toml"
assert_pass "bootstrap two files" "$d/20260217-current.toml $d/20260313-add-merkl.toml"

# ── Test 4: multiple dirs, each added is newest → pass ──────────────
echo "Test 4: two directories, each added file is newest"
d1="$TEST_TMPDIR/t4a/rootfiles"; d2="$TEST_TMPDIR/t4b/rootfiles"; mkdir -p "$d1" "$d2"
touch "$d1/20260101-init.toml" "$d1/20260313-new.toml"
touch "$d2/20260201-init.toml" "$d2/20260314-new.toml"
assert_pass "two dirs both newest" "$d1/20260313-new.toml $d2/20260314-new.toml"

# ── Test 5: added file older than pre-existing → fail ───────────────
echo "Test 5: added file older than a pre-existing file"
d="$TEST_TMPDIR/t5/rootfiles"; mkdir -p "$d"
touch "$d/20260101-old.toml" "$d/20260315-preexisting.toml" "$d/20260313-added.toml"
assert_fail "added older than existing" "$d/20260313-added.toml"

# ── Test 6: original CI bug — bootstrap new machine ─────────────────
echo "Test 6: original CI bug scenario (bootstrap with history)"
d="$TEST_TMPDIR/t6/arbitrum/rootfiles"; mkdir -p "$d"
touch "$d/20260217-current.toml" "$d/20260313-add-merkl.toml"
assert_pass "original CI bug" "$d/20260217-current.toml $d/20260313-add-merkl.toml"

# ── Test 7: added + pre-existing, all added are newer → pass ────────
echo "Test 7: two added files both newer than pre-existing"
d="$TEST_TMPDIR/t7/rootfiles"; mkdir -p "$d"
touch "$d/20260101-old.toml" "$d/20260313-a.toml" "$d/20260314-b.toml"
assert_pass "both added newer" "$d/20260313-a.toml $d/20260314-b.toml"

# ── Test 8: added + pre-existing, one added is older → fail ─────────
echo "Test 8: two added files, one older than pre-existing"
d="$TEST_TMPDIR/t8/rootfiles"; mkdir -p "$d"
touch "$d/20260201-preexisting.toml" "$d/20260101-backdated.toml" "$d/20260313-new.toml"
assert_fail "one added older than existing" "$d/20260101-backdated.toml $d/20260313-new.toml"

# ── Summary ──────────────────────────────────────────────────────────
echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] || exit 1
