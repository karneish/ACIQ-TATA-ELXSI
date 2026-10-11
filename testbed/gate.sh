#!/usr/bin/env bash
# testbed/gate.sh — run:  sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/gate.sh
# Stops at the first failed check. Check 12 is measurement only and never fails.
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p logs
LOG="logs/gate-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
VENV="${ACIQ_VENV:-$HOME/aciq-venv}"
R="ip netns exec router"     # deliberately unquoted: used as `$R cmd args`
PASSED=(); FAILED=""; MEASURED=()

[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }

if [ -x "$VENV/bin/python" ]; then
  PV=$("$VENV/bin/python" -c "import pyroute2,importlib.metadata as m;print(m.version('pyroute2'))" 2>/dev/null || echo "NOT-INSTALLED")
else
  PV="NO VENV at $VENV"
fi

echo "=== ACIQ M0 gate ==="
echo "log: $LOG"
echo "kernel:   $(uname -r)"
echo "tc:       $(tc -V 2>&1)"
echo "pyroute2: $PV"
echo

summary () {
  echo; echo "=== SUMMARY ==="
  for p in "${PASSED[@]:-}";   do [ -n "$p" ] && echo "PASS      $p"; done
  for m in "${MEASURED[@]:-}"; do [ -n "$m" ] && echo "MEASURED  $m"; done
  [ -n "$FAILED" ] && echo "FAIL      $FAILED"
}
ok ()   { PASSED+=("$1");  echo "[PASS] $1"; }
meas () { MEASURED+=("$1"); echo "[MEASURED] $1"; }
die ()  { FAILED="$1"; echo "[FAIL] $1"; echo; echo "STOPPED AT FIRST FAILURE"; summary; sleep 1; exit 1; }

# Priorities are READ FROM THE CODE, never restated here.
#
# The gate used to hardcode the DSCP-EF filters at prio 1 (ip) and prio 2 (ipv6)
# while aciq/tc.py installs them at 30/31. The numbers were never reconciled, so
# check 17 failed: the gate's EF filter sat BELOW the bridge's per-flow filters,
# EF won, and a flow the classifier had rejected still reached 1:10.
#
# That is the gate testing something production does not do -- the worst kind of
# divergence, because the gate keeps passing on its own terms. One source of
# truth from here on.
tcprio () {  # tcprio <ip|ipv6>
  $VENV/bin/python - "$1" <<'PY'
import sys
sys.path.insert(0, "..")
from aciq.tc import DSCP_FILTER_PRIO
print(DSCP_FILTER_PRIO[sys.argv[1]])
PY
}

# bytes observed on a given dport, first match only
ctbytes () { ip netns exec "$1" conntrack -L -f "$2" -p udp 2>/dev/null \
  | awk -v p="$3" '$0 ~ ("dport="p" ") { for(i=1;i<=NF;i++) if($i ~ /^bytes=/){split($i,b,"=");print b[2];exit} }'; }

# format-proof: read receiver-side goodput straight from iperf3 JSON.
# prints nothing on failure (missing 'end' key, or iperf3 emitted {"error":...})
# leading sleep avoids "server is busy" when called twice back-to-back.
rate () { sleep 1; ip netns exec wan iperf3 -c 10.0.1.2 -t 5 -J 2>/dev/null | python3 -c \
"import sys,json
try: print(round(json.load(sys.stdin)['end']['sum_received']['bits_per_second']/1e6,1))
except Exception: pass"; }

# ---------- 1 tooling ----------
MISS=""
for t in tc ip conntrack nft iperf3 ethtool python3; do command -v $t >/dev/null || MISS="$MISS $t"; done
[ -z "$MISS" ] && ok "check 1: tooling" || die "check 1: tooling missing:$MISS"

# ---------- 2 modules ----------
MISS=""
for m in sch_htb sch_netem sch_cake sch_fq_codel sch_prio act_gact act_police \
         cls_flower cls_u32 nf_conntrack; do
  modprobe -q "$m" 2>/dev/null || MISS="$MISS $m"
done
[ -z "$MISS" ] && ok "check 2: modules" || die "check 2: modules missing:$MISS"

# ---------- build testbed (prereq for 3-14) ----------
./cleanup.sh
./setup.sh || die "setup (prereq for checks 3-14)"

# ---------- 3 conntrack per-flow, loopback ----------
ip netns add ct
ip netns exec ct ip link set lo up
ip netns exec ct nft -f - <<'NFT'
table inet t {
  chain inflow {
    type filter hook input priority 0;
    ct state new counter
  }
}
NFT
ip netns exec ct sysctl -qw net.netfilter.nf_conntrack_acct=1
ip netns exec ct python3 -c "
import socket,time
a=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); b=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
t=time.time()
while time.time()-t<5:
    a.sendto(b'x'*1000,('127.0.0.1',9999)); b.sendto(b'x'*200,('127.0.0.1',9998)); time.sleep(0.001)"
