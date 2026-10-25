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
# Per-step stdout of the live runs. /tmp/opencode was the agent sandbox's
# scratch dir and never existed on a plain host: the redirect failed BEFORE
# the run started, so a (SIGTERM/SIGKILL/injection) case reported on a run
# that never launched. mktemp gives each step its own writable dir.
LOGDIR="$(mktemp -d /tmp/aciq-s5-XXXXXXXX)"
echo "[s5] scratch: $LOGDIR"

note() { echo "[$1] $2"; }
s5a=FAIL; s5b=FAIL; s5c=FAIL; s5d=FAIL

# ---- (a) SIGTERM: run with enforcement so there IS a filter to outlive ----
testbed/cleanup.sh >/dev/null 2>&1; testbed/setup.sh >/dev/null
"$PY" run_experiments.py --scenario s2_wan_drop --system aciq --seeds 1 \
        --no-setup --enforce >"$LOGDIR/s5a.out" 2>&1 &
RUN_PID=$!
# enforcement takes the whole first-half of the run (probes, verdicts);
# give it long enough that an installed filter is certain, not assumed
sleep 20
ip netns exec router tc filter show dev veth-lan | grep -q "dst_port" \
  && note a "pre: filters installed (witness)" \
  || note a "WARNING: no filter seen before SIGTERM; residue test is weak"
kill -TERM $RUN_PID 2>/dev/null; wait $RUN_PID 2>/dev/null
sleep 2
if ! ip netns exec router tc filter show dev veth-lan | grep -q "dst_port"; then
  s5a=PASS; note a "SIGTERM left NO filter residue (watchdog force-safe)"
else
  note a "filter SURVIVED SIGTERM (watchdog not engaged on the driver)"
fi

# ---- (b) SIGKILL: residue expected; next cleanup removes it ---------------
"$PY" run_experiments.py --scenario s2_wan_drop --system aciq --seeds 1 \
        --no-setup --enforce >"$LOGDIR/s5b.out" 2>&1 &
RUN_PID=$!
sleep 20; kill -KILL $RUN_PID 2>/dev/null; wait $RUN_PID 2>/dev/null
sleep 1
if ip netns exec router tc filter show dev veth-lan | grep -q "dst_port"; then
  note b "SIGKILL left residue (expected); next cleanup removes it"
fi
testbed/cleanup.sh >/dev/null 2>&1
if ! ip link show veth-lan >/dev/null 2>&1; then
  s5b=PASS; note b "cleanup after SIGKILL left nothing"
else
  note b "cleanup failed to remove veth-lan"
fi

# ---- (c) injected failed apply: tx path rolls back through the kernel -----
# The injection arms at the run's midpoint (t ~= 19s of 40s) and fails the
# NEXT class-add the transaction issues. Without a capacity drop the governor
# converges inside the first ~4s and the tree is then held steady -- no apply
# ever happens after 19s, the injected failure never fires, and there is no
# rollback to verify. The drop at t=25 guarantees a real, drop-triggered apply
# AFTER arming: it fails at the kernel, the rollback replays last-good, and
# the governor's post-drop ratchet re-applies on the following ticks, which
# is exactly the "run continued to commit" witness the verifier needs.
testbed/setup.sh >/dev/null
# a fresh UNUSED seed so the verifier judges exactly this injected run;
# the family glob would sweep unwitnessed normal runs and fail the check.
"$PY" run_experiments.py --scenario s2_wan_drop --system aciq \
        --seed 555 --seeds 1 --no-setup --drop-at 25 \
        --inject-fail-apply >"$LOGDIR/s5c.out" 2>&1
"$PY" tools/verify_s5c.py data/runs/s2_wan_drop__aciq__adaptive__seed555; \
    rc_c=$?; [ $rc_c -eq 0 ] && s5c=PASS || note c "verify_s5c.py says NO (rc=$rc_c)"
note c "S5(c) injection case complete"

# ---- (d) watchdog starvation through REAL tc commands ---------------------
# six breaches (MAX_RETRIES=5) through the REAL shield, then force the tree
# through REAL tc. PASS needs: shield latches SAFE_HELD, the safe tree is
# actually installed under netns router on veth-lan, and safe_state_in_force
# says so. Any refusal is the case's FAILURE, not a pass.
"$PY" - >"$LOGDIR/s5d.out" <<'EOF' && s5d=PASS || note d "shield case refused: see "$LOGDIR/s5d.out""
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
