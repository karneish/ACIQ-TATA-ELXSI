#!/usr/bin/env bash
# testbed/cleanup.sh — idempotent. Removes namespaces; veths and tc go with them.
# NOTE: pkill -x iperf3 also kills any iperf3 you started yourself. Intended for a test laptop.
pkill -x iperf3 2>/dev/null
for ns in client wan router ct; do ip netns del "$ns" 2>/dev/null; done
for d in veth-lan veth-wan; do ip link del "$d" 2>/dev/null; done
exit 0
