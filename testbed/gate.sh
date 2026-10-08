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
$R tc filter add dev veth-lan parent 1: protocol ip prio 1 u32 \
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
# prio 2, because a single priority cannot hold both the v4 and v6 filter
BEF=$($R tc -s class show dev veth-lan | awk '/class htb 1:10/{f=1} f&&/Sent/{print $2;exit}')
$R tc filter add dev veth-lan parent 1: protocol ipv6 prio 2 flower \
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
bmark () {  # bmark <src> <dst> <proto> <dport> <class> [timeout]
  # Preflight: the table must exist in the ROUTER namespace. `ns` defaults to
  # None, so omitting it runs nft in the host namespace where table `aciq` does
  # not exist, and nft answers "No such file or directory" pointing at the set
  # name -- which reads like a missing set in the bridge rather than a missing
  # namespace in this helper.
  ip netns exec router nft list table ip aciq >/dev/null 2>&1 \
    || die "bmark: no aciq table in the router namespace (is check 15 installed it?)"
  $VENV/bin/python - "$1" "$2" "$3" "$4" "$5" "${6:-120s}" <<'PY'
import sys
from aciq.bridge import FlowKey, family_of, generate_add_element
from aciq.marks import (CLASS_UNCLASSIFIED, CLASS_INTERACTIVE, CLASS_ADAPTIVE,
                        CLASS_BULK, CLASS_LEASED)
src, dst, proto, dport, cls, timeout = sys.argv[1:7]
ids = {"unclassified": CLASS_UNCLASSIFIED, "interactive": CLASS_INTERACTIVE,
       "adaptive": CLASS_ADAPTIVE, "bulk": CLASS_BULK, "leased": CLASS_LEASED}
key = FlowKey(src, dst, proto, int(dport))
# ns="router" is essential: without it the element is added in the host
# namespace and fails with "No such file or directory" on the set name.
argv = generate_add_element(family_of(src), key, ids[cls], timeout=timeout,
                            ns="router")
import subprocess
p = subprocess.run(list(argv), capture_output=True, text=True)
if p.returncode:
    sys.exit(f"nft add element failed rc={p.returncode}: {p.stderr.strip()}")
print("steered", src, dst, proto, dport, "->", cls, "(ns=router)")
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
send () {  # send <dst> <port> <size> <tos:hex|ef> [count]
  ip netns exec wan "$VENV/bin/python" - "$1" "$2" "$3" "$4" "${5:-40}" <<'PY'
import socket, sys, time
dst, port, size, tos, n = sys.argv[1:6]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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

send6 () {  # send6 <dst> <port> <size> [count]
  ip netns exec wan "$VENV/bin/python" - "$1" "$2" "$3" "${4:-40}" <<'PY'
import socket, sys, time
dst, port, size, n = sys.argv[1:5]
s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
for _ in range(int(n)):
    s.sendto(b"x" * int(size), (dst, int(port), 0, 0))
    time.sleep(0.002)
s.close()
PY
}

# ---------- 15 bridge installs ----------
export PYTHONPATH="$PWD/.."
$VENV/bin/python - <<'PY' || die "check 15: bridge setup failed"
import sys
sys.path.insert(0, "..")
from aciq.bridge import Bridge
Bridge(dev="veth-lan", in_if="veth-wan", ns="router").setup()
print("bridge setup ok")
PY
ip netns exec router nft list table ip aciq >/dev/null 2>&1 \
  || die "check 15: ip table aciq not created"
ip netns exec router nft list table ip6 aciq >/dev/null 2>&1 \
  || die "check 15: ip6 table aciq not created"
# Print the set definition and match on `timeout` rather than the literal
# "flags timeout". The previous assertion assumed nft prints that exact phrase in
# the listing, which is a claim about nftables' output format rather than about
# the bridge. The semantic requirement is that the set carries a timeout, so
# that is what is matched -- and the raw definition is echoed, so a failure
# reports what nft actually printed instead of only what was expected.
$R nft list set ip aciq interactive | tee /tmp/g15_set.txt
grep -q "timeout" /tmp/g15_set.txt \
  || die "check 15: interactive set carries no timeout (see /tmp/g15_set.txt)"
# Expiry itself is not assumed here -- check 19 proves the kernel ages an element
# out. This only proves the set was declared with the capability.
# Capture the filter list ONCE, report its exit status, and show it whatever
# the outcome. `cmd | grep -q` throws away both the exit status and the output,
# so "no flower filter installed" cannot be distinguished from "tc filter show
# errored" -- and this check has already failed for three unrelated reasons.
$R tc filter show dev "$EGR_IF" parent 1: > /tmp/g15_filters.txt 2>/tmp/g15_filters.err
F_RC=$?
echo "--- tc filter show rc=$F_RC, $(wc -l < /tmp/g15_filters.txt) lines ---"
cat /tmp/g15_filters.txt
[ -s /tmp/g15_filters.err ] && { echo "--- stderr ---"; cat /tmp/g15_filters.err; }
# The steer filters must key on the DSCP selector codes the rules stamp.
# Checking for `fw` here would have passed on the old design and fails now,
# which is the point: `tc fw` cannot read a packet mark on this toolchain.
[ "$F_RC" -eq 0 ] || die "check 15: 'tc filter show' failed rc=$F_RC (see /tmp/g15_filters.err)"
grep -q "flower" /tmp/g15_filters.txt \
  || die "check 15: no flower steer filter among $(wc -l < /tmp/g15_filters.txt) lines (see /tmp/g15_filters.txt)"
grep -q "ip_tos" /tmp/g15_filters.txt \
  || die "check 15: steer filters do not match on ip_tos (see /tmp/g15_filters.txt)"
ok "check 15: bridge installs (nft tables, timeout sets, flower steer filters)"

# Counter for one steering rule, read from the nft ruleset.
rulepkts () {  # rulepkts <setname>
  $R nft list ruleset | grep "@$1 " | head -1 \
    | sed -n 's/.*counter packets \([0-9]*\).*/\1/p'
}

# Watch the DSCP arriving at the CLIENT -- the last point before the wire.
#
# If the router's rewrite survives forwarding, the client sees 0x18. If the client
# sees 0x00, the DSCP was lost inside the router, which narrows the fault from
# "the writer" to "prerouting vs forwarding vs egress". Two tables rather than
# one with two rules, because identifying which counter belongs to which rule by
# rule order alone is exactly the kind of fragile parsing this gate has already
# been bitten by.
dscpwatch () {
  CN="ip netns exec client"
  $CN nft delete table ip dscp18 2>/dev/null
  $CN nft delete table ip dscp00 2>/dev/null
  $CN nft add table ip dscp18
  $CN nft add table ip dscp00
  $CN nft add chain ip dscp18 c '{ type filter hook prerouting priority mangle; policy accept; }'
  $CN nft add chain ip dscp00 c '{ type filter hook prerouting priority mangle; policy accept; }'
  $CN nft add rule ip dscp18 c ip dscp 0x18 counter
  $CN nft add rule ip dscp00 c ip dscp 0x00 counter
}
dscpwatch_read () {
  CN="ip netns exec client"
  echo "  arriving at client, DSCP 0x18 (steered):   $($CN nft list table ip dscp18 | sed -n 's/.*counter packets \([0-9]*\).*/\1/p')"
  echo "  arriving at client, DSCP 0x00 (untouched): $($CN nft list table ip dscp00 | sed -n 's/.*counter packets \([0-9]*\).*/\1/p')"
}

# ---------- 16a does flower ip_tos match IPv4 on EGRESS at all? ----------
# This sends a packet whose DSCP is ALREADY the adaptive selector code, so no
# nftables rule is involved. It isolates the tc reader from the nft writer.
#
# Why this must be tested separately: check 13 proved IPv4 DSCP-EF with u32, and
# check 14 proved flower ip_tos with IPv6. flower ip_tos on IPv4 EGRESS had never
# been exercised behaviourally -- only installed. Installing is not matching.
A20=$(cbytes 1:20); A30=$(cbytes 1:30)
send 10.0.1.2 7010 1000 18 60          # TOS 0x18 == CS3 == adaptive
sleep 1
B20=$(cbytes 1:20); B30=$(cbytes 1:30)
echo "16a (DSCP set by sender): 1:20 $A20 -> $B20   1:30 $A30 -> $B30"
awk -v a="$A20" -v b="$B20" 'BEGIN{exit !(b+0 > a+0 + 20000)}' \
  && ok "check 16a: flower ip_tos routes IPv4 DSCP 0x18 to 1:20 on egress" \
  || die "check 16a: flower ip_tos did NOT match IPv4 0x18 on egress (1:20 $A20 -> $B20).
A packet already carrying DSCP 0x18 was sent with no nftables rule involved.
If 1:20 did not grow, the tc READER cannot match IPv4 DSCP on egress, and the
steering mechanism must change rather than being debugged further."

# ---------- 16b the full nftables -> DSCP -> tc path ----------
A20=$(cbytes 1:20); A30=$(cbytes 1:30)
bmark 203.0.113.2 10.0.1.2 udp 7001 adaptive || die "check 16b: steering failed"
dscpwatch
send 10.0.1.2 7001 1000 0 60
sleep 1
dscpwatch_read
B20=$(cbytes 1:20); B30=$(cbytes 1:30)
PKT=$(rulepkts adaptive)
echo "16b (steered by nft): 1:20 $A20 -> $B20   1:30 $A30 -> $B30   rule matched $PKT pkt"
$R nft list set ip aciq adaptive | sed -n '1,8p'
echo "--- the rule as the kernel has it (does it set meta priority?) ---"
$R nft list ruleset | grep '@adaptive' | head -1
echo "--- PER-FILTER packet counters ---"
# Decisive and previously unused: if filter pref 12 shows 0 packets, flower did
# not match the DSCP. If it shows 60 and 1:20 is still flat, the flowid is not
# being applied -- a different fault with a different fix.
$R tc -s filter show dev "$EGR_IF" parent 1: | grep -E 'pref|ip_tos|packets'
echo "--- steer filters ---"
$R tc filter show dev "$EGR_IF" parent 1: | grep -E 'pref|ip_tos'
awk -v p="$PKT" 'BEGIN{exit !(p+0 > 0)}' \
  || die "check 16b: the nft rule matched nothing (counter=$PKT); the set lookup is broken"
awk -v a="$A20" -v b="$B20" 'BEGIN{exit !(b+0 > a+0 + 20000)}' \
  && ok "check 16b: steered IPv4 flow routed to 1:20 (rule matched $PKT pkt)" \
  || die "check 16b: rule matched $PKT pkt and set DSCP cs3, but 1:20 did not grow ($A20 -> $B20).
The nft WRITER ran (counter is non-zero) and the reader is proven by check 16a,
so the DSCP written in prerouting is not the DSCP seen on egress.

If the client-side watch above shows DSCP 0x18 arriving, the header rewrite
succeeded and the cause is that the rule did not also set meta priority:
'tc flower ip_tos' matches skb->priority, which the kernel fills from TOS on
ingress and which an 'ip dscp set' in prerouting does NOT update."

# ---------- 17 a flow marked unclassified loses EF priority ----------
# The evasion path: a flow that claims DSCP EF but is classified as bulk or
# unclassified must NOT reach 1:10.
#
# nftables prerouting rewrites the DSCP to the class selector code BEFORE tc sees
# the packet on egress, so by filter time the claim is gone and the steer filter
# for `unclassified` (CS1) routes it to 1:30. That holds regardless of prio
# ordering, because the rewrite has already happened.
C10=$(cbytes 1:10)
bmark 203.0.113.2 10.0.1.2 udp 7002 unclassified || die "check 17: steering failed"
send 10.0.1.2 7002 1000 ef 60    # DSCP EF claimed on the wire
sleep 1
D10=$(cbytes 1:10)
echo "EF-marked but classified unclassified: 1:10 $C10 -> $D10"
awk -v a="$C10" -v b="$D10" 'BEGIN{exit !(b+0 <= a+0 + 2000)}' \
  && ok "check 17: unclassified flow denied EF priority" \
  || die "check 17: EF-claimed unclassified flow still reached 1:10 ($C10 -> $D10)"

# ---------- 18 IPv6 mark routes to the marked class ----------
A20=$(cbytes 1:20)
# Source must be the wan namespace's IPv6 address. Check 13's conntrack line
# reads `src=fd00:2::2 dst=fd00:1::2 dport=7003`, and the nft set key is matched
# on (saddr, daddr, proto, dport) -- so the wrong source address yields an
# element that never matches, and the check fails while looking like a broken
# IPv6 steering path. The earlier value here was 2001:db8::2, taken from a
# documentation-range fixture rather than from the testbed's own addressing.
bmark fd00:2::2 fd00:1::2 udp 7003 adaptive || die "check 18: steering failed"
send6 fd00:1::2 7003 1000 60
sleep 1
B20=$(cbytes 1:20)
echo "ipv6 1:20 $A20 -> $B20"
awk -v a="$A20" -v b="$B20" 'BEGIN{exit !(b+0 > a+0 + 20000)}' \
  && ok "check 18: IPv6 mark routes udp/7003 to class 1:20" \
  || die "check 18: IPv6 1:20 did not grow ($A20 -> $B20)"

# ---------- 19 mark expiry ----------
# A short-lived element must age out in the kernel. This is the whole of mark
# expiry: no userspace sweeper, and a crashed ACIQ cannot leave stale marks
# alive because the kernel's timers keep running.
bmark 203.0.113.2 10.0.1.2 udp 7004 adaptive 3s || die "check 19: steering failed"
$R nft list set ip aciq adaptive | grep -q 7004 \
  || die "check 19: element absent immediately after add"
sleep 6
$R nft list set ip aciq adaptive | grep -q 7004 \
  && die "check 19: element still present after its 3s timeout" \
  || ok "check 19: mark expires via kernel set timeout"

# ---------- 20 teardown ----------
$VENV/bin/python - <<'PY' || die "check 20: bridge teardown failed"
import sys
sys.path.insert(0, "..")
from aciq.bridge import Bridge
Bridge(dev="veth-lan", in_if="veth-wan", ns="router").teardown()
PY
ip netns exec router nft list table ip aciq >/dev/null 2>&1 \
  && die "check 20: ip table aciq still present after teardown" \
  || ok "check 20: teardown removes the bridge tables"

summary
echo; echo "log saved to $LOG"
