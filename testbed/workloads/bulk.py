#!/usr/bin/env python3
"""bulk.py — a synthetic bulk transfer (the ISO download / update / backup case).

TCP, deliberately saturating. This is the traffic the QoS policy is supposed to
hold back without ever stopping it, so it must be genuinely greedy: if it does
not fill the link, the shaping tests prove nothing.

  # sink runs in the client netns, sender in the wan netns
  sudo ip netns exec client python3 bulk.py --listen --port 5004
  sudo ip netns exec wan    python3 bulk.py --dst 10.0.1.2 --port 5004 --duration 20
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time

BLOCK = 256 * 1024


def sink(port: int, out: dict, stop: threading.Event | None = None) -> None:
    """Listen in whatever namespace this process runs in.

    Deliberately a separate --listen mode: binding and connecting inside one
    process only works on a single host, and these workloads have to run on
    opposite sides of a router namespace.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(4)
    srv.settimeout(0.5)
    while not (stop is not None and stop.is_set()):
        try:
            conn, _ = srv.accept()
        except TimeoutError:
            continue
        except OSError:
            break
        received = 0
        t0 = time.monotonic()
        while True:
            try:
                b = conn.recv(1 << 20)
            except OSError:
                break
            if not b:
                break
            received += len(b)
        conn.close()
        dt = max(time.monotonic() - t0, 1e-9)
        out["bytes"] = out.get("bytes", 0) + received
        out["mbps"] = (out["bytes"] * 8) / dt / 1e6
        print(f"  [bulk sink] {out['bytes']} bytes  {out['mbps']:.2f} Mbps", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="ACIQ bulk transfer generator")
    ap.add_argument("--listen", action="store_true",
                    help="run as the receiving sink (in the client namespace)")
    ap.add_argument("--dst", default="10.0.1.2")
    ap.add_argument("--port", type=int, default=5004)
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--dscp", type=int, default=None)
    ap.add_argument("--label", default="bulk")
    ap.add_argument("--src", default=None,
                    help="source address to bind, so this workload is a "
                         "distinct device for lease matching")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    if args.listen:
        print(f"bulk sink listening on :{args.port}", flush=True)
        sink(args.port, {})
        return 0

    # Retry: the sink runs as a separate process and may not have bound yet.
    # A single failed connect would silently drop the whole workload, which
    # looks exactly like "the bulk transfer had no effect on the link".
    s = None
    last = None
    for _ in range(20):
        try:
            # See udpx.UdpProbe: binding a source is what makes this workload
            # a distinct device rather than another flow from the one address
            # the wan namespace holds.
            if args.src:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                s.bind((args.src, 0))
                s.connect((args.dst, args.port))
            else:
                s = socket.create_connection((args.dst, args.port), timeout=2)
            break
        except OSError as e:
            last = e
            time.sleep(0.25)
    if s is None:
        print(f"error: cannot connect to {args.dst}:{args.port} after retries: {last}",
              file=sys.stderr)
        return 1

    if args.dscp is not None:
        try:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, args.dscp << 2)
        except OSError:
            pass

    print(f"{args.label} -> {args.dst}:{args.port} for {args.duration}s (saturating)", flush=True)
    t0 = time.monotonic()
    end = t0 + args.duration
    sent = 0
    payload = b"\x00" * BLOCK
    try:
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass

    while time.monotonic() < end:
        try:
            s.sendall(payload)
            sent += BLOCK
        except OSError as e:
            print(f"  [{args.label}] send error: {e}", flush=True)
            break

    s.close()
    elapsed = max(time.monotonic() - t0, 1e-9)
    # Sender-side facts only. The sink runs in another namespace, so this
    # process cannot observe what was actually received — and should not.
    # Receiver-side throughput is measured from the tc class counters instead.
    rep = {
        "label": args.label,
        "sent_bytes": sent,
        "elapsed_s": round(elapsed, 3),
        "sender_mbps": round((sent * 8) / elapsed / 1e6, 2),
        "note": "received_bytes/mbps come from tc class counters, not from here",
    }
    print(json.dumps(rep, indent=2), flush=True)
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(rep, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
