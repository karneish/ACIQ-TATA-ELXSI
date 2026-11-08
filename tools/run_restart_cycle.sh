#!/usr/bin/env bash
# Crash-restart reconciliation live cycle.
#
# Starts an s2 run, SIGKILLs the runner mid-run (the controller dies, the
# tc tree it committed stays in the kernel), then reruns the same scenario
# and seed. On the second start, ExperimentRunner calls
# Harness.reconcile_after_restart(), which reads the live `tc qdisc` tree
# and adopts it as truth instead of assuming empty state.
#
# Pass criteria: the second run completes with policy_changes > 0,
# estimator lands, and result.json exists. The first (killed) run leaves
# an incomplete dir, which run_experiments cleans on rerun.
set -euo pipefail
SEED="${SEED:-1500}"
echo "== restart cycle seed $SEED (kill -9 mid-run, then rerun) =="
echo "-- phase 1: run, kill after 15s --"
sudo python3 run_experiments.py --scenario s2_wan_drop --system aciq \
  --mode adaptive --seed "$SEED" --seeds 1 --drop-at 10 --no-setup &
RUNNER=$!
sleep 15
kill -9 $RUNNER 2>/dev/null || true
wait $RUNNER 2>/dev/null || echo "(first run killed, as intended)"
echo "-- phase 2: rerun same scenario+seed; reconcile adopts live tree --"
sudo python3 run_experiments.py --scenario s2_wan_drop --system aciq \
  --mode adaptive --seed "$SEED" --seeds 1 --drop-at 10 --no-setup
echo "-- result --"
python3 - <<PY
import json
r = json.load(open("data/runs/s2_wan_drop__aciq__adaptive__seed${SEED}/result.json"))
print("estimator:", r["estimator_mbps"], "policy_changes:", r["policy_changes"])
assert r["policy_changes"] > 0, "second run must re-apply policy after reconcile"
print("restart cycle: PASS")
PY
