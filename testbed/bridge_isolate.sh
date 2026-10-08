#!/usr/bin/env bash
# testbed/bridge_isolate.sh — minimal reproduction of the DSCP steering fault.
#
#   cd ~/Desktop/Full-projects/TATA-ELXSI
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/bridge_isolate.sh
#
# WHY THIS EXISTS
#
# Gate check 16b says: a packet whose DSCP was rewritten by nftables in prerouting
# does not reach class 1:20, while a packet that arrived already carrying that DSCP
# does. Four hypotheses were tested and killed in the full gate:
#
#   * `meta l4proto` width mismatch          -> the rule matched all 60 packets
#   * the rewrite does not survive to egress -> the CLIENT received DSCP 0x18
#   * flower matches skb->priority           -> `meta priority set` was applied and
#                                              1:20 still did not grow
#   * no per-filter stats                    -> act_stats does not exist on this
#                                              kernel, so there are no counters
#
# The problem with debugging in the gate is that five steer filters, the gate's own
# DSCP-EF u32 filter at pref 1, four HTB classes, fq_codel leaves and two address
# families are all in the path at once. Nothing isolates which of them matters.
#
# So this builds the smallest thing that can fail:
#
#   one HTB tree, three classes, ONE flower filter, one nftables rule
#
# and runs the same two tests side by side:
#
#   A  DSCP set by the SENDER      -> should reach the class
#   B  DSCP set by NFTABLES        -> currently does not
#
# If B fails here, the fault is in the nftables-writes-DSCP / tc-reads-DSCP
# interaction and nothing in the rest of the bridge is relevant. If B passes here,
# the fault is in something the full gate adds, and this script has narrowed it
# to a named suspect instead of a vague interaction.
#
# Runs in seconds. Does not touch aciq.bridge: these commands are written by
# hand deliberately, so that a bug in the generator cannot hide a bug in the
# mechanism. bridge_probe.sh covers the generator; this covers the mechanism.

set -uo pipefail
cd "$(dirname "$0")"
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
DEV=veth-lan
IN=veth-wan
R="ip netns exec router"
W="ip netns exec wan"
C="ip netns exec client"

[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }

if ! ip netns list | grep -qw router; then
  echo "[setup] creating namespaces"
  ./cleanup.sh >/dev/null 2>&1 || true
  ./setup.sh >/dev/null || { echo "setup.sh failed"; exit 1; }
fi
echo "[setup] ready"
echo

PASS=0; FAIL=0
res () { # res <label> <condition-rc>
  if [ "$2" -eq 0 ]; then echo "  PASS  $1"; PASS=$((PASS+1))
  else echo "  FAIL  $1"; FAIL=$((FAIL+1)); fi
}
b () { $R tc -s class show dev "$DEV" | awk -v c="class htb $1" \
         '$0 ~ c {f=1} f && /Sent/ {print $2; exit}'; }
send () { # send <port> <tos-hex> [count]
  $W "$VENV/bin/python" - "$1" "$2" "${3:-60}" <<'PY'
import socket, sys, time
port, tos, n = int(sys.argv[1]), int(sys.argv[2], 16), int(sys.argv[3])
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
if tos:
    s.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos)
for _ in range(n):
    s.sendto(b"x" * 1000, ("10.0.1.2", port))
    time.sleep(0.002)
s.close()
PY
}

# ---------------------------------------------------------------------------
echo "--- minimal HTB tree: three classes, no fq_codel, no other filters ---"
$R tc qdisc del dev "$DEV" root 2>/dev/null
$R tc qdisc add dev "$DEV" root handle 1: htb default 30
$R tc class add dev "$DEV" parent 1:  classid 1:1  htb rate 100mbit ceil 100mbit
$R tc class add dev "$DEV" parent 1:1 classid 1:10 htb rate 40mbit  ceil 100mbit
$R tc class add dev "$DEV" parent 1:1 classid 1:20 htb rate 40mbit  ceil 100mbit
$R tc class add dev "$DEV" parent 1:1 classid 1:30 htb rate 40mbit  ceil 100mbit
echo "classes: $($R tc class show dev "$DEV" | grep -c 'class htb')"
echo

