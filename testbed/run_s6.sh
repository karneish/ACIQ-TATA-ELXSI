#!/usr/bin/env bash
# testbed/run_s6.sh — the S6 intent scenario on the LIVE testbed (TASK 4).
#   Background bulk + call + gaming on a healthy link. At t~1s one API intent
#   is requested through the REAL surface (IntentService, POST /intent) for
#   the gaming device, TTL 15s -> expires INSIDE the 40s run, and the plan
#   must auto-revert. 10 seeds, ACIQ vs B0 and CAKE-static, which have no
#   intent surface and declare that incapability.
# Writes a mechanical summary JSON for the report generator to quote.
# ~35 min (30 runs x ~70s). Needs the live testbed (sudo; make setup first).
set -uo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
OUT=data/experiments/s6; mkdir -p "$OUT"
SUMMARY="$OUT/s6_summary.json"; : >"$SUMMARY"

testbed/cleanup.sh >/dev/null 2>&1; testbed/setup.sh >/dev/null

"$PY" run_experiments.py --scenario s6_intent_expire \
     --system aciq --system b0_fifo --system b1_cake95 \
     --seeds 10 --seed 300 --no-setup \
     --api-intent --intent-at 1.0 --intent-ttl 15.0 --intent-weight 0.5 \
     >"$OUT/run_s6.log" 2>&1
rc=$?

# The verifier decides from the artefacts alone (result.json per seed,
# samples.jsonl lease_active series, <label>.sink.log per-second receiver
# lines). It prints one machine-readable line; run_s6 never writes its own
# verdict so the summary and the verifier cannot disagree.
VERDICT_LINE=$("$PY" tools/verify_s6.py "$OUT/run_s6.log" 2>&1)
echo "$VERDICT_LINE" | tee "$OUT/verify_s6.out"
granted=$(echo "$VERDICT_LINE" | grep -o 'granted=[A-Z]*' | head -1 | cut -d= -f2)
reverted=$(echo "$VERDICT_LINE" | grep -o 'reverted=[A-Z]*' | head -1 | cut -d= -f2)
floors=$(echo "$VERDICT_LINE" | grep -o 'floors=[A-Z]*' | head -1 | cut -d= -f2)
baselines=$(echo "$VERDICT_LINE" | grep -o 'baselines=[A-Z]*' | head -1 | cut -d= -f2)

cat >"$SUMMARY" <<EOF
{
 "intent_granted": "${granted:-NA}",
 "auto_reverted_at_expiry": "${reverted:-NA}",
 "floors_held": "${floors:-NA}",
 "baselines_declare_unsupported": "${baselines:-NA}",
 "run_rc": $rc,
 "host": "$($PY -V 2>&1)",
 "notes": "values PASS/FAIL/NA; per-seed details in data/runs/"
}
EOF
echo "s6 summary -> $SUMMARY"
[ "$granted" = PASS ] && [ "$reverted" = PASS ] && [ "$floors" = PASS ] \
  && [ "$baselines" = PASS ] || exit 1
