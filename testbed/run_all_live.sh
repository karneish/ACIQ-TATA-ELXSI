#!/usr/bin/env bash
# testbed/run_all_live.sh — EVERY privileged step of the fix round, in order,
# with per-step logs, a status-file resume (run again and completed steps are
# skipped), and the printed runtime estimate. ONE sudo command for the user.
#
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_all_live.sh
#
# Steps are named so the resume keys stay stable across re-runs. Total ~3 h
# wall clock on the reference host. Nothing here is simulated: steps that
# would need the kernel fail loudly if the kernel refuses.
set -uo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
STATUS_DIR="data/live_status"; mkdir -p "$STATUS_DIR" testbed/logs
T0=$(date +%s); KNOWN_TIME_TOTAL=10200
SEEDS="${SEEDS:-10}"

step() {  # step <id> <estimated min> <cmd...>
  local id="$1"; shift 2
  if [ -f "$STATUS_DIR/$id.done" ]; then
    echo "[skip] $id (done; delete $STATUS_DIR/$id.done to re-run)"
    return 2
  fi
  echo "===== $id | $(date +%H:%M:%S) ====="
  local log="$STATUS_DIR/$id.log"
  if "$@" >"$log" 2>&1; then
    date +%s >"$STATUS_DIR/$id.done"
    tail -3 "$log" | sed 's/^/    /'
    return 0
  fi
  cat "$log" | tail -30 | sed 's/^/    ! /'
  echo "STEP FAILED: $id — log: $log"
  NOW=$(date +%s)
  echo "elapsed total: $(( (NOW-T0)/60 )) min (est. total: $((KNOWN_TIME_TOTAL/60)))"
  exit 1
}

echo "[run_all_v4] live fix-round pipeline, SEEDS=$SEEDS"

step gate        5  ./testbed/gate.sh
# a leftover testbed from ANY previous session makes `setup` die on
# "namespace file exists"; clean FIRST, always (cleanup.sh is idempotent).
step reset       2  ./testbed/cleanup.sh
step setup       2  ./testbed/setup.sh

# -- four-arm matrices ------------------------------------------------------
# S2 and S4 already carry b0/cake95/aciq x 10 seeds; the fix-round gap is the
# ORACLE arm plus FULL seed counts for s1/s3 across all four arms.
for sc in s1_iso_during_call s3_tv_and_gaming; do
  for arm in b0_fifo b1_cake95 b1_cake_oracle aciq; do
    step "m_${sc}__${arm}" 8 \
      "$PY" run_experiments.py --scenario "$sc" --system "$arm" \
        --seeds "$SEEDS" --no-setup
  done
done
for sc in s2_wan_drop s4_capacity_recovery; do
  for arm in b1_cake_oracle; do
    step "m_${sc}__${arm}" 8 \
      "$PY" run_experiments.py --scenario "$sc" --system "$arm" \
        --seeds "$SEEDS" --no-setup
  done
done

# -- fairness / starvation under intent (T3 fixture on live workloads) ------
# Lease TTL 15 s INSIDE a 60 s run: the length so expiry, not just effect,
# is measured. Continuous bulk is part of the scenario's own workloads.
step intent_starvation 4 \
  "$PY" run_experiments.py --scenario s4_capacity_recovery --system aciq \
     --enforce --lease 203.0.113.2 --lease-weight 0.5 --lease-ttl-s 15 \
     --seed 7 --seeds 1 --no-setup

# -- safe-state / failure injection (S5) ------------------------------------
step s5_live       25 ./testbed/s5_live.sh

# -- resources/CPU overhead: closed-loop sampling already records
#    resources.decision_ms and cpu on every adaptive run above; nothing
#    extra to execute.

# -- classifier corpus ------------------------------------------------------
step corpus      40  ./testbed/corpus_live.sh

# -- dashboard evidence -----------------------------------------------------
step dashboard   3  ./testbed/dashboard_evidence.sh

# -- final teardown (ALWAYS, even after failures above) ---------------------
step cleanup     1  ./testbed/cleanup.sh

# -- offline report + evidence commit note ----------------------------------
"$PY" tools/build_report.py
"$PY" tools/audit_claims.py scan_path_citations | tail -1

NOW=$(date +%s)
echo
echo "ALL LIVE STEPS DONE in $(( (NOW-T0)/60 )) min (est. was $((KNOWN_TIME_TOTAL/60)))"
echo "Next for the fix round: review data/experiments/RESULTS.md and commit"
echo "under git; oracle-arm runs must NOT be described as operator-real."
