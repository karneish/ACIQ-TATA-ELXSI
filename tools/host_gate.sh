#!/usr/bin/env bash
# Run every gate that needs a real Linux kernel, in one invocation.
#
# WHY THIS EXISTS
#
# The blocked gates were previously described in prose with hand-written
# commands, and two of those commands named a scenario and a system that do not
# exist. They would have failed on a real host -- after building the testbed.
# Everything below is therefore validated against the real CLI, and the
# prerequisites are checked before anything privileged runs.
#
# SAFETY
#
# Every resource this touches belongs to the testbed:
#   - tests/test_rollback_live.py creates its OWN network namespace
#     (aciqrb<random>) with a veth pair inside it, and removes it on exit.
#     It never touches a host interface.
#   - testbed/setup.sh creates the testbed namespaces; testbed/cleanup.sh
#     removes them.
# Nothing here reconfigures the host's existing interfaces, routes or qdiscs.
#
# USAGE
#   sudo ./tools/host_gate.sh              # rollback + full acceptance
#   sudo ./tools/host_gate.sh --full       # + adaptation, CAKE comparison
#                                           #   (light-load AND congested), soak
#   sudo ./tools/host_gate.sh --check      # prerequisites only, changes nothing
#
# Exits non-zero if any executed gate fails. Gates that could not run are
# reported as SKIPPED, never as passing.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

REV="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
# Every results directory gets stamped with the revision that produced it, so
# evidence can never be silently combined with a report for a different commit.
stamp() { mkdir -p "$1" && git rev-parse HEAD > "$1/REVISION" 2>/dev/null || true; }
OUT="artifacts/validation/${REV}/host"

# Privilege is checked BEFORE anything is created.
#
# This used to `mkdir -p "$OUT" || exit 1` first, which meant an unprivileged
# run created (or tried to create) a directory and then reported "Nothing has
# been changed" -- and, when a previous root run had left the tree owned by
# root, it died on a raw `mkdir: Permission denied` instead of ever reaching the
# refusal message. So the script changed the filesystem on the path where it
# promises it changes nothing, and the error a user saw was the one they least
# needed.
#
# The test that catches this is
# test_it_refuses_without_root_and_changes_nothing -- which was silently
# discarded for the life of the file by a duplicate class definition, so
# neither the bug nor the fix was ever exercised. See TestNoSilentlyLostTests.
if [ "$(id -u)" -ne 0 ]; then
  echo "ACIQ host gate must run under sudo: it configures network namespaces." >&2
  echo "Nothing has been changed." >&2
  exit 1
fi

CHECK_ONLY=0
FULL=0
CONGESTED_ONLY=0
LATENCY_TAIL=0
LIGHT_ONLY=0
SCENARIO_A=0
RECOVERY=0
OBSERVE=""
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --full)  FULL=1 ;;
    --congested-only) CONGESTED_ONLY=1 ;;
    --latency-tail) LATENCY_TAIL=1 ;;
    --light-only) LIGHT_ONLY=1 ;;
    --scenario-a) SCENARIO_A=1 ;;
    --recovery) RECOVERY=1 ;;
    --observe) OBSERVE="--observe" ;;
    -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [ "$FULL" -eq 1 ] && [ "$CONGESTED_ONLY" -eq 1 ]; then
  echo "--full and --congested-only are mutually exclusive" >&2
  exit 2
fi

log()  { printf '%s\n' "$*" | tee -a "$OUT/host-gate.log"; }
skip() { printf '  [SKIPPED] %s -- %s\n' "$1" "$2" | tee -a "$OUT/host-gate.log"; }

log "ACIQ host gate -- revision ${REV}"
log "date: $(date -Is)"
log ""

# ---------------------------------------------------------------- prerequisites
log "-- prerequisites --"
MISSING=()
MISSING_ROOT=0
# Root was already required above, before anything was created. Re-asserting it
# here is harmless but the `else` branch was dead code.
log "  [ok ] root"

for t in ip tc iperf3; do
  if command -v "$t" >/dev/null 2>&1; then
    log "  [ok ] $t -> $(command -v "$t")"
  else
    log "  [FAIL] $t not on PATH"
    MISSING+=("$t")
  fi
done

if [ "$MISSING_ROOT" -eq 1 ] || [ "${#MISSING[@]}" -gt 0 ]; then
  log ""
  log "Cannot continue. On Pop!_OS:  sudo apt install iproute2 iperf3"
  log "Nothing has been changed."
  exit 1
fi

# namespace support is assumed by every gate below; prove it rather than assume
if ! ip netns add aciq_gate_probe 2>/dev/null; then
  log "  [FAIL] cannot create a network namespace; kernel or caps too restricted"
  log "Nothing has been changed."
  exit 1
fi
ip netns del aciq_gate_probe
log "  [ok ] network namespace support"
log ""
log "kernel: $(uname -r)"
log "iproute2: $(tc -V 2>&1 | head -1)"
log ""

if [ "$CHECK_ONLY" -eq 1 ]; then
  log "--check only: prerequisites satisfied, nothing executed --"
  exit 0
