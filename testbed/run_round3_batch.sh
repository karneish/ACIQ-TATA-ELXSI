#!/usr/bin/env bash
# testbed/run_round3_batch.sh — THE ONE batched privileged script for the
# round-3 brief (principle fixes: demand-probe up + severe-drop landing).
#
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_round3_batch.sh dev    # tuning band, seeds 1000-1009
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_round3_batch.sh final  # FROZEN band, seeds 1100-1109
#
# Only run `final` AFTER the agent has frozen constants from the dev band
# (docs/evidence/round3-params.md: the final band runs ONCE, never for
# tuning; any commit change between the constants-freeze and the final
# band regenerates provenance and invalidates the freeze).
#
# Resume-safe: every step writes data/live_status_round3/band_<id>.done;
# delete one to re-run that step. Band map:
#   data/runs_dev3    — DEV band (fallback seeds 1000-1009), tuning only
#   data/runs_final3  — FROZEN final band (seeds 1100-1109), once
#   reports           — RESULTS_* regenerated from disk only
#
# Arms: the brief forbids touching B0/CAKE arms; the two new round-3 arms
# (CAKE-conservative 0.50x static, CAKE-adaptive) run the opened scenarios
# so the report can compare queue disciplines on the same shapes ACIQ
# runs. Steps 1-20 min each, est ~6.5-9.5 h for dev, ~12-14 h for final.
# Run inside tmux. No sudo password is requested by any step; netns must
# be empty at exit (the last step checks).
set -uo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
export PYTHONPATH="$(pwd)"
BAND="${1:-dev}"

case "$BAND" in
  dev)
    SEED0=1000; RUNS_DIR=data/runs_dev3; EST_TOTAL=420    # minutes
    SCENARIOS="s2b_step_50 s2b_step_10 s2b_step_up_20to100 s2b_ramp_100to30 \
s7_up_20to60 s7_up_30to100 s7_rampup_30to100 s7_down_100to15 s7_down_100to8 \
s3_stress"
    ARMS="aciq b1_cake_cons b1_cake_auto"
    ;;
  final)
    SEED0=1100; RUNS_DIR=data/runs_final3; EST_TOTAL=840  # minutes
    # THE declared frozen band: every shipped scenario except s6_intent_expire
    # (the intent path is neither touched by nor claims anything from this
    # brief) across the FULL five-arm set.
    SCENARIOS="s1_iso_during_call s2_wan_drop s3_tv_and_gaming s4_capacity_recovery \
s2b_step_50 s2b_step_10 s2b_step_up_20to100 s2b_ramp_100to30 \
s7_up_20to60 s7_up_30to100 s7_rampup_30to100 s7_down_100to15 s7_down_100to8 \
s3_stress"
    ARMS="b0_fifo b1_cake95 b1_cake_oracle b1_cake_cons b1_cake_auto aciq"
    ;;
  *)
    echo "usage: $0 dev|final" >&2; exit 64;;
esac

STATUS_DIR="data/live_status_round3/"; mkdir -p "$STATUS_DIR" testbed/logs
T0=$(date +%s)

step() {  # id estm cmd...
  local id="$1"; local estm="$2"; shift 2
  if [ -f "$STATUS_DIR/${BAND}_${id}.done" ]; then
    echo "[skip] ${BAND}_${id} (done; delete $STATUS_DIR/${BAND}_${id}.done to re-run)"
    return
  fi
  echo "===== ${BAND}_${id} | est ${estm}m | $(date +%H:%M:%S) ====="
  local log="$STATUS_DIR/${BAND}_${id}.log"
  # A hung cell must not block the band for hours: the 2026-11-01 dev band
  # sat 40+ minutes on a b1_cake_auto seed whose sinks were never torn down
  # (the experiment never reached collect()). Bound every step at 3x its
  # estimate (floor 30 min) and let a timeout fail it loudly like any other
  # step; a restart re-runs it because no .done marker is written.
  local tmo=$(( estm * 3 )); [ "$tmo" -lt 30 ] && tmo=30
  if timeout --foreground --kill-after=60s "${tmo}m" "$@" >"$log" 2>&1; then
    date +%s >"$STATUS_DIR/${BAND}_${id}.done"
    tail -3 "$log" | sed 's/^/    /'
    return
  fi
  tail -40 "$log" | sed 's/^/    ! /'
  echo "STEP FAILED: ${BAND}_${id} — log: $log"
  NOW=$(date +%s); echo "elapsed: $(( (NOW-T0)/60 ))m est total: ${EST_TOTAL}m"
  exit 1
}

