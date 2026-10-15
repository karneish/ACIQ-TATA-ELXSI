#!/usr/bin/env python3
"""call.py — a synthetic voice/video call.

Small UDP packets roughly every 20 ms, which is what makes a call
latency-sensitive rather than merely small. Measures its OWN RTT, jitter and
loss from its own packets, so latency is never inferred from ICMP alone.

  # terminal 1 (the sink)
  sudo ip netns exec client python3 call.py --listen --port 5001

  # terminal 2 (the caller)
  sudo ip netns exec wan python3 call.py --dst 10.0.1.2 --port 5001 --duration 30
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from udpx import EchoSink, UdpProbe  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="ACIQ call generator")
    ap.add_argument("--listen", action="store_true", help="run as the echo sink")
    ap.add_argument("--dst", default="10.0.1.2")
    ap.add_argument("--port", type=int, default=5001)
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--pps", type=float, default=50.0, help="packets/sec (50 = one per 20ms)")
    ap.add_argument("--bytes", type=int, default=256)
    ap.add_argument("--dscp", type=int, default=None, help="e.g. 46 for EF")
    ap.add_argument("-6", "--ipv6", action="store_true")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--partial-out", default=None,
                    help="write the summary-so-far here, repeatedly, so the "
                         "driver can ingest latency DURING the run instead of "
                         "only at exit")
    args = ap.parse_args()

    family = socket.AF_INET6 if args.ipv6 else socket.AF_INET

    if args.listen:
        sink = EchoSink(args.port, family=family).start()
        print(f"call sink listening on :{args.port} ({family.name})", flush=True)
        try:
            while True:
                time.sleep(1)
                print(f"  sink rx={sink.packets} bytes={sink.bytes}", flush=True)
        except KeyboardInterrupt:
            sink.stop()
        return 0

    probe = UdpProbe(
        dst=args.dst, port=args.port, pps=args.pps,
        payload_bytes=args.bytes, family=family, label="call",
        partial_path=args.partial_out,
    )
    print(
        f"call -> {args.dst}:{args.port} for {args.duration}s "
        f"at {args.pps}pps ({args.bytes}B)",
        flush=True,
    )
    rep = probe.run(args.duration, dscp=args.dscp)
    probe.close()
    print(json.dumps(rep, indent=2), flush=True)
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(rep, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