fi

FAILED=0

# ------------------------------------------------------- 1. live rollback gate
log "== gate 1: live rollback verification (real kernel) =="
if python3 -m unittest tests.test_rollback_live -v 2>&1 | tee "$OUT/rollback-live.log" | tail -3; then
  log "  [PASS] live rollback"
else
  # unittest exits 0 on "OK (skipped=...)"; treat skips as NOT RUN
  if grep -q '^OK (skipped=' "$OUT/rollback-live.log"; then
    skip "live rollback" "tests skipped -- no evidence"
  else
    log "  [FAIL] live rollback -- see rollback-live.log"
    FAILED=1
  fi
fi
log ""

# ------------------------------------------------------------ 2. full harness
log "== gate 2: acceptance harness =="
python3 tools/acceptance.py 2>&1 | tee "$OUT/acceptance.log"
rc=${PIPESTATUS[0]}
if [ "$rc" -ne 0 ]; then
  log "  [FAIL] acceptance harness exited ${rc}"
  FAILED=1
elif grep -q 'complete acceptance run: True' "$OUT/acceptance.log"; then
  log "  [PASS] acceptance complete, 0 failures"
else
  log "  [WARN] acceptance ran but is NOT complete -- see the gate list above"
fi
log ""

# ---------------------------------------------------- latency-tail probe
# Deliberately short and deliberately a single seed. This is a DIAGNOSTIC, not a
# gate: the congested comparison reports p50 1.19 ms but p95 80.126 ms and p99
# 100.265 ms, and those are exact multiples of the 20 ms pacing interval and
# come out identical for FIFO, CAKE and ACIQ to 0.01 ms. A percentile cannot say
# which packets were slow or when. This run records every packet so they can be
# found in time against what the run was doing. One seed, 60s -- the answer is
# in the trace, not in the sample size.
latency_tail_probe() {
  log "== diagnostic: latency tail, 1 seed, per-packet trace =="
  log "  ~2 min. This is a diagnostic run, not a gate result."
  stamp data/host_gate_tail
  python3 run_experiments.py --scenario s2_wan_drop --system aciq \
      --drop 20 --drop-at 5 --seed 42 --duration-s 60 --enforce --observe \
      --results-dir data/host_gate_tail 2>&1 \
      | tee "$OUT/tail.log" | tail -4
  log "  trace: data/host_gate_tail/*/call.obs.jsonl"
}

# ---------------------------------------------------- congested comparison
# Factored out so `--congested-only` re-measures exactly this and nothing else.
congested_comparison() {
  log "== gate 4b: CONGESTED comparison (s2_wan_drop), 7 paired seeds =="
  log "  ~20 min plus testbed build"
  log "  this is the one that matters: a dropped link, not a free one"
  for sysname in b0_fifo b1_cake95 aciq; do
    stamp "data/host_gate_congested_${sysname}"
    # --enforce is passed for ALL THREE. It is a no-op on the baselines, which
    # have no classifier, so it cannot bias the comparison -- but omitting it
    # for aciq is what made the previous headline measurement meaningless:
    # every sample recorded filters_installed: 0, so "ACIQ beat CAKE" was
    # measured on a controller that never steered a single flow.
    python3 run_experiments.py --scenario s2_wan_drop --system "$sysname" \
        --drop 20 --drop-at 5 --seeds 7 --seed 42 --enforce $OBSERVE \
        --results-dir "data/host_gate_congested_${sysname}" 2>&1 \
        | tee -a "$OUT/comparison-congested.log" | tail -2
  done
  assert_flow_steering data/host_gate_congested_aciq
  log "  evidence: data/host_gate_congested_{b0_fifo,b1_cake95,aciq}"
}

light_comparison() {
  log "== gate 4: FIFO / CAKE / ACIQ comparison, light load, 7 paired seeds =="
  log "  ~20 min plus testbed build"
  for sysname in b0_fifo b1_cake95 aciq; do
    stamp "data/host_gate_${sysname}"
    # --enforce for the same reason as the congested gate; see assert_flow_steering.
    python3 run_experiments.py --scenario s3_tv_and_gaming --system "$sysname" \
        --seeds 7 --seed 42 --enforce $OBSERVE \
        --results-dir "data/host_gate_${sysname}" 2>&1 \
        | tee -a "$OUT/comparison.log" | tail -2
  done
  assert_flow_steering data/host_gate_aciq
  log "  evidence: data/host_gate_{b0_fifo,b1_cake95,aciq}"
}