ip netns exec ct conntrack -L -p udp | tail -6
A=$(ctbytes ct ipv4 9999); B=$(ctbytes ct ipv4 9998)
echo "9999(1000B)=$A  9998(200B)=$B"
[ -n "$A" ] && [ -n "$B" ] && [ "$A" -gt "$B" ] \
  && ok "check 3: conntrack loopback per-flow" || die "check 3: loopback (A=$A B=$B)"
ip netns del ct

# ---------- 4 namespaces / routes ----------
ip netns exec client ping -c1 -W2 10.0.1.1    >/dev/null 2>&1 \
  && ip netns exec wan ping -c1 -W2 203.0.113.1 >/dev/null 2>&1 \
  && ip netns exec wan ping -c1 -W2 -6 fd00:1::1 >/dev/null 2>&1 \
  && ok "check 4: namespaces and routes" || die "check 4: namespaces and routes"

# ---------- 5 offloads ----------
BAD=0
for p in "router veth-lan" "router veth-wan" "client veth-c" "wan veth-w"; do
  set -- $p
  for f in generic-receive-offload generic-segmentation-offload tcp-segmentation-offload; do
    ip netns exec "$1" ethtool -k "$2" 2>/dev/null | grep -q "$f: on" && BAD=1
  done
done
[ "$BAD" -eq 0 ] && ok "check 5: offloads off" || die "check 5: offloads still on"

ip netns exec client iperf3 -s -D

# ---------- 6 HTB class 1:1 is the bottleneck, same device ----------
# MEASURED FINDINGS from real gate runs — HTB capping is subtler than assumed:
#
#  run 1: parent 1:1 rate 100->20mbit, children left at rate 40/30 ceil 99/97
#         => 28.5 Mbps. ABOVE the parent's new rate. A child may borrow past its
#         parent's rate, up to its own ceil, against the device's real capacity.
#         So changing the parent rate alone does NOT cap anything.
#  run 2: children rescaled to rate 8mbit but ceil 9mbit
#         => 8.6 Mbps. The single iperf3 flow lands in ONE class (default 1:30)
#         and is capped by THAT CLASS's ceil, so clamping ceil too low underfills.
#
# EMPIRICAL RULE: a flow is bounded by its own class ceil. To cap the link at C,
# every child ceil must be <= C, and child rates are rescaled so their sum is
# <= C. Both are enforced by the M3 invariant; these runs are its evidence.
$R tc qdisc  add dev veth-lan root handle 1: htb default 30
$R tc class add dev veth-lan parent 1:  classid 1:1  htb rate 100mbit ceil 100mbit
$R tc class add dev veth-lan parent 1:1 classid 1:10 htb rate 40mbit  ceil 99mbit
$R tc class add dev veth-lan parent 1:1 classid 1:30 htb rate 30mbit  ceil 97mbit
$R tc qdisc add dev veth-lan parent 1:10 handle 10: fq_codel
$R tc qdisc add dev veth-lan parent 1:30 handle 30: fq_codel
A=$(rate); echo "at 100mbit: ${A:-no rate} Mbps"

echo "dropping parent 1:1 to 20mbit AND rescaling children (ceil must not exceed parent)"
$R tc class change dev veth-lan parent 1:  classid 1:1  htb rate 20mbit ceil 20mbit
$R tc class change dev veth-lan parent 1:1 classid 1:10 htb rate 8mbit  ceil 20mbit
$R tc class change dev veth-lan parent 1:1 classid 1:30 htb rate 8mbit  ceil 20mbit
SUMR=$((8+8)); MAXC=20
echo "invariant: sum(child rate)=$SUMR <= 20, max(child ceil)=$MAXC <= 20 -> $([ $SUMR -le 20 ] && [ $MAXC -le 20 ] && echo HOLDS || echo VIOLATED)"
B=$(rate); echo "at 20mbit:  ${B:-no rate} Mbps"
awk -v a="$A" -v b="$B" 'BEGIN{exit !(a+0>80 && a+0<110 && b+0>14 && b+0<24)}' \
  && ok "check 6: HTB bottleneck 1:1" \
  || die "check 6: A=${A:-none} B=${B:-none} (want ~90-97 then ~18-20; empty means iperf3 failed)"

