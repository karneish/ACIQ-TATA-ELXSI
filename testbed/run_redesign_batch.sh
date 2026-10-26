#!/usr/bin/env bash
# testbed/run_redesign_batch.sh — THE ONE batched privileged script for the
# redesign round (Tasks 1–4 of the current 5-task brief).
#
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_redesign_batch.sh
#
# Resume-safe: every step writes data/live_status_redesign/<id>.done; delete
# one to re-run that step. Steps abort hard on failure — after the DEV gate
# passes, the EVAL band runs ONCE and is never tuned against (task-2 rule);
# nothing after the eval step may modify controller parameters.
#
# Band map (ALL runs write into their own band directory; the committed
# POST-FIX matrix under data/runs is never overwritten):
#   data/runs_diag  — task-1 re-instrumented diagnosis (--observe, seeds 200/201)
#   data/runs_dev   — task-2 DEV band, seeds 400-409 (parameters may be judged here)
#   data/runs_eval  — task-2 EVAL band, seeds 500-509 (ONE run, frozen parameters)
#   data/runs       — task-3 s6 band, seeds 310-319 (append-only; verifier handles both 300 and 310 bands)
#   corpus_out      — task-4 fresh corpus (--port-offset 2000)
#
# Runtime estimate: ~3.5–5 h total (diag ~10 m, dev ~45 m, eval ~2.5–3.5 h,
# s6 ~35 m, corpus ~35 m). `ip netns list` must be EMPTY at exit.
set -uo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
export PYTHONPATH="$(pwd)"
STATUS_DIR="data/live_status_redesign/"; mkdir -p "$STATUS_DIR" testbed/logs
T0=$(date +%s)
EST_TOTAL=330   # minutes

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

echo "[run_redesign_batch] redesign round tasks 1-4 | $(date)"

# ---------- hygiene ----------
step gate 3 ./testbed/gate.sh
step reset_hub 3 ./testbed/cleanup.sh
step setup_ub 3 ./testbed/setup.sh

# ---------- Task 1: re-instrumented diagnosis ----------
# seeds 200/201, s1/s2/s4, ACIQ only, --observe so per-second receiver
# series exists this time (task-1 gap: per-second call latency was
# unrecoverable). Separate band dir by design; TESTBED CLEANUP between arms
# is NOT needed (--no-setup once).
for sc in s1_iso_during_call s2_wan_drop s4_capacity_recovery; do
  step "t1_diag_${sc}" 4 "$PY" run_experiments.py --scenario "$sc" \
       --system aciq --seed 200 --seeds 2 --no-setup --observe \
       --results-dir data/runs_diag
done

# ---------- Task 2 DEV band (parameters may be judged on these) ----------
# All four scenarios x ACIQ (the controller only; baselines have no tunable
# surface and are remeasured in the eval band) x seeds 400-409.
for sc in s1_iso_during_call s2_wan_drop s3_tv_and_gaming s4_capacity_recovery; do
  step "t2_dev_${sc}" 10 "$PY" run_experiments.py --scenario "$sc" \
       --system aciq --seed 400 --seeds 10 --no-setup \
       --results-dir data/runs_dev
done

# ---------- the DEV gate (mechanical; failure must stop the eval) ----------
step t2_dev_gate 1 "$PY" tools/verify_dev_band.py data/runs_dev
step t2_dev_report 1 "$PY" tools/build_report.py \
     --runs-root data/runs_dev \
     --dev-seeds 400-409 \
     --out data/experiments/RESULTS_DEV.md

echo "=== DEV band gate passed; the EVAL band starts now. ==="
echo "=== From this moment NO controller parameter may be changed. ==="

# ---------- Task 2 EVAL band (ONE run, never tuned against) ----------
# The full four-arm matrix on fresh seeds 500-509 into its own band dir.
for sc in s1_iso_during_call s2_wan_drop s3_tv_and_gaming s4_capacity_recovery; do
  for arm in b0_fifo b1_cake95 b1_cake_oracle aciq; do
    step "t2_eval_${sc}__${arm}" 20 \
         "$PY" run_experiments.py --scenario "$sc" --system "$arm" \
         --seed 500 --seeds 10 --no-setup --results-dir data/runs_eval
  done
done

# ---------- Task 3: s6 intent band, declared protocol ----------
# 60 s run, intent at t=10 s, TTL 20 s (EXPIRES inside the run), seeds
# 310-319, ACIQ vs the two declaring-incapable baselines.
step t3_s6 40 "$PY" run_experiments.py --scenario s6_intent_expire \
     --system aciq --system b0_fifo --system b1_cake95 \
     --seed 310 --seeds 10 --no-setup \
     --api-intent --intent-at 10.0 --intent-ttl 20.0 --intent-weight 0.5
# verdict is evidence for the report, NOT a gate: legacy 300-309 dirs live
# beside the new 310 band and a failing dir must not kill the batch.
step t3_s6_verify 1 sh -c "'$PY' tools/verify_s6.py data/runs; exit 0"

# ---------- Task 4: fresh classifier corpus, port-offset 2000 ----------
# The corpus flows are re-collected on FRESH dports (base + i + 2000);
# split seed stays 7 so the held-out protocol is unchanged. --out is the
# jsonl FILE (the collector writes counts.json beside it).
step t4_corpus 40 "$PY" -u tools/gen_corpus.py \
     --out data/experiments/classifier_corpus_fresh/corpus.jsonl \
     --port-offset 2000
step t4_corpus_eval 2 "$PY" tools/eval_corpus.py \
     --corpus data/experiments/classifier_corpus_fresh/corpus.jsonl \
     --out data/experiments/classifier_corpus_fresh/eval.json

# ---------- reports (band-labelled), audit, teardown ----------
# The master RESULTS.md gets ONE merged view: symlink farm over the three
# band roots so build_report renders POST-FIX (primary), DEV and EVAL
# blocks in the same document, each labelled by its seed band.
step t5_merged_view 1 sh -c '
  rm -rf data/experiments/bands_merge && mkdir -p data/experiments/bands_merge
  for d in data/runs/*__*__*__seed* data/runs_dev/*__*__*__seed* \
           data/runs_eval/*__*__*__seed*; do
    [ -d "$d" ] && ln -sfn "$(readlink -f "$d")" \
      "data/experiments/bands_merge/$(basename "$d")"
  done'
step t5_report 2 "$PY" tools/build_report.py \
     --runs-root data/experiments/bands_merge \
     --dev-seeds 400-409 --eval-seeds 500-509 \
     --eval-json data/experiments/classifier_corpus_fresh/eval.json \
     --out data/experiments/RESULTS.md
step t5_eval_report 2 "$PY" tools/build_report.py \
     --runs-root data/runs_eval --eval-seeds 500-509 \
     --out data/experiments/RESULTS_EVAL.md
"$PY" tools/audit_claims.py scan_path_citations | tail -1 || true

step cleanup_ub 5 ./testbed/cleanup.sh
if ip netns list 2>/dev/null | grep -qE '^(router|client|wan)'; then
  echo "WARNING: netns remain after cleanup:" >&2; ip netns list >&2; exit 2
fi

NOW=$(date +%s)
echo
echo "run_redesign_batch DONE in $(( (NOW-T0)/60 ))m (est ${EST_TOTAL}m)"
echo "Next (agent, no sudo): review data/experiments/RESULTS_EVAL.md"
echo "(the one-shot eval band), RESULTS.md (band-labelled), and update"
echo "FIX_REPORT + commit — parameters must NOT be retouched."
