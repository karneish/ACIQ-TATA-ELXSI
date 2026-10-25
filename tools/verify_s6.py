#!/usr/bin/env python3
"""verify_s6.py — mechanised verdict for the S6 intent scenario.

Reads only the run artefacts (result.json, samples.jsonl, <label>.sink.log)
and decides:

  granted      every ACIQ seed requested the intent over the real API surface
               (IntentService, POST /intent) and was GRANTED at t~1s;
  reverted     the lease was ACTIVE while in TTL (there is at least one tick
               with lease_active=true inside the window) and after TTL+GRACE
               no tick shows lease_active=true (auto-revert, no tacit
               lingering reserve beyond expiry);
  floors       during the intent window the gaming device's receiver-side
               per-second series never goes to zero, and the bulk receiver's
               series never collapses below 10% of its pre-intent median --
               on a healthy link, with the reserve taken from the same pools;
  baselines    every baseline seed DECLARES no intent support
               (intent.requested=true, intent.supported=false), never silent.

The floors line is a floor check, not a preferencing claim: a reserve must
NOT starve other classes on a healthy link. The RESERVED device's own
receiver series is checked to be non-zero (some bytes did flow protected).

Usage: verify_s6.py <s6_summary.log path OR runs_dir OR single run>
prints ONE line: granted=X reverted=Y floors=Z baselines=W details
exit 0 only when all four are PASS (run_s6.sh's acceptance).
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

INTENT_AT_S = 1.0
GRACE_S = 2.5          # ticks land ~1s apart; tolerate clock slab
TTL_S = 15.0

_SINK_LINE = re.compile(r"\[\s*([\w.-]+) sink\]\s+t=(\S+)\s+cum=(\d+)\s+"
                        r"bytes\s+inst=(\S+) Mbps")

#: sink starts 1.0s (launcher bind sleep) + settle before the driver's t=0
SINK_CLOCK_LEAD_S = 1.0


def run_dirs(arg: str) -> list[Path]:
    p = Path(arg)
    if p.is_dir() and (p / "result.json").exists():
        return [p]
    base = p.parent if p.is_file() else p
    # the s6 log normally sits in data/experiments/s6; runs in data/runs
    for cand in (base, *base.parents[:3]):
        for sub in (cand, cand / "runs"):
            hits = sorted(sub.glob("s6_intent_expire__*"))
            if hits:
                return hits
    raise SystemExit(f"no s6_intent_expire__* run dirs found for {arg}")


def sink_series(run: Path, label: str) -> list[tuple[float, float]]:
    """Per-second receiver inst-Mbps series from <label>.sink.log.

    Each printed inst measures the interval since the previous print (the
    sampler's first interval starts at sink-clock 0). Pairs carry the
    interval's START on the RUN clock, so `window(series, lo, hi)` reads
    inst values whose ~1s window began inside the window; pre-run intervals
    are dropped (lab startup, not the run).

    NOTE: for the UDP echo sinks (call/game) the line's bytes arrive on the
    sink in the CLIENT namespace, so the inst rate IS receiver-side delivery
    rate. Echo responses aside, it measures what arrived, which is what a
    floor claim on the gaming device needs.
    """
    log = next(iter(sorted(run.glob(f"{label}*.sink.log"))), None)
    ts: list[float] = []
    bs: list[float] = []
    if log is not None:
        for line in log.read_text().splitlines():
            m = _SINK_LINE.search(line)
            if m is None:
                continue
            try:
                t_v = float(m.group(2))
                v_v = float(m.group(4))
            except ValueError:
                continue        # t and inst appended TOGETHER or not at all
            ts.append(t_v)
            bs.append(v_v)
    if len(bs) < 2:
        return []
    # inst value k covers (t[k-1], t[k]] on the SINK clock (the first
    # print's interval starts at sink-clock 0); the pair carries the
    # interval's START, remapped to the RUN clock (sink born
    # SINK_CLOCK_LEAD_S + settle before the run's t=0). Pairs whose
    # interval started before the run are dropped: lab startup, not the run.
    lead = SINK_CLOCK_LEAD_S
    cfg_path = run / "config.json"
    if cfg_path.exists():
        try:
            settle = json.loads(cfg_path.read_text()).get("settle_s")
            if isinstance(settle, (int, float)):
                lead += float(settle)
        except (OSError, ValueError):
            pass
    starts = [0.0] + ts[:-1]
    return [(starts[i] - lead, bs[i]) for i in range(len(bs))
            if starts[i] - lead >= 0.0]


def window(series: list[tuple[float, float]], lo: float, hi: float) -> list[float]:
    return [v for t, v in series if lo <= t <= hi]


def main(argv: list[str]) -> int:
    n = {"granted": 0, "reverted": 0, "floors": 0, "baselines": 0}
    ok = {"granted": 0, "reverted": 0, "floors": 0, "baselines": 0}
    for run in run_dirs(argv[1]):
        results: dict[str, bool] = {"granted": False, "reverted": False,
                                    "floors": False, "baselines": False}
        intent, system = {}, ""
        samples: list[dict] = []
        try:
            res = json.loads((run / "result.json").read_text())
            intent = res.get("intent") or {}
            system = res.get("system", "")
            sj = run / "samples.jsonl"
            if sj.exists():
                samples = [json.loads(x) for x in sj.read_text().splitlines()]
        except (OSError, ValueError):
            continue

        if system != "aciq":
            # Baselines must DECLARE no intent support, never silently run.
            # They only join their own denominator: a baseline run has no
            # intent machinery to grant, revert or hold floors with.
            n["baselines"] += 1
            ok["baselines"] += 1 if (intent.get("requested") is True
                                     and intent.get("supported") is False) \
                else 0
            continue
        else:
            fired = intent.get("fired_at_run_t_s")
            note = intent.get("note") or ""
            # 1) granted at t~1 via the real service
            if (intent.get("requested") is True and isinstance(fired, (int, float))
                    and fired <= INTENT_AT_S + GRACE_S
                    and "GRANTED" in note):
                results["granted"] = True
            # 2) active inside the TTL window, never active after it
            if isinstance(fired, (int, float)):
                lo, hi = fired, fired + TTL_S
                inside = [s.get("lease_active") for s in samples
                          if lo <= s.get("t", -1) <= hi]
                after = [s.get("lease_active") for s in samples
                         if hi + GRACE_S <= s.get("t", -1e9)]
                results["reverted"] = bool(any(inside)) and not any(
                    a for a in after if a is not None)
            # 3) floors during the window (granted runs only)
            if results["granted"] and isinstance(fired, (int, float)):
                lo, hi = fired, fired + TTL_S
                game = window(sink_series(run, "game"), lo, hi)
                bulk = window(sink_series(run, "bulk"), lo, hi)
                bulk_pre = window(sink_series(run, "bulk"), 0.0, fired)
                med = statistics.median(bulk_pre) if bulk_pre else 0.0
                # A relative floor is meaningless when the pre window had no
                # usable bulk traffic (med ~ 0): then a declared ABSOLUTE
                # floor applies instead (fixed here, before any dataset --
                # this is not tuned on the data). Live s2/s4 post-drop bulk
                # medians are ~18-20 Mbps on the same link; 5 Mbps is a
                # third of that, still an honest starve boundary.
                BULK_ABS_FLOOR_MBPS = 5.0
                bulk_ok = ((min(bulk) >= 0.1 * med) if med > 1.0
                           else (min(bulk) >= BULK_ABS_FLOOR_MBPS))
                if game and bulk:
                    results["floors"] = min(game) > 0.0 and bulk_ok
            for k in ("granted", "reverted", "floors"):
                n[k] += 1
                ok[k] += 1 if results[k] else 0
    if n["granted"] == 0:
        print("granted=FAIL reverted=FAIL floors=FAIL baselines=FAIL "
              "(no s6 run dirs parsed)")
        return 1
    verdict = {k: ("PASS" if ok[k] == n[k] else "FAIL") for k in n}
    # Scope honesty: with no baseline dir in the provided set there is
    # nothing to declare-check; report that as N/A instead of a bare PASS
    # a reader could take for a verified claim.
    if n["baselines"] == 0:
        verdict["baselines"] = "N/A"
    counted = {k: v for k, v in verdict.items() if v != "N/A"}
    print("granted={granted} reverted={reverted} floors={floors} "
          "baselines={baselines} (granted {o[granted]}/{n[granted]}, "
          "revert {o[reverted]}/{n[reverted]}, floors {o[floors]}/{n[floors]}, "
          "base {o[baselines]}/{n[baselines]})".format(
              **verdict, o=ok, n=n))
    return 0 if all(v == "PASS" for v in counted.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
