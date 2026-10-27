#!/usr/bin/env bash
# s2b oracle-arm repair (Task 4 remediation, ~45 min, needs sudo).
#
# The engine's CAKE-oracle arm only engaged its declared "0.95 x the true
# FINAL capacity, from t=0" semantics for drop-protocoled scenarios: the
# 20 -> 100 up-step oracle built its tree at 19 (95% of the LAUNCH rate)
# and the ramp oracle at 95. Both violate docs/evidence/s2b-params.md.
# With the corrected engine (aciq/experiment.py: the final-capacity chain
# wins over a mid-run drop time) the 20 mis-protocol runs are re-taken on
# the SAME declared protocols and seeds 800-809 -- no tuning anywhere --
# and RESULTS_S2B.md regenerates from disk.
#
# Resume-safe: each step gets its own .done stamp in
# data/live_status_round2/. ACIQ_VENV points at the venv python.
set -uo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
STATUS="data/live_status_round2"
mkdir -p "$STATUS"

step() {
  local id="$1"; shift
  if [ -f "$STATUS/$id.done" ]; then
    echo "[skip] $id (done; delete $STATUS/$id.done to re-run)"
    return 0
  fi
  echo "===== $id | $(date +%H:%M:%S) ====="
  if "$@" >>"$STATUS/$id.log" 2>&1; then
    date +%s >"$STATUS/$id.done"
    tail -2 "$STATUS/$id.log" | sed 's/^/    /'
  else
    echo "STEP FAILED: $id — log: $STATUS/$id.log"
    exit 1
  fi
}

# the first round-2 batch ran cleanup at the end (netns gone): the repair
# needs the testbed back up before any run -- re-setup, never re-tune.
# First the sink orphan: the first batch left a host-side `call.py
# --listen` alive (it has no lifetime cap; a killed parent never stops
# it), appending lab-idle 0.00 Mbps lines to a COMMITTED seed42 artefact
# every second. Kill every orphan sink, then restore the polluted
# artefact to its committed state so no future commit snapshots idle
# noise. This kills only the three workload turns' LISTENERS, never a
# probe (probes carry --dst and exit on their own duration).
step s2b_fix_sinkorphans bash -c \
  'pkill -9 -f "workloads/call.py --port [0-9]* --listen" 2>/dev/null;
   pkill -9 -f "workloads/bulk.py --port [0-9]* --listen" 2>/dev/null;
   pkill -9 -f "workloads/video.py --port [0-9]* --listen" 2>/dev/null;
   chown -R mekarz:mekarz data/runs/s2_wan_drop__aciq__adaptive__seed42 || true;
   git checkout -- data/runs/s2_wan_drop__aciq__adaptive__seed42/call.sink.log || true;
   chown -R mekarz:mekarz data/runs/s2_wan_drop__aciq__adaptive__seed42 || true;
   sleep 2; tail -1 data/runs/s2_wan_drop__aciq__adaptive__seed42/call.sink.log'

step s2b_fix_setup ./testbed/setup.sh

step s2b_fix_uporphans bash -c \
  'rm -rf data/runs_s2b/s2b_step_up_20to100__b1_cake_oracle__*'
step s2b_fix_uprun "$PY" run_experiments.py \
  --scenario s2b_step_up_20to100 --system b1_cake_oracle \
  --mode static --seed 800 --seeds 10 --no-setup \
  --results-dir data/runs_s2b --report data/REPORT.md

step s2b_fix_ramperase bash -c \
  'rm -rf data/runs_s2b/s2b_ramp_100to30__b1_cake_oracle__*'
step s2b_fix_ramprun "$PY" run_experiments.py \
  --scenario s2b_ramp_100to30 --system b1_cake_oracle \
  --mode static --seed 800 --seeds 10 --no-setup \
  --results-dir data/runs_s2b --report data/REPORT.md

# verify the artifact states the CORRECTED semantics before the report
# is regenerated -- without this gate a reader could be shown a table
# whose "oracle" rows still carried the launch-rate bug.
step s2b_fix_verify "$PY" - <<'EOF'
import json, sys
from pathlib import Path
bad = 0
for d in sorted(Path("data/runs_s2b").iterdir()):
    if not d.is_dir() or "__b1_cake_oracle__" not in d.name:
        continue
    cfg = json.loads((d / "config.json").read_text())
    declared = None
    if cfg.get("recover_to_mbps") is not None:
        declared = 0.95 * cfg["recover_to_mbps"]
    elif cfg.get("ramp_to_mbps") is not None:
        declared = 0.95 * cfg["ramp_to_mbps"]
    elif cfg.get("drop_mbps") is not None and cfg.get("drop_at_s"):
        declared = 0.95 * cfg["drop_mbps"]
    rate = cfg.get("cake_rate_at_apply")
    if not cfg.get("oracle_from_start") or rate is None \
            or abs(rate - declared) > 0.01:
        bad += 1
        print(f"[BROKEN] {d.name}: rate={rate} declared={declared}")
print(f"oracle artefacts checked: rate matches the declared final rate "
      f"on all except {bad}")
if bad:
    sys.exit("oracle rate still wrong somewhere")
EOF

step s2b_fix_report "$PY" tools/build_report.py \
  --runs-root data/runs_s2b --eval-seeds 800-809 \
  --eval-json data/experiments/classifier_corpus_fresh/eval.json \
  --out data/experiments/RESULTS_S2B.md

echo "s2b repair DONE | $(date +%H:%M:%S) | est 45m"