# ---------- 7 netem on a leaf ----------
$R tc qdisc replace dev veth-lan parent 1:30 handle 40: netem delay 20ms
P=$(ip netns exec client ping -c3 -W3 10.0.1.1 | awk -F'/' '/rtt/{print $5}')
$R tc qdisc replace dev veth-lan parent 1:30 handle 30: fq_codel
echo "ping avg with 20ms netem: ${P:-?} ms"
awk -v p="$P" 'BEGIN{exit !(p+0>18)}' && ok "check 7: netem on leaf" || die "check 7: p=${P:-?}"

# ---------- 8 pyroute2 netlink ----------
"$VENV/bin/python" -c "import pyroute2" 2>/dev/null || die "check 8: pyroute2 not in $VENV"
if "$VENV/bin/python" -c "
from pyroute2 import NetNS
with NetNS('router') as ns:
    i=ns.link_lookup(ifname='veth-lan')[0]
    print('IFLA_STATS64:', ns.get_links(i)[0].get_attr('IFLA_STATS64'))
    for c in ns.get_classes(index=i): print('class',c['handle'],c.get_attr('TCA_STATS2'))"
then
  ok "check 8: pyroute2 netlink"
else
  $R tc -s -j class show dev veth-lan || die "check 8: netlink AND tc -s -j both failed"
  PASSED+=("check 8: tc -s -j fallback (NETLINK FAILED)")
  echo "[PASS (JSON fallback)] check 8: pyroute2 netlink failed; tc -s -j used instead"
fi

# ---------- 9 cake at root, 95% of emulated link ----------
$R tc qdisc del dev veth-lan root
$R tc qdisc add dev veth-lan root handle 1: cake bandwidth 95mbit
C=$(rate); echo "cake 95mbit: ${C:-no rate} Mbps"
awk -v c="$C" 'BEGIN{exit !(c+0>80 && c+0<96)}' && ok "check 9: cake at root" || die "check 9: c=${C:-none}"

# ---------- 10 cake + pfifo as leaves, BYTES on 1:50 ----------
# MEASURED FINDING (run 3): `tc qdisc change dev X root handle 1: htb default 50`
# fails with "Change operation not supported by specified qdisc". HTB's default
# class is fixed at creation; you cannot retarget a live HTB tree. The tree has
# to be rebuilt. That is a real constraint on M4/M9: any policy change needing a
# different default class is a full tree rebuild, which must be part of the
# transaction so rollback can restore it.
#
# So build the tree with default 50 already pointing at the single leaf class.
# (Unquoted $1 so "cake bandwidth 19mbit" expands to two arguments.)
build_single_leaf () {
  $R tc qdisc del dev veth-lan root 2>/dev/null
  $R tc qdisc  add dev veth-lan root handle 1: htb default 50
  $R tc class add dev veth-lan parent 1:  classid 1:1  htb rate 20mbit ceil 20mbit
  $R tc class add dev veth-lan parent 1:1 classid 1:50 htb rate 20mbit ceil 20mbit
  $R tc qdisc add dev veth-lan parent 1:50 handle 50: $1
}
bytes_on_1_50 () { $R tc -s class show dev veth-lan | awk '/class htb 1:50/{f=1} f&&/Sent/{print $2;exit}'; }

build_single_leaf "cake bandwidth 19mbit"
K=$(rate); BY=$(bytes_on_1_50)
echo "cake leaf: ${K:-no rate} Mbps, 1:50 bytes=$BY"
awk -v k="$K" -v by="$BY" 'BEGIN{exit !(k+0>14 && k+0<21 && by+0>1000000)}' \
  && ok "check 10a: cake as leaf" || die "check 10a: k=${K:-none} by=$BY (want 14-21 Mbps, >1MB on 1:50)"

build_single_leaf "pfifo limit 1000"
F=$(rate); BY=$(bytes_on_1_50)
echo "pfifo leaf: ${F:-no rate} Mbps, 1:50 bytes=$BY"
awk -v f="$F" -v by="$BY" 'BEGIN{exit !(f+0>14 && f+0<21 && by+0>1000000)}' \
  && ok "check 10b: pfifo as leaf" || die "check 10b: f=${F:-none} by=$BY (want 14-21 Mbps, >1MB on 1:50)"

