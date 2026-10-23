#!/usr/bin/env python3
"""Selftest for the workload generators.

Runs over loopback with no root, no namespaces and no shaping. It proves the
generators work and that their self-measurement is sane BEFORE they are used to
judge anything about the network.

    python3 testbed/workloads/selftest.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from udpx import EchoSink, UdpProbe, jain_fairness  # noqa: E402

FAILED = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "ok  " if cond else "FAIL"
    print(f"[{status}] {name}{('  ' + detail) if detail else ''}")
    if not cond:
        FAILED.append(name)


def main() -> int:
    print("=== udpx round trip over loopback ===")
    sink = EchoSink(5099, host="127.0.0.1").start()
    time.sleep(0.2)
    p = UdpProbe(dst="127.0.0.1", port=5099, pps=50.0, payload_bytes=256, label="test")
    rep = p.run(3.0)
    p.close()
    sink.stop()

    print(json.dumps(rep, indent=2))
    # 3s at 50pps => ~150. Assert the cadence actually held, not just >0:
    # a loop that falls behind silently under-sends and looks like low loss.
    check("cadence held (>=140 sent in 3s at 50pps)", rep["sent"] >= 140, f"sent={rep['sent']}")
    check("achieved rate ~= requested",
          abs(rep["pps_achieved"] - rep["pps_requested"]) < 2.0,
          f"{rep['pps_achieved']}/{rep['pps_requested']} pps")
    check("replies received", rep["received"] >= 140, f"received={rep['received']}")
    check("low loss on loopback", rep["loss_ratio"] < 0.10, f"loss={rep['loss_ratio']}")
    check("sub-ms RTT on loopback", rep["p50"] < 1.0, f"p50={rep['p50']}ms")
    check("p95 >= p50", rep["p95"] >= rep["p50"])
    check("percentiles ordered", rep["p50"] <= rep["p95"] <= rep["p99"])

    print("\n=== empty payload still parses ===")
    from udpx import build, parse
    rt = parse(build(42, 123456789))
    check("round trip through build/parse", rt == (42, 123456789), str(rt))

    print("\n=== junk is rejected, not misparsed ===")
    check("junk returns None", parse(b"not-aciq-traffic-here") is None)
    check("truncated returns None", parse(b"ACIQ\x00") is None)

    print("\n=== Jain fairness index ===")
    check("perfect fairness == 1.0", abs(jain_fairness([10, 10, 10]) - 1.0) < 1e-9)
    # Jain for [100,1,1] = 10404/(3*10002) ~= 0.3467 -- low, not near zero.
    # A one-hog case is still "unfair" but the index is bounded by 1/3, so the
    # threshold must reflect that rather than a guess.
    check("one hog is unfair", 0.3 < jain_fairness([100, 1, 1]) < 0.4,
          f"{jain_fairness([100, 1, 1]):.4f}")
    check("two hogs fairer than one", jain_fairness([10, 10, 1]) > jain_fairness([100, 1, 1]))
    check("empty is 0.0", jain_fairness([]) == 0.0)
    check("symmetric", abs(jain_fairness([1, 2, 3]) - jain_fairness([3, 2, 1])) < 1e-12)

    print("\n=== generators import and expose --help ===")
    import subprocess
    for g in ("call.py", "game.py", "video.py", "bulk.py"):
        r = subprocess.run([sys.executable, str(Path(__file__).parent / g), "--help"],
                           capture_output=True, text=True, timeout=20)
        check(f"{g} --help", r.returncode == 0 and "usage" in r.stdout.lower())

    print()
    if FAILED:
        print(f"FAILED {len(FAILED)}: {FAILED}")
        return 1
    print("all generator selftests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
