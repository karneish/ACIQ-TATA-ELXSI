#!/usr/bin/env python3
"""Control-plane cost benchmark.

Answers §15 with measurements taken on the host it runs on, and prints the
environment those measurements are valid for. There are no `tc` calls here and
no root: this measures the controller's own arithmetic, not kernel behaviour.
Kernel-side cost is a separate question and is reported as blocked in
`docs/gap-closure/performance-and-scalability.md`.

    python3 tools/bench.py [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aciq.classify import TrustStore, classify        # noqa: E402
from aciq.flowtrack import Flow, FlowFeatures, parse_conntrack_line  # noqa: E402
from aciq.intent import Lease                          # noqa: E402
from aciq.policy import build_plan                     # noqa: E402
from aciq.tc import build_tree, render                 # noqa: E402

CT_LINE = ("tcp 6 431999 ESTABLISHED src=203.0.113.4 dst=10.0.1.2 sport=51570 "
           "dport=443 src=10.0.1.2 dst=203.0.113.4 sport=443 dport=51570 "
           "[ASSURED] mark=0 use=1")


def _bench(fn, n=500):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return {"mean_us": round(statistics.mean(ts) * 1e6, 2),
            "p99_us": round(sorted(ts)[int(0.99 * len(ts)) - 1] * 1e6, 2),
            "max_us": round(max(ts) * 1e6, 2),
            "n": n}


def _rss_mb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)


def run() -> dict:
    lease = Lease(id="l1", target="device", ip="203.0.113.4", weight=0.6)
    tree = build_tree(build_plan(100.0, lease))
    ff = FlowFeatures(Flow("203.0.113.4", 5004, "10.0.1.2", 5005, "udp"),
                      dscp=46, rx_bytes=120_000, tx_bytes=120_000, packets=400,
                      age_s=5.0, avg_packet_bytes=300, burstiness=0.2,
                      duty_cycle=0.5)

    out = {
        "environment": {
            "kernel": platform.release(),
            "python": platform.python_version(),
            "machine": platform.machine(),
            "rss_mb_at_start": _rss_mb(),
            "note": "controller arithmetic only; no tc, no namespaces, no root",
        },
        "policy_planning": {
            "build_plan_no_lease": _bench(lambda: build_plan(100.0, None)),
            "build_plan_with_lease": _bench(lambda: build_plan(10.0, lease)),
        },
        "kernel_application": {
            "build_tree_and_render": _bench(
                lambda: render(build_tree(build_plan(100.0, lease)), dev="veth-lan", ns="router")),
            "tc_commands_per_apply": len(
                render(tree, dev="veth-lan", ns="router")),
            "note": "rendering only. Issuing the commands, and the kernel's "
                    "cost in doing so, are not measured here.",
        },
        "observation": {
            "parse_conntrack_line": _bench(
                lambda: parse_conntrack_line(CT_LINE), n=2000),
        },
        "classification": {
            "classify_one_flow": _bench(
                lambda: classify(ff, 10.0, TrustStore()), n=2000),
        },
    }

    per = out["classification"]["classify_one_flow"]["mean_us"] / 1e6
    out["classification"]["flows_per_1hz_tick"] = {
        str(n): round(n * per * 1e3, 3) for n in (10, 50, 100, 500)}
    out["environment"]["rss_mb_at_end"] = _rss_mb()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the result as JSON here")
    a = ap.parse_args()
    r = run()

    print("ACIQ control-plane cost")
    print(f"  kernel {r['environment']['kernel']}  "
          f"python {r['environment']['python']}  "
          f"rss {r['environment']['rss_mb_at_end']} MB")
    print()
    for section in ("policy_planning", "kernel_application", "observation",
                    "classification"):
        print(f"  {section}")
        for k, v in r[section].items():
            if isinstance(v, dict) and "mean_us" in v:
                print(f"    {k:<34} mean {v['mean_us']:8.2f} us  "
                      f"p99 {v['p99_us']:8.2f} us  max {v['max_us']:8.2f} us")
            elif k != "note":
                print(f"    {k:<34} {v}")
        if "note" in r[section]:
            print(f"    ({r[section]['note']})")
        print()
    print("  classifier cost per 1 Hz tick by flow count:")
    for n, ms in r["classification"]["flows_per_1hz_tick"].items():
        print(f"    {n:>4} flows -> {ms:8.3f} ms")
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=2) + "\n")
        print(f"\n  wrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())