#!/usr/bin/env bash
# Phase 6 COMPLETION gate: the full matrix BOTH EDGES and BOTH BASELINES.
#
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/phase6.sh
#
# 10 seeds x 3 systems (B0 pfifo, B1 cake@95%, ACIQ engine) x 2 scenarios:
#   s2_wan_drop          100 -> 20 Mbps at t=10, stays down (the drop edge)
#   s4_capacity_recovery  100 -> 20 at t=10, back to 100 at t=30 (the up edge)
#
# 60 real runs, roughly an hour of wall clock. Outputs:
#   data/runs/... (60 run artefacts)
#   the phase-6 matrix output
#   the phase-6 comparison output  (seed-paired rows, per scenario)
#   the paired markdown report    (human-readable paired table)
set -euo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"

testbed/cleanup.sh 2>/dev/null || true
testbed/setup.sh >/dev/null 2>&1 || true
ip netns list >/dev/null 2>&1 || { echo "testbed up failed"; exit 1; }
echo "[phase6] testbed ready at $(date -Iseconds)"

"$VENV/bin/python" tools/phase_matrix.py \
    --scenarios s2_wan_drop,s4_capacity_recovery \
    --systems b0_fifo,b1_cake95,aciq \
    --seeds 0,1,2,3,4,5,6,7,8,9 \
    --link-mbps 100 --drop-mbps 20 --drop-at 10 --recover-at 30 \
    --out data/experiments/phase6

echo "[phase6] done; artifacts in data/experiments/phase6/"
