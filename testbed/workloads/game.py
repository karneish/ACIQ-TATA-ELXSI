#!/usr/bin/env python3
"""game.py — a synthetic real-time game session.

Low rate and low payload, but far more latency-sensitive than video and much
less tolerant of jitter than a bulk transfer. A game differs from a call mainly
in cadence and jitter budget, so that is what changes here.

  sudo ip netns exec client python3 game.py --listen --port 5002
  sudo ip netns exec wan    python3 game.py --dst 10.0.1.2 --port 5002 --duration 30
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from udpx import EchoSink, UdpProbe  # noqa: E402

#: A game sends input/position updates, not a steady media stream.
GAME_PPS = 30.0
GAME_BYTES = 128


def main() -> int:
    ap = argparse.ArgumentParser(description="ACIQ game generator")
    ap.add_argument("--listen", action="store_true")
    ap.add_argument("--dst", default="10.0.1.2")
    ap.add_argument("--port", type=int, default=5002)
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--pps", type=float, default=GAME_PPS)
    ap.add_argument("--bytes", type=int, default=GAME_BYTES)
    ap.add_argument("--dscp", type=int, default=None)
    ap.add_argument("-6", "--ipv6", action="store_true")
    ap.add_argument("--src", default=None,
                    help="source address to bind, so this workload is a "
                         "distinct device for lease matching")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    family = socket.AF_INET6 if args.ipv6 else socket.AF_INET

    if args.listen:
        sink = EchoSink(args.port, family=family).start()
        print(f"game sink listening on :{args.port}", flush=True)
        try:
            while True:
                time.sleep(1)
                print(f"  sink rx={sink.packets} bytes={sink.bytes}", flush=True)
        except KeyboardInterrupt:
            sink.stop()
        return 0

    probe = UdpProbe(
        dst=args.dst, port=args.port, pps=args.pps,
        payload_bytes=args.bytes, family=family, label="game", src=args.src,
    )
    print(f"game -> {args.dst}:{args.port} for {args.duration}s at {args.pps}pps", flush=True)
    rep = probe.run(args.duration, dscp=args.dscp)
    probe.close()
    print(json.dumps(rep, indent=2), flush=True)
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(rep, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
