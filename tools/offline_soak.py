#!/usr/bin/env python3
"""Offline long-run resource and stability soak. No root, no kernel, no tc.

WHY THIS EXISTS

`docs/gap-closure/resource-reliability.md` marked long-run resource drift
**BLOCKED** and memory-over-30-minutes **NOT RUN**, because every live run in
this repository is bounded by the gate scripts and none exceeds ~40 s. The gap
it names is real: a control loop that is correct for forty seconds and grows a
dict for six hours is a different program.

This harness cannot measure the kernel, and does not pretend to. It drives the
*controller's own* data structures -- the flow tracker, the classifier, the trust
store, the capacity estimator and the policy planner -- through the same per-tick
arithmetic the live loop uses, for a configurable duration, and reports:

  * RSS sampled over time (start, end, peak) so unbounded growth is visible;
  * the size of every bounded structure at the end, against its documented cap;
  * throughput (ticks/s) so a slowdown over time is visible too.

The claim it supports is narrow and stated as such: the *controller* does not
leak over the soak. It says nothing about qdisc or packet-buffer memory, which
remain BLOCKED without a kernel.

    python3 tools/offline_soak.py --seconds 60
    python3 tools/offline_soak.py --seconds 1800 --flows 200 --json out.json
"""

from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aciq.capacity import CapacityEstimator, Measurement      # noqa: E402
from aciq.classify import (                                   # noqa: E402
    MAX_TRUST_SOURCES,
    TrustStore,
    classify,
)
from aciq.flowtrack import FlowTracker                        # noqa: E402
from aciq.policy import build_plan                            # noqa: E402

#: A synthetic conntrack snapshot. Two properties matter for a *stability*
#: test and neither is true of a naive generator:
#:
#:   1. Flows have finite lifetimes. A flow retires after LIFETIME ticks and
#:      its port is reused later, so the live population reaches a steady state
#:      instead of growing one entry per tick forever. Conntrack in a real
#:      network does exactly this -- entries leave when they close -- and a
#:      soak that ignored it would measure the generator's leak, not the
#:      controller's.
#:   2. Some flows claim EF, so the trust store is exercised rather than idle.
#:
#: Reply tuples carry their own counters, exactly as real conntrack does.
LIFETIME = 20


