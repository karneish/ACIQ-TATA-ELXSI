#!/usr/bin/env bash
# testbed/deep_trace.sh — one instrumented run + a concurrent raw `tc -s`
# sweep from the bottleneck (the launch-window evidence an artefact can
# only summarize). Scenarios: s1_iso_during_call | s2_wan_drop |
# s4_capacity_recovery; --observe, fresh seed 210, two seeds.
# Usage: sudo ./testbed/deep_trace.sh <scenario>
set -uo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
export PYTHONPATH="$(pwd)"
SC="${1:?scenario required}"
LOG="data/runs_diag/${SC}_deep_tcstats.log"
rm -f "$LOG"
"$PY" run_experiments.py --scenario "$SC" --system aciq --seed 210 \
     --seeds 2 --no-setup --observe --results-dir data/runs_diag &
RUN=$!
for i in $(seq 1 48); do
  echo "--- tc_s_sweep_t=$i" >>"$LOG"
  ip netns exec wan tc -s qdisc show dev veth-w >>"$LOG" 2>&1 || true
  sleep 0.25
done >>"$LOG" 2>&1 &
SWEEP=$!
wait "$RUN"
wait "$SWEEP" 2>/dev/null
echo "deep trace done: $LOG"