# ---------- 11 conntrack per-flow, forwarded, IPv4 ----------
ip netns exec wan python3 -c "
import socket,time
a=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); b=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
t=time.time()
while time.time()-t<6:
    a.sendto(b'x'*1000,('10.0.1.2',7001)); b.sendto(b'x'*200,('10.0.1.2',7002)); time.sleep(0.001)"
ip netns exec router conntrack -L -p udp | grep 'dport=700'
A=$(ctbytes router ipv4 7001); B=$(ctbytes router ipv4 7002)
echo "7001(1000B)=$A  7002(200B)=$B"
[ -n "$A" ] && [ -n "$B" ] && [ "$A" -gt "$B" ] \
  && ok "check 11: conntrack forwarded per-flow v4" || die "check 11: A=$A B=$B"

# ---------- 12 MEASUREMENT ONLY, no pass/fail ----------
snap () { $R tc -s class show dev veth-lan | grep -E 'class htb|Sent'
          $R tc -s qdisc show dev veth-lan | grep -E 'qdisc|Sent|backlog|ecn_mark'; }
$R tc qdisc del dev veth-lan root
$R tc qdisc  add dev veth-lan root handle 1: htb default 30
$R tc class add dev veth-lan parent 1:  classid 1:1  htb rate 20mbit ceil 20mbit
$R tc class add dev veth-lan parent 1:1 classid 1:10 htb rate 8mbit  ceil 20mbit
$R tc class add dev veth-lan parent 1:1 classid 1:30 htb rate 8mbit  ceil 20mbit
# 1:20 and 1:40 are needed for checks 15-20. The steer filters reference them by
# flowid, and `tc filter add ... flowid 1:20` against a class that does not exist
# fails with "Parent Qdisc doesn't exists" -- the same error that produced two
# rounds of false negatives in bridge_probe.sh, so it was worth fixing before it
# produced a third here and pointed the wrong way.
$R tc class add dev veth-lan parent 1:1 classid 1:20 htb rate 8mbit  ceil 20mbit
$R tc class add dev veth-lan parent 1:1 classid 1:40 htb rate 8mbit  ceil 20mbit
$R tc qdisc add dev veth-lan parent 1:10 handle 10: fq_codel
$R tc qdisc add dev veth-lan parent 1:30 handle 30: fq_codel
$R tc qdisc add dev veth-lan parent 1:20 handle 20: fq_codel
$R tc qdisc add dev veth-lan parent 1:40 handle 40: fq_codel
# prio comes from aciq.tc.DSCP_FILTER_PRIO so the gate and production cannot
# disagree about filter order again.
$R tc filter add dev veth-lan parent 1: protocol ip prio "$(tcprio ip)" u32 \
   match ip dsfield 0xb8 0xfc flowid 1:10
$R ping -c3 10.0.1.2 | tee /tmp/g12_base.txt | tail -2
snap > /tmp/g12_before.txt
ip netns exec wan iperf3 -c 10.0.1.2 -t 25 -f m > /tmp/g12_iperf.txt & P1=$!
sleep 3
ip netns exec wan ping -c18 -i1 -Q 0xB8 -W3 10.0.1.2 > /tmp/g12_a.txt & P2=$!
$R ping -c18 -i1 -W3 10.0.1.2                             > /tmp/g12_c.txt & P3=$!
sleep 1
ip netns exec wan ping -c18 -i1      -W3 10.0.1.2         > /tmp/g12_b.txt & P4=$!
wait $P1 $P2 $P3 $P4
snap > /tmp/g12_after.txt
echo "idle baseline:"; tail -2 /tmp/g12_base.txt
for f in a b c; do
  case $f in a) n="EF, class 1:10";; b) n="unmarked, class 1:30";; c) n="router-orig, class 1:30";; esac
  echo "($f) $n"; tail -2 /tmp/g12_$f.txt
  grep -oE 'time=[0-9.]+' /tmp/g12_$f.txt | tr '\n' ' '; echo
done
echo "counter delta (judge dropped/overlimits values, not which lines differ):"
diff /tmp/g12_before.txt /tmp/g12_after.txt
echo "throughput:"; grep -iE 'receiver' /tmp/g12_iperf.txt
meas "check 12: saturation signals (read numbers above)"