# Exactly ONE filter: DSCP 0x18 -> 1:20. Nothing else can match first.
echo "--- installing one flower filter: ip_tos 0x18/0xfc -> 1:20 ---"
$R tc filter add dev "$DEV" parent 1: protocol ip prio 10 flower skip_hw \
   ip_tos 0x18/0xfc flowid 1:20 \
  || { echo "could not install the flower filter"; exit 1; }
$R tc filter show dev "$DEV" parent 1: | sed -n '1,8p'
echo

# ---------------------------------------------------------------------------
echo "--- A: DSCP 0x18 set by the SENDER (no nftables involved) ---"
A0=$(b 1:20); A3=$(b 1:30)
send 7010 18 60
sleep 1
A1=$(b 1:20); A3n=$(b 1:30)
echo "  1:20 $A0 -> $A1    1:30 $A3 -> $A3n"
if [ "${A1:-0}" -gt "${A0:-0}" ]; then res "A: sender-set DSCP 0x18 reaches 1:20" 0
else res "A: sender-set DSCP 0x18 reaches 1:20 (FAILED -- so flower ip_tos does
      not work at all here, and the gate's 16a result was a fluke)" 1; fi
echo

# ---------------------------------------------------------------------------
echo "--- setting up one nftables rule that rewrites DSCP on dport 7001 ---"
$R nft delete table ip isote 2>/dev/null
$R nft add table ip isote
$R nft add chain ip isote c '{ type filter hook prerouting priority mangle; policy accept; }'
# dport only -- no set, no saddr/daddr/l4proto concatenation, nothing else to
# get wrong. If this still fails, the set machinery is irrelevant to the fault.
$R nft add rule ip isote c iifname "$IN" th dport 7001 ip dscp set cs3 counter
$R nft list ruleset | grep 'isote' | grep dport
echo

# ---------------------------------------------------------------------------
# E: WHERE does the rewritten DSCP exist?
#
# The contradiction: the CLIENT receives all 60 packets with DSCP 0x18, yet
# neither flower (which matches ip_tos) nor u32 (which reads the header
# directly) routes them. Those facts cannot both hold unless the DSCP is not
# 0x18 at tc time.
#
# So count it at each hook inside the router:
#
#   prerouting   - where the rule writes it
#   forward      - after routing, before egress. Should still be 0x18.
#   postrouting  - immediately before dev_queue_xmit
#
# Whichever hook first shows 0 tells us where it is being lost, which is a
# question about hook ordering rather than about DSCP, sets, or tc.
# ---------------------------------------------------------------------------
echo "--- E: where does the rewritten DSCP exist inside the router? ---"
$R nft delete table ip isopost 2>/dev/null
$R nft add table ip isopost
$R nft add chain ip isopost f '{ type filter hook forward priority mangle; policy accept; }'
$R nft add chain ip isopost p '{ type filter hook postrouting priority mangle; policy accept; }'
$R nft add chain ip isopost q '{ type filter hook prerouting priority -200; policy accept; }'
$R nft add rule ip isopost q th dport 7001 ip dscp 0x18 counter
$R nft add rule ip isopost q th dport 7001 ip dscp 0x00 counter
$R nft add rule ip isopost f th dport 7001 ip dscp 0x18 counter
$R nft add rule ip isopost f th dport 7001 ip dscp 0x00 counter
$R nft add rule ip isopost p th dport 7001 ip dscp 0x18 counter
$R nft add rule ip isopost p th dport 7001 ip dscp 0x00 counter

# re-assert the steering rule (test C replaced the table)
$R nft delete table ip isote 2>/dev/null
$R nft add table ip isote
$R nft add chain ip isote c '{ type filter hook prerouting priority mangle; policy accept; }'
$R nft add rule ip isote c iifname "$IN" th dport 7001 ip dscp set cs3 counter

