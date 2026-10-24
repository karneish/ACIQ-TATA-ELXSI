"""Fairness and starvation metrics that are COMPARABLE ACROSS MODES.

This module exists because of two audit findings (verification round
2026-10-23, findings DF-2 and the starvation check):

1. `MetricsFrame.fairness` (aciq/metrics.py, per-tick, counter-derived) is NOT
   comparable across systems. B0 and both CAKE arms run a single-class tree
   whose leaf handle is 1:50, so their whole link's counter is labelled
   `software_update` and the fairness index sees ONE class -- which trivially
   reports 1.0. ACIQ's sheet has two live classes out of seven and six rows of
   zero -- which reports ~0.5. Neither number says anything about fairness;
   they say counters were attributed differently.

2. Starvation must not be able to hide in an average. A bulk flow that is
   blocked for three seconds mid-run and healthy before and after has a
   healthy mean. The minimum over time is the number that catches it, and both
   numbers must come out of the same series, not from two different
   derivations.

The fix here computes fairness ONLY from the traffic generators' own reported
per-flow rates (workloads.json), which every mode records identically for the
same flows. Every mode runs the same scenario, so the input list is the same
shape for every mode: identical definition, identical support, comparable
values.

Queue-counter-derived per-class series (the ACIQ sheet in samples.jsonl) are
exposed here too, but are explicitly marked as ACIQ-only in consumers: they
cannot be compared against the baselines' aggregate-counter sheet.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

#: Workload kinds whose generator self-reports a packet-per-second rate.
_PPS_KINDS = frozenset({"call", "game"})
#: Everything else self-reports a sender throughput in Mbps (or bytes+s).
_MBPS_KINDS = frozenset({"bulk", "bulk_download", "video", "tv", "update",
                         "update_download", "backup"})

#: Labels that name TV-stream flows (tv1, tv2, ...). A scenario's three TV
#: streams are three SEPARATE flows for fairness purposes, exactly as they are
#: separate flows in the artefacts.
_TV_PREFIXES = ("tv",)

#: Workload kind (generator kind, or label for the TV prefix rule) ->
#: canonical TrafficClass value, spelled exactly as samples.jsonl's
#: per_class sheet keys them. Same alias intent as corrections.CLASS_ALIASES;
#: kept local so the fairness contract owns its own vocabulary.
_WORKLOAD_CLASS = {
    "call": "video_call_voice",
    "game": "interactive_gaming",
    "video": "adaptive_video_streaming",
    "tv": "adaptive_video_streaming",
    "bulk": "bulk_download",
    "bulk_download": "bulk_download",
    "update": "software_update",
    "update_download": "software_update",
    "backup": "cloud_backup",
    "cloud_backup": "cloud_backup",
}


def _kind_of(label: str, rep: dict[str, Any]) -> str:
    """Canonical workload kind for one flow's report.

    TV labels ("tv1", "tv2", ...) name separate flows of the video generator;
    everything else reports its kind directly.
    """
    kind = str(rep.get("kind") or rep.get("label") or "").lower()
    if label.startswith(_TV_PREFIXES) and any(ch.isdigit() for ch in label):
        return "tv"
    return kind


def assigned_classes(workloads: dict[str, Any]) -> list[str]:
    """The classes this scenario actually gave traffic to, from the workloads
    file — identically derivable for every mode, because every mode records
    the same workloads.json.

    This is the class scope the per-class minimum/starvation tables must
    use. A class no flow was assigned CANNOT be starved in a scenario:
    counting it as min 0 was the counter-attribution artefact (the samples
    sheet emits every class key for every mode), and it made even the
    pfifo baseline look like it starves `software_update` in a scenario
    that schedules none.
    """
    out: set[str] = set()
    for label, rep in sorted((workloads or {}).items()):
        if not isinstance(rep, dict):
            continue
        cls = _WORKLOAD_CLASS.get(_kind_of(label, rep))
        if cls:
            out.add(cls)
    return sorted(out)


def flow_rates(workloads: dict[str, Any]) -> dict[str, float]:
    """One rate per flow the scenario actually assigned, from the generator.

    `workloads` is a run directory's workloads.json (label -> generator
    self-report). Only labels present there contribute: a flow the scenario
    did not schedule is not "getting zero", it does not exist, and counting
    absent flows as zeroes was exactly how the old metric made ACIQ look
    arbitrarily starved.

    Raises no error on a missing rate: that flow is skipped and its absence is
    the caller's business (`MISSING.report` leaf). Fairness over n flows where
    1 flow failed to report is still reported as (n-1 flows), not faked with a
    zero.
    """
    rates: dict[str, float] = {}
    for label, rep in sorted((workloads or {}).items()):
        if not isinstance(rep, dict):
            continue
        rate = _rate_of(label, rep)
        if rate is None or rate < 0:
            continue
        rates[label] = float(rate)
    return rates


def _rate_of(label: str, rep: dict[str, Any]) -> float | None:
    kind = _kind_of(label, rep)
    if kind in _PPS_KINDS:
        got = rep.get("pps_achieved")
        return None if got is None else float(got)
    if kind in _MBPS_KINDS:
        got = rep.get("sender_mbps")
        return None if got is None else float(got)
    # Unknown kind: fall back to the throughput fields, preferring Mbps.
    if rep.get("sender_mbps") is not None:
        return float(rep["sender_mbps"])
    if rep.get("pps_achieved") is not None:
        return float(rep["pps_achieved"])
    return None


def jain(values: Sequence[float]) -> float | None:
    """(sum x)^2 / (n * sum x^2), over 2..n flows.

    Same definition as aciq.metrics.jain_fairness; kept as a thin delegation
    so there is exactly one place the definition lives. Deliberately the same
    None-on-nothing contract as there.
    """
    from .metrics import jain_fairness
    return jain_fairness(list(values))


def run_fairness(workloads: dict[str, Any]) -> float | None:
    """Fairness of ONE run, over per-flow generator rates.

    Cross-mode comparable by construction: the inputs are the flows the
    scenario assigned, which are identical across B0 / CAKE-static /
    CAKE-oracle / ACIQ for the same scenario and seed. Kernel-counter
    attribution (which is what made the per-tick sheet a trap) plays no part.
    """
    rates = flow_rates(workloads)
    if len(rates) < 2:
        return None
    return jain(list(rates.values()))


def per_class_series(samples: Iterable[dict[str, Any]], cls: str,
                     field: str = "goodput_mbps") -> list[tuple[float, float]]:
    """A class's metric over time from a run's samples.jsonl.

    Only ticks that actually record the class contribute; missing rows are
    gaps (returned only via `per_class_tick_cover`), never zeroes.
    """
    out: list[tuple[float, float]] = []
    for s in samples or ():
        row = (s.get("per_class") or {}).get(cls)
        if row is None:
            continue
        v = row.get(field)
        if isinstance(v, (int, float)):
            out.append((float(s["t"]), float(v)))
    return out


def per_class_tick_cover(samples: Iterable[dict[str, Any]], cls: str) -> int:
    """How many ticks recorded this class at all."""
    return len(per_class_series(samples, cls))


def minimum_over_time(series: Sequence[tuple[float, float]]) -> float | None:
    """The minimum value the series EVER reached.

    This is the starvation-sensitive cell: a flow that hits zero for even one
    tick reports 0.0 here, whatever its mean says. None only when the series
    is empty, so "never measured" and "measured zero" stay distinct.
    """
    if not series:
        return None
    return min(v for _, v in series)


def mean_over_time(series: Sequence[tuple[float, float]]) -> float | None:
    """Mean over the ticks that reported. The mean is reported NEXT TO the
    minimum on every table this project ships, precisely so nobody can argue
    the average away."""
    if not series:
        return None
    return sum(v for _, v in series) / len(series)


def starved_ticks(series: Sequence[tuple[float, float]],
                  threshold: float = 0.0) -> list[float]:
    """Timestamps at which the series was at or below `threshold`.

    A starvation verdict should be quotable as "starved at t=3.0..5.0", which
    needs the timestamps, not just a count.
    """
    return [t for t, v in series if v <= threshold]


# --------------------------------------------------------------------------
# demand-normalized fairness (fix 18)
#
# The raw flow-rate Jain above says "how equal are the deliveries", which
# answers the wrong question when demand is unequal: a 0.1 Mbps call sharing
# a link with an elastic bulk flow looks maximally UNfair there even though
# the call got everything it asked for and the bulk got the remainder. The
# metric below divides every flow's achieved rate by the demand the
# GENERATOR ITSELF declared in its report -- never an invented constant --
# and runs the same Jain over those satisfactions.
#
# Bluntly stated scope, because this is the part that gets misread later:
#   * call / game: demand = the flow's own `pps_requested`; achieved =
#     `pps_achieved`. Both self-reported, same unit, no conversion.
#   * video (tv): the generator sends a FIXED ladder schedule regardless of
#     congestion (testbed/workloads/video.py: the level walker is unaffected
#     by loss). Its demand is therefore deterministic: the time-average of
#     the ladder walk, computed from the report's own ladder/step_s/duration.
#   * bulk / update / backup: elastic, no declared demand; they are EXCLUDED
#     from this index (and the caller says so). They stay covered by the raw
#     run_fairness column and by the post-drop bulk cell.
# --------------------------------------------------------------------------

def video_demand_mbps(rep: dict[str, Any],
                      duration_s: float | None = None) -> float | None:
    """The time-averaged bitrate the ABR ladder walk DEMANDS.

    video.py walks the ladder unconditionally (level = (level+1) % len every
    --step seconds, starting at the first rung), so its demand is a
    deterministic schedule, derivable from the report alone: `ladder`,
    `step_s`, `elapsed_s`. Partial trailing segments are prorated; anything
    the report fails to carry returns None rather than a guessed constant.
    """
    ladder = rep.get("ladder")
    step = rep.get("step_s")
    dur = float(rep.get("elapsed_s") or duration_s or 0.0)
    if not isinstance(ladder, (list, tuple)) or len(ladder) < 2:
        return None
    rates = [float(x) for x in ladder]
    if not all(r > 0 for r in rates) or step is None or dur <= 0.0:
        return None
    step = float(step)
    if step <= 0.0:
        return None
    n = len(rates)
    steps_full = int(dur // step)
    rem = dur - steps_full * step
    total = 0.0
    for k in range(steps_full + (1 if rem > 0 else 0)):
        seg = rem if k == steps_full else step
        if seg <= 0.0:
            continue
        total += rates[k % n] * seg
    return total / dur


def _demand_of(label: str, rep: dict[str, Any]) -> float | None:
    """One flow's demand, in the same unit as its reported rate, or None
    when the flow is elastic / declared nothing."""
    kind = _kind_of(label, rep)
    if kind in _PPS_KINDS:
        got = rep.get("pps_requested")
        return None if got is None else float(got)
    if kind in ("video", "tv"):
        return video_demand_mbps(rep)
    return None


def flow_satisfactions(workloads: dict[str, Any]) -> dict[str, float]:
    """achieved/demand per flow that declares a demand, capped at 1.0.

    The cap is honesty about the metric, not optimisation: satisfaction says
    "di I get what I asked for", and a 52-packet blip of pps overshoot or a
    quantisation overstep in the video ladder must not read as
    over-servicing. Flows with no demand (elastic) are absent from the
    result, never present with a fake satisfaction.
    """
    out: dict[str, float] = {}
    for label, rep in sorted((workloads or {}).items()):
        if not isinstance(rep, dict):
            continue
        rate = _rate_of(label, rep)
        demand = _demand_of(label, rep)
        if rate is None or rate < 0 or demand is None or demand <= 0:
            continue
        out[label] = min(1.0, float(rate) / float(demand))
    return out


def run_demand_fairness(workloads: dict[str, Any]) -> float | None:
    """Jain over per-flow demand satisfactions; None below two flows.

    Comparability across modes holds by construction: every mode's
    workloads.json self-reports the same demands for the same flows, and the
    elastic flows each mode excludes are the same ones. It does NOT replace
    `run_fairness` -- a scenario whose assigned flows are ALL elastic (or a
    single interactive flow) has no demand-normalized index at all, and that
    absence must stay visible rather than fall back to something else.
    """
    sats = flow_satisfactions(workloads)
    if len(sats) < 2:
        return None
    return jain(list(sats.values()))