# ---------- 13 conntrack per-flow, forwarded, IPv6 ----------
ip netns exec wan python3 -c "
import socket,time
a=socket.socket(socket.AF_INET6,socket.SOCK_DGRAM); b=socket.socket(socket.AF_INET6,socket.SOCK_DGRAM)
t=time.time()
while time.time()-t<6:
    a.sendto(b'x'*1000,('fd00:1::2',7003,0,0)); b.sendto(b'x'*200,('fd00:1::2',7004,0,0)); time.sleep(0.001)"
ip netns exec router conntrack -L -f ipv6 -p udp | grep 'dport=700'
A=$(ctbytes router ipv6 7003); B=$(ctbytes router ipv6 7004)
echo "7003(1000B)=$A  7004(200B)=$B"
[ -n "$A" ] && [ -n "$B" ] && [ "$A" -gt "$B" ] \
  && ok "check 13: conntrack forwarded per-flow v6" || die "check 13: A=$A B=$B"

# ---------- 14 IPv6 filter match, proven by byte increase on 1:10 ----------
# A single priority cannot hold both the v4 and v6 filter, which is why
# DSCP_FILTER_PRIO has two entries. The values come from aciq.tc, not from here.
BEF=$($R tc -s class show dev veth-lan | awk '/class htb 1:10/{f=1} f&&/Sent/{print $2;exit}')
$R tc filter add dev veth-lan parent 1: protocol ipv6 prio "$(tcprio ipv6)" flower \
   ip_tos 0xb8/0xfc flowid 1:10 \
  || die "check 14: IPv6 filter syntax rejected"
ip netns exec wan ping -6 -c20 -i0.05 -Q 0xB8 -s 500 -W3 fd00:1::2 | tail -3
AFT=$($R tc -s class show dev veth-lan | awk '/class htb 1:10/{f=1} f&&/Sent/{print $2;exit}')
echo "class 1:10 bytes before=$BEF after=$AFT"
$R tc filter show dev veth-lan parent 1: | sed -n '1,14p'
awk -v a="$BEF" -v b="$AFT" 'BEGIN{exit !(b+0 > a+0 + 5000)}' \
  && ok "check 14: IPv6 EF filter routes to 1:10" || die "check 14: 1:10 bytes did not grow ($BEF -> $AFT)"


# ==========================================================================
# M1 -> M4 bridge: nftables mark -> tc fw -> class
#
# Checks 15-20 drive the REAL aciq.bridge generators rather than hand-written
# copies of the same commands. That is the point of splitting command
# generation (pure, unit-tested offline) from execution (needs root): the gate
# proves the kernel accepts what the shipped code emits, instead of proving that
# a second hand-written transcription of it works.
#
# Direction: flows ARRIVE on veth-wan and are shaped EGRESS on veth-lan, so the
# mark is set on ingress and read by the tc filters on the LAN side.
# ==========================================================================
BIN_IF=veth-wan
EGR_IF=veth-lan

# mark a flow using the shipped Bridge class
bmark () {  # bmark <src> <dst> <proto> <dport> <class>
  $VENV/bin/python - "$1" "$2" "$3" "$4" "$5" <<'PY'
import sys
sys.path.insert(0, "..")
from aciq.bridge import Bridge, FlowKey
from aciq.marks import (CLASS_UNCLASSIFIED, CLASS_INTERACTIVE, CLASS_ADAPTIVE,
                        CLASS_BULK, CLASS_LEASED)
src, dst, proto, dport, cls = sys.argv[1:6]
ids = {"unclassified": CLASS_UNCLASSIFIED, "interactive": CLASS_INTERACTIVE,
       "adaptive": CLASS_ADAPTIVE, "bulk": CLASS_BULK, "leased": CLASS_LEASED}
b = Bridge(dev="veth-lan", in_if="veth-wan", ns="router")
b.mark(FlowKey(src, dst, proto, int(dport)), ids[cls])
print("steered", src, dst, proto, dport, "->", cls)
PY
}

# Remove one flow's filter, via the shipped Bridge.
bunmark () {  # bunmark <src> <dst> <proto> <dport>
  $VENV/bin/python - "$1" "$2" "$3" "$4" <<'PY'
import sys
sys.path.insert(0, "..")
from aciq.bridge import Bridge, FlowKey
b = Bridge(dev="veth-lan", in_if="veth-wan", ns="router")
b.forget(FlowKey(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])))
print("released", sys.argv[1], sys.argv[4])
PY
}