E20=$(b 1:20)
send 7001 00 60
sleep 1
E21=$(b 1:20)
# Printed raw rather than parsed. An earlier attempt extracted counts with awk
# keyed on the chain name and never reset state between chains, so it could
# report a neighbouring chain's counter. Reading six lines is not worth an awk
# bug -- and this harness has already had two of its own.
echo "  1:20 $E20 -> $E21"
echo "  chain q = prerouting at -200 (BEFORE the rewrite: expect 0x18 = 0)"
echo "  chain f = forward at mangle     (AFTER  the rewrite: expect 0x18 = 60)"
echo "  chain p = postrouting at mangle (expect 0x18 = 60)"
echo
$R nft list table ip isopost | grep -E 'chain |ip dscp' | sed 's/^/    /'
echo

echo "--- B: DSCP 0x18 set by NFTABLES on dport 7001 ---"
B0=$(b 1:20); B3=$(b 1:30)
send 7001 00 60
sleep 1
B1=$(b 1:20); B3n=$(b 1:30)
NPKT=$($R nft list ruleset | grep 'dport 7001' | sed -n 's/.*counter packets \([0-9]*\).*/\1/p')
echo "  1:20 $B0 -> $B1    1:30 $B3 -> $B3n    nft rule matched ${NPKT:-?} pkt"
if [ "${B1:-0}" -gt "${B0:-0}" ]; then res "B: nftables-set DSCP reaches 1:20" 0
else res "B: nftables-set DSCP reaches 1:20" 1; fi

echo "  --- what the client actually receives ---"
$C nft delete table ip isowatch 2>/dev/null
$C nft add table ip isowatch
$C nft add chain ip isowatch c '{ type filter hook prerouting priority mangle; policy accept; }'
$C nft add rule ip isowatch c ip dscp 0x18 counter
$C nft add rule ip isowatch c ip dscp 0x00 counter
send 7001 00 60
sleep 1
echo "  --- the client-side watch, in full ---"
$C nft list table ip isowatch | sed 's/^/    /'
W18=$($C nft list table ip isowatch | grep 'ip dscp 0x18' \
        | sed -n 's/.*counter packets \([0-9]*\).*/\1/p')
W00=$($C nft list table ip isowatch | grep 'ip dscp 0x00' \
        | sed -n 's/.*counter packets \([0-9]*\).*/\1/p')
echo "  client saw DSCP 0x18: ${W18:-?}    DSCP 0x00: ${W00:-?}"
echo

# ---------------------------------------------------------------------------
echo "--- C: same, but the rule also sets meta priority (the unproven hypothesis) ---"
$R nft delete table ip isote 2>/dev/null
$R nft add table ip isote
$R nft add chain ip isote c '{ type filter hook prerouting priority mangle; policy accept; }'
$R nft add rule ip isote c iifname "$IN" th dport 7001 ip dscp set cs3 meta priority set 0x18 counter
C0=$(b 1:20)
send 7001 00 60
sleep 1
C1=$(b 1:20)
echo "  1:20 $C0 -> $C1"
if [ "${C1:-0}" -gt "${C0:-0}" ]; then res "C: meta priority makes it work" 0
else res "C: meta priority makes it work (no)" 1; fi
echo

# ---------------------------------------------------------------------------
# D: u32 instead of flower, for IPv4.
#
# `u32 match ip dsfield` reads the IP header directly. flower `ip_tos` has now
# been shown not to respond to a DSCP written by nftables even though the client
# receives the packet correctly marked. If u32 DOES route it, the header is
# demonstrably 0x18 at tc time, flower specifically is reading something else,
# and u32 is a working IPv4 mechanism.
#
# This is the pragmatic fix candidate: u32 for IPv4 (already proven by gate check
# 13 for DSCP-EF), flower for IPv6.
echo "--- D: u32 'match ip dsfield' instead of flower, IPv4 only ---"
$R tc filter add dev "$DEV" parent 1: protocol ip prio 9 u32 \
   match ip dsfield 0x18 0xfc flowid 1:20
