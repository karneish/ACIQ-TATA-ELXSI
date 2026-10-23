#!/usr/bin/env python3
"""Split a run's latency into a transition tail and a steady state.

WHY THIS EXISTS

The report says ACIQ's p50 is ~1.2 ms but its p95 is ~65 ms, and that the slow
packets "sit in a window at the start". That claim was prose. This tool makes it
a measurement: it reads the per-packet `*.obs.jsonl` (RTT =
recv_mono_s - sent_mono_s, both taken by the *same* probe process on one
monotonic clock -- see `testbed/workloads/udpx.py`; it is a round-trip time, NOT
a one-way delay, because there are no synchronised clocks across the namespaces)
and reports p50/p95/p99
and max separately for

    * the transition  -- t <  TRANSITION_S after the first packet
    * the steady state -- t >= TRANSITION_S

for every seed, plus the pooled distribution. If the steady-state p95 is close
to the p50 and the transition p95 is the outlier, the tail is an adaptation
transient and not steady queueing -- which is a very different claim from "the
scheduler is slow".

    python3 tools/tail_analysis.py --gate congested --json OUT.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: gate -> (results-dir prefix, workload stem)
GATES = {
    "congested": ("host_gate_congested", "call"),
    "light": ("host_gate", "game"),
}
#: Where the transition ends. Chosen from the data, not asserted: the sweep
#: below shows steady-state p95 is flat for any cut in 4..8 s.
TRANSITION_S = 5.0


def _delays(path: Path) -> list[tuple[float, float]]:
    """(rtt_ms, t_s) for every replied packet, ordered by send time.

    `rtt_ms` is the round-trip time: the probe stamps `sent_mono_s` before
    `sendto` and `recv_mono_s` when the echo returns, both from the same process,
    so the difference is a round trip on one clock and not a one-way delay.
    """
    out: list[tuple[float, float]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("recv_mono_s") is None or r.get("sent_mono_s") is None:
            continue
        out.append(((r["recv_mono_s"] - r["sent_mono_s"]) * 1000.0, r["sent_mono_s"]))
    out.sort(key=lambda x: x[1])
    return out


def _pct(a: list[float], p: float) -> float | None:
    if not a:
        return None
    a = sorted(a)
    k = max(0, min(len(a) - 1, int(round(p / 100.0 * (len(a) - 1)))))
    return a[k]


def _stats(delays: list[float]) -> dict:
    return {
        "n": len(delays),
        "p50": _pct(delays, 50),
        "p95": _pct(delays, 95),
        "p99": _pct(delays, 99),
        "max": max(delays) if delays else None,
        "mean": statistics.fmean(delays) if delays else None,
    }


def analyse(gate: str, systems: tuple[str, ...] = ("aciq",),
            transition_s: float = TRANSITION_S) -> dict:
    prefix, stem = GATES[gate]
    seeds: dict[str, dict] = {}
    pooled_tr: list[float] = []
    pooled_ss: list[float] = []
    for system in systems:
        for obs in sorted((ROOT / "data" / f"{prefix}_{system}").glob(f"*/{stem}.obs.jsonl")):
            seed = obs.parent.name.rsplit("seed", 1)[-1]
            rows = _delays(obs)
            if not rows:
                continue
            t0 = rows[0][1]
            tr = [d for d, t in rows if (t - t0) < transition_s]
            ss = [d for d, t in rows if (t - t0) >= transition_s]
            seeds.setdefault(system, {})[seed] = {
                "transition": _stats(tr),
                "steady": _stats(ss),
            }
            if system == "aciq":
                pooled_tr += tr
                pooled_ss += ss
    return {
        "gate": gate,
        "workload": stem,
        "transition_s": transition_s,
        "per_seed": seeds,
        "pooled": {"transition": _stats(pooled_tr), "steady": _stats(pooled_ss)},
    }


def _row(name: str, s: dict) -> str:
    def f(x):
        return "n/a" if x is None else f"{x:.2f}"
    return (f"| {name} | {s['n']} | {f(s['p50'])} | {f(s['p95'])} | "
            f"{f(s['p99'])} | {f(s['max'])} |")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gate", choices=sorted(GATES), default="congested")
    ap.add_argument("--transition", type=float, default=TRANSITION_S)
    ap.add_argument("--json")
    a = ap.parse_args()

    r = analyse(a.gate, transition_s=a.transition)
    if not r["pooled"]["transition"]["n"] and not r["pooled"]["steady"]["n"]:
        print("no evidence", file=sys.stderr)
        return 1

    print(f"# Tail analysis: {r['gate']} "
          f"(transition = first {r['transition_s']:.0f} s)\n")
    for system in sorted(r["per_seed"]):
        print(f"## {system} pooled")
        print("| window | n | p50 | p95 | p99 | max |")
        print("|---|---|---|---|---|---|")
        tr = [v["transition"] for v in r["per_seed"][system].values()]
        ss = [v["steady"] for v in r["per_seed"][system].values()]
        # Recompute pooled per system from per-seed stats is lossy; fall back to
        # the ACIQ pool for aciq and per-seed means otherwise.
        if system == "aciq":
            print(_row("transition", r["pooled"]["transition"]))
            print(_row("steady", r["pooled"]["steady"]))
        else:
            print(_row("transition (min..max p95)",
                       {"n": sum(x["n"] for x in tr),
                        "p50": None, "p95": min(x["p95"] for x in tr if x["p95"]),
                        "p99": None, "max": max(x["max"] for x in tr if x["max"])}))
            print(_row("steady (min..max p95)",
                       {"n": sum(x["n"] for x in ss),
                        "p50": None, "p95": min(x["p95"] for x in ss if x["p95"]),
                        "p99": None, "max": max(x["max"] for x in ss if x["max"])}))
        print()
    print("## ACIQ per seed")
    print("| seed | trans p95 | trans max | steady p95 | steady max |")
    print("|---|---|---|---|---|")
    for seed, v in sorted(r["per_seed"].get("aciq", {}).items()):
        tr, ss = v["transition"], v["steady"]
        g = lambda d, k: "n/a" if d[k] is None else f"{d[k]:.2f}"
        print(f"| {seed} | {g(tr,'p95')} | {g(tr,'max')} | "
              f"{g(ss,'p95')} | {g(ss,'max')} |")

    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=2) + "\n")
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
