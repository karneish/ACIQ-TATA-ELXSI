#!/usr/bin/env bash
# testbed/bridge_probe.sh — one-shot syntax probe for the M1->M4 bridge.
#
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/bridge_probe.sh
#
# WHY THIS EXISTS
#
# gate.sh stops at the first failure. When a command is wrong, that means one
# full ~2 minute gate run per bug, discovered one at a time, with no
# information about the commands that come after it. Checks 15-20 proved this:
# check 15 died on the very first command and left the set, rule and tc filter
# syntax entirely untested.
#
# This script instead runs every command the bridge would emit, one at a time,
# and reports PASS/FAIL per line. It answers "does the kernel accept this
# syntax?" for the whole bridge in seconds.
#
# WHAT IT DOES NOT DO
#
# It asserts nothing about traffic. It cannot tell you that a mark actually
# routes traffic to a class, that an unclassified flow loses EF priority, or
# that a mark expires. Those are behavioural and belong in gate.sh checks
# 16-19. This is syntax only.
#
# The commands come from Bridge.plan() -- the shipped generator -- not from a
# hand-written copy. A second transcription would pass here while the code
# stayed broken.

set -uo pipefail
cd "$(dirname "$0")"
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
DEV=veth-lan          # egress interface: where tc filters are installed
IN_IF=veth-wan        # ingress interface: where nft marks are set

if [ "$(id -u)" -ne 0 ]; then echo "run with sudo"; exit 1; fi
if [ ! -x "$VENV/bin/python" ]; then
  echo "no venv at $VENV -- set ACIQ_VENV"; exit 1
fi

echo "=== ACIQ bridge syntax probe ==="
echo "venv:   $VENV"
echo "kernel: $(uname -r)"
echo "tc:     $(tc -V 2>&1)"
echo "nft:    $(nft --version 2>&1)"
echo

# ---- namespaces must exist ------------------------------------------------
if ! ip netns list | grep -qw router; then
  echo "[setup] router namespace absent, creating it"
  ./cleanup.sh >/dev/null 2>&1 || true
  ./setup.sh >/dev/null || { echo "setup.sh failed"; exit 1; }
fi
echo "[setup] namespaces ready"
echo

PASS=0; FAIL=0
FAILED_CMDS=()

# try <label> <argv...>   -- runs one command, records the result
try () {
  local label="$1"; shift
  local out rc
  out=$("$@" 2>&1); rc=$?
  if [ $rc -eq 0 ]; then
    printf '  PASS  %-38s\n' "$label"
    PASS=$((PASS+1))
  else
    printf '  FAIL  %-38s rc=%s\n' "$label" "$rc"
    printf '        %s\n' "$(echo "$out" | head -3 | tr '\n' ' ')"
    FAIL=$((FAIL+1))
    FAILED_CMDS+=("$label")
  fi
}

# ==========================================================================
# 1. the shipped generator's commands, one at a time
# ==========================================================================
echo "--- bridge plan commands (from aciq.bridge.Bridge.plan) ---"

# Render each planned command with shlex.join, so the shell rebuilds exactly the
# argument vector python built -- including tokens that contain spaces, such as
# the nft chain and set definitions. A hand-rolled word-splitting loop would
# re-introduce the very class of bug the bridge tests exist to catch: a spec
# reaching the tool as one token instead of several.
"$VENV/bin/python" - "$DEV" "$IN_IF" <<'PY' > /tmp/aciq-probe.txt
import shlex
import sys
sys.path.insert(0, "..")
from aciq.bridge import Bridge
dev, in_if = sys.argv[1], sys.argv[2]
for argv in Bridge(dev=dev, in_if=in_if, ns="router").plan():
    print(shlex.join(argv))
PY

if [ ! -s /tmp/aciq-probe.txt ]; then
  echo "  FAIL  generator produced no commands"
  exit 1
fi

CMDS=0
while IFS= read -r line; do
  CMDS=$((CMDS+1))
  # shellcheck disable=SC2086
  out=$(eval "ip netns exec router $line" 2>&1); rc=$?
  short=$(echo "$line" | cut -c1-72)
  if [ $rc -eq 0 ]; then
    printf '  PASS  %s\n' "$short"
    PASS=$((PASS+1))
  else
    printf '  FAIL  %s\n' "$short"
    printf '        rc=%s  %s\n' "$rc" "$(echo "$out" | head -2 | tr '\n' ' ')"
    FAIL=$((FAIL+1))
    FAILED_CMDS+=("$short")
  fi
done < /tmp/aciq-probe.txt
echo "  ($CMDS commands from the generator)"
echo

# ==========================================================================
# 2. tc fw handle-mask syntax: primary vs fallback, in the same run
# ==========================================================================
# Why this needs probing: aciq/marks.py packs class, seen, confidence, reason
# and lease id into one 32-bit mark. A `tc fw` filter must match ONLY the class
# nibble, otherwise every (class x confidence x reason) combination needs its
# own static filter -- 5 x 4 x 4 = 80 -- and a new confidence bucket would
# invalidate all of them.
#
# Two candidate syntaxes; which one the kernel accepts is not something the
# unit tests can answer, because it is a property of iproute2.
echo "--- tc fw mask syntax ---"

FWDEV="ip netns exec router tc filter add dev $DEV parent 1: protocol ip prio 11 fw"
try "A: fw handle 0x01/0x0f"        $FWDEV handle 0x01/0x0f flowid 1:10
ip netns exec router tc filter del dev "$DEV" parent 1: protocol ip prio 11 2>/dev/null
try "B: fw mask 0xf handle 0x1"      $FWDEV mask 0xf handle 0x1 flowid 1:10
ip netns exec router tc filter del dev "$DEV" parent 1: protocol ip prio 11 2>/dev/null
try "C: fw classid (no handle)"      $FWDEV classid 1:10
ip netns exec router tc filter del dev "$DEV" parent 1: protocol ip prio 11 2>/dev/null
echo

# ==========================================================================
# 3. the element/key shape, which is the other place we could be wrong
# ==========================================================================
# The set is keyed (addr, addr, inet_proto, inet_service) and matched with
# `meta l4proto th dport @set`. If that concatenation is not supported, the
# fix is a different key shape, not a typo -- so it is probed explicitly.
echo "--- nft set key / lookup shape ---"

NS="ip netns exec router"
try "set with flags timeout"  $NS nft add set ip aciqprobe s1 \
  '{ type ipv4_addr . ipv4_addr . inet_proto . inet_service ; flags timeout ; timeout 120s ; }'
try "rule: l4proto th dport"  $NS nft add rule ip aciqprobe inetprobe \
  ip saddr ip daddr meta l4proto th dport @s1 meta mark set 16
try "element with timeout"    $NS nft add element ip aciqprobe s1 \
  '{ 203.0.113.2 . 10.0.1.2 . udp . 7001 timeout 120s }'
$NS nft delete table ip aciqprobe 2>/dev/null
echo

echo "=== SUMMARY ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo
  echo "failed commands:"
  for f in "${FAILED_CMDS[@]}"; do echo "  - $f"; done
  echo
  echo "Syntax only. Behaviour (does a mark route traffic?) is gate.sh 16-19."
  exit 1
fi
echo
echo "All syntax accepted. This does NOT prove behaviour -- run gate.sh."