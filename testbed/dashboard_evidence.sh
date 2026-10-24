#!/usr/bin/env bash
# testbed/dashboard_evidence.sh — capture a dashboard render for a real, live
# run. The report's dashboard section quotes THIS output, not a promise.
# Needs the live testbed. ~2 min.
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/dashboard_evidence.sh
set -euo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
DEST="data/experiments/dashboard"
mkdir -p "$DEST" testbed/logs
LOG="testbed/logs/dashboard-evidence.log"

testbed/cleanup.sh 2>/dev/null || true
testbed/setup.sh >/dev/null

echo "[dash] one ACIQ run (s2_wan_drop, seed 42), then render the page"
# The capture run lives under the dashboard evidence dir (RUNDATA below),
# NOT data/runs: data/runs is committed evidence and must never be
# overwritten in place by a later capture (that happened once; this path
# change is the fix).
RUNDATA="$DEST/dashboard_run"
"$PY" run_experiments.py --scenario s2_wan_drop --system aciq --seed 42 \
  --seeds 1 --results-dir "$RUNDATA" >"$LOG" 2>&1 || true
RUN=$(ls -td "$RUNDATA"/s2_wan_drop__* 2>/dev/null | head -1)
echo "[dash] run dir: $RUN"

"$PY" - "$RUN" "$DEST/dashboard.html" <<'EOF'
import json, sys
from aciq.dashboard import write_snapshot
run, dest = sys.argv[1], sys.argv[2]
rows = [json.loads(l) for l in open(f"{run}/samples.jsonl") if l.strip()]
res = json.load(open(f"{run}/result.json"))
# notes are untimed prose; timed marks come from config/the run itself
notes = "; ".join(res.get("notes", []))
subtitle = f"live evidence - {run}" + (f" | {notes}" if notes else "")
n = write_snapshot(rows, dest,
                   subtitle=subtitle)
print("rendered", dest, "bytes:", n if isinstance(n, int) else "-")
EOF
cp "$RUN/result.json" "$DEST/result.json"
cp "$RUN/samples.jsonl" "$DEST/samples.jsonl"
echo "[dash] evidence in $DEST"