$R tc filter show dev "$DEV" parent 1: | grep -A2 'pref 9 u32' | sed 's/^/  /'
D0=$(b 1:20); D3=$(b 1:30)
send 7001 00 60
sleep 1
D1=$(b 1:20); D3n=$(b 1:30)
echo "  1:20 $D0 -> $D1    1:30 $D3 -> $D3n"
if [ "${D1:-0}" -gt "${D0:-0}" ]; then
  res "D: u32 reads the header flower will not -- u32 is the IPv4 mechanism" 0
else
  res "D: u32 does not route the nftables-written DSCP" 1
fi
echo "  NOTE: D on its own proves nothing. The u32 filter is installed only in"
echo "  test D, so u32 has never been shown to work HERE at all -- not even for"
echo "  a DSCP the sender set. Test F is its positive control."
echo

# ---------------------------------------------------------------------------
# F and G: establish what each mechanism can actually read.
#
# D was inconclusive because u32 had never been tested against a working case,
# and because "meta priority" (test C) may not do what I assumed. Both need a
# positive control.
# ---------------------------------------------------------------------------
echo "--- F: u32 with a SENDER-set DSCP (positive control for u32) ---"
$R tc filter del dev "$DEV" parent 1: protocol ip pref 9 2>/dev/null
$R tc filter add dev "$DEV" parent 1: protocol ip prio 9 u32 \
   match ip dsfield 0x18 0xfc flowid 1:20
$R nft delete table ip isote 2>/dev/null   # no nftables rule active
F0=$(b 1:20); F3=$(b 1:30)
send 7010 18 60
sleep 1
F1=$(b 1:20); F3n=$(b 1:30)
echo "  1:20 $F0 -> $F1    1:30 $F3 -> $F3n"
if [ "${F1:-0}" -gt "${F0:-0}" ]; then res "F: u32 DOES read a sender-set DSCP (u32 works)" 0
else res "F: u32 fails even for a sender-set DSCP (u32 is simply broken here)" 1; fi
echo

echo "--- G: nftables sets ONLY skb->priority, no DSCP rewrite ---"
# Isolates the skb->priority hypothesis completely: no dscp write at all, so the
# header stays 0x00 and only skb->priority becomes 0x18.
#
# If flower now matches, flower reads skb->priority, the hypothesis is right, and
# the fix is to set priority -- for which test C is the negative control.
# If it does not match, flower reads the header, and test B's failure means the
# header is somehow not 0x18 for tc despite postrouting counting 0x18.
$R tc filter del dev "$DEV" parent 1: protocol ip prio 9 2>/dev/null
$R nft delete table ip isote 2>/dev/null
$R nft add table ip isote
$R nft add chain ip isote c '{ type filter hook prerouting priority mangle; policy accept; }'
$R nft add rule ip isote c iifname "$IN" th dport 7001 meta priority set 0x18 counter
$R nft list ruleset | grep 'isote' | grep dport | sed 's/^/  rule: /'
G0=$(b 1:20); G3=$(b 1:30)
send 7001 00 60
sleep 1
G1=$(b 1:20); G3n=$(b 1:30)
echo "  1:20 $G0 -> $G1    1:30 $G3 -> $G3n"
if [ "${G1:-0}" -gt "${G0:-0}" ]; then res "G: flower matches skb->priority -- that is what it reads" 0
else res "G: flower ignores skb->priority; it reads the header" 1; fi
echo