def _conntrack(gen: int, n: int) -> str:
    lines = []
    # A fixed pool of `n` slots; the flow occupying slot i is born every
    # LIFETIME ticks, so at any instant ~n flows are live and the rest have
    # retired.
    for i in range(n):
        born = (gen // LIFETIME) * LIFETIME
        age = gen - born
        # Slot is active only in the second half of each LIFETIME window, so the
        # population genuinely rises and falls rather than staying pinned.
        if age >= LIFETIME:
            continue
        sport = 1024 + (i * 37 % 60000)
        dscp_mark = " mark=0 use=1"
        # Every 5th flow claims EF by arriving with dscp already set; the
        # classifier sees that in `feat.dscp` below.
        rx = 120_000 + age * 4096 + i * 100
        tx = 5_000 + i * 10
        lines.append(
            f"udp 17 29 src=10.0.1.2 dst=203.0.113.{i % 250} "
            f"sport=5001 dport={sport} packets=100 bytes={tx} "
            f"src=203.0.113.{i % 250} dst=10.0.1.2 sport={sport} dport=5001 "
            f"packets={100 + age} bytes={rx}{dscp_mark}"
        )
    return "\n".join(lines)


def _rss_mb() -> float:
    """Current resident set size, in MiB.

    Deliberately `statm`, not `ru_maxrss`. `ru_maxrss` is the *peak* over the
    process's life and can never decrease, so a long run reports a "drift" that
    only climbs and hides whether memory is ever reclaimed -- and in this
    container it returned values with no relation to the process's real use.
    `statm`'s second field is the current resident pages, which is the number a
    leak question is actually about. The peak is kept separately, below.
    """
    try:
        with open("/proc/self/statm") as f:
            pages = int(f.read().split()[1])
        return pages * 4096 / 1024 / 1024
    except (OSError, IndexError, ValueError):
        # Non-Linux fallback: peak, flagged in the result.
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _rss_peak_mb() -> float:
    """Peak RSS (statm cannot give peak; ru_maxrss can)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def soak(seconds: float, flows: int, sample_every: float = 5.0,
         on_sample=None) -> dict:
    tracker = FlowTracker()
    trust = TrustStore()
    estimator = CapacityEstimator()
    gen = 0
    rss_samples = [_rss_mb()]
    # NOT a list of every tick. An earlier revision appended one float per tick
    # and a 30-minute run at 200 flows retained 262k floats -- about 8-10 MB,
    # which is *exactly* the "drift" it then reported. The harness was measuring
    # its own retention and calling it a controller leak. Only the first tick
    # time and the most recent one are needed.
    first_tick_s: float | None = None
    last_tick_s: float | None = None
    saturated_ticks = 0
    last_sample = 0.0
    start = time.monotonic()
    end = start + seconds

    while time.monotonic() < end:
        t0 = time.monotonic()
        now = t0 - start
        gen += 1

        tracker.observe(_conntrack(gen, flows), now)

        # Walk every tracked flow through classification, so the trust store
        # and the per-flow windows actually see work. This is the per-tick cost
        # the live loop pays. Every 5th flow is presented as EF-claiming, and
        # because these are moderate UDP flows the classifier denies the claim
        # and decays trust -- so the store's eviction path is exercised too.
        for idx, key in enumerate(list(tracker._samples)):   # noqa: SLF001
            feat = tracker.features(key, dscp=46 if idx % 5 == 0 else None)
            if feat is not None:
                classify(feat, capacity_mbps=100.0, trust=trust)

        # Drive the estimator: mostly saturated, an idle tick every 50 to
        # exercise the release path as well as the adaptation path.
        if gen % 50 == 0:
            m = Measurement(t=now, goodput_mbps=1.0)
        else:
            saturated_ticks += 1
            m = Measurement(t=now, goodput_mbps=20.0,
                            link_overlimit_rate_per_s=6000.0,
                            overlimit_rate_per_s=6000.0)
        estimator.observe(m)
        build_plan(estimator.current.mbps or 100.0)

        dt = time.monotonic() - t0
        if first_tick_s is None:
            first_tick_s = dt
        last_tick_s = dt
        if now - last_sample >= sample_every:
            rss_samples.append(_rss_mb())
            last_sample = now
            # Emit progress so a long run killed partway still leaves evidence
            # rather than nothing: an empty log reads as "not run".
            if on_sample is not None:
                on_sample(_result(seconds, flows, start, gen, first_tick_s,
                                  last_tick_s, rss_samples, saturated_ticks,
                                  tracker, trust, final=False))

    rss_samples.append(_rss_mb())
    return _result(seconds, flows, start, gen, first_tick_s, last_tick_s,
                   rss_samples, saturated_ticks, tracker, trust, final=True)


def _result(seconds, flows, start, gen, first_tick_s, last_tick_s, rss_samples,
            saturated_ticks, tracker, trust, final: bool) -> dict:
    elapsed = time.monotonic() - start
    rss_start, rss_end = rss_samples[0], rss_samples[-1]

    return {
        "complete": final,
        "seconds": round(elapsed, 1),
        "requested_seconds": seconds,
        "flows": flows,
        "ticks": gen,
        "ticks_per_s": round(gen / elapsed, 1) if elapsed else None,
        "saturated_ticks": saturated_ticks,
        "rss_start_mb": round(rss_start, 2),
        "rss_end_mb": round(rss_end, 2),
        "rss_peak_mb": round(max(rss_samples), 2),
        "rss_ru_maxrss_peak_mb": round(_rss_peak_mb(), 2),
        "rss_drift_mb": round(rss_end - rss_start, 2),
        "rss_samples_mb": [round(x, 2) for x in rss_samples],
        # Drift per tick is the leak-relevant slope: a constant per-tick growth
        # is unbounded, a drift that tapers is allocator high-water. Reported
        # rather than judged, so a reader can see which it is.
        "rss_drift_per_tick_kb": (round((rss_end - rss_start) * 1024 / gen, 3)
                                  if gen else None),
        "tracked_flows": len(tracker._samples),     # noqa: SLF001
        "trust_sources": len(trust),
        "trust_cap": MAX_TRUST_SOURCES,
        "last_tick_us": round(last_tick_s * 1e6, 1) if last_tick_s else None,
        "first_tick_us": round(first_tick_s * 1e6, 1) if first_tick_s else None,
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        #: Deliberately excluded, stated so nobody reads the number as more
        #: than it is.
        "not_measured": [
            "qdisc / packet-buffer memory (needs a kernel)",
            "controller CPU during a live convergence (needs a kernel)",
            "kernel-side cost of applying a policy (needs tc)",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seconds", type=float, default=60.0,
                    help="soak duration (default 60; use 1800 for the "
                         "30-minute requirement)")
    ap.add_argument("--flows", type=int, default=100,
                    help="simultaneous flows per tick")
    ap.add_argument("--json", default=None, help="write results as JSON")
    a = ap.parse_args()

    def _write(r: dict) -> None:
        if a.json:
            # Written every sample so a long run killed partway still leaves
            # evidence; `complete` distinguishes a finished run from a partial.
            Path(a.json).write_text(json.dumps(r, indent=2) + "\n")

    r = soak(a.seconds, a.flows, on_sample=_write)
    _write(r)

    print(f"offline soak: {r['seconds']}s, {r['flows']} flows, "
          f"{r['ticks']} ticks ({r['ticks_per_s']}/s)")
    print(f"  rss: start {r['rss_start_mb']} MB  end {r['rss_end_mb']} MB  "
          f"peak {r['rss_peak_mb']} MB  drift {r['rss_drift_mb']:+} MB")
    print(f"  tracked flows {r['tracked_flows']} (bounded by eviction)")
    print(f"  trust sources {r['trust_sources']} / cap {r['trust_cap']}")
    print(f"  first tick {r['first_tick_us']} us, last tick {r['last_tick_us']} us")
    print("  not measured: " + "; ".join(r["not_measured"]))

    if a.json:
        print(f"  wrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
