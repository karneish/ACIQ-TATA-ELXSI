#!/usr/bin/env bash
# testbed/setup.sh — client <-> router <-> wan, IPv4 + IPv6, offloads off.
# Everything below runs inside a namespace. No host sysctl, link or tc change.
set -Eeuo pipefail
# Print the failing line instead of dying silently under `set -e`.
trap 'echo "SETUP FAILED at line $LINENO: $BASH_COMMAND" >&2' ERR
# Kernel modules must be loaded before use. `cake` in particular does not
# auto-load: the experiment driver never ran gate.sh's modprobe list, so B1
# failed with "Specified qdisc kind is unknown" while the same command had
# passed inside the gate.
echo "[setup] loading kernel modules"
for m in sch_htb sch_netem sch_cake sch_fq_codel sch_prio \
         act_gact act_police cls_flower cls_u32 nf_conntrack; do
  modprobe -q "$m" || echo "warn: could not load $m"
done

echo "[setup] creating namespaces"

for n in client wan router; do ip netns add "$n"; done

ip link add veth-lan type veth peer name veth-c
ip link add veth-wan type veth peer name veth-w
ip link set veth-lan netns router; ip link set veth-c netns client
ip link set veth-wan netns router; ip link set veth-w  netns wan

ip -n router addr add 10.0.1.1/24   dev veth-lan
ip -n router addr add 203.0.113.1/24 dev veth-wan
ip -n client addr add 10.0.1.2/24   dev veth-c
ip -n wan    addr add 203.0.113.2/24 dev veth-w
ip -n router addr add fd00:1::1/64  dev veth-lan nodad
ip -n router addr add fd00:2::1/64  dev veth-wan nodad
ip -n client addr add fd00:1::2/64  dev veth-c    nodad
ip -n wan    addr add fd00:2::2/64  dev veth-w    nodad

for p in "router veth-lan" "router veth-wan" "client veth-c" "wan veth-w"; do
  set -- $p
  ip -n "$1" link set "$2" up
  # a forwarding router emitting RAs on veth pairs causes neighbour churn
  ip netns exec "$1" sysctl -qw net.ipv6.conf.all.accept_ra=0
  ip netns exec "$1" sysctl -qw net.ipv6.conf.default.accept_ra=0
  ip netns exec "$1" sysctl -qw net.ipv6.conf.lo.accept_ra=0
  ip netns exec "$1" ethtool -K "$2" gro off gso off tso off \
    || echo "warn: ethtool -K failed on $1/$2 (check 5 will judge this)"
done

ip netns exec client ip route add default via 10.0.1.1
ip netns exec wan    ip route add 10.0.1.0/24 via 203.0.113.1
ip netns exec client ip -6 route add fd00:2::/64 via fd00:1::1
ip netns exec wan    ip -6 route add fd00:1::/64 via fd00:2::1

ip netns exec router sysctl -qw net.ipv4.ip_forward=1
ip netns exec router sysctl -qw net.ipv6.conf.all.forwarding=1
for i in all veth-lan veth-wan; do
  ip netns exec router sysctl -qw "net.ipv4.conf.$i.rp_filter=0"
done

# nft rules FIRST: in a fresh netns the nf_conntrack sysctl may not exist until
# a rule pulls conntrack in. Accounting also only counts flows created after it is on.
# Use nft's native config-file syntax via a heredoc. The command-line form
#   nft add chain inet t fwd '{ type filter hook forward priority 0; }'
# is fragile across nft versions and quoting layers; the file form is unambiguous.
# The chain is named `traffic`, NOT `fwd`: `fwd` is a reserved nft keyword (the
# `fwd to <addr>` statement) and using it as a chain name is a syntax error.
echo "[setup] installing nft rule to activate conntrack accounting"
ip netns exec router nft -f - <<'NFT'
table inet t {
  chain traffic {
    type filter hook forward priority 0;
    ct state new counter
  }
}
NFT
ip netns exec router sysctl -qw net.netfilter.nf_conntrack_acct=1
echo "[setup] nf_conntrack_acct=$(ip netns exec router cat /proc/sys/net/netfilter/nf_conntrack_acct)"
echo "[setup] done"
