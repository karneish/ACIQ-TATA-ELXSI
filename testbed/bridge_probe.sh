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
# ==========================================================================
# 2. HOW DOES A PACKET MARK REACH A CLASS?
#
# Answer so far: `tc fw` cannot match a mark on iproute2 6.1.0. It accepts only
# classid, indev and action -- no `handle`, no `mask`, in either syntax. The
# "nftables sets -> mark -> static tc fw filters" design in aciq/bridge.py
# cannot be built on this toolchain. That is an absent capability, not a syntax
# slip, so no amount of argument reordering fixes it.
#
# The first run of this section was also invalid: it created fresh namespaces,
# so there was no HTB qdisc and every tc filter failed with "Parent Qdisc
# doesn't exists" BEFORE its syntax was ever parsed. A missing parent qdisc
# hides a syntax error, so every "FAIL" below the qdisc line was meaningless.
# The tree is now built first, and a baseline flower filter is probed to prove
# flower itself works before concluding anything about its key set.
# ==========================================================================
echo "--- preparing an HTB tree to attach filters to ---"
NS="ip netns exec router"
# mirrors gate.sh check 6; classes match aciq.tc.CLASS_IDS
$NS tc qdisc del dev "$DEV" root 2>/dev/null
try "root htb"    ip netns exec router tc qdisc add dev "$DEV" root handle 1: htb default 30
try "class 1:1"   ip netns exec router tc class add dev "$DEV" parent 1: classid 1:1 htb rate 100mbit
for c in 10 20 30 40; do
  try "class 1:$c" ip netns exec router tc class add dev "$DEV" parent 1:1 classid 1:$c htb rate 40mbit ceil 99mbit
done
echo

echo "--- baseline: does flower work at all here? ---"
D="ip netns exec router tc filter add dev $DEV parent 1:"
try "flower ip_proto (baseline)"  $D protocol ip prio 20 flower skip_hw ip_proto udp flowid 1:10
ip netns exec router tc filter del dev "$DEV" parent 1: prio 20 2>/dev/null
try "flower ip_tos (known-good)"  $D protocol ip prio 20 flower skip_hw ip_tos 0xb8/0xfc flowid 1:10
ip netns exec router tc filter del dev "$DEV" parent 1: prio 20 2>/dev/null
echo

echo "--- mark -> class candidates (parent qdisc now exists) ---"
try "fw handle 0x01/0x0f"          $D protocol ip prio 11 fw handle 0x01/0x0f flowid 1:10
ip netns exec router tc filter del dev "$DEV" parent 1: prio 11 2>/dev/null
try "fw mask 0xf handle 0x1"        $D protocol ip prio 11 fw mask 0xf handle 0x1 flowid 1:10
ip netns exec router tc filter del dev "$DEV" parent 1: prio 11 2>/dev/null
try "flower meta mark"              $D protocol all prio 11 flower skip_hw meta mark 0x1/0xf flowid 1:10
ip netns exec router tc filter del dev "$DEV" parent 1: prio 11 2>/dev/null

# `basic match "meta 0x1 0xf"` failed with "Usage: EXPR". The ematch grammar is
# not `meta`; ematch ops are named `skb/<field>`, and mark is one of them. Worth
# one more round, because if ematch can match skb/mark then the original
# nftables-sets -> mark -> static-filter design survives intact -- and every part
# of that half is already built and now proven on a real kernel.
try "basic match skb/mark"          $D protocol all prio 11 basic match "skb/mark 0x1 0xf" flowid 1:10
ip netns exec router tc filter del dev "$DEV" parent 1: prio 11 2>/dev/null
try "basic match skb/mark mask"     $D protocol all prio 11 basic match "skb/mark 0x1 0x0f" flowid 1:10
ip netns exec router tc filter del dev "$DEV" parent 1: prio 11 2>/dev/null
try "basic ematch skb/mark"         $D protocol all prio 11 basic ematch "skb/mark 0x1 0xf" flowid 1:10
ip netns exec router tc filter del dev "$DEV" parent 1: prio 11 2>/dev/null
try "basic match meta skb/mark"     $D protocol all prio 11 basic match "meta skb/mark 0x1 0xf" flowid 1:10
ip netns exec router tc filter del dev "$DEV" parent 1: prio 11 2>/dev/null
echo

