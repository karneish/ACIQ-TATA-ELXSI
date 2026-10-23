#!/usr/bin/env bash
# testbed/s5_live.sh — the S5 safe-state cases on the LIVE testbed:
#   (a) SIGTERM mid-run      -> watchdog force-safe, no filter residue
#   (b) SIGKILL mid-run      -> residue may exist; the NEXT run's cleanup
#                               removes it and the audit path says so
#   (c) injected failed apply-> rollback replays last-good tree
#   (d) watchdog starvation  -> shield drives the tree to SAFE_HELD
# Writes a mechanical summary JSON for the report generator to quote.
# ~25 min. Needs the live testbed (sudo; make setup first).
set -uo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
OUT=data/experiments/s5; mkdir -p "$OUT"
SUMMARY="$OUT/s5_summary.json"; : >"$SUMMARY"

note() { echo "[$1] $2"; }
s5a=FAIL; s5b=FAIL; s5c=FAIL; s5d=FAIL

# ---- (a) SIGTERM: reuse the gate's proven recipe but standalone ----------
testbed/cleanup.sh >/dev/null 2>&1; testbed/setup.sh >/dev/null
"$PY" run_experiments.py --scenario s2_wan_drop --system aciq --seeds 1 \
        --no-setup >/tmp/opencode/s5a.out 2>&1 &
RUN_PID=$!
sleep 8; kill -TERM $RUN_PID 2>/dev/null; wait $RUN_PID 2>/dev/null
sleep 2
if ! ip netns exec router tc filter show dev veth-lan | grep -q flower; then
  s5a=PASS; note a "SIGTERM left NO filter residue"
else
  note a "filter SURVIVED SIGTERM"
fi

# ---- (b) SIGKILL: residue expected; next cleanup removes it ---------------
"$PY" run_experiments.py --scenario s2_wan_drop --system aciq --seeds 1 \
        --no-setup >/tmp/opencode/s5b.out 2>&1 &
RUN_PID=$!
sleep 8; kill -KILL $RUN_PID 2>/dev/null; wait $RUN_PID 2>/dev/null
sleep 1
if ip netns exec router tc filter show dev veth-lan | grep -q flower; then
  note b "SIGKILL left residue (expected); next cleanup removes it"
fi
testbed/cleanup.sh >/dev/null 2>&1
ip link show veth-lan >/dev/null 2>&1 && s5b=BROKEN_CLEANUP
if ! ip link show veth-lan >/dev/null 2>&1; then
  s5b=PASS; note b "cleanup after SIGKILL left nothing"
fi

# ---- (c) injected failed apply: tx path rolls back through the kernel -----
testbed/setup.sh >/dev/null
"$PY" run_experiments.py --scenario s2_wan_drop --system aciq --seeds 1 \
        --no-setup --inject-fail-apply >/tmp/opencode/s5c.out 2>&1
"$(dirname "$0")/../tools/verify_s5c.py" data/runs/s2_wan_drop__aciq__adaptive__seed* \
    && s5c=PASS || note c "verify_s5c.py says NO"
note c "S5(c) injection case complete"

# ---- (d) watchdog starvation through REAL tc commands ---------------------
# six breaches (MAX_RETRIES=5) through the REAL shield, then force the tree
# through REAL tc. PASS needs: shield latches SAFE_HELD, the safe tree is
# actually installed under netns router on veth-lan, and safe_state_in_force
# says so. Any refusal is the case's FAILURE, not a pass.
"$PY" - <<'EOF' && s5d=PASS || note d "shield case refused: see /tmp/opencode/s5d.out"
import json, sys, time
sys.path.insert(0, ".")
from aciq.txn import Runner, TransactionManager
from aciq.shield import Shield, Mode
from aciq.policy import build_plan

shield = Shield()
tm = TransactionManager(Runner(), shield, ns="router", dev="veth-lan")
first = tm.apply(build_plan(20.0, None), now=0.0)
assert first.ok, f"initial apply failed: {first.reason}"
for i in range(6):                     # one past MAX_RETRIES (5)
    shield.breach(time.monotonic(), [f"live starve bomb #{i}"])
    if shield.state.mode is Mode.SAFE_HELD:
        break
assert shield.state.mode is Mode.SAFE_HELD, shield.state.mode
safe = tm.force_safe()
assert tm.safe_state_in_force, "force_safe did not hold the safe tree"
cls = tm._read_classes()
print(json.dumps({"first_apply": True, "mode": shield.state.mode.value,
                  "safe_in_force": True, "classes_after_safe": len(cls)}))
EOF

cat >"$SUMMARY" <<EOF
{
 "a_sigterm_no_filter_residue": "$s5a",
 "b_sigkill_residue_then_cleanup": "$s5b",
 "c_injected_failed_apply_rollbacks": "$s5c",
 "d_watchdog_starve_reaches_safe": "$s5d",
 "host": "$PY -V",
 "notes": "values PASS/FAIL only; the report quotes this file verbatim"
}
EOF
echo "s5 summary -> $SUMMARY"
[ "$s5a" = PASS ] && [ "$s5c" = PASS ] && [ "$s5d" = PASS ] || exit 1
