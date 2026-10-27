#!/usr/bin/env bash
# testbed/run_round2_batch.sh — THE ONE batched privileged script for the
# Task-3..6 round of the second brief.
#
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_round2_batch.sh
#
# Resume-safe: every step writes data/live_status_round2/<id>.done; delete
# one to re-run that step. Everything BEFORE s5 is diagnosis; the S2b band
# is EVALUATION-ONLY (declared docs/evidence/s2b-params.md: seeds 800-809,
# no tuning band, no parameter touched), so nothing after it is retuned.
#
# Band map:
#   data/experiments/s5*      — S5(c) three repeats + tc/nft dumps + live tool versions
#   data/runs_diag            — task-1 close-out deep traces (--observe + tc stats, seeds 210/211)
#   data/runs_s2b             — S2b generalization band, seeds 800-809, four arms
#   reports                   — RESULTS*.md regenerated (band-labelled)
#
# Runtime estimate: ~5.5–7 h (s5 ~25 m, deep traces ~12 m, s2b ~5–6 h,
# reports/audit/cleanup <10 m). `ip netns list` must be EMPTY at exit.
# No sudo password is requested by any step.
set -uo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
export PYTHONPATH="$(pwd)"
STATUS_DIR="data/live_status_round2/"; mkdir -p "$STATUS_DIR" testbed/logs
T0=$(date +%s)
EST_TOTAL=390   # minutes

step() {  # id estm cmd...
  local id="$1"; local estm="$2"; shift 2
  if [ -f "$STATUS_DIR/$id.done" ]; then
    echo "[skip] $id (done; delete $STATUS_DIR/$id.done to re-run)"
    return 2
  fi
  echo "===== $id | est ${estm}m | $(date +%H:%M:%S) ====="
  local log="$STATUS_DIR/$id.log"
  if "$@" >"$log" 2>&1; then
    date +%s >"$STATUS_DIR/$id.done"
    tail -3 "$log" | sed 's/^/    /'
    return 0
  fi
  tail -40 "$log" | sed 's/^/    ! /'
  echo "STEP FAILED: $id — log: $log"
  NOW=$(date +%s); echo "elapsed: $(( (NOW-T0)/60 ))m est total: ${EST_TOTAL}m"
  exit 1
}

echo "[run_round2_batch] round-2 tasks 3-6 | $(date)"

# ---------- hygiene ----------
step gate 3 ./testbed/gate.sh
step reset_hub 3 ./testbed/cleanup.sh
step setup_ub 3 ./testbed/setup.sh

# ---------- S5: safe state, three repeats, real tool versions ----------
# (testbed/s5_live.sh now runs the injected-apply case on THREE fresh
# seeds 555-557 with per-seed last-good/rollback/recommit stamps, tc/nft
# kernel dumps per repeat, and the live host's real tool versions in the
# summary the report quotes verbatim.)
step s5 25 ./testbed/s5_live.sh

# ---------- Task 1 close-out: deep traces under the LAUNCH FIX ----------
# ACIQ-only, --observe (per-packet call trace -> the report's
# time-resolved table); seeds 210/211 are fresh. The engine's per-tick
# samples already carry the netem backlog; the side dump below adds raw
# `tc -s qdisc` state from the bottleneck during the launch window
# (t = 0..8 s), the part the artefact can only summarize.
for sc in s1_iso_during_call s2_wan_drop s4_capacity_recovery; do
  step "t1_deep_${sc}" 4 ./testbed/deep_trace.sh "$sc"
done

# ---------- S2b generalization band (EVALUATION-ONLY, one run) ----------
# docs/evidence/s2b-params.md was written BEFORE these runs: scenario
# names, link protocols, seeds 800-809, metrics and the honesty rule.
# The four arms in full; ACIQ passes --enforce (same as the shipped EVAL
# band). run_experiments refuses --link/--drop overrides for these names.
for sc in s2b_step_50 s2b_step_10 s2b_step_up_20to100 s2b_ramp_100to30; do
  for arm in b0_fifo b1_cake95 b1_cake_oracle aciq; do
    step "s2b_${sc}__${arm}" 20 \
         "$PY" run_experiments.py --scenario "$sc" --system "$arm" \
         "--seed" 800 --seeds 10 --no-setup --enforce \
         --results-dir data/runs_s2b
  done
done

# ---------- reports ----------
# RESULTS* regenerate from DISK ONLY (one sudo pass; the eval/dev report
# files are root-owned from the prior batch). The merged farm re-derives;
# the S2b band gets its own documented report.
BANDS_ROOT=data/experiments/bands_merge
step t6_merged_farm 1 sh -c "
  rm -rf '$BANDS_ROOT' && mkdir -p '$BANDS_ROOT'
  for d in data/runs/*__*__*__seed* data/runs_dev/*__*__*__seed* \
           data/runs_eval/*__*__*__seed* data/runs_diag/*__*__*__seed*; do
    [ -d \"\$d\" ] && ln -sfn \"\$(readlink -f \"\$d\")\" \\
      \"data/experiments/bands_merge/\$(basename \"\$d\")\"
  done"
step t6_report 2 "$PY" tools/build_report.py \
     --runs-root data/experiments/bands_merge \
     --dev-seeds 400-409 --eval-seeds 500-509 \
     --eval-json data/experiments/classifier_corpus_fresh/eval.json \
     --out data/experiments/RESULTS.md
step t6_eval_report 1 "$PY" tools/build_report.py \
     --runs-root data/runs_eval --eval-seeds 500-509 \
     --eval-json data/experiments/classifier_corpus_fresh/eval.json \
     --out data/experiments/RESULTS_EVAL.md
step t6_dev_report 1 "$PY" tools/build_report.py \
     --runs-root data/runs_dev --dev-seeds 400-409 \
     --eval-json data/experiments/classifier_corpus_fresh/eval.json \
     --out data/experiments/RESULTS_DEV.md
step t6_s2b_report 1 "$PY" tools/build_report.py \
     --runs-root data/runs_s2b --eval-seeds 800-809 \
     --out data/experiments/RESULTS_S2B.md
"$PY" tools/audit_claims.py scan_path_citations | tail -1 || true

step cleanup_ub 5 ./testbed/cleanup.sh
if ip netns list 2>/dev/null | grep -qE '^(router|client|wan)'; then
  echo "WARNING: netns remain after cleanup:" >&2; ip netns list >&2; exit 2
fi

NOW=$(date +%s)
echo
echo "run_round2_batch DONE in $(( (NOW-T0)/60 ))m (est ${EST_TOTAL}m)"
echo "Next (agent, no sudo): review data/experiments/RESULTS_S2B.md and"
echo "RESULTS.md; the S2b band was run ONCE, never against tuning."
