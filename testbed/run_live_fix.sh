#!/usr/bin/env bash
# testbed/run_live_fix.sh — ONE batched script for the NEW MISSION live work
# (T4–T8). Resume via data/live_status_fix//*.done markers. For the user to
# run with sudo. Agent sandbox has no sudo/tc/netns.
#
# Usage:
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_live_fix.sh
#
set -uo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
STATUS_DIR="data/live_status_fix/"; mkdir -p "$STATUS_DIR" testbed/logs
T0=$(date +%s)
KNOWN_MIN_TOTAL=180

step() {  # id estm cmd...
  local id="$1"; local estm="$2"; shift 2
  if [ -f "$STATUS_DIR/$id.done" ]; then
    echo "[skip] $id (done; delete $STATUS_DIR/$id.done to re-run)"
    return 2
  fi
  echo "===== $id | est ${estm}m | $(date +%H:%M:%S) ====="
  local log="$STATUS_DIR/$id.log"
  if "$@" >"$log" 2>&1; then
    date +%s >"$STATUS_DIR/$id.done"
    tail -3 "$log" | sed 's/^/    /'
    return 0
  fi
  tail -40 "$log" | sed 's/^/    ! /'
  echo "STEP FAILED: $id — log: $log"
  NOW=$(date +%s); echo "elapsed: $(( (NOW-T0)/60 ))m est: ${KNOWN_MIN_TOTAL}m"
  exit 1
}

echo "[run_live_fix] NEW MISSION batch T4–T8 | $(date)"
echo "SEED_START=${SEED_START:-200} SEEDS=${SEEDS:-10}"

# Hygiene
step gate 2 ./testbed/gate.sh
step reset 2 ./testbed/cleanup.sh
step setup 2 ./testbed/setup.sh

# T4: S1–S4 ACIQ with NEW seeds 200–209 (distinct from 0-9/42-51) to avoid
# reusing seeded families. Also ensure all four arms present where missing.
SS="${SEED_START:-200}"; SN="${SEEDS:-10}"
for sc in s1_iso_during_call s2_wan_drop s3_tv_and_gaming s4_capacity_recovery; do
  for arm in b0_fifo b1_cake95 b1_cake_oracle aciq; do
    step "t4_${sc}__${arm}_seed${SS}_${SN}" 10 env PYTHONPATH=/home/mekarz/Desktop/Full-projects/TATA-ELXSI "$PY" run_experiments.py \
      --scenario "$sc" --system "$arm" --seed "$SS" --seeds "$SN" --no-setup
  done
done

# T6: S3 realism change — rerun ALL FOUR ARMS for S3 with the new config
for arm in b0_fifo b1_cake95 b1_cake_oracle aciq; do
  step "t6_s3_${arm}_rerun" 10 env PYTHONPATH=/home/mekarz/Desktop/Full-projects/TATA-ELXSI "$PY" run_experiments.py \
    --scenario s3_tv_and_gaming --system "$arm" --seed "$SS" --seeds "$SN" --no-setup
done

# T5: S5 intent live (existing script is batched; ensure it runs)
step t5_s5 30 ./testbed/s5_live.sh

# T7: corpus DEV-split fixes then fresh held-out (use corpus_live if available)
if [ -x ./testbed/corpus_live.sh ]; then
  step t7_corpus 40 ./testbed/corpus_live.sh
fi

# T8: dashboard/evidence regen
if [ -x ./testbed/dashboard_evidence.sh ]; then
  step t8_dashboard 5 ./testbed/dashboard_evidence.sh
fi

# Regenerate reports
"$PY" tools/build_report.py || true
"$PY" tools/audit_claims.py scan_path_citations | tail -1 || true

# Cleanup and verification
step cleanup 2 ./testbed/cleanup.sh

# Verify no netns remain
if ip netns list 2>/dev/null | grep -qE '^(router|client|wan)'; then
  echo "WARNING: netns still present after cleanup:" >&2
  ip netns list >&2
  exit 2
else
  echo "OK: ip netns list empty (or no netns)"
fi

NOW=$(date +%s)
echo
echo "run_live_fix DONE in $(( (NOW-T0)/60 ))m (est ${KNOWN_MIN_TOTAL}m)"
echo "Review data/experiments/RESULTS.md; regen once more if needed."
