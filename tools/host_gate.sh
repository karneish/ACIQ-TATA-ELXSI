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
#   sudo ./tools/host_gate.sh --full       # + adaptation and CAKE comparison
#   sudo ./tools/host_gate.sh --check      # prerequisites only, changes nothing
#
# Exits non-zero if any executed gate fails. Gates that could not run are
# reported as SKIPPED, never as passing.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

REV="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
OUT="artifacts/validation/${REV}/host"
mkdir -p "$OUT" || exit 1

CHECK_ONLY=0
FULL=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --full)  FULL=1 ;;
    -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf '%s\n' "$*" | tee -a "$OUT/host-gate.log"; }
skip() { printf '  [SKIPPED] %s -- %s\n' "$1" "$2" | tee -a "$OUT/host-gate.log"; }

log "ACIQ host gate -- revision ${REV}"
log "date: $(date -Is)"
log ""

# ---------------------------------------------------------------- prerequisites
log "-- prerequisites --"
MISSING=()
MISSING_ROOT=0
if [ "$(id -u)" -ne 0 ]; then
  log "  [FAIL] euid=$(id -u); this script must run under sudo"
  MISSING_ROOT=1
else
  log "  [ok ] root"
fi

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

# -------------------------------------------------- 3. optional longer exercises
if [ "$FULL" -eq 1 ]; then
  log "== gate 3: capacity-change adaptation (s2_wan_drop) =="
  log "  ~40s plus testbed build"
  python3 run_experiments.py --scenario s2_wan_drop --system aciq --enforce \
      --drop 10 --drop-at 5 --seed 42 --results-dir data/host_gate_adapt 2>&1 \
      | tee "$OUT/adaptation.log" | tail -5
  log "  evidence: data/host_gate_adapt"
  log ""

  log "== gate 4: FIFO / CAKE / ACIQ comparison, 7 paired seeds =="
  log "  ~20 min plus testbed build"
  for sysname in b0_fifo b1_cake95 aciq; do
    python3 run_experiments.py --scenario s3_tv_and_gaming --system "$sysname" \
        --seeds 7 --seed 42 --results-dir "data/host_gate_${sysname}" 2>&1 \
        | tee -a "$OUT/comparison.log" | tail -2
  done
  log "  evidence: data/host_gate_{b0_fifo,b1_cake95,aciq}"
  log ""

  log "== gate 5: 30-minute soak =="
  log "  the shipped scenarios are 30-40s; --duration-s is what makes this possible"
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