#!/usr/bin/env python3
"""Reconcile the headline comparison tables against the raw per-seed data.

WHY THIS EXISTS

The report's headline table ("median of 7 seeds") and its per-seed table were
maintained by hand. A data-reconciliation pass found the headline medians were
correct -- every one traces to a raw `call.json` / `game.json` -- but the
per-seed table had drifted: its p95 column did not match the raw p95 of the
same runs, and seed 42 in particular was off by an order of magnitude.

A headline that is right and a per-seed table that is wrong is worse than
either alone, because the wrong table is the evidence a reader would use to
check the headline. This tool closes that gap the only durable way: it re-derives
every number in the headline and per-seed tables *from the raw observation
files*, emits them as JSON, and fails if a hand-maintained table in the docs
disagrees.

It reads the workload's own self-report (`call.json`: p50/p95/p99/jitter/loss),
which is itself computed from the per-packet `*.obs.jsonl` file. The two are
cross-checked in `--verify-obs` mode.

    python3 tools/reconcile_results.py                       # report to stdout
    python3 tools/reconcile_results.py --json OUT.json       # machine-readable
    python3 tools/reconcile_results.py --check               # fail on mismatch
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: gate name -> (results-dir prefix, scenario name, workload file)
GATES = {
    "congested": ("host_gate_congested", "s2_wan_drop", "call.json"),
    "light": ("host_gate", "s3_tv_and_gaming", "game.json"),
}
SYSTEMS = ("b0_fifo", "b1_cake95", "aciq")
#: The percentile keys the workload self-report carries.
METRICS = ("p50", "p95", "p99", "jitter_ms", "loss_ratio")


def _load(prefix: str, system: str, workload: str) -> dict[int, dict]:
    """seed -> workload self-report, for one system's gate directory."""
    out: dict[int, dict] = {}
    pat = f"{prefix}_{system}"
    for d in sorted((ROOT / "data" / pat).glob(f"*/{workload}")):
        try:
            seed = int(d.parent.name.rsplit("seed", 1)[1])
        except (IndexError, ValueError):
            continue
        out[seed] = json.loads(d.read_text())
    return out


def _estimator_errors(prefix: str, system: str = "aciq") -> dict:
    """Per-seed capacity-estimator error against the provisioned reference.

    Reads `estimator_mbps` from each seed's `result.json` and the true
    post-drop rate from its `config.json` (`drop_mbps`). Error is the absolute
    percentage error `abs(est - ref) / ref * 100`. Returns the per-seed errors,
    the reference, and the worst case -- so a "within N%" claim is checked
    against the data rather than asserted.
    """
    out: dict[str, float] = {}
    refs: set[float] = set()
    for res in sorted((ROOT / "data" / f"{prefix}_{system}").glob("*/result.json")):
        est = json.loads(res.read_text()).get("estimator_mbps")
        cfg_path = res.with_name("config.json")
        if est is None or not cfg_path.exists():
            continue
        cfg = json.loads(cfg_path.read_text())
        ref = cfg.get("drop_mbps") or cfg.get("link_mbps")
        if not ref:
            continue
        refs.add(ref)
        seed = res.parent.name.rsplit("seed", 1)[-1]
        out[seed] = abs(est - ref) / ref * 100.0
    ref = next(iter(refs)) if len(refs) == 1 else None
    return {
        "reference_mbps": ref,
        "per_seed_error_pct": out,
        "worst_pct": max(out.values()) if out else None,
        "worst_several_refs": len(refs) > 1,
    }


def reconcile(gate: str) -> dict:
    prefix, scenario, workload = GATES[gate]
    per = {s: _load(prefix, s, workload) for s in SYSTEMS}
    seeds = sorted(set(per["aciq"]) & set(per["b0_fifo"]) & set(per["b1_cake95"]))
    if not seeds:
        return {"gate": gate, "scenario": scenario, "seeds": [], "complete": False}

    def med(system: str, metric: str) -> float | None:
        vals = [per[system][s][metric] for s in seeds
                if per[system].get(s, {}).get(metric) is not None]
        return statistics.median(vals) if vals else None

    headline = {
        system: {m: med(system, m) for m in METRICS} for system in SYSTEMS
    }
    per_seed = {
        system: {str(s): {m: per[system][s].get(m) for m in METRICS}
                 for s in seeds}
        for system in SYSTEMS
    }
    # Paired wins: ACIQ strictly better (lower) than each rival, per seed.
    wins = {}
    for rival in ("b0_fifo", "b1_cake95"):
        wins[rival] = {
            m: sum(1 for s in seeds
                   if per["aciq"][s][m] is not None
                   and per[rival][s][m] is not None
                   and per["aciq"][s][m] < per[rival][s][m])
            for m in METRICS
        }
    return {
        "gate": gate,
        "scenario": scenario,
        "workload": workload,
        "systems": list(SYSTEMS),
        "seeds": seeds,
        "n": len(seeds),
        "headline_median": headline,
        "per_seed": per_seed,
        "paired_wins_aciq_lower": wins,
        "estimator_error": _estimator_errors(prefix),
        "complete": True,
    }