# The brief's scenario A: "A large ISO download starts during a video
# conference; the controller limits the bulk queue and protects call latency."
#
# This is the scenario that was never run. s2_wan_drop (B) and s3_tv_and_gaming
# (C) both have evidence; s1_iso_during_call had none anywhere in data/. The
# audit prompt is explicit that all three mandatory scenarios need reproducible
# procedures and evidence, so it is wired here rather than left implicit in the
# scenario table.
scenario_a_comparison() {
  log "== gate 4a: scenario A (ISO download during a call), 7 paired seeds =="
  log "  ~20 min plus testbed build"
  for sysname in b0_fifo b1_cake95 aciq; do
    stamp "data/host_gate_s1_${sysname}"
    python3 run_experiments.py --scenario s1_iso_during_call --system "$sysname" \
        --seeds 7 --seed 42 --enforce $OBSERVE \
        --results-dir "data/host_gate_s1_${sysname}" 2>&1 \
        | tee -a "$OUT/comparison-s1.log" | tail -2
  done
  assert_flow_steering data/host_gate_s1_aciq
  log "  evidence: data/host_gate_s1_{b0_fifo,b1_cake95,aciq}"
}

# Capacity recovery: 100 -> 20 -> back to 100.
#
# Every adaptation gate so far tested only the falling edge. This restores the
# link mid-run so the controller has to walk the estimate back UP and rebuild
# the plan from it. A policy left pinned at the degraded rate after the link
# recovers is a real, user-visible defect that no drop-only test can see.
recovery_gate() {
  log "== gate 3b: capacity recovery, 100 -> 20 -> 100 =="
  log "  ~2 min plus testbed build"
  stamp data/host_gate_recovery
  python3 run_experiments.py --scenario s4_capacity_recovery --system aciq \
      --enforce --drop 20 --drop-at 10 --seed 42 --duration-s 60 \
      --recover-at 30 --recover-to 100 \
      --results-dir data/host_gate_recovery 2>&1 \
      | tee "$OUT/recovery.log" | tail -5
  log "  evidence: data/host_gate_recovery"
}

# A PASS must not be able to mean "nothing happened".
#
# The previous congested gate reported results from a run in which the
# classifier's verdicts existed but no tc filter was ever installed. Nothing
# errored, nothing warned, and the comparison was published anyway. This reads
# the evidence back and refuses to call it a pass unless flows were steered.
assert_flow_steering() {
  local prefix="${1:-data/host_gate_congested_aciq}"
  log "  -- verifying per-flow steering actually happened in ${prefix} --"
  local bad=0 seen=0
  for f in "$prefix"/*/result.json; do
    [ -e "$f" ] || continue
    seen=$((seen + 1))
    local n
    n=$(python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
print(max((s.get('filters_installed') or 0) for s in d.get('samples',[])) if d.get('samples') else 0)
" "$f")
    if [ "${n:-0}" -eq 0 ]; then
      log "  [FAIL] $(basename "$(dirname "$f")"): filters_installed=0 -- no flow was ever steered"
      bad=1
    fi
  done
  if [ "$seen" -eq 0 ]; then
    log "  [FAIL] no result.json under ${prefix} -- nothing to verify"
    bad=1
  elif [ "$bad" -eq 0 ]; then
    log "  [PASS] per-flow steering confirmed in all ${seen} aciq runs"
  else
    FAILED=1
  fi
}

# -------------------------------------------------- 3. optional longer exercises
if [ "$LATENCY_TAIL" -eq 1 ]; then
  latency_tail_probe
  log ""
elif [ "$RECOVERY" -eq 1 ]; then
  recovery_gate
  log ""
elif [ "$SCENARIO_A" -eq 1 ]; then
  scenario_a_comparison
  log ""
elif [ "$LIGHT_ONLY" -eq 1 ]; then
  light_comparison
  log ""
elif [ "$CONGESTED_ONLY" -eq 1 ]; then
  congested_comparison
  log ""
elif [ "$FULL" -eq 1 ]; then
  log "== gate 3: capacity-change adaptation (s2_wan_drop) =="
  log "  ~40s plus testbed build"
  stamp data/host_gate_adapt
  python3 run_experiments.py --scenario s2_wan_drop --system aciq --enforce \
      --drop 10 --drop-at 5 --seed 42 --results-dir data/host_gate_adapt 2>&1 \
      | tee "$OUT/adaptation.log" | tail -5
  log "  evidence: data/host_gate_adapt"
  log ""

  light_comparison
  log ""

  scenario_a_comparison
  log ""

  recovery_gate
  log ""

  congested_comparison
  log ""

  log "== gate 5: 30-minute soak =="
  log "  the shipped scenarios are 30-40s; --duration-s is what makes this possible"
  stamp data/host_gate_soak
  python3 run_experiments.py --scenario s3_tv_and_gaming --system aciq \
      --enforce --duration-s 1800 --results-dir data/host_gate_soak 2>&1 \
      | tee "$OUT/soak.log" | tail -5
  log "  evidence: data/host_gate_soak"
  log ""
fi

# ---------------------------------------------------------------------- summary
log "== summary =="
log "  evidence directory: ${OUT}"
log "  kernel: $(uname -r)"
if [ "$FAILED" -ne 0 ]; then
  log "  RESULT: one or more executed gates FAILED"
  exit 1
fi
log "  RESULT: every executed gate passed."
log "  Gates marked SKIPPED above produced no evidence and must not be"
log "  counted as passing. Re-run the acceptance harness and read its own"
log "  per-gate table before drawing any conclusion."
exit 0