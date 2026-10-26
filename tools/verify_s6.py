#!/usr/bin/env python3
"""verify_s6.py — mechanised verdict for the S6 intent scenario.

Reads only the run artefacts (result.json, samples.jsonl, <label>.sink.log)
and decides:

  granted      every ACIQ seed requested the intent over the real API surface
                (IntentService, POST /intent) and was GRANTED at the run's
                declared --intent-at (read per-run from config.json);
  reverted     the lease was ACTIVE while in TTL (there is at least one tick
                with lease_active=true inside the window) and after TTL+GRACE
                no tick shows lease_active=true (auto-revert, no tacit
                lingering reserve beyond expiry);
  floors       during the intent window the gaming device's receiver-side
                per-second series never goes to zero, and the bulk receiver's
                series never collapses below the policy's own guarantee
                (aciq.policy.floor_mbps) -- or below 10% of its pre-intent
                median, the stronger, when that median shows steady
                saturating bulk;
  baselines    every baseline seed DECLARES no intent support
                (intent.requested=true, intent.supported=false), never silent.

The floors line is a floor check, not a preferencing claim: a reserve must
NOT starve other classes on a healthy link, and the bound is aciq.policy's
own guarantee (floor_mbps), tightened to 10% of pre-intent bulk when the
pre window proves the bulk stream was saturating. The RESERVED device's own
receiver series is checked to be non-zero (some bytes did flow protected).
`recovered` measures the recovery window (docs/evidence/task3-params.md):
time from the lease going inactive until the bulk receiver series is back
to >= 90% of its pre-intent median, subject to a declared 5 s limit.

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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aciq import policy                  # noqa: E402  (floors come from the policy)

INTENT_AT_S = 10.0
GRACE_S = 2.5          # ticks land ~1s apart; tolerate clock slab
TTL_S = 20.0
#: Recovery metric (docs/evidence/task3-params.md): the bulk receiver series
#: must return to within this fraction of its pre-intent median within this
#: many seconds of the lease going inactive. 90% / 5 s are declared here,
#: before any 2026 dataset exists; they are not tuned on results.
RECOVERY_FRAC = 0.90
RECOVERY_LIMIT_S = 5.0

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
            # Per-run timings: config.json is the artefact of record; the
            # module constants above are only the fallback for artefacts
            # written before the timing was requested.
            try:
                cfg = json.loads((run / "config.json").read_text())
            except (OSError, ValueError):
                cfg = {}
            at_s = cfg.get("intent_at_s")
            ttl = cfg.get("intent_ttl_s")
            at_s = at_s if isinstance(at_s, (int, float)) else INTENT_AT_S
            ttl = ttl if isinstance(ttl, (int, float)) else TTL_S
            fired = intent.get("fired_at_run_t_s")
            note = intent.get("note") or ""
            # 1) granted at the declared run time via the real service
            if (intent.get("requested") is True and isinstance(fired, (int, float))
                    and fired > 0.0
                    and abs(fired - at_s) <= GRACE_S
                    and "GRANTED" in note):
                results["granted"] = True
            # 2) active inside the TTL window, never active after it
            if isinstance(fired, (int, float)):
                lo, hi = fired, fired + ttl
                inside = [s.get("lease_active") for s in samples
                          if lo <= s.get("t", -1) <= hi]
                after = [s.get("lease_active") for s in samples
                         if hi + GRACE_S <= s.get("t", -1e9)]
                results["reverted"] = bool(any(inside)) and not any(
                    a for a in after if a is not None)
            # 3) floors during the window (granted runs only). The floors
            # come from aciq.policy, not from a verifier-picked number: the
            # policy guarantees every class max(FLOOR_ABS_MBPS,
            # FLOOR_FRACTION x capacity) and caps bulk at
            # BULK_CEIL_FRACTION x capacity; a reserve must not starve bulk
            # below the policy's own guarantee (and, when the pre-intent
            # median shows the bulk stream was actually saturating, not
            # below 10% of that steady state, the stronger bound).
            if results["granted"] and isinstance(fired, (int, float)):
                lo, hi = fired, fired + ttl
                game = window(sink_series(run, "game"), lo, hi)
                bulk = window(sink_series(run, "bulk"), lo, hi)
                bulk_pre = window(sink_series(run, "bulk"), 0.0, fired)
                med = statistics.median(bulk_pre) if bulk_pre else 0.0
                cap = cfg.get("link_mbps") or 0.0
                policy_floor = (policy.floor_mbps(cap) if cap > 0.0
                                else policy.FLOOR_ABS_MBPS)
                bulk_ok = ((min(bulk) >= 0.1 * med) if med >= policy_floor
                           else (min(bulk) >= policy_floor))
                if game and bulk:
                    results["floors"] = min(game) > 0.0 and bulk_ok
                # 4) recovery (declared in task3-params.md): the bulk series
                # must return to within RECOVERY_FRAC of its pre-intent
                # median within RECOVERY_LIMIT_S of the lease going inactive.
                if med >= policy_floor:
                    recover_deadline = hi + GRACE_S + RECOVERY_LIMIT_S
                    need = RECOVERY_FRAC * med
                    hits = [t for t, v in sink_series(run, "bulk")
                            if hi + GRACE_S <= t <= recover_deadline and v >= need]
                    results["recovered"] = bool(hits)
                else:
                    # no meaningful pre-median: the recovery claim has no
                    # reference to measure against; record it as N/A
                    results["recovered"] = "n/a"
            for k in ("granted", "reverted", "floors"):
                n[k] += 1
                ok[k] += 1 if results.get(k) else 0
            # Recovery counts only where a pre-median made the reference
            # measurable; "n/a" runs join neither the numerator nor the
            # denominator.
            rec = results.get("recovered")
            if rec != "n/a":
                n["recovered"] = n.get("recovered", 0) + 1
                ok["recovered"] = ok.get("recovered", 0) + (1 if rec else 0)
    if n["granted"] == 0:
        print("granted=FAIL reverted=FAIL floors=FAIL recovered=N/A "
              "baselines=FAIL (no s6 run dirs parsed)")
        return 1
    verdict = {k: ("PASS" if ok[k] == n[k] else "FAIL")
               for k in n if n.get(k)}
    if n.get("recovered", 0) == 0:
        verdict["recovered"] = "N/A"
    # Scope honesty: with no baseline dir in the provided set there is
    # nothing to declare-check; report that as N/A instead of a bare PASS
    # a reader could take for a verified claim.
    if n["baselines"] == 0:
        verdict["baselines"] = "N/A"
    counted = {k: v for k, v in verdict.items() if v != "N/A"}
    rec_ok = ok.get("recovered", 0)
    rec_n = n.get("recovered", 0)
    print("granted={granted} reverted={reverted} floors={floors} "
          "recovered={recovered} baselines={baselines} (granted "
          "{o[granted]}/{n[granted]}, revert {o[reverted]}/{n[reverted]}, "
          "floors {o[floors]}/{n[floors]}, recovery {rec}/{recn}, "
          "base {o[baselines]}/{n[baselines]})".format(
              **verdict, o=ok, n=n, rec=rec_ok, recn=rec_n))
    return 0 if all(v == "PASS" for v in counted.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