# If nothing can read a mark, nftables can steer tc indirectly: rewrite DSCP to
# a reserved selector code and let flower match on it. Both components are
# proven (flower ip_tos above, and gate check 14).
#
# Both previous attempts here were invalid and said nothing:
#   `dscp set 0x28`    -- "syntax error, unexpected set": `dscp` is not a
#                          settable keyword in that position. A genuine result.
#   `meta dsfield set` -- genuinely not a meta key; the error helpfully lists
#                          the real ones. A genuine result.
#   `ip dscp set`      -- "No such file or directory" with the caret on the
#                          CHAIN NAME. That is a missing chain, not a syntax
#                          error: the rules were added to chains probe/probe2/
#                          probe3 which were never created. UNTESTED, and the
#                          correct spelling is the one worth knowing.
echo "--- steering via DSCP rewrite (if no mark matcher exists) ---"
$NS nft add chain ip aciq probe 2>/dev/null
$NS nft add chain ip aciq probe2 2>/dev/null
try "nft ip dscp set 0x28"  $NS nft add rule ip aciq probe \
  ip saddr . ip daddr . meta l4proto . th dport @leased ip dscp set 0x28
try "nft ip dscp set ef"    $NS nft add rule ip aciq probe2 \
  ip saddr . ip daddr . meta l4proto . th dport @leased ip dscp set af41
try "nft ip dscp set cs5"   $NS nft add rule ip aciq probe2 \
  ip saddr . ip daddr . meta l4proto . th dport @interactive ip dscp set cs5
# The IPv6 spelling is `ip6 dscp set`, which the probe has never exercised. The
# generator emits it, so it must be verified rather than assumed.
$NS nft add table ip6 aciqprobe 2>/dev/null
$NS nft add set ip6 aciqprobe s6 \
  '{ type ipv6_addr . ipv6_addr . inet_proto . inet_service ; flags timeout ; timeout 120s ; }' 2>/dev/null
try "nft ip6 dscp set cs5"  $NS nft add rule ip6 aciqprobe ip6 saddr . ip6 daddr . \
  meta l4proto . th dport @s6 ip6 dscp set cs5
$NS nft delete table ip6 aciqprobe 2>/dev/null
try "flower reads rewritten dscp" $D protocol ip prio 21 flower skip_hw ip_tos 0x28/0xfc flowid 1:20
ip netns exec router tc filter del dev "$DEV" parent 1: prio 21 2>/dev/null
$NS nft delete chain ip aciq probe 2>/dev/null
$NS nft delete chain ip aciq probe2 2>/dev/null
echo

# ==========================================================================
# 3. fallback key shape: can flower match the flow key directly?
# If no mark matcher exists, per-class flower filters are the remaining option.
# Trade-off: a netlink transaction per reclassification, which is exactly what
# the nftables-set design existed to avoid. Acceptable only if the number of
# concurrent classified flows is small, as it is for a home router.
# ==========================================================================
echo "--- flower flow-key matching ---"
try "flower proto+dst_port"  $D protocol ip prio 22 flower skip_hw ip_proto udp dst_port 7001 flowid 1:20
ip netns exec router tc filter del dev "$DEV" parent 1: prio 22 2>/dev/null
try "flower src+dst+proto+port" $D protocol ip prio 22 flower skip_hw \
  src_ip 203.0.113.2 dst_ip 10.0.1.2 ip_proto udp dst_port 7001 flowid 1:20
ip netns exec router tc filter del dev "$DEV" parent 1: prio 22 2>/dev/null
try "flower ipv6 flow key"  $D protocol ipv6 prio 22 flower skip_hw \
  src_ip 2001:db8::2 dst_ip fd00:1::2 ip_proto udp dst_port 7003 flowid 1:20
ip netns exec router tc filter del dev "$DEV" parent 1: prio 22 2>/dev/null
try "flower src_ip only"    $D protocol ip prio 22 flower skip_hw src_ip 203.0.113.2 flowid 1:20
ip netns exec router tc filter del dev "$DEV" parent 1: prio 22 2>/dev/null
echo

# ==========================================================================
# 4. nftables set + key lookup shape, on a table that actually exists this time
# ==========================================================================
# The first version of this section probed table `aciqprobe`, which was never
# created, so all three commands failed with "No such file or directory" and
# said nothing about the key shape. Created properly now.
echo "--- nft set key / lookup shape ---"
NS="ip netns exec router"
$NS nft delete table ip aciqprobe 2>/dev/null
$NS nft add table ip aciqprobe
try "set with flags timeout"  $NS nft add set ip aciqprobe s1 \
  '{ type ipv4_addr . ipv4_addr . inet_proto . inet_service ; flags timeout ; timeout 120s ; }'
try "chain for lookup"        $NS nft add chain ip aciqprobe c1 \
  '{ type filter hook prerouting priority mangle; policy accept; }'
try "rule: dotted concat lookup" $NS nft add rule ip aciqprobe c1 \
  iifname veth-wan ip saddr . ip daddr . meta l4proto . th dport @s1 meta mark set 16
try "element with timeout"    $NS nft add element ip aciqprobe s1 \
  '{ 203.0.113.2 . 10.0.1.2 . udp . 7001 timeout 120s }'
try "set list shows the element" $NS nft list set ip aciqprobe s1
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