echo "[run_round3_batch] band=$BAND seeds from $SEED0 | $(date)"

# ---------- hygiene ----------
step gate 3 ./testbed/gate.sh
step reset_hub 3 ./testbed/cleanup.sh
step setup_ub 3 ./testbed/setup.sh

# ---------- the band: scenario x arm cells, one step per cell ----------
# Each cell: 10 seeds (--seed $SEED0 --seeds 10). The engine picks the
# mode itself (ACIQ + CAKE-adaptive adaptive; the static arms static) and
# refuses any raw link override on declared scenario names (round-3
# protocol discipline).
for sc in $SCENARIOS; do
  for arm in $ARMS; do
    case "$sc" in
      s7_up_*|s7_rampup*|s2b_step_up*|s2b_ramp*) estm=16;;  # 60s runs
      *) estm=11;;                                          # 40s runs
    esac
    step "cell_${sc}__${arm}" "$estm" \
      "$PY" run_experiments.py --scenario "$sc" --system "$arm" \
      --seed "$SEED0" --seeds 10 --no-setup --enforce \
      --results-dir "$RUNS_DIR"
  done
done

# ---------- the gate: round-3 fixes judged mechanically ----------
# NOT a `step`: a FAIL here is a RESULT the agent must see, not a batch
# error; the log carries the full per-run verdicts.
echo "----- verify_round3 gate -----"
"$PY" tools/verify_round3.py "$RUNS_DIR" \
  | tee "$STATUS_DIR/${BAND}_verify.log" \
  || echo "[note] verify_round3 judged FAIL — recorded, batch continues"

# ---------- reports (disk only) ----------
step report_band 2 "$PY" tools/build_report.py \
  --runs-root "$RUNS_DIR" \
  --dev-seeds ${SEED0}-$((SEED0+9)) --eval-seeds ${SEED0}-$((SEED0+9)) \
  --out "data/experiments/RESULTS_$(echo $BAND | tr a-z A-Z)3.md"

if [ "$BAND" = final ]; then
  # The every-run provenance check the FIX_REPORT binds to.
  step final_provenance 1 sh -c "
    bad=\$(grep -rl '\"commit_hash\": null' '$RUNS_DIR' --include=result.json 2>/dev/null | wc -l)
    if [ \"\$bad\" -gt 0 ]; then
      echo \"COMMIT-PROVENANCE FAIL: \$bad result.json files have no commit_hash\"
      exit 1
    fi
    echo 'all runs carry commit_hash'"
  # Merge every band for the full RESULTS.md.
  BANDS_ROOT=data/experiments/bands_merge_r3
  step merged_farm 1 sh -c "
    rm -rf '$BANDS_ROOT' && mkdir -p '$BANDS_ROOT'
    for d in data/runs/*__*__*__seed* data/runs_dev3/*__*__*__seed* \
             data/runs_final3/*__*__*__seed* data/runs_s2b/*__*__*__seed* \
             data/runs_eval/*__*__*__seed* data/runs_dev/*__*__*__seed*; do
      [ -d \"\$d\" ] && ln -sfn \"\$(readlink -f \"\$d\")\" \
        \"$BANDS_ROOT/\$(basename \"\$d\")\"
    done"
  step merged_report 3 "$PY" tools/build_report.py \
    --runs-root "$BANDS_ROOT" --dev-seeds 1000-1009 --eval-seeds 1100-1109 \
    --eval-json data/experiments/classifier_corpus_fresh/eval.json \
    --out data/experiments/RESULTS.md
fi

"$PY" tools/audit_claims.py scan_path_citations | tail -1 || true

step cleanup_ub 5 ./testbed/cleanup.sh
if ip netns list 2>/dev/null | grep -qE '^(router|client|wan)'; then
  echo "WARNING: netns remain after cleanup:" >&2; ip netns list >&2; exit 2
fi

NOW=$(date +%s)
echo
echo "run_round3_batch [$BAND] DONE in $(( (NOW-T0)/60 ))m (est ${EST_TOTAL}m)"
echo "Next (agent, no sudo): read $RUNS_DIR (dev) or claims lock-in:"
echo "dev  -> tune constants from the artifacts, freeze, then rerun with 'final'"
echo "final-> update docs/FIX_REPORT.md PASS/FAIL from data/experiments/RESULTS_FINAL3.md"