# bytes on an HTB class, by classid
cbytes () { $R tc -s class show dev "$EGR_IF" \
  | awk -v c="class htb $1" '$0 ~ c {f=1} f && /Sent/ {print $2; exit}'; }

# send UDP from wan, optionally with an EF DSCP mark
# NOTE: the TOS argument is a HEX byte or the literal "ef". A bare "1" is no
# longer accepted as a boolean: after the rename to tos, "1" parses as IP_TOS
# 0x01, which is DSCP 0 with the ECN bits set -- silently the wrong value, and
# check 17 depends on claiming real EF.
send () {  # send <dst> <port> <size> <tos:hex|ef> [count] [src]
  # `src` is bound explicitly. The filters these checks install match an exact
  # source address, so letting the kernel pick one makes the check depend on
  # which address happens to be primary on the interface. That held only while
  # wan had a single address; adding per-device addresses broke check 18.
  ip netns exec wan "$VENV/bin/python" - "$1" "$2" "$3" "$4" "${5:-40}" "${6:-}" <<'PY'
import socket, sys, time
dst, port, size, tos, n, src = sys.argv[1:7]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
if src:
    s.bind((src, 0))
if tos == "ef":
    tos = 0xB8
elif tos in ("0", "", "none"):
    tos = 0
else:
    # reject a bare "1"/"0": those read as booleans to whoever wrote the call
    # site, and 0x01 is DSCP 0 with ECN set rather than what was intended
    if len(tos) < 2:
        sys.exit(f"ambiguous TOS {tos!r}: pass a hex byte like '18', or 'ef', or '0'")
    tos = int(tos, 16)
if tos:
    s.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos)
for _ in range(int(n)):
    s.sendto(b"x" * int(size), (dst, int(port)))
    time.sleep(0.002)
s.close()
PY
}

send6 () {  # send6 <dst> <port> <size> [count] [src]
  # See send(): bound explicitly, never left to source-address selection.
  ip netns exec wan "$VENV/bin/python" - "$1" "$2" "$3" "${4:-40}" "${5:-}" <<'PY'
import socket, sys, time
dst, port, size, n, src = sys.argv[1:6]
s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
if src:
    s.bind((src, 0, 0, 0))
for _ in range(int(n)):
    s.sendto(b"x" * int(size), (dst, int(port), 0, 0))
    time.sleep(0.002)
s.close()
PY
}

# Filter order is a correctness property, not a preference: a per-flow filter
# must be consulted before the DSCP-EF fallback, or a flow the classifier
# rejected still gets interactive priority. Asserted here rather than assumed,
# because the gate and aciq/tc.py disagreed about these numbers for the whole
# life of check 17 and only the failure revealed it.
$VENV/bin/python - <<'PY' || die "check 15: per-flow filters do not precede DSCP-EF"
import sys
sys.path.insert(0, "..")
from aciq.bridge import FLOW_FILTER_PRIO
from aciq.tc import DSCP_FILTER_PRIO
bad = [(p, FLOW_FILTER_PRIO[p], DSCP_FILTER_PRIO[p])
       for p in FLOW_FILTER_PRIO
       if FLOW_FILTER_PRIO[p] >= DSCP_FILTER_PRIO[p]]
print("per-flow", FLOW_FILTER_PRIO, "dscp-ef", DSCP_FILTER_PRIO)
sys.exit(f"per-flow filter at prio {bad} does not precede DSCP-EF" if bad else 0)
PY

# ---------- 15 per-flow filters install ----------
# Enforcement is a per-flow `tc flower` filter installed by Bridge.mark(). There
# is no static filter block, so this asserts the tc tree accepts one.
$R tc filter add dev "$EGR_IF" parent 1: protocol ip prio 99 flower skip_hw \
   src_ip 10.0.0.1 dst_ip 10.0.0.2 ip_proto tcp dst_port 65535 flowid 1:30 \
  || die "check 15: could not install a per-flow flower filter"
$R tc filter del dev "$EGR_IF" parent 1: protocol ip prio 99
ok "check 15: per-flow flower filters install"

