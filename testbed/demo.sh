#!/usr/bin/env bash
# testbed/demo.sh — the 12-minute live demo. Everything from a clean testbed
# to a rendered report for ONE scenario. 3 arms x 3 seeds, then evidence,
# corpus sampling at reduced length, and the offline report.
#
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv SCENARIO=s2_wan_drop SEEDS=3 \
#        ./testbed/demo.sh
set -euo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
SCENARIO="${SCENARIO:-s2_wan_drop}"
SEEDS="${SEEDS:-3}"
LOGS=testbed/logs; mkdir -p "$LOGS"
LOG="$LOGS/demo-$(date +%Y%m%d-%H%M%S).log"; exec > >(tee -a "$LOG") 2>&1

echo "== demo: $SCENARIO x 4 arms x $SEEDS seeds =="
testbed/cleanup.sh 2>/dev/null || true
testbed/setup.sh

for arm in b0_fifo b1_cake95 aciq; do
  MODE=adaptive; [ "$arm" = aciq ] && MODE=adaptive || MODE=static
  echo "-- arm $arm"
  "$PY" run_experiments.py --scenario "$SCENARIO" --system "$arm" \
        --mode "$MODE" --seeds "$SEEDS" --no-setup
done

echo "-- offline report (reads raw artefacts only)"
$PY tools/build_report.py
echo "-- dashboard evidence for the last ACIQ run"
testbed/dashboard_evidence.sh || echo "warn: dashboard evidence failed, continuing"
echo "-- demo log: $LOG"