# ---------------------------------------------------------------------------
# H: the destination port may be the variable that has been hiding all along.
#
#   A  dport 7010, sender sets DSCP 0x18            -> PASS
#   F  dport 7010, sender sets DSCP 0x18, u32       -> PASS
#   B  dport 7001, nft rewrites DSCP to 0x18        -> FAIL
#   D  dport 7001, nft rewrites DSCP to 0x18, u32   -> FAIL
#
# Port has been a silent confound throughout. Every pass used 7010 and every
# failure used 7001, and the two differ in BOTH the port and how the DSCP got
# there -- so "the DSCP written by nftables is invisible to tc" and "something
# about 7001" fit the evidence equally well.
#
# H separates them: the nftables rule steers 7010, and the sender sets DSCP 0.
# Same mechanism as B, different port.
# ---------------------------------------------------------------------------
echo "--- H: identical mechanism, dport 7010 instead of 7001 ---"
$R tc filter del dev "$DEV" parent 1: protocol ip pref 9 2>/dev/null
$R nft delete table ip isote 2>/dev/null
$R nft add table ip isote
$R nft add chain ip isote c '{ type filter hook prerouting priority mangle; policy accept; }'
$R nft add rule ip isote c iifname "$IN" th dport 7010 ip dscp set cs3 counter
H0=$(b 1:20); H3=$(b 1:30)
send 7010 00 60
sleep 1
H1=$(b 1:20); H3n=$(b 1:30)
HPK=$($R nft list ruleset | grep 'isote' | grep 'dport 7010' \
       | sed -n 's/.*counter packets \([0-9]*\).*/\1/p')
echo "  1:20 $H0 -> $H1    1:30 $H3 -> $H3n    nft rule matched ${HPK:-?} pkt"
if [ "${H1:-0}" -gt "${H0:-0}" ]; then
  res "H: nftables-steered DSCP WORKS on dport 7010 -- the port was the variable" 0
else
  res "H: nftables-steered DSCP fails on 7010 too -- it is the mechanism" 1
fi
echo

# ---------------------------------------------------------------------------
# I: and the mirror image -- sender sets the DSCP on dport 7001, no nftables.
# If I passes while B fails with identical packets except provenance, provenance
# is the variable. If I fails too, the port is.
# ---------------------------------------------------------------------------
echo "--- I: mirror of H -- sender sets DSCP 0x18 on dport 7001, no nftables ---"
$R nft delete table ip isote 2>/dev/null
I0=$(b 1:20)
send 7001 18 60
sleep 1
I1=$(b 1:20)
echo "  1:20 $I0 -> $I1"
if [ "${I1:-0}" -gt "${I0:-0}" ]; then
  res "I: sender-set DSCP works on 7001 -- the port is innocent, provenance is it" 0
else
  res "I: sender-set DSCP fails on 7001 -- the PORT is the variable" 1
fi
echo

echo "=== SUMMARY ==="
echo "PASS $PASS  FAIL $FAIL"
echo
echo "Interpretation:"
echo "  A pass, B fail  -> nftables-written DSCP is invisible to tc. The fault is"
echo "                    in the write/read interaction, not in sets, not in"
echo "                    priorities, not in the HTB tree."
echo "  A fail          -> flower ip_tos does not work on IPv4 egress here and"
echo "                    gate 16a's PASS was not reproducible."
echo "  A pass, B pass  -> the fault needs something the full gate adds."
echo
echo
echo "  F pass + D fail -> u32 works but rejects an nftables-written DSCP:"
echo "                    u32 reads the header, so the header is not 0x18 for"
echo "                    tc even though postrouting counts 0x18. Something"
echo "                    between postrouting and the classifier restores it."
echo "  F fail          -> u32 is unusable here; only flower is in play."
echo "  G pass          -> flower reads skb->priority. The fix is to set"
echo "                    priority, and test C's failure is then the anomaly"
echo "                    worth chasing."
echo "  G fail          -> flower reads the header, and test B's failure cannot"
echo "                    be explained by hook counters. Re-examine the premise."
echo
echo "  H pass, I pass  -> provenance: an nftables-written DSCP is not visible to"
echo "                    tc, a sender-written one is. The fix is a different"
echo "                    signalling channel, not a different classifier."
echo "  H pass, I fail  -> the port: 7001 specifically defeats both classifiers."
echo "  H fail, I pass  -> the mechanism, confirmed with the port held constant."