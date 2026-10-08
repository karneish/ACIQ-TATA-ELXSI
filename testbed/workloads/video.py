#!/usr/bin/env python3
"""video.py — a synthetic adaptive-bitrate TV stream.

TCP, because that is what real video delivery uses. Bitrate is stepped over
time so the flow behaves like ABR rather than one constant-rate transfer. The
sender reports what it sent; what actually arrived is read from the ``tc`` class
counters, since the sink lives in another namespace.

  # ABR ladder runs in the wan netns; the sink receives in the client netns.
  # The sender reports what it sent. Receiver throughput is measured from the
  # tc class counters, because the sender cannot see what arrived.
  sudo ip netns exec client python3 video.py --listen --port 5003
  sudo ip netns exec wan    python3 video.py --dst 10.0.1.2 --port 5003 --duration 30
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time

#: Bitrate ladder in Mbps, stepped every --step seconds. Mirrors an ABR client
#: moving between quality levels as conditions change.
LADDER = (8.0, 5.0, 3.0, 1.5)
STEP_S = 6.0
CHUNK = 64 * 1024


def sink(port: int, out: dict, stop: threading.Event | None = None) -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(4)
    srv.settimeout(0.5)
    out["started"] = time.monotonic()
    while not (stop is not None and stop.is_set()):
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        received = 0
        t0 = time.monotonic()
        while True:
            try:
                b = conn.recv(262144)
            except OSError:
                break
            if not b:
                break
            received += len(b)
        conn.close()
        dt = max(time.monotonic() - t0, 1e-9)
        out["bytes"] = out.get("bytes", 0) + received
        out["mbps"] = (out["bytes"] * 8) / dt / 1e6
        print(f"  [video sink] {received} bytes  {out['mbps']:.2f} Mbps", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="ACIQ adaptive video generator")
    ap.add_argument("--listen", action="store_true",
                    help="run as the receiving sink (in the client namespace)")
    ap.add_argument("--dst", default="10.0.1.2")
    ap.add_argument("--port", type=int, default=5003)
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--dscp", type=int, default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    if args.listen:
        print(f"video sink listening on :{args.port}", flush=True)
        sink(args.port, {"bytes": 0})
        return 0

    # Retry: the sink runs as a separate process and may not have bound yet.
    # A single failed connect would silently drop the whole workload, which
    # looks exactly like "the bulk transfer had no effect on the link".
    s = None
    last = None
    for _ in range(20):
        try:
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

    print(f"video -> {args.dst}:{args.port} for {args.duration}s (ABR ladder)", flush=True)
    t0 = time.monotonic()
    end = t0 + args.duration
    step_end = time.monotonic() + STEP_S
    level = 0
    sent = 0
    deadline_chunk = end

    while time.monotonic() < end:
        now = time.monotonic()
        if now >= step_end:
            level = (level + 1) % len(LADDER)
            step_end = now + STEP_S
            print(f"  [abr] step -> {LADDER[level]} Mbps", flush=True)
        mbps = LADDER[level]
        bytes_this_step = (mbps * 1e6 / 8) * 0.02  # 20 ms of video
        try:
            s.sendall(b"\x00" * int(bytes_this_step))
            sent += int(bytes_this_step)
        except OSError as e:
            print(f"  [video] send error: {e}", flush=True)
            break
        time.sleep(0.02)

    s.close()
    elapsed = max(time.monotonic() - t0, 1e-9)
    # Sender-side facts only; the sink is in another namespace and receiver
    # throughput comes from the tc class counters.
    rep = {
        "label": "video",
        "sent_bytes": sent,
        "elapsed_s": round(elapsed, 3),
        "sender_mbps": round((sent * 8) / elapsed / 1e6, 2),
        "ladder": list(LADDER),
        "step_s": STEP_S,
        "note": "received_bytes/mbps come from tc class counters, not from here",
    }
    print(json.dumps(rep, indent=2), flush=True)
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(rep, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
