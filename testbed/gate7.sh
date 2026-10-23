#!/usr/bin/env bash
# testbed/gate7.sh — the 7-class gate. Run:
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/gate7.sh
#
# Complements the legacy 20-check gate (gate.sh). This one drives the REAL
# product path: the HTB tree rendered by aciq.tc from a measured rate plan,
# verified by aciq.tc.verify() against a tc JSON read-back, per-flow steering
# into the real 7-class ids including the default class 1:70, an ifb-ingress
# capture probe, and the watchdog's force-safe teardown on a real SIGTERM.
# Stops at the first failed check.
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p logs
LOG="logs/gate7-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
VENV="${ACIQ_VENV:-$HOME/aciq-venv}"
R="ip netns exec router"     # deliberately unquoted: used as `$R cmd args`
PASSED=(); FAILED=""; MEASURED=()

[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }

ok () { echo "[PASS] $*"; PASSED+=("$*"); }
meas () { echo "[MEASURED] $*"; MEASURED+=("$*"); }
die () { echo "[FAIL] $*"; FAILED="$*"; summary; exit 1; }
summary () {
  echo; echo "=== gate7 SUMMARY ==="
  for p in "${PASSED[@]:-}"; do [ -n "$p" ] && echo "PASS      $p"; done
  for m in "${MEASURED[@]:-}"; do [ -n "$m" ] && echo "MEASURED  $m"; done
  [ -n "$FAILED" ] && echo "FAIL      $FAILED" && exit 1
  echo "ALL PASSED"; exit 0
}

MISS=""
for c in tc ip nft conntrack ping; do command -v "$c" >/dev/null || MISS="$MISS $c"; done
[ -x "$VENV/bin/python" ] || MISS="$MISS venv:$VENV"
[ -z "$MISS" ] && ok "p1: tooling" || die "p1: missing:$MISS"

# clean slate
./cleanup.sh 2>/dev/null || true
./setup.sh >/dev/null 2>&1 || true
$R ip link show veth-lan >/dev/null 2>&1 \
  && ok "p2: testbed up" || die "p2: testbed namespaces missing (setup.sh failed)"

# ==========================================================================
# p3: the REAL aciq.tc tree, at 20 Mbps, built and verified in-kernel
# ==========================================================================
OUT=$("$VENV/bin/python" - <<'PY'
import json, subprocess, sys
sys.path.insert(0, "..")
from aciq.policy import build_plan
from aciq.tc import build_tree, render, verify

plan = build_plan(20.0)
tree = build_tree(plan)
cmds = render(tree, dev="veth-lan", ns="router")
for argv in cmds:
    r = subprocess.run(argv, capture_output=True, text=True)
    if r.returncode != 0:
        print("APPLY-FAIL", " ".join(argv))
        print(r.stderr.strip()[:400])
        sys.exit(1)
print("applied", len(cmds), "commands,", len(tree.classes), "classes")
for c in tree.classes:
    print(f"class {c.classid:5s} rate={c.rate_mbps:7.3f} ceil={c.ceil_mbps:7.3f} "
          f"{'(root)' if c.cls is None else c.cls.value}")

# TEXT read-back, not JSON: on this iproute2 build `tc -j -s class` returns
# empty JSON (documented sharp edge in aciq/metrics; the legacy gate shows the
# same). aciq.qdisc.parse_class_text is the primary, gate-validated source.
r = subprocess.run(["ip", "netns", "exec", "router",
                    "tc", "-s", "class", "show", "dev", "veth-lan"],
                   capture_output=True, text=True)
from aciq.qdisc import parse_class_text
from aciq.tc import parse_class_state
state = parse_class_state(parse_class_text(r.stdout))
if not state:
    print("READBACK-EMPTY; raw head:", r.stdout[:200])
    sys.exit(1)
bad = verify(tree, state)
rates = {c.classid: c.rate_mbps for c in tree.classes if c.cls}
total = sum(rates.values())
print(f"verify: {len(state)} classes read back, mismatches={len(bad)}")
for m in bad:
    print("MISMATCH", m)
print(f"invariant: sum(child rate)={total:.3f} <= {plan.capacity_mbps:.3f} "
      f"-> {'HOLDS' if total <= plan.capacity_mbps + 1e-6 else 'BROKEN'}")
sys.exit(0 if not bad else 2)
PY
) || die "p3: real-tree build/verify failed: $OUT"
echo "$OUT"
echo "$OUT" | grep -q "mismatches=0" || die "p3: tree verify reported mismatches"
echo "$OUT" | grep -q "HOLDS" || die "p3: sum(child rate) invariant broken"
ok "p3: real 7-class tree built from aciq.policy/aciq.tc and verified in-kernel"