# ---------- 16 steered IPv4 flow reaches its class ----------
# This replaces the DSCP-steering check. A DSCP written by nftables is invisible
# to tc egress classifiers on this toolchain even though the packet is
# transmitted carrying it; a per-flow filter matches the flow key directly.
# See testbed/bridge_isolate.sh tests J and K.
A20=$(cbytes 1:20); A30=$(cbytes 1:30)
bmark 203.0.113.2 10.0.1.2 udp 7001 adaptive || die "check 16: steering failed"
send 10.0.1.2 7001 1000 0 60 203.0.113.2
sleep 1
B20=$(cbytes 1:20); B30=$(cbytes 1:30)
echo "1:20 $A20 -> $B20   1:30 $A30 -> $B30"
echo "--- the filter that was installed ---"
$R tc filter show dev "$EGR_IF" parent 1: | grep -E 'pref 5 |src_ip|dst_ip|dst_port' \
  | sed 's/^/  /'
awk -v a="$A20" -v b="$B20" 'BEGIN{exit !(b+0 > a+0 + 20000)}' \
  && ok "check 16: steered IPv4 flow routed to 1:20 -- ADAPTIVE receives traffic" \
  || die "check 16: 1:20 did not grow ($A20 -> $B20). This is the first check that
ADAPTIVE has ever received anything: adaptive_video reported goodput 0.0 in every
v0 sample because nothing routed to class 1:20."

# ---------- 17 a rejected EF-claiming flow does not reach 1:10 ----------
# The classifier must be able to deny EF priority to a flow that claims it. The
# per-flow filter sits at prio 5, ahead of the DSCP-EF fallback at prio 30, so an
# explicit verdict wins regardless of what the sender put in the header.
C10=$(cbytes 1:10)
bmark 203.0.113.2 10.0.1.2 udp 7002 unclassified || die "check 17: steering failed"
send 10.0.1.2 7002 1000 ef 60 203.0.113.2
sleep 1
D10=$(cbytes 1:10)
echo "EF-claiming but classified unclassified: 1:10 $C10 -> $D10"
awk -v a="$C10" -v b="$D10" 'BEGIN{exit !(b+0 <= a+0 + 2000)}' \
  && ok "check 17: a rejected EF-claiming flow does not reach 1:10" \
  || die "check 17: EF-claiming flow reached 1:10 anyway ($C10 -> $D10)"

# ---------- 18 steered IPv6 flow reaches its class ----------
A20=$(cbytes 1:20)
bmark fd00:2::2 fd00:1::2 udp 7003 adaptive || die "check 18: steering failed"
send6 fd00:1::2 7003 1000 60 fd00:2::2
sleep 1
B20=$(cbytes 1:20)
echo "ipv6 1:20 $A20 -> $B20"
awk -v a="$A20" -v b="$B20" 'BEGIN{exit !(b+0 > a+0 + 20000)}' \
  && ok "check 18: steered IPv6 flow routed to 1:20" \
  || die "check 18: IPv6 1:20 did not grow ($A20 -> $B20)"

# ---------- 19 removing the filter returns the flow to the default class ----------
# REPLACES the old "mark expiry" check. Per-flow filters have no kernel-side
# timeout: the nftables-set design expired them for free, and that capability is
# genuinely lost. So expiry is no longer something the kernel does for us, and
# removal has to be shown working rather than assumed.
E0=$(cbytes 1:20); E3=$(cbytes 1:30)
bunmark 203.0.113.2 10.0.1.2 udp 7001 || die "check 19: removal failed"
send 10.0.1.2 7001 1000 0 60 203.0.113.2
sleep 1
F20=$(cbytes 1:20); F30=$(cbytes 1:30)
echo "after removing the filter: 1:20 $E0 -> $F20   1:30 $E3 -> $F30"
awk -v a="$E0" -v b="$F20" 'BEGIN{exit !(b+0 <= a+0 + 2000)}' \
  && ok "check 19: removing the filter returns the flow to the default class" \
  || die "check 19: 1:20 still growing after the filter was removed ($E0 -> $F20)"

# ---------- 20 teardown ----------
$VENV/bin/python - <<'PY' || die "check 20: bridge teardown failed"
import sys
sys.path.insert(0, "..")
from aciq.bridge import Bridge, FlowKey
b = Bridge(dev="veth-lan", in_if="veth-wan", ns="router")
b.teardown()
PY
$R tc filter show dev "$EGR_IF" parent 1: | grep -q 'dst_port 700' \
  && die "check 20: a per-flow filter survived teardown" \
  || ok "check 20: teardown removes the bridge's filters"

summary
echo; echo "log saved to $LOG"
