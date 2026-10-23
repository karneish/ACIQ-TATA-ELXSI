#!/usr/bin/env bash
# Phase 5/6: the experiment matrix + paired comparison. THE USER RUNS THIS
# (needs sudo for the testbed). 10 seeds x 2 systems across the WAN-drop
# scenario, then the Wilcoxon paired table.
#
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/phase5.sh
#
# ~40 min wall clock at 40 s per run x 20 runs plus settling. Artifacts land
# in data/runs/; matrix + comparison in data/experiments/phase5/.
set -euo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"

testbed/cleanup.sh 2>/dev/null || true
testbed/setup.sh >/dev/null 2>&1 || true
ip netns list >/dev/null 2>&1 || { echo "testbed up failed"; exit 1; }
echo "[phase5] testbed ready at $(date -Iseconds)"

"$VENV/bin/python" tools/phase_matrix.py \
    --scenario s2_wan_drop --systems b0_fifo,aciq \
    --seeds 0,1,2,3,4,5,6,7,8,9 \
    --link-mbps 100 --drop-mbps 20 --drop-at 10 \
    --out data/experiments/phase5

echo "[phase5] matrix complete; comparison written to the phase-5 comparison output"