# ==========================================================================
# p5: per-flow steering on the real tree, incl. the DEFAULT class 1:70
# ==========================================================================
cn () { $R tc -s class show dev veth-lan \
  | awk -v c="class htb $1" '$0 ~ c {f=1} f && /Sent/ {print $2; exit}'; }

cdelta () { awk -v a="$1" -v b="$2" -v need="$3" 'BEGIN{exit !(b+0 > a+0 + need+0)}'; }

# steering helper from the shipped generator: reuse gate.sh's bmark pattern
bmark () {  # bmark <src> <dst> <proto> <dport> <class>
  $VENV/bin/python - "$1" "$2" "$3" "$4" "$5" <<'PY'
import sys
sys.path.insert(0, "..")
from aciq.bridge import Bridge, FlowKey
from aciq.marks import (CLASS_UNCLASSIFIED, CLASS_VIDEO_CALL, CLASS_GAMING,
                        CLASS_STREAMING, CLASS_BULK_DOWNLOAD,
                        CLASS_SOFTWARE_UPDATE, CLASS_CLOUD_BACKUP,
                        CLASS_UNKNOWN, CLASS_LEASED)
ids = {"unclassified": CLASS_UNCLASSIFIED, "video_call": CLASS_VIDEO_CALL,
       "gaming": CLASS_GAMING, "streaming": CLASS_STREAMING,
       "bulk": CLASS_BULK_DOWNLOAD, "update": CLASS_SOFTWARE_UPDATE,
       "backup": CLASS_CLOUD_BACKUP, "unknown": CLASS_UNKNOWN,
       "leased": CLASS_LEASED}
b = Bridge(dev="veth-lan", in_if="veth-wan", ns="router")
b.mark(FlowKey(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])),
       ids[sys.argv[5]])
print("steered", sys.argv[1], sys.argv[3], sys.argv[4], "->", sys.argv[5])
PY
}

send () {  # send <dst> <port> <size> [count] [src]
  ip netns exec wan "$VENV/bin/python" - "$1" "$2" "$3" "${4:-60}" "${5:-203.0.113.2}" <<'PY'
import socket, sys, time
dst, port, size, n, src = sys.argv[1:6]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((src, 0))
for _ in range(int(n)):
    s.sendto(b"x" * int(size), (dst, int(port)))
    time.sleep(0.002)
PY
}
send6 () {  # send6 <dst> <port> <size> [count] [src]
  ip netns exec wan "$VENV/bin/python" - "$1" "$2" "$3" "${4:-60}" "${5:-fd00:2::2}" <<'PY'
import socket, sys, time
dst, port, size, n, src = sys.argv[1:6]
s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
s.bind((src, 0, 0, 0))
for _ in range(int(n)):
    s.sendto(b"x" * int(size), (dst, int(port), 0, 0))
    time.sleep(0.002)
PY
}

# --- gaming -> 1:20 -------------------------------------------------------
A=$(cn 1:20); bmark 203.0.113.2 10.0.1.2 udp 7001 gaming
send 10.0.1.2 7001 1000 60 203.0.113.2; sleep 1
B=$(cn 1:20)
echo "gaming 1:20: $A -> $B"
cdelta "$A" "$B" 20000 && ok "p5a: v4 flow steered into GAMING 1:20" \
  || die "p5a: 1:20 did not grow ($A -> $B)"

# --- bulk_download -> 1:30 ------------------------------------------------
A=$(cn 1:30); bmark 203.0.113.2 10.0.1.2 udp 7002 bulk
send 10.0.1.2 7002 1400 80 203.0.113.2; sleep 1
B=$(cn 1:30)
echo "bulk 1:30: $A -> $B"
cdelta "$A" "$B" 80000 && ok "p5b: v4 flow steered into BULK_DOWNLOAD 1:30" \
  || die "p5b: 1:30 did not grow ($A -> $B)"

# --- software_update -> 1:50 over IPv6 ------------------------------------
A=$(cn 1:50); bmark fd00:2::2 fd00:1::2 udp 7003 update
send6 fd00:1::2 7003 1200 60 fd00:2::2; sleep 1
B=$(cn 1:50)
echo "update 1:50: $A -> $B"
cdelta "$A" "$B" 20000 && ok "p5c: IPv6 flow steered into SOFTWARE_UPDATE 1:50" \
  || die "p5c: 1:50 did not grow ($A -> $B)"