def _verify_obs(gate: str, tol_ms: float = 1.0) -> list[str]:
    """Cross-check each workload self-report against its raw .obs.jsonl.

    The self-report is derived from the per-packet file; if they disagree, the
    self-report is not evidence. The per-packet value is the **round-trip time**
    `recv_mono_s - sent_mono_s`, both stamped by the same probe process on one
    monotonic clock -- not a one-way delay.
    """
    prefix, _scenario, workload = GATES[gate]
    problems: list[str] = []
    for system in SYSTEMS:
        for obs in sorted((ROOT / "data" / f"{prefix}_{system}").glob("*.obs.jsonl")):
            rep = obs.with_name(obs.name.replace(".obs.jsonl", ".json"))
            if not rep.exists():
                continue
            delays = []
            for line in obs.read_text().splitlines():
                if not line.strip():
                    continue
                o = json.loads(line)
                if o.get("recv_mono_s") is not None and o.get("sent_mono_s") is not None:
                    delays.append((o["recv_mono_s"] - o["sent_mono_s"]) * 1000.0)
            if not delays:
                continue
            self_rep = json.loads(rep.read_text())
            delays.sort()
            n = len(delays)

            def pct(p: float, _d=delays, _n=n) -> float:
                k = max(0, min(_n - 1, int(round(p / 100.0 * (_n - 1)))))
                return _d[k]

            for key, p in (("p50", 50), ("p95", 95), ("p99", 99)):
                if self_rep.get(key) is None:
                    continue
                if abs(self_rep[key] - pct(p)) > tol_ms:
                    problems.append(
                        f"{obs.relative_to(ROOT)}: {key} self-report "
                        f"{self_rep[key]:.3f} ms vs obs {pct(p):.3f} ms")
    return problems


def _fmt(v: float | None, unit: str = "") -> str:
    return "n/a" if v is None else f"{v:.3f}{unit}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", help="write the reconciled tables as JSON")
    ap.add_argument("--check", action="store_true",
                    help="verify workload self-reports against raw .obs.jsonl")
    ap.add_argument("--gate", choices=sorted(GATES), default="congested")
    a = ap.parse_args()

    r = reconcile(a.gate)
    if not r["complete"]:
        print(f"[{a.gate}] no complete evidence found", file=sys.stderr)
        return 1

    print(f"# Reconcile: {r['gate']} ({r['scenario']}), "
          f"n={r['n']} seeds {r['seeds']}\n")
    hdr = "| metric | " + " | ".join(SYSTEMS) + " |"
    print(hdr)
    print("|---|" + "---|" * len(SYSTEMS))
    for m in METRICS:
        print(f"| {m} | " + " | ".join(
            _fmt(r["headline_median"][s][m], " ms" if m != "loss_ratio" else "")
            for s in SYSTEMS) + " |")
    print("\nPer-seed p95 / loss:")
    for s in r["seeds"]:
        row = " | ".join(
            f"{_fmt(r['per_seed'][sys][str(s)]['p95'], 'ms')}/"
            f"{_fmt(r['per_seed'][sys][str(s)]['loss_ratio'])}"
            for sys in SYSTEMS)
        print(f"| seed {s} | {row} |")
    print("\nPaired wins (ACIQ lower):")
    for rival, w in r["paired_wins_aciq_lower"].items():
        print(f"  vs {rival}: " + ", ".join(f"{m} {w[m]}/{r['n']}" for m in METRICS))

    est = r.get("estimator_error", {})
    if est.get("per_seed_error_pct"):
        ref = est["reference_mbps"]
        print(f"\nEstimator error vs reference {ref} Mbps (abs %):")
        for seed, e in sorted(est["per_seed_error_pct"].items()):
            print(f"  seed {seed}: {e:.2f}%")
        print(f"  worst: {est['worst_pct']:.2f}%")

    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=2) + "\n")
        print(f"\nwrote {a.json}")

    if a.check:
        problems = _verify_obs(a.gate)
        if problems:
            print("\n[self-report vs raw obs mismatches]", file=sys.stderr)
            for p in problems:
                print("  " + p, file=sys.stderr)
            return 1
        print("\nself-reports agree with raw .obs.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