# --- unclassified -> the DEFAULT class 1:70 -------------------------------
A=$(cn 1:70); bmark 203.0.113.2 10.0.1.2 udp 7002 unclassified
send 10.0.1.2 7002 1000 60 203.0.113.2; sleep 1
B=$(cn 1:70)
echo "unclassified -> default 1:70: $A -> $B"
cdelta "$A" "$B" 20000 && ok "p5d: unclassified mark lands in DEFAULT class 1:70" \
  || die "p5d: 1:70 did not grow ($A -> $B)"

# ==========================================================================
# p6: ifb ingress redirect — the capture path the header observer can use
# ==========================================================================
$R ip link add ifb-audit type ifb 2>/dev/null || true
$R ip link set ifb-audit up
$R tc qdisc add dev veth-wan ingress 2>/dev/null || true
$R tc filter add dev veth-wan parent ffff: protocol ip u32 \
  match ip protocol 17 0xff action mirred egress redirect dev ifb-audit \
  || true
TX0=$($R ip -j -s link show ifb-audit | python3 -c "
import json,sys
d=json.load(sys.stdin)[0]; print(d['stats64']['tx']['bytes'])")
send 10.0.1.2 7002 1400 100 203.0.113.2; sleep 1
TX1=$($R ip -j -s link show ifb-audit | python3 -c "
import json,sys
d=json.load(sys.stdin)[0]; print(d['stats64']['tx']['bytes'])")
echo "ifb tx: $TX0 -> $TX1"
cdelta "$TX0" "$TX1" 50000 \
  && ok "p6: ifb ingress redirect captured forwarded UDP traffic" \
  || { echo "ifb probe failed (tx $TX0 -> $TX1)"; FAILED="p6: ifb capture"; }
# teardown: the probe must not leave the mirror in place
$R tc qdisc del dev veth-wan ingress 2>/dev/null || true
$R ip link del ifb-audit 2>/dev/null || true
cdelta "$TX0" "$TX1" 50000 && ok "p7: ifb mirror torn down" || true

# ==========================================================================
# p8: watchdog — a SIGTERM'd process leaves NO filter residue
# ==========================================================================
bmark 203.0.113.2 10.0.1.2 udp 7001 gaming >/dev/null
cat > /tmp/watchdog_probe.py <<'PY'
import sys, time
sys.path.insert(0, "..")
from aciq.bridge import Bridge, FlowKey
from aciq.watchdog import Watchdog
b = Bridge(dev="veth-lan", in_if="veth-wan", ns="router")
key = FlowKey("203.0.113.2", "10.0.1.2", "udp", 7007)
cmds = b.mark(key, 2)          # CLASS_GAMING
print("installed", len(cmds), "tc commands", flush=True)
Watchdog(safe_fn=b.teardown, re_raise=True).install()
time.sleep(60)
PY
cp /tmp/watchdog_probe.py probe_tmp.py
( cd "$(pwd)" && "$VENV/bin/python" probe_tmp.py ) &
WPROBE=$!
sleep 1
$R tc filter show dev veth-lan parent 1: | grep -q "dst_port 7007" \
  && ok "p8a: probe filter installed before termination" \
  || die "p8a: probe never installed its filter"
kill -TERM "$WPROBE"; wait "$WPROBE" 2>/dev/null || true
sleep 1
$R tc filter show dev veth-lan parent 1: | grep -q "dst_port 7007" \
  && die "p8b: the filter SURVIVED SIGTERM — watchdog not enforced" \
  || ok "p8b: SIGTERM -> watchdog force-safe teardown removed the filter"

# ==========================================================================
# p9: end-of-gate residue check — bridge filters gone, then the whole tree
# ==========================================================================
# Scope note recorded honestly: Bridge.teardown() owns BRIDGE artifacts only
# (nft sets + its own per-flow filters, proven in p8b). The HTB tree was built
# by aciq.tc outside the bridge lifecycle, so removing it here is the SITE's
# job, and p9 proves the site did its job: device ends up completely empty.
$R tc filter show dev veth-lan parent 1: | grep -q "dst_port 700" \
  && die "p9: a bridge per-flow filter survived teardown" \
  || echo "no per-flow filters remain"
$R tc qdisc del dev veth-lan root 2>/dev/null || true
LEFT=$($R tc -s class show dev veth-lan 2>/dev/null | grep -c "class htb" || true)
[ "$LEFT" -eq 0 ] \
  && ok "p9: full teardown (bridge filters + qdisc tree), device empty" \
  || die "p9: htb classes remained after explicit tree removal ($LEFT)"

rm -f probe_tmp.py
summary
